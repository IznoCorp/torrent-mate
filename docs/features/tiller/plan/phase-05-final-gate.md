# Phase 5 — Final gate + ACCEPTANCE

## Gate

**All of Phases 1–4 must be COMPLETE before starting Phase 5.**

Required:

- All phase commits on `feat/tiller`.
- `make check` green on the Phase 4 commit.
- `npm --prefix web run build` exit 0.
- No open TODO comments referencing tiller sub-phases.

## Overview

Sync the VERSION file if stale (0.15.0 was already bumped by create-branch — just verify),
run the full gate (`make check` + npm build), formalise the ACCEPTANCE criteria as executable
shell commands, re-exercise each criterion, and cut the final gate commit. Six sub-phases.

---

## Sub-phase 5.1 — Verify VERSION file sync

**Commit (only if stale):** `chore(tiller): sync VERSION file to 0.15.0`

**What to check:**

```bash
# Check all version pins agree
grep -r "0\.15\.0\|__version__" src/kanbanmate/__init__.py
grep "^version" pyproject.toml
cat src/kanbanmate/VERSION 2>/dev/null || echo "no VERSION file"
```

Expected: all three sources agree on `0.15.0`. The `create-branch` sub-skill already bumped
`pyproject.toml` and `__init__.py`. If a stale `src/kanbanmate/VERSION` file exists with an old
value, fix it:

```bash
echo "0.15.0" > src/kanbanmate/VERSION
git add src/kanbanmate/VERSION
git commit -m "chore(tiller): sync VERSION file to 0.15.0"
```

If all three already agree — no commit needed; move to 5.2.

---

## Sub-phase 5.2 — make check green

**Commit (only for fixes):** `fix(tiller): <describe what was broken>`

Run the full gate:

```bash
make lint
```

Expected: ruff + mypy — zero errors. If errors appear, fix them (likely missing type annotations
on new functions, unused imports, or import-order issues from the new modules). Then:

```bash
make test
```

Expected: all tests PASS; the summary line must NOT contain `ERROR` (an `ERROR` line means a
collection crash — fix the import before counting passed tests). Check the summary:

```bash
make test 2>&1 | tail -5
```

Expected pattern: `N passed` with no `ERROR` or `FAILED`.

Then run the full combined gate:

```bash
make check
```

Expected: exit 0.

Common fixes to expect:

- `src/kanbanmate/http/agent_terminal.py`: mypy may complain about `websocket.cookies` type —
  add `# type: ignore[attr-defined]` on the cookies access line.
- `src/kanbanmate/core/body_regions.py`: the `_STATUS_BLOCK` and `_MARKER_LINE` imports from
  `body_edit` are private names — if ruff flags them, expose them as public aliases in
  `body_edit.py` (add `STATUS_BLOCK = _STATUS_BLOCK` etc.) or suppress with `# noqa: PLC2701`.
- `src/kanbanmate/app/reaper.py`: the new `from kanbanmate.app.control_state import …` lazy
  import inside a function — ruff may flag `PLC0415` (import not at top of file); suppress with
  `# noqa: PLC0415` (consistent with the existing pattern in this codebase).

Check module sizes:

```bash
make check 2>&1 | grep -i "LOC\|ceiling\|warning" || echo "no size warnings"
```

If any module exceeds 800 LOC (soft warning), note it. If any exceeds 1000 LOC (hard ceiling),
split the module before closing this phase.

---

## Sub-phase 5.3 — npm build

**Commit (only for fixes):** `fix(tiller): fix JS build issue — <describe>`

```bash
npm --prefix web ci
npm --prefix web run build
```

Expected: both exit 0.

Verify xterm is in the bundle:

```bash
grep -rl "xterm" web/dist/assets/ | head -3
```

Expected: at least one file matches (xterm.js bundled by Vite).

If the build fails:

- Missing CSS import: ensure `AgentTerminal.jsx` imports `"xterm/css/xterm.css"` — Vite handles
  CSS imports from node_modules.
- Missing export: check xterm v5 API (`Terminal` is a named export from `"xterm"`; `FitAddon` is
  a named export from `"@xterm/addon-fit"`).
- Type errors in JSX: Vite does not type-check — build errors are syntax/import errors only.

---

## Sub-phase 5.4 — Formalise ACCEPTANCE.md

**Commit:** `docs(tiller): formalise ACCEPTANCE.md ACC-01..ACC-10`

**Create `docs/features/tiller/ACCEPTANCE.md`:**

````markdown
# tiller ACCEPTANCE criteria

Per SH-16 / CLAUDE.md: every criterion is an executable shell command with a documented
expected output. Re-exercise all ACC-NN before squash merge.

---

## ACC-01 — WS auth gate

**Command:**

```bash
pytest tests/http/test_agent_terminal.py -k "auth" -q
```
````

**Expected output:** `1 passed` (the `test_ws_auth_required_closes_1008` test).

---

## ACC-02 — Write requires control

**Command:**

```bash
pytest tests/http/test_agent_terminal.py -k "control or take_control or write_rejected" -q
```

**Expected output:** `2 passed` (write-rejected-before-take-control + take-control-then-send).

---

## ACC-03 — Reaper suspended under control

**Command:**

```bash
pytest tests/app/test_control_state.py -q
```

**Expected output:** `5 passed` (all sentinel helpers including stale detection).

**Additional reaper unit test (add to `tests/app/test_reaper.py` if not present):**

```bash
pytest tests/app/test_reaper.py -k "attached or sentinel or deferred" -q
```

**Expected output:** `1 passed` (sentinel present → end_session not called).

---

## ACC-04 — Body marker safety

**Command:**

```bash
pytest tests/core/test_body_regions.py -q
```

**Expected output:** `11 passed` or more, `0 failed`.

---

