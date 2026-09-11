/** Label für Produkte ohne gesetzte Familie. */
export const FAMILY_NONE = 'Ohne Familie'

/** Normalisierter Familien-Schlüssel eines Produkts. */
export function productFamilyKey(product) {
  return String(product?.family || '').trim()
}

/** Eindeutige, sortierte Familiennamen aus einer Produktliste. */
export function collectProductFamilies(products) {
  return [...new Set(products.map(productFamilyKey).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, 'de'),
  )
}

/**
 * Produkte nach Familie gruppieren; „Ohne Familie“ steht am Ende.
 * @param {object[]} products
 * @returns {{ key: string, rows: object[] }[]}
 */
export function groupProductsByFamily(products, familyNone = FAMILY_NONE) {
  const groups = new Map()
  for (const product of products) {
    const key = productFamilyKey(product) || familyNone
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(product)
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
