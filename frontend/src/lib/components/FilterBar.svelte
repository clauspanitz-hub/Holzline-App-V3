<script>
  import { applyMediumCompanion, catalogFilterActive } from '../catalogFilter.js'

  let {
    media = [],
    colors = [],
    families = [],
    tags = [],
    filter = $bindable({
      mediumIds: [],
      colorIds: [],
      families: [],
      tagIds: [],
      q: '',
    }),
  } = $props()

  let familyOpen = $state(false)
  let tagOpen = $state(false)
  let familyRoot = $state(null)
  let tagRoot = $state(null)

  const active = $derived(catalogFilterActive(filter))
  const selectedMedia = $derived(media.filter((m) => filter.mediumIds.includes(m.id)))
  const familyLabel = $derived(
    filter.families.length ? `${filter.families.length} Familien` : 'alle Familien',
  )
  const tagLabel = $derived(filter.tagIds.length ? `${filter.tagIds.length} Tags` : 'alle Tags')

  function mediumById(id) {
    return media.find((m) => m.id === id) || null
  }

  function toggleMedium(id) {
    const on = filter.mediumIds.includes(id)
    const medium = mediumById(id)
    const mediumIds = on ? filter.mediumIds.filter((x) => x !== id) : [...filter.mediumIds, id]
    let colorIds = filter.colorIds
    if (on) {
      const drop = new Set(colors.filter((c) => c.medium_id === id).map((c) => c.id))
      colorIds = colorIds.filter((cid) => !drop.has(cid))
    }
    filter = applyMediumCompanion({ ...filter, mediumIds, colorIds }, medium, {
      families,
      tags,
      on: !on,
    })
  }

  function toggleColor(color) {
    const on = filter.colorIds.includes(color.id)
    const colorIds = on
      ? filter.colorIds.filter((id) => id !== color.id)
      : [...filter.colorIds, color.id]
    let mediumIds = filter.mediumIds
    let next = { ...filter, colorIds, mediumIds }
    if (!on && !mediumIds.includes(color.medium_id)) {
      mediumIds = [...mediumIds, color.medium_id]
      next = applyMediumCompanion({ ...filter, colorIds, mediumIds }, mediumById(color.medium_id), {
        families,
        tags,
        on: true,
      })
    }
    filter = next
  }

  function toggleFamily(name) {
    const on = filter.families.includes(name)
    filter = {
      ...filter,
      families: on ? filter.families.filter((f) => f !== name) : [...filter.families, name],
    }
  }

  function toggleTag(id) {
    const on = filter.tagIds.includes(id)
    filter = {
      ...filter,
      tagIds: on ? filter.tagIds.filter((x) => x !== id) : [...filter.tagIds, id],
    }
  }

  function clearAll() {
    filter = { mediumIds: [], colorIds: [], families: [], tagIds: [], q: '' }
  }

  function swatch(color) {
    return color?.hex || '#9AA0A6'
  }

  $effect(() => {
    if (!familyOpen && !tagOpen) return
    function onDoc(event) {
      if (familyOpen && familyRoot && !familyRoot.contains(event.target)) familyOpen = false
      if (tagOpen && tagRoot && !tagRoot.contains(event.target)) tagOpen = false
    }
    document.addEventListener('pointerdown', onDoc)
    return () => document.removeEventListener('pointerdown', onDoc)
  })
</script>

<div class="catalog-filter" class:active>
  <div class="catalog-filter-media">
    <span class="catalog-filter-label">Medium</span>
    <div class="catalog-filter-chips">
      {#each media as m (m.id)}
        <button
          type="button"
          class="chip"
          class:on={filter.mediumIds.includes(m.id)}
          aria-pressed={filter.mediumIds.includes(m.id)}
          onclick={() => toggleMedium(m.id)}
        >
          {m.name}
        </button>
      {:else}
        <span class="empty">Keine Medien.</span>
      {/each}
    </div>
  </div>

  <div class="catalog-filter-multi" bind:this={familyRoot}>
    <span class="catalog-filter-label">Familie</span>
    <button type="button" class="catalog-filter-trigger" onclick={() => (familyOpen = !familyOpen)}>
      {familyLabel}
    </button>
    {#if familyOpen}
      <div class="catalog-filter-menu" role="listbox">
        {#each families as family (family)}
          <label class="catalog-filter-option">
            <input
              type="checkbox"
              checked={filter.families.includes(family)}
              onchange={() => toggleFamily(family)}
            />
            {family}
          </label>
        {:else}
          <p class="empty">Keine Familien.</p>
        {/each}
      </div>
    {/if}
  </div>

  <div class="catalog-filter-multi" bind:this={tagRoot}>
    <span class="catalog-filter-label">Tag</span>
    <button type="button" class="catalog-filter-trigger" onclick={() => (tagOpen = !tagOpen)}>
      {tagLabel}
    </button>
    {#if tagOpen}
      <div class="catalog-filter-menu" role="listbox">
        {#each tags as t (t.id)}
          <label class="catalog-filter-option">
            <input
              type="checkbox"
              checked={filter.tagIds.includes(t.id)}
              onchange={() => toggleTag(t.id)}
            />
            {t.name}
          </label>
        {:else}
          <p class="empty">Keine Tags.</p>
        {/each}
      </div>
    {/if}
  </div>

  <label class="catalog-filter-search">Freitext
    <input
      type="search"
      placeholder="Name, Standort…"
      value={filter.q}
      oninput={(e) => (filter = { ...filter, q: e.currentTarget.value })}
    />
  </label>

  {#if selectedMedia.length}
    <div class="catalog-filter-colors">
      {#each selectedMedia as m (m.id)}
        {@const mediumColors = colors.filter((c) => c.medium_id === m.id)}
        <div class="catalog-filter-swatch-group">
          <span class="catalog-filter-swatch-label">{m.name}</span>
          <div class="catalog-filter-swatches">
            {#each mediumColors as c (c.id)}
              <button
                type="button"
                class="color-swatch"
                class:on={filter.colorIds.includes(c.id)}
                title={c.name}
                aria-label={c.name}
                aria-pressed={filter.colorIds.includes(c.id)}
                style={`background:${swatch(c)}`}
                onclick={() => toggleColor(c)}
              ></button>
            {:else}
              <span class="empty">Keine Farben.</span>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  {/if}

  {#if active}
    <div class="catalog-filter-status">
      <span>Filter aktiv</span>
      <button type="button" class="btn secondary compact" onclick={clearAll}>alle Filter entfernen</button>
    </div>
  {/if}
</div>
