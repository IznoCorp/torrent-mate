# vo-title — cross-language movie identity (ticket #435)

**Type:** bugfix — SemVer 0.97.5 → 0.97.6. **Branch:** `fix/vo-title`.

## The bug (proved in prod)

Wanted movie « Avant d'aller dormir » (followed_id 34, tmdb 204922, year 2014).
C411's Torznab API returns the correct release for the app-built query
(`avant d'aller dormir 2014` → `Before.I.Go.To.Sleep.2014.MULTI.VFI.1080p.BluRay.EAC3.5.1.x265-notag`,
infohash `f3e2e41466cd62c302b500c035f2f38e7857a6bc`), but `filter_to_movie`
(`acquire/orchestrator.py`) drops it: guessit parses the release title as
`Before I Go To Sleep` and `token_set_ratio("Before I Go To Sleep", "Avant d'aller dormir") = 25 < 60`.
The year — the real discriminator, and a match here (2014 = 2014) — is never
consulted because the title guard rejects first. The wanted row ends
`last_search_outcome=all_filtered`.

This is structural, not a one-off: MULTI releases on French trackers are named
with the ORIGINAL (usually English) title, while follows are stored under the
French display title from TMDB. Every FR-followed movie whose releases are
named in EN hits it.

## Root-cause fix: the filter must know every title the app knows

The app has the movie's `tmdb_id`; TMDB carries `original_title` (already
parsed into `MediaDetails.original_title` by `api/metadata/_tmdb_parsers.py`).
The identity filter must accept a release whose parsed title matches ANY known
title of the wanted movie — display title OR original title — with the year
check unchanged as the discriminator.

### Components

1. **Data** — migration `024_followed_original_title.sql`:
   `ALTER TABLE followed_series ADD COLUMN original_title TEXT` (nullable, one
   transaction, 023 pattern). `FollowedSeries.original_title: str | None`.
   Store: INSERT + `ON CONFLICT` refresh (`COALESCE(excluded.original_title,
   followed_series.original_title)` — a re-follow without the value must not
   erase it), all SELECT paths, `merge_metadata(original_title=...)` (COALESCE
   pattern, never overwrites with NULL).
   Convention: store the provider's original title VERBATIM, even when it
   equals the display title — non-NULL means « healed », which is what stops
   the detect backfill from refetching forever; the filter dedups identical
   titles before matching. (Deliberately NOT the `media_item` "`None` if same
   as title" convention: that table has no backfill loop to starve.)

2. **Capture at add time** — `FollowMetadata.original_title` + `_extract`
   reads `details.original_title`; `fill_from` fills it like the other fields.
   `is_complete` is UNCHANGED (the four card fields): a client posting a
   complete card still makes zero provider calls; such rows are healed by (4).
   Both add paths (web route, CLI follow) persist it via `merge_metadata`.

3. **Filter + wiring** — `filter_to_movie(results, titles: Sequence[str], year)`:
   keep a release when its parsed title scores ≥ 60 against ANY of `titles`.
   `GrabOrchestrator` gains `original_title_resolver` (same store-backed
   pattern as `year_resolver`), wired in `acquire/_factory.py` and
   `commands/search.py`; `commands/grab.py` passes
   `[row.title, row.original_title]`. Search queries still use the display
   title only (see Open items).

4. **Heal existing rows** — detect pass (`_detect_movie`): when a movie follow
   has `original_title IS NULL` and a `tmdb_id`, resolve via
   `registry.chain(MovieDetailsProvider)` and persist VERBATIM (fail-soft
   WARNING, `_persist_series_status` precedent). One provider call per
   un-healed row per detect run; a persisted value — equal to the display
   title or not — is non-NULL, so the row is never refetched.

## Non-regression tests

- `filter_to_movie` with the EXACT prod pair (release
  `Before.I.Go.To.Sleep.2014...x265-notag`, titles
  `["Avant d'aller dormir", "Before I Go to Sleep"]`, year 2014) → kept.
- Same release, display title only → still dropped (documents the old hole).
- Wholly-unrelated release vs both titles → dropped; wrong-year → dropped
  (guards intact).
- Store roundtrip + migration 024 idempotence/user_version.
- Enrichment extracts + persists `original_title`.
- Detect backfill: fills missing value, fail-soft on provider error, no call
  when already healed.
- Orchestrator `_search_chain` end-to-end with a stub tracker returning the
  prod release → `exit_path="available"` (the full-chain regression).

## Follow-ups (operator-requested 2026-08-15, same PR)

The three items originally listed as open were implemented on request:

1. **Original-title retry query** — `_search_chain` replays the search→narrow
   stage once with `build_search_query(item, original_title, year)` when the
   display-title attempt concludes a fully-healthy « nothing matched »
   (`no_candidates` / `no_matching_episode` / `no_matching_season` / movie
   identity-filter empty). Hard failures (outage/auth/circuit/degraded) keep
   their verdict — a retry must not muddle an honest diagnosis; a fruitless
   retry states the FIRST attempt's verdict. The `grab --dry-run` preview
   mirrors it (a preview that diverges from the run is a lie).
2. **Web API exposure** — `FollowedSeriesItem.original_title` (all three
   construction sites), OpenAPI + `schema.d.ts` regenerated. The VISUAL
   surface deliberately stops at the API: § maquette-fait-foi — the display
   is drawn in the refonte before any app UI derives it.
3. **Shows** — the retry query covers episodes/seasons, and the detect-pass
   backfill now heals shows too (`get_tv`, TMDB own-id, `original_name`).
   The backfill is capped per run (`_ORIGINAL_TITLE_BACKFILL_CAP`) so the
   first post-migration detect does not stall behind N provider round-trips.
