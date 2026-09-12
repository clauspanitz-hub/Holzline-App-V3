from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import backup, services
from app.auth import (
    AdminUser,
    CurrentUser,
    SESSION_COOKIE,
    create_session,
    delete_session_by_token,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import Unit, User, UserRole
from app.schemas import (
    BackupImportRequest,
    BackupImportResult,
    BomLineCreate,
    BomLineUpdate,
    BulkDeleteRequest,
    BulkDeleteResult,
    ChangePasswordRequest,
    ColorCreate,
    ColorMatchSuggestion,
    ColorRead,
    ColorUpdate,
    ColorWriteResult,
    LocationRead,
    LoginRequest,
    ManufactureRequest,
    ManufactureResult,
    MaterialBulkUpdate,
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
    ProductBulkUpdate,
    ProductCreate,
    ProductRead,
    ProductsFromColorsRequest,
    ProductsFromColorsResult,
    ProductSetCreate,
    ProductSetRead,
    ProductSetUpdate,
    ProductUpdate,
    SetBomLineCreate,
    ShopifyApplyRequest,
    ShopifyApplyResult,
    ShopifyIgnoredHandleRead,
    ShopifyInventoryImportResult,
    ShopifyPreviewResult,
    StockAdjustRequest,
    StockDeltaRequest,
    StockMovementRead,
    TagCreate,
    TagRead,
    TagUpdate,
    TransferRequest,
    TransformRequest,
    UnitInfo,
    UserCreate,
    UserRead,
    UserUpdate,
)

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/units", response_model=list[UnitInfo])
def units() -> list[UnitInfo]:
    return [UnitInfo(value=unit.value, label=unit.value) for unit in Unit]


@router.get("/media", response_model=list[MediumRead])
def media(db: Session = Depends(get_db)) -> list[MediumRead]:
    return services.list_media(db)


@router.post("/media", response_model=MediumRead, status_code=201)
def create_medium(payload: MediumCreate, db: Session = Depends(get_db)) -> MediumRead:
    return services.create_medium(db, payload)


@router.patch("/media/{medium_id}", response_model=MediumWriteResult)
def update_medium(medium_id: int, payload: MediumUpdate, db: Session = Depends(get_db)) -> MediumWriteResult:
    return services.update_medium(db, medium_id, payload)


@router.delete("/media/{medium_id}", status_code=204)
def delete_medium(medium_id: int, db: Session = Depends(get_db)) -> None:
    services.delete_medium(db, medium_id)


@router.get("/colors", response_model=list[ColorRead])
def colors(medium_id: int | None = None, db: Session = Depends(get_db)) -> list[ColorRead]:
    return services.list_colors(db, medium_id=medium_id)


@router.post("/colors", response_model=ColorRead, status_code=201)
def create_color(payload: ColorCreate, db: Session = Depends(get_db)) -> ColorRead:
    return services.create_color(db, payload)


@router.patch("/colors/{color_id}", response_model=ColorWriteResult)
def update_color(color_id: int, payload: ColorUpdate, db: Session = Depends(get_db)) -> ColorWriteResult:
    return services.update_color(db, color_id, payload)


@router.delete("/colors/{color_id}", status_code=204)
def delete_color(color_id: int, db: Session = Depends(get_db)) -> None:
    services.delete_color(db, color_id)


@router.get("/tags", response_model=list[TagRead])
def tags(db: Session = Depends(get_db)) -> list[TagRead]:
    return services.list_tags(db)


@router.post("/tags", response_model=TagRead, status_code=201)
def create_tag(payload: TagCreate, db: Session = Depends(get_db)) -> TagRead:
    return services.create_tag(db, payload)


@router.patch("/tags/{tag_id}", response_model=TagRead)
def update_tag(tag_id: int, payload: TagUpdate, db: Session = Depends(get_db)) -> TagRead:
    return services.update_tag(db, tag_id, payload)


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(tag_id: int, db: Session = Depends(get_db)) -> None:
    services.delete_tag(db, tag_id)


@router.get("/suggestions/by-color/{color_id}", response_model=list[ColorMatchSuggestion])
def suggestions_by_color(
    color_id: int,
    materials: bool = True,
    products: bool = True,
    db: Session = Depends(get_db),
) -> list[ColorMatchSuggestion]:
    return services.suggest_by_color(db, color_id, include_materials=materials, include_products=products)


@router.get("/suggestions/by-option-value", response_model=list[ColorMatchSuggestion])
def suggestions_by_option(
    value: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> list[ColorMatchSuggestion]:
    return services.suggest_for_option_value(db, value)


@router.get("/locations", response_model=list[LocationRead])
def locations(db: Session = Depends(get_db)) -> list[LocationRead]:
    return [LocationRead.model_validate(row) for row in services.list_locations(db)]


@router.get("/materials", response_model=list[MaterialRead])
def list_materials(
    tag: str | None = None,
    color_id: int | None = None,
    medium_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[MaterialRead]:
    return services.list_materials(db, tag=tag, color_id=color_id, medium_id=medium_id)


@router.post("/materials", response_model=MaterialRead, status_code=201)
def create_material(payload: MaterialCreate, db: Session = Depends(get_db)) -> MaterialRead:
    return services.create_material(db, payload)


@router.post("/materials/from-colors", response_model=MaterialsFromColorsResult, status_code=201)
def create_materials_from_colors(
    payload: MaterialsFromColorsRequest, db: Session = Depends(get_db)
) -> MaterialsFromColorsResult:
    return services.create_materials_from_colors(db, payload)


@router.get("/materials/{material_id}", response_model=MaterialRead)
def get_material(material_id: int, db: Session = Depends(get_db)) -> MaterialRead:
    return services.material_read(services.get_material(db, material_id))


@router.patch("/materials/{material_id}", response_model=MaterialRead)
def update_material(material_id: int, payload: MaterialUpdate, db: Session = Depends(get_db)) -> MaterialRead:
    return services.update_material(db, material_id, payload)


@router.post("/materials/bulk-update", response_model=list[MaterialRead])
def bulk_update_materials(payload: MaterialBulkUpdate, db: Session = Depends(get_db)) -> list[MaterialRead]:
    return services.bulk_update_materials(db, payload)


@router.post("/materials/bulk-delete", response_model=BulkDeleteResult)
def bulk_delete_materials(payload: BulkDeleteRequest, db: Session = Depends(get_db)) -> BulkDeleteResult:
    return services.bulk_delete_materials(db, payload)


@router.delete("/materials/{material_id}", status_code=204)
def delete_material(material_id: int, db: Session = Depends(get_db)) -> None:
    services.delete_material(db, material_id)


@router.put("/materials/{material_id}/stock", response_model=MaterialRead)
def adjust_material_stock(
    material_id: int,
    payload: StockAdjustRequest,
    db: Session = Depends(get_db),
) -> MaterialRead:
    return services.adjust_material_stock(db, material_id, payload)


@router.post("/materials/{material_id}/stock/delta", response_model=MaterialRead)
def delta_material_stock(
    material_id: int,
    payload: StockDeltaRequest,
    db: Session = Depends(get_db),
) -> MaterialRead:
    return services.delta_material_stock(db, material_id, payload)


@router.post("/materials/{material_id}/transfer", response_model=MaterialRead)
def transfer_material(
    material_id: int,
    payload: TransferRequest,
    db: Session = Depends(get_db),
) -> MaterialRead:
    return services.transfer_material(db, material_id, payload)


@router.get("/products", response_model=list[ProductRead])
def list_products(
    tag: str | None = None,
    color_id: int | None = None,
    medium_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[ProductRead]:
    return services.list_products(db, tag=tag, color_id=color_id, medium_id=medium_id)


@router.post("/products", response_model=ProductRead, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> ProductRead:
    return services.create_product(db, payload)


@router.post("/products/from-colors", response_model=ProductsFromColorsResult, status_code=201)
def create_products_from_colors(
    payload: ProductsFromColorsRequest, db: Session = Depends(get_db)
) -> ProductsFromColorsResult:
    return services.create_products_from_colors(db, payload)


@router.get("/products/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductRead:
    return services.product_read(services._load_product(db, product_id))


@router.patch("/products/{product_id}", response_model=ProductRead)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)) -> ProductRead:
    return services.update_product(db, product_id, payload)


@router.post("/products/bulk-update", response_model=list[ProductRead])
def bulk_update_products(payload: ProductBulkUpdate, db: Session = Depends(get_db)) -> list[ProductRead]:
    return services.bulk_update_products(db, payload)


@router.post("/products/bulk-delete", response_model=BulkDeleteResult)
def bulk_delete_products(payload: BulkDeleteRequest, db: Session = Depends(get_db)) -> BulkDeleteResult:
    return services.bulk_delete_products(db, payload)


@router.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)) -> None:
    services.delete_product(db, product_id)


@router.put("/products/{product_id}/stock", response_model=ProductRead)
def adjust_product_stock(
    product_id: int,
    payload: StockAdjustRequest,
    db: Session = Depends(get_db),
) -> ProductRead:
    return services.adjust_product_stock(db, product_id, payload)


@router.post("/products/{product_id}/stock/delta", response_model=ProductRead)
def delta_product_stock(
    product_id: int,
    payload: StockDeltaRequest,
    db: Session = Depends(get_db),
) -> ProductRead:
    return services.delta_product_stock(db, product_id, payload)


@router.post("/products/{product_id}/transfer", response_model=ProductRead)
def transfer_product(
    product_id: int,
    payload: TransferRequest,
    db: Session = Depends(get_db),
) -> ProductRead:
    return services.transfer_product(db, product_id, payload)


@router.post("/products/{product_id}/transform", response_model=ProductRead)
def transform_product(
    product_id: int,
    payload: TransformRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> ProductRead:
    return services.transform_product(db, product_id, payload, actor=user.username)


@router.get("/movements", response_model=list[StockMovementRead])
def list_movements(
    product_id: int | None = None,
    material_id: int | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[StockMovementRead]:
    return services.list_movements(db, product_id=product_id, material_id=material_id, limit=limit)


@router.post("/products/{product_id}/bom", response_model=ProductRead, status_code=201)
def add_bom_line(product_id: int, payload: BomLineCreate, db: Session = Depends(get_db)) -> ProductRead:
    return services.add_bom_line(db, product_id, payload)


@router.patch("/products/{product_id}/bom/{line_id}", response_model=ProductRead)
def update_bom_line(
    product_id: int,
    line_id: int,
    payload: BomLineUpdate,
    db: Session = Depends(get_db),
) -> ProductRead:
    return services.update_bom_line(db, product_id, line_id, payload)


@router.delete("/products/{product_id}/bom/{line_id}", response_model=ProductRead)
def delete_bom_line(product_id: int, line_id: int, db: Session = Depends(get_db)) -> ProductRead:
    return services.delete_bom_line(db, product_id, line_id)


@router.post("/products/{product_id}/manufacture", response_model=ManufactureResult)
def manufacture(
    product_id: int,
    payload: ManufactureRequest,
    db: Session = Depends(get_db),
) -> ManufactureResult:
    return services.manufacture(db, product_id, payload.quantity, payload.location_id)


@router.get("/sets", response_model=list[ProductSetRead])
def list_sets(db: Session = Depends(get_db)) -> list[ProductSetRead]:
    return services.list_sets(db)


@router.post("/sets", response_model=ProductSetRead, status_code=201)
def create_set(payload: ProductSetCreate, db: Session = Depends(get_db)) -> ProductSetRead:
    return services.create_set(db, payload)


@router.get("/sets/{set_id}", response_model=ProductSetRead)
def get_set(set_id: int, db: Session = Depends(get_db)) -> ProductSetRead:
    return services.product_set_read(db, services._load_set(db, set_id))


@router.patch("/sets/{set_id}", response_model=ProductSetRead)
def update_set(set_id: int, payload: ProductSetUpdate, db: Session = Depends(get_db)) -> ProductSetRead:
    return services.update_set(db, set_id, payload)


@router.delete("/sets/{set_id}", status_code=204)
def delete_set(set_id: int, db: Session = Depends(get_db)) -> None:
    services.delete_set(db, set_id)


@router.post("/sets/{set_id}/mappings", response_model=ProductSetRead, status_code=201)
def add_mapping(set_id: int, payload: OptionMappingCreate, db: Session = Depends(get_db)) -> ProductSetRead:
    return services.add_option_mapping(db, set_id, payload)


@router.delete("/sets/{set_id}/mappings/{mapping_id}", response_model=ProductSetRead)
def delete_mapping(set_id: int, mapping_id: int, db: Session = Depends(get_db)) -> ProductSetRead:
    return services.delete_option_mapping(db, set_id, mapping_id)


@router.delete("/sets/{set_id}/components", response_model=ProductSetRead)
def detach_component(
    set_id: int,
    material_id: int | None = None,
    product_id: int | None = None,
    db: Session = Depends(get_db),
) -> ProductSetRead:
    return services.detach_set_component(db, set_id, material_id=material_id, product_id=product_id)


@router.post("/sets/{set_id}/apply-mappings", response_model=ProductSetRead)
def apply_mappings(set_id: int, db: Session = Depends(get_db)) -> ProductSetRead:
    return services.apply_option_mappings(db, set_id)


@router.post("/sets/{set_id}/variants/{variant_id}/bom", response_model=ProductSetRead, status_code=201)
def add_set_bom(
    set_id: int,
    variant_id: int,
    payload: SetBomLineCreate,
    db: Session = Depends(get_db),
) -> ProductSetRead:
    return services.add_variant_bom_line(db, set_id, variant_id, payload)


@router.delete("/sets/{set_id}/variants/{variant_id}/bom/{line_id}", response_model=ProductSetRead)
def delete_set_bom(
    set_id: int,
    variant_id: int,
    line_id: int,
    db: Session = Depends(get_db),
) -> ProductSetRead:
    return services.delete_variant_bom_line(db, set_id, variant_id, line_id)


@router.get("/backup/export")
def backup_export(
    include_movements: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> JSONResponse:
    payload = backup.export_backup(db, include_movements=include_movements)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="holzlinge-backup-{stamp}.json"'},
    )


@router.post("/backup/import", response_model=BackupImportResult)
def backup_import(
    payload: BackupImportRequest,
    mode: Literal["replace", "merge"] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> BackupImportResult:
    """Query-Parameter `mode` hat Vorrang vor `mode` im Body; Default ist „merge“."""
    effective_mode = mode or payload.mode or "merge"
    return BackupImportResult(**backup.import_backup(db, payload.data, effective_mode))


@router.post("/sets/import/shopify-inventory", response_model=ShopifyInventoryImportResult)
async def import_shopify_inventory(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ShopifyInventoryImportResult:
    """Legacy: legt alle Varianten-Handles als Sets an. Bevorzugt Preview+Apply."""
    raw = await file.read()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV muss UTF-8 sein") from exc
    return services.import_shopify_inventory_csv(db, content)


@router.post("/sets/import/shopify-preview", response_model=ShopifyPreviewResult)
async def preview_shopify_catalog(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ShopifyPreviewResult:
    raw = await file.read()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV muss UTF-8 sein") from exc
    return services.preview_shopify_catalog_csv(db, content)


@router.post("/sets/import/shopify-apply", response_model=ShopifyApplyResult)
async def apply_shopify_catalog(
    file: UploadFile = File(...),
    items_json: str = Form(...),
    db: Session = Depends(get_db),
) -> ShopifyApplyResult:
    import json

    raw = await file.read()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV muss UTF-8 sein") from exc
    try:
        items = json.loads(items_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="items_json ungültig") from exc
    payload = ShopifyApplyRequest.model_validate({"items": items})
    return services.apply_shopify_catalog_csv(db, content, payload)


@router.get("/sets/ignored-handles", response_model=list[ShopifyIgnoredHandleRead])
def list_ignored_handles(db: Session = Depends(get_db)) -> list[ShopifyIgnoredHandleRead]:
    return services.list_ignored_shopify_handles(db)


@router.delete("/sets/ignored-handles/{handle}", status_code=204)
def unignore_handle(handle: str, db: Session = Depends(get_db)) -> None:
    services.unignore_shopify_handle(db, handle)


@router.post("/sets/bulk-delete", response_model=BulkDeleteResult)
def bulk_delete_sets(payload: BulkDeleteRequest, db: Session = Depends(get_db)) -> BulkDeleteResult:
    return services.bulk_delete_sets(db, payload)


def _user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        username=user.username,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post("/auth/login", response_model=UserRead)
def auth_login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserRead:
    from app.config import settings as app_settings

    user = db.scalars(select(User).where(User.username == payload.username.strip())).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Benutzername oder Passwort falsch")
    token = create_session(db, user)
    forwarded = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    secure = request.url.scheme == "https" or forwarded == "https"
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=app_settings.session_idle_hours * 3600,
        path="/",
    )
    return _user_read(user)


@router.post("/auth/logout", status_code=204)
def auth_logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    delete_session_by_token(db, token)
    forwarded = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    secure = request.url.scheme == "https" or forwarded == "https"
    response.delete_cookie(SESSION_COOKIE, path="/", secure=secure, samesite="lax")


@router.get("/auth/me", response_model=UserRead)
def auth_me(user: CurrentUser) -> UserRead:
    return _user_read(user)


@router.post("/auth/change-password", status_code=204)
def auth_change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> None:
    row = db.get(User, user.id)
    if not row or not verify_password(payload.current_password, row.password_hash):
        raise HTTPException(status_code=400, detail="Aktuelles Passwort falsch")
    row.password_hash = hash_password(payload.new_password)
    row.updated_at = datetime.now(timezone.utc)
    db.commit()


@router.get("/users", response_model=list[UserRead])
def list_users(admin: AdminUser, db: Session = Depends(get_db)) -> list[UserRead]:
    rows = db.scalars(select(User).order_by(User.username)).all()
    return [_user_read(u) for u in rows]


@router.post("/users", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, admin: AdminUser, db: Session = Depends(get_db)) -> UserRead:
    name = payload.username.strip()
    if db.scalars(select(User).where(User.username == name)).first():
        raise HTTPException(status_code=400, detail="Benutzername bereits vergeben")
    user = User(
        username=name,
        password_hash=hash_password(payload.password),
        role=UserRole(payload.role),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_read(user)


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: AdminUser,
    db: Session = Depends(get_db),
) -> UserRead:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    if payload.role is not None:
        if user.id == admin.id and payload.role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=400,
                detail="Eigene Rolle nicht ändern — sonst sperrst du dich aus",
            )
        user.role = UserRole(payload.role)
    if payload.is_active is not None:
        if user.id == admin.id and not payload.is_active:
            raise HTTPException(status_code=400, detail="Eigenen Account nicht deaktivieren")
        user.is_active = payload.is_active
        if not user.is_active:
            for sess in list(user.sessions):
                db.delete(sess)
    if payload.password:
        user.password_hash = hash_password(payload.password)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return _user_read(user)
