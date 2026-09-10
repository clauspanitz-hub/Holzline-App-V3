/**
 * Clientseitige Listen-Helfer: Live-Textfilter und Spaltensortierung.
 */

/**
 * @template T
 * @param {T[]} rows
 * @param {string} query
 * @param {(row: T) => string} rowToSearchText
 * @returns {T[]}
 */
export function filterRows(rows, query, rowToSearchText) {
  const q = String(query ?? '')
    .trim()
    .toLowerCase()
  if (!q) return rows
  return rows.filter((row) => {
    const text = String(rowToSearchText(row) ?? '').toLowerCase()
    return text.includes(q)
  })
}

/**
 * @param {unknown} a
 * @param {unknown} b
 * @returns {number}
 */
function compareValues(a, b) {
  if (a == null && b == null) return 0
  if (a == null || a === '') return 1
  if (b == null || b === '') return -1
  if (typeof a === 'number' && typeof b === 'number') {
    if (Number.isNaN(a) && Number.isNaN(b)) return 0
    if (Number.isNaN(a)) return 1
    if (Number.isNaN(b)) return -1
    return a - b
  }
  return String(a).localeCompare(String(b), 'de', { numeric: true, sensitivity: 'base' })
}

/**
 * @template T
 * @param {T[]} rows
 * @param {null|undefined|string|((row: T) => unknown)} key - Feldname oder Getter
 * @param {'asc'|'desc'} [dir]
 * @returns {T[]}
 */
export function sortRows(rows, key, dir = 'asc') {
  if (key == null || key === '') return rows
  const mult = dir === 'desc' ? -1 : 1
  const get = typeof key === 'function' ? key : (row) => row[key]
  return [...rows].sort((a, b) => compareValues(get(a), get(b)) * mult)
}

/**
 * @param {string|null|undefined} currentKey
 * @param {'asc'|'desc'|null|undefined} currentDir
 * @param {string} clickedKey
 * @returns {{ sortKey: string, sortDir: 'asc'|'desc' }}
 */
export function nextSortState(currentKey, currentDir, clickedKey) {
  if (currentKey === clickedKey) {
    return { sortKey: clickedKey, sortDir: currentDir === 'asc' ? 'desc' : 'asc' }
  }
  return { sortKey: clickedKey, sortDir: 'asc' }
}

/**
 * Visueller Indikator für aktive Sortierspalte.
 * @param {string|null|undefined} activeKey
 * @param {string} key
 * @param {'asc'|'desc'|null|undefined} dir
 * @returns {string}
 */
export function sortMark(activeKey, key, dir) {
  if (activeKey !== key) return ''
  return dir === 'desc' ? ' ▼' : ' ▲'
}

/**
 * Filter + Sort in einem Schritt (Filter zuerst).
 * @template T
 * @param {T[]} rows
 * @param {{ q?: string, sortKey?: string|null, sortDir?: 'asc'|'desc' }} ui
 * @param {(row: T) => string} rowToSearchText
 * @param {null|undefined|string|((row: T) => unknown)} sortGetter - wenn string, wird als Feld genutzt; sonst Getter
 */
export function prepareRows(rows, ui, rowToSearchText, sortGetter) {
  const filtered = filterRows(rows, ui?.q ?? '', rowToSearchText)
  const key = sortGetter ?? ui?.sortKey
  return sortRows(filtered, key, ui?.sortDir ?? 'asc')
}
