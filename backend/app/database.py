from collections.abc import Generator
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)


@event.listens_for(engine, "connect")
def _sqlite_foreign_keys(dbapi_connection, connection_record) -> None:  # noqa: ARG001
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DEFAULT_LOCATIONS = (
    ("Hamburg", False),
    ("Dahlenburg", False),
    ("In Bearbeitung", True),
    ("MA1", True),
    ("MA2", True),
    ("Ausschuss", True),
)

LOCATION_DISPLAY_ORDER = (
    "Hamburg",
    "Dahlenburg",
    "In Bearbeitung",
    "MA1",
    "MA2",
    "Ausschuss",
)

AUSSCHUSS_LOCATION_NAME = "Ausschuss"


def seed_locations(db: Session) -> None:
    from app.models import Location

    existing = {row.name for row in db.scalars(select(Location)).all()}
    for name, is_virtual in DEFAULT_LOCATIONS:
        if name not in existing:
            db.add(Location(name=name, is_virtual=is_virtual))
    db.commit()


def migrate_legacy_columns(engine) -> None:
    """Remove Phase-1 stock_quantity columns that break Phase-1.5 inserts."""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in ("materials", "products"):
            if table not in insp.get_table_names():
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if "stock_quantity" in cols:
                conn.execute(text(f"ALTER TABLE {table} DROP COLUMN stock_quantity"))


def migrate_purchase_fields(engine) -> None:
    """Add purchase_quantity / purchase_price; backfill from cost_per_unit."""
    insp = inspect(engine)
    if "materials" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("materials")}
    with engine.begin() as conn:
        if "purchase_quantity" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE materials ADD COLUMN purchase_quantity NUMERIC(14, 3) NOT NULL DEFAULT 1"
                )
            )
        if "purchase_price" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE materials ADD COLUMN purchase_price NUMERIC(14, 2) NOT NULL DEFAULT 0"
                )
            )
            conn.execute(text("UPDATE materials SET purchase_price = cost_per_unit"))
        conn.execute(
            text(
                """
                UPDATE materials
                SET cost_per_unit = CASE
                    WHEN purchase_quantity IS NULL OR purchase_quantity = 0 THEN cost_per_unit
                    ELSE ROUND(purchase_price * 1.0 / purchase_quantity, 4)
                END
                """
            )
        )


def migrate_legacy_stock(db: Session) -> None:
    """Copy Phase-1 stock_quantity columns into Hamburg stocks if stocks are empty."""
    from app.models import Location, Material, MaterialStock, Product, ProductStock

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    hamburg = db.scalars(select(Location).where(Location.name == "Hamburg")).first()
    if not hamburg:
        return

    # Only migrate if legacy column still exists (before drop)
    if "materials" in tables:
        cols = {c["name"] for c in insp.get_columns("materials")}
        if "stock_quantity" in cols:
            stock_count = db.scalars(select(MaterialStock.id).limit(1)).first()
            if stock_count is None:
                for material in db.scalars(select(Material)).all():
                    raw = db.execute(
                        text("SELECT stock_quantity FROM materials WHERE id = :id"),
                        {"id": material.id},
                    ).scalar()
                    qty = Decimal(str(raw or 0))
                    db.add(MaterialStock(material_id=material.id, location_id=hamburg.id, quantity=qty))

    if "products" in tables:
        cols = {c["name"] for c in insp.get_columns("products")}
        if "stock_quantity" in cols:
            stock_count = db.scalars(select(ProductStock.id).limit(1)).first()
            if stock_count is None:
                for product in db.scalars(select(Product)).all():
                    raw = db.execute(
                        text("SELECT stock_quantity FROM products WHERE id = :id"),
                        {"id": product.id},
                    ).scalar()
                    qty = Decimal(str(raw or 0))
                    db.add(ProductStock(product_id=product.id, location_id=hamburg.id, quantity=qty))

    db.commit()


def init_db() -> None:
    from app import models  # noqa: F401

    if settings.database_url.startswith("sqlite:///"):
        raw = settings.database_url.removeprefix("sqlite:///")
        db_path = Path(raw)
        if db_path.parent and str(db_path.parent) not in (".", ""):
            db_path.parent.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_locations(db)
        migrate_legacy_stock(db)
        migrate_legacy_columns(engine)
        migrate_purchase_fields(engine)
        migrate_tags_colors(engine)
        migrate_color_media_catalog(engine, db)
        migrate_min_stock(engine)
        migrate_product_is_template(engine)
        migrate_audit_timestamps(engine)
        migrate_transform_target(engine)
        migrate_product_family(engine)
        migrate_material_family(engine)
        migrate_overview_ignored(engine)
        seed_admin_user(db)
    finally:
        db.close()


def seed_admin_user(db: Session) -> None:
    """Create first admin from ADMIN_USER / ADMIN_PASSWORD if no users exist."""
    from app.auth import hash_password
    from app.config import settings
    from app.models import User, UserRole

    if db.scalars(select(User).limit(1)).first():
        return
    if not settings.admin_user or not settings.admin_password:
        return
    db.add(
        User(
            username=settings.admin_user.strip(),
            password_hash=hash_password(settings.admin_password),
            role=UserRole.ADMIN,
            is_active=True,
        )
    )
    db.commit()


def migrate_audit_timestamps(engine) -> None:
    """Add created_at/updated_at/created_by/updated_by on materials and products."""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in ("materials", "products"):
            if table not in insp.get_table_names():
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if "created_at" not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN created_at DATETIME"))
            if "updated_at" not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN updated_at DATETIME"))
            if "created_by" not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN created_by VARCHAR(100)"))
            if "updated_by" not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN updated_by VARCHAR(100)"))
            conn.execute(
                text(
                    f"""
                    UPDATE {table}
                    SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
                        updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
                    """
                )
            )


