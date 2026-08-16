# DESIGN — spine-actions (epic F4)

**Feature**: Targeted maintenance actions driven by the provenance spine.
**Type**: feat · **Bump**: 0.70.0 → 0.71.0 (minor) · **Branch**: `feat/spine-actions` · **Ticket**: #364
**Epic**: provenance tracking-spine (F0 → F5), roadmap `docs/archive/features/provenance/EPIC-ROADMAP.md`.

## 1. Intent (operator-ratified)

Roadmap §F4: _sur le spine — reprendre un item bloqué, re-scraper un grab précis, requeue par
état de parcours. Le registre devient le substrat des actions de maintenance ciblées._ Default
(autonomous contract): **CLI + web buttons**. Epic clause: LINK/reuse, don't rewrite; advisory
spine writes stay fail-soft; no DB fusion.

## 2. Design (reuse the established seams)

Three verbs, each reusing an existing mechanism keyed on a provenance row:

| Verb                                                         | Substrate                                                                | Mechanism (reused)                                                                                                                                                                  |
| ------------------------------------------------------------ | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Re-scrape a precise grab** / resume a stuck-at-scrape item | `ProvenanceRow` (info_hash → `media_ref` seed + `current_path` + `kind`) | forced scrape `scrape_{movie,tvshow}_forced(current_path, id)` on the staging folder + keep the spine live (`move_path` + `set_scrape_run`), exactly the F2 scrape-resolve template |
| **Requeue by journey state**                                 | `ProvenanceRow.info_hash` → `wanted.grabbed_hash` / `followed_id`        | `WantedStore.requeue_missing(wanted_id)` (→ pending, grabbed_hash NULL); the next grab re-acquires                                                                                  |
| **Stuck detection** (the substrate)                          | new `list_stuck(status, older_than)`                                     | in-flight rows (`status != 'dispatched'`) past an age, whose `current_path` still exists on disk (FS = truth, mirrors `prune_stale`)                                                |

**Surface choice**: route the web actions through the **acquisition-trigger** pattern
(`web/routes/acquisition_triggers.py` + `web/acquisition/runner.py`), NOT the `library-*`
maintenance registry — the registry-sync test constrains ids to `library-*`, and these are
acquisition-scoped per-item actions. Each action spawns a detached CLI runner, reserves a
`pipeline_run` row (`kind='maintenance'`), streams to Redis→WS, and reuses the liveness/idempotence
guards. Re-scrape holds the **per-staging-item scrape lock** (`acquire_scrape_resolve_lock`, exit 3
on busy) — NOT the global pipeline.lock — so distinct items re-scrape in parallel while staying
mutually exclusive with a full run. Requeue takes **no lock** (atomic wanted transition).

## 3. Data / store additions

`_ProvenanceSubStore.list_stuck(older_than, exists_fn, *, statuses=("grabbed","ingested","scraped"))`
— fail-soft (empty list on error): `SELECT * … WHERE status IN (…) AND current_path IS NOT NULL AND
COALESCE(scraped_at, ingested_at, grabbed_at) < :older_than`, then filter to rows whose
`current_path` still `exists_fn()` (the on-disk-and-idle definition of "stuck"; a vanished folder is
a candidate for `prune_stale`, not a resume). `dispatched`/`reconciled` are terminal, excluded.
Port (`ProvenanceSubStore`) extended. No migration (read-only query over existing columns).

## 4. CLI (new module `personalscraper/commands/spine.py`)

Two commands, registered on the shared Typer app, each `@handle_cli_errors` + `cli_run_row`:

