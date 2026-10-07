"""Mitarbeiter-Allowlist muss die echten HTTP-Methoden der Einkauf-Buchung treffen."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import SESSION_COOKIE, hash_token, mitarbeiter_allowed
from app.database import Base, get_db, seed_locations
from app.middleware_auth import AuthMiddleware
from app.models import AuthSession, Location, Material, MaterialStock, Unit, User, UserRole
from app.routers import router


def test_purchase_flow_methods_are_allowed():
    """Einkauf-Todo: PATCH Preis/zuletzt-bestellt, dann POST Bestandsdelta."""
    assert mitarbeiter_allowed("PATCH", "/api/materials/12") is True
    assert mitarbeiter_allowed("PUT", "/api/materials/12") is False
    assert mitarbeiter_allowed("POST", "/api/materials/12/stock/delta") is True
    assert mitarbeiter_allowed("POST", "/api/todos/3/complete") is True
    assert mitarbeiter_allowed("DELETE", "/api/materials/12") is False


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
    return db, SessionLocal


def test_mitarbeiter_can_book_purchase_via_patch_and_delta(monkeypatch):
    db, SessionLocal = _session()
    monkeypatch.setattr("app.middleware_auth.SessionLocal", SessionLocal)

    loc = db.scalars(select(Location).where(Location.name == "Hamburg")).one()
    material = Material(
        name="Leimholz",
        unit=Unit.STK,
        purchase_quantity=Decimal("1"),
        purchase_price=Decimal("10.00"),
        cost_per_unit=Decimal("10.0000"),
    )
    db.add(material)
    db.flush()
    db.add(MaterialStock(material_id=material.id, location_id=loc.id, quantity=Decimal("2")))
    staff = User(username="werkstatt", password_hash="x", role=UserRole.MITARBEITER)
    db.add(staff)
    db.flush()
    now = datetime.now(timezone.utc)
    token = "staff-session-token"
    db.add(
        AuthSession(
            user_id=staff.id,
            token_hash=hash_token(token),
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(hours=12),
        )
    )
    db.commit()

    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(router)

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, token)

    denied = client.put(
        f"/api/materials/{material.id}",
        json={"purchase_price": "24.00", "last_purchase_quantity": "8"},
    )
    assert denied.status_code == 403

    patched = client.patch(
        f"/api/materials/{material.id}",
        json={"purchase_price": "24.00", "last_purchase_quantity": "8"},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["purchase_price"] == "24.00"
    assert body["last_purchase_quantity"] == "8.000"

    delta = client.post(
        f"/api/materials/{material.id}/stock/delta",
        json={"location_id": loc.id, "delta": "8"},
    )
    assert delta.status_code == 200, delta.text
    hamburg = next(s for s in delta.json()["stocks"] if s["location_name"] == "Hamburg")
    assert hamburg["quantity"] == "10.000"

    db.close()
