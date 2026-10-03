"""Tests für Einkaufsassistent (Stückpreis aus Ausbeute, ADR 0028)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, seed_locations
from app.models import Material, MaterialProductYield, Product, ProductMaterial, Unit
from app.schemas import PurchaseAssistantApply, PurchaseAssistantItem
from app.services import (
    apply_purchase_assistant,
    bom_quantity_from_yield,
    material_cost_for_product,
    piece_price_from_yield,
    _load_product,
)


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


def _material(db: Session, name: str = "Leimholz Buche") -> Material:
    m = Material(
        name=name,
        unit=Unit.STK,
        purchase_quantity=Decimal("1"),
        purchase_price=Decimal("0"),
        cost_per_unit=Decimal("0"),
    )
    db.add(m)
    db.flush()
    return m


def _product(db: Session, name: str) -> Product:
    p = Product(name=name, sku=None, selling_price=Decimal("10"))
    db.add(p)
    db.flush()
    return p


def test_piece_price_formula():
    assert piece_price_from_yield(Decimal("24.00"), Decimal("8")) == Decimal("3.00")
    assert piece_price_from_yield(Decimal("10.00"), Decimal("3")) == Decimal("3.33")
    assert bom_quantity_from_yield(Decimal("8")) == Decimal("0.125")
    assert bom_quantity_from_yield(Decimal("4")) == Decimal("0.250")


def test_apply_existing_material_sets_price_bom_and_yield():
    db = _session()
    material = _material(db)
    p1 = _product(db, "Ring Uni")
    p2 = _product(db, "Ring Vintage")

    result = apply_purchase_assistant(
        db,
        PurchaseAssistantApply(
            material_id=material.id,
            purchase_price=Decimal("24.00"),
            items=[
                PurchaseAssistantItem(product_id=p1.id, pieces_per_unit=Decimal("8")),
                PurchaseAssistantItem(product_id=p2.id, pieces_per_unit=Decimal("4")),
            ],
        ),
    )

    assert result.created_material is False
    assert result.material.purchase_price == Decimal("24.00")
    assert result.material.purchase_quantity == Decimal("1.000")
    assert result.material.cost_per_unit == Decimal("24.0000")

    m = db.get(Material, material.id)
    assert m is not None
    assert m.purchase_price == Decimal("24.00")

    line1 = db.scalars(
        select(ProductMaterial).where(
            ProductMaterial.product_id == p1.id,
            ProductMaterial.material_id == material.id,
        )
    ).one()
    assert line1.quantity_required == Decimal("0.125")

    line2 = db.scalars(
        select(ProductMaterial).where(
            ProductMaterial.product_id == p2.id,
            ProductMaterial.material_id == material.id,
        )
    ).one()
    assert line2.quantity_required == Decimal("0.250")

    yields = db.scalars(
        select(MaterialProductYield).where(MaterialProductYield.material_id == material.id)
    ).all()
    assert len(yields) == 2

    prod1 = _load_product(db, p1.id)
    # 0.125 * 24 = 3.00
    assert material_cost_for_product(prod1) == Decimal("3.00")


def test_apply_creates_material_then_bom():
    db = _session()
    product = _product(db, "Kerze")

    result = apply_purchase_assistant(
        db,
        PurchaseAssistantApply(
            new_material_name="Filz Rolle Blau",
            purchase_price=Decimal("12.00"),
            items=[PurchaseAssistantItem(product_id=product.id, pieces_per_unit=Decimal("6"))],
        ),
    )

    assert result.created_material is True
    assert result.material.name == "Filz Rolle Blau"
    assert result.material.unit == Unit.STK
    assert result.material.purchase_price == Decimal("12.00")

    material = db.scalars(select(Material).where(Material.name == "Filz Rolle Blau")).one()
    line = db.scalars(
        select(ProductMaterial).where(
            ProductMaterial.product_id == product.id,
            ProductMaterial.material_id == material.id,
        )
    ).one()
    assert line.quantity_required == Decimal("0.167")  # 1/6 quantized to 3 dp

    y = db.scalars(
        select(MaterialProductYield).where(
            MaterialProductYield.material_id == material.id,
            MaterialProductYield.product_id == product.id,
        )
    ).one()
    assert y.pieces_per_unit == Decimal("6.000")
