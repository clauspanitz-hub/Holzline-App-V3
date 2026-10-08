"""Tests für Produktions-Tracking (ADR 0030)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, seed_locations
from app.models import LaborRate, Product, Unit, User, UserRole
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


def _product(db: Session, name: str = "Ring") -> Product:
    p = Product(name=name, sku=None, selling_price=Decimal("20"))
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
