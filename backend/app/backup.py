"""JSON-Backup: vollständiger Export/Import aller App-Daten über natürliche Schlüssel.

Das Backup enthält keine Datenbank-IDs. Referenzen werden über Namen bzw. Handles
aufgelöst, damit ein Backup auch in eine andere Instanz geladen werden kann.
Mengen und Preise werden als Strings serialisiert, um Decimal-Rundungsfehler zu
vermeiden.
"""

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app import services
from app.models import (
    Color,
    ColorMedium,
    Location,
    Material,
    MaterialFamily,
    MaterialStock,
    OptionMapping,
    Product,
    ProductFamily,
    ProductMaterial,
    ProductSet,
    ProductStock,
    SetBomLine,
    SetVariant,
    StockMovement,
    StockMovementKind,
    Tag,
    Unit,
    material_tags,
    product_tags,
)

FORMAT_ID = "holzlinge-backup"
FORMAT_VERSION = 1
IMPORT_MODES = ("replace", "merge")


# --------------------------------------------------------------------------- #
# Serialisierung
# --------------------------------------------------------------------------- #


def _num(value: Decimal | int | float | None) -> str | None:
    """Decimal als String ohne Exponentialschreibweise."""
    if value is None:
        return None
    return format(Decimal(value), "f")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _color_ref(color: Color | None) -> dict[str, str] | None:
    if color is None:
        return None
    return {"name": color.name, "medium": color.medium.name}


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _key(value: str) -> str:
    return value.strip().casefold()


def _as_list(payload: dict[str, Any], field: str) -> list[dict[str, Any]]:
    raw = payload.get(field) or []
    if not isinstance(raw, list):
        raise _bad_request(f"Feld „{field}“ muss eine Liste sein")
    for entry in raw:
        if not isinstance(entry, dict):
            raise _bad_request(f"Feld „{field}“ enthält einen ungültigen Eintrag")
    return raw


def _str_field(entry: dict[str, Any], field: str, *, context: str) -> str:
    value = entry.get(field)
    if not isinstance(value, str) or not value.strip():
        raise _bad_request(f"{context}: Feld „{field}“ fehlt oder ist leer")
    return value.strip()


def _opt_str(entry: dict[str, Any], field: str) -> str | None:
    value = entry.get(field)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _bool_field(entry: dict[str, Any], field: str, default: bool = False) -> bool:
    value = entry.get(field, default)
    return bool(value)


def _dec_field(
    entry: dict[str, Any],
    field: str,
    *,
    context: str,
    default: Decimal | None = None,
) -> Decimal | None:
    value = entry.get(field)
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise _bad_request(f"{context}: „{field}“ ist keine gültige Zahl ({value!r})") from exc


def _dt_field(entry: dict[str, Any], field: str) -> datetime | None:
    value = entry.get(field)
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #


def export_backup(db: Session, include_movements: bool = False) -> dict[str, Any]:
    """Alle App-Daten als JSON-fähiges Dict (ohne Datenbank-IDs)."""
    payload: dict[str, Any] = {
        "format": FORMAT_ID,
        "version": FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "include_movements": bool(include_movements),
        "locations": [
            {"name": row.name, "is_virtual": row.is_virtual}
            for row in db.scalars(select(Location).order_by(Location.name)).all()
        ],
        "color_media": [
            {"name": row.name}
            for row in db.scalars(select(ColorMedium).order_by(ColorMedium.name)).all()
        ],
        "colors": [
            {"name": row.name, "medium": row.medium.name, "hex": row.hex}
            for row in db.scalars(select(Color).order_by(Color.name)).all()
        ],
        "tags": [
            {"name": row.name} for row in db.scalars(select(Tag).order_by(Tag.name)).all()
        ],
        "material_families": _export_families(
            db.scalars(select(MaterialFamily).order_by(MaterialFamily.name)).all()
        ),
        "product_families": _export_families(
            db.scalars(select(ProductFamily).order_by(ProductFamily.name)).all()
        ),
        "materials": [
            _export_material(row)
            for row in db.scalars(
                select(Material)
                .options(selectinload(Material.family_ref).selectinload(MaterialFamily.parent))
                .order_by(Material.name)
            ).all()
        ],
        "products": [
            _export_product(row)
            for row in db.scalars(
                select(Product)
                .options(selectinload(Product.family_ref).selectinload(ProductFamily.parent))
                .order_by(Product.name)
            ).all()
        ],
        "product_sets": [
            _export_set(row)
            for row in db.scalars(select(ProductSet).order_by(ProductSet.handle)).all()
        ],
    }

    if include_movements:
        payload["movements"] = [
            _export_movement(row)
            for row in db.scalars(select(StockMovement).order_by(StockMovement.id)).all()
        ]

    return payload


