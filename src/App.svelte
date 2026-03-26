<script lang="ts">
  import { onMount } from 'svelte';
  import { writable, get } from 'svelte/store';
  import { fade, fly, scale } from 'svelte/transition';
  import { expoOut, backOut } from 'svelte/easing';
  import NoteList from './components/NoteList.svelte';
  import NoteForm from './components/NoteForm.svelte';
  import Search from './components/Search.svelte';
  import { updateNote } from './lib/api';
  import type { Note } from './lib/api';

  // --- State Management ---
  const notes = writable<Note[]>([]);
  const searchQuery = writable('');
  const sortBy = writable<'createdAt' | 'title' | 'id'>('createdAt');
  
  // High-Contrast Theme State
  let isDark = localStorage.getItem('theme') === 'dark';
  
  // Colors defined as constants for easy adjustment
  $: bgClass = isDark ? 'bg-[#001233]' : 'bg-[#FFFFFF]'; // Deep Blue vs Pure White
  $: cardClass = isDark ? 'bg-[#001d4a] border-[#002855]' : 'bg-[#F8FAFC] border-slate-200';
  $: textClass = isDark ? 'text-blue-50' : 'text-slate-900';

  function toggleTheme() {
    isDark = !isDark;
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
  }

  // --- AI Logic (Hand Tracking) ---
  let cameraActive = false;
  let videoEl: HTMLVideoElement | null = null;
  let handTracker: any = null;
  let cameraController: any = null;
  let palmActive = false;
  let draggedNote: Note | null = null;
  let draggedNotePosition = { x: 0, y: 0 };
  let lerpX = 0, lerpY = 0;

  notes.subscribe($n => localStorage.setItem('notes', JSON.stringify($n)));

  function onHandResults(results: any) {
    const landmarks = results.multiHandLandmarks?.[0];
    if (!landmarks) { palmActive = false; return; }

    const rawX = (1 - landmarks[9].x) * window.innerWidth;
    const rawY = landmarks[9].y * window.innerHeight;
    lerpX += (rawX - lerpX) * 0.25;
    lerpY += (rawY - lerpY) * 0.25;

    const isGrabbing = landmarks[8].y > landmarks[5].y;
    palmActive = isGrabbing;

    if (isGrabbing) {
      if (!draggedNote) {
        const elements = document.querySelectorAll('[data-note-id]');
        for (const el of elements) {
          const rect = el.getBoundingClientRect();
          if (lerpX > rect.left && lerpX < rect.right && lerpY > rect.top && lerpY < rect.bottom) {
            const id = parseInt(el.getAttribute('data-note-id') || '0');
            draggedNote = get(notes).find(n => n.id === id) || null;
            if (draggedNote) break;
          }
        }
      }
      draggedNotePosition = { x: lerpX, y: lerpY };
    } else if (draggedNote) {
      const id = draggedNote.id;
      notes.update(list => list.map(n => n.id === id ? { ...n, x: lerpX, y: lerpY } : n));
      updateNote(id, { x: lerpX, y: lerpY });
      draggedNote = null;
    }
  }

  async function startAI() {
    if (cameraActive) return stopAI();
    if (!(window as any).Hands) {
      const load = (src: string) => new Promise(res => {
        const s = document.createElement('script');
        s.src = src; s.onload = res; document.head.appendChild(s);
      });
      await load('https://cdn.jsdelivr.net/npm/@mediapipe/hands/hands.js');
      await load('https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js');
    }
    handTracker = new (window as any).Hands({ locateFile: (f: string) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${f}` });
    handTracker.setOptions({ selfieMode: true, maxNumHands: 1, modelComplexity: 1 });
    handTracker.onResults(onHandResults);
    cameraController = new (window as any).Camera(videoEl, {
      onFrame: async () => { if (cameraActive) await handTracker.send({ image: videoEl }); },
      width: 1280, height: 720
    });
    cameraController.start();
    cameraActive = true;
  }

  function stopAI() {
    cameraController?.stop();
    (videoEl?.srcObject as MediaStream)?.getTracks().forEach(t => t.stop());
    cameraActive = false;
    draggedNote = null;
  }

  onMount(() => {
    const local = localStorage.getItem('notes');
    if (local) notes.set(JSON.parse(local));
  });
</script>

<main class="relative min-h-screen {bgClass} {textClass} transition-colors duration-1000 overflow-hidden font-sans">
  
  <div class="fixed inset-0 pointer-events-none">
    <div class="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] {isDark ? 'bg-blue-400/20' : 'bg-indigo-500/10'} blur-[120px] rounded-full"></div>
    <div class="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] {isDark ? 'bg-cyan-400/20' : 'bg-purple-500/10'} blur-[120px] rounded-full"></div>
  </div>

  <video 
    bind:this={videoEl} 
    class="fixed inset-0 w-full h-full object-cover opacity-[0.1] {isDark ? 'brightness-150' : 'grayscale'} pointer-events-none z-0" 
    class:hidden={!cameraActive} 
    autoplay playsinline muted>
  </video>

  {#if cameraActive}
    <div 
      in:scale={{ duration: 400, easing: backOut }}
      class="fixed z-[999] pointer-events-none flex items-center justify-center transition-transform duration-75"
      style="left: {lerpX}px; top: {lerpY}px; transform: translate(-50%, -50%);"
    >
      <div class="w-10 h-10 border-4 {palmActive ? 'border-cyan-400 scale-125 bg-cyan-400/20' : 'border-white/40 bg-white/10'} rounded-full shadow-[0_0_40px_rgba(255,255,255,0.2)] transition-all"></div>
    </div>
  {/if}

  <div class="relative z-10 flex flex-col h-screen">
    
    <header in:fly={{ y: -50, duration: 800, easing: expoOut }} 
            class="px-10 py-6 flex justify-between items-center border-b {isDark ? 'border-blue-800/50' : 'border-slate-200'} backdrop-blur-2xl {isDark ? 'bg-blue-950/40' : 'bg-white/40'} sticky top-0 shadow-sm">
      <div class="flex items-center gap-4">
        <div class="w-10 h-10 bg-blue-600 rounded-2xl flex items-center justify-center shadow-xl shadow-blue-500/40 rotate-[-4deg]">
          <span class="text-white font-black text-2xl uppercase">N</span>
        </div>
        <h1 class="text-2xl font-black tracking-tighter uppercase">Notely <span class="text-blue-500">AI</span></h1>
      </div>

      <div class="flex items-center gap-6">
        <button 
          on:click={toggleTheme} 
          class="p-3 rounded-2xl transition-all active:scale-75 shadow-lg {isDark ? 'bg-blue-800 text-yellow-400 border-blue-700' : 'bg-slate-100 text-blue-600 border-slate-200'} border"
        >
          {#if isDark}
            <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" viewBox="0 0 24 24" fill="currentColor"><path d="M12 7a5 5 0 1 1-4.99 5.002A5 5 0 0 1 12 7zM2 13h2a1 1 0 0 0 0-2H2a1 1 0 0 0 0 2zm18 0h2a1 1 0 0 0 0-2h-2a1 1 0 0 0 0 2zM11 2v2a1 1 0 0 0 2 0V2a1 1 0 0 0-2 0zm0 18v2a1 1 0 0 0 2 0v-2a1 1 0 0 0-2 0zM5.989 4.575a1 1 0 1 0-1.414 1.414l1.414 1.415a1 1 0 1 0 1.414-1.414l-1.414-1.415zm13.435 13.435a1 1 0 1 0-1.414 1.414l1.414 1.415a1 1 0 1 0 1.414-1.414l-1.414-1.415z"/></svg>
          {:else}
            <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" viewBox="0 0 24 24" fill="currentColor"><path d="M12.3 22h-.1c-5.5 0-10-4.5-10-10s4.5-10 10-10c.5 0 1 .1 1.5.2.6.1 1 .7.9 1.3-.1.6-.7 1-1.3.9-.4-.1-.7-.1-1.1-.1-4.4 0-8 3.6-8 8s3.6 8 8 8c.4 0 .8 0 1.2-.1.6-.1 1.2.3 1.3.9s-.3 1.2-.9 1.3c-.5.1-1 .1-1.5.1z"/></svg>
          {/if}
        </button>
        
        <button 
          on:click={startAI} 
          class="px-8 py-3 rounded-2xl font-black text-sm tracking-widest transition-all active:scale-95 shadow-2xl {cameraActive ? 'bg-red-500 text-white shadow-red-500/30' : 'bg-blue-600 text-white shadow-blue-500/40'}"
        >
          {cameraActive ? 'SHUTDOWN AI' : 'INITIALIZE AI'}
        </button>
      </div>
    </header>

    <div class="flex-1 overflow-y-auto px-10 py-12 max-w-7xl mx-auto w-full">
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-12">
        
        <div in:fly={{ x: -40, duration: 1000, delay: 200 }} class="lg:col-span-4 space-y-10">
          <section class="p-8 rounded-[2.5rem] {cardClass} shadow-2xl transition-all duration-700">
            <h3 class="text-[10px] font-black uppercase tracking-[0.4em] text-blue-500 mb-8">Data Input</h3>
            <NoteForm on:created={(e) => notes.update(n => [e.detail.note, ...n])} />
          </section>
          
          <section class="p-8 rounded-[2.5rem] {cardClass} shadow-2xl transition-all duration-700">
            <h3 class="text-[10px] font-black uppercase tracking-[0.4em] text-blue-500 mb-8">System Search</h3>
            <Search {searchQuery} />
          </section>
        </div>

        <div in:fly={{ y: 50, duration: 1000, delay: 400 }} class="lg:col-span-8">
          <div class="flex items-center justify-between mb-10">
            <h2 class="text-4xl font-black tracking-tighter uppercase">Workspace</h2>
            <span class="px-5 py-2 rounded-2xl {isDark ? 'bg-blue-500/20 text-blue-300' : 'bg-blue-50 text-blue-600'} text-xs font-black uppercase tracking-widest">
              {get(notes).length} Objects Loaded
            </span>
          </div>
          <NoteList {notes} {searchQuery} {sortBy} {draggedNote} />
        </div>

      </div>
    </div>
  </div>

  {#if draggedNote}
    <div 
      class="fixed z-[1000] pointer-events-none w-80 p-8 {isDark ? 'bg-blue-900/90' : 'bg-white/95'} backdrop-blur-3xl rounded-[3rem] shadow-[0_60px_120px_-20px_rgba(30,58,138,0.6)] border-4 border-cyan-400/50"
      style="left: {draggedNotePosition.x}px; top: {draggedNotePosition.y}px; transform: translate(-50%, -50%) rotate(4deg) scale(1.15);"
    >
      <div class="flex items-center gap-2 mb-4">
        <div class="w-3 h-3 rounded-full bg-cyan-400 animate-ping"></div>
        <span class="text-[9px] font-black uppercase tracking-widest text-cyan-400">Syncing Spatial Data...</span>
      </div>
      <h2 class="text-2xl font-black leading-tight mb-2 uppercase">{draggedNote.title}</h2>
      <p class="text-sm opacity-60 line-clamp-3">{draggedNote.content}</p>
    </div>
  {/if}
</main>

<style>
  :global(body) { 
    margin: 0; 
    padding: 0;
    overflow: hidden;
    font-family: 'Inter', sans-serif;
  }

  /* Force the background to match the state immediately */
  :global(html) {
    background-color: #f8fafc;
  }
  :global(html.dark) {
    background-color: #001233;
  }
</style>