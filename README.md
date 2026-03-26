706e579737107779f40398321683495f26941566497257929427181829375107

# Notely OS

A high-performance, responsive fragments manager built with **Svelte**, **TypeScript**, and **TailwindCSS**.

## 🚀 Live Demo & Video
- **Deployed App:** [https://maytri315.github.io/inlabels-assignment/](https://maytri315.github.io/inlabels-assignment/)
- **Video Walkthrough:** [Link to your video]

## 🛠 Features Implemented
- **Fully Responsive UI**: Optimized layout for both mobile and desktop users using TailwindCSS.
- **Offline Sync & Optimistic UI**: Implements a `pendingOperations` queue in `localStorage` to store changes and automatically sync with the API upon reconnection.
- **Soft Delete with Undo**: Deleted notes are hidden from the UI for a 10-second window, allowing users to revert the action via a toast notification before permanent API deletion.
- **Infinite Scroll**: Dynamically loads 20 notes per page using `IntersectionObserver` to enhance browsing performance.
- **Debounced Search**: Integrated a 300ms debounce on the search input to improve performance and reduce unnecessary API calls.
- **Keyboard Shortcuts**: Includes power-user workflows such as `Esc` to close modals and `Ctrl+N` for new note focus.
- **Dark Mode**: A toggleable theme using Tailwind's class strategy with persistent state saved in `localStorage`.
- **Confirmation Modals**: Secure deletion process implemented via a reusable confirmation component.
- **Form Validation**: Strict validation ensures required fields are populated and character limits (100 for titles, 500 for content) are respected.
- **Loading Indicators**: Includes animated skeletons and spinners for all asynchronous data fetching and operations.

## 💡 Additional Feature: Note Pinning & Spatial Persistence
I implemented **Note Pinning** as the primary additional feature.
* **Functional Benefit**: Users can pin important fragments to the top of the list, ensuring high-priority information is always visible regardless of the creation date.
* **Spatial Organization**: The app separates "flow" notes from "positioned" notes, allowing fragments to be anchored to specific spatial coordinates (x, y).
* **Why**: This transforms the app from a simple list into a digital "AR-style" workspace, catering to non-linear thinkers who organize information visually.

## ⚙️ Setup & Run
1. **Clone the repository**: `git clone https://github.com/maytri315/inlabels-assignment.git`
2. **Install dependencies**: `npm install`
3. **Configure API**: Update the `API_BASE` in `src/lib/api.ts` with your [mockapi.io](https://mockapi.io) endpoint.
4. **Development**: `npm run dev`
5. **Build**: `npm run build`
6. **Preview**: `npm run preview`

## 🧠 Approach & Reflection
My approach centered on creating a modular Svelte architecture where notes and forms are decoupled into separate files for better maintainability. I prioritized an **Optimistic UI** strategy; for instance, when a note is pinned or updated, the local store reflects the change immediately while the `Fetch API` syncs the data in the background.

## ⚖️ Trade-offs & Assumptions
* **Storage**: Used `localStorage` for the offline queue due to simplicity; however, `IndexedDB` would be a more robust choice for production-scale data.
* **Sorting**: The app defaults to "Newest First" but overrides this logic for pinned notes to maintain priority visibility.
* **Environment**: Assumed modern browser support for `IntersectionObserver` and the `Fetch API`.

## 📦 Dependencies
- `svelte`: ^4.2.18
- `typescript`: For strict typing and preventing implicit `any`.
- `tailwindcss`: For rapid, responsive styling.
- `gh-pages`: For seamless deployment.

## ⏳ What I'd do with more time
- Implement unit and integration testing with Vitest.
- Add advanced tagging and category systems for note organization.
- Develop real-time synchronization using WebSockets for multi-device coordination.
