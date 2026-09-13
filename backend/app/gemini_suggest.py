"""Gemini-Vorschläge für unzugeordnete Shop-Zeilen. Kein Gedächtnis."""

from __future__ import annotations

import json
import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models import CustomerOrder, OrderLine, Product

log = logging.getLogger(__name__)

MAX_LINES = 40
MAX_PRODUCTS = 400


def _redact_secret(text: str) -> str:
    """API-Keys nie in UI/Logs durchreichen."""
    out = text or ""
    key = (settings.gemini_api_key or "").strip()
    if key:
        out = out.replace(key, "***")
    out = re.sub(r"([?&]key=)[^&\s'\"<>]+", r"\1***", out, flags=re.IGNORECASE)
    out = re.sub(r"(x-goog-api-key['\"\\s:=]+)[^\s'\"<>]+", r"\1***", out, flags=re.IGNORECASE)
    return out


def gemini_configured() -> bool:
    return bool((settings.gemini_api_key or "").strip())


def _catalog(db: Session) -> list[dict]:
    rows = db.scalars(
        select(Product)
        .where(Product.is_template.is_(False))
        .options(selectinload(Product.color))
        .order_by(Product.name)
        .limit(MAX_PRODUCTS)
    ).all()
    out = []
    for product in rows:
        out.append(
            {
                "id": product.id,
                "name": product.name,
                "sku": product.sku or "",
                "family": product.family or "",
                "color": product.color.name if product.color else "",
            }
        )
    return out


def _pending_lines(db: Session, origin: str) -> list[OrderLine]:
    origin_key = (origin or "").strip().casefold() or "shopify"
    return list(
        db.scalars(
            select(OrderLine)
            .join(CustomerOrder)
            .where(
                CustomerOrder.origin == origin_key,
                CustomerOrder.status == "review",
                OrderLine.product_id.is_(None),
                OrderLine.material_id.is_(None),
                OrderLine.suggested_product_id.is_(None),
            )
            .limit(MAX_LINES)
        ).all()
    )


def _parse_matches(text: str) -> list[dict]:
    raw = (text or "").strip()
    if not raw:
        return []
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        items = payload.get("matches") or payload.get("lines") or []
    elif isinstance(payload, list):
        items = payload
    else:
        items = []
    return [item for item in items if isinstance(item, dict)]


def suggest_unmatched_shop_lines(db: Session, origin: str = "shopify") -> tuple[int, str | None]:
    """Vorschläge an unzugeordnete Prüfungszeilen ohne bestehenden Vorschlag. Commitet nicht."""
    if not gemini_configured():
        return 0, None
    lines = _pending_lines(db, origin)
    if not lines:
        return 0, None
    catalog = _catalog(db)
    if not catalog:
        return 0, None
    allowed = {item["id"] for item in catalog}
    payload = {
        "lines": [
            {
                "id": line.id,
                "text": (line.shop_title or line.label or "").strip(),
                "sku": (line.shop_sku or "").strip(),
            }
            for line in lines
        ],
        "products": catalog,
    }
    prompt = (
        "Du ordnest Shop-Bestellzeilen eindeutig einem Lagerprodukt zu. "
        "Nur product_id aus der Liste oder null, wenn unsicher oder mehrere möglich. "
        "Keine Erfindung. Antwort nur JSON: "
        '{"matches":[{"id":<line id>,"product_id":<id oder null>}]}'
        f"\n\n{json.dumps(payload, ensure_ascii=False)}"
    )
    model = (settings.gemini_model or "gemini-3.1-flash-lite").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        response = httpx.post(
            url,
            headers={"x-goog-api-key": settings.gemini_api_key.strip()},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
            },
            timeout=45.0,
        )
        if response.status_code == 404:
            return 0, (
                f"Gemini-Modell „{model}“ nicht gefunden (404). "
                "GEMINI_MODEL in der .env prüfen (z. B. gemini-3.1-flash-lite)."
            )
        response.raise_for_status()
        body = response.json()
        text = (
            (((body.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}])[0].get("text")
            or ""
        )
    except Exception as exc:
        safe = _redact_secret(str(exc))
        log.warning("Gemini-Vorschlag fehlgeschlagen: %s", safe)
        return 0, f"Gemini-Vorschlag fehlgeschlagen: {safe}"

    by_id = {line.id: line for line in lines}
    applied = 0
    for item in _parse_matches(text):
        try:
            line_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        line = by_id.get(line_id)
        if line is None:
            continue
        raw_pid = item.get("product_id")
        if raw_pid in (None, "", "null"):
            continue
        try:
            product_id = int(raw_pid)
        except (TypeError, ValueError):
            continue
        if product_id not in allowed:
            continue
        line.suggested_product_id = product_id
        applied += 1
    return applied, None
