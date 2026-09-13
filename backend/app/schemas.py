from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.color_hex import normalize_hex
from app.models import Unit

Quantity = Annotated[Decimal, Field(max_digits=14, decimal_places=3)]
Money = Annotated[Decimal, Field(max_digits=14, decimal_places=2)]
UnitCost = Annotated[Decimal, Field(max_digits=14, decimal_places=4)]


class UnitInfo(BaseModel):
    value: str
    label: str


class MediumCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class MediumUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class MediumRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class MediumWriteResult(MediumRead):
    warnings: list[str] = []


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TagUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_system: bool = False

    @model_validator(mode="after")
    def mark_system_incomplete_tags(self) -> "TagRead":
        from app.incomplete_tags import is_system_incomplete_tag

        self.is_system = is_system_incomplete_tag(self.name)
        return self


class ColorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    medium_id: int
    hex: str | None = Field(default=None, max_length=7)

    @field_validator("hex")
    @classmethod
    def normalize_color_hex(cls, value: str | None) -> str | None:
        return normalize_hex(value)


class ColorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    medium_id: int | None = None
    hex: str | None = Field(default=None, max_length=7)

    @field_validator("hex")
    @classmethod
    def normalize_color_hex(cls, value: str | None) -> str | None:
        return normalize_hex(value)


class ColorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    hex: str | None = None
    medium_id: int
    medium: MediumRead
    label: str = ""

    @model_validator(mode="after")
    def build_label(self) -> "ColorRead":
        self.label = f"{self.name} ({self.medium.name})"
        return self


class ColorWriteResult(ColorRead):
    warnings: list[str] = []


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_virtual: bool


class StockByLocation(BaseModel):
    location_id: int
    location_name: str
    quantity: Quantity
    is_negative: bool = False


class MaterialBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    unit: Unit
    purchase_quantity: Quantity = Field(default=Decimal("1"), gt=0)
    purchase_price: Money = Decimal("0")
    min_stock: Quantity | None = None
    family: str | None = Field(default=None, max_length=200)
    color_id: int | None = None
    decimal_places: int = Field(default=0, ge=0, le=3)
    tag_ids: list[int] = []

    @field_validator("family")
    @classmethod
    def empty_family_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class MaterialCreate(MaterialBase):
    stock_quantity: Quantity = Decimal("0")
    location_id: int | None = None


class MaterialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    unit: Unit | None = None
    purchase_quantity: Quantity | None = Field(default=None, gt=0)
    purchase_price: Money | None = None
    min_stock: Quantity | None = None
    is_template: bool | None = None
    decimal_places: int | None = Field(default=None, ge=0, le=3)
    family: str | None = Field(default=None, max_length=200)
    color_id: int | None = None
    tag_ids: list[int] | None = None
    overview_ignored: bool | None = None

    @field_validator("family")
    @classmethod
    def empty_family_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class MaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    unit: Unit
    purchase_quantity: Quantity
    purchase_price: Money
    cost_per_unit: UnitCost
    min_stock: Quantity | None = None
    is_template: bool = False
    decimal_places: int = 0
    family: str | None = None
    overview_ignored: bool = False
    color_id: int | None = None
    color: ColorRead | None = None
    tags: list[TagRead] = []
    stock_total: Quantity
    is_negative: bool
    stocks: list[StockByLocation] = []
    incomplete_fields: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None


class BomLineCreate(BaseModel):
    material_id: int | None = None
    product_id: int | None = None
    quantity_required: Quantity = Field(gt=0)

    @model_validator(mode="after")
    def one_component(self) -> "BomLineCreate":
        if (self.material_id is None) == (self.product_id is None):
            raise ValueError("Genau eines von material_id oder product_id setzen")
        return self


class BomLineUpdate(BaseModel):
    quantity_required: Quantity = Field(gt=0)


