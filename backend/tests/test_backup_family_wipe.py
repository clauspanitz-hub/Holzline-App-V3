"""Replace-Import muss Unterfamilien löschen, ohne an parent_id RESTRICT zu scheitern."""

from __future__ import annotations

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.backup import export_backup, import_backup
from app.database import Base, seed_locations
from app.families import create_family
from app.models import MaterialFamily, ProductFamily


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
    return sessionmaker(bind=engine)()


def test_replace_import_roundtrip_with_subfamilies():
    db = _session()
    seed_locations(db)

    rings = create_family(db, "product", name="Ringe")
    create_family(db, "product", name="Vintage", parent_id=rings["id"])
    wood = create_family(db, "material", name="Holz")
    create_family(db, "material", name="Buche", parent_id=wood["id"])

    payload = export_backup(db)
    result = import_backup(db, payload, mode="replace")

    assert result["mode"] == "replace"
    products = list(db.scalars(select(ProductFamily)).all())
    materials = list(db.scalars(select(MaterialFamily)).all())
    product_names = {(row.name, row.parent.name if row.parent else None) for row in products}
    material_names = {(row.name, row.parent.name if row.parent else None) for row in materials}
    assert product_names == {("Ringe", None), ("Vintage", "Ringe")}
    assert material_names == {("Holz", None), ("Buche", "Holz")}
    db.close()
