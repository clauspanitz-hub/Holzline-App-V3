"""Tageslage: Gemini-Text für Übersicht (Zusammenfassung, Spruch, Nächste Schritte)."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.gemini_suggest import _redact_secret, gemini_configured
from app.models import CustomerOrder, TageslageCache, WorkTodo

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _today_key() -> str:
    return date.today().isoformat()


def collect_tageslage_stats(db: Session) -> dict:
    orders = list(
        db.scalars(
            select(CustomerOrder).where(CustomerOrder.status.in_(["open", "ready", "review"]))
        ).all()
    )
    current = [o for o in orders if o.status in ("open", "ready")]
    review = [o for o in orders if o.status == "review"]
    todos = list(
        db.scalars(
            select(WorkTodo)
            .where(WorkTodo.status == "open")
            .options(
                selectinload(WorkTodo.product),
                selectinload(WorkTodo.order),
            )
            .order_by(WorkTodo.created_at.asc())
        ).all()
    )
    by_kind = {"manufacture": 0, "create_article": 0, "purchase": 0, "other": 0}
    todo_items = []
    for todo in todos:
        if todo.kind in by_kind:
            by_kind[todo.kind] += 1
        else:
            by_kind["other"] += 1
        name = (
            (todo.product.name if todo.product else None)
            or (todo.title or "").replace("Fertigen: ", "").replace("Artikel anlegen: ", "").strip()
            or "Todo"
        )
        todo_items.append(
            {
                "id": todo.id,
                "kind": todo.kind,
                "title": todo.title,
                "product_name": name,
                "quantity": str(todo.quantity),
                "order_label": (
                    (todo.order.customer_name if todo.order and todo.order.customer_name else None)
                    or (todo.order.external_number if todo.order else None)
                    or f"#{todo.order_id}"
                ),
            }
        )
    return {
        "current_orders": len(current),
        "review_orders": len(review),
        "open_todos": len(todos),
        "todos_by_kind": by_kind,
        "todo_items": todo_items,
        "current_order_labels": [
            (o.customer_name or o.external_number or f"#{o.id}") for o in current[:12]
        ],
    }


def _parse_gemini_payload(text: str) -> dict:
    raw = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_steps(raw_steps: object, allowed_todo_ids: set[int]) -> list[dict]:
    if not isinstance(raw_steps, list):
        return []
    out = []
    for item in raw_steps[:3]:
        if isinstance(item, str):
            text = item.strip()
            if text:
                out.append({"text": text[:240], "todo_id": None})
            continue
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("step") or "").strip()
        if not text:
            continue
        todo_id = item.get("todo_id")
        try:
            tid = int(todo_id) if todo_id is not None else None
        except (TypeError, ValueError):
            tid = None
        if tid is not None and tid not in allowed_todo_ids:
            tid = None
        out.append({"text": text[:240], "todo_id": tid})
    return out


def _fallback_steps(stats: dict) -> list[dict]:
    """Ohne Gemini: bis zu 3 Schritte aus offenen Todos."""
    items = stats.get("todo_items") or []
    out = []
    for item in items[:3]:
        kind = item.get("kind")
        name = item.get("product_name") or item.get("title") or "Todo"
        qty = item.get("quantity") or "1"
        if kind == "manufacture":
            text = f"Fertige {qty}× {name} — bringt dich dem Versand näher."
        elif kind == "create_article":
            text = f"Lege „{name}“ an — dann kann die Bestellung weiterlaufen."
        else:
            text = f"Erledige: {item.get('title') or name}"
        out.append({"text": text[:240], "todo_id": item.get("id")})
    if not out:
        out = [
            {
                "text": "Schau in die kritischen Artikel — oft steckt dort die nächste sinnvolle Werkstatt-Aktion.",
                "todo_id": None,
            },
            {
                "text": "Prüfe offene Shop-Zuordnungen unter Bestellungen — klare Stammdaten sparen später Zeit.",
                "todo_id": None,
            },
        ]
    return out[:3]


def _call_gemini(stats: dict) -> tuple[str, str, list[dict], str | None]:
    """Returns summary, quote, steps, error."""
    if not gemini_configured():
        return (
            "Kurzlage nicht verfügbar (kein Gemini-Schlüssel). Kennzahlen und nächste Schritte bleiben.",
            "Auch ohne KI gilt: ein klarer nächster Schritt schlägt zehn offene Tabs.",
            _fallback_steps(stats),
            None,
        )
    model = (settings.gemini_model or "gemini-3.8-flash").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    prompt = (
        "Du bist die motivierende Tageslage für die Manufaktur Holzlinge "
        "(Holzspielzeug, Geburtstagsringe, Kerzensets, Gravur, Online-Shop). "
        "Antworte NUR JSON: "
        '{"summary":"<3-6 Sätze Deutsch, nenne offene Todo-Produkte namentlich>",'
        '"quote":"<ein motivierender Spruch des Tages zu Selbstständigkeit/Werkstatt/Todos>",'
        '"next_steps":[{"text":"<motivierend>", "todo_id":<id oder null>}]} '
        "Genau 2 oder 3 next_steps. Priorisiere echte offene Todos (todo_id aus der Liste); "
        "wenn wenig oder nichts offen ist, fülle mit holzlinge-passenden Motivationsideen "
        "(Stammdaten, kritisch, Shop, Werkstatt) ohne todo_id. Keine erfundenen Zahlen.\n\n"
        f"{json.dumps(stats, ensure_ascii=False)}"
    )
    try:
        response = httpx.post(
            url,
            headers={"x-goog-api-key": settings.gemini_api_key.strip()},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
            },
            timeout=45.0,
        )
        if response.status_code == 404:
            return (
                f"Kurzlage nicht verfügbar (Modell „{model}“). Kennzahlen und nächste Schritte bleiben.",
                "Auch ohne KI gilt: ein klarer nächster Schritt schlägt zehn offene Tabs.",
                _fallback_steps(stats),
                "model_404",
            )
        if response.status_code == 429:
            return (
                "Kurzlage kurz pausiert (Gemini-Kontingent). Kennzahlen und nächste Schritte aus den Todos.",
                "Pause ist produktiv: erst erledigen, dann neu abrufen.",
                _fallback_steps(stats),
                "rate_limit",
            )
        response.raise_for_status()
        body = response.json()
        text = (
            (((body.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}])[0].get("text")
            or ""
        )
    except Exception as exc:
        safe = _redact_secret(str(exc))
        log.warning("Tageslage Gemini fehlgeschlagen: %s", safe)
        return (
            "Kurzlage nicht verfügbar. Kennzahlen und nächste Schritte aus den Todos.",
            "Auch ohne KI gilt: ein klarer nächster Schritt schlägt zehn offene Tabs.",
            _fallback_steps(stats),
            safe,
        )

    data = _parse_gemini_payload(text)
    summary = str(data.get("summary") or "").strip() or "Kurzlage ohne Text."
    quote = str(data.get("quote") or "").strip()
    allowed = {int(t["id"]) for t in stats.get("todo_items") or []}
    steps = _normalize_steps(data.get("next_steps"), allowed)
    if not steps:
        steps = _fallback_steps(stats)
    return summary, quote, steps, None


def get_tageslage(db: Session, *, force_refresh: bool = False) -> dict:
    stats = collect_tageslage_stats(db)
    today = _today_key()
    row = db.scalars(select(TageslageCache).where(TageslageCache.cache_date == today)).first()

    if row is not None and not force_refresh:
        try:
            steps = json.loads(row.next_steps_json or "[]")
        except json.JSONDecodeError:
            steps = []
        if not isinstance(steps, list):
            steps = []
        return {
            "cache_date": today,
            "cached": True,
            "stats": stats,
            "summary": row.summary,
            "quote": row.quote,
            "next_steps": steps,
            "error": None,
        }

    summary, quote, steps, err = _call_gemini(stats)

    # Ohne Force: bei Fehler alten, brauchbaren Cache behalten
    if err and row is not None and not force_refresh:
        try:
            old_steps = json.loads(row.next_steps_json or "[]")
        except json.JSONDecodeError:
            old_steps = []
        if not isinstance(old_steps, list):
            old_steps = []
        if (row.summary or "").strip() and (old_steps or (row.quote or "").strip()):
            return {
                "cache_date": today,
                "cached": True,
                "stats": stats,
                "summary": row.summary,
                "quote": row.quote,
                "next_steps": old_steps,
                "error": err,
            }

    now = _utcnow()
    if row is None:
        row = TageslageCache(cache_date=today, created_at=now)
        db.add(row)
    row.summary = summary
    row.quote = quote
    row.next_steps_json = json.dumps(steps, ensure_ascii=False)
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return {
        "cache_date": today,
        "cached": False,
        "stats": stats,
        "summary": row.summary,
        "quote": row.quote,
        "next_steps": steps,
        "error": err,
    }
