# Phase 8 — Latent Bug Fixes (RatingSource Literal + VerifyItemDone eager catalog)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two **independently-verified latent bugs** the operator surfaced. Both are dormant today but break the moment a consumer is wired. Each = a 1–2 line production fix + a regression test (project rule: 1 bug = 1 test). These are **adjacent cleanup, not part of the check-plugins refactor** — folded in here at operator request; documented as such so review understands why `indexer/external_ids.py` moves in this PR.

> **Scope note (operator-approved):** Bug 2 is verify-adjacent (the verify-step event). Bug 1 lives in `indexer/external_ids.py` and is unrelated to the check framework — its presence in this PR is a deliberate scope decision (`norms:diff-scope` will see it; this phase doc is the justification).

**Tech Stack:** Python 3.11, pydantic `Literal`, `Event.__init_subclass__` registry, `event_from_envelope`, pytest + subprocess

---

## Gate (previous phase)

- The check-plugins refactor is complete through Phase 7; `make check` green at HEAD.
- `pytest tests/verify tests/enforce tests/commands -q` → all pass.

> These bug fixes are orthogonal to the refactor — they could run anytime — but are placed after the refactor so the no-behavior-change golden (Phases 0–6) and the deliberate fix-policy change (Phase 7) stay cleanly separated from unrelated bug fixes.

---

## Sub-phase 8.1 — Bug 1: `RatingSource` Literal aligned to stored value (`themoviedb` → `tmdb`)

**Verified evidence (independent confirmation):**

- `personalscraper/indexer/external_ids.py:34` — `RatingSource = Literal["imdb", "rotten_tomatoes", "metacritic", "themoviedb", "trakt"]` includes `themoviedb`, omits `tmdb`.
- `personalscraper/nfo_utils.py:35-43` `_NFO_RATING_SOURCE_REVERSE` maps `"themoviedb": "tmdb"`, `"tmdb": "tmdb"`; `nfo_utils.py:195` `source = _NFO_RATING_SOURCE_REVERSE.get(name, name)` → `extract_nfo_metadata` writes `ratings_json` with `source="tmdb"`, **never** `themoviedb`.
- `personalscraper/api/metadata/_base.py:156` documents `Notations.source` as `"imdb", "rotten_tomatoes", "trakt", "tmdb", "metacritic"` — the Literal claims to "mirror" it but diverges. The fix aligns with **both** the stored shape and `Notations.source`.

**⚠️ Correction to the original report — NOT dormant:** the models ARE exercised. `tests/indexer/test_external_ids_models.py:70` does `RatingEntry(source="themoviedb", …)` and `:81` reads `by_source["themoviedb"]` — these pass **only because** the Literal currently contains `themoviedb`. The fix therefore must **update the existing test**, not merely add one.

**Files:**

- Modify: `personalscraper/indexer/external_ids.py:34`
- Modify: `tests/indexer/test_external_ids_models.py` (lines 70 + 81: `themoviedb` → `tmdb`)
- Create: regression test in the same file

- [ ] **Step 1: Write the regression test FIRST (fails on current Literal)**

```python
# tests/indexer/test_external_ids_models.py — add:
def test_extract_nfo_metadata_rating_source_validates_against_model(tmp_path):
    """A <rating name="themoviedb"> round-trips to source='tmdb' (storage shape)
    and that value MUST validate against the Ratings model — pins the Literal
    to the real ratings_json contract (regression for the themoviedb/tmdb skew)."""
    import xml.etree.ElementTree as ET
    from personalscraper.nfo_utils import extract_nfo_metadata
    from personalscraper.indexer.external_ids import Ratings

    root = ET.Element("movie")
    ET.SubElement(root, "title").text = "M"; ET.SubElement(root, "year").text = "2020"
    r = ET.SubElement(root, "rating"); r.set("name", "themoviedb")
    ET.SubElement(r, "value").text = "8.2"; ET.SubElement(r, "votes").text = "4321"
    nfo = tmp_path / "M.nfo"; ET.ElementTree(root).write(nfo, encoding="unicode")

    meta = extract_nfo_metadata(nfo)
    assert meta["ratings"] == [{"source": "tmdb", "score": "8.2", "votes": 4321}]
    # The crux: the stored source ('tmdb') must validate against the model.
    Ratings.model_validate({"entries": meta["ratings"]})  # raises pre-fix (tmdb ∉ Literal)
```

- [ ] **Step 2: Run — expect FAIL** (`tmdb` not in the Literal → `ValidationError`).

```bash
pytest tests/indexer/test_external_ids_models.py::test_extract_nfo_metadata_rating_source_validates_against_model -q
```

- [ ] **Step 3: Fix the Literal**

