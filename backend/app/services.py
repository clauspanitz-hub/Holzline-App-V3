from datetime import datetime, timezone
from decimal import Decimal
from math import floor

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.color_hex import hex_for_color_name
from app.database import AUSSCHUSS_LOCATION_NAME
from app.models import (
    Color,
    ColorMedium,
    CustomerOrder,
    Location,
    Material,
    MaterialStock,
    OptionMapping,
    OrderLine,
    Product,
    ProductMaterial,
    ProductSet,
    ProductStock,
    SetBomLine,
    SetVariant,
    StockMovement,
    StockMovementKind,
    Tag,
    WorkTodo,
)
from app.schemas import (
    BomLineCreate,
    BomLineRead,
    BomLineUpdate,
    ColorCreate,
    ColorMatchSuggestion,
    ColorRead,
    ColorUpdate,
    ColorWriteResult,
    ManufactureResult,
    MaterialCreate,
    MaterialRead,
    MaterialsFromColorsRequest,
    MaterialsFromColorsResult,
    MaterialUpdate,
    MediumCreate,
    MediumRead,
    MediumUpdate,
    MediumWriteResult,
    OptionMappingCreate,
    OptionMappingRead,
    ProductCreate,
    ProductRead,
    ProductsFromColorsRequest,
    ProductsFromColorsResult,
    ProductSetCreate,
    ProductSetRead,
    ProductSetUpdate,
    ProductUpdate,
    SetBomLineCreate,
    SetBomLineRead,
    SetVariantRead,
    ShopifyInventoryImportResult,
    StockAdjustRequest,
    StockByLocation,
    StockDeltaRequest,
    StockMovementRead,
    TagCreate,
    TagRead,
    TagUpdate,
    TransferRequest,
    TransformRequest,
)


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.001"))


