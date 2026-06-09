# Phase 7 — PR fixes cycle 1

Findings from `/implement:pr-review` cycle 1 (5-agent toolkit). 2 medium + 5 minor,
all hardening-within-contract or test/doc completeness — **zero design contradictions**.
One finding (`enabled_not_in_priority`) ignored as out-of-RP5a-scope (deferred to RP5b).

## Gate

Requires phase 6 complete (`make check` green).

## Files

- **Modify:** `personalscraper/api/tracker/_errors.py` (A, C)
- **Modify:** `personalscraper/api/tracker/_factory.py` (E, H)
- **Modify:** `personalscraper/api/tracker/_registry.py` (D)
- **Modify:** `tests/unit/test_tracker_config_errors.py` (A)
- **Modify:** `tests/unit/test_tracker_factory.py` (B)
- **Modify:** `tests/unit/test_tracker_registry_close.py` (G)

## Tasks

### Task 7.1 — (A, Medium) Enforce `TrackerConfigError` invariants + freeze `issues`

In `_errors.py`, `TrackerConfigError.__init__`: raise `ValueError` if `issues` is empty or if any
issue has `severity != "error"` (the two invariants the docstring already promises). Store
`self.issues = tuple(issues)` (freeze at the boundary, parity with `ProviderExhausted.attempted`).
Update the attribute annotation/docstring to `tuple[TrackerConfigIssue, ...]`.

- Update `tests/unit/test_tracker_config_errors.py::test_carries_issues`: change `err.issues is issues`
  → equality (`list(err.issues) == issues` or `err.issues == tuple(issues)`).
- Add tests: `TrackerConfigError([])` raises `ValueError`; `TrackerConfigError([<warning-severity issue>])` raises `ValueError`.

**Acceptance:** the documented invariants are enforced by the type; `make check` green.

### Task 7.2 — (B, Medium) Test the never-fail-fast aggregation invariant

In `tests/unit/test_tracker_factory.py`, add a test that drives the **factory** to produce multiple
error issues at once: a `TrackerConfig` with two enabled, keyless trackers (`lacale` + `c411`,
`env={}`). Assert `TrackerConfigError` is raised, `len(exc.issues) == 2`, and both `lacale` and
`c411` appear in `[i.provider for i in exc.issues]`. (Mutation check: a fail-fast factory would
make this fail.)

**Acceptance:** the aggregation behaviour is non-vacuously pinned.

### Task 7.3 — (E, Minor) Narrow Step 2 `unknown_provider` to `priority` only

In `_factory.py` Step 2, the `unknown_provider` check currently unions `priority` **and**
`priority_by_media_type`. But `TrackerConfig._validate_priority_by_media_type` already rejects
unknown names in `priority_by_media_type` at config-load → that arm is unreachable. Iterate
`tracker_config.priority` only, and add a one-line comment noting `priority_by_media_type` unknown
names are rejected upstream by the model validator. (Leave Step 3's `disabled_in_priority` union
unchanged — that's a different, model-unvalidated check.)

**Acceptance:** no dead branch; `test_ghost_in_priority_raises` still green.

### Task 7.4 — (C, D, H, Minor) Docstring/comment accuracy

- (C) `_errors.py`: broaden the `unknown_provider` code docstring to cover BOTH emission sites
  (priority name absent from providers **and** enabled provider with no client implementation).
- (D) `_registry.py` `close()` docstring: reword "mirroring `ProviderRegistry.close()`" — clarify it
  closes each client's owned `_transport` directly (tracker clients expose no `close()` of their own);
  the parity is the fail-soft _shape_ (copied-list iterate, swallow per-client at DEBUG, no-op empty),
  not the close target.
- (H) `_factory.py:~117`: add a one-line comment documenting the single-key assumption of
  `api_key = env[required[0]]` (both current trackers are single-key; revisit for any multi-key tracker).

**Acceptance:** comments match the code; `make check` green.

### Task 7.5 — (G, Minor) Test the non-callable-`close` guard

In `tests/unit/test_tracker_registry_close.py`, add a test: a client whose `_transport.close` is a
**non-callable** (e.g. `_transport.close = 5`). `registry.close()` must not raise (the
`if not callable(close_fn): continue` guard). (Mutation check: collapsing the callable guard would
make this fail.)

**Acceptance:** the defensive guard is non-vacuously tested.

### Task 7.6 — Commit

One or two commits, e.g.:

- `fix(tracker-wiring): enforce TrackerConfigError invariants + freeze issues; narrow priority check; docstring fixes`
- `test(tracker-wiring): pin aggregation invariant + non-callable close guard + error-type invariants`

## Gate exit checklist

- [ ] `make check` green
- [ ] New tests fail on the pre-fix code (non-vacuous): aggregation, non-callable-close, empty/warning TrackerConfigError
- [ ] Commit SHA(s) recorded
