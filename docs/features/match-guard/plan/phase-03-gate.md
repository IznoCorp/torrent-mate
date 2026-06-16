# match-guard — Phase 3: Phase Gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify `make check` is fully green (ruff + mypy + full suite, 0 failed/errors), smoke-import the package, and manually re-exercise all 7 acceptance criteria (AC-1..AC-7) from the DESIGN to confirm the feature is complete before the gate commit.

**Architecture:** No code changes — this phase is verification only. All tasks are read-only checks and a single gate commit.

**Tech Stack:** make, pytest, ruff, mypy, python -c.

---

## File map

- No files created or modified. Gate commit only.

---

## Task 1: Smoke import

- [ ] **Step 1.1: Verify the package imports cleanly**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -c "import personalscraper; print('OK')"
```

Expected output: `OK` with no tracebacks or import errors.

- [ ] **Step 1.2: Verify the new symbols are importable**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -c "
from personalscraper.scraper.confidence import _length_ratio_guard
from personalscraper.scraper.classifier import is_degenerate_title
from personalscraper.scraper.tv_service import _recover_title_from_episodes
print('all symbols OK')
"
```

Expected output: `all symbols OK`.

---

## Task 2: Residual import grep (no deleted modules, but confirm no stray old paths)

- [ ] **Step 2.1: Confirm no leftover references to any accidental dead symbol**

```bash
cd /Users/izno/dev/PersonnalScaper && command rg "_length_ratio_guard|is_degenerate_title|_recover_title_from_episodes" --type py personalscraper/ tests/ 2>&1 | head -30
```

Expected: results only in the files we wrote — `personalscraper/scraper/confidence.py`, `personalscraper/scraper/classifier.py`, `personalscraper/scraper/tv_service.py`, `tests/scraper/test_confidence_match_guard.py`, `tests/scraper/test_classifier_match_guard.py`. No unexpected files.

---

## Task 3: Re-exercise AC-1..AC-6 individually

- [ ] **Step 3.1: AC-1 — Orville S03 suppression**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/test_confidence_match_guard.py::TestAC1OrvelleSuppression -v 2>&1 | tail -10
```

Expected: 2 PASSes (`test_season_token_rejects_glina_title`, `test_season_token_normalized_rejects_glina`).

- [ ] **Step 3.2: AC-2 — Orville recovery**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/test_confidence_match_guard.py::TestAC2OrvilleRecovery -v 2>&1 | tail -10
```

Expected: 3 PASSes.

- [ ] **Step 3.3: AC-3 — Among Us suppression**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/test_confidence_match_guard.py::TestAC3AmongUsSuppression -v 2>&1 | tail -10
```

Expected: 1 PASS.

- [ ] **Step 3.4: AC-4 — Directional preservation (The Hack / Top Chef France)**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/test_confidence_match_guard.py::TestAC4DirectionalPreservation -v 2>&1 | tail -10
```

Expected: 2 PASSes.

- [ ] **Step 3.5: AC-5 — Exact short title unaffected**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/test_confidence_match_guard.py::TestAC5ExactShortTitlesUnaffected -v 2>&1 | tail -10
```

Expected: 1 PASS.

- [ ] **Step 3.6: AC-6 — Regex scoping (is_degenerate_title)**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/test_classifier_match_guard.py -v 2>&1 | tail -20
```

Expected: 16 PASSes (6 True cases + 10 False cases).

---

## Task 4: Full `make check`

- [ ] **Step 4.1: Run make check**

```bash
cd /Users/izno/dev/PersonnalScaper && make check 2>&1 | tail -40
```

Expected: exits 0. The summary line must show `NNNN passed` with **0 failed** and **0 errors**. If the summary shows `ERROR` (not just `FAILED`), a collection crash occurred — fix imports before proceeding.

- [ ] **Step 4.2: If make check fails on lint (ruff version skew), fix with pinned ruff**

Only if step 4.1 shows ruff errors that are not present locally:

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m ruff check --fix personalscraper/scraper/confidence.py personalscraper/scraper/classifier.py personalscraper/scraper/tv_service.py tests/scraper/test_confidence_match_guard.py tests/scraper/test_classifier_match_guard.py && make check 2>&1 | tail -20
```

- [ ] **Step 4.3: AC-7 is satisfied when make check exits 0 with 0 failures**

No further action needed — AC-7 is a direct consequence of step 4.1 passing.

---

## Task 5: Phase gate commit

- [ ] **Step 5.1: Verify git status is clean except for the gate commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git status --short
```

Expected: empty output (all changes already committed in phases 1 and 2). If there are uncommitted files (e.g. ruff auto-fix from step 4.2), stage and commit them before the gate commit:

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/scraper/confidence.py personalscraper/scraper/classifier.py personalscraper/scraper/tv_service.py tests/scraper/test_confidence_match_guard.py tests/scraper/test_classifier_match_guard.py && git commit -m "style(match-guard): ruff fixes from CI version pin"
```

- [ ] **Step 5.2: Gate commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git commit --allow-empty -m "$(cat <<'EOF'
chore(match-guard): phase 3 gate — make check green, AC-1..AC-7 verified

All acceptance criteria exercised:
- AC-1: 'S03' rejected for 'Glina. Nowy rozdział' (guard fires)
- AC-2: ' S03' folder + Orville episode files → recovers 'The Orville'
- AC-3: 'Among' rejected for 'Love Amongst War' (ratio 0.312 < 0.67)
- AC-4: 'The Hack sur ecoute'→'The Hack' and 'Top Chef France'→'Top Chef' preserved
- AC-5: 'FROM'→'FROM' exact match unaffected
- AC-6: is_degenerate_title regex scoping verified (16 cases)
- AC-7: make check green (ruff + mypy + full suite, 0 failed/errors)
EOF
)"
```

---

## Checklist summary (DESIGN §Phase Gate)

Before marking this phase done, confirm all of the following:

- [ ] `make lint` — ruff + mypy: zero errors
- [ ] `make test` — full suite: `NNNN passed` with 0 failed/errors
- [ ] `make check` — lint + test + module-size + typed-api guardrails: exits 0
- [ ] Residual import grep — `_length_ratio_guard`, `is_degenerate_title`, `_recover_title_from_episodes` only in expected files
- [ ] `python -c "import personalscraper"` — smoke test passes
- [ ] AC-1..AC-7 each individually confirmed green (steps 3.1–3.6 + 4.3)
