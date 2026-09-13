"""Shopify-Admin-API: bezahlte, noch nicht vollständig erfüllte Aufträge einlesen."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models import CustomerOrder, OrderLine, Product
from app.order_match import match_product_for_shop_line, normalize_order_number

log = logging.getLogger(__name__)

ORDERS_QUERY = """
query HolzlingeOpenPaidOrders($first: Int!, $after: String, $query: String!) {
  orders(first: $first, after: $after, query: $query, sortKey: CREATED_AT, reverse: true) {
    pageInfo { hasNextPage endCursor }
    nodes {
      name
      createdAt
      cancelledAt
      displayFinancialStatus
      displayFulfillmentStatus
      shippingAddress { name }
      note
      lineItems(first: 50) {
        nodes {
          title
          variantTitle
          name
          sku
          quantity
          unfulfilledQuantity
          customAttributes { key value }
          product { handle title }
          variant {
            sku
            title
            selectedOptions { name value }
          }
        }
      }
    }
  }
}
"""

SEARCH_QUERY = "status:open financial_status:paid"
PAID_OK = {"PAID", "PARTIALLY_PAID"}
FULFILL_OK = {"UNFULFILLED", "PARTIALLY_FULFILLED"}
MISSING_CONFIG = "Shopify nicht konfiguriert (SHOPIFY_STORE, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET)"

_token_lock = threading.Lock()
_cached_token: str | None = None
_cached_token_until = 0.0


def _has_client_credentials() -> bool:
    return bool(
        (settings.shopify_store or "").strip()
        and (settings.shopify_client_id or "").strip()
        and (settings.shopify_client_secret or "").strip()
    )


def shopify_configured() -> bool:
    store = (settings.shopify_store or "").strip()
    if not store:
        return False
    if _has_client_credentials():
        return True
    return bool((settings.shopify_admin_token or "").strip())


def _shop_host() -> str:
    raw = (settings.shopify_store or "").strip()
    raw = raw.removeprefix("https://").removeprefix("http://").split("/")[0]
    if raw and "." not in raw:
        raw = f"{raw}.myshopify.com"
    return raw


def _oauth_error_message(status: int, body: str) -> str:
    """Shopify liefert bei OAuth oft HTML; ins Banner nur den Kern."""
    text = (body or "").strip()
    lower = text.lower()
    if "application_cannot_be_found" in lower:
        return (
            "Shopify kennt die App auf diesem Shop nicht (application_cannot_be_found). "
            "Shop-Domain prüfen, App im Dev Dashboard auf genau diesem Shop installieren, "
            "Client-ID/Secret aus derselben App kopieren. Shop und App müssen in derselben "
            "Shopify-Organisation liegen."
        )
    if "shop_not_permitted" in lower:
        return (
            "Client-Credentials nicht erlaubt: Shop und Dev-Dashboard-App müssen "
            "in derselben Shopify-Organisation liegen, und die App muss installiert sein."
        )
    snippet = text
    if "<" in snippet:
        start = lower.find("<title>")
        end = lower.find("</title>")
        if 0 <= start < end:
            snippet = text[start + 7 : end].strip()
        else:
            snippet = "HTML-Fehlerseite ohne JSON"
    snippet = " ".join(snippet.split())[:180]
    return f"Shopify-Token fehlgeschlagen ({status}): {snippet or 'unbekannter Fehler'}"


def _request_access_token() -> str:
    """Dev Dashboard: Client-ID/Secret → 24h-Access-Token (kein shpat_ mehr)."""
    host = _shop_host()
    url = f"https://{host}/admin/oauth/access_token"
    response = httpx.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": (settings.shopify_client_id or "").strip(),
            "client_secret": (settings.shopify_client_secret or "").strip(),
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise RuntimeError(_oauth_error_message(response.status_code, response.text or ""))
    payload = response.json()
    token = (payload.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Shopify-Token-Antwort ohne access_token")
    expires = int(payload.get("expires_in") or 86399)
    global _cached_token, _cached_token_until
    _cached_token = token
    _cached_token_until = time.time() + max(60, expires - 120)
    return token


def _access_token() -> str:
    legacy = (settings.shopify_admin_token or "").strip()
    if legacy and not _has_client_credentials():
        return legacy
    if not _has_client_credentials():
        raise RuntimeError(MISSING_CONFIG)
    global _cached_token, _cached_token_until
    with _token_lock:
        if _cached_token and time.time() < _cached_token_until:
            return _cached_token
        return _request_access_token()


def _parse_created(value: str | None) -> datetime:
    if not value:
        return datetime.now()
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now()
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return parsed


def _line_qty(node: dict) -> Decimal:
    raw = node.get("unfulfilledQuantity")
    if raw is None:
        raw = node.get("quantity") or 0
    try:
        qty = Decimal(str(raw))
    except Exception:
        qty = Decimal("0")
    return qty


def _form_hint_from_handle(handle: str | None) -> str | None:
    """Form/Stil aus dem Product-Handle, falls nicht schon im Titel (z. B. rund/eckig)."""
    h = (handle or "").casefold().replace("_", "-")
    if not h:
        return None
    for token, label in (
        ("eckig", "eckig"),
        ("rechteck", "eckig"),
        ("quadrat", "eckig"),
        ("rund", "rund"),
        ("oval", "oval"),
    ):
        if token in h:
            return label
    return None


def _line_label(node: dict) -> str:
    title = (node.get("title") or "").strip()
    variant = (node.get("variantTitle") or "").strip()
    if variant.casefold() in ("", "default title"):
        variant = ""
    # selectedOptions oft aussagekräftiger als variantTitle
    opts = []
    for opt in ((node.get("variant") or {}).get("selectedOptions")) or []:
        name = (opt.get("name") or "").strip()
        value = (opt.get("value") or "").strip()
        if not value or value.casefold() == "default title":
            continue
        if name.casefold() == "title":
            continue
        opts.append(value if not name else f"{name}: {value}")
    if opts:
        variant = " / ".join(opts)
    # Line-Item-Eigenschaften (Personalisierung am Artikel)
    attrs = []
    for attr in node.get("customAttributes") or []:
        key = (attr.get("key") or "").strip()
        value = (attr.get("value") or "").strip()
        if not value:
            continue
        attrs.append(f"{key}: {value}" if key else value)
    parts = [title] if title else []
    if variant:
        parts.append(variant)
    elif (node.get("name") or "").strip() and (node.get("name") or "").strip() != title:
        # name enthält oft „Titel - Variante“
        full = (node.get("name") or "").strip()
        if full.startswith(title) and len(full) > len(title) + 2:
            parts = [full]
    if attrs:
        parts.append(" · ".join(attrs))
    label = " - ".join(p for p in parts if p) if parts else "Position"
    handle = (node.get("product") or {}).get("handle") or ""
    form = _form_hint_from_handle(handle)
    if form and form.casefold() not in label.casefold():
        label = f"{label} · {form}"
    return label[:300]


def fetch_open_paid_orders() -> list[dict]:
    if not shopify_configured():
        raise RuntimeError(MISSING_CONFIG)
    host = _shop_host()
    version = (settings.shopify_api_version or "2026-01").strip()
    url = f"https://{host}/admin/api/{version}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": _access_token(),
    }
    out: list[dict] = []
    after = None
    with httpx.Client(timeout=30.0) as client:
        for _ in range(8):
            payload = {
                "query": ORDERS_QUERY,
                "variables": {"first": 50, "after": after, "query": SEARCH_QUERY},
            }
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
            if body.get("errors"):
                raise RuntimeError(str(body["errors"][0].get("message") or body["errors"][0]))
            data = (body.get("data") or {}).get("orders") or {}
            out.extend(data.get("nodes") or [])
            page = data.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            after = page.get("endCursor")
            if not after:
                break
    return out


def _usable_shop_order(node: dict) -> bool:
    if node.get("cancelledAt"):
        return False
    money = str(node.get("displayFinancialStatus") or "").upper()
    fulfill = str(node.get("displayFulfillmentStatus") or "").upper()
    if money not in PAID_OK:
        return False
    if fulfill not in FULFILL_OK:
        return False
    return True


def _customer_name(node: dict) -> str | None:
    customer = node.get("customer") or {}
    name = (customer.get("displayName") or "").strip()
    if name:
        return name[:200]
    ship = node.get("shippingAddress") or {}
    name = (ship.get("name") or "").strip()
    return name[:200] or None


def _usable_line_items(node: dict) -> list[dict]:
    out = []
    for item in ((node.get("lineItems") or {}).get("nodes")) or []:
        if _line_qty(item) > 0:
            out.append(item)
    return out


def _refresh_existing_shop_order(order: CustomerOrder, node: dict) -> bool:
    """Notiz und Positions-Labels bei erneutem Abruf nachziehen. Returns True wenn geändert."""
    changed = False
    note = (node.get("note") or "").strip()
    if note and not (order.note or "").strip():
        order.note = note[:2000]
        changed = True
    items = _usable_line_items(node)
    lines = list(order.lines or [])
    if not items or not lines:
        if changed:
            order.updated_at = datetime.now()
        return changed
    # 1:1 nach Reihenfolge, sonst nur bei gleicher Anzahl
    pairs: list[tuple[OrderLine, dict]] = []
    if len(items) == len(lines):
        pairs = list(zip(lines, items))
    elif len(lines) == 1 and len(items) == 1:
        pairs = [(lines[0], items[0])]
    for line, item in pairs:
        label = _line_label(item)
        if not label:
            continue
        if (line.shop_title or "") != label:
            line.shop_title = label
            changed = True
        # Anzeige-Label nur überschreiben, solange die Zeile unzugeordnet ist
        if not line.product_id and not line.material_id and (line.label or "") != label:
            line.label = label
            changed = True
    if changed:
        order.updated_at = datetime.now()
    return changed


def sync_shopify_orders(db: Session) -> dict:
    """Neue Shopify-Aufträge anlegen. Idempotent über Herkunft + Nummer."""
    from app.services import _order_load, _refresh_order_status, _sync_line_todos

    created = 0
    skipped = 0
    claimed = 0
    errors: list[str] = []
    try:
        nodes = fetch_open_paid_orders()
    except Exception as exc:
        log.warning("Shopify-Abruf fehlgeschlagen: %s", exc)
        return {"created": 0, "skipped": 0, "claimed": 0, "errors": [str(exc)]}

    products = list(
        db.scalars(select(Product).options(selectinload(Product.color))).unique().all()
    )
    from app.shop_map import load_maps, lookup_mapped_product

    maps = load_maps(db, origin="shopify")
    existing = list(
        db.scalars(
            select(CustomerOrder).options(selectinload(CustomerOrder.lines))
        ).all()
    )
    by_shop_num = {
        normalize_order_number(o.external_number): o
        for o in existing
        if o.origin == "shopify" and o.external_number
    }
    by_any_num = {}
    for order in existing:
        key = normalize_order_number(order.external_number)
        if key and key not in by_any_num:
            by_any_num[key] = order

    for node in nodes:
        name = (node.get("name") or "").strip()
        if not name:
            skipped += 1
            continue
        if not _usable_shop_order(node):
            skipped += 1
            continue
        key = normalize_order_number(name)
        if key in by_shop_num:
            existing_order = by_shop_num[key]
            if existing_order.status != "shipped":
                _refresh_existing_shop_order(existing_order, node)
            skipped += 1
            continue
        found = by_any_num.get(key)
        if found is not None and found.origin == "manual":
            found.origin = "shopify"
            found.external_number = name[:80]
            _refresh_existing_shop_order(found, node)
            found.updated_at = datetime.now()
            claimed += 1
            by_shop_num[key] = found
            continue
        if found is not None:
            skipped += 1
            continue

        raw_lines = _usable_line_items(node)
        prepared: list[tuple[str, Decimal, Product | None, str | None]] = []
        for item in raw_lines:
            qty = _line_qty(item)
            sku = item.get("sku") or ((item.get("variant") or {}).get("sku"))
            title = item.get("title") or ""
            variant_title = item.get("variantTitle")
            label = _line_label(item)
            mapped = lookup_mapped_product(
                maps,
                origin="shopify",
                sku=sku,
                title=label,
                variant_title=None,
            )
            product = match_product_for_shop_line(
                products,
                sku=sku,
                title=title,
                variant_title=variant_title,
                mapped=mapped,
            )
            prepared.append((label, qty, product, (sku or "").strip() or None))
        if not prepared:
            skipped += 1
            continue

        all_matched = all(prod is not None for _, _, prod, _ in prepared)
        status = "open" if all_matched else "review"
        note = (node.get("note") or "").strip() or None
        order = CustomerOrder(
            ordered_on=_parse_created(node.get("createdAt")),
            customer_name=_customer_name(node),
            external_number=name[:80],
            note=note[:2000] if note else None,
            origin="shopify",
            status=status,
        )
        db.add(order)
        db.flush()
        for label, qty, product, sku in prepared:
            line = OrderLine(
                order_id=order.id,
                quantity=qty,
                label=label,
                shop_title=label,
                shop_sku=sku[:100] if sku else None,
                product_id=product.id if product else None,
            )
            db.add(line)
            db.flush()
            if status == "open":
                _sync_line_todos(db, line)
        if status == "open":
            loaded = _order_load(db, order.id)
            _refresh_order_status(loaded)
        created += 1
        by_shop_num[key] = order
        by_any_num[key] = order

    db.commit()
    return {"created": created, "skipped": skipped, "claimed": claimed, "errors": errors}
