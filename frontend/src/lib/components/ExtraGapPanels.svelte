<script>
  import { itemDecimals, qtyStep } from '../api.js'

  let {
    kind = 'product',
    criticalRows = [],
    incompleteRows = [],
    ignoredRows = [],
    locations = [],
    selectedIds = $bindable([]),
    criticalOpen = $bindable(false),
    incompleteOpen = $bindable(false),
    ignoredOpen = $bindable(false),
    saving = false,
    onOpenEdit = () => {},
    onIgnore = () => {},
    onUnignore = () => {},
    onPatch = async () => {},
    onAdjustStock = async () => {},
  } = $props()

  const isMaterial = $derived(kind === 'material')
  const priceLabel = $derived(isMaterial ? 'Einkauf' : 'Verkauf')

  function isSelected(id) {
    return selectedIds.includes(id)
  }

  function toggle(id) {
    selectedIds = isSelected(id) ? selectedIds.filter((x) => x !== id) : [...selectedIds, id]
  }

  function stockVal(item, locId) {
    const row = (item.stocks || []).find((s) => s.location_id === locId)
    return row ? Number(row.quantity) : 0
  }

  async function blurNumber(item, field, event, allowEmpty = false) {
    const raw = event.currentTarget.value
    if (allowEmpty && String(raw).trim() === '') {
      await onPatch(item, { [field]: null })
      return
    }
    const n = Number(String(raw).replace(',', '.'))
    if (Number.isNaN(n)) return
    await onPatch(item, { [field]: String(n) })
  }

  async function blurStock(item, locId, event) {
    const n = Number(String(event.currentTarget.value).replace(',', '.'))
    if (Number.isNaN(n)) return
    await onAdjustStock(item, { location_id: locId, quantity: String(n) })
  }
</script>

<section class="panel" class:collapsed={!criticalOpen}>
  <div class="panel-header">
    <h2>
      <button type="button" class="group-toggle overview-section-toggle" onclick={() => (criticalOpen = !criticalOpen)}>
        {criticalOpen ? '▼' : '▶'} Kritische Artikel
        <span class="empty">({criticalRows.length})</span>
      </button>
    </h2>
  </div>
  {#if criticalOpen}
    {@render gapTable(criticalRows, true)}
    {#if ignoredRows.length}
      <button type="button" class="group-toggle overview-section-toggle" onclick={() => (ignoredOpen = !ignoredOpen)}>
        {ignoredOpen ? '▼' : '▶'} Ignorierte Engpässe
        <span class="empty">({ignoredRows.length})</span>
      </button>
      {#if ignoredOpen}
        <ul class="plain-list">
          {#each ignoredRows as item}
            <li class="bom-line">
              <div><strong>{item.name}</strong></div>
              <button type="button" class="btn secondary" disabled={saving} onclick={() => onUnignore(item)}>Wieder anzeigen</button>
            </li>
          {/each}
        </ul>
      {/if}
    {/if}
  {/if}
</section>

<section class="panel" class:collapsed={!incompleteOpen}>
  <div class="panel-header">
    <h2>
      <button type="button" class="group-toggle overview-section-toggle" onclick={() => (incompleteOpen = !incompleteOpen)}>
        {incompleteOpen ? '▼' : '▶'} Unvollständigkeit
        <span class="empty">({incompleteRows.length})</span>
      </button>
    </h2>
  </div>
  {#if incompleteOpen}
    {@render gapTable(incompleteRows, false)}
  {/if}
</section>

{#snippet gapTable(rows, showIgnore)}
  <div class="table-wrap stock-table-wrap">
    <table class="stock-table extra-gap-table">
      <thead>
        <tr>
          <th class="col-select"></th>
          <th>Name</th>
          <th>Min.</th>
          <th>{priceLabel} €</th>
          {#each locations as loc}
            <th class="num">{loc.name}</th>
          {/each}
          <th></th>
        </tr>
      </thead>
      <tbody>
        {#each rows as item (item.id)}
          <tr>
            <td class="col-select">
              <input
                type="checkbox"
                aria-label={`${item.name} wählen`}
                checked={isSelected(item.id)}
                onchange={() => toggle(item.id)}
              />
            </td>
            <td>
              <button type="button" class="group-toggle" onclick={() => onOpenEdit(item)}>{item.name}</button>
              {#if item.incomplete_fields?.length}
                <div class="incomplete-hint">
                  <span class="incomplete-icon" aria-hidden="true">!</span>
                  {item.incomplete_fields.join(', ')}
                </div>
              {/if}
            </td>
            <td>
              <input
                class="gap-cell"
                type="number"
                min="0"
                step="0.001"
                value={item.min_stock ?? ''}
                disabled={saving}
                onblur={(e) => blurNumber(item, 'min_stock', e, true)}
              />
            </td>
            <td>
              {#if isMaterial}
                <input
                  class="gap-cell"
                  type="number"
                  min="0"
                  step="0.01"
                  value={item.purchase_price ?? 0}
                  disabled={saving}
                  onblur={(e) => blurNumber(item, 'purchase_price', e)}
                />
              {:else}
                <input
                  class="gap-cell"
                  type="number"
                  min="0"
                  step="0.01"
                  value={item.selling_price ?? 0}
                  disabled={saving}
                  onblur={(e) => blurNumber(item, 'selling_price', e)}
                />
              {/if}
            </td>
            {#each locations as loc}
              <td class="num">
                <input
                  class="gap-cell"
                  type="number"
                  step={qtyStep(itemDecimals(item))}
                  value={stockVal(item, loc.id)}
                  disabled={saving}
                  onblur={(e) => blurStock(item, loc.id, e)}
                />
              </td>
            {/each}
            <td>
              <div class="row-actions">
                <button type="button" class="btn secondary" onclick={() => onOpenEdit(item)}>Bearbeiten</button>
                {#if showIgnore}
                  <button type="button" class="btn secondary" disabled={saving} onclick={() => onIgnore(item)}>Ignorieren</button>
                {/if}
              </div>
            </td>
          </tr>
        {:else}
          <tr>
            <td colspan={5 + locations.length} class="empty">Keine Einträge.</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/snippet}
