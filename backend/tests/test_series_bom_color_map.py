"""Serienanlage must remap BOM materials by name/family, not by arbitrary colour."""

from __future__ import annotations

import os
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import (
    Color,
    ColorMedium,
    Location,
    Material,
    Product,
    ProductMaterial,
    Unit,
)
from app.schemas import ProductsFromColorsRequest
from app.services import create_products_from_colors


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
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        Path(path).unlink(missing_ok=True)


def _palette(session: Session) -> tuple[Color, Color]:
    session.add(Location(name="Hamburg", is_virtual=False))
    medium = ColorMedium(name="Kerze")
    session.add(medium)
    session.flush()
    sage = Color(name="Salbeigrün", medium_id=medium.id)
    beige = Color(name="Beige", medium_id=medium.id)
    session.add_all([sage, beige])
    session.flush()
    return sage, beige


def _material(
    session: Session,
    name: str,
    color: Color,
    family: str,
) -> Material:
    row = Material(
        name=name,
        unit=Unit.STK,
        family=family,
        color_id=color.id,
        purchase_quantity=Decimal("1"),
        purchase_price=Decimal("0"),
        cost_per_unit=Decimal("0"),
    )
    session.add(row)
    session.flush()
    return row


def test_series_keeps_each_candle_material_in_kerzenset_bom(db_session: Session):
    sage, beige = _palette(db_session)
    klein_sage = _material(db_session, "Kerze klein Salbeigrün", sage, "Kerze klein")
    licht_sage = _material(db_session, "Lebenslicht Salbeigrün", sage, "Lebenslicht")
    # Beige Lebenslicht first: old code picked the lowest id of that colour for every line.
    licht_beige = _material(db_session, "Lebenslicht Beige", beige, "Lebenslicht")
    klein_beige = _material(db_session, "Kerze klein Beige", beige, "Kerze klein")

    template = Product(name="Kerzenset Salbeigrün", color_id=sage.id, family="Kerzenset")
    db_session.add(template)
    db_session.flush()
    db_session.add_all(
        [
            ProductMaterial(
                product_id=template.id,
                material_id=klein_sage.id,
                quantity_required=Decimal("10"),
            ),
            ProductMaterial(
                product_id=template.id,
                material_id=licht_sage.id,
                quantity_required=Decimal("1"),
            ),
        ]
    )
    db_session.commit()

    result = create_products_from_colors(
        db_session,
        ProductsFromColorsRequest(
            color_ids=[beige.id],
            base_name="Kerzenset",
            template_product_id=template.id,
        ),
    )
    assert result.warnings == []
    assert len(result.created) == 1
    created = result.created[0]
    by_material = {line.material_id: line for line in created.bom}
    assert set(by_material) == {klein_beige.id, licht_beige.id}
    assert by_material[klein_beige.id].quantity_required == Decimal("10")
    assert by_material[licht_beige.id].quantity_required == Decimal("1")


def test_series_does_not_borrow_unrelated_material_of_same_color(db_session: Session):
    sage, beige = _palette(db_session)
    klein_sage = _material(db_session, "Kerze klein Salbeigrün", sage, "Kerze klein")
    # No "Kerze klein Beige" — only an unrelated beige material.
    _material(db_session, "PLA Beige", beige, "PLA")
    template = Product(name="Kerzenset Salbeigrün", color_id=sage.id, family="Kerzenset")
    db_session.add(template)
    db_session.flush()
    db_session.add(
        ProductMaterial(
            product_id=template.id,
            material_id=klein_sage.id,
            quantity_required=Decimal("10"),
        )
    )
    db_session.commit()

    result = create_products_from_colors(
        db_session,
        ProductsFromColorsRequest(
            color_ids=[beige.id],
            base_name="Kerzenset",
            template_product_id=template.id,
        ),
    )
    assert len(result.created) == 1
    assert result.created[0].bom == []
    assert any("Kerze klein Salbeigrün" in w for w in result.warnings)

    leftover = db_session.scalars(select(ProductMaterial).where(ProductMaterial.product_id == result.created[0].id)).all()
    assert leftover == []
