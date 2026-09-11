import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Unit(str, enum.Enum):
    STK = "Stk"
    M = "m"
    KG = "kg"
    G = "g"
    M2 = "m²"
    L = "l"
    ML = "ml"


material_tags = Table(
    "material_tags",
    Base.metadata,
    Column("material_id", ForeignKey("materials.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

product_tags = Table(
    "product_tags",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_virtual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    material_stocks: Mapped[list["MaterialStock"]] = relationship(back_populates="location")
    product_stocks: Mapped[list["ProductStock"]] = relationship(back_populates="location")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class ColorMedium(Base):
    """Farb-Medium — pflegbarer Katalog (Seed: Lack, PLA)."""

    __tablename__ = "color_media"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    colors: Mapped[list["Color"]] = relationship(back_populates="medium", cascade="all, delete-orphan")


class Color(Base):
    __tablename__ = "colors"
    __table_args__ = (UniqueConstraint("name", "medium_id", name="uq_color_name_medium"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    medium_id: Mapped[int] = mapped_column(
        ForeignKey("color_media.id", ondelete="CASCADE"),
        nullable=False,
    )

    medium: Mapped[ColorMedium] = relationship(back_populates="colors")
    materials: Mapped[list["Material"]] = relationship(back_populates="color")
    products: Mapped[list["Product"]] = relationship(back_populates="color")


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    unit: Mapped[Unit] = mapped_column(Enum(Unit, values_callable=lambda x: [e.value for e in x]), nullable=False)
    purchase_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("1"))
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    cost_per_unit: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0"))
    min_stock: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    color_id: Mapped[int | None] = mapped_column(ForeignKey("colors.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    color: Mapped[Color | None] = relationship(back_populates="materials")
    tags: Mapped[list[Tag]] = relationship(secondary=material_tags)
    product_links: Mapped[list["ProductMaterial"]] = relationship(back_populates="material")
    stocks: Mapped[list["MaterialStock"]] = relationship(back_populates="material", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    min_stock: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    family: Mapped[str | None] = mapped_column(String(200), nullable=True)
    color_id: Mapped[int | None] = mapped_column(ForeignKey("colors.id", ondelete="SET NULL"), nullable=True)
    transform_target_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    color: Mapped[Color | None] = relationship(back_populates="products")
    tags: Mapped[list[Tag]] = relationship(secondary=product_tags)
    transform_target: Mapped["Product | None"] = relationship(
        remote_side="Product.id",
        foreign_keys=[transform_target_id],
    )
    materials: Mapped[list["ProductMaterial"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    stocks: Mapped[list["ProductStock"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class MaterialStock(Base):
    __tablename__ = "material_stocks"
    __table_args__ = (UniqueConstraint("material_id", "location_id", name="uq_material_location"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("0"))

    material: Mapped[Material] = relationship(back_populates="stocks")
    location: Mapped[Location] = relationship(back_populates="material_stocks")


class ProductStock(Base):
    __tablename__ = "product_stocks"
    __table_args__ = (UniqueConstraint("product_id", "location_id", name="uq_product_location"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("0"))

    product: Mapped[Product] = relationship(back_populates="stocks")
    location: Mapped[Location] = relationship(back_populates="product_stocks")


class ProductMaterial(Base):
    __tablename__ = "product_materials"
    __table_args__ = (UniqueConstraint("product_id", "material_id", name="uq_product_material"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False)
    quantity_required: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)

    product: Mapped[Product] = relationship(back_populates="materials")
    material: Mapped[Material] = relationship(back_populates="product_links")


class ProductSet(Base):
    """Shopify-Set (kein Lagerbestand). Tabellenname 'sets' ist in SQL reserviert → product_sets."""

    __tablename__ = "product_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    handle: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    count_materials_in_buildability: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    variants: Mapped[list["SetVariant"]] = relationship(
        back_populates="product_set",
        cascade="all, delete-orphan",
    )
    option_mappings: Mapped[list["OptionMapping"]] = relationship(
        back_populates="product_set",
        cascade="all, delete-orphan",
    )


class SetVariant(Base):
    __tablename__ = "set_variants"
    __table_args__ = (
        UniqueConstraint(
            "set_id",
            "option1_value",
            "option2_value",
            "option3_value",
            name="uq_set_variant_options",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("product_sets.id", ondelete="CASCADE"), nullable=False)
    option1_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    option1_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    option2_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    option2_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    option3_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    option3_value: Mapped[str | None] = mapped_column(String(100), nullable=True)

    product_set: Mapped[ProductSet] = relationship(back_populates="variants")
    bom_lines: Mapped[list["SetBomLine"]] = relationship(
        back_populates="variant",
        cascade="all, delete-orphan",
    )


class SetBomLine(Base):
    __tablename__ = "set_bom_lines"
    __table_args__ = (
        CheckConstraint(
            "(material_id IS NOT NULL AND product_id IS NULL) OR (material_id IS NULL AND product_id IS NOT NULL)",
            name="ck_set_bom_one_component",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("set_variants.id", ondelete="CASCADE"), nullable=False)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"), nullable=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=True)
    quantity_required: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    variant: Mapped[SetVariant] = relationship(back_populates="bom_lines")
    material: Mapped[Material | None] = relationship()
    product: Mapped[Product | None] = relationship()


class OptionMapping(Base):
    __tablename__ = "option_mappings"
    __table_args__ = (
        UniqueConstraint("set_id", "option_name", "option_value", name="uq_option_mapping"),
        CheckConstraint(
            "(material_id IS NOT NULL AND product_id IS NULL) OR (material_id IS NULL AND product_id IS NOT NULL)",
            name="ck_option_mapping_one_component",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("product_sets.id", ondelete="CASCADE"), nullable=False)
    option_name: Mapped[str] = mapped_column(String(100), nullable=False)
    option_value: Mapped[str] = mapped_column(String(100), nullable=False)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"), nullable=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=True)
    quantity_required: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("1"))

    product_set: Mapped[ProductSet] = relationship(back_populates="option_mappings")
    material: Mapped[Material | None] = relationship()
    product: Mapped[Product | None] = relationship()


class StockMovementKind(str, enum.Enum):
    TRANSFER = "transfer"
    TRANSFORM = "transform"


class StockMovement(Base):
    """Nachvollziehbare Umbuchung (virtuelle Standorte) oder Umwandlung."""

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[StockMovementKind] = mapped_column(
        Enum(StockMovementKind, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id", ondelete="SET NULL"), nullable=True)
    to_product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    from_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    to_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    product: Mapped[Product | None] = relationship(foreign_keys=[product_id])
    to_product: Mapped[Product | None] = relationship(foreign_keys=[to_product_id])
    material: Mapped[Material | None] = relationship()
    from_location: Mapped[Location] = relationship(foreign_keys=[from_location_id])
    to_location: Mapped[Location] = relationship(foreign_keys=[to_location_id])
