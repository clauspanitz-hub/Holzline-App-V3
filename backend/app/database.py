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
        migrate_material_is_template(engine)
        migrate_audit_timestamps(engine)
        migrate_transform_target(engine)
        migrate_product_family(engine)
        migrate_material_family(engine)
        migrate_overview_ignored(engine)
        migrate_product_selling_price(engine)
        migrate_product_bom_components(engine)
        migrate_shopify_ignored_handles(engine)
        migrate_product_is_on_demand(engine)
        migrate_shopify_import_queue(engine)
        migrate_orders_todos(engine)
        migrate_order_origin(engine)
        migrate_shop_line_maps(engine)
        migrate_tageslage_cache(engine)
        migrate_incoming_mails(engine)
        migrate_order_note(engine)
        migrate_color_hex(engine, db)
        migrate_material_decimal_places(engine)
        migrate_purchase_todos(engine)
        migrate_order_line_set_variant(engine)
        seed_admin_user(db)
        from app.services import backfill_incomplete_tags, ensure_system_incomplete_tags

        newly = ensure_system_incomplete_tags(db)
        if newly:
            backfill_incomplete_tags(db, newly)
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


def migrate_material_is_template(engine) -> None:
    """Add materials.is_template flag for Serienanlage-Vorlagen."""
    insp = inspect(engine)
    with engine.begin() as conn:
        if "materials" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("materials")}
        if "is_template" not in cols:
            conn.execute(text("ALTER TABLE materials ADD COLUMN is_template BOOLEAN NOT NULL DEFAULT 0"))


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


def migrate_product_selling_price(engine) -> None:
    """Verkaufspreis am Produkt (Euro, Default 0 = unvollständig)."""
    insp = inspect(engine)
    with engine.begin() as conn:
        if "products" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("products")}
        if "selling_price" not in cols:
            conn.execute(
                text("ALTER TABLE products ADD COLUMN selling_price NUMERIC(14, 2) NOT NULL DEFAULT 0")
            )


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


def migrate_shopify_ignored_handles(engine) -> None:
    """Table for Shopify handles hidden in the CSV assistant."""
    insp = inspect(engine)
    if "shopify_ignored_handles" in insp.get_table_names():
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE shopify_ignored_handles (
                    handle VARCHAR(200) PRIMARY KEY,
                    title VARCHAR(300),
                    ignored_at DATETIME NOT NULL
                )
                """
            )
        )


def migrate_product_is_on_demand(engine) -> None:
    """Flag for products created from On-Demand Shopify import queue entries."""
    insp = inspect(engine)
    if "products" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("products")}
    if "is_on_demand" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE products ADD COLUMN is_on_demand BOOLEAN NOT NULL DEFAULT 0"))


def migrate_shopify_import_queue(engine) -> None:
    """Persistent Import-Warteschlange for Serie/On-Demand handles."""
    insp = inspect(engine)
    if "shopify_import_queue" in insp.get_table_names():
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE shopify_import_queue (
                    handle VARCHAR(200) PRIMARY KEY,
                    title VARCHAR(300) NOT NULL,
                    kind VARCHAR(20) NOT NULL,
                    on_demand BOOLEAN NOT NULL DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'open',
                    option_axes JSON NOT NULL,
                    option_values JSON NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    completed_at DATETIME
                )
                """
            )
        )


