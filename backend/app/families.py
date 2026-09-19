"""Familien-Kataloge (Material/Produkt) mit einer Unterebene — ADR 0025."""

from __future__ import annotations

from typing import Literal, TypeVar

from fastapi import HTTPException
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session, selectinload

from app.models import Material, MaterialFamily, Product, ProductFamily

FamilyKind = Literal["material", "product"]
FamilyModel = TypeVar("FamilyModel", MaterialFamily, ProductFamily)


def _model(kind: FamilyKind):
    return MaterialFamily if kind == "material" else ProductFamily


def _article_model(kind: FamilyKind):
    return Material if kind == "material" else Product


def _article_label(kind: FamilyKind) -> str:
    return "Materialien" if kind == "material" else "Produkte"


def family_read(row: MaterialFamily | ProductFamily) -> dict:
    parent = row.parent
    return {
        "id": row.id,
        "name": row.name,
        "parent_id": row.parent_id,
        "parent_name": parent.name if parent else None,
        "is_parent": row.parent_id is None,
        "child_count": len(row.children) if row.children is not None else 0,
    }


def list_families(db: Session, kind: FamilyKind) -> list[dict]:
    Model = _model(kind)
    rows = db.scalars(
        select(Model)
        .options(selectinload(Model.parent), selectinload(Model.children))
        .order_by(Model.parent_id.is_not(None), Model.name)
    ).all()
    parents = [r for r in rows if r.parent_id is None]
    children = [r for r in rows if r.parent_id is not None]
    parents.sort(key=lambda r: r.name.casefold())
    children.sort(key=lambda r: (r.parent.name.casefold() if r.parent else "", r.name.casefold()))
    ordered = parents + children
    return [family_read(r) for r in ordered]


def get_family(db: Session, kind: FamilyKind, family_id: int):
    Model = _model(kind)
    row = db.scalars(
        select(Model)
        .where(Model.id == family_id)
        .options(selectinload(Model.parent), selectinload(Model.children))
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Familie nicht gefunden")
    return row


def _assert_unique_name(
    db: Session,
    kind: FamilyKind,
    name: str,
    parent_id: int | None,
    *,
    exclude_id: int | None = None,
) -> None:
    Model = _model(kind)
    stmt = select(Model).where(Model.name == name)
    if parent_id is None:
        stmt = stmt.where(Model.parent_id.is_(None))
    else:
        stmt = stmt.where(Model.parent_id == parent_id)
    if exclude_id is not None:
        stmt = stmt.where(Model.id != exclude_id)
    if db.scalars(stmt.limit(1)).first():
        scope = "Elternfamilien" if parent_id is None else "Unterfamilien derselben Elternfamilie"
        raise HTTPException(status_code=409, detail=f"Name „{name}“ existiert bereits unter den {scope}")


def create_family(db: Session, kind: FamilyKind, *, name: str, parent_id: int | None = None) -> dict:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name darf nicht leer sein")
    if parent_id is not None:
        parent = get_family(db, kind, parent_id)
        if parent.parent_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Unterfamilien dürfen keine weiteren Unterfamilien haben",
            )
    _assert_unique_name(db, kind, name, parent_id)
    Model = _model(kind)
    row = Model(name=name, parent_id=parent_id)
    db.add(row)
    db.commit()
    return family_read(get_family(db, kind, row.id))


def update_family(db: Session, kind: FamilyKind, family_id: int, *, name: str) -> dict:
    row = get_family(db, kind, family_id)
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name darf nicht leer sein")
    _assert_unique_name(db, kind, name, row.parent_id, exclude_id=row.id)
    row.name = name
    # Denormalisierte Anzeige am Artikel synchron halten
    Article = _article_model(kind)
    for article in db.scalars(select(Article).where(Article.family_id == row.id)).all():
        article.family = name
    db.commit()
    return family_read(get_family(db, kind, family_id))


