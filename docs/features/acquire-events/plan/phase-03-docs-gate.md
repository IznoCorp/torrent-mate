# Phase 3 — Docs update + ACCEPTANCE.md + `make check` gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `docs/reference/event-bus.md` (catalog table: 10 new rows + count prose),
update `docs/reference/architecture.md` (acquire/ module map + event domains list), write
`docs/features/acquire-events/ACCEPTANCE.md` with executable shell criteria matching
DESIGN §8, and pass the final `make check` gate.

**Architecture:** Documentation-only phase. No new source files. All three doc updates
are mechanical additions: append rows, bump counts, add bullet points. `ACCEPTANCE.md`
uses the exact executable-command format mandated by the ACCEPTANCE criteria format rule
(SH-16): every criterion is a shell command with a documented expected output.

**Tech Stack:** Markdown, shell one-liners (`python -c "..."`, `pytest -k "..."`).

---

## Gate (start of phase)

Phase 2 delivered:

- `personalscraper/subscribers/acquire.py` — `AcquisitionTelegramSubscriber`
- `personalscraper/conf/models/api_config.py` — `NotifyConfig.acquire_notify_enabled: bool = False`
- `personalscraper/commands/pipeline.py` — acquisition subscriber wired in `run`
- `tests/subscribers/test_acquire_subscriber.py` — dispatch + toggle + fail-soft tests
- `make check` green

Verify gate before starting:

```bash
cd /Users/izno/dev/PersonnalScaper
make check 2>&1 | tail -5
python -c "
from personalscraper.subscribers.acquire import AcquisitionTelegramSubscriber
from personalscraper.conf.models.api_config import NotifyConfig
assert NotifyConfig().acquire_notify_enabled is False
print('Phase 2 gate confirmed')
"
```

---

## File map

| Action | File                                         | Responsibility                              |
| ------ | -------------------------------------------- | ------------------------------------------- |
| Modify | `docs/reference/event-bus.md`                | append 10 catalog rows + bump count prose   |
| Modify | `docs/reference/architecture.md`             | acquire/ events.py entry + event-domain ref |
| Create | `docs/features/acquire-events/ACCEPTANCE.md` | 4 executable ACC criteria (DESIGN §8)       |

---

## Task 3.1 — Update `docs/reference/event-bus.md`

**Files:**

- Modify: `docs/reference/event-bus.md`

- [ ] **Step 3.1.1 — Read the current catalog section header**

  Read `docs/reference/event-bus.md` around the `## Event catalog (v1)` section
  (lines ~158–204) to locate:
  1. The prose line `The v1 catalog defines exactly 23 production event classes`.
  2. The last row of the catalog table (`VerifyItemDone`).

- [ ] **Step 3.1.2 — Bump the prose count**

  Change:

  ```
  The v1 catalog defines exactly 23 production event classes
  ```

  To:

  ```
  The v1 catalog defines exactly 33 production event classes
  ```

  Also update the parenthetical that says `len(_EVENT_CLASS_REGISTRY) == 23` to `== 33`.

- [ ] **Step 3.1.3 — Append 10 new rows to the catalog table**

  Append the following rows immediately after the `VerifyItemDone` row (keep the same
  column order: `Class | Module | Payload fields | Producer`):

  ```markdown
  | `SeriesFollowed` | `personalscraper.acquire.events` | `media_ref: MediaRef`, `title: str` | Follow D1 (wave 4) |
  | `SeriesUnfollowed` | `personalscraper.acquire.events` | `media_ref: MediaRef` | Follow D1 (wave 4) |
  | `WantedEnqueued` | `personalscraper.acquire.events` | `media_ref: MediaRef`, `kind: Literal["movie","episode"]`, `season: int \| None`, `episode: int \| None` | Follow D2 (wave 4) |
  | `WantedAbandoned` | `personalscraper.acquire.events` | `media_ref: MediaRef`, `reason: str` | Follow D2 cutoff (wave 4) |
  | `GrabSucceeded` | `personalscraper.acquire.events` | `media_ref: MediaRef \| None`, `info_hash: str`, `source_tracker: str`, `category: str \| None`, `tags: tuple[str, ...]` | RP5b / Follow D3 + Ratio C1 (wave 5)|
  | `GrabFailed` | `personalscraper.acquire.events` | `media_ref: MediaRef \| None`, `source_tracker: str \| None`, `reason: str` | RP5b (wave 5) |
  | `SeedObligationRecorded` | `personalscraper.acquire.events` | `info_hash: str`, `source_tracker: str`, `min_seed_time_s: int`, `dispatched_path: str \| None` | RP3 dispatch / O2 (wave 5) |
  | `SeedObligationBreached` | `personalscraper.acquire.events` | `info_hash: str`, `source_tracker: str`, `dispatched_path: str \| None` | O2 (wave 5) |
  | `SeedObligationSatisfied` | `personalscraper.acquire.events` | `info_hash: str`, `source_tracker: str` | O2 (wave 5) |
  | `RatioMeasured` | `personalscraper.acquire.events` | `tracker: str`, `observed_ratio: float`, `target_ratio: float` | Ratio C1 (wave 5) |
  ```

