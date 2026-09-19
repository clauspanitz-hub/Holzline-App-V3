"""Tests für Einkauf-Todos Auto-Sync (ADR 0023)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, seed_locations
from app.models import Location, Material, MaterialStock, Unit, WorkTodo
from app.purchase_todos import (
    generate_purchase_todos,
    is_material_critical,
    material_stock_available,
    sync_purchase_todos,
)


def _session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    seed_locations(db)
    return db


def _loc(db: Session, name: str) -> Location:
    return db.scalars(select(Location).where(Location.name == name)).one()


def _material(db: Session, *, min_stock: Decimal | None, hamburg: Decimal, ausschuss: Decimal = Decimal("0")) -> Material:
    m = Material(
        name=f"Mat-{hamburg}-{ausschuss}-{min_stock}",
        unit=Unit.STK,
        purchase_quantity=Decimal("10"),
        purchase_price=Decimal("1"),
        cost_per_unit=Decimal("0.1"),
        min_stock=min_stock,
    )
    db.add(m)
    db.flush()
    db.add(MaterialStock(material_id=m.id, location_id=_loc(db, "Hamburg").id, quantity=hamburg))
    if ausschuss:
        db.add(MaterialStock(material_id=m.id, location_id=_loc(db, "Ausschuss").id, quantity=ausschuss))
    db.flush()
    db.refresh(m, attribute_names=["stocks"])
    for s in m.stocks:
        _ = s.location
    return m


def test_ausschuss_excluded_from_available_and_critical():
    db = _session()
    m = _material(db, min_stock=Decimal("5"), hamburg=Decimal("0"), ausschuss=Decimal("20"))
    assert material_stock_available(m) == Decimal("0")
    assert is_material_critical(m) is True
    db.close()


def test_complete_when_min_stock_met_and_recreate_when_below():
    db = _session()
    m = _material(db, min_stock=Decimal("10"), hamburg=Decimal("3"))
    first = sync_purchase_todos(db, material_ids={m.id})
    assert first["created"] == 1
    open_todos = db.scalars(
        select(WorkTodo).where(WorkTodo.material_id == m.id, WorkTodo.status == "open")
    ).all()
    assert len(open_todos) == 1
    todo_id = open_todos[0].id

    # Bestand auf Mindestbestand heben → erledigen
    stock = db.scalars(
        select(MaterialStock).where(
            MaterialStock.material_id == m.id,
            MaterialStock.location_id == _loc(db, "Hamburg").id,
        )
    ).one()
    stock.quantity = Decimal("10")
    db.flush()
    db.expire(m)
    m = db.get(Material, m.id)
    _ = [s.location for s in m.stocks]

    done = sync_purchase_todos(db, material_ids={m.id})
    assert done["completed_stale"] == 1
    assert done["created"] == 0
    old = db.get(WorkTodo, todo_id)
    assert old is not None
    assert old.status == "done"
    assert old.completed_at is not None

    # Wieder unter Mindestbestand → neues offenes Todo
    stock.quantity = Decimal("2")
    db.flush()
    db.expire(m)
    m = db.get(Material, m.id)
    _ = [s.location for s in m.stocks]

    again = sync_purchase_todos(db, material_ids={m.id})
    assert again["created"] == 1
    opens = db.scalars(
        select(WorkTodo).where(WorkTodo.material_id == m.id, WorkTodo.status == "open")
    ).all()
    assert len(opens) == 1
    assert opens[0].id != todo_id
    dones = db.scalars(
        select(WorkTodo).where(WorkTodo.material_id == m.id, WorkTodo.status == "done")
    ).all()
    assert len(dones) == 1
    db.close()


def test_max_one_open_and_generate_button():
    db = _session()
    m = _material(db, min_stock=Decimal("5"), hamburg=Decimal("1"))
    sync_purchase_todos(db, material_ids={m.id})
    second = sync_purchase_todos(db, material_ids={m.id})
    assert second["created"] == 0
    assert second["skipped_existing"] == 1
    bulk = generate_purchase_todos(db)
    assert bulk["skipped_existing"] >= 1
    opens = db.scalars(
        select(WorkTodo).where(WorkTodo.material_id == m.id, WorkTodo.status == "open")
    ).all()
    assert len(opens) == 1
    db.close()


def test_ignored_skipped_on_auto_create():
    db = _session()
    m = _material(db, min_stock=Decimal("5"), hamburg=Decimal("0"))
    m.overview_ignored = True
    db.flush()
    result = sync_purchase_todos(db, material_ids={m.id})
    assert result["created"] == 0
    assert result["skipped_ignored"] == 1
    with_ignored = sync_purchase_todos(db, material_ids={m.id}, include_ignored=True)
    assert with_ignored["created"] == 1
    db.close()
