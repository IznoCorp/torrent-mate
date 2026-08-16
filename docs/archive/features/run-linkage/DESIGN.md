# DESIGN — run-linkage (epic F3)

**Feature**: Link each `pipeline_run` to the acquisitions it processed.
**Type**: feat · **Bump**: 0.69.0 → 0.70.0 (minor) · **Branch**: `feat/run-linkage` · **Ticket**: #362
**Epic**: provenance tracking-spine (F0 → F5), roadmap `docs/archive/features/provenance/EPIC-ROADMAP.md`.

## 1. Intent (operator-ratified)

Roadmap §F3: _lier chaque `pipeline_run` aux acquisitions qu'il a traitées (quels grabs ont coulé
dans quel run) → « quel run a scrapé / dispatché ce média ? » devient répondable._ Consolidates the
"pipeline execution" pillar onto the spine. Epic clause: LINK, don't rewrite; no acquire.db+library.db
fusion; fail-soft advisory.

## 2. The design driver (why per-stage columns, not one run id)

An acquisition is advanced by **different runs** at different stages:

- **grab** runs as its OWN `pipeline_run` (`kind='maintenance'`, `command='grab'`), OUTSIDE any full
  `personalscraper run`. Its `current_correlation_id` is a fresh uuid **misaligned** with its own
  run row — so the grab stamp must read the `CliRunRecorder.run_uid` handle, NOT the ContextVar.
- **ingest / sort / scrape / dispatch** run inside `Pipeline.run()`, which binds
  `current_correlation_id = str(run_id)`; `.hex` == that run's `pipeline_run.run_uid` (the exact
  reconstruction the scrape finalizer already does for `scrape_decision`).

So the run that _grabbed_ an item ≠ the run that _scraped/dispatched_ it. A single `run_uid` column
would be overwritten and lie. F3 uses **per-stage nullable columns**, paralleling the existing `*_at`
set. Cross-DB (pipeline_run in library.db, spine in acquire.db) ⇒ **no FK**, advisory back-link only
(same pattern as 010's `followed_id`, 011's `decision_id`).

## 3. Data model (migration 012 — additive ALTER)

`ALTER TABLE staging_provenance ADD COLUMN` ×4, nullable TEXT, `user_version` 11 → 12, one transaction.

| Column             | Stamped at                        | Source of run_uid                                        |
| ------------------ | --------------------------------- | -------------------------------------------------------- |
| `grab_run_uid`     | `upsert_grab`                     | the grab command's `CliRunRecorder.run_uid` (hex)        |
| `ingest_run_uid`   | `set_ingest`                      | `current_correlation_id` → `.hex` (pipeline ingest step) |
| `scrape_run_uid`   | new `set_scrape_run` (path-keyed) | `current_correlation_id` → `.hex` (scrape)               |
| `dispatch_run_uid` | `record_dispatch_by_path`         | `current_correlation_id` → `.hex` (dispatch)             |

All nullable: a grab via qBittorrent-direct (no row at all, ACC-06), a grab with no indexer DB, or any
stage that cannot resolve a run degrades to NULL — never an error.

## 4. Write path (advisory, fail-soft)

Each stage-write method gains an **optional** `run_uid: str | None = None` param, stamped inside the
existing `_safe_write` (best-effort, swallowed). New `set_scrape_run(staging_path, *, run_uid)` —
path-keyed (like `move_path`), NFC/NFD-robust, UPDATE-only (no-op when untracked), called once per
scraped item in the scrape orchestrator (confident OR ambiguous). Ports extended:
`StagingProvenanceWriter` (core) gains `run_uid` on `set_ingest`/`record_dispatch_by_path` + a
`set_scrape_run`; `ProvenanceSubStore` mirrors it.

Wiring (each a small, fail-soft addition; no stage behaviour changes):

- **grab** — `commands/grab.py` already owns the `CliRunRecorder`; thread its `run_uid` into the grab
  pass → `upsert_grab(..., run_uid=...)`.
- **ingest** — `pipeline_steps.py`/`ingest.py`: derive `run_uid` from `current_correlation_id` → `set_ingest(..., run_uid)`.
- **scrape** — `scraper/run.py` derives `run_uid` (already does, for `scrape_decision`) and passes it to
  the `Scraper`; the orchestrator calls `set_scrape_run(result.media_path, run_uid)` per item.
- **dispatch** — `delete_authority.record_dispatch`: derive `run_uid` from `current_correlation_id`
  → `record_dispatch_by_path(..., run_uid)`.

`pipeline_run` / `PipelineRunWriter` / `steps_json` stay **untouched** (authoritative, not rewritten).

## 5. Read surface (both directions answerable)

- **Journey → run** (`JourneyItem` + `ParcoursPanel`): expose `grab_run_uid` / `ingest_run_uid` /
  `scrape_run_uid` / `dispatch_run_uid`. The « Scrapé » / « Rangé » stage chips deep-link to the run
  detail (`/pipeline?run=<uid>` — the existing redirect route) so "which run scraped/dispatched this?"
  is one click.
- **Run → acquisitions** (converse): a `list_journeys_for_run(run_uid)` store method (matches any
  `*_run_uid` column) exposed via `GET /api/acquisition/journeys?run_uid=<uid>`, so a run-detail view
  can list "acquisitions this run processed". ⇒ `make openapi`.

## 6. Non-regression guarantees (tested)

- Every column nullable + every write fail-soft: a wiped registry / missing run ⇒ today's behaviour.
- Manual/direct item (no spine row): no run stamp (UPDATE-only no-op), ACC-06 preserved.
- `pipeline_run` and its web views unchanged; the F0/F1/F2 stage writes unchanged except the new
  optional `run_uid` param (defaulted None → existing callers unaffected).
- Grab stamp uses the recorder handle, not the misaligned ContextVar (correctness, per the map).

## 7. ACCEPTANCE (executable)

- **ACC-F3-01** — migration applies, version 12, 4 run columns present.
- **ACC-F3-02** — a full pipeline stamps `ingest_run_uid`/`scrape_run_uid`/`dispatch_run_uid` with the
  run's hex uid on a tracked item (integration: correlation bound → run_uid on the row).
- **ACC-F3-03** — grab stamps `grab_run_uid` from the recorder handle (not the ContextVar).
- **ACC-F3-04** — `GET /api/acquisition/journeys?run_uid=<uid>` returns only acquisitions that run touched.
- **ACC-F3-05** — untracked/manual item never gets a run stamp; wiped registry ⇒ today's behaviour.
- **ACC-F3-06** — `make check` green; `make openapi` no drift; frontend gates green.

## 8. Phases

1. **Schema + store** — migration 012, `ProvenanceRow` fields, optional `run_uid` on the stage-writes
   - `set_scrape_run` + `list_journeys_for_run`, ports; unit tests + migration-version bump.
2. **Wire the 4 stages** — grab (recorder handle) / ingest / scrape (orchestrator) / dispatch;
   integration tests that a run's uid lands on the row; grab-alignment + manual-item no-op tests.
3. **Read surface** — JourneyItem run fields + `?run_uid=` filter + `make openapi`; ParcoursPanel run
   deep-links; frontend tests. Phase gate + PR.
