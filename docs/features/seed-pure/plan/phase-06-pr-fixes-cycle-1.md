# Phase 6 — PR fixes cycle 1

> Fixes from `/implement:pr-review` cycle 1 (PR #201, 5-lens review). 1 major + 1 medium + minor type/consistency/doc. Ignored: namespace-collision doc note, seed-list completed-only note, list-column assertion (cosmetic).

**Goal:** Fix the **major** Transmission no-category corruption (the feature silently fails on Transmission for category-less torrents — its headline use case), make the reserved clean-side flag non-silent, and tighten the PR's own protocol typing + defensive-read consistency.

---

## Gate

Phase 5 complete: `make check` green (6858 passed), PR #201 open, CI green.

---

## Sub-phase 6.1 — Fix Transmission no-category corruption (F-A, MAJOR)

**Files:** `personalscraper/api/torrent/transmission.py`, `tests/api/torrent/test_tagger.py`, `tests/unit/test_transmission_add.py` (plan-drift — see note below).

> **PLAN-DRIFT (6.1):** `tests/unit/test_transmission_add.py::TestLabelsHelper::test_no_category` directly asserted the pre-fix (buggy) `_labels(None, ["action"]) == ["action"]` contract. Updated to the sentinel contract `== ["", "action"]` so the regression gate does not re-assert the corruption. The parametrized `test_d5_round_trip_stable_for_supported_inputs` and `tests/unit/test_transmission_tags.py` only exercise category-present / no-labels cases, so they stay green unchanged.

**Root cause:** Transmission stores `labels=[category, *tags]` (flat). For a torrent with **no category** (`labels=[]`), `add_tags(["seed-pure"])` writes `labels=["seed-pure"]`; `_torrent_item` then reads `labels[0]` as the category → `tags=[]` → the ingest skip (`SEED_PURE in tags`) never fires. `add()` already rejects this ambiguity (`ValueError`, "review #6"); the tagger must instead **make it work** (the operator wants the tag applied), so use an **empty-string sentinel** for the no-category slot.

### Task 1 — sentinel for the no-category slot (consistent across all label round-trip sites)

- [x] **F-A.1 — `_labels(category, tags)`:** when `category is None` **and** `tags` is non-empty, return `["", *deduped_tags]` (empty-string sentinel = "no category"); when `category is None` and `tags` empty, return `[]` (unchanged); when `category` set, `[category, *deduped_tags]` (unchanged). (`add()` never passes `category=None`+tags — it rejects first — so this only affects the tagger path.) Document the sentinel in the `_labels` docstring.
- [x] **F-A.2 — read side treats `labels[0] == ""` as no-category** in BOTH `_torrent_item` and the read-first of `add_tags`/`remove_tags`: `if labels and labels[0] == "": category = None; tags = labels[1:]` else the existing `category = labels[0] if labels else None; tags = labels[1:]`. (Extract a tiny module-level helper `_split_labels(labels) -> tuple[str | None, list[str]]` and use it in all THREE sites to avoid drift — the type-design lens flagged the heuristic is duplicated in 4 places.)
- [x] **Tests (test_tagger.py):**
  - `test_tx_add_tags_no_category_roundtrips_as_tag` (**LOAD-BEARING regression**): `_mock_torrent([])` (no category) → `add_tags("h", ["seed-pure"])` → assert `change_torrent` called with `labels=["", "seed-pure"]`; then feed `["", "seed-pure"]` through `_torrent_item` (or `_split_labels`) and assert `category is None` AND `SEED_PURE in tags` (the property the whole feature depends on). **Mutation-proof:** fails against the pre-fix code (which writes `labels=["seed-pure"]` → read back as category, `SEED_PURE not in tags`). Verified: pre-fix `add_tags([])` wrote `["seed-pure"]` (scratch reproduction) and pre-fix `remove_tags(["", "seed-pure"])` left an orphan `['']`.
  - `test_tx_remove_tags_no_category`: `_mock_torrent(["", "seed-pure"])` → `remove_tags(["seed-pure"])` → `change_torrent(labels=[])`.
  - Keep the existing category-preservation golden (`["movies", ...]`) green — the sentinel must NOT affect the with-category path. (Stayed green.)
- [x] **Gate 6.1:** `pytest tests/api/torrent/test_tagger.py -q` (16 passed); ruff + `mypy personalscraper/api/torrent/transmission.py` clean; regression `tests/api/torrent/ tests/unit/test_transmission*.py` 66 passed.
- [x] **Commit:** `fix(seed-pure): Transmission tagger preserves seed-pure as a tag on category-less torrents (no-category sentinel)`

---

## Sub-phase 6.2 — Reserved flag non-silent + protocol typing + consistency (F-B..F-F)

**Files:** `personalscraper/conf/models/scraper.py`, `personalscraper/sorter/run.py`, `personalscraper/pipeline_steps.py`, `personalscraper/commands/seed.py`, tests.

- [x] **F-B (MEDIUM) — reserved flag must not lie.** Add a Pydantic validator to `ProcessCleanConfig` that **raises** (`ValueError`) if `verify_seed_pure is True`, with a message like "process_clean.verify_seed_pure is reserved and not yet enforced (clean-side guard intentionally not implemented — see DESIGN §4.2). The active guardrails are the always-on ingest skip + the opt-in sort guard." Keeps the flag (config symmetry) but makes enabling it fail loudly instead of silently doing nothing. Test: `pytest.raises(ValidationError)` for `ProcessCleanConfig(verify_seed_pure=True)`; default `False` still builds.
- [x] **F-C (MINOR) — type `run_sort` against the protocol it extends.** Change `run_sort`'s `torrent_client: object | None` → `torrent_client: "TorrentLister | None"` (import `TorrentLister` from `api/torrent/_contracts` under `TYPE_CHECKING`), drop the `# type: ignore[attr-defined]` on `get_completed()`, and use `t.tags` directly (TorrentItem always has it). Same in the `SortStep` wiring in `pipeline_steps.py` if it annotates the client. Keep the `try/except` fail-soft.
- [x] **F-D (MINOR) — `seed list` defensive read.** In `commands/seed.py`, change `SEED_PURE in t.tags` → `SEED_PURE in (getattr(t, "tags", None) or [])` for consistency with the ingest/sort sibling guards added in this feature.
- [x] **F-E (MINOR) — `run_sort` docstring clarity.** Add a sentence to the `torrent_client` arg doc: the standalone `sort` command does NOT wire a client (pipeline-only guard, by design — DESIGN §4.2); the flag has effect only on the full-pipeline path.
- [x] **F-F (MINOR) — sort-guard log context.** In `run_sort`'s `except` for the guard, add `error_type=type(exc).__name__` and a `consequence="sort proceeds with empty seed-pure skip set; ingest-skip remains the authoritative guardrail"` to the `log.warning`.
- [x] **Gate 6.2:** ruff + `mypy` on the touched source; `pytest tests/conf/ tests/sorter/ tests/commands/test_seed.py -q` (new + no regression).
- [x] **Commit:** `fix(seed-pure): reject the reserved clean-side flag + type run_sort against TorrentLister + defensive seed-list + log context`

---

## Final gate (main session, phase 6 milestone)

`make check` green + `python -c "import personalscraper"` smoke (no docs/feature_map change → design-gaps unchanged). Then mark phase 6 `[x]`.
