<script>
  import { onMount } from 'svelte'
  import { api, formatMoney, formatQty, formatUnitCost, formatDateTime, formatActor } from './lib/api.js'
  import { filterRows, sortRows, nextSortState, sortMark, prepareRows } from './lib/tableUtils.js'
  import { productFamilyKey, collectProductFamilies, groupProductsByFamily } from './lib/productFamily.js'
  import {
    matchColorsForShopifyValue as matchColorsPool,
    resolveSetComponents as resolveSetComponentsLib,
    templateSeriesPrefix,
  } from './lib/setOptionMatch.js'
  import FamilyFilter from './lib/components/FamilyFilter.svelte'
  import ProductGroupSection from './lib/components/ProductGroupSection.svelte'
  import BackupPanel from './lib/components/BackupPanel.svelte'

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
  let filterTag = $state('')
  let filterColorId = $state('')
  let filterFamily = $state('')
  let filterMaterialFamily = $state('')
  let overviewProductsOpen = $state(true)
  let overviewMaterialsOpen = $state(true)
  let overviewIgnoredOpen = $state(false)
  let colorSuggestions = $state([])
  let loading = $state(true)
  let flash = $state(null)
  let saveButtonOk = $state(false)
  let flashClearTimer = null
  let saveOkTimer = null
  let saving = $state(false)

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
  let transferModal = $state(null)
  let transformModal = $state(null)
  let movementsModal = $state(null) // { title, rows }
  let setModal = $state(null)
  let setStep = $state(1) // 1 Überblick, 2 Zuordnen, 3 Baubarkeit
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
  let bulkMaterialModal = $state(null) // { mediumId }
  let bulkProductModal = $state(null) // { mediumId?, baseName, templateProductId }
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

  let materialForm = $state(emptyMaterial())
  let productForm = $state(emptyProduct())
  let bomForm = $state({ kind: 'material', material_id: '', product_id: '', quantity_required: '' })
  let manufactureForm = $state({ quantity: '1', location_id: '' })
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

  function emptyBulkEditForm() {
    return {
      deleteSelected: false,
      min_stock: '',
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
      bom_material_id: '',
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
    collapsedFamilies = { ...collapsedFamilies, [key]: !collapsedFamilies[key] }
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

  function openBulkMaterials(mediumId = null, { keepTemplate = false, baseName = null } = {}) {
    const mid = mediumId != null ? Number(mediumId) : media[0]?.id || null
    const prevTemplate = keepTemplate ? bulkForm.template_material_id : ''
    const base =
      baseName != null
        ? baseName
        : keepTemplate
          ? bulkForm.base_name
          : ''
    const pool = mid ? colorsForMedium(mid) : colors
    const available = pool.filter((c) => !isBulkMaterialColorTaken(base, c)).map((c) => c.id)
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
    bulkMaterialModal = { mediumId: mid }
  }

  function materialTemplateById(templateMaterialId) {
    if (!templateMaterialId) return null
    return materials.find((m) => m.id === Number(templateMaterialId)) || null
  }

  /** Mindestbestand der Vorlage als Vorbelegung für die Serienanlage. */
  function templateMinStock(templateProductId) {
    if (!templateProductId) return ''
    const template = products.find((p) => p.id === Number(templateProductId))
    return template?.min_stock != null ? String(template.min_stock) : ''
  }

  function materialTemplateMinStock(templateMaterialId) {
    const template = materialTemplateById(templateMaterialId)
    return template?.min_stock != null ? String(template.min_stock) : ''
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
    if (bulkForm.min_stock === '') {
      bulkForm.min_stock = materialTemplateMinStock(bulkForm.template_material_id)
    }
    const pool = bulkMaterialModal?.mediumId
      ? colorsForMedium(bulkMaterialModal.mediumId)
      : colors
    bulkForm.colorIds = pool.filter((c) => !isBulkMaterialColorTaken(base, c)).map((c) => c.id)
  }

  function openBulkProducts({ mediumId = null, baseName = '', templateProductId = '', minStock = null } = {}) {
    const mid = mediumId != null ? Number(mediumId) : null
    const base = baseName || ''
    const pool = mid ? colorsForMedium(mid) : colors
    const available = pool.filter((c) => !isBulkProductColorTaken(base, c)).map((c) => c.id)
    bulkForm = {
      ...bulkForm,
      colorIds: available,
      base_name: base,
      template_product_id: templateProductId ? String(templateProductId) : '',
      min_stock: minStock != null ? minStock : templateMinStock(templateProductId),
      location_id: String(locations.find((x) => x.name === 'Hamburg')?.id || locations[0]?.id || ''),
    }
    bulkProductModal = { mediumId: mid }
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
      })
      bulkProductModal = null
      await refresh()
      const msg = `${result.created.length} Produkt(e) angelegt` +
        (result.skipped.length ? `, ${result.skipped.length} übersprungen` : '')
      showFlash('ok', msg)
      if (result.warnings?.length) {
        showFlash('error', result.warnings.slice(0, 3).join(' · '))
      }
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
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
      showFlash('ok', ignored ? 'Aus Übersicht ausgeblendet.' : 'Wieder in Übersicht.')
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
      const mid = Number(bulkEditForm.bom_material_id)
      const qty = bulkEditForm.bom_quantity
      if (!mid || !qty || Number(qty) <= 0) {
        showFlash('error', 'Für Stückliste Material und Menge angeben.')
        return
      }
      if (
        !confirm(
          `WARNUNG: Stücklistenzeile (Material ${mid}, Menge ${qty}) bei ${ids.length} Produkten hinzufügen oder ändern?\nAndere Zeilen bleiben erhalten.`,
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
      if (kind === 'product' && bulkEditForm.setBom) {
        const materialId = Number(bulkEditForm.bom_material_id)
        const quantity_required = String(bulkEditForm.bom_quantity)
        for (const id of ids) {
          const product = products.find((p) => p.id === id)
          const existing = (product?.bom || []).find((line) => line.material_id === materialId)
          if (existing) {
            await api.products.updateBom(id, existing.id, { quantity_required })
          } else {
            await api.products.addBom(id, { material_id: materialId, quantity_required })
          }
        }
      }
      if (kind === 'material') selectedMaterialIds = []
      else selectedProductIds = []
      bulkEditModal = null
      await refresh()
      showFlash('ok', `${ids.length} Eintrag/Einträge aktualisiert.`)
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

  async function refresh({ silent = false } = {}) {
    if (!authUser) return
    if (!silent) loading = true
    try {
      if (authUser.role === 'mitarbeiter') {
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
        return
      }
      const filter = {
        tag: filterTag || undefined,
        color_id: filterColorId || undefined,
      }
      const [m, p, u, l, s, med, c, t] = await Promise.all([
        api.materials.list(filter),
        api.products.list(filter),
        api.units(),
        api.locations(),
        api.sets.list(),
        api.media.list(),
        api.colors.list(),
        api.tags.list(),
      ])
      materials = m
      products = p
      units = u
      locations = l
      sets = s
      media = med
      colors = c
      allTags = t
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
      if (!materialForm.location_id && l[0]) materialForm.location_id = String(l.find((x) => x.name === 'Hamburg')?.id || l[0].id)
      if (!productForm.location_id && l[0]) productForm.location_id = String(l.find((x) => x.name === 'Hamburg')?.id || l[0].id)
      if (tab === 'users') await loadUsers()
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
      formatQty(item.stock_total),
      item.is_negative ? 'negativ' : '',
      ...locs.map((loc) => `${loc.name} ${formatQty(stockAt(item, loc.id))}`),
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
        const stock = line.stock_total != null ? ` Lager ${formatQty(line.stock_total)}` : ''
        return `${line.component_name} ${formatQty(line.quantity_required)}${stock}`
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
    const familyFiltered = filterMaterialFamily
      ? criticalMaterials.filter((m) => productFamilyKey(m) === filterMaterialFamily)
      : criticalMaterials
    return prepareRows(
      familyFiltered,
      listUi.overviewMaterials,
      (m) => stockRowSearchText(m, materialLocations),
      stockSortGetter(listUi.overviewMaterials.sortKey),
    )
  })
  const overviewMaterialGroups = $derived(groupProductsByFamily(displayedOverviewMaterials))
  const familyFilteredOverviewProducts = $derived(
    filterFamily
      ? criticalProducts.filter((p) => productFamilyKey(p) === filterFamily)
      : criticalProducts,
  )
  const displayedOverviewProducts = $derived(
    prepareRows(
      familyFilteredOverviewProducts,
      listUi.overviewProducts,
      (p) => stockRowSearchText(p, orderedLocations),
      stockSortGetter(listUi.overviewProducts.sortKey),
    ),
  )
  const overviewProductGroups = $derived(groupProductsByFamily(displayedOverviewProducts))
  const displayedMaterials = $derived.by(() => {
    const familyFiltered = filterMaterialFamily
      ? materials.filter((m) => productFamilyKey(m) === filterMaterialFamily)
      : materials
    return prepareRows(
      familyFiltered,
      listUi.materials,
      (m) => stockRowSearchText(m, materialLocations),
      stockSortGetter(listUi.materials.sortKey),
    )
  })
  const materialFamilies = $derived(collectProductFamilies(materials))
  const materialGroups = $derived(groupProductsByFamily(displayedMaterials))
  const familyFilteredProducts = $derived(
    filterFamily ? products.filter((p) => productFamilyKey(p) === filterFamily) : products,
  )
  const displayedProducts = $derived(
    prepareRows(
      familyFilteredProducts,
      listUi.products,
      (p) => stockRowSearchText(p, orderedLocations),
      stockSortGetter(listUi.products.sortKey),
    ),
  )
  /** Vorhandene Produktfamilien für den Filter (ohne Leerwerte). */
  const productFamilies = $derived(collectProductFamilies(products))
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
    return formatQty(item.min_stock)
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

  function openCreateMaterial(template = null) {
    materialForm = emptyMaterial()
    materialForm.location_id = String(locations.find((x) => x.name === 'Hamburg')?.id || locations[0]?.id || '')
    showMaterialTags = false
    if (template) {
      const mid = mediumIdFromColor(template.color_id)
      materialForm = {
        ...materialForm,
        name: `${template.name} (Kopie)`,
        unit: template.unit,
        purchase_quantity: String(template.purchase_quantity ?? 1),
        purchase_price: String(template.purchase_price ?? template.cost_per_unit ?? 0),
        min_stock: template.min_stock != null ? String(template.min_stock) : '',
        family: template.family || '',
        stock_quantity: '0',
        medium_id: mid,
        color_id: template.color_id ? String(template.color_id) : '',
        tagIds: (template.tags || []).map((t) => t.id),
      }
      showMaterialTags = materialForm.tagIds.length > 0
    }
    materialModal = { mode: 'create' }
  }

  function openEditMaterial(material) {
    const mid = mediumIdFromColor(material.color_id) || (material.color?.medium_id ? String(material.color.medium_id) : '')
    materialForm = {
      name: material.name,
      unit: material.unit,
      stock_quantity: '0',
      purchase_quantity: String(material.purchase_quantity ?? 1),
      purchase_price: String(material.purchase_price ?? material.cost_per_unit ?? 0),
      min_stock: material.min_stock != null ? String(material.min_stock) : '',
      is_template: !!material.is_template,
      family: material.family || '',
      location_id: '',
      medium_id: mid,
      color_id: material.color_id ? String(material.color_id) : '',
      tagIds: (material.tags || []).map((t) => t.id),
    }
    showMaterialTags = materialForm.tagIds.length > 0
    initStockDrafts(material)
    materialModal = { mode: 'edit', id: material.id, material }
  }

  function openCreateProduct(template = null) {
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
        stock_quantity: '0',
        min_stock: template.min_stock != null ? String(template.min_stock) : '',
        family: template.family || '',
        medium_id: mid,
        color_id: template.color_id ? String(template.color_id) : '',
        tagIds: (template.tags || []).map((t) => t.id),
      }
      showProductTags = productForm.tagIds.length > 0
    }
    productModal = { mode: 'create', product: null, templateBom: template?.bom ? [...template.bom] : [] }
  }

  function openEditProduct(product) {
    const mid = mediumIdFromColor(product.color_id) || (product.color?.medium_id ? String(product.color.medium_id) : '')
    productForm = {
      name: product.name,
      sku: product.sku || '',
      stock_quantity: '0',
      min_stock: product.min_stock != null ? String(product.min_stock) : '',
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

  function openManufacture(product) {
    manufactureForm = {
      quantity: '1',
      location_id: String(locations.find((x) => x.name === 'Hamburg')?.id || locations[0]?.id || ''),
    }
    manufactureModal = product
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

  async function saveMaterial() {
    saving = true
    try {
      const colorPayload = {
        color_id: materialForm.color_id ? Number(materialForm.color_id) : null,
        tag_ids: materialForm.tagIds,
      }
      if (materialModal.mode === 'create') {
        await api.materials.create({
          name: materialForm.name.trim(),
          unit: materialForm.unit,
          purchase_quantity: materialForm.purchase_quantity,
          purchase_price: materialForm.purchase_price,
          min_stock: parseOptionalQty(materialForm.min_stock),
          family: materialForm.family.trim() || null,
          stock_quantity: materialForm.stock_quantity,
          location_id: Number(materialForm.location_id),
          ...colorPayload,
        })
        showFlash('ok', 'Material angelegt.')
        markSaved()
      } else {
        await api.materials.update(materialModal.id, {
          name: materialForm.name.trim(),
          unit: materialForm.unit,
          purchase_quantity: materialForm.purchase_quantity,
          purchase_price: materialForm.purchase_price,
          min_stock: parseOptionalQty(materialForm.min_stock),
          is_template: !!materialForm.is_template,
          family: materialForm.family.trim() || null,
          ...colorPayload,
        })
        showFlash('ok', 'Material gespeichert.')
        markSaved()
      }
      materialModal = null
      await refresh()
    } catch (error) {
      showFlash('error', error.message)
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

  async function saveProduct() {
    saving = true
    try {
      const colorPayload = {
        color_id: productForm.color_id ? Number(productForm.color_id) : null,
        transform_target_id: productForm.transform_target_id
          ? Number(productForm.transform_target_id)
          : null,
        tag_ids: productForm.tagIds,
      }
      if (productModal.mode === 'create') {
        const created = await api.products.create({
          name: productForm.name.trim(),
          sku: productForm.sku.trim() || null,
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
      } else {
        await api.products.update(productModal.product.id, {
          name: productForm.name.trim(),
          sku: productForm.sku.trim() || null,
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
        }
      }
    } catch (error) {
      showFlash('error', error.message)
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
      manufactureModal = null
      await refresh()
      showFlash(result.warnings?.length ? 'warn' : 'ok', result.warnings?.join(' ') || 'Fertigung gebucht.')
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
    const mapped = setItem.option_mappings?.length || 0
    const withBom = setItem.variants?.filter((v) => v.bom?.length)?.length || 0
    const buildable = setItem.variants?.filter((v) => v.buildable_quantity > 0)?.length || 0
    if (!setItem.variant_count) return 'Noch keine Varianten'
    if (!mapped) return 'Schritt 2: Farben zuordnen'
    if (!withBom) return 'Schritt 2: Zuordnung anwenden'
    return `${buildable} von ${setItem.variant_count} baubar`
  }

  async function onImportFile(event) {
    const file = event.target.files?.[0]
    if (!file) return
    saving = true
    try {
      const result = await api.sets.importShopify(file)
      await refresh()
      showFlash('ok', result.message)
      if ((result.sets_touched ?? 1) === 1 && result.set_id) {
        const created = sets.find((s) => s.id === result.set_id)
        if (created) await openSet(created, 2)
      }
    } catch (error) {
      showFlash('error', error.message)
    } finally {
      saving = false
      event.target.value = ''
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
  <header class="brand">
    <h1>Holzlinge</h1>
    <p>Inventar, Standorte, Stücklisten und baubare Sets.</p>
    {#if authUser}
      <div class="auth-bar">
        <span class="empty">{authUser.username} ({authUser.role === 'admin' ? 'Admin' : 'Mitarbeiter'})</span>
        <button type="button" class="btn secondary" onclick={() => (passwordModal = true)}>Passwort</button>
        <button type="button" class="btn secondary" onclick={doLogout}>Abmelden</button>
      </div>
    {/if}
  </header>

  {#if flash}
    <div class={`flash ${flash.type}`}>{flash.message}</div>
  {/if}

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
  <nav class="tabs" aria-label="Hauptnavigation">
    {#if authUser.role === 'admin'}
      <button class="tab" class:active={tab === 'overview'} onclick={() => (tab = 'overview')}>Übersicht</button>
      <button class="tab" class:active={tab === 'materials'} onclick={() => (tab = 'materials')}>Materialien</button>
      <button class="tab" class:active={tab === 'products'} onclick={() => (tab = 'products')}>Produkte</button>
      <button class="tab" class:active={tab === 'staff'} onclick={() => (tab = 'staff')}>
        Bei Mitarbeitern{#if staffQueueProducts.length} ({staffQueueProducts.length}){/if}
      </button>
      <button class="tab" class:active={tab === 'catalogs'} onclick={() => (tab = 'catalogs')}>Kataloge</button>
      <button class="tab" class:active={tab === 'sets'} onclick={() => (tab = 'sets')}>Sets</button>
      <button class="tab" class:active={tab === 'users'} onclick={() => { tab = 'users'; loadUsers() }}>Benutzer</button>
    {:else}
      <button class="tab" class:active={tab === 'staff'} onclick={() => (tab = 'staff')}>
        Bei Mitarbeitern{#if staffQueueProducts.length} ({staffQueueProducts.length}){/if}
      </button>
    {/if}
  </nav>

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
    <section class="panel">
      <div class="panel-header">
        <h2>Kritische Bestände</h2>
        <button class="btn secondary" onclick={refresh}>Aktualisieren</button>
      </div>
      {#if negativeMaterials.length || negativeProducts.length}
        <div class="flash warn">
          Negativbestand vorhanden — Details in den Listen prüfen.
        </div>
      {/if}
      <p class="empty">
        Zuerst kritische Produkte, darunter kritische Materialien (Gesamt ≤ 0 oder unter Mindestbestand).
        Einzelne Einträge können dauerhaft ausgeblendet werden.
      </p>

      <button type="button" class="group-toggle overview-section-toggle" onclick={() => (overviewProductsOpen = !overviewProductsOpen)}>
        {overviewProductsOpen ? '▼' : '▶'} Produkte
        <span class="empty">({criticalProducts.length})</span>
      </button>
      {#if overviewProductsOpen}
        <div class="filter-bar form-grid filter-bar-end">
          <FamilyFilter families={productFamilies} bind:value={filterFamily} />
          <label class="list-search">Suche
            <input type="search" placeholder="Name, Standort, Meta…" bind:value={listUi.overviewProducts.q} />
          </label>
        </div>
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
                  <tr class="row-click" onclick={() => openEditProduct(product)}>
                    <td>
                      {product.name}
                      {#if formatMinStock(product)}
                        <div class="min-stock-hint">Min. {formatMinStock(product)}</div>
                      {/if}
                    </td>
                    {#each orderedLocations as loc}
                      <td class="num" class:neg={stockAt(product, loc.id) < 0}>{formatQty(stockAt(product, loc.id))}</td>
                    {/each}
                    <td class="num" class:neg={Number(product.stock_total) <= 0 || product.is_negative}>
                      {formatQty(product.stock_total)}
                    </td>
                    <td onclick={(e) => e.stopPropagation()}>
                      <div class="row-actions">
                        <button class="btn secondary" onclick={() => openEditProduct(product)}>Bearbeiten</button>
                        <button class="btn secondary" disabled={saving} onclick={() => setOverviewIgnored('product', product, true)}>Ignorieren</button>
                      </div>
                    </td>
                  </tr>
                {/snippet}
              </ProductGroupSection>
            </tbody>
          </table>
        </div>
      {/if}

      <button type="button" class="group-toggle overview-section-toggle" onclick={() => (overviewMaterialsOpen = !overviewMaterialsOpen)}>
        {overviewMaterialsOpen ? '▼' : '▶'} Materialien
        <span class="empty">({criticalMaterials.length})</span>
      </button>
      {#if overviewMaterialsOpen}
        <div class="filter-bar form-grid filter-bar-end">
          <FamilyFilter families={materialFamilies} bind:value={filterMaterialFamily} />
          <label class="list-search">Suche
            <input type="search" placeholder="Name, Standort, Meta…" bind:value={listUi.overviewMaterials.q} />
          </label>
        </div>
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
                  <tr class="row-click" onclick={() => openEditMaterial(material)}>
                    <td>
                      {material.name}
                      {#if formatMinStock(material)}
                        <div class="min-stock-hint">Min. {formatMinStock(material)} {material.unit}</div>
                      {/if}
                    </td>
                    {#each materialLocations as loc}
                      <td class="num" class:neg={stockAt(material, loc.id) < 0}>{formatQty(stockAt(material, loc.id))}</td>
                    {/each}
                    <td class="num" class:neg={Number(material.stock_total) <= 0 || material.is_negative}>
                      {formatQty(material.stock_total)} {material.unit}
                    </td>
                    <td onclick={(e) => e.stopPropagation()}>
                      <div class="row-actions">
                        <button class="btn secondary" onclick={() => openEditMaterial(material)}>Bearbeiten</button>
                        <button class="btn secondary" disabled={saving} onclick={() => setOverviewIgnored('material', material, true)}>Ignorieren</button>
                      </div>
                    </td>
                  </tr>
                {/snippet}
              </ProductGroupSection>
            </tbody>
          </table>
        </div>
      {/if}

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
    </section>
    <BackupPanel onFlash={showFlash} onImported={refresh} />
  {:else if tab === 'materials'}
    <section class="panel">
      <div class="panel-header">
        <h2>Materialien</h2>
        <div class="row-actions">
          <button class="btn secondary" onclick={() => openBulkMaterials()}>Aus Farben…</button>
          <button class="btn" onclick={openCreateMaterial}>Neu</button>
        </div>
      </div>
      <div class="filter-bar form-grid filter-bar-end">
        <label>Filter Tag
          <select bind:value={filterTag} onchange={refresh}>
            <option value="">alle</option>
            {#each allTags as t}<option value={t.name}>{t.name}</option>{/each}
          </select>
        </label>
        <label>Filter Farbe
          <select bind:value={filterColorId} onchange={refresh}>
            <option value="">alle</option>
            {#each colors as c}<option value={c.id}>{c.label}</option>{/each}
          </select>
        </label>
        <FamilyFilter families={materialFamilies} bind:value={filterMaterialFamily} />
        <label class="list-search">Suche
          <input type="search" placeholder="Name, Standort, Farbe, Tags…" bind:value={listUi.materials.q} />
        </label>
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
                <tr class="row-click" onclick={() => openEditMaterial(material)}>
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
                    <td class="num" class:neg={stockAt(material, loc.id) < 0}>{formatQty(stockAt(material, loc.id))}</td>
                  {/each}
                  <td class="num" class:neg={Number(material.stock_total) <= 0 || material.is_negative}>
                    {formatQty(material.stock_total)} {material.unit}
                  </td>
                  <td class="meta-cell">
                    <div>{formatDateTime(material.updated_at)}</div>
                    <div class="empty">{formatActor(material.updated_by)}</div>
                  </td>
                  <td onclick={(e) => e.stopPropagation()}>
                    <div class="row-actions">
                      <button class="btn secondary" onclick={() => openEditMaterial(material)}>Bearbeiten</button>
                      <button class="btn secondary" onclick={() => openTransfer('material', material)}>Umbuchen</button>
                      <button class="btn danger" onclick={() => removeMaterial(material)}>Löschen</button>
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
    <section class="panel">
      <div class="panel-header">
        <h2>Produkte</h2>
        <div class="row-actions">
          <button class="btn secondary" disabled={saving} onclick={suggestFamilies}>Familien vorschlagen</button>
          <button class="btn secondary" onclick={() => openBulkProducts()}>Aus Farben…</button>
          <button class="btn" onclick={openCreateProduct}>Neu</button>
        </div>
      </div>
      <div class="filter-bar form-grid filter-bar-end">
        <label>Filter Tag
          <select bind:value={filterTag} onchange={refresh}>
            <option value="">alle</option>
            {#each allTags as t}<option value={t.name}>{t.name}</option>{/each}
          </select>
        </label>
        <label>Filter Farbe
          <select bind:value={filterColorId} onchange={refresh}>
            <option value="">alle</option>
            {#each colors as c}<option value={c.id}>{c.label}</option>{/each}
          </select>
        </label>
        <FamilyFilter families={productFamilies} bind:value={filterFamily} />
        <label class="list-search">Suche
          <input type="search" placeholder="Name, Standort, Farbe, Tags…" bind:value={listUi.products.q} />
        </label>
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
                <tr class="row-click" onclick={() => openEditProduct(product)}>
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
                    <td class="num" class:neg={stockAt(product, loc.id) < 0}>{formatQty(stockAt(product, loc.id))}</td>
                  {/each}
                  <td class="num" class:neg={Number(product.stock_total) <= 0 || product.is_negative}>
                    {formatQty(product.stock_total)}
                  </td>
                  <td class="meta-cell">
                    <div>{formatDateTime(product.updated_at)}</div>
                    <div class="empty">{formatActor(product.updated_by)}</div>
                  </td>
                  <td onclick={(e) => e.stopPropagation()}>
                    <div class="row-actions">
                      <button class="btn secondary" onclick={() => openEditProduct(product)}>Bearbeiten</button>
                      <button class="btn" onclick={() => openManufacture(product)}>Fertigen</button>
                      <button class="btn secondary" onclick={() => openTransfer('product', product)}>Umbuchen</button>
                      {#if canTransformProduct(product)}
                        <button class="btn secondary" onclick={() => openTransform(product)}>Umwandeln</button>
                      {/if}
                      <button class="btn secondary" onclick={() => openMovements(product)}>Historie</button>
                      <button class="btn danger" onclick={() => removeProduct(product)}>Löschen</button>
                    </div>
                  </td>
                </tr>
              {/snippet}
            </ProductGroupSection>
          </tbody>
        </table>
      </div>
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
                  <td class="num" class:neg={stockAt(product, loc.id) < 0}>{formatQty(stockAt(product, loc.id))}</td>
                {/each}
                <td>
                  <div class="row-actions">
                    <button class="btn secondary" onclick={() => openTransfer('product', product)}>Umbuchen</button>
                    {#if canTransformProduct(product)}
                      <button class="btn" onclick={() => openTransform(product)}>Umwandeln</button>
                    {/if}
                    <button class="btn secondary" onclick={() => openMovements(product)}>Historie</button>
                    <button class="btn secondary" onclick={() => openEditProduct(product)}>Bearbeiten</button>
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
                      <td colspan="2" class="empty">Noch keine Farben — unten eintragen.</td>
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
  {:else}
    <section class="panel">
      <div class="panel-header">
        <h2>Shopify-Sets</h2>
        <label class="btn" style="display:inline-flex;align-items:center;gap:.35rem">
          1. Shopify-CSV importieren (Produkte-Export oder Inventory)
          <input type="file" accept=".csv,text/csv" hidden onchange={onImportFile} disabled={saving} />
        </label>
      </div>

      <div class="steps-intro">
        <p><strong>Was ist ein Set?</strong> Nur in Shopify verkauft — bei euch liegen die Einzelteile (Produkte/Materialien). Hier siehst du, welche Farbkombinationen aus dem Lager noch baubar sind.</p>
        <ol>
          <li>CSV aus Shopify importieren (Varianten laden)</li>
          <li>Jede Option (z. B. Ringfarbe „Salbeigrün“) einem Lagerartikel zuordnen</li>
          <li>Zuordnung anwenden → Baubarkeit prüfen</li>
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
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (materialModal = null)}>
    <div class="modal" role="dialog" aria-modal="true">
      <h3>{materialModal.mode === 'create' ? 'Material anlegen' : 'Material bearbeiten'}</h3>
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
        <label>Einkaufsmenge (Packung in Einheit)
          <input type="number" step="0.001" min="0.001" bind:value={materialForm.purchase_quantity} required />
        </label>
        <label>Einkaufspreis für diese Menge (€)
          <input type="number" step="0.01" bind:value={materialForm.purchase_price} required />
        </label>
        <p class="empty" style="margin:0">
          → Preis/Einheit: {formatUnitCost(computedUnitCost(materialForm.purchase_price, materialForm.purchase_quantity))}
          (z. B. 750 ml für 30 € → 0,04 €/ml)
        </p>
        <label>Mindestbestand (optional)
          <input type="number" step="0.001" min="0" bind:value={materialForm.min_stock} placeholder="leer = keiner" />
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
          <label>Anfangsbestand<input type="number" step="0.001" bind:value={materialForm.stock_quantity} required /></label>
        {/if}
        <div class="modal-actions">
          <button type="button" class="btn secondary" onclick={() => (materialModal = null)}>Abbrechen</button>
          <button class="btn" disabled={saving}>{saveButtonOk ? '✓ Gespeichert' : 'Speichern'}</button>
        </div>
      </form>
      {#if materialModal.mode === 'edit'}
        <div class="bom-block">
          <h4>Bestand je Standort (Gesamt {formatQty(materialModal.material?.stock_total ?? 0)})</h4>
          {#each materialLocations as loc}
            {#if stockDrafts[loc.id]}
            <div class="stock-row">
              <strong>{loc.name}</strong>
              <label>Setzen
                <input type="number" step="0.001" bind:value={stockDrafts[loc.id].setValue} />
              </label>
              <button type="button" class="btn secondary" disabled={saving} onclick={() => setMaterialStock(loc.id)}>Setzen</button>
              <label>+/− Menge
                <input type="number" step="0.001" min="0.001" bind:value={stockDrafts[loc.id].deltaValue} />
              </label>
              <div class="row-actions">
                <button type="button" class="btn secondary" disabled={saving} onclick={() => deltaMaterialStock(loc.id, 1)}>+</button>
                <button type="button" class="btn secondary" disabled={saving} onclick={() => deltaMaterialStock(loc.id, -1)}>−</button>
              </div>
            </div>
            {/if}
          {/each}
        </div>
      {/if}
    </div>
  </div>
{/if}

{#if productModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (productModal = null)}>
    <div class="modal" role="dialog" aria-modal="true">
      <h3>{productModal.mode === 'create' ? 'Produkt anlegen' : 'Produkt bearbeiten'}</h3>
      <form class="form-grid" onsubmit={(e) => { e.preventDefault(); saveProduct() }}>
        <label>Name
          <input list="product-name-suggestions" bind:value={productForm.name} required />
        </label>
        <datalist id="product-name-suggestions">
          {#each products as p}<option value={p.name}></option>{/each}
        </datalist>
        <label>SKU<input bind:value={productForm.sku} placeholder="optional" /></label>
        <label>Produktfamilie
          <input list="product-family-suggestions" bind:value={productForm.family} placeholder="optional, z. B. Ring" />
        </label>
        <datalist id="product-family-suggestions">
          {#each productFamilies as f}<option value={f}></option>{/each}
        </datalist>
        <label>Mindestbestand (optional)
          <input type="number" step="0.001" min="0" bind:value={productForm.min_stock} placeholder="leer = keiner" />
        </label>
        {#if productModal.mode === 'edit'}
          <label class="tag-check">
            <input type="checkbox" bind:checked={productForm.is_template} />
            Ist Vorlage
          </label>
        {/if}
        <label>Wird zu (Umwandlung)
          <select bind:value={productForm.transform_target_id}>
            <option value="">keins</option>
            {#each products.filter((p) => !productModal.product || p.id !== productModal.product.id) as p}
              <option value={p.id}>{p.name}</option>
            {/each}
          </select>
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
          <label>Anfangsbestand<input type="number" step="0.001" bind:value={productForm.stock_quantity} required /></label>
        {/if}
        <div class="modal-actions">
          <button type="button" class="btn secondary" onclick={() => (productModal = null)}>Schließen</button>
          <button class="btn" disabled={saving}>{saveButtonOk ? '✓ Gespeichert' : 'Speichern'}</button>
        </div>
      </form>
      {#if productModal.product}
        <div class="bom-block">
          <h4>Bestand je Standort (Gesamt {formatQty(productModal.product.stock_total)})</h4>
          {#each orderedLocations as loc}
            {#if stockDrafts[loc.id]}
            <div class="stock-row">
              <strong>{loc.name}</strong>
              <label>Setzen
                <input type="number" step="0.001" bind:value={stockDrafts[loc.id].setValue} />
              </label>
              <button type="button" class="btn secondary" disabled={saving} onclick={() => setProductStock(loc.id)}>Setzen</button>
              <label>+/− Menge
                <input type="number" step="0.001" min="0.001" bind:value={stockDrafts[loc.id].deltaValue} />
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
                · {formatQty(line.quantity_required)}{line.material_unit ? ` ${line.material_unit}` : ''}
                · {formatMoney(line.line_cost)}
              </div>
              <button class="btn danger" onclick={() => removeBomLine(line)}>Entfernen</button>
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
                <select bind:value={bomForm.product_id}>
                  <option value="">wählen…</option>
                  {#each availableBomProducts as p}<option value={p.id}>{p.name}</option>{/each}
                </select>
              </label>
            {:else}
              <label>Material
                <select bind:value={bomForm.material_id}>
                  <option value="">wählen…</option>
                  {#each availableBomMaterials as m}<option value={m.id}>{m.name} ({m.unit})</option>{/each}
                </select>
              </label>
            {/if}
            <label>Menge pro Produkteinheit
              <input type="number" step="0.001" min="0.001" bind:value={bomForm.quantity_required} placeholder="z. B. 0,056" required />
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
                <label>Einkaufsmenge<input type="number" step="0.001" min="0.001" bind:value={inlineMaterialForm.purchase_quantity} /></label>
                <label>Einkaufspreis (€)<input type="number" step="0.01" bind:value={inlineMaterialForm.purchase_price} /></label>
                <p class="empty" style="margin:0">
                  → {formatUnitCost(computedUnitCost(inlineMaterialForm.purchase_price, inlineMaterialForm.purchase_quantity))} / Einheit
                </p>
                <label>Standort
                  <select bind:value={inlineMaterialForm.location_id}>{#each locations as l}<option value={l.id}>{l.name}</option>{/each}</select>
                </label>
                <label>Anfangsbestand<input type="number" step="0.001" bind:value={inlineMaterialForm.stock_quantity} /></label>
                <button class="btn" disabled={saving || !inlineMaterialForm.name.trim()} onclick={createInlineMaterial}>
                  Material anlegen & auswählen
                </button>
              </div>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  </div>
{/if}

{#if manufactureModal}
  <div class="modal-backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && (manufactureModal = null)}>
    <div class="modal" role="dialog" aria-modal="true">
      <h3>Fertigen: {manufactureModal.name}</h3>
      <form class="form-grid" onsubmit={(e) => { e.preventDefault(); runManufacture() }}>
        <label>Menge<input type="number" step="0.001" min="0.001" bind:value={manufactureForm.quantity} required /></label>
        <label>Standort
          <select bind:value={manufactureForm.location_id}>{#each locations as l}<option value={l.id}>{l.name}</option>{/each}</select>
        </label>
        <div class="modal-actions">
          <button type="button" class="btn secondary" onclick={() => (manufactureModal = null)}>Abbrechen</button>
          <button class="btn" disabled={saving}>Fertigen</button>
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
        <label>Menge<input type="number" step="0.001" min="0.001" bind:value={transferForm.quantity} required /></label>
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
        <label>Menge<input type="number" step="0.001" min="0.001" bind:value={transformForm.quantity} required /></label>
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
              <button class="btn danger" disabled={saving} onclick={() => removeMapping(mapping)}>Entfernen</button>
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
              <button class="btn danger" disabled={saving} onclick={() => detachSetComponent(comp)}>Entfernen</button>
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
              <button class="btn danger" onclick={() => removeMapping(mapping)}>Entfernen</button>
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
                <select
                  value={getSetOptionConfig(mappingForm.option_name).templateId}
                  onchange={(e) => {
                    const tid = e.currentTarget.value
                    const t = products.find((p) => p.id === Number(tid))
                    const series = t ? templateSeriesPrefix(t, colors) : ''
                    patchSetOptionConfig(mappingForm.option_name, {
                      templateId: tid,
                      baseName: series || t?.family || getSetOptionConfig(mappingForm.option_name).baseName,
                    })
                  }}
                >
                  <option value="">ohne</option>
                  {#each productsForBomTemplate as p}
                    <option value={p.id}>{p.is_template ? `Vorlage: ${p.name}` : p.name}</option>
                  {/each}
                </select>
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
        Optional Vorlage (Einheit/Einkauf/Tags, „Ist Vorlage“), dann Serienanlage.
        Name = „Basis Farbe“ — z. B. Vorlage „Kerzen klein - Altrosa“ → Basis „Kerzen klein -“.
        Bestand startet bei 0. Schon vorhandene Namen sind nicht wählbar.
      </p>
      <div class="form-grid">
        <label>Basisname
          <input
            bind:value={bulkForm.base_name}
            placeholder="z. B. Kerzen klein -"
            required
            oninput={() => {
              const pool = bulkMaterialModal.mediumId
                ? colorsForMedium(bulkMaterialModal.mediumId)
                : colors
              const available = pool
                .filter((c) => !isBulkMaterialColorTaken(bulkForm.base_name, c))
                .map((c) => c.id)
              bulkForm.colorIds = available
            }}
          />
        </label>
        <label>Medium-Filter
          <select
            value={bulkMaterialModal.mediumId ?? ''}
            onchange={(e) => {
              const mid = e.currentTarget.value ? Number(e.currentTarget.value) : null
              openBulkMaterials(mid, { keepTemplate: true })
            }}
          >
            <option value="">alle Medien</option>
            {#each media as m}<option value={m.id}>{m.name}</option>{/each}
          </select>
        </label>
        <label>Vorlage
          <select bind:value={bulkForm.template_material_id} onchange={onBulkMaterialTemplateChange}>
            <option value="">keine</option>
            {#each materialsForSeriesTemplate as m}
              <option value={m.id}>Vorlage: {m.name}</option>
            {/each}
          </select>
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
          <input type="number" step="0.001" min="0" bind:value={bulkForm.min_stock} placeholder="leer = Vorlage / keiner" />
        </label>
        {#if !hasMaterialTemplates}
          <p class="empty" style="grid-column:1/-1;margin:0">
            Noch keine Vorlage — Material bearbeiten und „Ist Vorlage“ setzen.
          </p>
        {/if}
      </div>
      <fieldset class="tag-picker" style="margin-top:.75rem">
        <legend>Farben</legend>
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
      </fieldset>
      <div class="modal-actions">
        <button type="button" class="btn secondary" onclick={() => (bulkMaterialModal = null)}>Abbrechen</button>
        <button
          type="button"
          class="btn"
          disabled={saving || !bulkForm.colorIds.length || !bulkForm.base_name.trim()}
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
      <h3>Produkte aus Farben</h3>
      <p class="empty" style="margin-top:0">
        Zuerst optional eine Vorlage anlegen (Stückliste/Tags, „Ist Vorlage“), dann Serienanlage.
        Name = „Basis Farbe“. Farbige Stücklisten-Materialien werden umgebogen.
      </p>
      <div class="form-grid">
        <label>Basisname
          <input
            bind:value={bulkForm.base_name}
            placeholder="z. B. Ring"
            required
            oninput={() => {
              const pool = bulkProductModal.mediumId
                ? colorsForMedium(bulkProductModal.mediumId)
                : colors
              const available = pool
                .filter((c) => !isBulkProductColorTaken(bulkForm.base_name, c))
                .map((c) => c.id)
              bulkForm.colorIds = available
            }}
          />
        </label>
        <label>Medium-Filter
          <select
            value={bulkProductModal.mediumId ?? ''}
            onchange={(e) => {
              const mid = e.currentTarget.value ? Number(e.currentTarget.value) : null
              openBulkProducts({
                mediumId: mid,
                baseName: bulkForm.base_name,
                templateProductId: bulkForm.template_product_id,
              })
            }}
          >
            <option value="">alle Medien</option>
            {#each media as m}<option value={m.id}>{m.name}</option>{/each}
          </select>
        </label>
        <label>Stücklisten-Vorlage
          <select bind:value={bulkForm.template_product_id} onchange={onBulkTemplateChange}>
            <option value="">keine</option>
            {#each productsForBomTemplate as p}
              <option value={p.id}>{p.is_template ? `Vorlage: ${p.name}` : p.name}</option>
            {/each}
          </select>
        </label>
        <label>Mindestbestand (optional)
          <input type="number" step="0.001" min="0" bind:value={bulkForm.min_stock} placeholder="leer = keiner" />
        </label>
        {#if !hasProductTemplates}
          <p class="empty" style="grid-column:1/-1;margin:0">
            Noch keine Vorlage — Produkt anlegen und „Ist Vorlage“ setzen.
          </p>
        {/if}
      </div>
      <fieldset class="tag-picker" style="margin-top:.75rem">
        <legend>Farben</legend>
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
      </fieldset>
      <div class="modal-actions">
        <button type="button" class="btn secondary" onclick={() => (bulkProductModal = null)}>Abbrechen</button>
        <button
          type="button"
          class="btn"
          disabled={saving || !bulkForm.colorIds.length || !bulkForm.base_name.trim()}
          onclick={submitBulkProducts}
        >
          {bulkForm.colorIds.length} anlegen
        </button>
      </div>
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
                  step="0.001"
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
                    <small>Hinzufügen oder Menge ändern (mit Warnung)</small>
                  </span>
                </label>
              </div>
              {#if bulkEditForm.setBom}
                <div class="bulk-block-body bulk-block-nested">
                  <label class="bulk-field">Material
                    <select bind:value={bulkEditForm.bom_material_id}>
                      <option value="">wählen…</option>
                      {#each materials as m}<option value={m.id}>{m.name}</option>{/each}
                    </select>
                  </label>
                  <label class="bulk-field">Menge pro Produkteinheit
                    <input type="number" step="0.001" min="0.001" bind:value={bulkEditForm.bom_quantity} />
                  </label>
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
            <button class="btn danger" disabled={saving}>Löschen</button>
          {:else}
            <button class="btn" disabled={saving}>Speichern</button>
          {/if}
        </div>
      </form>
    </div>
  </div>
{/if}
