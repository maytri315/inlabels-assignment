<script lang="ts">
  import { onDestroy } from 'svelte';
  import { writable } from 'svelte/store';

  type WritableStore<T> = ReturnType<typeof writable<T>>;
  type ToastType = {id: number, message: string, type: 'success' | 'error' | 'info', action?: {label: string, callback: () => void}};

  export let toasts: WritableStore<ToastType[]>;

  let timeouts: number[] = [];

  function removeToast(id: number) {
    toasts.update(t => t.filter(toast => toast.id !== id));
  }

  onDestroy(() => {
    timeouts.forEach(clearTimeout);
  });
</script>

<div class="fixed bottom-4 right-4 space-y-2 z-40">
  {#each $toasts as toast (toast.id)}
    <div class="text-white p-3 rounded shadow flex items-center justify-between" class:bg-green-500={toast.type === 'success'} class:bg-red-500={toast.type === 'error'} class:bg-blue-500={toast.type === 'info'}>
      <span>{toast.message}</span>
      {#if toast.action}
        <button on:click={() => { toast.action?.callback(); removeToast(toast.id); }} class="ml-2 underline">{toast.action.label}</button>
      {/if}
      <button on:click={() => removeToast(toast.id)} class="ml-2">×</button>
    </div>
  {/each}
</div>