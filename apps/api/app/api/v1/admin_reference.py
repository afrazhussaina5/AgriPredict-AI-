"""Admin reference-data import endpoints (Phase 5).

Design rules:

* Every import endpoint requires the ``admin`` role via ``require_admin``. Since
  admin grants are created only through the controlled process in Phase 15,
  these endpoints stay closed until then - the correct, safe default.
* Every import defaults to ``dry_run=true``. Writing requires an explicit
  ``dry_run=false`` together with ``confirm=true``.
* The operator must declare the source. Nothing is imported anonymously.
* Every run writes an audit entry, including what was rejected and why.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...core.dependencies import DbSession, require_admin
from ...core.errors import ValidationError
from ...models import User, UserRole
from ...repositories import AuditRepository
from ...schemas.reference import ImportResult
from ...services.reference_import_specs import IMPORT_SPECS
from ...services.reference_service import (
    SUPPORTED_ENTITIES,
    ImportValidationError,
    ReferenceService,
)

router = APIRouter(prefix="/admin/reference", tags=["admin-reference"])

AdminUser = Annotated[User, Depends(require_admin)]


class SourceDeclaration(BaseModel):
    """Who provided the data and what it is."""

    source_key: str = Field(min_length=2, max_length=60)
    source_name: str = Field(min_length=2, max_length=200)
    url: str | None = Field(default=None, max_length=500)
    publisher: str | None = Field(default=None, max_length=200)
    # Whether the publisher is a government body. The operator asserts this; the
    # platform never infers it.
    is_official: bool = False
    license_notes: str | None = Field(default=None, max_length=500)


class ImportRequest(BaseModel):
    entity_type: str = Field(description="One of: " + ", ".join(sorted(SUPPORTED_ENTITIES)))
    csv_text: str = Field(min_length=1, max_length=5_000_000)
    source: SourceDeclaration
    dry_run: bool = Field(default=True)
    confirm: bool = Field(
        default=False,
        description="Must be true to write. Guards against an accidental write.",
    )


@router.get("/entities", summary="Entity types that can be imported")
def list_entities() -> dict[str, dict[str, list[str]]]:
    """Return the supported entity types and their CSV columns."""
    return dict(IMPORT_SPECS)


@router.post("/import", response_model=ImportResult, summary="Import reference data")
async def import_reference_data(
    payload: ImportRequest,
    user: AdminUser,
    session: DbSession,
) -> ImportResult:
    """Validate, and optionally apply, a CSV import of reference data."""
    if payload.entity_type not in SUPPORTED_ENTITIES:
        raise ValidationError(f"Unknown entity type '{payload.entity_type}'.")

    service = ReferenceService(session)
    source = await service.ensure_source(
        payload.source.source_key,
        payload.source.source_name,
        url=payload.source.url,
        publisher=payload.source.publisher,
        is_official=payload.source.is_official,
        license_notes=payload.source.license_notes,
    )

    # Writing requires BOTH an explicit dry_run=false AND an explicit confirm.
    dry_run = payload.dry_run or not payload.confirm

    try:
        source_obj, _created = source
        report = await service.import_rows(
            payload.entity_type,
            payload.csv_text,
            source_obj,
            dry_run=dry_run,
            performed_by_user_id=user.id,
        )
    except ImportValidationError as exc:
        await session.rollback()
        raise ValidationError(str(exc)) from exc

    await AuditRepository(session).record(
        action="reference.import",
        entity_type="reference",
        entity_id=payload.entity_type,
        actor_user_id=user.id,
        actor_role=UserRole.ADMIN,
        result="success" if not report.rejected_count else "partial",
        details={
            "source": source_obj.source_key,
            "dry_run": report.dry_run,
            "rows": report.row_count,
            "inserted": report.inserted_count,
            "updated": report.updated_count,
            "skipped": report.skipped_count,
            "rejected": report.rejected_count,
            "source_key": payload.source.source_key,
        },
    )
    await session.commit()

    return ImportResult(
        entity_type=report.entity_type,
        dry_run=report.dry_run,
        row_count=report.row_count,
        inserted_count=report.inserted_count,
        updated_count=report.updated_count,
        skipped_count=report.skipped_count,
        rejected_count=report.rejected_count,
        rejection_reasons=report.reasons,
    )


__all__ = ["ImportRequest", "SourceDeclaration", "router"]