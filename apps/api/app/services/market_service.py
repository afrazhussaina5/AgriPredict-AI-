"""Market price service (Phase 6).

Responsibilities
----------------
* **Fetch** - pull official daily market prices from data.gov.in (Agmarknet
  variety-wise daily market prices resource) and normalise them into the
  :class:`MarketPrice` model.
* **Store** - upsert prices so the public board can serve the last successful
  import without hitting the upstream API on every request.
* **Project** - filter by commodity/grade/district and return a public
  projection that always carries source, date and freshness.

Design rules
------------
* ``GET /market/prices`` is read-only and public. It never decides that a
  number is verified; it only reports what the import pipeline successfully
  wrote.
* Prices are ingested in batches and upserted on the unique key
  (commodity, grade, mandi, district, state, date, unit). A missing grade is
  stored as NULL and rendered as "not graded".
* The freshness timestamp is the *last successful extraction*, not the latest
  business-day observation. The UI shows it next to every row so nobody
  mistakes a stale snapshot for a live quote.
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, UTC
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import AppError, RateLimitError
from ..core.logging import get_logger
from ..models import (
    Commodity,
    CommodityGrade,
    District,
    Mandi,
    MarketPrice,
    MarketPriceCache,
    MeasurementUnit,
    ReferenceSource,
    State,
)
from ..repositories import ReferenceRepository

logger = get_logger(__name__)

# Official data.gov.in resource ID for the Agmarknet variety-wise market
# prices (government data, free, no key required for the public resource).
MARKET_RESOURCE_ID = os.environ.get(
    "MARKET_API_RESOURCE_ID",
    "9ef84268-d588-465a-a308-a864a43d0070",
)

MARKET_API_URL = os.environ.get(
    "MARKET_API_URL",
    "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070",
)

# A single extract of a business day is the unit we normalise.
EXTRACT_CACHE_SECONDS = 300  # 5 minutes

# How many rows one extract may pull, and how many it asks for per page.
# The public board covers every mandi in the resource, so this is a ceiling on
# one run rather than the size of the import: raise it for a full backfill.
MAX_EXTRACT_ROWS = int(os.environ.get("MARKET_MAX_ROWS", "20000"))
PAGE_SIZE = int(os.environ.get("MARKET_PAGE_SIZE", "500"))
# Total wall clock allowed for one extract. A government portal that stalls
# must not hold a request open forever.
FETCH_DEADLINE_SECONDS = 120
# How many rows of an extract the cache keeps. Beyond this the cache holds a
# sample only, and fetch_latest re-polls rather than returning a partial batch.
CACHE_SAMPLE_ROWS = 20

# Grades shipped by the source. A/B/C are the official Indian grading scheme.
# UNKNOWN is stored when the source row has no grade column.
SUPPORTED_GRADES = {"A", "B", "C", "UNKNOWN"}

# Rows we would hand to the UI after joining to references. The projection
# always carries provenance and freshness so nobody mistakes a stale snapshot
# for a live quote.
_ROW_FIELDS = [
    "commodity_code",
    "commodity_name",
    "grade",
    "mandi_name",
    "mandi_code",
    "district_name",
    "state_name",
    "market_date",
    "modal_price",
    "unit_code",
    "arrivals",
    "source_name",
    "imported_at",
]

# Cap on a page of the upstream resource, so a runaway response cannot pull
# the whole archive into memory.
MAX_EXTRACT_ROWS = 200


@dataclass(frozen=True)
class ExtractedBatch:
    rows: list[dict]
    fetched_at: datetime
    errors: list[str] = field(default_factory=list)
    # True when ``rows`` came from the extract cache rather than upstream.
    from_cache: bool = False
    # How many rows the cached extract really held. When this is larger than
    # len(rows) the cache only stored a sample, so the caller must NOT treat
    # rows as the complete extract - it has to re-poll upstream.
    cached_row_count: int = 0

    @property
    def is_complete(self) -> bool:
        """True when ``rows`` is the whole extract, not a cached sample."""
        return not self.from_cache or self.cached_row_count == len(self.rows)


def _normalise_row(item: dict) -> dict:
    """Map one government row onto our field vocabulary."""
    def _get(key: str, default: str | None = None) -> str | None:
        value = item.get(key)
        if value is None or str(value).strip() == "":
            return default
        return str(value).strip()

    # Government resource columns (common convention): Commodity,
    # CommodityName, Variety, Grade, MandiName, MandiDistr, District, State,
    # MarketDate, ModalPrice, ArrivalPrice, MinPrice, MaxPrice, Unit,
    # ArrivalQty.
    return {
        "commodity": _get("Commodity") or _get("CommodityName"),
        "commodity_code": _get("CommodityCode") or _get("Commodity"),
        "grade": _get("Grade"),
        "mandi": _get("MandiName") or _get("Mandi"),
        "mandi_code": _get("MandiCode") or _get("MandiName"),
        "district": _get("MandiDistr") or _get("District") or _get("DistrictName"),
        "district_code": _get("MandiDistCode") or _get("DistrictCode"),
        "state": _get("State") or _get("StName") or _get("StateName"),
        "state_code": _get("StateCode") or _get("StCode"),
        "date": _get("MarketDate") or _get("Date") or _get("MarketDay"),
        "modal_price": _get("ModalPrice") or _get("Modal"),
        "arrivals": _get("ArrivalQty") or _get("Arrivals"),
        "unit": _get("Unit") or _get("UnitName"),
        "unit_code": _get("UnitCode") or _get("Unit"),
    }


def _parse_market_date(value: str | None) -> date | None:
    """Parse the date formats the government resource is known to ship."""
    if not value:
        return None
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


class MarketService:
    """Fetch, store and project official market prices."""

    # ------------------------------------------------------------------ fetch

    async def fetch_latest(self, session: AsyncSession) -> ExtractedBatch:
        """Return a normalised batch from the official Agmarknet resource.

        The extract cache exists to stop us hammering a government portal, not
        to satisfy a caller with a partial result. If the cached extract was
        larger than the sample we stored, the batch is reported as incomplete
        and we poll upstream again - otherwise a second import within
        ``EXTRACT_CACHE_SECONDS`` would quietly write only the sample.
        """
        now = datetime.now(UTC)
        cached = await self._read_cache(session)
        if cached is not None and (
            now - cached.fetched_at
        ).total_seconds() < EXTRACT_CACHE_SECONDS:
            if cached.is_complete:
                return cached
            logger.info(
                "Cached extract holds a sample of %d/%d rows; re-polling upstream.",
                len(cached.rows),
                cached.cached_row_count,
            )

        rows: list[dict] = []
        errors: list[str] = []

        try:
            payload = await self._fetch_payload()
        except AppError as exc:
            errors.append(f"fetch_failed: {exc.message}")
            payload = None
        except Exception as exc:  # noqa: BLE001 - upstream must never 500 us
            logger.warning("Market fetch failed: %s", type(exc).__name__)
            errors.append(f"fetch_failed: {type(exc).__name__}")
            payload = None

        if payload is not None:
            rows = self._normalise(payload)
            if not rows:
                errors.append("no_rows_returned")

        fetched_at = datetime.now(UTC)
        batch = ExtractedBatch(rows, fetched_at, errors)
        await self._write_cache(session, batch)
        return batch

    async def _fetch_payload(self) -> dict:
        """Page through the resource and return every row it ships.

        The board must cover *all* mandis, so this walks the whole result set
        rather than taking the first page. It stops on the first of: a short
        page (we have reached the end), an empty page, a repeated page (an
        upstream that ignores ``offset`` would otherwise loop), or the row
        ceiling. Duplicates are dropped on the business-day key, so re-reading
        an overlapping page is harmless.
        """
        headers = {
            "Accept": "application/json",
            "User-Agent": "AgriPredict-AI-market/1.0 (public data.gov.in resource)",
        }
        page_size = min(PAGE_SIZE, MAX_EXTRACT_ROWS)
        params: dict[str, str] = {"format": "json", "limit": str(page_size)}
        captured: list[dict] = []
        seen: set[str] = set()

        deadline = time.monotonic() + FETCH_DEADLINE_SECONDS
        async with asyncio.timeout_at(deadline):
            from aiohttp import ClientSession

            async with ClientSession() as session:
                previous_page_signature: tuple = ()
                while len(captured) < MAX_EXTRACT_ROWS:
                    async with session.get(
                        MARKET_API_URL, headers=headers, params=params
                    ) as response:
                        if response.status == 429:
                            raise RateLimitError(
                                "Market API rate-limited; retry later."
                            )
                        response.raise_for_status()
                        payload = await response.json()

                    page = self._flatten(payload)

                    # An upstream that ignores `offset` would hand back the
                    # same page for ever; stop instead of spinning.
                    signature: tuple = tuple(
                        str(item.get(key, ""))
                        for item in page[:1]
                        for key in ("Commodity", "MandiName", "MarketDate")
                    )
                    if not page or signature == previous_page_signature:
                        break
                    previous_page_signature = signature

                    added = 0
                    for item in page:
                        # Raw government rows go in untouched: normalisation
                        # happens exactly once, in _normalise.
                        row_signature = self._raw_signature(item)
                        if row_signature in seen:
                            continue
                        seen.add(row_signature)
                        captured.append(item)
                        added += 1

                    # A short page means we reached the end of the resource.
                    if len(page) < page_size:
                        break
                    if added == 0:
                        break
                    params["offset"] = str(int(params.get("offset", "0")) + len(page))

        return {"result": captured}

    @staticmethod
    def _raw_signature(item: dict) -> str:
        """Identity of an un-normalised source row, for de-duplication."""
        return "|".join(
            f"{key}={value}" for key, value in sorted(item.items()) if value != ""
        )

    @staticmethod
    def _row_key(row: dict) -> tuple:
        """The business-day observation a price row is uniquely known by."""
        return (
            row.get("commodity_code"),
            row.get("grade"),
            row.get("mandi_code"),
            row.get("district"),
            row.get("state"),
            row.get("date"),
            row.get("unit_code"),
        )

    @staticmethod
    def _flatten(payload: Any) -> list[dict]:
        """Accept either a bare list of records or the data.gov.in envelope."""
        if isinstance(payload, list):
            return [dict(item) for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("result", "data", "records"):
                if key in payload and isinstance(payload[key], list):
                    return [
                        dict(item) for item in payload[key] if isinstance(item, dict)
                    ]
            for value in payload.values():
                if isinstance(value, dict):
                    nested = MarketService._flatten(value)
                    if nested:
                        return nested
        return []

    @staticmethod
    def _normalise(payload: dict) -> list[dict]:
        """Turn the raw government payload into a uniform dict per row.

        Rows are de-duplicated on the business-day key, because two mandis may
        report the same commodity+grade+day and the board must show one row
        per observation, not two copies of it.
        """
        out: list[dict] = []
        seen: set[tuple] = set()
        for item in payload.get("result", []) or []:
            try:
                row = _normalise_row(item)
            except ValueError:
                continue
            key = MarketService._row_key(row)
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
        return out

    # ---------------------------------------------------------------- storage

    async def _write_cache(self, session: AsyncSession, batch: ExtractedBatch) -> None:
        """Persist extract metadata so freshness is cheap to report.

        Only metadata plus a bounded sample of rows is stored; the full rows
        live in ``market_prices``. The cache row is a get-then-set rather than
        a dialect-specific upsert, so the same code runs on SQLite (tests) and
        PostgreSQL (production).

        ``row_count`` is stored alongside the sample precisely so a cache hit
        can tell "this is everything" from "this is the first 20 of 40".
        """
        payload = json.dumps(
            {
                "rows": batch.rows[:CACHE_SAMPLE_ROWS],
                "row_count": len(batch.rows),
                "fetched_at": batch.fetched_at.isoformat(),
                "errors": batch.errors,
            }
        )
        result = await session.execute(
            select(MarketPriceCache).where(MarketPriceCache.key == "latest_extract")
        )
        cache = result.scalar_one_or_none()
        if cache is None:
            session.add(MarketPriceCache(key="latest_extract", value=payload))
        else:
            cache.value = payload
        await session.commit()

    async def _read_cache(self, session: AsyncSession) -> ExtractedBatch | None:
        """Return the cached extract, or None when it cannot be trusted.

        A cache hit whose stored sample is smaller than its recorded row count
        is reported as ``from_cache`` with ``cached_row_count`` set, so
        :meth:`fetch_latest` re-polls instead of silently importing a sample.
        """
        result = await session.execute(
            select(MarketPriceCache.value).where(
                MarketPriceCache.key == "latest_extract"
            )
        )
        raw = result.scalar_one_or_none()
        if not raw:
            return None
        try:
            payload = json.loads(raw)
            fetched_at = datetime.fromisoformat(payload["fetched_at"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None
        rows = payload.get("rows", [])
        return ExtractedBatch(
            rows,
            fetched_at,
            payload.get("errors", []),
            from_cache=True,
            cached_row_count=int(payload.get("row_count", len(rows))),
        )

    # ------------------------------------------------------------------ store

    async def _persist_rows(self, session: AsyncSession, rows: list[dict]) -> int:
        """Upsert one batch of market prices. Returns rows written."""
        now = datetime.now(UTC)
        repository = ReferenceRepository(session)
        inserted = 0
        for row in rows:
            market_date = _parse_market_date(row.get("date"))
            if market_date is None:
                logger.warning("Market price skipped: unparseable date %r",
                               row.get("date"))
                continue
            try:
                state = await repository.get_or_create_state(
                    self._required(row, "state"), row.get("state_code")
                )
                district = await repository.get_or_create_district(
                    self._required(row, "district"),
                    row.get("district_code"),
                    state,
                )
                mandi = await repository.get_or_create_mandi(
                    self._required(row, "mandi"),
                    row.get("mandi_code"),
                    district,
                    row.get("has_storage"),
                )
                commodity = await repository.get_or_create_commodity(
                    self._required(row, "commodity"), row.get("commodity_code")
                )
                grade = await repository.get_or_create_grade(
                    row.get("grade"), commodity
                )
                unit = await repository.get_or_create_unit(
                    self._required(row, "unit"), row.get("unit_code")
                )
            except (KeyError, ValueError) as exc:
                logger.warning("Market price skipped: %s", exc)
                continue

            source = await repository.get_or_create_source(
                "data.gov.in", "India Ministry of Agriculture (Agmarknet)"
            )

            record = MarketPrice(
                commodity_id=commodity.id,
                grade_id=grade.id if grade else None,
                mandi_id=mandi.id,
                district_id=district.id,
                state_id=state.id,
                market_date=market_date,
                unit_id=unit.id,
                modal_price=self._to_decimal(row.get("modal_price")),
                arrivals=self._to_int(row.get("arrivals")),
                source_id=source.id,
                imported_at=now,
            )
            await self._upsert_price(session, record)
            inserted += 1
        await session.commit()
        return inserted

    @staticmethod
    def _required(row: dict, key: str) -> str:
        value = row.get(key)
        if value is None or str(value).strip() == "":
            raise KeyError(f"missing required field '{key}'")
        return str(value).strip()

    @staticmethod
    async def _upsert_price(session: AsyncSession, record: MarketPrice) -> None:
        """Insert or refresh one price on the business-day unique key.

        Re-importing the same day must never duplicate a row: the unique
        constraint covers commodity+grade+mandi+district+state+date+unit, so a
        match means "the same observation seen again" and only the numbers
        move.
        """
        existing = (
            await session.execute(
                select(MarketPrice).where(
                    MarketPrice.commodity_id == record.commodity_id,
                    MarketPrice.grade_id == record.grade_id,
                    MarketPrice.mandi_id == record.mandi_id,
                    MarketPrice.district_id == record.district_id,
                    MarketPrice.state_id == record.state_id,
                    MarketPrice.market_date == record.market_date,
                    MarketPrice.unit_id == record.unit_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(record)
            return
        existing.modal_price = record.modal_price
        existing.arrivals = record.arrivals
        existing.source_id = record.source_id
        existing.imported_at = record.imported_at

    # ------------------------------------------------------------ references

    @staticmethod
    def _to_decimal(value: str | None) -> Decimal | None:
        if value is None or str(value).strip() == "":
            return None
        try:
            return Decimal(str(value).replace(",", "").strip())
        except InvalidOperation:
            return None

    @staticmethod
    def _to_int(value: str | None) -> int | None:
        if value is None or str(value).strip() == "":
            return None
        try:
            return int(str(value).replace(",", "").strip())
        except ValueError:
            return None

    # ---------------------------------------------------------------- project

    async def public_rows(
        self,
        session: AsyncSession,
        commodity_id: int | None = None,
        grade_id: int | None = None,
        district_id: int | None = None,
    ) -> list[dict]:
        """Public projection. Every row carries provenance and freshness."""
        statement = (
            select(MarketPrice)
            .join(Commodity, MarketPrice.commodity_id == Commodity.id)
            .join(
                CommodityGrade,
                MarketPrice.grade_id == CommodityGrade.id,
                isouter=True,  # a missing grade is "not graded", not absent
            )
            .join(Mandi, MarketPrice.mandi_id == Mandi.id)
            .join(District, MarketPrice.district_id == District.id)
            .join(State, MarketPrice.state_id == State.id)
            .join(MeasurementUnit, MarketPrice.unit_id == MeasurementUnit.id)
            .join(ReferenceSource, MarketPrice.source_id == ReferenceSource.id)
        )
        if commodity_id is not None:
            statement = statement.where(MarketPrice.commodity_id == commodity_id)
        if grade_id is not None:
            statement = statement.where(MarketPrice.grade_id == grade_id)
        if district_id is not None:
            statement = statement.where(MarketPrice.district_id == district_id)
        statement = statement.order_by(MarketPrice.market_date.desc())

        rows = (await session.execute(statement)).scalars().all()
        return [self._project(row) for row in rows]

    def _project(self, row: MarketPrice) -> dict:
        grade = row.grade.code if row.grade else "UNKNOWN"
        return {
            "commodity_code": row.commodity.code,
            "commodity_name": row.commodity.name,
            "grade": grade,
            "mandi_name": row.mandi.name,
            "mandi_code": row.mandi.code,
            "district_name": row.district.name,
            "state_name": row.state.name,
            "market_date": row.market_date.isoformat(),
            "modal_price": str(row.modal_price)
            if row.modal_price is not None
            else None,
            "unit_code": row.unit.code,
            "arrivals": row.arrivals,
            "source_name": row.source.name,
            "imported_at": row.imported_at.isoformat(),
        }

    async def list_commodities(self, session: AsyncSession) -> list[dict]:
        rows = await session.execute(
            select(Commodity).where(Commodity.is_active.is_(True)).order_by(Commodity.name)
        )
        return [
            {"code": r.code, "name": r.name, "category": r.category}
            for r in rows.scalars().all()
        ]

    async def list_grades(self, session: AsyncSession) -> list[dict]:
        """Every grade that can appear on the board, with its real id.

        ``id`` is what ``GET /market/prices?grade_id=`` filters on, so the
        public board can offer a working grade filter. Only grades actually
        referenced by a stored price are returned: a grade nobody has ever
        imported would only widen the filter with dead options.
        """
        statement = (
            select(CommodityGrade, func.count(MarketPrice.id))
            .join(MarketPrice, MarketPrice.grade_id == CommodityGrade.id)
            .where(CommodityGrade.is_active.is_(True))
            .group_by(CommodityGrade.id)
            .order_by(CommodityGrade.code)
        )
        result = await session.execute(statement)
        grades: list[dict] = []
        for grade, price_count in result.all():
            commodity = grade.commodity
            grades.append(
                {
                    "id": grade.id,
                    "code": grade.code,
                    "name": grade.name,
                    "commodity_id": commodity.id if commodity else None,
                    "commodity_code": commodity.code if commodity else None,
                    "row_count": price_count,
                }
            )
        return grades

    async def mandi_rows(self, session: AsyncSession, mandi_id: int) -> list[dict]:
        rows = (
            await session.execute(
                select(MarketPrice)
                .where(MarketPrice.mandi_id == mandi_id)
                .order_by(MarketPrice.market_date.desc())
            )
        ).scalars().all()
        return [self._project(r) for r in rows]

    async def import_dates(self, session: AsyncSession) -> datetime | None:
        row = await session.execute(
            select(func.max(MarketPrice.imported_at))
        )
        return row.scalar()


__all__ = [
    "EXTRACT_CACHE_SECONDS",
    "ExtractedBatch",
    "MARKET_API_URL",
    "MARKET_RESOURCE_ID",
    "MarketService",
    "SUPPORTED_GRADES",
]
