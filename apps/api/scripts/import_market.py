"""Import official market prices from data.gov.in (Agmarknet).

Command line use (run from ``apps/api``):

    python -m scripts.import_market --dry-run
    python -m scripts.import_market --apply
    python -m scripts.import_market --apply --max-rows 50000
    python -m scripts.import_market --source-url https://api.data.gov.in/... --apply

Rules enforced here:

* **Dry run is the default.** ``--apply`` is required to write.
* Every row is reported as ``fetched`` / ``written`` / ``skipped`` so a silent
  partial import is impossible: if the upstream ships fewer rows than you
  expect, this prints the number it actually got.
* Provenance is not optional. Every price row is stamped with the source
  (``data.gov.in / Agmarknet``) it came from, and the extract timestamp is
  recorded so ``GET /market/freshness`` can label a stale board.
* Re-running the same business day is safe: prices are upserted on the
  commodity+grade+mandi+district+state+date+unit key, never duplicated.

This is the only thing that writes to ``market_prices``. The API itself is
read-only by design - no public endpoint triggers an import.
"""

import argparse
import asyncio
import sys

from app.core.config import get_settings
from app.core.database import dispose_engine, get_session_factory, init_engine
from app.core.logging import configure_logging
from app.services import market_service as market_module
from app.services.market_service import MarketService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.import_market",
        description="Import official mandi prices from data.gov.in (Agmarknet).",
    )
    parser.add_argument(
        "--source-url",
        help="Override the upstream resource URL (default: the built-in "
             "data.gov.in resource id).",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Ceiling on rows pulled in this run. Defaults to "
             "MARKET_MAX_ROWS (20000).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch upstream and report, without writing. This is the default.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write. Required for any database change.",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    if args.source_url:
        market_module.MARKET_API_URL = args.source_url
    if args.max_rows is not None:
        if args.max_rows < 1:
            print("Error: --max-rows must be at least 1.", file=sys.stderr)
            return 2
        market_module.MAX_EXTRACT_ROWS = args.max_rows

    configure_logging(get_settings().LOG_LEVEL)
    if init_engine(get_settings()) is None:
        print("Error: no database is configured (POSTGRES_DSN is empty).",
              file=sys.stderr)
        return 1

    service = MarketService()
    factory = get_session_factory()
    assert factory is not None

    async with factory() as session:
        try:
            batch = await service.fetch_latest(session)
        except Exception as exc:  # noqa: BLE001 - report, never traceback
            await session.rollback()
            print(f"Import failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

        print(f"source        : {market_module.MARKET_API_URL}")
        print(f"fetched at    : {batch.fetched_at.isoformat()}")
        print(f"rows fetched  : {len(batch.rows)}")
        if batch.errors:
            print("fetch errors  :")
            for error in batch.errors:
                print(f"  - {error}")

        if not batch.rows:
            print(
                "\nNothing to import. The upstream returned no usable rows - "
                "check connectivity and that the resource id is still live."
            )
            await dispose_engine()
            return 1

        if not args.apply:
            print("mode          : DRY RUN (nothing written)")
            print("\nRe-run with --apply to write these rows.")
            await dispose_engine()
            return 0

        written = await service._persist_rows(session, batch.rows)
        print("mode          : APPLIED")
        print(f"rows written  : {written}")

        if written < len(batch.rows):
            # Never let a partial import look like a complete one.
            print(
                f"WARNING: {len(batch.rows) - written} row(s) were skipped "
                "(bad date or missing state/district/mandi/commodity/unit).",
                file=sys.stderr,
            )

    await dispose_engine()
    return 0


def main() -> int:
    args = _build_parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())