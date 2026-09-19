"""Einkauf-Todos aus kritischem Materialbestand (ADR 0019, 0023)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import AUSSCHUSS_LOCATION_NAME
from app.models import Material, MaterialStock, WorkTodo


def _q(value: Decimal | float | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal("0.001"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def material_stock_total(material: Material) -> Decimal:
    """Summe aller Standorte inkl. Ausschuss (Anzeige/Legacy)."""
    return sum((_q(s.quantity) for s in material.stocks), Decimal("0"))


def material_stock_available(material: Material) -> Decimal:
    """Summe der Bestände ohne Ausschuss — maßgeblich für Einkauf-Todos."""
    total = Decimal("0")
    for stock in material.stocks:
        location = getattr(stock, "location", None)
        if location is not None and getattr(location, "name", None) == AUSSCHUSS_LOCATION_NAME:
            continue
        total += _q(stock.quantity)
    return total


def is_material_critical(material: Material) -> bool:
    available = material_stock_available(material)
    if available <= 0:
        return True
    min_stock = getattr(material, "min_stock", None)
    if min_stock is not None and available < _q(min_stock):
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


def _materials_with_stocks(db: Session, material_ids: set[int] | None = None) -> list[Material]:
    stmt = select(Material).options(
        selectinload(Material.stocks).selectinload(MaterialStock.location)
    )
    if material_ids is not None:
        if not material_ids:
            return []
        stmt = stmt.where(Material.id.in_(material_ids))
    return list(db.scalars(stmt).unique().all())


def _complete_todo(todo: WorkTodo) -> None:
    todo.status = "done"
    todo.completed_at = _utcnow()


def sync_purchase_todos(
    db: Session,
    *,
    material_ids: set[int] | None = None,
    include_ignored: bool = False,
    create_missing: bool = True,
) -> dict[str, int]:
    """Erledigt offene Einkauf-Todos bei erfülltem Mindestbestand; legt bei Unterschreitung neue an.

    - Erledigt (nicht löschen), wenn Material fehlt oder nicht mehr kritisch.
    - Neues offenes Todo, wenn kritisch und keines offen (max. eines offen pro Material).
    - Altes erledigtes Todo bleibt stehen.
    - ``material_ids`` begrenzt auf betroffene Materialien (Bestandsänderung); ``None`` = alle.
    """
    completed_stale = 0
    created = 0
    skipped_existing = 0
    skipped_ignored = 0

    open_stmt = (
        select(WorkTodo)
        .where(
            WorkTodo.kind == "purchase",
            WorkTodo.category == "purchase",
            WorkTodo.status == "open",
        )
        .options(selectinload(WorkTodo.material).selectinload(Material.stocks).selectinload(MaterialStock.location))
    )
    if material_ids is not None:
        open_stmt = open_stmt.where(
            (WorkTodo.material_id.in_(material_ids)) | (WorkTodo.material_id.is_(None))
        )

    open_todos = list(db.scalars(open_stmt).unique().all())
    for todo in open_todos:
        material = todo.material
        if material is None or not is_material_critical(material):
            _complete_todo(todo)
            completed_stale += 1

    if completed_stale:
        db.flush()

    if not create_missing:
        return {
            "created": 0,
            "skipped_existing": 0,
            "skipped_ignored": 0,
            "completed_stale": completed_stale,
        }

    materials = _materials_with_stocks(db, material_ids)
    existing_open: set[int] = set()
    for todo in _open_purchase_todos(db):
        if todo.material_id is None:
            continue
        if material_ids is not None and todo.material_id not in material_ids:
            continue
        existing_open.add(todo.material_id)

    for material in materials:
        if not is_material_critical(material):
            continue
        if bool(getattr(material, "overview_ignored", False)) and not include_ignored:
            skipped_ignored += 1
            continue
        if material.id in existing_open:
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
        existing_open.add(material.id)
        created += 1

    if created or completed_stale:
        db.flush()

    return {
        "created": created,
        "skipped_existing": skipped_existing,
        "skipped_ignored": skipped_ignored,
        "completed_stale": completed_stale,
    }


def cleanup_stale_purchase_todos(db: Session) -> int:
    """Legacy-Alias: erledigt veraltete offene Einkauf-Todos (früher: löschen)."""
    return sync_purchase_todos(db, create_missing=False)["completed_stale"]


def generate_purchase_todos(db: Session, *, include_ignored: bool = False) -> dict[str, int]:
    """Bulk-Hilfe: Sync für alle Materialien (Knopf „Einkauf-Todos erzeugen“)."""
    result = sync_purchase_todos(db, include_ignored=include_ignored, create_missing=True)
    db.commit()
    return result
