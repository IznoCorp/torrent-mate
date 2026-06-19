"""Tests for :mod:`kanbanmate.core.config_validate`.

Covers value objects, the oracle pass, each of V1-V10 semantic checks, and the
resolve simulator.  Each validator test uses a *genuinely-produced* Finding —
never an empty-list comparison.
"""

from __future__ import annotations

import importlib.resources

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
    f = Finding(
        field="transitions[0].permission_mode",
        message="Bad mode",
        severity="error",
        locus="transitions[0]",
    )
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
    rt = ResolvedTransition(
        matched=False, transition=None, tier="none", engine_handled="", would_launch=False
    )
    assert rt.matched is False
    assert rt.transition is None
    assert rt.would_launch is False


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
    """V2: a prompt where the /implement: token is replaced by garbage → error."""
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
    mangled_draft = PipelineDraft(
        definition=Definition(
            columns=clean.definition.columns,
            transitions=mangled_transitions,
            defaults=clean.definition.defaults,
        ),
        binding=clean.binding,
    )
    result = validate(mangled_draft)
    v2_errors = [
        f for f in result.findings if f.severity == "error" and "slash" in f.message.lower()
    ]
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
        f for f in result.findings if f.severity == "error" and "permission_mode" in f.field
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
            f for f in result.findings if f.severity == "error" and "permission_mode" in f.field
        ]
        assert not v3_errors, f"Unexpected V3 error for valid mode {mode!r}: {v3_errors}"


# ---------------------------------------------------------------------------
# validate: V4 — profile in PROFILES
# ---------------------------------------------------------------------------


def test_validate_v4_unknown_profile() -> None:
    """V4: a profile not in PROFILES (e.g. 'bogus') must produce an error."""
    t = TransitionDef(
        from_col="Backlog",
        to_col="InProgress",
        profile="bogus",  # invalid — not a workflow profile
        prompt="/implement:phase {{code}}",
        permission_mode="auto",
    )
    draft = _draft_with_one_transition(t)
    result = validate(draft)
    v4_errors = [f for f in result.findings if f.severity == "error" and "profile" in f.field]
    assert v4_errors, "Expected a V4 error for unknown profile 'bogus'"


def test_validate_v4_accepts_merge_profile() -> None:
    """V4: 'merge' is now a VALID profile (the autonomous merge stage, operator decision)."""
    t = TransitionDef(
        from_col="Backlog",
        to_col="InProgress",
        profile="merge",
        prompt="merge it",
        permission_mode="auto",
    )
    draft = _draft_with_one_transition(t)
    result = validate(draft)
    v4_errors = [f for f in result.findings if f.severity == "error" and "profile" in f.field]
    assert not v4_errors, f"'merge' must be accepted by V4; got {v4_errors}"


def test_validate_v4_valid_profiles() -> None:
    """V4: all valid profiles (incl. 'merge') pass without error."""
    for profile in ("docs", "prepare", "dev", "check", "merge"):
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
        f
        for f in result.findings
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
        f
        for f in result.findings
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
        TransitionDef(from_col="*", to_col="B"),  # wild_to covers (*, B)
        TransitionDef(from_col="A", to_col="B"),  # explicit — shadowed by (*, B)
    ]
    draft = PipelineDraft(
        definition=Definition(columns=cols, transitions=transitions, defaults=Defaults(3, 10)),
        binding=Binding(project="owner/repo"),
    )
    result = validate(draft)
    v6_warnings = [
        f for f in result.findings if f.severity == "warning" and "shadow" in f.message.lower()
    ]
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
    v7_errors = [
        f for f in result.findings if f.severity == "error" and "reactive" in f.message.lower()
    ]
    assert v7_errors, "Expected a V7 error for a prompt-bearing transition into a reactive column"


def test_validate_v7_prompt_into_merge_column() -> None:
    """V7: a prompt-bearing transition whose to_col is 'Merge' → error (Merge=human-only)."""
    # Build a minimal draft with all real columns but a synthetic * → Merge with a prompt.
    clean = _clean_draft()
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
        f for f in result.findings if f.severity == "error" and "merge" in f.message.lower()
    ]
    assert v7_errors, "Expected a V7 error for a prompt-bearing transition into Merge"


