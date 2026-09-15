<script>
  import { api } from '../api.js'

  /** @type {{ onFlash?: (type: string, message: string) => void, onImported?: () => void | Promise<void> }} */
  let { onFlash = () => {}, onImported = async () => {} } = $props()

  let includeMovements = $state(false)
  let exporting = $state(false)
  let importing = $state(false)
  let importInput = $state(null)

  function backupFilename() {
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
    return `holzlinge-backup-${stamp}.json`
  }

  function downloadJson(data) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = backupFilename()
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  async function handleExport() {
    exporting = true
    try {
      const data = await api.backup.export(includeMovements)
      downloadJson(data)
      onFlash('ok', 'Datensicherung wurde heruntergeladen.')
    } catch (error) {
      onFlash('error', error.message || 'Export fehlgeschlagen.')
    } finally {
      exporting = false
    }
  }

  function openImportPicker() {
    importInput?.click()
  }

  async function handleImportFile(event) {
    const file = event.currentTarget.files?.[0]
    event.currentTarget.value = ''
    if (!file) return

    let backup
    try {
      const text = await file.text()
      backup = JSON.parse(text)
    } catch {
      onFlash('error', 'Die Datei ist keine gültige JSON-Sicherung.')
      return
    }

    const mergeOk = confirm(
      'Daten zusammenführen?\n\n' +
        'Bestehende Einträge werden anhand von Name bzw. SKU/Handle/Farbe+Medium abgeglichen. ' +
        'Fehlende werden angelegt, Stammdaten aktualisiert. Bestände je Standort werden beim Match gesetzt (nicht addiert).\n\n' +
        'Mit „Abbrechen“ können Sie stattdessen „Ersetzen“ wählen.',
    )
    if (mergeOk) {
      await runImport('merge', backup)
      return
    }

    const replaceOk = confirm(
      'Alle bestehenden Daten ersetzen?\n\n' +
        'WARNUNG: Der gesamte App-Stand wird durch die Sicherung ersetzt. ' +
        'Bestellungen und Todos sind nicht in der JSON-Datei und werden mitgelöscht. ' +
        'Dies kann nicht rückgängig gemacht werden.\n\n' +
        'Wirklich fortfahren?',
    )
    if (!replaceOk) return
    await runImport('replace', backup)
  }

  async function runImport(mode, backup) {
    importing = true
    try {
      await api.backup.import(mode, backup)
      await onImported()
      onFlash('ok', mode === 'replace' ? 'Daten wurden ersetzt.' : 'Daten wurden zusammengeführt.')
    } catch (error) {
      onFlash('error', error.message || 'Import fehlgeschlagen.')
    } finally {
      importing = false
    }
  }
</script>

<section class="panel backup-panel">
  <div class="panel-header">
    <h2>Sicherung</h2>
  </div>
  <p class="empty" style="margin-top:0">
    Vollständiger App-Stand als JSON-Datei exportieren oder wiederherstellen. Kein Ersatz für Host-Backups der Datenbank.
  </p>
  <div class="filter-bar form-grid backup-actions">
    <label class="backup-checkbox">
      <input type="checkbox" bind:checked={includeMovements} />
      Bewegungs-Historie einschließen
    </label>
    <div class="row-actions">
      <button class="btn secondary" disabled={exporting || importing} onclick={handleExport}>
        {exporting ? 'Exportiere…' : 'Daten exportieren'}
      </button>
      <button class="btn secondary" disabled={exporting || importing} onclick={openImportPicker}>
        {importing ? 'Importiere…' : 'Daten importieren'}
      </button>
      <input
        bind:this={importInput}
        type="file"
        accept=".json,application/json"
        hidden
        onchange={handleImportFile}
      />
    </div>
  </div>
</section>

<style>
  .backup-panel {
    margin-top: 1rem;
  }

  .backup-actions {
    align-items: end;
  }

  .backup-checkbox {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    margin: 0;
  }

  .backup-checkbox input {
    width: auto;
    margin: 0;
  }
</style>
