# Season Grab — whole-season acquisition

**Ticket**: #378
**Date**: 2026-08-01
**Status**: operator rules frozen (3 decisions, 2026-08-01)
**Codename**: `season-grab`
**Version**: 0.74.1 → 0.75.0 (minor)
**Branch**: feat/season-grab

## 1. Problem

Acquisition is episode-only: detection enqueues per-episode wanted rows, the grab
builds `"{title} SxxEyy"` and `filter_to_episode` DROPS season packs (PR #214).
Yet triage already ingests season packs end-to-end (PR #213 — 4-gate detection,
`SxxE01-Eyy` split into `Saison XX/`), and dispatch's TV merge rule replaces
per-episode files. The missing piece is the acquisition side: wanting, finding,
ranking and grabbing a WHOLE season.

## 2. Operator rules (frozen 2026-08-01 — verbatim intent)

| #   | Rule                                                                                                                                                                                                              |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R1  | **Auto season wanted** when: the season's LAST episode aired **≥ 1 week ago** AND we own **≤ half** of the season's episodes.                                                                                     |
| R2  | **Episode→season conversion**: when an episode's search finds no episode-exact result BUT a whole-season pack for its season IS present in the results, acquire the season instead.                               |
| R3  | **Uniformity replace**: grabbing a season REPLACES every episode we already own for that season (uniform files) — delivered by the existing dispatch TV merge rule (pack carries all episodes; per-file replace). |
| R4  | **Manual button**: per-season « Récupérer la saison » action in the Suivis UI.                                                                                                                                    |
| R5  | **Absorption**: when a season wanted is created/grabbed, the season's live episode wanteds get a dedicated traceable status (absorbed), never searched again.                                                     |
| R6  | **Fallback**: at the season wanted's cutoff (existing backoff/cutoff machinery), re-enqueue the missing episodes individually (season status → fallback; Telegram notif per existing cutoff path).                |

## 3. Architecture

### 3.1 Domain + store

- `WantedKind` gains `"season"` (`acquire/domain.py` — validation set; season wanted =
  `kind="season", season=N, episode=None`).
- Wanted statuses gain `"absorbed"` (episode rows absorbed by a season wanted — carries
  `absorbed_by` = season wanted id in the payload/provenance) and season-specific
  terminal `"fallback_episodes"` (season row that degraded to per-episode retry, R6).
- `acquire.db` migration (additive, lazy per existing migration runner) only if a CHECK
  constraint or status enum requires it — inspect `migrations/001_init.sql`; otherwise
  status strings flow.
- Provenance spine: absorption + fallback recorded as events (existing catalog pattern —
  `WantedEnqueued` already carries kind/season/episode; add `SeasonAbsorbedEpisodes` +
  `SeasonFellBackToEpisodes` to the acquisition event catalog, registered in the
  eager-import hub).

### 3.2 Detection (auto — R1)

In `acquire/detect.py`, after the per-episode pass for a followed show: group the
show's aired episodes by season; for each season where (a) ALL episodes have aired,
(b) `last_air_date <= today - 7d`, (c) owned episode count `<= total/2` (ownership
predicate per episode, RP6), (d) no live season wanted exists, (e) the season is not
fully owned: enqueue the season wanted + absorb (R5) the season's live episode
wanteds. Dedup rule mirrors the movie one (one live season wanted per follow+season).

### 3.3 Episode→season conversion (R2)

In the search pass (`acquire/_search_pass.py`): when an episode wanted's search returns
raw results but ZERO episode-exact survivors (`filter_to_episode` empties), run the new
`filter_to_season` over the SAME raw results; if ≥1 whole-season pack for that episode's
season survives: enqueue/reuse the season wanted for that season, absorb the episode
(and its live siblings), and let the season wanted proceed on the NEXT pass (no
double-grab in the same tick — simple, idempotent).

### 3.4 Season search + ranking + grab

- Query: `"{title} S{NN}"` via the existing store-backed title resolver (zero-padded;
  the tracker search already tolerates broader hits — filtering is ours).
- `filter_to_season(results, season)`: keep only WHOLE-season packs for that season —
  reuse/adapt the triage season-pack gates (PR #213 parser) : `SxxE01-Eyy` full-range
  markers, bare `Sxx`/`Season N`/`Intégrale`/`Complete` without a specific episode;
  reject partial ranges and multi-season packs (v1: single-season only).
- Ranking: `rank(..., media_kind="season")` — the #376 provision (`size_thresholds_by_type
.season`) activates naturally.
- Grab: unchanged shared core (fetch+POST, contenu-utile tag) → ingest → triage's
  existing season-pack split (#213) → dispatch TV merge (R3 replace).
- Reconcile: the season wanted completes when the season's episodes land (existing
  reconcile follows dispatched paths; season row marked grabbed at grab time like
  episodes — verify the reconcile path keys on wanted id, not episode identity).

### 3.5 Fallback (R6)

Where the cutoff currently abandons a wanted: for `kind=="season"`, instead re-enqueue
the season's MISSING episodes (ownership-checked) as fresh episode wanteds (normal
backoff), set the season row to `fallback_episodes`, emit the event; the existing
cutoff Telegram notification fires with the season context.

### 3.6 Web UI + API (product-intent §2/§5/§8 — deep-linkable, truthful states)

- `POST /api/acquisition/follows/{id}/seasons/{season}/grab` (staging-guarded via the
  single `guarded_api` dependency, typed response) → creates the season wanted + absorbs
  (R4/R5). OpenAPI regenerated + committed.
- Suivis detail: per-season button « Récupérer la saison » (disabled when a live season
  wanted exists); episode state legend gains « absorbé (saison) »; File d'acquisition
  renders season rows (« Saison NN » label, kind badge).
- Parcours/spine: season wanteds appear as journeys like episodes (kind label).

## 4. Non-goals (v1)

- Multi-season / complete-series packs (single season only).
- Quality upgrades via season packs when the season is already fully owned.
- Changing the episode flow when a season is >half owned (stays per-episode).
- Retro-compat (<1.0.0).

## 5. Acceptance seeds (executable — ACCEPTANCE.md at phase 5)

- ACC: unit — R1 boundary matrix (aired-1w edge, exactly-half owned edge).
- ACC: unit — R2 conversion (episode search 0-exact + pack present → season wanted, siblings absorbed).
- ACC: unit — filter_to_season accepts full-range/bare-Sxx/Intégrale, rejects partial + multi-season.
- ACC: rank golden — media_kind="season" uses the season tiers.
- ACC: e2e (temp store) — cutoff fallback re-enqueues exactly the missing episodes.
- ACC: API — POST season grab 403 on staging role, absorbs siblings, 409/no-op on live duplicate.
- ACC: live dry-run (post-merge) — `follow detect --dry-run` on the real store reports season candidates without writes.

## 6. Test plan

Unit per module (detect R1 matrix, conversion R2, filter_to_season parser reuse,
absorption/fallback store transitions), API route tests (staging guard, typed), frontend
vitest (button, states, list rows), golden ranking pin. Live proofs post-merge per §5.

## 7. Risks

- **Pack quality variance** vs episode profile: hard filters (quality profile) apply
  unchanged to packs — a pack failing the profile is filtered like any release.
- **Absorption races** (detect vs search pass same tick): absorption is idempotent,
  keyed on live-status rows; single-writer store discipline (RP3) serializes.
- **Triage split edge cases** stay #213's domain — no triage changes in this feature.
