<script>
  /**
   * Einklappbare Familien-Gruppen für Produkt-/Material-Tabellen.
   * Zeileninhalt kommt per Snippet aus der Eltern-Komponente.
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
</script>

{#each groups as group (group.key)}
  <tr class="group-header">
    <td colspan={colSpan}>
      <div class="group-header-row">
        <button type="button" class="group-toggle" onclick={() => onToggleCollapse(group.key)}>
          {collapsedFamilies[group.key] === false ? '▼' : '▶'}
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
  {#if collapsedFamilies[group.key] === false}
    {#each group.rows as item (item.uid ?? item.id)}
      {@render row({ item, product: item, group })}
    {/each}
  {/if}
{:else}
  <tr><td colspan={colSpan} class="empty">{emptyMessage}</td></tr>
{/each}
