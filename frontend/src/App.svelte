<script>
  import { onMount } from 'svelte'
  import { api, formatMoney, formatQty, formatUnitCost, formatDateTime, formatActor, itemDecimals, qtyInputValue, qtyStep } from './lib/api.js'
  import { filterRows, sortRows, nextSortState, sortMark, prepareRows } from './lib/tableUtils.js'
  import { productFamilyKey, collectProductFamilies, groupProductsByFamily } from './lib/productFamily.js'
  import {
    matchColorsForShopifyValue as matchColorsPool,
    resolveSetComponents as resolveSetComponentsLib,
    templateSeriesPrefix,
  } from './lib/setOptionMatch.js'
  import FamilySelect from './lib/components/FamilySelect.svelte'
  import ProductGroupSection from './lib/components/ProductGroupSection.svelte'
  import BackupPanel from './lib/components/BackupPanel.svelte'
  import FilterBar from './lib/components/FilterBar.svelte'
  import ExtraGapPanels from './lib/components/ExtraGapPanels.svelte'
  import { applyCatalogFilter, emptyCatalogFilter } from './lib/catalogFilter.js'

  let tab = $state('overview')
  let authUser = $state(null)
  let authChecked = $state(false)
  let loginForm = $state({ username: '', password: '' })
  let passwordModal = $state(false)
  let passwordForm = $state({ current_password: '', new_password: '', confirm: '' })
  let users = $state([])
  let userForm = $state({ username: '', password: '', role: 'mitarbeiter' })
  let materials = $state([])
  let products = $state([])
  let sets = $state([])
  let units = $state([])
  let locations = $state([])
  let media = $state([])
  let colors = $state([])
  let allTags = $state([])
  let catalogFilter = $state(emptyCatalogFilter())
  let overviewCriticalOpen = $state(false)
  let overviewIncompleteOpen = $state(false)
  let overviewIgnoredOpen = $state(false)
  let overviewOrdersOpen = $state(true)
  let overviewTodosOpen = $state(true)
  let overviewTageslageOpen = $state(true)
  let tageslage = $state(null)
  let tageslageLoading = $state(false)
  let extraMatCriticalOpen = $state(false)
  let extraMatIncompleteOpen = $state(false)
  let extraMatIgnoredOpen = $state(false)
  let extraProdCriticalOpen = $state(false)
  let extraProdIncompleteOpen = $state(false)
  let extraProdIgnoredOpen = $state(false)
  let sellingPriceConflicts = $state(null)
  let sellingPriceStage = $state('ask')
  let sellingPricePicks = $state({})
  let shippedOrdersOpen = $state(false)
  let manualOrderOpen = $state(false)
  let etsyMails = $state([])
  let colorSuggestions = $state([])
  let loading = $state(true)
  let flash = $state(null)
  let saveButtonOk = $state(false)
  let flashClearTimer = null
  let saveOkTimer = null
  let saving = $state(false)
  let pendingDeleteOrderId = $state(null)

  /** Clientseitige Suche/Sortierung je Listen-Block */
  let listUi = $state({
    overviewMaterials: { q: '', sortKey: 'name', sortDir: 'asc' },
    overviewProducts: { q: '', sortKey: 'name', sortDir: 'asc' },
    materials: { q: '', sortKey: 'updated_at', sortDir: 'desc' },
    products: { q: '', sortKey: 'updated_at', sortDir: 'desc' },
    staff: { q: '', sortKey: 'name', sortDir: 'asc' },
    catalogColors: { q: '', sortKey: 'name', sortDir: 'asc' },
    catalogTags: { q: '', sortKey: 'name', sortDir: 'asc' },
    sets: { q: '', sortKey: 'name', sortDir: 'asc' },
    setBuildable: { q: '', sortKey: 'label', sortDir: 'asc' },
    setBlocked: { q: '', sortKey: 'label', sortDir: 'asc' },
  })

  let materialModal = $state(null)
  let productModal = $state(null)
  let manufactureModal = $state(null)
  let purchaseModal = $state(null)
  let transferModal = $state(null)
  let transformModal = $state(null)
  let movementsModal = $state(null) // { title, rows }
  let setModal = $state(null)
  let setStep = $state(1) // 1 Überblick, 2 Zuordnen, 3 Baubarkeit
  let shopifyAssistant = $state(null) // { file, preview, actions, showIgnored }
  let importQueue = $state([])
  let importQueueFilter = $state('open') // open | done | all
  let queueAxisModal = $state(null) // { item, axes, colorAxis }
  let orders = $state([])
  let todos = $state([])
  let loadedBuckets = { catalog: false, inventory: false, orders: false, sets: false, queue: false }
  let todoCategoryFilter = $state('workshop')
  let todoStatusFilter = $state('open')
  let orderForm = $state(emptyOrderForm())
  let manufactureTodoId = $state(null)
  let articleChoiceTodo = $state(null)
  let ignoredHandlesModal = $state(false)
  let ignoredHandles = $state([])
  let setCleanupModal = $state(false)
  let setCleanupIds = $state([])
  let showMaterialTags = $state(false)
  let showProductTags = $state(false)

  /** Aktive Inline-Zelle: key = `${kind}:${id}:${field}`, original + value */
  let catalogEdit = $state(null)
  let catalogNewMedia = $state('')
  let catalogNewColorDrafts = $state({}) // mediumId -> name
  let catalogNewTag = $state('')
  let catalogSavingKey = $state('')
  let selectedCatalogMediumId = $state(null)

  /** Bulk: Materialien/Produkte aus Katalogfarben */
  let bulkMaterialModal = $state(null) // { mediumId, fromQueue? }
  let bulkProductModal = $state(null) // { mediumId?, fromQueue? }
  let bulkForm = $state({
    colorIds: [],
    unit: 'ml',
    purchase_quantity: '750',
    purchase_price: '0',
    min_stock: '',
    location_id: '',
    base_name: '',
    template_product_id: '',
    template_material_id: '',
  })

  /** Produktfamilien: eingeklappte Gruppen der Produkt-Tabelle */
  let collapsedFamilies = $state({}) // familienKey -> true

  /** Mehrfachauswahl für Sammelbearbeitung */
  let selectedMaterialIds = $state([])
  let selectedProductIds = $state([])
  let bulkEditModal = $state(null) // { kind: 'material' | 'product' }
  let bulkEditForm = $state(emptyBulkEditForm())
  /** Momentaufnahme sichtbarer Zeilen für Vorheriger/Nächster im Bearbeiten-Dialog */
  let editNav = $state(null) // { kind: 'material' | 'product', ids: number[], index: number }
  let editFormBaseline = $state('')

  let materialForm = $state(emptyMaterial())
  let productForm = $state(emptyProduct())
  let bomForm = $state({ kind: 'material', material_id: '', product_id: '', quantity_required: '' })
  let manufactureForm = $state({ quantity: '1', location_id: '' })
  let purchaseForm = $state({ quantity: '', location_id: '', purchase_price: '' })
  let transferForm = $state({ from_location_id: '', to_location_id: '', quantity: '1', note: '' })
  let transformForm = $state({ location_id: '', quantity: '1', note: '' })
  let stockDrafts = $state({}) // location_id -> { setValue, deltaValue }
  let mappingForm = $state({
    option_name: '',
    option_value: '',
    kind: 'product',
    component_id: '',
    quantity_required: '1',
  })
  /** Pro Options-Name: Medium, Typ, Vorlage, Basisname */
  let setOptionConfig = $state({})
  /** Zeilen-Overrides: `${option}::${value}` → { colorId, componentId, skip } */
  let setRowOverrides = $state({})

  function emptySetOptionConfig() {
    return { mediumId: '', kind: 'product', templateId: '', baseName: '' }
  }

  function getSetOptionConfig(optionName) {
    return setOptionConfig[optionName] || emptySetOptionConfig()
  }

  function patchSetOptionConfig(optionName, patch) {
    if (!optionName) return
    setOptionConfig = {
      ...setOptionConfig,
      [optionName]: { ...getSetOptionConfig(optionName), ...patch },
    }
  }

  function setBatchRowKey(optionName, value) {
    return `${optionName}::${value}`
  }

  function matchColorsForShopifyValue(mediumId, value) {
    return matchColorsPool(colorsForMedium(mediumId), value)
  }

  function resolveSetComponents(kind, colorId, templateId, baseName) {
    const template = templateId ? products.find((p) => p.id === Number(templateId)) : null
    const rows = kind === 'material' ? materials : products
    return resolveSetComponentsLib(kind, colorId, rows, template, baseName, colors, productFamilyKey)
  }

  let inlineMaterialForm = $state(null)

  function emptyMaterial() {
    return {
      name: '',
      unit: 'Stk',
      stock_quantity: '0',
      purchase_quantity: '1',
      purchase_price: '0',
      min_stock: '',
      is_template: false,
      decimal_places: 0,
      family: '',
      location_id: '',
      medium_id: '',
      color_id: '',
      tagIds: [],
    }
  }
  function emptyProduct() {
    return {
      name: '',
      sku: '',
      selling_price: '0',
      stock_quantity: '0',
      min_stock: '',
      is_template: false,
      family: '',
      location_id: '',
      medium_id: '',
      color_id: '',
      transform_target_id: '',
      tagIds: [],
    }
  }

  function nowDateTimeLocal() {
    const d = new Date()
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  }

  function emptyOrderLine() {
    return { product_id: '', label: '', quantity: '1' }
  }

  function emptyOrderForm() {
    return {
      ordered_on: nowDateTimeLocal(),
      customer_name: '',
      external_number: '',
      lines: [emptyOrderLine()],
    }
  }

  function onOrderProductPicked(index, productId) {
    const lines = [...orderForm.lines]
    lines[index] = { ...lines[index], product_id: productId }
    if (productId) {
      const product = products.find((p) => String(p.id) === String(productId))
      if (product) lines[index].label = product.name
    }
    if (productId && index === lines.length - 1) {
      lines.push(emptyOrderLine())
    }
    orderForm.lines = lines
  }

  function orderStatusLabel(status) {
    if (status === 'review') return 'zur Prüfung'
    if (status === 'ready') return 'versandbereit'
    if (status === 'shipped') return 'versendet'
    return 'offen'
  }

  function orderOpenTodoHint(order) {
    const open = (order.todos || []).filter((t) => t.status === 'open')
    if (!open.length) return ''
    const fertigen = open.filter((t) => t.kind === 'manufacture').length
    const anlegen = open.filter((t) => t.kind === 'create_article').length
    const bits = []
    if (fertigen) bits.push(`${fertigen}× Fertigen`)
    if (anlegen) bits.push(`${anlegen}× Anlegen`)
    if (!bits.length) bits.push(`${open.length} offen`)
    return bits.join(', ')
  }

  function lineHasCreateTodo(order, line) {
    return (order.todos || []).some(
      (t) => t.order_line_id === line.id && t.status === 'open' && t.kind === 'create_article',
    )
  }

  function orderLineForTodo(todo) {
    const order = orders.find((o) => o.id === todo.order_id)
    return order?.lines?.find((ln) => ln.id === todo.order_line_id) || null
  }

  function orderOriginLabel(origin) {
    if (origin === 'shopify') return 'Shopify'
    if (origin === 'etsy') return 'Etsy'
    return 'Manuell'
  }

  function todoKindLabel(kind) {
    if (kind === 'manufacture') return 'Fertigen'
    if (kind === 'create_article') return 'Artikel anlegen'
    if (kind === 'purchase') return 'Einkauf'
    return kind
  }

  function emptyBulkEditForm() {
    return {
      deleteSelected: false,
      min_stock: '',
      selling_price: '',
      clear_min_stock: false,
      setTags: false,
      tagIds: [],
      family: '',
      clear_family: false,
      is_template: '', // '' = nicht ändern, 'yes', 'no'
      setStock: false,
      stock_location_id: '',
      stock_quantity: '',
      setBom: false,
      bom_mode: 'upsert',
      bom_kind: 'material',
      bom_material_id: '',
      bom_product_id: '',
      bom_quantity: '',
    }
  }

  function emptyInlineMaterial() {
    return {
      name: '',
      unit: 'Stk',
      purchase_quantity: '1',
      purchase_price: '0',
      stock_quantity: '0',
      location_id: String(locations.find((x) => x.name === 'Hamburg')?.id || locations[0]?.id || ''),
      decimal_places: 0,
    }
  }

  function computedUnitCost(purchasePrice, purchaseQuantity) {
    const q = Number(purchaseQuantity)
    const p = Number(purchasePrice)
    if (!q || q <= 0) return 0
    return p / q
  }

  function colorTagMeta(item) {
    const parts = []
    if (item.color?.label) parts.push(item.color.label)
    else if (item.color?.name) {
      const mediumName = item.color.medium?.name || item.color.medium
      parts.push(mediumName ? `${item.color.name} (${mediumName})` : item.color.name)
    }
    if (item.tags?.length) parts.push(item.tags.map((t) => t.name).join(', '))
    return parts.join(' · ')
  }

  function toggleFamilyCollapse(key) {
    const isOpen = collapsedFamilies[key] === false
    collapsedFamilies = { ...collapsedFamilies, [key]: isOpen }
  }

  function incompleteHint(item) {
    const fields = item?.incomplete_fields
    if (!Array.isArray(fields) || !fields.length) return ''
    return fields.join(', ')
  }

  function showFlash(type, message) {
    flash = { type, message }
    if (flashClearTimer) clearTimeout(flashClearTimer)
    if (type === 'ok' || type === 'warn') {
      flashClearTimer = setTimeout(() => {
        if (flash?.message === message) flash = null
      }, 2800)
    }
  }

  function markSaved() {
    saveButtonOk = true
    if (saveOkTimer) clearTimeout(saveOkTimer)
    saveOkTimer = setTimeout(() => {
      saveButtonOk = false
    }, 2000)
  }

  function flashRenameResult(okMessage, result) {
    const warnings = result?.warnings
    if (Array.isArray(warnings) && warnings.length) {
      showFlash('warn', `${okMessage} ${warnings.join(' ')}`)
    } else {
      showFlash('ok', okMessage)
    }
  }

  function colorsForMedium(mediumId) {
    if (!mediumId) return []
    const mid = Number(mediumId)
    return colors.filter((c) => c.medium_id === mid)
  }

  function bulkProductName(baseName, color) {
    return `${String(baseName || '').trim()} ${color.name}`.trim()
  }

  function isBulkProductColorTaken(baseName, color) {
    const name = bulkProductName(baseName, color)
    if (!name) return false
    return products.some((p) => p.name === name)
  }

  function isBulkMaterialColorTaken(baseName, color) {
    const name = bulkProductName(baseName, color)
    if (!name) return false
    return materials.some((m) => m.name === name)
  }

  /** Basis aus Vorlagenname: Farbsuffix am Ende abschneiden (wie Produkt-Nachlegen). */
  function seriesBaseFromTemplate(template) {
    if (!template?.name) return ''
    let base = String(template.name).trim()
    const colorName = template.color?.name
    if (colorName && base.toLowerCase().endsWith(String(colorName).toLowerCase())) {
      base = base.slice(0, base.length - colorName.length).trim() || base
    }
    return base
  }

  function queueBaseName(title, optionValues, colorAxis) {
    const extras = []
    for (const [axis, vals] of Object.entries(optionValues || {})) {
      if (colorAxis && axis === colorAxis) continue
      const clean = (vals || []).map((v) => String(v).trim()).filter(Boolean)
      if (clean.length === 1) extras.push(clean[0])
      else if (clean.length > 1) extras.push(clean.join('/'))
    }
    const t = String(title || '').trim()
    if (!extras.length) return t
    return `${t} — ${extras.join(' — ')}`
  }

  function matchQueueColorIds(mediumId, shopifyValues) {
    if (!mediumId || !shopifyValues?.length) return []
    const ids = []
    const seen = new Set()
    for (const val of shopifyValues) {
      const hits = matchColorsForShopifyValue(mediumId, val)
      if (hits.length === 1) {
        const id = hits[0].id
        if (!seen.has(id)) {
          seen.add(id)
          ids.push(id)
        }
      }
    }
    return ids
  }

  function colorIdsForBulk({ mediumId, base, kind, fromQueue, colorIds }) {
    if (colorIds != null) return colorIds
    if (fromQueue?.shopifyValues?.length) {
      if (!mediumId) return []
      const matched = matchQueueColorIds(mediumId, fromQueue.shopifyValues)
      const takenFn = kind === 'material' ? isBulkMaterialColorTaken : isBulkProductColorTaken
      return matched.filter((id) => {
        const c = colors.find((x) => x.id === id)
        return c && !takenFn(base, c)
      })
    }
    const pool = mediumId ? colorsForMedium(mediumId) : colors
    const takenFn = kind === 'material' ? isBulkMaterialColorTaken : isBulkProductColorTaken
    return pool.filter((c) => !takenFn(base, c)).map((c) => c.id)
  }

  function openBulkMaterials(mediumId = null, { keepTemplate = false, baseName = null, fromQueue = undefined } = {}) {
    const mid = mediumId != null ? Number(mediumId) : media[0]?.id || null
    const prevTemplate = keepTemplate ? bulkForm.template_material_id : ''
    const fq = fromQueue !== undefined ? fromQueue : bulkMaterialModal?.fromQueue || null
    const base =
      baseName != null
        ? baseName
        : keepTemplate
          ? bulkForm.base_name
          : ''
    // From queue: do not auto-pick first medium — user must choose for Farb-Match
    const effectiveMid = fq ? (mediumId != null ? Number(mediumId) : null) : mid
    const available = colorIdsForBulk({
      mediumId: effectiveMid,
      base,
      kind: 'material',
      fromQueue: fq,
    })
    bulkForm = {
      ...bulkForm,
      colorIds: available,
      base_name: base,
      unit: keepTemplate && prevTemplate ? bulkForm.unit : 'ml',
      purchase_quantity: keepTemplate && prevTemplate ? bulkForm.purchase_quantity : '750',
      purchase_price: keepTemplate && prevTemplate ? bulkForm.purchase_price : '0',
      min_stock: keepTemplate ? bulkForm.min_stock : '',
      template_material_id: prevTemplate || '',
      location_id: String(locations.find((x) => x.name === 'Hamburg')?.id || locations[0]?.id || ''),
    }
    bulkMaterialModal = { mediumId: effectiveMid, fromQueue: fq }
  }

  function materialTemplateById(templateMaterialId) {
    if (!templateMaterialId) return null
    return materials.find((m) => m.id === Number(templateMaterialId)) || null
  }

  /** Mindestbestand der Vorlage als Vorbelegung für die Serienanlage. */
  function templateMinStock(templateProductId) {
    if (!templateProductId) return ''
    const template = products.find((p) => p.id === Number(templateProductId))
    return template?.min_stock != null ? qtyInputValue(template.min_stock, 0) : ''
  }

  function materialTemplateMinStock(templateMaterialId) {
    const template = materialTemplateById(templateMaterialId)
    return template?.min_stock != null ? qtyInputValue(template.min_stock, itemDecimals(template)) : ''
  }

  /** Vorlage im Material-Serien-Dialog: Basis + Stammdaten aus Vorlage. */
  function onBulkMaterialTemplateChange() {
    const template = materialTemplateById(bulkForm.template_material_id)
    if (!template) return
    const base = seriesBaseFromTemplate(template)
    bulkForm.base_name = base
    bulkForm.unit = template.unit
    bulkForm.purchase_quantity = String(template.purchase_quantity ?? 1)
    bulkForm.purchase_price = String(template.purchase_price ?? 0)
    bulkForm.decimal_places = itemDecimals(template)
    if (bulkForm.min_stock === '') {
      bulkForm.min_stock = materialTemplateMinStock(bulkForm.template_material_id)
    }
    bulkForm.colorIds = colorIdsForBulk({
      mediumId: bulkMaterialModal?.mediumId,
      base,
      kind: 'material',
      fromQueue: bulkMaterialModal?.fromQueue,
    })
  }

  function openBulkProducts({
    mediumId = null,
    baseName = '',
    templateProductId = '',
    minStock = null,
    colorIds = null,
    fromQueue = undefined,
  } = {}) {
    const mid = mediumId != null ? Number(mediumId) : null
    const fq = fromQueue !== undefined ? fromQueue : bulkProductModal?.fromQueue || null
    const base = baseName || ''
    const available = colorIdsForBulk({
      mediumId: mid,
      base,
      kind: 'product',
      fromQueue: fq,
      colorIds,
    })
    bulkForm = {
      ...bulkForm,
      colorIds: available,
      base_name: base,
      template_product_id: templateProductId ? String(templateProductId) : '',
      min_stock: minStock != null ? minStock : templateMinStock(templateProductId),
      location_id: String(locations.find((x) => x.name === 'Hamburg')?.id || locations[0]?.id || ''),
    }
    bulkProductModal = { mediumId: mid, fromQueue: fq }
  }

  /** Vorlage im Serien-Dialog gewechselt: Mindestbestand nur übernehmen, wenn leer. */
  function onBulkTemplateChange() {
    if (bulkForm.min_stock !== '') return
    bulkForm.min_stock = templateMinStock(bulkForm.template_product_id)
  }

  function toggleBulkColorId(colorId) {
    const id = Number(colorId)
    if (bulkForm.colorIds.includes(id)) bulkForm.colorIds = bulkForm.colorIds.filter((x) => x !== id)
    else bulkForm.colorIds = [...bulkForm.colorIds, id]
  }

  async function submitBulkMaterials() {
    const base = bulkForm.base_name.trim()
    if (!base) {
      showFlash('error', 'Basisname fehlt (z. B. Kerzen klein -).')
      return
    }
    if (!bulkForm.colorIds.length) {
      showFlash('error', 'Mindestens eine Farbe wählen.')
      return
    }
    const queueHandle = bulkMaterialModal?.fromQueue?.handle || null
    saving = true
    try {
      const body = {
        color_ids: bulkForm.colorIds,
        base_name: base,
        template_material_id: bulkForm.template_material_id
          ? Number(bulkForm.template_material_id)
          : null,
        min_stock: parseOptionalQty(bulkForm.min_stock),
        location_id: bulkForm.location_id ? Number(bulkForm.location_id) : null,
      }
      if (bulkForm.unit) body.unit = bulkForm.unit
      if (bulkForm.purchase_quantity !== '' && bulkForm.purchase_quantity != null) {
        body.purchase_quantity = bulkForm.purchase_quantity
      }
      if (bulkForm.purchase_price !== '' && bulkForm.purchase_price != null) {
        body.purchase_price = bulkForm.purchase_price
      }
      const result = await api.materials.fromColors(body)
      bulkMaterialModal = null
      await refresh()
      const msg = `${result.created.length} Material(ien) angelegt` +
        (result.skipped.length ? `, ${result.skipped.length} übersprungen` : '')
      showFlash('ok', msg)
      for (const w of result.warnings || []) showFlash('ok', w)
      await maybeMarkQueueDone(queueHandle)
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function submitBulkProducts() {
    const base = bulkForm.base_name.trim()
    if (!base) {
      showFlash('error', 'Basisname fehlt (z. B. Ring).')
      return
    }
    if (!bulkForm.colorIds.length) {
      showFlash('error', 'Mindestens eine Farbe wählen.')
      return
    }
    const queueHandle = bulkProductModal?.fromQueue?.handle || null
    const onDemand = !!bulkProductModal?.fromQueue?.onDemand
    saving = true
    try {
      const result = await api.products.fromColors({
        color_ids: bulkForm.colorIds,
        base_name: base,
        template_product_id: bulkForm.template_product_id
          ? Number(bulkForm.template_product_id)
          : null,
        min_stock: parseOptionalQty(bulkForm.min_stock),
        location_id: bulkForm.location_id ? Number(bulkForm.location_id) : null,
        stock_quantity: '0',
        is_on_demand: onDemand,
      })
      bulkProductModal = null
      await refresh()
      const msg = `${result.created.length} Produkt(e) angelegt` +
        (result.skipped.length ? `, ${result.skipped.length} übersprungen` : '')
      showFlash('ok', msg)
      if (result.warnings?.length) {
        showFlash('error', result.warnings.slice(0, 3).join(' · '))
      }
      await maybeMarkQueueDone(queueHandle)
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function loadImportQueue() {
    if (!authUser || authUser.role !== 'admin') return
    try {
      importQueue = await api.importQueue.list()
    } catch (error) {
      if (error.status !== 401) showFlash('error', error.message)
    }
  }

  function importQueueRows() {
    if (importQueueFilter === 'all') return importQueue
    return importQueue.filter((r) => r.status === importQueueFilter)
  }

  function importQueueOpenCount() {
    return importQueue.filter((r) => r.status === 'open').length
  }

  function displayedTodos() {
    return todos.filter((t) => {
      if (todoCategoryFilter !== 'all' && t.category !== todoCategoryFilter) return false
      if (todoStatusFilter !== 'all' && t.status !== todoStatusFilter) return false
      return true
    })
  }

  function openTodoCount() {
    return todos.filter((t) => t.status === 'open' && t.category === 'workshop').length
  }

  function startTodo(todo) {
    if (todo.kind === 'manufacture') {
      const product = products.find((p) => p.id === todo.product_id)
      if (!product) {
        showFlash('error', 'Produkt nicht gefunden.')
        return
      }
      openManufacture(product, { quantity: todo.quantity, todoId: todo.id })
      return
    }
    if (todo.kind === 'create_article') {
      const order = orders.find((o) => o.id === todo.order_id)
      const line = orderLineForTodo(todo)
      if (order && (order.origin === 'shopify' || order.origin === 'etsy')) {
        openCreateProductFromOrderLine(order, line || { label: todoLabelForCreate(todo), quantity: todo.quantity })
        return
      }
      articleChoiceTodo = todo
    }
  }

  function todoLabelForCreate(todo) {
    return String(todo.title || '').replace(/^Artikel anlegen:\s*/i, '').trim()
  }

  function chooseArticleKind(kind) {
    const todo = articleChoiceTodo
    if (!todo) return
    articleChoiceTodo = null
    const name = todoLabelForCreate(todo)
    const orderLink = { orderId: todo.order_id, lineId: todo.order_line_id }
    if (kind === 'material') openCreateMaterial(null, { name, orderLink })
    else openCreateProduct(null, { name, orderLink })
  }

  async function submitOrder() {
    const lines = orderForm.lines
      .map((ln) => ({
        quantity: ln.quantity,
        product_id: ln.product_id ? Number(ln.product_id) : null,
        label: (ln.label || '').trim() || null,
      }))
      .filter((ln) => ln.product_id || ln.label)
    if (!lines.length) {
      showFlash('error', 'Mindestens eine Position (Produkt oder Freitext).')
      return
    }
    saving = true
    try {
      await api.orders.create({
        ordered_on: orderForm.ordered_on || null,
        customer_name: orderForm.customer_name.trim() || null,
        external_number: orderForm.external_number.trim() || null,
        lines,
      })
      orderForm = emptyOrderForm()
      await refresh()
      showFlash('ok', 'Bestellung angelegt.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function markOrderShipped(order) {
    saving = true
    try {
      await api.orders.update(order.id, { status: 'shipped' })
      await refresh()
      showFlash('ok', 'Als versendet markiert.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function deleteOrder(order) {
    if (pendingDeleteOrderId !== order.id) {
      pendingDeleteOrderId = order.id
      return
    }
    saving = true
    try {
      await api.orders.remove(order.id)
      pendingDeleteOrderId = null
      loadedBuckets.orders = false
      await refresh()
      showFlash('ok', 'Bestellung gelöscht.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function syncShopifyOrders() {
    saving = true
    try {
      const result = await api.orders.syncShopify()
      loadedBuckets.orders = false
      await refresh()
      const bits = []
      if (result.created) bits.push(`${result.created} neu`)
      if (result.claimed) bits.push(`${result.claimed} übernommen`)
      if (result.suggested) bits.push(`${result.suggested} Vorschlag`)
      if (result.skipped) bits.push(`${result.skipped} übersprungen`)
      showFlash('ok', bits.length ? `Shopify: ${bits.join(', ')}.` : 'Shopify: keine neuen Aufträge.')
      if (result.errors?.length) showFlash('error', result.errors[0])
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function parseEtsyMails() {
    saving = true
    try {
      const result = await api.orders.parseEtsyMails()
      loadedBuckets.orders = false
      await refresh()
      const bits = []
      if (result.fetched) bits.push(`${result.fetched} geholt`)
      if (result.created) bits.push(`${result.created} Bestellung`)
      if (result.suggested) bits.push(`${result.suggested} Vorschlag`)
      if (result.duplicates) bits.push(`${result.duplicates} Doppel`)
      if (result.failed) bits.push(`${result.failed} Fehler`)
      showFlash('ok', bits.length ? `Etsy-Mail: ${bits.join(', ')}.` : 'Etsy-Mail: nichts Neues.')
      if (result.errors?.length) showFlash('error', result.errors[0])
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function ignoreEtsyMail(mail) {
    saving = true
    try {
      await api.orders.ignoreEtsyMail(mail.id)
      etsyMails = etsyMails.filter((m) => m.id !== mail.id)
      showFlash('ok', 'Mail ignoriert.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function approveOrder(order) {
    saving = true
    try {
      await api.orders.approve(order.id)
      loadedBuckets.orders = false
      await refresh()
      showFlash('ok', 'Bestellung abgenickt.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function setReviewLineProduct(order, line, productId) {
    saving = true
    try {
      let result
      if (productId) {
        result = await api.orders.linkLine(order.id, line.id, { product_id: Number(productId) })
      } else {
        result = await api.orders.linkLine(order.id, line.id, { unassign: true })
      }
      loadedBuckets.orders = false
      await refresh()
      if (result?.notices?.length) showFlash('warn', result.notices.join(' '))
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  function startQueueSeries(item) {
    const axes = item.option_axes?.length
      ? item.option_axes
      : Object.keys(item.option_values || {})
    if (axes.length <= 1) {
      openSeriesFromQueue(item, axes[0] || null)
      return
    }
    queueAxisModal = { item, axes, colorAxis: axes[0] }
  }

  function openSeriesFromQueue(item, colorAxis) {
    queueAxisModal = null
    const values = item.option_values || {}
    const shopifyValues = colorAxis
      ? values[colorAxis] || []
      : Object.values(values).flat()
    const base = queueBaseName(item.title, values, colorAxis)
    const fromQueue = {
      handle: item.handle,
      onDemand: !!item.on_demand,
      shopifyValues,
      colorAxis,
    }
    if (item.kind === 'material') {
      openBulkMaterials(null, { baseName: base, fromQueue })
    } else {
      openBulkProducts({ baseName: base, fromQueue })
    }
  }

  async function maybeMarkQueueDone(handle) {
    if (!handle) return
    if (!confirm('Als erledigt in der Import-Warteschlange markieren?')) return
    try {
      await api.importQueue.setStatus(handle, 'done')
      await loadImportQueue()
      showFlash('ok', 'In der Import-Warteschlange als erledigt markiert.')
    } catch (error) {
      showFlash('error', error.message)
    }
  }

  async function discardQueueItem(handle) {
    if (!confirm('Eintrag aus der Import-Warteschlange entfernen?')) return
    try {
      await api.importQueue.remove(handle)
      await loadImportQueue()
    } catch (error) {
      showFlash('error', error.message)
    }
  }

  async function reopenQueueItem(handle) {
    try {
      await api.importQueue.setStatus(handle, 'open')
      await loadImportQueue()
    } catch (error) {
      showFlash('error', error.message)
    }
  }

  function toggleSelectedMaterial(id) {
    if (selectedMaterialIds.includes(id)) selectedMaterialIds = selectedMaterialIds.filter((x) => x !== id)
    else selectedMaterialIds = [...selectedMaterialIds, id]
  }

  function toggleSelectedProduct(id) {
    if (selectedProductIds.includes(id)) selectedProductIds = selectedProductIds.filter((x) => x !== id)
    else selectedProductIds = [...selectedProductIds, id]
  }

  function toggleAllDisplayedMaterials() {
    const ids = displayedMaterials.map((m) => m.id)
    const allSelected = ids.length > 0 && ids.every((id) => selectedMaterialIds.includes(id))
    if (allSelected) selectedMaterialIds = selectedMaterialIds.filter((id) => !ids.includes(id))
    else selectedMaterialIds = [...new Set([...selectedMaterialIds, ...ids])]
  }

  /** Alle Artikel einer Familien-Gruppe an-/abwählen (Produkt- oder Materialliste). */
  function toggleFamilySelection(group, kind = 'product') {
    const ids = group.rows.map((row) => row.id)
    if (kind === 'material') {
      const allSelected = ids.length > 0 && ids.every((id) => selectedMaterialIds.includes(id))
      if (allSelected) selectedMaterialIds = selectedMaterialIds.filter((id) => !ids.includes(id))
      else selectedMaterialIds = [...new Set([...selectedMaterialIds, ...ids])]
      return
    }
    const allSelected = ids.length > 0 && ids.every((id) => selectedProductIds.includes(id))
    if (allSelected) selectedProductIds = selectedProductIds.filter((id) => !ids.includes(id))
    else selectedProductIds = [...new Set([...selectedProductIds, ...ids])]
  }

  function isFamilySelected(group, kind = 'product') {
    const selected = kind === 'material' ? selectedMaterialIds : selectedProductIds
    return group.rows.length > 0 && group.rows.every((row) => selected.includes(row.id))
  }

  function openBulkEdit(kind) {
    bulkEditForm = emptyBulkEditForm()
    bulkEditModal = { kind }
  }

  async function setOverviewIgnored(kind, item, ignored) {
    saving = true
    try {
      if (kind === 'material') await api.materials.update(item.id, { overview_ignored: ignored })
      else await api.products.update(item.id, { overview_ignored: ignored })
      await refresh()
      showFlash('ok', ignored ? 'Aus der Warnliste ausgeblendet.' : 'Wieder in der Warnliste.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function patchGapItem(kind, item, patch) {
    saving = true
    try {
      if (kind === 'material') await api.materials.update(item.id, patch)
      else await api.products.update(item.id, patch)
      await refresh({ silent: true })
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function adjustGapStock(kind, item, body) {
    saving = true
    try {
      if (kind === 'material') await api.materials.adjustStock(item.id, body)
      else await api.products.adjustStock(item.id, body)
      await refresh({ silent: true })
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function resolveSellingPriceConflicts(mode, overrides = {}) {
    const rows = sellingPriceConflicts || []
    if (!rows.length) return
    saving = true
    try {
      const idsCsv = []
      for (const row of rows) {
        const choice = overrides[row.product_id] || mode
        if (choice === 'csv') idsCsv.push(row.product_id)
      }
      if (idsCsv.length) {
        const byPrice = new Map()
        for (const row of rows) {
          if (!idsCsv.includes(row.product_id)) continue
          const key = String(row.csv)
          if (!byPrice.has(key)) byPrice.set(key, [])
          byPrice.get(key).push(row.product_id)
        }
        for (const [price, ids] of byPrice) {
          await api.products.bulkUpdate({ ids, selling_price: price })
        }
      }
      sellingPriceConflicts = null
      await refresh()
      showFlash('ok', mode === 'keep' ? 'Bisherige Verkaufspreise behalten.' : 'Verkaufspreise aus CSV übernommen.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function submitBulkEdit() {
    const kind = bulkEditModal?.kind
    const ids = kind === 'material' ? selectedMaterialIds : selectedProductIds
    if (!ids.length) return

    if (bulkEditForm.deleteSelected) {
      const label = kind === 'material' ? 'Materialien' : 'Produkte'
      if (
        !confirm(
          `WARNUNG: ${ids.length} ${label} unwiderruflich löschen?\n\n` +
            `Nicht löschbare Einträge (z. B. Material in einer Produkt-Stückliste) bleiben erhalten und werden gemeldet.`,
        )
      ) {
        return
      }
      saving = true
      try {
        const result =
          kind === 'material'
            ? await api.materials.bulkDelete({ ids })
            : await api.products.bulkDelete({ ids })
        if (kind === 'material') selectedMaterialIds = []
        else selectedProductIds = []
        bulkEditModal = null
        await refresh()
        const deleted = result.deleted_ids?.length || 0
        const skipped = result.skipped || []
        if (skipped.length) {
          const lines = skipped
            .slice(0, 8)
            .map((s) => `• ${s.name}: ${s.reason}`)
            .join('\n')
          const more = skipped.length > 8 ? `\n… und ${skipped.length - 8} weitere` : ''
          showFlash(
            deleted ? 'warn' : 'error',
            `${deleted} gelöscht, ${skipped.length} übersprungen:\n${lines}${more}`,
          )
        } else {
          showFlash('ok', `${deleted} Eintrag/Einträge gelöscht.`)
        }
        markSaved()
      } catch (error) {
        showFlash('error', error.message)
      } finally {
        saving = false
      }
      return
    }

    if (bulkEditForm.setStock) {
      const locId = Number(bulkEditForm.stock_location_id)
      const qty = bulkEditForm.stock_quantity
      if (!locId || qty === '' || qty == null) {
        showFlash('error', 'Für Bestand Standort und Menge angeben.')
        return
      }
      if (
        !confirm(
          `WARNUNG: Bestand von ${ids.length} Einträgen an diesem Standort auf ${qty} setzen?\nDas überschreibt die bisherigen Werte.`,
        )
      ) {
        return
      }
    }
    if (kind === 'product' && bulkEditForm.setBom) {
      const bomKind = bulkEditForm.bom_kind === 'product' ? 'product' : 'material'
      const componentId = Number(bomKind === 'product' ? bulkEditForm.bom_product_id : bulkEditForm.bom_material_id)
      const qty = bulkEditForm.bom_quantity
      const remove = bulkEditForm.bom_mode === 'remove'
      if (!componentId) {
        showFlash('error', 'Für die Stückliste eine Komponente wählen.')
        return
      }
      if (!remove && (!qty || Number(qty) <= 0)) {
        showFlash('error', 'Für Stückliste Komponente und Menge angeben.')
        return
      }
      const componentName =
        (bomKind === 'product'
          ? products.find((p) => p.id === componentId)?.name
          : materials.find((m) => m.id === componentId)?.name) || `#${componentId}`
      if (remove) {
        if (
          !confirm(
            `WARNUNG: Stücklistenzeile „${componentName}“ bei ${ids.length} Produkten entfernen?\nAndere Zeilen bleiben. Produkte ohne diese Zeile werden übersprungen.`,
          )
        ) {
          return
        }
      } else if (
        !confirm(
          `WARNUNG: Stücklistenzeile „${componentName}“ (Menge ${qty}) bei ${ids.length} Produkten hinzufügen oder ändern?\nAndere Zeilen bleiben erhalten.`,
        )
      ) {
        return
      }
    }

    const body = { ids }
    if (bulkEditForm.clear_min_stock) {
      body.clear_min_stock = true
    } else {
      const min = parseOptionalQty(bulkEditForm.min_stock)
      if (min != null) body.min_stock = min
    }
    if (bulkEditForm.selling_price !== '' && bulkEditForm.selling_price != null) {
      body.selling_price = bulkEditForm.selling_price
    }
    if (bulkEditForm.setTags) body.tag_ids = bulkEditForm.tagIds
    if (bulkEditForm.clear_family) body.clear_family = true
    else if (bulkEditForm.family.trim()) body.family = bulkEditForm.family.trim()
    if (bulkEditForm.is_template === 'yes') body.is_template = true
    else if (bulkEditForm.is_template === 'no') body.is_template = false
    saving = true
    try {
      const hasSafeFields =
        body.clear_min_stock ||
        body.min_stock != null ||
        body.selling_price != null ||
        body.tag_ids ||
        body.clear_family ||
        body.family != null ||
        body.is_template != null
      if (hasSafeFields) {
        if (kind === 'material') await api.materials.bulkUpdate(body)
        else await api.products.bulkUpdate(body)
      }
      if (bulkEditForm.setStock) {
        const locId = Number(bulkEditForm.stock_location_id)
        const quantity = String(bulkEditForm.stock_quantity)
        for (const id of ids) {
          if (kind === 'material') await api.materials.adjustStock(id, { location_id: locId, quantity })
          else await api.products.adjustStock(id, { location_id: locId, quantity })
        }
      }
      let bomSkipped = 0
      let bomChanged = 0
      if (kind === 'product' && bulkEditForm.setBom) {
        const bomKind = bulkEditForm.bom_kind === 'product' ? 'product' : 'material'
        const componentId = Number(bomKind === 'product' ? bulkEditForm.bom_product_id : bulkEditForm.bom_material_id)
        const remove = bulkEditForm.bom_mode === 'remove'
        const quantity_required = String(bulkEditForm.bom_quantity)
        for (const id of ids) {
          const product = products.find((p) => p.id === id)
          const existing = (product?.bom || []).find((line) =>
            bomKind === 'product'
              ? Number(line.product_id) === componentId
              : Number(line.material_id) === componentId,
          )
          if (remove) {
            if (!existing) {
              bomSkipped += 1
              continue
            }
            await api.products.removeBom(id, existing.id)
            bomChanged += 1
          } else if (existing) {
            await api.products.updateBom(id, existing.id, { quantity_required })
            bomChanged += 1
          } else {
            const payload =
              bomKind === 'product'
                ? { product_id: componentId, quantity_required }
                : { material_id: componentId, quantity_required }
            await api.products.addBom(id, payload)
            bomChanged += 1
          }
        }
      }
      if (kind === 'material') selectedMaterialIds = []
      else selectedProductIds = []
      bulkEditModal = null
      await refresh()
      if (kind === 'product' && bulkEditForm.setBom && bulkEditForm.bom_mode === 'remove') {
        showFlash(
          'ok',
          bomSkipped
            ? `Stückliste: ${bomChanged} entfernt, ${bomSkipped} ohne diese Zeile übersprungen.`
            : `Stücklistenzeile bei ${bomChanged} Produkten entfernt.`,
        )
      } else {
        showFlash('ok', `${ids.length} Eintrag/Einträge aktualisiert.`)
      }
      markSaved()
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  /** Familie aus Produktname ableiten: „Ring Salbeigrün“ + Farbe „Salbeigrün“ → „Ring“. */
  function familyFromColorSuffix(product) {
    const colorName = product.color?.name
    if (!colorName) return ''
    const name = String(product.name || '').trim()
    if (!name.toLowerCase().endsWith(colorName.toLowerCase())) return ''
    return name.slice(0, name.length - colorName.length).trim()
  }

  async function suggestFamilies() {
    const proposals = new Map() // Familie -> Produkt-IDs
    for (const product of products) {
      if (productFamilyKey(product)) continue
      const family = familyFromColorSuffix(product)
      if (!family) continue
      if (!proposals.has(family)) proposals.set(family, [])
      proposals.get(family).push(product.id)
    }
    if (!proposals.size) {
      showFlash('ok', 'Keine Vorschläge — Produktnamen enden nicht auf ihren Farbnamen.')
      return
    }
    const total = [...proposals.values()].reduce((sum, ids) => sum + ids.length, 0)
    const preview = [...proposals.keys()].slice(0, 8).join(', ')
    const ok = confirm(
      `${total} Produkt(e) in ${proposals.size} Familie(n) einsortieren?\n\n` +
        `${preview}${proposals.size > 8 ? ' …' : ''}`,
    )
    if (!ok) return
    saving = true
    try {
      for (const [family, ids] of proposals) {
        await api.products.bulkUpdate({ ids, family })
      }
      await refresh()
      showFlash('ok', `${total} Produkt(e) ${proposals.size} Familie(n) zugeordnet.`)
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  function onFormMediumChange(form) {
    form.color_id = ''
    colorSuggestions = []
  }

  function familyMembers(kind, family, excludeId = null) {
    const key = String(family || '').trim()
    if (!key) return []
    const rows = kind === 'material' ? materials : products
    return rows.filter((row) => productFamilyKey(row) === key && row.id !== excludeId)
  }

  /** Tag ist bei allen Familienmitgliedern schon gesetzt → ausgegraut. */
  function tagFullyOnFamily(kind, family, tagId) {
    const members = familyMembers(kind, family)
    if (!members.length) return false
    return members.every((row) => (row.tags || []).some((t) => t.id === tagId))
  }

  function tagIdKey(ids) {
    return [...new Set((ids || []).map(Number).filter((id) => Number.isFinite(id)))]
      .sort((a, b) => a - b)
      .join(',')
  }

  /** Tag-Liste nur mitsenden, wenn sie sich gegenüber dem geladenen Artikel geändert hat. */
  function tagIdsIfChanged(originalTags, currentIds) {
    const originalIds = (originalTags || []).map((t) => t.id)
    if (tagIdKey(originalIds) === tagIdKey(currentIds)) return null
    return currentIds
  }

  async function toggleTagId(form, tagId, kind = null) {
    const id = Number(tagId)
    const adding = !form.tagIds.includes(id)
    if (!adding) {
      form.tagIds = form.tagIds.filter((x) => x !== id)
      return
    }
    form.tagIds = [...form.tagIds, id]
    if (!kind) return

    const tagMeta = allTags.find((t) => t.id === id)
    if (tagMeta?.is_system) return

    const family = String(form.family || '').trim()
    const editingId =
      kind === 'material'
        ? materialModal?.mode === 'edit'
          ? materialModal.id
          : null
        : productModal?.mode === 'edit'
          ? productModal.product?.id
          : null
    if (!family || !editingId) return

    const siblings = familyMembers(kind, family, editingId).filter(
      (row) => !(row.tags || []).some((t) => t.id === id),
    )
    if (!siblings.length) return
    const tagName = tagMeta?.name || 'Tag'
    if (
      !confirm(
        `Tag „${tagName}“ auch ${siblings.length} weiteren ${kind === 'material' ? 'Materialien' : 'Produkten'} der Familie „${family}“ geben?`,
      )
    ) {
      return
    }
    saving = true
    try {
      for (const row of siblings) {
        const tag_ids = [...new Set([...(row.tags || []).map((t) => t.id), id])]
        if (kind === 'material') await api.materials.update(row.id, { tag_ids })
        else await api.products.update(row.id, { tag_ids })
      }
      await refresh({ silent: true })
      showFlash('ok', `Tag „${tagName}“ an Familie „${family}“ vergeben.`)
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  function mediumIdFromColor(colorId) {
    if (!colorId) return ''
    const c = colors.find((x) => x.id === Number(colorId))
    return c ? String(c.medium_id) : ''
  }

  async function loadTageslage({ refresh: force = false } = {}) {
    if (!authUser || authUser.role === 'mitarbeiter') return
    tageslageLoading = true
    try {
      tageslage = await api.overview.tageslage(force)
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      tageslageLoading = false
    }
  }

  async function refresh({ silent = false } = {}) {
    loadedBuckets = { catalog: false, inventory: false, orders: false, sets: false, queue: false }
    await ensureTabData({ silent })
    if (tab === 'overview') await loadTageslage()
  }

  async function selectTab(next) {
    tab = next
    await ensureTabData({ silent: true })
    if (next === 'overview') await loadTageslage()
  }

  async function ensureTabData({ silent = false } = {}) {
    if (!authUser) return
    if (!silent) loading = true
    try {
      if (authUser.role === 'mitarbeiter') {
        if (!loadedBuckets.catalog || !loadedBuckets.inventory) {
          const [p, u, l, med, c] = await Promise.all([
            api.products.list(),
            api.units(),
            api.locations(),
            api.media.list(),
            api.colors.list(),
          ])
          products = p
          units = u
          locations = l
          media = med
          colors = c
          materials = []
          sets = []
          allTags = []
          loadedBuckets.catalog = true
          loadedBuckets.inventory = true
        }
        return
      }
      const t = tab
      const jobs = []
      if (!loadedBuckets.catalog) {
        jobs.push(
          Promise.all([api.units(), api.locations(), api.media.list(), api.colors.list(), api.tags.list()]).then(
            ([u, l, med, c, tags]) => {
              units = u
              locations = l
              media = med
              colors = c
              allTags = tags
              const drafts = { ...catalogNewColorDrafts }
              for (const row of med) {
                if (drafts[row.id] == null) drafts[row.id] = ''
              }
              catalogNewColorDrafts = drafts
              if (selectedCatalogMediumId != null && !med.some((x) => x.id === selectedCatalogMediumId)) {
                selectedCatalogMediumId = med[0]?.id ?? null
              } else if (selectedCatalogMediumId == null && med[0]) {
                selectedCatalogMediumId = med[0].id
              }
              if (!materialForm.location_id && l[0]) {
                materialForm.location_id = String(l.find((x) => x.name === 'Hamburg')?.id || l[0].id)
              }
              if (!productForm.location_id && l[0]) {
                productForm.location_id = String(l.find((x) => x.name === 'Hamburg')?.id || l[0].id)
              }
              loadedBuckets.catalog = true
            },
          ),
        )
      }
      if (t !== 'users' && !loadedBuckets.inventory) {
        jobs.push(
          Promise.all([api.materials.list(), api.products.list()]).then(([m, p]) => {
            materials = m
            products = p
            loadedBuckets.inventory = true
          }),
        )
      }
      if (['overview', 'orders', 'todos'].includes(t) && !loadedBuckets.orders) {
        jobs.push(
          Promise.all([api.orders.list(), api.todos.list(), api.orders.listEtsyMails().catch(() => [])]).then(
            ([o, td, mails]) => {
              orders = o
              todos = td
              etsyMails = mails || []
              loadedBuckets.orders = true
            },
          ),
        )
      }
      if (['sets', 'import'].includes(t) && !loadedBuckets.sets) {
        jobs.push(
          api.sets.list().then((s) => {
            sets = s
            loadedBuckets.sets = true
          }),
        )
      }
      if (!loadedBuckets.queue) {
        jobs.push(
          loadImportQueue().then(() => {
            loadedBuckets.queue = true
          }),
        )
      }
      await Promise.all(jobs)
      if (t === 'users') await loadUsers()
    } catch (error) {
      if (error.status === 401) {
        authUser = null
        return
      }
      showFlash('error', error.message)
    } finally {
      if (!silent) loading = false
    }
  }

  async function bootstrapAuth() {
    loading = true
    try {
      authUser = await api.auth.me()
      if (authUser.role === 'mitarbeiter') tab = 'staff'
      await refresh({ silent: true })
    } catch (error) {
      authUser = null
      if (error.status !== 401) showFlash('error', error.message)
    } finally {
      authChecked = true
      loading = false
    }
  }

  async function doLogin() {
    saving = true
    try {
      authUser = await api.auth.login({
        username: loginForm.username.trim(),
        password: loginForm.password,
      })
      loginForm = { username: '', password: '' }
      if (authUser.role === 'mitarbeiter') tab = 'staff'
      else tab = 'overview'
      await refresh({ silent: true })
      showFlash('ok', `Angemeldet als ${authUser.username}`)
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function doLogout() {
    try {
      await api.auth.logout()
    } catch {
      /* ignore */
    }
    authUser = null
    tab = 'overview'
  }

  async function loadUsers() {
    users = await api.users.list()
  }

  async function createUserAccount() {
    if (!userForm.username.trim() || !userForm.password) return
    saving = true
    try {
      await api.users.create({
        username: userForm.username.trim(),
        password: userForm.password,
        role: userForm.role,
      })
      userForm = { username: '', password: '', role: 'mitarbeiter' }
      await loadUsers()
      showFlash('ok', 'Benutzer angelegt.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function patchUser(id, body) {
    saving = true
    try {
      const updated = await api.users.update(id, body)
      await loadUsers()
      if (authUser && updated.id === authUser.id) {
        authUser = updated
        if (authUser.role === 'mitarbeiter') tab = 'staff'
      }
      showFlash('ok', 'Benutzer aktualisiert.')
    } catch (error) {
      showFlash('error', error.message)
      await loadUsers()
    } finally {
      saving = false
    }
  }

  async function submitPasswordChange() {
    if (passwordForm.new_password !== passwordForm.confirm) {
      showFlash('error', 'Neues Passwort stimmt nicht überein.')
      return
    }
    saving = true
    try {
      await api.auth.changePassword({
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      })
      passwordModal = false
      passwordForm = { current_password: '', new_password: '', confirm: '' }
      showFlash('ok', 'Passwort geändert.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  onMount(bootstrapAuth)

  const LOCATION_ORDER = ['Hamburg', 'Dahlenburg', 'In Bearbeitung', 'MA1', 'MA2', 'Ausschuss']
  const MATERIAL_LOCATION_ORDER = ['Hamburg', 'Dahlenburg']
  const STAFF_LOCATION_NAMES = ['MA1', 'MA2']

  function sortByLocationOrder(list, order) {
    return [...list].sort((a, b) => {
      const ia = order.indexOf(a.name)
      const ib = order.indexOf(b.name)
      return (ia === -1 ? 1000 : ia) - (ib === -1 ? 1000 : ib) || a.name.localeCompare(b.name)
    })
  }

  /** Produkte: alle Standorte inkl. virtuelle. */
  const orderedLocations = $derived(sortByLocationOrder(locations, LOCATION_ORDER))

  /** Materialien: nur physische Standorte Hamburg/Dahlenburg. */
  const materialLocations = $derived(
    sortByLocationOrder(
      locations.filter((l) => MATERIAL_LOCATION_ORDER.includes(l.name)),
      MATERIAL_LOCATION_ORDER,
    ),
  )

  function isCritical(item) {
    const total = Number(item.stock_total)
    if (total <= 0) return true
    if (item.min_stock != null && item.min_stock !== '' && total < Number(item.min_stock)) return true
    return false
  }

  const criticalMaterials = $derived(
    materials.filter((item) => isCritical(item) && !item.overview_ignored),
  )
  const criticalProducts = $derived(
    products.filter((item) => isCritical(item) && !item.overview_ignored),
  )
  const ignoredCriticalMaterials = $derived(
    materials.filter((item) => isCritical(item) && item.overview_ignored),
  )
  const ignoredCriticalProducts = $derived(
    products.filter((item) => isCritical(item) && item.overview_ignored),
  )
  const negativeMaterials = $derived(materials.filter((item) => item.is_negative))
  const negativeProducts = $derived(products.filter((item) => item.is_negative))
  const currentOrders = $derived(orders.filter((o) => o.status === 'open' || o.status === 'ready'))
  const reviewOrders = $derived(orders.filter((o) => o.status === 'review'))
  const shippedOrders = $derived(orders.filter((o) => o.status === 'shipped'))
  const overviewOpenTodos = $derived(
    todos.filter((t) => t.status === 'open' && t.category !== 'purchase' && t.order_id),
  )
  const incompleteMaterials = $derived(
    materials.filter((item) => Array.isArray(item.incomplete_fields) && item.incomplete_fields.length),
  )
  const incompleteProducts = $derived(
    products.filter((item) => Array.isArray(item.incomplete_fields) && item.incomplete_fields.length),
  )
  const hasProductTemplates = $derived(products.some((p) => p.is_template))
  const hasMaterialTemplates = $derived(materials.some((m) => m.is_template))
  const productsForBomTemplate = $derived(
    [...products].sort((a, b) => {
      if (!!a.is_template !== !!b.is_template) return a.is_template ? -1 : 1
      return a.name.localeCompare(b.name, 'de')
    }),
  )
  const materialsForSeriesTemplate = $derived.by(() => {
    const mid = bulkMaterialModal?.mediumId != null ? Number(bulkMaterialModal.mediumId) : null
    const templates = materials.filter((m) => m.is_template)
    return [...templates].sort((a, b) => {
      const aMatch = mid != null && a.color?.medium_id === mid
      const bMatch = mid != null && b.color?.medium_id === mid
      if (aMatch !== bMatch) return aMatch ? -1 : 1
      return a.name.localeCompare(b.name, 'de')
    })
  })

  function stockAt(item, locationId) {
    const row = item.stocks?.find((s) => s.location_id === locationId)
    return row ? Number(row.quantity) : 0
  }

  function toggleListSort(block, columnKey) {
    const cur = listUi[block]
    const next = nextSortState(cur.sortKey, cur.sortDir, columnKey)
    listUi[block] = { ...cur, ...next }
  }

  function stockRowSearchText(item, locs) {
    const parts = [
      item.name,
      colorTagMeta(item),
      item.unit,
      formatMinStock(item) ? `Min. ${formatMinStock(item)}` : '',
      formatQty(item.stock_total, itemDecimals(item)),
      item.is_negative ? 'negativ' : '',
      ...locs.map((loc) => `${loc.name} ${formatQty(stockAt(item, loc.id), itemDecimals(item))}`),
    ]
    return parts.filter(Boolean).join(' ')
  }

  function stockSortGetter(sortKey) {
    if (sortKey === 'total') return (row) => Number(row.stock_total)
    if (sortKey === 'updated_at') return (row) => row.updated_at || ''
    if (sortKey === 'created_at') return (row) => row.created_at || ''
    if (typeof sortKey === 'string' && sortKey.startsWith('stock:')) {
      const locId = Number(sortKey.slice(6))
      return (row) => stockAt(row, locId)
    }
    return (row) => row.name
  }

  function setRowSearchText(setItem) {
    return [setItem.name, String(setItem.variant_count ?? ''), setStatus(setItem)].join(' ')
  }

  function setSortGetter(sortKey) {
    if (sortKey === 'variant_count') return (row) => Number(row.variant_count)
    if (sortKey === 'status') return (row) => setStatus(row)
    return (row) => row.name
  }

  function variantBomSearchText(variant) {
    const bom = (variant.bom || [])
      .map((line) => {
        const stock = line.stock_total != null ? ` Lager ${formatQty(line.stock_total, line.decimal_places ?? 0)}` : ''
        return `${line.component_name} ${formatQty(line.quantity_required, line.decimal_places ?? 0)}${stock}`
      })
      .join(' ')
    return [variant.label, String(variant.buildable_quantity ?? ''), bom || 'keine Stückliste'].join(' ')
  }

  function variantSortGetter(sortKey) {
    if (sortKey === 'buildable_quantity') return (row) => Number(row.buildable_quantity)
    if (sortKey === 'bom') {
      return (row) =>
        (row.bom || []).map((l) => `${l.component_name} ${l.quantity_required}`).join(' ') || ''
    }
    return (row) => row.label
  }

  const displayedOverviewMaterials = $derived.by(() => {
    return prepareRows(
      criticalMaterials,
      listUi.overviewMaterials,
      (m) => stockRowSearchText(m, materialLocations),
      stockSortGetter(listUi.overviewMaterials.sortKey),
    )
  })
  const overviewMaterialGroups = $derived(groupProductsByFamily(displayedOverviewMaterials))
  const displayedOverviewProducts = $derived(
    prepareRows(
      criticalProducts,
      listUi.overviewProducts,
      (p) => stockRowSearchText(p, orderedLocations),
      stockSortGetter(listUi.overviewProducts.sortKey),
    ),
  )
  const overviewProductGroups = $derived(groupProductsByFamily(displayedOverviewProducts))
  const displayedMaterials = $derived.by(() => {
    return prepareRows(
      applyCatalogFilter(materials, catalogFilter, colors, media),
      { ...listUi.materials, q: catalogFilter.q },
      (m) => stockRowSearchText(m, materialLocations),
      stockSortGetter(listUi.materials.sortKey),
    )
  })
  const materialFamilies = $derived(collectProductFamilies(materials))
  const materialGroups = $derived(groupProductsByFamily(displayedMaterials))
  const displayedProducts = $derived(
    prepareRows(
      applyCatalogFilter(products, catalogFilter, colors, media),
      { ...listUi.products, q: catalogFilter.q },
      (p) => stockRowSearchText(p, orderedLocations),
      stockSortGetter(listUi.products.sortKey),
    ),
  )
  /** Vorhandene Produktfamilien für den Filter (ohne Leerwerte). */
  const productFamilies = $derived(collectProductFamilies(products))
  const catalogFilterFamilies = $derived(
    [...new Set([...productFamilies, ...materialFamilies])].sort((a, b) => a.localeCompare(b, 'de')),
  )
  const displayedIncompleteProducts = $derived(
    prepareRows(
      incompleteProducts,
      { ...listUi.overviewProducts, q: '' },
      (p) => stockRowSearchText(p, orderedLocations),
      stockSortGetter('name'),
    ),
  )
  const displayedIncompleteMaterials = $derived(
    prepareRows(
      incompleteMaterials,
      { ...listUi.overviewMaterials, q: '' },
      (m) => stockRowSearchText(m, materialLocations),
      stockSortGetter('name'),
    ),
  )
  const extraCriticalMaterials = $derived(
    prepareRows(
      applyCatalogFilter(criticalMaterials, catalogFilter, colors, media),
      { q: catalogFilter.q, sortKey: 'name', sortDir: 'asc' },
      (m) => stockRowSearchText(m, materialLocations),
      stockSortGetter('name'),
    ),
  )
  const extraIncompleteMaterials = $derived(
    prepareRows(
      applyCatalogFilter(incompleteMaterials, catalogFilter, colors, media),
      { q: catalogFilter.q, sortKey: 'name', sortDir: 'asc' },
      (m) => stockRowSearchText(m, materialLocations),
      stockSortGetter('name'),
    ),
  )
  const extraCriticalProducts = $derived(
    prepareRows(
      applyCatalogFilter(criticalProducts, catalogFilter, colors, media),
      { q: catalogFilter.q, sortKey: 'name', sortDir: 'asc' },
      (p) => stockRowSearchText(p, materialLocations),
      stockSortGetter('name'),
    ),
  )
  const extraIncompleteProducts = $derived(
    prepareRows(
      applyCatalogFilter(incompleteProducts, catalogFilter, colors, media),
      { q: catalogFilter.q, sortKey: 'name', sortDir: 'asc' },
      (p) => stockRowSearchText(p, materialLocations),
      stockSortGetter('name'),
    ),
  )
  const extraIgnoredMaterials = $derived(
    prepareRows(
      applyCatalogFilter(ignoredCriticalMaterials, catalogFilter, colors, media),
      { q: catalogFilter.q, sortKey: 'name', sortDir: 'asc' },
      (m) => stockRowSearchText(m, materialLocations),
      stockSortGetter('name'),
    ),
  )
  const extraIgnoredProducts = $derived(
    prepareRows(
      applyCatalogFilter(ignoredCriticalProducts, catalogFilter, colors, media),
      { q: catalogFilter.q, sortKey: 'name', sortDir: 'asc' },
      (p) => stockRowSearchText(p, materialLocations),
      stockSortGetter('name'),
    ),
  )
  const incompleteProductGroups = $derived(groupProductsByFamily(displayedIncompleteProducts))
  const incompleteMaterialGroups = $derived(groupProductsByFamily(displayedIncompleteMaterials))
  const bomQtyStep = $derived.by(() => {
    if (bomForm.kind === 'product') return qtyStep(0)
    const mat = materials.find((m) => String(m.id) === String(bomForm.material_id))
    return qtyStep(itemDecimals(mat))
  })
  const productGroups = $derived(groupProductsByFamily(displayedProducts))
  const staffQueueProducts = $derived.by(() => {
    const maLocs = locations.filter((l) => STAFF_LOCATION_NAMES.includes(l.name))
    return products.filter((p) => {
      if (!p.transform_target_id) return false
      return maLocs.some((loc) => Number(stockAt(p, loc.id)) > 0)
    })
  })
  const displayedStaffQueue = $derived(
    prepareRows(
      staffQueueProducts,
      listUi.staff,
      (p) =>
        [p.name, p.transform_target_name, colorTagMeta(p), ...STAFF_LOCATION_NAMES]
          .filter(Boolean)
          .join(' '),
      listUi.staff.sortKey || 'name',
    ),
  )
  const displayedSets = $derived(
    prepareRows(sets, listUi.sets, setRowSearchText, setSortGetter(listUi.sets.sortKey)),
  )
  const displayedCatalogTags = $derived(
    prepareRows(allTags, listUi.catalogTags, (t) => t.name, listUi.catalogTags.sortKey || 'name'),
  )
  const displayedCatalogMedia = $derived.by(() => {
    const q = String(listUi.catalogColors.q ?? '')
      .trim()
      .toLowerCase()
    const dir = listUi.catalogColors.sortDir || 'asc'
    return media
      .map((m) => {
        const all = colorsForMedium(m.id)
        const mediumHit = q && m.name.toLowerCase().includes(q)
        const colorsFiltered = q && !mediumHit ? filterRows(all, q, (c) => c.name) : all
        return {
          medium: m,
          colors: sortRows(colorsFiltered, (c) => c.name, dir),
          visible: !q || mediumHit || colorsFiltered.length > 0,
        }
      })
      .filter((block) => block.visible)
  })

  function parseOptionalQty(value) {
    if (value === '' || value === null || value === undefined) return null
    const n = Number(value)
    return Number.isFinite(n) ? n : null
  }

  function formatMinStock(item) {
    if (item.min_stock == null || item.min_stock === '') return ''
    return formatQty(item.min_stock, itemDecimals(item))
  }

  function initStockDrafts(item) {
    const drafts = {}
    for (const loc of locations) {
      const existing = item.stocks?.find((s) => s.location_id === loc.id)
      drafts[loc.id] = {
        setValue: existing ? String(existing.quantity) : '0',
        deltaValue: '1',
      }
    }
    stockDrafts = drafts
  }

  function visibleGroupItemIds(groups) {
    const ids = []
    for (const group of groups || []) {
      if (collapsedFamilies[group.key] !== false) continue
      for (const row of group.rows || []) {
        if (row?.id != null) ids.push(row.id)
      }
    }
    return ids
  }

  function beginEditNav(kind, ids, currentId) {
    const list = Array.isArray(ids) ? ids.map((id) => Number(id)).filter((id) => Number.isFinite(id)) : []
    const index = list.indexOf(Number(currentId))
    if (list.length < 2 || index < 0) {
      editNav = null
      return
    }
    editNav = { kind, ids: list, index }
  }

  function captureEditBaseline(kind) {
    editFormBaseline = JSON.stringify(kind === 'material' ? materialForm : productForm)
  }

  function editFormDirty(kind) {
    return JSON.stringify(kind === 'material' ? materialForm : productForm) !== editFormBaseline
  }

  function navItemExists(kind, id) {
    const rows = kind === 'material' ? materials : products
    return rows.some((row) => Number(row.id) === Number(id))
  }

  function editNavNeighbor(delta) {
    if (!editNav) return -1
    let i = editNav.index + delta
    while (i >= 0 && i < editNav.ids.length) {
      if (navItemExists(editNav.kind, editNav.ids[i])) return i
      i += delta
    }
    return -1
  }

  const showEditNav = $derived(
    !!editNav && (materialModal?.mode === 'edit' || productModal?.mode === 'edit'),
  )
  const editNavHasPrev = $derived.by(() => {
    if (!editNav) return false
    const rows = editNav.kind === 'material' ? materials : products
    for (let i = editNav.index - 1; i >= 0; i--) {
      const id = editNav.ids[i]
      if (rows.some((row) => Number(row.id) === Number(id))) return true
    }
    return false
  })
  const editNavHasNext = $derived.by(() => {
    if (!editNav) return false
    const rows = editNav.kind === 'material' ? materials : products
    for (let i = editNav.index + 1; i < editNav.ids.length; i++) {
      const id = editNav.ids[i]
      if (rows.some((row) => Number(row.id) === Number(id))) return true
    }
    return false
  })

  function closeMaterialModal() {
    materialModal = null
    editNav = null
  }

  function closeProductModal() {
    productModal = null
    editNav = null
  }

  async function stepEditNav(delta) {
    if (!editNav || saving) return
    const kind = editNav.kind
    if (editFormDirty(kind)) {
      const ok = kind === 'material' ? await saveMaterial({ keepOpen: true }) : await saveProduct({ keepOpen: true })
      if (!ok) return
    }
    const nextIndex = editNavNeighbor(delta)
    if (nextIndex < 0) return
    const id = editNav.ids[nextIndex]
    const item = (kind === 'material' ? materials : products).find((row) => Number(row.id) === Number(id))
    if (!item) return
    editNav = { ...editNav, index: nextIndex }
    if (kind === 'material') openEditMaterial(item, { keepNav: true })
    else openEditProduct(item, { keepNav: true })
  }

  function openCreateMaterial(template = null, { name = '', orderLink = null } = {}) {
    editNav = null
    materialForm = emptyMaterial()
    materialForm.location_id = String(locations.find((x) => x.name === 'Hamburg')?.id || locations[0]?.id || '')
    showMaterialTags = false
    if (name) materialForm.name = name
    if (template) {
      const mid = mediumIdFromColor(template.color_id)
      materialForm = {
        ...materialForm,
        name: `${template.name} (Kopie)`,
        unit: template.unit,
        purchase_quantity: String(template.purchase_quantity ?? 1),
        purchase_price: String(template.purchase_price ?? template.cost_per_unit ?? 0),
        min_stock: template.min_stock != null ? qtyInputValue(template.min_stock, itemDecimals(template)) : '',
        family: template.family || '',
        decimal_places: itemDecimals(template),
        stock_quantity: '0',
        medium_id: mid,
        color_id: template.color_id ? String(template.color_id) : '',
        tagIds: (template.tags || []).map((t) => t.id),
      }
      showMaterialTags = materialForm.tagIds.length > 0
    }
    materialModal = { mode: 'create', orderLink }
  }

  function openEditMaterial(material, { ids, keepNav = false } = {}) {
    if (!keepNav) beginEditNav('material', ids, material.id)
    const mid = mediumIdFromColor(material.color_id) || (material.color?.medium_id ? String(material.color.medium_id) : '')
    materialForm = {
      name: material.name,
      unit: material.unit,
      stock_quantity: '0',
      purchase_quantity: String(material.purchase_quantity ?? 1),
      purchase_price: String(material.purchase_price ?? material.cost_per_unit ?? 0),
      min_stock: material.min_stock != null ? qtyInputValue(material.min_stock, itemDecimals(material)) : '',
      is_template: !!material.is_template,
      decimal_places: itemDecimals(material),
      family: material.family || '',
      location_id: '',
      medium_id: mid,
      color_id: material.color_id ? String(material.color_id) : '',
      tagIds: (material.tags || []).map((t) => t.id),
    }
    showMaterialTags = materialForm.tagIds.length > 0
    initStockDrafts(material)
    materialModal = { mode: 'edit', id: material.id, material }
    captureEditBaseline('material')
  }

  function openCreateProduct(template = null, { name = '', sku = '', family = '', mediumId = '', colorId = '', orderLink = null } = {}) {
    editNav = null
    productForm = emptyProduct()
    productForm.location_id = String(locations.find((x) => x.name === 'Hamburg')?.id || locations[0]?.id || '')
    inlineMaterialForm = null
    colorSuggestions = []
    showProductTags = false
    if (template) {
      const mid = mediumIdFromColor(template.color_id)
      productForm = {
        ...productForm,
        name: `${template.name} (Kopie)`,
        sku: '',
        selling_price: template.selling_price != null ? String(template.selling_price) : '0',
        stock_quantity: '0',
        min_stock: template.min_stock != null ? qtyInputValue(template.min_stock, 0) : '',
        family: template.family || '',
        medium_id: mid,
        color_id: template.color_id ? String(template.color_id) : '',
        tagIds: (template.tags || []).map((t) => t.id),
      }
      showProductTags = productForm.tagIds.length > 0
    }
    if (name) productForm.name = name
    if (sku) productForm.sku = sku
    if (family) productForm.family = family
    if (mediumId) productForm.medium_id = String(mediumId)
    if (colorId) productForm.color_id = String(colorId)
    productModal = { mode: 'create', product: null, templateBom: template?.bom ? [...template.bom] : [], orderLink }
  }

  /** Shop-Titel → Farbe (eindeutig) + Familie/Basis als Vorschlag. */
  function suggestPrefillFromShopLine(line) {
    const title = String(line?.shop_title || line?.label || '').trim()
    const sku = String(line?.shop_sku || '').trim()
    const tokens = title.split(/[\s,;|/–—\-]+/).filter((t) => t.length > 1)
    const hitIds = new Set()
    const hits = []
    for (const token of tokens) {
      for (const c of matchColorsPool(colors, token)) {
        if (!hitIds.has(c.id)) {
          hitIds.add(c.id)
          hits.push(c)
        }
      }
    }
    for (const c of colors) {
      if (title.toLowerCase().includes(String(c.name || '').toLowerCase()) && !hitIds.has(c.id)) {
        hitIds.add(c.id)
        hits.push(c)
      }
    }
    let colorId = ''
    let mediumId = ''
    let family = ''
    if (hits.length === 1) {
      const c = hits[0]
      colorId = String(c.id)
      mediumId = c.medium_id ? String(c.medium_id) : mediumIdFromColor(c.id)
      const colorName = c.name
      let base = title
      const inRe = new RegExp(`\\s+in\\s+${colorName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}.*$`, 'i')
      base = base.replace(inRe, '').trim()
      if (base.toLowerCase().endsWith(colorName.toLowerCase())) {
        base = base.slice(0, base.length - colorName.length).trim()
      }
      base = base.split(/[–—|]/)[0].trim()
      family = base.slice(0, 120)
    } else {
      family = title.split(/[–—|]/)[0].trim().slice(0, 120)
    }
    return { name: title, sku, family, mediumId, colorId }
  }

  function openCreateProductFromOrderLine(order, line) {
    const pre = suggestPrefillFromShopLine(line)
    openCreateProduct(null, {
      ...pre,
      orderLink: { orderId: order.id, lineId: line.id },
    })
  }

  async function queueCreateArticleFromReview(order, line) {
    saving = true
    try {
      const result = await api.orders.queueCreate(order.id, line.id)
      loadedBuckets.orders = false
      await refresh()
      const notice = (result.notices || [])[0]
      showFlash('ok', notice === 'bereits vorgemerkt' ? 'Bereits vorgemerkt.' : 'Auf Anlege-Liste (Todos).')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  function openEditProduct(product, { ids, keepNav = false } = {}) {
    if (!keepNav) beginEditNav('product', ids, product.id)
    const mid = mediumIdFromColor(product.color_id) || (product.color?.medium_id ? String(product.color.medium_id) : '')
    productForm = {
      name: product.name,
      sku: product.sku || '',
      selling_price: product.selling_price != null ? String(product.selling_price) : '0',
      stock_quantity: '0',
      min_stock: product.min_stock != null ? qtyInputValue(product.min_stock, 0) : '',
      is_template: !!product.is_template,
      family: product.family || '',
      location_id: '',
      medium_id: mid,
      color_id: product.color_id ? String(product.color_id) : '',
      transform_target_id: product.transform_target_id ? String(product.transform_target_id) : '',
      tagIds: (product.tags || []).map((t) => t.id),
    }
    showProductTags = productForm.tagIds.length > 0
    bomForm = { kind: 'material', material_id: '', product_id: '', quantity_required: '' }
    initStockDrafts(product)
    productModal = { mode: 'edit', product }
    loadColorSuggestions(product.color_id)
    captureEditBaseline('product')
  }

  async function loadColorSuggestions(colorId) {
    if (!colorId) {
      colorSuggestions = []
      return
    }
    try {
      colorSuggestions = await api.suggestions.byColor(colorId, { materials: true, products: true })
    } catch {
      colorSuggestions = []
    }
  }

  async function loadOptionSuggestions(value) {
    if (!value) {
      colorSuggestions = []
      return
    }
    try {
      colorSuggestions = await api.suggestions.byOptionValue(value)
    } catch {
      colorSuggestions = []
    }
  }

  function catalogCellKey(kind, id, field = 'name') {
    return `${kind}:${id}:${field}`
  }

  function catalogCellValue(kind, id, field, fallback) {
    const key = catalogCellKey(kind, id, field)
    if (catalogEdit?.key === key) return catalogEdit.value
    return String(fallback ?? '')
  }

  function beginCatalogEdit(kind, id, field, current) {
    if (kind === 'tag') {
      const tag = allTags.find((t) => t.id === id)
      if (tag?.is_system) return
    }
    const key = catalogCellKey(kind, id, field)
    if (catalogEdit?.key === key) return
    const value = String(current ?? '')
    catalogEdit = { key, original: value, value }
  }

  function setCatalogEditValue(kind, id, field, value) {
    const key = catalogCellKey(kind, id, field)
    if (catalogEdit?.key !== key) return
    catalogEdit = { ...catalogEdit, value }
  }

  function cancelCatalogEdit(event) {
    if (event) event.preventDefault()
    catalogEdit = null
    if (event?.currentTarget && typeof event.currentTarget.blur === 'function') {
      event.currentTarget.blur()
    }
  }

  async function commitCatalogEdit() {
    if (!catalogEdit || catalogSavingKey) return
    const { key, original, value } = catalogEdit
    const [kind, idStr, field] = key.split(':')
    const id = Number(idStr)
    const trimmed = String(value ?? '').trim()
    const orig = String(original ?? '').trim()

    if (trimmed === orig) {
      if (catalogEdit?.key === key) catalogEdit = null
      return
    }
    if (field === 'name' && !trimmed) {
      if (catalogEdit?.key === key) catalogEdit = null
      return
    }

    catalogSavingKey = key
    saving = true
    try {
      if (kind === 'media') {
        const result = await api.media.update(id, { name: trimmed })
        flashRenameResult('Medium umbenannt.', result)
      } else if (kind === 'color') {
        if (field === 'medium_id') {
          const result = await api.colors.update(id, { medium_id: Number(trimmed) })
          flashRenameResult('Medium der Farbe geändert.', result)
        } else {
          const result = await api.colors.update(id, { name: trimmed })
          flashRenameResult('Farbe umbenannt.', result)
        }
      } else if (kind === 'tag') {
        await api.tags.update(id, { name: trimmed })
        showFlash('ok', 'Tag umbenannt.')
      }
      if (catalogEdit?.key === key) catalogEdit = null
      await refresh({ silent: true })
    } catch (error) {
      showFlash('error', error.message)
      if (catalogEdit?.key === key || !catalogEdit) {
        catalogEdit = { key, original, value: original }
      }
    } finally {
      saving = false
      catalogSavingKey = ''
    }
  }

  async function saveColorHex(color, hex) {
    const next = String(hex || '').trim().toUpperCase()
    const prev = String(color.hex || '').trim().toUpperCase()
    if (next === prev || saving) return
    saving = true
    try {
      await api.colors.update(color.id, { hex: next || null })
      await refresh({ silent: true })
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  function onCatalogEditKeydown(event) {
    if (event.key === 'Enter') {
      event.preventDefault()
      event.currentTarget.blur()
    } else if (event.key === 'Escape') {
      cancelCatalogEdit(event)
    }
  }

  async function commitNewMedia() {
    const name = catalogNewMedia.trim()
    if (!name || saving) return
    saving = true
    catalogSavingKey = 'new:media'
    try {
      const created = await api.media.create({ name })
      catalogNewMedia = ''
      await refresh({ silent: true })
      selectedCatalogMediumId = created.id
      showFlash('ok', `Medium „${name}“ angelegt.`)
      queueMicrotask(() => document.querySelector('[data-catalog-new-media]')?.focus())
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
      catalogSavingKey = ''
    }
  }

  function onNewMediaKeydown(event) {
    if (event.key === 'Enter') {
      event.preventDefault()
      commitNewMedia()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      catalogNewMedia = ''
      event.currentTarget.blur()
    }
  }

  async function commitNewColor(mediumId) {
    const name = String(catalogNewColorDrafts[mediumId] || '').trim()
    const mid = Number(mediumId)
    if (!name || !mid || saving) return
    saving = true
    catalogSavingKey = `new:color:${mid}`
    try {
      await api.colors.create({ name, medium_id: mid })
      catalogNewColorDrafts = { ...catalogNewColorDrafts, [mid]: '' }
      await refresh({ silent: true })
      showFlash('ok', `Farbe „${name}“ angelegt.`)
      queueMicrotask(() => document.querySelector(`[data-catalog-new-color="${mid}"]`)?.focus())
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
      catalogSavingKey = ''
    }
  }

  function onNewColorKeydown(event, mediumId) {
    if (event.key === 'Enter') {
      event.preventDefault()
      commitNewColor(mediumId)
    } else if (event.key === 'Escape') {
      event.preventDefault()
      catalogNewColorDrafts = { ...catalogNewColorDrafts, [mediumId]: '' }
      event.currentTarget.blur()
    }
  }

  async function commitNewTag() {
    const name = catalogNewTag.trim()
    if (!name || saving) return
    saving = true
    catalogSavingKey = 'new:tag'
    try {
      await api.tags.create({ name })
      catalogNewTag = ''
      await refresh({ silent: true })
      showFlash('ok', `Tag „${name}“ angelegt.`)
      queueMicrotask(() => document.querySelector('[data-catalog-new-tag]')?.focus())
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
      catalogSavingKey = ''
    }
  }

  function onNewTagKeydown(event) {
    if (event.key === 'Enter') {
      event.preventDefault()
      commitNewTag()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      catalogNewTag = ''
      event.currentTarget.blur()
    }
  }

  async function deleteCatalogMedium(item) {
    const colorCount = colors.filter((c) => c.medium_id === item.id).length
    if (colorCount > 0) {
      const ok = confirm(
        `Medium „${item.name}“ wirklich löschen?\n\n` +
          `Achtung: Alle ${colorCount} Farbe(n) dieses Mediums werden gelöscht. ` +
          `An Materialien und Produkten wird die Farbe entfernt.`,
      )
      if (!ok) return
    }
    saving = true
    try {
      await api.media.remove(item.id)
      await refresh({ silent: true })
      showFlash('ok', `Medium „${item.name}“ gelöscht.`)
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function deleteCatalogColor(item) {
    if (!confirm(`Farbe „${item.name}“ löschen?`)) return
    saving = true
    try {
      await api.colors.remove(item.id)
      await refresh({ silent: true })
      showFlash('ok', `Farbe „${item.name}“ gelöscht.`)
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function deleteCatalogTag(item) {
    saving = true
    try {
      await api.tags.remove(item.id)
      await refresh({ silent: true })
      showFlash('ok', `Tag „${item.name}“ gelöscht.`)
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  function applySuggestion(s) {
    if (productModal && s.kind === 'material') {
      bomForm.kind = 'material'
      bomForm.material_id = String(s.id)
      bomForm.product_id = ''
    } else if (productModal && s.kind === 'product') {
      bomForm.kind = 'product'
      bomForm.product_id = String(s.id)
      bomForm.material_id = ''
    } else if (setModal) {
      mappingForm.kind = s.kind
      mappingForm.component_id = String(s.id)
    }
  }

  function openManufacture(product, { quantity = null, todoId = null } = {}) {
    manufactureForm = {
      quantity: quantity != null ? String(quantity) : '1',
      location_id: String(locations.find((x) => x.name === 'Hamburg')?.id || locations[0]?.id || ''),
    }
    manufactureTodoId = todoId
    manufactureModal = product
  }

  function openPurchase(material) {
    purchaseForm = {
      quantity: '',
      location_id: String(
        materialLocations.find((x) => x.name === 'Hamburg')?.id || materialLocations[0]?.id || '',
      ),
      purchase_price: String(material.purchase_price ?? 0),
    }
    purchaseModal = material
  }

  function openTransfer(kind, item) {
    transferForm = {
      from_location_id: String(item.stocks[0]?.location_id || locations[0]?.id || ''),
      to_location_id: String(locations.find((x) => x.name === 'In Bearbeitung')?.id || locations[1]?.id || ''),
      quantity: '1',
      note: '',
    }
    transferModal = { kind, item }
  }

  function canTransformProduct(product) {
    if (!product?.transform_target_id) return false
    return String(product.name || '').toLowerCase().includes('uni')
  }

  function openTransform(product, preferredLocationName = null) {
    if (!canTransformProduct(product)) {
      showFlash(
        'error',
        product?.transform_target_id
          ? 'Umwandlung nur für Produkte mit „Uni“ im Namen.'
          : 'Kein Zielprodukt verknüpft — unter Bearbeiten „Wird zu“ setzen.',
      )
      return
    }
    const maLoc =
      locations.find((x) => x.name === preferredLocationName) ||
      locations.find((x) => x.name === 'MA1' && Number(stockAt(product, x.id)) > 0) ||
      locations.find((x) => x.name === 'MA2' && Number(stockAt(product, x.id)) > 0) ||
      locations.find((x) => x.name === 'MA1')
    transformForm = {
      location_id: String(maLoc?.id || locations[0]?.id || ''),
      quantity: '1',
      note: '',
    }
    transformModal = product
  }

  async function openMovements(product) {
    try {
      const rows = await api.movements.list({ product_id: product.id, limit: 100 })
      movementsModal = { title: product.name, productId: product.id, rows }
    } catch (error) {
      showFlash('error', error.message)
    }
  }

  async function saveMaterial({ keepOpen = false } = {}) {
    saving = true
    try {
      const colorPayload = {
        color_id: materialForm.color_id ? Number(materialForm.color_id) : null,
      }
      const nextMaterialTags = tagIdsIfChanged(
        materialModal.mode === 'edit' ? materialModal.material?.tags : null,
        materialForm.tagIds,
      )
      if (materialModal.mode === 'create' || nextMaterialTags) {
        colorPayload.tag_ids = materialModal.mode === 'create' ? materialForm.tagIds : nextMaterialTags
      }
      if (materialModal.mode === 'create') {
        const created = await api.materials.create({
          name: materialForm.name.trim(),
          unit: materialForm.unit,
          purchase_quantity: materialForm.purchase_quantity,
          purchase_price: materialForm.purchase_price,
          min_stock: parseOptionalQty(materialForm.min_stock),
          family: materialForm.family.trim() || null,
          decimal_places: itemDecimals(materialForm),
          stock_quantity: materialForm.stock_quantity,
          location_id: Number(materialForm.location_id),
          ...colorPayload,
        })
        if (materialModal.orderLink) {
          await api.orders.linkLine(materialModal.orderLink.orderId, materialModal.orderLink.lineId, {
            material_id: created.id,
          })
        }
        showFlash('ok', 'Material angelegt.')
        markSaved()
        materialModal = null
        editNav = null
        await refresh()
        return true
      }
      await api.materials.update(materialModal.id, {
        name: materialForm.name.trim(),
        unit: materialForm.unit,
        purchase_quantity: materialForm.purchase_quantity,
        purchase_price: materialForm.purchase_price,
        min_stock: parseOptionalQty(materialForm.min_stock),
        is_template: !!materialForm.is_template,
        family: materialForm.family.trim() || null,
        decimal_places: itemDecimals(materialForm),
        ...colorPayload,
      })
      showFlash('ok', 'Material gespeichert.')
      markSaved()
      await refresh()
      if (keepOpen) {
        const fresh = materials.find((m) => m.id === materialModal.id)
        if (fresh) {
          materialModal = { ...materialModal, material: fresh }
          initStockDrafts(fresh)
          captureEditBaseline('material')
        }
        return true
      }
      materialModal = null
      editNav = null
      return true
    } catch (error) {
      showFlash('error', error.message)
      return false
    } finally {
      saving = false
    }
  }

  async function setMaterialStock(locationId) {
    const draft = stockDrafts[locationId]
    if (!draft || materialModal?.mode !== 'edit') return
    saving = true
    try {
      const updated = await api.materials.adjustStock(materialModal.id, {
        location_id: Number(locationId),
        quantity: draft.setValue,
      })
      materialModal = { ...materialModal, material: updated }
      initStockDrafts(updated)
      await refresh()
      showFlash('ok', 'Bestand gesetzt.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function deltaMaterialStock(locationId, sign) {
    const draft = stockDrafts[locationId]
    if (!draft || materialModal?.mode !== 'edit') return
    const amount = Number(draft.deltaValue)
    if (!amount || amount <= 0) {
      showFlash('error', 'Bitte eine positive Menge für +/− angeben.')
      return
    }
    saving = true
    try {
      const updated = await api.materials.deltaStock(materialModal.id, {
        location_id: Number(locationId),
        delta: sign * amount,
      })
      materialModal = { ...materialModal, material: updated }
      initStockDrafts(updated)
      await refresh()
      showFlash('ok', 'Bestand angepasst.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function removeMaterial(material) {
    if (
      !confirm(
        `Material „${material.name}“ löschen?\n\n` +
          `Falls es in Sets verknüpft ist, werden diese Set-Zuordnungen und Stücklistenzeilen mit entfernt.`,
      )
    )
      return
    try {
      await api.materials.remove(material.id)
      showFlash('ok', 'Material gelöscht.')
      await refresh()
    } catch (error) {
      showFlash('error', error.message)
    }
  }

  async function saveProduct({ keepOpen = false } = {}) {
    saving = true
    try {
      const colorPayload = {
        color_id: productForm.color_id ? Number(productForm.color_id) : null,
        transform_target_id: productForm.transform_target_id
          ? Number(productForm.transform_target_id)
          : null,
      }
      const nextProductTags = tagIdsIfChanged(
        productModal.mode === 'edit' ? productModal.product?.tags : null,
        productForm.tagIds,
      )
      if (productModal.mode === 'create' || nextProductTags) {
        colorPayload.tag_ids = productModal.mode === 'create' ? productForm.tagIds : nextProductTags
      }
      if (productModal.mode === 'create') {
        const created = await api.products.create({
          name: productForm.name.trim(),
          sku: productForm.sku.trim() || null,
          selling_price: productForm.selling_price === '' ? '0' : productForm.selling_price,
          min_stock: parseOptionalQty(productForm.min_stock),
          is_template: !!productForm.is_template,
          family: productForm.family.trim() || null,
          stock_quantity: productForm.stock_quantity,
          location_id: Number(productForm.location_id),
          ...colorPayload,
        })
        // Copy BOM from template if present
        if (productModal.templateBom?.length) {
          for (const line of productModal.templateBom) {
            await api.products.addBom(created.id, {
              material_id: line.material_id,
              quantity_required: line.quantity_required,
            })
          }
        }
        showFlash('ok', 'Produkt angelegt — Stückliste prüfen/ergänzen.')
        markSaved()
        if (productModal.orderLink) {
          await api.orders.linkLine(productModal.orderLink.orderId, productModal.orderLink.lineId, {
            product_id: created.id,
          })
        }
        await refresh()
        const fresh = products.find((p) => p.id === created.id)
        productModal = { mode: 'edit', product: fresh || created }
        const item = fresh || created
        productForm = {
          ...productForm,
          is_template: !!(item.is_template ?? productForm.is_template),
          family: item.family || '',
          medium_id: mediumIdFromColor(item.color_id) || (item.color?.medium_id ? String(item.color.medium_id) : ''),
          color_id: item.color_id ? String(item.color_id) : '',
          tagIds: (item.tags || []).map((t) => t.id),
        }
        initStockDrafts(fresh || created)
        bomForm = { kind: 'material', material_id: '', product_id: '', quantity_required: '' }
        inlineMaterialForm = null
        await loadColorSuggestions((fresh || created).color_id)
        captureEditBaseline('product')
        const mid = productForm.medium_id
        if (mid) {
          const colorName = colors.find((c) => c.id === Number(productForm.color_id))?.name
          let base = productForm.name.trim()
          if (colorName && base.toLowerCase().endsWith(colorName.toLowerCase())) {
            base = base.slice(0, base.length - colorName.length).trim()
          }
          const more = colorsForMedium(mid).filter(
            (c) =>
              c.id !== Number(productForm.color_id) &&
              !isBulkProductColorTaken(base || productForm.name.trim(), c),
          )
          if (
            more.length &&
            confirm(`Auch Produkte für ${more.length} weitere Farbe(n) dieses Mediums anlegen?`)
          ) {
            openBulkProducts({
              mediumId: Number(mid),
              baseName: base || productForm.name.trim(),
              templateProductId: created.id,
            })
          }
        }
        return true
      }
      await api.products.update(productModal.product.id, {
        name: productForm.name.trim(),
        sku: productForm.sku.trim() || null,
        selling_price: productForm.selling_price === '' ? '0' : productForm.selling_price,
        min_stock: parseOptionalQty(productForm.min_stock),
        is_template: !!productForm.is_template,
        family: productForm.family.trim() || null,
        ...colorPayload,
      })
      showFlash('ok', 'Produkt gespeichert.')
      markSaved()
      await refresh()
      const fresh = products.find((p) => p.id === productModal.product.id)
      if (fresh) {
        productModal = { mode: 'edit', product: fresh }
        initStockDrafts(fresh)
        await loadColorSuggestions(fresh.color_id)
        captureEditBaseline('product')
      }
      return true
    } catch (error) {
      showFlash('error', error.message)
      return false
    } finally {
      saving = false
    }
  }

  async function setProductStock(locationId) {
    const draft = stockDrafts[locationId]
    if (!draft || !productModal?.product) return
    saving = true
    try {
      const updated = await api.products.adjustStock(productModal.product.id, {
        location_id: Number(locationId),
        quantity: draft.setValue,
      })
      productModal = { mode: 'edit', product: updated }
      initStockDrafts(updated)
      await refresh()
      showFlash('ok', 'Bestand gesetzt.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function deltaProductStock(locationId, sign) {
    const draft = stockDrafts[locationId]
    if (!draft || !productModal?.product) return
    const amount = Number(draft.deltaValue)
    if (!amount || amount <= 0) {
      showFlash('error', 'Bitte eine positive Menge für +/− angeben.')
      return
    }
    saving = true
    try {
      const updated = await api.products.deltaStock(productModal.product.id, {
        location_id: Number(locationId),
        delta: sign * amount,
      })
      productModal = { mode: 'edit', product: updated }
      initStockDrafts(updated)
      await refresh()
      showFlash('ok', 'Bestand angepasst.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function removeProduct(product) {
    if (!confirm(`Produkt „${product.name}“ löschen?`)) return
    try {
      await api.products.remove(product.id)
      productModal = null
      editNav = null
      showFlash('ok', 'Produkt gelöscht.')
      await refresh()
    } catch (error) {
      showFlash('error', error.message)
    }
  }

  async function addBomLine() {
    if (!productModal?.product) return
    if (!bomForm.quantity_required || Number(bomForm.quantity_required) <= 0) {
      showFlash('error', 'Bitte die Menge pro Produkteinheit angeben (z. B. 0,056).')
      return
    }
    const body = { quantity_required: bomForm.quantity_required }
    if (bomForm.kind === 'product') {
      if (!bomForm.product_id) {
        showFlash('error', 'Bitte ein Produkt für die Stückliste wählen.')
        return
      }
      body.product_id = Number(bomForm.product_id)
    } else {
      if (!bomForm.material_id) {
        showFlash('error', 'Bitte ein Material für die Stückliste wählen.')
        return
      }
      body.material_id = Number(bomForm.material_id)
    }
    saving = true
    try {
      const updated = await api.products.addBom(productModal.product.id, body)
      bomForm = { kind: bomForm.kind, material_id: '', product_id: '', quantity_required: '' }
      await refresh()
      productModal = { mode: 'edit', product: products.find((p) => p.id === updated.id) || updated }
      initStockDrafts(productModal.product)
      showFlash('ok', 'Stücklistenzeile hinzugefügt.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function createInlineMaterial() {
    if (!inlineMaterialForm || !productModal?.product) return
    saving = true
    try {
      const created = await api.materials.create({
        name: inlineMaterialForm.name.trim(),
        unit: inlineMaterialForm.unit,
        purchase_quantity: inlineMaterialForm.purchase_quantity,
        purchase_price: inlineMaterialForm.purchase_price,
        stock_quantity: inlineMaterialForm.stock_quantity,
        location_id: Number(inlineMaterialForm.location_id),
        decimal_places: itemDecimals(inlineMaterialForm),
      })
      await refresh()
      bomForm = { kind: 'material', material_id: String(created.id), product_id: '', quantity_required: bomForm.quantity_required || '' }
      inlineMaterialForm = null
      showFlash('ok', `Material „${created.name}“ angelegt — Menge eintragen und hinzufügen.`)
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function removeBomLine(line) {
    const updated = await api.products.removeBom(productModal.product.id, line.id)
    await refresh()
    productModal = { mode: 'edit', product: products.find((p) => p.id === updated.id) || updated }
  }

  async function runManufacture() {
    saving = true
    try {
      const result = await api.products.manufacture(manufactureModal.id, {
        quantity: manufactureForm.quantity,
        location_id: Number(manufactureForm.location_id),
      })
      if (manufactureTodoId) {
        await api.todos.complete(manufactureTodoId)
        manufactureTodoId = null
      }
      manufactureModal = null
      await refresh()
      showFlash(result.warnings?.length ? 'warn' : 'ok', result.warnings?.join(' ') || 'Fertigung gebucht.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function submitPurchase() {
    if (!purchaseModal) return
    const qty = Number(String(purchaseForm.quantity).replace(',', '.'))
    if (!Number.isFinite(qty) || qty <= 0) {
      showFlash('error', 'Menge muss größer als 0 sein.')
      return
    }
    saving = true
    try {
      await api.materials.update(purchaseModal.id, {
        purchase_price: purchaseForm.purchase_price,
      })
      await api.materials.deltaStock(purchaseModal.id, {
        location_id: Number(purchaseForm.location_id),
        delta: qty,
      })
      purchaseModal = null
      await refresh()
      showFlash('ok', 'Einkauf gespeichert.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function runTransfer() {
    saving = true
    try {
      const body = {
        from_location_id: Number(transferForm.from_location_id),
        to_location_id: Number(transferForm.to_location_id),
        quantity: transferForm.quantity,
        note: transferForm.note?.trim() || null,
      }
      if (transferModal.kind === 'material') await api.materials.transfer(transferModal.item.id, body)
      else await api.products.transfer(transferModal.item.id, body)
      transferModal = null
      await refresh()
      showFlash('ok', 'Umbuchung gespeichert.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function runTransform() {
    if (!transformModal) return
    saving = true
    try {
      await api.products.transform(transformModal.id, {
        location_id: Number(transformForm.location_id),
        quantity: transformForm.quantity,
        note: transformForm.note?.trim() || null,
      })
      transformModal = null
      await refresh()
      showFlash('ok', 'Umwandlung gebucht.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function openSet(setItem, step = null) {
    const full = await api.sets.get(setItem.id)
    setModal = full
    const names = [...new Set(full.variants.flatMap((v) => [v.option1_name, v.option2_name, v.option3_name].filter(Boolean)))]
    mappingForm.option_name = names[0] || ''
    setRowOverrides = {}
    setStep = step != null ? step : 1
  }

  function setStatus(setItem) {
    const mapped = setItem.option_mappings?.length || setItem.mapping_count || 0
    const withBom = setItem.variants?.filter((v) => v.bom?.length)?.length || 0
    const buildable = setItem.variants?.filter((v) => v.buildable_quantity > 0)?.length || 0
    if (!setItem.variant_count) return 'Noch keine Varianten'
    if (!mapped) return 'Schritt 2: Farben zuordnen'
    if (setItem.variants?.length) {
      if (!withBom) return 'Schritt 2: Zuordnung anwenden'
      return `${buildable} von ${setItem.variant_count} baubar`
    }
    return `${setItem.variant_count} Varianten`
  }

  async function onImportFile(event) {
    const file = event.target.files?.[0]
    if (!file) return
    saving = true
    try {
      const preview = await api.sets.previewShopify(file)
      const actions = {}
      for (const h of preview.handles) {
        if (h.ignored) actions[h.handle] = 'ignore'
        else if (h.existing_set_id) actions[h.handle] = 'set'
        else if ((h.option_axes?.length || 0) >= 2) actions[h.handle] = 'skip'
        else actions[h.handle] = 'skip'
      }
      shopifyAssistant = {
        file,
        preview,
        actions,
        showIgnored: false,
      }
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
      event.target.value = ''
    }
  }

  function shopifyAssistantRows() {
    if (!shopifyAssistant?.preview?.handles) return []
    const rows = shopifyAssistant.preview.handles
    if (shopifyAssistant.showIgnored) return rows
    return rows.filter((h) => !h.ignored)
  }

  async function submitShopifyAssistant() {
    if (!shopifyAssistant?.file) return
    const items = Object.entries(shopifyAssistant.actions)
      .filter(([, action]) => action && action !== 'skip')
      .map(([handle, action]) => ({ handle, action }))
    if (!items.length) {
      showFlash('error', 'Mindestens eine Aktion wählen (nicht nur „überspringen“).')
      return
    }
    saving = true
    try {
      const result = await api.sets.applyShopify(shopifyAssistant.file, items)
      shopifyAssistant = null
      await refresh()
      if (result.selling_price_conflicts?.length) {
        sellingPriceConflicts = result.selling_price_conflicts
        sellingPriceStage = 'ask'
        sellingPricePicks = Object.fromEntries(result.selling_price_conflicts.map((c) => [c.product_id, 'csv']))
      }
      showFlash('ok', result.message)
      if (result.queue_upserted > 0) {
        tab = 'import'
        showFlash(
          'ok',
          `${result.queue_upserted} Eintrag/Einträge in der Import-Warteschlange — dort Serienanlage starten.`,
        )
      }
      if (result.set_ids?.length === 1) {
        const created = sets.find((s) => s.id === result.set_ids[0])
        if (created) await openSet(created, 2)
      }
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function openIgnoredHandles() {
    try {
      ignoredHandles = await api.sets.listIgnoredHandles()
      ignoredHandlesModal = true
    } catch (error) {
      showFlash('error', error.message)
    }
  }

  async function restoreIgnoredHandle(handle) {
    try {
      await api.sets.unignoreHandle(handle)
      ignoredHandles = ignoredHandles.filter((h) => h.handle !== handle)
      showFlash('ok', `„${handle}“ wieder in der Übersicht.`)
    } catch (error) {
      showFlash('error', error.message)
    }
  }

  function openSetCleanup() {
    // Vorauswahl: alles außer typischen Geburtstagssets
    setCleanupIds = sets
      .filter((s) => !String(s.handle || '').includes('geburtstagsset'))
      .map((s) => s.id)
    setCleanupModal = true
  }

  function toggleSetCleanupId(id) {
    if (setCleanupIds.includes(id)) setCleanupIds = setCleanupIds.filter((x) => x !== id)
    else setCleanupIds = [...setCleanupIds, id]
  }

  async function submitSetCleanup() {
    if (!setCleanupIds.length) {
      showFlash('error', 'Keine Sets ausgewählt.')
      return
    }
    if (!confirm(`${setCleanupIds.length} Set(s) unwiderruflich löschen? Lagerprodukte bleiben erhalten.`)) return
    saving = true
    try {
      const result = await api.sets.bulkDelete({ ids: setCleanupIds })
      setCleanupModal = false
      await refresh()
      showFlash(
        'ok',
        `${result.deleted_ids.length} Set(s) gelöscht` +
          (result.skipped?.length ? `, ${result.skipped.length} übersprungen` : ''),
      )
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function toggleMaterialCheck() {
    const updated = await api.sets.update(setModal.id, {
      count_materials_in_buildability: !setModal.count_materials_in_buildability,
    })
    setModal = updated
    await refresh()
  }

  async function addMapping() {
    saving = true
    try {
      const body = {
        option_name: mappingForm.option_name.trim(),
        option_value: mappingForm.option_value.trim(),
        quantity_required: mappingForm.quantity_required,
        material_id: mappingForm.kind === 'material' ? Number(mappingForm.component_id) : null,
        product_id: mappingForm.kind === 'product' ? Number(mappingForm.component_id) : null,
      }
      const updated = await api.sets.addMapping(setModal.id, body)
      setModal = updated
      mappingForm.option_value = ''
      mappingForm.component_id = ''
      await refresh()
      showFlash('ok', 'Zuordnung gespeichert.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function applyMappings() {
    saving = true
    try {
      setModal = await api.sets.applyMappings(setModal.id)
      await refresh()
      setStep = 3
      showFlash('ok', 'Zuordnungen angewendet — Baubarkeit prüfen.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function removeMapping(mapping) {
    saving = true
    try {
      setModal = await api.sets.removeMapping(setModal.id, mapping.id)
      await refresh({ silent: true })
      showFlash('ok', 'Zuordnung entfernt.')
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function detachSetComponent(comp) {
    saving = true
    try {
      setModal = await api.sets.detachComponent(setModal.id, {
        material_id: comp.kind === 'material' ? comp.id : undefined,
        product_id: comp.kind === 'product' ? comp.id : undefined,
      })
      await refresh({ silent: true })
      showFlash('ok', `„${comp.name}“ aus dem Set entfernt.`)
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  const setUsedComponents = $derived.by(() => {
    if (!setModal) return []
    const map = new Map()
    for (const v of setModal.variants || []) {
      for (const line of v.bom || []) {
        const kind = line.component_kind || (line.material_id ? 'material' : 'product')
        const id = line.material_id || line.product_id
        if (!id) continue
        const key = `${kind}:${id}`
        const prev = map.get(key) || { kind, id, name: line.component_name, count: 0 }
        prev.count += 1
        map.set(key, prev)
      }
    }
    return [...map.values()].sort((a, b) => a.name.localeCompare(b.name, 'de'))
  })

  const availableBomMaterials = $derived(
    materials.filter((m) => !productModal?.product?.bom?.some((line) => line.material_id === m.id)),
  )

  const availableBomProducts = $derived(
    products.filter(
      (p) =>
        p.id !== productModal?.product?.id &&
        !productModal?.product?.bom?.some((line) => line.product_id === p.id),
    ),
  )

  const optionNames = $derived(
    setModal
      ? [...new Set(setModal.variants.flatMap((v) => [v.option1_name, v.option2_name, v.option3_name].filter(Boolean)))]
      : [],
  )

  const optionValues = $derived.by(() => {
    if (!setModal || !mappingForm.option_name) return []
    const values = new Set()
    for (const v of setModal.variants) {
      if (v.option1_name === mappingForm.option_name && v.option1_value) values.add(v.option1_value)
      if (v.option2_name === mappingForm.option_name && v.option2_value) values.add(v.option2_value)
      if (v.option3_name === mappingForm.option_name && v.option3_value) values.add(v.option3_value)
    }
    return [...values].sort()
  })

  const unmappedOptionValues = $derived.by(() => {
    if (!setModal || !mappingForm.option_name) return optionValues
    const mapped = new Set(
      setModal.option_mappings
        .filter((m) => m.option_name === mappingForm.option_name)
        .map((m) => m.option_value),
    )
    return optionValues.filter((v) => !mapped.has(v))
  })

  const setBatchRows = $derived.by(() => {
    const option = mappingForm.option_name
    const cfg = getSetOptionConfig(option)
    if (!setModal || !option || !cfg.mediumId) return []
    return optionValues.map((value) => {
      const key = setBatchRowKey(option, value)
      const ov = setRowOverrides[key] || {}
      const already = setModal.option_mappings.some(
        (m) => m.option_name === option && m.option_value === value,
      )
      const candidates = matchColorsForShopifyValue(cfg.mediumId, value)
      let colorId = ov.colorId != null && ov.colorId !== undefined ? String(ov.colorId) : ''
      let status = 'ok'
      if (ov.skip) {
        status = 'skip'
      } else if (!colorId) {
        if (candidates.length === 1) colorId = String(candidates[0].id)
        else if (candidates.length === 0) status = 'missing_color'
        else status = 'ambiguous_color'
      }
      const comps =
        colorId && !ov.skip
          ? resolveSetComponents(cfg.kind, colorId, cfg.templateId, cfg.baseName)
          : []
      let componentId = ov.componentId != null && ov.componentId !== undefined ? String(ov.componentId) : ''
      if (!ov.skip && colorId && status === 'ok') {
        if (!componentId) {
          if (comps.length === 1) componentId = String(comps[0].id)
          else if (comps.length === 0) status = 'missing_article'
          else status = 'ambiguous_article'
        }
      }
      return {
        key,
        value,
        colorId,
        candidates,
        comps,
        componentId,
        status,
        already,
        kind: cfg.kind,
      }
    })
  })

  const setBatchReadyCount = $derived(
    setBatchRows.filter((r) => !r.already && r.componentId && r.status !== 'skip').length,
  )

  function patchSetRow(option, value, patch) {
    const key = setBatchRowKey(option, value)
    setRowOverrides = { ...setRowOverrides, [key]: { ...(setRowOverrides[key] || {}), ...patch } }
  }

  async function saveBatchMappings() {
    const option = mappingForm.option_name
    const toSave = setBatchRows.filter((r) => !r.already && r.componentId && r.status !== 'skip')
    if (!toSave.length) {
      showFlash('error', 'Keine speicherbaren Zeilen — Farben/Artikel klären.')
      return
    }
    saving = true
    try {
      let saved = 0
      for (const row of toSave) {
        const body = {
          option_name: option.trim(),
          option_value: row.value.trim(),
          quantity_required: '1',
          material_id: row.kind === 'material' ? Number(row.componentId) : null,
          product_id: row.kind === 'product' ? Number(row.componentId) : null,
        }
        setModal = await api.sets.addMapping(setModal.id, body)
        saved += 1
      }
      await refresh({ silent: true })
      showFlash('ok', `${saved} Zuordnung(en) gespeichert.`)
      markSaved()
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  async function createMissingBatchArticles() {
    const option = mappingForm.option_name
    const cfg = getSetOptionConfig(option)
    if (cfg.kind !== 'product') {
      showFlash('error', 'Nachlegen derzeit nur für Produkte (Serienanlage).')
      return
    }
    const missing = setBatchRows.filter((r) => !r.already && r.colorId && r.status === 'missing_article')
    if (!missing.length) {
      showFlash('error', 'Keine fehlenden Produkte mit geklärter Farbe.')
      return
    }
    const templateId = cfg.templateId ? Number(cfg.templateId) : null
    const template = templateId ? products.find((p) => p.id === templateId) : null
    let base =
      cfg.baseName.trim() ||
      template?.family ||
      (template?.name ? String(template.name) : '') ||
      option.replace(/farbe$/i, '').trim() ||
      'Produkt'
    if (template?.color?.name && base.toLowerCase().endsWith(String(template.color.name).toLowerCase())) {
      base = base.slice(0, base.length - template.color.name.length).trim() || base
    }
    if (!confirm(`${missing.length} fehlende Produkte für „${base}“ anlegen?`)) return
    saving = true
    try {
      const result = await api.products.fromColors({
        color_ids: missing.map((r) => Number(r.colorId)),
        base_name: base,
        template_product_id: templateId,
        location_id: locations.find((x) => x.name === 'Hamburg')?.id || locations[0]?.id || null,
      })
      await refresh({ silent: true })
      showFlash('ok', `${result.created?.length || 0} Produkt(e) angelegt.`)
      if (result.warnings?.length) showFlash('warn', result.warnings.slice(0, 3).join(' · '))
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
    }
  }

  const buildableVariants = $derived(
    setModal ? setModal.variants.filter((v) => v.buildable_quantity > 0) : [],
  )
  const blockedVariants = $derived(
    setModal ? setModal.variants.filter((v) => v.buildable_quantity === 0) : [],
  )
  const displayedBuildableVariants = $derived(
    prepareRows(
      buildableVariants,
      listUi.setBuildable,
      variantBomSearchText,
      variantSortGetter(listUi.setBuildable.sortKey),
    ),
  )
  const displayedBlockedVariants = $derived(
    prepareRows(
      blockedVariants,
      listUi.setBlocked,
      variantBomSearchText,
      variantSortGetter(listUi.setBlocked.sortKey),
    ),
  )
</script>

<div class="app-shell">
  {#if !authChecked || (loading && !authUser)}
    <header class="brand">
      <h1>Holzlinge</h1>
    </header>
  {:else if !authUser}
    <header class="brand">
      <h1>Holzlinge</h1>
      <p>Inventar, Standorte, Stücklisten und baubare Sets.</p>
    </header>
  {:else}
    <div class="app-chrome">
      <header class="brand">
        <h1>Holzlinge</h1>
        <div class="auth-bar">
          <span class="empty">{authUser.username}</span>
          <button type="button" class="btn secondary compact" onclick={() => (passwordModal = true)}>Passwort</button>
          <button type="button" class="btn secondary compact" onclick={doLogout}>Abmelden</button>
        </div>
      </header>
      <nav class="tabs" aria-label="Hauptnavigation">
        {#if authUser.role === 'admin'}
          <button class="tab" class:active={tab === 'overview'} onclick={() => selectTab('overview')}>Übersicht</button>
          <button class="tab" class:active={tab === 'materials'} onclick={() => selectTab('materials')}>Materialien</button>
          <button class="tab" class:active={tab === 'products'} onclick={() => selectTab('products')}>Produkte</button>
          <button class="tab" class:active={tab === 'orders'} onclick={() => selectTab('orders')}>Bestellungen</button>
          <button class="tab" class:active={tab === 'todos'} onclick={() => selectTab('todos')}>
            Todos{#if openTodoCount()} ({openTodoCount()}){/if}
          </button>
          <button class="tab" class:active={tab === 'staff'} onclick={() => selectTab('staff')}>
            Bei Mitarbeitern{#if staffQueueProducts.length} ({staffQueueProducts.length}){/if}
          </button>
          <button class="tab" class:active={tab === 'catalogs'} onclick={() => selectTab('catalogs')}>Kataloge</button>
          <button class="tab" class:active={tab === 'import'} onclick={() => selectTab('import')}>
            Import{#if importQueueOpenCount()} ({importQueueOpenCount()}){/if}
          </button>
          <button class="tab" class:active={tab === 'sets'} onclick={() => selectTab('sets')}>Sets</button>
          <button class="tab" class:active={tab === 'users'} onclick={() => selectTab('users')}>Benutzer</button>
        {:else}
          <button class="tab" class:active={tab === 'staff'} onclick={() => selectTab('staff')}>
            Bei Mitarbeitern{#if staffQueueProducts.length} ({staffQueueProducts.length}){/if}
          </button>
        {/if}
      </nav>
      {#if authUser.role === 'admin' && (tab === 'materials' || tab === 'products')}
        <FilterBar
          {media}
          {colors}
          families={catalogFilterFamilies}
          tags={allTags}
          bind:filter={catalogFilter}
        />
      {/if}
    </div>
  {/if}

  {#if flash}
    <div class={`flash ${flash.type}`}>{flash.message}</div>
  {/if}

  {#snippet todosMarkup(rows, emptyText)}
    <div class="table-wrap desktop-only">
      <table>
        <thead>
          <tr>
            <th>Todo</th>
            <th>Bestellung</th>
            <th>Menge</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each rows as todo}
            <tr class:empty={todo.status === 'done'}>
              <td><strong>{todoKindLabel(todo.kind)}</strong> · {todo.title}</td>
              <td>{todo.order_label || `#${todo.order_id}`}</td>
              <td>{formatQty(todo.quantity)}</td>
              <td>{todo.status === 'done' ? 'erledigt' : 'offen'}</td>
              <td class="col-actions">
                {#if todo.status === 'open'}
                  <button type="button" class="btn" onclick={() => startTodo(todo)}>Los</button>
                {/if}
              </td>
            </tr>
          {:else}
            <tr><td colspan="6" class="empty">{emptyText}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    <div class="card-list mobile-only">
      {#each rows as todo}
        <article class="card" class:empty={todo.status === 'done'}>
          <h3>{todoKindLabel(todo.kind)}</h3>
          <p>{todo.title}</p>
          <p class="empty">{todo.order_label} · {formatQty(todo.quantity)}</p>
          {#if todo.status === 'open'}
            <div class="row-actions"><button type="button" class="btn" onclick={() => startTodo(todo)}>Los</button></div>
          {/if}
        </article>
      {:else}
        <p class="empty">{emptyText}</p>
      {/each}
    </div>
  {/snippet}

  {#snippet ordersMarkup(rows, emptyText)}
    <div class="table-wrap desktop-only">
      <table>
        <thead>
          <tr>
            <th>Datum</th>
            <th>Kunde / Nummer</th>
            <th>Herkunft</th>
            <th>Positionen</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each rows as order}
            <tr class:empty={order.status === 'shipped'}>
              <td>{formatDateTime(order.ordered_on)}</td>
              <td>
                <strong>{order.customer_name || '—'}</strong>
                <div class="empty" style="margin:0">{order.external_number || `#${order.id}`}</div>
              </td>
              <td>{orderOriginLabel(order.origin)}</td>
              <td>
                {#each order.lines as ln}
                  <div>{formatQty(ln.quantity)}× {ln.label}</div>
                {/each}
                {#if order.note}
                  <div class="empty" style="margin-top:.25rem">Notiz: {order.note}</div>
                {/if}
              </td>
              <td>
                <div>{orderStatusLabel(order.status)}</div>
                {#if orderOpenTodoHint(order)}
                  <div class="empty" style="margin:0">{orderOpenTodoHint(order)}</div>
                {/if}
              </td>
              <td class="col-actions">
                {#if order.status === 'ready'}
                  <button type="button" class="btn" onclick={() => markOrderShipped(order)}>Versendet</button>
                {/if}
                {#if order.status !== 'shipped'}
                  {#if pendingDeleteOrderId === order.id}
                    <button type="button" class="btn danger" disabled={saving} onclick={() => deleteOrder(order)}>Wirklich löschen?</button>
                    <button type="button" class="btn secondary" disabled={saving} onclick={() => (pendingDeleteOrderId = null)}>Abbrechen</button>
                  {:else}
                    <button type="button" class="btn secondary" disabled={saving} onclick={() => deleteOrder(order)}>Löschen</button>
                  {/if}
                {/if}
              </td>
            </tr>
          {:else}
            <tr><td colspan="6" class="empty">{emptyText}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
    <div class="card-list mobile-only">
      {#each rows as order}
        <article class="card" class:empty={order.status === 'shipped'}>
          <h3>{order.customer_name || order.external_number || `Bestellung ${order.id}`}</h3>
          <p class="empty">
            {formatDateTime(order.ordered_on)} · {orderOriginLabel(order.origin)} · {orderStatusLabel(order.status)}
            {#if orderOpenTodoHint(order)} · {orderOpenTodoHint(order)}{/if}
          </p>
          {#each order.lines as ln}
            <p>{formatQty(ln.quantity)}× {ln.label}</p>
          {/each}
          {#if order.note}
            <p class="empty">Notiz: {order.note}</p>
          {/if}
          <div class="row-actions">
            {#if order.status === 'ready'}
              <button type="button" class="btn" onclick={() => markOrderShipped(order)}>Versendet</button>
            {/if}
            {#if order.status !== 'shipped'}
              {#if pendingDeleteOrderId === order.id}
                <button type="button" class="btn danger" disabled={saving} onclick={() => deleteOrder(order)}>Wirklich löschen?</button>
                <button type="button" class="btn secondary" disabled={saving} onclick={() => (pendingDeleteOrderId = null)}>Abbrechen</button>
              {:else}
                <button type="button" class="btn secondary" disabled={saving} onclick={() => deleteOrder(order)}>Löschen</button>
              {/if}
            {/if}
          </div>
        </article>
      {:else}
        <p class="empty">{emptyText}</p>
      {/each}
    </div>
  {/snippet}

  {#if !authChecked || (loading && !authUser)}
    <div class="panel"><p class="empty">Lade…</p></div>
  {:else if !authUser}
    <section class="panel login-panel">
      <h2>Anmelden</h2>
      <form class="form-grid" onsubmit={(e) => { e.preventDefault(); doLogin() }}>
        <label>Benutzername
          <input bind:value={loginForm.username} autocomplete="username" required />
        </label>
        <label>Passwort
          <input type="password" bind:value={loginForm.password} autocomplete="current-password" required />
        </label>
        <div class="row-actions">
          <button class="btn" type="submit" disabled={saving}>Anmelden</button>
        </div>
      </form>
    </section>
  {:else}
  {#if loading}
    <div class="panel"><p class="empty">Lade…</p></div>
  {:else if tab === 'users' && authUser.role === 'admin'}
    <section class="panel">
      <div class="panel-header">
        <h2>Benutzer</h2>
      </div>
      <h3>Neu anlegen</h3>
      <form class="form-grid" onsubmit={(e) => { e.preventDefault(); createUserAccount() }}>
        <label>Benutzername<input bind:value={userForm.username} required /></label>
        <label>Passwort<input type="password" bind:value={userForm.password} required minlength="6" /></label>
        <label>Rolle
          <select bind:value={userForm.role}>
            <option value="mitarbeiter">Mitarbeiter</option>
            <option value="admin">Admin</option>
          </select>
        </label>
        <div class="row-actions"><button class="btn" type="submit" disabled={saving}>Anlegen</button></div>
      </form>
      <div class="table-wrap" style="margin-top:1rem">
        <table>
          <thead>
            <tr><th>Name</th><th>Rolle</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {#each users as u}
              <tr>
                <td>{u.username}{#if u.id === authUser.id} <span class="empty">(du)</span>{/if}</td>
                <td>
                  {#if u.id === authUser.id}
                    Admin
                  {:else}
                    <select
                      value={u.role}
                      onchange={(e) => {
                        const role = e.currentTarget.value
                        if (role === u.role) return
                        if (!confirm(`Rolle von „${u.username}“ auf ${role === 'admin' ? 'Admin' : 'Mitarbeiter'} setzen?`)) {
                          e.currentTarget.value = u.role
                          return
                        }
                        patchUser(u.id, { role })
                      }}
                      disabled={saving}
                    >
                      <option value="admin">Admin</option>
                      <option value="mitarbeiter">Mitarbeiter</option>
                    </select>
                  {/if}
                </td>
                <td>{u.is_active ? 'aktiv' : 'deaktiviert'}</td>
                <td class="row-actions">
                  <button
                    type="button"
                    class="btn secondary"
                    disabled={saving}
                    onclick={() => {
                      const pw = prompt(`Neues Passwort für ${u.username} (min. 6 Zeichen):`)
                      if (pw && pw.length >= 6) patchUser(u.id, { password: pw })
                    }}
                  >Passwort setzen</button>
                  <button
                    type="button"
                    class="btn secondary"
                    disabled={saving || u.id === authUser.id}
                    onclick={() => patchUser(u.id, { is_active: !u.is_active })}
                  >{u.is_active ? 'Deaktivieren' : 'Aktivieren'}</button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>
  {:else if tab === 'overview'}
    {#if negativeMaterials.length || negativeProducts.length}
      <div class="flash warn">
        Negativbestand vorhanden — Details in den Listen prüfen.
      </div>
    {/if}

    <section class="panel" class:collapsed={!overviewOrdersOpen}>
      <div class="panel-header">
        <h2>
          <button type="button" class="group-toggle overview-section-toggle" onclick={() => (overviewOrdersOpen = !overviewOrdersOpen)}>
            {overviewOrdersOpen ? '▼' : '▶'} Aktuelle Bestellungen
            <span class="empty">({currentOrders.length})</span>
          </button>
        </h2>
        <button class="btn secondary" onclick={refresh}>Aktualisieren</button>
      </div>
      {#if overviewOrdersOpen}
        {#if reviewOrders.length}
          <p class="empty">Zur Prüfung: {reviewOrders.length} — unter Bestellungen zuordnen und abnicken.</p>
        {/if}
        {@render ordersMarkup(currentOrders, 'Keine aktuellen Bestellungen.')}
      {/if}
    </section>

    <section class="panel" class:collapsed={!overviewTodosOpen}>
      <div class="panel-header">
        <h2>
          <button type="button" class="group-toggle overview-section-toggle" onclick={() => (overviewTodosOpen = !overviewTodosOpen)}>
            {overviewTodosOpen ? '▼' : '▶'} Offene Todos aus Bestellungen
            <span class="empty">({overviewOpenTodos.length})</span>
          </button>
        </h2>
      </div>
      {#if overviewTodosOpen}
        {@render todosMarkup(overviewOpenTodos, 'Keine offenen Werkstatt-Todos aus Bestellungen.')}
      {/if}
    </section>

    <section class="panel tageslage-panel" class:collapsed={!overviewTageslageOpen}>
      <div class="panel-header">
        <h2>
          <button type="button" class="group-toggle overview-section-toggle" onclick={() => (overviewTageslageOpen = !overviewTageslageOpen)}>
            {overviewTageslageOpen ? '▼' : '▶'} Tageslage
            {#if tageslage?.cache_date}<span class="empty">({tageslage.cache_date})</span>{/if}
          </button>
        </h2>
        <button
          type="button"
          class="btn secondary"
          disabled={tageslageLoading || saving}
          onclick={() => loadTageslage({ refresh: true })}
        >Aktualisieren</button>
      </div>
      {#if overviewTageslageOpen}
        {#if tageslageLoading && !tageslage}
          <p class="empty">Lade Tageslage…</p>
        {:else if tageslage}
          <div class="tageslage-stats">
            <span><strong>{tageslage.stats?.current_orders ?? 0}</strong> aktuelle Bestellungen</span>
            <span><strong>{tageslage.stats?.review_orders ?? 0}</strong> zur Prüfung</span>
            <span><strong>{tageslage.stats?.open_todos ?? 0}</strong> offene Todos</span>
            {#if tageslage.stats?.todos_by_kind}
              <span class="empty">
                Fertigen {tageslage.stats.todos_by_kind.manufacture || 0}
                · Anlegen {tageslage.stats.todos_by_kind.create_article || 0}
              </span>
            {/if}
          </div>
          {#if tageslage.summary}
            <p class="tageslage-summary">{tageslage.summary}</p>
          {/if}
          {#if tageslage.next_steps?.length}
            <h3 class="tageslage-next-title">Als Nächstes</h3>
            <ol class="tageslage-next">
              {#each tageslage.next_steps as step, i (i)}
                <li>
                  <span>{step.text}</span>
                  {#if step.todo_id}
                    {#each todos.filter((t) => t.id === step.todo_id && t.status === 'open') as todo (todo.id)}
                      <button type="button" class="btn" onclick={() => startTodo(todo)}>Los</button>
                    {/each}
                  {/if}
                </li>
              {/each}
            </ol>
          {/if}
          {#if tageslage.quote}
            <blockquote class="tageslage-quote">{tageslage.quote}</blockquote>
          {/if}
          {#if tageslage.error}
            <p class="empty">
              {#if tageslage.error === 'rate_limit'}
                Gemini-Kontingent erreicht — Fallback aktiv. Später „Aktualisieren“.
              {:else if tageslage.error === 'model_404'}
                Gemini-Modell nicht gefunden — Fallback aktiv.
              {:else}
                Kurzlage ggf. unvollständig (API) — Fallback aktiv.
              {/if}
            </p>
          {/if}
        {:else}
          <p class="empty">Tageslage noch nicht geladen.</p>
        {/if}
      {/if}
    </section>

    <section class="panel" class:collapsed={!overviewCriticalOpen}>
      <div class="panel-header">
        <h2>
          <button type="button" class="group-toggle overview-section-toggle" onclick={() => (overviewCriticalOpen = !overviewCriticalOpen)}>
            {overviewCriticalOpen ? '▼' : '▶'} Kritische Artikel
            <span class="empty">({displayedOverviewProducts.length + displayedOverviewMaterials.length})</span>
          </button>
        </h2>
      </div>
      {#if overviewCriticalOpen}
        <p class="empty">
          Produkte und Materialien mit Gesamt ≤ 0 oder unter Mindestbestand. Einträge können dauerhaft ignoriert werden.
        </p>
        <h3>Produkte</h3>
        <div class="table-wrap stock-table-wrap">
          <table class="stock-table">
            <thead>
              <tr>
                <th>
                  <button type="button" class="th-sort" onclick={() => toggleListSort('overviewProducts', 'name')}>
                    Name{sortMark(listUi.overviewProducts.sortKey, 'name', listUi.overviewProducts.sortDir)}
                  </button>
                </th>
                {#each orderedLocations as loc}
                  <th class="num">
                    <button type="button" class="th-sort" onclick={() => toggleListSort('overviewProducts', `stock:${loc.id}`)}>
                      {loc.name}{sortMark(listUi.overviewProducts.sortKey, `stock:${loc.id}`, listUi.overviewProducts.sortDir)}
                    </button>
                  </th>
                {/each}
                <th class="num">
                  <button type="button" class="th-sort" onclick={() => toggleListSort('overviewProducts', 'total')}>
                    Gesamt{sortMark(listUi.overviewProducts.sortKey, 'total', listUi.overviewProducts.sortDir)}
                  </button>
                </th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <ProductGroupSection
                groups={overviewProductGroups}
                {collapsedFamilies}
                colSpan={orderedLocations.length + 3}
                emptyMessage="Keine kritischen Produkte."
                onToggleCollapse={toggleFamilyCollapse}
              >
                {#snippet row({ product })}
                  <tr class="row-click" onclick={() => openEditProduct(product, { ids: visibleGroupItemIds(overviewProductGroups) })}>
                    <td>
                      {product.name}
                      {#if formatMinStock(product)}
                        <div class="min-stock-hint">Min. {formatMinStock(product)}</div>
                      {/if}
                    </td>
                    {#each orderedLocations as loc}
                      <td class="num" class:neg={stockAt(product, loc.id) < 0}>{formatQty(stockAt(product, loc.id), 0)}</td>
                    {/each}
                    <td class="num" class:neg={Number(product.stock_total) <= 0 || product.is_negative}>
                      {formatQty(product.stock_total, 0)}
                    </td>
                    <td onclick={(e) => e.stopPropagation()}>
                      <div class="row-actions">
                        <button class="btn secondary" onclick={() => openEditProduct(product, { ids: visibleGroupItemIds(overviewProductGroups) })}>Bearbeiten</button>
                        <button class="btn secondary" disabled={saving} onclick={() => setOverviewIgnored('product', product, true)}>Ignorieren</button>
                      </div>
                    </td>
                  </tr>
                {/snippet}
              </ProductGroupSection>
            </tbody>
          </table>
        </div>

        <h3>Materialien</h3>
        <div class="table-wrap stock-table-wrap">
          <table class="stock-table">
            <thead>
              <tr>
                <th>
                  <button type="button" class="th-sort" onclick={() => toggleListSort('overviewMaterials', 'name')}>
                    Name{sortMark(listUi.overviewMaterials.sortKey, 'name', listUi.overviewMaterials.sortDir)}
                  </button>
                </th>
                {#each materialLocations as loc}
                  <th class="num">
                    <button type="button" class="th-sort" onclick={() => toggleListSort('overviewMaterials', `stock:${loc.id}`)}>
                      {loc.name}{sortMark(listUi.overviewMaterials.sortKey, `stock:${loc.id}`, listUi.overviewMaterials.sortDir)}
                    </button>
                  </th>
                {/each}
                <th class="num">
                  <button type="button" class="th-sort" onclick={() => toggleListSort('overviewMaterials', 'total')}>
                    Gesamt{sortMark(listUi.overviewMaterials.sortKey, 'total', listUi.overviewMaterials.sortDir)}
                  </button>
                </th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <ProductGroupSection
                groups={overviewMaterialGroups}
                {collapsedFamilies}
                colSpan={materialLocations.length + 3}
                emptyMessage="Keine kritischen Materialien."
                onToggleCollapse={toggleFamilyCollapse}
              >
                {#snippet row({ item: material })}
                  <tr class="row-click" onclick={() => openEditMaterial(material, { ids: visibleGroupItemIds(overviewMaterialGroups) })}>
                    <td>
                      {material.name}
                      {#if formatMinStock(material)}
                        <div class="min-stock-hint">Min. {formatMinStock(material)} {material.unit}</div>
                      {/if}
                    </td>
                    {#each materialLocations as loc}
                      <td class="num" class:neg={stockAt(material, loc.id) < 0}>{formatQty(stockAt(material, loc.id), itemDecimals(material))}</td>
                    {/each}
                    <td class="num" class:neg={Number(material.stock_total) <= 0 || material.is_negative}>
                      {formatQty(material.stock_total, itemDecimals(material))} {material.unit}
                    </td>
                    <td onclick={(e) => e.stopPropagation()}>
                      <div class="row-actions">
                        <button class="btn secondary" onclick={() => openEditMaterial(material, { ids: visibleGroupItemIds(overviewMaterialGroups) })}>Bearbeiten</button>
                        <button class="btn secondary" disabled={saving} onclick={() => setOverviewIgnored('material', material, true)}>Ignorieren</button>
                      </div>
                    </td>
                  </tr>
                {/snippet}
              </ProductGroupSection>
            </tbody>
          </table>
        </div>

        {#if ignoredCriticalProducts.length || ignoredCriticalMaterials.length}
          <button type="button" class="group-toggle overview-section-toggle" onclick={() => (overviewIgnoredOpen = !overviewIgnoredOpen)}>
            {overviewIgnoredOpen ? '▼' : '▶'} Ignorierte Engpässe
            <span class="empty">({ignoredCriticalProducts.length + ignoredCriticalMaterials.length})</span>
          </button>
          {#if overviewIgnoredOpen}
            <ul class="plain-list">
              {#each ignoredCriticalProducts as product}
                <li class="bom-line">
                  <div>Produkt <strong>{product.name}</strong></div>
                  <button class="btn secondary" disabled={saving} onclick={() => setOverviewIgnored('product', product, false)}>Wieder anzeigen</button>
                </li>
              {/each}
              {#each ignoredCriticalMaterials as material}
                <li class="bom-line">
                  <div>Material <strong>{material.name}</strong></div>
                  <button class="btn secondary" disabled={saving} onclick={() => setOverviewIgnored('material', material, false)}>Wieder anzeigen</button>
                </li>
              {/each}
            </ul>
          {/if}
        {/if}
      {/if}
    </section>

    <section class="panel" class:collapsed={!overviewIncompleteOpen}>
      <div class="panel-header">
        <h2>
          <button type="button" class="group-toggle overview-section-toggle" onclick={() => (overviewIncompleteOpen = !overviewIncompleteOpen)}>
            {overviewIncompleteOpen ? '▼' : '▶'} Unvollständigkeit
            <span class="empty">({displayedIncompleteProducts.length + displayedIncompleteMaterials.length})</span>
          </button>
        </h2>
      </div>
      {#if overviewIncompleteOpen}
        <p class="empty">Fehlende Stammdaten (System-Tags „fehlt …“).</p>
        <h3>Produkte</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Fehlt</th><th></th></tr></thead>
            <tbody>
              <ProductGroupSection
                groups={incompleteProductGroups}
                {collapsedFamilies}
                colSpan={3}
                emptyMessage="Keine unvollständigen Produkte."
                onToggleCollapse={toggleFamilyCollapse}
              >
                {#snippet row({ product })}
                  <tr class="row-click" onclick={() => openEditProduct(product, { ids: visibleGroupItemIds(incompleteProductGroups) })}>
                    <td>{product.name}</td>
                    <td>{incompleteHint(product) || '—'}</td>
                    <td onclick={(e) => e.stopPropagation()}>
                      <button class="btn secondary" onclick={() => openEditProduct(product, { ids: visibleGroupItemIds(incompleteProductGroups) })}>Bearbeiten</button>
                    </td>
                  </tr>
                {/snippet}
              </ProductGroupSection>
            </tbody>
          </table>
        </div>
        <h3>Materialien</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Fehlt</th><th></th></tr></thead>
            <tbody>
              <ProductGroupSection
                groups={incompleteMaterialGroups}
                {collapsedFamilies}
                colSpan={3}
                emptyMessage="Keine unvollständigen Materialien."
                onToggleCollapse={toggleFamilyCollapse}
              >
                {#snippet row({ item: material })}
                  <tr class="row-click" onclick={() => openEditMaterial(material, { ids: visibleGroupItemIds(incompleteMaterialGroups) })}>
                    <td>{material.name}</td>
                    <td>{incompleteHint(material) || '—'}</td>
                    <td onclick={(e) => e.stopPropagation()}>
                      <button class="btn secondary" onclick={() => openEditMaterial(material, { ids: visibleGroupItemIds(incompleteMaterialGroups) })}>Bearbeiten</button>
                    </td>
                  </tr>
                {/snippet}
              </ProductGroupSection>
            </tbody>
          </table>
        </div>
      {/if}
    </section>
    <BackupPanel onFlash={showFlash} onImported={refresh} />
  {:else if tab === 'materials'}
    <ExtraGapPanels
      kind="material"
      criticalRows={extraCriticalMaterials}
      incompleteRows={extraIncompleteMaterials}
      ignoredRows={extraIgnoredMaterials}
      locations={materialLocations}
      bind:selectedIds={selectedMaterialIds}
      bind:criticalOpen={extraMatCriticalOpen}
      bind:incompleteOpen={extraMatIncompleteOpen}
      bind:ignoredOpen={extraMatIgnoredOpen}
      {saving}
      onOpenEdit={(item, ids) => openEditMaterial(item, { ids })}
      onIgnore={(item) => setOverviewIgnored('material', item, true)}
      onUnignore={(item) => setOverviewIgnored('material', item, false)}
      onPatch={(item, patch) => patchGapItem('material', item, patch)}
      onAdjustStock={(item, body) => adjustGapStock('material', item, body)}
      onPurchase={openPurchase}
    />
    <section class="panel">
      <div class="panel-header">
        <h2>Materialien</h2>
        <div class="row-actions">
          <button class="btn secondary" onclick={() => openBulkMaterials()}>Aus Farben…</button>
          <button class="btn" onclick={openCreateMaterial}>Neu</button>
        </div>
      </div>
      {#if selectedMaterialIds.length}
        <div class="bulk-bar">
          <span>{selectedMaterialIds.length} ausgewählt</span>
          <div class="row-actions">
            <button class="btn" onclick={() => openBulkEdit('material')}>Mehrfach bearbeiten…</button>
            <button class="btn secondary" onclick={() => (selectedMaterialIds = [])}>Auswahl aufheben</button>
          </div>
        </div>
      {/if}
      <div class="table-wrap stock-table-wrap">
        <table class="stock-table">
          <thead>
            <tr>
              <th class="col-select">
                <input
                  type="checkbox"
                  aria-label="Alle sichtbaren Materialien wählen"
                  checked={displayedMaterials.length > 0 &&
                    displayedMaterials.every((m) => selectedMaterialIds.includes(m.id))}
                  onchange={toggleAllDisplayedMaterials}
                />
              </th>
              <th>
                <button type="button" class="th-sort" onclick={() => toggleListSort('materials', 'name')}>
                  Name{sortMark(listUi.materials.sortKey, 'name', listUi.materials.sortDir)}
                </button>
              </th>
              {#each materialLocations as loc}
                <th class="num">
                  <button type="button" class="th-sort" onclick={() => toggleListSort('materials', `stock:${loc.id}`)}>
                    {loc.name}{sortMark(listUi.materials.sortKey, `stock:${loc.id}`, listUi.materials.sortDir)}
                  </button>
                </th>
              {/each}
              <th class="num">
                <button type="button" class="th-sort" onclick={() => toggleListSort('materials', 'total')}>
                  Gesamt{sortMark(listUi.materials.sortKey, 'total', listUi.materials.sortDir)}
                </button>
              </th>
              <th>
                <button type="button" class="th-sort" onclick={() => toggleListSort('materials', 'updated_at')}>
                  Geändert{sortMark(listUi.materials.sortKey, 'updated_at', listUi.materials.sortDir)}
                </button>
              </th>
              <th>Aktionen</th>
            </tr>
          </thead>
          <tbody>
            <ProductGroupSection
              groups={materialGroups}
              {collapsedFamilies}
              colSpan={materialLocations.length + 5}
              emptyMessage="Keine Materialien."
              showFamilySelect={true}
              isFamilySelected={(group) => isFamilySelected(group, 'material')}
              onToggleCollapse={toggleFamilyCollapse}
              onToggleFamilySelection={(group) => toggleFamilySelection(group, 'material')}
            >
              {#snippet row({ item: material })}
                <tr class="row-click" onclick={() => openEditMaterial(material, { ids: visibleGroupItemIds(materialGroups) })}>
                  <td class="col-select" onclick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      aria-label={`Material ${material.name} wählen`}
                      checked={selectedMaterialIds.includes(material.id)}
                      onchange={() => toggleSelectedMaterial(material.id)}
                    />
                  </td>
                  <td>
                    {material.name}
                    {#if productFamilyKey(material)}<div class="empty">{productFamilyKey(material)}</div>{/if}
                    {#if colorTagMeta(material)}<div class="empty">{colorTagMeta(material)}</div>{/if}
                    {#if formatMinStock(material)}
                      <div class="min-stock-hint">Min. {formatMinStock(material)} {material.unit}</div>
                    {/if}
                    {#if incompleteHint(material)}
                      <div class="incomplete-hint" title="Unvollständige Daten">
                        <span class="incomplete-icon" aria-hidden="true">!</span>
                        {incompleteHint(material)}
                      </div>
                    {/if}
                  </td>
                  {#each materialLocations as loc}
                    <td class="num" class:neg={stockAt(material, loc.id) < 0}>{formatQty(stockAt(material, loc.id), itemDecimals(material))}</td>
                  {/each}
                  <td class="num" class:neg={Number(material.stock_total) <= 0 || material.is_negative}>
                    {formatQty(material.stock_total, itemDecimals(material))} {material.unit}
                  </td>
                  <td class="meta-cell">
                    <div>{formatDateTime(material.updated_at)}</div>
                    <div class="empty">{formatActor(material.updated_by)}</div>
                  </td>
                  <td onclick={(e) => e.stopPropagation()}>
                    <div class="row-actions">
                      <button class="btn secondary" onclick={() => openEditMaterial(material, { ids: visibleGroupItemIds(materialGroups) })}>Bearbeiten</button>
                      <button class="btn secondary" onclick={() => openTransfer('material', material)}>Umbuchen</button>
                      <button type="button" class="btn danger" onclick={(e) => { e.stopPropagation(); removeMaterial(material) }}>Löschen</button>
                    </div>
                  </td>
                </tr>
              {/snippet}
            </ProductGroupSection>
          </tbody>
        </table>
      </div>
    </section>
  {:else if tab === 'products'}
    <ExtraGapPanels
      kind="product"
      criticalRows={extraCriticalProducts}
      incompleteRows={extraIncompleteProducts}
      ignoredRows={extraIgnoredProducts}
      locations={materialLocations}
      bind:selectedIds={selectedProductIds}
      bind:criticalOpen={extraProdCriticalOpen}
      bind:incompleteOpen={extraProdIncompleteOpen}
      bind:ignoredOpen={extraProdIgnoredOpen}
      {saving}
      onOpenEdit={(item, ids) => openEditProduct(item, { ids })}
      onIgnore={(item) => setOverviewIgnored('product', item, true)}
      onUnignore={(item) => setOverviewIgnored('product', item, false)}
      onPatch={(item, patch) => patchGapItem('product', item, patch)}
      onAdjustStock={(item, body) => adjustGapStock('product', item, body)}
      onManufacture={openManufacture}
    />
    <section class="panel">
      <div class="panel-header">
        <h2>Produkte</h2>
        <div class="row-actions">
          <button class="btn secondary" disabled={saving} onclick={suggestFamilies}>Familien vorschlagen</button>
          <button class="btn secondary" onclick={() => openBulkProducts()}>Aus Farben…</button>
          <button class="btn" onclick={openCreateProduct}>Neu</button>
        </div>
      </div>
      {#if selectedProductIds.length}
        <div class="bulk-bar">
          <span>{selectedProductIds.length} ausgewählt</span>
          <div class="row-actions">
            <button class="btn" onclick={() => openBulkEdit('product')}>Mehrfach bearbeiten…</button>
            <button class="btn secondary" onclick={() => (selectedProductIds = [])}>Auswahl aufheben</button>
          </div>
        </div>
      {/if}
      <div class="table-wrap stock-table-wrap">
        <table class="stock-table">
          <thead>
            <tr>
              <th class="col-select"></th>
              <th>
                <button type="button" class="th-sort" onclick={() => toggleListSort('products', 'name')}>
                  Name{sortMark(listUi.products.sortKey, 'name', listUi.products.sortDir)}
                </button>
              </th>
              {#each orderedLocations as loc}
                <th class="num">
                  <button type="button" class="th-sort" onclick={() => toggleListSort('products', `stock:${loc.id}`)}>
                    {loc.name}{sortMark(listUi.products.sortKey, `stock:${loc.id}`, listUi.products.sortDir)}
                  </button>
                </th>
              {/each}
              <th class="num">
                <button type="button" class="th-sort" onclick={() => toggleListSort('products', 'total')}>
                  Gesamt{sortMark(listUi.products.sortKey, 'total', listUi.products.sortDir)}
                </button>
              </th>
              <th>
                <button type="button" class="th-sort" onclick={() => toggleListSort('products', 'updated_at')}>
                  Geändert{sortMark(listUi.products.sortKey, 'updated_at', listUi.products.sortDir)}
                </button>
              </th>
              <th>Aktionen</th>
            </tr>
          </thead>
          <tbody>
            <ProductGroupSection
              groups={productGroups}
              {collapsedFamilies}
              colSpan={orderedLocations.length + 5}
              emptyMessage="Keine Produkte."
              showFamilySelect={true}
              isFamilySelected={isFamilySelected}
              onToggleCollapse={toggleFamilyCollapse}
              onToggleFamilySelection={toggleFamilySelection}
            >
              {#snippet row({ product })}
                <tr class="row-click" onclick={() => openEditProduct(product, { ids: visibleGroupItemIds(productGroups) })}>
                  <td class="col-select" onclick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      aria-label={`Produkt ${product.name} wählen`}
                      checked={selectedProductIds.includes(product.id)}
                      onchange={() => toggleSelectedProduct(product.id)}
                    />
                  </td>
                  <td>
                    {product.name}
                    {#if productFamilyKey(product)}<div class="empty">{productFamilyKey(product)}</div>{/if}
                    {#if colorTagMeta(product)}<div class="empty">{colorTagMeta(product)}</div>{/if}
                    {#if formatMinStock(product)}
                      <div class="min-stock-hint">Min. {formatMinStock(product)}</div>
                    {/if}
                    {#if incompleteHint(product)}
                      <div class="incomplete-hint" title="Unvollständige Daten">
                        <span class="incomplete-icon" aria-hidden="true">!</span>
                        {incompleteHint(product)}
                      </div>
                    {/if}
                    {#if product.transform_target_name}
                      <div class="empty">→ {product.transform_target_name}</div>
                    {/if}
                  </td>
                  {#each orderedLocations as loc}
                    <td class="num" class:neg={stockAt(product, loc.id) < 0}>{formatQty(stockAt(product, loc.id), 0)}</td>
                  {/each}
                  <td class="num" class:neg={Number(product.stock_total) <= 0 || product.is_negative}>
                    {formatQty(product.stock_total, 0)}
                  </td>
                  <td class="meta-cell">
                    <div>{formatDateTime(product.updated_at)}</div>
                    <div class="empty">{formatActor(product.updated_by)}</div>
                  </td>
                  <td onclick={(e) => e.stopPropagation()}>
                    <div class="row-actions">
                      <button class="btn secondary" onclick={() => openEditProduct(product, { ids: visibleGroupItemIds(productGroups) })}>Bearbeiten</button>
                      <button class="btn" onclick={() => openManufacture(product)}>Fertigen</button>
                      <button class="btn secondary" onclick={() => openTransfer('product', product)}>Umbuchen</button>
                      {#if canTransformProduct(product)}
                        <button class="btn secondary" onclick={() => openTransform(product)}>Umwandeln</button>
                      {/if}
                      <button class="btn secondary" onclick={() => openMovements(product)}>Historie</button>
                      <button type="button" class="btn danger" onclick={(e) => { e.stopPropagation(); removeProduct(product) }}>Löschen</button>
                    </div>
                  </td>
                </tr>
              {/snippet}
            </ProductGroupSection>
          </tbody>
        </table>
      </div>
    </section>
  {:else if tab === 'orders'}
    <section class="panel">
      <div class="panel-header">
        <h2>Bestellungen</h2>
        <div class="row-actions">
          <button type="button" class="btn secondary" onclick={syncShopifyOrders} disabled={saving}>Shopify abrufen</button>
          <button type="button" class="btn secondary" onclick={parseEtsyMails} disabled={saving}>Etsy-Mails parsen</button>
        </div>
      </div>
      <p class="empty" style="margin-top:0">
        Oben Etsy-Mail-Warteschlange und Aufträge zur Prüfung. Dann aktuelle Aufträge. Schnellerfassung zugeklappt. Versendete unten.
      </p>

      <h3>Etsy-Mails {#if etsyMails.length}<span class="empty">({etsyMails.length})</span>{/if}</h3>
      {#if etsyMails.length}
        <div class="review-orders">
          {#each etsyMails as mail (mail.id)}
            <article class="review-order">
              <h3>{mail.subject || `Mail ${mail.id}`}</h3>
              <p class="empty">
                {mail.status === 'duplicate' ? 'Doppel' : mail.status === 'error' ? 'Fehler' : 'wartet'}
                {#if mail.from_addr} · {mail.from_addr}{/if}
              </p>
              {#if mail.error_message}
                <p class="flash error" style="margin:.35rem 0">{mail.error_message}</p>
              {/if}
              {#if mail.body_preview}
                <p class="empty" style="white-space:pre-wrap">{mail.body_preview}</p>
              {/if}
              <div class="row-actions">
                <button type="button" class="btn secondary" onclick={() => ignoreEtsyMail(mail)} disabled={saving}>Ignorieren</button>
                {#if mail.status === 'pending'}
                  <span class="empty">Wird beim Parsen verarbeitet</span>
                {/if}
              </div>
            </article>
          {/each}
        </div>
      {:else}
        <p class="empty">Keine Mails in der Warteschlange. „Etsy-Mails parsen“ holt zuerst neue aus dem Postfach.</p>
      {/if}

      <h3>Zur Prüfung {#if reviewOrders.length}<span class="empty">({reviewOrders.length})</span>{/if}</h3>
      {#if reviewOrders.length}
        <div class="review-orders">
          {#each reviewOrders as order (order.id)}
            <article class="review-order">
              <h3>{order.customer_name || order.external_number || `Bestellung ${order.id}`}</h3>
              <p class="empty">{formatDateTime(order.ordered_on)} · {orderOriginLabel(order.origin)} · {order.external_number || ''}</p>
              {#if order.note}
                <p class="tageslage-summary" style="margin:.4rem 0">Notiz: {order.note}</p>
              {/if}
              {#each order.lines as ln (ln.id)}
                <div class="review-line">
                  <p class="review-line-shop">
                    <span class="review-line-qty">{formatQty(ln.quantity)}×</span>
                    {ln.shop_title || ln.label}
                  </p>
                  {#if ln.suggested_product_id && !ln.product_id}
                    <div class="review-suggest">
                      <p>Vorschlag: <strong>{ln.suggested_product_name || 'Produkt'}</strong></p>
                      <button
                        type="button"
                        class="btn"
                        disabled={saving}
                        onclick={() => setReviewLineProduct(order, ln, ln.suggested_product_id)}
                      >Übernehmen</button>
                    </div>
                  {/if}
                  <label class="review-line-assign">Lagerprodukt
                    <FamilySelect
                      value={ln.product_id || ''}
                      items={products}
                      emptyLabel="unzugeordnet"
                      inline
                      onchange={(v) => setReviewLineProduct(order, ln, v)}
                    />
                  </label>
                  {#if !ln.product_id && !ln.material_id}
                    <div class="row-actions" style="margin-top:.35rem">
                      <button
                        type="button"
                        class="btn secondary"
                        disabled={saving}
                        onclick={() => openCreateProductFromOrderLine(order, ln)}
                      >Produkt erzeugen</button>
                      {#if lineHasCreateTodo(order, ln)}
                        <span class="empty">vorgemerkt</span>
                      {:else}
                        <button
                          type="button"
                          class="btn secondary"
                          disabled={saving}
                          onclick={() => queueCreateArticleFromReview(order, ln)}
                        >Auf Liste</button>
                      {/if}
                    </div>
                  {/if}
                </div>
              {/each}
              <div class="row-actions">
                <button type="button" class="btn" onclick={() => approveOrder(order)} disabled={saving}>Abnicken</button>
                {#if pendingDeleteOrderId === order.id}
                  <button type="button" class="btn danger" onclick={() => deleteOrder(order)} disabled={saving}>Wirklich löschen?</button>
                  <button type="button" class="btn secondary" onclick={() => (pendingDeleteOrderId = null)} disabled={saving}>Abbrechen</button>
                {:else}
                  <button type="button" class="btn secondary" onclick={() => deleteOrder(order)} disabled={saving}>Löschen</button>
                {/if}
              </div>
            </article>
          {/each}
        </div>
      {:else}
        <p class="empty">Keine Bestellungen zur Prüfung.</p>
      {/if}

      <h3 style="margin-top:1.5rem">Aktuelle Bestellungen</h3>
      {@render ordersMarkup(currentOrders, 'Keine aktuellen Bestellungen.')}

      <button type="button" class="group-toggle overview-section-toggle" style="margin-top:1.5rem" onclick={() => (manualOrderOpen = !manualOrderOpen)}>
        {manualOrderOpen ? '▼' : '▶'} Neue Bestellung (Schnellerfassung)
      </button>
      {#if manualOrderOpen}
      <form class="form-grid" style="margin-top:.75rem" onsubmit={(e) => { e.preventDefault(); submitOrder() }}>
        <label>Datum und Uhrzeit<input type="datetime-local" bind:value={orderForm.ordered_on} required /></label>
        <label>Kunde (optional)<input bind:value={orderForm.customer_name} placeholder="Name" /></label>
        <label>Nummer (optional)<input bind:value={orderForm.external_number} placeholder="später Shopify/Etsy" /></label>
        {#each orderForm.lines as line, i}
          <div class="order-line" style="grid-column:1/-1">
            <label>Produkt
              <FamilySelect
                value={line.product_id}
                items={products}
                emptyLabel="Freitext / später anlegen"
                onchange={(v) => onOrderProductPicked(i, v)}
              />
            </label>
            <label>Menge<input type="number" step={qtyStep(0)} min="1" bind:value={line.quantity} required /></label>
            <div class="row-actions">
              {#if orderForm.lines.length > 1}
                <button type="button" class="btn secondary" onclick={() => { orderForm.lines = orderForm.lines.filter((_, j) => j !== i) }}>Entfernen</button>
              {/if}
            </div>
            {#if !line.product_id}
              <label class="order-line-free">Freitext
                <input bind:value={line.label} placeholder="z. B. Schild Mia 2026" />
              </label>
            {/if}
          </div>
        {/each}
        <div class="row-actions" style="grid-column:1/-1">
          <button type="button" class="btn secondary" onclick={() => { orderForm.lines = [...orderForm.lines, emptyOrderLine()] }}>Position hinzufügen</button>
          <button class="btn" type="submit" disabled={saving}>Bestellung anlegen</button>
        </div>
      </form>
      {/if}

      <button type="button" class="group-toggle overview-section-toggle" style="margin-top:1.5rem" onclick={() => (shippedOrdersOpen = !shippedOrdersOpen)}>
        {shippedOrdersOpen ? '▼' : '▶'} Versendete Bestellungen
        <span class="empty">({shippedOrders.length})</span>
      </button>
      {#if shippedOrdersOpen}
        {@render ordersMarkup(shippedOrders, 'Keine versendeten Bestellungen.')}
      {/if}
    </section>
  {:else if tab === 'todos'}
    <section class="panel">
      <div class="panel-header">
        <h2>Todos</h2>
      </div>
      <p class="empty" style="margin-top:0">
        Werkstatt zuerst. Einkauf-Todos aus Mindestbestand kommen im nächsten Schritt — der Filter ist schon da.
      </p>
      <div class="filter-bar form-grid">
        <label>Art
          <select bind:value={todoCategoryFilter}>
            <option value="workshop">Werkstatt</option>
            <option value="purchase">Einkauf</option>
            <option value="all">Alle</option>
          </select>
        </label>
        <label>Status
          <select bind:value={todoStatusFilter}>
            <option value="open">Offen</option>
            <option value="done">Erledigt</option>
            <option value="all">Alle</option>
          </select>
        </label>
      </div>
      {@render todosMarkup(displayedTodos(), todoCategoryFilter === 'purchase' ? 'Einkauf-Todos kommen im nächsten Schritt (Mindestbestand).' : 'Keine Todos.')}
    </section>
  {:else if tab === 'staff'}
    <section class="panel">
      <div class="panel-header">
        <h2>Bei Mitarbeitern</h2>
      </div>
      <p class="empty" style="margin-top:0">
        Quellprodukte mit Bestand an MA1/MA2 (z. B. Uni-Ringe vor Vintage-Bemalung). Umbuchen zurück oder umwandeln, wenn fertig.
      </p>
      <div class="filter-bar form-grid">
        <label class="list-search">Suche
          <input type="search" placeholder="Name, Zielprodukt…" bind:value={listUi.staff.q} />
        </label>
      </div>
      <div class="table-wrap stock-table-wrap">
        <table class="stock-table">
          <thead>
            <tr>
              <th>
                <button type="button" class="th-sort" onclick={() => toggleListSort('staff', 'name')}>
                  Quellprodukt{sortMark(listUi.staff.sortKey, 'name', listUi.staff.sortDir)}
                </button>
              </th>
              <th>Wird zu</th>
              {#each locations.filter((l) => STAFF_LOCATION_NAMES.includes(l.name)) as loc}
                <th class="num">{loc.name}</th>
              {/each}
              <th>Aktionen</th>
            </tr>
          </thead>
          <tbody>
            {#each displayedStaffQueue as product}
              <tr>
                <td>
                  {product.name}
                  {#if colorTagMeta(product)}<div class="empty">{colorTagMeta(product)}</div>{/if}
                </td>
                <td>{product.transform_target_name || '—'}</td>
                {#each locations.filter((l) => STAFF_LOCATION_NAMES.includes(l.name)) as loc}
                  <td class="num" class:neg={stockAt(product, loc.id) < 0}>{formatQty(stockAt(product, loc.id), 0)}</td>
                {/each}
                <td>
                  <div class="row-actions">
                    <button class="btn secondary" onclick={() => openTransfer('product', product)}>Umbuchen</button>
                    {#if canTransformProduct(product)}
                      <button class="btn" onclick={() => openTransform(product)}>Umwandeln</button>
                    {/if}
                    <button type="button" class="btn secondary" onclick={() => openMovements(product)}>Historie</button>
                  </div>
                </td>
              </tr>
            {:else}
              <tr>
                <td colspan="5" class="empty">
                  Nichts bei Mitarbeitern — Quellprodukte mit „Wird zu“ und Bestand an MA1/MA2 erscheinen hier.
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>
  {:else if tab === 'catalogs'}
    <section class="panel">
      <div class="panel-header">
        <h2>Kataloge</h2>
      </div>
      <p class="empty" style="margin-top:0">
        Medium wählen oder anlegen — darunter die Farb-Tabelle. Enter/Blur speichert, Esc verwirft.
      </p>

      <div class="catalog-block">
        <h3>Medien &amp; Farben</h3>
        <div class="filter-bar form-grid">
          <label class="list-search">Suche
            <input type="search" placeholder="Medium oder Farbe…" bind:value={listUi.catalogColors.q} />
          </label>
        </div>

        {#each displayedCatalogMedia as block (block.medium.id)}
          {@const m = block.medium}
          <div
            class="catalog-medium"
            class:selected={selectedCatalogMediumId === m.id}
            role="button"
            tabindex="0"
            onclick={() => (selectedCatalogMediumId = m.id)}
            onkeydown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                selectedCatalogMediumId = m.id
              }
            }}
          >
            <div class="catalog-medium-head">
              <input
                class="catalog-cell catalog-medium-title"
                type="text"
                value={catalogCellValue('media', m.id, 'name', m.name)}
                disabled={saving && catalogSavingKey === catalogCellKey('media', m.id, 'name')}
                onfocus={() => {
                  selectedCatalogMediumId = m.id
                  beginCatalogEdit('media', m.id, 'name', m.name)
                }}
                oninput={(e) => setCatalogEditValue('media', m.id, 'name', e.currentTarget.value)}
                onblur={commitCatalogEdit}
                onkeydown={onCatalogEditKeydown}
                onclick={(e) => e.stopPropagation()}
                aria-label={`Medium ${m.name}`}
              />
              <span class="empty catalog-medium-count">{block.colors.length} Farben</span>
              <button
                type="button"
                class="btn secondary"
                onclick={(e) => {
                  e.stopPropagation()
                  openBulkMaterials(m.id)
                }}
              >Materialien…</button>
              <button
                type="button"
                class="btn secondary"
                onclick={(e) => {
                  e.stopPropagation()
                  openBulkProducts({ mediumId: m.id })
                }}
              >Produkte…</button>
              <button
                type="button"
                class="btn-icon danger"
                title="Löschen"
                aria-label="Medium löschen"
                disabled={saving}
                onclick={(e) => {
                  e.stopPropagation()
                  deleteCatalogMedium(m)
                }}
              >✕</button>
            </div>

            <div class="table-wrap catalog-table-wrap">
              <table class="catalog-table">
                <thead>
                  <tr>
                    <th>
                      <button type="button" class="th-sort" onclick={() => toggleListSort('catalogColors', 'name')}>
                        Farbe{sortMark(listUi.catalogColors.sortKey, 'name', listUi.catalogColors.sortDir)}
                      </button>
                    </th>
                    <th>Hex</th>
                    <th class="col-actions"></th>
                  </tr>
                </thead>
                <tbody>
                  {#each block.colors as c}
                    <tr>
                      <td>
                        <input
                          class="catalog-cell"
                          type="text"
                          value={catalogCellValue('color', c.id, 'name', c.name)}
                          disabled={saving && catalogSavingKey === catalogCellKey('color', c.id, 'name')}
                          onfocus={() => {
                            selectedCatalogMediumId = m.id
                            beginCatalogEdit('color', c.id, 'name', c.name)
                          }}
                          oninput={(e) => setCatalogEditValue('color', c.id, 'name', e.currentTarget.value)}
                          onblur={commitCatalogEdit}
                          onkeydown={onCatalogEditKeydown}
                          aria-label={`Farbe ${c.name}`}
                        />
                      </td>
                      <td>
                        <input
                          class="catalog-hex"
                          type="color"
                          value={c.hex || '#9AA0A6'}
                          title={c.hex || 'kein Hex — grau'}
                          aria-label={`Hex ${c.name}`}
                          disabled={saving}
                          onchange={(e) => saveColorHex(c, e.currentTarget.value)}
                        />
                      </td>
                      <td class="col-actions">
                        <button
                          type="button"
                          class="btn-icon danger"
                          title="Löschen"
                          aria-label="Farbe löschen"
                          disabled={saving}
                          onclick={() => deleteCatalogColor(c)}
                        >✕</button>
                      </td>
                    </tr>
                  {:else}
                    <tr>
                      <td colspan="3" class="empty">Noch keine Farben — unten eintragen.</td>
                    </tr>
                  {/each}
                  <tr class="catalog-new-row">
                    <td>
                      <input
                        class="catalog-cell"
                        type="text"
                        data-catalog-new-color={m.id}
                        bind:value={catalogNewColorDrafts[m.id]}
                        placeholder="Neue Farbe…"
                        disabled={saving && catalogSavingKey === `new:color:${m.id}`}
                        onfocus={() => (selectedCatalogMediumId = m.id)}
                        onblur={() => commitNewColor(m.id)}
                        onkeydown={(e) => onNewColorKeydown(e, m.id)}
                        aria-label={`Neue Farbe für ${m.name}`}
                      />
                    </td>
                    <td></td>
                    <td class="col-actions"></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        {:else}
          <p class="empty">{listUi.catalogColors.q ? 'Keine Treffer.' : 'Noch keine Medien.'}</p>
        {/each}

        <div class="form-grid catalog-add" style="margin-top:1rem">
          <label>Neues Medium
            <input
              class="catalog-cell"
              style="border-color:var(--line);background:var(--bg-soft)"
              type="text"
              data-catalog-new-media
              bind:value={catalogNewMedia}
              placeholder="z. B. Lack, PLA, Öl…"
              disabled={saving && catalogSavingKey === 'new:media'}
              onblur={commitNewMedia}
              onkeydown={onNewMediaKeydown}
              aria-label="Neues Medium"
            />
          </label>
        </div>
      </div>

      <div class="catalog-block">
        <h3>Tags</h3>
        <div class="filter-bar form-grid">
          <label class="list-search">Suche
            <input type="search" placeholder="Tag-Name…" bind:value={listUi.catalogTags.q} />
          </label>
        </div>
        <div class="table-wrap catalog-table-wrap">
          <table class="catalog-table">
            <thead>
              <tr>
                <th>
                  <button type="button" class="th-sort" onclick={() => toggleListSort('catalogTags', 'name')}>
                    Name{sortMark(listUi.catalogTags.sortKey, 'name', listUi.catalogTags.sortDir)}
                  </button>
                </th>
                <th class="col-actions"></th>
              </tr>
            </thead>
            <tbody>
              {#each displayedCatalogTags as t}
                <tr>
                  <td>
                    {#if t.is_system}
                      <span class="catalog-cell catalog-cell-static" title="System-Tag (Unvollständigkeit)">{t.name}</span>
                    {:else}
                      <input
                        class="catalog-cell"
                        type="text"
                        value={catalogCellValue('tag', t.id, 'name', t.name)}
                        disabled={saving && catalogSavingKey === catalogCellKey('tag', t.id, 'name')}
                        onfocus={() => beginCatalogEdit('tag', t.id, 'name', t.name)}
                        oninput={(e) => setCatalogEditValue('tag', t.id, 'name', e.currentTarget.value)}
                        onblur={commitCatalogEdit}
                        onkeydown={onCatalogEditKeydown}
                        aria-label={`Tag ${t.name}`}
                      />
                    {/if}
                  </td>
                  <td class="col-actions">
                    {#if !t.is_system}
                      <button type="button" class="btn-icon danger" title="Löschen" aria-label="Tag löschen" disabled={saving} onclick={() => deleteCatalogTag(t)}>✕</button>
                    {/if}
                  </td>
                </tr>
              {:else}
                <tr><td colspan="2" class="empty">{listUi.catalogTags.q ? 'Keine Treffer.' : 'Noch keine Tags.'}</td></tr>
              {/each}
              <tr class="catalog-new-row">
                <td>
                  <input
                    class="catalog-cell"
                    type="text"
                    data-catalog-new-tag
                    bind:value={catalogNewTag}
                    placeholder="Neuer Tag…"
                    disabled={saving && catalogSavingKey === 'new:tag'}
                    onblur={commitNewTag}
                    onkeydown={onNewTagKeydown}
                    aria-label="Neuer Tag"
                  />
                </td>
                <td class="col-actions"></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  {:else if tab === 'import'}
    <section class="panel">
      <div class="panel-header">
        <h2>Import-Warteschlange</h2>
        <div class="panel-actions" style="display:flex;flex-wrap:wrap;gap:.5rem;align-items:center">
          <label class="btn" style="display:inline-flex;align-items:center;gap:.35rem">
            Shopify-CSV Assistent
            <input type="file" accept=".csv,text/csv" hidden onchange={onImportFile} disabled={saving} />
          </label>
        </div>
      </div>
      <p class="empty" style="margin-top:0">
        Handles aus dem Assistenten (Serie Produkt/Material oder On-Demand). Medium wählen, Shopify-Farben dem Katalog mappen, dann Serienanlage.
      </p>
      <div class="filter-bar form-grid">
        <label>Status
          <select bind:value={importQueueFilter}>
            <option value="open">Offen</option>
            <option value="done">Erledigt</option>
            <option value="all">Alle</option>
          </select>
        </label>
      </div>
      <div class="table-wrap desktop-only">
        <table>
          <thead>
            <tr>
              <th>Titel</th>
              <th>Typ</th>
              <th>Optionen</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each importQueueRows() as row}
              <tr class:empty={row.status === 'done'}>
                <td>
                  <strong>{row.title}</strong>
                  <div class="empty" style="margin:0">{row.handle}</div>
                </td>
                <td>
                  {row.kind === 'material' ? 'Serie Material' : row.on_demand ? 'On-Demand' : 'Serie Produkt'}
                </td>
                <td>
                  {(row.option_axes || []).join(' · ') || '—'}
                  {#if row.option_values}
                    <div class="empty" style="margin:0;font-size:.85em">
                      {Object.entries(row.option_values)
                        .map(([k, v]) => `${k}: ${(v || []).length}`)
                        .join(' · ')}
                    </div>
                  {/if}
                </td>
                <td>{row.status === 'done' ? 'erledigt' : 'offen'}</td>
                <td class="col-actions">
                  {#if row.status === 'open'}
                    <button type="button" class="btn" onclick={() => startQueueSeries(row)}>Serienanlage</button>
                    <button type="button" class="btn secondary" onclick={() => discardQueueItem(row.handle)}>Verwerfen</button>
                  {:else}
                    <button type="button" class="btn secondary" onclick={() => reopenQueueItem(row.handle)}>Wieder öffnen</button>
                    <button type="button" class="btn secondary" onclick={() => discardQueueItem(row.handle)}>Löschen</button>
                  {/if}
                </td>
              </tr>
            {:else}
              <tr><td colspan="5" class="empty">Keine Einträge — im Assistenten Serie/On-Demand markieren.</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div class="card-list mobile-only">
        {#each importQueueRows() as row}
          <article class="card" class:empty={row.status === 'done'}>
            <h3>{row.title}</h3>
            <p class="empty">{row.handle}</p>
            <p>
              {row.kind === 'material' ? 'Serie Material' : row.on_demand ? 'On-Demand' : 'Serie Produkt'}
              · {row.status === 'done' ? 'erledigt' : 'offen'}
            </p>
            <div class="row-actions">
              {#if row.status === 'open'}
                <button type="button" class="btn" onclick={() => startQueueSeries(row)}>Serienanlage</button>
                <button type="button" class="btn secondary" onclick={() => discardQueueItem(row.handle)}>Verwerfen</button>
              {:else}
                <button type="button" class="btn secondary" onclick={() => reopenQueueItem(row.handle)}>Wieder öffnen</button>
                <button type="button" class="btn secondary" onclick={() => discardQueueItem(row.handle)}>Löschen</button>
              {/if}
            </div>
          </article>
        {:else}
          <p class="empty">Keine Einträge — im Assistenten Serie/On-Demand markieren.</p>
        {/each}
      </div>
    </section>
  {:else if tab === 'sets'}
    <section class="panel">
      <div class="panel-header">
        <h2>Shopify-Sets</h2>
        <div class="panel-actions" style="display:flex;flex-wrap:wrap;gap:.5rem;align-items:center">
          <label class="btn" style="display:inline-flex;align-items:center;gap:.35rem">
            Shopify-CSV Assistent
            <input type="file" accept=".csv,text/csv" hidden onchange={onImportFile} disabled={saving} />
          </label>
          <button type="button" class="btn secondary" onclick={openIgnoredHandles}>Ignorieren-Liste</button>
          <button type="button" class="btn secondary" onclick={openSetCleanup} disabled={!sets.length}>Sets aufräumen</button>
        </div>
      </div>

      <div class="steps-intro">
        <p><strong>Was ist ein Set?</strong> Nur Zusammenstellungen aus <em>mehreren</em> Lagerprodukten (z. B. Geburtstagsset). Einfache Farbvarianten → Assistent als Serie markieren, dann Tab <strong>Import</strong> → Serienanlage.</p>
        <ol>
          <li>Produkte-CSV laden → Handles einordnen (Set / Serie / On-Demand / ignorieren)</li>
          <li>Bei Sets: Optionen zuordnen und anwenden; bei Serie: Tab Import</li>
          <li>Baubarkeit prüfen</li>
        </ol>
      </div>

      <div class="filter-bar form-grid">
        <label class="list-search">Suche
          <input type="search" placeholder="Set, Status…" bind:value={listUi.sets.q} />
        </label>
      </div>

      <div class="table-wrap desktop-only">
        <table>
          <thead>
            <tr>
              <th>
                <button type="button" class="th-sort" onclick={() => toggleListSort('sets', 'name')}>
                  Set{sortMark(listUi.sets.sortKey, 'name', listUi.sets.sortDir)}
                </button>
              </th>
              <th>
                <button type="button" class="th-sort" onclick={() => toggleListSort('sets', 'variant_count')}>
                  Varianten{sortMark(listUi.sets.sortKey, 'variant_count', listUi.sets.sortDir)}
                </button>
              </th>
              <th>
                <button type="button" class="th-sort" onclick={() => toggleListSort('sets', 'status')}>
                  Status{sortMark(listUi.sets.sortKey, 'status', listUi.sets.sortDir)}
                </button>
              </th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each displayedSets as setItem}
              <tr>
                <td>{setItem.name}</td>
                <td>{setItem.variant_count}</td>
                <td>{setStatus(setItem)}</td>
                <td><button class="btn secondary" onclick={() => openSet(setItem)}>Einrichten</button></td>
              </tr>
            {:else}
              <tr><td colspan="4" class="empty">{listUi.sets.q ? 'Keine Treffer.' : 'Noch kein Set — oben Shopify Produkte- oder Inventory-CSV wählen.'}</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div class="card-list">
        {#each displayedSets as setItem}
          <article class="item-card">
            <h3>{setItem.name}</h3>
            <div class="meta">
              <span>{setItem.variant_count} Varianten</span>
              <span>{setStatus(setItem)}</span>
            </div>
            <button class="btn secondary" onclick={() => openSet(setItem)}>Einrichten</button>
          </article>
        {:else}
          <p class="empty">{listUi.sets.q ? 'Keine Treffer.' : 'Noch kein Set — Shopify-CSV importieren.'}</p>
        {/each}
      </div>
    </section>
  {/if}
  {/if}
</div>

{#if passwordModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (passwordModal = false)}>
    <div class="modal" role="dialog" aria-modal="true">
      <h3>Passwort ändern</h3>
      <form class="form-grid" onsubmit={(e) => { e.preventDefault(); submitPasswordChange() }}>
        <label>Aktuelles Passwort
          <input type="password" bind:value={passwordForm.current_password} required autocomplete="current-password" />
        </label>
        <label>Neues Passwort
          <input type="password" bind:value={passwordForm.new_password} required minlength="6" autocomplete="new-password" />
        </label>
        <label>Neues Passwort wiederholen
          <input type="password" bind:value={passwordForm.confirm} required minlength="6" autocomplete="new-password" />
        </label>
        <div class="modal-actions">
          <button type="button" class="btn secondary" onclick={() => (passwordModal = false)}>Abbrechen</button>
          <button class="btn" disabled={saving}>Speichern</button>
        </div>
      </form>
    </div>
  </div>
{/if}

{#if materialModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && closeMaterialModal()}>
    <div class="modal" role="dialog" aria-modal="true">
      {#if materialModal.mode === 'edit'}
        <div class="modal-sticky">
          <h3>Material bearbeiten</h3>
          <p class="modal-sticky-name">{materialForm.name || materialModal.material?.name || '—'}</p>
          {#if showEditNav && editNav?.kind === 'material'}
            <div class="edit-nav">
              <button type="button" class="btn secondary" disabled={saving || !editNavHasPrev} onclick={() => stepEditNav(-1)}>Vorheriger</button>
              <button type="button" class="btn secondary" disabled={saving || !editNavHasNext} onclick={() => stepEditNav(1)}>Nächster</button>
            </div>
          {/if}
        </div>
      {:else}
        <h3>Material anlegen</h3>
      {/if}
      <form class="form-grid" onsubmit={(e) => { e.preventDefault(); saveMaterial() }}>
        <label>Name
          <input list="material-name-suggestions" bind:value={materialForm.name} required />
        </label>
        <datalist id="material-name-suggestions">
          {#each materials as m}<option value={m.name}></option>{/each}
        </datalist>
        <label>Einheit
          <select bind:value={materialForm.unit}>{#each units as u}<option value={u.value}>{u.label}</option>{/each}</select>
        </label>
        <label>Nachkommastellen
          <select bind:value={materialForm.decimal_places}>
            <option value={0}>0 (ganze Zahlen)</option>
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
          </select>
        </label>
        <label>Einkaufsmenge (Packung in Einheit)
          <input type="number" step={qtyStep(materialForm.decimal_places)} min={qtyStep(materialForm.decimal_places)} bind:value={materialForm.purchase_quantity} required />
        </label>
        <label>Einkaufspreis für diese Menge (€)
          <input type="number" step="0.01" bind:value={materialForm.purchase_price} required />
        </label>
        <p class="empty" style="margin:0">
          → Preis/Einheit: {formatUnitCost(computedUnitCost(materialForm.purchase_price, materialForm.purchase_quantity))}
          (z. B. 750 ml für 30 € → 0,04 €/ml)
        </p>
        <label>Mindestbestand (optional)
          <input type="number" step={qtyStep(materialForm.decimal_places)} min="0" bind:value={materialForm.min_stock} placeholder="leer = keiner" />
        </label>
        <label>Materialfamilie
          <input list="material-family-suggestions" bind:value={materialForm.family} placeholder="optional" />
        </label>
        <datalist id="material-family-suggestions">
          {#each materialFamilies as f}<option value={f}></option>{/each}
        </datalist>
        {#if materialModal.mode === 'edit'}
          <label class="tag-check">
            <input type="checkbox" bind:checked={materialForm.is_template} />
            Ist Vorlage
          </label>
        {/if}
        <label>Medium
          <select
            bind:value={materialForm.medium_id}
            onchange={() => onFormMediumChange(materialForm)}
          >
            <option value="">keine</option>
            {#each media as m}<option value={m.id}>{m.name}</option>{/each}
          </select>
        </label>
        {#if materialForm.medium_id}
          <label>Farbe
            <select bind:value={materialForm.color_id}>
              <option value="">keine</option>
              {#each colorsForMedium(materialForm.medium_id) as c}<option value={c.id}>{c.name}</option>{/each}
            </select>
          </label>
        {/if}
        {#if !showMaterialTags}
          <button type="button" class="btn secondary" onclick={() => (showMaterialTags = true)}>Tags zuordnen</button>
        {:else}
          <fieldset class="tag-picker">
            <legend>Tags</legend>
            {#each allTags as t}
              {@const familyTaken = tagFullyOnFamily('material', materialForm.family, t.id)}
              <label class="tag-check" class:tag-muted={familyTaken && !materialForm.tagIds.includes(t.id)}>
                <input
                  type="checkbox"
                  checked={materialForm.tagIds.includes(t.id)}
                  disabled={familyTaken && !materialForm.tagIds.includes(t.id)}
                  onchange={() => toggleTagId(materialForm, t.id, 'material')}
                />
                {t.name}{#if familyTaken && !materialForm.tagIds.includes(t.id)} <span class="empty">(Familie hat ihn)</span>{/if}
              </label>
            {:else}
              <p class="empty">Keine Tags im Katalog — unter „Kataloge“ anlegen.</p>
            {/each}
          </fieldset>
        {/if}
        {#if materialModal.mode === 'create'}
          <label>Anfangsbestand-Standort
            <select bind:value={materialForm.location_id}>{#each materialLocations as l}<option value={l.id}>{l.name}</option>{/each}</select>
          </label>
          <label>Anfangsbestand<input type="number" step={qtyStep(materialForm.decimal_places)} bind:value={materialForm.stock_quantity} required /></label>
        {/if}
        <div class="modal-actions">
          <button type="button" class="btn secondary" onclick={() => closeMaterialModal()}>Abbrechen</button>
          <button class="btn" disabled={saving}>{saveButtonOk ? '✓ Gespeichert' : 'Speichern'}</button>
        </div>
      </form>
      {#if materialModal.mode === 'edit'}
        <div class="bom-block">
          <h4>Bestand je Standort (Gesamt {formatQty(materialModal.material?.stock_total ?? 0, itemDecimals(materialModal.material))})</h4>
          {#each materialLocations as loc}
            {#if stockDrafts[loc.id]}
            <div class="stock-row">
              <strong>{loc.name}</strong>
              <label>Setzen
                <input type="number" step={qtyStep(itemDecimals(materialModal.material))} bind:value={stockDrafts[loc.id].setValue} />
              </label>
              <button type="button" class="btn secondary" disabled={saving} onclick={() => setMaterialStock(loc.id)}>Setzen</button>
              <label>+/− Menge
                <input type="number" step={qtyStep(itemDecimals(materialModal.material))} min={qtyStep(itemDecimals(materialModal.material))} bind:value={stockDrafts[loc.id].deltaValue} />
              </label>
              <div class="row-actions">
                <button type="button" class="btn secondary" disabled={saving} onclick={() => deltaMaterialStock(loc.id, 1)}>+</button>
                <button type="button" class="btn secondary" disabled={saving} onclick={() => deltaMaterialStock(loc.id, -1)}>−</button>
              </div>
            </div>
            {/if}
          {/each}
        </div>
        {#if showEditNav && editNav?.kind === 'material'}
          <div class="edit-nav edit-nav-bottom">
            <button type="button" class="btn secondary" disabled={saving || !editNavHasPrev} onclick={() => stepEditNav(-1)}>Vorheriger</button>
            <button type="button" class="btn secondary" disabled={saving || !editNavHasNext} onclick={() => stepEditNav(1)}>Nächster</button>
          </div>
        {/if}
      {/if}
    </div>
  </div>
{/if}

{#if productModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && closeProductModal()}>
    <div class="modal" role="dialog" aria-modal="true">
      {#if productModal.mode === 'edit'}
        <div class="modal-sticky">
          <h3>Produkt bearbeiten</h3>
          <p class="modal-sticky-name">{productForm.name || productModal.product?.name || '—'}</p>
          {#if showEditNav && editNav?.kind === 'product'}
            <div class="edit-nav">
              <button type="button" class="btn secondary" disabled={saving || !editNavHasPrev} onclick={() => stepEditNav(-1)}>Vorheriger</button>
              <button type="button" class="btn secondary" disabled={saving || !editNavHasNext} onclick={() => stepEditNav(1)}>Nächster</button>
            </div>
          {/if}
        </div>
      {:else}
        <h3>Produkt anlegen</h3>
      {/if}
      <form class="form-grid" onsubmit={(e) => { e.preventDefault(); saveProduct() }}>
        <label>Name
          <input list="product-name-suggestions" bind:value={productForm.name} required />
        </label>
        <datalist id="product-name-suggestions">
          {#each products as p}<option value={p.name}></option>{/each}
        </datalist>
        <label>SKU<input bind:value={productForm.sku} placeholder="optional" /></label>
        <label>Verkaufspreis (€)
          <input type="number" step="0.01" min="0" bind:value={productForm.selling_price} />
        </label>
        <label>Produktfamilie
          <input list="product-family-suggestions" bind:value={productForm.family} placeholder="optional, z. B. Ring" />
        </label>
        <datalist id="product-family-suggestions">
          {#each productFamilies as f}<option value={f}></option>{/each}
        </datalist>
        <label>Mindestbestand (optional)
          <input type="number" step={qtyStep(0)} min="0" bind:value={productForm.min_stock} placeholder="leer = keiner" />
        </label>
        {#if productModal.mode === 'edit'}
          <label class="tag-check">
            <input type="checkbox" bind:checked={productForm.is_template} />
            Ist Vorlage
          </label>
        {/if}
        <label>Wird zu (Umwandlung)
          <FamilySelect
            bind:value={productForm.transform_target_id}
            items={products.filter((p) => !productModal.product || p.id !== productModal.product.id)}
            emptyLabel="keins"
          />
        </label>
        <label>Medium
          <select
            bind:value={productForm.medium_id}
            onchange={() => onFormMediumChange(productForm)}
          >
            <option value="">keine</option>
            {#each media as m}<option value={m.id}>{m.name}</option>{/each}
          </select>
        </label>
        {#if productForm.medium_id}
          <label>Farbe
            <select
              bind:value={productForm.color_id}
              onchange={() => loadColorSuggestions(productForm.color_id ? Number(productForm.color_id) : null)}
            >
              <option value="">keine</option>
              {#each colorsForMedium(productForm.medium_id) as c}<option value={c.id}>{c.name}</option>{/each}
            </select>
          </label>
        {/if}
        {#if !showProductTags}
          <button type="button" class="btn secondary" onclick={() => (showProductTags = true)}>Tags zuordnen</button>
        {:else}
          <fieldset class="tag-picker">
            <legend>Tags</legend>
            {#each allTags as t}
              {@const familyTaken = tagFullyOnFamily('product', productForm.family, t.id)}
              <label class="tag-check" class:tag-muted={familyTaken && !productForm.tagIds.includes(t.id)}>
                <input
                  type="checkbox"
                  checked={productForm.tagIds.includes(t.id)}
                  disabled={familyTaken && !productForm.tagIds.includes(t.id)}
                  onchange={() => toggleTagId(productForm, t.id, 'product')}
                />
                {t.name}{#if familyTaken && !productForm.tagIds.includes(t.id)} <span class="empty">(Familie hat ihn)</span>{/if}
              </label>
            {:else}
              <p class="empty">Keine Tags im Katalog — unter „Kataloge“ anlegen.</p>
            {/each}
          </fieldset>
        {/if}
        {#if productModal.mode === 'create'}
          <label>Anfangsbestand-Standort
            <select bind:value={productForm.location_id}>{#each locations as l}<option value={l.id}>{l.name}</option>{/each}</select>
          </label>
          <label>Anfangsbestand<input type="number" step={qtyStep(0)} bind:value={productForm.stock_quantity} required /></label>
        {/if}
        <div class="modal-actions">
          <button type="button" class="btn secondary" onclick={() => closeProductModal()}>Schließen</button>
          <button class="btn" disabled={saving}>{saveButtonOk ? '✓ Gespeichert' : 'Speichern'}</button>
        </div>
      </form>
      {#if productModal.product}
        <div class="bom-block">
          <h4>Bestand je Standort (Gesamt {formatQty(productModal.product.stock_total, 0)})</h4>
          {#each orderedLocations as loc}
            {#if stockDrafts[loc.id]}
            <div class="stock-row">
              <strong>{loc.name}</strong>
              <label>Setzen
                <input type="number" step={qtyStep(0)} bind:value={stockDrafts[loc.id].setValue} />
              </label>
              <button type="button" class="btn secondary" disabled={saving} onclick={() => setProductStock(loc.id)}>Setzen</button>
              <label>+/− Menge
                <input type="number" step={qtyStep(0)} min="1" bind:value={stockDrafts[loc.id].deltaValue} />
              </label>
              <div class="row-actions">
                <button type="button" class="btn secondary" disabled={saving} onclick={() => deltaProductStock(loc.id, 1)}>+</button>
                <button type="button" class="btn secondary" disabled={saving} onclick={() => deltaProductStock(loc.id, -1)}>−</button>
              </div>
            </div>
            {/if}
          {/each}
        </div>
        <div class="bom-block">
          <h4>Stückliste · Materialkosten {formatMoney(productModal.product.material_cost)}</h4>
          <p class="empty" style="margin-top:0">
            Menge = Verbrauch <strong>pro 1 Produkt</strong>. Zeilen können Material oder Produkt sein
            (z. B. Ziffernset aus Einzelziffern).
          </p>
          {#if colorSuggestions.length}
            <div class="suggest-block">
              <p class="empty" style="margin:0 0 .35rem">Vorschläge gleiche Farbe (nicht automatisch eingefügt):</p>
              <div class="suggest-chips">
                {#each colorSuggestions as s}
                  <button type="button" class="chip" onclick={() => applySuggestion(s)}>
                    {s.kind === 'product' ? 'Produkt' : 'Material'}: {s.name} · {s.color_label}
                  </button>
                {/each}
              </div>
            </div>
          {/if}
          {#each productModal.product.bom as line}
            <div class="bom-line">
              <div>
                {line.component_kind === 'product' ? 'Produkt' : 'Material'}:
                {line.component_name || line.material_name}
                · {formatQty(line.quantity_required, line.decimal_places ?? 0)}{line.material_unit ? ` ${line.material_unit}` : ''}
                · {formatMoney(line.line_cost)}
              </div>
              <button type="button" class="btn danger" onclick={() => removeBomLine(line)}>Entfernen</button>
            </div>
          {:else}
            <p class="empty">Keine Stückliste.</p>
          {/each}
          <div class="form-grid" style="margin-top:.75rem">
            <label>Art
              <select bind:value={bomForm.kind}>
                <option value="material">Material</option>
                <option value="product">Produkt</option>
              </select>
            </label>
            {#if bomForm.kind === 'product'}
              <label>Produkt
                <FamilySelect bind:value={bomForm.product_id} items={availableBomProducts} emptyLabel="wählen…" />
              </label>
            {:else}
              <label>Material
                <FamilySelect
                  bind:value={bomForm.material_id}
                  items={availableBomMaterials}
                  emptyLabel="wählen…"
                  formatItem={(m) => `${m.name} (${m.unit})`}
                />
              </label>
            {/if}
            <label>Menge pro Produkteinheit
              <input type="number" step={bomQtyStep} min={bomQtyStep} bind:value={bomForm.quantity_required} placeholder="z. B. 1" required />
            </label>
            <div class="row-actions">
              <button
                class="btn secondary"
                disabled={
                  saving ||
                  !bomForm.quantity_required ||
                  (bomForm.kind === 'product' ? !bomForm.product_id : !bomForm.material_id)
                }
                onclick={addBomLine}
              >
                Zur Stückliste hinzufügen
              </button>
              {#if bomForm.kind === 'material'}
                <button
                  type="button"
                  class="btn secondary"
                  onclick={() => (inlineMaterialForm = inlineMaterialForm ? null : emptyInlineMaterial())}
                >
                  {inlineMaterialForm ? 'Material-Anlage ausblenden' : 'Fehlendes Material anlegen'}
                </button>
              {/if}
            </div>
          </div>
          {#if inlineMaterialForm}
            <div class="bom-block" style="border-top:none;margin-top:.5rem">
              <h4>Neues Material</h4>
              <div class="form-grid">
                <label>Name<input bind:value={inlineMaterialForm.name} required /></label>
                <label>Einheit
                  <select bind:value={inlineMaterialForm.unit}>{#each units as u}<option value={u.value}>{u.label}</option>{/each}</select>
                </label>
                <label>Nachkommastellen
                  <select bind:value={inlineMaterialForm.decimal_places}>
                    <option value={0}>0</option>
                    <option value={1}>1</option>
                    <option value={2}>2</option>
                    <option value={3}>3</option>
                  </select>
                </label>
                <label>Einkaufsmenge<input type="number" step={qtyStep(inlineMaterialForm.decimal_places)} min={qtyStep(inlineMaterialForm.decimal_places)} bind:value={inlineMaterialForm.purchase_quantity} /></label>
                <label>Einkaufspreis (€)<input type="number" step="0.01" bind:value={inlineMaterialForm.purchase_price} /></label>
                <p class="empty" style="margin:0">
                  → {formatUnitCost(computedUnitCost(inlineMaterialForm.purchase_price, inlineMaterialForm.purchase_quantity))} / Einheit
                </p>
                <label>Standort
                  <select bind:value={inlineMaterialForm.location_id}>{#each locations as l}<option value={l.id}>{l.name}</option>{/each}</select>
                </label>
                <label>Anfangsbestand<input type="number" step={qtyStep(inlineMaterialForm.decimal_places)} bind:value={inlineMaterialForm.stock_quantity} /></label>
                <button class="btn" disabled={saving || !inlineMaterialForm.name.trim()} onclick={createInlineMaterial}>
                  Material anlegen & auswählen
                </button>
              </div>
            </div>
          {/if}
        </div>
      {/if}
      {#if showEditNav && editNav?.kind === 'product'}
        <div class="edit-nav edit-nav-bottom">
          <button type="button" class="btn secondary" disabled={saving || !editNavHasPrev} onclick={() => stepEditNav(-1)}>Vorheriger</button>
          <button type="button" class="btn secondary" disabled={saving || !editNavHasNext} onclick={() => stepEditNav(1)}>Nächster</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

{#if manufactureModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (manufactureModal = null, manufactureTodoId = null)}>
    <div class="modal" role="dialog" aria-modal="true">
      <h3>Fertigen: {manufactureModal.name}</h3>
      <form class="form-grid" onsubmit={(e) => { e.preventDefault(); runManufacture() }}>
        <label>Menge<input type="number" step={qtyStep(0)} min="1" bind:value={manufactureForm.quantity} required /></label>
        <label>Standort
          <select bind:value={manufactureForm.location_id}>{#each locations as l}<option value={l.id}>{l.name}</option>{/each}</select>
        </label>
        <div class="modal-actions">
          <button type="button" class="btn secondary" onclick={() => { manufactureModal = null; manufactureTodoId = null }}>Abbrechen</button>
          <button class="btn" disabled={saving}>Fertigen</button>
        </div>
      </form>
    </div>
  </div>
{/if}

{#if purchaseModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (purchaseModal = null)}>
    <div class="modal" role="dialog" aria-modal="true">
      <h3>Einkauf: {purchaseModal.name}</h3>
      <form class="form-grid" onsubmit={(e) => { e.preventDefault(); submitPurchase() }}>
        <label>Menge ({purchaseModal.unit})
          <input type="number" step={qtyStep(itemDecimals(purchaseModal))} min={qtyStep(itemDecimals(purchaseModal))} bind:value={purchaseForm.quantity} required />
        </label>
        <label>Standort
          <select bind:value={purchaseForm.location_id}>{#each materialLocations as l}<option value={l.id}>{l.name}</option>{/each}</select>
        </label>
        <label>Neuer Einkaufspreis (€)
          <input type="number" step="0.01" min="0" bind:value={purchaseForm.purchase_price} required />
        </label>
        <p class="empty" style="margin:0">Bisher: {formatMoney(purchaseModal.purchase_price)}</p>
        <div class="modal-actions">
          <button type="button" class="btn secondary" onclick={() => (purchaseModal = null)}>Abbrechen</button>
          <button class="btn" disabled={saving}>Speichern</button>
        </div>
      </form>
    </div>
  </div>
{/if}

{#if transferModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (transferModal = null)}>
    <div class="modal" role="dialog" aria-modal="true">
      <h3>Umbuchen: {transferModal.item.name}</h3>
      <form class="form-grid" onsubmit={(e) => { e.preventDefault(); runTransfer() }}>
        <label>Von<select bind:value={transferForm.from_location_id}>{#each locations as l}<option value={l.id}>{l.name}</option>{/each}</select></label>
        <label>Nach<select bind:value={transferForm.to_location_id}>{#each locations as l}<option value={l.id}>{l.name}</option>{/each}</select></label>
        <label>Menge<input type="number" step={transferModal.kind === 'material' ? qtyStep(itemDecimals(transferModal.item)) : qtyStep(0)} min={transferModal.kind === 'material' ? qtyStep(itemDecimals(transferModal.item)) : '1'} bind:value={transferForm.quantity} required /></label>
        <label>Notiz (optional)<input bind:value={transferForm.note} placeholder="z. B. Ausschuss / zurück" /></label>
        <div class="modal-actions">
          <button type="button" class="btn secondary" onclick={() => (transferModal = null)}>Abbrechen</button>
          <button class="btn" disabled={saving}>Umbuchen</button>
        </div>
      </form>
    </div>
  </div>
{/if}

{#if transformModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (transformModal = null)}>
    <div class="modal" role="dialog" aria-modal="true">
      <h3>Umwandeln: {transformModal.name} → {transformModal.transform_target_name}</h3>
      <form class="form-grid" onsubmit={(e) => { e.preventDefault(); runTransform() }}>
        <label>Standort
          <select bind:value={transformForm.location_id}>
            {#each locations as l}<option value={l.id}>{l.name}</option>{/each}
          </select>
        </label>
        <label>Menge<input type="number" step={qtyStep(0)} min="1" bind:value={transformForm.quantity} required /></label>
        <label>Notiz (optional)<input bind:value={transformForm.note} /></label>
        <div class="modal-actions">
          <button type="button" class="btn secondary" onclick={() => (transformModal = null)}>Abbrechen</button>
          <button class="btn" disabled={saving}>Umwandeln</button>
        </div>
      </form>
    </div>
  </div>
{/if}

{#if movementsModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (movementsModal = null)}>
    <div class="modal" role="dialog" aria-modal="true" style="width:min(720px,100%)">
      <h3>Historie: {movementsModal.title}</h3>
      <p class="empty" style="margin-top:0">Umbuchungen mit virtuellen Standorten und Umwandlungen.</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Wann</th>
              <th>Art</th>
              <th>Von</th>
              <th>Nach</th>
              <th class="num">Menge</th>
              <th>Notiz</th>
            </tr>
          </thead>
          <tbody>
            {#each movementsModal.rows as row}
              <tr>
                <td class="meta-cell">{formatDateTime(row.created_at)}</td>
                <td>
                  {#if row.kind === 'transform'}
                    Umwandlung{#if row.to_product_name}: → {row.to_product_name}{/if}
                  {:else}
                    Umbuchen
                  {/if}
                </td>
                <td>{row.from_location_name}</td>
                <td>{row.to_location_name}</td>
                <td class="num">{formatQty(row.quantity)}</td>
                <td>{row.note || '—'}</td>
              </tr>
            {:else}
              <tr><td colspan="6" class="empty">Noch keine Bewegungen.</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn secondary" onclick={() => (movementsModal = null)}>Schließen</button>
      </div>
    </div>
  </div>
{/if}

{#if setModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (setModal = null)}>
    <div class="modal" role="dialog" aria-modal="true" style="width:min(960px,100%)">
      <h3>{setModal.name}</h3>
      <p class="empty" style="margin-top:0">{setModal.variant_count} Varianten aus Shopify</p>

      <div class="wizard-steps">
        <button type="button" class="wizard-step" class:active={setStep === 1} onclick={() => (setStep = 1)}>1. Überblick</button>
        <button type="button" class="wizard-step" class:active={setStep === 2} onclick={() => (setStep = 2)}>2. Zuordnen</button>
        <button type="button" class="wizard-step" class:active={setStep === 3} onclick={() => (setStep = 3)}>3. Baubarkeit</button>
      </div>

      {#if setStep === 1}
        <div class="bom-block">
          <p>Dieses Set existiert nur in Shopify. Hier verknüpfst du die Shopify-Farben mit euren Lagerartikeln, damit die App sagt, wie viele Sets ihr noch zusammenstellen könnt.</p>
          <ul class="plain-list">
            <li>{setModal.variant_count} Varianten geladen</li>
            <li>{setModal.option_mappings.length} Options-Zuordnungen</li>
            <li>{setModal.variants.filter((v) => v.bom?.length).length} Varianten mit Stückliste</li>
            <li>{setUsedComponents.length} verschiedene Lagerartikel in Stücklisten</li>
          </ul>
          <label class="check-row">
            <input type="checkbox" checked={setModal.count_materials_in_buildability} onchange={toggleMaterialCheck} />
            Auch Material-Bestände für „baubar“ prüfen (nicht nur Produkte)
          </label>

          <h4>Options-Zuordnungen</h4>
          {#each setModal.option_mappings as mapping}
            <div class="bom-line">
              <div>
                <strong>{mapping.option_name}</strong> „{mapping.option_value}“
                → {mapping.component_kind === 'product' ? 'Produkt' : 'Material'}
                {mapping.component_name}
                (× {formatQty(mapping.quantity_required)})
              </div>
              <button type="button" class="btn danger" disabled={saving} onclick={() => removeMapping(mapping)}>Entfernen</button>
            </div>
          {:else}
            <p class="empty">Keine Options-Zuordnung — unter Schritt 2 anlegen.</p>
          {/each}

          <h4 style="margin-top:1rem">Lagerartikel in Varianten-Stücklisten</h4>
          <p class="empty" style="margin-top:0">Auch nach „Anwenden“ sichtbar — hier kannst du z. B. „Farbe Blau Test“ komplett aus dem Set nehmen.</p>
          {#each setUsedComponents as comp}
            <div class="bom-line">
              <div>
                {comp.kind === 'product' ? 'Produkt' : 'Material'}
                <strong>{comp.name}</strong>
                <span class="empty">· in {comp.count} Varianten</span>
              </div>
              <button type="button" class="btn danger" disabled={saving} onclick={() => detachSetComponent(comp)}>Entfernen</button>
            </div>
          {:else}
            <p class="empty">Noch keine Stücklistenzeilen — Zuordnungen anwenden oder manuell setzen.</p>
          {/each}

          <div class="modal-actions">
            <button type="button" class="btn" onclick={() => (setStep = 2)}>Weiter zu Zuordnen</button>
            <button type="button" class="btn secondary" onclick={() => (setStep = 3)}>Zur Baubarkeit</button>
          </div>
        </div>
      {:else if setStep === 2}
        <div class="bom-block">
          <p class="empty" style="margin-top:0">
            Pro Options-Name: Medium + Vorlage/Familie. Darunter alle Shopify-Werte — Katalogfarbe matchen
            (bei Unklarheit Dropdown), Artikel folgt aus Farbe. Menge immer 1.
          </p>

          <h4>Gespeicherte Zuordnungen</h4>
          {#each setModal.option_mappings as mapping}
            <div class="bom-line">
              <div>
                <strong>{mapping.option_name}</strong> „{mapping.option_value}“
                → {mapping.component_kind === 'product' ? 'Produkt' : 'Material'}
                {mapping.component_name}
                (× {formatQty(mapping.quantity_required)})
              </div>
              <button type="button" class="btn danger" onclick={() => removeMapping(mapping)}>Entfernen</button>
            </div>
          {:else}
            <p class="empty">Noch keine Zuordnung — unten die erste Option zuordnen.</p>
          {/each}

          <h4 style="margin-top:1rem">Option zuordnen</h4>
          <div class="form-grid">
            <label>Options-Name
              <select bind:value={mappingForm.option_name}>
                {#each optionNames as n}<option value={n}>{n}</option>{/each}
              </select>
            </label>
            <label>Medium
              <select
                value={getSetOptionConfig(mappingForm.option_name).mediumId}
                onchange={(e) => patchSetOptionConfig(mappingForm.option_name, { mediumId: e.currentTarget.value })}
              >
                <option value="">wählen… (z. B. Lack / PLA)</option>
                {#each media as m}<option value={m.id}>{m.name}</option>{/each}
              </select>
            </label>
            <label>Artikel-Typ
              <select
                value={getSetOptionConfig(mappingForm.option_name).kind}
                onchange={(e) => patchSetOptionConfig(mappingForm.option_name, { kind: e.currentTarget.value })}
              >
                <option value="product">Produkt (Ring / Kerzenset / Ziffernset)</option>
                <option value="material">Material</option>
              </select>
            </label>
            {#if getSetOptionConfig(mappingForm.option_name).kind === 'product'}
              <label>Vorlage
                <FamilySelect
                  value={getSetOptionConfig(mappingForm.option_name).templateId}
                  items={productsForBomTemplate}
                  emptyLabel="ohne"
                  formatItem={(p) => p.is_template ? `Vorlage: ${p.name}` : p.name}
                  onchange={(tid) => {
                    const t = products.find((p) => p.id === Number(tid))
                    const series = t ? templateSeriesPrefix(t, colors) : ''
                    patchSetOptionConfig(mappingForm.option_name, {
                      templateId: tid,
                      baseName: series || t?.family || getSetOptionConfig(mappingForm.option_name).baseName,
                    })
                  }}
                />
              </label>
              <label>Basisname / Familie
                <input
                  list="product-family-suggestions"
                  value={getSetOptionConfig(mappingForm.option_name).baseName}
                  oninput={(e) => patchSetOptionConfig(mappingForm.option_name, { baseName: e.currentTarget.value })}
                  placeholder="z. B. Geburtstagsring - Uni"
                />
              </label>
            {/if}
          </div>

          {#if getSetOptionConfig(mappingForm.option_name).mediumId}
            <div class="table-wrap" style="margin-top:1rem">
              <table>
                <thead>
                  <tr>
                    <th>Shopify-Wert</th>
                    <th>Katalogfarbe</th>
                    <th>Lagerartikel</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {#each setBatchRows as row (row.key)}
                    <tr class:neg={row.status.startsWith('ambiguous') || row.status.startsWith('missing')}>
                      <td>
                        {row.value}
                        {#if row.already}<div class="empty">schon zugeordnet</div>{/if}
                      </td>
                      <td>
                        {#if row.already}
                          —
                        {:else if row.status === 'skip'}
                          <span class="empty">übersprungen</span>
                        {:else}
                          <select
                            value={row.colorId}
                            onchange={(e) =>
                              patchSetRow(mappingForm.option_name, row.value, {
                                colorId: e.currentTarget.value,
                                componentId: '',
                                skip: false,
                              })}
                          >
                            <option value="">{row.status === 'ambiguous_color' ? 'klären…' : row.status === 'missing_color' ? 'wählen…' : 'Match…'}</option>
                            {#each (row.candidates.length ? row.candidates : colorsForMedium(getSetOptionConfig(mappingForm.option_name).mediumId)) as c}
                              <option value={c.id}>{c.name}</option>
                            {/each}
                          </select>
                        {/if}
                      </td>
                      <td>
                        {#if row.already}
                          —
                        {:else if row.status === 'skip'}
                          —
                        {:else}
                          <select
                            value={row.componentId}
                            onchange={(e) =>
                              patchSetRow(mappingForm.option_name, row.value, {
                                componentId: e.currentTarget.value,
                                colorId: row.colorId,
                                skip: false,
                              })}
                          >
                            <option value="">{row.comps.length > 1 ? 'wählen…' : '—'}</option>
                            {#each (row.comps.length ? row.comps : resolveSetComponents(row.kind, row.colorId, getSetOptionConfig(mappingForm.option_name).templateId, getSetOptionConfig(mappingForm.option_name).baseName)) as item}
                              <option value={item.id}>{item.name}</option>
                            {/each}
                          </select>
                        {/if}
                      </td>
                      <td>
                        {#if row.already}
                          <span class="empty">ok</span>
                        {:else if row.status === 'ok' && row.componentId}
                          bereit
                        {:else if row.status === 'ambiguous_color'}
                          Farbe unklar
                        {:else if row.status === 'missing_color'}
                          keine Farbe
                        {:else if row.status === 'ambiguous_article'}
                          Artikel unklar
                        {:else if row.status === 'missing_article'}
                          Artikel fehlt
                        {:else if row.status === 'skip'}
                          —
                        {:else}
                          {row.status}
                        {/if}
                        {#if !row.already}
                          <button
                            type="button"
                            class="btn secondary"
                            style="margin-left:.35rem"
                            onclick={() => patchSetRow(mappingForm.option_name, row.value, { skip: true, colorId: '', componentId: '' })}
                          >Skip</button>
                        {/if}
                      </td>
                    </tr>
                  {:else}
                    <tr><td colspan="4" class="empty">Medium wählen, dann erscheinen die Shopify-Werte.</td></tr>
                  {/each}
                </tbody>
              </table>
            </div>
            <div class="row-actions" style="margin-top:.75rem">
              <button type="button" class="btn" disabled={saving || !setBatchReadyCount} onclick={saveBatchMappings}>
                {setBatchReadyCount} Zuordnung(en) speichern
              </button>
              <button type="button" class="btn secondary" disabled={saving} onclick={createMissingBatchArticles}>
                Fehlende Produkte nachlegen…
              </button>
            </div>
          {/if}

          <div class="modal-actions" style="margin-top:1rem">
            <button type="button" class="btn secondary" onclick={() => (setStep = 1)}>Zurück</button>
            <button class="btn" disabled={saving || !setModal.option_mappings.length} onclick={applyMappings}>
              Auf alle Varianten anwenden →
            </button>
          </div>
        </div>
      {:else}
        <div class="bom-block">
          <p>
            <strong>{buildableVariants.length}</strong> Varianten baubar ·
            <strong>{blockedVariants.length}</strong> nicht baubar
            (Summe über alle Standorte)
          </p>
          <label class="check-row">
            <input type="checkbox" checked={setModal.count_materials_in_buildability} onchange={toggleMaterialCheck} />
            Materialien in Baubarkeit mitzählen
          </label>

          <h4>Baubar</h4>
          <div class="filter-bar form-grid">
            <label class="list-search">Suche
              <input type="search" placeholder="Variante, BOM…" bind:value={listUi.setBuildable.q} />
            </label>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>
                    <button type="button" class="th-sort" onclick={() => toggleListSort('setBuildable', 'label')}>
                      Variante{sortMark(listUi.setBuildable.sortKey, 'label', listUi.setBuildable.sortDir)}
                    </button>
                  </th>
                  <th>
                    <button type="button" class="th-sort" onclick={() => toggleListSort('setBuildable', 'buildable_quantity')}>
                      Stück{sortMark(listUi.setBuildable.sortKey, 'buildable_quantity', listUi.setBuildable.sortDir)}
                    </button>
                  </th>
                  <th>
                    <button type="button" class="th-sort" onclick={() => toggleListSort('setBuildable', 'bom')}>
                      Benötigt{sortMark(listUi.setBuildable.sortKey, 'bom', listUi.setBuildable.sortDir)}
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody>
                {#each displayedBuildableVariants as variant}
                  <tr>
                    <td>{variant.label}</td>
                    <td>{variant.buildable_quantity}</td>
                    <td>
                      {#each variant.bom as line}
                        <div>{line.component_name} × {formatQty(line.quantity_required)}</div>
                      {:else}
                        <span class="empty">keine Stückliste</span>
                      {/each}
                    </td>
                  </tr>
                {:else}
                  <tr><td colspan="3" class="empty">{listUi.setBuildable.q ? 'Keine Treffer.' : 'Keine baubare Variante — Zuordnungen prüfen oder Bestand erhöhen.'}</td></tr>
                {/each}
              </tbody>
            </table>
          </div>

          {#if blockedVariants.length}
            <h4 style="margin-top:1rem">Nicht baubar / ohne Stückliste</h4>
            <div class="filter-bar form-grid">
              <label class="list-search">Suche
                <input type="search" placeholder="Variante, BOM…" bind:value={listUi.setBlocked.q} />
              </label>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>
                      <button type="button" class="th-sort" onclick={() => toggleListSort('setBlocked', 'label')}>
                        Variante{sortMark(listUi.setBlocked.sortKey, 'label', listUi.setBlocked.sortDir)}
                      </button>
                    </th>
                    <th>
                      <button type="button" class="th-sort" onclick={() => toggleListSort('setBlocked', 'bom')}>
                        Stückliste{sortMark(listUi.setBlocked.sortKey, 'bom', listUi.setBlocked.sortDir)}
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {#each (listUi.setBlocked.q ? displayedBlockedVariants : displayedBlockedVariants.slice(0, 30)) as variant}
                    <tr>
                      <td>{variant.label}</td>
                      <td>
                        {#each variant.bom as line}
                          <div>{line.component_name} × {formatQty(line.quantity_required)} (Lager {formatQty(line.stock_total)})</div>
                        {:else}
                          <span class="empty">— Zuordnung fehlt oder nicht angewendet</span>
                        {/each}
                      </td>
                    </tr>
                  {:else}
                    <tr><td colspan="2" class="empty">Keine Treffer.</td></tr>
                  {/each}
                </tbody>
              </table>
            </div>
            {#if !listUi.setBlocked.q && displayedBlockedVariants.length > 30}
              <p class="empty">… und {displayedBlockedVariants.length - 30} weitere (Suche zeigt alle)</p>
            {/if}
          {/if}

          <div class="modal-actions">
            <button type="button" class="btn secondary" onclick={() => (setStep = 2)}>Zuordnungen ändern</button>
            <button type="button" class="btn secondary" onclick={() => (setModal = null)}>Fertig</button>
          </div>
        </div>
      {/if}

      <div class="modal-actions">
        <button class="btn secondary" onclick={() => (setModal = null)}>Schließen</button>
      </div>
    </div>
  </div>
{/if}

{#if bulkMaterialModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (bulkMaterialModal = null)}>
    <div class="modal" role="dialog" aria-modal="true">
      <h3>Materialien aus Farben</h3>
      <p class="empty" style="margin-top:0">
        {#if bulkMaterialModal.fromQueue}
          Aus Import-Warteschlange: zuerst <strong>Medium</strong> wählen (Shopify-Farben → Katalog), Vorlage optional.
        {:else}
          Optional Vorlage (Einheit/Einkauf/Tags, „Ist Vorlage“), dann Serienanlage.
          Name = „Basis Farbe“ — z. B. Vorlage „Kerzen klein - Altrosa“ → Basis „Kerzen klein -“.
          Bestand startet bei 0. Schon vorhandene Namen sind nicht wählbar.
        {/if}
      </p>
      {#if bulkMaterialModal.fromQueue?.shopifyValues?.length}
        <p class="empty" style="margin-top:0">
          Shopify-Farben: {bulkMaterialModal.fromQueue.shopifyValues.join(', ')}
          {#if bulkMaterialModal.mediumId}
            · gematcht: {matchQueueColorIds(bulkMaterialModal.mediumId, bulkMaterialModal.fromQueue.shopifyValues).length}
          {/if}
        </p>
      {/if}
      <div class="form-grid">
        <label>Basisname
          <input
            bind:value={bulkForm.base_name}
            placeholder="z. B. Kerzen klein -"
            required
            oninput={() => {
              bulkForm.colorIds = colorIdsForBulk({
                mediumId: bulkMaterialModal.mediumId,
                base: bulkForm.base_name,
                kind: 'material',
                fromQueue: bulkMaterialModal.fromQueue,
              })
            }}
          />
        </label>
        <label>Medium{bulkMaterialModal.fromQueue ? ' (Pflicht für Match)' : '-Filter'}
          <select
            value={bulkMaterialModal.mediumId ?? ''}
            onchange={(e) => {
              const mid = e.currentTarget.value ? Number(e.currentTarget.value) : null
              openBulkMaterials(mid, {
                keepTemplate: true,
                baseName: bulkForm.base_name,
                fromQueue: bulkMaterialModal.fromQueue || null,
              })
            }}
          >
            {#if bulkMaterialModal.fromQueue}
              <option value="">Medium wählen…</option>
            {:else}
              <option value="">alle Medien</option>
            {/if}
            {#each media as m}<option value={m.id}>{m.name}</option>{/each}
          </select>
        </label>
        <label>Vorlage
          <FamilySelect
            bind:value={bulkForm.template_material_id}
            items={materialsForSeriesTemplate}
            emptyLabel="keine"
            formatItem={(m) => `Vorlage: ${m.name}`}
            onchange={() => onBulkMaterialTemplateChange()}
          />
        </label>
        <label>Einheit
          <select bind:value={bulkForm.unit}>{#each units as u}<option value={u.value}>{u.label}</option>{/each}</select>
        </label>
        <label>Einkaufsmenge
          <input type="number" step="0.001" min="0.001" bind:value={bulkForm.purchase_quantity} />
        </label>
        <label>Einkaufspreis (€)
          <input type="number" step="0.01" bind:value={bulkForm.purchase_price} />
        </label>
        <label>Mindestbestand (optional)
          <input type="number" step={qtyStep(bulkForm.decimal_places)} min="0" bind:value={bulkForm.min_stock} placeholder="leer = Vorlage / keiner" />
        </label>
        {#if !hasMaterialTemplates}
          <p class="empty" style="grid-column:1/-1;margin:0">
            Noch keine Vorlage — Material bearbeiten und „Ist Vorlage“ setzen.
          </p>
        {/if}
      </div>
      <fieldset class="tag-picker" style="margin-top:.75rem">
        <legend>Farben</legend>
        {#if bulkMaterialModal.fromQueue && !bulkMaterialModal.mediumId}
          <p class="empty">Zuerst Medium wählen.</p>
        {:else}
          {#each (bulkMaterialModal.mediumId ? colorsForMedium(bulkMaterialModal.mediumId) : colors) as c}
            {@const taken = isBulkMaterialColorTaken(bulkForm.base_name, c)}
            <label class="tag-check" class:empty={taken}>
              <input
                type="checkbox"
                disabled={taken}
                checked={!taken && bulkForm.colorIds.includes(c.id)}
                onchange={() => toggleBulkColorId(c.id)}
              />
              {c.label}{taken ? ' (schon Material)' : ''}
            </label>
          {:else}
            <p class="empty">Keine Farben.</p>
          {/each}
        {/if}
      </fieldset>
      <div class="modal-actions">
        <button type="button" class="btn secondary" onclick={() => (bulkMaterialModal = null)}>Abbrechen</button>
        <button
          type="button"
          class="btn"
          disabled={saving || !bulkForm.colorIds.length || !bulkForm.base_name.trim() || (bulkMaterialModal.fromQueue && !bulkMaterialModal.mediumId)}
          onclick={submitBulkMaterials}
        >
          {bulkForm.colorIds.length} anlegen
        </button>
      </div>
    </div>
  </div>
{/if}

{#if bulkProductModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (bulkProductModal = null)}>
    <div class="modal" role="dialog" aria-modal="true">
      <h3>Produkte aus Farben{#if bulkProductModal.fromQueue?.onDemand} (On-Demand){/if}</h3>
      <p class="empty" style="margin-top:0">
        {#if bulkProductModal.fromQueue}
          Aus Import-Warteschlange: zuerst <strong>Medium</strong> wählen (Shopify-Farben → Katalog), Vorlage optional.
        {:else}
          Zuerst optional eine Vorlage anlegen (Stückliste/Tags, „Ist Vorlage“), dann Serienanlage.
          Name = „Basis Farbe“. Farbige Stücklisten-Materialien werden umgebogen.
        {/if}
      </p>
      {#if bulkProductModal.fromQueue?.shopifyValues?.length}
        <p class="empty" style="margin-top:0">
          Shopify-Farben: {bulkProductModal.fromQueue.shopifyValues.join(', ')}
          {#if bulkProductModal.mediumId}
            · gematcht: {matchQueueColorIds(bulkProductModal.mediumId, bulkProductModal.fromQueue.shopifyValues).length}
          {/if}
        </p>
      {/if}
      <div class="form-grid">
        <label>Basisname
          <input
            bind:value={bulkForm.base_name}
            placeholder="z. B. Ring"
            required
            oninput={() => {
              bulkForm.colorIds = colorIdsForBulk({
                mediumId: bulkProductModal.mediumId,
                base: bulkForm.base_name,
                kind: 'product',
                fromQueue: bulkProductModal.fromQueue,
              })
            }}
          />
        </label>
        <label>Medium{bulkProductModal.fromQueue ? ' (Pflicht für Match)' : '-Filter'}
          <select
            value={bulkProductModal.mediumId ?? ''}
            onchange={(e) => {
              const mid = e.currentTarget.value ? Number(e.currentTarget.value) : null
              openBulkProducts({
                mediumId: mid,
                baseName: bulkForm.base_name,
                templateProductId: bulkForm.template_product_id,
                minStock: bulkForm.min_stock,
                fromQueue: bulkProductModal.fromQueue || null,
              })
            }}
          >
            {#if bulkProductModal.fromQueue}
              <option value="">Medium wählen…</option>
            {:else}
              <option value="">alle Medien</option>
            {/if}
            {#each media as m}<option value={m.id}>{m.name}</option>{/each}
          </select>
        </label>
        <label>Stücklisten-Vorlage
          <FamilySelect
            bind:value={bulkForm.template_product_id}
            items={productsForBomTemplate}
            emptyLabel="keine"
            formatItem={(p) => p.is_template ? `Vorlage: ${p.name}` : p.name}
            onchange={() => onBulkTemplateChange()}
          />
        </label>
        <label>Mindestbestand (optional)
          <input type="number" step={qtyStep(0)} min="0" bind:value={bulkForm.min_stock} placeholder="leer = keiner" />
        </label>
        {#if !hasProductTemplates}
          <p class="empty" style="grid-column:1/-1;margin:0">
            Noch keine Vorlage — Produkt anlegen und „Ist Vorlage“ setzen.
          </p>
        {/if}
      </div>
      <fieldset class="tag-picker" style="margin-top:.75rem">
        <legend>Farben</legend>
        {#if bulkProductModal.fromQueue && !bulkProductModal.mediumId}
          <p class="empty">Zuerst Medium wählen.</p>
        {:else}
          {#each (bulkProductModal.mediumId ? colorsForMedium(bulkProductModal.mediumId) : colors) as c}
            {@const taken = isBulkProductColorTaken(bulkForm.base_name, c)}
            <label class="tag-check" class:empty={taken}>
              <input
                type="checkbox"
                disabled={taken}
                checked={!taken && bulkForm.colorIds.includes(c.id)}
                onchange={() => toggleBulkColorId(c.id)}
              />
              {c.label}{taken ? ' (schon Produkt)' : ''}
            </label>
          {:else}
            <p class="empty">Keine Farben.</p>
          {/each}
        {/if}
      </fieldset>
      <div class="modal-actions">
        <button type="button" class="btn secondary" onclick={() => (bulkProductModal = null)}>Abbrechen</button>
        <button
          type="button"
          class="btn"
          disabled={saving || !bulkForm.colorIds.length || !bulkForm.base_name.trim() || (bulkProductModal.fromQueue && !bulkProductModal.mediumId)}
          onclick={submitBulkProducts}
        >
          {bulkForm.colorIds.length} anlegen
        </button>
      </div>
    </div>
  </div>
{/if}

{#if sellingPriceConflicts?.length}
  <div class="modal-backdrop" role="presentation">
    <div class="modal" role="dialog" aria-modal="true">
      <h3>Verkaufspreise weichen ab</h3>
      {#if sellingPriceStage === 'ask'}
        <p class="empty" style="margin-top:0">
          {sellingPriceConflicts.length} Produkt(e) haben schon einen Preis, der vom CSV abweicht.
        </p>
        <div class="modal-actions">
          <button type="button" class="btn" disabled={saving} onclick={() => resolveSellingPriceConflicts('csv')}>alle CSV</button>
          <button type="button" class="btn secondary" disabled={saving} onclick={() => resolveSellingPriceConflicts('keep')}>alle behalten</button>
          <button type="button" class="btn secondary" onclick={() => (sellingPriceStage = 'list')}>einzeln</button>
        </div>
      {:else}
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>Produkt</th><th>Bisher</th><th>CSV</th><th></th></tr>
            </thead>
            <tbody>
              {#each sellingPriceConflicts as row}
                <tr>
                  <td>{row.name}</td>
                  <td class="num">{formatMoney(row.current)}</td>
                  <td class="num">{formatMoney(row.csv)}</td>
                  <td>
                    <label><input type="radio" name={`price-${row.product_id}`} checked={sellingPricePicks[row.product_id] === 'csv'} onchange={() => (sellingPricePicks = { ...sellingPricePicks, [row.product_id]: 'csv' })} /> CSV</label>
                    <label><input type="radio" name={`price-${row.product_id}`} checked={sellingPricePicks[row.product_id] === 'keep'} onchange={() => (sellingPricePicks = { ...sellingPricePicks, [row.product_id]: 'keep' })} /> behalten</label>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn secondary" onclick={() => (sellingPriceStage = 'ask')}>Zurück</button>
          <button type="button" class="btn" disabled={saving} onclick={() => resolveSellingPriceConflicts('mixed', sellingPricePicks)}>Übernehmen</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

{#if bulkEditModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (bulkEditModal = null)}>
    <div class="modal modal-bulk" role="dialog" aria-modal="true">
      <h3>{bulkEditModal.kind === 'material' ? 'Materialien' : 'Produkte'} mehrfach bearbeiten</h3>
      <p class="empty" style="margin-top:0">
        {bulkEditModal.kind === 'material' ? selectedMaterialIds.length : selectedProductIds.length} ausgewählt —
        {bulkEditForm.deleteSelected ? 'Löschmodus aktiv.' : 'leere Felder bleiben unverändert.'}
      </p>
      <form class="bulk-edit-form" onsubmit={(e) => { e.preventDefault(); submitBulkEdit() }}>
        <section class="bulk-block bulk-block-danger">
          <div class="bulk-block-head">
            <label class="bulk-block-toggle">
              <input type="checkbox" bind:checked={bulkEditForm.deleteSelected} />
              <span>
                <strong>Ausgewählte löschen</strong>
                <small>Unwiderruflich — andere Aktionen unten sind dann deaktiviert</small>
              </span>
            </label>
          </div>
        </section>

        <fieldset class="bulk-edit-fields" disabled={bulkEditForm.deleteSelected}>
          <section class="bulk-block">
            <h4 class="bulk-block-title">Mindestbestand</h4>
            <div class="bulk-block-body">
              <label class="bulk-field">Wert setzen
                <input
                  type="number"
                  step={bulkEditModal.kind === 'product' ? qtyStep(0) : 'any'}
                  min="0"
                  bind:value={bulkEditForm.min_stock}
                  placeholder="leer = nicht ändern"
                  disabled={bulkEditForm.clear_min_stock}
                />
              </label>
              <label class="bulk-inline-check">
                <input type="checkbox" bind:checked={bulkEditForm.clear_min_stock} />
                Stattdessen leeren
              </label>
            </div>
          </section>

          {#if bulkEditModal.kind === 'product'}
            <section class="bulk-block">
              <h4 class="bulk-block-title">Verkaufspreis</h4>
              <div class="bulk-block-body">
                <label class="bulk-field">Wert setzen (€)
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    bind:value={bulkEditForm.selling_price}
                    placeholder="leer = nicht ändern"
                  />
                </label>
              </div>
            </section>
          {/if}

          <section class="bulk-block">
            <h4 class="bulk-block-title">{bulkEditModal.kind === 'material' ? 'Materialfamilie' : 'Produktfamilie'}</h4>
            <div class="bulk-block-body">
              <label class="bulk-field">Name setzen
                <input
                  bind:value={bulkEditForm.family}
                  placeholder="leer = nicht ändern"
                  disabled={bulkEditForm.clear_family}
                />
              </label>
              <label class="bulk-inline-check">
                <input type="checkbox" bind:checked={bulkEditForm.clear_family} />
                Stattdessen leeren
              </label>
            </div>
          </section>

          {#if bulkEditModal.kind === 'product' || bulkEditModal.kind === 'material'}
            <section class="bulk-block">
              <h4 class="bulk-block-title">Ist Vorlage</h4>
              <div class="bulk-block-body">
                <label class="bulk-field">Status
                  <select bind:value={bulkEditForm.is_template}>
                    <option value="">nicht ändern</option>
                    <option value="yes">ja</option>
                    <option value="no">nein</option>
                  </select>
                </label>
              </div>
            </section>
          {/if}

          <section class="bulk-block">
            <div class="bulk-block-head">
              <label class="bulk-block-toggle">
                <input type="checkbox" bind:checked={bulkEditForm.setStock} />
                <span>
                  <strong>Bestand setzen</strong>
                  <small>Absolutwert an einem Standort (mit Warnung)</small>
                </span>
              </label>
            </div>
            {#if bulkEditForm.setStock}
              <div class="bulk-block-body bulk-block-nested">
                <label class="bulk-field">Standort
                  <select bind:value={bulkEditForm.stock_location_id} required>
                    <option value="">wählen…</option>
                    {#each (bulkEditModal.kind === 'material' ? materialLocations : orderedLocations) as loc}
                      <option value={loc.id}>{loc.name}</option>
                    {/each}
                  </select>
                </label>
                <label class="bulk-field">Bestand (Absolut)
                  <input type="number" step="0.001" bind:value={bulkEditForm.stock_quantity} placeholder="z. B. 10" />
                </label>
              </div>
            {/if}
          </section>

          {#if bulkEditModal.kind === 'product'}
            <section class="bulk-block">
              <div class="bulk-block-head">
                <label class="bulk-block-toggle">
                  <input type="checkbox" bind:checked={bulkEditForm.setBom} />
                  <span>
                    <strong>Stücklistenzeile</strong>
                    <small>Hinzufügen/Ändern oder Entfernen (mit Warnung)</small>
                  </span>
                </label>
              </div>
              {#if bulkEditForm.setBom}
                <div class="bulk-block-body bulk-block-nested">
                  <label class="bulk-field">Aktion
                    <select bind:value={bulkEditForm.bom_mode}>
                      <option value="upsert">Hinzufügen oder Menge ändern</option>
                      <option value="remove">Zeile entfernen</option>
                    </select>
                  </label>
                  <label class="bulk-field">Komponente
                    <select bind:value={bulkEditForm.bom_kind}>
                      <option value="material">Material</option>
                      <option value="product">Produkt</option>
                    </select>
                  </label>
                  {#if bulkEditForm.bom_kind === 'product'}
                    <label class="bulk-field">Produkt
                      <FamilySelect bind:value={bulkEditForm.bom_product_id} items={products} emptyLabel="wählen…" />
                    </label>
                  {:else}
                    <label class="bulk-field">Material
                      <FamilySelect
                        bind:value={bulkEditForm.bom_material_id}
                        items={materials}
                        emptyLabel="wählen…"
                        formatItem={(m) => `${m.name} (${m.unit})`}
                      />
                    </label>
                  {/if}
                  {#if bulkEditForm.bom_mode !== 'remove'}
                    <label class="bulk-field">Menge pro Produkteinheit
                      <input type="number" step="0.001" min="0.001" bind:value={bulkEditForm.bom_quantity} />
                    </label>
                  {/if}
                </div>
              {/if}
            </section>
          {/if}

          <section class="bulk-block">
            <div class="bulk-block-head">
              <label class="bulk-block-toggle">
                <input type="checkbox" bind:checked={bulkEditForm.setTags} />
                <span>
                  <strong>Tags ersetzen</strong>
                  <small>Gesamte Tag-Liste der Auswahl überschreiben</small>
                </span>
              </label>
            </div>
            {#if bulkEditForm.setTags}
              <div class="bulk-block-body bulk-block-nested">
                <fieldset class="tag-picker">
                  <legend>Tags wählen</legend>
                  {#each allTags as t}
                    <label class="tag-check">
                      <input
                        type="checkbox"
                        checked={bulkEditForm.tagIds.includes(t.id)}
                        onchange={() => toggleTagId(bulkEditForm, t.id)}
                      />
                      {t.name}
                    </label>
                  {:else}
                    <p class="empty">Keine Tags im Katalog — unter „Kataloge“ anlegen.</p>
                  {/each}
                </fieldset>
              </div>
            {/if}
          </section>
        </fieldset>

        <div class="modal-actions">
          <button type="button" class="btn secondary" onclick={() => (bulkEditModal = null)}>Abbrechen</button>
          {#if bulkEditForm.deleteSelected}
            <button type="submit" class="btn danger" disabled={saving}>Löschen</button>
          {:else}
            <button type="submit" class="btn" disabled={saving}>Speichern</button>
          {/if}
        </div>
      </form>
    </div>
  </div>
{/if}

{#if articleChoiceTodo}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (articleChoiceTodo = null)}>
    <div class="modal" role="dialog" aria-modal="true">
      <h3>Artikel anlegen</h3>
      <p class="empty" style="margin-top:0">
        Bestellzeile „{todoLabelForCreate(articleChoiceTodo)}“ — Produkt oder Material? Bei Bestellungen ist Produkt der Normalfall.
      </p>
      <div class="modal-actions">
        <button type="button" class="btn secondary" onclick={() => (articleChoiceTodo = null)}>Abbrechen</button>
        <button type="button" class="btn secondary" onclick={() => chooseArticleKind('material')}>Material</button>
        <button type="button" class="btn" onclick={() => chooseArticleKind('product')}>Produkt</button>
      </div>
    </div>
  </div>
{/if}

{#if queueAxisModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (queueAxisModal = null)}>
    <div class="modal" role="dialog" aria-modal="true">
      <h3>Farb-Option wählen</h3>
      <p class="empty" style="margin-top:0">
        Mehrere Shopify-Optionen — welche Achse sind die Variantenfarben? Die übrigen fließen in den Basisnamen.
      </p>
      <p><strong>{queueAxisModal.item.title}</strong></p>
      <label>Diese Option ist die Farbe
        <select bind:value={queueAxisModal.colorAxis}>
          {#each queueAxisModal.axes as axis}
            <option value={axis}>{axis} ({(queueAxisModal.item.option_values?.[axis] || []).length} Werte)</option>
          {/each}
        </select>
      </label>
      <div class="modal-actions">
        <button type="button" class="btn secondary" onclick={() => (queueAxisModal = null)}>Abbrechen</button>
        <button
          type="button"
          class="btn"
          onclick={() => openSeriesFromQueue(queueAxisModal.item, queueAxisModal.colorAxis)}
        >
          Weiter zur Serienanlage
        </button>
      </div>
    </div>
  </div>
{/if}

{#if shopifyAssistant}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (shopifyAssistant = null)}>
    <div class="modal modal-bulk modal-assistant" role="dialog" aria-modal="true">
      <h3>Shopify-CSV Assistent</h3>
      <p class="empty" style="margin-top:0">
        Pro Artikel wählen: Set (Zusammenstellung), Serie, On-Demand oder ignorieren.
        Nichts wird still angelegt — erst „Übernehmen“.
      </p>
      <label class="bulk-inline-check" style="margin-bottom:.75rem">
        <input type="checkbox" bind:checked={shopifyAssistant.showIgnored} />
        Ignorierte Handles in der Liste zeigen
      </label>
      <div class="table-wrap" style="max-height:50vh;overflow:auto">
        <table>
          <thead>
            <tr>
              <th>Shopify-Artikel</th>
              <th>Varianten</th>
              <th>Optionen</th>
              <th>Aktion</th>
            </tr>
          </thead>
          <tbody>
            {#each shopifyAssistantRows() as h}
              <tr>
                <td>
                  <strong>{h.title}</strong>
                  <div class="empty">{h.handle}</div>
                  {#if h.existing_set_id}<span class="empty">bereits als Set</span>{/if}
                  {#if h.ignored}<span class="empty">ignoriert</span>{/if}
                </td>
                <td>{h.variant_count}</td>
                <td class="empty">{(h.option_axes || []).join(' · ') || '—'}</td>
                <td>
                  <select
                    value={shopifyAssistant.actions[h.handle] || 'skip'}
                    onchange={(e) => {
                      shopifyAssistant.actions = {
                        ...shopifyAssistant.actions,
                        [h.handle]: e.currentTarget.value,
                      }
                    }}
                  >
                    <option value="skip">überspringen</option>
                    <option value="set">Set</option>
                    <option value="series_product">Serie Produkt</option>
                    <option value="series_material">Serie Material</option>
                    <option value="on_demand">On-Demand</option>
                    <option value="ignore">ignorieren</option>
                  </select>
                </td>
              </tr>
            {:else}
              <tr><td colspan="4" class="empty">Keine Einträge (Filter?). Ignorierte einblenden oder andere CSV.</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn secondary" onclick={() => (shopifyAssistant = null)}>Abbrechen</button>
        <button type="button" class="btn" disabled={saving} onclick={submitShopifyAssistant}>Übernehmen</button>
      </div>
    </div>
  </div>
{/if}

{#if ignoredHandlesModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (ignoredHandlesModal = false)}>
    <div class="modal" role="dialog" aria-modal="true">
      <h3>Ignorieren-Liste</h3>
      <p class="empty" style="margin-top:0">Dauerhaft ausgeblendet im Assistenten, bis wiederhergestellt.</p>
      <ul style="margin:0;padding-left:1.1rem;max-height:50vh;overflow:auto">
        {#each ignoredHandles as h}
          <li style="margin:.4rem 0;display:flex;gap:.5rem;align-items:center;justify-content:space-between">
            <span>{h.title || h.handle} <span class="empty">({h.handle})</span></span>
            <button type="button" class="btn secondary" onclick={() => restoreIgnoredHandle(h.handle)}>Wiederherstellen</button>
          </li>
        {:else}
          <li class="empty">Keine ignorierten Handles.</li>
        {/each}
      </ul>
      <div class="modal-actions">
        <button type="button" class="btn secondary" onclick={() => (ignoredHandlesModal = false)}>Schließen</button>
      </div>
    </div>
  </div>
{/if}

{#if setCleanupModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (setCleanupModal = false)}>
    <div class="modal modal-bulk" role="dialog" aria-modal="true">
      <h3>Sets aufräumen</h3>
      <p class="empty" style="margin-top:0">
        Falsch importierte Varianten-Artikel entfernen. Geburtstagssets behalten — Häkchen bei Löschen-Kandidaten.
      </p>
      <div style="margin-bottom:.5rem;display:flex;gap:.5rem">
        <button type="button" class="btn secondary" onclick={() => (setCleanupIds = sets.map((s) => s.id))}>Alle</button>
        <button type="button" class="btn secondary" onclick={() => (setCleanupIds = [])}>Keine</button>
      </div>
      <fieldset class="tag-picker" style="max-height:45vh;overflow:auto">
        {#each sets as s}
          <label class="tag-check">
            <input
              type="checkbox"
              checked={setCleanupIds.includes(s.id)}
              onchange={() => toggleSetCleanupId(s.id)}
            />
            {s.name}
            <span class="empty">({s.variant_count} Var.)</span>
          </label>
        {/each}
      </fieldset>
      <div class="modal-actions">
        <button type="button" class="btn secondary" onclick={() => (setCleanupModal = false)}>Abbrechen</button>
        <button type="button" class="btn danger" disabled={saving || !setCleanupIds.length} onclick={submitSetCleanup}>
          {setCleanupIds.length} löschen
        </button>
      </div>
    </div>
  </div>
{/if}
