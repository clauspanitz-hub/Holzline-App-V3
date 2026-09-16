"""Shop-Zeile → Produkt: SKU, Shop-Zuordnung, sonst Name/Farbe, sonst unzugeordnet."""

from __future__ import annotations


def normalize_order_number(value: str | None) -> str:
    text = (value or "").strip()
    if text.startswith("#"):
        text = text[1:].strip()
    return text.casefold()


def _fold(value: str | None) -> str:
    return (value or "").strip().casefold()


def sku_key(sku: str | None) -> str | None:
    text = _fold(sku)
    return text[:100] or None


def title_key(title: str | None, variant_title: str | None = None) -> str:
    title_s = (title or "").strip()
    variant_s = (variant_title or "").strip()
    if variant_s and title_s:
        folded_title = _fold(title_s)
        if folded_title.endswith(_fold(variant_s)) or " - " in title_s:
            return folded_title[:300]
        return _fold(f"{title_s} - {variant_s}")[:300]
    return _fold(title_s)[:300]


def match_product_for_shop_line(
    products: list,
    *,
    sku: str | None,
    title: str,
    variant_title: str | None = None,
    mapped=None,
):
    usable = [p for p in products if not bool(getattr(p, "is_template", False))]
    sk = sku_key(sku)
    if sk:
        sku_hits = [p for p in usable if _fold(p.sku) == sk]
        if len(sku_hits) == 1:
            return sku_hits[0]

    if mapped is not None:
        return mapped

    title_s = (title or "").strip()
    variant_s = (variant_title or "").strip()
    name_keys = {_fold(title_s)} if title_s else set()
    if variant_s:
        name_keys.add(_fold(variant_s))
        if title_s:
            name_keys.add(_fold(f"{title_s} - {variant_s}"))
            name_keys.add(_fold(f"{title_s} {variant_s}"))
    name_keys.discard("")
    exact = [p for p in usable if _fold(p.name) in name_keys]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return None

    color_keys = set()
    if variant_s:
        color_keys.add(_fold(variant_s))
    if " - " in title_s:
        color_keys.add(_fold(title_s.rsplit(" - ", 1)[-1]))
    color_keys.discard("")
    if not color_keys:
        return None

    prefix = title_s
    if variant_s and _fold(prefix).endswith(_fold(variant_s)):
        prefix = prefix[: -len(variant_s)].rstrip(" -")
    prefix_key = _fold(prefix)
    color_hits = []
    for product in usable:
        color_name = _fold(product.color.name if product.color else None)
        if not color_name or color_name not in color_keys:
            continue
        product_key = _fold(product.name)
        if product_key in name_keys:
            color_hits.append(product)
            continue
        if prefix_key and (
            product_key.startswith(prefix_key) or prefix_key in product_key
        ):
            color_hits.append(product)
    ids = {p.id for p in color_hits}
    if len(ids) == 1:
        return color_hits[0]
    return None
