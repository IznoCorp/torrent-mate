# Phase 10 — Interpreter bump to Python 3.12

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Design refs: DESIGN §2 (engine = `kanbanmate` package + `kanban` console script), §7 (CI),
> §12 (repo layout). Operator decision (baked into this plan): interpreter = **pyenv 3.12.4**
> (the interpreter the host already has), editable install, global.

**Goal**: bump the project's minimum interpreter from 3.11 to **3.12**, re-install editable under
**pyenv 3.12.4**, update the CI workflows that pin 3.11, and confirm `make check` is green under
3.12. This is the interpreter the production host (IznoServer) runs and the version the new daemon
will be launched under in phase 11 — so the gate must be proven on it BEFORE the cutover.

---

## Gate

Phase 9 complete; `make check` green under the current (3.11) interpreter; PR #1 open. Branch
`feat/genesis`. Confirm `pyenv versions` lists `3.12.4` on the host (the operator's existing
interpreter); if absent, `pyenv install 3.12.4` first (host op, outside the repo).

---

> **The gap.** NEW pins 3.11 in three places: `pyproject.toml` (`requires-python = ">=3.11"`,
> `[tool.ruff] target-version = "py311"`, `[tool.mypy] python_version = "3.11"`), `.github/
workflows/pr.yml` (`Set up Python 3.11` / `python-version: "3.11"`), and `.github/workflows/
nightly.yml` (same). Nothing in `src/` is 3.11-specific (no `from __future__` removal needed —
> the codebase already uses `from __future__ import annotations` and modern typing), so the bump is
> packaging + CI + a clean re-install + a green-gate proof.

---

### 10.1 — Bump `pyproject.toml` to 3.12

**Files**: `pyproject.toml`.

- [ ] `[project] requires-python = ">=3.12"` (was `>=3.11`).
- [ ] `[tool.ruff] target-version = "py312"` (was `py311`) — lets ruff lint against 3.12 syntax/idioms.
- [ ] `[tool.mypy] python_version = "3.12"` (was `"3.11"`) — type-checks against the 3.12 stdlib.
- [ ] Leave `dependencies` and `[project.scripts]` unchanged (typer / PyYAML / attrs all support
      3.12; the console scripts are version-agnostic).
- [ ] Verify: `python -c "import tomllib, pathlib; tomllib.loads(pathlib.Path('pyproject.toml')
    .read_text())"` parses (no TOML typo).

```bash
git commit -m "build(genesis): require Python 3.12 (pyproject requires-python + ruff/mypy targets)"
```

---

### 10.2 — Re-install editable under pyenv 3.12.4 (the pth/editable step)

> **Operational, not a code change** — this sub-phase is the local re-install runbook that makes
> `make check` run under 3.12. It produces no commit of its own (no tracked file changes); its
> result is the green gate that 10.4 commits. Keep the exact commands here so the cutover (phase 11)
> can reuse them.

**Commands** (run from the repo root `/Users/izno/dev/KanbanMate`):

- [ ] Select the interpreter for this project. **Audit note:** `pyenv local` WRITES `.python-version`
      at the repo root and the global `~/.gitignore` does NOT cover it — so EITHER add
      `.python-version` to the repo `.gitignore` (preferred; keeps the tree clean for the phase-11 /
      archive "repo clean" preconditions) OR use `pyenv shell 3.12.4` (one-shot, writes nothing). The
      phase gate asserts `python --version → 3.12.4` LITERALLY, so the pyenv-3.12.4 shim (not a bare
      Homebrew `python3.12`, which is 3.12.9 on this host) must be the active interpreter:
      `bash
    pyenv local 3.12.4            # or: pyenv shell 3.12.4 for a one-shot
    python --version              # → Python 3.12.4
    `