def _export_families(rows: list) -> list[dict[str, Any]]:
    by_id = {row.id: row for row in rows}
    parents = [r for r in rows if r.parent_id is None]
    children = [r for r in rows if r.parent_id is not None]
    out: list[dict[str, Any]] = []
    for row in sorted(parents, key=lambda r: r.name.casefold()):
        out.append({"name": row.name, "parent": None})
    for row in sorted(
        children,
        key=lambda r: ((by_id[r.parent_id].name if r.parent_id in by_id else ""), r.name.casefold()),
    ):
        parent = by_id.get(row.parent_id)
        out.append({"name": row.name, "parent": parent.name if parent else None})
    return out


def _family_export_fields(article) -> dict[str, str | None]:
    ref = getattr(article, "family_ref", None)
    if ref is not None:
        parent = ref.parent
        return {
            "family": ref.name,
            "family_parent": parent.name if parent else None,
        }
    return {"family": getattr(article, "family", None), "family_parent": None}


def _export_material(material: Material) -> dict[str, Any]:
    fam = _family_export_fields(material)
    return {
        "name": material.name,
        "unit": material.unit.value,
        "purchase_quantity": _num(material.purchase_quantity),
        "purchase_price": _num(material.purchase_price),
        "cost_per_unit": _num(material.cost_per_unit),
        "min_stock": _num(material.min_stock),
        "is_template": bool(getattr(material, "is_template", False)),
        "decimal_places": int(getattr(material, "decimal_places", 0) or 0),
        "family": fam["family"],
        "family_parent": fam["family_parent"],
        "overview_ignored": bool(getattr(material, "overview_ignored", False)),
        "color": _color_ref(material.color),
        "tags": sorted(tag.name for tag in material.tags),
        "stocks": [
            {"location": stock.location.name, "quantity": _num(stock.quantity)}
            for stock in sorted(material.stocks, key=lambda s: s.location.name)
        ],
        "created_at": _iso(material.created_at),
        "updated_at": _iso(material.updated_at),
        "created_by": material.created_by,
        "updated_by": material.updated_by,
    }


def _export_product(product: Product) -> dict[str, Any]:
    fam = _family_export_fields(product)
    return {
        "name": product.name,
        "sku": product.sku,
        "selling_price": _num(getattr(product, "selling_price", None)),
        "min_stock": _num(product.min_stock),
        "is_template": product.is_template,
        "is_on_demand": bool(getattr(product, "is_on_demand", False)),
        "family": fam["family"],
        "family_parent": fam["family_parent"],
        "overview_ignored": bool(getattr(product, "overview_ignored", False)),
        "color": _color_ref(product.color),
        "transform_target": services.vintage_name_from_uni(product.name),
        "tags": sorted(tag.name for tag in product.tags),
        "stocks": [
            {"location": stock.location.name, "quantity": _num(stock.quantity)}
            for stock in sorted(product.stocks, key=lambda s: s.location.name)
        ],
        "bom": [
            {
                "material_name": line.material.name if line.material else None,
                "product_name": line.component_product.name if line.component_product else None,
                "quantity_required": _num(line.quantity_required),
            }
            for line in sorted(
                product.materials,
                key=lambda line: (
                    line.material.name if line.material else "",
                    line.component_product.name if line.component_product else "",
                ),
            )
        ],
        "created_at": _iso(product.created_at),
        "updated_at": _iso(product.updated_at),
        "created_by": product.created_by,
        "updated_by": product.updated_by,
    }


def _component_ref(material: Material | None, product: Product | None) -> dict[str, Any]:
    return {
        "material_name": material.name if material else None,
        "product_name": product.name if product else None,
    }


def _export_set(product_set: ProductSet) -> dict[str, Any]:
    return {
        "name": product_set.name,
        "handle": product_set.handle,
        "count_materials_in_buildability": product_set.count_materials_in_buildability,
        "variants": [
            {
                "option1_name": variant.option1_name,
                "option1_value": variant.option1_value,
                "option2_name": variant.option2_name,
                "option2_value": variant.option2_value,
                "option3_name": variant.option3_name,
                "option3_value": variant.option3_value,
                "bom": [
                    {
                        **_component_ref(line.material, line.product),
                        "quantity_required": _num(line.quantity_required),
                        "is_manual": line.is_manual,
                    }
                    for line in variant.bom_lines
                ],
            }
            for variant in product_set.variants
        ],
        "option_mappings": [
            {
                "option_name": mapping.option_name,
                "option_value": mapping.option_value,
                **_component_ref(mapping.material, mapping.product),
                "quantity_required": _num(mapping.quantity_required),
            }
            for mapping in product_set.option_mappings
        ],
    }


def _export_movement(movement: StockMovement) -> dict[str, Any]:
    return {
        "kind": movement.kind.value,
        "product_name": movement.product.name if movement.product else None,
        "material_name": movement.material.name if movement.material else None,
        "to_product_name": movement.to_product.name if movement.to_product else None,
        "from_location": movement.from_location.name,
        "to_location": movement.to_location.name,
        "quantity": _num(movement.quantity),
        "note": movement.note,
        "created_at": _iso(movement.created_at),
        "created_by": movement.created_by,
    }


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #


