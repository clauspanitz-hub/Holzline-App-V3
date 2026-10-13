<script>
  import { onMount } from 'svelte'
  import { api, formatDateTime } from '../api.js'

  let {
    compact = false,
    onError = (_msg) => {},
  } = $props()

  /** @type {{ id: number, text: string, author: string, created_at: string, updated_at?: string|null }[]} */
  let messages = $state([])
  let noteBody = $state('')
  let noteDirty = $state(false)
  let noteSaving = $state(false)
  let loading = $state(true)
  let author = $state(/** @type {'claus'|'simona'} */ ('claus'))
  let draft = $state('')
  let sending = $state(false)
  /** @type {number|null} */
  let editingId = $state(null)
  let editText = $state('')
  let listEl = $state(/** @type {HTMLElement|null} */ (null))
  /** @type {ReturnType<typeof setTimeout>|null} */
  let noteTimer = null

  const AUTHOR_LABEL = { claus: 'Claus', simona: 'Simona' }

  async function load() {
    loading = true
    try {
      const [msgs, note] = await Promise.all([api.team.messages(), api.team.getNote()])
      messages = msgs || []
      if (!noteDirty) noteBody = note?.body ?? ''
      queueMicrotask(() => scrollToBottom())
    } catch (e) {
      onError(e.message || 'Pinnwand laden fehlgeschlagen')
    } finally {
      loading = false
    }
  }

  function scrollToBottom() {
    if (listEl) listEl.scrollTop = listEl.scrollHeight
  }

  async function sendMessage() {
    const text = draft.trim()
    if (!text || sending) return
    sending = true
    try {
      const created = await api.team.createMessage({ text, author })
      messages = [...messages, created]
      draft = ''
      queueMicrotask(() => scrollToBottom())
    } catch (e) {
      onError(e.message || 'Senden fehlgeschlagen')
    } finally {
      sending = false
    }
  }

  function startEdit(msg) {
    editingId = msg.id
    editText = msg.text
  }

  function cancelEdit() {
    editingId = null
    editText = ''
  }

  async function saveEdit() {
    if (editingId == null) return
    const text = editText.trim()
    if (!text) return
    try {
      const updated = await api.team.updateMessage(editingId, { text })
      messages = messages.map((m) => (m.id === updated.id ? updated : m))
      cancelEdit()
    } catch (e) {
      onError(e.message || 'Bearbeiten fehlgeschlagen')
    }
  }

  async function removeMessage(id) {
    if (!confirm('Nachricht löschen?')) return
    try {
      await api.team.deleteMessage(id)
      messages = messages.filter((m) => m.id !== id)
      if (editingId === id) cancelEdit()
    } catch (e) {
      onError(e.message || 'Löschen fehlgeschlagen')
    }
  }

  function scheduleNoteSave() {
    noteDirty = true
    if (noteTimer) clearTimeout(noteTimer)
    noteTimer = setTimeout(() => saveNote(), 600)
  }

  async function saveNote() {
    if (noteTimer) {
      clearTimeout(noteTimer)
      noteTimer = null
    }
    noteSaving = true
    try {
      const saved = await api.team.putNote({ body: noteBody })
      noteBody = saved.body
      noteDirty = false
    } catch (e) {
      onError(e.message || 'Notiz speichern fehlgeschlagen')
    } finally {
      noteSaving = false
    }
  }

  onMount(() => {
    load()
    return () => {
      if (noteTimer) clearTimeout(noteTimer)
    }
  })
</script>

