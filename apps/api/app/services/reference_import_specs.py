"""Documented CSV column specifications for each importable entity.

Kept separate from the import logic so the same definitions drive the admin
API documentation and the CSV templates shipped with the repository.
"""

from typing import Any

IMPORT_SPECS: dict[str, dict[str, list[str]]] = {
    "states": {
        "required": ["code", "name"],
        "optional": ["name_hi", "name_te"],
    },
    "districts": {
        "required": ["state_code", "code", "name"],
        "optional": ["name_hi", "name_te"],
    },
    "mandis": {
        "required": ["district_code", "code", "name"],
        "optional": ["name_hi", "name_te", "has_storage"],
    },
    "localities": {
        "required": ["district_code", "kind", "name"],
        "optional": ["name_hi", "name_te", "latitude", "longitude"],
    },
    "commodities": {
        "required": ["code", "name"],
        "optional": ["name_hi", "name_te", "category"],
    },
    "varieties": {
        "required": ["commodity_code", "code", "name"],
        "optional": ["name_hi", "name_te"],
    },
    "grades": {
        "required": ["code", "name"],
        "optional": ["commodity_code", "name_hi", "name_te"],
    },
    "units": {
        "required": ["code", "name", "dimension"],
        "optional": ["name_hi", "name_te", "to_base_kg"],
    },
}


def template_header(entity_type: str) -> str:
    """Return the CSV header row for an entity type."""
    spec: dict[str, list[str]] | None = IMPORT_SPECS.get(entity_type)
    if spec is None:
        raise KeyError(entity_type)
    return ",".join([*spec["required"], *spec["optional"]])


def template_rows(entity_type: str) -> list[dict[str, Any]]:
    """Return clearly-labelled placeholder rows for documentation.

    These are EXAMPLES ONLY. They contain no real place names and must never be
    imported as data.
    """
    return []


__all__ = ["IMPORT_SPECS", "template_header", "template_rows"]