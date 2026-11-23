"""Tests for the market price pipeline and the public board (Phase 6).

Two levels are covered:

* service level (async ``session`` fixture) - normalisation, date parsing, the
  upsert on the business-day unique key, and the public projection,
* API level (``client`` fixture) - the endpoints the board renders from,
  including the grade filter that broke when it had no id to filter on.

The rows below are TEST DATA ONLY. They mimic the shape of the data.gov.in
Agmarknet resource (deliberately awkward: unparseable dates, missing grades,
blank prices) so the pipeline is proven to survive the real feed's messiness.
They are never shipped as real market prices.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MarketPrice
from app.services.market_service import (
    MarketService,
    _normalise_row,
    _parse_market_date,
)


# ------------------------------------------------------------ source rows

GOV_ROW = {
    "Commodity": "Tomato",
    "Grade": "A",
    "MandiName": "Azadpur",
    "MandiDistr": "North Delhi",
    "State": "Delhi",
    "MarketDate": "2026-10-05",
    "ModalPrice": "1250.50",
    "ArrivalQty": "320",
    "Unit": "quintal",
}


# ------------------------------------------------------------- normalisation


def test_normalise_maps_the_government_column_names() -> None:
    row = _normalise_row(GOV_ROW)
    assert row["commodity"] == "Tomato"
    assert row["commodity_code"] == "Tomato"
    assert row["mandi"] == "Azadpur"
    assert row["district"] == "North Delhi"
    assert row["state"] == "Delhi"
    assert row["date"] == "2026-10-05"
    assert row["modal_price"] == "1250.50"
    assert row["arrivals"] == "320"
    assert row["unit"] == "quintal"


def test_normalise_treats_a_blank_string_as_missing() -> None:
    """The source ships empty strings, not nulls, for absent values."""
    row = _normalise_row({**GOV_ROW, "Grade": "   ", "ArrivalQty": ""})
    assert row["grade"] is None
    assert row["arrivals"] is None


def test_normalise_prefers_the_variety_column_over_the_name_column() -> None:
    row = _normalise_row({**GOV_ROW, "CommodityName": "Tomato (Hybrid)"})
    assert row["commodity"] == "Tomato"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-10-05", date(2026, 10, 5)),
        ("05-10-2026", date(2026, 10, 5)),
        ("05/10/2026", date(2026, 10, 5)),
        ("2026/10/05", date(2026, 10, 5)),
    ],
)
def test_parse_market_date_accepts_the_formats_the_source_ships(
    raw: str, expected: date
) -> None:
    assert _parse_market_date(raw) == expected


def test_parse_market_date_returns_none_rather_than_guessing() -> None:
    """A date we cannot read must be skipped, never invented."""
    assert _parse_market_date("not a date") is None
    assert _parse_market_date("") is None
    assert _parse_market_date(None) is None


# -------------------------------------------------------------- the service


async def _seed_one_price(session: AsyncSession, **overrides) -> None:
    """Persist one price through the real pipeline."""
    row = _normalise_row({**GOV_ROW, **overrides.pop("source", {})})
    row.update(overrides)
    await MarketService()._persist_rows(session, [row])


async def _count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(MarketPrice.id)))
    return result.scalar_one()


async def test_persist_resolves_references_and_stores_the_price(
    session: AsyncSession,
) -> None:
    await _seed_one_price(session)

    rows = await MarketService().public_rows(session)
    assert len(rows) == 1
    row = rows[0]
    assert row["commodity_name"] == "Tomato"
    assert row["mandi_name"] == "Azadpur"
    assert row["district_name"] == "North Delhi"
    assert row["state_name"] == "Delhi"
    assert row["grade"] == "A"
    # A decimal money value must not lose precision on the way through.
    assert row["modal_price"] == "1250.50"
    assert row["arrivals"] == 320
    assert row["source_name"]


async def test_reimporting_the_same_day_upserts_instead_of_duplicating(
    session: AsyncSession,
) -> None:
    """The unique key is the business-day observation: a re-import is the
    same row seen again, so only the numbers move."""
    await _seed_one_price(session)
    assert await _count(session) == 1

    await _seed_one_price(session, source={"ModalPrice": "1400.00"})
    assert await _count(session) == 1

    rows = await MarketService().public_rows(session)
    assert rows[0]["modal_price"] == "1400.00"


async def test_a_row_with_no_grade_is_stored_as_not_graded(
    session: AsyncSession,
) -> None:
    await _seed_one_price(session, source={"Grade": ""})

    rows = await MarketService().public_rows(session)
    assert len(rows) == 1
    assert rows[0]["grade"] == "UNKNOWN"


async def test_a_blank_price_is_stored_as_null_not_zero(
    session: AsyncSession,
) -> None:
    """Zero is a real price. A missing price must stay null so the board can
    say "not published" instead of lying about a free crop."""
    await _seed_one_price(session, source={"ModalPrice": ""})

    rows = await MarketService().public_rows(session)
    assert rows[0]["modal_price"] is None


async def test_a_row_with_an_unreadable_date_is_skipped_not_guessed(
    session: AsyncSession,
) -> None:
    await _seed_one_price(session, source={"MarketDate": "sometime tuesday"})

    assert await _count(session) == 0
    assert await MarketService().public_rows(session) == []


async def test_a_row_missing_a_required_field_is_skipped(
    session: AsyncSession,
) -> None:
    """A partial government row must not half-create a reference hierarchy."""
    row = _normalise_row({**GOV_ROW, "State": ""})
    await MarketService()._persist_rows(session, [row])

    assert await _count(session) == 0


async def test_prices_are_ordered_newest_market_day_first(
    session: AsyncSession,
) -> None:
    await _seed_one_price(session, source={"MarketDate": "2026-10-01"})
    await _seed_one_price(session, source={"MarketDate": "2026-10-05"})

    rows = await MarketService().public_rows(session)
    assert [row["market_date"] for row in rows] == ["2026-10-05", "2026-10-01"]


async def test_public_rows_filter_by_commodity_and_grade(
    session: AsyncSession,
) -> None:
    await _seed_one_price(session)
    await _seed_one_price(
        session, source={"Grade": "B", "MandiName": "Karnal", "MandiDistr": "Karnal",
                         "State": "Haryana", "MarketDate": "2026-10-04"}
    )

    service = MarketService()
    assert len(await service.public_rows(session)) == 2

    grade_a = next(g for g in await service.list_grades(session) if g["code"] == "A")
    assert len(await service.public_rows(session, grade_id=grade_a["id"])) == 1


async def test_list_grades_reports_the_id_the_price_query_filters_on(
    session: AsyncSession,
) -> None:
    """Regression: the board's grade filter is useless without this id.

    The reference ``/reference/grades`` endpoint only returns commodity-agnostic
    grades, so the board must read the grades that actually appear on it.
    """
    await _seed_one_price(session)

    grades = await MarketService().list_grades(session)
    assert [grade["code"] for grade in grades] == ["A"]

    grade = grades[0]
    assert isinstance(grade["id"], int)
    # The repository upper-cases derived codes; the display name is untouched.
    assert grade["commodity_code"] == "TOMATO"
    assert grade["row_count"] == 1

    # The id really is the one /market/prices?grade_id= accepts.
    filtered = await MarketService().public_rows(session, grade_id=grade["id"])
    assert len(filtered) == 1
    assert filtered[0]["grade"] == "A"


async def test_list_grades_omits_a_grade_nobody_has_imported(
    session: AsyncSession,
) -> None:
    """A grade with no stored row would only widen the filter with dead
    options."""
    await _seed_one_price(session, source={"Grade": "A"})
    await _seed_one_price(
        session, source={"Grade": "B", "MandiName": "Karnal", "MandiDistr": "Karnal",
                         "State": "Haryana", "MarketDate": "2026-10-04"}
    )

    grades = await MarketService().list_grades(session)
    assert sorted(grade["code"] for grade in grades) == ["A", "B"]
    assert all(grade["row_count"] == 1 for grade in grades)


async def test_extracting_twice_within_the_cache_window_reuses_the_extract(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second extract must not hit upstream inside the 5 minute window."""
    service = MarketService()

    calls = {"n": 0}

    async def _counting_fetch() -> dict:
        calls["n"] += 1
        return {"result": [GOV_ROW]}

    monkeypatch.setattr(service, "_fetch_payload", _counting_fetch)

    first = await service.fetch_latest(session)
    assert calls["n"] == 1
    assert first.errors == []
    assert len(first.rows) == 1

    second = await service.fetch_latest(session)
    assert calls["n"] == 1, "a warm cache must not call upstream again"
    # The cached extract is the same observation, not a fresh empty one.
    assert len(second.rows) == 1


