"""Verkaufsstatistik: Stückzahlen aus shipped Order-Lines + Set-BOM (ADR 0032)."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CustomerOrder, Product, SetBomLine
from app.schemas import ProductSalesStatRead


def product_sales(db: Session, *, limit: int | None = None) -> list[ProductSalesStatRead]:
    """Aggregiert verkaufte Stückzahlen je Lagerprodukt (nur status=shipped, all-time).

    - Direktprodukt: quantity
    - Set-Variante: je BOM-Produkt quantity × quantity_required (Material-BOM ignoriert)
    - Material-/Freitext-only: übersprungen
    - Nur Mengen > 0; Sortierung Stückzahl desc, dann Name
    """
    orders = db.scalars(
        select(CustomerOrder)
        .where(CustomerOrder.status == "shipped")
        .options(selectinload(CustomerOrder.lines))
    ).all()

    sold: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    variant_ids: set[int] = set()

    for order in orders:
        for line in order.lines:
            if line.product_id is not None:
                sold[line.product_id] += Decimal(line.quantity)
            elif line.set_variant_id is not None:
                variant_ids.add(line.set_variant_id)

    bom_products: dict[int, list[tuple[int, Decimal]]] = defaultdict(list)
    if variant_ids:
        bom_rows = db.scalars(
            select(SetBomLine).where(
                SetBomLine.variant_id.in_(variant_ids),
                SetBomLine.product_id.isnot(None),
            )
        ).all()
        for row in bom_rows:
            assert row.product_id is not None
            bom_products[row.variant_id].append((row.product_id, Decimal(row.quantity_required)))

    for order in orders:
        for line in order.lines:
            if line.product_id is not None:
                continue
            if line.set_variant_id is None:
                continue
            line_qty = Decimal(line.quantity)
            for product_id, qty_req in bom_products.get(line.set_variant_id, []):
                sold[product_id] += line_qty * qty_req

    if not sold:
        return []

    products = {
        p.id: p.name
        for p in db.scalars(select(Product).where(Product.id.in_(sold.keys()))).all()
    }

    rows: list[ProductSalesStatRead] = []
    for product_id, qty in sold.items():
        if qty <= 0:
            continue
        name = products.get(product_id)
        if name is None:
            continue
        rows.append(
            ProductSalesStatRead(
                product_id=product_id,
                product_name=name,
                quantity_sold=qty,
            )
        )

    rows.sort(key=lambda r: (-r.quantity_sold, r.product_name.lower(), r.product_id))
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return rows