def migrate_min_stock(engine) -> None:
    """Add optional min_stock to materials and products."""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in ("materials", "products"):
            if table not in insp.get_table_names():
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if "min_stock" not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN min_stock NUMERIC(14, 3)"))


def migrate_product_is_template(engine) -> None:
    """Add products.is_template flag for Serienanlage-Vorlagen."""
    insp = inspect(engine)
    with engine.begin() as conn:
        if "products" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("products")}
        if "is_template" not in cols:
            conn.execute(text("ALTER TABLE products ADD COLUMN is_template BOOLEAN NOT NULL DEFAULT 0"))


def migrate_transform_target(engine) -> None:
    """Add products.transform_target_id for Quell→Ziel-Umwandlung."""
    insp = inspect(engine)
    with engine.begin() as conn:
        if "products" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("products")}
        if "transform_target_id" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE products ADD COLUMN transform_target_id "
                    "INTEGER REFERENCES products(id) ON DELETE SET NULL"
                )
            )


def migrate_product_family(engine) -> None:
    """Add products.family for Produktfamilie grouping."""
    insp = inspect(engine)
    with engine.begin() as conn:
        if "products" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("products")}
        if "family" not in cols:
            conn.execute(text("ALTER TABLE products ADD COLUMN family VARCHAR(200)"))


def migrate_material_family(engine) -> None:
    """Add materials.family for Materialfamilie grouping."""
    insp = inspect(engine)
    with engine.begin() as conn:
        if "materials" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("materials")}
        if "family" not in cols:
            conn.execute(text("ALTER TABLE materials ADD COLUMN family VARCHAR(200)"))


def migrate_overview_ignored(engine) -> None:
    """Flag to hide critical items from Übersicht until manually restored."""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in ("materials", "products"):
            if table not in insp.get_table_names():
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if "overview_ignored" not in cols:
                conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN overview_ignored BOOLEAN NOT NULL DEFAULT 0")
                )


def migrate_tags_colors(engine) -> None:
    """Ensure color_id columns exist (tables created via create_all)."""
    insp = inspect(engine)
    with engine.begin() as conn:
        if "materials" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("materials")}
            if "color_id" not in cols:
                conn.execute(text("ALTER TABLE materials ADD COLUMN color_id INTEGER REFERENCES colors(id)"))
        if "products" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("products")}
            if "color_id" not in cols:
                conn.execute(text("ALTER TABLE products ADD COLUMN color_id INTEGER REFERENCES colors(id)"))


DEFAULT_COLOR_MEDIA = ("Lack", "PLA")


def seed_color_media(db: Session) -> None:
    from app.models import ColorMedium

    existing = {row.name.casefold(): row for row in db.scalars(select(ColorMedium)).all()}
    for name in DEFAULT_COLOR_MEDIA:
        if name.casefold() not in existing:
            db.add(ColorMedium(name=name))
    db.commit()


def migrate_color_media_catalog(engine, db: Session) -> None:
    """Migrate colors.medium Enum → color_media + colors.medium_id; seed Lack/PLA."""
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    if "color_media" not in tables:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE color_media (
                        id INTEGER NOT NULL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL UNIQUE
                    )
                    """
                )
            )
        insp = inspect(engine)
        tables = set(insp.get_table_names())

    seed_color_media(db)

    if "colors" not in tables:
        return

    cols = {c["name"] for c in insp.get_columns("colors")}

    # Fresh schema already uses medium_id only
    if "medium_id" in cols and "medium" not in cols:
        return

    with engine.connect() as conn:
        # SQLite: foreign_keys must be toggled outside an open transaction
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.commit()
        with conn.begin():
            if "medium_id" not in cols:
                conn.execute(text("ALTER TABLE colors ADD COLUMN medium_id INTEGER"))

            if "medium" in cols:
                media_rows = conn.execute(text("SELECT id, name FROM color_media")).fetchall()
                by_name = {name.casefold(): mid for mid, name in media_rows}
                legacy = conn.execute(text("SELECT id, medium FROM colors WHERE medium_id IS NULL")).fetchall()
                for color_id, medium_name in legacy:
                    key = str(medium_name or "").strip()
                    if not key:
                        continue
                    mid = by_name.get(key.casefold())
                    if mid is None:
                        conn.execute(text("INSERT INTO color_media (name) VALUES (:n)"), {"n": key})
                        mid = conn.execute(
                            text("SELECT id FROM color_media WHERE name = :n"), {"n": key}
                        ).scalar()
                        by_name[key.casefold()] = mid
                    conn.execute(
                        text("UPDATE colors SET medium_id = :mid WHERE id = :cid"),
                        {"mid": mid, "cid": color_id},
                    )

            conn.execute(text("DELETE FROM colors WHERE medium_id IS NULL"))

            # Rebuild to drop legacy `medium` + old unique(name, medium)
            conn.execute(
                text(
                    """
                    CREATE TABLE colors__new (
                        id INTEGER NOT NULL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        medium_id INTEGER NOT NULL,
                        CONSTRAINT uq_color_name_medium UNIQUE (name, medium_id),
                        FOREIGN KEY(medium_id) REFERENCES color_media (id) ON DELETE CASCADE
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO colors__new (id, name, medium_id)
                    SELECT id, name, medium_id FROM colors
                    """
                )
            )
            conn.execute(text("DROP TABLE colors"))
            conn.execute(text("ALTER TABLE colors__new RENAME TO colors"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()

    seed_color_media(db)