def _m(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _unit_cost(purchase_price: Decimal, purchase_quantity: Decimal) -> Decimal:
    qty = Decimal(purchase_quantity)
    if qty <= 0:
        return Decimal("0.0000")
    return (Decimal(purchase_price) / qty).quantize(Decimal("0.0001"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stamp_update(entity: Material | Product) -> None:
    entity.updated_at = _utcnow()


def _allocate_unique_name(
    db: Session,
    model: type[Material] | type[Product],
    desired: str,
    *,
    exclude_id: int | None = None,
) -> tuple[str, str | None]:
    """Return unique name; numeric suffix if taken. (name, warning)."""

    def is_taken(name: str) -> bool:
        stmt = select(model.id).where(model.name == name)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        return db.scalars(stmt.limit(1)).first() is not None

    if not is_taken(desired):
        return desired, None
    n = 2
    while True:
        candidate = f"{desired} {n}"
        if not is_taken(candidate):
            return candidate, f"Name „{desired}“ belegt — umbenannt zu „{candidate}“."
        n += 1


def _rename_entity(
    db: Session,
    entity: Material | Product,
    desired: str,
    warnings: list[str],
) -> None:
    if entity.name == desired:
        return
    model = Material if isinstance(entity, Material) else Product
    new_name, warn = _allocate_unique_name(db, model, desired, exclude_id=entity.id)
    if warn:
        warnings.append(warn)
    entity.name = new_name
    _stamp_update(entity)


def get_location(db: Session, location_id: int) -> Location:
    location = db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Standort nicht gefunden")
    return location


def default_location(db: Session) -> Location:
    location = db.scalars(select(Location).where(Location.name == "Hamburg")).first()
    if not location:
        location = db.scalars(select(Location)).first()
    if not location:
        raise HTTPException(status_code=500, detail="Keine Standorte vorhanden")
    return location


def list_locations(db: Session) -> list[Location]:
    from app.database import LOCATION_DISPLAY_ORDER

    rows = list(db.scalars(select(Location)).all())
    order_index = {name: i for i, name in enumerate(LOCATION_DISPLAY_ORDER)}

    def sort_key(loc: Location) -> tuple:
        return (order_index.get(loc.name, 1000), loc.name)

    return sorted(rows, key=sort_key)


def color_read(color: Color | None) -> ColorRead | None:
    if not color:
        return None
    return ColorRead(
        id=color.id,
        name=color.name,
        hex=color.hex,
        medium_id=color.medium_id,
        medium=MediumRead.model_validate(color.medium),
    )


def resolve_tags(db: Session, tag_ids: list[int]) -> list[Tag]:
    """Assign only existing catalog tags (no free-text create)."""
    if not tag_ids:
        return []
    unique_ids: list[int] = []
    seen: set[int] = set()
    for tid in tag_ids:
        if tid in seen:
            continue
        seen.add(tid)
        unique_ids.append(tid)
    rows = list(db.scalars(select(Tag).where(Tag.id.in_(unique_ids))).all())
    by_id = {t.id: t for t in rows}
    missing = [tid for tid in unique_ids if tid not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"Tag(s) nicht gefunden: {missing}")
    return [by_id[tid] for tid in unique_ids]


def merge_tags(*groups: list[Tag]) -> list[Tag]:
    """Merge tag lists preserving order; first occurrence wins."""
    out: list[Tag] = []
    seen: set[int] = set()
    for group in groups:
        for tag in group:
            if tag.id in seen:
                continue
            seen.add(tag.id)
            out.append(tag)
    return out


def ensure_system_incomplete_tags(db: Session) -> list[str]:
    """Create missing system fehlt-tags. Returns names of newly created tags."""
    from app.incomplete_tags import SYSTEM_INCOMPLETE_TAG_NAMES

    newly: list[str] = []
    for name in sorted(SYSTEM_INCOMPLETE_TAG_NAMES):
        exists = db.scalars(select(Tag).where(Tag.name == name).limit(1)).first()
        if exists is None:
            db.add(Tag(name=name))
            newly.append(name)
    if newly:
        db.commit()
    return newly


def _system_incomplete_tag_map(db: Session) -> dict[str, Tag]:
    from app.incomplete_tags import SYSTEM_INCOMPLETE_TAG_NAMES

    rows = db.scalars(select(Tag).where(Tag.name.in_(SYSTEM_INCOMPLETE_TAG_NAMES))).all()
    by_name = {t.name: t for t in rows}
    for name in SYSTEM_INCOMPLETE_TAG_NAMES:
        if name not in by_name:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
            by_name[name] = tag
    return by_name


def sync_incomplete_tags(
    db: Session,
    entity: Material | Product,
    *,
    before_missing: list[str],
) -> None:
    """Update fehlt-tags from incomplete-field transitions. Caller commits.

    - Fields now complete → remove corresponding tag.
    - Fields newly incomplete (in after but not before) → add tag.
    - Still incomplete and tag was manually removed → leave absent.
    """
    from app.incomplete_tags import TAG_BY_FIELD

    if isinstance(entity, Material):
        after_missing = material_incomplete_fields_raw(entity)
    else:
        after_missing = product_incomplete_fields_raw(entity)

    after_set = set(after_missing)
    before_set = set(before_missing)
    by_name = _system_incomplete_tag_map(db)

    kept: list[Tag] = []
    for tag in list(entity.tags):
        field = next((f for f, n in TAG_BY_FIELD.items() if n == tag.name), None)
        if field is not None and field not in after_set:
            continue
        kept.append(tag)
    entity.tags = kept
    current_names = {t.name for t in entity.tags}

    for field in after_set - before_set:
        tag_name = TAG_BY_FIELD[field]
        if tag_name not in current_names:
            entity.tags = [*entity.tags, by_name[tag_name]]
            current_names.add(tag_name)


def backfill_incomplete_tags(db: Session, newly_created_tag_names: list[str]) -> None:
    """One-shot: assign fehlt-tags for fields whose system tags were just created."""
    from app.incomplete_tags import TAG_BY_FIELD

    if not newly_created_tag_names:
        return
    new_names = set(newly_created_tag_names)

    materials = db.scalars(select(Material).options(selectinload(Material.tags))).all()
    for material in materials:
        after = material_incomplete_fields_raw(material)
        before = [f for f in after if TAG_BY_FIELD[f] not in new_names]
        sync_incomplete_tags(db, material, before_missing=before)

    products = db.scalars(
        select(Product).options(
            selectinload(Product.tags),
            selectinload(Product.materials),
        )
    ).all()
    for product in products:
        after = product_incomplete_fields_raw(product)
        before = [f for f in after if TAG_BY_FIELD[f] not in new_names]
        sync_incomplete_tags(db, product, before_missing=before)

    db.commit()


def get_medium(db: Session, medium_id: int) -> ColorMedium:
    medium = db.get(ColorMedium, medium_id)
    if not medium:
        raise HTTPException(status_code=404, detail="Medium nicht gefunden")
    return medium


def list_media(db: Session) -> list[MediumRead]:
    rows = db.scalars(select(ColorMedium).order_by(ColorMedium.name)).all()
    return [MediumRead.model_validate(r) for r in rows]


def create_medium(db: Session, payload: MediumCreate) -> MediumRead:
    name = payload.name.strip()
    medium = ColorMedium(name=name)
    db.add(medium)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Medium „{name}“ existiert bereits") from exc
    db.refresh(medium)
    return MediumRead.model_validate(medium)


def update_medium(db: Session, medium_id: int, payload: MediumUpdate) -> MediumWriteResult:
    medium = get_medium(db, medium_id)
    old_name = medium.name
    new_name = payload.name.strip()
    medium.name = new_name
    warnings: list[str] = []
    try:
        if old_name != new_name:
            colors = list(
                db.scalars(
                    select(Color).where(Color.medium_id == medium_id).options(selectinload(Color.medium))
                ).all()
            )
            for color in colors:
                old_series = f"{old_name} {color.name}".strip()
                new_series = f"{new_name} {color.name}".strip()
                for material in db.scalars(select(Material).where(Material.name == old_series)).all():
                    _rename_entity(db, material, new_series, warnings)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Medium „{new_name}“ existiert bereits") from exc
    db.refresh(medium)
    result = MediumWriteResult.model_validate(medium)
    result.warnings = warnings
    return result


def delete_medium(db: Session, medium_id: int) -> None:
    """Deletes medium and its colors (CASCADE); materials/products.color_id → NULL."""
    medium = get_medium(db, medium_id)
    db.delete(medium)
    db.commit()


def get_color(db: Session, color_id: int | None) -> Color | None:
    if color_id is None:
        return None
    color = db.scalars(
        select(Color).where(Color.id == color_id).options(selectinload(Color.medium))
    ).first()
    if not color:
        raise HTTPException(status_code=404, detail="Farbe nicht gefunden")
    return color


def list_colors(db: Session, medium_id: int | None = None) -> list[ColorRead]:
    stmt = select(Color).options(selectinload(Color.medium)).order_by(Color.medium_id, Color.name)
    if medium_id is not None:
        stmt = stmt.where(Color.medium_id == medium_id)
    rows = db.scalars(stmt).all()
    return [color_read(r) for r in rows]  # type: ignore[arg-type]


def create_color(db: Session, payload: ColorCreate) -> ColorRead:
    medium = get_medium(db, payload.medium_id)
    name = payload.name.strip()
    color = Color(
        name=name,
        medium_id=medium.id,
        hex=payload.hex or hex_for_color_name(name),
    )
    db.add(color)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Farbe „{payload.name.strip()}“ ({medium.name}) existiert bereits",
        ) from exc
    return color_read(get_color(db, color.id))  # type: ignore[arg-type]


def update_color(db: Session, color_id: int, payload: ColorUpdate) -> ColorWriteResult:
    color = get_color(db, color_id)
    assert color is not None
    old_name = color.name
    old_medium_name = color.medium.name
    old_medium_id = color.medium_id
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        color.name = data["name"].strip()
    if "medium_id" in data and data["medium_id"] is not None:
        medium = get_medium(db, data["medium_id"])
        color.medium_id = medium.id
    if "hex" in data:
        color.hex = data["hex"]
    warnings: list[str] = []
    try:
        db.flush()
        # Reload medium relationship after potential medium_id change
        db.refresh(color, attribute_names=["medium"])
        new_name = color.name
        new_medium_name = color.medium.name
        old_series = f"{old_medium_name} {old_name}".strip()
        new_series = f"{new_medium_name} {new_name}".strip()

        if old_series != new_series:
            for material in db.scalars(select(Material).where(Material.name == old_series)).all():
                _rename_entity(db, material, new_series, warnings)

        # Products: exakter Serienname zuerst, dann Suffix „ {alteFarbe}“ (color_id)
        old_suffix = f" {old_name}"
        if old_name != new_name or old_medium_id != color.medium_id:
            for product in db.scalars(select(Product).where(Product.color_id == color_id)).all():
                if product.name == old_series:
                    _rename_entity(db, product, new_series, warnings)
                elif old_name != new_name and product.name.endswith(old_suffix):
                    base = product.name[: -len(old_suffix)]
                    desired = f"{base} {new_name}".strip()
                    _rename_entity(db, product, desired, warnings)

        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Farbe „{color.name}“ existiert in diesem Medium bereits",
        ) from exc
    read = color_read(get_color(db, color.id))  # type: ignore[arg-type]
    assert read is not None
    return ColorWriteResult(**read.model_dump(), warnings=warnings)


def delete_color(db: Session, color_id: int) -> None:
    color = get_color(db, color_id)
    assert color is not None
    # SQLite may still have NO ACTION FKs from older migrations — clear refs explicitly.
    for material in db.scalars(select(Material).where(Material.color_id == color_id)).all():
        material.color_id = None
    for product in db.scalars(select(Product).where(Product.color_id == color_id)).all():
        product.color_id = None
    db.flush()
    db.delete(color)
    db.commit()


def list_tags(db: Session) -> list[TagRead]:
    rows = db.scalars(select(Tag).order_by(Tag.name)).all()
    return [TagRead.model_validate(r) for r in rows]


def create_tag(db: Session, payload: TagCreate) -> TagRead:
    from app.incomplete_tags import is_system_incomplete_tag

    name = payload.name.strip()
    if is_system_incomplete_tag(name):
        raise HTTPException(
            status_code=400,
            detail=f"Tag „{name}“ ist ein System-Tag und wird automatisch verwaltet",
        )
    tag = Tag(name=name)
    db.add(tag)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Tag „{name}“ existiert bereits") from exc
    db.refresh(tag)
    return TagRead.model_validate(tag)


def update_tag(db: Session, tag_id: int, payload: TagUpdate) -> TagRead:
    from app.incomplete_tags import is_system_incomplete_tag

    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag nicht gefunden")
    if is_system_incomplete_tag(tag.name):
        raise HTTPException(status_code=400, detail=f"System-Tag „{tag.name}“ kann nicht umbenannt werden")
    new_name = payload.name.strip()
    if is_system_incomplete_tag(new_name):
        raise HTTPException(status_code=400, detail=f"Name „{new_name}“ ist für System-Tags reserviert")
    tag.name = new_name
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Tag „{tag.name}“ existiert bereits") from exc
    db.refresh(tag)
    return TagRead.model_validate(tag)


def delete_tag(db: Session, tag_id: int) -> None:
    """Removes tag; M:N links cascade-deleted."""
    from app.incomplete_tags import is_system_incomplete_tag

    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag nicht gefunden")
    if is_system_incomplete_tag(tag.name):
        raise HTTPException(status_code=400, detail=f"System-Tag „{tag.name}“ kann nicht gelöscht werden")
    db.delete(tag)
    db.commit()


def _material_stock_total(material: Material) -> Decimal:
    return _q(sum((Decimal(s.quantity) for s in material.stocks), Decimal("0")))


def _product_stock_total(product: Product) -> Decimal:
    return _q(sum((Decimal(s.quantity) for s in product.stocks), Decimal("0")))


def _stock_available_from_rows(stocks: list) -> Decimal:
    return _q(
        sum(
            (
                Decimal(s.quantity)
                for s in stocks
                if getattr(s.location, "name", None) != AUSSCHUSS_LOCATION_NAME
            ),
            Decimal("0"),
        )
    )


def _material_stock_available(material: Material) -> Decimal:
    return _stock_available_from_rows(material.stocks)


def _product_stock_available(product: Product) -> Decimal:
    return _stock_available_from_rows(product.stocks)


def _location_is_virtual(location: Location) -> bool:
    return bool(location.is_virtual)


def _record_movement(
    db: Session,
    *,
    kind: StockMovementKind,
    quantity: Decimal,
    from_location_id: int,
    to_location_id: int,
    product_id: int | None = None,
    material_id: int | None = None,
    to_product_id: int | None = None,
    note: str | None = None,
    created_by: str | None = None,
) -> None:
    db.add(
        StockMovement(
            kind=kind,
            product_id=product_id,
            material_id=material_id,
            to_product_id=to_product_id,
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            quantity=quantity,
            note=(note.strip() if note and note.strip() else None),
            created_by=created_by,
        )
    )


def _maybe_record_transfer(
    db: Session,
    *,
    from_loc: Location,
    to_loc: Location,
    quantity: Decimal,
    product_id: int | None = None,
    material_id: int | None = None,
    note: str | None = None,
) -> None:
    if _location_is_virtual(from_loc) or _location_is_virtual(to_loc):
        _record_movement(
            db,
            kind=StockMovementKind.TRANSFER,
            quantity=quantity,
            from_location_id=from_loc.id,
            to_location_id=to_loc.id,
            product_id=product_id,
            material_id=material_id,
            note=note,
        )


def movement_read(row: StockMovement) -> StockMovementRead:
    return StockMovementRead(
        id=row.id,
        kind=row.kind.value if hasattr(row.kind, "value") else str(row.kind),
        product_id=row.product_id,
        product_name=row.product.name if row.product else None,
        material_id=row.material_id,
        material_name=row.material.name if row.material else None,
        to_product_id=row.to_product_id,
        to_product_name=row.to_product.name if row.to_product else None,
        from_location_id=row.from_location_id,
        from_location_name=row.from_location.name if row.from_location else "?",
        to_location_id=row.to_location_id,
        to_location_name=row.to_location.name if row.to_location else "?",
        quantity=row.quantity,
        note=row.note,
        created_at=row.created_at,
        created_by=row.created_by,
    )


def list_movements(
    db: Session,
    *,
    product_id: int | None = None,
    material_id: int | None = None,
    limit: int = 100,
) -> list[StockMovementRead]:
    stmt = (
        select(StockMovement)
        .options(
            selectinload(StockMovement.product),
            selectinload(StockMovement.to_product),
            selectinload(StockMovement.material),
            selectinload(StockMovement.from_location),
            selectinload(StockMovement.to_location),
        )
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(min(max(limit, 1), 500))
    )
    if product_id is not None:
        stmt = stmt.where(
            (StockMovement.product_id == product_id) | (StockMovement.to_product_id == product_id)
        )
    if material_id is not None:
        stmt = stmt.where(StockMovement.material_id == material_id)
    return [movement_read(row) for row in db.scalars(stmt).all()]


def _resolve_transform_target(db: Session, product_id: int, target_id: int | None) -> int | None:
    if target_id is None:
        return None
    if target_id == product_id:
        raise HTTPException(status_code=400, detail="Zielprodukt darf nicht dasselbe Produkt sein")
    target = db.get(Product, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Zielprodukt nicht gefunden")
    return target.id


def product_name_allows_transform(name: str) -> bool:
    """Umwandlung nur wenn der Produktname „Uni“ enthält (Groß-/Kleinschreibung egal)."""
    return "uni" in (name or "").casefold()


def _stock_rows_material(material: Material) -> list[StockByLocation]:
    return [
        StockByLocation(
            location_id=s.location_id,
            location_name=s.location.name,
            quantity=s.quantity,
            is_negative=s.quantity < 0,
        )
        for s in sorted(material.stocks, key=lambda x: x.location.name)
    ]


def _stock_rows_product(product: Product) -> list[StockByLocation]:
    return [
        StockByLocation(
            location_id=s.location_id,
            location_name=s.location.name,
            quantity=s.quantity,
            is_negative=s.quantity < 0,
        )
        for s in sorted(product.stocks, key=lambda x: x.location.name)
    ]


def _get_or_create_material_stock(db: Session, material_id: int, location_id: int) -> MaterialStock:
    row = db.scalars(
        select(MaterialStock).where(
            MaterialStock.material_id == material_id,
            MaterialStock.location_id == location_id,
        )
    ).first()
    if not row:
        row = MaterialStock(material_id=material_id, location_id=location_id, quantity=Decimal("0"))
        db.add(row)
        db.flush()
    return row


def _get_or_create_product_stock(db: Session, product_id: int, location_id: int) -> ProductStock:
    row = db.scalars(
        select(ProductStock).where(
            ProductStock.product_id == product_id,
            ProductStock.location_id == location_id,
        )
    ).first()
    if not row:
        row = ProductStock(product_id=product_id, location_id=location_id, quantity=Decimal("0"))
        db.add(row)
        db.flush()
    return row


def material_cost_for_product(product: Product, *, _seen: set[int] | None = None) -> Decimal:
    """Roll up material purchase cost through nested product BOM lines."""
    seen = set() if _seen is None else _seen
    if product.id in seen:
        return Decimal("0")
    seen.add(product.id)
    total = Decimal("0")
    for line in product.materials:
        qty = Decimal(line.quantity_required)
        if line.material_id is not None and line.material is not None:
            total += qty * Decimal(line.material.cost_per_unit)
        elif line.component_product is not None:
            total += qty * material_cost_for_product(line.component_product, _seen=seen)
        elif line.component_product_id is not None:
            # lazy: cost unknown without load — treat as 0 in this path
            pass
    return _m(total)


def bom_line_read(line: ProductMaterial, *, db: Session | None = None) -> BomLineRead:
    qty = Decimal(line.quantity_required)
    if line.material_id is not None and line.material is not None:
        line_cost = _m(qty * Decimal(line.material.cost_per_unit))
        return BomLineRead(
            id=line.id,
            material_id=line.material_id,
            product_id=None,
            component_name=line.material.name,
            component_kind="material",
            material_unit=line.material.unit,
            quantity_required=line.quantity_required,
            line_cost=line_cost,
            decimal_places=int(getattr(line.material, "decimal_places", 0) or 0),
        )
    component = line.component_product
    if component is None and db is not None and line.component_product_id is not None:
        component = _load_product(db, line.component_product_id)
    name = component.name if component else f"Produkt #{line.component_product_id}"
    nested_cost = material_cost_for_product(component) if component else Decimal("0")
    return BomLineRead(
        id=line.id,
        material_id=None,
        product_id=line.component_product_id,
        component_name=name,
        component_kind="product",
        material_unit=None,
        quantity_required=line.quantity_required,
        line_cost=_m(qty * Decimal(nested_cost)),
        decimal_places=0,
    )


def material_incomplete_fields_raw(material: Material) -> list[str]:
    missing: list[str] = []
    if material.min_stock is None:
        missing.append("Mindestbestand")
    if Decimal(material.purchase_price) == 0:
        missing.append("Einkaufspreis")
    return missing


def product_incomplete_fields_raw(product: Product) -> list[str]:
    missing: list[str] = []
    if product.min_stock is None:
        missing.append("Mindestbestand")
    if not product.materials:
        missing.append("Stückliste")
    return missing


def material_incomplete_fields(material: Material) -> list[str]:
    from app.incomplete_tags import visible_incomplete_fields

    return visible_incomplete_fields(
        material_incomplete_fields_raw(material),
        {t.name for t in material.tags},
    )


def product_incomplete_fields(product: Product) -> list[str]:
    from app.incomplete_tags import visible_incomplete_fields

    return visible_incomplete_fields(
        product_incomplete_fields_raw(product),
        {t.name for t in product.tags},
    )


def material_read(material: Material) -> MaterialRead:
    total = _material_stock_total(material)
    return MaterialRead(
        id=material.id,
        name=material.name,
        unit=material.unit,
        purchase_quantity=material.purchase_quantity,
        purchase_price=material.purchase_price,
        cost_per_unit=material.cost_per_unit,
        min_stock=material.min_stock,
        is_template=bool(getattr(material, "is_template", False)),
        decimal_places=int(getattr(material, "decimal_places", 0) or 0),
        family=material.family,
        overview_ignored=bool(getattr(material, "overview_ignored", False)),
        color_id=material.color_id,
        color=color_read(material.color),
        tags=[TagRead.model_validate(t) for t in material.tags],
        stock_total=total,
        is_negative=total < 0 or any(s.quantity < 0 for s in material.stocks),
        stocks=_stock_rows_material(material),
        incomplete_fields=material_incomplete_fields(material),
        created_at=material.created_at,
        updated_at=material.updated_at,
        created_by=material.created_by,
        updated_by=material.updated_by,
    )


def product_read(product: Product) -> ProductRead:
    total = _product_stock_total(product)
    available = _product_stock_available(product)
    target = product.transform_target
    return ProductRead(
        id=product.id,
        name=product.name,
        sku=product.sku,
        min_stock=product.min_stock,
        is_template=bool(product.is_template),
        is_on_demand=bool(getattr(product, "is_on_demand", False)),
        family=product.family,
        overview_ignored=bool(getattr(product, "overview_ignored", False)),
        color_id=product.color_id,
        color=color_read(product.color),
        transform_target_id=product.transform_target_id,
        transform_target_name=target.name if target else None,
        tags=[TagRead.model_validate(t) for t in product.tags],
        stock_total=total,
        stock_available=available,
        material_cost=material_cost_for_product(product),
        is_negative=total < 0 or any(s.quantity < 0 for s in product.stocks),
        stocks=_stock_rows_product(product),
        bom=[bom_line_read(line) for line in product.materials],
        incomplete_fields=product_incomplete_fields(product),
        created_at=product.created_at,
        updated_at=product.updated_at,
        created_by=product.created_by,
        updated_by=product.updated_by,
    )


def _load_material(db: Session, material_id: int) -> Material:
    material = db.scalars(
        select(Material)
        .where(Material.id == material_id)
        .options(
            selectinload(Material.stocks).selectinload(MaterialStock.location),
            selectinload(Material.color).selectinload(Color.medium),
            selectinload(Material.tags),
        )
    ).first()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material nicht gefunden")
    return material


def get_material(db: Session, material_id: int) -> Material:
    return _load_material(db, material_id)


def list_materials(
    db: Session,
    tag: str | None = None,
    color_id: int | None = None,
    medium_id: int | None = None,
) -> list[MaterialRead]:
    stmt = (
        select(Material)
        .order_by(Material.updated_at.desc(), Material.name)
        .options(
            selectinload(Material.stocks).selectinload(MaterialStock.location),
            selectinload(Material.color).selectinload(Color.medium),
            selectinload(Material.tags),
        )
    )
    if tag:
        stmt = stmt.join(Material.tags).where(Tag.name == tag)
    if color_id is not None:
        stmt = stmt.where(Material.color_id == color_id)
    if medium_id is not None:
        stmt = stmt.join(Material.color).where(Color.medium_id == medium_id)
    rows = db.scalars(stmt).unique().all()
    return [material_read(row) for row in rows]


def create_material(db: Session, payload: MaterialCreate) -> MaterialRead:
    location = get_location(db, payload.location_id) if payload.location_id else default_location(db)
    purchase_quantity = _q(payload.purchase_quantity)
    purchase_price = _m(payload.purchase_price)
    color = get_color(db, payload.color_id)
    material = Material(
        name=payload.name.strip(),
        unit=payload.unit,
        purchase_quantity=purchase_quantity,
        purchase_price=purchase_price,
        cost_per_unit=_unit_cost(purchase_price, purchase_quantity),
        min_stock=_q(payload.min_stock) if payload.min_stock is not None else None,
        family=(payload.family.strip() if payload.family else None),
        color_id=color.id if color else None,
        decimal_places=int(payload.decimal_places or 0),
    )
    material.tags = resolve_tags(db, payload.tag_ids)
    db.add(material)
    try:
        db.flush()
        db.add(
            MaterialStock(
                material_id=material.id,
                location_id=location.id,
                quantity=_q(payload.stock_quantity),
            )
        )
        sync_incomplete_tags(db, material, before_missing=[])
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        msg = str(getattr(exc, "orig", exc)).lower()
        if "unique" in msg or "name" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Materialname „{payload.name.strip()}“ ist bereits vergeben",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Material konnte nicht gespeichert werden: {exc.orig}",
        ) from exc
    return material_read(_load_material(db, material.id))


def _colors_with_material(db: Session) -> set[int]:
    rows = db.scalars(select(Material.color_id).where(Material.color_id.is_not(None)).distinct()).all()
    return {int(c) for c in rows if c is not None}


def _unique_material_name(db: Session, color: Color) -> tuple[str, str | None]:
    """Preferred: Medium + Farbe; numeric suffix if taken. Returns (name, warning)."""
    base = f"{color.medium.name} {color.name}".strip()
    if not db.scalars(select(Material.id).where(Material.name == base).limit(1)).first():
        return base, None
    n = 2
    while True:
        candidate = f"{base} {n}"
        if not db.scalars(select(Material.id).where(Material.name == candidate).limit(1)).first():
            return candidate, f"Materialname „{base}“ belegt — angelegt als „{candidate}“."
        n += 1


def create_materials_from_colors(db: Session, payload: MaterialsFromColorsRequest) -> MaterialsFromColorsResult:
    from app.schemas import BulkSkipInfo

    base = payload.base_name.strip()
    created_ids: list[int] = []
    skipped: list[BulkSkipInfo] = []
    warnings: list[str] = []
    location = get_location(db, payload.location_id) if payload.location_id else default_location(db)
    used_names: set[str] = set()

    template: Material | None = None
    if payload.template_material_id is not None:
        template = _load_material(db, payload.template_material_id)

    unit = payload.unit if payload.unit is not None else (template.unit if template else None)
    if payload.purchase_quantity is not None:
        purchase_quantity = _q(payload.purchase_quantity)
    elif template is not None:
        purchase_quantity = _q(template.purchase_quantity)
    else:
        purchase_quantity = None
    if payload.purchase_price is not None:
        purchase_price = _m(payload.purchase_price)
    elif template is not None:
        purchase_price = _m(template.purchase_price)
    else:
        purchase_price = None

    if unit is None or purchase_quantity is None or purchase_price is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Einheit und Einkauf müssen im Dialog stehen oder von der Vorlage kommen",
        )

    cost = _unit_cost(purchase_price, purchase_quantity)
    dialog_tags = resolve_tags(db, payload.tag_ids)
    template_tags = list(template.tags) if template else []
    tags = merge_tags(template_tags, dialog_tags)

    if payload.min_stock is not None:
        series_min_stock: Decimal | None = _q(payload.min_stock)
    elif template is not None and template.min_stock is not None:
        series_min_stock = _q(template.min_stock)
    else:
        series_min_stock = None
    series_decimals = int(template.decimal_places or 0) if template is not None else 0

    seen: set[int] = set()
    for color_id in payload.color_ids:
        if color_id in seen:
            continue
        seen.add(color_id)
        color = get_color(db, color_id)
        if not color:
            skipped.append(BulkSkipInfo(color_id=color_id, color_name="?", reason="Farbe nicht gefunden"))
            continue
        name = f"{base} {color.name}".strip()
        if name in used_names or db.scalars(select(Material.id).where(Material.name == name).limit(1)).first():
            skipped.append(
                BulkSkipInfo(
                    color_id=color_id,
                    color_name=color.name,
                    reason=f"Materialname „{name}“ bereits vergeben",
                )
            )
            continue
        material = Material(
            name=name,
            unit=unit,
            purchase_quantity=purchase_quantity,
            purchase_price=purchase_price,
            cost_per_unit=cost,
            min_stock=series_min_stock,
            family=base,
            color_id=color.id,
            decimal_places=series_decimals,
        )
        material.tags = list(tags)
        db.add(material)
        db.flush()
        db.add(
            MaterialStock(
                material_id=material.id,
                location_id=location.id,
                quantity=_q(Decimal("0")),
            )
        )
        created_ids.append(material.id)
        used_names.add(name)

    for mid in created_ids:
        material = _load_material(db, mid)
        sync_incomplete_tags(db, material, before_missing=[])
    db.commit()
    created = [material_read(_load_material(db, mid)) for mid in created_ids]
    return MaterialsFromColorsResult(created=created, skipped=skipped, warnings=warnings)


