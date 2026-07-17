# Phase 03 — File d'acquisition (merge wanted + downloads)

**Goal**: Merge « Recherches » (WantedPanel) and « Téléchargements » (DownloadsPanel) into a
single « File d'acquisition » tab, collapse TABS 5→4, redirect legacy `?tab=wanted|downloads`
→ `?tab=file`, and deliver the one-flow wanted→grabbed→ingest surface (§9).

**Constitution served**: §9, DOIT-2, DOIT-10, NE-DOIT-PAS-1/5, E5, E6.

## Surface

| File                                                                 | Action                                                               |
| -------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `frontend/src/components/acquisition/meta.ts`                        | TABS: 5→4, add `"file"` id, remove `"wanted"`/`"downloads"`          |
| `frontend/src/pages/AcquisitionPage.tsx`                             | Redirect logic: `?tab=wanted\|downloads` → `?tab=file`, new tab id   |
| `frontend/src/components/acquisition/FileDAcquisitionPanel.tsx`      | NEW — merged panel (grouped searches + per-download rows)            |
| `frontend/src/components/acquisition/FileDAcquisitionPanel.test.tsx` | NEW — tests for merged panel                                         |
| `frontend/src/pages/AcquisitionPage.test.tsx`                        | Update: 4 tabs, redirect assertions                                  |
| `frontend/src/router.tsx`                                            | Add `?tab=wanted\|downloads` → `?tab=file` redirect? (optional)      |
| `frontend/src/components/acquisition/WantedPanel.tsx`                | UNCHANGED in place — used as import for grouped-search sub-component |
| `frontend/src/components/acquisition/DownloadsPanel.tsx`             | UNCHANGED — used as import for download sub-component                |

## Sub-phases

### 3.1 — TABS 5→4 + redirect logic

**Commit**: `feat(acquisition-queue): collapse acquisition tabs 5→4, redirect ?tab=wanted|downloads → ?tab=file`

In `frontend/src/components/acquisition/meta.ts`:

- Replace `TABS` array:
  ```typescript
  export const TABS: readonly { id: TabId; label: string }[] = [
    { id: "followed", label: "Suivis" },
    { id: "file", label: "File d'acquisition" },
    { id: "obligations", label: "Obligations" },
    { id: "watcher", label: "Watcher" },
  ];
  ```
- Update `TabId` type: remove `"wanted"` and `"downloads"`, add `"file"`.
- The `NavCountBadge` for downloads: move from `tab.id === "downloads"` to the File
  tab header (count of active downloads, same query — `useDownloads` already at page level).

In `frontend/src/pages/AcquisitionPage.tsx`:

- Add redirect logic BEFORE the `activeTab` derivation:
  ```typescript
  const rawTab = searchParams.get("tab");
  // Redirect legacy tabs (replace so Back doesn't cycle through the redirect)
  if (rawTab === "wanted" || rawTab === "downloads") {
    const next = new URLSearchParams(searchParams);
    next.set("tab", "file");
    // useEffect + setSearchParams with replace: true — fires once on mount
  }
  ```
  Use a `useEffect` that fires once when `rawTab` is `"wanted"` or `"downloads"`,
  calling `setSearchParams` with `{ replace: true }`.
- Update `activeTab` validation: `TABS.some((t) => t.id === rawTab)` — `"wanted"` and
  `"downloads"` no longer match, so they fall to redirect before validation.
- Add the new `FileDAcquisitionPanel` case:
  ```typescript
  {activeTab === "file" && <FileDAcquisitionPanel />}
  ```
- Remove `{activeTab === "wanted" && <WantedPanel />}` and
  `{activeTab === "downloads" && <DownloadsPanel />}`.

### 3.2 — FileDAcquisitionPanel: grouped searches + per-download rows

**Commit**: `feat(acquisition-queue): File d'acquisition merged panel — grouped searches + live downloads`

Create `frontend/src/components/acquisition/FileDAcquisitionPanel.tsx`:

**Layout** (segmented control + two sections):

```
┌─────────────────────────────────────────────┐
│  Segmented: [Recherches] [Téléchargements]  │
│  (clear active state per E5)                │
├─────────────────────────────────────────────┤
│  Recherches section:                        │
│  ┌─ Status filter (Select, survives) ──────┐│
│  │  Tous · En attente · En recherche · …   ││
│  ├──────────────────────────────────────────┤│
│  │ ▲ Série A (3 saisons, 12 épisodes)      ││
│  │   ├─ S01 (5 eps) ▸                       ││
│  │   ├─ S02 (4 eps) ▹                       ││
│  │   └─ S03 (3 eps) ▹                       ││
│  │ ▲ Série B (1 saison, 2 épisodes)         ││
│  │   └─ S01 (2 eps) ▸                       ││
│  └──────────────────────────────────────────┘│
│                                              │
│  Téléchargements section:                    │
│  ┌─ "client torrent injoignable" notice ────┐│
│  │  (when client_available===false)          ││
│  ├──────────────────────────────────────────┤│
│  │  DownloadRow 1 (progress, state, size)    ││
│  │  DownloadRow 2                            ││
│  └──────────────────────────────────────────┘│
│  3s poll on downloads (existing useDownloads) │
└─────────────────────────────────────────────┘
```