class BomLineRead(BaseModel):
    id: int
    material_id: int | None = None
    product_id: int | None = None
    component_name: str
    component_kind: Literal["material", "product"]
    material_unit: Unit | None = None
    quantity_required: Quantity
    line_cost: Money
    decimal_places: int = 0


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sku: str | None = Field(default=None, max_length=100)
    selling_price: Money = Decimal("0")
    min_stock: Quantity | None = None
    is_template: bool = False
    family: str | None = Field(default=None, max_length=200)
    color_id: int | None = None
    transform_target_id: int | None = None
    tag_ids: list[int] = []
    is_on_demand: bool = False

    @field_validator("sku")
    @classmethod
    def empty_sku_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("family")
    @classmethod
    def empty_family_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ProductCreate(ProductBase):
    stock_quantity: Quantity = Decimal("0")
    location_id: int | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    sku: str | None = Field(default=None, max_length=100)
    selling_price: Money | None = None
    min_stock: Quantity | None = None
    is_template: bool | None = None
    is_on_demand: bool | None = None
    family: str | None = Field(default=None, max_length=200)
    color_id: int | None = None
    transform_target_id: int | None = None
    tag_ids: list[int] | None = None
    overview_ignored: bool | None = None

    @field_validator("sku")
    @classmethod
    def empty_sku_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("family")
    @classmethod
    def empty_family_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sku: str | None
    selling_price: Money = Decimal("0")
    min_stock: Quantity | None = None
    is_template: bool = False
    is_on_demand: bool = False
    family: str | None = None
    overview_ignored: bool = False
    color_id: int | None = None
    color: ColorRead | None = None
    transform_target_id: int | None = None
    transform_target_name: str | None = None
    tags: list[TagRead] = []
    stock_total: Quantity
    stock_available: Quantity
    material_cost: Money
    is_negative: bool
    stocks: list[StockByLocation] = []
    bom: list[BomLineRead] = []
    incomplete_fields: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None


class ManufactureRequest(BaseModel):
    quantity: Quantity = Field(gt=0)
    location_id: int | None = None


class ManufactureResult(BaseModel):
    product: ProductRead
    warnings: list[str]


class TransferRequest(BaseModel):
    from_location_id: int
    to_location_id: int
    quantity: Quantity = Field(gt=0)
    note: str | None = Field(default=None, max_length=500)


class TransformRequest(BaseModel):
    location_id: int
    quantity: Quantity = Field(gt=0)
    note: str | None = Field(default=None, max_length=500)


class StockMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    product_id: int | None = None
    product_name: str | None = None
    material_id: int | None = None
    material_name: str | None = None
    to_product_id: int | None = None
    to_product_name: str | None = None
    from_location_id: int
    from_location_name: str
    to_location_id: int
    to_location_name: str
    quantity: Quantity
    note: str | None = None
    created_at: datetime | None = None
    created_by: str | None = None


class StockAdjustRequest(BaseModel):
    location_id: int
    quantity: Quantity


class StockDeltaRequest(BaseModel):
    location_id: int
    delta: Quantity


class SetBomLineCreate(BaseModel):
    material_id: int | None = None
    product_id: int | None = None
    quantity_required: Quantity = Field(gt=0)
    is_manual: bool = True

    @model_validator(mode="after")
    def one_component(self) -> "SetBomLineCreate":
        if (self.material_id is None) == (self.product_id is None):
            raise ValueError("Genau eines von material_id oder product_id setzen")
        return self


class SetBomLineRead(BaseModel):
    id: int
    material_id: int | None
    product_id: int | None
    component_name: str
    component_kind: str
    quantity_required: Quantity
    is_manual: bool
    stock_total: Quantity
    buildable_from_line: int


class SetVariantRead(BaseModel):
    id: int
    option1_name: str | None
    option1_value: str | None
    option2_name: str | None
    option2_value: str | None
    option3_name: str | None
    option3_value: str | None
    label: str
    buildable_quantity: int
    bom: list[SetBomLineRead] = []


class OptionMappingCreate(BaseModel):
    option_name: str = Field(min_length=1, max_length=100)
    option_value: str = Field(min_length=1, max_length=100)
    material_id: int | None = None
    product_id: int | None = None
    quantity_required: Quantity = Field(gt=0, default=Decimal("1"))

    @model_validator(mode="after")
    def one_component(self) -> "OptionMappingCreate":
        if (self.material_id is None) == (self.product_id is None):
            raise ValueError("Genau eines von material_id oder product_id setzen")
        return self


class OptionMappingRead(BaseModel):
    id: int
    option_name: str
    option_value: str
    material_id: int | None
    product_id: int | None
    component_name: str
    component_kind: str
    quantity_required: Quantity


class ProductSetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    handle: str = Field(min_length=1, max_length=200)
    count_materials_in_buildability: bool = True


class ProductSetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    count_materials_in_buildability: bool | None = None


class ProductSetRead(BaseModel):
    id: int
    name: str
    handle: str
    count_materials_in_buildability: bool
    variant_count: int
    mapping_count: int = 0
    variants: list[SetVariantRead] = []
    option_mappings: list[OptionMappingRead] = []


