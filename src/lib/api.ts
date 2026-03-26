const API_BASE = 'https://69bee93d17c3d7d97793516a.mockapi.io/notes'; // Replace with your mockapi URL
const PENDING_KEY = 'pendingOperations';

type PendingOperation =
  | { type: 'create'; payload: Omit<Note, 'id' | 'createdAt'> }
  | { type: 'update'; id: number | string; payload: Partial<Note> }
  | { type: 'delete'; id: number | string };

export interface Note {
  id: number | string;
  title: string;
  content: string;
  createdAt: string;
  pinned?: boolean;
  x?: number;
  y?: number;
}

export async function getNotes(page = 1, limit = 20, search = '', sortBy = 'createdAt', order = 'desc'): Promise<Note[]> {
  const params = new URLSearchParams({
    page: page.toString(),
    limit: limit.toString(),
    sortBy,
    order,
  });
  if (search) params.append('search', search);
  try {
    const res = await fetch(`${API_BASE}?${params}`);
    if (!res.ok) throw new Error('Failed to fetch notes');
    return res.json();
  } catch (error) {
    console.error(error);
    // load from localStorage
    const local = localStorage.getItem('notes');
    return local ? JSON.parse(local) as Note[] : [];
  }
}

export async function createNote(note: Omit<Note, 'id' | 'createdAt'>): Promise<Note> {
  const newNote = { ...note, createdAt: new Date().toISOString() };
  try {
    const res = await fetch(API_BASE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newNote),
    });
    if (!res.ok) throw new Error('Failed to create note');
    const created = await res.json();
    saveToLocal(created);
    return created;
  } catch (error) {
    console.error(error);
    queueOperation({ type: 'create', payload: note });
    // optimistic, save locally
    const localNotes = JSON.parse(localStorage.getItem('notes') || '[]') as Note[];
    const id = Date.now(); // temp id
    const tempNote = { ...newNote, id };
    localNotes.push(tempNote);
    localStorage.setItem('notes', JSON.stringify(localNotes));
    return tempNote;
  }
}

export async function updateNote(id: number | string, updates: Partial<Note>): Promise<Note> {
  try {
    const res = await fetch(`${API_BASE}/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    if (!res.ok) throw new Error('Failed to update note');
    const updated = await res.json();
    saveToLocal(updated);
    return updated;
  } catch (error) {
    console.error(error);
    queueOperation({ type: 'update', id, payload: updates });
    // optimistic update local
    const localNotes = JSON.parse(localStorage.getItem('notes') || '[]') as Note[];
    const index = localNotes.findIndex((n: Note) => n.id === id);
    if (index !== -1) {
      localNotes[index] = { ...localNotes[index], ...updates };
      localStorage.setItem('notes', JSON.stringify(localNotes));
    }
    return localNotes[index];
  }
}

export async function deleteNote(id: number | string): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete note');
    removeFromLocal(id);
  } catch (error) {
    console.error(error);
    queueOperation({ type: 'delete', id });
    // optimistic delete local
    removeFromLocal(id);
  }
}

function queueOperation(op: PendingOperation) {
  const pending = JSON.parse(localStorage.getItem(PENDING_KEY) || '[]') as PendingOperation[];
  pending.push(op);
  localStorage.setItem(PENDING_KEY, JSON.stringify(pending));
}

export async function syncPendingOperations() {
  const pending = JSON.parse(localStorage.getItem(PENDING_KEY) || '[]') as PendingOperation[];
  const remaining: PendingOperation[] = [];

  for (const op of pending) {
    try {
      if (op.type === 'create') {
        await createNote(op.payload);
      } else if (op.type === 'update') {
        await updateNote(op.id, op.payload);
      } else if (op.type === 'delete') {
        await deleteNote(op.id);
      }
    } catch {
      remaining.push(op);
    }
  }

  localStorage.setItem(PENDING_KEY, JSON.stringify(remaining));
  return remaining.length === 0;
}

function saveToLocal(note: Note) {
  const localNotes = JSON.parse(localStorage.getItem('notes') || '[]') as Note[];
  const index = localNotes.findIndex((n: Note) => n.id === note.id);
  if (index !== -1) {
    localNotes[index] = note;
  } else {
    localNotes.push(note);
  }
  localStorage.setItem('notes', JSON.stringify(localNotes));
}

function removeFromLocal(id: number | string) {
  const localNotes = JSON.parse(localStorage.getItem('notes') || '[]') as Note[];
  const filtered = localNotes.filter((n: Note) => n.id !== id);
  localStorage.setItem('notes', JSON.stringify(filtered));
}