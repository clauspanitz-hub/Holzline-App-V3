"""Shopify-Sync: gematchte Aufträge dürfen den Abruf nicht abstürzen."""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import CustomerOrder, Location, Product, ProductStock, WorkTodo
from app.shopify_orders import sync_shopify_orders


def _memory_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, _record) -> None:  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _paid_unfulfilled_order(*, name: str, sku: str, title: str, quantity: int = 2) -> dict:
    return {
        "name": name,
        "createdAt": "2026-09-16T10:00:00Z",
        "cancelledAt": None,
        "displayFinancialStatus": "PAID",
        "displayFulfillmentStatus": "UNFULFILLED",
        "shippingAddress": {"name": "Max Mustermann"},
        "note": "Bitte gravieren",
        "lineItems": {
            "nodes": [
                {
                    "title": title,
                    "variantTitle": None,
                    "name": title,
                    "sku": sku,
                    "quantity": quantity,
                    "unfulfilledQuantity": quantity,
                    "customAttributes": [],
                    "product": {"handle": "holzling-eiche", "title": title},
                    "variant": {
                        "sku": sku,
                        "title": "Default Title",
                        "selectedOptions": [],
                    },
                }
            ]
        },
    }


class ShopifyMatchedOrderSyncTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _memory_session()
        loc = Location(name="Hamburg", is_virtual=False)
        self.db.add(loc)
        self.db.flush()
        product = Product(name="Holzling Eiche", sku="HL-001")
        self.db.add(product)
        self.db.flush()
        self.db.add(ProductStock(product_id=product.id, location_id=loc.id, quantity=Decimal("10")))
        self.db.commit()
        self.product_id = product.id

    def tearDown(self) -> None:
        self.db.close()

    def test_fully_matched_order_is_created_without_crash(self) -> None:
        node = _paid_unfulfilled_order(name="#1842", sku="HL-001", title="Holzling Eiche")
        with patch("app.shopify_orders.fetch_open_paid_orders", return_value=[node]):
            result = sync_shopify_orders(self.db)

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["errors"], [])
        order = self.db.scalars(select(CustomerOrder)).one()
        self.assertEqual(order.origin, "shopify")
        self.assertEqual(order.external_number, "#1842")
        self.assertEqual(order.status, "ready")
        self.assertEqual(len(order.lines), 1)
        self.assertEqual(order.lines[0].product_id, self.product_id)
        open_todos = self.db.scalars(select(WorkTodo).where(WorkTodo.status == "open")).all()
        self.assertEqual(open_todos, [])

    def test_matched_order_without_stock_stays_open_with_manufacture_todo(self) -> None:
        stock = self.db.scalars(select(ProductStock)).one()
        stock.quantity = Decimal("0")
        self.db.commit()
        node = _paid_unfulfilled_order(name="#1843", sku="HL-001", title="Holzling Eiche")
        with patch("app.shopify_orders.fetch_open_paid_orders", return_value=[node]):
            result = sync_shopify_orders(self.db)

        self.assertEqual(result["created"], 1)
        order = self.db.scalars(select(CustomerOrder)).one()
        self.assertEqual(order.status, "open")
        todos = list(order.todos)
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0].kind, "manufacture")

    def test_unmatched_then_matched_in_same_batch_both_persist(self) -> None:
        unmatched = _paid_unfulfilled_order(name="#1001", sku="UNKNOWN", title="Unbekanntes Teil")
        matched = _paid_unfulfilled_order(name="#1002", sku="HL-001", title="Holzling Eiche")
        with patch("app.shopify_orders.fetch_open_paid_orders", return_value=[unmatched, matched]):
            result = sync_shopify_orders(self.db)

        self.assertEqual(result["created"], 2)
        numbers = {o.external_number: o.status for o in self.db.scalars(select(CustomerOrder)).all()}
        self.assertEqual(numbers["#1001"], "review")
        self.assertEqual(numbers["#1002"], "ready")


if __name__ == "__main__":
    unittest.main()
