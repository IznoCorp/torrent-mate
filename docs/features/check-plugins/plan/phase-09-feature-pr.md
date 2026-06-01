# Phase 9 — Feature PR + Review (auto-invoked)

> **For agentic workers:** This phase is orchestrated by the implementation lifecycle skills, not implemented by hand. It is auto-invoked by `/implement:phase` once all of Phases 0–8 are `[x]`.

**Goal:** Run the full local quality gate, push `feat/check-plugins`, open the PR, poll CI to green, then run the PR review loop and merge (squash, **manual** per the merge strategy chosen at feature start).

**Tech Stack:** `implement:feature-pr`, `implement:pr-review`, `pr-review-toolkit`, GitHub via `github-curl`

---

## Gate (previous phase)

- Phases 0–8 all `[x]` in `IMPLEMENTATION.md`.
- `make check` green at HEAD; characterization golden green (against the Phase-7-updated baseline); all suites pass.

---

## Sub-phase 9.1 — Local gate + push + PR (`/implement:feature-pr`)

- [ ] Full local quality gate (CLAUDE.md Phase Gate checklist):
  - `make lint` → 0 · `make test` → all pass, 0 collection ERROR · `make check` → rc=0, coverage ≥ 90 %.
  - Residual-import greps: `rg -t py 'MediaFixer' personalscraper/ tests/` → rc=1 ; `rg -t py 'from personalscraper\.verify\.checker import.*\b(Severity|CheckResult)\b' personalscraper/ tests/` → rc=1.
  - `python3 scripts/check-module-size.py` → rc=0 ; `python -c "import personalscraper"` → 0.
  - CI-only guardrails run locally: `audit_design_coverage --strict`, `update_feature_map --check` (paired Design:/Contract: sections; feature_map regenerated).
- [ ] Re-exercise **every** ACCEPTANCE criterion (INDEX ACC table) — all pass.
- [ ] Push `feat/check-plugins`; open PR with generated title/body (summary, phase map, ACC results, the deliberate Phase-7 behavior change, the Phase-8 scope note for `indexer/external_ids.py`). Note the branch also carries the unrelated `ddef4042` roadmap-curation commit — flag it in the PR body.
- [ ] Poll CI to green (watch for billing-blocked false-failures; `concurrency:cancel-in-progress` — avoid trivial follow-up pushes).

## Sub-phase 9.2 — Review loop + merge (`/implement:pr-review`)

- [ ] Run `pr-review-toolkit` (code / silent-failure / tests / comments) on the PR.
- [ ] Filter every finding against DESIGN + plan (no design contradictions), severity-classify, re-verify in code (evidence-before-severity), fix with regression tests. Max 5 cycles; record each cycle in `IMPLEMENTATION.md`.
- [ ] **Manual squash merge** (operator merges when review is clean — merge strategy = manual). Do NOT auto-merge.

---

## Phase Gate (feature complete)

```bash
# After merge:
git checkout main && git pull
python -c "import personalscraper; print(personalscraper.__version__)"   # 0.20.0
personalscraper verify --list-checks                                      # framework live on main
```

Expected: PR merged (squash), `main` at 0.20.0, the unified check framework shipped. Feature `check-plugins` complete.
