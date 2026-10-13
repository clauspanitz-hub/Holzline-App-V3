"""Verkaufsstatistik aus shipped Order-Lines + Set-BOM (ADR 0032)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password, mitarbeiter_allowed, require_user
from app.database import Base, get_db, seed_locations
from app.models import (
    CustomerOrder,
    Material,
    OrderLine,
    Product,
    ProductSet,
    SetBomLine,
    SetVariant,
    User,
    UserRole,
)
from app.routers import router
from app.sales_stats import product_sales


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


def _client(db: Session, user: User) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[require_user] = lambda: user
    return TestClient(app)


def _admin(db: Session) -> User:
    user = User(username="admin", password_hash=hash_password("secret12"), role=UserRole.ADMIN)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _mitarbeiter(db: Session) -> User:
    user = User(username="simona", password_hash=hash_password("secret12"), role=UserRole.MITARBEITER)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _product(db: Session, name: str) -> Product:
    p = Product(name=name, selling_price=Decimal("10"))
    db.add(p)
    db.flush()
    return p


def _order(
    db: Session,
    *,
    status: str,
    lines: list[tuple[Decimal, int | None, int | None, int | None, str]],
) -> CustomerOrder:
    """lines: (qty, product_id, material_id, set_variant_id, label)"""
    order = CustomerOrder(
        ordered_on=datetime.now(timezone.utc),
        customer_name="Test",
        origin="manual",
        status=status,
    )
    db.add(order)
    db.flush()
    for qty, product_id, material_id, set_variant_id, label in lines:
        db.add(
            OrderLine(
                order_id=order.id,
                quantity=qty,
                label=label,
                product_id=product_id,
                material_id=material_id,
                set_variant_id=set_variant_id,
            )
        )
    db.commit()
    db.refresh(order)
    return order


def test_only_shipped_counts_direct_product():
    db = _session()
    ring = _product(db, "Ring Rosa")
    candle = _product(db, "Kerze Blau")
    db.commit()

    _order(db, status="shipped", lines=[(Decimal("3"), ring.id, None, None, "Ring")])
    _order(db, status="open", lines=[(Decimal("10"), ring.id, None, None, "Ring")])
    _order(db, status="ready", lines=[(Decimal("5"), candle.id, None, None, "Kerze")])
    _order(db, status="review", lines=[(Decimal("7"), candle.id, None, None, "Kerze")])
    _order(db, status="shipped", lines=[(Decimal("2"), candle.id, None, None, "Kerze")])

    rows = product_sales(db)
    by_id = {r.product_id: r for r in rows}
    assert ring.id in by_id
    assert by_id[ring.id].quantity_sold == Decimal("3")
    assert by_id[candle.id].quantity_sold == Decimal("2")
    assert all(r.quantity_sold > 0 for r in rows)
    db.close()


def test_set_bom_products_only_multiply_quantity():
    db = _session()
    ring = _product(db, "Ring Uni")
    number = _product(db, "Zahlenstecker")
    mat = Material(name="Kerze lose", unit="Stk", purchase_quantity=Decimal("1"), purchase_price=Decimal("1"))
    db.add(mat)
    db.flush()

    ps = ProductSet(name="Geburtstagsset", handle="geburtstag")
    db.add(ps)
    db.flush()
    variant = SetVariant(set_id=ps.id, option1_name="Farbe", option1_value="Rosa")
    db.add(variant)
    db.flush()
    db.add(SetBomLine(variant_id=variant.id, product_id=ring.id, quantity_required=Decimal("1")))
    db.add(SetBomLine(variant_id=variant.id, product_id=number.id, quantity_required=Decimal("2")))
    db.add(SetBomLine(variant_id=variant.id, material_id=mat.id, quantity_required=Decimal("10")))
    db.commit()

    _order(
        db,
        status="shipped",
        lines=[(Decimal("3"), None, None, variant.id, "Set")],
    )
    # Material-only + Freitext dürfen nicht erscheinen
    _order(
        db,
        status="shipped",
        lines=[
            (Decimal("9"), None, mat.id, None, "Material"),
            (Decimal("4"), None, None, None, "Freitext Schild"),
        ],
    )

    rows = product_sales(db)
    by_id = {r.product_id: r.quantity_sold for r in rows}
    assert by_id[ring.id] == Decimal("3")  # 3 × 1
    assert by_id[number.id] == Decimal("6")  # 3 × 2
    assert len(rows) == 2
    # Ranking: number (6) vor ring (3)
    assert rows[0].product_id == number.id
    assert rows[1].product_id == ring.id
    db.close()


def test_limit_and_api_endpoint():
    db = _session()
    user = _admin(db)
    products = [_product(db, f"P{i}") for i in range(5)]
    db.commit()
    for i, p in enumerate(products):
        _order(db, status="shipped", lines=[(Decimal(str(i + 1)), p.id, None, None, p.name)])

    top2 = product_sales(db, limit=2)
    assert len(top2) == 2
    assert top2[0].quantity_sold == Decimal("5")
    assert top2[1].quantity_sold == Decimal("4")

    client = _client(db, user)
    res = client.get("/api/stats/product-sales?limit=2")
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data) == 2
    assert data[0]["product_name"] == "P4"
    assert Decimal(str(data[0]["quantity_sold"])) == Decimal("5")

    full = client.get("/api/stats/product-sales")
    assert full.status_code == 200
    assert len(full.json()) == 5

    staff = _client(db, _mitarbeiter(db))
    staff_res = staff.get("/api/stats/product-sales")
    assert staff_res.status_code == 200
    assert len(staff_res.json()) == 5
    db.close()


def test_empty_when_no_shipped():
    db = _session()
    p = _product(db, "Alone")
    db.commit()
    _order(db, status="open", lines=[(Decimal("1"), p.id, None, None, "x")])
    assert product_sales(db) == []
    db.close()


def test_mitarbeiter_allowlist_includes_product_sales():
    assert mitarbeiter_allowed("GET", "/api/stats/product-sales")
    assert not mitarbeiter_allowed("POST", "/api/stats/product-sales")
