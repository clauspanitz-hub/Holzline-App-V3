"""Gemerkte Shop-Zuordnung: Herkunft + SKU oder Titel → Lagerprodukt."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CustomerOrder, OrderLine, Product, ShopLineMap
from app.order_match import sku_key, title_key


def line_title_key(line: OrderLine) -> str:
    return title_key(line.shop_title or line.label, None)


def line_sku_key(line: OrderLine) -> str | None:
    return sku_key(line.shop_sku)


def lookup_mapped_product(
    maps: list[ShopLineMap],
    *,
    origin: str,
    sku: str | None,
    title: str,
    variant_title: str | None = None,
) -> Product | None:
    origin_key = (origin or "").strip().casefold() or "shopify"
    sk = sku_key(sku)
    if sk:
        sku_hits = [m for m in maps if m.origin == origin_key and m.sku_key == sk]
        ids = {m.product_id for m in sku_hits if m.product_id}
        if len(ids) == 1:
            return sku_hits[0].product
    tk = title_key(title, variant_title)
    if not tk:
        return None
    title_hits = [m for m in maps if m.origin == origin_key and m.title_key == tk]
    if len(title_hits) == 1:
        return title_hits[0].product
    return None


def load_maps(db: Session, origin: str = "shopify") -> list[ShopLineMap]:
    origin_key = (origin or "").strip().casefold() or "shopify"
    return list(
        db.scalars(
            select(ShopLineMap)
            .where(ShopLineMap.origin == origin_key)
            .options(selectinload(ShopLineMap.product))
        ).all()
    )


def remember_shop_line(
    db: Session,
    *,
    origin: str,
    line: OrderLine,
    product: Product,
) -> tuple[Product | None, list[str]]:
    """Letzte Bestätigung gewinnt. Gibt (altes Produkt, Hinweise) zurück."""
    notices: list[str] = []
    origin_key = (origin or "").strip().casefold() or "shopify"
    tk = line_title_key(line)
    sk = line_sku_key(line)
    if not tk:
        return None, notices

    row = db.scalars(
        select(ShopLineMap).where(ShopLineMap.origin == origin_key, ShopLineMap.title_key == tk)
    ).first()
    old_id = row.product_id if row else None
    if row is None:
        row = ShopLineMap(origin=origin_key, title_key=tk, product_id=product.id)
        db.add(row)
    elif old_id != product.id:
        old = db.get(Product, old_id) if old_id else None
        old_name = old.name if old else "unbekannt"
        notices.append(f"Shop-Zuordnung geändert: {old_name} → {product.name}.")
        row.product_id = product.id
    if sk:
        row.sku_key = sk
    db.flush()
    return None, notices


def fill_product_sku(db: Session, product: Product, shop_sku: str | None) -> list[str]:
    raw = (shop_sku or "").strip()
    if not raw:
        return []
    if (product.sku or "").strip():
        if (product.sku or "").strip().casefold() != raw.casefold():
            return [f"Produkt-SKU „{product.sku}“ bleibt (Shop: {raw})."]
        return []
    owner = db.scalars(select(Product).where(Product.sku == raw)).first()
    if owner and owner.id != product.id:
        return [f"SKU „{raw}“ gehört schon zu „{owner.name}“ — nicht übernommen."]
    product.sku = raw[:100]
    return [f"SKU „{raw}“ am Produkt {product.name} gesetzt."]


def spread_shop_assignment(
    db: Session,
    *,
    origin: str,
    source: OrderLine,
    product: Product,
) -> int:
    """Andere unzugeordnete Prüfungszeilen derselben Identität mitziehen."""
    origin_key = (origin or "").strip().casefold() or "shopify"
    tk = line_title_key(source)
    sk = line_sku_key(source)
    if not tk:
        return 0
    rows = db.scalars(
        select(OrderLine)
        .join(CustomerOrder)
        .where(
            CustomerOrder.origin == origin_key,
            CustomerOrder.status == "review",
            OrderLine.id != source.id,
            OrderLine.product_id.is_(None),
            OrderLine.material_id.is_(None),
        )
    ).all()
    count = 0
    for line in rows:
        same_title = line_title_key(line) == tk
        same_sku = bool(sk) and line_sku_key(line) == sk
        if not (same_title or same_sku):
            continue
        line.product_id = product.id
        line.suggested_product_id = None
        count += 1
    return count
