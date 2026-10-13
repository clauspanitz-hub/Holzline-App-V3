<script>
  import { groupByFamily } from '../productFamily.js'

  let {
    value = $bindable(''),
    items = [],
    emptyLabel = 'wählen…',
    formatItem = (item) => item?.name ?? '',
    disabled = false,
    inline = false,
    onchange,
    /** @type {Record<string|number, number> | null} Map product_id → quantity_sold; null = kein Verkaufs-Schalter */
    salesQtyById = null,
    /** Opt-in „nach Verkauf sortieren“ (gemeinsamer Parent-State / localStorage) */
    sortBySales = false,
    onSortBySalesChange = (_v) => {},
  } = $props()

  let open = $state(false)
  let query = $state('')
  let expanded = $state({})
  let rootEl = $state(null)
  let searchEl = $state(null)

  const showSalesToggle = $derived(salesQtyById != null)

  const selected = $derived(items.find((item) => String(item.id) === String(value)) ?? null)
  const selectedLabel = $derived(selected ? formatItem(selected) : emptyLabel)

  function salesQty(item) {
    if (!salesQtyById) return 0
    const n = Number(salesQtyById[item.id] ?? salesQtyById[String(item.id)] ?? 0)
    return Number.isFinite(n) ? n : 0
  }

  function nameKey(item) {
    return String(formatItem(item) || '').toLowerCase()
  }

  const filteredItems = $derived.by(() => {
    const q = query.trim().toLowerCase()
    if (!q) return items
    return items.filter((item) => {
      const name = nameKey(item)
      const family = String(item?.family || '').toLowerCase()
      return name.includes(q) || family.includes(q)
    })
  })

  /** Flache Verkaufsreihenfolge: verkauft desc, dann Name; 0-Verkäufe darunter alphabetisch. */
  const salesOrdered = $derived.by(() => {
    const rows = [...filteredItems]
    rows.sort((a, b) => {
      const qa = salesQty(a)
      const qb = salesQty(b)
      if (qa !== qb) return qb - qa
      const na = nameKey(a)
      const nb = nameKey(b)
      if (na < nb) return -1
      if (na > nb) return 1
      return Number(a.id) - Number(b.id)
    })
    return rows
  })

  const groups = $derived.by(() => groupByFamily(filteredItems))

  function isGroupOpen(key) {
    if (query.trim()) return true
    return expanded[key] === true
  }

  function toggleGroup(key) {
    expanded = { ...expanded, [key]: !isGroupOpen(key) }
  }

  function choose(id) {
    value = id == null || id === '' ? '' : String(id)
    open = false
    query = ''
    onchange?.(value)
  }

  function toggleOpen() {
    if (disabled) return
    open = !open
    if (open) {
      query = ''
      queueMicrotask(() => searchEl?.focus())
    }
  }

  function onDocPointer(event) {
    if (rootEl && !rootEl.contains(event.target)) {
      open = false
      query = ''
    }
  }

  function toggleSalesSort(event) {
    event.stopPropagation()
    onSortBySalesChange?.(!sortBySales)
  }

  $effect(() => {
    if (!open) return
    document.addEventListener('pointerdown', onDocPointer)
    return () => document.removeEventListener('pointerdown', onDocPointer)
  })
</script>

<div class="family-select" class:open class:inline bind:this={rootEl}>
  <button
    type="button"
    class="family-select-trigger"
    {disabled}
    aria-haspopup="listbox"
    aria-expanded={open}
    onclick={toggleOpen}
  >
    <span class:empty={!selected}>{selectedLabel}</span>
    <span class="family-select-caret" aria-hidden="true">{open ? '▲' : '▼'}</span>
  </button>
  {#if open}
    <div class="family-select-panel" role="listbox">
      {#if showSalesToggle}
        <label class="family-select-sales-toggle">
          <input type="checkbox" checked={sortBySales} onchange={toggleSalesSort} />
          nach Verkauf sortieren
        </label>
      {/if}
      <input
        bind:this={searchEl}
        class="family-select-search"
        type="search"
        placeholder="Suchen…"
        bind:value={query}
        onkeydown={(e) => {
          if (e.key === 'Escape') {
            open = false
            query = ''
          }
        }}
      />
      <button type="button" class="family-select-option empty-option" onclick={() => choose('')}>
        {emptyLabel}
      </button>
      {#if sortBySales && showSalesToggle}
        {#each salesOrdered as item (item.id)}
          {@const qty = salesQty(item)}
          <button
            type="button"
            class="family-select-option"
            class:selected={String(item.id) === String(value)}
            role="option"
            aria-selected={String(item.id) === String(value)}
            onclick={() => choose(item.id)}
          >
            <span class="family-select-option-main">
              {formatItem(item)}
              {#if item.family}
                <span class="empty family-select-family-label">{item.family}</span>
              {/if}
            </span>
            {#if qty > 0}
              <span class="empty family-select-sales-qty">{qty}</span>
            {/if}
          </button>
        {:else}
          <p class="empty family-select-empty">Keine Treffer.</p>
        {/each}
      {:else}
        {#each groups as group (group.key)}
          <button type="button" class="family-select-group" onclick={() => toggleGroup(group.key)}>
            {isGroupOpen(group.key) ? '▼' : '▶'} {group.key}
            <span class="empty">({group.rows.length})</span>
          </button>
          {#if isGroupOpen(group.key)}
            {#each group.rows as item (item.id)}
              <button
                type="button"
                class="family-select-option"
                class:selected={String(item.id) === String(value)}
                role="option"
                aria-selected={String(item.id) === String(value)}
                onclick={() => choose(item.id)}
              >
                {formatItem(item)}
              </button>
            {/each}
          {/if}
        {:else}
          <p class="empty family-select-empty">Keine Treffer.</p>
        {/each}
      {/if}
    </div>
  {/if}
</div>