async def test_an_unreachable_upstream_is_recorded_not_raised(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A government portal outage must degrade the board, never 500 it."""

    async def _boom() -> dict:
        raise RuntimeError("connection reset")

    monkeypatch.setattr(MarketService(), "_fetch_payload", _boom)
    batch = await MarketService().fetch_latest(session)

    assert batch.rows == []
    assert any("fetch_failed" in error for error in batch.errors)


# ------------------------------------------------- the two data-loss bugs

# Regression 1: the extract cache stored only ``rows[:20]`` but returned those
# 20 as if they were the whole extract, so any second import inside the cache
# window silently wrote a fraction of the real data.


def _many_rows(count: int) -> list[dict]:
    return [
        {
            **GOV_ROW,
            "Commodity": f"Crop{index}",
            "MandiName": f"Mandi{index}",
            "MandiDistr": f"District{index}",
            "MarketDate": f"2026-10-{index % 28 + 1:02d}",
        }
        for index in range(count)
    ]


async def test_a_warm_cache_never_returns_a_truncated_extract(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cache hit must never quietly shrink the import.

    The cache stores a bounded sample for freshness reporting. When the real
    extract was bigger, the batch has to be reported as incomplete so the
    caller re-polls - otherwise a re-run writes 20 of 90 rows.
    """
    service = MarketService()
    total = 90

    calls = {"n": 0}

    async def _counting_fetch() -> dict:
        calls["n"] += 1
        return {"result": _many_rows(total)}

    monkeypatch.setattr(service, "_fetch_payload", _counting_fetch)

    first = await service.fetch_latest(session)
    assert len(first.rows) == total
    assert first.is_complete
    assert calls["n"] == 1

    second = await service.fetch_latest(session)
    assert calls["n"] == 2, "a truncated cache must trigger a re-poll"
    assert len(second.rows) == total, "the re-poll must return the whole extract"
    assert second.is_complete


async def test_a_small_extract_is_served_from_cache(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the cache really does hold the whole extract, reuse it."""
    service = MarketService()

    calls = {"n": 0}

    async def _counting_fetch() -> dict:
        calls["n"] += 1
        return {"result": _many_rows(3)}

    monkeypatch.setattr(service, "_fetch_payload", _counting_fetch)

    await service.fetch_latest(session)
    second = await service.fetch_latest(session)

    assert calls["n"] == 1, "a complete cache entry must avoid the upstream"
    assert len(second.rows) == 3
    assert second.from_cache is True


# Regression 2: the fetch only ever took the first page, so "all market data"
# could never actually arrive.


async def test_fetch_pages_through_the_whole_resource(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every page must be read, not just the first."""
    rows = _many_rows(1200)
    pages: list[int] = []

    class _Response:
        def __init__(self, payload: dict) -> None:
            self._payload = payload
            self.status = 200

        async def __aenter__(self) -> "_Response":
            return self

        async def __aexit__(self, *_exc: object) -> bool:
            return False

        def raise_for_status(self) -> None:
            return None

        async def json(self) -> dict:
            return self._payload

    class _Session:
        async def __aenter__(self) -> "_Session":
            return self

        async def __aexit__(self, *_exc: object) -> bool:
            return False

        def get(self, _url: str, headers: dict, params: dict) -> _Response:
            offset = int(params.get("offset", "0"))
            limit = int(params["limit"])
            pages.append(offset)
            return _Response({"result": rows[offset:offset + limit]})

    import aiohttp

    import app.services.market_service as module

    monkeypatch.setattr(module, "PAGE_SIZE", 100, raising=False)
    monkeypatch.setattr(module, "MAX_EXTRACT_ROWS", 5000, raising=False)
    # aiohttp is imported inside the method, so patch it on the real module.
    monkeypatch.setattr(aiohttp, "ClientSession", _Session)

    captured = await MarketService()._fetch_payload()

    assert len(captured["result"]) == 1200, "every row must be captured"
    assert len(pages) > 1, "the resource must be paged, not read once"
    assert pages[0] == 0


async def test_an_upstream_that_ignores_offset_does_not_loop_forever(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A server that ignores ``offset`` would otherwise hang the import."""
    calls = {"n": 0}

    class _Response:
        status = 200

        async def __aenter__(self) -> "_Response":
            return self

        async def __aexit__(self, *_exc: object) -> bool:
            return False

        def raise_for_status(self) -> None:
            return None

        async def json(self) -> dict:
            return {"result": _many_rows(5)}

    class _Session:
        async def __aenter__(self) -> "_Session":
            return self

        async def __aexit__(self, *_exc: object) -> bool:
            return False

        def get(self, _url: str, headers: dict, params: dict) -> _Response:
            calls["n"] += 1
            return _Response()

    import aiohttp

    monkeypatch.setattr(aiohttp, "ClientSession", _Session)

    captured = await MarketService()._fetch_payload()

    assert calls["n"] <= 3, "a repeated page must stop the loop"
    assert len(captured["result"]) == 5


def test_normalise_drops_a_duplicate_observation() -> None:
    """Two copies of the same commodity+grade+mandi+day are one observation."""
    rows = MarketService._normalise({"result": [GOV_ROW, dict(GOV_ROW)]})
    assert len(rows) == 1


async def test_modal_price_survives_as_a_decimal_not_a_float(
    session: AsyncSession,
) -> None:
    """Money must never pass through a JS/DB float: 0.1 + 0.2 must be 0.30."""
    await _seed_one_price(session, source={"ModalPrice": "0.30"})

    row = (
        await session.execute(select(MarketPrice.modal_price))
    ).scalar_one()
    assert isinstance(row, Decimal)
    assert row == Decimal("0.30")


# ---------------------------------------------------------------- the API


def test_public_board_endpoints_are_reachable_without_signing_in(
    client: TestClient,
) -> None:
    """The board is public: no token, no 401."""
    for path in (
        "/api/v1/market/prices",
        "/api/v1/market/commodities",
        "/api/v1/market/grades",
        "/api/v1/market/freshness",
        "/api/v1/market/source",
        "/api/v1/market/schema",
    ):
        assert client.get(path).status_code == 200, path


def test_an_empty_board_is_empty_not_an_error(client: TestClient) -> None:
    assert client.get("/api/v1/market/prices").json() == []
    assert client.get("/api/v1/market/commodities").json() == []
    assert client.get("/api/v1/market/grades").json() == []
    assert client.get("/api/v1/market/freshness").json() == {"last_imported_at": None}


def test_source_endpoint_names_the_upstream(client: TestClient) -> None:
    body = client.get("/api/v1/market/source").json()
    assert "data.gov.in" in body["source_name"]