class _Ctx:
    """Namens-Register für die ID-Auflösung zwischen den Import-Pässen."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.created: Counter = Counter()
        self.updated: Counter = Counter()
        self.warnings: list[str] = []
        self.locations: dict[str, Location] = {}
        self.media: dict[str, ColorMedium] = {}
        self.colors: dict[tuple[str, str], Color] = {}
        self.tags: dict[str, Tag] = {}
        self.material_families: dict[tuple[str | None, str], MaterialFamily] = {}
        self.product_families: dict[tuple[str | None, str], ProductFamily] = {}
        self.materials: dict[str, Material] = {}
        self.products: dict[str, Product] = {}
        self.products_by_sku: dict[str, Product] = {}

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def load_existing(self) -> None:
        db = self.db
        self.locations = {_key(r.name): r for r in db.scalars(select(Location)).all()}
        self.media = {_key(r.name): r for r in db.scalars(select(ColorMedium)).all()}
        self.colors = {
            (_key(r.name), _key(r.medium.name)): r for r in db.scalars(select(Color)).all()
        }
        self.tags = {_key(r.name): r for r in db.scalars(select(Tag)).all()}
        self.material_families = {}
        for row in db.scalars(
            select(MaterialFamily).options(selectinload(MaterialFamily.parent))
        ).all():
            parent_key = _key(row.parent.name) if row.parent else None
            self.material_families[(parent_key, _key(row.name))] = row
        self.product_families = {}
        for row in db.scalars(
            select(ProductFamily).options(selectinload(ProductFamily.parent))
        ).all():
            parent_key = _key(row.parent.name) if row.parent else None
            self.product_families[(parent_key, _key(row.name))] = row
        self.materials = {_key(r.name): r for r in db.scalars(select(Material)).all()}
        products = db.scalars(select(Product)).all()
        self.products = {_key(r.name): r for r in products}
        self.products_by_sku = {_key(r.sku): r for r in products if r.sku}

    def resolve_family(self, kind: str, entry: dict[str, Any], *, context: str):
        """family + optional family_parent → Katalogknoten (anlegen falls nötig)."""
        name = _opt_str(entry, "family")
        if not name:
            return None
        parent_name = _opt_str(entry, "family_parent")
        registry = self.material_families if kind == "material" else self.product_families
        Model = MaterialFamily if kind == "material" else ProductFamily
        parent_key = _key(parent_name) if parent_name else None
        if parent_name:
            parent = registry.get((None, parent_key))
            if parent is None:
                parent = Model(name=parent_name, parent_id=None)
                self.db.add(parent)
                self.db.flush()
                registry[(None, parent_key)] = parent
                self.created[f"{kind}_families"] += 1
            child = registry.get((parent_key, _key(name)))
            if child is None:
                child = Model(name=name, parent_id=parent.id)
                self.db.add(child)
                self.db.flush()
                registry[(parent_key, _key(name))] = child
                self.created[f"{kind}_families"] += 1
            return child
        parent = registry.get((None, _key(name)))
        if parent is None:
            parent = Model(name=name, parent_id=None)
            self.db.add(parent)
            self.db.flush()
            registry[(None, _key(name))] = parent
            self.created[f"{kind}_families"] += 1
        return parent

    def resolve_location(self, name: str | None, *, context: str) -> Location | None:
        if not name:
            return None
        location = self.locations.get(_key(name))
        if location is None:
            self.warn(f"{context}: Standort „{name}“ unbekannt — übersprungen")
        return location

    def resolve_color(self, ref: Any, *, context: str) -> Color | None:
        if not isinstance(ref, dict):
            return None
        name = _opt_str(ref, "name")
        medium = _opt_str(ref, "medium")
        if not name or not medium:
            return None
        color = self.colors.get((_key(name), _key(medium)))
        if color is None:
            self.warn(f"{context}: Farbe „{name} ({medium})“ unbekannt — nicht gesetzt")
        return color

    def resolve_material(self, name: str | None, *, context: str) -> Material | None:
        if not name:
            return None
        material = self.materials.get(_key(name))
        if material is None:
            self.warn(f"{context}: Material „{name}“ unbekannt — übersprungen")
        return material

    def resolve_product(self, name: str | None, *, context: str) -> Product | None:
        if not name:
            return None
        product = self.products.get(_key(name))
        if product is None:
            self.warn(f"{context}: Produkt „{name}“ unbekannt — übersprungen")
        return product

    def resolve_tags(self, names: Any, *, context: str) -> list[Tag]:
        if not isinstance(names, list):
            return []
        resolved: list[Tag] = []
        for raw in names:
            name = str(raw).strip()
            if not name:
                continue
            tag = self.tags.get(_key(name))
            if tag is None:
                self.warn(f"{context}: Tag „{name}“ unbekannt — übersprungen")
                continue
            if tag not in resolved:
                resolved.append(tag)
        return resolved


def import_backup(db: Session, payload: dict[str, Any], mode: str = "merge") -> dict[str, Any]:
    """Backup einlesen. `mode`: „replace“ (App-Daten ersetzen) oder „merge“ (Upsert).

    Gibt `{"mode", "created", "updated", "warnings"}` zurück.
    """
    if mode not in IMPORT_MODES:
        raise _bad_request(f"Unbekannter Modus „{mode}“ — erlaubt: {', '.join(IMPORT_MODES)}")
    _validate_envelope(payload)

    ctx = _Ctx(db)
    try:
        if mode == "replace":
            _wipe_app_data(db)
        ctx.load_existing()

        _import_locations(ctx, _as_list(payload, "locations"))
        _import_media(ctx, _as_list(payload, "color_media"))
        _import_colors(ctx, _as_list(payload, "colors"))
        _import_tags(ctx, _as_list(payload, "tags"))
        _import_families(ctx, "material", _as_list(payload, "material_families"))
        _import_families(ctx, "product", _as_list(payload, "product_families"))
        _import_materials(ctx, _as_list(payload, "materials"))
        products = _as_list(payload, "products")
        _import_products(ctx, products)
        _import_product_links(ctx, products)
        _import_sets(ctx, _as_list(payload, "product_sets"))
        _import_movements(ctx, payload, mode)

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise _bad_request(f"Backup konnte nicht geladen werden: {exc.orig}") from exc
    except Exception:
        db.rollback()
        raise

    return {
        "mode": mode,
        "created": dict(sorted(ctx.created.items())),
        "updated": dict(sorted(ctx.updated.items())),
        "warnings": ctx.warnings,
    }


def _validate_envelope(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise _bad_request("Backup muss ein JSON-Objekt sein")
    if payload.get("format") != FORMAT_ID:
        raise _bad_request(f"Unbekanntes Backup-Format — erwartet „{FORMAT_ID}“")
    try:
        version = int(payload.get("version"))
    except (TypeError, ValueError) as exc:
        raise _bad_request("Backup-Version fehlt oder ist ungültig") from exc
    if version != FORMAT_VERSION:
        raise _bad_request(f"Backup-Version {version} nicht unterstützt (erwartet {FORMAT_VERSION})")


def _wipe_app_data(db: Session) -> None:
    """App-Daten löschen — FK-sichere Reihenfolge. Standorte bleiben erhalten."""
    db.execute(delete(StockMovement))
    db.execute(delete(SetBomLine))
    db.execute(delete(OptionMapping))
    db.execute(delete(SetVariant))
    db.execute(delete(ProductSet))
    db.execute(delete(ProductMaterial))
    db.execute(delete(product_tags))
    db.execute(delete(material_tags))
    db.execute(delete(ProductStock))
    db.execute(delete(MaterialStock))
    # Selbstreferenz auflösen, bevor Produkte gelöscht werden
    db.execute(update(Product).values(transform_target_id=None))
    db.execute(delete(Product))
    db.execute(delete(Material))
    db.execute(delete(ProductFamily))
    db.execute(delete(MaterialFamily))
    db.execute(delete(Color))
    db.execute(delete(ColorMedium))
    db.execute(delete(Tag))
    db.flush()
    db.expire_all()


def _import_locations(ctx: _Ctx, entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        name = _str_field(entry, "name", context="Standort")
        existing = ctx.locations.get(_key(name))
        is_virtual = _bool_field(entry, "is_virtual")
        if existing is None:
            location = Location(name=name, is_virtual=is_virtual)
            ctx.db.add(location)
            ctx.db.flush()
            ctx.locations[_key(name)] = location
            ctx.created["locations"] += 1
        elif existing.is_virtual != is_virtual or existing.name != name:
            existing.name = name
            existing.is_virtual = is_virtual
            ctx.updated["locations"] += 1


def _import_media(ctx: _Ctx, entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        name = _str_field(entry, "name", context="Farb-Medium")
        existing = ctx.media.get(_key(name))
        if existing is None:
            medium = ColorMedium(name=name)
            ctx.db.add(medium)
            ctx.db.flush()
            ctx.media[_key(name)] = medium
            ctx.created["color_media"] += 1
        elif existing.name != name:
            existing.name = name
            ctx.updated["color_media"] += 1


def _import_colors(ctx: _Ctx, entries: list[dict[str, Any]]) -> None:
    from app.color_hex import hex_for_color_name, normalize_hex

    for entry in entries:
        name = _str_field(entry, "name", context="Farbe")
        medium_name = _str_field(entry, "medium", context=f"Farbe „{name}“")
        medium = ctx.media.get(_key(medium_name))
        if medium is None:
            medium = ColorMedium(name=medium_name)
            ctx.db.add(medium)
            ctx.db.flush()
            ctx.media[_key(medium_name)] = medium
            ctx.created["color_media"] += 1
        try:
            hex_val = normalize_hex(_opt_str(entry, "hex"))
        except ValueError:
            ctx.warn(f"Farbe „{name}“: Hex ungültig — ignoriert")
            hex_val = None
        if not hex_val:
            hex_val = hex_for_color_name(name)
        key = (_key(name), _key(medium_name))
        existing = ctx.colors.get(key)
        if existing is not None:
            if hex_val and not existing.hex:
                existing.hex = hex_val
                ctx.updated["colors"] += 1
            continue
        color = Color(name=name, medium_id=medium.id, hex=hex_val)
        ctx.db.add(color)
        ctx.db.flush()
        ctx.colors[key] = color
        ctx.created["colors"] += 1


def _import_tags(ctx: _Ctx, entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        name = _str_field(entry, "name", context="Tag")
        existing = ctx.tags.get(_key(name))
        if existing is None:
            tag = Tag(name=name)
            ctx.db.add(tag)
            ctx.db.flush()
            ctx.tags[_key(name)] = tag
            ctx.created["tags"] += 1
        elif existing.name != name:
            existing.name = name
            ctx.updated["tags"] += 1


def _import_families(ctx: _Ctx, kind: str, entries: list[dict[str, Any]]) -> None:
    """Zuerst Eltern, dann Unterfamilien."""
    registry = ctx.material_families if kind == "material" else ctx.product_families
    Model = MaterialFamily if kind == "material" else ProductFamily
    parents = [e for e in entries if not _opt_str(e, "parent")]
    children = [e for e in entries if _opt_str(e, "parent")]
    for entry in parents:
        name = _str_field(entry, "name", context=f"{kind}-Familie")
        key = (None, _key(name))
        if key in registry:
            ctx.updated[f"{kind}_families"] += 1
            continue
        row = Model(name=name, parent_id=None)
        ctx.db.add(row)
        ctx.db.flush()
        registry[key] = row
        ctx.created[f"{kind}_families"] += 1
    for entry in children:
        name = _str_field(entry, "name", context=f"{kind}-Unterfamilie")
        parent_name = _opt_str(entry, "parent")
        assert parent_name
        parent = registry.get((None, _key(parent_name)))
        if parent is None:
            parent = Model(name=parent_name, parent_id=None)
            ctx.db.add(parent)
            ctx.db.flush()
            registry[(None, _key(parent_name))] = parent
            ctx.created[f"{kind}_families"] += 1
        key = (_key(parent_name), _key(name))
        if key in registry:
            ctx.updated[f"{kind}_families"] += 1
            continue
        row = Model(name=name, parent_id=parent.id)
        ctx.db.add(row)
        ctx.db.flush()
        registry[key] = row
        ctx.created[f"{kind}_families"] += 1


def _parse_unit(entry: dict[str, Any], *, context: str) -> Unit:
    raw = _str_field(entry, "unit", context=context)
    try:
        return Unit(raw)
    except ValueError as exc:
        allowed = ", ".join(u.value for u in Unit)
        raise _bad_request(f"{context}: Einheit „{raw}“ unbekannt (erlaubt: {allowed})") from exc


def _set_stocks(
    ctx: _Ctx,
    entries: Any,
    *,
    context: str,
    existing: dict[int, MaterialStock | ProductStock],
    make: Any,
) -> None:
    """Bestände pro Standort SETZEN (nicht addieren)."""
    if not isinstance(entries, list):
        return
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        location = ctx.resolve_location(_opt_str(raw, "location"), context=context)
        if location is None:
            continue
        quantity = _dec_field(raw, "quantity", context=context, default=Decimal("0")) or Decimal("0")
        row = existing.get(location.id)
        if row is None:
            ctx.db.add(make(location.id, services._q(quantity)))
        else:
            row.quantity = services._q(quantity)


def _import_materials(ctx: _Ctx, entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        name = _str_field(entry, "name", context="Material")
        context = f"Material „{name}“"
        material = ctx.materials.get(_key(name))
        is_new = material is None

        unit = _parse_unit(entry, context=context)
        purchase_quantity = _dec_field(
            entry, "purchase_quantity", context=context, default=Decimal("1")
        ) or Decimal("1")
        purchase_price = _dec_field(
            entry, "purchase_price", context=context, default=Decimal("0")
        ) or Decimal("0")
        if purchase_quantity <= 0:
            ctx.warn(f"{context}: Einkaufsmenge ≤ 0 — auf 1 gesetzt")
            purchase_quantity = Decimal("1")

        if is_new:
            material = Material(name=name)
            ctx.db.add(material)
            material.created_at = _dt_field(entry, "created_at") or services._utcnow()
            material.created_by = _opt_str(entry, "created_by")
        else:
            material.name = name

        material.unit = unit
        material.purchase_quantity = services._q(purchase_quantity)
        material.purchase_price = services._m(purchase_price)
        material.cost_per_unit = services._unit_cost(purchase_price, purchase_quantity)
        min_stock = _dec_field(entry, "min_stock", context=context)
        material.min_stock = services._q(min_stock) if min_stock is not None else None
        material.is_template = _bool_field(entry, "is_template")
        raw_decimals = entry.get("decimal_places", 0)
        try:
            decimals = int(raw_decimals if raw_decimals is not None else 0)
        except (TypeError, ValueError):
            decimals = 0
        material.decimal_places = max(0, min(3, decimals))
        from app.families import assign_article_family

        assign_article_family(material, ctx.resolve_family("material", entry, context=context))
        material.overview_ignored = bool(entry.get("overview_ignored") or False)
        color = ctx.resolve_color(entry.get("color"), context=context)
        material.color_id = color.id if color else None
        material.tags = ctx.resolve_tags(entry.get("tags"), context=context)
        material.updated_at = services._utcnow()
        material.updated_by = _opt_str(entry, "updated_by")
        ctx.db.flush()

        ctx.materials[_key(name)] = material
        _set_stocks(
            ctx,
            entry.get("stocks"),
            context=context,
            existing={stock.location_id: stock for stock in material.stocks},
            make=lambda location_id, qty, mid=material.id: MaterialStock(
                material_id=mid, location_id=location_id, quantity=qty
            ),
        )
        ctx.db.flush()
        if is_new:
            ctx.created["materials"] += 1
        else:
            ctx.updated["materials"] += 1


def _apply_sku(ctx: _Ctx, product: Product, sku: str | None, *, context: str) -> None:
    """SKU setzen und das Namensregister nachziehen; Kollisionen werden gemeldet."""
    if sku:
        owner = ctx.products_by_sku.get(_key(sku))
        if owner is not None and owner is not product:
            ctx.warn(f"{context}: SKU „{sku}“ bereits bei „{owner.name}“ — nicht übernommen")
            return

    previous = _key(product.sku) if product.sku else None
    if previous and (sku is None or _key(sku) != previous):
        ctx.products_by_sku.pop(previous, None)
    product.sku = sku
    if sku:
        ctx.products_by_sku[_key(sku)] = product


def _import_products(ctx: _Ctx, entries: list[dict[str, Any]]) -> None:
    """Pass 1: Stammdaten, Farbe, Tags, Bestände. Keine Selbst-/BOM-Referenzen."""
    matched: set[int] = set()
    for entry in entries:
        name = _str_field(entry, "name", context="Produkt")
        context = f"Produkt „{name}“"
        sku = _opt_str(entry, "sku")
        product = ctx.products.get(_key(name))
        if product is None and sku:
            # SKU ist stabiler als der Name → erlaubt Umbenennungen beim Merge.
            candidate = ctx.products_by_sku.get(_key(sku))
            if candidate is not None and candidate.id not in matched:
                product = candidate
        is_new = product is None

        if is_new:
            product = Product(name=name)
            ctx.db.add(product)
            product.created_at = _dt_field(entry, "created_at") or services._utcnow()
            product.created_by = _opt_str(entry, "created_by")
        elif _key(product.name) != _key(name):
            clash = ctx.products.get(_key(name))
            if clash is not None and clash is not product:
                ctx.warn(f"{context}: Name bereits vergeben — Umbenennung übersprungen")
            else:
                ctx.products.pop(_key(product.name), None)
                product.name = name
        else:
            product.name = name

        _apply_sku(ctx, product, sku, context=context)
        selling_price = _dec_field(entry, "selling_price", context=context, default=Decimal("0"))
        product.selling_price = services._m(selling_price if selling_price is not None else 0)
        min_stock = _dec_field(entry, "min_stock", context=context)
        product.min_stock = services._q(min_stock) if min_stock is not None else None
        product.is_template = _bool_field(entry, "is_template")
        product.is_on_demand = _bool_field(entry, "is_on_demand")
        from app.families import assign_article_family

        assign_article_family(product, ctx.resolve_family("product", entry, context=context))
        product.overview_ignored = _bool_field(entry, "overview_ignored")
        color = ctx.resolve_color(entry.get("color"), context=context)
        product.color_id = color.id if color else None
        product.tags = ctx.resolve_tags(entry.get("tags"), context=context)
        product.updated_at = services._utcnow()
        product.updated_by = _opt_str(entry, "updated_by")
        ctx.db.flush()

        matched.add(product.id)
        ctx.products[_key(name)] = product
        _set_stocks(
            ctx,
            entry.get("stocks"),
            context=context,
            existing={stock.location_id: stock for stock in product.stocks},
            make=lambda location_id, qty, pid=product.id: ProductStock(
                product_id=pid, location_id=location_id, quantity=qty
            ),
        )
        ctx.db.flush()
        if is_new:
            ctx.created["products"] += 1
        else:
            ctx.updated["products"] += 1


def _import_product_links(ctx: _Ctx, entries: list[dict[str, Any]]) -> None:
    """Pass 2: transform_target und Stücklisten — alle Produkte/Materialien existieren."""
    for entry in entries:
        name = _str_field(entry, "name", context="Produkt")
        context = f"Produkt „{name}“"
        product = ctx.products.get(_key(name))
        if product is None:
            continue

        # transform_target_id Legacy: Runtime nutzt Uni→Vintage per Name; Feld bleibt ungesetzt
        product.transform_target_id = None

        desired_mat: dict[int, Decimal] = {}
        desired_prod: dict[int, Decimal] = {}
        for raw in entry.get("bom") or []:
            if not isinstance(raw, dict):
                continue
            quantity = _dec_field(raw, "quantity_required", context=f"{context} (Stückliste)")
            if quantity is None or quantity <= 0:
                ctx.warn(f"{context}: Stücklisten-Menge ungültig — übersprungen")
                continue
            material_id, product_id = _component_ids(ctx, raw, context=f"{context} (Stückliste)")
            if material_id is not None:
                desired_mat[material_id] = services._q(quantity)
            elif product_id is not None:
                if product_id == product.id:
                    ctx.warn(f"{context}: Selbstbezug in Stückliste — übersprungen")
                    continue
                desired_prod[product_id] = services._q(quantity)

        existing_mat = {
            line.material_id: line for line in product.materials if line.material_id is not None
        }
        existing_prod = {
            line.component_product_id: line
            for line in product.materials
            if line.component_product_id is not None
        }
        for material_id, line in existing_mat.items():
            if material_id not in desired_mat:
                ctx.db.delete(line)
        for component_id, line in existing_prod.items():
            if component_id not in desired_prod:
                ctx.db.delete(line)
        for material_id, quantity in desired_mat.items():
            line = existing_mat.get(material_id)
            if line is None:
                ctx.db.add(
                    ProductMaterial(
                        product_id=product.id,
                        material_id=material_id,
                        component_product_id=None,
                        quantity_required=quantity,
                    )
                )
            else:
                line.quantity_required = quantity
        for component_id, quantity in desired_prod.items():
            line = existing_prod.get(component_id)
            if line is None:
                ctx.db.add(
                    ProductMaterial(
                        product_id=product.id,
                        material_id=None,
                        component_product_id=component_id,
                        quantity_required=quantity,
                    )
                )
            else:
                line.quantity_required = quantity
        ctx.db.flush()


def _component_ids(ctx: _Ctx, entry: dict[str, Any], *, context: str) -> tuple[int | None, int | None]:
    material_name = _opt_str(entry, "material_name")
    product_name = _opt_str(entry, "product_name")
    if bool(material_name) == bool(product_name):
        ctx.warn(f"{context}: genau eine Komponente (Material oder Produkt) erwartet — übersprungen")
        return None, None
    if material_name:
        material = ctx.resolve_material(material_name, context=context)
        return (material.id if material else None), None
    product = ctx.resolve_product(product_name, context=context)
    return None, (product.id if product else None)


def _import_sets(ctx: _Ctx, entries: list[dict[str, Any]]) -> None:
    db = ctx.db
    by_handle = {_key(row.handle): row for row in db.scalars(select(ProductSet)).all()}

    for entry in entries:
        handle = _str_field(entry, "handle", context="Set")
        name = _opt_str(entry, "name") or handle
        context = f"Set „{handle}“"
        product_set = by_handle.get(_key(handle))
        is_new = product_set is None
        if is_new:
            product_set = ProductSet(name=name, handle=handle)
            db.add(product_set)
        else:
            product_set.name = name
        product_set.count_materials_in_buildability = _bool_field(
            entry, "count_materials_in_buildability", default=True
        )
        db.flush()
        by_handle[_key(handle)] = product_set
        if is_new:
            ctx.created["product_sets"] += 1
        else:
            ctx.updated["product_sets"] += 1

        _import_variants(ctx, product_set, entry.get("variants") or [], context=context)
        _import_option_mappings(
            ctx, product_set, entry.get("option_mappings") or [], context=context
        )


def _variant_key(entry: dict[str, Any] | SetVariant) -> tuple[str, str, str]:
    if isinstance(entry, SetVariant):
        values = (entry.option1_value, entry.option2_value, entry.option3_value)
    else:
        values = (
            _opt_str(entry, "option1_value"),
            _opt_str(entry, "option2_value"),
            _opt_str(entry, "option3_value"),
        )
    return tuple((value or "").strip().casefold() for value in values)  # type: ignore[return-value]


def _import_variants(
    ctx: _Ctx, product_set: ProductSet, entries: Any, *, context: str
) -> None:
    if not isinstance(entries, list):
        return
    existing = {_variant_key(variant): variant for variant in product_set.variants}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = _variant_key(entry)
        variant = existing.get(key)
        is_new = variant is None
        if is_new:
            variant = SetVariant(set_id=product_set.id)
            ctx.db.add(variant)
            existing[key] = variant
        for index in (1, 2, 3):
            setattr(variant, f"option{index}_name", _opt_str(entry, f"option{index}_name"))
            setattr(variant, f"option{index}_value", _opt_str(entry, f"option{index}_value"))
        ctx.db.flush()
        if is_new:
            ctx.created["set_variants"] += 1
        else:
            ctx.updated["set_variants"] += 1

        variant_context = f"{context} Variante „{'/'.join(k for k in key if k) or '–'}“"
        for line in list(variant.bom_lines):
            ctx.db.delete(line)
        ctx.db.flush()
        for raw in entry.get("bom") or []:
            if not isinstance(raw, dict):
                continue
            material_id, product_id = _component_ids(ctx, raw, context=variant_context)
            if material_id is None and product_id is None:
                continue
            quantity = _dec_field(raw, "quantity_required", context=variant_context)
            if quantity is None or quantity <= 0:
                ctx.warn(f"{variant_context}: Stücklisten-Menge ungültig — übersprungen")
                continue
            ctx.db.add(
                SetBomLine(
                    variant_id=variant.id,
                    material_id=material_id,
                    product_id=product_id,
                    quantity_required=services._q(quantity),
                    is_manual=_bool_field(raw, "is_manual"),
                )
            )
            ctx.created["set_bom_lines"] += 1
        ctx.db.flush()


def _import_option_mappings(
    ctx: _Ctx, product_set: ProductSet, entries: Any, *, context: str
) -> None:
    if not isinstance(entries, list):
        return
    existing = {
        (_key(m.option_name), _key(m.option_value)): m for m in product_set.option_mappings
    }
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        option_name = _str_field(entry, "option_name", context=context)
        option_value = _str_field(entry, "option_value", context=context)
        mapping_context = f"{context} Option „{option_name}={option_value}“"
        material_id, product_id = _component_ids(ctx, entry, context=mapping_context)
        if material_id is None and product_id is None:
            continue
        quantity = _dec_field(
            entry, "quantity_required", context=mapping_context, default=Decimal("1")
        ) or Decimal("1")
        if quantity <= 0:
            ctx.warn(f"{mapping_context}: Menge ≤ 0 — auf 1 gesetzt")
            quantity = Decimal("1")

        key = (_key(option_name), _key(option_value))
        mapping = existing.get(key)
        if mapping is None:
            mapping = OptionMapping(
                set_id=product_set.id, option_name=option_name, option_value=option_value
            )
            ctx.db.add(mapping)
            existing[key] = mapping
            ctx.created["option_mappings"] += 1
        else:
            ctx.updated["option_mappings"] += 1
        mapping.material_id = material_id
        mapping.product_id = product_id
        mapping.quantity_required = services._q(quantity)
        ctx.db.flush()


def _import_movements(ctx: _Ctx, payload: dict[str, Any], mode: str) -> None:
    entries = payload.get("movements")
    if not entries:
        return
    if mode != "replace":
        ctx.warn(
            "Bewegungen werden im Merge-Modus nicht importiert "
            "(würde die Historie doppeln) — Modus „replace“ verwenden"
        )
        return

    for entry in _as_list(payload, "movements"):
        context = "Bewegung"
        raw_kind = _str_field(entry, "kind", context=context)
        try:
            kind = StockMovementKind(raw_kind)
        except ValueError:
            ctx.warn(f"{context}: Typ „{raw_kind}“ unbekannt — übersprungen")
            continue
        from_location = ctx.resolve_location(_opt_str(entry, "from_location"), context=context)
        to_location = ctx.resolve_location(_opt_str(entry, "to_location"), context=context)
        if from_location is None or to_location is None:
            continue
        quantity = _dec_field(entry, "quantity", context=context, default=Decimal("0")) or Decimal("0")
        product = ctx.products.get(_key(_opt_str(entry, "product_name") or ""))
        material = ctx.materials.get(_key(_opt_str(entry, "material_name") or ""))
        to_product = ctx.products.get(_key(_opt_str(entry, "to_product_name") or ""))
        ctx.db.add(
            StockMovement(
                kind=kind,
                product_id=product.id if product else None,
                material_id=material.id if material else None,
                to_product_id=to_product.id if to_product else None,
                from_location_id=from_location.id,
                to_location_id=to_location.id,
                quantity=services._q(quantity),
                note=_opt_str(entry, "note"),
                created_at=_dt_field(entry, "created_at") or services._utcnow(),
                created_by=_opt_str(entry, "created_by"),
            )
        )
        ctx.created["movements"] += 1
    ctx.db.flush()