- [ ] **Step 3.1.4 — Update the footer note below the table**

  The current note reads:

  ```
  The set is pinned by `test_every_event_has_factory` in
  `tests/fixtures/test_factories_registry.py`; adding a new event requires
  extending both the registry and the factories in the same commit.
  ```

  No content change needed — it still applies. Optionally append:

  ```
  RP4 (`acquire-events`) added 10 acquisition events (catalog: 23 → 33).
  ```

---

## Task 3.2 — Update `docs/reference/architecture.md`

**Files:**

- Modify: `docs/reference/architecture.md`

- [ ] **Step 3.2.1 — Read the acquire/ directory listing**

  Search for the `acquire/` block in the architecture module map (around line 44–52
  based on the current file). It currently lists:

  ```
  │   ├── acquire/         # Acquisition lobe — 4-table SQLite store (RP3) + delete authority
  │   │   ├── domain.py           # Frozen VOs: FollowedSeries, WantedItem, SeedObligation, RatioState
  │   │   ├── delete_authority.py # DeleteAuthority: ...
  │   │   ├── _factory.py         # build_acquire_context ...
  │   │   ├── store.py            # ...
  │   │   ├── context.py          # AcquireContext dataclass ...
  │   │   └── migrations/         # SQL migration scripts for acquire.db
  ```

- [ ] **Step 3.2.2 — Add `events.py` entry to the acquire/ block**

  Insert a new line for `events.py` after `domain.py` (keeping alphabetical / logical order):

  ```
  │   │   ├── events.py           # Event catalog (RP4): 10 frozen Event subclasses for Follow/Grab/Seed/Ratio
  ```

  The exact insertion point: after the `domain.py` line, before `delete_authority.py` or
  whichever file follows it.

- [ ] **Step 3.2.3 — Find and update the event-domains enumeration (if present)**

  Search for any section that enumerates event domains (e.g., a list of modules that
  define events, or a table cross-referencing `events/` with lobe names):

  ```bash
  grep -n "event.*domain\|dispatch.*events\|indexer.*events\|acquire.*events" \
    /Users/izno/dev/PersonnalScaper/docs/reference/architecture.md --include="*.md" | head -10
  ```

  If such a list exists, add `acquire/events.py` to it. If no such enumeration exists,
  skip this step.

---

## Task 3.3 — Write `docs/features/acquire-events/ACCEPTANCE.md`

**Files:**

- Create: `docs/features/acquire-events/ACCEPTANCE.md`

The ACCEPTANCE criteria format rule (SH-16) requires every criterion to be an
executable shell command with documented expected output. Four criteria from DESIGN §8:

