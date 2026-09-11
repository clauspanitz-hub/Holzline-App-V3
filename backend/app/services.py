from datetime import datetime, timezone
from decimal import Decimal
from math import floor

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import AUSSCHUSS_LOCATION_NAME
from app.models import (
    Color,
    ColorMedium,
    Location,
    Material,
    MaterialStock,
    OptionMapping,
    Product,
    ProductMaterial,
    ProductSet,
    ProductStock,
    SetBomLine,
    SetVariant,
    StockMovement,
    StockMovementKind,
    Tag,
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
    color = Color(name=payload.name.strip(), medium_id=medium.id)
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
    name = payload.name.strip()
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
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag nicht gefunden")
    tag.name = payload.name.strip()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Tag „{tag.name}“ existiert bereits") from exc
    db.refresh(tag)
    return TagRead.model_validate(tag)


def delete_tag(db: Session, tag_id: int) -> None:
    """Removes tag; M:N links cascade-deleted."""
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag nicht gefunden")
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


def material_cost_for_product(product: Product) -> Decimal:
    total = Decimal("0")
    for line in product.materials:
        total += Decimal(line.quantity_required) * Decimal(line.material.cost_per_unit)
    return _m(total)


def bom_line_read(line: ProductMaterial) -> BomLineRead:
    line_cost = _m(Decimal(line.quantity_required) * Decimal(line.material.cost_per_unit))
    return BomLineRead(
        id=line.id,
        material_id=line.material_id,
        material_name=line.material.name,
        material_unit=line.material.unit,
        quantity_required=line.quantity_required,
        line_cost=line_cost,
    )


def material_incomplete_fields(material: Material) -> list[str]:
    missing: list[str] = []
    if material.min_stock is None:
        missing.append("Mindestbestand")
    if Decimal(material.purchase_price) == 0:
        missing.append("Einkaufspreis")
    return missing


def product_incomplete_fields(product: Product) -> list[str]:
    missing: list[str] = []
    if product.min_stock is None:
        missing.append("Mindestbestand")
    if not product.materials:
        missing.append("Stückliste")
    return missing


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
        color_id=color.id if color else None,
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


def _colors_with_product(db: Session) -> set[int]:
    rows = db.scalars(select(Product.color_id).where(Product.color_id.is_not(None)).distinct()).all()
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

    taken = _colors_with_material(db)
    created_ids: list[int] = []
    skipped: list[BulkSkipInfo] = []
    warnings: list[str] = []
    location = get_location(db, payload.location_id) if payload.location_id else default_location(db)
    tags = resolve_tags(db, payload.tag_ids)
    purchase_quantity = _q(payload.purchase_quantity)
    purchase_price = _m(payload.purchase_price)
    cost = _unit_cost(purchase_price, purchase_quantity)

    seen: set[int] = set()
    for color_id in payload.color_ids:
        if color_id in seen:
            continue
        seen.add(color_id)
        color = get_color(db, color_id)
        if not color:
            skipped.append(BulkSkipInfo(color_id=color_id, color_name="?", reason="Farbe nicht gefunden"))
            continue
        if color_id in taken:
            skipped.append(
                BulkSkipInfo(color_id=color_id, color_name=color.name, reason="bereits als Material vorhanden")
            )
            continue
        name, name_warn = _unique_material_name(db, color)
        if name_warn:
            warnings.append(name_warn)
        material = Material(
            name=name,
            unit=payload.unit,
            purchase_quantity=purchase_quantity,
            purchase_price=purchase_price,
            cost_per_unit=cost,
            color_id=color.id,
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
        taken.add(color_id)

    db.commit()
    created = [material_read(_load_material(db, mid)) for mid in created_ids]
    return MaterialsFromColorsResult(created=created, skipped=skipped, warnings=warnings)


def update_material(db: Session, material_id: int, payload: MaterialUpdate) -> MaterialRead:
    material = _load_material(db, material_id)
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
    if "color_id" in data:
        color = get_color(db, data["color_id"])
        data["color_id"] = color.id if color else None
    for key, value in data.items():
        setattr(material, key, value)
    if tag_ids is not None:
        material.tags = resolve_tags(db, tag_ids)
    material.cost_per_unit = _unit_cost(Decimal(material.purchase_price), Decimal(material.purchase_quantity))
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
    if material.product_links:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Material ist in einer Produkt-Stückliste verknüpft und kann nicht gelöscht werden",
        )
    # Set-Zuordnungen und Varianten-Stücklisten lösen (sonst RESTRICT).
    for mapping in db.scalars(select(OptionMapping).where(OptionMapping.material_id == material_id)).all():
        db.delete(mapping)
    for line in db.scalars(select(SetBomLine).where(SetBomLine.material_id == material_id)).all():
        db.delete(line)
    db.flush()
    db.delete(material)
    db.commit()


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


def create_products_from_colors(db: Session, payload: ProductsFromColorsRequest) -> ProductsFromColorsResult:
    from app.schemas import BulkSkipInfo

    base = payload.base_name.strip()
    taken = _colors_with_product(db)
    created_ids: list[int] = []
    skipped: list[BulkSkipInfo] = []
    warnings: list[str] = []
    location = get_location(db, payload.location_id) if payload.location_id else default_location(db)
    tags = resolve_tags(db, payload.tag_ids)

    template_lines: list[ProductMaterial] = []
    if payload.template_product_id is not None:
        template = _load_product(db, payload.template_product_id)
        template_lines = list(template.materials)

    seen: set[int] = set()
    for color_id in payload.color_ids:
        if color_id in seen:
            continue
        seen.add(color_id)
        color = get_color(db, color_id)
        if not color:
            skipped.append(BulkSkipInfo(color_id=color_id, color_name="?", reason="Farbe nicht gefunden"))
            continue
        if color_id in taken:
            skipped.append(
                BulkSkipInfo(color_id=color_id, color_name=color.name, reason="bereits als Produkt vorhanden")
            )
            continue
        name = f"{base} {color.name}".strip()
        if db.scalars(select(Product.id).where(Product.name == name).limit(1)).first():
            skipped.append(
                BulkSkipInfo(color_id=color_id, color_name=color.name, reason=f"Produktname „{name}“ bereits vergeben")
            )
            continue

        product = Product(name=name, sku=None, color_id=color.id)
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
        for line in template_lines:
            source_mat = line.material
            if source_mat is None:
                source_mat = db.get(Material, line.material_id)
            if source_mat is None:
                continue
            # ensure color loaded for remap
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
                    quantity_required=_q(line.quantity_required),
                )
            )

        created_ids.append(product.id)
        taken.add(color_id)

    db.commit()
    created = [product_read(_load_product(db, pid)) for pid in created_ids]
    return ProductsFromColorsResult(created=created, skipped=skipped, warnings=warnings)


