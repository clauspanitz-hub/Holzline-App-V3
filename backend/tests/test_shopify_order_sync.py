"""Shopify-Sync darf dieselbe Nummer nicht zweimal anlegen."""

from __future__ import annotations

import os
import tempfile
import threading
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, migrate_shopify_order_number_unique
from app.models import CustomerOrder, OrderLine, Product
from app.shopify_orders import _import_shopify_nodes, sync_shopify_orders


def _shop_order(name: str = "#1001", sku: str = "R1", title: str = "Ring", variant: str = "Rosa") -> dict:
    return {
        "name": name,
        "createdAt": "2026-09-13T10:00:00Z",
        "cancelledAt": None,
        "displayFinancialStatus": "PAID",
        "displayFulfillmentStatus": "UNFULFILLED",
        "customer": {"displayName": "Ada"},
        "shippingAddress": {},
        "lineItems": {
            "nodes": [
                {
                    "title": title,
                    "variantTitle": variant,
                    "sku": sku,
                    "quantity": 1,
                    "unfulfilledQuantity": 1,
                    "variant": {"sku": sku},
                }
            ]
        },
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

    Base.metadata.create_all(engine)
    migrate_shopify_order_number_unique(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session, factory
    finally:
        session.close()
        engine.dispose()
        Path(path).unlink(missing_ok=True)


def _add_product(session: Session, *, name: str = "Ring Rosa", sku: str = "R1") -> Product:
    product = Product(name=name, sku=sku, selling_price=Decimal("0"))
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


def test_second_sync_skips_existing_shopify_number(db_session):
    session, _factory = db_session
    _add_product(session)
    first = _import_shopify_nodes(session, [_shop_order()])
    assert first["created"] == 1
    second = _import_shopify_nodes(session, [_shop_order()])
    assert second["created"] == 0
    assert second["skipped"] >= 1
    assert session.scalars(select(CustomerOrder)).all().__len__() == 1


def test_null_nodes_do_not_abort_import(db_session):
    session, _factory = db_session
    _add_product(session)
    result = _import_shopify_nodes(
        session,
        [None, _shop_order(), {"name": "#1002", "lineItems": {"nodes": [None]}}],
    )
    assert result["created"] == 1
    order = session.scalars(select(CustomerOrder)).first()
    assert order is not None
    assert order.external_number == "#1001"
    lines = session.scalars(select(OrderLine)).all()
    assert len(lines) == 1


def test_unique_index_blocks_duplicate_shopify_number(db_session):
    session, _factory = db_session
    session.add(CustomerOrder(ordered_on=__import__("datetime").datetime.now(), origin="shopify", external_number="#1001", status="review"))
    session.commit()
    session.add(CustomerOrder(ordered_on=__import__("datetime").datetime.now(), origin="shopify", external_number="#1001", status="review"))
    with pytest.raises(Exception):
        session.commit()


def test_concurrent_sync_creates_order_once(db_session):
    session, factory = db_session
    _add_product(session)
    session.close()

    errors: list[BaseException] = []

    def worker() -> None:
        db = factory()
        try:
            with patch("app.shopify_orders.fetch_open_paid_orders", return_value=[_shop_order()]):
                sync_shopify_orders(db)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            db.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    check = factory()
    try:
        orders = check.scalars(select(CustomerOrder)).all()
        assert len(orders) == 1
        assert orders[0].external_number == "#1001"
    finally:
        check.close()
