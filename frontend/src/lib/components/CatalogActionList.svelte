<script>
  /**
   * Familien-gruppiierte Aktionskarten für Materialien/Produkte (UI-Redesign).
   * Keine Tabellenzeilen — scannbare Karten + Dialoge.
   */
  let {
    groups = [],
    collapsedFamilies = {},
    emptyMessage = 'Keine Einträge.',
    showFamilySelect = false,
    isFamilySelected = () => false,
    onToggleCollapse = () => {},
    onToggleFamilySelection = () => {},
    card,
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
    return parentOpen(parentKey)
  }
</script>

{#if groups.length}
  <div class="catalog-action-list">
    {#each groups as group (group.key)}
      <div class="catalog-family">
        <div class="group-header-row catalog-family-head">
          <button type="button" class="group-toggle" onclick={() => onToggleCollapse(group.key)}>
            {parentOpen(group.key) ? '▼' : '▶'}
            {group.key}
            <span class="empty">({group.rows.length})</span>
          </button>
          {#if showFamilySelect}
            <button type="button" class="btn secondary compact" onclick={() => onToggleFamilySelection(group)}>
              {isFamilySelected(group) ? 'Familie abwählen' : 'Familie wählen'}
            </button>
          {/if}
        </div>

        {#if parentOpen(group.key)}
          {#if group.subgroups?.length}
            {#if (group.directRows || []).length}
              <div class="card-list catalog-cards">
                {#each group.directRows as item (item.uid ?? item.id)}
                  {@render card({ item, product: item, group })}
                {/each}
              </div>
            {/if}
            {#each group.subgroups as sub (subKey(group.key, sub.key))}
              <div class="catalog-subfamily">
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
                {#if subOpen(group.key, sub.key)}
                  <div class="card-list catalog-cards">
                    {#each sub.rows as item (item.uid ?? item.id)}
                      {@render card({ item, product: item, group })}
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          {:else}
            <div class="card-list catalog-cards">
              {#each group.rows as item (item.uid ?? item.id)}
                {@render card({ item, product: item, group })}
              {/each}
            </div>
          {/if}
        {/if}
      </div>
    {/each}
  </div>
{:else}
  <p class="empty">{emptyMessage}</p>
{/if}
