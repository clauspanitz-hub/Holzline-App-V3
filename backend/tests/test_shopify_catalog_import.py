"""Shopify-CSV-Assistent: Set-Import darf nicht an sku/price im Parser-Dict scheitern."""

from __future__ import annotations

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, seed_locations
from app.models import ProductSet, SetVariant
from app.schemas import ShopifyApplyRequest
from app.services import apply_shopify_catalog_csv


CSV_WITH_SKU_AND_PRICE = """Handle,Title,Option1 Name,Option1 Value,Option2 Name,Option2 Value,Option3 Name,Option3 Value,Variant SKU,Variant Price
geburtstagsring,Geburtstagsring,Farbe,Salbei,Form,rund,,,GR-SALBEI-RUND,79.90
geburtstagsring,Geburtstagsring,Farbe,Rot,Form,eckig,,,GR-ROT-ECKIG,79.90
"""


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


def test_apply_set_action_accepts_csv_sku_and_price():
    db = _session()
    result = apply_shopify_catalog_csv(
        db,
        CSV_WITH_SKU_AND_PRICE,
        ShopifyApplyRequest(items=[{"handle": "geburtstagsring", "action": "set"}]),
    )
    assert result.sets_created == 1
    assert result.variants_upserted == 2

    product_set = db.scalars(select(ProductSet).where(ProductSet.handle == "geburtstagsring")).one()
    assert product_set.name == "Geburtstagsring"
    variants = list(
        db.scalars(select(SetVariant).where(SetVariant.set_id == product_set.id)).all()
    )
    assert len(variants) == 2
    values = {(v.option1_value, v.option2_value) for v in variants}
    assert values == {("Salbei", "rund"), ("Rot", "eckig")}
    db.close()
