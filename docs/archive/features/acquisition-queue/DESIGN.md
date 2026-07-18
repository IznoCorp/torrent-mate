# Design overhaul V4 — Acquisition : rangées compactes, File d'acquisition, obligations titrées

**Ticket**: #308 (epic #304) · **Binding source**: `docs/superpowers/specs/2026-07-16-design-overhaul-design.md`
§3.1 + §5.1 + §7.2 (merge confirmed) — this DESIGN is an extraction, the spec wins on conflict.
**Product intent**: §5 (completeness épisode-par-épisode), §9 (one flow wanted→grabbed→ingest), DOIT-2
(FR reasons, truthful states), DOIT-10 (URL-addressable), NE-DOIT-PAS-1/5 (never a calm lie on
unreachable torrent client), E1–E6 findings.

## Grounding (verified in code 2026-07-17)

- `frontend/src/components/acquisition/meta.ts:67` — `TABS` = followed / wanted / downloads /
  obligations / watcher (5). Target: followed / **file** / obligations / watcher (4).
- `frontend/src/pages/AcquisitionPage.tsx` — `?tab=` URL-addressable, default `followed` clean URL;
  WS invalidation via `acqKeys`.
- `WantedPanel.tsx` (196 L) + `DownloadsPanel.tsx` (144 L) — merge sources. DownloadsPanel already
  polls 3 s and carries the « client torrent injoignable » fail-soft notice — both MUST survive.
- `FollowedPanel.tsx` (569 L) — current rows are large (poster, EN synopsis, inline amber actions);
  `CompletenessAccordion.tsx` (126 L) is the per-season/episode detail — stays the inline expansion.
- `personalscraper/web/models/acquisition.py:147` — `ObligationItem` has `info_hash`,
  `dispatched_path`, ratio state; **no `title`**.
- `personalscraper/web/routes/acquisition.py:417` — `GET /api/acquisition/obligations`.

## 1. Frontend

### 1.1 Suivis — compact rows (E1/E2/E3)

- Row = poster thumb (~72 px) + title + status chip + completeness `NN/NN` (tabular mono `font-mono
tabular-nums`) + next-due; actions collapse into one `⋯` DropdownMenu (Rechercher maintenant,
  Cadence, Retirer, Actif/Inactif) — no primary-amber row buttons left.
- English synopses removed from rows (E3) — nothing in the row that isn't operator-actionable.
- « Détail par épisode » stays the inline season-by-season expansion (CompletenessAccordion), un-regressed.

### 1.2 File d'acquisition — merged tab (§7.2 arbitrated)

- Tabs 5 → 4: `wanted` + `downloads` → **`file`** (« File d'acquisition »), one §9 flow
  wanted → grabbed → ingest. `?tab=wanted` and `?tab=downloads` redirect (replace) to `?tab=file`.
- Searches grouped série → saison with counts (E6), groups **expandable**: every episode row keeps
  its status badge AND its FR reason (abandoned/deferred included — the tail is where the lies live,
  DOIT-2). The status filter survives the merge.
- Per-download rows preserved verbatim: progress, state badge, size, 3 s poll, and the explicit
  « client torrent injoignable » fail-soft notice (NE-DOIT-PAS-1/5) — never a calm empty state.
- Segmented control with a clear active state (E5); horizontal scroll on mobile (no 3-row wrap).

### 1.3 Obligations — title-led rows (E4)

- Row leads with the media **title** (new API field, §2 below); `info_hash` demoted to truncated
  mono + copy affordance. Tracker/ratio/seed-time columns unchanged.

### 1.4 Watcher — unchanged (numbered results = DOIT-6 acquis).

## 2. Backend (§5.1 — the only route change)

- `ObligationItem.title: str | None` — resolved server-side: `dispatched_path` basename when set,
  else indexer lookup by `info_hash`, else `None` (frontend falls back to hash). Fail-soft: resolver
  errors never break the listing.
- `make openapi` + commit `openapi.json` / `schema.d.ts` (CI drift guard).
- Every route stays staging-guarded + typed; no other backend change in this wave.

## 3. Proof (§méthode)

- Dated prod capture: compact rows, merged File d'acquisition with an expanded group showing an
  episode FR reason, obligations titled, redirects `?tab=wanted|downloads` → `?tab=file`.
- 390 px iframe: zero horizontal page overflow; segmented control scrolls horizontally.
- `scripts/check-acquisition-coherence.py` → zero anomaly (executed, dated).

## Sequencing invariant (spec §6)

Only `/acquisition` surfaces + the ObligationItem enrichment. No Système/Config work (V5). No
regression on: watcher numbered results, obligations release flow, wanted per-episode badges/reasons,
downloads fail-soft notice, add-follow search flow (MediaSearchAdd).
