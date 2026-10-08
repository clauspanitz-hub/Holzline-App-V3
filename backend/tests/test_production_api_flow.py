"""HTTP-Smoke (Dependency-Overrides): Create → Board wie Frontend-Pfad."""

from __future__ import annotations

from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password, mitarbeiter_allowed, require_user
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
