<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { createNote } from '../lib/api';

  let title = '';
  let content = '';
  let submitting = false;

  const dispatch = createEventDispatcher();

  async function handleSubmit() {
    if (!title.trim() || !content.trim()) return;
    submitting = true;
    try {
      const newNote = await createNote({ title: title.trim(), content: content.trim() });
      dispatch('created', { note: newNote });
      title = '';
      content = '';
    } catch (error) {
      console.error(error);
    }
    submitting = false;
  }
</script>

<form on:submit|preventDefault={handleSubmit} class="mb-4 p-4 bg-white dark:bg-gray-800 rounded shadow">
  <input bind:value={title} placeholder="Title" class="w-full p-2 mb-2 border rounded dark:bg-gray-700 dark:border-gray-600" required maxlength="100" />
  <textarea bind:value={content} placeholder="Content" class="w-full p-2 mb-2 border rounded dark:bg-gray-700 dark:border-gray-600" required maxlength="500"></textarea>
  <button type="submit" disabled={submitting} class="bg-blue-500 text-white px-4 py-2 rounded disabled:opacity-50">
    {#if submitting} Creating... {:else} Create Note {/if}
  </button>
</form>