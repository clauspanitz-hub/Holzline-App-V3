"""Tests für Einkauf-Todos Auto-Sync (ADR 0023), inkl. Negativbestand nach Fertigung."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, seed_locations
from app.models import (
    Location,
    Material,
    MaterialStock,
    Product,
    ProductMaterial,
    ProductSet,
    SetBomLine,
    SetVariant,
    Unit,
    WorkTodo,
)
from app.purchase_todos import (
    generate_purchase_todos,
    is_material_critical,
    material_has_negative_location,
    material_needs_purchase_todo,
    material_stock_available,
    sync_purchase_todos,
)
from app.services import assemble_variant, manufacture


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


def _material(
    db: Session,
    *,
    min_stock: Decimal | None,
    hamburg: Decimal,
    ausschuss: Decimal = Decimal("0"),
    dahlenburg: Decimal | None = None,
    name: str | None = None,
) -> Material:
    m = Material(
        name=name or f"Mat-{hamburg}-{ausschuss}-{min_stock}",
        unit=Unit.STK,
        purchase_quantity=Decimal("10"),
        purchase_price=Decimal("1"),
        cost_per_unit=Decimal("0.1"),
        min_stock=min_stock,
    )
    db.add(m)
    db.flush()
    db.add(MaterialStock(material_id=m.id, location_id=_loc(db, "Hamburg").id, quantity=hamburg))
    if dahlenburg is not None:
        db.add(
            MaterialStock(
                material_id=m.id,
                location_id=_loc(db, "Dahlenburg").id,
                quantity=dahlenburg,
            )
        )
    if ausschuss:
        db.add(MaterialStock(material_id=m.id, location_id=_loc(db, "Ausschuss").id, quantity=ausschuss))
    db.flush()
    db.refresh(m, attribute_names=["stocks"])
    for s in m.stocks:
        _ = s.location
    return m


def _open_purchase(db: Session, material_id: int) -> list[WorkTodo]:
    return list(
        db.scalars(
            select(WorkTodo).where(
                WorkTodo.material_id == material_id,
                WorkTodo.kind == "purchase",
                WorkTodo.status == "open",
            )
        ).all()
    )


def test_ausschuss_excluded_from_available_and_critical():
    db = _session()
    m = _material(db, min_stock=Decimal("5"), hamburg=Decimal("0"), ausschuss=Decimal("20"))
    assert material_stock_available(m) == Decimal("0")
    assert is_material_critical(m) is True
    db.close()


def test_complete_when_min_stock_met_and_recreate_when_below():
    db = _session()
    m = _material(db, min_stock=Decimal("10"), hamburg=Decimal("3"))
    first = sync_purchase_todos(db, material_ids={m.id})
    assert first["created"] == 1
    open_todos = db.scalars(
        select(WorkTodo).where(WorkTodo.material_id == m.id, WorkTodo.status == "open")
    ).all()
    assert len(open_todos) == 1
    todo_id = open_todos[0].id

    # Bestand auf Mindestbestand heben → erledigen
    stock = db.scalars(
        select(MaterialStock).where(
            MaterialStock.material_id == m.id,
            MaterialStock.location_id == _loc(db, "Hamburg").id,
        )
    ).one()
    stock.quantity = Decimal("10")
    db.flush()
    db.expire(m)
    m = db.get(Material, m.id)
    _ = [s.location for s in m.stocks]

    done = sync_purchase_todos(db, material_ids={m.id})
    assert done["completed_stale"] == 1
    assert done["created"] == 0
    old = db.get(WorkTodo, todo_id)
    assert old is not None
    assert old.status == "done"
    assert old.completed_at is not None

    # Wieder unter Mindestbestand → neues offenes Todo
    stock.quantity = Decimal("2")
    db.flush()
    db.expire(m)
    m = db.get(Material, m.id)
    _ = [s.location for s in m.stocks]

    again = sync_purchase_todos(db, material_ids={m.id})
    assert again["created"] == 1
    opens = db.scalars(
        select(WorkTodo).where(WorkTodo.material_id == m.id, WorkTodo.status == "open")
    ).all()
    assert len(opens) == 1
    assert opens[0].id != todo_id
    dones = db.scalars(
        select(WorkTodo).where(WorkTodo.material_id == m.id, WorkTodo.status == "done")
    ).all()
    assert len(dones) == 1
    db.close()


def test_max_one_open_and_generate_button():
    db = _session()
    m = _material(db, min_stock=Decimal("5"), hamburg=Decimal("1"))
    sync_purchase_todos(db, material_ids={m.id})
    second = sync_purchase_todos(db, material_ids={m.id})
    assert second["created"] == 0
    assert second["skipped_existing"] == 1
    bulk = generate_purchase_todos(db)
    assert bulk["skipped_existing"] >= 1
    opens = db.scalars(
        select(WorkTodo).where(WorkTodo.material_id == m.id, WorkTodo.status == "open")
    ).all()
    assert len(opens) == 1
    db.close()


def test_ignored_skipped_on_auto_create():
    db = _session()
    m = _material(db, min_stock=Decimal("5"), hamburg=Decimal("0"))
    m.overview_ignored = True
    db.flush()
    result = sync_purchase_todos(db, material_ids={m.id})
    assert result["created"] == 0
    assert result["skipped_ignored"] == 1
    with_ignored = sync_purchase_todos(db, material_ids={m.id}, include_ignored=True)
    assert with_ignored["created"] == 1
    db.close()


def test_location_negative_needs_purchase_even_if_total_ok():
    db = _session()
    m = _material(
        db,
        min_stock=None,
        hamburg=Decimal("-3"),
        dahlenburg=Decimal("20"),
        name="LocNeg",
    )
    assert material_stock_available(m) == Decimal("17")
    assert is_material_critical(m) is False
    assert material_has_negative_location(m) is True
    assert material_needs_purchase_todo(m) is True
    result = sync_purchase_todos(db, material_ids={m.id})
    assert result["created"] == 1
    assert len(_open_purchase(db, m.id)) == 1
    db.close()


def test_manufacture_negative_material_opens_purchase_todo():
    db = _session()
    m = _material(db, min_stock=None, hamburg=Decimal("2"), name="FertigMat")
    product = Product(name="FertigProd", selling_price=Decimal("10"))
    db.add(product)
    db.flush()
    db.add(ProductMaterial(product_id=product.id, material_id=m.id, quantity_required=Decimal("5")))
    db.commit()

    result = manufacture(db, product.id, Decimal("1"), _loc(db, "Hamburg").id)
    assert any("negativ" in w.lower() for w in result.warnings)
    opens = _open_purchase(db, m.id)
    assert len(opens) == 1
    assert opens[0].source == "auto"
    assert opens[0].title == "Einkauf: FertigMat"
    db.close()


def test_manufacture_location_negative_with_other_stock_opens_todo_once():
    db = _session()
    m = _material(
        db,
        min_stock=None,
        hamburg=Decimal("2"),
        dahlenburg=Decimal("20"),
        name="SplitMat",
    )
    product = Product(name="SplitProd", selling_price=Decimal("10"))
    db.add(product)
    db.flush()
    db.add(ProductMaterial(product_id=product.id, material_id=m.id, quantity_required=Decimal("5")))
    db.commit()

    manufacture(db, product.id, Decimal("1"), _loc(db, "Hamburg").id)
    opens = _open_purchase(db, m.id)
    assert len(opens) == 1
    todo_id = opens[0].id

    # Zweites Fertigen: kein Duplikat
    manufacture(db, product.id, Decimal("1"), _loc(db, "Hamburg").id)
    opens2 = _open_purchase(db, m.id)
    assert len(opens2) == 1
    assert opens2[0].id == todo_id
    db.close()


def test_manufacture_stock_recovery_completes_purchase_todo():
    db = _session()
    m = _material(db, min_stock=None, hamburg=Decimal("1"), name="RecoverMat")
    product = Product(name="RecoverProd", selling_price=Decimal("10"))
    db.add(product)
    db.flush()
    db.add(ProductMaterial(product_id=product.id, material_id=m.id, quantity_required=Decimal("3")))
    db.commit()

    manufacture(db, product.id, Decimal("1"), _loc(db, "Hamburg").id)
    opens = _open_purchase(db, m.id)
    assert len(opens) == 1
    todo_id = opens[0].id

    stock = db.scalars(
        select(MaterialStock).where(
            MaterialStock.material_id == m.id,
            MaterialStock.location_id == _loc(db, "Hamburg").id,
        )
    ).one()
    stock.quantity = Decimal("5")
    db.flush()
    done = sync_purchase_todos(db, material_ids={m.id})
    assert done["completed_stale"] == 1
    assert done["created"] == 0
    old = db.get(WorkTodo, todo_id)
    assert old is not None
    assert old.status == "done"
    assert old.completed_at is not None
    assert _open_purchase(db, m.id) == []
    db.close()


def test_assemble_negative_material_opens_purchase_todo():
    db = _session()
    m = _material(db, min_stock=None, hamburg=Decimal("1"), name="AssembleMat")
    ps = ProductSet(name="Set Neg", handle="set-neg")
    db.add(ps)
    db.flush()
    variant = SetVariant(
        set_id=ps.id,
        option1_name="Farbe",
        option1_value="Natur",
    )
    db.add(variant)
    db.flush()
    db.add(SetBomLine(variant_id=variant.id, material_id=m.id, quantity_required=Decimal("4")))
    db.commit()

    result = assemble_variant(db, variant.id, Decimal("1"), _loc(db, "Hamburg").id)
    assert any("negativ" in w.lower() for w in result.warnings)
    opens = _open_purchase(db, m.id)
    assert len(opens) == 1
    assert opens[0].title == "Einkauf: AssembleMat"
    db.close()
