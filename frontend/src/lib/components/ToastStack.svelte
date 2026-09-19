<script>
  /** @typedef {{ id: number, type: string, message: string, at: number, goTo?: { tab?: string, run?: () => void | Promise<void> } }} Toast */

  /** @type {{ toasts?: Toast[], onDismiss?: (id: number) => void, onGoTo?: (toast: Toast) => void | Promise<void> }} */
  let { toasts = [], onDismiss = () => {}, onGoTo = async () => {} } = $props()

  function formatTime(at) {
    try {
      return new Date(at).toLocaleTimeString('de-DE', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    } catch {
      return ''
    }
  }

  async function handleClick(toast) {
    if (toast.goTo) {
      const go = window.confirm('Zur Stelle?')
      if (go) await onGoTo(toast)
    }
    onDismiss(toast.id)
  }
</script>

{#if toasts.length}
  <div class="toast-stack" aria-live="polite" aria-relevant="additions">
    {#each toasts as toast (toast.id)}
      <button
        type="button"
        class={`toast flash ${toast.type}`}
        onclick={() => handleClick(toast)}
      >
        <span class="toast-message">{toast.message}</span>
        <span class="toast-meta">
          <time datetime={new Date(toast.at).toISOString()}>{formatTime(toast.at)}</time>
          {#if toast.goTo}
            <span class="toast-hint">· Zur Stelle?</span>
          {:else}
            <span class="toast-hint">· tippen zum Schließen</span>
          {/if}
        </span>
      </button>
    {/each}
  </div>
{/if}
