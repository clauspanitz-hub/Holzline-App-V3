"""Tests für Familien-Katalog mit Unterfamilien (ADR 0025)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, seed_locations
from app.families import (
    assign_article_family,
    create_family,
    delete_family,
    find_or_create_parent,
    list_families,
    migrate_family_catalogs,
)
from app.models import Material, MaterialFamily, Product, ProductFamily, Unit
from app.schemas import MaterialsFromColorsRequest, ProductsFromColorsRequest
from app import services


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
    migrate_family_catalogs(engine, db)
    return db


def test_separate_catalogs_and_one_level():
    db = _session()
    mat = create_family(db, "material", name="Lack")
    prod = create_family(db, "product", name="Lack")
    assert db.get(MaterialFamily, mat["id"]).name == "Lack"
    assert db.get(ProductFamily, prod["id"]).name == "Lack"
    assert db.scalars(select(MaterialFamily)).all()
    assert db.scalars(select(ProductFamily)).all()
    sub = create_family(db, "material", name="Vintage", parent_id=mat["id"])
    assert sub["parent_id"] == mat["id"]
    with pytest.raises(HTTPException) as exc:
        create_family(db, "material", name="ZuTief", parent_id=sub["id"])
    assert exc.value.status_code == 400
    db.close()


def test_migrate_free_text_to_parent():
    db = _session()
    m = Material(
        name="Ring Rot",
        unit=Unit.STK,
        purchase_quantity=Decimal("1"),
        purchase_price=Decimal("1"),
        cost_per_unit=Decimal("1"),
        family="Ring",
    )
    db.add(m)
    db.commit()
    engine = db.get_bind()
    migrate_family_catalogs(engine, db)
    db.refresh(m)
    assert m.family_id is not None
    fam = db.get(MaterialFamily, m.family_id)
    assert fam is not None
    assert fam.name == "Ring"
    assert fam.parent_id is None
    db.close()


def test_delete_blocked_with_articles_or_children():
    db = _session()
    parent = create_family(db, "product", name="Ring")
    create_family(db, "product", name="Vintage", parent_id=parent["id"])
    with pytest.raises(HTTPException) as exc:
        delete_family(db, "product", parent["id"])
    assert exc.value.status_code == 409

    leaf = create_family(db, "product", name="Solo")
    p = Product(name="P1", family_id=leaf["id"], family="Solo")
    db.add(p)
    db.commit()
    with pytest.raises(HTTPException) as exc2:
        delete_family(db, "product", leaf["id"])
    assert exc2.value.status_code == 409
    db.close()


def test_series_find_or_create_parent():
    db = _session()
    # Minimal medium/color for series
    from app.models import Color, ColorMedium

    medium = ColorMedium(name="Lack")
    db.add(medium)
    db.flush()
    color = Color(name="Rot", medium_id=medium.id)
    db.add(color)
    db.commit()

    result = services.create_products_from_colors(
        db,
        ProductsFromColorsRequest(
            base_name="Ring",
            color_ids=[color.id],
            min_stock=Decimal("1"),
        ),
    )
    assert len(result.created) == 1
    created = result.created[0]
    assert created.family == "Ring"
    assert created.family_id is not None
    fam = db.get(ProductFamily, created.family_id)
    assert fam is not None and fam.parent_id is None

    # second series same base reuses parent
    color2 = Color(name="Blau", medium_id=medium.id)
    db.add(color2)
    db.commit()
    result2 = services.create_products_from_colors(
        db,
        ProductsFromColorsRequest(
            base_name="Ring",
            color_ids=[color2.id],
            min_stock=Decimal("1"),
        ),
    )
    assert result2.created[0].family_id == created.family_id
    parents = [f for f in list_families(db, "product") if f["parent_id"] is None and f["name"] == "Ring"]
    assert len(parents) == 1
    db.close()


def test_parent_filter_includes_subfamily_articles_via_read_fields():
    db = _session()
    parent = create_family(db, "material", name="Holz")
    sub = create_family(db, "material", name="Buche", parent_id=parent["id"])
    m1 = Material(
        name="Holz A",
        unit=Unit.STK,
        purchase_quantity=Decimal("1"),
        purchase_price=Decimal("1"),
        cost_per_unit=Decimal("1"),
    )
    m2 = Material(
        name="Buche A",
        unit=Unit.STK,
        purchase_quantity=Decimal("1"),
        purchase_price=Decimal("1"),
        cost_per_unit=Decimal("1"),
    )
    db.add_all([m1, m2])
    db.flush()
    assign_article_family(m1, db.get(MaterialFamily, parent["id"]))
    assign_article_family(m2, db.get(MaterialFamily, sub["id"]))
    db.commit()

    rows = services.list_materials(db)
    by_name = {r.name: r for r in rows}
    assert by_name["Holz A"].family_parent_name is None
    assert by_name["Holz A"].family == "Holz"
    assert by_name["Buche A"].family_parent_name == "Holz"
    assert by_name["Buche A"].family == "Buche"
    db.close()


def test_find_or_create_parent_idempotent():
    db = _session()
    a = find_or_create_parent(db, "material", "PLA")
    db.commit()
    b = find_or_create_parent(db, "material", "PLA")
    db.commit()
    assert a.id == b.id
    db.close()
