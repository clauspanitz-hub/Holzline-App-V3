<script>
  /**
   * Einklappbare Familien-Gruppen für Produkt-/Material-Tabellen.
   * Elternkopf → optional Unterköpfe → Zeilen.
   */
  let {
    groups = [],
    collapsedFamilies = {},
    colSpan = 5,
    emptyMessage = 'Keine Einträge.',
    showFamilySelect = false,
    isFamilySelected = () => false,
    onToggleCollapse = () => {},
    onToggleFamilySelection = () => {},
    row,
  } = $props()

  function subKey(parentKey, subName) {
    return `${parentKey}::${subName}`
  }

  function parentOpen(key) {
    return collapsedFamilies[key] === false
  }

  function subOpen(parentKey, subName) {
    const key = subKey(parentKey, subName)
    if (collapsedFamilies[key] === false) return true
    if (collapsedFamilies[key] === true) return false
    // Default: Untergruppen mit aufgeklapptem Eltern auch offen
    return parentOpen(parentKey)
  }
</script>

{#each groups as group (group.key)}
  <tr class="group-header">
    <td colspan={colSpan}>
      <div class="group-header-row">
        <button type="button" class="group-toggle" onclick={() => onToggleCollapse(group.key)}>
          {parentOpen(group.key) ? '▼' : '▶'}
          {group.key}
          <span class="empty">({group.rows.length})</span>
        </button>
        {#if showFamilySelect}
          <button type="button" class="btn secondary" onclick={() => onToggleFamilySelection(group)}>
            {isFamilySelected(group) ? 'Familie abwählen' : 'Familie wählen'}
          </button>
        {/if}
      </div>
    </td>
  </tr>
  {#if parentOpen(group.key)}
    {#if group.subgroups?.length}
      {#each group.directRows || [] as item (item.uid ?? item.id)}
        {@render row({ item, product: item, group })}
      {/each}
      {#each group.subgroups as sub (subKey(group.key, sub.key))}
        <tr class="group-header group-subheader">
          <td colspan={colSpan}>
            <div class="group-header-row">
              <button
                type="button"
                class="group-toggle sub"
                onclick={() => onToggleCollapse(subKey(group.key, sub.key))}
              >
                {subOpen(group.key, sub.key) ? '▼' : '▶'}
                {sub.key}
                <span class="empty">({sub.rows.length})</span>
              </button>
            </div>
          </td>
        </tr>
        {#if subOpen(group.key, sub.key)}
          {#each sub.rows as item (item.uid ?? item.id)}
            {@render row({ item, product: item, group })}
          {/each}
        {/if}
      {/each}
    {:else}
      {#each group.rows as item (item.uid ?? item.id)}
        {@render row({ item, product: item, group })}
      {/each}
    {/if}
  {/if}
{:else}
  <tr><td colspan={colSpan} class="empty">{emptyMessage}</td></tr>
{/each}
