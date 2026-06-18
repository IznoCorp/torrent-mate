# Implementation Progress — helm

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Configuration interface — config core + HTTP API (PR 1) (type: minor)
**Version bump**: 0.5.1 → 0.6.0
**Branch**: `feat/helm`
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/helm/DESIGN.md
**Master plan**: docs/features/helm/plan/INDEX.md

> Scope: PR 1 only — backend-neutral config core + headless local-loopback HTTP API. No UI (PR 2),
> no board mutation (PR 3). The 3-PR arc is documented in DESIGN.md so the steps compose, but #5
> implements PR 1 only.

## Phases

| # | Phase | File | Status |
| --- | --- | --- | --- |
| 1 | Core: profiles relocation + config model | plan/phase-01-core-profiles-and-model.md | [x] |
| 2 | Serializer (render_pipeline) | plan/phase-02-serializer.md | [x] |
| 3 | Validator + resolve | plan/phase-03-validator-and-resolve.md | [x] |
| 4 | Config service (app) | plan/phase-04-config-service.md | [x] |
| 5 | HTTP API + CLI + packaging | plan/phase-05-http-cli-packaging.md | [x] |

## Review cycles

### Cycle 1

PR #33 reviewed via `/pr-review-toolkit:review-pr` (5 specialised agents: code-reviewer,
pr-test-analyzer, silent-failure-hunter, type-design-analyzer, design-conformity). Design-conformity
verdict: 9/10 CONFORM, no design contradictions. Findings filtered against DESIGN.md and the plan;
retained findings fixed on `feat/helm` (PR left OPEN — merge is human-only).

**Retained + fixed**

- **(major) `--root` silently dropped.** `kanban config serve --root X` accepted/echoed the flag but
  every endpoint called `_get_service()` with no argument → always `~/.kanban/`. Threaded the root via
  `app.state.kanban_root` (set in `cli/config.py:serve` before `uvicorn.run`, read in
  `http/config_api._get_service`). Test: `test_get_service_honors_app_state_root`.
- **(medium) `from_loaded` leaked `YAMLError`/`AttributeError`** instead of the documented `ValueError`
  (an empty/malformed/non-mapping `transitions.yml` — exactly the input helm exists to fix — would 500
  on `GET /api/config`). `core/transitions.load_transitions` has no non-dict guard (unlike
  `load_columns`). Hardened `from_loaded`: parse + `is None`/`isinstance` guard + wrap `YAMLError` as
  `ValueError`; empty doc → graceful empty draft. Tests: empty / malformed / non-mapping.
- **(medium) `get_render` + `post_resolve` unguarded** → opaque 500 traceback on a load/loader error.
  Wrapped to match `get_config` (render → 500 on load error; resolve → 422 on a loader-rejected draft).
  Tests: `test_post_resolve_invalid_draft_returns_422`.
- **(medium) `column_class` typo silently demoted reactive→inert** (no V-check, oracle accepts it).
  Added **V9** (column-class membership). Tests: invalid + clean.
- **(medium) Defaults had no sanity bound** (a `concurrency_cap`/rate of 0 stalls the pipeline; the
  published schema declares `minimum: 1`). Added **V10** (defaults sanity). Tests: both fields.
- **Test gaps** (per `pr-test-analyzer`): structural-422 contract (F1), V8 no-false-positive on a
  matching block (F2), real explicit-vs-wildcard precedence contention + honest rename (F3), `wild_from`
  tier (F4), `POST /api/config` write-to-disk side-effect (F5).
- **(minor)** V1 finding f-string rendered `{{'key'}}` → now `{{key}}`; `Finding.severity` typed
  `Literal["error", "warning"]` (hardens the save gate). DESIGN §7.1 reconciled (V7 wording; V9/V10 rows;
  V1–V10 counts).

**Ignored (conform to DESIGN — not defects)**

- `ResolvedTransition.would_launch = matched and prompt is not None` — explicitly specified in DESIGN §6
  ("an agent fires" = prompt present; script-only is a gate, not a launch).
- `save` is per-file atomic, not transactional across the two files — DESIGN §12 specifies "one file at
  a time"; validation runs first so content is valid.
- `resolve` reads `TransitionConfig` private `_explicit/_wild_from/_wild_to` to report the tier — core→core,
  tested, `noqa`-flagged; `.get()` does not expose the tier. Acceptable for PR 1 (noted for PR 3).

**Gate**: `make lint` clean (ruff + mypy, 219 files); helm suites + layering 86 passed; module-size guard
no hard-ceiling breach (`config_validate.py` 623 LOC); `import kanbanmate` + daemon-purity smoke green.
(The ~36 `tests/bin/`+`test_doctor` failures are the known env-only helper-shim cases — CI `check` green.)

### Cycle 2 (verification)

Adversarial re-review of the cycle-1 fix diff (`3df7eb4`): a correctness re-reviewer and a
design-conformity re-checker. Both verdicts: fixes **correct and complete**, design↔implementation
**coherent**, **no new critical/major/medium**. One trivial **minor** residue — the
`config_validate.py` module docstring still said "8 semantic checks (V1–V8)" — fixed in `4b02fcb`.

`make lint` clean; helm suites + layering green; CI `check` pass on both fix commits.

No critical/major/medium findings remain → review loop exits. PR #33 left OPEN for human merge.

## Next action

All phases complete — run /implement:feature-pr (push + PR + CI).
