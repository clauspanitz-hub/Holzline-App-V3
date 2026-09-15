"""Replace-Import darf Bestellungen nicht als leere Hüllen stehen lassen."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.backup import export_backup, import_backup
from app.models import CustomerOrder, Location, OrderLine, Product, WorkTodo


def _minimal_backup(product_name: str = "Ring Rosa") -> dict:
    return {
        "format": "holzlinge-backup",
        "version": 1,
        "locations": [{"name": "Hamburg", "is_virtual": False}],
        "color_media": [],
        "colors": [],
        "tags": [],
        "materials": [],
        "products": [{"name": product_name, "sku": "R1"}],
        "product_sets": [],
    }


@pytest.fixture()
def db_session():
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, _connection_record) -> None:  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from app.database import Base

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        Path(path).unlink(missing_ok=True)


def _seed_product_and_order(session):
    session.add(Location(name="Hamburg", is_virtual=False))
    session.flush()
    product = Product(name="Ring Rosa", sku="R1", selling_price=Decimal("12.00"))
    session.add(product)
    session.flush()
    order = CustomerOrder(
        ordered_on=datetime(2026, 9, 14, 10, 0, 0),
        customer_name="Ada",
        external_number="#1001",
        origin="shopify",
        status="open",
    )
    session.add(order)
    session.flush()
    line = OrderLine(
        order_id=order.id,
        quantity=Decimal("1"),
        label="Ring Rosa",
        product_id=product.id,
    )
    session.add(line)
    session.flush()
    session.add(
        WorkTodo(
            order_id=order.id,
            order_line_id=line.id,
            kind="manufacture",
            category="workshop",
            status="open",
            title="Fertigen: Ring Rosa",
            quantity=Decimal("1"),
            product_id=product.id,
        )
    )
    session.commit()
    return product.id, order.id


def test_replace_import_clears_orders_instead_of_orphaning_them(db_session):
    _product_id, order_id = _seed_product_and_order(db_session)
    payload = export_backup(db_session)
    assert any(p["name"] == "Ring Rosa" for p in payload["products"])

    result = import_backup(db_session, payload, mode="replace")
    assert result["mode"] == "replace"

    remaining_orders = db_session.scalars(select(CustomerOrder)).all()
    remaining_lines = db_session.scalars(select(OrderLine)).all()
    remaining_todos = db_session.scalars(select(WorkTodo)).all()
    assert remaining_orders == []
    assert remaining_lines == []
    assert remaining_todos == []

    restored = db_session.scalars(select(Product).where(Product.name == "Ring Rosa")).first()
    assert restored is not None
    assert restored.sku == "R1"
    assert db_session.get(CustomerOrder, order_id) is None


def test_merge_import_keeps_linked_orders(db_session):
    product_id, order_id = _seed_product_and_order(db_session)
    result = import_backup(db_session, _minimal_backup(), mode="merge")
    assert result["mode"] == "merge"

    order = db_session.get(CustomerOrder, order_id)
    assert order is not None
    assert order.external_number == "#1001"
    line = db_session.scalars(select(OrderLine).where(OrderLine.order_id == order_id)).first()
    assert line is not None
    assert line.product_id == product_id
