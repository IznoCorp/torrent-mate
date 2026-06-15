# Phase 6 — PR fixes cycle 1

> Fixes from PR #1 review cycle 1 (33 confirmed findings; 6 refuted as intentional design choices).
> All retained findings are coherent with DESIGN.md scope. Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Severities: 1 critical, 6 major, 7 medium addressed here; ~16 minor doc/test nits folded opportunistically into the
> nearest sub-phase where cheap, otherwise deferred (do not block on minors).

---

## Gate

Phase 5 complete; PR #1 open + CI green. Branch feat/genesis. `make check` green at start.
Decided fix approach for the critical name/key seam (operator): **resolve at the columns layer** (match the GitHub
Status option NAME against the columns model; the adapter stays dumb).

---

### 6.1 — Resolve board option name to column (CRITICAL launch fix)

**Findings**: types-3 (critical) + errors-6 (major). The github adapter sets `Ticket.column_key` to the GitHub Status
option NAME ("In Progress"), but `decide()` resolves `columns.get(transition.to_column)` against the columns.yml KEY
("InProgress"). The shipped `columns.yml.tmpl` uses key≠name for the AGENT columns, so every move into a triggering
column misses → NOOP → **no agent ever launches on the default board**, with zero diagnostic.
**Approach (operator-chosen — columns layer)**: in `core/columns.py` provide a name→Column resolution (the Column model
already carries both `key` and `name`); make the launch decision resolve the board's option NAME to a Column by name
(prefer name, fall back to key for back-compat). Resolution lives in `core/decide.py`/`app/tick.py` (core stays pure).
ALSO (errors-6): when a transition's destination column is **unknown** to the model, LOG a warning (distinguish a
misconfiguration from an intentional inert NOOP — do not stay silent). Fold the minor comments-9 fix (decide module
docstring omits the unattended-hours BLOCK trigger) here if touching decide.py.
**Files**: `src/kanbanmate/core/columns.py`, `src/kanbanmate/core/decide.py` and/or `src/kanbanmate/app/tick.py`,
`tests/app/test_tick.py`, `tests/core/test_decide.py`.
**Acceptance**: a Ticket whose `column_key` is the GitHub option NAME of an AGENT column (e.g. "In Progress") resolves to
`ActionKind.LAUNCH` — a NEW test exercises the real adapter→decide seam with key≠name (the variance the old unit tests
masked by using the key); an unknown destination column emits a log warning rather than a silent NOOP; `make check` green.

```bash
git commit -m "fix(genesis): resolve board Status-option name to column (launch path broken on default board)"
```

---

### 6.2 — Daemon writes heartbeat marker; doctor docstrings corrected (MAJOR)

