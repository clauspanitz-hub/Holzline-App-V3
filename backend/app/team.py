"""Team-Pinnwand + gemeinsames Scratchpad (ADR 0031)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TeamMessage, TeamNote
from app.schemas import TeamMessageCreate, TeamMessageRead, TeamMessageUpdate, TeamNoteRead, TeamNoteUpdate

TEAM_NOTE_ID = 1
ALLOWED_AUTHORS = frozenset({"claus", "simona"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _message_read(row: TeamMessage) -> TeamMessageRead:
    return TeamMessageRead.model_validate(row)


def list_messages(db: Session) -> list[TeamMessageRead]:
    rows = db.scalars(select(TeamMessage).order_by(TeamMessage.created_at.asc(), TeamMessage.id.asc())).all()
    return [_message_read(r) for r in rows]


def create_message(db: Session, payload: TeamMessageCreate) -> TeamMessageRead:
    author = payload.author.strip().lower()
    if author not in ALLOWED_AUTHORS:
        raise HTTPException(status_code=400, detail="Absender muss claus oder simona sein")
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text darf nicht leer sein")
    row = TeamMessage(text=text, author=author)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _message_read(row)


def update_message(db: Session, message_id: int, payload: TeamMessageUpdate) -> TeamMessageRead:
    row = db.get(TeamMessage, message_id)
    if not row:
        raise HTTPException(status_code=404, detail="Nachricht nicht gefunden")
    data = payload.model_dump(exclude_unset=True)
    if "text" in data:
        text = (data["text"] or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Text darf nicht leer sein")
        row.text = text
    if "author" in data and data["author"] is not None:
        author = str(data["author"]).strip().lower()
        if author not in ALLOWED_AUTHORS:
            raise HTTPException(status_code=400, detail="Absender muss claus oder simona sein")
        row.author = author
    row.updated_at = _utcnow()
    db.commit()
    db.refresh(row)
    return _message_read(row)


def delete_message(db: Session, message_id: int) -> None:
    row = db.get(TeamMessage, message_id)
    if not row:
        raise HTTPException(status_code=404, detail="Nachricht nicht gefunden")
    db.delete(row)
    db.commit()


def get_or_create_note(db: Session) -> TeamNote:
    row = db.get(TeamNote, TEAM_NOTE_ID)
    if row:
        return row
    row = TeamNote(id=TEAM_NOTE_ID, body="", updated_at=_utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_note(db: Session) -> TeamNoteRead:
    row = get_or_create_note(db)
    return TeamNoteRead.model_validate(row)


def upsert_note(db: Session, payload: TeamNoteUpdate) -> TeamNoteRead:
    row = get_or_create_note(db)
    row.body = payload.body if payload.body is not None else ""
    row.updated_at = _utcnow()
    db.commit()
    db.refresh(row)
    return TeamNoteRead.model_validate(row)
