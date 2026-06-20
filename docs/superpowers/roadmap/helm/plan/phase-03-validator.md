# Phase 3 — Validator (V1–V8) + move-resolution simulation

**Goal:** turn the runtime fail-loud semantics into **save-time errors with a field locus**
(DESIGN §5), reusing the authoritative loaders as a validation oracle, and expose the
move-resolution simulation that makes wildcard precedence legible.

**Files:** `src/kanbanmate/core/config_validate.py` (new),
`tests/core/test_config_validate.py` (new). Depends on Phase 2 (`render_pipeline`).

### 3.1 — Oracle pass + structured errors

Define the value objects (DESIGN §3.1.a), **owned by this module** (plain JSON-friendly
dataclasses): `Finding(code: str, message: str, locus: dict | None)` (`locus` = best-effort
`{transition_index, field}` or `{column_key}` or `None`), `ValidationResult(valid: bool,
errors: list[Finding], warnings: list[Finding])`, and `ResolvedTransition` (the JSON-friendly
projection used by 3.3). `validate(cfg) -> ValidationResult`. The oracle pass renders the draft
and runs `load_transitions` / `load_columns`, mapping any `ValueError` to a `Finding` (e.g.
duplicate `(from,to)`, `*→*`, empty list, bad `permission_mode` YAML type, unknown wildcard
combo).

**Acceptance:** each loader `ValueError` path produces a corresponding `Finding` with a
non-`None` locus where derivable. Tests feed malformed drafts (duplicate pair, `*→*`) and
assert the codes.

### 3.2 — Semantic checks V1–V8

Implement the DESIGN §5.2 table:

- **V1** placeholder resolution against the known set (re-verified against
  `app/actions.LaunchAction._build_context`: `code, title, branch, ticket_body, script_output,
issue_body, comments, codename, design_path, plan_paths, base_clone, dev_repo_path`); **V2**
  slash-command preservation (warn on a mistyped known command); **V3** `permission_mode` ∈
  allowed set & no `bypass` — **import** the loader's frozenset (export a public alias
  `ALLOWED_PERMISSION_MODES` from `core/transitions.py` — currently `_ALLOWED_PERMISSION_MODES`)
  rather than re-listing the five values, so the two can never drift; **V4** `profile` required
  on prompt-bearing rows AND `profile ∈ adapters.perms.PROFILES` (`docs/prepare/dev/check` — the
  four PoC profiles, phase 22; the `safe`/`trusted` naming is resolved in HEAD); **V5**
  `advance`/`on_fail` targets exist; **V6** `from`/`to` reference existing column keys or `"*"`
  (no `"*"` inside a list); **V7** wildcard-shadow **warnings**; **V8** `launch_target_columns()`
  invariant preserved — its purpose is **preventing `Merge` from ever becoming a launch target**;
  the canonical example is `Review→Merge`, a script **gate** (no prompt) so `Merge` is NOT a
  launch target. (V8 is a defense-in-depth signal; the real merge ban lives in perms `deny` +
  branch protection, NOT this validator.)

**Acceptance:** one focused test per rule (positive + negative). V3 negative includes a
`bypassPermissions` value → error, and a test asserts V3's allowed set IS the imported
`ALLOWED_PERMISSION_MODES` (drift guard). V4 negative: a prompt row with empty `profile` → error,
and a `profile` outside `perms.PROFILES` → error. V8: a config that tried to attach a prompt to
`Review→Merge` (making `Merge` a launch target) → error.

### 3.3 — Move-resolution simulation (whitelist-only scope)

`resolve(cfg, from_key, to_key) -> ResolvedTransition | None` honoring whitelist precedence
(explicit `(from,to)` > `(from,*)` > `(*,to)`; `None` = not whitelisted).

**Scope (HEAD-verified, DESIGN §5.3):** `resolve()` is **whitelist-only** — exactly
`TransitionConfig.get` semantics. It does NOT replicate `core/decide.decide()`'s **reactive
routing**, which intercepts a move INTO a reactive (Cancel) column as TEARDOWN and `Cancel→Backlog`
as RESET **before** the whitelist is consulted. So a `None` from `resolve()` means "no whitelist
row matched" — for a reactive-column edge the real daemon would still act (teardown/reset), and
the UI labels those edges as engine-handled rather than claiming a transition fires. Layering the
reactive interception in is deferred to PR 3 (when the UI hosts columns).

**Acceptance:** tests cover an explicit hit, a `(from,*)` hit shadowing a `(*,to)`, a pure
`(*,to)` hit, and a `None` (unwhitelisted) result. A test asserts `resolve` agrees with the
runtime `TransitionConfig.get` precedence for the default config across all column pairs (it does
NOT claim to agree with `decide()` on the reactive Cancel/Backlog edges).

### Phase gate

`rm -rf .mypy_cache && make check` green; per-rule tests pass; no residual imports.
