"""JSON-Backup muss Bezugsquellen, Shops und Materialnotizen erhalten."""

from __future__ import annotations

import os
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.backup import export_backup, import_backup
from app.models import (
    Location,
    Material,
    MaterialPurchaseSource,
    Shop,
    Unit,
)


def _minimal_backup(**overrides) -> dict:
    payload = {
        "format": "holzlinge-backup",
        "version": 1,
        "locations": [{"name": "Hamburg", "is_virtual": False}],
        "color_media": [],
        "colors": [],
        "tags": [],
        "shops": [],
        "materials": [],
        "products": [],
        "product_sets": [],
    }
    payload.update(overrides)
    return payload


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


def _seed_material_with_source(session):
    session.add(Location(name="Hamburg", is_virtual=False))
    shop = Shop(name="Amazon", domain_hint="amazon.de")
    session.add(shop)
    session.flush()
    material = Material(
        name="PLA Rosa",
        unit=Unit.G,
        purchase_quantity=Decimal("1000"),
        purchase_price=Decimal("20.00"),
        cost_per_unit=Decimal("0.02"),
        reorder_quantity=Decimal("2000"),
        last_purchase_quantity=Decimal("1500"),
        alternatives_note="Auch bei Modulor",
        products_note="Für Ringe",
    )
    session.add(material)
    session.flush()
    session.add(
        MaterialPurchaseSource(
            material_id=material.id,
            shop_id=shop.id,
            url="https://amazon.de/pla-rosa",
            note="1 kg Rolle",
            is_preferred=True,
        )
    )
    session.commit()
    return material.id, shop.id


def test_export_includes_shops_and_purchase_sources(db_session):
    _seed_material_with_source(db_session)
    payload = export_backup(db_session)

    assert any(s["name"] == "Amazon" for s in payload["shops"])
    material = next(m for m in payload["materials"] if m["name"] == "PLA Rosa")
    assert material["reorder_quantity"] == "2000.000"
    assert material["last_purchase_quantity"] == "1500.000"
    assert material["alternatives_note"] == "Auch bei Modulor"
    assert material["products_note"] == "Für Ringe"
    assert material["purchase_sources"] == [
        {
            "shop_name": "Amazon",
            "url": "https://amazon.de/pla-rosa",
            "note": "1 kg Rolle",
            "is_preferred": True,
        }
    ]


def test_replace_import_restores_purchase_sources(db_session):
    _seed_material_with_source(db_session)
    payload = export_backup(db_session)

    leftover = Shop(name="Alter Shop", domain_hint="old.example")
    db_session.add(leftover)
    db_session.commit()

    result = import_backup(db_session, payload, mode="replace")
    assert result["mode"] == "replace"

    shop = db_session.scalars(select(Shop).where(Shop.name == "Amazon")).first()
    assert shop is not None
    assert shop.domain_hint == "amazon.de"
    assert db_session.scalars(select(Shop).where(Shop.name == "Alter Shop")).first() is None

    material = db_session.scalars(select(Material).where(Material.name == "PLA Rosa")).first()
    assert material is not None
    assert material.reorder_quantity == Decimal("2000")
    assert material.last_purchase_quantity == Decimal("1500")
    assert material.alternatives_note == "Auch bei Modulor"
    assert material.products_note == "Für Ringe"
    sources = list(material.purchase_sources)
    assert len(sources) == 1
    assert sources[0].url == "https://amazon.de/pla-rosa"
    assert sources[0].shop_id == shop.id
    assert sources[0].is_preferred is True
    assert sources[0].note == "1 kg Rolle"


def test_merge_of_legacy_backup_keeps_existing_sources(db_session):
    material_id, shop_id = _seed_material_with_source(db_session)
    legacy = _minimal_backup(
        materials=[
            {
                "name": "PLA Rosa",
                "unit": "g",
                "purchase_quantity": "1000",
                "purchase_price": "20.00",
            }
        ]
    )
    result = import_backup(db_session, legacy, mode="merge")
    assert result["mode"] == "merge"

    material = db_session.get(Material, material_id)
    assert material is not None
    sources = list(material.purchase_sources)
    assert len(sources) == 1
    assert sources[0].shop_id == shop_id
    assert material.alternatives_note == "Auch bei Modulor"
    assert material.reorder_quantity == Decimal("2000")