def update_material(db: Session, material_id: int, payload: MaterialUpdate) -> MaterialRead:
    material = _load_material(db, material_id)
    before_missing = material_incomplete_fields_raw(material)
    data = payload.model_dump(exclude_unset=True)
    tag_ids = data.pop("tag_ids", None)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    if "purchase_quantity" in data and data["purchase_quantity"] is not None:
        data["purchase_quantity"] = _q(data["purchase_quantity"])
    if "purchase_price" in data and data["purchase_price"] is not None:
        data["purchase_price"] = _m(data["purchase_price"])
    if "min_stock" in data:
        data["min_stock"] = _q(data["min_stock"]) if data["min_stock"] is not None else None
    if "family" in data and data["family"] is not None:
        data["family"] = data["family"].strip() or None
    if "color_id" in data:
        color = get_color(db, data["color_id"])
        data["color_id"] = color.id if color else None
    for key, value in data.items():
        setattr(material, key, value)
    if tag_ids is not None:
        material.tags = resolve_tags(db, tag_ids)
    material.cost_per_unit = _unit_cost(Decimal(material.purchase_price), Decimal(material.purchase_quantity))
    sync_incomplete_tags(db, material, before_missing=before_missing)
    _stamp_update(material)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        name = data.get("name") or material.name
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Materialname „{name}“ ist bereits vergeben",
        ) from exc
    return material_read(_load_material(db, material.id))


def delete_material(db: Session, material_id: int) -> None:
    material = _load_material(db, material_id)
    err = _delete_material_row(db, material)
    if err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err)
    db.commit()


def _delete_material_row(db: Session, material: Material) -> str | None:
    """Remove material in-session. Returns error reason or None. Caller commits."""
    if material.product_links:
        return "Material ist in einer Produkt-Stückliste verknüpft und kann nicht gelöscht werden"
    for mapping in db.scalars(select(OptionMapping).where(OptionMapping.material_id == material.id)).all():
        db.delete(mapping)
    for line in db.scalars(select(SetBomLine).where(SetBomLine.material_id == material.id)).all():
        db.delete(line)
    db.flush()
    db.delete(material)
    return None


