# Phase 19 — PR-review fixes (cycle 3): seed `--project-id` half-seed guard

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Source: the cycle-3 re-review (4-agent focused workflow, 2026-06-09). Completeness vs cycle-2 = CLEAN
> (all 15 phase-18 items closed); non-keystone correctness = CLEAN; final PoC-conformance = CLEAN.
> The new-defect hunt surfaced ONE retained MEDIUM (+ a coupled MINOR that blocks its fix).
> PoC root: `/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/kanbanmate/`. NEW: `src/kanbanmate/`.
> Merge is HUMAN-ONLY (merge_mode=manual) — cycle ends green; the human squash-merges PR #1.
> **Clear `.mypy_cache` before every gate** (`rm -rf .mypy_cache && make check`).

**The finding (MEDIUM, deviation_UNJUSTIFIED — regresses a PoC safety).** `kanban seed`'s Backlog-landing
pre-check (#3, phase 18.7) only fires when the Status options can be NAMED. `_known_status_options`
(cli/seed.py:308-312) probes `getattr(seeder, "status_options", None)` then falls back to the registry
`entry.option_map`. But `GithubClient` has NO `status_options` method, and on the explicit `--project-id`
override path `resolved_entry` stays `None` (the registry lookup is skipped when `project_id` is passed). So
`_known_status_options` returns `None` → the pre-check at seed.py:377-382 is SKIPPED → `seed()` creates issue
1, then `move_card(item_id, "Backlog")` raises mid-loop if the board has no `Backlog` option → an orphaned
**half-seed** (exactly what the guard exists to prevent). The PoC (`cli/runners.py:244-262`) had NO
`--project-id` override and ALWAYS evaluated `entry.option_map.get(SEED_LANDING_COLUMN)` from the registry —
every PoC seed was guarded. NEW's additive `--project-id` path therefore introduced an UNguarded path the
source-of-truth never had. **Coupled MINOR:** `client.py` is at exactly 1000 LOC (the hard ceiling), so the
fix (adding a `status_options` method) cannot land without first restoring headroom.

---

## 19.1 — restore client.py headroom: extract `UrllibTransport` → `_transport.py`

**Why (the coupled MINOR).** `src/kanbanmate/adapters/github/client.py` is at exactly 1000 physical LOC (the
Makefile size guard FAILS at `> 1000`). Phase 18 pushed it to the boundary (988→1000). Any new method fails
the gate. `UrllibTransport` (+ `Timeouts` + `_is_transient`) is a self-contained HTTP-transport concern
(lines ~66-342), DISTINCT from the GitHub-domain `GithubClient`, defined BEFORE it (no back-dependency) —
the ideal cohesive extraction. Mirrors the `app/reaper.py`/`app/depgate.py`/`app/drain.py` precedent.

**Files**: `src/kanbanmate/adapters/github/_transport.py` (NEW), `src/kanbanmate/adapters/github/client.py`
(import + re-export), `tests/adapters/github/test_pagination.py` (import unaffected if re-exported).

- [ ] Create `src/kanbanmate/adapters/github/_transport.py`: move `_is_transient`, `Timeouts`,
      `UrllibTransport` (+ any module-level constants they use — `_MAX_ATTEMPTS`, user-agent, base URLs, etc.)
      verbatim. Carry their imports (`http.client`, `json`, `time`, `Callable`, `urlparse`, `_parsers`'
      `GitHubHTTPError`/`raise_for_errors`, `_rest`). Full module docstring. Behaviour-preserving — byte-identical
      method bodies.
- [ ] `client.py`: replace the moved definitions with `from kanbanmate.adapters.github._transport import (
    Timeouts, UrllibTransport)` (and `_is_transient` if still referenced) at the import block, and
      RE-EXPORT `Timeouts` + `UrllibTransport` (add to `__all__` if present, else the import alone re-exports
      for `from ...client import Timeouts, UrllibTransport`) so the existing
      `tests/adapters/github/test_pagination.py:24` import (`from ...client import GithubClient, Timeouts,
    UrllibTransport`) keeps working WITHOUT editing the test. Verify `test_pagination.py` still imports/constructs
      them (lines 24, 970, 994) — if the re-export covers it, no test edit; otherwise update the test import.
- [ ] Layering: `_transport.py` is in `adapters/github` (same layer) — imports only stdlib + `_parsers`/`_rest`
      (same package). `tests/test_layering.py` must stay green.
- [ ] Verify: `rm -rf .mypy_cache && make check` green; client.py now well under 1000 (target ~760);
      `_transport.py` under 800.

```bash
git commit -m "refactor(genesis): extract UrllibTransport to _transport.py (restore client.py headroom under the 1000-LOC ceiling)"
```

---

## 19.2 — guard the `--project-id` seed path: add `GithubClient.status_options`

**The fix.** Add a `status_options(project_id: str) -> dict[str, str]` method to `GithubClient` so the seed
guard's `getattr(seeder, "status_options", None)` probe SUCCEEDS on the real client — closing the unguarded
`--project-id` half-seed path. `seed.py` already probes it (no seed.py change needed); the method makes the
probe resolve.

**Files**: `src/kanbanmate/adapters/github/client.py` (add `status_options`),
`tests/adapters/github/test_client.py` (unit test), `tests/cli/test_seed.py` (the `--project-id` guard test).

- [ ] Add `GithubClient.status_options(self, project_id: str) -> dict[str, str]`: returns the board's
      `{option_name: option_id}` Status-option map, reusing the EXISTING plumbing
      `self._graphql(_queries.status_option_map(project_id))` + `_parsers.parse_status_option_map(data)` (the
      exact 2 lines `ensure_columns` already runs at client.py:810-811). Full Google-style docstring (it is the
      seed-guard's option probe + the `BoardReader`-adjacent Status introspection). The request inherits the
      client's mandatory connect+read timeouts via `_graphql`. OPTIONAL: dedup `ensure_columns` /
      `status_field_node_id` to call `status_options` (only if byte-for-byte behaviour-preserving; else leave them).
- [ ] Tests: - `test_client.py`: `GithubClient.status_options(pid)` returns the parsed option map (stub `_graphql` to
      return a status-option-map payload; assert the `{name: id}` result). - `test_seed.py`: a seed on the EXPLICIT `--project-id` path (no registry entry) with a seeder whose
      `status_options` returns a map WITHOUT `Backlog` → `seed()` raises clean BEFORE any `create_issue`
      (assert no issue created); with `Backlog` present → proceeds. This proves the previously-unguarded
      path is now guarded (the regression-vs-PoC is closed).
- [ ] Verify: `rm -rf .mypy_cache && make check` green; client.py still ≤ 1000 (it dropped ~240 in 19.1, so
      +~12 for the method is safe). Residual: `rg --type py "def status_options" src` → the new method;
      `_known_status_options`'s probe now resolves on the real client.

```bash
git commit -m "fix(genesis): add GithubClient.status_options so the seed Backlog guard covers the --project-id path (no more half-seed)"
```

---

### Phase 19 Gate

1. `rm -rf .mypy_cache && make lint` — zero (ruff + mypy src tests).
2. `make test` — all pass. `make check` — clean (module-size: client.py back under the ceiling with headroom;
   `_transport.py` < 800).
3. Residual / parity greps:
   - `rg --type py "def status_options" src` → `GithubClient.status_options`.
   - `rg --type py "class UrllibTransport" src` → now in `_transport.py` (not client.py).
   - `rg --type py "UrllibTransport" tests` → still resolves (re-export or updated import).
4. Parity check — exercised in tests: a `--project-id` seed against a board with no `Backlog` option fails
   clean BEFORE creating any issue (the PoC's always-on landing guard, now restored on the override path).
5. `python -c "import kanbanmate"` — exits 0.

```bash
git commit --allow-empty -m "chore(genesis): phase 19 gate — PR-review fixes cycle 3 (seed --project-id half-seed guard + client.py headroom)"
```