- [ ] Editable re-install with dev extras under the 3.12 interpreter. The editable install rewrites
      the `kanbanmate` `.pth`/`__editable__` finder into the 3.12 `site-packages`, so `import
    kanbanmate` resolves to `src/kanbanmate` under 3.12 and the `kanban*` console scripts are
      re-shimmed into the 3.12 `bin/`:
      `bash
    pip install -e ".[dev]"
    python -c "import kanbanmate, sys; print(kanbanmate.__file__, sys.version)"
    which kanban && kanban --help | head -1
    `
- [ ] If a stale 3.11 editable shim shadows the new one on PATH, confirm `which kanban` points at
      the pyenv-3.12 `shims/`/`bin` (not a leftover 3.11 path). `pyenv rehash` after the install
      refreshes the shims.
- [ ] No commit — proceed to 10.3/10.4 (the proof + CI bump are the committed artifacts).

---

### 10.3 — Bump the CI workflows off 3.11

**Files**: `.github/workflows/pr.yml`, `.github/workflows/nightly.yml`.

- [ ] `pr.yml`: rename the step `Set up Python 3.11` → `Set up Python 3.12` and set
      `python-version: "3.12"`. The rest of the job (`pip install -e ".[dev]"`, `make check`, import
      smoke, Node + `claude plugin validate`) is unchanged.
- [ ] `nightly.yml`: same — `Set up Python 3.12` / `python-version: "3.12"`. Integration job body
      unchanged.
- [ ] (Optional, only if a matrix is desired) — out of scope for v1: a single 3.12 line matches the
      single production interpreter. Document that a `3.12`-only CI matches `requires-python >=3.12`
      and the host; a wider matrix is a ROADMAP nicety, not needed for the cutover.
- [ ] Verify: `rg -n "3\.11" .github/workflows/` → zero matches.

```bash
git add -f .github/workflows/pr.yml .github/workflows/nightly.yml
git commit -m "ci(genesis): run CI on Python 3.12 (match requires-python and the production host)"
```

---

### 10.4 — Prove `make check` green under 3.12

**Files**: none (proof sub-phase; the gate commit is empty-allowed).

- [ ] Under the 3.12.4 interpreter (10.2), run the full gate and capture the summary:
      `bash
    python --version           # → 3.12.4
    make lint                  # ruff check + ruff format --check + mypy(strict) src tests → 0 errors
    make test                  # pytest -m "not integration" → all pass, 0 failed/errors
    make check                 # lint + test + size guard → clean
    python -c "import kanbanmate"   # exit 0
    kanban --help              # lists all commands
    `
- [ ] Mypy under `python_version = 3.12` may surface NEW deprecation/strictness diffs vs 3.11
      (e.g. stdlib stubs that changed). Fix any that appear (types only; no behavioural change) and
      fold them into THIS sub-phase. If zero diffs, note "mypy clean under 3.12, no diffs from 3.11".
- [ ] Residual grep across the repo: `rg -n "3\.11|py311" pyproject.toml .github/ Makefile` → zero
      matches (the only intentional remaining "3.1x" mention is in docs prose, if any).

```bash
git commit --allow-empty -m "chore(genesis): phase 10 gate — interpreter bump to Python 3.12 (make check green)"
```

---

### Phase 10 Gate

1. `python --version` → `3.12.4` (the pyenv interpreter the gate ran under).
2. `make lint` — zero errors under 3.12 (`mypy python_version = 3.12`).
3. `make test` — all pass under 3.12.
4. `make check` — clean.
5. `rg -n "3\.11|py311" pyproject.toml .github/workflows/` → zero matches.
6. `python -c "import kanbanmate"` — exits 0; `kanban --help` lists all commands.

---

> **Forward-ref to phase 11 (§11.A).** Phase 11's `kanban install --kanban-command` code commit (the
> one `feat(genesis)` TDD change in that otherwise-operational phase) also lands on THIS green 3.12
> tree, BEFORE the host activation uses it — see phase-11 §11.A. It is sequenced here so PM2 can be
> pinned to the absolute pyenv-3.12 `kanban` at install time.
