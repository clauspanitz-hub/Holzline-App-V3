<script>
  /**
   * Workflow-Sidebar: Werkstatt · Lager · Bestellungen · Stammdaten · Admin
   * @typedef {{ id: string, label: string, badge?: number | string }} NavItem
   * @typedef {{ title: string, items: NavItem[] }} NavGroup
   */
  let {
    tab = 'overview',
    role = 'admin',
    username = '',
    open = false,
    openTodos = 0,
    staffCount = 0,
    importOpen = 0,
    onSelect = (_id) => {},
    onPassword = () => {},
    onLogout = () => {},
    onClose = () => {},
  } = $props()

  /** @type {NavGroup[]} */
  const adminGroups = $derived([
    {
      title: 'Werkstatt',
      items: [
        { id: 'todos', label: 'Todos', badge: openTodos || undefined },
        { id: 'overview', label: 'Übersicht' },
        { id: 'staff', label: 'Bei Mitarbeitern', badge: staffCount || undefined },
      ],
    },
    {
      title: 'Lager',
      items: [
        { id: 'materials', label: 'Materialien' },
        { id: 'products', label: 'Produkte' },
        { id: 'sets', label: 'Sets' },
      ],
    },
    {
      title: 'Bestellungen',
      items: [{ id: 'orders', label: 'Bestellungen' }],
    },
    {
      title: 'Stammdaten',
      items: [
        { id: 'catalogs', label: 'Kataloge' },
        { id: 'import', label: 'Import', badge: importOpen || undefined },
      ],
    },
    {
      title: 'Admin',
      items: [{ id: 'users', label: 'Benutzer' }],
    },
  ])

  /** @type {NavGroup[]} */
  const staffGroups = $derived([
    {
      title: 'Werkstatt',
      items: [{ id: 'staff', label: 'Bei Mitarbeitern', badge: staffCount || undefined }],
    },
  ])

  const groups = $derived(role === 'admin' ? adminGroups : staffGroups)

  function choose(id) {
    onSelect(id)
    onClose()
  }
</script>

{#if open}
  <button type="button" class="nav-scrim" aria-label="Menü schließen" onclick={onClose}></button>
{/if}

<aside class="app-nav" class:open aria-label="Hauptnavigation">
  <div class="nav-brand">
    <p class="nav-eyebrow">Inventar</p>
    <h1>Holzlinge</h1>
  </div>

  <nav class="nav-groups">
    {#each groups as group}
      <div class="nav-group">
        <p class="nav-group-title">{group.title}</p>
        <ul>
          {#each group.items as item}
            <li>
              <button
                type="button"
                class="nav-item"
                class:active={tab === item.id}
                onclick={() => choose(item.id)}
              >
                <span>{item.label}</span>
                {#if item.badge}
                  <span class="nav-badge">{item.badge}</span>
                {/if}
              </button>
            </li>
          {/each}
        </ul>
      </div>
    {/each}
  </nav>

  <div class="nav-footer">
    <span class="nav-user">{username}</span>
    <div class="nav-footer-actions">
      <button type="button" class="btn secondary compact" onclick={onPassword}>Passwort</button>
      <button type="button" class="btn secondary compact" onclick={onLogout}>Abmelden</button>
    </div>
  </div>
</aside>