def update_product(db: Session, product_id: int, payload: ProductUpdate) -> ProductRead:
    product = _load_product(db, product_id)
    data = payload.model_dump(exclude_unset=True)
    tag_ids = data.pop("tag_ids", None)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
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
    for mapping in db.scalars(select(OptionMapping).where(OptionMapping.product_id == product_id)).all():
        db.delete(mapping)
    for line in db.scalars(select(SetBomLine).where(SetBomLine.product_id == product_id)).all():
        db.delete(line)
    db.flush()
    db.delete(product)
    db.commit()


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


def transform_product(db: Session, product_id: int, payload: TransformRequest) -> ProductRead:
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
    )
    _stamp_update(source)
    target = db.get(Product, source.transform_target_id)
    if target:
        _stamp_update(target)
    db.commit()
    return product_read(_load_product(db, product_id))


def add_bom_line(db: Session, product_id: int, payload: BomLineCreate) -> ProductRead:
    product = _load_product(db, product_id)
    _load_material(db, payload.material_id)
    line = ProductMaterial(
        product_id=product.id,
        material_id=payload.material_id,
        quantity_required=_q(payload.quantity_required),
    )
    db.add(line)
    _stamp_update(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Material ist bereits in der Stückliste",
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
    line = next((item for item in product.materials if item.id == line_id), None)
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stücklistenzeile nicht gefunden")
    db.delete(line)
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
        mat_stock = _get_or_create_material_stock(db, line.material_id, location.id)
        new_stock = _q(Decimal(mat_stock.quantity) - needed)
        if new_stock < 0:
            warnings.append(
                f"Material „{line.material.name}“ an {location.name} wird negativ "
                f"(Bestand {new_stock} {line.material.unit.value} nach Abbuchung von {needed})."
            )
        mat_stock.quantity = new_stock

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


def product_set_read(db: Session, product_set: ProductSet, include_variants: bool = True) -> ProductSetRead:
    variants = (
        [variant_read(db, product_set, variant) for variant in product_set.variants] if include_variants else []
    )
    return ProductSetRead(
        id=product_set.id,
        name=product_set.name,
        handle=product_set.handle,
        count_materials_in_buildability=product_set.count_materials_in_buildability,
        variant_count=len(product_set.variants),
        variants=variants,
        option_mappings=[option_mapping_read(db, m) for m in product_set.option_mappings],
    )


def list_sets(db: Session) -> list[ProductSetRead]:
    rows = db.scalars(
        select(ProductSet)
        .order_by(ProductSet.name)
        .options(
            selectinload(ProductSet.variants).selectinload(SetVariant.bom_lines),
            selectinload(ProductSet.option_mappings),
        )
    ).all()
    return [product_set_read(db, row) for row in rows]


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
    import csv
    import io

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames or "Handle" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail="Ungültiger Shopify Inventory-Export")

    variants: dict[tuple, dict] = {}
    title = None
    handle = None
    for row in reader:
        handle = (row.get("Handle") or "").strip()
        if not handle:
            continue
        title = (row.get("Title") or handle).strip()
        key = (
            (row.get("Option1 Value") or "").strip() or None,
            (row.get("Option2 Value") or "").strip() or None,
            (row.get("Option3 Value") or "").strip() or None,
        )
        variants[key] = {
            "option1_name": (row.get("Option1 Name") or "").strip() or None,
            "option1_value": key[0],
            "option2_name": (row.get("Option2 Name") or "").strip() or None,
            "option2_value": key[1],
            "option3_name": (row.get("Option3 Name") or "").strip() or None,
            "option3_value": key[2],
        }

    if not handle or not variants:
        raise HTTPException(status_code=400, detail="Keine Varianten im Export gefunden")

    existing = db.scalars(select(ProductSet).where(ProductSet.handle == handle)).first()
    created = False
    if not existing:
        existing = ProductSet(name=title or handle, handle=handle, count_materials_in_buildability=True)
        db.add(existing)
        db.flush()
        created = True
    else:
        existing.name = title or existing.name

    product_set = _load_set(db, existing.id)
    existing_keys = {
        (v.option1_value, v.option2_value, v.option3_value): v for v in product_set.variants
    }
    upserted = 0
    for key, data in variants.items():
        if key in existing_keys:
            continue
        db.add(SetVariant(set_id=existing.id, **data))
        upserted += 1
    db.commit()

    return ShopifyInventoryImportResult(
        set_id=existing.id,
        created_set=created,
        variants_upserted=upserted,
        message=f"Set „{existing.name}“: {upserted} neue Varianten importiert ({len(variants)} gesamt im File).",
    )
