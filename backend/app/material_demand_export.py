"""Export offener Einkauf-Todos als Materialbedarfsliste (CSV/PDF) für Lieferantenbestellungen."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Material, MaterialPurchaseSource, MaterialStock, WorkTodo
from app.purchase_todos import material_stock_available

_FONTS_DIR = Path(__file__).resolve().parent / "fonts"
_FONT_REGULAR = _FONTS_DIR / "DejaVuSans.ttf"
_FONT_BOLD = _FONTS_DIR / "DejaVuSans-Bold.ttf"

CSV_HEADERS = [
    "Material",
    "Menge",
    "Einheit",
    "Bestand verfügbar",
    "Mindestbestand",
    "Shop",
    "URL",
    "Quelle-Notiz",
    "Alternativen",
    "Todo-Titel",
]


@dataclass(frozen=True)
class DemandRow:
    material_name: str
    quantity: str
    unit: str
    stock_available: str
    min_stock: str
    shop_name: str
    source_url: str
    source_note: str
    alternatives_note: str
    todo_title: str


def _q(value: Decimal | float | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal("0.001"))


def _fmt_qty(value: Decimal | float | int | str | None, decimals: int = 0) -> str:
    if value is None or value == "":
        return ""
    q = _q(value)
    d = max(0, min(3, int(decimals)))
    quantized = q.quantize(Decimal("1") if d == 0 else Decimal(f"1.{'0' * d}"))
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _preferred_source(material: Material | None) -> MaterialPurchaseSource | None:
    if material is None:
        return None
    sources = list(getattr(material, "purchase_sources", None) or [])
    if not sources:
        return None
    for source in sources:
        if bool(getattr(source, "is_preferred", False)):
            return source
    return sources[0]


def _unit_label(material: Material | None) -> str:
    if material is None:
        return ""
    unit = getattr(material, "unit", None)
    if unit is None:
        return ""
    return unit.value if hasattr(unit, "value") else str(unit)


def collect_demand_rows(db: Session) -> list[DemandRow]:
    """Offene Einkauf-Todos (auto + manuell) als Bedarfsliste, sortiert nach Materialname."""
    stmt = (
        select(WorkTodo)
        .where(
            WorkTodo.kind == "purchase",
            WorkTodo.category == "purchase",
            WorkTodo.status == "open",
        )
        .options(
            selectinload(WorkTodo.material)
            .selectinload(Material.stocks)
            .selectinload(MaterialStock.location),
            selectinload(WorkTodo.material)
            .selectinload(Material.purchase_sources)
            .selectinload(MaterialPurchaseSource.shop),
        )
        .order_by(WorkTodo.id)
    )
    todos = list(db.scalars(stmt).unique().all())
    rows: list[DemandRow] = []
    for todo in todos:
        material = todo.material
        decimals = int(getattr(material, "decimal_places", 0) or 0) if material else 0
        source = _preferred_source(material)
        shop = getattr(source, "shop", None) if source else None
        shop_name = getattr(shop, "name", "") if shop else ""
        available = material_stock_available(material) if material else None
        min_stock = getattr(material, "min_stock", None) if material else None
        name = material.name if material is not None else (todo.title or "Ohne Material")
        rows.append(
            DemandRow(
                material_name=name,
                quantity=_fmt_qty(todo.quantity, decimals),
                unit=_unit_label(material),
                stock_available=_fmt_qty(available, decimals) if material is not None else "",
                min_stock=_fmt_qty(min_stock, decimals) if min_stock is not None else "",
                shop_name=shop_name or "",
                source_url=(source.url if source else "") or "",
                source_note=(source.note if source and source.note else "") or "",
                alternatives_note=(getattr(material, "alternatives_note", None) or "") if material else "",
                todo_title=todo.title or "",
            )
        )
    rows.sort(key=lambda r: (r.material_name.casefold(), r.todo_title.casefold()))
    return rows


def export_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def build_csv(rows: list[DemandRow]) -> bytes:
    """CSV mit Semikolon und UTF-8-BOM für Excel DE."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(CSV_HEADERS)
    for row in rows:
        writer.writerow(
            [
                row.material_name,
                row.quantity,
                row.unit,
                row.stock_available,
                row.min_stock,
                row.shop_name,
                row.source_url,
                row.source_note,
                row.alternatives_note,
                row.todo_title,
            ]
        )
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


class _DemandPdf(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("DejaVu", size=8)
        self.set_text_color(90, 90, 90)
        self.cell(0, 8, f"Seite {self.page_no()}/{{nb}}", align="C")


def build_pdf(rows: list[DemandRow], *, generated_at: datetime | None = None) -> bytes:
    if not _FONT_REGULAR.is_file() or not _FONT_BOLD.is_file():
        raise FileNotFoundError(
            f"PDF-Schriften fehlen unter {_FONTS_DIR} (DejaVuSans.ttf / DejaVuSans-Bold.ttf)"
        )

    when = generated_at or datetime.now(timezone.utc)
    stamp = when.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")

    pdf = _DemandPdf(orientation="L", format="A4", unit="mm")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_font("DejaVu", "", str(_FONT_REGULAR))
    pdf.add_font("DejaVu", "B", str(_FONT_BOLD))
    pdf.add_page()

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Materialbedarf — Lieferantenbestellung", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", size=10)
    pdf.set_text_color(70, 70, 70)
    pdf.cell(
        0,
        7,
        f"Offene Einkauf-Todos · {len(rows)} Position(en) · erstellt {stamp}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)
    pdf.set_text_color(0, 0, 0)

    # Material | Menge | Einheit | Bestand | Min. | Shop | URL
    col_widths = [55, 22, 18, 28, 24, 40, 90]
    headers = ["Material", "Menge", "Einheit", "Bestand", "Min.", "Shop", "URL"]

    def _header_row() -> None:
        pdf.set_font("DejaVu", "B", 9)
        pdf.set_fill_color(235, 235, 230)
        for width, label in zip(col_widths, headers, strict=True):
            pdf.cell(width, 8, label, border=1, fill=True)
        pdf.ln()

    _header_row()
    pdf.set_font("DejaVu", size=8)

    if not rows:
        pdf.cell(sum(col_widths), 8, "Keine offenen Einkauf-Todos.", border=1, new_x="LMARGIN", new_y="NEXT")
    else:
        for row in rows:
            values = [
                row.material_name,
                row.quantity,
                row.unit,
                row.stock_available,
                row.min_stock,
                row.shop_name,
                row.source_url,
            ]
            if pdf.get_y() > 180:
                pdf.add_page()
                _header_row()
                pdf.set_font("DejaVu", size=8)
            for width, val in zip(col_widths, values, strict=True):
                text = val or ""
                max_w = width - 2
                if pdf.get_string_width(text) > max_w:
                    while text and pdf.get_string_width(text + "…") > max_w:
                        text = text[:-1]
                    text = text + "…"
                pdf.cell(width, 7, text, border=1)
            pdf.ln()

    out = pdf.output()
    return bytes(out) if isinstance(out, (bytes, bytearray)) else out.encode("latin-1")