- [ ] **Step 3.3.1 — Write ACCEPTANCE.md**

  ````markdown
  # ACCEPTANCE — RP4: acquire-events (0.26.0 → 0.27.0)

  Every criterion is an executable shell command. Run from the repo root with
  the `feat/acquire-events` branch checked out and `pip install -e ".[dev]"`
  done.

  ---

  ## ACC-01 — Registry count = 33

  **Criterion:** After importing `personalscraper.events`, the
  `_EVENT_CLASS_REGISTRY` contains exactly 33 production event classes.

  ```bash
  python -c "
  import personalscraper.events
  from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY
  assert len(_EVENT_CLASS_REGISTRY) == 33, \
      f'Expected 33, got {len(_EVENT_CLASS_REGISTRY)}: {sorted(_EVENT_CLASS_REGISTRY)}'
  print('ACC-01 PASS: registry =', len(_EVENT_CLASS_REGISTRY))
  "
  ```
  ````

  **Expected output:** `ACC-01 PASS: registry = 33`

  ***

  ## ACC-02 — Envelope round-trip for all 10 acquisition events

  **Criterion:** Every acquisition event survives `event_to_envelope` →
  `json.dumps` → `json.loads` → `event_from_envelope` and reconstructs to an
  equal instance (including nested `MediaRef` fields).

  ```bash
  pytest tests/acquire/test_acquire_events.py::test_acquire_events_envelope_roundtrip \
    -v --tb=short
  ```

  **Expected output:** 10 PASSED (one per event class: SeriesFollowed,
  SeriesUnfollowed, WantedEnqueued, WantedAbandoned, GrabSucceeded, GrabFailed,
  SeedObligationRecorded, SeedObligationBreached, SeedObligationSatisfied,
  RatioMeasured). No FAILED, no ERROR.

  ***

  ## ACC-03 — Muted subscriber: no send when disabled, one send when enabled

  **Criterion:** `AcquisitionTelegramSubscriber` with `enabled=False` never calls
  `notifier.send`; with `enabled=True` calls it exactly once per emit (mocked notifier).

  ```bash
  pytest tests/subscribers/test_acquire_subscriber.py \
    -k "disabled_does_not_send or enabled_sends_once" \
    -v --tb=short
  ```

  **Expected output:** 20 PASSED (10 disabled + 10 enabled parametrized variants).
  No FAILED, no ERROR.

  ***

  ## ACC-04 — Full quality gate

  **Criterion:** `make check` exits 0 (lint + mypy + all tests pass, module-size
  budget respected).

  ```bash
  make check
  ```

  **Expected output:** Final line contains `passed` with 0 failed and 0 errors.
  Exit code 0.

  ```

  ```

- [ ] **Step 3.3.2 — Verify all four ACC criteria pass right now**

  Run each criterion command in order:

  ```bash
  cd /Users/izno/dev/PersonnalScaper

  # ACC-01
  python -c "
  import personalscraper.events
  from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY
  assert len(_EVENT_CLASS_REGISTRY) == 33, len(_EVENT_CLASS_REGISTRY)
  print('ACC-01 PASS:', len(_EVENT_CLASS_REGISTRY))
  "

  # ACC-02
  pytest tests/acquire/test_acquire_events.py::test_acquire_events_envelope_roundtrip \
    -v --tb=short 2>&1 | tail -15

  # ACC-03
  pytest tests/subscribers/test_acquire_subscriber.py \
    -k "disabled_does_not_send or enabled_sends_once" \
    -v --tb=short 2>&1 | tail -15

  # ACC-04
  make check 2>&1 | tail -10
  ```

  All four must pass before committing.

---

## Task 3.4 — Commit Phase 3

- [ ] **Step 3.4.1 — Stage and commit docs**

  The global `.gitignore` blocks `docs/` — use `git add -f`:

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  git add -f \
    docs/reference/event-bus.md \
    docs/reference/architecture.md \
    docs/features/acquire-events/ACCEPTANCE.md
  git commit -m "docs(acquire-events): event-bus catalog + architecture + ACCEPTANCE criteria"
  ```

---

## Task 3.5 — Final phase gate commit

- [ ] **Step 3.5.1 — Run the full check one last time**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  make check 2>&1 | tail -10
  ```

  Expected: green, 0 failures, 0 errors.

- [ ] **Step 3.5.2 — Smoke-import check**

  ```bash
  python -c "import personalscraper; print('smoke import: OK')"
  ```

  Expected: `smoke import: OK`

- [ ] **Step 3.5.3 — Phase gate commit**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  git commit --allow-empty -m "chore(acquire-events): phase 3 gate — docs + ACCEPTANCE + make check green"
  ```

  (Use `--allow-empty` only if nothing was left unstaged; normally the commit in
  Task 3.4 already carries the changes and this commit is purely a milestone marker.
  If there are unstaged changes, stage and commit them normally instead.)

---

## Phase 3 gate (feature complete)

```bash
cd /Users/izno/dev/PersonnalScaper

# Registry count
python -c "
import personalscraper.events
from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY
assert len(_EVENT_CLASS_REGISTRY) == 33
print('ACC-01 OK')
"

# Round-trip
pytest tests/acquire/test_acquire_events.py::test_acquire_events_envelope_roundtrip --tb=short -q
echo "ACC-02 done"

# Subscriber toggle
pytest tests/subscribers/test_acquire_subscriber.py \
  -k "disabled_does_not_send or enabled_sends_once" --tb=short -q
echo "ACC-03 done"

# Full gate
make check && echo "ACC-04 OK"
```

All four output lines (`ACC-01 OK`, `ACC-02 done`, `ACC-03 done`, `ACC-04 OK`) confirm
the feature is complete and ready for PR.
