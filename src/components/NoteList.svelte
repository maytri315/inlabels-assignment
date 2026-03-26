<script lang="ts">
  import { onMount, createEventDispatcher } from 'svelte';
  import NoteItem from './NoteItem.svelte';
  import LoadingSkeleton from './LoadingSkeleton.svelte';
  import { getNotes, type Note } from '../lib/api';

  export let notes: import('svelte/store').Writable<Note[]>;
  export let searchQuery: import('svelte/store').Writable<string>;
  export let sortBy: import('svelte/store').Writable<'createdAt' | 'title' | 'id'>;
  export let draggedNote: Note | null = null;

  let loading = false;
  let page = 1;
  let hasMore = true;
  let observer: IntersectionObserver;
  const dispatch = createEventDispatcher();

  // FIX: Use loose inequality (!= null) to catch both undefined and null
  $: flowNotes = $notes ? $notes.filter(n => n.x == null || n.y == null) : [];
  $: positionedNotes = $notes ? $notes.filter(n => n.x != null && n.y != null) : [];

  onMount(async () => {
    await loadNotes(true);
    setupInfiniteScroll();
  });

  async function loadNotes(reset = false) {
    if (reset) { page = 1; hasMore = true; }
    loading = true;
    try {
      const newNotes = await getNotes(page, 20, $searchQuery, $sortBy, $sortBy === 'title' ? 'asc' : 'desc');
      
      // Preserve local positions
      const localNotes = JSON.parse(localStorage.getItem('notes') || '[]') as Note[];
      const posMap = new Map(localNotes.filter(n => n.x != null).map(n => [String(n.id), n]));

      const merged = newNotes.map(apiNote => {
        const pos = posMap.get(String(apiNote.id));
        return pos ? { ...apiNote, x: pos.x, y: pos.y } : apiNote;
      });

      if (merged.length < 20) hasMore = false;
      notes.update(n => {
        const combined = reset ? merged : [...n, ...merged];
        return combined.sort((a, b) => {
          if (a.pinned && !b.pinned) return -1;
          if (!a.pinned && b.pinned) return 1;
          return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
        });
      });
      page++;
    } catch (e) { console.error(e); }
    loading = false;
  }

  function setupInfiniteScroll() {
    const sentinel = document.getElementById('sentinel');
    if (sentinel) {
      observer = new IntersectionObserver(async (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading) await loadNotes();
      });
      observer.observe(sentinel);
    }
  }

  function handleUpdated(event: CustomEvent) {
    notes.update(n => n.map(item => item.id === event.detail.note.id ? event.detail.note : item));
  }

  $: if ($searchQuery !== undefined) loadNotes(true);
</script>

<div class="relative min-h-screen">
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
    {#each flowNotes as note (note.id ?? note.createdAt)}
      <div 
        data-note-id={note.id} 
        class="transition-opacity"
        style={draggedNote?.id === note.id ? 'opacity: 0.2' : 'opacity: 1'}
      >
        <NoteItem {note} on:updated={handleUpdated} on:delete />
      </div>
    {/each}
    
    {#if loading}
      {#each Array(3) as _} <LoadingSkeleton /> {/each}
    {/if}
  </div>

  {#each positionedNotes as note (note.id ?? note.createdAt)}
    <div
      data-note-id={note.id}
      class="fixed z-20 w-[300px] transition-opacity shadow-xl"
      style="left: {note.x}px; top: {note.y}px; {draggedNote?.id === note.id ? 'opacity: 0.2' : 'opacity: 1'}"
    >
      <NoteItem {note} on:updated={handleUpdated} on:delete />
    </div>
  {/each}
</div>

{#if hasMore} <div id="sentinel" class="h-20"></div> {/if}