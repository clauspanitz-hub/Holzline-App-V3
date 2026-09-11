/**
 * Matching Shopify-Optionswerte ↔ Katalogfarben und Vorlagen-Serie ↔ Lagerartikel.
 */

/** Shopify-/Umgangssprache → Katalog-Normalform (nach normalizeColorKey). */
const COLOR_ALIASES = {
  pink: 'rosa',
  white: 'weiss',
  salbeigruen: 'salbei',
  salbei: 'salbei',
  // „Dunkelblau“-Stil → PLA-Katalog „BlauDunkel“
  dunkelblau: 'blaudunkel',
  hellblau: 'blauhell',
  dunkelgelb: 'gelbdunkel',
  hellgelb: 'gelbhell',
  dunkelgruen: 'gruendunkel',
  hellgruen: 'gruenhell',
  dunkelflieder: 'fliederdunkel',
  hellflieder: 'fliederhell',
  dunklerot: 'rot',
  hellrosa: 'rosa',
}

/**
 * @param {string} value
 * @returns {string}
 */
export function normalizeColorKey(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/ß/g, 'ss')
    .replace(/ä/g, 'ae')
    .replace(/ö/g, 'oe')
    .replace(/ü/g, 'ue')
    .replace(/[^a-z0-9]+/g, '')
}

/**
 * Varianten für „Dunkelblau“ / „Dunkles Grün“ / „Helles Flieder“ ↔ BlauDunkel / GrünDunkel / FliederHell.
 * @param {string} norm already normalized key
 * @returns {string[]}
 */
export function colorKeyVariants(norm) {
  const out = new Set([norm])
  if (COLOR_ALIASES[norm]) out.add(COLOR_ALIASES[norm])

  const adjMatch = norm.match(
    /^(dunkles|dunklem|dunkler|dunkle|dunkel|helles|hellem|heller|helle|hell)(.+)$/,
  )
  if (adjMatch) {
    // „dunkles“ beginnt mit dunkl-, nicht dunkel- (Flexion)
    const adj = /^dunk/.test(adjMatch[1]) ? 'dunkel' : 'hell'
    const rest = adjMatch[2]
    if (rest) {
      out.add(rest + adj)
      out.add(adj + rest)
      if (COLOR_ALIASES[rest + adj]) out.add(COLOR_ALIASES[rest + adj])
      if (COLOR_ALIASES[adj + rest]) out.add(COLOR_ALIASES[adj + rest])
    }
  }

  // Bereits zusammengesetzt: blaudunkel → auch dunkelblau
  if (norm.endsWith('dunkel') && norm.length > 6) {
    const rest = norm.slice(0, -6)
    out.add('dunkel' + rest)
  }
  if (norm.endsWith('hell') && norm.length > 4) {
    const rest = norm.slice(0, -4)
    out.add('hell' + rest)
  }

  return [...out]
}

/**
 * @param {{ id: number, name: string }[]} pool Farben eines Mediums
 * @param {string} shopifyValue
 * @returns {{ id: number, name: string }[]}
 */
export function matchColorsForShopifyValue(pool, shopifyValue) {
  const raw = String(shopifyValue || '').trim()
  if (!raw || !pool?.length) return []

  const keys = colorKeyVariants(normalizeColorKey(raw))
  const byKey = new Map()
  for (const c of pool) {
    byKey.set(normalizeColorKey(c.name), c)
  }

  const exact = []
  const seen = new Set()
  for (const k of keys) {
    const hit = byKey.get(k)
    if (hit && !seen.has(hit.id)) {
      seen.add(hit.id)
      exact.push(hit)
    }
  }
  if (exact.length) return exact

  // Weiches Matching nur, wenn eindeutig oder wenige Kandidaten
  const soft = pool.filter((c) => {
    const n = normalizeColorKey(c.name)
    return keys.some((k) => k && (n.includes(k) || k.includes(n)))
  })
  return soft
}

/**
 * Serien-Präfix aus Vorlagen-Namen (ohne angehängte Farbe), z. B.
 * „Geburtstagsring - Uni - Salbei“ → „Geburtstagsring - Uni“.
 * @param {{ name?: string, color_id?: number|null }|null|undefined} template
 * @param {{ id: number, name: string }[]} colors
 * @returns {string}
 */
export function templateSeriesPrefix(template, colors = []) {
  if (!template?.name) return ''
  let name = String(template.name).trim()
  if (template.color_id) {
    const color = colors.find((c) => c.id === Number(template.color_id))
    if (color?.name) {
      const suffix = ` - ${color.name}`
      if (name.toLowerCase().endsWith(suffix.toLowerCase())) {
        return name.slice(0, name.length - suffix.length).trim()
      }
    }
  }
  const parts = name.split(' - ')
  if (parts.length >= 2) return parts.slice(0, -1).join(' - ').trim()
  return name
}

/**
 * Lagerartikel zur Farbe; Vorlage-Serie hat Vorrang vor Familie/Basisname.
 * @param {'product'|'material'} kind
 * @param {number|string} colorId
 * @param {{ id: number, name: string, family?: string, color_id?: number }[]} rows materials or products
 * @param {{ id: number, name: string, family?: string, color_id?: number }|null|undefined} template
 * @param {string} baseName
 * @param {{ id: number, name: string }[]} colors
 * @param {(item: object) => string} familyKeyFn
 */
export function resolveSetComponents(kind, colorId, rows, template, baseName, colors, familyKeyFn) {
  if (!colorId) return []
  const cid = Number(colorId)
  let matched = rows.filter((r) => r.color_id === cid)

  const series = templateSeriesPrefix(template, colors)
  if (series && kind === 'product') {
    const seriesRows = matched.filter((p) =>
      String(p.name).toLowerCase().startsWith(series.toLowerCase()),
    )
    if (seriesRows.length) return seriesRows
  }

  const family = String(template?.family || baseName || '').trim()
  if (family && kind === 'product') {
    const famRows = matched.filter(
      (p) =>
        familyKeyFn(p) === family ||
        String(p.name).toLowerCase().startsWith(family.toLowerCase()),
    )
    if (famRows.length) matched = famRows
  } else if (baseName && matched.length > 1) {
    const pref = matched.filter((r) =>
      String(r.name).toLowerCase().startsWith(String(baseName).toLowerCase()),
    )
    if (pref.length) matched = pref
  }
  return matched
}
