# Phase 2 — Gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify `make check` is fully green (ruff + mypy + check_logging + all tests), smoke-test the import, and re-exercise every AC-1..AC-10 acceptance criterion.

**Architecture:** No new code. This phase is a structured verification sweep: run the full gate, resolve any residual lint/type issues, then explicitly tick off each acceptance criterion.

**Tech Stack:** `make check`, `pytest`, `command python`, `command rg -g '*.py'`.

---

## Task 1: `make check` — full gate

- [ ] **Step 1.1: Run `make check`**

```bash
make check
```

Expected: `make check` exits 0. The summary line must show `NNNN passed` with **0 failed / 0 errors**.

Common failure modes and fixes:

- **ruff I001 / E501**: run `command python -m ruff check --fix personalscraper/ tests/` then re-stage changed files.
- **mypy**: if `_youtube_search_fallback` has a type error on `item.title`/`item.year`, add `# type: ignore[attr-defined]` matching the existing `Any`-typed patterns in orchestrator.py.
- **check_logging**: if a `structlog.get_logger` crept in, replace with `from personalscraper.logger import get_logger` + `get_logger(__name__)`.
- **test ERROR (collection crash)**: fix imports before re-running.

- [ ] **Step 1.2: If `make check` failed — fix and re-run**

After applying any fix:

```bash
git add -p
git commit -m "chore(trailer-fallback): fix gate lint/type nits"
make check
```

Do not proceed to Task 2 until `make check` exits 0.

- [ ] **Step 1.3: Confirm test count baseline**

```bash
command python -m pytest tests/ --co -q 2>&1 | tail -5
```

Note the collected count. It should be >= the pre-feature baseline (no tests deleted). `make check` / coverage mode collects ~161 fewer than bare `pytest` — compare like-for-like.

---

## Task 2: AC-1..AC-10 re-exercise

Run each criterion explicitly to confirm it is green. These are the executable shell commands from DESIGN.md §Acceptance.

- [ ] **Step 2.1: AC-1 — TMDB URL → YTDLP_ERROR, fallback → SUCCESS**

```bash
command python -m pytest "tests/trailers/test_orchestrator.py::TestTrailersOrchestratorFallback::test_ytdlp_failure_triggers_youtube_fallback_and_succeeds" -v
```

Expected: `PASSED`.

- [ ] **Step 2.2: AC-2 — Both downloads fail → terminal state**

```bash
command python -m pytest "tests/trailers/test_orchestrator.py::TestTrailersOrchestratorFallback::test_ytdlp_failure_fallback_also_fails_keeps_terminal_state" -v
```

Expected: `PASSED`.

- [ ] **Step 2.3: AC-3 — Search returns None → single download, terminal**

```bash
command python -m pytest "tests/trailers/test_orchestrator.py::TestTrailersOrchestratorFallback::test_ytdlp_failure_fallback_returns_none_no_second_download" -v
```

Expected: `PASSED`.

- [ ] **Step 2.4: AC-4 — Search returns same URL → tried-set blocks 2nd download**

```bash
command python -m pytest "tests/trailers/test_orchestrator.py::TestTrailersOrchestratorFallback::test_ytdlp_failure_fallback_returns_same_url_no_double_download" -v
```

Expected: `PASSED`.

- [ ] **Step 2.5: AC-5 — `fallback_youtube_search=False` → search not called**

```bash
command python -m pytest "tests/trailers/test_orchestrator.py::TestTrailersOrchestratorFallback::test_fallback_disabled_by_config" -v
```

Expected: `PASSED`.

- [ ] **Step 2.6: AC-6 — `CircuitOpenError` from search → no crash, terminal**

```bash
command python -m pytest "tests/trailers/test_orchestrator.py::TestTrailersOrchestratorFallback::test_fallback_youtube_circuit_open_is_clean" -v
```

Expected: `PASSED`.

- [ ] **Step 2.7: AC-7 — HTTP_ERROR also triggers fallback**

```bash
command python -m pytest "tests/trailers/test_orchestrator.py::TestTrailersOrchestratorFallback::test_http_error_also_triggers_fallback" -v
```

Expected: `PASSED`.

- [ ] **Step 2.8: AC-8 — Back-compat: amended test does not make a live call**

```bash
command python -m pytest "tests/trailers/test_orchestrator.py::TestTrailersOrchestratorBasic::test_run_ytdlp_error_increments_counter" -v
```

Expected: `PASSED`.

- [ ] **Step 2.9: AC-9 — `TrailersConfig().fallback_youtube_search` defaults `True`**

```bash
command python -m pytest "tests/conf/test_models.py::TestTrailersConfig::test_trailers_config_fallback_youtube_search_default" -v
```

Expected: `PASSED`.

- [ ] **Step 2.10: AC-10 — `make check` green (captured from Task 1)**

Already confirmed in Task 1, Step 1.1. No further action required.

---

## Task 3: Residual-import grep

Confirm no dead import paths or stale references were left behind.

- [ ] **Step 3.1: Verify no bare structlog usage introduced**

```bash
command rg "structlog.get_logger" /Users/izno/dev/PersonnalScaper/personalscraper/trailers/orchestrator.py -g '*.py'
```

Expected: zero matches.

- [ ] **Step 3.2: Verify `fallback_youtube_search` is referenced in orchestrator**

```bash
command rg "fallback_youtube_search" /Users/izno/dev/PersonnalScaper/personalscraper/ -g '*.py'
```

Expected: at least two matches — one in `conf/models/trailers.py` (field definition) and one in `trailers/orchestrator.py` (runtime read).

- [ ] **Step 3.3: Verify `_youtube_search_fallback` is defined and called**

```bash
command rg "_youtube_search_fallback" /Users/izno/dev/PersonnalScaper/personalscraper/ -g '*.py'
```

Expected: two matches — the `def _youtube_search_fallback` definition and the `alt = self._youtube_search_fallback(item)` call site.

---

## Task 4: Phase gate commit

- [ ] **Step 4.1: Confirm working tree is clean**

```bash
git status --short
```

Expected: no modified files (all changes already committed in Phase 1).

- [ ] **Step 4.2: Phase gate commit**

If there are uncommitted changes (from gate fixes in Task 1), stage and commit them first, then:

```bash
git commit --allow-empty -m "chore(trailer-fallback): phase 2 gate — make check green, AC-1..AC-10 verified"
```

Use `--allow-empty` only if the working tree is already clean. If there were fixes, they were committed in Task 1 Step 1.2, so the tree is clean here.
