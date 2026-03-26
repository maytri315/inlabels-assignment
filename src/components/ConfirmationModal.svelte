<script lang="ts">
  export let show = false;
  export let message = '';
  export let onConfirm: () => void;
  export let onCancel: () => void;
</script>

{#if show}
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="bg-white dark:bg-gray-800 p-4 rounded shadow">
      <p class="mb-4">{message}</p>
      <button on:click={onConfirm} class="bg-red-500 text-white px-4 py-2 rounded mr-2">Confirm</button>
      <button on:click={onCancel} class="bg-gray-500 text-white px-4 py-2 rounded">Cancel</button>
    </div>
  </div>
{/if}