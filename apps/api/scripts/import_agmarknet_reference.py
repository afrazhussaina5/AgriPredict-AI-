"""Import REAL reference data from the official Agmarknet API (NIC).

Agmarknet is the Government of India's mandi price portal. Its public
``/daily-price-arrival/filters`` endpoint returns the authoritative reference
vocabulary - states, districts, markets (mandis), commodities, varieties and
grades - as published by the Ministry of Agriculture & Farmers Welfare.

Command line use (run from ``apps/api``):

    python -m scripts.import_agmarknet_reference --dry-run
    python -m scripts.import_agmarknet_reference --apply

Rules enforced here:

* **Dry run is the default.** ``--apply`` is required to write.
* **Filter placeholders are never imported.** The endpoint's first row for
  every dimension is a UI sentinel ("All States/UTs", "All Districts",
  "All Markets", "All Grades", "All Varieties"). These are not places; they
  would otherwise land in the database as real reference rows.
* Rows whose parent is missing are skipped, never invented.
* Provenance is recorded: the rows are written under an official source
  (``agmarknet-official``) so ``/reference/status`` can report where the
  vocabulary came from.

Note on prices: this imports the reference *vocabulary* only. The daily price
report on the same API is captcha-protected and is deliberately NOT called
here - see scripts/import_market.py for the price path.
"""

import argparse
import asyncio
import csv
import io
import sys

import aiohttp

from app.core.config import get_settings
from app.core.database import check_connection, dispose_engine, get_session_factory, init_engine
from app.core.logging import configure_logging
from app.services.reference_service import ImportValidationError, ReferenceService

AGMARKNET_FILTERS_URL = "https://api.agmarknet.gov.in/v1/daily-price-arrival/filters"

SOURCE_KEY = "agmarknet-official"
SOURCE_NAME = "Agmarknet (Ministry of Agriculture & Farmers Welfare, Government of India)"
SOURCE_URL = "https://agmarknet.gov.in/"

# The endpoint's first entry per dimension is a UI placeholder, not a real
# place. Their ids are all in the 1000xx range and their names start with
# "All". Both checks are applied so a future renumbering cannot slip through.
SENTINEL_IDS = {100000, 100001, 100002, 100003, 100006, 100007}


def _is_sentinel(row_id: object, name: str) -> bool:
    if isinstance(row_id, int) and row_id in SENTINEL_IDS:
        return True
    return str(name).strip().lower().startswith("all ")