- **`acquisition-rescrape [--hash H | --path P | --stuck] [--older-than SECONDS] [--dry-run]`** —
  for each targeted tracked staging item: look up its `ProvenanceRow`, resolve the forced id from
  `media_ref` (`kind='movie'` → tmdb; `episode` → tvdb, falling back to tmdb), acquire the per-item
  scrape lock, run `scrape_{movie,tvshow}_forced(current_path, id)`, verify an NFO landed, and keep
  the spine live (`move_path` old→final + `set_scrape_run(final, run_uid, scraped_at)`). Skips a row
  with no `media_ref` (a manual item — direct it to the decision path). `--stuck` fans over
  `list_stuck`. Advisory + fail-soft per item; a per-item failure never aborts the batch.
- **`acquisition-requeue --hash H [--dry-run]`** — trace `info_hash` → wanted row(s) (by
  `grabbed_hash`, else `followed_id`+kind), `requeue_missing` each (→ pending). The item re-enters
  the grab queue on the next run. No lock.

Both record `cli_run_row` counts (`rescraped`/`requeued`/`skipped`) so the web runner surfaces them.

## 5. Web (acquisition-trigger pattern) + frontend

- **`GET /api/acquisition/journeys`** gains a computed `stuck: bool` per item (in-flight + folder
  exists + past the default idle age) so the UI can flag actionable items. (Read-only; no new store
  state.) ⇒ `make openapi`.
- **`POST /api/acquisition/journeys/{info_hash}/rescrape`** and **`…/requeue`** — guarded
  (`require_not_staging` + `require_x_requested_with` + `guarded_api`), reserve a `pipeline_run` row
  and spawn the CLI via a new `PERSONALSCRAPER_ACQ_COMMAND` branch (`rescrape`/`requeue`) in
  `web/acquisition/runner.py::_build_argv`; 202 + idempotence via the existing liveness guard.
- **`ParcoursPanel`**: per-journey action buttons (« Re-scraper », « Requeue ») + a « Bloqué » badge
  when `stuck`. Product-intent §pipeline-lisible / acquisition-visibility: the operator sees a stuck
  acquisition and acts in one click. Mobile 390px.

## 6. Non-regression guarantees (tested)

- Manual/direct item (no spine row): re-scrape/requeue is a no-op (nothing to act on), ACC-06.
- The forced-scrape resolve path (`scrape_resolve.py`), `library-rescrape`, and the maintenance
  registry (+ its sync test) are **untouched**.
- Every spine write stays `_safe_write`; `list_stuck` is fail-soft (empty on error).
- Re-scrape holds only the per-item scrape lock (parallel-safe, mutually exclusive with a full run);
  requeue is lock-free. Both staging-guarded.
- Grab-direct / personalscraper-without-follow unaffected (F0 ACC-06 both senses).

## 7. ACCEPTANCE (executable)

- **ACC-F4-01** — `list_stuck` returns an in-flight, on-disk, aged row and excludes dispatched /
  vanished / fresh rows.
- **ACC-F4-02** — `acquisition-rescrape --hash H` re-scrapes the tracked item via the forced id from
  its `media_ref`, keeps `current_path` live, and records the scrape stage (integration).
- **ACC-F4-03** — `acquisition-requeue --hash H` sets the linked wanted row back to `pending`.
- **ACC-F4-04** — the rescrape/requeue web endpoints are staging-guarded (403 on staging) and
  auth-guarded (401 without session); a live run 409s (idempotence).
- **ACC-F4-05** — `GET /journeys` exposes `stuck` and a manual item never appears as rescrapable.
- **ACC-F4-06** — `make check` green; `make openapi` no drift; frontend gates green.

## 8. Phases

1. **Spine substrate** — `list_stuck` (+ port) + a `stuck` flag on `JourneyItem`/`get_journeys`;
   unit tests + endpoint test.
2. **CLI actions** — `commands/spine.py` (`acquisition-rescrape` + `acquisition-requeue`), reusing
   the forced-scrape + wanted-requeue seams; integration tests (rouge-avant), anti-regression.
3. **Web + frontend** — guarded trigger endpoints + runner `_build_argv` branch + ParcoursPanel
   buttons/badge + `make openapi` + frontend tests. Phase gate + PR.