<div class="team-pinboard" class:compact>
  <section class="team-messages" aria-label="Team-Nachrichten">
    <header class="team-section-head">
      <h3>Pinnwand</h3>
      <button type="button" class="btn secondary team-refresh" disabled={loading} onclick={load}>
        Aktualisieren
      </button>
    </header>

    <div class="team-message-list" bind:this={listEl}>
      {#if loading && !messages.length}
        <p class="empty">Lade…</p>
      {:else if !messages.length}
        <p class="empty">Noch keine Nachrichten.</p>
      {:else}
        {#each messages as msg (msg.id)}
          <article class="team-message" class:editing={editingId === msg.id}>
            <div class="team-message-meta">
              <strong>{AUTHOR_LABEL[msg.author] || msg.author}</strong>
              <time datetime={msg.created_at}>{formatDateTime(msg.created_at)}</time>
              {#if msg.updated_at}
                <span class="empty">bearbeitet</span>
              {/if}
            </div>
            {#if editingId === msg.id}
              <textarea rows="3" bind:value={editText}></textarea>
              <div class="team-message-actions">
                <button type="button" class="btn" onclick={saveEdit}>Speichern</button>
                <button type="button" class="btn secondary" onclick={cancelEdit}>Abbrechen</button>
              </div>
            {:else}
              <p class="team-message-text">{msg.text}</p>
              <div class="team-message-actions">
                <button type="button" class="btn secondary" onclick={() => startEdit(msg)}>Bearbeiten</button>
                <button type="button" class="btn danger" onclick={() => removeMessage(msg.id)}>Löschen</button>
              </div>
            {/if}
          </article>
        {/each}
      {/if}
    </div>

    <form
      class="team-composer"
      onsubmit={(e) => {
        e.preventDefault()
        sendMessage()
      }}
    >
      <div class="team-author-switch" role="group" aria-label="Absender">
        <button
          type="button"
          class="team-author-btn"
          class:active={author === 'claus'}
          aria-pressed={author === 'claus'}
          onclick={() => (author = 'claus')}
        >
          Claus
        </button>
        <button
          type="button"
          class="team-author-btn"
          class:active={author === 'simona'}
          aria-pressed={author === 'simona'}
          onclick={() => (author = 'simona')}
        >
          Simona
        </button>
      </div>
      <textarea
        rows="2"
        placeholder="Nachricht…"
        bind:value={draft}
        onkeydown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            sendMessage()
          }
        }}
      ></textarea>
      <button type="submit" class="btn" disabled={sending || !draft.trim()}>Senden</button>
    </form>
  </section>

  <section class="team-notes" aria-label="Gemeinsame Notizen">
    <header class="team-section-head">
      <h3>Notizen</h3>
      <span class="empty">{noteSaving ? 'Speichern…' : noteDirty ? '…' : 'gemeinsam'}</span>
    </header>
    <textarea
      class="team-note-pad"
      rows="6"
      placeholder="Gemeinsames Scratchpad…"
      bind:value={noteBody}
      oninput={scheduleNoteSave}
      onblur={() => {
        if (noteDirty) saveNote()
      }}
    ></textarea>
  </section>
</div>

<style>
  .team-pinboard {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    min-height: 0;
    height: 100%;
  }

  .team-messages {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    flex: 1 1 58%;
    min-height: 0;
  }

  .team-notes {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    flex: 0 0 auto;
  }

  .team-section-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .team-section-head h3 {
    margin: 0;
    font-family: var(--display);
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--forest);
  }

  .team-refresh {
    padding: 0.25rem 0.55rem;
    font-size: 0.8rem;
  }

  .team-message-list {
    flex: 1 1 auto;
    min-height: 8rem;
    max-height: none;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    padding-right: 0.15rem;
  }

  .team-message {
    padding: 0.45rem 0.15rem 0.55rem;
    border-bottom: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  }

  .team-message-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 0.65rem;
    font-size: 0.78rem;
    color: var(--muted);
    margin-bottom: 0.2rem;
  }

  .team-message-meta strong {
    color: var(--forest);
  }

  .team-message-text {
    margin: 0 0 0.35rem;
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.35;
  }

  .team-message-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .team-message-actions .btn {
    padding: 0.25rem 0.55rem;
    font-size: 0.78rem;
  }

  .team-composer {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    padding-top: 0.25rem;
  }

  .team-author-switch {
    display: flex;
    gap: 0.35rem;
  }

  .team-author-btn {
    border: 1px solid var(--line);
    background: var(--bg-elevated);
    color: var(--forest);
    border-radius: var(--radius);
    padding: 0.3rem 0.7rem;
    font-weight: 700;
    font-size: 0.85rem;
  }

  .team-author-btn.active {
    background: var(--forest);
    color: var(--accent-ink);
    border-color: var(--forest);
  }

  .team-composer textarea,
  .team-message textarea,
  .team-note-pad {
    width: 100%;
    resize: vertical;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: var(--field-bg);
    color: var(--field-ink);
    padding: 0.5rem 0.65rem;
    font: inherit;
  }

  .team-note-pad {
    min-height: 7rem;
  }
</style>
