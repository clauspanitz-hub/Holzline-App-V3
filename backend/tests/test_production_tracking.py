"""Tests für Produktions-Tracking Slice 1+2 (ADR 0030)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, seed_locations
from app.models import LaborRate, Product, ProductFamily, Unit, User, UserRole
from app.auth import hash_password
from app import production


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


def _user(db: Session, rate: LaborRate | None = None) -> User:
    u = User(
        username="claus",
        password_hash=hash_password("secret12"),
        role=UserRole.ADMIN,
        labor_rate_id=rate.id if rate else None,
    )
    db.add(u)
    db.flush()
    return u


def _product(db: Session, name: str = "Ring", *, family_id: int | None = None) -> Product:
    p = Product(name=name, sku=None, selling_price=Decimal("20"), family_id=family_id)
    db.add(p)
    db.flush()
    return p


def test_parallel_tracks_and_product_cost_with_quantities():
    db = _session()
    rate = production.create_labor_rate(db, "Werkstatt", Decimal("60"))
    user = _user(db, rate)
    machine = production.create_machine(db, "Fräse", power_w=Decimal("1000"))
    production.set_energy_tariff(db, Decimal("0.40"))
    product = _product(db)

    process = production.create_process(db, user, title="Ringe", product_id=product.id, quantity=Decimal("9"))
    production.add_step(db, process.id, "Fräsen", quantity=Decimal("9"))
    production.add_step(db, process.id, "Schleifen", quantity=Decimal("1"))
    process = production.get_process(db, process.id)
    fraesen = process.steps[0]
    schleifen = process.steps[1]

    start = datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc)
    production.start_track(db, user, fraesen.id, "labor", started_at=start)
    production.start_track(db, user, fraesen.id, "machine", machine_id=machine.id, started_at=start)
    production.start_track(db, user, schleifen.id, "labor", started_at=start)

    process = production.get_process(db, process.id)
    assert sum(1 for s in process.steps for t in s.tracks if t.ended_at is None) == 3

    # Fräsen labor+machine 90 min; Schleifen labor 5 min
    production.stop_track(
        db, process.steps[0].tracks[0].id, ended_at=start + timedelta(minutes=90)
    )
    production.stop_track(
        db, process.steps[0].tracks[1].id, ended_at=start + timedelta(minutes=90)
    )
    production.stop_track(
        db, process.steps[1].tracks[0].id, ended_at=start + timedelta(minutes=5)
    )

    process = production.complete_process(db, process.id)
    assert process.status == "done"

    costs = production.compute_process_unit_costs(db, process)
    # labor: 90min/9 + 5min/1 = 10 + 5 = 15 min = 900 sec
    assert costs["labor_seconds_per_unit"] == Decimal("900.000")
    # machine: 90min/9 = 10 min = 600 sec
    assert costs["machine_seconds_per_unit"] == Decimal("600.000")
    # labor €: (1.5h/9)*60 + (5/60 h /1)*60 = 10 + 5 = 15
    assert costs["labor_eur_per_unit"] == Decimal("15.0000")
    # energy: 1.5h * 1kW / 9 * 0.40€ = 1.5/9*0.4 = 0.0667
    assert costs["energy_kwh_per_unit"] == Decimal("0.166667")
    assert costs["energy_eur_per_unit"] == Decimal("0.0667")

    current = production.current_product_cost(db, product.id)
    assert current["sample_count"] == 1
    assert current["total_eur_per_unit"] == costs["total_eur_per_unit"]

    history = production.list_product_cost_history(db, product.id)
    assert len(history) == 1
    assert history[0].labor_eur_per_unit == Decimal("15.0000")


def test_user_default_labor_rate_on_start():
    db = _session()
    rate = production.create_labor_rate(db, "MA", Decimal("40"))
    user = _user(db, rate)
    process = production.create_process(db, user, title="Frei")
    production.add_step(db, process.id, "Lackieren")
    process = production.get_process(db, process.id)
    process = production.start_track(db, user, process.steps[0].id, "labor")
    track = process.steps[0].tracks[0]
    assert track.labor_rate_id == rate.id


def test_slice2_multi_link_same_cost_and_estimates():
    db = _session()
    rate = production.create_labor_rate(db, "Werkstatt", Decimal("60"))
    user = _user(db, rate)
    family = ProductFamily(name="Ringe")
    db.add(family)
    db.flush()
    p1 = _product(db, "Ring Buche", family_id=family.id)
    p2 = _product(db, "Ring Eiche", family_id=family.id)
    p3 = _product(db, "Einzel")

    run = production.create_process(
        db,
        user,
        title="Geburtstagsring aus Buche",
        product_ids=[p3.id],
        family_ids=[family.id],
        quantity=Decimal("3"),
    )
    assert {p.id for p in run.product_links} == {p3.id}
    assert {f.id for f in run.family_links} == {family.id}

    # Prozess mit Schätzung (keine Messung)
    production.add_step(
        db,
        run.id,
        "Fräsen",
        quantity=Decimal("3"),
        estimated_labor_seconds=Decimal("1800"),  # 30 Min
    )
    run = production.get_process(db, run.id)
    step = run.steps[0]
    assert step.estimated_labor_seconds == Decimal("1800")
    assert production.effective_step_seconds(step, "labor") == Decimal("1800")

    costs = production.compute_process_unit_costs(db, run)
    # 1800s / 3 = 600s/unit; labor €: (0.5h/3)*60 = 10
    assert costs["labor_seconds_per_unit"] == Decimal("600")
    assert costs["labor_eur_per_unit"] == Decimal("10.0000")

    run = production.complete_process(db, run.id)
    linked = production.linked_product_ids(db, run)
    assert linked == {p1.id, p2.id, p3.id}

    # Gleicher Snapshot-Satz für alle Verknüpfungen (Q19 A)
    for pid in (p1.id, p2.id, p3.id):
        hist = production.list_product_cost_history(db, pid)
        assert len(hist) == 1
        assert hist[0].labor_eur_per_unit == Decimal("10.0000")
        assert hist[0].total_eur_per_unit == Decimal("10.0000")

    fam_cost = production.current_family_cost(db, family.id)
    assert fam_cost["sample_product_count"] == 2
    assert fam_cost["prices_differ"] is False
    assert fam_cost["avg_total_eur_per_unit"] == Decimal("10.0000")


def test_slice2_measurement_prefers_over_estimate():
    db = _session()
    rate = production.create_labor_rate(db, "Werkstatt", Decimal("60"))
    user = _user(db, rate)
    product = _product(db)

    run = production.create_process(db, user, title="Messung", product_ids=[product.id], quantity=Decimal("1"))
    production.add_step(
        db,
        run.id,
        "Schleifen",
        estimated_labor_seconds=Decimal("3600"),
    )
    run = production.get_process(db, run.id)
    step = run.steps[0]
    start = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    production.start_track(db, user, step.id, "labor", started_at=start)
    run = production.get_process(db, run.id)
    production.stop_track(db, run.steps[0].tracks[0].id, ended_at=start + timedelta(minutes=10))
    run = production.get_process(db, run.id)
    assert production.measured_step_seconds(run.steps[0], "labor") == Decimal("600")
    assert production.effective_step_seconds(run.steps[0], "labor") == Decimal("600")
    costs = production.compute_process_unit_costs(db, run)
    assert costs["labor_seconds_per_unit"] == Decimal("600")
    assert costs["labor_eur_per_unit"] == Decimal("10.0000")  # 10min = 1/6 h * 60


def test_slice2_create_run_then_nested_processes_like_ui():
    """UX-Flow: Lauf anlegen → darunter Prozesse mit Schätzung (Create-Form / Board)."""
    db = _session()
    user = _user(db)
    family = ProductFamily(name="Ringe UI")
    db.add(family)
    db.flush()
    p1 = _product(db, "Ring UI", family_id=family.id)

    run = production.create_process(
        db,
        user,
        title="Geburtstagsring Nesting",
        product_ids=[p1.id],
        family_ids=[family.id],
        quantity=Decimal("4"),
    )
    assert run.title == "Geburtstagsring Nesting"
    assert run.steps == [] or len(run.steps) == 0

    for name, est in (("Fräsen", 1200), ("Schleifen", 600), ("Ölen", 300)):
        production.add_step(
            db,
            run.id,
            name,
            quantity=Decimal("4"),
            estimated_labor_seconds=Decimal(str(est)),
            estimated_machine_seconds=Decimal("180") if name == "Fräsen" else None,
        )

    run = production.get_process(db, run.id)
    assert len(run.steps) == 3
    assert [s.name for s in run.steps] == ["Fräsen", "Schleifen", "Ölen"]
    fraesen = run.steps[0]
    assert fraesen.estimated_labor_seconds == Decimal("1200")
    assert fraesen.estimated_machine_seconds == Decimal("180")
    assert production.effective_step_seconds(fraesen, "labor") == Decimal("1200")
    assert production.effective_step_seconds(fraesen, "machine") == Decimal("180")
    board = production.list_board(db, status="active")
    assert any(r.id == run.id and len(r.steps) == 3 for r in board)


def test_board_active_includes_fresh_create_immediately():
    """Create-Response und Board status=active müssen denselben Lauf liefern (kein Filter-Mismatch)."""
    db = _session()
    user = _user(db)
    created = production.create_process(db, user, title="Sofort sichtbar")
    assert created.status == "active"
    board = production.list_board(db, status="active")
    assert any(r.id == created.id for r in board)
    done_board = production.list_board(db, status="done")
    assert not any(r.id == created.id for r in done_board)
    with_step = production.add_step(db, created.id, "Fräsen", estimated_labor_seconds=Decimal("60"))
    assert with_step.status == "active"
    board2 = production.list_board(db, status="active")
    hit = next(r for r in board2 if r.id == created.id)
    assert len(hit.steps) == 1
    assert hit.steps[0].name == "Fräsen"


def test_slice2_max_processes_and_family_average():
    db = _session()
    rate = production.create_labor_rate(db, "Werkstatt", Decimal("30"))
    user = _user(db, rate)
    family = ProductFamily(name="Ziffern")
    db.add(family)
    db.flush()
    a = _product(db, "Ziffer A", family_id=family.id)
    b = _product(db, "Ziffer B", family_id=family.id)

    run = production.create_process(db, user, title="Batch", family_ids=[family.id], quantity=Decimal("1"))
    for i in range(10):
        production.add_step(db, run.id, f"Schritt {i + 1}", estimated_labor_seconds=Decimal("60"))
    try:
        production.add_step(db, run.id, "Zu viel")
        assert False, "expected max processes error"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400

    production.complete_process(db, run.id)
    # same cost both products
    assert production.current_product_cost(db, a.id)["total_eur_per_unit"] == production.current_product_cost(
        db, b.id
    )["total_eur_per_unit"]

    # Force different current costs by completing a second run only for product A
    run2 = production.create_process(db, user, title="Nur A", product_ids=[a.id], quantity=Decimal("1"))
    production.add_step(db, run2.id, "Extra", estimated_labor_seconds=Decimal("3600"))
    production.complete_process(db, run2.id)

    fam = production.current_family_cost(db, family.id)
    assert fam["prices_differ"] is True
    # Ø of two different totals
    ca = production.current_product_cost(db, a.id)["total_eur_per_unit"]
    cb = production.current_product_cost(db, b.id)["total_eur_per_unit"]
    assert ca != cb
    expected = ((ca + cb) / 2).quantize(Decimal("0.0001"))
    assert fam["avg_total_eur_per_unit"] == expected
