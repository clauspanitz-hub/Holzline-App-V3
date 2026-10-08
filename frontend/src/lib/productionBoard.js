/**
 * Board-Merge für Produktionsläufe — verhindert, dass ein leerer/stale
 * Server-Fetch optimistische oder frisch erzeugte Läufe aus der UI wischt.
 */

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
  }

  for (const pin of Object.values(pins)) {
    if (pin?.id && !next.some((r) => r.id === pin.id)) {
      next = [pin, ...next]
    }
  }

  // Bulletproof: leerer erfolgreicher Fetch darf lokale aktive Läufe nicht löschen
  // (stale parallel reload / kurzzeitiger Backend-Glitch nach Create).
  if (!next.length && previousBoard.length && !allowEmptyWipe) {
    return previousBoard
  }

  const byId = new Map()
  for (const run of next) {
    if (run?.id != null) byId.set(run.id, run)
  }
  return [...byId.values()].sort((a, b) => Number(b.id) - Number(a.id))
}

/**
 * @param {Record<string|number, object>} pins
 * @param {object} run
 */
export function pinProductionRun(pins, run) {
  if (!run?.id) return pins
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