def bulk_delete_materials(db: Session, payload: "BulkDeleteRequest") -> "BulkDeleteResult":
    from app.schemas import BulkDeleteRequest, BulkDeleteResult, BulkDeleteSkip

    if not isinstance(payload, BulkDeleteRequest):
        payload = BulkDeleteRequest.model_validate(payload)
    deleted_ids: list[int] = []
    skipped: list[BulkDeleteSkip] = []
    seen: set[int] = set()
    for mid in payload.ids:
        if mid in seen:
            continue
        seen.add(mid)
        material = db.scalars(
            select(Material)
            .where(Material.id == mid)
            .options(selectinload(Material.product_links))
        ).first()
        if not material:
            skipped.append(BulkDeleteSkip(id=mid, name="?", reason="nicht gefunden"))
            continue
        name = material.name
        err = _delete_material_row(db, material)
        if err:
            skipped.append(BulkDeleteSkip(id=mid, name=name, reason=err))
            continue
        deleted_ids.append(mid)
    db.commit()
    return BulkDeleteResult(deleted_ids=deleted_ids, skipped=skipped)

def adjust_material_stock(db: Session, material_id: int, payload: StockAdjustRequest) -> MaterialRead:
    _load_material(db, material_id)
    get_location(db, payload.location_id)
    row = _get_or_create_material_stock(db, material_id, payload.location_id)
    row.quantity = _q(payload.quantity)
    db.commit()
    return material_read(_load_material(db, material_id))


def delta_material_stock(db: Session, material_id: int, payload: StockDeltaRequest) -> MaterialRead:
    _load_material(db, material_id)
    get_location(db, payload.location_id)
    row = _get_or_create_material_stock(db, material_id, payload.location_id)
    row.quantity = _q(Decimal(row.quantity) + Decimal(payload.delta))
    db.commit()
    return material_read(_load_material(db, material_id))


def transfer_material(db: Session, material_id: int, payload: TransferRequest) -> MaterialRead:
    if payload.from_location_id == payload.to_location_id:
        raise HTTPException(status_code=400, detail="Quell- und Zielstandort müssen unterschiedlich sein")
    _load_material(db, material_id)
    from_loc = get_location(db, payload.from_location_id)
    to_loc = get_location(db, payload.to_location_id)
    qty = _q(payload.quantity)
    source = _get_or_create_material_stock(db, material_id, payload.from_location_id)
    target = _get_or_create_material_stock(db, material_id, payload.to_location_id)
    source.quantity = _q(Decimal(source.quantity) - qty)
    target.quantity = _q(Decimal(target.quantity) + qty)
    _maybe_record_transfer(
        db,
        from_loc=from_loc,
        to_loc=to_loc,
        quantity=qty,
        material_id=material_id,
        note=payload.note,
    )
    db.commit()
    return material_read(_load_material(db, material_id))


def _load_product(db: Session, product_id: int) -> Product:
    product = db.scalars(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.materials).selectinload(ProductMaterial.material),
            selectinload(Product.materials).selectinload(ProductMaterial.component_product).selectinload(
                Product.materials
            ).selectinload(ProductMaterial.material),
            selectinload(Product.materials)
            .selectinload(ProductMaterial.component_product)
            .selectinload(Product.materials)
            .selectinload(ProductMaterial.component_product),
            selectinload(Product.stocks).selectinload(ProductStock.location),
            selectinload(Product.color).selectinload(Color.medium),
            selectinload(Product.tags),
            selectinload(Product.transform_target),
        )
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produkt nicht gefunden")
    return product


def list_products(
    db: Session,
    tag: str | None = None,
    color_id: int | None = None,
    medium_id: int | None = None,
) -> list[ProductRead]:
    stmt = (
        select(Product)
        .order_by(Product.updated_at.desc(), Product.name)
        .options(
            selectinload(Product.materials).selectinload(ProductMaterial.material),
            selectinload(Product.materials).selectinload(ProductMaterial.component_product).selectinload(
                Product.materials
            ).selectinload(ProductMaterial.material),
            selectinload(Product.stocks).selectinload(ProductStock.location),
            selectinload(Product.color).selectinload(Color.medium),
            selectinload(Product.tags),
            selectinload(Product.transform_target),
        )
    )
    if tag:
        stmt = stmt.join(Product.tags).where(Tag.name == tag)
    if color_id is not None:
        stmt = stmt.where(Product.color_id == color_id)
    if medium_id is not None:
        stmt = stmt.join(Product.color).where(Color.medium_id == medium_id)
    rows = db.scalars(stmt).unique().all()
    return [product_read(row) for row in rows]


def create_product(db: Session, payload: ProductCreate) -> ProductRead:
    location = get_location(db, payload.location_id) if payload.location_id else default_location(db)
    color = get_color(db, payload.color_id)
    product = Product(
        name=payload.name.strip(),
        sku=payload.sku,
        min_stock=_q(payload.min_stock) if payload.min_stock is not None else None,
        is_template=bool(payload.is_template),
        is_on_demand=bool(getattr(payload, "is_on_demand", False)),
        family=(payload.family.strip() if payload.family else None),
        color_id=color.id if color else None,
        transform_target_id=None,
    )
    product.tags = resolve_tags(db, payload.tag_ids)
    db.add(product)
    try:
        db.flush()
        product.transform_target_id = _resolve_transform_target(db, product.id, payload.transform_target_id)
        db.add(
            ProductStock(
                product_id=product.id,
                location_id=location.id,
                quantity=_q(payload.stock_quantity),
            )
        )
        sync_incomplete_tags(db, product, before_missing=[])
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        msg = str(getattr(exc, "orig", exc)).lower()
        if "unique" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Produktname oder SKU „{payload.name.strip()}“ / „{payload.sku or '—'}“ bereits vergeben",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Produkt konnte nicht gespeichert werden: {exc.orig}",
        ) from exc
    return product_read(_load_product(db, product.id))


def _material_for_target_color(db: Session, source_material: Material, target_color_id: int) -> Material | None:
    """Keep colorless materials; remap colored BOM lines to a material with the target color."""
    if source_material.color_id is None:
        return source_material
    if source_material.color_id == target_color_id:
        return source_material
    return db.scalars(
        select(Material)
        .where(Material.color_id == target_color_id)
        .order_by(Material.id)
        .limit(1)
    ).first()


def _product_for_target_color(db: Session, source: Product, target_color_id: int) -> Product | None:
    """Remap a BOM component product to the same series name with the target color."""
    if source.color_id is None:
        return source
    if source.color_id == target_color_id:
        return source
    target_color = get_color(db, target_color_id)
    source_color = source.color or get_color(db, source.color_id)
    if not target_color or not source_color:
        return None
    name = source.name
    for sep in (f" - {source_color.name}", f" {source_color.name}"):
        if name.endswith(sep):
            base = name[: -len(sep)]
            for new_sep in (f" - {target_color.name}", f" {target_color.name}"):
                candidate = f"{base}{new_sep}"
                found = db.scalars(select(Product).where(Product.name == candidate).limit(1)).first()
                if found:
                    return found
    if source.family:
        matches = list(
            db.scalars(
                select(Product).where(
                    Product.family == source.family,
                    Product.color_id == target_color_id,
                )
            ).all()
        )
        if len(matches) == 1:
            return matches[0]
    return None


def _bom_would_cycle(db: Session, parent_id: int, component_product_id: int) -> bool:
    """True if adding component_product_id under parent_id would create a cycle."""
    if component_product_id == parent_id:
        return True
    stack = [component_product_id]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if current == parent_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        child_ids = db.scalars(
            select(ProductMaterial.component_product_id).where(
                ProductMaterial.product_id == current,
                ProductMaterial.component_product_id.is_not(None),
            )
        ).all()
        stack.extend(int(cid) for cid in child_ids if cid is not None)
    return False


def create_products_from_colors(db: Session, payload: ProductsFromColorsRequest) -> ProductsFromColorsResult:
    from app.schemas import BulkSkipInfo

    base = payload.base_name.strip()
    created_ids: list[int] = []
    skipped: list[BulkSkipInfo] = []
    warnings: list[str] = []
    location = get_location(db, payload.location_id) if payload.location_id else default_location(db)
    dialog_tags = resolve_tags(db, payload.tag_ids)
    used_names: set[str] = set()

    template_lines: list[ProductMaterial] = []
    template_min_stock: Decimal | None = None
    template_tags: list[Tag] = []
    if payload.template_product_id is not None:
        template = _load_product(db, payload.template_product_id)
        template_lines = list(template.materials)
        template_min_stock = template.min_stock
        template_tags = list(template.tags)

    tags = merge_tags(template_tags, dialog_tags)

    if payload.min_stock is not None:
        series_min_stock: Decimal | None = _q(payload.min_stock)
    else:
        series_min_stock = _q(template_min_stock) if template_min_stock is not None else None

    seen: set[int] = set()
    for color_id in payload.color_ids:
        if color_id in seen:
            continue
        seen.add(color_id)
        color = get_color(db, color_id)
        if not color:
            skipped.append(BulkSkipInfo(color_id=color_id, color_name="?", reason="Farbe nicht gefunden"))
            continue
        name = f"{base} {color.name}".strip()
        if name in used_names or db.scalars(select(Product.id).where(Product.name == name).limit(1)).first():
            skipped.append(
                BulkSkipInfo(
                    color_id=color_id,
                    color_name=color.name,
                    reason=f"Produktname „{name}“ bereits vergeben",
                )
            )
            continue

        product = Product(
            name=name,
            sku=None,
            color_id=color.id,
            min_stock=series_min_stock,
            family=base,
            is_on_demand=bool(payload.is_on_demand),
        )
        product.tags = list(tags)
        db.add(product)
        db.flush()
        db.add(
            ProductStock(
                product_id=product.id,
                location_id=location.id,
                quantity=_q(payload.stock_quantity),
            )
        )

        used_material_ids: set[int] = set()
        used_component_ids: set[int] = set()
        for line in template_lines:
            if line.material_id is not None:
                source_mat = line.material
                if source_mat is None:
                    source_mat = db.get(Material, line.material_id)
                if source_mat is None:
                    continue
                if source_mat.color_id is not None and source_mat.color is None:
                    source_mat = _load_material(db, source_mat.id)
                target_mat = _material_for_target_color(db, source_mat, color.id)
                if target_mat is None:
                    warnings.append(
                        f"Produkt „{name}“: Stückliste ohne „{source_mat.name}“ "
                        f"(kein Material mit Farbe {color.name})."
                    )
                    continue
                if target_mat.id in used_material_ids:
                    warnings.append(
                        f"Produkt „{name}“: doppelte Stücklistenzeile für „{target_mat.name}“ übersprungen."
                    )
                    continue
                used_material_ids.add(target_mat.id)
                db.add(
                    ProductMaterial(
                        product_id=product.id,
                        material_id=target_mat.id,
                        component_product_id=None,
                        quantity_required=_q(line.quantity_required),
                    )
                )
                continue

            source_comp = line.component_product
            if source_comp is None and line.component_product_id is not None:
                source_comp = db.get(Product, line.component_product_id)
            if source_comp is None:
                continue
            if source_comp.color_id is not None and source_comp.color is None:
                source_comp = _load_product(db, source_comp.id)
            target_comp = _product_for_target_color(db, source_comp, color.id)
            if target_comp is None:
                warnings.append(
                    f"Produkt „{name}“: Stückliste ohne „{source_comp.name}“ "
                    f"(kein Produkt mit Farbe {color.name})."
                )
                continue
            if target_comp.id in used_component_ids or target_comp.id == product.id:
                warnings.append(
                    f"Produkt „{name}“: doppelte/ungültige Stücklistenzeile für „{target_comp.name}“ übersprungen."
                )
                continue
            used_component_ids.add(target_comp.id)
            db.add(
                ProductMaterial(
                    product_id=product.id,
                    material_id=None,
                    component_product_id=target_comp.id,
                    quantity_required=_q(line.quantity_required),
                )
            )

        created_ids.append(product.id)
        used_names.add(name)

    for pid in created_ids:
        product = _load_product(db, pid)
        sync_incomplete_tags(db, product, before_missing=[])
    db.commit()
    created = [product_read(_load_product(db, pid)) for pid in created_ids]
    return ProductsFromColorsResult(created=created, skipped=skipped, warnings=warnings)


