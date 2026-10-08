"""Produktions-Tracking: Zeiten, Maschinen, Produktkosten (ADR 0030)."""

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
    ProductionProcess,
    ProductionStep,
    ProductionTimeTrack,
    User,
)

ENERGY_SETTING_KEY = "energy_eur_per_kwh"
ZERO = Decimal("0")


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


def track_duration_seconds(track: ProductionTimeTrack, *, now: datetime | None = None) -> Decimal:
    start = _ensure_aware(track.started_at)
    end = _ensure_aware(track.ended_at) if track.ended_at else _ensure_aware(now or _utcnow())
    secs = (end - start).total_seconds()
    return max(ZERO, _dec(secs))


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


# --- Processes / steps / tracks ---------------------------------------------


def _process_query():
    return select(ProductionProcess).options(
        selectinload(ProductionProcess.steps).selectinload(ProductionStep.tracks),
        selectinload(ProductionProcess.product),
    )


def get_process(db: Session, process_id: int) -> ProductionProcess:
    row = db.scalars(_process_query().where(ProductionProcess.id == process_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Prozess nicht gefunden")
    return row


def list_board(db: Session, *, status: str = "active") -> list[ProductionProcess]:
    q = _process_query().where(ProductionProcess.status == status).order_by(ProductionProcess.id.desc())
    return list(db.scalars(q).all())


def create_process(
    db: Session,
    user: User,
    *,
    title: str | None = None,
    product_id: int | None = None,
    quantity: Decimal | None = None,
) -> ProductionProcess:
    if product_id is not None and not db.get(Product, product_id):
        raise HTTPException(status_code=400, detail="Produkt nicht gefunden")
    row = ProductionProcess(
        title=(title.strip() if title and title.strip() else None),
        product_id=product_id,
        quantity=_qty(quantity),
        status="active",
        created_by_user_id=user.id,
    )
    db.add(row)
    db.commit()
    return get_process(db, row.id)


def update_process(
    db: Session,
    process_id: int,
    *,
    title: str | None = None,
    product_id: int | None = None,
    clear_product: bool = False,
    quantity: Decimal | None = None,
    clear_quantity: bool = False,
) -> ProductionProcess:
    row = get_process(db, process_id)
    if row.status != "active" and (title is not None or clear_product or product_id is not None):
        # allow quantity/title edits on done? keep simple: only active for structural edits
        pass
    if title is not None:
        row.title = title.strip() or None
    if clear_product:
        row.product_id = None
    elif product_id is not None:
        if not db.get(Product, product_id):
            raise HTTPException(status_code=400, detail="Produkt nicht gefunden")
        row.product_id = product_id
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
) -> ProductionProcess:
    process = get_process(db, process_id)
    if process.status != "active":
        raise HTTPException(status_code=400, detail="Abgeschlossener Prozess — Schritt nicht anlegbar")
    clean = name.strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Schrittname erforderlich")
    qty = _qty(quantity)
    if qty is None:
        qty = _qty(process.quantity)
    sort_hint = len(process.steps)
    db.add(
        ProductionStep(
            process_id=process.id,
            name=clean,
            quantity=qty,
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
) -> ProductionProcess:
    step = db.get(ProductionStep, step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Schritt nicht gefunden")
    if name is not None:
        clean = name.strip()
        if not clean:
            raise HTTPException(status_code=400, detail="Schrittname erforderlich")
        step.name = clean
    if clear_quantity:
        step.quantity = None
    elif quantity is not None:
        step.quantity = _qty(quantity)
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
        raise HTTPException(status_code=404, detail="Schritt nicht gefunden")
    if step.process.status != "active":
        raise HTTPException(status_code=400, detail="Prozess ist abgeschlossen")
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


def compute_process_unit_costs(
    db: Session,
    process: ProductionProcess,
    *,
    energy_tariff: Decimal | None = None,
    live_rates: bool = True,
) -> dict[str, Decimal]:
    """Summe (Zeiten÷Schrittmenge) × Tarife → Kosten pro Stück für diesen Prozess."""
    tariff = energy_tariff if energy_tariff is not None else get_energy_tariff(db)
    rate_cache: dict[int, Decimal] = {}
    power_cache: dict[int, Decimal | None] = {}
    labor_secs = ZERO
    machine_secs = ZERO
    labor_eur = ZERO
    energy_kwh = ZERO

    for step in process.steps:
        qty = step_quantity(step, process)
        if not qty:
            continue
        for track in step.tracks:
            if track.ended_at is None:
                continue
            secs = track_duration_seconds(track)
            hours = secs / Decimal("3600")
            per_unit_secs = secs / qty
            if track.kind == "labor":
                labor_secs += per_unit_secs
                rate = _rate_eur(db, track.labor_rate_id, rate_cache) if live_rates else _rate_eur(
                    db, track.labor_rate_id, rate_cache
                )
                labor_eur += (hours / qty) * rate
            elif track.kind == "machine":
                machine_secs += per_unit_secs
                power = _machine_power(db, track.machine_id, power_cache)
                if power is not None and power > 0:
                    kwh = hours * (power / Decimal("1000"))
                    energy_kwh += kwh / qty

    energy_eur = energy_kwh * tariff
    return {
        "labor_seconds_per_unit": labor_secs,
        "machine_seconds_per_unit": machine_secs,
        "labor_eur_per_unit": _money(labor_eur),
        "energy_kwh_per_unit": energy_kwh.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
        "energy_eur_per_unit": _money(energy_eur),
        "total_eur_per_unit": _money(labor_eur + energy_eur),
    }


def complete_process(db: Session, process_id: int) -> ProductionProcess:
    process = get_process(db, process_id)
    if process.status == "done":
        return process
    # stop open tracks
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

    if process.product_id:
        costs = compute_process_unit_costs(db, process)
        db.add(
            ProductCostSnapshot(
                product_id=process.product_id,
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


def current_product_cost(db: Session, product_id: int) -> dict[str, Any]:
    if not db.get(Product, product_id):
        raise HTTPException(status_code=404, detail="Produkt nicht gefunden")
    processes = list(
        db.scalars(
            _process_query().where(
                ProductionProcess.product_id == product_id,
                ProductionProcess.status == "done",
            )
        ).all()
    )
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
        # skip empty cost samples
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
