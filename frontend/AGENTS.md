<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Frontend — Agent Guide

## Stack

Next.js 16.2 (App Router) / TypeScript / Tailwind CSS

## Structure

```
src/
├── app/                    # Pages (file-system routing)
│   ├── page.tsx            # Home — nav cards for all sections
│   ├── auth/page.tsx       # Magic link request
│   ├── auth/verify/page.tsx # Token verification
│   ├── profile/page.tsx    # User profile (membrane editing)
│   ├── signals/page.tsx    # Signal creation/listing
│   ├── network/page.tsx    # Trust graph (vouches given/received)
│   ├── matches/page.tsx    # Match list
│   ├── matches/[id]/page.tsx # Match detail
│   ├── organizations/page.tsx      # Org list (search, create, cards)
│   ├── organizations/[id]/page.tsx # Org detail (membrane, members, vouch-in)
│   ├── events/page.tsx             # Event list (search, create, upcoming, cards)
│   ├── events/[id]/page.tsx        # Event detail (membrane, participants, vouch-in)
│   ├── messages/page.tsx           # Inbox (thread list, unread badges, new message)
│   └── messages/[id]/page.tsx      # Thread detail (message history, compose, block)
├── components/
│   └── AttributeList.tsx   # Shared membrane entry editor (used by profile page)
└── lib/
    ├── api.ts              # API client — types, mock data, real + mock implementations
    └── useAuth.ts          # Auth hook (session state, logout)
```

## Conventions

### All Pages Are Client Components

Every page uses `"use client"` with React hooks. No server components, no server actions. Data fetching happens in `useEffect` via `api.*` calls.

### API Client Pattern (`lib/api.ts`)

The `api` object has two implementations selected at build time:
- **Mock mode** (`NEXT_PUBLIC_DEV_MOCK=true`): in-memory data, no backend needed
- **Real mode**: fetch calls to `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`)

Both implementations share the same type signatures. Namespaced under feature groups (e.g., `api.messages.*`, `api.trust.*`). When adding new endpoints:
1. Add TypeScript types at the top of `api.ts`
2. Add mock data variables and mock API methods in the mock block
3. Add real API methods in the real block
4. Keep both in sync

### Page Pattern

Every page follows this structure:
1. `useAuth()` for session state
2. `useState` + `useCallback` + `useEffect` for data loading
3. Loading state → auth check → render
4. Forms use controlled inputs with `useState`

### Styling

Dark theme with neutral/emerald palette. Cards use `rounded-xl border border-neutral-800 bg-neutral-900/60` with hover states. Buttons use `bg-gray-900 text-white rounded hover:bg-gray-700`. Keep it consistent.

### Adding a New Entity Page

Follow the organization or event page as a template:
1. Create `app/<entity>/page.tsx` — list view with search, create form, cards
2. Create `app/<entity>/[id]/page.tsx` — detail view with membrane, members/participants, vouch-in
3. Add types and API methods to `lib/api.ts` (both mock and real)
4. Add nav card to `app/page.tsx`
