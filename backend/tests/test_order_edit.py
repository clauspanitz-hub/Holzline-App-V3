"""Tests für lokales Bestell-Edit (ADR 0026)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import require_user
from app.database import Base, seed_locations
from app.models import (
    CustomerOrder,
    Product,
    ProductSet,
    ProductStock,
    SetVariant,
    User,
    UserRole,
    WorkTodo,
)
from app.routers import router
from app.schemas import OrderEdit, OrderLineEdit
from app.services import create_order, edit_order


def _session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, _record) -> None:  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    seed_locations(db)
    return db


def _product(db: Session, name: str, *, stock: Decimal = Decimal("0")) -> Product:
    from app.models import Location

    p = Product(name=name, sku=None, selling_price=Decimal("10"))
    db.add(p)
    db.flush()
    loc = db.scalars(select(Location).where(Location.name == "Hamburg")).one()
    db.add(ProductStock(product_id=p.id, location_id=loc.id, quantity=stock))
    db.flush()
    return p


def _open_order_with_product(db: Session, product: Product, qty: str = "2") -> CustomerOrder:
    from app.schemas import OrderCreate, OrderLineCreate

    read = create_order(
        db,
        OrderCreate(
            ordered_on=datetime(2026, 9, 28, 12, 0, 0),
            customer_name="Test",
            lines=[OrderLineCreate(quantity=Decimal(qty), product_id=product.id)],
        ),
    )
    return db.get(CustomerOrder, read.id)


def test_edit_changes_qty_and_resyncs_todos():
    db = _session()
    product = _product(db, "Ring Uni", stock=Decimal("0"))
    order = _open_order_with_product(db, product, "2")
    line = order.lines[0]
    todos = db.scalars(select(WorkTodo).where(WorkTodo.order_id == order.id, WorkTodo.status == "open")).all()
    assert len(todos) == 1
    assert todos[0].kind == "manufacture"
    assert todos[0].quantity == Decimal("2")

    result = edit_order(
        db,
        order.id,
        OrderEdit(
            note="Personalisierung: Mia",
            lines=[OrderLineEdit(id=line.id, quantity=Decimal("5"), product_id=product.id)],
        ),
    )
    assert result.note == "Personalisierung: Mia"
    assert len(result.lines) == 1
    assert result.lines[0].quantity == Decimal("5")
    todos = db.scalars(select(WorkTodo).where(WorkTodo.order_id == order.id, WorkTodo.status == "open")).all()
    assert len(todos) == 1
    assert todos[0].quantity == Decimal("5")
    db.close()


def test_edit_remove_line_drops_open_todos_and_allows_empty():
    db = _session()
    product = _product(db, "Kerze", stock=Decimal("0"))
    order = _open_order_with_product(db, product)
    assert db.scalars(select(WorkTodo).where(WorkTodo.order_id == order.id, WorkTodo.status == "open")).first()

    result = edit_order(db, order.id, OrderEdit(lines=[]))
    assert result.lines == []
    assert any("keine Positionen" in n for n in result.notices)
    assert db.scalars(select(WorkTodo).where(WorkTodo.order_id == order.id, WorkTodo.status == "open")).first() is None
    refreshed = db.get(CustomerOrder, order.id)
    assert refreshed is not None
    assert refreshed.status == "ready"
    db.close()


def test_edit_add_freetext_and_product_line():
    db = _session()
    product = _product(db, "Schild", stock=Decimal("10"))
    order = _open_order_with_product(db, product, "1")
    # Mit genug Bestand → kein Fertigen-Todo; Status ready
    order = db.get(CustomerOrder, order.id)
    line_id = order.lines[0].id

    result = edit_order(
        db,
        order.id,
        OrderEdit(
            lines=[
                OrderLineEdit(id=line_id, quantity=Decimal("1"), product_id=product.id),
                OrderLineEdit(quantity=Decimal("1"), label="Unbekanntes Teil"),
            ]
        ),
    )
    assert len(result.lines) == 2
    labels = {ln.label for ln in result.lines}
    assert "Schild" in labels
    assert "Unbekanntes Teil" in labels
    create_todos = db.scalars(
        select(WorkTodo).where(
            WorkTodo.order_id == order.id,
            WorkTodo.status == "open",
            WorkTodo.kind == "create_article",
        )
    ).all()
    assert len(create_todos) == 1
    db.close()


def _set_variant(db: Session, name: str = "Geburtstagsring") -> SetVariant:
    ps = ProductSet(name=name, handle=f"{name.casefold().replace(' ', '-')}-set")
    db.add(ps)
    db.flush()
    variant = SetVariant(
        set_id=ps.id,
        option1_name="Farbe",
        option1_value="Rot",
    )
    db.add(variant)
    db.flush()
    return variant


def _open_order_with_set(db: Session, variant: SetVariant, qty: str = "1") -> CustomerOrder:
    from app.schemas import OrderCreate, OrderLineCreate

    read = create_order(
        db,
        OrderCreate(
            ordered_on=datetime(2026, 9, 28, 12, 0, 0),
            customer_name="Set-Kunde",
            lines=[OrderLineCreate(quantity=Decimal(qty), set_variant_id=variant.id)],
        ),
    )
    return db.get(CustomerOrder, read.id)


def test_edit_note_does_not_reopen_completed_assemble():
    """Reine Notiz darf Zusammenstellen nicht erneut anlegen (sonst doppelte BOM-Abbuchung)."""
    db = _session()
    variant = _set_variant(db)
    order = _open_order_with_set(db, variant, "1")
    line = order.lines[0]
    todos = db.scalars(select(WorkTodo).where(WorkTodo.order_id == order.id, WorkTodo.status == "open")).all()
    assert len(todos) == 1
    assert todos[0].kind == "assemble"
    todos[0].status = "done"
    todos[0].completed_at = datetime(2026, 9, 28, 13, 0, 0)
    db.commit()
    order.status = "ready"
    db.commit()
    done_id = todos[0].id

    result = edit_order(
        db,
        order.id,
        OrderEdit(
            note="Personalisierung: Mia",
            lines=[OrderLineEdit(id=line.id, quantity=Decimal("1"), set_variant_id=variant.id)],
        ),
    )
    assert result.note == "Personalisierung: Mia"
    assert result.status == "ready"
    open_todos = db.scalars(select(WorkTodo).where(WorkTodo.order_id == order.id, WorkTodo.status == "open")).all()
    assert open_todos == []
    done = db.get(WorkTodo, done_id)
    assert done is not None
    assert done.status == "done"
    db.close()


def test_edit_note_keeps_open_manufacture_todo_id():
    db = _session()
    product = _product(db, "Ring Uni", stock=Decimal("0"))
    order = _open_order_with_product(db, product, "2")
    line = order.lines[0]
    todo = db.scalars(select(WorkTodo).where(WorkTodo.order_id == order.id, WorkTodo.status == "open")).one()
    todo_id = todo.id

    result = edit_order(
        db,
        order.id,
        OrderEdit(
            note="nur Notiz",
            lines=[OrderLineEdit(id=line.id, quantity=Decimal("2"), product_id=product.id)],
        ),
    )
    assert result.note == "nur Notiz"
    assert result.status == "open"
    still = db.scalars(select(WorkTodo).where(WorkTodo.order_id == order.id, WorkTodo.status == "open")).all()
    assert len(still) == 1
    assert still[0].id == todo_id
    assert still[0].quantity == Decimal("2")
    db.close()


def test_edit_assemble_qty_increase_after_done_creates_delta_only():
    db = _session()
    variant = _set_variant(db, "Delta-Set")
    order = _open_order_with_set(db, variant, "1")
    line = order.lines[0]
    todo = db.scalars(select(WorkTodo).where(WorkTodo.order_id == order.id, WorkTodo.status == "open")).one()
    todo.status = "done"
    db.commit()
    order.status = "ready"
    db.commit()

    result = edit_order(
        db,
        order.id,
        OrderEdit(
            lines=[OrderLineEdit(id=line.id, quantity=Decimal("3"), set_variant_id=variant.id)],
        ),
    )
    assert result.status == "open"
    open_todos = db.scalars(select(WorkTodo).where(WorkTodo.order_id == order.id, WorkTodo.status == "open")).all()
    assert len(open_todos) == 1
    assert open_todos[0].kind == "assemble"
    assert open_todos[0].quantity == Decimal("2")
    db.close()


def test_edit_rejects_shipped():
    db = _session()
    product = _product(db, "Versendet", stock=Decimal("5"))
    order = _open_order_with_product(db, product, "1")
    order.status = "shipped"
    db.commit()
    with pytest.raises(HTTPException) as exc:
        edit_order(
            db,
            order.id,
            OrderEdit(lines=[OrderLineEdit(quantity=Decimal("1"), label="x")]),
        )
    assert exc.value.status_code == 400
    assert "Versendete" in str(exc.value.detail)
    db.close()


def test_edit_admin_guard_on_router():
    db = _session()
    product = _product(db, "AdminGuard", stock=Decimal("5"))
    order = _open_order_with_product(db, product, "1")

    app = FastAPI()
    app.include_router(router)

    staff = User(username="staff", password_hash="x", role=UserRole.MITARBEITER)
    admin = User(username="admin", password_hash="x", role=UserRole.ADMIN)
    db.add_all([staff, admin])
    db.commit()

    def _get_db():
        yield db

    from app.database import get_db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[require_user] = lambda: staff

    client = TestClient(app)
    r = client.put(
        f"/api/orders/{order.id}/edit",
        json={"note": None, "lines": [{"quantity": "1", "label": "neu"}]},
    )
    assert r.status_code == 403

    app.dependency_overrides[require_user] = lambda: admin
    r2 = client.put(
        f"/api/orders/{order.id}/edit",
        json={"note": "ok", "lines": [{"quantity": "1", "label": "neu"}]},
    )
    assert r2.status_code == 200
    assert r2.json()["note"] == "ok"
    assert len(r2.json()["lines"]) == 1
    db.close()
