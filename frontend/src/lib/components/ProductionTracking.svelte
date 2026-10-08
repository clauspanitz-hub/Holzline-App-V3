<script>
  import { formatMoney, formatDateTime } from '../api.js'

  let {
    api,
    products = [],
    productFamilies = [],
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
  /** Create-Form: offen bis erster erfolgreicher Start; danach Board im Fokus. */
  let createOpen = $state(true)
  let focusRunId = $state(null)
  /** Verhindert, dass ein veraltetes reload() Board/createOpen überschreibt (Race). */
  let reloadSeq = 0
  let costProductId = $state('')
  let costFamilyId = $state('')
  let costCurrent = $state(null)
  let costHistory = $state([])
  let familyCost = $state(null)

  function emptyProcessDraft() {
    return { name: '', quantity: '', est_labor_min: '', est_machine_min: '' }
  }

  let newRun = $state({
    title: '',
    product_ids: [],
    family_ids: [],
    quantity: '',
  })
  let newProcesses = $state([emptyProcessDraft()])
  let stepDrafts = $state({}) // runId -> draft
  let machineDraft = $state({ name: '', note: '', power_w: '' })
  let rateDraft = $state({ name: '', eur_per_hour: '' })
  let energyDraft = $state('')
  let tick = $state(0)
  let machinePick = $state({})

  $effect(() => {
    const id = setInterval(() => {
      tick += 1
    }, 1000)
    return () => clearInterval(id)
  })

  function upsertRun(run) {
    if (!run?.id) return
    const rest = board.filter((r) => r.id !== run.id)
    board = [run, ...rest]
  }

  /**
   * @param {{ keepCreateClosed?: boolean, ensureRun?: object | null }} [opts]
   * keepCreateClosed: nach „Lauf starten“ Create nicht wieder aufklappen
   * ensureRun: Lauf aus Create-Response, falls Board-Fetch ihn verfehlt/Race
   */
  export async function reload(opts = {}) {
    const { keepCreateClosed = false, ensureRun = null } = opts
    const seq = ++reloadSeq
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
      if (seq !== reloadSeq) return
      let next = Array.isArray(b) ? b : []
      if (ensureRun?.id && !next.some((r) => r.id === ensureRun.id)) {
        next = [ensureRun, ...next]
      }
      board = next
      machines = m
      laborRates = r
      settings = s
      energyDraft = String(s.energy_eur_per_kwh ?? '')
      if (u) users = u
      if (keepCreateClosed) {
        createOpen = false
      } else if (!board.length && focusRunId == null) {
        createOpen = true
      }
    } catch (e) {
      if (seq !== reloadSeq) return
      if (ensureRun?.id) {
        upsertRun(ensureRun)
        if (keepCreateClosed) createOpen = false
      }
      onToast(e.message || 'Laden fehlgeschlagen', 'error')
    } finally {
      if (seq === reloadSeq) loading = false
    }
  }

  $effect(() => {
    void api
    void isAdmin
    reload()
  })

  function ensureDraft(runId) {
    if (!stepDrafts[runId]) {
      stepDrafts = {
        ...stepDrafts,
        [runId]: emptyProcessDraft(),
      }
    }
  }

  function draft(runId) {
    ensureDraft(runId)
    return stepDrafts[runId]
  }

  function setDraft(runId, patch) {
    ensureDraft(runId)
    stepDrafts = { ...stepDrafts, [runId]: { ...stepDrafts[runId], ...patch } }
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

  function minToSecs(minStr) {
    if (minStr === '' || minStr == null) return null
    const n = Number(minStr)
    if (!Number.isFinite(n) || n < 0) return null
    return Math.round(n * 60)
  }

  function secsToMinInput(secs) {
    if (secs == null || secs === '') return ''
    const n = Number(secs)
    if (!Number.isFinite(n)) return ''
    return String(Math.round((n / 60) * 10) / 10)
  }

  function toggleId(list, id) {
    const n = Number(id)
    return list.includes(n) ? list.filter((x) => x !== n) : [...list, n]
  }

  function familyLabel(f) {
    if (f.parent_name) return `${f.parent_name} › ${f.name}`
    return f.name
  }

  function runLinksLabel(run) {
    const parts = []
    for (const p of run.products || []) parts.push(p.name)
    for (const f of run.families || []) parts.push(`Familie: ${f.name}`)
    return parts.length ? parts.join(', ') : '—'
  }

  function scrollToRun(runId) {
    queueMicrotask(() => {
      const el =
        document.getElementById(`run-${runId}`) || document.getElementById('aktive-laeufe')
      el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  function openCreateForm() {
    createOpen = true
    focusRunId = null
    queueMicrotask(() => {
      document.getElementById('create-run')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  function setNewProcess(index, patch) {
    newProcesses = newProcesses.map((row, i) => (i === index ? { ...row, ...patch } : row))
  }

  function addNewProcessRow() {
    if (newProcesses.length >= 10) {
      onToast('Maximal 10 Prozesse pro Lauf', 'error')
      return
    }
    newProcesses = [...newProcesses, emptyProcessDraft()]
  }

  function removeNewProcessRow(index) {
    if (newProcesses.length <= 1) {
      newProcesses = [emptyProcessDraft()]
      return
    }
    newProcesses = newProcesses.filter((_, i) => i !== index)
  }

  async function createRun() {
    try {
      const body = {
        title: newRun.title.trim() || null,
        product_ids: newRun.product_ids.length ? newRun.product_ids : null,
        family_ids: newRun.family_ids.length ? newRun.family_ids : null,
        quantity: newRun.quantity !== '' ? Number(newRun.quantity) : null,
      }
      let latest = await api.production.createProcess(body)
      const initials = newProcesses.filter((p) => p.name.trim()).slice(0, 10)
      for (const p of initials) {
        latest = await api.production.addStep(latest.id, {
          name: p.name.trim(),
          quantity: p.quantity !== '' ? Number(p.quantity) : null,
          estimated_labor_seconds: minToSecs(p.est_labor_min),
          estimated_machine_seconds: minToSecs(p.est_machine_min),
        })
      }
      newRun = { title: '', product_ids: [], family_ids: [], quantity: '' }
      newProcesses = [emptyProcessDraft()]
      createOpen = false
      focusRunId = latest.id
      // Sofort sichtbar — unabhängig von parallelem/stale reload()
      upsertRun(latest)
      await reload({ keepCreateClosed: true, ensureRun: latest })
      createOpen = false
      focusRunId = latest.id
      if (!board.some((r) => r.id === latest.id)) upsertRun(latest)
      onToast(
        initials.length
          ? `Lauf gestartet · ${initials.length} Prozess(e)`
          : 'Lauf gestartet — jetzt Prozesse anlegen',
        'ok',
      )
      scrollToRun(latest.id)
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  async function patchRun(id, body) {
    try {
      await api.production.updateProcess(id, body)
      await reload()
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  async function addProcess(runId) {
    const d = draft(runId)
    if (!d.name.trim()) {
      onToast('Prozessname fehlt', 'error')
      return
    }
    const count = board.find((r) => r.id === runId)?.steps?.length ?? 0
    if (count >= 10) {
      onToast('Maximal 10 Prozesse pro Lauf', 'error')
      return
    }
    try {
      await api.production.addStep(runId, {
        name: d.name.trim(),
        quantity: d.quantity !== '' ? Number(d.quantity) : null,
        estimated_labor_seconds: minToSecs(d.est_labor_min),
        estimated_machine_seconds: minToSecs(d.est_machine_min),
      })
      stepDrafts = { ...stepDrafts, [runId]: emptyProcessDraft() }
      focusRunId = runId
      await reload()
      onToast('Prozess angelegt', 'ok')
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  async function patchProcess(stepId, body) {
    try {
      await api.production.updateStep(stepId, body)
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

  async function completeRun(id) {
    try {
      await api.production.completeProcess(id)
      if (focusRunId === id) focusRunId = null
      await reload()
      onToast('Produktionslauf abgeschlossen', 'ok')
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

  async function loadProductCosts() {
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

  async function loadFamilyCosts() {
    if (!costFamilyId) {
      familyCost = null
      return
    }
    try {
      familyCost = await api.production.familyCost(Number(costFamilyId))
    } catch (e) {
      onToast(e.message || 'Fehler', 'error')
    }
  }

  function defaultRateLabel() {
    if (!authUser?.labor_rate_id) return '—'
    return laborRates.find((r) => r.id === authUser.labor_rate_id)?.name || `#${authUser.labor_rate_id}`
  }
</script>

<section class="panel">
  <div class="panel-header">
    <h2>Produktion</h2>
    <div class="row-actions">
      <button type="button" class="btn secondary compact" onclick={() => reload()} disabled={loading}>Aktualisieren</button>
      {#if !createOpen}
        <button type="button" class="btn compact" onclick={openCreateForm}>Neuer Lauf</button>
      {/if}
      {#if isAdmin}
        <button type="button" class="btn secondary compact" onclick={() => (adminOpen = !adminOpen)}>
          {adminOpen ? 'Stammdaten zu' : 'Stammdaten'}
        </button>
      {/if}
    </div>
  </div>
  <p class="empty" style="margin-top:0">
    Ablauf: Produktionslauf anlegen → darunter Prozesse (bis 10) mit Schätzung, Messung und Timer.
    Multi-Select Produkte/Familien am Lauf. Kein Fertigen/Lager.
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
</section>

<section id="aktive-laeufe" class="aktive-laeufe" aria-labelledby="aktive-laeufe-heading">
  <div class="board-heading">
    <h3 id="aktive-laeufe-heading">Aktive Läufe</h3>
    <span class="chip soft board-count">{board.length} offen</span>
  </div>
  {#if !board.length}
    <p class="empty board-empty">
      {loading ? 'Lade Läufe…' : 'Keine aktiven Produktionsläufe — starte einen über „Neuer Lauf“ / Formular darunter.'}
    </p>
  {/if}
  {#each board as run}
    <section
      id="run-{run.id}"
      class="panel process-card"
      class:focused={focusRunId === run.id}
    >
      <div class="panel-header">
        <h3>{run.title || runLinksLabel(run) || `Lauf #${run.id}`}</h3>
        <button type="button" class="btn secondary compact" onclick={() => completeRun(run.id)}>Abschließen</button>
      </div>
      <p class="muted run-meta">
        Verknüpfung: {runLinksLabel(run)} · Stückzahl: {run.quantity ?? '—'} · Default-Satz: {defaultRateLabel()}
      </p>

      <details class="run-meta-details">
        <summary>Lauf bearbeiten (Name, Stück, Produkte/Familien)</summary>
        <div class="form-grid">
          <label>Hauptname
            <input
              value={run.title ?? ''}
              onchange={(e) => patchRun(run.id, { title: e.currentTarget.value })}
            />
          </label>
          <label>Stückzahl Lauf
            <input
              type="number"
              min="0"
              step="1"
              value={run.quantity ?? ''}
              onchange={(e) => {
                const v = e.currentTarget.value
                if (v === '') patchRun(run.id, { clear_quantity: true })
                else patchRun(run.id, { quantity: Number(v) })
              }}
            />
          </label>
        </div>

        <div class="multi-pick compact">
          <div>
            <div class="multi-pick-title">Produkte</div>
            <div class="check-grid">
              {#each products as p}
                <label class="check-row">
                  <input
                    type="checkbox"
                    checked={(run.product_ids || []).includes(p.id)}
                    onchange={() => {
                      const next = toggleId(run.product_ids || [], p.id)
                      patchRun(run.id, { product_ids: next, family_ids: run.family_ids || [] })
                    }}
                  />
                  <span>{p.name}</span>
                </label>
              {/each}
            </div>
          </div>
          <div>
            <div class="multi-pick-title">Familien</div>
            <div class="check-grid">
              {#each productFamilies as f}
                <label class="check-row">
                  <input
                    type="checkbox"
                    checked={(run.family_ids || []).includes(f.id)}
                    onchange={() => {
                      const next = toggleId(run.family_ids || [], f.id)
                      patchRun(run.id, { product_ids: run.product_ids || [], family_ids: next })
                    }}
                  />
                  <span>{familyLabel(f)}</span>
                </label>
              {/each}
            </div>
          </div>
        </div>
      </details>

      <div class="process-section">
        <div class="process-section-head">
          <h4>Prozesse</h4>
          <span class="chip soft">{run.steps?.length ?? 0}/10</span>
        </div>

        {#if !(run.steps?.length)}
          <p class="process-empty">
            Noch keine Prozesse. Lege z.&nbsp;B. Fräsen, Schleifen an — Name, Stück, Schätzung; danach Timer für die Messung.
          </p>
        {/if}

        {#each run.steps as step}
          <div class="step-block">
            <div class="step-head">
              <strong>{step.name}</strong>
              <span class="muted">Stück: {step.quantity ?? run.quantity ?? '—'}</span>
              <span class="muted">Schätzung A {fmtSecs(step.estimated_labor_seconds)} / M {fmtSecs(step.estimated_machine_seconds)}</span>
              <span class="muted">Messung A {fmtSecs(step.measured_labor_seconds)} / M {fmtSecs(step.measured_machine_seconds)}</span>
              <span class="chip soft">effektiv A {fmtSecs(step.effective_labor_seconds)} / M {fmtSecs(step.effective_machine_seconds)}</span>
            </div>

            <div class="form-grid inline-est">
              <label>Schätzung Arbeit (Min)
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={secsToMinInput(step.estimated_labor_seconds)}
                  onchange={(e) => {
                    const v = e.currentTarget.value
                    if (v === '') patchProcess(step.id, { clear_estimated_labor: true })
                    else patchProcess(step.id, { estimated_labor_seconds: minToSecs(v) })
                  }}
                />
              </label>
              <label>Schätzung Maschine (Min)
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={secsToMinInput(step.estimated_machine_seconds)}
                  onchange={(e) => {
                    const v = e.currentTarget.value
                    if (v === '') patchProcess(step.id, { clear_estimated_machine: true })
                    else patchProcess(step.id, { estimated_machine_seconds: minToSecs(v) })
                  }}
                />
              </label>
              <label>Stückzahl Prozess
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={step.quantity ?? ''}
                  onchange={(e) => {
                    const v = e.currentTarget.value
                    if (v === '') patchProcess(step.id, { clear_quantity: true })
                    else patchProcess(step.id, { quantity: Number(v) })
                  }}
                />
              </label>
            </div>

            <div class="track-list">
              {#each step.tracks as track}
                <div class="track-row" class:running={track.running}>
                  <span class="chip">{track.kind === 'labor' ? 'Arbeit' : 'Maschine'}</span>
                  {#if track.kind === 'machine' && track.machine_id}
                    <span class="muted">{machines.find((m) => m.id === track.machine_id)?.name || `#${track.machine_id}`}</span>
                  {/if}
                  {#if track.kind === 'labor' && track.labor_rate_id}
                    <span class="muted">{laborRates.find((r) => r.id === track.labor_rate_id)?.name || `Satz #${track.labor_rate_id}`}</span>
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
                  <option value={m.id}>{m.name}{#if m.power_w != null} ({m.power_w} W){/if}</option>
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

        <div class="add-process" class:emphasize={!(run.steps?.length)}>
          <div class="add-process-title">Prozess hinzufügen</div>
          <div class="form-grid">
            <label>Name
              <input
                value={draft(run.id).name}
                oninput={(e) => setDraft(run.id, { name: e.currentTarget.value })}
                placeholder="z. B. Schleifen"
              />
            </label>
            <label>Stückzahl
              <input
                type="number"
                min="0"
                step="1"
                value={draft(run.id).quantity}
                oninput={(e) => setDraft(run.id, { quantity: e.currentTarget.value })}
                placeholder="Default aus Lauf"
              />
            </label>
            <label>Schätzung Arbeit (Min)
              <input
                type="number"
                min="0"
                step="0.5"
                value={draft(run.id).est_labor_min}
                oninput={(e) => setDraft(run.id, { est_labor_min: e.currentTarget.value })}
              />
            </label>
            <label>Schätzung Maschine (Min)
              <input
                type="number"
                min="0"
                step="0.5"
                value={draft(run.id).est_machine_min}
                oninput={(e) => setDraft(run.id, { est_machine_min: e.currentTarget.value })}
              />
            </label>
            <div class="row-actions" style="align-self:end">
              <button type="button" class="btn" onclick={() => addProcess(run.id)}>
                Prozess anlegen ({run.steps?.length ?? 0}/10)
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  {/each}
</section>

{#if createOpen}
  <section id="create-run" class="panel create-panel">
    <div class="panel-header">
      <h3>Neuen Produktionslauf</h3>
      <button type="button" class="btn secondary compact" onclick={() => (createOpen = false)}>
        {board.length ? 'Zum Board' : 'Schließen'}
      </button>
    </div>
    <p class="muted create-hint">
      1) Hauptname + optional Produkte/Familien · 2) optional erste Prozesse · 3) Start — du landest auf dem Lauf-Board.
    </p>

    <div class="form-grid">
      <label>Hauptname
        <input bind:value={newRun.title} placeholder="z. B. Geburtstagsring aus Buche" />
      </label>
      <label>Stückzahl Lauf
        <input type="number" min="0" step="1" bind:value={newRun.quantity} placeholder="optional" />
      </label>
    </div>

    <details class="links-details" open={!board.length}>
      <summary>Produkte &amp; Familien (Multi-Select)</summary>
      <div class="multi-pick">
        <div>
          <div class="multi-pick-title">Produkte</div>
          <div class="check-grid">
            {#each products as p}
              <label class="check-row">
                <input
                  type="checkbox"
                  checked={newRun.product_ids.includes(p.id)}
                  onchange={() => {
                    newRun = { ...newRun, product_ids: toggleId(newRun.product_ids, p.id) }
                  }}
                />
                <span>{p.name}</span>
              </label>
            {/each}
          </div>
        </div>
        <div>
          <div class="multi-pick-title">Produktfamilien</div>
          <div class="check-grid">
            {#each productFamilies as f}
              <label class="check-row">
                <input
                  type="checkbox"
                  checked={newRun.family_ids.includes(f.id)}
                  onchange={() => {
                    newRun = { ...newRun, family_ids: toggleId(newRun.family_ids, f.id) }
                  }}
                />
                <span>{familyLabel(f)}</span>
              </label>
            {/each}
          </div>
        </div>
      </div>
    </details>

    <div class="create-processes">
      <div class="process-section-head">
        <h4>Prozesse (optional vor Start)</h4>
        <span class="chip soft">{newProcesses.filter((p) => p.name.trim()).length}/10</span>
      </div>
      <p class="muted" style="margin:0 0 0.5rem">
        Kannst du hier schon anlegen oder nach dem Start auf dem Lauf-Board.
      </p>
      {#each newProcesses as row, index}
        <div class="create-process-row">
          <label>Name
            <input
              value={row.name}
              oninput={(e) => setNewProcess(index, { name: e.currentTarget.value })}
              placeholder="z. B. Fräsen"
            />
          </label>
          <label>Stück
            <input
              type="number"
              min="0"
              step="1"
              value={row.quantity}
              oninput={(e) => setNewProcess(index, { quantity: e.currentTarget.value })}
            />
          </label>
          <label>Schätz. Arbeit (Min)
            <input
              type="number"
              min="0"
              step="0.5"
              value={row.est_labor_min}
              oninput={(e) => setNewProcess(index, { est_labor_min: e.currentTarget.value })}
            />
          </label>
          <label>Schätz. Maschine (Min)
            <input
              type="number"
              min="0"
              step="0.5"
              value={row.est_machine_min}
              oninput={(e) => setNewProcess(index, { est_machine_min: e.currentTarget.value })}
            />
          </label>
          <div class="row-actions" style="align-self:end">
            <button type="button" class="btn secondary compact" onclick={() => removeNewProcessRow(index)}>Entfernen</button>
          </div>
        </div>
      {/each}
      {#if newProcesses.length < 10}
        <button type="button" class="btn secondary compact" onclick={addNewProcessRow}>Weitere Prozesszeile</button>
      {/if}
    </div>

    <div class="row-actions" style="margin-top:0.75rem">
      <button type="button" class="btn" onclick={createRun}>Lauf starten</button>
    </div>
  </section>
{/if}

<section class="panel">
  <div class="panel-header">
    <h3>Produktkosten</h3>
  </div>
  <p class="empty" style="margin-top:0">
    Am Produkt immer sichtbar. Familie filterbar — bei abweichenden Preisen Durchschnitt.
  </p>
  <div class="form-grid">
    <label>Produkt
      <select bind:value={costProductId} onchange={loadProductCosts}>
        <option value="">wählen…</option>
        {#each products as p}
          <option value={p.id}>{p.name}</option>
        {/each}
      </select>
    </label>
    <div class="row-actions" style="align-self:end">
      <button type="button" class="btn secondary" onclick={loadProductCosts} disabled={!costProductId}>Laden</button>
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

  <h4 style="margin-top:1.25rem">Familien-Ø</h4>
  <div class="form-grid">
    <label>Produktfamilie
      <select bind:value={costFamilyId} onchange={loadFamilyCosts}>
        <option value="">wählen…</option>
        {#each productFamilies as f}
          <option value={f.id}>{familyLabel(f)}</option>
        {/each}
      </select>
    </label>
    <div class="row-actions" style="align-self:end">
      <button type="button" class="btn secondary" onclick={loadFamilyCosts} disabled={!costFamilyId}>Laden</button>
    </div>
  </div>
  {#if familyCost}
    <p>
      {familyCost.family_name}: Ø <strong>{formatMoney(familyCost.avg_total_eur_per_unit)}</strong> / Stück
      · {familyCost.sample_product_count}/{familyCost.product_count} Produkte mit Daten
      {#if familyCost.prices_differ}
        · <span class="chip soft">abweichend → Durchschnitt</span>
      {/if}
    </p>
    {#if familyCost.products?.length}
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Produkt</th>
              <th>Stichproben</th>
              <th>Gesamt €</th>
            </tr>
          </thead>
          <tbody>
            {#each familyCost.products as row}
              <tr>
                <td>{row.product_name}</td>
                <td>{row.sample_count}</td>
                <td>{formatMoney(row.total_eur_per_unit)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</section>

<style>
  .aktive-laeufe {
    margin: 1.1rem 0 0.5rem;
    padding: 0.85rem 0.9rem 0.5rem;
    border: 2px solid color-mix(in srgb, var(--accent, #2f6f4e) 45%, var(--border, #ccc));
    border-radius: 0.45rem;
    background: color-mix(in srgb, var(--accent, #2f6f4e) 6%, transparent);
    scroll-margin-top: 1rem;
  }
  .board-heading {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.75rem;
    margin: 0 0 0.5rem;
  }
  .board-heading h3 {
    margin: 0;
    font-size: 1.2rem;
  }
  .board-count {
    font-weight: 600;
  }
  .board-empty {
    margin: 0 0 0.75rem;
  }
  .process-card {
    margin-top: 0.75rem;
    scroll-margin-top: 1rem;
  }
  .process-card.focused {
    outline: 2px solid color-mix(in srgb, var(--accent, #2f6f4e) 55%, transparent);
    outline-offset: 2px;
  }
  .process-section {
    margin-top: 0.85rem;
    padding-top: 0.75rem;
    border-top: 1px solid color-mix(in srgb, var(--border, #ccc) 80%, transparent);
  }
  .process-section-head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.35rem;
  }
  .process-section-head h4 {
    margin: 0;
  }
  .process-empty {
    margin: 0.35rem 0 0.75rem;
    padding: 0.65rem 0.75rem;
    background: color-mix(in srgb, var(--accent, #2f6f4e) 12%, transparent);
    border-radius: 0.35rem;
    font-size: 0.95em;
  }
  .add-process {
    margin-top: 0.75rem;
    padding: 0.65rem;
    border: 1px dashed color-mix(in srgb, var(--border, #ccc) 90%, transparent);
    border-radius: 0.35rem;
  }
  .add-process.emphasize {
    border-color: color-mix(in srgb, var(--accent, #2f6f4e) 55%, transparent);
    background: color-mix(in srgb, var(--accent, #2f6f4e) 8%, transparent);
  }
  .add-process-title {
    font-weight: 600;
    margin-bottom: 0.35rem;
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
  .run-meta {
    margin: 0 0 0.5rem;
  }
  .run-meta-details,
  .links-details {
    margin: 0.35rem 0 0.5rem;
  }
  .run-meta-details summary,
  .links-details summary {
    cursor: pointer;
    font-weight: 600;
    margin-bottom: 0.5rem;
  }
  .create-panel {
    margin-top: 1rem;
  }
  .create-hint {
    margin: 0 0 0.75rem;
  }
  .create-processes {
    margin-top: 0.85rem;
    padding-top: 0.65rem;
    border-top: 1px solid color-mix(in srgb, var(--border, #ccc) 80%, transparent);
  }
  .create-process-row {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.5rem;
    margin-bottom: 0.65rem;
    padding-bottom: 0.65rem;
    border-bottom: 1px solid color-mix(in srgb, var(--border, #ccc) 55%, transparent);
  }
  @media (min-width: 720px) {
    .create-process-row {
      grid-template-columns: 1.4fr 0.7fr 0.9fr 0.9fr auto;
      align-items: end;
    }
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
  .multi-pick {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.75rem;
    margin-top: 0.5rem;
  }
  @media (min-width: 720px) {
    .multi-pick {
      grid-template-columns: 1fr 1fr;
    }
  }
  .multi-pick-title {
    font-weight: 600;
    margin-bottom: 0.35rem;
  }
  .check-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.25rem;
    max-height: 12rem;
    overflow: auto;
    padding: 0.35rem 0;
  }
  .check-row {
    display: flex;
    gap: 0.5rem;
    align-items: flex-start;
    font-size: 0.95em;
  }
  .chip.soft {
    background: color-mix(in srgb, var(--border, #ccc) 35%, transparent);
    border-radius: 0.25rem;
    padding: 0.1rem 0.4rem;
  }
  .inline-est {
    margin: 0.35rem 0 0.5rem;
  }
</style>
