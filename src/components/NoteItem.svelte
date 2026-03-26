<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { updateNote, type Note } from '../lib/api';

  export let note: Note;
  // New prop to handle visual state during hand-drag
  export let isDragged = false; 

  let editing = false;
  let editTitle = note.title;
  let editContent = note.content;
  let saving = false;

  const dispatch = createEventDispatcher();

  async function handleSave() {
    if (note.id === undefined || note.id === null) {
      console.error('Cannot save note with undefined ID', note);
      return;
    }

    saving = true;
    try {
      const updated = await updateNote(note.id, { title: editTitle, content: editContent });
      dispatch('updated', { note: updated });
      editing = false;
    } catch (error) {
      console.error(error);
    }
    saving = false;
  }

  function handleDelete() {
    dispatch('delete', { id: note.id });
  }

  function handleEdit() {
    editing = true;
  }

  async function togglePin() {
    if (note.id === undefined || note.id === null) {
      console.error('Cannot toggle pin for note with undefined ID', note);
      return;
    }

    const updated = await updateNote(note.id, { pinned: !note.pinned });
    dispatch('updated', { note: updated });
  }
</script>

<div 
  data-note-id={note.id}
  class="p-4 bg-white dark:bg-gray-800 rounded shadow transition-opacity duration-200 {note.pinned ? 'border-l-4 border-yellow-500' : ''}"
  style:opacity={isDragged ? '0.2' : '1'}
>
  {#if editing}
    <input bind:value={editTitle} class="w-full p-2 mb-2 border rounded dark:bg-gray-700 dark:border-gray-600" />
    <textarea bind:value={editContent} class="w-full p-2 mb-2 border rounded dark:bg-gray-700 dark:border-gray-600"></textarea>
    <div class="flex gap-2">
      <button on:click={handleSave} disabled={saving} class="bg-green-500 text-white px-2 py-1 rounded disabled:opacity-50">Save</button>
      <button on:click={() => editing = false} class="bg-gray-500 text-white px-2 py-1 rounded">Cancel</button>
    </div>
  {:else}
    <div class="flex justify-between items-start mb-2">
      <h3 class="font-bold truncate pr-2">{note.title}</h3>
      <button on:click={togglePin} class="text-yellow-500 hover:scale-110 transition-transform">
        {note.pinned ? '📌' : '📍'}
      </button>
    </div>
    <p class="mb-2 text-gray-700 dark:text-gray-300 break-words">{note.content}</p>
    <p class="text-[10px] text-gray-400 dark:text-gray-500 mb-4">{new Date(note.createdAt).toLocaleString()}</p>
    
    <div class="flex gap-2">
      <button on:click={handleEdit} class="bg-yellow-500 text-white text-xs px-3 py-1 rounded hover:bg-yellow-600">Edit</button>
      <button on:click={handleDelete} class="bg-red-500 text-white text-xs px-3 py-1 rounded hover:bg-red-600">Delete</button>
    </div>
  {/if}
</div>