class ShopifyInventoryImportResult(BaseModel):
    set_id: int | None = None
    created_set: bool = False
    variants_upserted: int = 0
    sets_touched: int = 0
    sets_created: int = 0
    message: str


class ShopifyHandlePreview(BaseModel):
    handle: str
    title: str
    variant_count: int
    option_axes: list[str] = []
    option_values: dict[str, list[str]] = {}
    ignored: bool = False
    existing_set_id: int | None = None


class ShopifyPreviewResult(BaseModel):
    handles: list[ShopifyHandlePreview]
    ignored_total: int = 0


class ShopifyApplyItem(BaseModel):
    handle: str
    action: Literal["set", "ignore", "series_product", "series_material", "on_demand", "skip"]


class ShopifyApplyRequest(BaseModel):
    items: list[ShopifyApplyItem] = Field(min_length=1)


class ShopifySeriesJob(BaseModel):
    handle: str
    title: str
    kind: Literal["product", "material"]
    on_demand: bool = False
    option_axes: list[str] = []
    option_values: dict[str, list[str]] = {}


class SellingPriceConflict(BaseModel):
    product_id: int
    name: str
    current: Money
    csv: Money


class ShopifyApplyResult(BaseModel):
    sets_created: int = 0
    sets_updated: int = 0
    variants_upserted: int = 0
    ignored_added: int = 0
    queue_upserted: int = 0
    series_jobs: list[ShopifySeriesJob] = []
    set_ids: list[int] = []
    selling_prices_filled: int = 0
    selling_price_conflicts: list[SellingPriceConflict] = []
    message: str


class ShopifyIgnoredHandleRead(BaseModel):
    handle: str
    title: str | None = None
    ignored_at: datetime | None = None


class ShopifyIgnoredHandlesPut(BaseModel):
    handles: list[str] = Field(min_length=1)
    titles: dict[str, str] = {}


class ImportQueueItemRead(BaseModel):
    handle: str
    title: str
    kind: Literal["product", "material"]
    on_demand: bool = False
    status: Literal["open", "done"] = "open"
    option_axes: list[str] = []
    option_values: dict[str, list[str]] = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None


class ImportQueueStatusUpdate(BaseModel):
    status: Literal["open", "done"]


class BackupImportRequest(BaseModel):
    """Backup-Import per JSON-Body: vollständiges Backup-Objekt + Modus."""

    data: dict[str, Any]
    mode: Literal["replace", "merge"] | None = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=6, max_length=200)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=6, max_length=200)
    role: Literal["admin", "mitarbeiter"] = "mitarbeiter"


class UserUpdate(BaseModel):
    role: Literal["admin", "mitarbeiter"] | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6, max_length=200)


