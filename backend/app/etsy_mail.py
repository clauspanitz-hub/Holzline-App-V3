"""Etsy-Mail-Eingang: IMAP → Warteschlange → Gemini → Bestellung zur Prüfung."""

from __future__ import annotations

import email
import imaplib
import json
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from email.header import decode_header, make_header
from email.message import Message
from html.parser import HTMLParser
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.gemini_suggest import _redact_secret, gemini_configured
from app.models import CustomerOrder, IncomingMail, OrderLine, Product
from app.order_match import match_product_for_shop_line, normalize_order_number

log = logging.getLogger(__name__)

BODY_MAX = 20000


def imap_configured() -> bool:
    return bool(
        (settings.imap_host or "").strip()
        and (settings.imap_user or "").strip()
        and (settings.imap_password or "").strip()
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _HTMLToText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style"):
            self._skip = True
        elif tag in ("br", "p", "div", "tr", "li"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = False
        elif tag in ("p", "div", "tr", "li"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip and data:
            self._parts.append(data)

    def text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self._parts)).strip()


def html_to_text(html: str) -> str:
    parser = _HTMLToText()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html or "")
    return parser.text()


def _decode_header_value(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return raw


def _part_payload(part: Message) -> str:
    try:
        payload = part.get_payload(decode=True)
    except Exception:
        payload = None
    if payload is None:
        data = part.get_payload()
        return data if isinstance(data, str) else ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except Exception:
        return payload.decode("utf-8", errors="replace")


def extract_body_text(msg: Message) -> str:
    """Bevorzugt text/plain; sonst HTML→Text."""
    plain_parts: list[str] = []
    html_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_content_disposition() == "attachment":
                continue
            ctype = (part.get_content_type() or "").lower()
            text = _part_payload(part)
            if ctype == "text/plain":
                plain_parts.append(text)
            elif ctype == "text/html":
                html_parts.append(text)
    else:
        ctype = (msg.get_content_type() or "").lower()
        text = _part_payload(msg)
        if ctype == "text/html":
            html_parts.append(text)
        else:
            plain_parts.append(text)
    if plain_parts:
        body = "\n\n".join(p.strip() for p in plain_parts if p.strip())
    elif html_parts:
        body = html_to_text("\n".join(html_parts))
    else:
        body = ""
    body = body.strip()
    if len(body) > BODY_MAX:
        body = body[:BODY_MAX] + "\n…"
    return body


def _message_id(msg: Message) -> str:
    mid = (msg.get("Message-ID") or msg.get("Message-Id") or "").strip()
    if mid:
        return mid[:300]
    # Fallback: stabile Kurz-ID aus Betreff+Datum+From
    subject = _decode_header_value(msg.get("Subject"))
    date = msg.get("Date") or ""
    frm = _decode_header_value(msg.get("From"))
    return f"local-{hash((subject, date, frm)) & 0xFFFFFFFFFFFF:x}"[:300]


def _ensure_mailbox(conn: imaplib.IMAP4_SSL, name: str) -> None:
    typ, _ = conn.select(name)
    if typ == "OK":
        return
    conn.create(name)


def _move_to_processed(conn: imaplib.IMAP4_SSL, uid: bytes, processed: str) -> None:
    try:
        conn.uid("COPY", uid, processed)
        conn.uid("STORE", uid, "+FLAGS", r"(\Deleted)")
    except Exception as exc:
        log.warning("IMAP Verschieben fehlgeschlagen: %s", _redact_secret(str(exc)))


def fetch_new_mails(db: Session) -> dict[str, Any]:
    """Neue Mails aus IMAP in die Warteschlange; danach nach „verarbeitet“."""
    if not imap_configured():
        return {"fetched": 0, "errors": ["IMAP nicht konfiguriert"]}

    host = settings.imap_host.strip()
    port = int(settings.imap_port or 993)
    user = settings.imap_user.strip()
    password = settings.imap_password.strip()
    folder = (settings.imap_folder or "INBOX").strip() or "INBOX"
    processed = (settings.imap_processed_folder or "verarbeitet").strip() or "verarbeitet"

    fetched = 0
    errors: list[str] = []
    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(user, password)
    except Exception as exc:
        safe = _redact_secret(str(exc))
        log.warning("IMAP Login fehlgeschlagen: %s", safe)
        return {"fetched": 0, "errors": [f"IMAP: {safe}"]}

    try:
        _ensure_mailbox(conn, processed)
        typ, _ = conn.select(folder)
        if typ != "OK":
            return {"fetched": 0, "errors": [f"IMAP-Ordner „{folder}“ nicht erreichbar"]}

        typ, data = conn.uid("SEARCH", None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return {"fetched": 0, "errors": []}

        uids = data[0].split()
        existing_ids = {
            mid
            for mid in db.scalars(select(IncomingMail.message_id)).all()
            if mid
        }

        for uid in uids:
            typ, msg_data = conn.uid("FETCH", uid, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else None
            if not isinstance(raw, (bytes, bytearray)):
                continue
            msg = email.message_from_bytes(raw)
            mid = _message_id(msg)
            if mid in existing_ids:
                _move_to_processed(conn, uid, processed)
                continue
            body = extract_body_text(msg)
            row = IncomingMail(
                origin="etsy",
                message_id=mid,
                subject=_decode_header_value(msg.get("Subject"))[:500] or None,
                from_addr=_decode_header_value(msg.get("From"))[:300] or None,
                body_text=body,
                status="pending",
                received_at=_utcnow(),
                created_at=_utcnow(),
                updated_at=_utcnow(),
            )
            db.add(row)
            existing_ids.add(mid)
            fetched += 1
            _move_to_processed(conn, uid, processed)

        try:
            conn.expunge()
        except Exception:
            pass
        db.flush()
    except Exception as exc:
        safe = _redact_secret(str(exc))
        log.warning("IMAP Abruf fehlgeschlagen: %s", safe)
        errors.append(safe)
    finally:
        try:
            conn.logout()
        except Exception:
            pass

    return {"fetched": fetched, "errors": errors}


def _parse_qty(value: Any) -> Decimal:
    try:
        qty = Decimal(str(value).replace(",", ".").strip())
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")
    if qty <= 0:
        return Decimal("0")
    return qty


def _call_gemini_parse(mail: IncomingMail) -> tuple[dict | None, str | None]:
    if not gemini_configured():
        return None, "Kein Gemini-Schlüssel"
    model = (settings.gemini_model or "gemini-3.1-flash-lite").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    prompt = (
        "Du liest eine Etsy-Bestellmail für die Manufaktur Holzlinge. "
        "Antworte NUR JSON: "
        '{"external_number":"<Bestellnummer>",'
        '"customer_name":"<Kunde oder null>",'
        '"ordered_on":"<ISO-Datum oder null>",'
        '"lines":[{"title":"<Produkt/Titel>","sku":"<SKU oder null>","quantity":1}]} '
        "Mindestens eine Position mit Titel und Menge > 0. "
        "Keine erfundenen Positionen.\n\n"
        f"Betreff: {mail.subject or ''}\n"
        f"Von: {mail.from_addr or ''}\n\n"
        f"{mail.body_text or ''}"
    )
    try:
        response = httpx.post(
            url,
            headers={"x-goog-api-key": settings.gemini_api_key.strip()},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
            },
            timeout=60.0,
        )
        if response.status_code == 429:
            return None, "Gemini-Kontingent erreicht"
        if response.status_code == 404:
            return None, f"Gemini-Modell „{model}“ nicht gefunden"
        response.raise_for_status()
        body = response.json()
        text = (
            (((body.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}])[0].get("text")
            or ""
        )
    except Exception as exc:
        return None, _redact_secret(str(exc))

    raw = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, "Gemini-Antwort kein gültiges JSON"
    if not isinstance(data, dict):
        return None, "Gemini-Antwort ungültig"
    return data, None


def _parse_ordered_on(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    text = str(value or "").strip()
    if not text:
        return datetime.now()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except ValueError:
        return datetime.now()


def parse_pending_mails(db: Session) -> dict[str, Any]:
    """Wartende Mails mit Gemini parsen → Bestellungen zur Prüfung. Commitet nicht."""
    from app.shop_map import load_maps, lookup_mapped_product

    created = 0
    duplicates = 0
    failed = 0
    errors: list[str] = []

    pending = list(
        db.scalars(
            select(IncomingMail)
            .where(IncomingMail.status.in_(("pending", "error")))
            .order_by(IncomingMail.id.asc())
        ).all()
    )
    if not pending:
        return {"created": 0, "duplicates": 0, "failed": 0, "errors": []}

    products = list(
        db.scalars(select(Product).options(selectinload(Product.color))).unique().all()
    )
    maps = load_maps(db, origin="etsy")
    existing_etsy = {
        normalize_order_number(o.external_number): o
        for o in db.scalars(select(CustomerOrder).where(CustomerOrder.origin == "etsy")).all()
        if o.external_number
    }

    for mail in pending:
        data, err = _call_gemini_parse(mail)
        if err or not data:
            mail.status = "error"
            mail.error_message = (err or "Parse fehlgeschlagen")[:500]
            mail.updated_at = _utcnow()
            failed += 1
            if err and err not in errors:
                errors.append(err)
            continue

        number = str(data.get("external_number") or "").strip()
        lines_raw = data.get("lines") if isinstance(data.get("lines"), list) else []
        prepared: list[tuple[str, Decimal, Product | None, str | None]] = []
        for item in lines_raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("label") or "").strip()
            sku = str(item.get("sku") or "").strip() or None
            qty = _parse_qty(item.get("quantity", 1))
            if not title or qty <= 0:
                continue
            label = title[:300]
            mapped = lookup_mapped_product(
                maps, origin="etsy", sku=sku, title=label, variant_title=None
            )
            product = match_product_for_shop_line(
                products, sku=sku, title=title, variant_title=None, mapped=mapped
            )
            prepared.append((label, qty, product, sku[:100] if sku else None))

        if not number or not prepared:
            mail.status = "error"
            mail.error_message = "Nummer oder Positionen fehlen"
            mail.updated_at = _utcnow()
            failed += 1
            continue

        key = normalize_order_number(number)
        if key in existing_etsy:
            mail.status = "duplicate"
            mail.error_message = f"Bestellung {number} existiert bereits — Ignorieren oder erneut prüfen"
            mail.updated_at = _utcnow()
            duplicates += 1
            continue

        customer = data.get("customer_name")
        customer_name = str(customer).strip()[:200] if customer else None
        order = CustomerOrder(
            ordered_on=_parse_ordered_on(data.get("ordered_on")),
            customer_name=customer_name or None,
            external_number=number[:80],
            origin="etsy",
            status="review",
        )
        db.add(order)
        db.flush()
        for label, qty, product, sku in prepared:
            db.add(
                OrderLine(
                    order_id=order.id,
                    quantity=qty,
                    label=label,
                    shop_title=label,
                    shop_sku=sku,
                    product_id=product.id if product else None,
                )
            )
        existing_etsy[key] = order
        db.delete(mail)
        created += 1

    return {
        "created": created,
        "duplicates": duplicates,
        "failed": failed,
        "errors": errors,
    }


def list_queue(db: Session) -> list[IncomingMail]:
    return list(
        db.scalars(
            select(IncomingMail)
            .where(IncomingMail.status.in_(("pending", "duplicate", "error")))
            .order_by(IncomingMail.id.desc())
        ).all()
    )


def ignore_mail(db: Session, mail_id: int) -> None:
    row = db.get(IncomingMail, mail_id)
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Mail nicht gefunden")
    db.delete(row)
