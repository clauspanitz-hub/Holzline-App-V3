"""Tests für manuelle Todos (ADR 0027)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, seed_locations
from app.models import CustomerOrder, Product, ProductStock, WorkTodo
from app.schemas import OrderCreate, OrderEdit, OrderLineCreate, OrderLineEdit, TodoCreate, TodoUpdate
from app.services import create_order, create_todo, edit_order, update_todo


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


def test_create_manual_todo_minimal():
    db = _session()
    read = create_todo(
        db,
        TodoCreate(kind="manufacture", title="Vorproduzieren Ringe", quantity=Decimal("5")),
    )
    assert read.source == "manual"
    assert read.kind == "manufacture"
    assert read.title == "Vorproduzieren Ringe"
    assert read.quantity == Decimal("5.000")
    assert read.order_id is None
    assert read.product_id is None
    assert read.category == "workshop"


def test_create_manual_purchase_and_link_order():
    db = _session()
    product = _product(db, "Brett", stock=Decimal("0"))
    order_read = create_order(
        db,
        OrderCreate(
            ordered_on=datetime(2026, 10, 3, 12, 0, 0),
            customer_name="Claus",
            lines=[OrderLineCreate(quantity=Decimal("1"), product_id=product.id)],
        ),
    )
    todo = create_todo(
        db,
        TodoCreate(
            kind="purchase",
            title="Leim nachbestellen",
            quantity=Decimal("2"),
            order_id=order_read.id,
        ),
    )
    assert todo.source == "manual"
    assert todo.category == "purchase"
    assert todo.order_id == order_read.id
    assert todo.order_line_id is None


def test_manual_todo_survives_line_sync():
    db = _session()
    product = _product(db, "Ring Uni", stock=Decimal("0"))
    order_read = create_order(
        db,
        OrderCreate(
            ordered_on=datetime(2026, 10, 3, 12, 0, 0),
            customer_name="Test",
            lines=[OrderLineCreate(quantity=Decimal("2"), product_id=product.id)],
        ),
    )
    order = db.get(CustomerOrder, order_read.id)
    line = order.lines[0]
    manual = create_todo(
        db,
        TodoCreate(
            kind="manufacture",
            title="Manuell: Extra Fertigen",
            quantity=Decimal("1"),
            order_id=order.id,
            order_line_id=line.id,
            product_id=product.id,
        ),
    )
    assert manual.source == "manual"

    edit_order(
        db,
        order.id,
        OrderEdit(
            lines=[
                OrderLineEdit(
                    id=line.id,
                    quantity=Decimal("4"),
                    product_id=product.id,
                    label=product.name,
                )
            ]
        ),
    )
    remaining = db.scalars(
        select(WorkTodo).where(WorkTodo.id == manual.id)
    ).first()
    assert remaining is not None
    assert remaining.status == "open"
    assert remaining.source == "manual"
    assert remaining.title == "Manuell: Extra Fertigen"
    assert remaining.quantity == Decimal("1.000")

    autos = db.scalars(
        select(WorkTodo).where(
            WorkTodo.order_line_id == line.id,
            WorkTodo.source == "auto",
            WorkTodo.status == "open",
        )
    ).all()
    assert len(autos) == 1
    assert autos[0].kind == "manufacture"
    assert autos[0].quantity == Decimal("4.000")


def test_update_manual_todo():
    db = _session()
    created = create_todo(db, TodoCreate(kind="manufacture", title="Alt", quantity=Decimal("1")))
    updated = update_todo(
        db,
        created.id,
        TodoUpdate(kind="assemble", title="Neu", quantity=Decimal("3"), set_variant_id=None),
    )
    assert updated.kind == "assemble"
    assert updated.title == "Neu"
    assert updated.quantity == Decimal("3.000")
    assert updated.category == "workshop"