def update_product(db: Session, product_id: int, payload: ProductUpdate) -> ProductRead:
    product = _load_product(db, product_id)
    before_missing = product_incomplete_fields_raw(product)
    data = payload.model_dump(exclude_unset=True)
    tag_ids = data.pop("tag_ids", None)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    if "family" in data and data["family"] is not None:
        data["family"] = data["family"].strip() or None
    if "min_stock" in data:
        data["min_stock"] = _q(data["min_stock"]) if data["min_stock"] is not None else None
    if "color_id" in data:
        color = get_color(db, data["color_id"])
        data["color_id"] = color.id if color else None
    if "transform_target_id" in data:
        data["transform_target_id"] = _resolve_transform_target(db, product.id, data["transform_target_id"])
    for key, value in data.items():
        setattr(product, key, value)
    if tag_ids is not None:
        product.tags = resolve_tags(db, tag_ids)
    sync_incomplete_tags(db, product, before_missing=before_missing)
    _stamp_update(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Produktname oder SKU bereits vergeben",
        ) from exc
    return product_read(_load_product(db, product.id))


def bulk_update_materials(db: Session, payload: "MaterialBulkUpdate") -> list[MaterialRead]:
    from app.schemas import MaterialBulkUpdate

    if not isinstance(payload, MaterialBulkUpdate):
        payload = MaterialBulkUpdate.model_validate(payload)
    tags = resolve_tags(db, payload.tag_ids) if payload.tag_ids is not None else None
    family = payload.family.strip() if payload.family else None
    result_ids: list[int] = []
    for mid in payload.ids:
        material = _load_material(db, mid)
        before_missing = material_incomplete_fields_raw(material)
        if payload.clear_min_stock:
            material.min_stock = None
        elif payload.min_stock is not None:
            material.min_stock = _q(payload.min_stock)
        if payload.clear_family:
            material.family = None
        elif payload.family is not None:
            material.family = family
        if payload.is_template is not None:
            material.is_template = bool(payload.is_template)
        if tags is not None:
            material.tags = list(tags)
        sync_incomplete_tags(db, material, before_missing=before_missing)
        _stamp_update(material)
        result_ids.append(material.id)
    db.commit()
    return [material_read(_load_material(db, mid)) for mid in result_ids]


def bulk_update_products(db: Session, payload: "ProductBulkUpdate") -> list[ProductRead]:
    from app.schemas import ProductBulkUpdate

    if not isinstance(payload, ProductBulkUpdate):
        payload = ProductBulkUpdate.model_validate(payload)
    tags = resolve_tags(db, payload.tag_ids) if payload.tag_ids is not None else None
    family = payload.family.strip() if payload.family else None
    result_ids: list[int] = []
    for pid in payload.ids:
        product = _load_product(db, pid)
        before_missing = product_incomplete_fields_raw(product)
        if payload.clear_min_stock:
            product.min_stock = None
        elif payload.min_stock is not None:
            product.min_stock = _q(payload.min_stock)
        if payload.clear_family:
            product.family = None
        elif payload.family is not None:
            product.family = family
        if payload.is_template is not None:
            product.is_template = bool(payload.is_template)
        if tags is not None:
            product.tags = list(tags)
        sync_incomplete_tags(db, product, before_missing=before_missing)
        _stamp_update(product)
        result_ids.append(product.id)
    db.commit()
    return [product_read(_load_product(db, pid)) for pid in result_ids]


def suggest_by_color(
    db: Session,
    color_id: int,
    include_materials: bool = True,
    include_products: bool = True,
) -> list[ColorMatchSuggestion]:
    color = get_color(db, color_id)
    assert color is not None
    suggestions: list[ColorMatchSuggestion] = []
    if include_materials:
        mats = db.scalars(
            select(Material)
            .where(Material.color_id == color_id)
            .options(
                selectinload(Material.stocks).selectinload(MaterialStock.location),
                selectinload(Material.color),
            )
        ).all()
        for m in mats:
            suggestions.append(
                ColorMatchSuggestion(
                    kind="material",
                    id=m.id,
                    name=m.name,
                    color_id=color.id,
                    color_label=f"{color.name} ({color.medium.name})",
                    stock_total=_material_stock_total(m),
                )
            )
    if include_products:
        prods = db.scalars(
            select(Product)
            .where(Product.color_id == color_id)
            .options(
                selectinload(Product.stocks).selectinload(ProductStock.location),
                selectinload(Product.color),
            )
        ).all()
        for p in prods:
            suggestions.append(
                ColorMatchSuggestion(
                    kind="product",
                    id=p.id,
                    name=p.name,
                    color_id=color.id,
                    color_label=f"{color.name} ({color.medium.name})",
                    stock_total=_product_stock_total(p),
                )
            )
    return suggestions


def suggest_for_option_value(db: Session, option_value: str) -> list[ColorMatchSuggestion]:
    """Match option value text to color name (same spelling), any medium — caller filters medium if needed."""
    value = option_value.strip()
    if not value:
        return []
    colors = db.scalars(select(Color).where(Color.name == value)).all()
    # loose match
    if not colors:
        colors = [c for c in db.scalars(select(Color)).all() if c.name.casefold() == value.casefold()]
    out: list[ColorMatchSuggestion] = []
    for color in colors:
        out.extend(suggest_by_color(db, color.id, include_materials=True, include_products=True))
    return out


def delete_product(db: Session, product_id: int) -> None:
    product = _load_product(db, product_id)
    err = _delete_product_row(db, product)
    if err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err)
    db.commit()


def _delete_product_row(db: Session, product: Product) -> str | None:
    """Remove product in-session. Returns error reason or None. Caller commits."""
    used_as_component = db.scalars(
        select(ProductMaterial.id).where(ProductMaterial.component_product_id == product.id).limit(1)
    ).first()
    if used_as_component is not None:
        return "Produkt ist in einer Produkt-Stückliste verknüpft und kann nicht gelöscht werden"
    for mapping in db.scalars(select(OptionMapping).where(OptionMapping.product_id == product.id)).all():
        db.delete(mapping)
    for line in db.scalars(select(SetBomLine).where(SetBomLine.product_id == product.id)).all():
        db.delete(line)
    db.flush()
    db.delete(product)
    return None


def bulk_delete_products(db: Session, payload: "BulkDeleteRequest") -> "BulkDeleteResult":
    from app.schemas import BulkDeleteRequest, BulkDeleteResult, BulkDeleteSkip

    if not isinstance(payload, BulkDeleteRequest):
        payload = BulkDeleteRequest.model_validate(payload)
    deleted_ids: list[int] = []
    skipped: list[BulkDeleteSkip] = []
    seen: set[int] = set()
    for pid in payload.ids:
        if pid in seen:
            continue
        seen.add(pid)
        product = db.get(Product, pid)
        if not product:
            skipped.append(BulkDeleteSkip(id=pid, name="?", reason="nicht gefunden"))
            continue
        name = product.name
        err = _delete_product_row(db, product)
        if err:
            skipped.append(BulkDeleteSkip(id=pid, name=name, reason=err))
            continue
        deleted_ids.append(pid)
    db.commit()
    return BulkDeleteResult(deleted_ids=deleted_ids, skipped=skipped)


def adjust_product_stock(db: Session, product_id: int, payload: StockAdjustRequest) -> ProductRead:
    _load_product(db, product_id)
    get_location(db, payload.location_id)
    row = _get_or_create_product_stock(db, product_id, payload.location_id)
    row.quantity = _q(payload.quantity)
    db.commit()
    return product_read(_load_product(db, product_id))


def delta_product_stock(db: Session, product_id: int, payload: StockDeltaRequest) -> ProductRead:
    _load_product(db, product_id)
    get_location(db, payload.location_id)
    row = _get_or_create_product_stock(db, product_id, payload.location_id)
    row.quantity = _q(Decimal(row.quantity) + Decimal(payload.delta))
    db.commit()
    return product_read(_load_product(db, product_id))


def transfer_product(db: Session, product_id: int, payload: TransferRequest) -> ProductRead:
    if payload.from_location_id == payload.to_location_id:
        raise HTTPException(status_code=400, detail="Quell- und Zielstandort müssen unterschiedlich sein")
    _load_product(db, product_id)
    from_loc = get_location(db, payload.from_location_id)
    to_loc = get_location(db, payload.to_location_id)
    qty = _q(payload.quantity)
    source = _get_or_create_product_stock(db, product_id, payload.from_location_id)
    target = _get_or_create_product_stock(db, product_id, payload.to_location_id)
    source.quantity = _q(Decimal(source.quantity) - qty)
    target.quantity = _q(Decimal(target.quantity) + qty)
    _maybe_record_transfer(
        db,
        from_loc=from_loc,
        to_loc=to_loc,
        quantity=qty,
        product_id=product_id,
        note=payload.note,
    )
    db.commit()
    return product_read(_load_product(db, product_id))


def transform_product(
    db: Session,
    product_id: int,
    payload: TransformRequest,
    *,
    actor: str | None = None,
) -> ProductRead:
    source = _load_product(db, product_id)
    if not product_name_allows_transform(source.name):
        raise HTTPException(
            status_code=400,
            detail="Umwandlung nur für Produkte mit „Uni“ im Namen",
        )
    if not source.transform_target_id:
        raise HTTPException(
            status_code=400,
            detail="Kein Zielprodukt verknüpft — unter Bearbeiten „Wird zu“ setzen",
        )
    if source.transform_target_id == source.id:
        raise HTTPException(status_code=400, detail="Zielprodukt darf nicht dasselbe Produkt sein")
    location = get_location(db, payload.location_id)
    qty = _q(payload.quantity)
    source_stock = _get_or_create_product_stock(db, source.id, location.id)
    target_stock = _get_or_create_product_stock(db, source.transform_target_id, location.id)
    source_stock.quantity = _q(Decimal(source_stock.quantity) - qty)
    target_stock.quantity = _q(Decimal(target_stock.quantity) + qty)
    _record_movement(
        db,
        kind=StockMovementKind.TRANSFORM,
        quantity=qty,
        from_location_id=location.id,
        to_location_id=location.id,
        product_id=source.id,
        to_product_id=source.transform_target_id,
        note=payload.note,
        created_by=actor,
    )
    _stamp_update(source)
    target = db.get(Product, source.transform_target_id)
    if target:
        _stamp_update(target)
    db.commit()
    return product_read(_load_product(db, product_id))


