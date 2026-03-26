# Notes App

A simple web application for managing notes, built with Svelte and TailwindCSS.

## Features

- View, create, update, and delete notes
- Responsive design
- Dark mode toggle
- Search notes
- Pagination with infinite scroll
- Soft delete with undo
- Offline support with localStorage
- Keyboard shortcuts
- Confirmation modals
- Form validation
- Loading indicators and skeletons

## Additional Feature

Pinning notes: Users can pin important notes to keep them at the top of the list.

## Tech Stack

- Svelte
- TypeScript
- TailwindCSS
- Fetch API

## Setup

1. Clone the repository
2. Run `npm install`
3. Create a project on [mockapi.io](https://mockapi.io) and update the API_BASE in `src/lib/api.ts`
4. Run `npm run dev` for development
5. Run `npm run build` for production build
6. Run `npm run preview` to preview the build

## Deployment

Deploy to GitHub Pages:

1. Run `npm run build`
2. Run `npm run deploy`

Or deploy to Vercel, Netlify, etc.

## API

Uses mockapi.io for CRUD operations on notes.

Endpoint: `GET/POST/PUT/DELETE /notes`

Note structure:
```json
{
  "id": 1,
  "title": "Note Title",
  "content": "Note content",
  "createdAt": "2023-01-01T00:00:00.000Z",
  "pinned": false
}
```

## Approach

I approached this by first setting up the project with Svelte, TypeScript, and TailwindCSS. Then implemented the core CRUD operations with optimistic UI and localStorage for offline support. Added UX features like dark mode, search, pagination, and soft deletes. Ensured responsive design and accessibility.

## Trade-offs

- Used localStorage for simplicity, but for production, a more robust storage like IndexedDB would be better.
- Infinite scroll instead of traditional pagination for better UX, but may not be ideal for large datasets.
- Soft delete with 10-second undo, adjustable.

## Assumptions

- Users have modern browsers with ES6 support.
- mockapi.io is used as specified.

## Dependencies

- svelte: ^4.2.18
- tailwindcss: latest
- autoprefixer: latest
- postcss: latest
- gh-pages: for deployment

## What I'd do with more time

- Add tests with Vitest
- Implement proper routing for 404 page
- Add more animations
- Improve accessibility
- Add categories or tags for notes
- Implement real-time sync with WebSockets

SHA-256 hash of GitHub username: placeholder

Deployed at: https://yourusername.github.io/notes-app/

Video: [Link to video]