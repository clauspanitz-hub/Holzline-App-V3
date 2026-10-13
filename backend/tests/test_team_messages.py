"""Team-Pinnwand + Scratchpad (ADR 0031)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password, mitarbeiter_allowed, require_user
from app.database import Base, get_db, seed_locations
from app.models import TeamMessage, TeamNote, User, UserRole
from app.routers import router
from app.team import TEAM_NOTE_ID, get_note, list_messages, upsert_note
from app.schemas import TeamNoteUpdate


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


def _admin(db: Session) -> User:
    user = User(
        username="admin",
        password_hash=hash_password("secret12"),
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _mitarbeiter(db: Session) -> User:
    user = User(
        username="simona",
        password_hash=hash_password("secret12"),
        role=UserRole.MITARBEITER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_message_crud_and_note_singleton():
    db = _session()
    user = _admin(db)
    client = _client(db, user)

    empty = client.get("/api/team/messages")
    assert empty.status_code == 200
    assert empty.json() == []

    created = client.post(
        "/api/team/messages",
        json={"text": "Holz für Ringe nachbestellt", "author": "claus"},
    )
    assert created.status_code == 201, created.text
    msg = created.json()
    assert msg["author"] == "claus"
    assert msg["text"] == "Holz für Ringe nachbestellt"
    assert msg["created_at"]
    assert msg["updated_at"] is None

    listed = client.get("/api/team/messages")
    assert len(listed.json()) == 1

    patched = client.patch(
        f"/api/team/messages/{msg['id']}",
        json={"text": "Holz für Ringe ist da"},
    )
    assert patched.status_code == 200
    assert patched.json()["text"] == "Holz für Ringe ist da"
    assert patched.json()["updated_at"] is not None
    assert patched.json()["author"] == "claus"

    note = client.get("/api/team/note")
    assert note.status_code == 200
    assert note.json()["id"] == TEAM_NOTE_ID
    assert note.json()["body"] == ""

    saved = client.put("/api/team/note", json={"body": "Morgen Simona: Fräsen"})
    assert saved.status_code == 200
    assert saved.json()["body"] == "Morgen Simona: Fräsen"

    again = client.get("/api/team/note")
    assert again.json()["body"] == "Morgen Simona: Fräsen"

    deleted = client.delete(f"/api/team/messages/{msg['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/team/messages").json() == []


def test_invalid_author_rejected():
    db = _session()
    client = _client(db, _admin(db))
    bad = client.post("/api/team/messages", json={"text": "x", "author": "other"})
    assert bad.status_code == 422


def test_mitarbeiter_allowlist_covers_team_api():
    assert mitarbeiter_allowed("GET", "/api/team/messages")
    assert mitarbeiter_allowed("POST", "/api/team/messages")
    assert mitarbeiter_allowed("PATCH", "/api/team/messages/3")
    assert mitarbeiter_allowed("DELETE", "/api/team/messages/3")
    assert mitarbeiter_allowed("GET", "/api/team/note")
    assert mitarbeiter_allowed("PUT", "/api/team/note")


def test_mitarbeiter_can_post_and_edit():
    db = _session()
    client = _client(db, _mitarbeiter(db))
    created = client.post(
        "/api/team/messages",
        json={"text": "Fertig mit MA1", "author": "simona"},
    )
    assert created.status_code == 201
    mid = created.json()["id"]
    patched = client.patch(f"/api/team/messages/{mid}", json={"text": "Fertig mit MA2"})
    assert patched.status_code == 200
    assert patched.json()["author"] == "simona"


def test_service_note_upsert_and_order():
    db = _session()
    note = get_note(db)
    assert note.id == TEAM_NOTE_ID
    upsert_note(db, TeamNoteUpdate(body="Pad"))
    assert get_note(db).body == "Pad"

    from app.schemas import TeamMessageCreate
    from app.team import create_message

    a = create_message(db, TeamMessageCreate(text="erste", author="claus"))
    b = create_message(db, TeamMessageCreate(text="zweite", author="simona"))
    ids = [m.id for m in list_messages(db)]
    assert ids == [a.id, b.id]
    assert db.scalar(select(TeamMessage).where(TeamMessage.id == a.id)) is not None
    assert db.get(TeamNote, TEAM_NOTE_ID) is not None
