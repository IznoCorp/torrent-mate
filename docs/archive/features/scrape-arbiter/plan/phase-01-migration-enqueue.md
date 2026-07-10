# Phase 1 — Migration 013 + DecisionWriter + Candidate Surfacing + Enqueue Wiring

## Gate

- [ ] `feat/scrape-arbiter` branch exists on current `origin/main`
- [ ] DESIGN.md validated by operator (2026-07-09)
- [ ] `make lint` + `make test` green on clean checkout

---

### Sub-phase 1.1 — Migration 013 `scrape_decision`

**Creates:** `personalscraper/indexer/migrations/013_scrape_decision.sql`
**Modifies:** (none)
**Test:** `tests/indexer/test_migrations.py` (assert version 13 present, table shape)

**DESIGN ref:** §3 table schema (all columns, `idx_scrape_decision_status` index, upsert
semantics by `staging_path`, NFC normalization requirement)

SQL script creates `scrape_decision` table with columns: `id`, `staging_path` (UNIQUE NOT
NULL), `media_kind` (NOT NULL, `'movie'` or `'tvshow'`), `extracted_title` (NOT NULL),
`extracted_year` (INTEGER nullable), `trigger` (NOT NULL, `'below_threshold'` /
`'mid_band'` / `'ambiguous'`), `candidates_json` (TEXT NOT NULL), `status` (TEXT NOT NULL
DEFAULT `'pending'`), `resolution_json` (TEXT), `run_uid` (TEXT), `created_at` (REAL NOT
NULL), `updated_at` (REAL NOT NULL), `resolved_at` (REAL). Index on `status`. `INSERT INTO
schema_version(version) VALUES (13); PRAGMA user_version = 13;`. Test: `test_migrations.py`
already validates version chain; extend assertion to verify table + index exist + column
types.

**Commit:** `feat(scrape-arbiter): add migration 013 scrape_decision table`

---

### Sub-phase 1.2 — DecisionCandidate model + JSON shape doc

**Creates:** `personalscraper/scraper/decision_candidate.py`
**Modifies:** `docs/reference/indexer-json-shapes.md` (add `DecisionCandidate` section)

**DESIGN ref:** §3 `candidates_json` element shape (`DecisionCandidate` Pydantic model:
`provider`, `provider_id`, `title`, `year`, `score`, `poster_url`, `overview`)

Model `DecisionCandidate(BaseModel)` with fields matching DESIGN §3 shape. Used by
`DecisionWriter` (sub-phase 1.3) for serialization validation and by REST routes (phase 3)
for response models. Update `indexer-json-shapes.md` documenting the JSON column shape with
a Pydantic model reference and example JSON. Test: `tests/scraper/test_decision_candidate.py`
— round-trip serialization, nullable fields, field types.

**Commit:** `feat(scrape-arbiter): add DecisionCandidate model and JSON shape doc`

---

### Sub-phase 1.3 — DecisionWriter

**Creates:** `personalscraper/scraper/decision_writer.py`
**Test:** `tests/scraper/test_decision_writer.py`

**DESIGN ref:** §4 `DecisionWriter` (mirrors `PipelineRunWriter`: fail-soft, own
connection, injected from composition boundary — never opened in `_build_app_context`)

`DecisionWriter(db_path: Path)` class with methods:

- `upsert(staging_path, media_kind, extracted_title, extracted_year, trigger,
candidates_json, run_uid)` — opens short-lived `sqlite3` connection (WAL pragmas),
  NFC-normalizes `staging_path`, uses `INSERT ... ON CONFLICT(staging_path) DO UPDATE
... WHERE scrape_decision.status='pending'` (NOT `INSERT OR REPLACE` — which would
  clobber the status of non-pending rows). Sets `created_at = updated_at =
time.time()` on insert; refreshes `candidates_json`, `"trigger"`, `run_uid`,
  `updated_at` on update. Never resurrects resolved/dismissed/superseded rows.
- `mark_superseded_orphans()` — marks `pending` rows where `staging_path` no longer
  exists on disk as `'superseded'`. Run at enqueue + listing time.
- `resolve(decision_id, provider, provider_id, via="pick")` — sets
  `status='resolved'`, `resolution_json`, `resolved_at`, `updated_at`.
- `dismiss(decision_id)` — sets `status='dismissed'`, `updated_at`.
- All methods fail-soft: try/except, log warning, never raise.

Test: upsert NFC dedup, dismissed non-resurrection, orphan GC, connection lifecycle
(short-lived, no leak), fail-soft behavior.

**Commit:** `feat(scrape-arbiter): add DecisionWriter with upsert and orphan GC`

---

### Sub-phase 1.4 — confidence.py candidate surfacing + TV ambiguity delta

**Modifies:** `personalscraper/scraper/confidence.py`
**Test:** `tests/scraper/test_confidence.py`

**DESIGN ref:** §4 — match functions additionally return scored candidate list (top-5)
alongside best match; TV path gains ambiguity-delta detection