## ACC-05 — Body coherence gate

**Command:**

```bash
pytest tests/http/test_monitor_api.py -k "body_patch or patch" -q
```

**Expected output:** `4 passed` (happy path + 400 incoherence + 422 bad shape + markers
preserved).

---

## ACC-06 — Collapsible defaults

**Command (build + grep):**

```bash
npm --prefix web run build 2>&1 | tail -3 && \
grep -l "resolveCollapsed\|km:board:collapsed" web/src/panels/BoardPanel.jsx \
  web/src/lib/collapse.js
```

**Expected output:** build exit 0; both files listed (collapse logic present in both).

---

## ACC-07 — Build ships the terminal

**Command:**

```bash
npm --prefix web ci && npm --prefix web run build && \
grep -rl "xterm" web/dist/assets/ | head -1
```

**Expected output:** build exits 0; at least one path printed (xterm present in bundle).

---

## ACC-08 — Full gate

**Command:**

```bash
make check
```

**Expected output:** exit 0 (ruff + mypy zero errors; all Python tests green; module size
guards pass).

**Smoke test:**

```bash
python -c "import kanbanmate; print(kanbanmate.__version__)"
```

**Expected output:** `0.15.0`

---

## ACC-09 — Manual mobile pass (documented)

**Documented manual test (not automated — no JS test runner):**

1. Open KanbanMateUI on a phone browser (`https://km.iznogoudatall.xyz`).
2. Navigate to Monitoring; select a running ticket.
3. Tap "Terminal interactif" — the xterm terminal opens.
4. Tap "Prendre le contrôle" — red border appears.
5. Use the quick-key "↵ Enter" button — confirm the agent pane responds.
6. Tap "Rendre la main" — border returns to normal.
7. Tap "Éditer la description" — RichPromptEditor opens with the freeform prose.
8. Edit one word; tap "Enregistrer" — 200 OK; ticket detail refreshes.
9. Navigate to Board; collapse a non-empty column; reload the page — column stays collapsed
   (state persisted via localStorage).

**Capture:** take a screenshot or GIF of steps 3–5 and attach to ticket #47 as evidence.

---

## ACC-10 — Version surfaced

**Command:**

```bash
curl -s --connect-timeout 5 --max-time 10 http://localhost:8796/api/health
```

**Expected output:** JSON containing `"version"` matching `kanbanmate.__version__`, e.g.:

```json
{ "status": "ok", "version": "0.15.0" }
```

**Sidebar check (manual):** open KanbanMateUI on desktop and mobile — confirm `v0.15.0` appears
at the bottom of the sidebar (desktop) and in the mobile drawer footer.

````

Commit:

```bash
git add -f docs/features/tiller/ACCEPTANCE.md
git commit -m "docs(tiller): formalise ACCEPTANCE.md ACC-01..ACC-10"
````

(The `-f` flag is needed because `docs/` is blocked by the global `~/.gitignore`.)

---

## Sub-phase 5.5 — Re-exercise ACC-01..ACC-10

**No commit (unless a fix is needed — then:** `fix(tiller): <what>` **first).**

Run each executable criterion in sequence:

```bash
# ACC-01
pytest tests/http/test_agent_terminal.py -k "auth" -q
# ACC-02
pytest tests/http/test_agent_terminal.py -k "control or write_rejected" -q
# ACC-03
pytest tests/app/test_control_state.py -q
# ACC-04
pytest tests/core/test_body_regions.py -q
# ACC-05
pytest tests/http/test_monitor_api.py -k "body_patch or patch" -q
# ACC-06
npm --prefix web run build 2>&1 | tail -3 && grep -l "resolveCollapsed" web/src/panels/BoardPanel.jsx web/src/lib/collapse.js
# ACC-07
npm --prefix web ci && npm --prefix web run build && grep -rl "xterm" web/dist/assets/ | head -1
# ACC-08
make check && python -c "import kanbanmate; print(kanbanmate.__version__)"
# ACC-10 (requires kanban config serve running on 8796)
curl -s --connect-timeout 5 --max-time 10 http://localhost:8796/api/health || echo "server not running — defer to live deploy"
```

**ACC-09** is a manual mobile pass — document with a screenshot attached to ticket #47.

If any criterion fails:

1. Fix the underlying issue.
2. Commit the fix: `fix(tiller): <what ACC-NN revealed>`.
3. Re-run that criterion to confirm it now passes.
4. Re-run `make check` to confirm no regression.

All 9 executable criteria must show the expected output before closing this sub-phase.

---

## Sub-phase 5.6 — Gate commit

**Commit:** `chore(tiller): phase 5 gate — final gate + ACCEPTANCE green`

```bash
git add -f docs/features/tiller/plan/INDEX.md \
           docs/features/tiller/plan/phase-0*.md \
           docs/features/tiller/ACCEPTANCE.md
git commit -m "chore(tiller): phase 5 gate — final gate + ACCEPTANCE green"
```

Then update `IMPLEMENTATION.md` to mark Phase 5 complete (the `implement:phase` orchestrator
handles this — do not edit manually).

---

## Definition of Done

- [ ] `python -c "import kanbanmate; print(kanbanmate.__version__)"` → `0.15.0`.
- [ ] `make check` → exit 0.
- [ ] `npm --prefix web ci && npm --prefix web run build` → exit 0.
- [ ] `grep -rl "xterm" web/dist/assets/ | head -1` → non-empty.
- [ ] `docs/features/tiller/ACCEPTANCE.md` exists with ACC-01..ACC-10 as executable commands.
- [ ] All 9 executable ACC criteria pass (ACC-09 documented manually).
- [ ] Gate commit `chore(tiller): phase 5 gate — final gate + ACCEPTANCE green` is the HEAD of
      `feat/tiller`.
