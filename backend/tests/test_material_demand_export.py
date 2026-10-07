"""Tests für Materialbedarf-Export PDF/CSV (offene Einkauf-Todos)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, seed_locations
from app.material_demand_export import build_csv, build_pdf, collect_demand_rows
from app.models import (
    Location,
    Material,
    MaterialPurchaseSource,
    MaterialStock,
    Shop,
    Unit,
    WorkTodo,
)
from sqlalchemy import select


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


def test_collect_and_export_csv_pdf_open_purchase_todos():
    db = _session()
    shop = Shop(name="Holzshop")
    db.add(shop)
    db.flush()

    m = Material(
        name="Leimholz äöüß",
        unit=Unit.M2,
        purchase_quantity=Decimal("1"),
        purchase_price=Decimal("25"),
        cost_per_unit=Decimal("25"),
        min_stock=Decimal("2"),
        decimal_places=2,
        alternatives_note="Sperrholz ok",
    )
    db.add(m)
    db.flush()
    db.add(MaterialStock(material_id=m.id, location_id=_loc(db, "Hamburg").id, quantity=Decimal("0.5")))
    db.add(
        MaterialPurchaseSource(
            material_id=m.id,
            shop_id=shop.id,
            url="https://example.com/leimholz",
            note="Natur",
            is_preferred=True,
        )
    )
    db.add(
        WorkTodo(
            kind="purchase",
            category="purchase",
            status="open",
            source="auto",
            title="Einkauf: Leimholz äöüß",
            quantity=Decimal("3.5"),
            material_id=m.id,
        )
    )
    # Erledigtes Todo darf nicht in den Export
    db.add(
        WorkTodo(
            kind="purchase",
            category="purchase",
            status="done",
            source="auto",
            title="Einkauf: Alt",
            quantity=Decimal("1"),
            material_id=m.id,
        )
    )
    db.commit()

    rows = collect_demand_rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.material_name == "Leimholz äöüß"
    assert row.quantity == "3,5"
    assert row.unit == "m²"
    assert row.stock_available == "0,5"
    assert row.min_stock == "2"
    assert row.shop_name == "Holzshop"
    assert row.source_url == "https://example.com/leimholz"
    assert row.alternatives_note == "Sperrholz ok"

    csv_bytes = build_csv(rows)
    text = csv_bytes.decode("utf-8-sig")
    assert "Material;Menge;Einheit" in text
    assert "Leimholz äöüß;3,5;m²;0,5;2;Holzshop;https://example.com/leimholz" in text

    pdf_bytes = build_pdf(rows)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_export_empty_list():
    db = _session()
    rows = collect_demand_rows(db)
    assert rows == []
    csv_bytes = build_csv(rows)
    assert b"Material;Menge" in csv_bytes
    pdf_bytes = build_pdf(rows)
    assert pdf_bytes.startswith(b"%PDF")
