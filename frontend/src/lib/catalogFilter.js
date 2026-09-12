import { productFamilyKey } from './productFamily.js'

export function emptyCatalogFilter() {
  return {
    mediumIds: [],
    colorIds: [],
    families: [],
    tagIds: [],
    q: '',
  }
}

export function namesMatch(a, b) {
  return String(a || '').trim().toLowerCase() === String(b || '').trim().toLowerCase()
}

export function familyMatchingMedium(mediumName, families = []) {
  return families.find((f) => namesMatch(f, mediumName)) || null
}

export function tagMatchingMedium(mediumName, tags = []) {
  return tags.find((t) => namesMatch(t.name, mediumName)) || null
}

/** Familie und Tag gleichen Namens mit Medium an-/abschalten. */
export function applyMediumCompanion(filter, medium, { families = [], tags = [], on }) {
  if (!medium) return filter
  const family = familyMatchingMedium(medium.name, families)
  const tag = tagMatchingMedium(medium.name, tags)
  let nextFamilies = [...(filter.families || [])]
  let nextTags = [...(filter.tagIds || [])]
  if (on) {
    if (family && !nextFamilies.some((f) => namesMatch(f, family))) nextFamilies.push(family)
    if (tag && !nextTags.includes(tag.id)) nextTags.push(tag.id)
  } else {
    if (family) nextFamilies = nextFamilies.filter((f) => !namesMatch(f, family))
    if (tag) nextTags = nextTags.filter((id) => Number(id) !== Number(tag.id))
  }
  return { ...filter, families: nextFamilies, tagIds: nextTags }
}

export function catalogFilterActive(filter) {
  if (!filter) return false
  return (
    (filter.mediumIds || []).length > 0 ||
    (filter.colorIds || []).length > 0 ||
    (filter.families || []).length > 0 ||
    (filter.tagIds || []).length > 0 ||
    String(filter.q || '').trim() !== ''
  )
}

function colorByIdMap(colors) {
  const map = new Map()
  for (const color of colors || []) map.set(Number(color.id), color)
  return map
}

/** Innerhalb einer Art ODER, zwischen Arten UND. */
export function itemMatchesCatalogFilter(item, filter, colors = []) {
  if (!catalogFilterActive(filter)) return true
  const mediumIds = (filter.mediumIds || []).map(Number)
  const colorIds = (filter.colorIds || []).map(Number)
  const familySet = new Set(filter.families || [])
  const tagIds = new Set((filter.tagIds || []).map(Number))
  const lookup = colorByIdMap(colors)

  if (mediumIds.length) {
    const itemMedium = Number(item.color?.medium_id || 0)
    if (!itemMedium || !mediumIds.includes(itemMedium)) return false
    const selectedForMedium = colorIds.filter((id) => lookup.get(id)?.medium_id === itemMedium)
    if (selectedForMedium.length && !selectedForMedium.includes(Number(item.color_id))) return false
  } else if (colorIds.length && !colorIds.includes(Number(item.color_id))) {
    return false
  }

  if (familySet.size && !familySet.has(productFamilyKey(item))) return false

  if (tagIds.size) {
    const ids = (item.tags || []).map((t) => Number(t.id))
    if (!ids.some((id) => tagIds.has(id))) return false
  }

  return true
}

export function applyCatalogFilter(rows, filter, colors = []) {
  if (!Array.isArray(rows)) return []
  if (!catalogFilterActive(filter)) return rows
  return rows.filter((item) => itemMatchesCatalogFilter(item, filter, colors))
}
