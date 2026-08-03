# rm-lacale — Acceptance Criteria

> **Feature**: rm-lacale (#156 — complete removal of the LaCale tracker + Torr9 zero-remnant proof)
> **Version**: 0.77.0
> **Date**: 2026-08-03
> **DESIGN**: docs/features/rm-lacale/DESIGN.md
> **Plan**: docs/features/rm-lacale/plan/phase-03-acceptance-full-gate.md
>
> Every criterion is an executable shell command with documented expected output.
> Prose-only criteria are invalid per SH-16 / tech-debt 0.16.0.
> Status is updated at each phase gate and at the final PR gate.
>
> **Command-form note (BINDING — plan INDEX deviation 1)**: DESIGN D8/D10 write
> the greps as `--type py -g '*.ts' …`. On ripgrep 15.1.0 (this machine) a `-g`
> glob OVERRIDES the type filter — the design's exact command silently searches
> zero `.py` files (verified empirically 2026-08-03). ACC-01/ACC-02 below use
> the corrected all-glob form (`-g '*.py'` instead of `--type py`), confirmed to
> catch all py hits. Same intent, corrected letter.

---

## ACC-01 — lacale zero-hit grep (D10)

**What**: Zero `lacale` remnants (case-insensitive) across backend, tests,
frontend sources, config example, reference docs, root CLAUDE.md and
`.env.example`. Single exemption: the removed-tracker regression suite, which
pins the name on purpose. `docs/archive/**` and `docs/features/rm-lacale/**`
(D10's other stated exemptions) are outside the scanned paths by construction;
historical `docs/analysis/` files are untracked.
**Scope**: DESIGN D10 (residual-import gate — the deletion IS the feature).

```bash
rg -i "lacale" -g '*.py' -g '*.ts' -g '*.tsx' -g '*.json5' -g '*.md' -g '!tests/acquire/test_removed_tracker_history.py' personalscraper/ tests/ frontend/src/ config.example/ docs/reference/ CLAUDE.md .env.example
# Expected: no output, exit 1
```

**Status**: PASS (exercised 2026-08-03 — observed no output, exit 1.
Non-vacuity check same day: dropping the exclusion glob, the exempted file
`tests/acquire/test_removed_tracker_history.py` yields 6 matches — the grep
form does catch py hits.)

---

## ACC-02 — torr9 zero-hit grep (D8)

**What**: Zero `torr9` remnants (case-insensitive) across the same surfaces —
the executable zero-remnant proof for the earlier Torr9 removal. Same single
exemption: the regression suite pins torr9 absence + historic readability
(phase 1 reworded the two explanatory comments in `api/tracker/_base.py` and
`tests/unit/test_c411_client.py` so only that file needs exempting).
**Scope**: DESIGN D8 (Torr9 executable proof, per operator ask).

```bash
rg -i "torr9" -g '*.py' -g '*.ts' -g '*.tsx' -g '*.json5' -g '*.md' -g '!tests/acquire/test_removed_tracker_history.py' personalscraper/ tests/ frontend/src/ config.example/ docs/reference/
# Expected: no output, exit 1
```

**Status**: PASS (exercised 2026-08-03 — observed no output, exit 1)

---

## ACC-03 — enum + factory registry absence

**What**: `ProviderName` no longer carries a `LACALE` member and the tracker
factory's class registry no longer knows `lacale`.
**Scope**: DESIGN D1 (remove ALL LaCale code: enum member + factory entry).

```bash
command python3 -c "from personalscraper.api._contracts import ProviderName; assert not hasattr(ProviderName, 'LACALE'); print('OK: no ProviderName.LACALE')"
command python3 -c "from personalscraper.api.tracker._factory import _TRACKER_CLASSES; assert 'lacale' not in _TRACKER_CLASSES; print('OK: lacale not in _TRACKER_CLASSES')"
# Expected: both exit 0 — "OK: no ProviderName.LACALE" / "OK: lacale not in _TRACKER_CLASSES"
```

**Status**: PASS (exercised 2026-08-03 — observed `OK: no ProviderName.LACALE`
and `OK: lacale not in _TRACKER_CLASSES`)

---

## ACC-04 — factory raises its standard unknown-tracker error for "lacale"

**What**: Re-enabling `lacale` in config is a loud `unknown_provider` boot
error — the factory's standard contract for any name without a client
implementation, never a silent skip and never a resurrected client. Snippet
mirrors the absence pin `test_factory_rejects_the_removed_tracker_as_unknown`
in the regression suite.
**Scope**: DESIGN D1 + §4 (registry tests assert lacale is UNKNOWN).

```bash
command python3 -c "
from unittest.mock import MagicMock
from personalscraper.api.tracker._errors import TrackerConfigError
from personalscraper.api.tracker._factory import build_tracker_registry
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.transport._policy import CircuitPolicy
from personalscraper.conf.models.api_config import TrackerConfig, TrackerProviderConfig
from personalscraper.core.event_bus import EventBus
cfg = TrackerConfig(providers={'lacale': TrackerProviderConfig(enabled=True)}, priority=['lacale'])
try:
    build_tracker_registry(cfg, RankingConfig(), settings=MagicMock(), event_bus=EventBus(),
                           cb_policy=CircuitPolicy(failure_threshold=5, cooldown_seconds=1.0), env={})
except TrackerConfigError as e:
    assert [i.code for i in e.issues] == ['unknown_provider'], e.issues
    assert e.issues[0].provider == 'lacale'
    print('OK: factory raises unknown_provider for lacale')
else:
    raise SystemExit('FAIL: factory accepted lacale')
"
# Expected: OK: factory raises unknown_provider for lacale (exit 0)
```

**Status**: PASS (exercised 2026-08-03 — observed
`OK: factory raises unknown_provider for lacale`)

---

## ACC-05 — historic rows render (D2 regression suite)

**What**: The removed-tracker regression suite passes — obligations read-model,
delete authority veto/allow, dispatch/grab writers, cross-seed and ratio_state
rows, enum/activation/factory absence — parametrized over BOTH decommissioned
trackers (`torr9` + `lacale`). Historic DB rows with
`source_tracker="lacale"` stay readable as plain strings, no enum coercion.
**Scope**: DESIGN D2 (truthful history, NO data migration) + D9 (coverage must
not shrink silently).

```bash
pytest tests/acquire/test_removed_tracker_history.py -q
# Expected: all pass, 0 failed
```

**Status**: PASS (exercised 2026-08-03 — observed
`21 passed, 4 warnings in 1.36s`)

---

## ACC-06 — dead docs/fixtures gone

**What**: `docs/reference/lacale-api.md` and the `docs/reference/_samples/lacale/`
fixture directory no longer exist.
**Scope**: DESIGN D7 (docs purge — docs lie otherwise).

```bash
test ! -f docs/reference/lacale-api.md && test ! -d docs/reference/_samples/lacale && echo OK
# Expected: OK (exit 0)
```

**Status**: PASS (exercised 2026-08-03 — observed `OK`)

---

## ACC-07 — openapi no drift

**What**: Regenerating the OpenAPI schema and TS types from the current routes
produces zero diff against the committed `frontend/openapi.json` +
`frontend/src/api/schema.d.ts` (the D4 sample rewrite was regenerated and
committed in phase 2).
**Scope**: DESIGN D5 (any web model/docstring change ⇒ `make openapi` + commit;
CI drift guard).

```bash
make openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts
# Expected: exit 0, empty diff
```

**Status**: PASS (exercised 2026-08-03 — observed
`OpenAPI schema and TS types are up to date.`, empty diff, exit 0)

---

## ACC-08 — backend gate (make check)

**What**: The full backend gate — lint + test-with-coverage + module-size +
PRAGMA discipline + typed-api + version bump + frontend vitest/build — is
green.
**Scope**: DESIGN §4 (full `make check` green) / phase 3 full gate.

```bash
make check
# Expected: exit 0 — zero lint errors, "NNNN passed" with 0 failed / 0 ERROR
```

**Status**: PASS (exercised 2026-08-03 — exit 0; backend under coverage
`10040 passed, 3 skipped, 2 xfailed, 799 warnings in 127.02s`;
`check-module-size: 4 finding(s)` (advisory, 0.9.0 policy);
`PRAGMA discipline: OK (470 files checked, 0 violations)`;
`version bump OK: 0.76.0 -> 0.77.0`; frontend
`Tests 1136 passed (1136)` + build + PWA precache OK)

---

## ACC-09 — frontend gate

**What**: Frontend typecheck, eslint, design-system token lint, full vitest run
and production build are all green.
**Scope**: DESIGN §4 (frontend gates green) / phase 3 full gate.

```bash
cd frontend && npm run typecheck && npm run lint && npm run lint:ds && npm run test -- --run && npm run build
# Expected: all green, exit 0
```

**Status**: PASS (exercised 2026-08-03 — typecheck clean; eslint clean;
`✓ lint:tokens — no hardcoded colours outside the DS token source.`;
vitest `Test Files 116 passed (116)` / `Tests 1136 passed (1136)`;
build `✓ built` + `PWA v1.3.0 … precache 27 entries (1255.63 KiB)`)

---

## Re-exercise Log

| Date       | Phase | ACC-01 | ACC-02 | ACC-03 | ACC-04 | ACC-05 | ACC-06 | ACC-07 | ACC-08 | ACC-09 |
| ---------- | ----- | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
| 2026-08-03 | 3     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     |

Run notes (2026-08-03, phase 3 full gate):

- ACC-01..09: each command ran individually from the project root — observed
  outputs recorded verbatim in the per-criterion Status lines above. All PASS
  on first execution; no re-runs needed (the known one-off flakes —
  event_bus alloc, test_drift idempotence — did not occur).
- `make lint` exit 0: `All checks passed!` / `1252 files already formatted` /
  `Success: no issues found in 475 source files` /
  `0 finding(s): 0 error(s), 0 warning(s)`.
- `make test` exit 0 (first run):
  `10177 passed, 3 skipped, 2 xfailed, 800 warnings in 85.94s (0:01:25)` —
  0 failed, 0 ERROR. (Coverage in `make check` deselects ~137 tests vs
  `make test` — known gap, 0-failures is the gate.)
- Residual-import grep (Phase Gate rule, deleted module):
  `rg -n "tracker.lacale|tracker import lacale|LaCaleClient" -g '*.py' personalscraper/ tests/`
  → zero matches, exit 1.
- Import smoke: `python3 -c "import personalscraper"` → OK.
- `git status --short` after the gates: no stray uncommitted reformat (only
  pre-existing untracked local artifacts — `.memdb/`, `.memtrace/`,
  `docs/analysis/`, `node_modules/`, `solidify_pr.json`).