def add_bom_line(db: Session, product_id: int, payload: BomLineCreate) -> ProductRead:
    product = _load_product(db, product_id)
    before_missing = product_incomplete_fields_raw(product)
    if payload.material_id is not None:
        _load_material(db, payload.material_id)
        line = ProductMaterial(
            product_id=product.id,
            material_id=payload.material_id,
            component_product_id=None,
            quantity_required=_q(payload.quantity_required),
        )
    else:
        assert payload.product_id is not None
        if _bom_would_cycle(db, product.id, payload.product_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stückliste würde einen Zyklus erzeugen (Produkt enthält sich selbst).",
            )
        _load_product(db, payload.product_id)
        line = ProductMaterial(
            product_id=product.id,
            material_id=None,
            component_product_id=payload.product_id,
            quantity_required=_q(payload.quantity_required),
        )
    db.add(line)
    db.flush()
    db.expire(product, ["materials"])
    product = _load_product(db, product_id)
    sync_incomplete_tags(db, product, before_missing=before_missing)
    _stamp_update(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Komponente ist bereits in der Stückliste",
        ) from exc
    return product_read(_load_product(db, product.id))


def update_bom_line(db: Session, product_id: int, line_id: int, payload: BomLineUpdate) -> ProductRead:
    product = _load_product(db, product_id)
    line = next((item for item in product.materials if item.id == line_id), None)
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stücklistenzeile nicht gefunden")
    line.quantity_required = _q(payload.quantity_required)
    _stamp_update(product)
    db.commit()
    return product_read(_load_product(db, product.id))


def delete_bom_line(db: Session, product_id: int, line_id: int) -> ProductRead:
    product = _load_product(db, product_id)
    before_missing = product_incomplete_fields_raw(product)
    line = next((item for item in product.materials if item.id == line_id), None)
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stücklistenzeile nicht gefunden")
    db.delete(line)
    db.flush()
    # Refresh materials collection after delete for incomplete check
    db.expire(product, ["materials"])
    product = _load_product(db, product_id)
    sync_incomplete_tags(db, product, before_missing=before_missing)
    _stamp_update(product)
    db.commit()
    return product_read(_load_product(db, product.id))


def manufacture(db: Session, product_id: int, quantity: Decimal, location_id: int | None) -> ManufactureResult:
    product = _load_product(db, product_id)
    location = get_location(db, location_id) if location_id else default_location(db)
    qty = _q(quantity)
    warnings: list[str] = []

    product_stock = _get_or_create_product_stock(db, product.id, location.id)
    product_stock.quantity = _q(Decimal(product_stock.quantity) + qty)

    for line in product.materials:
        needed = _q(qty * Decimal(line.quantity_required))
        if line.material_id is not None:
            mat_stock = _get_or_create_material_stock(db, line.material_id, location.id)
            new_stock = _q(Decimal(mat_stock.quantity) - needed)
            mat_name = line.material.name if line.material else f"#{line.material_id}"
            unit = line.material.unit.value if line.material else ""
            if new_stock < 0:
                warnings.append(
                    f"Material „{mat_name}“ an {location.name} wird negativ "
                    f"(Bestand {new_stock} {unit} nach Abbuchung von {needed})."
                )
            mat_stock.quantity = new_stock
        elif line.component_product_id is not None:
            comp_stock = _get_or_create_product_stock(db, line.component_product_id, location.id)
            new_stock = _q(Decimal(comp_stock.quantity) - needed)
            comp_name = (
                line.component_product.name
                if line.component_product
                else f"#{line.component_product_id}"
            )
            if new_stock < 0:
                warnings.append(
                    f"Produkt „{comp_name}“ an {location.name} wird negativ "
                    f"(Bestand {new_stock} nach Abbuchung von {needed})."
                )
            comp_stock.quantity = new_stock

    db.commit()
    refreshed = _load_product(db, product.id)
    if _product_stock_total(refreshed) < 0:
        warnings.append(f"Produkt „{product.name}“ hat negativen Gesamtbestand.")
    return ManufactureResult(product=product_read(refreshed), warnings=warnings)


def _variant_label(variant: SetVariant) -> str:
    parts = [v for v in (variant.option1_value, variant.option2_value, variant.option3_value) if v]
    return " / ".join(parts) if parts else f"Variante #{variant.id}"


def _component_stock_total(db: Session, material_id: int | None, product_id: int | None) -> Decimal:
    if material_id is not None:
        return _material_stock_available(_load_material(db, material_id))
    if product_id is not None:
        return _product_stock_available(_load_product(db, product_id))
    return Decimal("0")


def _component_name(db: Session, material_id: int | None, product_id: int | None) -> tuple[str, str]:
    if material_id is not None:
        material = _load_material(db, material_id)
        return material.name, "material"
    product = _load_product(db, product_id)  # type: ignore[arg-type]
    return product.name, "product"


def _buildable_from_qty(stock: Decimal, required: Decimal) -> int:
    if required <= 0:
        return 0
    return max(0, floor(float(stock / required)))


def set_bom_line_read(db: Session, line: SetBomLine) -> SetBomLineRead:
    name, kind = _component_name(db, line.material_id, line.product_id)
    stock = _component_stock_total(db, line.material_id, line.product_id)
    return SetBomLineRead(
        id=line.id,
        material_id=line.material_id,
        product_id=line.product_id,
        component_name=name,
        component_kind=kind,
        quantity_required=line.quantity_required,
        is_manual=line.is_manual,
        stock_total=stock,
        buildable_from_line=_buildable_from_qty(stock, Decimal(line.quantity_required)),
    )


def variant_buildable_quantity(db: Session, product_set: ProductSet, variant: SetVariant) -> int:
    if not variant.bom_lines:
        return 0
    quantities: list[int] = []
    for line in variant.bom_lines:
        if line.material_id is not None and not product_set.count_materials_in_buildability:
            continue
        stock = _component_stock_total(db, line.material_id, line.product_id)
        quantities.append(_buildable_from_qty(stock, Decimal(line.quantity_required)))
    return min(quantities) if quantities else 0


def variant_read(db: Session, product_set: ProductSet, variant: SetVariant) -> SetVariantRead:
    return SetVariantRead(
        id=variant.id,
        option1_name=variant.option1_name,
        option1_value=variant.option1_value,
        option2_name=variant.option2_name,
        option2_value=variant.option2_value,
        option3_name=variant.option3_name,
        option3_value=variant.option3_value,
        label=_variant_label(variant),
        buildable_quantity=variant_buildable_quantity(db, product_set, variant),
        bom=[set_bom_line_read(db, line) for line in variant.bom_lines],
    )


def option_mapping_read(db: Session, mapping: OptionMapping) -> OptionMappingRead:
    name, kind = _component_name(db, mapping.material_id, mapping.product_id)
    return OptionMappingRead(
        id=mapping.id,
        option_name=mapping.option_name,
        option_value=mapping.option_value,
        material_id=mapping.material_id,
        product_id=mapping.product_id,
        component_name=name,
        component_kind=kind,
        quantity_required=mapping.quantity_required,
    )


def _load_set(db: Session, set_id: int) -> ProductSet:
    product_set = db.scalars(
        select(ProductSet)
        .where(ProductSet.id == set_id)
        .options(
            selectinload(ProductSet.variants).selectinload(SetVariant.bom_lines),
            selectinload(ProductSet.option_mappings),
        )
    ).first()
    if not product_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Set nicht gefunden")
    return product_set


def product_set_read(
    db: Session,
    product_set: ProductSet,
    include_variants: bool = True,
    include_mappings: bool = True,
) -> ProductSetRead:
    variants = (
        [variant_read(db, product_set, variant) for variant in product_set.variants] if include_variants else []
    )
    mappings = (
        [option_mapping_read(db, m) for m in product_set.option_mappings] if include_mappings else []
    )
    return ProductSetRead(
        id=product_set.id,
        name=product_set.name,
        handle=product_set.handle,
        count_materials_in_buildability=product_set.count_materials_in_buildability,
        variant_count=len(product_set.variants),
        mapping_count=len(product_set.option_mappings),
        variants=variants,
        option_mappings=mappings,
    )


def list_sets(db: Session) -> list[ProductSetRead]:
    rows = db.scalars(
        select(ProductSet)
        .order_by(ProductSet.name)
        .options(
            selectinload(ProductSet.variants),
            selectinload(ProductSet.option_mappings),
        )
    ).all()
    return [product_set_read(db, row, include_variants=False, include_mappings=False) for row in rows]


def create_set(db: Session, payload: ProductSetCreate) -> ProductSetRead:
    product_set = ProductSet(
        name=payload.name.strip(),
        handle=payload.handle.strip(),
        count_materials_in_buildability=payload.count_materials_in_buildability,
    )
    db.add(product_set)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Set-Handle bereits vergeben") from exc
    return product_set_read(db, _load_set(db, product_set.id))


