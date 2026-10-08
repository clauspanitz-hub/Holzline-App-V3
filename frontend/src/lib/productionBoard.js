/**
 * Board-Merge für Produktionsläufe — verhindert, dass ein leerer/stale
 * Server-Fetch optimistische oder frisch erzeugte Läufe aus der UI wischt.
 * Bevorzugt die reichere Nesting-Payload (Prozesse/Tracks), wenn Pin und Server divergieren.
 */

/**
 * @param {object|null|undefined} run
 * @returns {number}
 */
export function runNestingScore(run) {
  if (!run) return 0
  const steps = Array.isArray(run.steps) ? run.steps : []
  let tracks = 0
  for (const step of steps) {
    tracks += Array.isArray(step?.tracks) ? step.tracks.length : 0
  }
  return steps.length * 1000 + tracks
}

/**
 * @param {object[]} serverRuns
 * @param {{ pins?: Record<string|number, object>, ensureRun?: object|null, previousBoard?: object[], allowEmptyWipe?: boolean }} [opts]
 * @returns {object[]}
 */
export function mergeProductionBoard(serverRuns, opts = {}) {
  const {
    pins = {},
    ensureRun = null,
    previousBoard = [],
    allowEmptyWipe = false,
  } = opts

  let next = Array.isArray(serverRuns) ? [...serverRuns] : []

  if (ensureRun?.id && !next.some((r) => r.id === ensureRun.id)) {
    next = [ensureRun, ...next]
  } else if (ensureRun?.id) {
    next = next.map((r) =>
      r.id === ensureRun.id && runNestingScore(ensureRun) > runNestingScore(r) ? ensureRun : r,
    )
  }

  for (const pin of Object.values(pins)) {
    if (!pin?.id) continue
    const idx = next.findIndex((r) => r.id === pin.id)
    if (idx < 0) {
      next = [pin, ...next]
    } else if (runNestingScore(pin) > runNestingScore(next[idx])) {
      next = next.map((r, i) => (i === idx ? pin : r))
    }
  }

  // Bulletproof: leerer erfolgreicher Fetch darf lokale aktive Läufe nicht löschen
  // (stale parallel reload / kurzzeitiger Backend-Glitch nach Create).
  if (!next.length && previousBoard.length && !allowEmptyWipe) {
    return previousBoard
  }

  // Server lieferte Läufe ohne Prozesse, lokal hatten wir welche → Nesting behalten.
  if (next.length && previousBoard.length && !allowEmptyWipe) {
    const prevById = new Map(previousBoard.filter((r) => r?.id != null).map((r) => [r.id, r]))
    next = next.map((run) => {
      const prev = prevById.get(run.id)
      if (prev && runNestingScore(prev) > runNestingScore(run)) return prev
      return run
    })
  }

  const byId = new Map()
  for (const run of next) {
    if (run?.id == null) continue
    const existing = byId.get(run.id)
    if (!existing || runNestingScore(run) >= runNestingScore(existing)) {
      byId.set(run.id, run)
    }
  }
  return [...byId.values()].sort((a, b) => Number(b.id) - Number(a.id))
}

/**
 * @param {Record<string|number, object>} pins
 * @param {object} run
 */
export function pinProductionRun(pins, run) {
  if (!run?.id) return pins
  const prev = pins[run.id] ?? pins[String(run.id)]
  if (prev && runNestingScore(prev) > runNestingScore(run)) {
    return pins
  }
  return { ...pins, [run.id]: run }
}

/**
 * @param {Record<string|number, object>} pins
 * @param {number|string} runId
 */
export function unpinProductionRun(pins, runId) {
  if (runId == null) return pins
  const next = { ...pins }
  delete next[runId]
  delete next[String(runId)]
  return next
}