```python
# external_ids.py:34
RatingSource = Literal["imdb", "tmdb", "rotten_tomatoes", "metacritic", "trakt"]
```

- [ ] **Step 4: Update the existing test that encoded the wrong contract**

```python
# tests/indexer/test_external_ids_models.py
# line ~70:  RatingEntry(source="themoviedb", score="8.2", votes=4_321)  →  source="tmdb"
# line ~81:  assert by_source["themoviedb"].votes == 4_321               →  by_source["tmdb"]
```

- [ ] **Step 5: Run the full model test file — expect pass**

```bash
pytest tests/indexer/test_external_ids_models.py -q   # all pass, incl. the new regression
```

- [ ] **Step 6: Commit** — `fix(check-plugins): align RatingSource literal to stored value (themoviedb→tmdb)`.

---

## Sub-phase 8.2 — Bug 2: `VerifyItemDone` registered in the eager event catalog

**Verified evidence (independent confirmation):**

- `personalscraper/events/__init__.py:1-13` docstring promises eager import of **every** producer so `event_from_envelope` resolves any production event class. It imports 6 producer modules but **not** `personalscraper.verify.events`; `VerifyItemDone` is **absent** from `__all__`.
- `personalscraper/verify/events.py` — `VerifyItemDone(Event)` auto-registers via `Event.__init_subclass__` **only when imported** (i.e. via `verify.run`).
- `personalscraper/core/event_bus.py:125` — `raise KeyError(f"Unknown event type: {type_name!r}")` (fail-loud).
- `tests/event_bus/test_pipeline_events.py:126` — `import personalscraper.verify.events  # noqa: F401 — eager-import side effect` — the workaround proves the gap is real and already bites.

**Files:**

- Modify: `personalscraper/events/__init__.py` (eager import + `__all__`)
- Create: regression test (fresh-interpreter envelope resolution)
- Modify: `tests/event_bus/test_pipeline_events.py` (remove the now-unneeded workaround at line 126)

- [ ] **Step 1: Write the regression test FIRST (isolated interpreter)**

```python
# tests/event_bus/test_verify_item_done_catalog.py
"""VerifyItemDone must resolve from the eager catalog WITHOUT importing verify.run.
Runs in a subprocess so the test session's prior imports cannot mask the gap."""
import subprocess
import sys


def test_verify_item_done_resolves_from_catalog_only():
    code = (
        "import personalscraper.events\n"  # catalog ONLY — no verify.run
        "from personalscraper.core.event_bus import event_from_envelope\n"
        "e = event_from_envelope({'_type': 'VerifyItemDone', 'item': 'X (2020)',"
        " 'status': 'valid', 'errors': [], 'checks_passed': 5, 'checks_total': 5})\n"
        "assert type(e).__name__ == 'VerifyItemDone'\n"
        "print('OK')\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, f"resolution failed:\n{proc.stderr}"
    assert "OK" in proc.stdout
```

- [ ] **Step 2: Run — expect FAIL** (KeyError: Unknown event type 'VerifyItemDone').

```bash
pytest tests/event_bus/test_verify_item_done_catalog.py -q
```

- [ ] **Step 3: Fix `events/__init__.py`**

```python
# add to the eager-import block:
from personalscraper.verify import events as _verify_events  # noqa: F401
from personalscraper.verify.events import VerifyItemDone
# add to __all__ (keep alphabetical):
"VerifyItemDone",
```

Guard against an import cycle: `verify.events` only imports `core.event_bus.Event` (lightweight) — confirm `python -c "import personalscraper.events"` still succeeds.

- [ ] **Step 4: Remove the workaround in `test_pipeline_events.py`**

```python
# delete line 126:  import personalscraper.verify.events  # noqa: F401 — eager-import side effect
```

(The catalog now guarantees registration; the workaround is dead.)

- [ ] **Step 5: Run — expect pass**

```bash
pytest tests/event_bus/test_verify_item_done_catalog.py tests/event_bus/test_pipeline_events.py -q
python -c "import personalscraper.events"   # no import cycle
```

- [ ] **Step 6: Commit** — `fix(check-plugins): eager-register VerifyItemDone in the event catalog`.

---

## Phase Gate

```bash
make lint && make test && make check
pytest tests/indexer/test_external_ids_models.py -q                 # Bug 1 (incl. regression)
pytest tests/event_bus/test_verify_item_done_catalog.py -q          # Bug 2 (isolated resolution)
pytest tests/verify tests/enforce tests/commands -q                 # ACC-02 unaffected
python -c "import personalscraper"
```

Expected: all green. Two latent bombs defused; each pinned by a test that fails when its fix is reverted.
