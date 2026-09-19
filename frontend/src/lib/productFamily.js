/** Label für Artikel ohne gesetzte Familie. */
export const FAMILY_NONE = 'Ohne Familie'

/** Blattname der Familienzuordnung. */
export function familyKey(item) {
  return String(item?.family || '').trim()
}

/** Elternname für Gruppierung (bei Unterfamilie = parent, sonst Blatt). */
export function familyParentKey(item) {
  const parent = String(item?.family_parent_name || '').trim()
  if (parent) return parent
  return familyKey(item)
}

/** @deprecated Alias — nutze familyKey */
export const productFamilyKey = familyKey

/** Eindeutige Elternfamilien-Namen aus Katalog + Artikeln. */
export function collectParentFamilyNames(catalog = [], items = []) {
  const names = new Set()
  for (const row of catalog || []) {
    if (row.parent_id == null && row.name) names.add(String(row.name).trim())
  }
  for (const item of items || []) {
    const parent = familyParentKey(item)
    if (parent) names.add(parent)
  }
  return [...names].filter(Boolean).sort((a, b) => a.localeCompare(b, 'de'))
}

/** Eindeutige, sortierte Familiennamen (Blätter) aus einer Artikelliste. */
export function collectFamilies(items) {
  return [...new Set(items.map(familyKey).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, 'de'),
  )
}

/** @deprecated Alias — nutze collectFamilies */
export const collectProductFamilies = collectFamilies

/**
 * Artikel nach Elternfamilie gruppieren; optional Unterköpfe.
 * @returns {{ key: string, rows: object[], subgroups?: { key: string, rows: object[] }[] }[]}
 */
export function groupByFamily(items, familyNone = FAMILY_NONE) {
  /** @type {Map<string, { direct: object[], subs: Map<string, object[]> }>} */
  const parents = new Map()
  const none = []

  for (const item of items) {
    const leaf = familyKey(item)
    if (!leaf) {
      none.push(item)
      continue
    }
    const parent = familyParentKey(item) || leaf
    if (!parents.has(parent)) parents.set(parent, { direct: [], subs: new Map() })
    const bucket = parents.get(parent)
    const hasSub = Boolean(String(item?.family_parent_name || '').trim())
    if (hasSub) {
      if (!bucket.subs.has(leaf)) bucket.subs.set(leaf, [])
      bucket.subs.get(leaf).push(item)
    } else {
      bucket.direct.push(item)
    }
  }

  const groups = [...parents.entries()]
    .map(([key, bucket]) => {
      const subgroups = [...bucket.subs.entries()]
        .map(([subKey, rows]) => ({ key: subKey, rows }))
        .sort((a, b) => a.key.localeCompare(b.key, 'de'))
      const rows = [...bucket.direct, ...subgroups.flatMap((s) => s.rows)]
      return { key, rows, directRows: bucket.direct, subgroups }
    })
    .sort((a, b) => a.key.localeCompare(b.key, 'de'))

  if (none.length) {
    groups.push({ key: familyNone, rows: none, directRows: none, subgroups: [] })
  }
  return groups
}

/** @deprecated Alias — nutze groupByFamily */
export const groupProductsByFamily = groupByFamily

/**
 * Filter: gewählte Namen sind Eltern- und/oder Blattnamen.
 * Elternmatch schließt direkte + Unterfamilien-Artikel ein.
 */
export function itemMatchesFamilyFilter(item, selectedNames) {
  if (!selectedNames?.size) return true
  const leaf = familyKey(item)
  const parent = familyParentKey(item)
  if (leaf && selectedNames.has(leaf)) return true
  if (parent && selectedNames.has(parent)) return true
  return false
}

/** Optionen für Familien-Select (Eltern + eingerückte Unterfamilien). */
export function familySelectOptions(catalog = []) {
  const parents = (catalog || [])
    .filter((f) => f.parent_id == null)
    .sort((a, b) => String(a.name).localeCompare(String(b.name), 'de'))
  const children = (catalog || []).filter((f) => f.parent_id != null)
  const options = []
  for (const parent of parents) {
    options.push({
      id: parent.id,
      label: parent.name,
      indent: false,
      parent_id: null,
    })
    const kids = children
      .filter((c) => Number(c.parent_id) === Number(parent.id))
      .sort((a, b) => String(a.name).localeCompare(String(b.name), 'de'))
    for (const kid of kids) {
      options.push({
        id: kid.id,
        label: kid.name,
        indent: true,
        parent_id: parent.id,
      })
    }
  }
  return options
}
