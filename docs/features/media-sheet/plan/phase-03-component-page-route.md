# Phase 3 - Composant + page + route + helper

**Codename**: `media-sheet` . **Gate**: Phase 2 complete.

## Gate

> Phase 2 [x] - `GET /api/media/{provider}/{provider_id}` returns typed response; cache TTL 300s; ownership crossing; `degraded_reason` on provider error (never 500). `openapi.json` + `schema.d.ts` regenerated and committed.

## ANCHOR CORRECTION

- **DESIGN says** `MediaCard.tsx` has `onOpen` prop, route at `router.tsx`, mirror test at `router.test.tsx`.
- **Reality**: confirmed. `MediaCard` at line 25 has `onOpen?: () => void`, lines 102-105 render poster+meta as button. `router.tsx` exports `routes: RouteObject[]` - new path under `AppShell` children (line 46-84). `router.test.tsx` uses `renderAt(path)` + `createMemoryRouter(routes)`. `frontend/src/components/media/` does NOT exist - must be created. `frontend/src/lib/__tests__` exists.
- **Route pattern**: `path: "media/:provider/:providerId"` inside `AppShell` children.

## Sub-phases

### 3.1 Helper `mediaSheetHref`

**Files**:
- `frontend/src/lib/media-href.ts` (create)
- `frontend/src/lib/__tests__/media-href.test.ts` (create)

**Implementation**:
```typescript
export interface MediaRef_ {
  provider: string;
  providerId: string;
}

export function mediaSheetHref(ref: MediaRef_): string {
  return `/media/${encodeURIComponent(ref.provider)}/${encodeURIComponent(ref.providerId)}`;
}
```
- Pure function. `encodeURIComponent` on both segments (D8: single source of truth).

**Tests**:
- URL shape: `mediaSheetHref({provider: "tmdb", providerId: "27205"})` -> `"/media/tmdb/27205"`.
- IDs with special chars are encoded.

**Gate**:
```bash
cd frontend && npx vitest run src/lib/__tests__/media-href.test.ts
```

### 3.2 `MediaSheet` component

**Files**:
- `frontend/src/components/media/MediaSheet.tsx` (create - new directory)
- `frontend/src/components/media/MediaSheet.test.tsx` (create)

**Implementation**:
- Autonomous component: receives `{provider, providerId}`, queries `/api/media/{provider}/{providerId}` via `@tanstack/react-query` `useQuery`.
- States: Loading (Skeleton), Error (`ErrorState`), Degraded (data + warning banner, D9), Loaded (full layout).
- Loaded layout: poster (provider URL, D3), title, year, director, genres (Badge chips), synopsis, trailer YouTube link (D10), series status + seasons table (TV), ownership section (D5).
- Root element: `data-testid="media-sheet"` for route mirror test.
- Mobile-responsive: Tailwind responsive classes.

**Tests**:
- Loading/error/degraded/loaded states.
- Movie: no series section. TV: series status, seasons.
- Missing director: "Realisateur inconnu" text.
- Trailer URL shown when present; absent -> no trailer section.

**Gate**:
```bash
cd frontend && npx vitest run src/components/media/MediaSheet.test.tsx
```

### 3.3 `MediaSheetPage` + route + mirror test

**Files**:
- `frontend/src/pages/MediaSheetPage.tsx` (create)
- `frontend/src/router.tsx` (modify)
- `frontend/src/router.test.tsx` (modify)

**Implementation**:
- `MediaSheetPage.tsx`: reads `useParams()` for `provider` + `providerId`, renders `<MediaSheet />`.
- `router.tsx`: add `{ path: "media/:provider/:providerId", element: <MediaSheetPage /> }` under AppShell children. Add import.
- `router.test.tsx`: mirror test mocking `/api/media/tmdb/27205` -> 200 with minimal well-shaped response, asserts `screen.findByTestId("media-sheet")`.

**IMPORTANT**: new route -> mirror test MANDATORY.

**Gate**:
```bash
cd frontend && npx vitest run src/router.test.tsx
cd frontend && npx tsc --noEmit
cd frontend && npx eslint src/router.tsx src/pages/MediaSheetPage.tsx src/components/media/MediaSheet.tsx src/lib/media-href.ts
```

### 3.4 Gate - Phase 3 complete

```bash
cd frontend && npx vitest run src/router.test.tsx src/components/media/MediaSheet.test.tsx src/lib/__tests__/media-href.test.ts
cd frontend && npx tsc --noEmit && npx eslint .
make lint
python -m pytest tests/ -v -k "not e2e"
```

**Commit**: `feat(media-sheet): MediaSheet component + page + route + mediaSheetHref helper (D7,D8)`