**Findings**: code-4 (major) + comments-1 (major) + comments-12 (minor) + comments-2 (minor). `kanban doctor` reads
`<root>/daemon.heartbeat` and FAILs when absent, but nothing writes it → doctor always exits 1 on a healthy daemon.
**Approach**: in `daemon/loop.py`, write/touch `<root>/daemon.heartbeat` after each completed tick (atomic-ish; the path
doctor already reads). Correct `cli/doctor.py` `_check_heartbeat_fresh` docstring (stop asserting an unimplemented write)
and the `app/tick.py` heartbeat forward-reference comment. Fold comments-2 (doctor docstring says "seven" checks but lists
eight → "eight").
**Files**: `src/kanbanmate/daemon/loop.py`, `src/kanbanmate/cli/doctor.py`, `src/kanbanmate/app/tick.py`,
`tests/cli/test_doctor.py`, `tests/daemon/` (heartbeat-written assertion — may live in 6.5's loop test).
**Acceptance**: after a tick, `<root>/daemon.heartbeat` exists and is fresh; `doctor`'s heartbeat check PASSES for a
fresh file (test); no docstring claims an unimplemented write; `make check` green.

```bash
git commit -m "fix(genesis): daemon writes daemon.heartbeat each tick so kanban doctor passes (reader had no writer)"
```

---

### 6.3 — Bound `_status_option_counts` pagination (MAJOR)

**Finding**: errors-4 (major) + comments-5 (minor). `_status_option_counts()` uses a bare `while True:` with no max-page
cap / empty-endCursor / non-advancing-cursor guard — the exact protections `snapshot()` already applies — reached on the
normal `kanban init` path, so a malformed/repeated-cursor response hangs init forever.
**Approach**: mirror `snapshot()`'s guards (max_pages cap + break on empty endCursor + break on `end_cursor == after`).
Fold comments-5 (stale `board_items` "page 1 only" docstring — pagination is shipped).
**Files**: `src/kanbanmate/adapters/github/client.py`, `src/kanbanmate/adapters/github/_queries.py` (docstring),
`tests/adapters/github/test_pagination.py`.
**Acceptance**: a fixture with `hasNextPage:true` + null/repeated endCursor terminates (test asserts no infinite loop);
`make check` green.

```bash
git commit -m "fix(genesis): bound _status_option_counts pagination (init could hang on malformed cursor)"
```

---

### 6.4 — Exception-isolate daemon config reload (MAJOR)

**Finding**: code-5 + errors-5 (major; same defect). The config hot-reload (`_load_wiring_config`) sits OUTSIDE the
tick's try/except, so a half-saved/malformed/deleted `config.yml` raises out of `run_loop` and crashes the daemon —
contradicting its own "a failed cycle must not crash the daemon" contract.
**Approach**: wrap the reload in try/except; on failure log and KEEP serving with the previous (last-good) WiringConfig.
**Files**: `src/kanbanmate/daemon/loop.py`, `tests/daemon/test_loop.py` (assert reload-failure → loop continues with
prior config — may co-locate with 6.5).
**Acceptance**: a bad config edit mid-run is logged and the loop continues on the previous config (test); `make check` green.

```bash
git commit -m "fix(genesis): exception-isolate daemon config reload (bad config.yml must not crash the daemon)"
```

---

### 6.5 — Behavioral tests for run_loop + \_load_wiring_config (MAJOR + MEDIUM)

**Findings**: tests-1 (major) + tests-5 (medium). The daemon orchestration spine (`run_loop`, `_acquire_lock`,
`_load_wiring_config`, `_config_mtime`, `_install_signal_handlers`) has NO behavioral test — only an import smoke test —
despite shipping purpose-built seams (`max_iterations`, injectable `sleep`).
**Approach**: add `tests/daemon/__init__.py` + `tests/daemon/test_loop.py`. Drive `run_loop` with `max_iterations`, a fake
`sleep`, and a monkeypatched `run_one_tick` (incl. one that RAISES → assert the loop continues), asserting: flock acquire +
release-in-finally, second-instance refusal (DaemonLockError), mtime-driven reload, shutdown-flag/SIGTERM finish-then-exit,
and the heartbeat write (6.2) + reload-resilience (6.4). Test `_load_wiring_config`: valid config→WiringConfig fields,
missing required key→KeyError, missing columns file→FileNotFoundError, PAUSE sentinel→kill_switch=True.
**Files**: `tests/daemon/__init__.py`, `tests/daemon/test_loop.py`.
**Acceptance**: the loop's lock/reload/shutdown/exception-continue/heartbeat paths and the config loader's success+failure

- kill-switch derivation are covered; `make check` green (mypy src tests included).

```bash
git commit -m "test(genesis): behavioral tests for run_loop + _load_wiring_config (orchestration spine)"
```

---

### 6.6 — Wire the dependency gate into launch (MEDIUM)

**Finding**: code-2 (medium). `core/dependency_gate.evaluate()` (parse `Depends on #N`, require each in a Done/Merge
column) has zero call sites — agents launch regardless of unmet dependencies, leaving a designed core module dead.
**Approach**: wire `evaluate()` into the launch decision in `app/tick.py` (which holds the snapshot): on a LAUNCH verdict,
evaluate the ticket's dependencies against the snapshot; if unmet → do NOT launch (BLOCK + sticky comment explaining the
unmet dependency). The issue body carrying `Depends on #N` must be available — if the snapshot Ticket does not carry the
body, extend the adapter/snapshot to include it (minimal) OR, if that is out of cycle scope, document the precise deferral
in the module + DESIGN-note and add a test for the pure `evaluate()` wiring decision. Prefer wiring it.
**Files**: `src/kanbanmate/app/tick.py` (+ possibly `adapters/github` / `core/domain` for the issue body), `tests/app/test_tick.py`.
**Acceptance**: a ticket entering an agent column with an unmet `Depends on #N` is NOT launched (BLOCK); with deps met it
launches — test asserts both; `make check` green.

```bash
git commit -m "feat(genesis): gate agent launch on dependency_gate (Depends on #N must be in a done column)"
```

---

### 6.7 — Wire anti-loop state through the tick + fix misleading comment (MEDIUM)

**Finding**: code-1 (medium). `tick()` builds `DecideContext` WITHOUT `antiloop_state` and `record_move()` is never called,
so the dedup/rate-limit guard is inert. (DESIGN §6 downgrades anti-loop — diff-idempotence is the production backstop — so
this is defense-in-depth + a misleading comment, not a safety hole.)
**Approach**: thread an `AntiLoopState` across ticks (carry it in the in-memory daemon state alongside PersistedState),
pass it into `DecideContext.antiloop_state`, and call `core/antiloop.record_move()` after each automatic move so the guard
accumulates. Correct the misleading `tick.py` "idempotence comes from state + anti-loop" comment to reflect that diff is
the primary backstop and anti-loop is defense-in-depth.
**Files**: `src/kanbanmate/app/tick.py`, `src/kanbanmate/app/wiring.py` (state threading), `tests/app/test_tick.py`.
**Acceptance**: the daemon records its own automatic moves and threads `antiloop_state` across ticks (test: a repeated
automatic move to the same target is dedup-guarded); the comment is accurate; `make check` green.