def delete_family(db: Session, kind: FamilyKind, family_id: int) -> None:
    row = get_family(db, kind, family_id)
    if row.parent_id is None and row.children:
        raise HTTPException(
            status_code=409,
            detail=f"Familie „{row.name}“ hat noch {len(row.children)} Unterfamilie(n)",
        )
    Article = _article_model(kind)
    count = db.scalars(
        select(Article.id).where(Article.family_id == family_id).limit(1)
    ).first()
    if count is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Familie „{row.name}“ ist noch mit {_article_label(kind)} verknüpft",
        )
    db.delete(row)
    db.commit()


def find_or_create_parent(db: Session, kind: FamilyKind, name: str):
    """Find-or-create Elternfamilie; keine Commit — Caller committed."""
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Familienname darf nicht leer sein")
    Model = _model(kind)
    existing = db.scalars(
        select(Model).where(Model.parent_id.is_(None), Model.name == name).limit(1)
    ).first()
    if existing:
        return existing
    row = Model(name=name, parent_id=None)
    db.add(row)
    db.flush()
    return row


def resolve_family_id(
    db: Session,
    kind: FamilyKind,
    family_id: int | None,
    *,
    allow_none: bool = True,
):
    if family_id is None:
        if allow_none:
            return None
        raise HTTPException(status_code=400, detail="family_id fehlt")
    return get_family(db, kind, family_id)


def assign_article_family(article, family_row) -> None:
    """Setzt family_id und denormalisiertes family-Label (Blattname)."""
    if family_row is None:
        article.family_id = None
        article.family = None
        return
    article.family_id = family_row.id
    article.family = family_row.name


def family_fields_for_read(article) -> dict:
    ref = getattr(article, "family_ref", None)
    if ref is None:
        # Fallback: nur Freitext (vor Migration / Backup)
        name = getattr(article, "family", None)
        return {
            "family_id": getattr(article, "family_id", None),
            "family": name,
            "family_parent_id": None,
            "family_parent_name": None,
        }
    parent = ref.parent
    return {
        "family_id": ref.id,
        "family": ref.name,
        "family_parent_id": parent.id if parent else None,
        "family_parent_name": parent.name if parent else None,
    }


def migrate_family_catalogs(engine, db: Session) -> None:
    """Tabellen anlegen, family_id-Spalten, Freitext → Elternfamilien."""
    insp = inspect(engine)
    with engine.begin() as conn:
        if "material_families" not in insp.get_table_names():
            conn.execute(
                text(
                    """
                    CREATE TABLE material_families (
                        id INTEGER NOT NULL PRIMARY KEY,
                        name VARCHAR(200) NOT NULL,
                        parent_id INTEGER REFERENCES material_families(id) ON DELETE RESTRICT
                    )
                    """
                )
            )
        if "product_families" not in insp.get_table_names():
            conn.execute(
                text(
                    """
                    CREATE TABLE product_families (
                        id INTEGER NOT NULL PRIMARY KEY,
                        name VARCHAR(200) NOT NULL,
                        parent_id INTEGER REFERENCES product_families(id) ON DELETE RESTRICT
                    )
                    """
                )
            )
        for table, col in (("materials", "family_id"), ("products", "family_id")):
            if table not in insp.get_table_names():
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if col not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} INTEGER"))

    _backfill_free_text(db, "material")
    _backfill_free_text(db, "product")


def _backfill_free_text(db: Session, kind: FamilyKind) -> None:
    Article = _article_model(kind)
    Model = _model(kind)
    rows = db.scalars(
        select(Article).where(
            Article.family.is_not(None),
            Article.family_id.is_(None),
        )
    ).all()
    if not rows:
        return
    cache: dict[str, MaterialFamily | ProductFamily] = {}
    for article in rows:
        raw = (article.family or "").strip()
        if not raw:
            article.family = None
            continue
        parent = cache.get(raw)
        if parent is None:
            parent = db.scalars(
                select(Model).where(Model.parent_id.is_(None), Model.name == raw).limit(1)
            ).first()
            if parent is None:
                parent = Model(name=raw, parent_id=None)
                db.add(parent)
                db.flush()
            cache[raw] = parent
        article.family_id = parent.id
        article.family = parent.name
    db.commit()
