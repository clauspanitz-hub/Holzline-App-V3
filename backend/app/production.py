"""Produktions-Tracking: Läufe, Prozesse, Zeiten, Maschinen, Produktkosten (ADR 0030)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AppSetting,
    LaborRate,
    Machine,
    Product,
    ProductCostSnapshot,
    ProductFamily,
    ProductionProcess,
    ProductionStep,
    ProductionTimeTrack,
    User,
)

ENERGY_SETTING_KEY = "energy_eur_per_kwh"
ZERO = Decimal("0")
MAX_PROCESSES_PER_RUN = 10


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dec(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _qty(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    q = _dec(value)
    return q if q > 0 else None


def _secs_or_none(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    s = _dec(value)
    return s if s >= 0 else None


def get_energy_tariff(db: Session) -> Decimal:
    row = db.get(AppSetting, ENERGY_SETTING_KEY)
    if not row or not row.value.strip():
        return ZERO
    try:
        return max(ZERO, _dec(row.value))
    except Exception:
        return ZERO


def set_energy_tariff(db: Session, eur_per_kwh: Decimal) -> Decimal:
    value = max(ZERO, _dec(eur_per_kwh))
    row = db.get(AppSetting, ENERGY_SETTING_KEY)
    if row:
        row.value = str(value)
    else:
        db.add(AppSetting(key=ENERGY_SETTING_KEY, value=str(value)))
    db.commit()
    return value


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _secs_qty(value: Decimal | float | int) -> Decimal:
    """Sekunden auf Quantity-Schema (max. 3 Nachkommastellen) — verhindert Board-500."""
    return max(ZERO, _dec(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def track_duration_seconds(track: ProductionTimeTrack, *, now: datetime | None = None) -> Decimal:
    start = _ensure_aware(track.started_at)
    end = _ensure_aware(track.ended_at) if track.ended_at else _ensure_aware(now or _utcnow())
    secs = (end - start).total_seconds()
    return _secs_qty(secs)


def step_quantity(step: ProductionStep, process: ProductionProcess) -> Decimal | None:
    return _qty(step.quantity) or _qty(process.quantity)


# --- Labor rates / machines -------------------------------------------------


def list_labor_rates(db: Session) -> list[LaborRate]:
    return list(db.scalars(select(LaborRate).order_by(LaborRate.name)).all())


def create_labor_rate(db: Session, name: str, eur_per_hour: Decimal) -> LaborRate:
    clean = name.strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Name erforderlich")
    if db.scalars(select(LaborRate).where(LaborRate.name == clean)).first():
        raise HTTPException(status_code=400, detail="Stundensatz-Name bereits vergeben")
    row = LaborRate(name=clean, eur_per_hour=max(ZERO, _dec(eur_per_hour)))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_labor_rate(
    db: Session, rate_id: int, *, name: str | None = None, eur_per_hour: Decimal | None = None
) -> LaborRate:
    row = db.get(LaborRate, rate_id)
    if not row:
        raise HTTPException(status_code=404, detail="Stundensatz nicht gefunden")
    if name is not None:
        clean = name.strip()
        if not clean:
            raise HTTPException(status_code=400, detail="Name erforderlich")
        other = db.scalars(select(LaborRate).where(LaborRate.name == clean, LaborRate.id != rate_id)).first()
        if other:
            raise HTTPException(status_code=400, detail="Stundensatz-Name bereits vergeben")
        row.name = clean
    if eur_per_hour is not None:
        row.eur_per_hour = max(ZERO, _dec(eur_per_hour))
    row.updated_at = _utcnow()
    db.commit()
    db.refresh(row)
    return row


def delete_labor_rate(db: Session, rate_id: int) -> None:
    row = db.get(LaborRate, rate_id)
    if not row:
        raise HTTPException(status_code=404, detail="Stundensatz nicht gefunden")
    db.delete(row)
    db.commit()


def list_machines(db: Session) -> list[Machine]:
    return list(db.scalars(select(Machine).order_by(Machine.name)).all())


def create_machine(
    db: Session, name: str, *, note: str | None = None, power_w: Decimal | None = None
) -> Machine:
    clean = name.strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Name erforderlich")
    if db.scalars(select(Machine).where(Machine.name == clean)).first():
        raise HTTPException(status_code=400, detail="Maschinenname bereits vergeben")
    row = Machine(
        name=clean,
        note=(note.strip() if note and note.strip() else None),
        power_w=_dec(power_w) if power_w is not None else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_machine(
    db: Session,
    machine_id: int,
    *,
    name: str | None = None,
    note: str | None = None,
    power_w: Decimal | None = None,
    clear_power: bool = False,
) -> Machine:
    row = db.get(Machine, machine_id)
    if not row:
        raise HTTPException(status_code=404, detail="Maschine nicht gefunden")
    if name is not None:
        clean = name.strip()
        if not clean:
            raise HTTPException(status_code=400, detail="Name erforderlich")
        other = db.scalars(select(Machine).where(Machine.name == clean, Machine.id != machine_id)).first()
        if other:
            raise HTTPException(status_code=400, detail="Maschinenname bereits vergeben")
        row.name = clean
    if note is not None:
        row.note = note.strip() or None
    if clear_power:
        row.power_w = None
    elif power_w is not None:
        row.power_w = max(ZERO, _dec(power_w))
    row.updated_at = _utcnow()
    db.commit()
    db.refresh(row)
    return row


def delete_machine(db: Session, machine_id: int) -> None:
    row = db.get(Machine, machine_id)
    if not row:
        raise HTTPException(status_code=404, detail="Maschine nicht gefunden")
    db.delete(row)
    db.commit()


# --- Runs (Produktionsläufe) / processes (Prozesse) / tracks -----------------


def _process_query():
    return select(ProductionProcess).options(
        selectinload(ProductionProcess.steps).selectinload(ProductionStep.tracks),
        selectinload(ProductionProcess.product),
        selectinload(ProductionProcess.product_links),
        selectinload(ProductionProcess.family_links),
        selectinload(ProductionProcess.created_by),
    )


def get_process(db: Session, process_id: int) -> ProductionProcess:
    row = db.scalars(_process_query().where(ProductionProcess.id == process_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Produktionslauf nicht gefunden")
    return row


def list_board(db: Session, *, status: str = "active") -> list[ProductionProcess]:
    q = _process_query().where(ProductionProcess.status == status).order_by(ProductionProcess.id.desc())
    return list(db.scalars(q).all())


def _family_ids_expanded(db: Session, family_ids: list[int]) -> set[int]:
    """Elternfamilie schließt Unterfamilien-IDs ein."""
    if not family_ids:
        return set()
    expanded: set[int] = set(family_ids)
    children = db.scalars(
        select(ProductFamily).where(ProductFamily.parent_id.in_(list(expanded)))
    ).all()
    for child in children:
        expanded.add(child.id)
    return expanded


def _resolve_products(db: Session, product_ids: list[int] | None) -> list[Product]:
    if not product_ids:
        return []
    unique = list(dict.fromkeys(int(pid) for pid in product_ids))
    rows = list(db.scalars(select(Product).where(Product.id.in_(unique))).all())
    found = {p.id for p in rows}
    missing = [pid for pid in unique if pid not in found]
    if missing:
        raise HTTPException(status_code=400, detail=f"Produkt nicht gefunden: {missing[0]}")
    # preserve order
    by_id = {p.id: p for p in rows}
    return [by_id[pid] for pid in unique]


def _resolve_families(db: Session, family_ids: list[int] | None) -> list[ProductFamily]:
    if not family_ids:
        return []
    unique = list(dict.fromkeys(int(fid) for fid in family_ids))
    rows = list(db.scalars(select(ProductFamily).where(ProductFamily.id.in_(unique))).all())
    found = {f.id for f in rows}
    missing = [fid for fid in unique if fid not in found]
    if missing:
        raise HTTPException(status_code=400, detail=f"Produktfamilie nicht gefunden: {missing[0]}")
    by_id = {f.id: f for f in rows}
    return [by_id[fid] for fid in unique]


def _set_run_links(
    db: Session,
    row: ProductionProcess,
    *,
    product_ids: list[int] | None = None,
    family_ids: list[int] | None = None,
    legacy_product_id: int | None = None,
    clear_links: bool = False,
) -> None:
    if clear_links:
        row.product_links = []
        row.family_links = []
        row.product_id = None
        return

    if product_ids is not None or legacy_product_id is not None:
        ids = list(product_ids) if product_ids is not None else []
        if legacy_product_id is not None and legacy_product_id not in ids:
            ids = [legacy_product_id, *ids]
        row.product_links = _resolve_products(db, ids)
        row.product_id = row.product_links[0].id if row.product_links else None

    if family_ids is not None:
        row.family_links = _resolve_families(db, family_ids)


def linked_product_ids(db: Session, process: ProductionProcess) -> set[int]:
    """Alle Produkttypen, die denselben Kosten-Satz dieses Laufs erhalten (Q19 A)."""
    ids: set[int] = {p.id for p in (process.product_links or [])}
    if process.product_id:
        ids.add(process.product_id)
    fam_ids = [f.id for f in (process.family_links or [])]
    if fam_ids:
        expanded = _family_ids_expanded(db, fam_ids)
        for pid in db.scalars(select(Product.id).where(Product.family_id.in_(expanded))).all():
            ids.add(pid)
    return ids


def create_process(
    db: Session,
    user: User,
    *,
    title: str | None = None,
    product_id: int | None = None,
    product_ids: list[int] | None = None,
    family_ids: list[int] | None = None,
    quantity: Decimal | None = None,
) -> ProductionProcess:
    row = ProductionProcess(
        title=(title.strip() if title and title.strip() else None),
        quantity=_qty(quantity),
        status="active",
        created_by_user_id=user.id,
    )
    db.add(row)
    db.flush()
    _set_run_links(
        db,
        row,
        product_ids=product_ids,
        family_ids=family_ids,
        legacy_product_id=product_id,
    )
    db.commit()
    return get_process(db, row.id)


def update_process(
    db: Session,
    process_id: int,
    *,
    title: str | None = None,
    product_id: int | None = None,
    clear_product: bool = False,
    product_ids: list[int] | None = None,
    family_ids: list[int] | None = None,
    clear_links: bool = False,
    quantity: Decimal | None = None,
    clear_quantity: bool = False,
) -> ProductionProcess:
    row = get_process(db, process_id)
    if title is not None:
        row.title = title.strip() or None
    if clear_links or clear_product:
        _set_run_links(db, row, clear_links=True)
    elif product_ids is not None or family_ids is not None or product_id is not None:
        # Legacy product_id allein = Produkte ersetzen; product_ids explizit setzen
        if product_ids is not None:
            pids = product_ids
            legacy = None
        elif product_id is not None:
            pids = [product_id]
            legacy = None
        else:
            pids = [p.id for p in row.product_links]
            legacy = None
        fids = family_ids if family_ids is not None else [f.id for f in row.family_links]
        _set_run_links(db, row, product_ids=pids, family_ids=fids, legacy_product_id=legacy)
    if clear_quantity:
        row.quantity = None
    elif quantity is not None:
        row.quantity = _qty(quantity)
    row.updated_at = _utcnow()
    db.commit()
    return get_process(db, process_id)


def add_step(
    db: Session,
    process_id: int,
    name: str,
    *,
    quantity: Decimal | None = None,
    estimated_labor_seconds: Decimal | None = None,
    estimated_machine_seconds: Decimal | None = None,
) -> ProductionProcess:
    process = get_process(db, process_id)
    if process.status != "active":
        raise HTTPException(status_code=400, detail="Abgeschlossener Lauf — Prozess nicht anlegbar")
    if len(process.steps) >= MAX_PROCESSES_PER_RUN:
        raise HTTPException(
            status_code=400,
            detail=f"Maximal {MAX_PROCESSES_PER_RUN} Prozesse pro Produktionslauf",
        )
    clean = name.strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Prozessname erforderlich")
    qty = _qty(quantity)
    if qty is None:
        qty = _qty(process.quantity)
    sort_hint = len(process.steps)
    db.add(
        ProductionStep(
            process_id=process.id,
            name=clean,
            quantity=qty,
            estimated_labor_seconds=_secs_or_none(estimated_labor_seconds),
            estimated_machine_seconds=_secs_or_none(estimated_machine_seconds),
            sort_hint=sort_hint,
        )
    )
    process.updated_at = _utcnow()
    db.commit()
    return get_process(db, process_id)


def update_step(
    db: Session,
    step_id: int,
    *,
    name: str | None = None,
    quantity: Decimal | None = None,
    clear_quantity: bool = False,
    estimated_labor_seconds: Decimal | None = None,
    clear_estimated_labor: bool = False,
    estimated_machine_seconds: Decimal | None = None,
    clear_estimated_machine: bool = False,
) -> ProductionProcess:
    step = db.get(ProductionStep, step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Prozess nicht gefunden")
    if name is not None:
        clean = name.strip()
        if not clean:
            raise HTTPException(status_code=400, detail="Prozessname erforderlich")
        step.name = clean
    if clear_quantity:
        step.quantity = None
    elif quantity is not None:
        step.quantity = _qty(quantity)
    if clear_estimated_labor:
        step.estimated_labor_seconds = None
    elif estimated_labor_seconds is not None:
        step.estimated_labor_seconds = _secs_or_none(estimated_labor_seconds)
    if clear_estimated_machine:
        step.estimated_machine_seconds = None
    elif estimated_machine_seconds is not None:
        step.estimated_machine_seconds = _secs_or_none(estimated_machine_seconds)
    step.updated_at = _utcnow()
    step.process.updated_at = _utcnow()
    db.commit()
    return get_process(db, step.process_id)


def start_track(
    db: Session,
    user: User,
    step_id: int,
    kind: str,
    *,
    machine_id: int | None = None,
    labor_rate_id: int | None = None,
    started_at: datetime | None = None,
) -> ProductionProcess:
    if kind not in ("labor", "machine"):
        raise HTTPException(status_code=400, detail="kind muss labor oder machine sein")
    step = db.get(ProductionStep, step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Prozess nicht gefunden")
    if step.process.status != "active":
        raise HTTPException(status_code=400, detail="Produktionslauf ist abgeschlossen")
    open_same = db.scalars(
        select(ProductionTimeTrack).where(
            ProductionTimeTrack.step_id == step_id,
            ProductionTimeTrack.kind == kind,
            ProductionTimeTrack.ended_at.is_(None),
        )
    ).first()
    if open_same:
        raise HTTPException(
            status_code=400,
            detail="Zeitspur läuft bereits — zuerst stoppen",
        )
    rate_id = labor_rate_id
    if kind == "labor":
        if rate_id is None:
            rate_id = user.labor_rate_id
        if rate_id is not None and not db.get(LaborRate, rate_id):
            raise HTTPException(status_code=400, detail="Stundensatz nicht gefunden")
    mid = None
    if kind == "machine":
        if machine_id is None:
            raise HTTPException(status_code=400, detail="Maschine wählen")
        if not db.get(Machine, machine_id):
            raise HTTPException(status_code=400, detail="Maschine nicht gefunden")
        mid = machine_id
    track = ProductionTimeTrack(
        step_id=step.id,
        kind=kind,
        machine_id=mid,
        labor_rate_id=rate_id if kind == "labor" else None,
        user_id=user.id,
        started_at=_ensure_aware(started_at) if started_at else _utcnow(),
    )
    db.add(track)
    step.process.updated_at = _utcnow()
    db.commit()
    return get_process(db, step.process_id)


def stop_track(db: Session, track_id: int, *, ended_at: datetime | None = None) -> ProductionProcess:
    track = db.get(ProductionTimeTrack, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Zeitspur nicht gefunden")
    if track.ended_at is not None:
        raise HTTPException(status_code=400, detail="Zeitspur bereits gestoppt")
    end = _ensure_aware(ended_at) if ended_at else _utcnow()
    if end < _ensure_aware(track.started_at):
        raise HTTPException(status_code=400, detail="Ende vor Start")
    track.ended_at = end
    track.updated_at = _utcnow()
    track.step.process.updated_at = _utcnow()
    db.commit()
    return get_process(db, track.step.process_id)


def update_track(
    db: Session,
    track_id: int,
    *,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    clear_ended: bool = False,
    labor_rate_id: int | None = None,
    clear_labor_rate: bool = False,
    machine_id: int | None = None,
) -> ProductionProcess:
    track = db.get(ProductionTimeTrack, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Zeitspur nicht gefunden")
    if started_at is not None:
        track.started_at = _ensure_aware(started_at)
    if clear_ended:
        track.ended_at = None
    elif ended_at is not None:
        track.ended_at = _ensure_aware(ended_at)
    if track.kind == "labor":
        if clear_labor_rate:
            track.labor_rate_id = None
        elif labor_rate_id is not None:
            if not db.get(LaborRate, labor_rate_id):
                raise HTTPException(status_code=400, detail="Stundensatz nicht gefunden")
            track.labor_rate_id = labor_rate_id
    if track.kind == "machine" and machine_id is not None:
        if not db.get(Machine, machine_id):
            raise HTTPException(status_code=400, detail="Maschine nicht gefunden")
        track.machine_id = machine_id
    if track.ended_at and _ensure_aware(track.ended_at) < _ensure_aware(track.started_at):
        raise HTTPException(status_code=400, detail="Ende vor Start")
    track.updated_at = _utcnow()
    track.step.process.updated_at = _utcnow()
    db.commit()
    return get_process(db, track.step.process_id)


# --- Costing ----------------------------------------------------------------


def _rate_eur(db: Session, rate_id: int | None, cache: dict[int, Decimal]) -> Decimal:
    if rate_id is None:
        return ZERO
    if rate_id in cache:
        return cache[rate_id]
    row = db.get(LaborRate, rate_id)
    val = _dec(row.eur_per_hour) if row else ZERO
    cache[rate_id] = val
    return val


def _machine_power(db: Session, machine_id: int | None, cache: dict[int, Decimal | None]) -> Decimal | None:
    if machine_id is None:
        return None
    if machine_id in cache:
        return cache[machine_id]
    row = db.get(Machine, machine_id)
    val = _dec(row.power_w) if row and row.power_w is not None else None
    cache[machine_id] = val
    return val


def measured_step_seconds(step: ProductionStep, kind: str) -> Decimal:
    total = ZERO
    for track in step.tracks:
        if track.kind != kind or track.ended_at is None:
            continue
        total += track_duration_seconds(track)
    return total


def has_completed_tracks(step: ProductionStep, kind: str) -> bool:
    return any(t.kind == kind and t.ended_at is not None for t in step.tracks)


def effective_step_seconds(step: ProductionStep, kind: str) -> Decimal:
    """Messung wenn vorhanden, sonst Schätzung (Q20 A)."""
    if has_completed_tracks(step, kind):
        return measured_step_seconds(step, kind)
    if kind == "labor":
        raw = _dec(step.estimated_labor_seconds) if step.estimated_labor_seconds is not None else ZERO
    else:
        raw = _dec(step.estimated_machine_seconds) if step.estimated_machine_seconds is not None else ZERO
    return _secs_qty(raw)


def compute_process_unit_costs(
    db: Session,
    process: ProductionProcess,
    *,
    energy_tariff: Decimal | None = None,
    live_rates: bool = True,
) -> dict[str, Decimal]:
    """Summe (effektive Zeiten÷Prozessmenge) × Tarife → Kosten pro Stück für diesen Lauf."""
    del live_rates  # immer aktuelle Tarife / Track-Sätze
    tariff = energy_tariff if energy_tariff is not None else get_energy_tariff(db)
    rate_cache: dict[int, Decimal] = {}
    power_cache: dict[int, Decimal | None] = {}
    labor_secs = ZERO
    machine_secs = ZERO
    labor_eur = ZERO
    energy_kwh = ZERO

    fallback_rate_id = None
    if process.created_by and process.created_by.labor_rate_id:
        fallback_rate_id = process.created_by.labor_rate_id

    for step in process.steps:
        qty = step_quantity(step, process)
        if not qty:
            continue

        # --- Labor ---
        if has_completed_tracks(step, "labor"):
            for track in step.tracks:
                if track.kind != "labor" or track.ended_at is None:
                    continue
                secs = track_duration_seconds(track)
                hours = secs / Decimal("3600")
                labor_secs += secs / qty
                rate = _rate_eur(db, track.labor_rate_id, rate_cache)
                labor_eur += (hours / qty) * rate
        else:
            est = _dec(step.estimated_labor_seconds) if step.estimated_labor_seconds is not None else ZERO
            if est > 0:
                labor_secs += est / qty
                rate = _rate_eur(db, fallback_rate_id, rate_cache)
                labor_eur += ((est / Decimal("3600")) / qty) * rate

        # --- Machine ---
        if has_completed_tracks(step, "machine"):
            for track in step.tracks:
                if track.kind != "machine" or track.ended_at is None:
                    continue
                secs = track_duration_seconds(track)
                hours = secs / Decimal("3600")
                machine_secs += secs / qty
                power = _machine_power(db, track.machine_id, power_cache)
                if power is not None and power > 0:
                    kwh = hours * (power / Decimal("1000"))
                    energy_kwh += kwh / qty
        else:
            est = _dec(step.estimated_machine_seconds) if step.estimated_machine_seconds is not None else ZERO
            if est > 0:
                machine_secs += est / qty
                # ohne Maschinen-Track keine Leistung → Energie 0 aus Schätzung

    energy_eur = energy_kwh * tariff
    return {
        "labor_seconds_per_unit": _secs_qty(labor_secs),
        "machine_seconds_per_unit": _secs_qty(machine_secs),
        "labor_eur_per_unit": _money(labor_eur),
        "energy_kwh_per_unit": energy_kwh.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
        "energy_eur_per_unit": _money(energy_eur),
        "total_eur_per_unit": _money(labor_eur + energy_eur),
    }


def complete_process(db: Session, process_id: int) -> ProductionProcess:
    process = get_process(db, process_id)
    if process.status == "done":
        return process
    now = _utcnow()
    for step in process.steps:
        for track in step.tracks:
            if track.ended_at is None:
                track.ended_at = now
                track.updated_at = now
    process.status = "done"
    process.completed_at = now
    process.updated_at = now
    db.flush()

    target_ids = linked_product_ids(db, process)
    if target_ids:
        costs = compute_process_unit_costs(db, process)
        for pid in sorted(target_ids):
            db.add(
                ProductCostSnapshot(
                    product_id=pid,
                    process_id=process.id,
                    captured_at=now,
                    labor_seconds_per_unit=costs["labor_seconds_per_unit"],
                    machine_seconds_per_unit=costs["machine_seconds_per_unit"],
                    labor_eur_per_unit=costs["labor_eur_per_unit"],
                    energy_kwh_per_unit=costs["energy_kwh_per_unit"],
                    energy_eur_per_unit=costs["energy_eur_per_unit"],
                    total_eur_per_unit=costs["total_eur_per_unit"],
                )
            )
    db.commit()
    return get_process(db, process_id)


def _runs_for_product(db: Session, product_id: int) -> list[ProductionProcess]:
    """Abgeschlossene Läufe, die diesem Produkttyp zugeordnet sind (direkt oder via Familie)."""
    product = db.get(Product, product_id)
    if not product:
        return []
    family_match_ids: set[int] = set()
    if product.family_id:
        fam = db.get(ProductFamily, product.family_id)
        if fam:
            family_match_ids.add(fam.id)
            if fam.parent_id:
                family_match_ids.add(fam.parent_id)

    candidates = list(
        db.scalars(
            _process_query().where(ProductionProcess.status == "done")
        ).all()
    )
    matched: list[ProductionProcess] = []
    for process in candidates:
        link_ids = {p.id for p in (process.product_links or [])}
        if process.product_id:
            link_ids.add(process.product_id)
        if product_id in link_ids:
            matched.append(process)
            continue
        fam_ids = {f.id for f in (process.family_links or [])}
        if fam_ids & family_match_ids:
            matched.append(process)
    return matched


def current_product_cost(db: Session, product_id: int) -> dict[str, Any]:
    if not db.get(Product, product_id):
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    processes = _runs_for_product(db, product_id)
    if not processes:
        return {
            "product_id": product_id,
            "sample_count": 0,
            "labor_seconds_per_unit": ZERO,
            "machine_seconds_per_unit": ZERO,
            "labor_eur_per_unit": ZERO,
            "energy_kwh_per_unit": ZERO,
            "energy_eur_per_unit": ZERO,
            "total_eur_per_unit": ZERO,
        }
    tariff = get_energy_tariff(db)
    totals = {
        "labor_seconds_per_unit": ZERO,
        "machine_seconds_per_unit": ZERO,
        "labor_eur_per_unit": ZERO,
        "energy_kwh_per_unit": ZERO,
        "energy_eur_per_unit": ZERO,
        "total_eur_per_unit": ZERO,
    }
    counted = 0
    for process in processes:
        costs = compute_process_unit_costs(db, process, energy_tariff=tariff, live_rates=True)
        if (
            costs["labor_seconds_per_unit"] == ZERO
            and costs["machine_seconds_per_unit"] == ZERO
            and costs["total_eur_per_unit"] == ZERO
        ):
            continue
        counted += 1
        for key in totals:
            totals[key] += costs[key]
    if counted == 0:
        return {
            "product_id": product_id,
            "sample_count": 0,
            **{k: ZERO for k in totals},
        }
    n = Decimal(counted)
    return {
        "product_id": product_id,
        "sample_count": counted,
        "labor_seconds_per_unit": (totals["labor_seconds_per_unit"] / n).quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        ),
        "machine_seconds_per_unit": (totals["machine_seconds_per_unit"] / n).quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        ),
        "labor_eur_per_unit": _money(totals["labor_eur_per_unit"] / n),
        "energy_kwh_per_unit": (totals["energy_kwh_per_unit"] / n).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        ),
        "energy_eur_per_unit": _money(totals["energy_eur_per_unit"] / n),
        "total_eur_per_unit": _money(totals["total_eur_per_unit"] / n),
    }


def list_product_cost_history(db: Session, product_id: int) -> list[ProductCostSnapshot]:
    if not db.get(Product, product_id):
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    return list(
        db.scalars(
            select(ProductCostSnapshot)
            .where(ProductCostSnapshot.product_id == product_id)
            .order_by(ProductCostSnapshot.captured_at.desc())
        ).all()
    )


def _products_in_family(db: Session, family_id: int) -> list[Product]:
    family = db.get(ProductFamily, family_id)
    if not family:
        raise HTTPException(status_code=404, detail="Produktfamilie nicht gefunden")
    expanded = _family_ids_expanded(db, [family_id])
    return list(
        db.scalars(select(Product).where(Product.family_id.in_(expanded)).order_by(Product.name)).all()
    )


def current_family_cost(db: Session, family_id: int) -> dict[str, Any]:
    """Familien-Ø der Produktkosten; bei abweichenden Einzelwerten Durchschnitt (Q22 A)."""
    products = _products_in_family(db, family_id)
    family = db.get(ProductFamily, family_id)
    assert family is not None
    items: list[dict[str, Any]] = []
    for product in products:
        cost = current_product_cost(db, product.id)
        items.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "sample_count": cost["sample_count"],
                "total_eur_per_unit": cost["total_eur_per_unit"],
                "labor_eur_per_unit": cost["labor_eur_per_unit"],
                "energy_eur_per_unit": cost["energy_eur_per_unit"],
            }
        )
    with_samples = [i for i in items if i["sample_count"] > 0]
    if not with_samples:
        return {
            "family_id": family_id,
            "family_name": family.name,
            "product_count": len(items),
            "sample_product_count": 0,
            "prices_differ": False,
            "avg_total_eur_per_unit": ZERO,
            "avg_labor_eur_per_unit": ZERO,
            "avg_energy_eur_per_unit": ZERO,
            "products": items,
        }
    n = Decimal(len(with_samples))
    avg_total = _money(sum((i["total_eur_per_unit"] for i in with_samples), ZERO) / n)
    avg_labor = _money(sum((i["labor_eur_per_unit"] for i in with_samples), ZERO) / n)
    avg_energy = _money(sum((i["energy_eur_per_unit"] for i in with_samples), ZERO) / n)
    distinct = {str(i["total_eur_per_unit"]) for i in with_samples}
    return {
        "family_id": family_id,
        "family_name": family.name,
        "product_count": len(items),
        "sample_product_count": len(with_samples),
        "prices_differ": len(distinct) > 1,
        "avg_total_eur_per_unit": avg_total,
        "avg_labor_eur_per_unit": avg_labor,
        "avg_energy_eur_per_unit": avg_energy,
        "products": items,
    }
