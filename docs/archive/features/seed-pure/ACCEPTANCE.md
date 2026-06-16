# ACCEPTANCE — seed-pure (Seed Safety O1)

Every criterion below is an **executable shell command** with a documented
expected output (SH-16 rule). Run from the repo root with the `personalscraper`
package installed (`pip install -e ".[dev]"`).

Re-exercise ALL criteria before squash merge.

> **Re-scope note (DESIGN §4.2 / §7 / §8-B):** the real, always-on guardrail is
> the **ingest** skip. The sort-side guard is **opt-in** (`config.sort.verify_seed_pure`,
> default off) and performs a **genuine exclusion**. The clean-side
> `config.process_clean.verify_seed_pure` flag exists for config symmetry but is
> **reserved / not enforced** — there is intentionally **no** seed-pure code in
> `process/` (post-sort name-matching against renamed items is unreliable). ACC-07
> and ACC-08 pin this re-scope.

---

## ACC-01 — `SEED_PURE` constant importable from `core.tags`, value `"seed-pure"`

**Command:**

```bash
python -c "from personalscraper.core.tags import SEED_PURE; assert SEED_PURE == 'seed-pure'; print('ACC01_OK')"
```

**Expected:** prints `seed-pure` is the value; the assertion holds and the script
prints `ACC01_OK` (exit 0).

---

## ACC-02 — qBittorrent tagger: `add_tags`/`remove_tags` call the right `qbittorrentapi` endpoints; idempotent (empty list = no-op); protocol compliance

**Command:**

```bash
pytest tests/api/torrent/test_tagger.py -k "qbit" --tb=short -q
```

**Expected:** `5 passed, 9 deselected`, `0 failed` — covers `torrents_addTags`/
`torrents_removeTags` call assertions, empty-list no-ops (add + remove), and
`isinstance(client, TorrentTagger)` protocol compliance.

---

## ACC-03 — Transmission tagger: `add_tags`/`remove_tags` preserve `labels[0]` (category) via read-first write; idempotent

**Command:**

```bash
pytest tests/api/torrent/test_tagger.py -k "tx_add_tags_preserves_category or tx" --tb=short -q
```

**Expected:** `7 passed, 7 deselected`, `0 failed` — covers the
category-preservation golden (`test_tx_add_tags_preserves_category` /
`test_tx_remove_tags_preserves_category`: category at `labels[0]` survives a
read-first add/remove), idempotent add-already-present / remove-absent, empty-list
no-ops, and protocol compliance.

---

## ACC-04 — `seed mark`/`unmark` call the tagger with `[SEED_PURE]`; `seed list` filters by tag; no-client exits 1; layering

**Command:**

```bash
pytest tests/commands/test_seed.py --tb=short -q
```

**Expected:** `6 passed`, `0 failed` — covers `mark` → `add_tags(hash, [SEED_PURE])`,
`unmark` → `remove_tags(hash, [SEED_PURE])`, `list` shows only seed-pure torrents
(and an empty render when none are tagged), no-client exits non-zero, and the
`commands/seed.py` does-not-import-indexer layering guard.

---

## ACC-05 — Ingest skip golden + ordering: seed-pure torrent skipped (`skip_count` incremented, `ItemProgressed(status='skipped', reason='seed_pure')` emitted, `get_content_path` not called); non-tagged torrent NOT skipped by this check; below-ratio + seed-pure counted once

**Command:**

```bash
pytest tests/ingest/test_ingest_seed_pure.py --tb=short -q
```

**Expected:** `5 passed`, `0 failed` — covers `skip_count == 1`, the
`ItemProgressed(status='skipped', reason='seed_pure')` event, `get_content_path`
not called for a seed-pure torrent, a non-tagged torrent NOT skipped by this check,
and the ordering golden (`test_seed_pure_and_below_ratio_counted_once`: a torrent
both below-ratio and seed-pure is counted exactly once, ratio firing first).

---

## ACC-06 — Sort-side guard OFF (default) → no torrent-client query

**Command:**

```bash
pytest tests/sorter/test_sort_seed_pure_guard.py -k "guard_off" --tb=short -q
```

**Expected:** `1 passed, 5 deselected`, `0 failed` —
`test_run_sort_guard_off_no_client_query`: with `config.sort.verify_seed_pure`
unset (default `False`), `run_sort` issues **zero** `get_completed` calls and
`Sorter.process` receives an empty `skip_names` — zero added cost on the baseline
pipeline.

---

## ACC-07 — Sort-side guard ON → REAL exclusion (load-bearing)

**Command:**

```bash
pytest 'tests/sorter/test_sort_seed_pure_guard.py::TestSorterProcessSkipNames::test_sort_process_excludes_skip_names' --tb=short -q
```

**Expected:** `1 passed`, `0 failed` — proves the exclusion is **genuine, not
vacuous**: an item whose name is in `Sorter.process`'s `skip_names` yields a
`skipped` `SortResult` (`message="seed_pure"`) and `sort_item` is **NOT** called
for it (the item is not sorted into the library). This is the load-bearing
guarantee that distinguishes a real exclusion from a count-only guard.

---

## ACC-08 — Clean-side flag reserved / not-enforced (intentional non-implementation)

**Command:**

```bash
python -c "from personalscraper.conf.models.scraper import ProcessCleanConfig; assert ProcessCleanConfig().verify_seed_pure is False; print('ACC08_RESERVED_OK')"
rg 'SEED_PURE|seed_pure' --type py personalscraper/process/
```

**Expected:** First command prints `ACC08_RESERVED_OK` (the flag exists, defaults
`False`). Second command produces **no output** (exit code 1) — there is **no**
seed-pure code anywhere in `personalscraper/process/`, documenting the intentional
non-implementation of the clean-side guard (post-sort name-matching against renamed
items is unreliable; DESIGN §4.2 / §8-B).

---

## ACC-09 — Layering guard: `core/tags.py` imports nothing project-internal; no raw `"seed-pure"` literal in ingest/sorter/conf

**Command:**

```bash
rg '^from |^import ' --type py personalscraper/core/tags.py
rg '"seed-pure"' --type py personalscraper/ingest/ personalscraper/sorter/ personalscraper/conf/
```

**Expected:** Both commands produce **no output** (exit code 1). First: `core/tags.py`
has **no** import statements at all (anchored `^from `/`^import ` match real
imports only, not the docstring prose) — it is the bottom layer. Second: no raw
`"seed-pure"` string literal in `ingest/`, `sorter/`, or `conf/` — every layer
imports the `SEED_PURE` constant from `core.tags`.

---

## ACC-10 — `make check` green; `python -c "import personalscraper"` smoke; design-gaps + feature-map scripts exit 0

**Command:**

```bash
make check
python -c "import personalscraper; print('OK')"
python3 scripts/audit_design_coverage.py --strict
python3 scripts/update_feature_map.py --check
```

**Expected:** All four commands exit 0. `make check` summary shows 0 failed /
0 errors. `python -c` prints `OK`. `audit_design_coverage.py --strict` prints
`audit: 0 finding(s), 0 error(s).` and exits 0. `update_feature_map.py --check`
exits 0 with no output. (This is the gate criterion — `make check` is run by the
phase-5 gate; the two design-gaps scripts are CI-only and were run locally here:
both exit 0.)
