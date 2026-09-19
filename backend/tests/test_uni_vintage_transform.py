"""Tests für Uni→Vintage Namensauflösung und Transform (ADR 0006)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, seed_locations
from app.models import Location, Product, ProductStock
from app.schemas import TransformRequest
from app.services import (
    find_uni_transform_target,
    product_name_allows_transform,
    transform_product,
    vintage_name_from_uni,
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


def test_vintage_name_from_uni():
    assert vintage_name_from_uni("Geburtstagsring - Uni - Salbei") == "Geburtstagsring - Vintage - Salbei"
    assert vintage_name_from_uni("uni ring") == "Vintage ring"
    assert vintage_name_from_uni("Universal") is None
    assert vintage_name_from_uni("Vintage Ring") is None
    assert product_name_allows_transform("Ring Uni")
    assert not product_name_allows_transform("Universal")


def test_find_and_transform_by_name():
    db = _session()
    ma1 = _loc(db, "MA1")
    uni = Product(name="Ring - Uni - Rot", selling_price=Decimal("0"))
    vin = Product(name="Ring - Vintage - Rot", selling_price=Decimal("0"))
    db.add_all([uni, vin])
    db.flush()
    db.add(ProductStock(product_id=uni.id, location_id=ma1.id, quantity=Decimal("3")))
    db.commit()

    uni = db.get(Product, uni.id)
    target = find_uni_transform_target(db, uni)
    assert target is not None
    assert target.name == "Ring - Vintage - Rot"

    result = transform_product(
        db,
        uni.id,
        TransformRequest(location_id=ma1.id, quantity=Decimal("2"), note=None),
        actor="test",
    )
    assert result.transform_target_name == "Ring - Vintage - Rot"

    uni_stock = db.scalars(
        select(ProductStock).where(ProductStock.product_id == uni.id, ProductStock.location_id == ma1.id)
    ).one()
    vin_stock = db.scalars(
        select(ProductStock).where(ProductStock.product_id == vin.id, ProductStock.location_id == ma1.id)
    ).one()
    assert uni_stock.quantity == Decimal("1")
    assert vin_stock.quantity == Decimal("2")
    db.close()


def test_transform_fails_without_vintage_product():
    db = _session()
    ma1 = _loc(db, "MA1")
    uni = Product(name="Ring - Uni - Blau", selling_price=Decimal("0"))
    db.add(uni)
    db.flush()
    db.add(ProductStock(product_id=uni.id, location_id=ma1.id, quantity=Decimal("1")))
    db.commit()

    from fastapi import HTTPException

    try:
        transform_product(
            db,
            uni.id,
            TransformRequest(location_id=ma1.id, quantity=Decimal("1"), note=None),
        )
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "Vintage" in exc.detail
    db.close()
