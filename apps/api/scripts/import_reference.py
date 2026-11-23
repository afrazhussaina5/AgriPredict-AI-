"""Import verified reference data from CSV files.

Command line use (run from ``apps/api``):

    python -m scripts.import_reference --entity states --file states.csv --dry-run
    python -m scripts.import_reference --entity states --file states.csv \\
        --source-key my-state-directory --source-name "State statistical handbooks" \\
        --url https://example.org/data --apply

Rules enforced here:

* **Nothing is imported without a source.** ``--source-key`` and
  ``--source-name`` are required to actually write.
* Dry run is the default. ``--apply`` is required to write.
* Every run writes a ``reference_import_logs`` row, including rejections.
* No network access, no credentials, no paid services.
"""

import argparse
import asyncio
import sys

from app.core.config import get_settings
from app.core.database import dispose_engine, get_session_factory, init_engine
from app.core.logging import configure_logging
from app.services.reference_import_specs import template_header
from app.services.reference_service import (
    SUPPORTED_ENTITIES,
    ImportValidationError,
    ReferenceService,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.import_reference",
        description="Import verified reference data (states, districts, mandis...).",
    )
    parser.add_argument(
        "--entity", required=True, choices=sorted(SUPPORTED_ENTITIES),
        help="What the file contains.",
    )
    parser.add_argument("--file", help="Path to the CSV file.")
    parser.add_argument(
        "--print-template", action="store_true",
        help="Print the required CSV header for --entity and exit.",
    )
    parser.add_argument("--source-key", help="Stable key, e.g. 'gov-directory-2026'.")
    parser.add_argument("--source-name", help="Human readable source name.")
    parser.add_argument("--url", help="Where the data came from.")
    parser.add_argument("--publisher", help="Who published it.")
    parser.add_argument(
        "--official", action="store_true",
        help="Assert that the publisher is a government body. The tool never infers this.",
    )
    parser.add_argument("--license-notes", help="Licence or usage notes.")
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually write. Without this flag the import is a dry run.",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    if args.print_template:
        print(template_header(args.entity))
        return 0

    if not args.file:
        print("Error: --file is required (or use --print-template).", file=sys.stderr)
        return 2
    if args.apply and (not args.source_key or not args.source_name):
        print(
            "Error: --source-key and --source-name are required to write data. "
            "Reference data is never imported anonymously.",
            file=sys.stderr,
        )
        return 2

    configure_logging(get_settings().LOG_LEVEL)
    if init_engine(get_settings()) is None:
        print("Error: no database is configured (POSTGRES_DSN is empty).", file=sys.stderr)
        return 1

    factory = get_session_factory()
    assert factory is not None
    async with factory() as session:
        service = ReferenceService(session)
        source = await service.ensure_source(
            args.source_key or "unattributed-dry-run",
            args.source_name or "Unattributed (dry run)",
            url=args.url,
            publisher=args.publisher,
            is_official=args.official,
            license_notes=args.license_notes,
        )
        await session.commit()

        try:
            with open(args.file, encoding="utf-8-sig", newline="") as handle:
                csv_text = handle.read()
            source_obj, _created = source
            report = await service.import_rows(
                args.entity, csv_text, source_obj, dry_run=not args.apply
            )
        except ImportValidationError as exc:
            await session.rollback()
            print(f"Invalid file: {exc}", file=sys.stderr)
            return 1
        except OSError as exc:
            await session.rollback()
            print(f"Could not read the file: {exc}", file=sys.stderr)
            return 1

        print(f"entity        : {report.entity_type}")
        print(f"mode          : {'DRY RUN (nothing written)' if report.dry_run else 'APPLIED'}")
        print(f"rows read     : {report.row_count}")
        print(f"inserted      : {report.inserted_count}")
        print(f"updated       : {report.updated_count}")
        print(f"skipped       : {report.skipped_count}")
        print(f"rejected      : {report.rejected_count}")
        if report.reasons:
            print("rejection reasons:")
            for reason in report.reasons:
                print(f"  - {reason}")

        if report.dry_run:
            print("\nRe-run with --apply (plus --source-key and --source-name) to write.")

    await dispose_engine()
    return 0


def main() -> int:
    args = _build_parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())