class UserRead(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BackupImportResult(BaseModel):
    mode: Literal["replace", "merge"]
    created: dict[str, int] = {}
    updated: dict[str, int] = {}
    warnings: list[str] = []


class ColorMatchSuggestion(BaseModel):
    kind: str  # material | product
    id: int
    name: str
    color_id: int
    color_label: str
    stock_total: Quantity


class BulkSkipInfo(BaseModel):
    color_id: int
    color_name: str
    reason: str


class MaterialsFromColorsRequest(BaseModel):
    color_ids: list[int] = Field(min_length=1)
    base_name: str = Field(min_length=1, max_length=180)
    template_material_id: int | None = None
    unit: Unit | None = None
    purchase_quantity: Quantity | None = Field(default=None, gt=0)
    purchase_price: Money | None = None
    min_stock: Quantity | None = None
    location_id: int | None = None
    tag_ids: list[int] = []

    @model_validator(mode="after")
    def require_stammdaten_or_template(self) -> "MaterialsFromColorsRequest":
        if self.template_material_id is not None:
            return self
        missing: list[str] = []
        if self.unit is None:
            missing.append("unit")
        if self.purchase_quantity is None:
            missing.append("purchase_quantity")
        if self.purchase_price is None:
            missing.append("purchase_price")
        if missing:
            raise ValueError(
                "Ohne Vorlage sind Einheit und Einkauf Pflicht "
                f"(fehlt: {', '.join(missing)})"
            )
        return self


class MaterialsFromColorsResult(BaseModel):
    created: list[MaterialRead]
    skipped: list[BulkSkipInfo]
    warnings: list[str] = []


class ProductsFromColorsRequest(BaseModel):
    color_ids: list[int] = Field(min_length=1)
    base_name: str = Field(min_length=1, max_length=180)
    template_product_id: int | None = None
    min_stock: Quantity | None = None
    location_id: int | None = None
    tag_ids: list[int] = []
    stock_quantity: Quantity = Decimal("0")
    is_on_demand: bool = False


class ProductsFromColorsResult(BaseModel):
    created: list[ProductRead]
    skipped: list[BulkSkipInfo]
    warnings: list[str] = []


class MaterialBulkUpdate(BaseModel):
    ids: list[int] = Field(min_length=1)
    min_stock: Quantity | None = None
    clear_min_stock: bool = False
    tag_ids: list[int] | None = None
    family: str | None = Field(default=None, max_length=200)
    clear_family: bool = False
    is_template: bool | None = None


class ProductBulkUpdate(BaseModel):
    ids: list[int] = Field(min_length=1)
    min_stock: Quantity | None = None
    clear_min_stock: bool = False
    selling_price: Money | None = None
    tag_ids: list[int] | None = None
    family: str | None = Field(default=None, max_length=200)
    clear_family: bool = False
    is_template: bool | None = None


class BulkDeleteRequest(BaseModel):
    ids: list[int] = Field(min_length=1)


class BulkDeleteSkip(BaseModel):
    id: int
    name: str
    reason: str


class BulkDeleteResult(BaseModel):
    deleted_ids: list[int]
    skipped: list[BulkDeleteSkip] = []


class OrderLineCreate(BaseModel):
    quantity: Quantity = Field(gt=0)
    product_id: int | None = None
    material_id: int | None = None
    label: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def need_product_or_label(self) -> "OrderLineCreate":
        if self.product_id is None and self.material_id is None and not (self.label or "").strip():
            raise ValueError("Position braucht Produkt, Material oder Freitext")
        return self


class OrderLineLink(BaseModel):
    product_id: int | None = None
    material_id: int | None = None
    quantity: Quantity | None = None
    unassign: bool = False


class ShopifyOrderSyncResult(BaseModel):
    created: int = 0
    skipped: int = 0
    claimed: int = 0
    suggested: int = 0
    errors: list[str] = []


class TodoRead(BaseModel):
    id: int
    order_id: int
    order_line_id: int
    kind: Literal["manufacture", "create_article", "purchase"]
    category: Literal["workshop", "purchase"]
    status: Literal["open", "done"]
    title: str
    quantity: Quantity
    product_id: int | None = None
    material_id: int | None = None
    product_name: str | None = None
    material_name: str | None = None
    order_label: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class OrderLineRead(BaseModel):
    id: int
    quantity: Quantity
    label: str
    shop_sku: str | None = None
    shop_title: str | None = None
    product_id: int | None = None
    material_id: int | None = None
    product_name: str | None = None
    material_name: str | None = None
    suggested_product_id: int | None = None
    suggested_product_name: str | None = None
    todos: list[TodoRead] = []


class OrderCreate(BaseModel):
    ordered_on: datetime | None = None
    customer_name: str | None = Field(default=None, max_length=200)
    external_number: str | None = Field(default=None, max_length=80)
    lines: list[OrderLineCreate] = Field(min_length=1)


class OrderUpdate(BaseModel):
    customer_name: str | None = Field(default=None, max_length=200)
    external_number: str | None = Field(default=None, max_length=80)
    status: Literal["shipped"] | None = None


class OrderRead(BaseModel):
    id: int
    ordered_on: datetime
    customer_name: str | None = None
    external_number: str | None = None
    origin: Literal["manual", "shopify", "etsy"] = "manual"
    status: Literal["review", "open", "ready", "shipped"]
    lines: list[OrderLineRead] = []
    todos: list[TodoRead] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None
    notices: list[str] = []


class TageslageNextStep(BaseModel):
    text: str
    todo_id: int | None = None


class TageslageStats(BaseModel):
    current_orders: int = 0
    review_orders: int = 0
    open_todos: int = 0
    todos_by_kind: dict[str, int] = {}
    todo_items: list[dict] = []
    current_order_labels: list[str] = []


class TageslageRead(BaseModel):
    cache_date: str
    cached: bool = False
    stats: TageslageStats
    summary: str = ""
    quote: str = ""
    next_steps: list[TageslageNextStep] = []
    error: str | None = None
