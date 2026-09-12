"""System tags for incomplete master data (fehlt …)."""

from __future__ import annotations

FIELD_MIN_STOCK = "Mindestbestand"
FIELD_BOM = "Stückliste"
FIELD_PURCHASE = "Einkaufspreis"
FIELD_SELLING = "Verkaufspreis"

TAG_BY_FIELD: dict[str, str] = {
    FIELD_MIN_STOCK: "fehlt Mindestbestand",
    FIELD_BOM: "fehlt Stückliste",
    FIELD_PURCHASE: "fehlt Einkaufspreis",
    FIELD_SELLING: "fehlt Verkaufspreis",
}

SYSTEM_INCOMPLETE_TAG_NAMES: frozenset[str] = frozenset(TAG_BY_FIELD.values())

MATERIAL_INCOMPLETE_FIELDS: frozenset[str] = frozenset({FIELD_MIN_STOCK, FIELD_PURCHASE})
PRODUCT_INCOMPLETE_FIELDS: frozenset[str] = frozenset({FIELD_MIN_STOCK, FIELD_BOM, FIELD_SELLING})


def is_system_incomplete_tag(name: str) -> bool:
    return name in SYSTEM_INCOMPLETE_TAG_NAMES


def visible_incomplete_fields(raw_missing: list[str], tag_names: set[str]) -> list[str]:
    """Only fields whose fehlt-tag is still assigned (manual remove = ignore)."""
    return [field for field in raw_missing if TAG_BY_FIELD.get(field) in tag_names]