def _csv(rows: list[dict], columns: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


async def _fetch_filters() -> dict:
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(
            AGMARKNET_FILTERS_URL,
            headers={
                "Accept": "application/json",
                "User-Agent": "AgriPredict-AI-reference/1.0 (public Agmarknet API)",
            },
        ) as response:
            response.raise_for_status()
            payload = await response.json()
    if not payload.get("status"):
        raise RuntimeError(f"Agmarknet returned an error: {payload.get('message')}")
    return payload["data"]


def _build_csvs(data: dict) -> dict[str, str]:
    """Convert the API payload into the project's documented CSV shapes."""
    group_names = {
        item["id"]: item["cmdt_grp_name"]
        for item in data.get("cmdt_group_data", [])
        if isinstance(item, dict) and "id" in item
    }

    states = []
    state_ids: set[int] = set()
    for item in data.get("state_data", []):
        name = item.get("state_name", "")
        if _is_sentinel(item.get("state_id"), name):
            continue
        states.append({"code": item["state_id"], "name": name.strip()})
        state_ids.add(item["state_id"])

    districts = []
    district_ids: set[int] = set()
    for item in data.get("district_data", []):
        name = item.get("district_name", "")
        if _is_sentinel(item.get("id"), name):
            continue
        state_id = item.get("state_id")
        if state_id not in state_ids:
            continue  # never invent a district under a state we do not have
        districts.append(
            {
                "state_code": state_id,
                "code": item["id"],
                "name": name.strip(),
            }
        )
        district_ids.add(item["id"])

    mandis = []
    for item in data.get("market_data", []):
        name = item.get("mkt_name", "")
        if _is_sentinel(item.get("id"), name):
            continue
        district_id = item.get("district_id")
        if district_id not in district_ids:
            continue  # a market with no known district cannot be placed
        mandis.append(
            {
                "district_code": district_id,
                "code": item["id"],
                "name": name.strip(),
            }
        )

    commodities = []
    commodity_ids: set[int] = set()
    for item in data.get("cmdt_data", []):
        name = item.get("cmdt_name", "")
        if _is_sentinel(item.get("cmdt_id"), name):
            continue
        commodities.append(
            {
                "code": item["cmdt_id"],
                "name": name.strip(),
                "category": group_names.get(item.get("cmdt_group_id")),
            }
        )
        commodity_ids.add(item["cmdt_id"])

    grades = []
    for item in data.get("grade_data", []):
        name = item.get("grade_name", "")
        if _is_sentinel(item.get("grade_id"), name):
            continue
        grades.append({"code": item["grade_id"], "name": name.strip()})

    # Parents first: a district cannot resolve without its state.
    return {
        "states": _csv(states, ["code", "name"]),
        "districts": _csv(districts, ["state_code", "code", "name"]),
        "mandis": _csv(mandis, ["district_code", "code", "name"]),
        "commodities": _csv(commodities, ["code", "name", "category"]),
        "grades": _csv(grades, ["code", "name"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.import_agmarknet_reference",
        description="Import official states, districts, mandis, commodities "
        "and grades from the Agmarknet API.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and validate, but do not write. This is the default.",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Write the imported rows to the database.",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    configure_logging(get_settings().LOG_LEVEL)

    print(f"fetching       : {AGMARKNET_FILTERS_URL}")
    try:
        data = await _fetch_filters()
    except Exception as exc:  # noqa: BLE001 - report, never traceback
        print(f"Fetch failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    csvs = _build_csvs(data)
    print(f"source         : {SOURCE_NAME}")
    for entity, text in csvs.items():
        print(f"  {entity:12s}: {max(text.count(chr(10)) - 1, 0)} rows")
    print(f"mode           : {'APPLIED' if args.apply else 'DRY RUN (nothing written)'}")

    if args.dry_run or not args.apply:
        print("\nRe-run with --apply to write. Verify the row counts above first.")
        return 0

    if init_engine(get_settings()) is None:
        print("Error: no database is configured (POSTGRES_DSN is empty).",
              file=sys.stderr)
        return 1

    if not await check_connection():
        print("Error: database configured but not reachable.", file=sys.stderr)
        return 1

    factory = get_session_factory()
    if factory is None:
        print("Error: no session factory after init (bug).", file=sys.stderr)
        return 1

    # Order matters: a district needs its state, a mandi needs its district.
    for entity in ("states", "districts", "mandis", "commodities", "grades"):
        async with factory() as session:
            svc = ReferenceService(session)
            source, created = await svc.ensure_source(
                SOURCE_KEY,
                SOURCE_NAME,
                url=SOURCE_URL,
                publisher="Government of India",
                is_official=True,
            )
            await session.commit()
            print(
                f"source {entity:12s}: "
                f"{'created' if created else 'reused'} "
                f"({source.source_key})")
            try:
                report = await svc.import_rows(
                    entity,
                    csvs[entity],
                    source,
                    dry_run=False,
                )
            except ImportValidationError as exc:
                await session.rollback()
                print(f"{entity}: invalid - {exc}", file=sys.stderr)
                return 1
            print(
                f"{entity:12s}: "
                f"inserted={report.inserted_count} "
                f"updated={report.updated_count} "
                f"skipped={report.skipped_count} "
                f"rejected={report.rejected_count}")
            if report.reasons:
                for reason in report.reasons[:3]:
                    print(f"    - {reason}")

    await dispose_engine()
    print("\nDone. Check GET /api/v1/reference/status for the imported counts.")
    return 0


def main() -> int:
    args = _build_parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())