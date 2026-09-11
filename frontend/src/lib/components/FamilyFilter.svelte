<script>
  /** @type {{ families?: string[], value?: string }} */
  let { families = [], value = $bindable('') } = $props()
</script>

<label>Filter Familie
  <select bind:value>
    <option value="">alle</option>
    {#each families as family (family)}
      <option value={family}>{family}</option>
    {/each}
  </select>
</label>
