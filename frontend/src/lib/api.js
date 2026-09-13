async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }
  const response = await fetch(path, { ...options, headers, credentials: 'include' })

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
    const err = new Error(
      Array.isArray(data?.detail)
        ? data.detail.map((item) => item.msg || JSON.stringify(item)).join(', ')
        : data?.detail || response.statusText || 'Anfrage fehlgeschlagen',
    )
    err.status = response.status
    throw err
  }
  return data
}

export const api = {
  auth: {
    me: () => request('/api/auth/me'),
    login: (body) => request('/api/auth/login', { method: 'POST', body: JSON.stringify(body) }),
    logout: () => request('/api/auth/logout', { method: 'POST' }),
    changePassword: (body) =>
      request('/api/auth/change-password', { method: 'POST', body: JSON.stringify(body) }),
  },
  users: {
    list: () => request('/api/users'),
    create: (body) => request('/api/users', { method: 'POST', body: JSON.stringify(body) }),
    update: (id, body) => request(`/api/users/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  },
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
    bulkUpdate: (body) => request('/api/materials/bulk-update', { method: 'POST', body: JSON.stringify(body) }),
    bulkDelete: (body) => request('/api/materials/bulk-delete', { method: 'POST', body: JSON.stringify(body) }),
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
    bulkUpdate: (body) => request('/api/products/bulk-update', { method: 'POST', body: JSON.stringify(body) }),
    bulkDelete: (body) => request('/api/products/bulk-delete', { method: 'POST', body: JSON.stringify(body) }),
    remove: (id) => request(`/api/products/${id}`, { method: 'DELETE' }),
    adjustStock: (id, body) => request(`/api/products/${id}/stock`, { method: 'PUT', body: JSON.stringify(body) }),
    deltaStock: (id, body) =>
      request(`/api/products/${id}/stock/delta`, { method: 'POST', body: JSON.stringify(body) }),
    transfer: (id, body) => request(`/api/products/${id}/transfer`, { method: 'POST', body: JSON.stringify(body) }),
    transform: (id, body) => request(`/api/products/${id}/transform`, { method: 'POST', body: JSON.stringify(body) }),
    addBom: (id, body) => request(`/api/products/${id}/bom`, { method: 'POST', body: JSON.stringify(body) }),
    updateBom: (id, lineId, body) =>
      request(`/api/products/${id}/bom/${lineId}`, { method: 'PATCH', body: JSON.stringify(body) }),
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
  backup: {
    export: async (includeMovements = false) => {
      const params = new URLSearchParams()
      params.set('include_movements', includeMovements ? 'true' : 'false')
      const response = await fetch(`/api/backup/export?${params}`)
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
          : detail || response.statusText || 'Export fehlgeschlagen'
        throw new Error(message)
      }
      return data
    },
    import: (mode, backup) =>
      request('/api/backup/import', {
        method: 'POST',
        body: JSON.stringify({ mode, data: backup }),
      }),
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
    previewShopify: (file) => {
      const form = new FormData()
      form.append('file', file)
      return request('/api/sets/import/shopify-preview', { method: 'POST', body: form })
    },
    applyShopify: (file, items) => {
      const form = new FormData()
      form.append('file', file)
      form.append('items_json', JSON.stringify(items))
      return request('/api/sets/import/shopify-apply', { method: 'POST', body: form })
    },
    listIgnoredHandles: () => request('/api/sets/ignored-handles'),
    unignoreHandle: (handle) =>
      request(`/api/sets/ignored-handles/${encodeURIComponent(handle)}`, { method: 'DELETE' }),
    bulkDelete: (body) => request('/api/sets/bulk-delete', { method: 'POST', body: JSON.stringify(body) }),
  },
  importQueue: {
    list: (status) => {
      const q = status ? `?status=${encodeURIComponent(status)}` : ''
      return request(`/api/import-queue${q}`)
    },
    setStatus: (handle, status) =>
      request(`/api/import-queue/${encodeURIComponent(handle)}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      }),
    remove: (handle) =>
      request(`/api/import-queue/${encodeURIComponent(handle)}`, { method: 'DELETE' }),
  },
  orders: {
    list: (status) => {
      const q = status ? `?status=${encodeURIComponent(status)}` : ''
      return request(`/api/orders${q}`)
    },
    create: (body) => request('/api/orders', { method: 'POST', body: JSON.stringify(body) }),
    update: (id, body) => request(`/api/orders/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    remove: (id) => request(`/api/orders/${id}`, { method: 'DELETE' }),
    approve: (id) => request(`/api/orders/${id}/approve`, { method: 'POST' }),
    syncShopify: () => request('/api/orders/shopify-sync', { method: 'POST' }),
    listEtsyMails: () => request('/api/orders/etsy-mails'),
    parseEtsyMails: () => request('/api/orders/etsy-mails/parse', { method: 'POST' }),
    ignoreEtsyMail: (id) => request(`/api/orders/etsy-mails/${id}/ignore`, { method: 'POST' }),
    linkLine: (orderId, lineId, body) =>
      request(`/api/orders/${orderId}/lines/${lineId}`, { method: 'PATCH', body: JSON.stringify(body) }),
    queueCreate: (orderId, lineId) =>
      request(`/api/orders/${orderId}/lines/${lineId}/queue-create`, { method: 'POST' }),
  },
  todos: {
    list: ({ category, status } = {}) => {
      const q = new URLSearchParams()
      if (category) q.set('category', category)
      if (status) q.set('status', status)
      const qs = q.toString()
      return request(`/api/todos${qs ? `?${qs}` : ''}`)
    },
    complete: (id) => request(`/api/todos/${id}/complete`, { method: 'POST' }),
  },
  overview: {
    tageslage: (refresh = false) =>
      request(`/api/overview/tageslage${refresh ? '?refresh=true' : ''}`),
  },
}

/** Nachkommastellen eines Artikels (Produkte immer 0, Material laut Feld). */
export function itemDecimals(item) {
  if (item == null) return 0
  const n = Number(item.decimal_places)
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(3, Math.trunc(n)))
}

export function qtyStep(decimals = 0) {
  const d = itemDecimals({ decimal_places: decimals })
  if (d === 0) return '1'
  return (10 ** -d).toFixed(d)
}

/** Wert für number-Inputs: 1 statt 1.000; Brüche nur wenn Nachkommastellen erlaubt. */
export function qtyInputValue(value, decimals = 0) {
  if (value === '' || value == null) return ''
  const n = Number(String(value).replace(',', '.'))
  if (!Number.isFinite(n)) return ''
  const d = itemDecimals({ decimal_places: decimals })
  if (d === 0) return String(Math.round(n))
  return String(Number(n.toFixed(d)))
}

export function formatQty(value, decimals = 0) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '0'
  return n.toLocaleString('de-DE', {
    minimumFractionDigits: 0,
    maximumFractionDigits: itemDecimals({ decimal_places: decimals }),
  })
}

export function formatItemQty(item, value = item?.stock_total) {
  return formatQty(value, itemDecimals(item))
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
  return stocks.map((s) => `${s.location_name}: ${formatQty(s.quantity, 0)}`).join(' · ')
}