def test_validate_v7_allows_merge_profile_into_merge_column() -> None:
    """V7 carve-out: a prompt-bearing transition into 'Merge' carrying the 'merge' profile (the
    sanctioned autonomous merge stage, DESIGN §15) is ALLOWED — no V7 error."""
    clean = _clean_draft()
    new_transitions = list(clean.definition.transitions) + [
        TransitionDef(
            from_col="Review",
            to_col="Merge",
            profile="merge",  # the sanctioned autonomous merge stage
            prompt="merge {{code}}",
            permission_mode="auto",
        )
    ]
    draft = PipelineDraft(
        definition=Definition(
            columns=clean.definition.columns,
            transitions=new_transitions,
            defaults=clean.definition.defaults,
        ),
        binding=clean.binding,
    )
    result = validate(draft)
    merge_errors = [
        f
        for f in result.findings
        if f.severity == "error" and "merge" in f.message.lower() and "Merge" in (f.field or "")
    ]
    assert not merge_errors, (
        f"merge-profile transition into Merge must be allowed; got {merge_errors}"
    )


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
    columns_with_defaults = (
        columns_template + "\ndefaults:\n  concurrency_cap: 99\n  move_rate_limit_per_hour: 10\n"
    )

    draft = PipelineDraft.from_loaded(render_transitions_yaml("owner/repo"), columns_with_defaults)
    # The draft has concurrency_cap=3 (from transitions.yml); columns says 99.
    result = validate(draft, columns_yaml=columns_with_defaults)
    v8_warnings = [
        f for f in result.findings if f.severity == "warning" and "default" in f.message.lower()
    ]
    assert v8_warnings, (
        "Expected a V8 warning when columns.yml defaults disagree with transitions.yml"
    )


def test_validate_v8_no_false_positive_on_matching_block() -> None:
    """V8 must NOT fire when a present columns.yml defaults: block AGREES with transitions.yml.

    Guards the documented trap (config_validate.py:354-365): an uncommented block
    that matches must produce zero warnings — only a disagreeing block does.
    """
    columns_template = _columns_yaml()
    # The shipped transitions.yml defaults are 3 / 10; spell them out, matching.
    columns_with_matching = (
        columns_template + "\ndefaults:\n  concurrency_cap: 3\n  move_rate_limit_per_hour: 10\n"
    )
    draft = PipelineDraft.from_loaded(render_transitions_yaml("owner/repo"), columns_with_matching)
    result = validate(draft, columns_yaml=columns_with_matching)
    v8_warnings = [
        f for f in result.findings if f.severity == "warning" and "default" in f.message.lower()
    ]
    assert not v8_warnings, f"V8 false-positive on a matching defaults block: {v8_warnings}"


# ---------------------------------------------------------------------------
# validate: V9 — column-class membership
# ---------------------------------------------------------------------------


def test_validate_v9_invalid_column_class() -> None:
    """V9: a column_class outside {reactive, inert} → error finding (silent demotion guard)."""
    draft = _clean_draft()
    # Corrupt one column's class with a typo; without V9 this would silently
    # render as inert (no action key) with no finding.
    draft.definition.columns[0].column_class = "reactve"
    result = validate(draft)
    v9_errors = [f for f in result.findings if f.severity == "error" and "column_class" in f.field]
    assert v9_errors, "Expected a V9 error for an invalid column_class"
    assert "reactve" in v9_errors[0].message


def test_validate_v9_clean_config_no_column_class_findings() -> None:
    """The shipped config (all reactive/inert) produces no V9 finding."""
    result = validate(_clean_draft())
    v9 = [f for f in result.findings if "column_class" in f.field]
    assert not v9, f"Unexpected V9 findings on the shipped config: {v9}"


# ---------------------------------------------------------------------------
# validate: V10 — defaults sanity
# ---------------------------------------------------------------------------


def test_validate_v10_non_positive_concurrency_cap() -> None:
    """V10: concurrency_cap < 1 → error (a 0 cap stalls every launch)."""
    draft = _clean_draft()
    draft.definition.defaults.concurrency_cap = 0
    result = validate(draft)
    v10 = [f for f in result.findings if f.severity == "error" and "concurrency_cap" in f.field]
    assert v10, "Expected a V10 error for concurrency_cap=0"


