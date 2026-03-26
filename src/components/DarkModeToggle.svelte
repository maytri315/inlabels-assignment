<script lang="ts">
  export let darkMode: import('svelte/store').Writable<boolean>;

  function toggle() {
    darkMode.update(d => {
      const newVal = !d;
      document.documentElement.classList.toggle('dark', newVal);
      localStorage.setItem('darkMode', newVal.toString());
      return newVal;
    });
  }
</script>

<button on:click={toggle} class="p-2 bg-gray-200 dark:bg-gray-700 rounded">
  {#if $darkMode} 🌙 {:else} ☀️ {/if}
</button>