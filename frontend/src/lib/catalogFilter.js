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

function selectedMediumNames(mediumIds, media = []) {
  const ids = new Set((mediumIds || []).map(Number))
  const names = new Set()
  for (const medium of media || []) {
    if (!ids.has(Number(medium.id))) continue
    const name = String(medium.name || '').trim().toLowerCase()
    if (name) names.add(name)
  }
  return names
}

function itemMatchesMedium(item, mediumIds, colorIds, colors, media) {
  const names = selectedMediumNames(mediumIds, media)
  const lookup = colorByIdMap(colors)
  const itemMedium = Number(item.color?.medium_id || lookup.get(Number(item.color_id))?.medium_id || 0)
  const colorHit = itemMedium && mediumIds.includes(itemMedium)
  const familyHit = names.has(String(productFamilyKey(item) || '').trim().toLowerCase())
  const tagHit = (item.tags || []).some((t) => names.has(String(t.name || '').trim().toLowerCase()))
  if (!colorHit && !familyHit && !tagHit) return false
  if (colorIds.length && !colorIds.includes(Number(item.color_id))) return false
  return true
}

/** Innerhalb einer Art ODER, zwischen Arten UND. */
export function itemMatchesCatalogFilter(item, filter, colors = [], media = []) {
  if (!catalogFilterActive(filter)) return true
  const mediumIds = (filter.mediumIds || []).map(Number)
  const colorIds = (filter.colorIds || []).map(Number)
  const familySet = new Set(filter.families || [])
  const tagIds = new Set((filter.tagIds || []).map(Number))

  if (mediumIds.length) {
    if (!itemMatchesMedium(item, mediumIds, colorIds, colors, media)) return false
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

export function applyCatalogFilter(rows, filter, colors = [], media = []) {
  if (!Array.isArray(rows)) return []
  if (!catalogFilterActive(filter)) return rows
  return rows.filter((item) => itemMatchesCatalogFilter(item, filter, colors, media))
}
