"""Einkaufsquellen / Shops (ADR 0021)."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Material, MaterialPurchaseSource, ProductMaterial, Shop


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def shop_name_from_url(url: str) -> str | None:
    raw = (url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = "https://" + raw
    try:
        host = urlparse(raw).hostname or ""
    except Exception:
        return None
    host = host.lower().removeprefix("www.")
    if not host:
        return None
    # grober Anzeigename: erste Domain-Label kapitalisieren
    label = host.split(".")[0]
    return label[:1].upper() + label[1:] if label else host


def list_shops(db: Session) -> list[Shop]:
    return list(db.scalars(select(Shop).order_by(Shop.name.asc())).all())


def create_shop(db: Session, name: str, domain_hint: str | None = None) -> Shop:
    shop = Shop(name=name.strip(), domain_hint=(domain_hint or "").strip() or None)
    db.add(shop)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Shop „{name}“ existiert bereits") from exc
    db.refresh(shop)
    return shop


def update_shop(db: Session, shop_id: int, name: str | None = None, domain_hint: str | None = None) -> Shop:
    shop = db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop nicht gefunden")
    if name is not None:
        shop.name = name.strip()
    if domain_hint is not None:
        shop.domain_hint = domain_hint.strip() or None
    shop.updated_at = _utcnow()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Shop-Name bereits vergeben") from exc
    db.refresh(shop)
    return shop


def delete_shop(db: Session, shop_id: int) -> None:
    shop = db.get(Shop, shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop nicht gefunden")
    if shop.sources:
        raise HTTPException(
            status_code=409,
            detail="Shop hat noch Bezugsquellen und kann nicht gelöscht werden",
        )
    db.delete(shop)
    db.commit()


def find_or_create_shop_for_url(db: Session, url: str, shop_name: str | None = None) -> Shop:
    suggested = (shop_name or "").strip() or shop_name_from_url(url) or "Shop"
    existing = db.scalars(select(Shop).where(Shop.name == suggested)).first()
    if existing:
        return existing
    # match by domain_hint
    try:
        host = urlparse(url if "://" in url else "https://" + url).hostname or ""
        host = host.lower().removeprefix("www.")
    except Exception:
        host = ""
    if host:
        by_domain = db.scalars(select(Shop).where(Shop.domain_hint == host)).first()
        if by_domain:
            return by_domain
    shop = Shop(name=suggested, domain_hint=host or None)
    db.add(shop)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        again = db.scalars(select(Shop).where(Shop.name == suggested)).first()
        if again:
            return again
        raise HTTPException(status_code=409, detail="Shop konnte nicht angelegt werden")
    return shop


def replace_material_sources(
    db: Session,
    material: Material,
    sources: list[dict],
) -> None:
    """Ersetzt alle Quellen eines Materials. sources: shop_id?, shop_name?, url, note?, is_preferred?"""
    material.purchase_sources.clear()
    db.flush()
    preferred_seen = False
    for raw in sources:
        url = str(raw.get("url") or "").strip()
        if not url:
            continue
        shop_id = raw.get("shop_id")
        shop_name = raw.get("shop_name")
        if shop_id:
            shop = db.get(Shop, int(shop_id))
            if not shop:
                raise HTTPException(status_code=400, detail=f"Shop #{shop_id} nicht gefunden")
        else:
            shop = find_or_create_shop_for_url(db, url, shop_name=shop_name)
        is_preferred = bool(raw.get("is_preferred"))
        if is_preferred:
            preferred_seen = True
        material.purchase_sources.append(
            MaterialPurchaseSource(
                shop_id=shop.id,
                url=url,
                note=(str(raw.get("note") or "").strip() or None),
                is_preferred=is_preferred,
            )
        )
    if material.purchase_sources and not preferred_seen:
        material.purchase_sources[0].is_preferred = True
    elif preferred_seen:
        # nur eine bevorzugt
        first_pref = True
        for src in material.purchase_sources:
            if src.is_preferred:
                if first_pref:
                    first_pref = False
                else:
                    src.is_preferred = False


def used_in_products(db: Session, material_id: int) -> list[dict]:
    rows = db.scalars(
        select(ProductMaterial)
        .where(ProductMaterial.material_id == material_id)
        .options(selectinload(ProductMaterial.product))
    ).all()
    seen: set[int] = set()
    out: list[dict] = []
    for link in rows:
        if not link.product or link.product.id in seen:
            continue
        seen.add(link.product.id)
        out.append({"id": link.product.id, "name": link.product.name})
    out.sort(key=lambda x: x["name"].casefold())
    return out


def preferred_source(material: Material) -> MaterialPurchaseSource | None:
    pref = next((s for s in material.purchase_sources if s.is_preferred), None)
    if pref:
        return pref
    return material.purchase_sources[0] if material.purchase_sources else None


def list_sources_overview(db: Session) -> list[dict]:
    shops = list_shops(db)
    sources = db.scalars(
        select(MaterialPurchaseSource)
        .options(
            selectinload(MaterialPurchaseSource.shop),
            selectinload(MaterialPurchaseSource.material),
        )
        .order_by(MaterialPurchaseSource.id.asc())
    ).all()
    by_shop: dict[int, list] = {s.id: [] for s in shops}
    orphan: list = []
    for src in sources:
        entry = {
            "id": src.id,
            "material_id": src.material_id,
            "material_name": src.material.name if src.material else "?",
            "shop_id": src.shop_id,
            "shop_name": src.shop.name if src.shop else "?",
            "url": src.url,
            "note": src.note,
            "is_preferred": src.is_preferred,
        }
        if src.shop_id in by_shop:
            by_shop[src.shop_id].append(entry)
        else:
            orphan.append(entry)
    groups = []
    for shop in shops:
        groups.append(
            {
                "shop_id": shop.id,
                "shop_name": shop.name,
                "domain_hint": shop.domain_hint,
                "sources": by_shop.get(shop.id, []),
            }
        )
    if orphan:
        groups.append({"shop_id": None, "shop_name": "Ohne Shop", "domain_hint": None, "sources": orphan})
    return groups
