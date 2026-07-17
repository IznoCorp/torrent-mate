# Phase 02 — Suivis compact rows + Obligations title-led rows

**Goal**: Compact the Suivis rows (E1/E2/E3 — poster thumb, mono completeness, DropdownMenu,
synopsis removed, CompletenessAccordion kept) and lead Obligations rows with the new `title`
field (E4 — hash truncated mono + copy affordance).

**Constitution served**: §5, E1, E2, E3, E4.

## Surface

| File                                                            | Action                                                      |
| --------------------------------------------------------------- | ----------------------------------------------------------- |
| `frontend/src/components/acquisition/FollowedPanel.tsx`         | Compact rows: 72px thumb, mono completeness, DropdownMenu   |
| `frontend/src/components/acquisition/ObligationsPanel.tsx`      | Title-led rows: `item.title` primary, hash truncated + copy |
| `frontend/src/components/acquisition/meta.ts`                   | Add `truncate` reuse; no structural changes needed          |
| `frontend/src/components/acquisition/FollowedPanel.test.tsx`    | Update assertions for compact layout                        |
| `frontend/src/components/acquisition/CompletenessAccordion.tsx` | UNCHANGED — stays inline expansion per invariant            |

## Sub-phases

### 2.1 — Compact Suivis rows

**Commit**: `feat(acquisition-queue): compact followed rows — 72px thumb, mono completeness, DropdownMenu`

In `FollowedPanel.tsx`:

**Row structure** (replaces current `MediaCard`-based rows):

- **Poster thumb**: ~72px height, `rounded-md`, `object-cover`, `shrink-0`. Use the existing
  `item.poster_url` (already nullable — render a placeholder when absent).
- **Title + status chip**: `item.title` in `font-medium`, plus the existing status badge
  (`FOLLOW_STATUS_LABEL` + `FOLLOW_STATUS_TONE`).
- **Completeness**: `NN/NN` in `font-mono tabular-nums` (e.g. `89/89`). Derive from
  `item.owned_count` / `item.aired_count` when available; show `—` when `aired_count` is
  `None`.
- **Next due**: `untilLabel(item.next_search_at, Date.now())` in `text-xs text-muted-foreground`.
- **Actions**: collapse into ONE `⋯` `DropdownMenu` (shadcn `DropdownMenu` component):
  - « Rechercher maintenant » → trigger `triggerFollowedSearch` mutation (existing)
  - « Cadence » → opens the existing cadence dialog (keep existing dialog, just move trigger)
  - « Actif / Inactif » → the existing Switch toggle (move from inline to menu)
  - « Retirer » → the existing unfollow mutation with confirmation dialog (move from inline to menu)
- **English synopses removed** (E3): drop `item.overview` from the row. The overview field
  stays on the model (it's fetched at follow time) but no longer renders in the compact row.
- **« Détail par épisode »** stays the inline `CompletenessAccordion` (existing, untouched).
- **Cadence caption** (grab schedule + temperature) stays above/below the list — unchanged.

**Mobile**: at <640px, the row stacks vertically (poster left, text right within available
width). The DropdownMenu stays accessible on mobile (no hover-only trigger — use `onClick`).

### 2.2 — Obligations title-led rows

**Commit**: `feat(acquisition-queue): lead obligations rows with resolved title, truncated hash mono + copy`

In `ObligationsPanel.tsx`:

- **Primary column**: `item.title ?? truncate(item.info_hash, 12)` — the resolved title when
  available (from Phase 1 backend), otherwise the truncated info_hash.
- **Hash column**: `item.info_hash` rendered in `font-mono text-xs`, truncated to 12 chars
  with a copy-to-clipboard button (use `navigator.clipboard.writeText` + a check icon for
  1.5s confirmation). The full hash remains on `title` attribute for hover.
- **Tracker/ratio/seed-time columns**: unchanged — `item.source_tracker`, `item.observed_ratio`,
  `item.accumulated_seed_time_s`, `item.min_seed_time_s`, `item.min_ratio`.
- **Status filter + table layout**: unchanged — the existing `Select` filter and `Table`
  structure stay.

### 2.3 — Tests

**Commit**: `test(acquisition-queue): update FollowedPanel + ObligationsPanel tests for compact rows`

**FollowedPanel.test.tsx**:

- Assert poster thumb renders at ~72px (check `h-18` or explicit height class)
- Assert synopsis is NOT rendered (the overview text is absent from the DOM)
- Assert DropdownMenu exists and contains action items
- Assert completeness renders as `font-mono tabular-nums`
- Assert CompletenessAccordion still renders on expand

**ObligationsPanel** (new test or extend existing page test):

- Assert `title` renders when non-null
- Assert fallback to truncated info_hash when `title` is null
- Assert copy button renders and click copies full hash
- Assert tracker/ratio/seed-time columns still render

## Gate

- [ ] All commits have Conventional Commits format with `(acquisition-queue)` scope
- [ ] `cd frontend && npm run lint` → 0 errors
- [ ] `cd frontend && npm run lint:ds` → 0 errors
- [ ] `cd frontend && npm run typecheck` → 0 errors
- [ ] `npx vitest run` → all passing
- [ ] `make lint && make test` (backend — assert zero regressions)
- [ ] Visual check: Suivis row at 1440px shows poster + title + `89/89` + `⋯` — no amber buttons, no English synopsis
- [ ] Visual check: Obligations row shows media title, hash is secondary mono + copy
- [ ] Visual check: CompletenessAccordion expands inline, un-regressed