```bash
git commit -m "fix(genesis): thread anti-loop state through tick + record_move (guard was inert)"
```

---

### 6.8 — `claude_install` reports a failed plugin install (MEDIUM)

**Finding**: errors-2 (medium). `claude_install()` discards the `claude plugin install` return code and the CLI prints
"claude plugin registered" even on failure (false success). Fold errors-7 (minor): guard the missing-`claude`-binary
FileNotFoundError so `kanban install` reports an actionable error instead of a raw traceback after "host tier ready".
**Approach**: check the install command's result; on non-success, report a clear non-success outcome (do not echo success).
Guard `_is_kanban_installed`/install for a missing `claude` binary. Keep idempotency (already from the list-check guard).
**Files**: `src/kanbanmate/cli/install.py`, `src/kanbanmate/cli/app.py`, `tests/cli/test_install_claude.py`.
**Acceptance**: a failed plugin install → non-success report (test); a missing `claude` binary → clean actionable error,
not a traceback (test); `make check` green.

```bash
git commit -m "fix(genesis): claude-tier install reports failure instead of false success"
```

---

### 6.9 — Enforce AntiLoopState immutability at the type (MEDIUM)

**Finding**: types-1 (medium). `AntiLoopState` is `@dataclass(frozen=True)` but its `dict` fields are mutable in place,
so the documented "input state left untouched" invariant is convention-only (and the instance is incidentally unhashable).
**Approach**: express immutability at the type boundary (e.g. store the data in immutable structures — tuples of pairs, or
`Mapping`-typed fields populated only via `record_move`'s copy), so in-place mutation is prevented; `record_move` keeps
returning a new state. Keep the public `is_blocked`/`record_move` signatures stable.
**Files**: `src/kanbanmate/core/antiloop.py`, `tests/core/test_antiloop.py`.
**Acceptance**: in-place mutation of the state is prevented/typed-out; `record_move` still returns a fresh state; existing
antiloop tests pass; `make check` green.

```bash
git commit -m "refactor(genesis): make AntiLoopState immutability type-enforced, not convention"
```

---

### 6.10 — Reconcile fetched_at + monotonic-vs-wallclock docs (MEDIUM)

**Findings**: types-2 (medium) + comments-3 (minor) + comments-4 (minor). `BoardSnapshot.fetched_at` is documented as
"used by the adaptive poll interval strategy" but is never read, and its `time.monotonic` base diverges from the
wall-clock `time.time()` used everywhere else; `interval.py`/`antiloop.py` docstrings say "monotonic" but production feeds
wall-clock.
**Approach**: pick ONE coherent story and make code+docs agree. Simplest: relax `fetched_at`'s docstring (it is not wired
into the interval) OR wire it in; and correct the `interval.py`/`antiloop.py` "monotonic" docstrings to "wall-clock/POSIX
seconds" to match the injected `Clock` (do NOT switch the code to monotonic — antiloop timestamps are persisted and must
stay wall-clock-comparable).
**Files**: `src/kanbanmate/core/domain.py`, `src/kanbanmate/core/interval.py`, `src/kanbanmate/core/antiloop.py`.
**Acceptance**: no docstring claims an unfulfilled wiring or a wrong time-base; `make check` green.

```bash
git commit -m "docs(genesis): reconcile fetched_at + monotonic/wall-clock time-base docstrings with reality"
```

---

### 6.11 — Test the github adapter fail-loud error paths (MEDIUM)

**Finding**: tests-2 (medium). The adapter's fail-loud guards are untested: `GraphQLError` (non-empty GraphQL `errors`
array), `GitHubHTTPError` (HTTP ≥ 400 carrying the decoded body), and `ValueError` ("no Status single-select field").
**Approach**: add tests feeding (a) a GraphQL response with an `errors` array → assert `GraphQLError`; (b) a status-fieldless
fields response → assert `ValueError`; (c) the transport HTTP≥400 branch → assert `GitHubHTTPError`.
**Files**: `tests/adapters/github/test_client.py` (+ fixtures if needed).
**Acceptance**: the three guards are each exercised by a `pytest.raises` test; `make check` green.

```bash
git commit -m "test(genesis): cover github adapter fail-loud error paths (GraphQLError, HTTP error, no-Status-field)"
```

---

### Phase 6 Gate

1. `make lint` — zero errors (ruff + `mypy src tests`)
2. `make test` — all pass
3. `make check` — clean
4. The critical launch-path fix is proven by a test exercising the adapter→decide seam with key≠name
5. `python -c "import kanbanmate"` — exits 0

```bash
git commit --allow-empty -m "chore(genesis): phase 6 gate — PR fixes cycle 1"
```
