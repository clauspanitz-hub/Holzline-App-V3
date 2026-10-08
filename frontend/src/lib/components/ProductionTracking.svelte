<script>
  import { formatMoney, formatDateTime } from '../api.js'

  let {
    api,
    products = [],
    authUser = null,
    isAdmin = false,
    onToast = (_msg, _kind) => {},
  } = $props()

  let board = $state([])
  let machines = $state([])
  let laborRates = $state([])
  let settings = $state({ energy_eur_per_kwh: 0 })
  let users = $state([])
  let loading = $state(false)
  let adminOpen = $state(false)
  let costProductId = $state('')
  let costCurrent = $state(null)
  let costHistory = $state([])

  let newProcess = $state({ title: '', product_id: '', quantity: '' })
  let stepDrafts = $state({}) // processId -> { name, quantity }
  let machineDraft = $state({ name: '', note: '', power_w: '' })
  let rateDraft = $state({ name: '', eur_per_hour: '' })
  let energyDraft = $state('')
  let tick = $state(0)

  $effect(() => {
    const id = setInterval(() => {
      tick += 1
    }, 1000)
    return () => clearInterval(id)
  })

  export async function reload() {
    loading = true
    try {
      const tasks = [
        api.production.board('active'),
        api.machines.list(),
        api.laborRates.list(),
        api.production.settings(),
      ]
      if (isAdmin) tasks.push(api.users.list())
      const [b, m, r, s, u] = await Promise.all(tasks)
      board = b
      machines = m
      laborRates = r
      settings = s
      energyDraft = String(s.energy_eur_per_kwh ?? '')
      if (u) users = u
    } catch (e) {
      onToast(e.message || 'Laden fehlgeschlagen', 'error')
    } finally {
      loading = false
    }
  }

  $effect(() => {
    void api
    void isAdmin
    reload()
  })

  function ensureDraft(processId) {
    if (!stepDrafts[processId]) {
      stepDrafts = { ...stepDrafts, [processId]: { name: '', quantity: '' } }
    }
  }

  function draftName(processId) {
    ensureDraft(processId)
    return stepDrafts[processId]?.name ?? ''
  }

  function setDraftName(processId, value) {
    ensureDraft(processId)
    stepDrafts = {
      ...stepDrafts,
      [processId]: { ...stepDrafts[processId], name: value },
    }
  }

  function draftQty(processId) {
    ensureDraft(processId)
    return stepDrafts[processId]?.quantity ?? ''
  }

  function setDraftQty(processId, value) {
    ensureDraft(processId)
    stepDrafts = {
      ...stepDrafts,
      [processId]: { ...stepDrafts[processId], quantity: value },
    }
  }

  function fmtDuration(startedAt, endedAt) {
    void tick
    const start = new Date(startedAt).getTime()
    const end = endedAt ? new Date(endedAt).getTime() : Date.now()
    let secs = Math.max(0, Math.floor((end - start) / 1000))
    const h = Math.floor(secs / 3600)
    secs %= 3600
    const m = Math.floor(secs / 60)
    const s = secs % 60
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    return `${m}:${String(s).padStart(2, '0')}`
  }

  function fmtSecs(secs) {
    const n = Number(secs)
    if (!Number.isFinite(n) || n <= 0) return '—'
    const m = Math.round(n / 60)
    if (m < 60) return `${m} Min`
    const h = Math.floor(m / 60)
    const rm = m % 60
    return `${h}h ${rm}m`
  }

  async function createProcess() {
    try {
      const body = {
        title: newProcess.title.trim() || null,
        product_id: newProcess.product_id ? Number(newProcess.product_id) : null,
        quantity: newProcess.quantity !== '' ? Number(newProcess.quantity) : null,
      }
      await api.production.createProcess(body)
      newProcess = { title: '', product_id: '', quantity: '' }
      await reload()
      onToast('Prozess gestartet', 'ok')
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  async function patchProcess(id, body) {
    try {
      await api.production.updateProcess(id, body)
      await reload()
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  async function addStep(processId) {
    ensureDraft(processId)
    const d = stepDrafts[processId]
    if (!d.name.trim()) {
      onToast('Schrittname fehlt', 'error')
      return
    }
    try {
      await api.production.addStep(processId, {
        name: d.name.trim(),
        quantity: d.quantity !== '' ? Number(d.quantity) : null,
      })
      stepDrafts = { ...stepDrafts, [processId]: { name: '', quantity: '' } }
      await reload()
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  async function startLabor(stepId) {
    try {
      await api.production.startTrack(stepId, { kind: 'labor' })
      await reload()
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  async function startMachine(stepId, machineId) {
    if (!machineId) {
      onToast('Maschine wählen', 'error')
      return
    }
    try {
      await api.production.startTrack(stepId, { kind: 'machine', machine_id: Number(machineId) })
      await reload()
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  async function stopTrack(trackId) {
    try {
      await api.production.stopTrack(trackId)
      await reload()
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  async function completeProcess(id) {
    try {
      await api.production.completeProcess(id)
      await reload()
      onToast('Prozess abgeschlossen', 'ok')
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  async function saveMachine() {
    if (!machineDraft.name.trim()) return
    try {
      await api.machines.create({
        name: machineDraft.name.trim(),
        note: machineDraft.note.trim() || null,
        power_w: machineDraft.power_w !== '' ? Number(machineDraft.power_w) : null,
      })
      machineDraft = { name: '', note: '', power_w: '' }
      await reload()
      onToast('Maschine angelegt', 'ok')
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  async function saveRate() {
    if (!rateDraft.name.trim()) return
    try {
      await api.laborRates.create({
        name: rateDraft.name.trim(),
        eur_per_hour: Number(rateDraft.eur_per_hour || 0),
      })
      rateDraft = { name: '', eur_per_hour: '' }
      await reload()
      onToast('Stundensatz angelegt', 'ok')
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  async function saveEnergy() {
    try {
      await api.production.updateSettings({ energy_eur_per_kwh: Number(energyDraft || 0) })
      await reload()
      onToast('Stromtarif gespeichert', 'ok')
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  async function setUserRate(userId, laborRateId) {
    try {
      if (!laborRateId) {
        await api.users.update(userId, { clear_labor_rate: true })
      } else {
        await api.users.update(userId, { labor_rate_id: Number(laborRateId) })
      }
      await reload()
      onToast('Stundensatz am Benutzer gesetzt', 'ok')
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  async function loadCosts() {
    if (!costProductId) {
      costCurrent = null
      costHistory = []
      return
    }
    try {
      const id = Number(costProductId)
      costCurrent = await api.production.productCost(id)
      costHistory = await api.production.productCostHistory(id)
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  let machinePick = $state({})
</script>

<section class="panel">
  <div class="panel-header">
    <h2>Produktion</h2>
    <div class="row-actions">
      <button type="button" class="btn secondary compact" onclick={() => reload()} disabled={loading}>Aktualisieren</button>
      {#if isAdmin}
        <button type="button" class="btn secondary compact" onclick={() => (adminOpen = !adminOpen)}>
          {adminOpen ? 'Stammdaten zu' : 'Stammdaten'}
        </button>
      {/if}
    </div>
  </div>
  <p class="empty" style="margin-top:0">
    Parallele Prozesse und Schritte timen (Arbeitszeit + Maschinenzeit). Mengen je Prozess/Schritt wählbar.
    Kein Fertigen/Lager — nur Zeit und Kosten.
  </p>

  {#if isAdmin && adminOpen}
    <div class="panel" style="margin:1rem 0;padding:1rem">
      <h3 style="margin-top:0">Stammdaten (Admin)</h3>
      <div class="form-grid">
        <label>Stromtarif (€/kWh)
          <input type="number" step="0.0001" min="0" bind:value={energyDraft} />
        </label>
        <div class="row-actions" style="align-self:end">
          <button type="button" class="btn" onclick={saveEnergy}>Tarif speichern</button>
        </div>
      </div>

      <h4>Maschinen</h4>
      <div class="form-grid">
        <label>Name <input bind:value={machineDraft.name} /></label>
        <label>Notiz <input bind:value={machineDraft.note} /></label>
        <label>Leistung (W) <input type="number" min="0" step="1" bind:value={machineDraft.power_w} /></label>
        <div class="row-actions" style="align-self:end">
          <button type="button" class="btn secondary" onclick={saveMachine}>Anlegen</button>
        </div>
      </div>
      {#if machines.length}
        <ul class="compact-list">
          {#each machines as m}
            <li>{m.name}{#if m.power_w != null} · {m.power_w} W{/if}{#if m.note} — {m.note}{/if}</li>
          {/each}
        </ul>
      {/if}

      <h4>Stundensätze</h4>
      <div class="form-grid">
        <label>Name <input bind:value={rateDraft.name} /></label>
        <label>€/h <input type="number" min="0" step="0.01" bind:value={rateDraft.eur_per_hour} /></label>
        <div class="row-actions" style="align-self:end">
          <button type="button" class="btn secondary" onclick={saveRate}>Anlegen</button>
        </div>
      </div>
      {#if laborRates.length}
        <ul class="compact-list">
          {#each laborRates as r}
            <li>{r.name}: {formatMoney(r.eur_per_hour)}/h</li>
          {/each}
        </ul>
      {/if}

      <h4>Default-Satz je Benutzer</h4>
      {#each users as u}
        <label class="inline-assign">{u.username}
          <select
            value={u.labor_rate_id ?? ''}
            onchange={(e) => setUserRate(u.id, e.currentTarget.value)}
          >
            <option value="">— keiner —</option>
            {#each laborRates as r}
              <option value={r.id}>{r.name}</option>
            {/each}
          </select>
        </label>
      {/each}
    </div>
  {/if}

  <div class="form-grid" style="margin-top:1rem">
    <label>Titel (optional)
      <input bind:value={newProcess.title} placeholder="z. B. Ringe Charge" />
    </label>
    <label>Produkt (optional)
      <select bind:value={newProcess.product_id}>
        <option value="">— frei —</option>
        {#each products as p}
          <option value={p.id}>{p.name}</option>
        {/each}
      </select>
    </label>
    <label>Stückzahl Prozess
      <input type="number" min="0" step="1" bind:value={newProcess.quantity} placeholder="optional" />
    </label>
    <div class="row-actions" style="align-self:end">
      <button type="button" class="btn" onclick={createProcess}>Prozess starten</button>
    </div>
  </div>
</section>

{#if !board.length}
  <p class="empty">Keine aktiven Prozesse — starte einen oben.</p>
{:else}
  {#each board as proc}
    <section class="panel process-card">
      <div class="panel-header">
        <h3>{proc.title || proc.product_name || `Prozess #${proc.id}`}</h3>
        <button type="button" class="btn secondary compact" onclick={() => completeProcess(proc.id)}>Abschließen</button>
      </div>
      <div class="form-grid">
        <label>Produkt
          <select
            value={proc.product_id ?? ''}
            onchange={(e) => {
              const v = e.currentTarget.value
              if (!v) patchProcess(proc.id, { clear_product: true })
              else patchProcess(proc.id, { product_id: Number(v) })
            }}
          >
            <option value="">— frei —</option>
            {#each products as p}
              <option value={p.id}>{p.name}</option>
            {/each}
          </select>
        </label>
        <label>Stückzahl Prozess
          <input
            type="number"
            min="0"
            step="1"
            value={proc.quantity ?? ''}
            onchange={(e) => {
              const v = e.currentTarget.value
              if (v === '') patchProcess(proc.id, { clear_quantity: true })
              else patchProcess(proc.id, { quantity: Number(v) })
            }}
          />
        </label>
      </div>

      {#each proc.steps as step}
        <div class="step-block">
          <div class="step-head">
            <strong>{step.name}</strong>
            <span class="muted">Menge: {step.quantity ?? proc.quantity ?? '—'}</span>
          </div>
          <div class="track-list">
            {#each step.tracks as track}
              <div class="track-row" class:running={track.running}>
                <span class="chip">{track.kind === 'labor' ? 'Arbeit' : 'Maschine'}</span>
                {#if track.kind === 'machine' && track.machine_id}
                  <span class="muted">{machines.find((m) => m.id === track.machine_id)?.name || `#${track.machine_id}`}</span>
                {/if}
                <span class="timer">{fmtDuration(track.started_at, track.ended_at)}</span>
                {#if track.running}
                  <button type="button" class="btn compact" onclick={() => stopTrack(track.id)}>Stop</button>
                {:else}
                  <span class="muted">bis {formatDateTime(track.ended_at)}</span>
                {/if}
              </div>
            {/each}
          </div>
          <div class="row-actions wrap">
            <button type="button" class="btn secondary compact" onclick={() => startLabor(step.id)}>Arbeit Start</button>
            <select bind:value={machinePick[step.id]}>
              <option value="">Maschine…</option>
              {#each machines as m}
                <option value={m.id}>{m.name}</option>
              {/each}
            </select>
            <button
              type="button"
              class="btn secondary compact"
              onclick={() => startMachine(step.id, machinePick[step.id])}
            >Maschine Start</button>
          </div>
        </div>
      {/each}

      <div class="form-grid" style="margin-top:0.75rem">
        <label>Schritt hinzufügen
          <input
            value={draftName(proc.id)}
            oninput={(e) => setDraftName(proc.id, e.currentTarget.value)}
            placeholder="z. B. Schleifen"
          />
        </label>
        <label>Menge Schritt
          <input
            type="number"
            min="0"
            step="1"
            value={draftQty(proc.id)}
            oninput={(e) => setDraftQty(proc.id, e.currentTarget.value)}
            placeholder="Default aus Prozess"
          />
        </label>
        <div class="row-actions" style="align-self:end">
          <button type="button" class="btn secondary" onclick={() => addStep(proc.id)}>Schritt anlegen</button>
        </div>
      </div>
    </section>
  {/each}
{/if}

<section class="panel">
  <div class="panel-header">
    <h3>Produktkosten</h3>
  </div>
  <p class="empty" style="margin-top:0">
    Aktuell: Ø Zeiten × heutige Tarife. Historie: Snapshots nach Abschluss.
  </p>
  <div class="form-grid">
    <label>Produkt
      <select bind:value={costProductId} onchange={loadCosts}>
        <option value="">wählen…</option>
        {#each products as p}
          <option value={p.id}>{p.name}</option>
        {/each}
      </select>
    </label>
    <div class="row-actions" style="align-self:end">
      <button type="button" class="btn secondary" onclick={loadCosts} disabled={!costProductId}>Laden</button>
    </div>
  </div>
  {#if costCurrent}
    <p>
      Stichproben: {costCurrent.sample_count} ·
      Arbeit {fmtSecs(costCurrent.labor_seconds_per_unit)} ({formatMoney(costCurrent.labor_eur_per_unit)}) ·
      Maschine {fmtSecs(costCurrent.machine_seconds_per_unit)} ·
      Energie {formatMoney(costCurrent.energy_eur_per_unit)} ·
      <strong>gesamt {formatMoney(costCurrent.total_eur_per_unit)}</strong> / Stück
    </p>
  {/if}
  {#if costHistory.length}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Wann</th>
            <th>Arbeit €</th>
            <th>Energie €</th>
            <th>Gesamt €</th>
          </tr>
        </thead>
        <tbody>
          {#each costHistory as h}
            <tr>
              <td>{formatDateTime(h.captured_at)}</td>
              <td>{formatMoney(h.labor_eur_per_unit)}</td>
              <td>{formatMoney(h.energy_eur_per_unit)}</td>
              <td>{formatMoney(h.total_eur_per_unit)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</section>

<style>
  .process-card {
    margin-top: 1rem;
  }
  .step-block {
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid color-mix(in srgb, var(--border, #ccc) 80%, transparent);
  }
  .step-head {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
    align-items: baseline;
    margin-bottom: 0.35rem;
  }
  .track-list {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .track-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
  }
  .track-row.running .timer {
    font-variant-numeric: tabular-nums;
    font-weight: 600;
  }
  .muted {
    opacity: 0.75;
    font-size: 0.9em;
  }
  .row-actions.wrap {
    flex-wrap: wrap;
    margin-top: 0.5rem;
  }
  .compact-list {
    margin: 0.5rem 0 1rem;
    padding-left: 1.2rem;
  }
  .inline-assign {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    margin: 0.35rem 0;
  }
  .inline-assign select {
    flex: 1;
    max-width: 16rem;
  }
</style>
