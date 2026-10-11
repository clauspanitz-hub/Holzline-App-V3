"""Abgeschlossene Läufe / Historie (Q23–Q30)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import production
from app.auth import hash_password, require_user
from app.database import Base, get_db, seed_locations
from app.models import User, UserRole
from app.routers import router


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


def _user(db: Session) -> User:
    u = User(
        username="claus",
        password_hash=hash_password("secret12"),
        role=UserRole.ADMIN,
    )
    db.add(u)
    db.flush()
    return u


def _client(db: Session, user: User) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[require_user] = lambda: user
    return TestClient(app)


def test_create_run_gets_template_and_done_groups_under_template():
    db = _session()
    user = _user(db)
    run = production.create_process(db, user, title="Geburtstagsring")
    production.add_step(db, run.id, "Fräsen")
    assert run.template_id is not None
    tmpl_id = run.template_id

    start = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
    step = production.get_process(db, run.id).steps[0]
    production.start_track(db, user, step.id, "labor", started_at=start)
    production.stop_track(
        db, production.get_process(db, run.id).steps[0].tracks[0].id,
        ended_at=start + timedelta(minutes=30),
    )
    done = production.complete_process(db, run.id, history_note="erster Lauf")
    assert done.status == "done"
    assert done.history_note == "erster Lauf"
    assert done.template_id == tmpl_id

    groups = production.list_templates_with_done_runs(db)
    assert len(groups) == 1
    assert groups[0]["id"] == tmpl_id
    assert groups[0]["name"] == "Geburtstagsring"
    assert len(groups[0]["runs"]) == 1
    assert groups[0]["runs"][0].history_note == "erster Lauf"


def test_retime_creates_new_active_under_same_template():
    db = _session()
    user = _user(db)
    run = production.create_process(db, user, title="Ringe Buche", quantity=Decimal("3"))
    production.add_step(
        db, run.id, "Fräsen", quantity=Decimal("3"), estimated_labor_seconds=Decimal("600")
    )
    production.add_step(db, run.id, "Schleifen")
    done = production.complete_process(db, run.id)
    tmpl_id = done.template_id

    fresh = production.retime_process(db, user, done.id, history_note="mit neuem Fräser")
    assert fresh.status == "active"
    assert fresh.template_id == tmpl_id
    assert fresh.id != done.id
    assert fresh.history_note == "mit neuem Fräser"
    assert fresh.title == "Ringe Buche"
    assert len(fresh.steps) == 2
    assert fresh.steps[0].name == "Fräsen"
    assert fresh.steps[0].estimated_labor_seconds == Decimal("600")
    assert fresh.steps[0].tracks == []
    # Quelle unverändert Historie
    source = production.get_process(db, done.id)
    assert source.status == "done"
    assert source.template_id == tmpl_id


def test_archive_meta_ok_structure_and_times_rejected():
    db = _session()
    user = _user(db)
    run = production.create_process(db, user, title="Alt")
    production.add_step(db, run.id, "Fräsen")
    done = production.complete_process(db, run.id, history_note=None)
    step_id = done.steps[0].id

    updated = production.update_process(
        db, done.id, title="Korrigiert", history_note="Tippfehler"
    )
    assert updated.title == "Korrigiert"
    assert updated.history_note == "Tippfehler"

    try:
        production.update_process(db, done.id, quantity=Decimal("9"))
        assert False, "expected 400"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400

    try:
        production.add_step(db, done.id, "Neu")
        assert False, "expected 400"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400

    try:
        production.update_step(db, step_id, name="Geändert")
        assert False, "expected 400"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400


def test_api_templates_and_retime_and_board_done():
    db = _session()
    user = _user(db)
    db.commit()
    client = _client(db, user)

    created = client.post(
        "/api/production/processes",
        json={"title": "API Historie", "quantity": 1},
    )
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]
    tmpl_id = created.json()["template_id"]
    assert tmpl_id is not None

    step = client.post(
        f"/api/production/processes/{run_id}/steps",
        json={"name": "Fräsen", "estimated_labor_seconds": 120},
    )
    assert step.status_code == 201

    done = client.post(
        f"/api/production/processes/{run_id}/complete",
        json={"history_note": "ok"},
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "done"
    assert done.json()["history_note"] == "ok"

    board_done = client.get("/api/production/board", params={"status": "done"})
    assert board_done.status_code == 200
    assert any(r["id"] == run_id for r in board_done.json())

    templates = client.get("/api/production/templates")
    assert templates.status_code == 200
    data = templates.json()
    assert len(data) >= 1
    group = next(t for t in data if t["id"] == tmpl_id)
    assert group["name"] == "API Historie"
    assert len(group["runs"]) == 1
    assert group["runs"][0]["total_measured_seconds"] is not None

    # Archiv: Step-PATCH → 400
    bad = client.patch(
        f"/api/production/steps/{group['runs'][0]['steps'][0]['id']}",
        json={"name": "Nope"},
    )
    assert bad.status_code == 400

    # Meta-PATCH ok
    meta = client.patch(
        f"/api/production/processes/{run_id}",
        json={"history_note": "korrigiert"},
    )
    assert meta.status_code == 200
    assert meta.json()["history_note"] == "korrigiert"

    retime = client.post(
        f"/api/production/processes/{run_id}/retime",
        json={"history_note": "zweiter Versuch"},
    )
    assert retime.status_code == 201, retime.text
    fresh = retime.json()
    assert fresh["status"] == "active"
    assert fresh["template_id"] == tmpl_id
    assert fresh["id"] != run_id
    assert len(fresh["steps"]) == 1

    active = client.get("/api/production/board", params={"status": "active"})
    assert any(r["id"] == fresh["id"] for r in active.json())
