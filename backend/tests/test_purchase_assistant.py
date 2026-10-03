"""Tests für Einkaufsassistent (Stückpreis aus Ausbeute, ADR 0028)."""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, seed_locations
from app.models import Location, Material, MaterialProductYield, MaterialStock, Product, ProductMaterial, Unit
from app.schemas import PurchaseAssistantApply, PurchaseAssistantItem
from app.services import (
    apply_purchase_assistant,
    bom_quantity_from_yield,
    list_material_yields,
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


def test_apply_preserves_purchase_quantity_and_scales_bom():
    """Bestehende Einkaufsmenge (z. B. 750 g Filament) darf nicht auf 1 gesetzt werden."""
    db = _session()
    material = Material(
        name="PLA Schwarz",
        unit=Unit.G,
        purchase_quantity=Decimal("750"),
        purchase_price=Decimal("25.00"),
        cost_per_unit=Decimal("0.0333"),
    )
    db.add(material)
    db.flush()
    loc = db.scalars(select(Location).where(Location.name == "Hamburg")).one()
    db.add(MaterialStock(material_id=material.id, location_id=loc.id, quantity=Decimal("750")))
    ring = _product(db, "Ring Uni")
    other = _product(db, "Ring Vintage")
    db.add(
        ProductMaterial(
            product_id=ring.id,
            material_id=material.id,
            component_product_id=None,
            quantity_required=Decimal("12"),
        )
    )
    db.add(
        ProductMaterial(
            product_id=other.id,
            material_id=material.id,
            component_product_id=None,
            quantity_required=Decimal("15"),
        )
    )
    db.flush()

    derived = list_material_yields(db, material.id)
    by_name = {row.product_name: row for row in derived}
    assert by_name["Ring Uni"].pieces_per_unit == Decimal("62.500")  # 750 / 12
    assert by_name["Ring Vintage"].pieces_per_unit == Decimal("50.000")  # 750 / 15

    result = apply_purchase_assistant(
        db,
        PurchaseAssistantApply(
            material_id=material.id,
            purchase_price=Decimal("30.00"),
            purchase_quantity=Decimal("1"),  # Frontend/ADR schickte bisher immer 1
            items=[PurchaseAssistantItem(product_id=ring.id, pieces_per_unit=Decimal("60"))],
        ),
    )

    assert result.material.purchase_quantity == Decimal("750.000")
    assert result.material.purchase_price == Decimal("30.00")
    assert result.material.cost_per_unit == Decimal("0.0400")  # 30 / 750

    stock = db.scalars(
        select(MaterialStock).where(MaterialStock.material_id == material.id)
    ).one()
    assert stock.quantity == Decimal("750")

    line_ring = db.scalars(
        select(ProductMaterial).where(
            ProductMaterial.product_id == ring.id,
            ProductMaterial.material_id == material.id,
        )
    ).one()
    assert line_ring.quantity_required == Decimal("12.500")  # 750 / 60

    line_other = db.scalars(
        select(ProductMaterial).where(
            ProductMaterial.product_id == other.id,
            ProductMaterial.material_id == material.id,
        )
    ).one()
    assert line_other.quantity_required == Decimal("15.000")

    prod_other = _load_product(db, other.id)
    # 15 g * (30 / 750) = 0.60 — nicht 15 * 30
    assert material_cost_for_product(prod_other) == Decimal("0.60")


def test_apply_rejects_yield_that_quantizes_bom_to_zero():
    db = _session()
    material = _material(db)
    product = _product(db, "Winzig")
    try:
        apply_purchase_assistant(
            db,
            PurchaseAssistantApply(
                material_id=material.id,
                purchase_price=Decimal("10.00"),
                items=[PurchaseAssistantItem(product_id=product.id, pieces_per_unit=Decimal("2000"))],
            ),
        )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "Stücklistenmenge würde 0" in str(exc.detail)
    else:
        raise AssertionError("erwartete HTTPException bei Ausbeute 2000")