def migrate_orders_todos(engine) -> None:
    """Bestellungen, Positionen und Todos (Phase 2 erster Schnitt)."""
    insp = inspect(engine)
    names = set(insp.get_table_names())
    with engine.begin() as conn:
        if "orders" not in names:
            conn.execute(
                text(
                    """
                    CREATE TABLE orders (
                        id INTEGER NOT NULL PRIMARY KEY,
                        ordered_on DATETIME NOT NULL,
                        customer_name VARCHAR(200),
                        external_number VARCHAR(80),
                        origin VARCHAR(20) NOT NULL DEFAULT 'manual',
                        status VARCHAR(20) NOT NULL DEFAULT 'open',
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
        if "order_lines" not in names:
            conn.execute(
                text(
                    """
                    CREATE TABLE order_lines (
                        id INTEGER NOT NULL PRIMARY KEY,
                        order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                        quantity NUMERIC(14, 3) NOT NULL,
                        label VARCHAR(300) NOT NULL,
                        product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
                        material_id INTEGER REFERENCES materials(id) ON DELETE SET NULL
                    )
                    """
                )
            )
        if "todos" not in names:
            conn.execute(
                text(
                    """
                    CREATE TABLE todos (
                        id INTEGER NOT NULL PRIMARY KEY,
                        order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                        order_line_id INTEGER REFERENCES order_lines(id) ON DELETE CASCADE,
                        kind VARCHAR(30) NOT NULL,
                        category VARCHAR(20) NOT NULL DEFAULT 'workshop',
                        status VARCHAR(20) NOT NULL DEFAULT 'open',
                        title VARCHAR(300) NOT NULL,
                        quantity NUMERIC(14, 3) NOT NULL DEFAULT 1,
                        product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
                        material_id INTEGER REFERENCES materials(id) ON DELETE SET NULL,
                        created_at DATETIME NOT NULL,
                        completed_at DATETIME
                    )
                    """
                )
            )


def migrate_order_origin(engine) -> None:
    """Herkunft am Auftrag (manual / shopify / etsy)."""
    insp = inspect(engine)
    if "orders" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("orders")}
    with engine.begin() as conn:
        if "origin" not in cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN origin VARCHAR(20) NOT NULL DEFAULT 'manual'"))
        conn.execute(
            text(
                """
                UPDATE orders SET origin = 'manual'
                WHERE origin IS NULL OR origin = ''
                """
            )
        )


def migrate_shop_line_maps(engine) -> None:
    """Shop-Zuordnung und Shop-Felder an Bestellpositionen."""
    insp = inspect(engine)
    names = set(insp.get_table_names())
    with engine.begin() as conn:
        if "order_lines" in names:
            cols = {c["name"] for c in insp.get_columns("order_lines")}
            if "shop_sku" not in cols:
                conn.execute(text("ALTER TABLE order_lines ADD COLUMN shop_sku VARCHAR(100)"))
            if "shop_title" not in cols:
                conn.execute(text("ALTER TABLE order_lines ADD COLUMN shop_title VARCHAR(300)"))
            if "suggested_product_id" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE order_lines ADD COLUMN suggested_product_id INTEGER "
                        "REFERENCES products(id) ON DELETE SET NULL"
                    )
                )
            conn.execute(
                text(
                    """
                    UPDATE order_lines
                    SET shop_title = label
                    WHERE shop_title IS NULL OR shop_title = ''
                    """
                )
            )
        if "shop_line_maps" not in names:
            conn.execute(
                text(
                    """
                    CREATE TABLE shop_line_maps (
                        id INTEGER NOT NULL PRIMARY KEY,
                        origin VARCHAR(20) NOT NULL,
                        title_key VARCHAR(300) NOT NULL,
                        sku_key VARCHAR(100),
                        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                        UNIQUE (origin, title_key)
                    )
                    """
                )
            )



def migrate_tageslage_cache(engine) -> None:
    """Tages-Cache für Übersicht-Tageslage (Gemini-Text)."""
    insp = inspect(engine)
    if "tageslage_cache" in set(insp.get_table_names()):
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE tageslage_cache (
                    id INTEGER NOT NULL PRIMARY KEY,
                    cache_date VARCHAR(10) NOT NULL UNIQUE,
                    summary TEXT NOT NULL DEFAULT '',
                    quote TEXT NOT NULL DEFAULT '',
                    next_steps_json TEXT NOT NULL DEFAULT '[]',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )


def migrate_incoming_mails(engine) -> None:
    """IMAP-Warteschlange für Etsy-Mails (ADR 0018)."""
    insp = inspect(engine)
    if "incoming_mails" in set(insp.get_table_names()):
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE incoming_mails (
                    id INTEGER NOT NULL PRIMARY KEY,
                    origin VARCHAR(20) NOT NULL DEFAULT 'etsy',
                    message_id VARCHAR(300) NOT NULL UNIQUE,
                    subject VARCHAR(500),
                    from_addr VARCHAR(300),
                    body_text TEXT NOT NULL DEFAULT '',
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    error_message VARCHAR(500),
                    received_at DATETIME,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )


def migrate_order_note(engine) -> None:
    """Bestellnotiz / Personalisierung (Shopify note, Etsy-Mail)."""
    insp = inspect(engine)
    if "orders" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("orders")}
    if "note" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE orders ADD COLUMN note TEXT"))


def migrate_color_hex(engine, db: Session) -> None:
    """Hex am Farbkatalog; leere Werte aus dem Namen zuweisen."""
    from app.color_hex import hex_for_color_name
    from app.models import Color

    insp = inspect(engine)
    if "colors" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("colors")}
    if "hex" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE colors ADD COLUMN hex VARCHAR(7)"))
        db.expire_all()
    for color in db.scalars(select(Color)).all():
        if color.hex:
            continue
        guessed = hex_for_color_name(color.name)
        if guessed:
            color.hex = guessed
    db.commit()


def migrate_order_line_set_variant(engine) -> None:
    """Set-Variante an Bestellposition (ADR 0020)."""
    insp = inspect(engine)
    if "order_lines" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("order_lines")}
    if "set_variant_id" in cols:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE order_lines ADD COLUMN set_variant_id INTEGER "
                "REFERENCES set_variants(id) ON DELETE SET NULL"
            )
        )


def migrate_purchase_todos(engine) -> None:
    """Bestellmenge/zuletzt bestellt am Material; Todos ohne Bestellung (ADR 0019)."""
    insp = inspect(engine)
    if "materials" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("materials")}
        with engine.begin() as conn:
            if "reorder_quantity" not in cols:
                conn.execute(text("ALTER TABLE materials ADD COLUMN reorder_quantity NUMERIC(14, 3)"))
            if "last_purchase_quantity" not in cols:
                conn.execute(text("ALTER TABLE materials ADD COLUMN last_purchase_quantity NUMERIC(14, 3)"))

    if "todos" not in insp.get_table_names():
        return
    todo_cols = {c["name"]: c for c in insp.get_columns("todos")}
    order_col = todo_cols.get("order_id")
    if order_col is None or order_col.get("nullable"):
        return

    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.commit()
        with conn.begin():
            conn.execute(
                text(
                    """
                    CREATE TABLE todos_new (
                        id INTEGER NOT NULL PRIMARY KEY,
                        order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                        order_line_id INTEGER REFERENCES order_lines(id) ON DELETE CASCADE,
                        kind VARCHAR(30) NOT NULL,
                        category VARCHAR(20) NOT NULL DEFAULT 'workshop',
                        status VARCHAR(20) NOT NULL DEFAULT 'open',
                        title VARCHAR(300) NOT NULL,
                        quantity NUMERIC(14, 3) NOT NULL DEFAULT 1,
                        product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
                        material_id INTEGER REFERENCES materials(id) ON DELETE SET NULL,
                        created_at DATETIME NOT NULL,
                        completed_at DATETIME
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO todos_new (
                        id, order_id, order_line_id, kind, category, status, title,
                        quantity, product_id, material_id, created_at, completed_at
                    )
                    SELECT
                        id, order_id, order_line_id, kind, category, status, title,
                        quantity, product_id, material_id, created_at, completed_at
                    FROM todos
                    """
                )
            )
            conn.execute(text("DROP TABLE todos"))
            conn.execute(text("ALTER TABLE todos_new RENAME TO todos"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()


def migrate_material_decimal_places(engine) -> None:
    """Nachkommastellen am Material (0–3), Default 0."""
    insp = inspect(engine)
    if "materials" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("materials")}
    if "decimal_places" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE materials ADD COLUMN decimal_places INTEGER NOT NULL DEFAULT 0"))


def migrate_product_bom_components(engine) -> None:
    """Allow product_materials lines to reference a component product (XOR with material)."""
    insp = inspect(engine)
    if "product_materials" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("product_materials")}
    if "component_product_id" in cols:
        return

    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.commit()
        with conn.begin():
            conn.execute(
                text(
                    """
                    CREATE TABLE product_materials_new (
                        id INTEGER NOT NULL PRIMARY KEY,
                        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                        material_id INTEGER REFERENCES materials(id) ON DELETE RESTRICT,
                        component_product_id INTEGER REFERENCES products(id) ON DELETE RESTRICT,
                        quantity_required NUMERIC(14, 3) NOT NULL,
                        CHECK (
                            (material_id IS NOT NULL AND component_product_id IS NULL)
                            OR (material_id IS NULL AND component_product_id IS NOT NULL)
                        )
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO product_materials_new (id, product_id, material_id, component_product_id, quantity_required)
                    SELECT id, product_id, material_id, NULL, quantity_required FROM product_materials
                    """
                )
            )
            conn.execute(text("DROP TABLE product_materials"))
            conn.execute(text("ALTER TABLE product_materials_new RENAME TO product_materials"))
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_product_bom_material "
                    "ON product_materials(product_id, material_id) WHERE material_id IS NOT NULL"
                )
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_product_bom_component "
                    "ON product_materials(product_id, component_product_id) WHERE component_product_id IS NOT NULL"
                )
            )
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()


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
