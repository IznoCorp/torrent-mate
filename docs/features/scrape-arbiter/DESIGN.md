# S5 — Interactive Scraping: Decision Queue + Targeted Resolve (scrape-arbiter)

**Ticket**: #184 `[S5] Web UI — scraping interactif` (wave 6, P2, depends on #158 ✅)
**Date**: 2026-07-09
**Status**: validated by operator (4 scoping decisions + 2 section approvals, 2026-07-09)

## 1. Problem

The batch scrape auto-picks TMDB/TVDB matches. Three situations produce silent bad outcomes
or dead ends today (`personalscraper/scraper/confidence.py`):

- **`< LOW_CONFIDENCE (0.5)`** — item is skipped (`skipped_low_confidence`), parked in staging
  forever unless the operator scrapes it manually (MediaElch).
- **Mid band `0.5–0.8`** — batch auto-accepts the best candidate; wrong matches slip through
  silently. (A CLI `interactive=True` mode exists — `prompt_user_choice()`,
  `confidence.py:928` — but it blocks synchronously and is unusable from the web/night runs.)
- **Ambiguous** — two candidates ≥ 0.5 within `AMBIGUITY_DELTA (0.05)`; movies only emit a
  warning (`movie_match_ambiguous`), the pick still happens.

The roadmap flags a structural prerequisite: a pause/resume-on-human-decision seam the batch
pipeline lacks. **Operator decision: the batch never blocks.** The seam is realized as an
async decision queue + immediate targeted re-drive, not a mid-run pause.

## 2. Operator decisions (locked)

| #   | Decision          | Choice                                                                                                                         |
| --- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Interaction model | **Hybrid**: decision queue filled by batch runs + web surface to drain it                                                      |
| 2   | Queue scope       | **All three triggers**: `<0.5`, mid band `0.5–0.8` (batch behavior change: enqueued instead of auto-accepted), ambiguity delta |
| 3   | Resolution effect | **Immediate targeted re-scrape** (detached runner, S3 pattern) pinning the chosen provider ID                                  |
| 4   | Depth             | **Work identity only** (movie/show provider ID) + search override (title/year); season/episode mapping stays automatic         |

Architecture assembly retained: **table + detached runner** (approach 1).

## 3. Data model — migration 013 `scrape_decision`

One row per staging item awaiting an identity decision, in `library.db`:

```sql
CREATE TABLE scrape_decision (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    staging_path    TEXT    UNIQUE NOT NULL,  -- absolute path, NFC-normalized (macFUSE NFD gotcha)
    media_kind      TEXT    NOT NULL,         -- 'movie' | 'tvshow'
    extracted_title TEXT    NOT NULL,         -- title guessed from the folder name
    extracted_year  INTEGER,                  -- year guessed, NULL if none
    trigger         TEXT    NOT NULL,         -- 'below_threshold' | 'mid_band' | 'ambiguous'
    candidates_json TEXT    NOT NULL,         -- snapshot: top-5 scored candidates
    status          TEXT    NOT NULL DEFAULT 'pending',
                    -- 'pending' | 'resolved' | 'dismissed' | 'superseded'
    resolution_json TEXT,                     -- {provider, provider_id, via: 'pick'|'search_override', ...}
    run_uid         TEXT,                     -- run that enqueued (or last refreshed) the row
    created_at      REAL    NOT NULL,         -- epoch seconds (time.time() — epoch invariant)
    updated_at      REAL    NOT NULL,
    resolved_at     REAL
);
CREATE INDEX idx_scrape_decision_status ON scrape_decision(status);
```

`candidates_json` element shape (Pydantic model `DecisionCandidate`, documented in
`docs/reference/indexer-json-shapes.md`): `{provider: 'tmdb'|'tvdb', provider_id: int,
title: str, year: int|null, score: float, poster_url: str|null, overview: str|null}`.

**Upsert semantics** (by `staging_path`, NFC): a batch run refreshes `candidates_json`,
`trigger`, `run_uid`, `updated_at` of a `pending` row; it never resurrects `resolved` /
`dismissed` / `superseded` rows. Timestamps are epoch `time.time()`.

## 4. Enqueue — scrape step changes

- `confidence.py` match functions additionally return the **scored candidate list** (top-5)
  alongside the best match (movies: `match_movie`; TV: `match_tvshow_tvdb`/`match_tvshow`).
  The TV path gains the same ambiguity-delta detection movies already have.
- `movie_service.py` / TV service produce a new `ScrapeResult.action = "queued_for_decision"`
  for the three triggers. For the mid band this **replaces** the current auto-accept
  (operator-assumed batch behavior change). `<0.5` items keep their skip semantics for
  verify/dispatch (item stays in staging) — the decision row is additive.
- A `DecisionWriter` (mirroring `PipelineRunWriter`: fail-soft, own connection, injected
  from the composition boundary — never opened in `_build_app_context` as a lifetime
  resource) performs the upsert.
- `ItemProgressed(step="scrape", status="queued_for_decision", details={trigger, confidence,
candidates_count})` is emitted per enqueued item (bus → Redis → web WS).
- `StepReport`: `queued_for_decision` counted in `counts`; paths listed alongside
  `unmatched_paths` (existing operator-visibility artifact).
- Orphan GC: at enqueue time and at listing time, a `pending` row whose `staging_path` no
  longer exists is marked `superseded`.

## 5. Resolution — `scrape-resolve` CLI + detached runner

