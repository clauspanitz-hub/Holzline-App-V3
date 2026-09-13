"""Einkauf-Todos aus kritischem Materialbestand (ADR 0019)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Material, WorkTodo


def _q(value: Decimal | float | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal("0.001"))


def material_stock_total(material: Material) -> Decimal:
    return sum((_q(s.quantity) for s in material.stocks), Decimal("0"))


def is_material_critical(material: Material) -> bool:
    total = material_stock_total(material)
    if total <= 0:
        return True
    min_stock = getattr(material, "min_stock", None)
    if min_stock is not None and total < _q(min_stock):
        return True
    return False


def suggested_purchase_quantity(material: Material) -> Decimal:
    for attr in ("reorder_quantity", "last_purchase_quantity", "purchase_quantity"):
        raw = getattr(material, attr, None)
        if raw is None:
            continue
        qty = _q(raw)
        if qty > 0:
            return qty
    return Decimal("1")


def _open_purchase_todos(db: Session, material_id: int | None = None) -> list[WorkTodo]:
    stmt = select(WorkTodo).where(
        WorkTodo.kind == "purchase",
        WorkTodo.category == "purchase",
        WorkTodo.status == "open",
    )
    if material_id is not None:
        stmt = stmt.where(WorkTodo.material_id == material_id)
    return list(db.scalars(stmt).all())


def cleanup_stale_purchase_todos(db: Session) -> int:
    """Löscht offene Einkauf-Todos, wenn das Material fehlt oder nicht mehr kritisch ist."""
    todos = (
        db.scalars(
            select(WorkTodo)
            .where(
                WorkTodo.kind == "purchase",
                WorkTodo.category == "purchase",
                WorkTodo.status == "open",
            )
            .options(selectinload(WorkTodo.material).selectinload(Material.stocks))
        )
        .unique()
        .all()
    )
    deleted = 0
    for todo in todos:
        material = todo.material
        if material is None or not is_material_critical(material):
            db.delete(todo)
            deleted += 1
    if deleted:
        db.flush()
    return deleted


def generate_purchase_todos(db: Session, *, include_ignored: bool = False) -> dict[str, int]:
    """Legt offene Einkauf-Todos für kritische Materialien an (höchstens eines pro Material)."""
    deleted_stale = cleanup_stale_purchase_todos(db)
    materials = db.scalars(select(Material).options(selectinload(Material.stocks))).unique().all()
    existing = {
        t.material_id
        for t in _open_purchase_todos(db)
        if t.material_id is not None
    }
    created = 0
    skipped_existing = 0
    skipped_ignored = 0
    for material in materials:
        if not is_material_critical(material):
            continue
        if bool(getattr(material, "overview_ignored", False)) and not include_ignored:
            skipped_ignored += 1
            continue
        if material.id in existing:
            skipped_existing += 1
            continue
        qty = suggested_purchase_quantity(material)
        db.add(
            WorkTodo(
                order_id=None,
                order_line_id=None,
                kind="purchase",
                category="purchase",
                status="open",
                title=f"Einkauf: {material.name}",
                quantity=qty,
                product_id=None,
                material_id=material.id,
            )
        )
        existing.add(material.id)
        created += 1
    db.commit()
    return {
        "created": created,
        "skipped_existing": skipped_existing,
        "skipped_ignored": skipped_ignored,
        "deleted_stale": deleted_stale,
    }
