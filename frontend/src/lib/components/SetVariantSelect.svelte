<script>
  /**
   * Combobox für Set-Varianten analog FamilySelect:
   * Gruppe = Set-Name, Zeilen = kurze Options-Labels (z. B. „Fisch / rot“).
   * Nutzt dieselben CSS-Klassen wie FamilySelect.
   */
  let {
    value = $bindable(''),
    items = [],
    emptyLabel = 'wählen…',
    disabled = false,
    inline = false,
    onchange,
  } = $props()

  let open = $state(false)
  let query = $state('')
  let expanded = $state({})
  let rootEl = $state(null)
  let searchEl = $state(null)

  const selected = $derived(items.find((item) => String(item.id) === String(value)) ?? null)
  const selectedLabel = $derived(
    selected
      ? [selected.setName, selected.label].filter(Boolean).join(' · ') || emptyLabel
      : emptyLabel,
  )

  const groups = $derived.by(() => {
    const q = query.trim().toLowerCase()
    const filtered = q
      ? items.filter((item) => {
          const label = String(item?.label || '').toLowerCase()
          const setName = String(item?.setName || '').toLowerCase()
          return label.includes(q) || setName.includes(q)
        })
      : items

    /** @type {Map<string, typeof items>} */
    const bySet = new Map()
    for (const item of filtered) {
      const key = String(item?.setName || '').trim() || 'Ohne Set'
      if (!bySet.has(key)) bySet.set(key, [])
      bySet.get(key).push(item)
    }
    return [...bySet.entries()]
      .map(([key, rows]) => ({ key, rows }))
      .sort((a, b) => a.key.localeCompare(b.key, 'de'))
  })

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

  $effect(() => {
    if (!open) return
    document.addEventListener('pointerdown', onDocPointer)
    return () => document.removeEventListener('pointerdown', onDocPointer)
  })
</script>

<div class="family-select set-variant-select" class:open class:inline bind:this={rootEl}>
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
              {item.label}
            </button>
          {/each}
        {/if}
      {:else}
        <p class="empty family-select-empty">Keine Treffer.</p>
      {/each}
    </div>
  {/if}
</div>
