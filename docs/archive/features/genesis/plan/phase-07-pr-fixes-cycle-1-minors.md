# Phase 7 — PR fixes cycle 1 (deferred minors)

> The 11 minor cycle-1 review findings deferred from phase 6 (the other ~7 minors were folded into 6.x).
> Operator directive: correct EVERYTHING. Each sub-phase = ONE commit `<type>(genesis): <description>`.

---

## Gate

Phase 6 complete; PR #1 updated + CI green; `make check` green (409 passed). Branch feat/genesis.

---

### 7.1 — Robustify state load against a corrupt file (errors-8)

**Finding**: `FsStateStore.load()` does `json.loads(path.read_text())` + `TicketState(**data)` with NO guard, unlike
`list_running()` which skips files raising `(OSError, json.JSONDecodeError)`. The agent-facing `cli/cancel.py`
`build_cancel_ticket()` calls `load()` with no guard → a corrupt/partial `state/<issue>.json` crashes `kanban cancel`
with an opaque traceback instead of the idempotent teardown the docstring promises (absent state is safe).
**Fix**: make `FsStateStore.load()` treat an unreadable/corrupt/partial state file the SAME as absent — catch
`(OSError, json.JSONDecodeError, TypeError)` and return `None` (poison file → no-state path), mirroring `list_running`.
**Files**: `src/kanbanmate/adapters/store/fs_store.py`, `tests/adapters/test_fs_store.py`.
**Acceptance**: a corrupt `state/<n>.json` → `load()` returns `None` (test); `kanban cancel` degrades to the idempotent
absent-state path rather than raising. `make check` green.

```bash
git commit -m "fix(genesis): FsStateStore.load tolerates a corrupt state file (treat as absent, like list_running)"
```

---

### 7.2 — Closed Status type instead of bare str (types-4)

**Finding**: `TicketState.status` is `str`; the closed set (`"running"`/`"idle"`) lives as raw literals across
`fs_store.list_running` (filter `== "running"`), `cli/sessions.py` (`status == "running"`), and `app/actions.py`
(`STATUS_RUNNING = "running"`) — a typo silently makes a ticket invisible to the reaper. The rest of the domain uses
enums for closed sets (`ColumnClass`, `ActionKind`).
**Fix**: introduce a `TicketStatus` (Enum with `RUNNING`/`IDLE`, or `Literal["running","idle"]`) as the single source of
truth in `ports/store.py`; type `TicketState.status` with it; update the writer (`actions.STATUS_RUNNING`) and readers
(`fs_store.list_running`, `sessions.py`) to use it. Keep the on-disk JSON value a plain string (serialise the enum value)
so existing state files + fixtures still parse.
**Files**: `src/kanbanmate/ports/store.py`, `src/kanbanmate/adapters/store/fs_store.py`, `src/kanbanmate/cli/sessions.py`,
`src/kanbanmate/app/actions.py`, the affected tests.
**Acceptance**: status is a closed type (mypy rejects an off-set value at write sites); round-trip save/load preserves the
value; reaper/list_running/sessions still work; `make check` green.

```bash
git commit -m "refactor(genesis): closed TicketStatus type for TicketState.status (was a bare str)"
```

---

### 7.3 — Fill the remaining small test gaps (tests-3, tests-4, tests-6, tests-7)

**Findings**: untested branches/functions: (tests-3) the per-action watchdog `FutureTimeoutError` branch in
`app/tick.py` `_run_with_watchdog`; (tests-4) the reap partial-failure path (`_reap_stale_agents` `errors += 1` when a
reap sub-action fails — CHECK FIRST: sub-phase 6.7 may already cover this via `test_failed_reap_move_is_not_recorded`;
add only if a `move_card`-raises → `reaped==0, errors>=1` assertion is missing); (tests-6) `adapters/github/token.load_token`
(env `KANBAN_TOKEN` wins, file fallback, `FileNotFoundError`, `.strip()`); (tests-7) `app/wiring.build_tick_config`
(columns map + kill_switch threading).
**Fix**: add the missing tests, driving the real code via injectable seams (a blocking adapter past `action_timeout` for
the watchdog; an explicit `env` dict + `path` for `load_token`; a `WiringConfig` for `build_tick_config`).
**Files**: `tests/app/test_tick.py`, `tests/adapters/github/test_token.py` (new) or test_client.py, `tests/app/test_wiring.py`
(new) or an existing app test. TEST-ONLY — do not modify src/.
**Acceptance**: each named branch/function is exercised by a new test; `make check` green.

