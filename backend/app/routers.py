from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app import services
from app.database import get_db
from app.models import Unit
from app.schemas import (
    BomLineCreate,
    BomLineUpdate,
    ColorCreate,
    ColorMatchSuggestion,
    ColorRead,
    ColorUpdate,
    ColorWriteResult,
    LocationRead,
    ManufactureRequest,
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
    ProductCreate,
    ProductRead,
    ProductsFromColorsRequest,
    ProductsFromColorsResult,
    ProductSetCreate,
    ProductSetRead,
    ProductSetUpdate,
    ProductUpdate,
    SetBomLineCreate,
    ShopifyInventoryImportResult,
    StockAdjustRequest,
    StockDeltaRequest,
    TagCreate,
    TagRead,
    TagUpdate,
    TransferRequest,
    TransformRequest,
    StockMovementRead,
    UnitInfo,
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
    db: Session = Depends(get_db),
) -> ProductRead:
    return services.transform_product(db, product_id, payload)


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


@router.post("/sets/import/shopify-inventory", response_model=ShopifyInventoryImportResult)
async def import_shopify_inventory(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ShopifyInventoryImportResult:
    raw = await file.read()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV muss UTF-8 sein") from exc
    return services.import_shopify_inventory_csv(db, content)