**Segmented control** (E5):

- Two segments: « Recherches » · « Téléchargements ».
- Clear active state: the active segment has `bg-background text-foreground shadow-sm`
  (matching the tab active state pattern from `AcquisitionPage.tsx:138-139`). Inactive
  segment has `text-muted-foreground hover:text-foreground`.
- Mobile: horizontal scroll via `overflow-x-auto` on the segmented control container
  (no 3-row wrap — E5). At 390px, the two segments scroll horizontally without
  page-level overflow.

**Grouped searches** (E6 + DOIT-2):

- Fetch wanted items via `useWanted` (existing hook, same query key `acqKeys.wanted`).
- Group by `item.title` → by `item.season`.
- Each series group is a **collapsible section** (use shadcn `Accordion`, or a simple
  `details`/`summary` pattern):
  - Header: `▲ Série Title (N saisons, M épisodes)` with a count badge per status
  - Body: one sub-group per season « Saison NN (K épisodes) », expandable
  - Every episode row keeps its `status` badge AND its FR reason tooltip (the
    `STATUS_LABEL[item.status]` + the reason when available — `abandoned`/`deferred`
    rows are the tail where lies live, DOIT-2).
- **Status filter survives the merge**: the existing `WANTED_STATUS_OPTIONS` + `Select`
  from `WantedPanel.tsx` is promoted to the merged panel header. Filtering re-fetches
  via `useWanted({ status })` — no client-side re-filter.
- **Pagination**: kept from `WantedPanel` (existing `page`/`pageSize` state, prev/next
  buttons).

**Per-download rows** (NE-DOIT-PAS-1/5):

- Directly reuse `DownloadRow` from `DownloadsPanel.tsx` (extract as a named export if
  currently file-private — it's currently a file-local function at
  `DownloadsPanel.tsx:44`).
- Export `DownloadRow` from `DownloadsPanel.tsx` (or extract to a shared
  `acquisition/download-row.tsx`).
- The 3s poll (`useDownloads` hook, `refetchInterval: 3_000`) stays.
- The « client torrent injoignable » fail-soft notice (`DownloadsPanel.tsx:130-134`)
  stays — show it above the download list when `client_available === false`.
  **Never an empty state that reads as « rien de téléchargé »** when the client is
  just unreachable.

**WantedPanel.tsx / DownloadsPanel.tsx status**:

- Both files are KEPT in the tree (not deleted — acquisition history could reference
  them). The `AcquisitionPage.tsx` stops importing them; they become dead references
  cleaned in a later cleanup wave.
- Extract `DownloadRow` as a named export for reuse.

### 3.3 — Tests (redirects + merged panel)

**Commit**: `test(acquisition-queue): redirect coverage + FileDAcquisitionPanel tests`

**AcquisitionPage.test.tsx**:

- Assert `?tab=wanted` redirects to `?tab=file` (replace, no history entry for redirect)
- Assert `?tab=downloads` redirects to `?tab=file`
- Assert `?tab=file` renders `FileDAcquisitionPanel` (heading/text present)
- Assert `?tab=followed` still renders FollowedPanel (no regression)
- Assert `?tab=obligations` still renders ObligationsPanel (no regression)
- Assert `?tab=watcher` still renders WatcherPanel (no regression)
- Assert unknown `?tab=bogus` defaults to `followed` (clean URL, no param)

**FileDAcquisitionPanel.test.tsx** (new):

- Assert segmented control renders with two segments
- Assert « Recherches » segment shows grouped wanted items by title
- Assert episode row renders status badge + FR reason (for an `abandoned` row)
- Assert « Téléchargements » segment shows download rows
- Assert `client_available=false` notice renders, download rows still list
- Assert status filter survives (change filter → re-fetch with new params)
- Assert 390px horizontal scroll: container `overflow-x-auto`, no page-level overflow

## Gate

- [ ] All commits have Conventional Commits format with `(acquisition-queue)` scope
- [ ] `cd frontend && npm run lint` → 0 errors
- [ ] `cd frontend && npm run lint:ds` → 0 errors
- [ ] `cd frontend && npm run typecheck` → 0 errors
- [ ] `npx vitest run` → all passing (incl. redirect assertions)
- [ ] `make lint && make test` (backend — assert zero regressions)
- [ ] Visual check: `?tab=wanted` → `?tab=file` redirect works, URL bar shows `?tab=file`
- [ ] Visual check: Back button from `?tab=file` goes to `?tab=followed` (not through the redirect)
- [ ] Visual check: File d'acquisition at 1440px shows segmented control + grouped searches + downloads active
- [ ] Visual check: An `abandoned` episode row shows its status badge AND FR reason
- [ ] Visual check: Downloads section shows « client torrent injoignable » when client down (not empty)
- [ ] Visual check: Segmented control at 390px scrolls horizontally, no page overflow
- [ ] Watcher tab untouched — numbered results still render (DOIT-6)
- [ ] MediaSearchAdd flow untouched — add-by-search still works
