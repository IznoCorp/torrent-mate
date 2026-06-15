# Phase 4 — Integration CI + Fixtures

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Design refs: DESIGN §6 (H6, H7), §7 (testing strategy).

**Goal**: H6 — real captured GraphQL fixtures replacing synthetic ones.
H7 — integration tests actually executed against a dedicated test org/Project (gated on
`KANBAN_TOKEN` secret). Nightly CI workflow.

---

## Gate

Phase 3 complete: H3–H5 committed, `make check` green, pagination + perms + kill-switch tested.

---

### 4.1 — H6: real captured GraphQL fixtures

**Files**: `tests/adapters/github/fixtures/` (new real fixture files),
`tests/adapters/github/test_client.py` (update), `tests/adapters/github/test_pagination.py` (update).

- [ ] Capture real GraphQL responses from the test org (or replay from PoC fixture shapes in
      `PersonnalScaper/.claude/skills/kanban/tests/github/fixtures/`). Required fixture files:
  - `board_snapshot_page1.json` — full `projectItems` response, page 1 (`hasNextPage: true`)
  - `board_snapshot_page2.json` — page 2 (`hasNextPage: false`)
  - `cheap_probe.json` — `projectItems(first:5 orderBy:{field:UPDATED_AT direction:DESC})` response
  - `move_mutation.json` — `updateProjectV2ItemFieldValue` success response
  - `comment_rest.json` — REST `POST /repos/{owner}/{repo}/issues/{n}/comments` success response
- [ ] Update `test_client.py` and `test_pagination.py` to load fixtures from disk rather than
      inline dicts. Assert parsed `Ticket` fields match fixture values exactly.
- [ ] Verify: `make test` pass. Fixtures committed under `tests/adapters/github/fixtures/`.

```bash
git commit -m "test(genesis): H6 real captured GraphQL fixtures (board snapshot, move, comment)"
```

---

### 4.2 — L2 local-real test: full tick with real tmux + real git

**Files**: `tests/local_real/__init__.py`, `tests/local_real/test_tick_local.py`.

- [ ] Write `@pytest.mark.local_real` integration test that:
  1. Creates a real bare git repo in `tmp_path`.
  2. Instantiates `FsBoardReader` stub (returns a fake `BoardSnapshot` with one ticket in an
     agent column) and real `FsStore`, `WorktreeAdapter`, `SessionsAdapter`.
  3. Calls `tick()` directly (no PM2, no daemon loop).
  4. Asserts a real tmux session exists (`tmux has-session -t ticket-<n>`).
  5. Asserts worktree directory created under `tmp_path`.
  6. Teardown: kill tmux session, remove worktree.
- [ ] This test proves a real column move spawns a real tmux session in a real worktree
      (DESIGN §7 L2 "local-real" level).
- [ ] Gate: `claude` binary stubbed to `echo` in the test env (`env={"PATH": ...}`).
- [ ] Verify: `pytest -m local_real tests/local_real/` passes in a terminal with tmux available.

```bash
git commit -m "test(genesis): L2 local-real tick test (real tmux + real git, GitHub faked)"
```

---

### 4.3 — H7: integration test against real GitHub Projects v2

**Files**: `tests/integration/__init__.py`, `tests/integration/test_poll_real_board.py`,
`.github/workflows/nightly.yml`.

- [ ] Write `@pytest.mark.integration` test (gated on env var `KANBAN_TOKEN`):
  1. Read config from `KANBAN_TEST_PROJECT` env var (node id of the test org's project).
  2. Move a known test card to an inert column via `BoardWriter.move_card`.
  3. Run `tick()` once (via `kanban poll --once` or direct call).
  4. Assert `diff()` detected the move (persisted state updated).
  5. Assert no tmux session launched (inert column → NOOP).
- [ ] `nightly.yml` CI workflow: trigger on schedule (`0 3 * * *`) + manual dispatch.
      Needs secrets `KANBAN_TOKEN` + `KANBAN_TEST_PROJECT`. Steps:
      `pip install -e ".[dev]"` → `pytest -m integration tests/integration/ -v`.
- [ ] Verify: `make test` (unit only) still passes. Integration test skips without `KANBAN_TOKEN`.

```bash
git commit -m "test(genesis): H7 integration tests against real GitHub Projects v2 + nightly CI"
```

---

### 4.4 — Update PR CI to include `claude plugin validate`

**Files**: `.github/workflows/pr.yml` (extend).

- [ ] Add steps to `pr.yml` after `make check`:
      `claude plugin validate . --strict` (marketplace) AND
      `claude plugin validate ./plugin --strict` (plugin) — run on every PR, no secrets needed.
      This is the L1+L2+validate split described in DESIGN §7.
- [ ] Verify: `make check` passes locally. `pr.yml` diff is minimal (the validate steps added).

```bash
git commit -m "ci(genesis): add plugin validate steps to PR workflow (DESIGN §7 CI split)"
```

---

### Phase 4 Gate

1. `make lint` — zero errors
2. `make test` — all pass (integration skipped without secret — expected)
3. `make check` — clean
4. `pytest -m local_real tests/local_real/` — passes (requires tmux; skip in CI if unavailable)
5. `python -c "import kanbanmate"` — exits 0

```bash
git commit --allow-empty -m "chore(genesis): phase 4 gate — integration CI + fixtures"
```