def test_validate_v10_non_positive_rate_limit() -> None:
    """V10: move_rate_limit_per_hour < 1 → error."""
    draft = _clean_draft()
    draft.definition.defaults.move_rate_limit_per_hour = 0
    result = validate(draft)
    v10 = [
        f
        for f in result.findings
        if f.severity == "error" and "move_rate_limit_per_hour" in f.field
    ]
    assert v10, "Expected a V10 error for move_rate_limit_per_hour=0"


# ---------------------------------------------------------------------------
# validate: clean config (no findings)
# ---------------------------------------------------------------------------


def test_validate_clean_config_no_findings() -> None:
    """The shipped config must produce zero findings (error or warning)."""
    result = validate(_clean_draft())
    errors = [f for f in result.findings if f.severity == "error"]
    assert not errors, f"Unexpected errors from the shipped config: {errors}"
    assert result.ok is True


# ---------------------------------------------------------------------------
# resolve: move simulation
# ---------------------------------------------------------------------------


def test_resolve_explicit_edge() -> None:
    """An uncontested explicit edge resolves with tier='explicit' (real shipped edge)."""
    draft = _clean_draft()
    # Backlog → Brainstorming is an explicit edge in the shipped config (no
    # (*, Brainstorming) wildcard exists, so this is uncontested).
    result = resolve(draft, "Backlog", "Brainstorming")
    assert result.matched is True
    assert result.tier == "explicit"


def test_resolve_explicit_wins_over_wildcard() -> None:
    """When an explicit (A→B) and a wildcard (*→B) BOTH match, explicit wins (real contention)."""
    cols = [
        ColumnDef(key="A", name="A", column_class="inert"),
        ColumnDef(key="B", name="B", column_class="inert"),
        ColumnDef(key="C", name="C", column_class="inert"),
    ]
    # Both rows resolve into B; A→B is explicit, *→B is wild_to. The loader keeps
    # them in distinct lookup tables, so this is genuine precedence contention.
    explicit_row = TransitionDef(from_col="A", to_col="B", prompt="from-explicit")
    wildcard_row = TransitionDef(from_col="*", to_col="B", prompt="from-wildcard")
    draft = PipelineDraft(
        definition=Definition(
            columns=cols,
            transitions=[explicit_row, wildcard_row],
            defaults=Defaults(concurrency_cap=3, move_rate_limit_per_hour=10),
        ),
        binding=Binding(project="owner/repo"),
    )
    # A→B matches BOTH rows; explicit must win.
    res = resolve(draft, "A", "B")
    assert res.matched is True
    assert res.tier == "explicit"
    assert res.transition is not None and res.transition.prompt == "from-explicit"
    # C→B matches ONLY the wildcard.
    res2 = resolve(draft, "C", "B")
    assert res2.matched is True
    assert res2.tier == "wild_to"
    assert res2.transition is not None and res2.transition.prompt == "from-wildcard"


def test_resolve_wild_from_tier() -> None:
    """(Blocked, *) is the lone wild_from row — Blocked→anything matches with tier='wild_from'."""
    draft = _clean_draft()
    # Blocked → Done is not an explicit edge; it matches the (Blocked, *) wildcard.
    result = resolve(draft, "Blocked", "Done")
    assert result.matched is True
    assert result.tier == "wild_from"


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


def test_validate_v11_empty_board_rejected() -> None:
    """V11: a board with no columns AND no transitions is an error.

    An empty board trips none of V1-V10 and the loaders accept it, so without V11 a POST /api/config
    of an empty/defaulted draft would validate clean and WIPE the live pipeline (data-loss).
    """
    draft = PipelineDraft(
        definition=Definition(
            columns=[],
            transitions=[],
            defaults=Defaults(concurrency_cap=3, move_rate_limit_per_hour=10),
        ),
        binding=Binding(project="owner/repo"),
    )
    result = validate(draft)
    assert not result.ok
    errs = " ".join(f.message.lower() for f in result.findings if f.severity == "error")
    assert "at least one column" in errs
    assert "at least one transition" in errs