**Plan correction (detailed-variants, 2026-07-09):** The original plan prescribed
changing `match_movie()` and `match_tvshow_tvdb()` to return a tuple. The actual
implementation instead created NEW `_detailed`-variant functions
(`match_movie_detailed`, `match_tvshow_tvdb_detailed`, `match_tvshow_detailed`)
that return `(MatchResult | None, list[DecisionCandidate])`, while the existing
public signatures (`match_movie`, `match_tvshow_tvdb`, `match_tvshow`) are kept as
thin wrappers returning only `MatchResult | None`. This avoids touching ~60
existing call sites across the codebase that only consume the best match.

Detailed-variant functions:

- `match_movie_detailed(tmdb_client, title, year)` — l.418
- `match_tvshow_tvdb_detailed(tvdb_client, title, year, local_seasons=None)` — l.630
- `match_tvshow_detailed(tmdb_client, tvdb_client, title, year, local_seasons=None)` — l.939

Each follows the same search, scoring, and content-aware disambiguation as the
original, but additionally returns the top-5 scored candidates as
`DecisionCandidate` instances. The TVDB path emits a `tvshow_match_ambiguous`
warning (l.752) when the top two candidates are both ≥ `LOW_CONFIDENCE` (0.5) and
within `AMBIGUITY_DELTA` (0.05) — the same ambiguity detection movies have via
`movie_match_ambiguous`.

**Test fix (2026-07-09):** `test_tvdb_ambiguous_emits_warning` originally used
"Similar Show A" / "Similar Show B" as TVDB returned titles. The superstring
penalty (`_superstring_penalty`) treats "A" as a noise token (article, dropped →
no penalty) but "B" as a content word (→ -0.08 penalty). This created a score gap
of 0.08 > 0.05 AMBIGUITY_DELTA, so the ambiguity warning never fired. Fixed by
using identical-name candidates ("Ambiguous Show", different provider IDs), which
guarantee identical scores and a gap of 0.0 < 0.05 without scoring-function
interference.

Test matrix per DESIGN §9: 0.49 → below_threshold, 0.65 → mid_band, 0.85 +
runner-up 0.83 → ambiguous, 0.85 clean → auto. 97 tests pass.

**Commit:** `feat(scrape-arbiter): surface top-5 candidates and add TV ambiguity delta`

---

### Sub-phase 1.5 — ScrapeResult.action queued_for_decision + enqueue wiring

**Modifies:** `personalscraper/scraper/_shared.py`, `personalscraper/scraper/movie_service.py`,
`personalscraper/scraper/tv_service.py`, `personalscraper/scraper/run.py`
**Test:** `tests/scraper/test_scraper.py`, `tests/scraper/test_tv_service_extra.py`

**DESIGN ref:** §4 — `ScrapeResult.action = "queued_for_decision"` for three triggers;
mid-band replaces auto-accept; `<0.5` additive row

Add `"queued_for_decision"` to `ScrapeResult.action` docstring and usage. In
`movie_service.py` and `tv_service.py`: after confidence scoring, for triggers
`below_threshold` / `mid_band` / `ambiguous`, set `result.action = "queued_for_decision"`
and store `result.candidates = [...]` (list of `DecisionCandidate`, new optional field on
`ScrapeResult`). Mid-band: **replace** auto-accept — set action to
`"queued_for_decision"` instead of `"scraped"`. `<0.5`: keep `"skipped_low_confidence"`
action but **additively** set a `decision_candidates` attribute. In `run.py`: after
collecting `ScrapeResult`s, iterate items with `action == "queued_for_decision"` (or
decision candidates set), call `DecisionWriter.upsert()`, emit `ItemProgressed`, call
`DecisionWriter.mark_superseded_orphans()`.

**Commit:** `feat(scrape-arbiter): wire queued_for_decision enqueue into scrape step`

---

### Sub-phase 1.6 — StepReport counting + ItemProgressed emission

**Modifies:** `personalscraper/scraper/run.py`, `personalscraper/models.py`
**Test:** `tests/scraper/test_run.py`

**DESIGN ref:** §4 — `ItemProgressed(step="scrape", status="queued_for_decision",
details={...})`; `StepReport` counts `queued_for_decision`; paths in `unmatched_paths`

Add `queued_for_decision` count to `StepReport.counts` dict. Append queued staging paths
to `StepReport.unmatched_paths` (existing operator-visibility artifact, consistent with
current `skipped_low_confidence`). Emit `ItemProgressed` per enqueued item:
`step="scrape"`, `item=str(staging_path)`, `status="queued_for_decision"`,
`details={trigger, confidence, candidates_count}`. Test: assert `StepReport.counts`
includes `queued_for_decision` key; assert `ItemProgressed` events are emitted on event
bus for each enqueued item (mock event bus capture).

**Commit:** `feat(scrape-arbiter): emit ItemProgressed and count queued_for_decision in StepReport`