```bash
git commit -m "test(genesis): cover watchdog timeout, reap partial-failure, load_token, build_tick_config"
```

---

### 7.4 — Docstring/comment accuracy nits (comments-6, 7, 8, 10)

**Findings**: (comments-6) `cli/init.py` comment "the daemon re-reads this [clone columns.yml] on a mtime change" — the
daemon watches `config.yml`'s mtime, not the clone's columns.yml; (comments-7) dead `_DEFAULT_TITLE_SUFFIX = ""` constant
in `cli/init.py` with a misleading comment (title defaulting is inline at `title = project_title or name`); (comments-8)
`ports/store.py` module docstring attributes the Protocol's writes to "atomic O_EXCL + flock", but Protocol methods use
temp-file + `os.replace`; O_EXCL+flock guard only the adapter-specific `reserve_slot`; (comments-10) `core/columns.py`
`_resolve_class` docstring ends with the garbled clause "`kanban-move` refuses agent targets anti-loop".
**Fix**: correct comment-6 to say the daemon watches config.yml's mtime; remove the dead `_DEFAULT_TITLE_SUFFIX` + its
comment; clarify the store.py docstring (state writes = temp+os.replace; O_EXCL+flock = slot reservation only); reword the
columns.py clause (e.g. "the more conservative choice, since kanban-move's anti-loop guard refuses agent-column targets").
**Files**: `src/kanbanmate/cli/init.py`, `src/kanbanmate/ports/store.py`, `src/kanbanmate/core/columns.py`.
**Acceptance**: each docstring/comment now matches the code; the dead constant is gone (rg shows no references lost);
`make check` green (ruff may flag the removed unused constant — confirm clean).

```bash
git commit -m "docs(genesis): correct misleading comments + drop dead constant (init/store/columns)"
```

---

### 7.5 — Implement the daemon JSONL log writer (comments-11)

**Finding**: `cli/logs.py` documents (present tense) that "the daemon writes structured JSONL to `<root>/log/daemon.jsonl`"
and reads it, but NOTHING writes it — `kanban logs` reads a non-existent file and shows nothing. Same reader-without-writer
gap as the heartbeat (fixed in 6.2). DESIGN §5 specifies structured JSONL daemon logging.
**Fix**: make the doc TRUE by implementing the writer — add a JSON-lines logging handler in the daemon (`daemon/loop.py`
`main()` / a small `daemon/logging` helper) that writes one JSON object per line to `<root>/log/daemon.jsonl` (create the
`log/` dir; ensure `kanban logs` reads what the daemon writes). Keep it minimal and correct: structured records (timestamp,
level, event/message, and the issue number when present). Reconcile the `logs.py` docstring with the now-real writer (and
the `DEFAULT_TAIL` "size-rotated" comment — either add a simple size cap or soften the claim to match what is implemented).
Per-ticket `ticket-<n>.log` (the agent session's own log) is out of scope here — note it as agent-side.
**Files**: `src/kanbanmate/daemon/loop.py` (+ a tiny `daemon/jsonl_log.py` helper if cleaner), `src/kanbanmate/cli/logs.py`
(docstring reconcile), `tests/daemon/test_loop.py` or `tests/cli/test_logs.py` (assert the daemon writes a JSONL line that
`kanban logs` reads back).
**Acceptance**: running the daemon (one tick, in a tmp root) writes a parseable JSON line to `<root>/log/daemon.jsonl`;
`kanban logs` reads it back; the logs.py docstring matches reality; `make check` green.

```bash
git commit -m "feat(genesis): daemon writes structured JSONL log so kanban logs works (reader had no writer)"
```

---

### Phase 7 Gate

1. `make lint` — zero errors (ruff + `mypy src tests`)
2. `make test` — all pass
3. `make check` — clean
4. `rg --type py 'monotonic|_DEFAULT_TITLE_SUFFIX|refuses agent targets anti-loop' src/` — zero matches (nits gone)
5. `python -c "import kanbanmate"` — exits 0

```bash
git commit --allow-empty -m "chore(genesis): phase 7 gate — PR fixes cycle 1 (deferred minors)"
```
