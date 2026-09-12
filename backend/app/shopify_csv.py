"""Parse Shopify Products / Inventory CSV into per-handle catalogs."""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation


def parse_variant_price(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    text = str(raw).strip().replace("€", "").replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    text = re.sub(r"[^0-9.]", "", text)
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if value < 0:
        return None
    return value.quantize(Decimal("0.01"))


def parse_shopify_catalog_csv(content: str) -> dict[str, dict]:
    """Return handle -> { title, variants: {(o1,o2,o3)->fields}, option_values: {name: set} }.

    Skips Default-Title-only rows. Forward-fills Title and Option names.
    """
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames or "Handle" not in reader.fieldnames:
        raise ValueError("Ungültiger Shopify-Export (Spalte „Handle“ fehlt)")

    by_handle: dict[str, dict] = {}
    current_handle: str | None = None
    option_names: list[str | None] = [None, None, None]

    for row in reader:
        handle = (row.get("Handle") or "").strip()
        if not handle:
            continue
        if handle != current_handle:
            current_handle = handle
            option_names = [None, None, None]
            by_handle.setdefault(handle, {"title": handle, "variants": {}, "option_values": defaultdict(set)})

        title_cell = (row.get("Title") or "").strip()
        if title_cell:
            by_handle[handle]["title"] = title_cell

        for i in range(3):
            name_cell = (row.get(f"Option{i + 1} Name") or "").strip()
            if name_cell:
                option_names[i] = name_cell

        values = [(row.get(f"Option{i + 1} Value") or "").strip() or None for i in range(3)]
        if not any(values):
            continue
        if values[0] == "Default Title" and values[1] is None and values[2] is None:
            continue

        names = [option_names[i] if values[i] is not None else None for i in range(3)]
        if values[0] is not None and not names[0]:
            continue

        key = (values[0], values[1], values[2])
        sku = (row.get("Variant SKU") or row.get("SKU") or "").strip() or None
        price = parse_variant_price(row.get("Variant Price") or row.get("Price"))
        by_handle[handle]["variants"][key] = {
            "option1_name": names[0],
            "option1_value": values[0],
            "option2_name": names[1],
            "option2_value": values[1],
            "option3_name": names[2],
            "option3_value": values[2],
            "sku": sku,
            "price": price,
        }
        for n, v in zip(names, values):
            if n and v:
                by_handle[handle]["option_values"][n].add(v)

    usable = {
        h: {
            "title": data["title"],
            "variants": data["variants"],
            "option_values": {k: sorted(vs) for k, vs in data["option_values"].items()},
        }
        for h, data in by_handle.items()
        if data["variants"]
    }
    return usable

