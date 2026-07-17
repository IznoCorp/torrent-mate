# Phase 05 — PR fixes cycle 1 (review findings, PR #315)

## Gate

- [ ] Phases 1–4 done, PR #315 open, CI green on 74a0e3ef.

### Sub-phase 5.1 — Code fixes (honest downloads errors, guarded composition, movie rows)

**Commit:** `fix(acquisition-queue): honest downloads error state + guarded title composition + movie rows`

1. **F1 (CRITICAL, NE-DOIT-PAS-1/5)** — `FileDAcquisitionPanel.tsx` downloads section: add an
   explicit `downloadsQuery.isError` branch (mirror the wanted section's pattern, FR message
   « Erreur de chargement : {message} ») rendered INSTEAD of the calm empty state; the empty state
   renders only when `!isLoading && !isError && downloads.length === 0`. While reworking the block,
   **hoist the « client torrent injoignable » notice out of the `downloads.length > 0` branch** (F3 —
   removes the fragile implicit backend invariant).
2. **F2 (MEDIUM)** — `ObligationsPanel.tsx` copy button: add `.catch` on
   `navigator.clipboard.writeText` → `toast.error("Copie du hash impossible")` (sonner, as in
   FollowedPanel). No check icon on failure.
3. **T2/C5 (MEDIUM)** — `routes/acquisition.py` `_resolve_obligation_titles`: wrap the title-map
   COMPOSITION loop per-row (`try/except Exception` + `logger.warning` with hash context, matching
   the apply loop) so one malformed row can't blank ALL titles; reword the docstring to the honest
   contract and add « (case-insensitive) » to the step-1 join description (C10).
4. **Movie rows (MEDIUM, DOIT-2)** — `FileDAcquisitionPanel.tsx`: wanted rows with
   `kind === "movie"` must not render « Saison ?? » nor the raw `movie` enum. Movies group under a
   « Film » season label (or render flat under the title group) and the row label uses the FR kind
   (« Film »). Orphan groups (empty title, followed row deleted) render « (série retirée) » instead
   of a blank accordion header.

### Sub-phase 5.2 — Test hardening (mutation-proven gaps)

**Commit:** `test(acquisition-queue): mutation-proof join/redirect/error invariants`

- Backend `tests/unit/web/routes/test_acquisition_read.py`:
  - `test_title_join_case_insensitive` — grabbed_hash uppercase vs info_hash lowercase → composed
    title (kills the `lower()` mutation).
  - Two-row isolation: corrupt-path row first + joinable row second → 200 AND second title composed
    (kills removal of the per-item/per-row guards).
  - Directory `dispatched_path` (dotted, extension-less) → basename verbatim (kills unconditional
    `.stem`).
- Frontend:
  - `FileDAcquisitionPanel.test.tsx`: `useDownloads` mocked `isError: true` → FR error message
    present, calm empty state ABSENT; combined `downloads=[]` + `client_available=false` → notice
    still visible (post-hoist); abandoned badge tone `danger` asserted (not just the label); a
    `kind:"movie"` wanted row → « Film » rendered, no « Saison ?? », raw `movie` absent.
  - `AcquisitionPage.test.tsx`: back-navigation probe — two-entry history, after redirect
    `navigate(-1)` lands on the pre-legacy entry (kills `replace: true` → `false`).
  - `FollowedPanel.test.tsx`: assert MediaPoster presence (thumb) and `font-mono tabular-nums`
    class on the completeness node (de-vacuize the two named tests).
  - `ObligationsPanel.test.tsx`: clipboard rejection path → `toast.error` called, no check icon.

### Sub-phase 5.3 — Docs sweep (comment accuracy)

**Commit:** `docs(acquisition-queue): comment accuracy sweep from review cycle 1`

- `AcquisitionPage.tsx`: module + function docblocks (File d'acquisition, not Wanted), line ~52
  shareable form `?tab=file`, badge comment « File d'acquisition », shell docstring mentions the
  downloads poll it owns.
- `FileDAcquisitionPanel.tsx` (+ its test header): « FR status labels » (no reason field exists).
- `WantedPanel.tsx` / `DownloadsPanel.tsx`: supersession notes (kept in tree, not mounted;
  DownloadRow exported for reuse).
- `FollowedPanel.tsx`: « card grid » phrasing → rows (lines ~180/~277).

## Recorded open items (operator arbitration — §méthode rule 4)

- **Pagination partial groups (MEDIUM, design)**: `groupByTitleSeason` groups the current 50-item
  page only — a series spanning a page boundary shows partial counts per page. Honest fix = server-side
  grouping or full-set fetch; needs arbitrage (out of this cycle's scope decision, NOT self-labelled
  out-of-scope: recorded for the operator).
- **F4 (LOW)**: the arrival badge reads 0 (« rien ») on downloads fetch error — A4 avowed-limit
  surface; fixing needs a distinct badge error affordance.
- **Multi-row hash label non-determinism (INFO)**: join has no ORDER BY; a hash matching several
  wanted rows may alternate its composed SxxEyy label between refreshes.
- **UI cannot distinguish resolver crash from no-title-data (INFO, F5)**: both render hashes; would
  need a response-level degradation flag if it ever matters.
