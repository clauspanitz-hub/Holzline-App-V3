async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }
  const response = await fetch(path, { ...options, headers })

  if (response.status === 204) return null

  const text = await response.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }

  if (!response.ok) {
    const detail = data?.detail
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg || JSON.stringify(item)).join(', ')
      : detail || response.statusText || 'Anfrage fehlgeschlagen'
    throw new Error(message)
  }
  return data
}

export const api = {
  units: () => request('/api/units'),
  media: {
    list: () => request('/api/media'),
    create: (body) => request('/api/media', { method: 'POST', body: JSON.stringify(body) }),
    update: (id, body) => request(`/api/media/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    remove: (id) => request(`/api/media/${id}`, { method: 'DELETE' }),
  },
  locations: () => request('/api/locations'),
  colors: {
    list: (params = {}) => {
      const q = new URLSearchParams()
      if (params.medium_id) q.set('medium_id', params.medium_id)
      const qs = q.toString()
      return request(`/api/colors${qs ? `?${qs}` : ''}`)
    },
    create: (body) => request('/api/colors', { method: 'POST', body: JSON.stringify(body) }),
    update: (id, body) => request(`/api/colors/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    remove: (id) => request(`/api/colors/${id}`, { method: 'DELETE' }),
  },
  tags: {
    list: () => request('/api/tags'),
    create: (body) => request('/api/tags', { method: 'POST', body: JSON.stringify(body) }),
    update: (id, body) => request(`/api/tags/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    remove: (id) => request(`/api/tags/${id}`, { method: 'DELETE' }),
  },
  suggestions: {
    byColor: (colorId, { materials = true, products = true } = {}) =>
      request(`/api/suggestions/by-color/${colorId}?materials=${materials}&products=${products}`),
    byOptionValue: (value) =>
      request(`/api/suggestions/by-option-value?value=${encodeURIComponent(value)}`),
  },
  materials: {
    list: (params = {}) => {
      const q = new URLSearchParams()
      if (params.tag) q.set('tag', params.tag)
      if (params.color_id) q.set('color_id', params.color_id)
      if (params.medium_id) q.set('medium_id', params.medium_id)
      const qs = q.toString()
      return request(`/api/materials${qs ? `?${qs}` : ''}`)
    },
    create: (body) => request('/api/materials', { method: 'POST', body: JSON.stringify(body) }),
    fromColors: (body) =>
      request('/api/materials/from-colors', { method: 'POST', body: JSON.stringify(body) }),
    update: (id, body) => request(`/api/materials/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    remove: (id) => request(`/api/materials/${id}`, { method: 'DELETE' }),
    adjustStock: (id, body) => request(`/api/materials/${id}/stock`, { method: 'PUT', body: JSON.stringify(body) }),
    deltaStock: (id, body) =>
      request(`/api/materials/${id}/stock/delta`, { method: 'POST', body: JSON.stringify(body) }),
    transfer: (id, body) => request(`/api/materials/${id}/transfer`, { method: 'POST', body: JSON.stringify(body) }),
  },
  products: {
    list: (params = {}) => {
      const q = new URLSearchParams()
      if (params.tag) q.set('tag', params.tag)
      if (params.color_id) q.set('color_id', params.color_id)
      if (params.medium_id) q.set('medium_id', params.medium_id)
      const qs = q.toString()
      return request(`/api/products${qs ? `?${qs}` : ''}`)
    },
    create: (body) => request('/api/products', { method: 'POST', body: JSON.stringify(body) }),
    fromColors: (body) =>
      request('/api/products/from-colors', { method: 'POST', body: JSON.stringify(body) }),
    update: (id, body) => request(`/api/products/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    remove: (id) => request(`/api/products/${id}`, { method: 'DELETE' }),
    adjustStock: (id, body) => request(`/api/products/${id}/stock`, { method: 'PUT', body: JSON.stringify(body) }),
    deltaStock: (id, body) =>
      request(`/api/products/${id}/stock/delta`, { method: 'POST', body: JSON.stringify(body) }),
    transfer: (id, body) => request(`/api/products/${id}/transfer`, { method: 'POST', body: JSON.stringify(body) }),
    transform: (id, body) => request(`/api/products/${id}/transform`, { method: 'POST', body: JSON.stringify(body) }),
    addBom: (id, body) => request(`/api/products/${id}/bom`, { method: 'POST', body: JSON.stringify(body) }),
    removeBom: (id, lineId) => request(`/api/products/${id}/bom/${lineId}`, { method: 'DELETE' }),
    manufacture: (id, body) =>
      request(`/api/products/${id}/manufacture`, { method: 'POST', body: JSON.stringify(body) }),
  },
  movements: {
    list: ({ product_id, material_id, limit } = {}) => {
      const params = new URLSearchParams()
      if (product_id) params.set('product_id', product_id)
      if (material_id) params.set('material_id', material_id)
      if (limit) params.set('limit', String(limit))
      const qs = params.toString()
      return request(`/api/movements${qs ? `?${qs}` : ''}`)
    },
  },
  sets: {
    list: () => request('/api/sets'),
    get: (id) => request(`/api/sets/${id}`),
    create: (body) => request('/api/sets', { method: 'POST', body: JSON.stringify(body) }),
    update: (id, body) => request(`/api/sets/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    remove: (id) => request(`/api/sets/${id}`, { method: 'DELETE' }),
    addMapping: (id, body) => request(`/api/sets/${id}/mappings`, { method: 'POST', body: JSON.stringify(body) }),
    removeMapping: (id, mappingId) => request(`/api/sets/${id}/mappings/${mappingId}`, { method: 'DELETE' }),
    detachComponent: (id, { material_id, product_id } = {}) => {
      const q = new URLSearchParams()
      if (material_id) q.set('material_id', material_id)
      if (product_id) q.set('product_id', product_id)
      return request(`/api/sets/${id}/components?${q}`, { method: 'DELETE' })
    },
    applyMappings: (id) => request(`/api/sets/${id}/apply-mappings`, { method: 'POST' }),
    addBom: (id, variantId, body) =>
      request(`/api/sets/${id}/variants/${variantId}/bom`, { method: 'POST', body: JSON.stringify(body) }),
    removeBom: (id, variantId, lineId) =>
      request(`/api/sets/${id}/variants/${variantId}/bom/${lineId}`, { method: 'DELETE' }),
    importShopify: (file) => {
      const form = new FormData()
      form.append('file', file)
      return request('/api/sets/import/shopify-inventory', { method: 'POST', body: form })
    },
  },
}

export function formatQty(value) {
  return Number(value).toLocaleString('de-DE', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 3,
  })
}

export function formatMoney(value) {
  return Number(value).toLocaleString('de-DE', {
    style: 'currency',
    currency: 'EUR',
  })
}

export function formatUnitCost(value) {
  return Number(value).toLocaleString('de-DE', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  })
}

/** Datum/Zeit für UI (de-DE); leere Werte als Gedankenstrich. */
export function formatDateTime(value) {
  if (value == null || value === '') return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })
}

export function formatActor(value) {
  if (value == null || String(value).trim() === '') return '—'
  return String(value)
}

export function stockSummary(stocks = []) {
  if (!stocks.length) return '—'
  return stocks.map((s) => `${s.location_name}: ${formatQty(s.quantity)}`).join(' · ')
}
