"""HTTP-Smoke (Dependency-Overrides): Create → Board wie Frontend-Pfad."""

from __future__ import annotations

from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from datetime import datetime, timedelta, timezone

from app.auth import hash_password, mitarbeiter_allowed, require_user
from app.database import Base, get_db, seed_locations
from app.models import Product, ProductFamily, User, UserRole
from app.routers import router
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


def _client(db: Session, user: User) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[require_user] = lambda: user
    return TestClient(app)


def test_create_run_appears_on_active_board_immediately():
    db = _session()
    user = User(
        username="claus",
        password_hash=hash_password("secret12"),
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = _client(db, user)

    empty = client.get("/api/production/board", params={"status": "active"})
    assert empty.status_code == 200
    assert empty.json() == []

    created = client.post(
        "/api/production/processes",
        json={
            "title": "Geburtstagsring API-Flow",
            "product_ids": None,
            "family_ids": None,
            "quantity": 2,
        },
    )
    assert created.status_code == 201, created.text
    run = created.json()
    assert run["status"] == "active"
    assert run["title"] == "Geburtstagsring API-Flow"

    board = client.get("/api/production/board", params={"status": "active"})
    assert board.status_code == 200
    assert any(r["id"] == run["id"] for r in board.json())

    stepped = client.post(
        f"/api/production/processes/{run['id']}/steps",
        json={
            "name": "Fräsen",
            "quantity": 2,
            "estimated_labor_seconds": 600,
            "estimated_machine_seconds": 120,
        },
    )
    assert stepped.status_code == 201, stepped.text
    assert len(stepped.json()["steps"]) == 1

    board2 = client.get("/api/production/board", params={"status": "active"})
    hit = next(r for r in board2.json() if r["id"] == run["id"])
    assert len(hit["steps"]) == 1
    assert hit["steps"][0]["name"] == "Fräsen"
    assert Decimal(str(hit["steps"][0]["estimated_labor_seconds"])) == Decimal("600")
    db.close()


def test_mitarbeiter_allowlist_includes_family_costs():
    assert mitarbeiter_allowed("GET", "/api/production/family-costs/3")
    assert mitarbeiter_allowed("GET", "/api/production/board")
    assert mitarbeiter_allowed("POST", "/api/production/processes")


def test_reload_board_keeps_nested_steps_and_stopped_tracks():
    """ui-v1.18: Stop → Messung (Subsekunden) darf Board/Reload nicht mit 500 killen."""
    import time

    db = _session()
    user = User(
        username="claus",
        password_hash=hash_password("secret12"),
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = _client(db, user)

    created = client.post(
        "/api/production/processes",
        json={"title": "Reload Persist", "quantity": 1},
    )
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]

    stepped = client.post(
        f"/api/production/processes/{run_id}/steps",
        json={
            "name": "Fräsen",
            "quantity": 1,
            "estimated_labor_seconds": 600,
            "estimated_machine_seconds": 120,
        },
    )
    assert stepped.status_code == 201, stepped.text
    step_id = stepped.json()["steps"][0]["id"]

    machine = client.post("/api/machines", json={"name": "CNC", "power_w": 800})
    assert machine.status_code == 201, machine.text
    mid = machine.json()["id"]

    labor = client.post(f"/api/production/steps/{step_id}/tracks", json={"kind": "labor"})
    assert labor.status_code == 201, labor.text
    mach = client.post(
        f"/api/production/steps/{step_id}/tracks",
        json={"kind": "machine", "machine_id": mid},
    )
    assert mach.status_code == 201, mach.text

    # Double-start labor must fail cleanly (no orphan second open track)
    dup = client.post(f"/api/production/steps/{step_id}/tracks", json={"kind": "labor"})
    assert dup.status_code == 400, dup.text

    time.sleep(0.05)
    tracks = mach.json()["steps"][0]["tracks"]
    labor_track = next(t for t in tracks if t["kind"] == "labor")
    stopped = client.post(f"/api/production/tracks/{labor_track['id']}/stop", json={})
    assert stopped.status_code == 200, stopped.text
    stopped_step = next(s for s in stopped.json()["steps"] if s["id"] == step_id)
    assert Decimal(str(stopped_step["measured_labor_seconds"])) > 0
    assert stopped_step["estimated_labor_seconds"] is not None

    # Simulate full remount: fresh board must still nest steps + tracks
    board = client.get("/api/production/board", params={"status": "active"})
    assert board.status_code == 200, board.text
    hit = next(r for r in board.json() if r["id"] == run_id)
    assert len(hit["steps"]) == 1
    assert hit["steps"][0]["name"] == "Fräsen"
    assert len(hit["steps"][0]["tracks"]) == 2
    labor_after = next(t for t in hit["steps"][0]["tracks"] if t["kind"] == "labor")
    assert labor_after["running"] is False
    assert labor_after["ended_at"] is not None
    assert Decimal(str(hit["steps"][0]["measured_labor_seconds"])) > 0
    # Schema Quantity: max 3 decimal places (was the Board-500 root cause)
    measured = Decimal(str(hit["steps"][0]["measured_labor_seconds"]))
    assert measured == measured.quantize(Decimal("0.001"))
    db.close()


def test_product_cost_endpoints_accept_energy_and_unit_cost_precision():
    """Nach Lauf mit Maschinenenergie dürfen Produkt-/Familienkosten nicht mit 500 sterben.

    compute_process_unit_costs liefert kWh mit 6 und € mit 4 Nachkommastellen
    (Numeric am Snapshot). Response-Models mit Money/Quantity (2/3) haben die
    Endpunkte nach 'Kosten laden' gekillt.
    """
    db = _session()
    rate = production.create_labor_rate(db, "Werkstatt", Decimal("60"))
    user = User(
        username="claus",
        password_hash=hash_password("secret12"),
        role=UserRole.ADMIN,
        labor_rate_id=rate.id,
    )
    db.add(user)
    db.flush()
    machine = production.create_machine(db, "Fräse", power_w=Decimal("1000"))
    production.set_energy_tariff(db, Decimal("0.40"))
    family = ProductFamily(name="Ringe")
    db.add(family)
    db.flush()
    product = Product(name="Ring", selling_price=Decimal("20"), family_id=family.id)
    db.add(product)
    db.commit()
    db.refresh(user)
    db.refresh(product)
    db.refresh(family)

    process = production.create_process(
        db, user, title="Ringe", product_id=product.id, family_ids=[family.id], quantity=Decimal("9")
    )
    production.add_step(db, process.id, "Fräsen", quantity=Decimal("9"))
    process = production.get_process(db, process.id)
    step = process.steps[0]
    start = datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc)
    production.start_track(db, user, step.id, "labor", started_at=start)
    production.start_track(db, user, step.id, "machine", machine_id=machine.id, started_at=start)
    process = production.get_process(db, process.id)
    production.stop_track(db, process.steps[0].tracks[0].id, ended_at=start + timedelta(minutes=90))
    production.stop_track(db, process.steps[0].tracks[1].id, ended_at=start + timedelta(minutes=90))
    production.complete_process(db, process.id)

    client = _client(db, user)
    current = client.get(f"/api/production/product-costs/{product.id}")
    assert current.status_code == 200, current.text
    body = current.json()
    assert Decimal(str(body["energy_kwh_per_unit"])) == Decimal("0.166667")
    assert Decimal(str(body["energy_eur_per_unit"])) == Decimal("0.0667")
    assert Decimal(str(body["total_eur_per_unit"])) == Decimal("10.0667")

    history = client.get(f"/api/production/product-costs/{product.id}/history")
    assert history.status_code == 200, history.text
    assert len(history.json()) == 1
    assert Decimal(str(history.json()[0]["energy_kwh_per_unit"])) == Decimal("0.166667")

    family_cost = client.get(f"/api/production/family-costs/{family.id}")
    assert family_cost.status_code == 200, family_cost.text
    assert Decimal(str(family_cost.json()["avg_total_eur_per_unit"])) == Decimal("10.0667")
    db.close()
