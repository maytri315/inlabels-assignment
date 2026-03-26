<script lang="ts">
  import { debounce } from '../lib/utils';

  export let searchQuery: import('svelte/store').Writable<string>;

  let query = '';

  const debouncedUpdate = debounce((value: string) => {
    searchQuery.set(value);
  }, 300);

  $: debouncedUpdate(query);
</script>

<input bind:value={query} placeholder="Search notes..." class="w-full p-2 border rounded dark:bg-gray-800 dark:border-gray-600" />