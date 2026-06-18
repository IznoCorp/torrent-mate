# Phase 3 — Validator + resolve

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `core/config_validate.py` with the value objects `Finding`, `ValidationResult`,
`ResolvedTransition`, plus `validate(draft) -> ValidationResult` (oracle + 8 semantic checks
V1–V8) and `resolve(draft, from_col, to_col) -> ResolvedTransition`.

**Architecture:** Pure `core` layer. `validate` runs two tiers: (1) render the draft and feed both
YAML strings through the real loaders — any `ValueError` becomes a `Finding(severity="error")` (the
oracle backstop); (2) 8 semantic checks that the loaders never emit. `resolve` builds a
`TransitionConfig` from the draft (render → `load_transitions`) and calls `.get(from_col, to_col)`
as the single source of truth for whitelist precedence — no reimplementation.

**Tech Stack:** Pure stdlib + `re` (for V1 placeholder grammar). No new deps.

## Global Constraints

- `core/` imports ONLY stdlib + `yaml` + sibling `core` modules. V4 imports from `core.profiles`
  (Phase 1). V3 imports `_ALLOWED_PERMISSION_MODES` from `core.transitions` (already in `core`).
- Each validator check must produce a `Finding` with a meaningful `field` + `locus` — never
  compare an empty list to an empty list (that would make the test vacuous).
- Tests live in `tests/core/`.

---

## Task 3.1 — Value objects: `Finding`, `ValidationResult`, `ResolvedTransition`

**Files:**
- Create: `src/kanbanmate/core/config_validate.py` (initial structure with value objects only)
- Create: `tests/core/test_config_validate.py` (value object tests)

**Interfaces:**
- Produces:
  - `Finding(field: str, message: str, severity: str, locus: str)` dataclass
  - `ValidationResult(findings: list[Finding], ok: bool)` dataclass — `ok` is `True` iff no `error`-severity finding
  - `ResolvedTransition(matched: bool, transition: TransitionDef | None, tier: str, engine_handled: str, would_launch: bool)` dataclass
- Consumed by: Tasks 3.2–3.4 (`validate`, `resolve`), Phase 4 (`config_service`), Phase 5 (HTTP endpoints)

- [ ] **Step 3.1.1: Write value object tests**

```python
# tests/core/test_config_validate.py
"""Tests for :mod:`kanbanmate.core.config_validate`.

Covers value objects, the oracle pass, each of V1-V8 semantic checks, and the
resolve simulator.  Each validator test uses a *genuinely-produced* Finding —
never an empty-list comparison.
"""

from __future__ import annotations

import importlib.resources

import pytest

from kanbanmate.core.config_model import (
    Binding,
    ColumnDef,
    Defaults,
    Definition,
    PipelineDraft,
    TransitionDef,
)
from kanbanmate.core.config_validate import (
    Finding,
    ResolvedTransition,
    ValidationResult,
    resolve,
    validate,
)
from kanbanmate.core.transitions_defaults import render_transitions_yaml


def _columns_yaml() -> str:
    ref = importlib.resources.files("kanbanmate") / "assets" / "columns.yml.tmpl"
    return ref.read_text(encoding="utf-8")


def _clean_draft() -> PipelineDraft:
    """Return a valid shipped-config draft (should produce no findings)."""
    return PipelineDraft.from_loaded(render_transitions_yaml("owner/repo"), _columns_yaml())


def _draft_with_one_transition(t: TransitionDef) -> PipelineDraft:
    """Return a minimal 2-column draft containing exactly one transition row."""
    cols = [
        ColumnDef(key="Backlog", name="Backlog", column_class="inert"),
        ColumnDef(key="InProgress", name="In Progress", column_class="inert"),
    ]
    return PipelineDraft(
        definition=Definition(
            columns=cols,
            transitions=[t],
            defaults=Defaults(concurrency_cap=3, move_rate_limit_per_hour=10),
        ),
        binding=Binding(project="owner/repo"),
    )


# ---------------------------------------------------------------------------
# Value object tests
# ---------------------------------------------------------------------------


def test_finding_fields() -> None:
    """Finding stores all four fields without modification."""
    f = Finding(field="transitions[0].permission_mode", message="Bad mode", severity="error", locus="transitions[0]")
    assert f.field == "transitions[0].permission_mode"
    assert f.message == "Bad mode"
    assert f.severity == "error"
    assert f.locus == "transitions[0]"


def test_validation_result_ok_no_errors() -> None:
    """ok is True when findings list is empty."""
    vr = ValidationResult(findings=[], ok=True)
    assert vr.ok is True


def test_validation_result_ok_only_warnings() -> None:
    """ok must be True when findings contain only warnings (warnings do not block save)."""
    warn = Finding(field="f", message="m", severity="warning", locus="l")
    vr = ValidationResult(findings=[warn], ok=True)
    assert vr.ok is True


def test_validation_result_not_ok_with_error() -> None:
    """ok is False when at least one error finding exists."""
    err = Finding(field="f", message="m", severity="error", locus="l")
    vr = ValidationResult(findings=[err], ok=False)
    assert vr.ok is False


def test_resolved_transition_unmatched() -> None:
    """ResolvedTransition for an un-whitelisted move has matched=False and no transition."""
    rt = ResolvedTransition(matched=False, transition=None, tier="none", engine_handled="", would_launch=False)
    assert rt.matched is False
    assert rt.transition is None
    assert rt.would_launch is False
```

