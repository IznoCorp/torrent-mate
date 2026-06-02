# Phase 6 — Granular CLI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--check <name>` (repeatable) and `--list-checks` to the `verify`, `enforce`, and `library validate` commands. The flags are additive — absent them, behavior is byte-identical to today (golden + existing suites stay green).

**Architecture:** Each command grows two optional Typer parameters. `--list-checks` prints the `CheckSpec` rows for the command's stage (via `catalog.list_checks()` filtered by stage) and exits 0. `--check NAME` (repeatable) restricts the run to the named checks for that stage; an unknown name prints the available set and exits non-zero. Filtering is applied by passing an allow-set down to the run functions, which intersect it with `registry.checks_for(stage, mt)`.

**Tech Stack:** Python 3.11, Typer, `catalog.list_checks`, `registry`, pytest + `CliRunner`/`typer.testing`

---

## Gate (previous phase)

- Both stages migrated: `registry.checks_for(DISPATCH, …)` and `checks_for(STAGING, …)` return the full plugin set.
- `pytest tests/verify/test_characterization_golden.py -q` → all pass.
- `pytest tests/verify tests/enforce -q` → all pass.

---

## Sub-phase 6.1 — `--list-checks` and `--check` plumbing in run functions

**Files:**

- Modify: `personalscraper/verify/run.py` (accept optional `only: frozenset[str] | None`)
- Modify: `personalscraper/verify/verifier.py` (thread `only` into the registry loop)
- Modify: `personalscraper/verify/library_checks.py` (`validate_library` / `validate_from_index` accept `only`)
- Modify: `personalscraper/enforce/run.py` + `coherence_checker.py` (accept `only`)

- [ ] **Step 1: Write failing tests** (`tests/verify/checks/test_cli_check_filter.py`) — a run with `only={"nfo_present"}` produces results only for `nfo_present`; `only` containing an unknown name raises a clear `ValueError`/`typer.BadParameter`.

- [ ] **Step 2: Add an `only` filter helper to the registry**

```python
# registry.py
def checks_for_filtered(self, stage, media_type, only: "frozenset[str] | None"):
    checks = self.checks_for(stage, media_type)
    if only is None:
        return checks
    unknown = only - {c.name for c in checks} - {c.name for c in self._all_for_stage(stage)}
    if unknown:
        raise KeyError(f"Unknown check(s) for stage {stage.value}: {sorted(unknown)}")
    return [c for c in checks if c.name in only]
```

Thread `only` from each run function into its registry loop (default `None` → no filtering → byte-identical).

- [ ] **Step 3: Run filter tests → pass; re-run golden (no `--check` path unchanged).**

- [ ] **Step 4: Commit** — `feat(check-plugins): thread optional check allow-set through verify/enforce/library runs`.

---

## Sub-phase 6.2 — Typer flags on the 3 commands

**Files:**

- Modify: `personalscraper/commands/pipeline.py` (`verify`, `enforce`)
- Modify: `personalscraper/commands/library/maintenance.py` (`library validate`)

- [ ] **Step 1: Add flags to `verify`** (same shape for `enforce` and `library validate`, with the stage fixed per command):

```python
check: list[str] = typer.Option(None, "--check", help="Run only the named check(s); repeatable"),
list_checks: bool = typer.Option(False, "--list-checks", help="List available checks and exit"),
```

```python
if list_checks:
    from personalscraper.verify.checks.catalog import list_checks as _list
    from personalscraper.verify.checks.base import CheckStage
    for spec in (s for s in _list() if s.stage == CheckStage.DISPATCH):
        fix = "fixable" if spec.fixable else "-"
        idx = "indexable" if spec.indexable else "-"
        console.print(f"  {spec.name:<34} [{spec.group}] {spec.default_severity.value:<7} {fix:<8} {idx:<9} {spec.description}")
    raise typer.Exit(0)

only = frozenset(check) if check else None
# pass only=… into run_verify(...)
```

Unknown-name handling: the `KeyError` from `checks_for_filtered` is converted to `typer.BadParameter` (prints available names, exits ≠ 0).

- [ ] **Step 2: Write CLI tests** (`tests/commands/test_verify_cli_checks.py`, `test_enforce_cli_checks.py`, `test_library_validate_cli_checks.py`) using `typer.testing.CliRunner`:
  - `--list-checks` exits 0 and prints ≥ 1 spec for the command's stage.
  - `--check nfo_present` runs without error.
  - `--check bogus_name` exits ≠ 0 with the available-names hint.

- [ ] **Step 3: ACC-04 — manual verification**

```bash
personalscraper verify --list-checks       # ACC-04a: prints DISPATCH specs, exit 0
personalscraper verify --check nfo_present  # ACC-04b: runs only nfo_present
personalscraper enforce --list-checks       # prints STAGING specs
```

- [ ] **Step 4: Commit** — `feat(check-plugins): add --check/--list-checks to verify, enforce, library validate`.

---

## Phase Gate

```bash
make lint && make test && make check
pytest tests/verify/test_characterization_golden.py -q   # ACC-01 (no-flag path unchanged)
pytest tests/verify tests/enforce tests/commands -q       # ACC-02 + CLI tests
personalscraper verify --list-checks                      # ACC-04a
python3 scripts/check-module-size.py                      # ACC-07
python -c "import personalscraper"
```

Expected: all green. The check catalog is now reachable from the CLI; the Web-UI enumeration API (`catalog.list_checks`) is exercised end-to-end.