def update_set(db: Session, set_id: int, payload: ProductSetUpdate) -> ProductSetRead:
    product_set = _load_set(db, set_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    for key, value in data.items():
        setattr(product_set, key, value)
    db.commit()
    return product_set_read(db, _load_set(db, set_id))


def delete_set(db: Session, set_id: int) -> None:
    product_set = _load_set(db, set_id)
    db.delete(product_set)
    db.commit()


def add_option_mapping(db: Session, set_id: int, payload: OptionMappingCreate) -> ProductSetRead:
    _load_set(db, set_id)
    if payload.material_id is not None:
        _load_material(db, payload.material_id)
    if payload.product_id is not None:
        _load_product(db, payload.product_id)
    mapping = OptionMapping(
        set_id=set_id,
        option_name=payload.option_name.strip(),
        option_value=payload.option_value.strip(),
        material_id=payload.material_id,
        product_id=payload.product_id,
        quantity_required=_q(payload.quantity_required),
    )
    db.add(mapping)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mapping für diese Option existiert bereits") from exc
    return product_set_read(db, _load_set(db, set_id))


def delete_option_mapping(db: Session, set_id: int, mapping_id: int) -> ProductSetRead:
    product_set = _load_set(db, set_id)
    mapping = next((m for m in product_set.option_mappings if m.id == mapping_id), None)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping nicht gefunden")
    option_name = mapping.option_name
    option_value = mapping.option_value
    material_id = mapping.material_id
    product_id = mapping.product_id
    db.delete(mapping)
    db.flush()
    # Angewendete (nicht manuelle) BOM-Zeilen für dieselbe Option entfernen
    for variant in product_set.variants:
        pairs = [
            (variant.option1_name, variant.option1_value),
            (variant.option2_name, variant.option2_value),
            (variant.option3_name, variant.option3_value),
        ]
        if (option_name, option_value) not in pairs:
            continue
        for line in list(variant.bom_lines):
            if line.is_manual:
                continue
            if material_id and line.material_id == material_id:
                db.delete(line)
            elif product_id and line.product_id == product_id:
                db.delete(line)
    db.commit()
    return product_set_read(db, _load_set(db, set_id))


def detach_set_component(
    db: Session,
    set_id: int,
    *,
    material_id: int | None = None,
    product_id: int | None = None,
) -> ProductSetRead:
    """Remove a warehouse component from option mappings and all variant BOM lines."""
    if (material_id is None) == (product_id is None):
        raise HTTPException(status_code=400, detail="Genau material_id oder product_id angeben")
    product_set = _load_set(db, set_id)
    if material_id is not None:
        for mapping in list(product_set.option_mappings):
            if mapping.material_id == material_id:
                db.delete(mapping)
        for variant in product_set.variants:
            for line in list(variant.bom_lines):
                if line.material_id == material_id:
                    db.delete(line)
    else:
        for mapping in list(product_set.option_mappings):
            if mapping.product_id == product_id:
                db.delete(mapping)
        for variant in product_set.variants:
            for line in list(variant.bom_lines):
                if line.product_id == product_id:
                    db.delete(line)
    db.commit()
    return product_set_read(db, _load_set(db, set_id))


def apply_option_mappings(db: Session, set_id: int) -> ProductSetRead:
    product_set = _load_set(db, set_id)
    mapping_index = {(m.option_name, m.option_value): m for m in product_set.option_mappings}

    for variant in product_set.variants:
        for line in list(variant.bom_lines):
            if not line.is_manual:
                db.delete(line)
        db.flush()

        option_pairs = [
            (variant.option1_name, variant.option1_value),
            (variant.option2_name, variant.option2_value),
            (variant.option3_name, variant.option3_value),
        ]
        for name, value in option_pairs:
            if not name or not value:
                continue
            mapping = mapping_index.get((name, value))
            if not mapping:
                continue
            db.add(
                SetBomLine(
                    variant_id=variant.id,
                    material_id=mapping.material_id,
                    product_id=mapping.product_id,
                    quantity_required=mapping.quantity_required,
                    is_manual=False,
                )
            )
    db.commit()
    return product_set_read(db, _load_set(db, set_id))


def add_variant_bom_line(db: Session, set_id: int, variant_id: int, payload: SetBomLineCreate) -> ProductSetRead:
    product_set = _load_set(db, set_id)
    variant = next((v for v in product_set.variants if v.id == variant_id), None)
    if not variant:
        raise HTTPException(status_code=404, detail="Variante nicht gefunden")
    if payload.material_id is not None:
        _load_material(db, payload.material_id)
    if payload.product_id is not None:
        _load_product(db, payload.product_id)
    db.add(
        SetBomLine(
            variant_id=variant.id,
            material_id=payload.material_id,
            product_id=payload.product_id,
            quantity_required=_q(payload.quantity_required),
            is_manual=True,
        )
    )
    db.commit()
    return product_set_read(db, _load_set(db, set_id))


def delete_variant_bom_line(db: Session, set_id: int, variant_id: int, line_id: int) -> ProductSetRead:
    product_set = _load_set(db, set_id)
    variant = next((v for v in product_set.variants if v.id == variant_id), None)
    if not variant:
        raise HTTPException(status_code=404, detail="Variante nicht gefunden")
    line = next((item for item in variant.bom_lines if item.id == line_id), None)
    if not line:
        raise HTTPException(status_code=404, detail="Stücklistenzeile nicht gefunden")
    db.delete(line)
    db.commit()
    return product_set_read(db, _load_set(db, set_id))


def import_shopify_inventory_csv(db: Session, content: str) -> ShopifyInventoryImportResult:
    """Legacy: import *all* catalog handles as sets. Prefer preview + apply."""
    from app.shopify_csv import parse_shopify_catalog_csv

    try:
        usable = parse_shopify_catalog_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not usable:
        raise HTTPException(
            status_code=400,
            detail="Keine Varianten im Export gefunden (nur Default-Title oder leere Optionen)",
        )

    result = _upsert_sets_from_catalog(db, usable, handles=list(usable.keys()))
    db.commit()
    first = result["set_ids"][0] if result["set_ids"] else None
    return ShopifyInventoryImportResult(
        set_id=first,
        created_set=result["sets_created"] > 0,
        variants_upserted=result["variants_upserted"],
        sets_touched=result["sets_touched"],
        sets_created=result["sets_created"],
        message=result["message"],
    )


def _upsert_sets_from_catalog(
    db: Session,
    usable: dict[str, dict],
    *,
    handles: list[str],
) -> dict:
    total_upserted = 0
    sets_created = 0
    set_ids: list[int] = []
    summaries: list[str] = []

    for handle in handles:
        data = usable.get(handle)
        if not data:
            continue
        variants = data["variants"]
        title = data["title"] or handle
        existing = db.scalars(select(ProductSet).where(ProductSet.handle == handle)).first()
        created = False
        if not existing:
            existing = ProductSet(
                name=title,
                handle=handle,
                count_materials_in_buildability=True,
            )
            db.add(existing)
            db.flush()
            created = True
            sets_created += 1
        else:
            existing.name = title or existing.name

        set_ids.append(existing.id)
        product_set = _load_set(db, existing.id)
        existing_keys = {
            (v.option1_value, v.option2_value, v.option3_value): v for v in product_set.variants
        }
        upserted = 0
        for key, variant_data in variants.items():
            if key in existing_keys:
                continue
            db.add(SetVariant(set_id=existing.id, **variant_data))
            upserted += 1
        total_upserted += upserted
        summaries.append(
            f"„{existing.name}“: +{upserted} Varianten ({len(variants)} im File)"
            + (" [neu]" if created else "")
        )

    touched = len(set_ids)
    if touched == 0:
        message = "Keine Sets angelegt."
    elif touched == 1:
        message = summaries[0] + "."
    else:
        message = (
            f"{touched} Sets ({sets_created} neu), {total_upserted} neue Varianten. "
            + "; ".join(summaries[:5])
            + (" …" if len(summaries) > 5 else "")
        )
    return {
        "sets_created": sets_created,
        "sets_touched": touched,
        "variants_upserted": total_upserted,
        "set_ids": set_ids,
        "message": message,
    }


def preview_shopify_catalog_csv(db: Session, content: str) -> "ShopifyPreviewResult":
    from app.models import ShopifyIgnoredHandle
    from app.schemas import ShopifyHandlePreview, ShopifyPreviewResult
    from app.shopify_csv import parse_shopify_catalog_csv

    try:
        usable = parse_shopify_catalog_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ignored_rows = db.scalars(select(ShopifyIgnoredHandle)).all()
    ignored_map = {r.handle: r for r in ignored_rows}
    existing_sets = {
        s.handle: s.id for s in db.scalars(select(ProductSet)).all()
    }

    handles: list[ShopifyHandlePreview] = []
    for handle, data in sorted(usable.items(), key=lambda x: x[1]["title"].lower()):
        axes = list(data["option_values"].keys())
        handles.append(
            ShopifyHandlePreview(
                handle=handle,
                title=data["title"] or handle,
                variant_count=len(data["variants"]),
                option_axes=axes,
                option_values=data["option_values"],
                ignored=handle in ignored_map,
                existing_set_id=existing_sets.get(handle),
            )
        )
    return ShopifyPreviewResult(handles=handles, ignored_total=len(ignored_map))


def apply_shopify_catalog_csv(db: Session, content: str, payload: "ShopifyApplyRequest") -> "ShopifyApplyResult":
    from app.models import ShopifyIgnoredHandle, ShopifyImportQueueItem
    from app.schemas import (
        ShopifyApplyRequest,
        ShopifyApplyResult,
        ShopifySeriesJob,
    )
    from app.shopify_csv import parse_shopify_catalog_csv

    if not isinstance(payload, ShopifyApplyRequest):
        payload = ShopifyApplyRequest.model_validate(payload)

    try:
        usable = parse_shopify_catalog_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    set_handles: list[str] = []
    ignored_added = 0
    series_jobs: list[ShopifySeriesJob] = []
    queue_upserted = 0
    now = _utcnow()

    for item in payload.items:
        handle = item.handle.strip()
        data = usable.get(handle)
        if item.action == "skip":
            continue
        if item.action == "ignore":
            title = (data["title"] if data else None) or handle
            row = db.get(ShopifyIgnoredHandle, handle)
            if row is None:
                db.add(ShopifyIgnoredHandle(handle=handle, title=title))
                ignored_added += 1
            else:
                row.title = title
            continue
        if data is None:
            continue
        if item.action == "set":
            set_handles.append(handle)
            row = db.get(ShopifyIgnoredHandle, handle)
            if row is not None:
                db.delete(row)
            continue
        if item.action in ("series_product", "series_material", "on_demand"):
            kind = "material" if item.action == "series_material" else "product"
            on_demand = item.action == "on_demand"
            title = data["title"] or handle
            axes = list(data["option_values"].keys())
            values = {k: list(v) for k, v in data["option_values"].items()}
            series_jobs.append(
                ShopifySeriesJob(
                    handle=handle,
                    title=title,
                    kind=kind,
                    on_demand=on_demand,
                    option_axes=axes,
                    option_values=values,
                )
            )
            q = db.get(ShopifyImportQueueItem, handle)
            if q is None:
                db.add(
                    ShopifyImportQueueItem(
                        handle=handle,
                        title=title,
                        kind=kind,
                        on_demand=on_demand,
                        status="open",
                        option_axes=axes,
                        option_values=values,
                        created_at=now,
                        updated_at=now,
                        completed_at=None,
                    )
                )
            else:
                q.title = title
                q.kind = kind
                q.on_demand = on_demand
                q.option_axes = axes
                q.option_values = values
                q.updated_at = now
                # Re-marking reopens done entries
                q.status = "open"
                q.completed_at = None
            queue_upserted += 1
            ignored = db.get(ShopifyIgnoredHandle, handle)
            if ignored is not None:
                db.delete(ignored)

    upsert = {"sets_created": 0, "sets_touched": 0, "variants_upserted": 0, "set_ids": [], "message": ""}
    if set_handles:
        upsert = _upsert_sets_from_catalog(db, usable, handles=set_handles)

    db.commit()
    parts = []
    if upsert["sets_touched"]:
        parts.append(upsert["message"])
    if ignored_added:
        parts.append(f"{ignored_added} Handle(s) ignoriert")
    if queue_upserted:
        parts.append(f"{queue_upserted} in Import-Warteschlange")
    return ShopifyApplyResult(
        sets_created=upsert["sets_created"],
        sets_updated=max(0, upsert["sets_touched"] - upsert["sets_created"]),
        variants_upserted=upsert["variants_upserted"],
        ignored_added=ignored_added,
        queue_upserted=queue_upserted,
        series_jobs=series_jobs,
        set_ids=upsert["set_ids"],
        message="; ".join(parts) if parts else "Keine Änderungen.",
    )


def _import_queue_read(row) -> "ImportQueueItemRead":
    from app.schemas import ImportQueueItemRead

    return ImportQueueItemRead(
        handle=row.handle,
        title=row.title,
        kind=row.kind if row.kind in ("product", "material") else "product",
        on_demand=bool(row.on_demand),
        status=row.status if row.status in ("open", "done") else "open",
        option_axes=list(row.option_axes or []),
        option_values={k: list(v) for k, v in (row.option_values or {}).items()},
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


def list_import_queue(db: Session, status: str | None = None) -> list["ImportQueueItemRead"]:
    from app.models import ShopifyImportQueueItem

    stmt = select(ShopifyImportQueueItem).order_by(
        ShopifyImportQueueItem.status.asc(),
        ShopifyImportQueueItem.updated_at.desc(),
    )
    if status in ("open", "done"):
        stmt = stmt.where(ShopifyImportQueueItem.status == status)
    rows = db.scalars(stmt).all()
    return [_import_queue_read(r) for r in rows]


def update_import_queue_status(db: Session, handle: str, status: str) -> "ImportQueueItemRead":
    from app.models import ShopifyImportQueueItem

    row = db.get(ShopifyImportQueueItem, handle.strip())
    if row is None:
        raise HTTPException(status_code=404, detail="Warteschlangen-Eintrag nicht gefunden")
    if status not in ("open", "done"):
        raise HTTPException(status_code=400, detail="status muss open oder done sein")
    now = _utcnow()
    row.status = status
    row.updated_at = now
    row.completed_at = now if status == "done" else None
    db.commit()
    db.refresh(row)
    return _import_queue_read(row)


def delete_import_queue_item(db: Session, handle: str) -> None:
    from app.models import ShopifyImportQueueItem

    row = db.get(ShopifyImportQueueItem, handle.strip())
    if row is None:
        raise HTTPException(status_code=404, detail="Warteschlangen-Eintrag nicht gefunden")
    db.delete(row)
    db.commit()


def list_ignored_shopify_handles(db: Session) -> list["ShopifyIgnoredHandleRead"]:
    from app.models import ShopifyIgnoredHandle
    from app.schemas import ShopifyIgnoredHandleRead

    rows = db.scalars(select(ShopifyIgnoredHandle).order_by(ShopifyIgnoredHandle.handle)).all()
    return [
        ShopifyIgnoredHandleRead(handle=r.handle, title=r.title, ignored_at=r.ignored_at) for r in rows
    ]


def unignore_shopify_handle(db: Session, handle: str) -> None:
    from app.models import ShopifyIgnoredHandle

    row = db.get(ShopifyIgnoredHandle, handle.strip())
    if not row:
        raise HTTPException(status_code=404, detail="Handle nicht auf der Ignorieren-Liste")
    db.delete(row)
    db.commit()


def bulk_delete_sets(db: Session, payload: "BulkDeleteRequest") -> "BulkDeleteResult":
    from app.schemas import BulkDeleteRequest, BulkDeleteResult, BulkDeleteSkip

    if not isinstance(payload, BulkDeleteRequest):
        payload = BulkDeleteRequest.model_validate(payload)
    deleted: list[int] = []
    skipped: list[BulkDeleteSkip] = []
    for sid in payload.ids:
        product_set = db.get(ProductSet, sid)
        if product_set is None:
            skipped.append(BulkDeleteSkip(id=sid, name=str(sid), reason="nicht gefunden"))
            continue
        name = product_set.name
        db.delete(product_set)
        deleted.append(sid)
    db.commit()
    return BulkDeleteResult(deleted_ids=deleted, skipped=skipped)


def _order_display(order: CustomerOrder) -> str:
    if order.customer_name:
        return order.customer_name
    if order.external_number:
        return order.external_number
    return f"Bestellung {order.id}"


def _todo_read(todo: WorkTodo) -> "TodoRead":
    from app.schemas import TodoRead

    order = todo.order
    return TodoRead(
        id=todo.id,
        order_id=todo.order_id,
        order_line_id=todo.order_line_id,
        kind=todo.kind if todo.kind in ("manufacture", "create_article", "purchase") else "create_article",
        category=todo.category if todo.category in ("workshop", "purchase") else "workshop",
        status=todo.status if todo.status in ("open", "done") else "open",
        title=todo.title,
        quantity=_q(todo.quantity),
        product_id=todo.product_id,
        material_id=todo.material_id,
        product_name=todo.product.name if todo.product else None,
        material_name=todo.material.name if todo.material else None,
        order_label=_order_display(order) if order else None,
        created_at=todo.created_at,
        completed_at=todo.completed_at,
    )


def _line_read(line: OrderLine, include_todos: bool = True) -> "OrderLineRead":
    from app.schemas import OrderLineRead

    return OrderLineRead(
        id=line.id,
        quantity=_q(line.quantity),
        label=line.label,
        product_id=line.product_id,
        material_id=line.material_id,
        product_name=line.product.name if line.product else None,
        material_name=line.material.name if line.material else None,
        todos=[_todo_read(t) for t in line.todos] if include_todos else [],
    )


def _order_read(order: CustomerOrder, include_line_todos: bool = True) -> "OrderRead":
    from app.schemas import OrderRead

    status = order.status if order.status in ("open", "ready", "shipped") else "open"
    return OrderRead(
        id=order.id,
        ordered_on=order.ordered_on,
        customer_name=order.customer_name,
        external_number=order.external_number,
        status=status,
        lines=[_line_read(ln, include_todos=include_line_todos) for ln in order.lines],
        todos=[_todo_read(t) for t in order.todos],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _order_load(db: Session, order_id: int) -> CustomerOrder:
    order = db.scalars(
        select(CustomerOrder)
        .where(CustomerOrder.id == order_id)
        .options(
            selectinload(CustomerOrder.lines).selectinload(OrderLine.product),
            selectinload(CustomerOrder.lines).selectinload(OrderLine.material),
            selectinload(CustomerOrder.lines).selectinload(OrderLine.todos).selectinload(WorkTodo.product),
            selectinload(CustomerOrder.lines).selectinload(OrderLine.todos).selectinload(WorkTodo.material),
            selectinload(CustomerOrder.todos).selectinload(WorkTodo.product),
            selectinload(CustomerOrder.todos).selectinload(WorkTodo.material),
            selectinload(CustomerOrder.todos).selectinload(WorkTodo.order),
        )
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")
    return order


def _refresh_order_status(order: CustomerOrder) -> None:
    if order.status == "shipped":
        return
    has_open = any(t.status == "open" for t in order.todos)
    order.status = "open" if has_open else "ready"
    order.updated_at = _utcnow()


def _needs_manufacture(db: Session, product: Product, qty: Decimal) -> bool:
    if bool(getattr(product, "is_on_demand", False)):
        return True
    loaded = product
    if not product.stocks:
        loaded = _load_product(db, product.id)
    return _product_stock_available(loaded) < _q(qty)


def _sync_line_todos(db: Session, line: OrderLine) -> None:
    for todo in list(line.todos):
        if todo.status == "open":
            db.delete(todo)
    db.flush()

    qty = _q(line.quantity)
    if line.product_id is None and line.material_id is None:
        db.add(
            WorkTodo(
                order_id=line.order_id,
                order_line_id=line.id,
                kind="create_article",
                category="workshop",
                status="open",
                title=f"Artikel anlegen: {line.label}",
                quantity=qty,
            )
        )
        return
    if line.product_id is not None:
        product = line.product or _load_product(db, line.product_id)
        if _needs_manufacture(db, product, qty):
            db.add(
                WorkTodo(
                    order_id=line.order_id,
                    order_line_id=line.id,
                    kind="manufacture",
                    category="workshop",
                    status="open",
                    title=f"Fertigen: {product.name}",
                    quantity=qty,
                    product_id=product.id,
                )
            )


def create_order(db: Session, payload: "OrderCreate") -> "OrderRead":
    from app.schemas import OrderCreate

    if not isinstance(payload, OrderCreate):
        payload = OrderCreate.model_validate(payload)
    ordered_on = payload.ordered_on or datetime.now()
    order = CustomerOrder(
        ordered_on=ordered_on,
        customer_name=(payload.customer_name or "").strip() or None,
        external_number=(payload.external_number or "").strip() or None,
        status="open",
    )
    db.add(order)
    db.flush()
    for item in payload.lines:
        label = (item.label or "").strip()
        product = _load_product(db, item.product_id) if item.product_id else None
        material = _load_material(db, item.material_id) if item.material_id else None
        if not label:
            label = product.name if product else (material.name if material else "")
        line = OrderLine(
            order_id=order.id,
            quantity=_q(item.quantity),
            label=label,
            product_id=product.id if product else None,
            material_id=material.id if material else None,
        )
        db.add(line)
        db.flush()
        _sync_line_todos(db, line)
    db.flush()
    order = _order_load(db, order.id)
    _refresh_order_status(order)
    db.commit()
    return _order_read(_order_load(db, order.id))


def list_orders(db: Session, status: str | None = None) -> list["OrderRead"]:
    stmt = (
        select(CustomerOrder)
        .order_by(CustomerOrder.ordered_on.desc(), CustomerOrder.id.desc())
        .options(
            selectinload(CustomerOrder.lines).selectinload(OrderLine.product),
            selectinload(CustomerOrder.lines).selectinload(OrderLine.material),
            selectinload(CustomerOrder.todos).selectinload(WorkTodo.product),
            selectinload(CustomerOrder.todos).selectinload(WorkTodo.material),
            selectinload(CustomerOrder.todos).selectinload(WorkTodo.order),
        )
    )
    if status in ("open", "ready", "shipped"):
        stmt = stmt.where(CustomerOrder.status == status)
    rows = db.scalars(stmt).unique().all()
    return [_order_read(row, include_line_todos=False) for row in rows]


def get_order(db: Session, order_id: int) -> "OrderRead":
    return _order_read(_order_load(db, order_id))


def update_order(db: Session, order_id: int, payload: "OrderUpdate") -> "OrderRead":
    from app.schemas import OrderUpdate

    if not isinstance(payload, OrderUpdate):
        payload = OrderUpdate.model_validate(payload)
    order = _order_load(db, order_id)
    data = payload.model_dump(exclude_unset=True)
    if "customer_name" in data:
        order.customer_name = (data["customer_name"] or "").strip() or None
    if "external_number" in data:
        order.external_number = (data["external_number"] or "").strip() or None
    if data.get("status") == "shipped":
        _refresh_order_status(order)
        if order.status == "open":
            raise HTTPException(status_code=400, detail="Bestellung hat noch offene Todos")
        order.status = "shipped"
    order.updated_at = _utcnow()
    db.commit()
    return _order_read(_order_load(db, order_id))


def delete_order(db: Session, order_id: int) -> None:
    order = db.get(CustomerOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")
    if order.status == "shipped":
        raise HTTPException(status_code=400, detail="Versendete Bestellung nicht löschen")
    db.delete(order)
    db.commit()


def link_order_line(db: Session, order_id: int, line_id: int, payload: "OrderLineLink") -> "OrderRead":
    from app.schemas import OrderLineLink

    if not isinstance(payload, OrderLineLink):
        payload = OrderLineLink.model_validate(payload)
    order = _order_load(db, order_id)
    line = next((ln for ln in order.lines if ln.id == line_id), None)
    if line is None:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")
    if payload.product_id:
        product = _load_product(db, payload.product_id)
        line.product_id = product.id
        line.material_id = None
        line.label = product.name
    elif payload.material_id:
        material = _load_material(db, payload.material_id)
        line.material_id = material.id
        line.product_id = None
        line.label = material.name
    else:
        raise HTTPException(status_code=400, detail="Produkt oder Material angeben")
    _sync_line_todos(db, line)
    db.flush()
    order = _order_load(db, order_id)
    _refresh_order_status(order)
    db.commit()
    return _order_read(_order_load(db, order_id))


def list_todos(
    db: Session,
    category: str | None = None,
    status: str | None = None,
) -> list["TodoRead"]:
    stmt = (
        select(WorkTodo)
        .order_by(WorkTodo.status.asc(), WorkTodo.created_at.desc())
        .options(
            selectinload(WorkTodo.product),
            selectinload(WorkTodo.material),
            selectinload(WorkTodo.order),
        )
    )
    if category in ("workshop", "purchase"):
        stmt = stmt.where(WorkTodo.category == category)
    if status in ("open", "done"):
        stmt = stmt.where(WorkTodo.status == status)
    rows = db.scalars(stmt).all()
    return [_todo_read(row) for row in rows]


def complete_todo(db: Session, todo_id: int) -> "TodoRead":
    todo = db.get(WorkTodo, todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="Todo nicht gefunden")
    todo.status = "done"
    todo.completed_at = _utcnow()
    db.flush()
    order = _order_load(db, todo.order_id)
    _refresh_order_status(order)
    db.commit()
    db.refresh(todo)
    todo = db.scalars(
        select(WorkTodo)
        .where(WorkTodo.id == todo_id)
        .options(
            selectinload(WorkTodo.product),
            selectinload(WorkTodo.material),
            selectinload(WorkTodo.order),
        )
    ).first()
    return _todo_read(todo)