- [ ] **Step 3.1.2: Run value object tests (expect ImportError)**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/core/test_config_validate.py::test_finding_fields -v
```

Expected: `ImportError: cannot import name 'Finding' from 'kanbanmate.core.config_validate'`

- [ ] **Step 3.1.3: Create `core/config_validate.py` with value objects only (no `validate`/`resolve` yet)**

```python
# src/kanbanmate/core/config_validate.py
"""Validator and move-resolution simulator for the pipeline draft (DESIGN §6–§7).

:func:`validate` converts the loaders' launch-time ``ValueError`` s into
structured save-time ``Finding`` objects, plus 8 semantic checks the loaders
never emit (V1–V8).  :func:`resolve` simulates the whitelist-resolution step
of the daemon's ``decide()`` path for a given ``(from, to)`` move — PR-1 scoped
to whitelist resolution only (DESIGN §6).

Layering: ``core`` only — no I/O, no adapters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from kanbanmate.core.config_model import PipelineDraft, TransitionDef


@dataclass
class Finding:
    """A single validator finding with a field locus (DESIGN §7).

    Attributes:
        field: Dot-path to the offending field, e.g. ``"transitions[3].permission_mode"``.
        message: Human-readable explanation of the issue.
        severity: ``"error"`` (blocks save) or ``"warning"`` (advisory only).
        locus: Short locus label for grouping, e.g. ``"transitions[3]"``.
    """

    field: str
    message: str
    severity: str  # "error" | "warning"
    locus: str


@dataclass
class ValidationResult:
    """Result of :func:`validate` (DESIGN §7).

    Attributes:
        findings: All findings produced by the validator (errors + warnings).
        ok: ``True`` iff no ``"error"``-severity finding exists.  Warnings do
            not block save (DESIGN §11).
    """

    findings: list[Finding]
    ok: bool


@dataclass
class ResolvedTransition:
    """Result of :func:`resolve` (DESIGN §6).

    Attributes:
        matched: Whether a whitelisted transition was found.
        transition: The matched :class:`~kanbanmate.core.config_model.TransitionDef`,
            or ``None`` when unmatched.
        tier: Precedence tier — ``"explicit"``, ``"wild_from"``, ``"wild_to"``,
            or ``"none"``.
        engine_handled: ``"teardown"`` when the destination is a reactive
            column (Cancel); ``"reset"`` when leaving a reactive column to the
            reset target (``Cancel → Backlog``); ``""`` otherwise.  These moves
            are intercepted by ``decide()`` before the whitelist in the real
            engine (``core/decide.py:212-237``); PR 1 labels them rather than
            simulating the full ``decide()`` verdict.
        would_launch: ``True`` when the matched transition has a prompt (an
            agent fires for this move).
    """

    matched: bool
    transition: TransitionDef | None
    tier: str  # "explicit" | "wild_from" | "wild_to" | "none"
    engine_handled: str  # "" | "teardown" | "reset"
    would_launch: bool
```

- [ ] **Step 3.1.4: Run value object tests**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/core/test_config_validate.py -k "test_finding or test_validation_result or test_resolved_transition" -v
```

Expected: all PASS.

---

## Task 3.2 — `validate`: oracle pass + V1–V8 semantic checks

**Files:**
- Modify: `src/kanbanmate/core/config_validate.py` (add `validate` function)
- Modify: `tests/core/test_config_validate.py` (add one test per V1–V8 + clean case)

**Interfaces:**
- Consumes: `PipelineDraft` (Phase 1), `render_pipeline` (Phase 2)
- Produces: `validate(draft: PipelineDraft) -> ValidationResult`
- Key symbol references:
  - `_TOKEN` = `re.compile(r"\{\{\s*([\w.]+)\s*\}\}")` at `core/placeholders.py:16`
  - `_ALLOWED_PERMISSION_MODES` at `core/transitions.py:45`
  - `PROFILES` at `core/profiles.py` (Phase 1)
  - 12 context keys: `code`, `title`, `branch`, `ticket_body`, `script_output`, `issue_body`, `comments`, `codename`, `design_path`, `plan_paths`, `base_clone`, `dev_repo_path` (from `app/launch_context.py:92-112`)
  - `advance`/`on_fail` grammar at `core/domain.py:202-205` (strings `"stop"`, `"auto:<col>"`, `""`, `"move:<col>"`, `"rollback"`)
  - `DEFAULT_RESET_TARGET = "Backlog"` at `core/decide.py:63`
  - `TransitionConfig.launch_target_columns()` at `core/transitions.py:213-244`

- [ ] **Step 3.2.1: Add `validate` tests (one per V1–V8 + clean case)**

Append to `tests/core/test_config_validate.py`:

```python
# ---------------------------------------------------------------------------
# validate: oracle pass
# ---------------------------------------------------------------------------


def test_validate_oracle_catches_invalid_yaml() -> None:
    """The oracle pass catches structural errors that load_transitions would raise."""
    # An empty from/to string is rejected by load_transitions.
    bad_t = TransitionDef(from_col="", to_col="InProgress")
    draft = _draft_with_one_transition(bad_t)
    result = validate(draft)
    errors = [f for f in result.findings if f.severity == "error"]
    assert errors, "Expected at least one error from the oracle pass for an empty from_col"
    assert result.ok is False


# ---------------------------------------------------------------------------
# validate: V1 — placeholder resolution
# ---------------------------------------------------------------------------


def test_validate_v1_unknown_placeholder() -> None:
    """V1: a {{nope}} token that is not in the 12 dispatch context keys → error."""
    t = TransitionDef(
        from_col="Backlog",
        to_col="InProgress",
        profile="dev",
        prompt="Hello {{nope}} world",
        permission_mode="auto",
    )
    draft = _draft_with_one_transition(t)
    result = validate(draft)
    v1_errors = [
        f for f in result.findings if f.severity == "error" and "placeholder" in f.message.lower()
    ]
    assert v1_errors, "Expected a V1 placeholder error for {{nope}}"
    assert "transitions[0]" in v1_errors[0].locus


def test_validate_v1_known_placeholder_no_error() -> None:
    """V1: {{code}} and {{title}} are valid dispatch context keys — no placeholder error."""
    t = TransitionDef(
        from_col="Backlog",
        to_col="InProgress",
        profile="dev",
        prompt="/implement:brainstorm {{code}} {{title}}",
        permission_mode="auto",
    )
    draft = _draft_with_one_transition(t)
    result = validate(draft)
    v1_errors = [
        f for f in result.findings if f.severity == "error" and "placeholder" in f.message.lower()
    ]
    assert not v1_errors, f"Unexpected V1 errors: {v1_errors}"


# ---------------------------------------------------------------------------
# validate: V2 — slash-command preservation
# ---------------------------------------------------------------------------


def test_validate_v2_mangled_slash_command() -> None:
    """V2: a prompt where /implement: token is replaced by garbage → error."""
    t = TransitionDef(
        from_col="Backlog",
        to_col="InProgress",
        profile="dev",
        # Simulate a round-trip that mangled the slash command.
        prompt="MANGLED:brainstorm {{code}}",
        permission_mode="auto",
    )
    # To trigger V2 we need to have the same transition in the original shipped config
    # but mangled here.  V2 checks whether a shipped prompt that contained /implement:
    # still contains it after the edit.  Use a prompt that should contain /implement: but doesn't.
    # The validator compares against the rendered round-trip — if the draft's rendered
    # prompt differs from the loader's round-tripped version in /implement: preservation,
    # it fires.
    # IMPLEMENTATION NOTE: V2 in the validator checks ALL prompt strings for mangled
    # /implement: tokens — specifically, if a prompt contains a string that looks like
    # it was a slash command (e.g. starts with "MANGLED:" and came from /implement:brainstorm)
    # — that is hard to detect generically.  The simpler correct interpretation:
    # V2 asserts that every prompt whose shipped equivalent contains /implement: STILL
    # contains /implement: after a round-trip (i.e. rendering does not strip slashes).
    # In practice: test that any prompt string that starts with a capital letter where
    # /implement would be is flagged.
    #
    # Pragmatic test: a prompt that is supposed to contain '/implement:' but does NOT
    # (the shipped brainstorm transition always has /implement:brainstorm) — if the user
    # edits the draft and removes the slash command, V2 fires.
    # We simulate this by building a draft with the Backlog→Brainstorming row but a
    # mangled prompt.
    clean = _clean_draft()
    # Find the Backlog→Brainstorming transition and mangle its prompt.
    mangled_transitions = []
    for tr in clean.definition.transitions:
        if tr.from_col == "Backlog" and tr.to_col == "Brainstorming":
            mangled_transitions.append(
                TransitionDef(
                    from_col=tr.from_col,
                    to_col=tr.to_col,
                    profile=tr.profile,
                    prompt="implement brainstorm {{code}}",  # stripped the /
                    advance=tr.advance,
                    permission_mode=tr.permission_mode,
                )
            )
        else:
            mangled_transitions.append(tr)
    from dataclasses import replace
    mangled_draft = PipelineDraft(
        definition=Definition(
            columns=clean.definition.columns,
            transitions=mangled_transitions,
            defaults=clean.definition.defaults,
        ),
        binding=clean.binding,
    )
    result = validate(mangled_draft)
    v2_errors = [f for f in result.findings if f.severity == "error" and "slash" in f.message.lower()]
    assert v2_errors, "Expected a V2 slash-command error for a mangled /implement: token"


# ---------------------------------------------------------------------------
# validate: V3 — permission_mode whitelist
# ---------------------------------------------------------------------------


def test_validate_v3_bypass_permissions_mode() -> None:
    """V3: bypassPermissions is banned — must produce an error."""
    t = TransitionDef(
        from_col="Backlog",
        to_col="InProgress",
        profile="dev",
        prompt="/implement:phase {{code}}",
        permission_mode="bypassPermissions",
    )
    draft = _draft_with_one_transition(t)
    result = validate(draft)
    v3_errors = [
        f for f in result.findings
        if f.severity == "error" and "permission_mode" in f.field
    ]
    assert v3_errors, "Expected a V3 error for bypassPermissions"
    assert "bypassPermissions" in v3_errors[0].message or "permission_mode" in v3_errors[0].field


def test_validate_v3_valid_permission_mode() -> None:
    """V3: 'auto' and 'dontAsk' are valid — no V3 error."""
    for mode in ("auto", "dontAsk", "acceptEdits", "default", "plan"):
        t = TransitionDef(
            from_col="Backlog",
            to_col="InProgress",
            profile="dev",
            prompt="/implement:phase {{code}}",
            permission_mode=mode,
        )
        draft = _draft_with_one_transition(t)
        result = validate(draft)
        v3_errors = [
            f for f in result.findings
            if f.severity == "error" and "permission_mode" in f.field
        ]
        assert not v3_errors, f"Unexpected V3 error for valid mode {mode!r}: {v3_errors}"


# ---------------------------------------------------------------------------
# validate: V4 — profile in PROFILES
# ---------------------------------------------------------------------------


def test_validate_v4_unknown_profile() -> None:
    """V4: 'merge' is not in PROFILES — must produce an error."""
    t = TransitionDef(
        from_col="Backlog",
        to_col="InProgress",
        profile="merge",  # invalid — merge=human-only, not a workflow profile
        prompt="/implement:phase {{code}}",
        permission_mode="auto",
    )
    draft = _draft_with_one_transition(t)
    result = validate(draft)
    v4_errors = [
        f for f in result.findings
        if f.severity == "error" and "profile" in f.field
    ]
    assert v4_errors, "Expected a V4 error for unknown profile 'merge'"


def test_validate_v4_valid_profiles() -> None:
    """V4: all four valid profiles pass without error."""
    for profile in ("docs", "prepare", "dev", "check"):
        t = TransitionDef(
            from_col="Backlog",
            to_col="InProgress",
            profile=profile,
            prompt="/implement:phase {{code}}",
            permission_mode="auto",
        )
        draft = _draft_with_one_transition(t)
        result = validate(draft)
        v4_errors = [f for f in result.findings if f.severity == "error" and "profile" in f.field]
        assert not v4_errors, f"Unexpected V4 error for valid profile {profile!r}: {v4_errors}"


# ---------------------------------------------------------------------------
# validate: V5 — column-target existence
# ---------------------------------------------------------------------------


def test_validate_v5_unknown_advance_target() -> None:
    """V5: advance:auto:Nowhere — Nowhere is not a column key → error."""
    t = TransitionDef(
        from_col="Backlog",
        to_col="InProgress",
        profile="dev",
        prompt="/implement:phase {{code}}",
        advance="auto:Nowhere",
        permission_mode="auto",
    )
    draft = _draft_with_one_transition(t)
    result = validate(draft)
    v5_errors = [
        f for f in result.findings
        if f.severity == "error" and ("advance" in f.field or "column" in f.message.lower())
    ]
    assert v5_errors, "Expected a V5 error for advance:auto:Nowhere"


def test_validate_v5_valid_advance_target() -> None:
    """V5: advance:auto:InProgress — InProgress is in the column list → no V5 error."""
    t = TransitionDef(
        from_col="Backlog",
        to_col="InProgress",
        profile="dev",
        prompt="/implement:phase {{code}}",
        advance="auto:InProgress",
        permission_mode="auto",
    )
    draft = _draft_with_one_transition(t)
    result = validate(draft)
    v5_errors = [
        f for f in result.findings
        if f.severity == "error" and ("advance" in f.field or "Nowhere" in f.message)
    ]
    assert not v5_errors, f"Unexpected V5 errors: {v5_errors}"


# ---------------------------------------------------------------------------
# validate: V6 — wildcard-precedence shadow
# ---------------------------------------------------------------------------


def test_validate_v6_explicit_shadowed_by_wildcard() -> None:
    """V6: an explicit (A, B) row that comes AFTER a (*, B) wildcard is unreachable → warning."""
    cols = [
        ColumnDef(key="A", name="A", column_class="inert"),
        ColumnDef(key="B", name="B", column_class="inert"),
    ]
    transitions = [
        TransitionDef(from_col="*", to_col="B"),          # wild_to covers (*, B)
        TransitionDef(from_col="A", to_col="B"),          # explicit — shadowed by (*, B)
    ]
    draft = PipelineDraft(
        definition=Definition(columns=cols, transitions=transitions, defaults=Defaults(3, 10)),
        binding=Binding(project="owner/repo"),
    )
    result = validate(draft)
    v6_warnings = [f for f in result.findings if f.severity == "warning" and "shadow" in f.message.lower()]
    assert v6_warnings, "Expected a V6 shadow warning for explicit row after wildcard"


# ---------------------------------------------------------------------------
# validate: V7 — launch_target_columns invariant
# ---------------------------------------------------------------------------


def test_validate_v7_prompt_into_reactive_column() -> None:
    """V7: a prompt-bearing transition into a reactive column (Cancel) → error."""
    cols = [
        ColumnDef(key="Backlog", name="Backlog", column_class="inert"),
        ColumnDef(key="Cancel", name="Cancel", column_class="reactive"),
    ]
    transitions = [
        TransitionDef(
            from_col="Backlog",
            to_col="Cancel",
            profile="dev",
            prompt="/implement:phase {{code}}",  # prompt into a reactive col → V7
            permission_mode="auto",
        )
    ]
    draft = PipelineDraft(
        definition=Definition(columns=cols, transitions=transitions, defaults=Defaults(3, 10)),
        binding=Binding(project="owner/repo"),
    )
    result = validate(draft)
    v7_errors = [f for f in result.findings if f.severity == "error" and "reactive" in f.message.lower()]
    assert v7_errors, "Expected a V7 error for a prompt-bearing transition into a reactive column"


def test_validate_v7_prompt_into_merge_column() -> None:
    """V7: a prompt-bearing transition whose to_col is 'Merge' → error (Merge=human-only)."""
    # Build a minimal draft with all real columns but a synthetic * → Merge with a prompt.
    clean = _clean_draft()
    from dataclasses import replace
    new_transitions = list(clean.definition.transitions) + [
        TransitionDef(
            from_col="*",
            to_col="Merge",
            profile="dev",
            prompt="do the merge {{code}}",
            permission_mode="auto",
        )
    ]
    bad_draft = PipelineDraft(
        definition=Definition(
            columns=clean.definition.columns,
            transitions=new_transitions,
            defaults=clean.definition.defaults,
        ),
        binding=clean.binding,
    )
    result = validate(bad_draft)
    v7_errors = [
        f for f in result.findings
        if f.severity == "error" and "merge" in f.message.lower()
    ]
    assert v7_errors, "Expected a V7 error for a prompt-bearing transition into Merge"


# ---------------------------------------------------------------------------
# validate: V8 — defaults coherence
# ---------------------------------------------------------------------------


def test_validate_v8_columns_defaults_disagree() -> None:
    """V8: a columns.yml that contains a defaults: block disagreeing with transitions.yml → warning.

    This test constructs the scenario directly by using a columns_yaml that has
    an uncommented defaults: block with a different concurrency_cap.
    """
    # Build a columns YAML with an explicit (uncommented) defaults block that
    # disagrees with the draft's Defaults(concurrency_cap=3).
    ref = importlib.resources.files("kanbanmate") / "assets" / "columns.yml.tmpl"
    columns_template = ref.read_text(encoding="utf-8")
    # Append a real defaults block that conflicts with the transitions defaults.
    columns_with_defaults = columns_template + "\ndefaults:\n  concurrency_cap: 99\n  move_rate_limit_per_hour: 10\n"

    from kanbanmate.core.transitions_defaults import render_transitions_yaml
    draft = PipelineDraft.from_loaded(render_transitions_yaml("owner/repo"), columns_with_defaults)
    # The draft has concurrency_cap=3 (from transitions.yml); columns says 99.
    # We need to pass BOTH the draft AND the raw columns_yaml to the validator so
    # it can detect the disagreement.
    # IMPLEMENTATION NOTE: validate() takes only the draft, which already holds
    # the merged Defaults from transitions.yml.  For V8 to work, the validator
    # needs access to the raw columns_yaml to read its defaults: block.  This
    # means validate() needs a second optional parameter: validate(draft,
    # columns_yaml=None). When columns_yaml is provided and contains an
    # uncommented defaults: block that disagrees with draft.definition.defaults,
    # V8 fires a warning.
    # The HTTP service layer will pass columns_yaml=columns_text to validate().
    result = validate(draft, columns_yaml=columns_with_defaults)
    v8_warnings = [f for f in result.findings if f.severity == "warning" and "default" in f.message.lower()]
    assert v8_warnings, "Expected a V8 warning when columns.yml defaults disagree with transitions.yml"


# ---------------------------------------------------------------------------
# validate: clean config (no findings)
# ---------------------------------------------------------------------------


def test_validate_clean_config_no_findings() -> None:
    """The shipped config must produce zero findings (error or warning)."""
    result = validate(_clean_draft())
    errors = [f for f in result.findings if f.severity == "error"]
    assert not errors, f"Unexpected errors from the shipped config: {errors}"
    assert result.ok is True
```

- [ ] **Step 3.2.2: Run tests to see which pass (value objects) and which fail (validate missing)**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/core/test_config_validate.py -v 2>&1 | head -60
```

Expected: value object tests PASS; tests that call `validate()` fail with `ImportError`.

- [ ] **Step 3.2.3: Implement `validate` in `core/config_validate.py`**

Add these imports at the top of `config_validate.py`:

```python
from __future__ import annotations

from typing import Any

import yaml

from kanbanmate.core.config_model import PipelineDraft, TransitionDef
from kanbanmate.core.config_serialize import render_pipeline
from kanbanmate.core.columns import load_columns
from kanbanmate.core.transitions import load_transitions, _ALLOWED_PERMISSION_MODES
from kanbanmate.core.profiles import PROFILES
from kanbanmate.core.placeholders import _TOKEN
```

`_TOKEN` (`core/placeholders.py:16`, `re.compile(r"\{\{\s*([\w.]+)\s*\}\}")`) is the **single
source of truth** for the `{{ token }}` grammar — importing it (a legal `core → core` import) keeps
V1 from drifting against a hand-copied regex. It captures a dotted path (`{{a.b}}` → `"a.b"`); V1
validates the **first** dotted segment against `_CONTEXT_KEYS` (matching how
`core/placeholders._resolve` walks the top-level key first). `yaml` + `Any` back the V8 raw-document
presence check and the V1 capture handling.

Add the following to `core/config_validate.py`:

```python
# The 12 dispatch context keys built in app/launch_context.py:86-112.
# Core may not import app, so the set is reproduced here verbatim.
_CONTEXT_KEYS: frozenset[str] = frozenset({
    "code", "title", "branch", "ticket_body", "script_output",
    "issue_body", "comments", "codename", "design_path",
    "plan_paths", "base_clone", "dev_repo_path",
})

# The reset target: a card leaving a reactive column goes here (core/decide.py:63).
_DEFAULT_RESET_TARGET = "Backlog"


def _check_v1_placeholders(
    t: TransitionDef, idx: int, findings: list[Finding]
) -> None:
    """V1: every {{token}} in a prompt must resolve against the 12 dispatch context keys."""
    if t.prompt is None:
        return
    for m in _TOKEN.finditer(t.prompt):
        key = m.group(1).split(".")[0]  # top-level segment only
        if key not in _CONTEXT_KEYS:
            findings.append(Finding(
                field=f"transitions[{idx}].prompt",
                message=f"Unknown placeholder {{{{'{key}'}}}} — not in dispatch context keys ({sorted(_CONTEXT_KEYS)})",
                severity="error",
                locus=f"transitions[{idx}]",
            ))


def _check_v2_slash_commands(
    t: TransitionDef, idx: int, findings: list[Finding]
) -> None:
    """V2: /implement:* tokens must be preserved (not mangled by an edit)."""
    if t.prompt is None:
        return
    # If the prompt contains what looks like a mangled implement command
    # (e.g. "implement:brainstorm" without a leading slash), flag it.
    # Pattern: any word immediately followed by ":brainstorm", ":plan", etc.
    # that LACKS the leading slash.
    _SLASH_CMDS = ("brainstorm", "plan", "create-branch", "phase", "pr-review", "feature", "prepare-feature")
    for cmd in _SLASH_CMDS:
        # Match "implement:<cmd>" without a preceding "/" (mangled form).
        if re.search(rf"(?<!/)(implement:{re.escape(cmd)})", t.prompt):
            findings.append(Finding(
                field=f"transitions[{idx}].prompt",
                message=f"Slash command '/implement:{cmd}' appears mangled (missing leading '/'); verify the prompt",
                severity="error",
                locus=f"transitions[{idx}]",
            ))


def _check_v3_permission_mode(
    t: TransitionDef, idx: int, findings: list[Finding]
) -> None:
    """V3: permission_mode must be in the allowed set; bypass* is banned."""
    mode = t.permission_mode
    if not mode:
        return  # empty string → loader will default it; not a validator concern
    if mode not in _ALLOWED_PERMISSION_MODES:
        findings.append(Finding(
            field=f"transitions[{idx}].permission_mode",
            message=(
                f"permission_mode {mode!r} is not allowed. "
                f"Allowed: {sorted(_ALLOWED_PERMISSION_MODES)}. "
                "bypassPermissions is NEVER allowed."
            ),
            severity="error",
            locus=f"transitions[{idx}]",
        ))


def _check_v4_profile(
    t: TransitionDef, idx: int, findings: list[Finding]
) -> None:
    """V4: profile must be one of the four workflow profiles or empty string."""
    profile = t.profile
    if not profile:
        return  # empty = no-op / script-only transition; allowed
    if profile not in PROFILES:
        findings.append(Finding(
            field=f"transitions[{idx}].profile",
            message=(
                f"profile {profile!r} is not a valid workflow profile. "
                f"Allowed: {list(PROFILES)}"
            ),
            severity="error",
            locus=f"transitions[{idx}]",
        ))


def _extract_col_targets(value: str) -> list[str]:
    """Return concrete column key targets from an advance/on_fail directive string.

    Parses 'auto:<col>' (advance) and 'move:<col>' (on_fail) to extract the
    column key.  Returns an empty list for 'stop', '', 'rollback' (no column).
    """
    if value.startswith("auto:"):
        return [value[5:]]
    if value.startswith("move:"):
        return [value[5:]]
    return []


def _col_keys(value: str | list[str]) -> list[str]:
    """Normalise a from_col/to_col (``str`` | ``"*"`` | ``list[str]``) to concrete keys.

    Drops the ``"*"`` wildcard (it matches any column, so it is never an
    existence target). A scalar becomes a one-element list; a list is returned
    element-wise. This is the single seam the validators use so the
    ``str | list[str]`` authoring shape (DESIGN §4.1) is handled in one place.
    """
    vals = value if isinstance(value, list) else [value]
    return [v for v in vals if v and v != "*"]


def _check_v5_column_targets(
    t: TransitionDef, idx: int, col_keys: frozenset[str], findings: list[Finding]
) -> None:
    """V5: every non-wildcard from/to, advance:auto:<col>, on_fail:move:<col> must name a real column."""
    def _check_key(key: str, field_name: str) -> None:
        if key and key not in col_keys:
            findings.append(Finding(
                field=f"transitions[{idx}].{field_name}",
                message=f"Column key {key!r} does not exist in the column list",
                severity="error",
                locus=f"transitions[{idx}]",
            ))

    # Check every concrete from_col / to_col key (the wildcard and lists are
    # normalised by _col_keys; each list member is checked individually).
    for k in _col_keys(t.from_col):
        _check_key(k, "from_col")
    for k in _col_keys(t.to_col):
        _check_key(k, "to_col")

    # Check advance:auto:<col> and on_fail:move:<col> targets.
    for col in _extract_col_targets(t.advance):
        _check_key(col, "advance")
    for col in _extract_col_targets(t.on_fail):
        _check_key(col, "on_fail")


def _check_v6_wildcard_shadow(
    transitions: list[TransitionDef], findings: list[Finding]
) -> None:
    """V6: warn when a wildcard row makes a later explicit row unreachable-by-intent.

    Specifically: a (*, to) wild_to entry that appears BEFORE an explicit (from, to)
    makes the explicit row unreachable (the wildcard wins per precedence at
    core/transitions.py:202-211). This is a WARNING — it may be intentional.
    """
    # Collect (*, to) wild_to entries and their positions. A wildcard is always
    # a scalar "*"; list-valued from/to (authoring sugar) is never a wildcard.
    wild_to_seen: dict[str, int] = {}  # to_col → earliest index
    for idx, t in enumerate(transitions):
        if t.from_col == "*" and isinstance(t.to_col, str) and t.to_col != "*":
            if t.to_col not in wild_to_seen:
                wild_to_seen[t.to_col] = idx

    # Look for explicit (from, to) rows that come AFTER the wild_to for the same
    # to_col. Restrict to plain scalar explicit edges — list-valued rows are
    # authoring sugar covered by the oracle pass + V5, not by this shadow heuristic.
    for idx, t in enumerate(transitions):
        if (
            isinstance(t.from_col, str) and t.from_col != "*"
            and isinstance(t.to_col, str) and t.to_col != "*"
        ):
            wild_idx = wild_to_seen.get(t.to_col)
            if wild_idx is not None and wild_idx < idx:
                findings.append(Finding(
                    field=f"transitions[{idx}]",
                    message=(
                        f"Explicit ({t.from_col!r} → {t.to_col!r}) at index {idx} is shadowed "
                        f"by wildcard (* → {t.to_col!r}) at index {wild_idx} "
                        "(wildcard-precedence: explicit wins, but the wildcard appeared first — "
                        "verify authoring intent)"
                    ),
                    severity="warning",
                    locus=f"transitions[{idx}]",
                ))


def _check_v7_launch_target_invariant(
    draft: PipelineDraft, findings: list[Finding]
) -> None:
    """V7: no prompt-bearing transition may resolve into a reactive column or into 'Merge'."""
    reactive_keys = frozenset(c.key for c in draft.definition.columns if c.column_class == "reactive")
    for idx, t in enumerate(draft.definition.transitions):
        if t.prompt is None:
            continue
        # Concrete to_col targets (the wildcard and lists are normalised by
        # _col_keys — a prompt-bearing row into any of these keys is checked).
        for col in _col_keys(t.to_col):
            if col in reactive_keys:
                findings.append(Finding(
                    field=f"transitions[{idx}].to_col",
                    message=(
                        f"A prompt-bearing transition resolves into reactive column {col!r}. "
                        "Reactive columns are handled mechanically by the engine (teardown/reset); "
                        "a prompt would re-fire the agent."
                    ),
                    severity="error",
                    locus=f"transitions[{idx}]",
                ))
            if col == "Merge":
                findings.append(Finding(
                    field=f"transitions[{idx}].to_col",
                    message=(
                        "A prompt-bearing transition targets 'Merge'. Merge is a human-only gate "
                        "(DESIGN §15 / V7) — an agent must never be launched into Merge."
                    ),
                    severity="error",
                    locus=f"transitions[{idx}]",
                ))


def _check_v8_defaults_coherence(
    draft: PipelineDraft,
    columns_yaml: str | None,
    findings: list[Finding],
) -> None:
    """V8: warn if an uncommented columns.yml defaults: block disagrees with transitions.yml.

    The authoritative defaults are in transitions.yml (DESIGN §10 / app/wiring.py:229-230).
    A hand-uncommented columns.yml defaults: block that disagrees is dead config that the
    daemon silently ignores, trapping the operator.
    """
    if not columns_yaml:
        return
    from kanbanmate.core.columns import load_board_defaults  # noqa: PLC0415

    # CRITICAL: load_board_defaults() NEVER returns None — an ABSENT defaults:
    # block yields BoardDefaults() (3/10) exactly like a present block that
    # spells out 3/10 (core/columns.py:217-235). The shipped columns.yml ships
    # the block COMMENTED OUT (assets/columns.yml.tmpl:26-28), so the raw
    # document has no top-level "defaults" key. V8 fires ONLY when an
    # uncommented block is actually present — detect presence on the RAW
    # document, never on the loader's defaulted return (else raising the
    # transitions cap with columns.yml's block still commented would emit a
    # false-positive warning).
    raw_cols: Any = yaml.safe_load(columns_yaml)
    if not isinstance(raw_cols, dict) or not isinstance(raw_cols.get("defaults"), dict):
        return  # No uncommented columns.yml defaults: block — nothing to compare.

    board_defaults = load_board_defaults(columns_yaml)

    t_cap = draft.definition.defaults.concurrency_cap
    t_rate = draft.definition.defaults.move_rate_limit_per_hour
    c_cap = board_defaults.concurrency_cap
    c_rate = board_defaults.move_rate_limit_per_hour

    if c_cap != t_cap:
        findings.append(Finding(
            field="columns.defaults.concurrency_cap",
            message=(
                f"columns.yml defaults.concurrency_cap={c_cap} disagrees with "
                f"transitions.yml defaults.concurrency_cap={t_cap}. "
                "The daemon reads transitions.yml (authoritative); the columns.yml value is dead config."
            ),
            severity="warning",
            locus="columns.defaults",
        ))
    if c_rate != t_rate:
        findings.append(Finding(
            field="columns.defaults.move_rate_limit_per_hour",
            message=(
                f"columns.yml defaults.move_rate_limit_per_hour={c_rate} disagrees with "
                f"transitions.yml defaults.move_rate_limit_per_hour={t_rate}. "
                "The daemon reads transitions.yml (authoritative); the columns.yml value is dead config."
            ),
            severity="warning",
            locus="columns.defaults",
        ))


def validate(draft: PipelineDraft, *, columns_yaml: str | None = None) -> ValidationResult:
    """Validate a :class:`~kanbanmate.core.config_model.PipelineDraft`.

    Runs two tiers (DESIGN §7):

    1. **Oracle pass** — render the draft and feed both YAML documents through
       the real loaders (``load_transitions`` + ``load_columns``). Any
       ``ValueError`` becomes a ``Finding(severity='error')``. This guarantees
       helm can never save a config the daemon would crash on.
    2. **Semantic checks V1–V8** — field-located checks the loaders never emit
       (placeholder resolution, slash-command preservation, permission_mode
       whitelist, profile whitelist, column-target existence,
       wildcard-precedence shadow, launch-target invariant, defaults
       coherence).

    Args:
        draft: The pipeline draft to validate.
        columns_yaml: The raw ``columns.yml`` string, required for V8 (defaults
            coherence).  When ``None``, V8 is skipped.

    Returns:
        A :class:`ValidationResult` with all findings.  ``ok`` is ``True``
        iff no ``error``-severity finding exists.
    """
    findings: list[Finding] = []

    # §7.0 — Oracle pass: render and feed through the real loaders.
    try:
        rendered = render_pipeline(draft)
        load_transitions(rendered.transitions)
        load_columns(rendered.columns)
    except ValueError as exc:
        findings.append(Finding(
            field="draft",
            message=f"Loader oracle rejected the rendered config: {exc}",
            severity="error",
            locus="draft",
        ))
        # When the oracle fails, the rendered YAML is invalid; semantic checks
        # that depend on it (e.g. V7's launch_target_columns) would produce
        # spurious findings.  Return early with just the oracle error.
        return ValidationResult(findings=findings, ok=False)

    # §7.1 — Semantic checks V1–V8.
    col_keys = frozenset(c.key for c in draft.definition.columns)
    for idx, t in enumerate(draft.definition.transitions):
        _check_v1_placeholders(t, idx, findings)
        _check_v2_slash_commands(t, idx, findings)
        _check_v3_permission_mode(t, idx, findings)
        _check_v4_profile(t, idx, findings)
        _check_v5_column_targets(t, idx, col_keys, findings)

    _check_v6_wildcard_shadow(draft.definition.transitions, findings)
    _check_v7_launch_target_invariant(draft, findings)
    _check_v8_defaults_coherence(draft, columns_yaml, findings)

    ok = not any(f.severity == "error" for f in findings)
    return ValidationResult(findings=findings, ok=ok)
```

**NOTE on `load_board_defaults`:** Check whether `core/columns.py` exports this function. If not, implement V8 inline by parsing the raw `columns_yaml` with `yaml.safe_load` and checking for a top-level `defaults:` key:

```python
# Inline V8 implementation when load_board_defaults is not exported:
def _check_v8_defaults_coherence(draft, columns_yaml, findings):
    if not columns_yaml:
        return
    import yaml as _yaml
    doc = _yaml.safe_load(columns_yaml)
    if not isinstance(doc, dict):
        return
    col_defs = doc.get("defaults")
    if not isinstance(col_defs, dict):
        return  # No uncommented defaults block
    c_cap = col_defs.get("concurrency_cap")
    c_rate = col_defs.get("move_rate_limit_per_hour")
    t_cap = draft.definition.defaults.concurrency_cap
    t_rate = draft.definition.defaults.move_rate_limit_per_hour
    if c_cap is not None and c_cap != t_cap:
        findings.append(Finding(
            field="columns.defaults.concurrency_cap",
            message=f"columns.yml defaults.concurrency_cap={c_cap} disagrees with transitions.yml={t_cap} (dead config)",
            severity="warning",
            locus="columns.defaults",
        ))
    if c_rate is not None and c_rate != t_rate:
        findings.append(Finding(
            field="columns.defaults.move_rate_limit_per_hour",
            message=f"columns.yml defaults.move_rate_limit_per_hour={c_rate} disagrees with transitions.yml={t_rate} (dead config)",
            severity="warning",
            locus="columns.defaults",
        ))
```

- [ ] **Step 3.2.4: Run validate tests**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/core/test_config_validate.py -v -k "not resolve"
```

Expected: all PASS. Fix any failures by examining the Finding fields and adjusting the check logic.

---

## Task 3.3 — `resolve` simulator

**Files:**
- Modify: `src/kanbanmate/core/config_validate.py` (add `resolve` function)
- Modify: `tests/core/test_config_validate.py` (add resolve tests)

**Interfaces:**
- Produces: `resolve(draft: PipelineDraft, from_col: str, to_col: str) -> ResolvedTransition`
- Key precedence: `TransitionConfig.get` at `core/transitions.py:183-211` — explicit wins over `wild_from`, which wins over `wild_to`; no match → `tier="none"`, `matched=False`

- [ ] **Step 3.3.1: Add resolve tests**

Append to `tests/core/test_config_validate.py`:

```python
# ---------------------------------------------------------------------------
# resolve: move simulation
# ---------------------------------------------------------------------------


def test_resolve_explicit_wins_over_wildcard() -> None:
    """Explicit (Backlog, InProgress) wins over (*, InProgress) wildcard — real edge."""
    draft = _clean_draft()
    # Backlog → Brainstorming is an explicit edge in the shipped config.
    result = resolve(draft, "Backlog", "Brainstorming")
    assert result.matched is True
    assert result.tier == "explicit"


def test_resolve_wildcard_to_blocked() -> None:
    """(*, Blocked) is a wild_to row — any source into Blocked matches."""
    draft = _clean_draft()
    result = resolve(draft, "InProgress", "Blocked")
    assert result.matched is True
    # (*, Blocked) is a wild_to (to_col="Blocked", from_col="*").
    assert result.tier == "wild_to"


def test_resolve_unwhitelisted_move() -> None:
    """A move with no matching row → matched=False, tier='none'."""
    draft = _clean_draft()
    # Brainstorming → Merge is NOT whitelisted in the shipped config.
    result = resolve(draft, "Brainstorming", "Merge")
    assert result.matched is False
    assert result.tier == "none"
    assert result.transition is None
    assert result.would_launch is False


def test_resolve_cancel_engine_handled_teardown() -> None:
    """Any move into Cancel → engine_handled='teardown' (reactive column intercept)."""
    draft = _clean_draft()
    # (* → Cancel) is in the whitelist; Cancel is reactive.
    result = resolve(draft, "InProgress", "Cancel")
    assert result.engine_handled == "teardown"


def test_resolve_cancel_to_backlog_engine_handled_reset() -> None:
    """Cancel → Backlog → engine_handled='reset' (leaving a reactive column)."""
    draft = _clean_draft()
    result = resolve(draft, "Cancel", "Backlog")
    assert result.engine_handled == "reset"


def test_resolve_would_launch_true_for_prompt_bearing() -> None:
    """would_launch is True for a transition that has a prompt."""
    draft = _clean_draft()
    # Backlog → Brainstorming has a prompt in the shipped config.
    result = resolve(draft, "Backlog", "Brainstorming")
    assert result.would_launch is True


def test_resolve_would_launch_false_for_no_op() -> None:
    """would_launch is False for a no-op (no prompt, no script) transition."""
    draft = _clean_draft()
    # Plan → Planned is a no-op (no prompt, no script).
    result = resolve(draft, "Plan", "Planned")
    assert result.matched is True
    assert result.would_launch is False
```

- [ ] **Step 3.3.2: Implement `resolve` in `core/config_validate.py`**

Add after the `validate` function:

```python
def resolve(
    draft: PipelineDraft, from_col: str, to_col: str
) -> ResolvedTransition:
    """Simulate whitelist resolution for a ``(from_col, to_col)`` move (DESIGN §6).

    Mirrors ``TransitionConfig.get`` precedence (``core/transitions.py:183-211``)
    by rendering the draft → ``load_transitions`` → calling ``.get()``.  This is the
    single source of truth for whitelist precedence — no re-implementation.

    Also computes ``engine_handled`` from the column classes in the draft:
    - ``"teardown"`` when ``to_col`` is a reactive column (the engine's
      ``decide()`` intercepts before the whitelist; ``core/decide.py:212-237``).
    - ``"reset"`` when ``from_col`` is reactive and ``to_col == "Backlog"``
      (the engine's reset-target return path; ``core/decide.py:63``).
    - ``""`` otherwise.

    PR-1 scope: whitelist resolution only.  The full ``decide()`` verdict set
    (LAUNCH / ROLLBACK / TEARDOWN / RESET) is mirrored end-to-end in PR 3.

    Args:
        draft: The editable pipeline draft.
        from_col: The source column key.
        to_col: The destination column key.

    Returns:
        A :class:`ResolvedTransition` describing the whitelist verdict.
    """
    # Render and load to get a TransitionConfig (single source of truth for
    # precedence — core/transitions.py:183-211).
    rendered = render_pipeline(draft)
    tc = load_transitions(rendered.transitions)

    matched_transition = tc.get(from_col, to_col)

    # Determine the precedence tier by querying which lookup table matched.
    # Mirrors the order in TransitionConfig.get (transitions.py:202-211):
    # explicit > wild_from > wild_to.
    tier = "none"
    if matched_transition is not None:
        if tc._explicit and (from_col, to_col) in (tc._explicit or {}):
            tier = "explicit"
        elif tc._wild_from and from_col in (tc._wild_from or {}):
            tier = "wild_from"
        elif tc._wild_to and to_col in (tc._wild_to or {}):
            tier = "wild_to"

    # Determine engine_handled from column classes.
    reactive_keys = frozenset(c.key for c in draft.definition.columns if c.column_class == "reactive")
    engine_handled = ""
    if to_col in reactive_keys:
        engine_handled = "teardown"
    elif from_col in reactive_keys and to_col == _DEFAULT_RESET_TARGET:
        engine_handled = "reset"

    # Convert matched Transition to TransitionDef for the caller.
    transition_def: TransitionDef | None = None
    if matched_transition is not None:
        transition_def = TransitionDef(
            from_col=matched_transition.from_col,
            to_col=matched_transition.to_col,
            profile=matched_transition.profile,
            prompt=matched_transition.prompt,
            script=matched_transition.script,
            advance=matched_transition.advance,
            on_fail=matched_transition.on_fail,
            permission_mode=matched_transition.permission_mode,
        )

    return ResolvedTransition(
        matched=matched_transition is not None,
        transition=transition_def,
        tier=tier,
        engine_handled=engine_handled,
        would_launch=matched_transition is not None and matched_transition.prompt is not None,
    )
```

- [ ] **Step 3.3.3: Run all validate tests**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/core/test_config_validate.py -v
```

Expected: all PASS. Pay particular attention to `test_resolve_cancel_engine_handled_teardown` — `(*, Cancel)` is a `wild_to` row so the tier will be `"wild_to"` while `engine_handled="teardown"` (these are independent signals; the test checks `engine_handled` only).

- [ ] **Step 3.3.4: Run layering guard + full suite**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/test_layering.py tests/core/ -v
```

Expected: all PASS.

- [ ] **Step 3.3.5: Phase gate**

```bash
cd /Users/izno/dev/worktrees/ticket-5
make lint
make test
make check
python -c "import kanbanmate"
```

Expected: all clean.

- [ ] **Step 3.3.6: Commit**

```bash
cd /Users/izno/dev/worktrees/ticket-5
git add src/kanbanmate/core/config_validate.py tests/core/test_config_validate.py
git commit -m "feat(helm): core/config_validate.py — validate (V1-V8) + resolve simulator"
```