**CLI** (testable, human-runnable): `personalscraper scrape-resolve <staging_path>
--provider tmdb|tvdb --id <provider_id>`. Fetches **by ID** (no search) through the existing
service fetch/write paths, writes NFO + artwork into the staging folder, marks the decision
`resolved` (`resolution_json`), exit 0/1/2 (success / scrape error / misconfiguration).
**Lock ownership (R11 conformity)**: `scrape-resolve` **self-acquires** `pipeline.lock` for
its lifetime (same convention as `library-rescrape` — it writes into staging), and is added
to `_CLI_SELF_LOCKING` so the web runner does NOT double-acquire (a double acquisition would
deadlock the child, per the R11 ground-truth table). A direct human CLI invocation is thereby
protected too.

**Web runner** (`personalscraper/web/decisions/runner.py`, S3 pattern verbatim): detached
subprocess, env contract, reserves a `pipeline_run` row (`kind='maintenance'`,
`command='scrape-resolve'`, `options_json={decision_id, provider, provider_id}`) under
`BEGIN IMMEDIATE` before 202, streams output to Redis + 64 KiB ring, finalizes the row on
every exit path. Route-level lock probe → 409 when a pipeline run is active (+ pre-spawn
re-probe, R11 pattern).

**After resolve**: item has a valid NFO → next batch run sees `skipped_already_done`;
verify/dispatch proceed normally. No dispatch is triggered by S5 (unchanged pipeline flow).

## 6. REST surface (S2-S7 conventions: typed models → `make openapi` → schema.d.ts; `guarded_api` perimeter; XRW on mutations; `require_not_staging` on writes)

| Method | Route                         | Contract                                                                                                                             |
| ------ | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| GET    | `/api/decisions`              | `DecisionsResponse` — paginated, `status` filter (default `pending`), `pending_count`                                                |
| GET    | `/api/decisions/{id}`         | `DecisionDetail` (full candidates snapshot) — 404 unknown, 410 superseded                                                            |
| POST   | `/api/decisions/{id}/search`  | body `{title, year?}` → fresh `DecisionCandidate[]` (live provider search, no persistence) — read-only, session+XRW                  |
| POST   | `/api/decisions/{id}/resolve` | body `{provider, provider_id}` → **202** `{run_uid}` — 404/410, **409** pipeline lock held or a resolve already running, staging 403 |
| POST   | `/api/decisions/{id}/dismiss` | marks `dismissed` (manual/MediaElch path) → 200 — staging 403                                                                        |

## 7. Frontend — `/decisions` page + shell badge

- **Page `/decisions`** (mobile-first, shadcn/TanStack, DS components): pending-decision list
  (extracted title, folder, trigger chip, candidate count) → detail panel: candidate cards
  (poster, title, year, score bar), title/year override form → `search` for fresh candidates,
  actions **Choisir** (resolve), **Re-chercher**, **Ignorer** (dismiss). Live resolve output
  reuses `RunLogFeed` (S3); on success the item leaves the list
  (`invalidateQueries(['decisions'])` + `['pipeline','history']`).
- **Badge**: pending count in the shell nav; refetch triggered by the WS
  `queued_for_decision` ItemProgressed envelopes and after resolve/dismiss mutations.
- Typed client helpers via `apiFetch` `params` (R15 — no raw fetch).
- Resolution history is visible in the existing unified run history
  (`command='scrape-resolve'`; RunDetail maintenance branch renders command + output_tail).

## 8. Error handling

- Resolve while a pipeline run holds the lock → 409 with detail; UI toast + retry.
- Runner failure (provider down, invalid ID) → decision stays `pending`, run row `error`
  with `output_tail`; UI surfaces the failed run inline.
- `search` provider failure → 502-mapped `ApiError` detail toast; no state change.
- Superseded (folder gone) → 410 on detail/resolve; list GC marks + hides.
- Concurrent double-resolve of the same decision → the `pipeline_run` reservation +
  `scrape-resolve` self-lock serialize; second POST gets 409.
- No new config knob (YAGNI): existing thresholds (`HIGH_CONFIDENCE`, `LOW_CONFIDENCE`,
  `AMBIGUITY_DELTA`) drive the triggers; behavior change documented in `web-ui.md` §S5 +
  `scraping.md`.

## 9. Testing

- **Unit**: trigger matrix (0.49 → below_threshold; 0.65 → mid_band; 0.85+runner-up 0.83 →
  ambiguous; 0.85 clean → auto), upsert NFC dedup + dismissed non-resurrection, migration 013,
  orphan GC, fetch-by-ID service paths with **golden fixtures** (vacuous-test lesson).
- **Routes**: list/detail/search/resolve/dismiss happy + 401/400(XRW)/403(staging)/404/409/410
  on the `_mount_guarded` harness.
- **Runner lifecycle** (S3-style, real child): success → NFO written + decision resolved +
  row success; failure → pending + row error; `pipeline.lock` held during child (LOCK_HELD
  e2e probe) via the `scrape-resolve` self-acquire.
- **Frontend**: vitest — page render, candidate pick flow, badge count, dismiss;
  lint + typecheck + vitest triple gate.
- **ACC (SH-16 executable)**: enqueue observed on a real `--dry-run`-first run; live resolve
  exercised on staging-safe data; badge count via authenticated curl; every ACC-NN is a shell
  command with expected output.

## 10. Phases (indicative — plan will refine)

1. Migration 013 + `DecisionWriter` + confidence.py candidate surfacing + enqueue wiring.
2. `scrape-resolve` CLI (fetch-by-ID, self-locking) + web runner + journal wiring.
3. REST routes + models + OpenAPI regen.
4. Frontend `/decisions` page + badge + typed client.
5. Integration gates + ACC + docs (`web-ui.md` §S5, `scraping.md`, `indexer-json-shapes.md`).

## Out of scope (operator-locked)

- Mid-run blocking pause / intra-run decision injection (approach 3, rejected).
- Season/episode-level arbitration (depth decision #4).
- Changes to dispatch/verify semantics; multi-user; notifications beyond the badge.
