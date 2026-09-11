/** Label für Artikel ohne gesetzte Familie. */
export const FAMILY_NONE = 'Ohne Familie'

/** Normalisierter Familien-Schlüssel eines Artikels (Produkt oder Material). */
export function familyKey(item) {
  return String(item?.family || '').trim()
}

/** @deprecated Alias — nutze familyKey */
export const productFamilyKey = familyKey

/** Eindeutige, sortierte Familiennamen aus einer Artikelliste. */
export function collectFamilies(items) {
  return [...new Set(items.map(familyKey).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, 'de'),
  )
}

/** @deprecated Alias — nutze collectFamilies */
export const collectProductFamilies = collectFamilies

/**
 * Artikel nach Familie gruppieren; „Ohne Familie“ steht am Ende.
 * @param {object[]} items
 * @returns {{ key: string, rows: object[] }[]}
 */
export function groupByFamily(items, familyNone = FAMILY_NONE) {
  const groups = new Map()
  for (const item of items) {
    const key = familyKey(item) || familyNone
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(item)
  }
  return [...groups.entries()]
    .map(([key, rows]) => ({ key, rows }))
    .sort((a, b) => {
      const aNone = a.key === familyNone
      const bNone = b.key === familyNone
      if (aNone !== bNone) return aNone ? 1 : -1
      return a.key.localeCompare(b.key, 'de')
    })
}

/** @deprecated Alias — nutze groupByFamily */
export const groupProductsByFamily = groupByFamily
