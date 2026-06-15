"""Tests for :mod:`kanbanmate.core.transitions`.

Ported from the PoC ``tests/test_transitions.py`` and extended with the
validation-order + defaults-block + string-input-divergence cases required by
phase 12.2.
"""

from __future__ import annotations

import pytest

from kanbanmate.core.transitions import (
    Transition,
    load_transitions,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_yaml(transitions: str) -> str:
    """Wrap a transitions YAML fragment into a valid document."""
    return f"project: test/repo\ndefaults:\n  concurrency_cap: 5\n  move_rate_limit_per_hour: 20\ntransitions:\n{transitions}"


# ---------------------------------------------------------------------------
# Transition dataclass
# ---------------------------------------------------------------------------


def test_transition_defaults() -> None:
    """A ``Transition`` constructed with only ``from_col``/``to_col`` gets the
    documented defaults."""
    t = Transition(from_col="Backlog", to_col="InProgress")
    assert t.from_col == "Backlog"
    assert t.to_col == "InProgress"
    assert t.profile == ""
    assert t.prompt is None
    assert t.script is None
    assert t.advance == "stop"
    assert t.on_fail == ""
    assert t.permission_mode == "auto"
    assert t.has_action is False


def test_has_action_prompt_only() -> None:
    """``has_action`` is ``True`` when a prompt is set (even without a script)."""
    t = Transition(from_col="A", to_col="B", prompt="/implement:phase {{code}}")
    assert t.has_action is True


def test_has_action_script_only() -> None:
    """``has_action`` is ``True`` when a script is set (even without a prompt)."""
    t = Transition(from_col="A", to_col="B", script="bin/check.sh")
    assert t.has_action is True


def test_has_action_both() -> None:
    """``has_action`` is ``True`` when BOTH prompt and script are set."""
    t = Transition(from_col="A", to_col="B", prompt="/implement:phase", script="bin/check.sh")
    assert t.has_action is True


def test_has_action_neither() -> None:
    """``has_action`` is ``False`` when both prompt and script are ``None``."""
    t = Transition(from_col="A", to_col="B")
    assert t.has_action is False


# ---------------------------------------------------------------------------
# TransitionConfig.get — wildcard precedence
# ---------------------------------------------------------------------------


def test_explicit_beats_wildcard() -> None:
    """An explicit ``(from, to)`` pair beats both ``(from, *)`` and ``(*, to)``
    wildcards that also match the same concrete move."""
    cfg = load_transitions(
        _minimal_yaml(
            "  - {from: 'Backlog', to: 'InProgress', prompt: 'explicit'}\n"
            "  - {from: 'Backlog', to: '*', prompt: 'wild_from'}\n"
            "  - {from: '*', to: 'InProgress', prompt: 'wild_to'}\n"
        )
    )
    t = cfg.get("Backlog", "InProgress")
    assert t is not None
    assert t.prompt == "explicit"


def test_wild_from_matches_any_destination() -> None:
    """``(from, *)`` matches ANY destination column from the given source."""
    cfg = load_transitions(_minimal_yaml("  - {from: 'Backlog', to: '*', prompt: 'wild'}\n"))
    t = cfg.get("Backlog", "SomeUnknownColumn")
    assert t is not None
    assert t.prompt == "wild"


def test_wild_to_matches_any_source() -> None:
    """``(*, to)`` matches ANY source column into the given destination."""
    cfg = load_transitions(_minimal_yaml("  - {from: '*', to: 'Cancel', prompt: 'teardown'}\n"))
    t = cfg.get("RandomColumn", "Cancel")
    assert t is not None
    assert t.prompt == "teardown"


def test_unlisted_pair_returns_none() -> None:
    """A pair not covered by any explicit or wildcard entry returns ``None``.
    The caller MUST roll the card back — e.g. ``get("Backlog", "Merge") is None``."""
    cfg = load_transitions(_minimal_yaml("  - {from: 'Backlog', to: 'InProgress', prompt: 'go'}\n"))
    assert cfg.get("Backlog", "Merge") is None


def test_none_when_tables_empty() -> None:
    """``get`` returns ``None`` when no transitions are defined at all."""
    cfg = load_transitions("project: test/repo\ndefaults: {}\ntransitions: []")
    assert cfg.get("Backlog", "InProgress") is None


# ---------------------------------------------------------------------------
# from/to list expansion (cartesian product) — genesis phase 20.1
# ---------------------------------------------------------------------------


def test_from_list_expands_to_explicit_edges() -> None:
    """``from: [a, b, c], to: d`` expands to 3 explicit edges, all carrying the
    SAME action (the shared prompt)."""
    cfg = load_transitions(
        _minimal_yaml("  - {from: ['a', 'b', 'c'], to: 'd', prompt: 'shared'}\n")
    )
    for src in ("a", "b", "c"):
        t = cfg.get(src, "d")
        assert t is not None
        assert t.prompt == "shared"
    # No spurious extra edges.
    assert cfg.get("a", "x") is None


def test_cartesian_product_both_sides() -> None:
    """``from: [a, b], to: [c, d]`` expands to the 4-edge cartesian product."""
    cfg = load_transitions(
        _minimal_yaml("  - {from: ['a', 'b'], to: ['c', 'd'], prompt: 'cart'}\n")
    )
    for src in ("a", "b"):
        for dst in ("c", "d"):
            t = cfg.get(src, dst)
            assert t is not None, f"missing edge {src}->{dst}"
            assert t.prompt == "cart"


def test_list_member_beats_wildcard() -> None:
    """A list-expanded member ``[a, b] → c`` feeds ``_explicit`` and therefore
    wins over a separate ``(*, c)`` wildcard, exactly as a hand-written ``a→c``."""
    cfg = load_transitions(
        _minimal_yaml(
            "  - {from: ['a', 'b'], to: 'c', prompt: 'list_member'}\n"
            "  - {from: '*', to: 'c', prompt: 'wild_to'}\n"
        )
    )
    # Both list members resolve to the explicit action, not the wildcard.
    assert cfg.get("a", "c").prompt == "list_member"  # type: ignore[union-attr]
    assert cfg.get("b", "c").prompt == "list_member"  # type: ignore[union-attr]
    # The wildcard still catches a source NOT in the list.
    assert cfg.get("z", "c").prompt == "wild_to"  # type: ignore[union-attr]


def test_duplicate_pair_list_and_explicit_raises() -> None:
    """A list-expanded pair colliding with an explicit row on the SAME
    ``(from, to)`` key is rejected (no silent last-wins)."""
    with pytest.raises(ValueError, match="duplicate transition"):
        load_transitions(
            _minimal_yaml(
                "  - {from: ['a', 'b'], to: 'c', prompt: 'from_list'}\n"
                "  - {from: 'a', to: 'c', prompt: 'explicit'}\n"
            )
        )


def test_duplicate_pair_within_list_raises() -> None:
    """Two list rows expanding to the same concrete pair are rejected."""
    with pytest.raises(ValueError, match="duplicate transition"):
        load_transitions(
            _minimal_yaml(
                "  - {from: ['a', 'b'], to: 'c', prompt: 'one'}\n"
                "  - {from: ['a'], to: ['c'], prompt: 'two'}\n"
            )
        )


def test_duplicate_wildcard_to_raises() -> None:
    """Two ``(*, to)`` rows colliding on the same destination are rejected."""
    with pytest.raises(ValueError, match="duplicate wildcard"):
        load_transitions(
            _minimal_yaml(
                "  - {from: '*', to: 'Cancel', prompt: 'a'}\n"
                "  - {from: '*', to: 'Cancel', prompt: 'b'}\n"
            )
        )


def test_duplicate_wildcard_from_raises() -> None:
    """Two ``(from, *)`` rows colliding on the same source are rejected."""
    with pytest.raises(ValueError, match="duplicate wildcard"):
        load_transitions(
            _minimal_yaml(
                "  - {from: 'Blocked', to: '*', prompt: 'a'}\n"
                "  - {from: 'Blocked', to: '*', prompt: 'b'}\n"
            )
        )


def test_star_inside_list_raises() -> None:
    """The ``'*'`` wildcard may NOT appear inside a ``from``/``to`` list."""
    with pytest.raises(ValueError, match=r"may not appear inside"):
        load_transitions(_minimal_yaml("  - {from: ['a', '*'], to: 'c', prompt: 'bad'}\n"))


def test_empty_from_list_raises() -> None:
    """An empty ``from`` list whitelists nothing → ``ValueError``."""
    with pytest.raises(ValueError, match="empty 'from' list"):
        load_transitions(_minimal_yaml("  - {from: [], to: 'c', prompt: 'bad'}\n"))


def test_empty_to_list_raises() -> None:
    """An empty ``to`` list whitelists nothing → ``ValueError``."""
    with pytest.raises(ValueError, match="empty 'to' list"):
        load_transitions(_minimal_yaml("  - {from: 'a', to: [], prompt: 'bad'}\n"))


def test_list_non_string_member_raises() -> None:
    """A non-string member in a ``from``/``to`` list → ``ValueError``."""
    with pytest.raises(ValueError, match="must be non-empty strings"):
        load_transitions(_minimal_yaml("  - {from: ['a', 5], to: 'c', prompt: 'bad'}\n"))


# ---------------------------------------------------------------------------
# Validation: load_transitions error cases (fail-CLOSED)
# ---------------------------------------------------------------------------


def test_star_star_raises() -> None:
    """A ``'*' -> '*'`` wildcard pair is rejected with ``ValueError``."""
    with pytest.raises(ValueError, match=r"\*.*\*"):
        load_transitions(_minimal_yaml("  - {from: '*', to: '*', prompt: 'bad'}\n"))


def test_missing_from_raises() -> None:
    """An entry without ``from`` raises ``ValueError``."""
    with pytest.raises(ValueError, match="missing.*'from'"):
        load_transitions(_minimal_yaml("  - {to: 'InProgress', prompt: 'go'}\n"))


def test_missing_to_raises() -> None:
    """An entry without ``to`` raises ``ValueError``."""
    with pytest.raises(ValueError, match="missing.*'to'"):
        load_transitions(_minimal_yaml("  - {from: 'Backlog', prompt: 'go'}\n"))


def test_permission_mode_bool_raises() -> None:
    """A ``permission_mode: no`` (YAML coerced to bool ``False``) raises
    ``ValueError`` with a quote-it hint."""
    with pytest.raises(ValueError, match="quote it"):
        load_transitions(
            "project: test/repo\ndefaults: {}\ntransitions:\n"
            "  - {from: 'Backlog', to: 'InProgress', prompt: 'go', permission_mode: no}\n"
        )


def test_permission_mode_bypass_raises() -> None:
    """``bypassPermissions`` (any case variant) is banned — raises ``ValueError``."""
    with pytest.raises(ValueError, match="banned"):
        load_transitions(
            _minimal_yaml(
                "  - {from: 'Backlog', to: 'InProgress', prompt: 'go',"
                " permission_mode: 'bypassPermissions'}\n"
            )
        )


def test_permission_mode_bypass_mixed_case_raises() -> None:
    """A ``permission_mode`` containing 'bypass' in any casing raises."""
    with pytest.raises(ValueError, match="banned"):
        load_transitions(
            _minimal_yaml(
                "  - {from: 'Backlog', to: 'InProgress', prompt: 'go',"
                " permission_mode: 'BypassPermissions'}\n"
            )
        )


def test_permission_mode_unknown_raises() -> None:
    """An unknown ``permission_mode`` value raises ``ValueError`` listing the
    allowed set."""
    with pytest.raises(ValueError, match="unknown permission_mode"):
        load_transitions(
            _minimal_yaml(
                "  - {from: 'Backlog', to: 'InProgress', prompt: 'go',"
                " permission_mode: 'superman'}\n"
            )
        )


def test_permission_mode_int_raises() -> None:
    """A ``permission_mode: 5`` (YAML int) raises ``ValueError`` (non-string guard)."""
    with pytest.raises(ValueError, match="must be a string"):
        load_transitions(
            "project: test/repo\ndefaults: {}\ntransitions:\n"
            "  - {from: 'Backlog', to: 'InProgress', prompt: 'go', permission_mode: 5}\n"
        )


def test_permission_mode_none_raises() -> None:
    """A ``permission_mode:`` with no value (YAML null → Python ``None``) raises."""
    with pytest.raises(ValueError, match="must be a string"):
        load_transitions(
            "project: test/repo\ndefaults: {}\ntransitions:\n"
            "  - {from: 'Backlog', to: 'InProgress', prompt: 'go', permission_mode:}\n"
        )


# ---------------------------------------------------------------------------
# Defaults block
# ---------------------------------------------------------------------------


def test_defaults_block_parses_cap_and_rate_limit() -> None:
    """The ``defaults`` block ``concurrency_cap`` and ``move_rate_limit_per_hour``
    are parsed and surfaced on the config."""
    cfg = load_transitions(
        "project: test/repo\n"
        "defaults:\n"
        "  concurrency_cap: 8\n"
        "  move_rate_limit_per_hour: 30\n"
        "transitions: []\n"
    )
    assert cfg.concurrency_cap == 8
    assert cfg.move_rate_limit_per_hour == 30


def test_defaults_block_falls_back_cap() -> None:
    """When ``concurrency_cap`` is absent, defaults to 3 (#4 — aligned with the template)."""
    cfg = load_transitions("project: test/repo\ndefaults: {}\ntransitions: []\n")
    assert cfg.concurrency_cap == 3


def test_defaults_block_falls_back_rate() -> None:
    """When ``move_rate_limit_per_hour`` is absent, defaults to 10."""
    cfg = load_transitions("project: test/repo\ndefaults: {}\ntransitions: []\n")
    assert cfg.move_rate_limit_per_hour == 10


def test_defaults_block_completely_absent() -> None:
    """When the ``defaults`` key is absent entirely, both values fall back (cap 3, #4)."""
    cfg = load_transitions("project: test/repo\ntransitions: []\n")
    assert cfg.concurrency_cap == 3
    assert cfg.move_rate_limit_per_hour == 10


def test_project_header() -> None:
    """The ``project`` header is parsed and surfaced."""
    cfg = load_transitions("project: owner/repo\ndefaults: {}\ntransitions: []\n")
    assert cfg.project == "owner/repo"


def test_project_header_absent() -> None:
    """When the ``project`` header is absent, it defaults to ``""``."""
    cfg = load_transitions("defaults: {}\ntransitions: []\n")
    assert cfg.project == ""


# ---------------------------------------------------------------------------
# Empty / null YAML input (string-input divergence safety)
# ---------------------------------------------------------------------------


def test_empty_yaml_text() -> None:
    """An empty YAML string produces a valid (empty) config (``safe_load`` returns
    ``None``, which becomes ``{}``)."""
    cfg = load_transitions("")
    assert cfg.project == ""
    assert cfg.concurrency_cap == 3  # #4: loader fallback aligned with the template default
    assert cfg.move_rate_limit_per_hour == 10
    assert cfg.get("Backlog", "InProgress") is None


def test_null_yaml_root() -> None:
    """A YAML document that parses to ``None`` (``---``) produces a valid empty config."""
    cfg = load_transitions("---")
    assert cfg.project == ""
    assert cfg.concurrency_cap == 3  # #4: loader fallback aligned with the template default


# ---------------------------------------------------------------------------
# Allowed permission modes stress
# ---------------------------------------------------------------------------


def test_all_allowed_modes_accepted() -> None:
    """Every member of ``_ALLOWED_PERMISSION_MODES`` is accepted without error."""
    for mode in ("default", "acceptEdits", "auto", "dontAsk", "plan"):
        cfg = load_transitions(
            _minimal_yaml(
                f"  - {{from: 'Backlog', to: '{mode}', prompt: 'go', permission_mode: '{mode}'}}\n"
            )
        )
        t = cfg.get("Backlog", mode)
        assert t is not None
        assert t.permission_mode == mode


# ---------------------------------------------------------------------------
# Multiple entries + table separation
# ---------------------------------------------------------------------------


def test_multiple_explicit_entries() -> None:
    """Multiple explicit pairs are correctly routed into the explicit table."""
    cfg = load_transitions(
        _minimal_yaml(
            "  - {from: 'Backlog', to: 'Spec', prompt: 'design'}\n"
            "  - {from: 'Spec', to: 'Plan', prompt: 'plan'}\n"
            "  - {from: 'Plan', to: 'ReadyToDev', prompt: null}\n"
        )
    )
    assert cfg.get("Backlog", "Spec") is not None
    assert cfg.get("Backlog", "Spec").prompt == "design"  # type: ignore[union-attr]
    assert cfg.get("Spec", "Plan") is not None
    assert cfg.get("Spec", "Plan").prompt == "plan"  # type: ignore[union-attr]
    t = cfg.get("Plan", "ReadyToDev")
    assert t is not None
    assert t.has_action is False  # allowed no-op


def test_mixed_explicit_and_wildcards() -> None:
    """Explicit, wild-to, and wild-from entries coexist correctly."""
    cfg = load_transitions(
        _minimal_yaml(
            "  - {from: 'Backlog', to: 'InProgress', prompt: 'explicit'}\n"
            "  - {from: '*', to: 'Cancel', prompt: 'teardown'}\n"
            "  - {from: 'Blocked', to: '*', prompt: 'unblock'}\n"
        )
    )
    # Explicit wins when present.
    assert cfg.get("Backlog", "InProgress").prompt == "explicit"  # type: ignore[union-attr]
    # Wild (*, Cancel) catches anything → Cancel.
    assert cfg.get("InProgress", "Cancel").prompt == "teardown"  # type: ignore[union-attr]
    # Wild (Blocked, *) catches Blocked → anything.
    assert cfg.get("Blocked", "InProgress").prompt == "unblock"  # type: ignore[union-attr]
    # Unlisted pair.
    assert cfg.get("InProgress", "Unknown") is None


# ---------------------------------------------------------------------------
# launch_target_columns(): the prompt-bearing destinations (DESIGN §8.0.5)
# ---------------------------------------------------------------------------


def test_launch_targets_collect_explicit_prompt_destinations() -> None:
    """Explicit prompt-bearing pairs contribute their ``to_col``."""
    cfg = load_transitions(
        _minimal_yaml(
            "  - {from: 'Backlog', to: 'Spec', prompt: 'design'}\n"
            "  - {from: 'Spec', to: 'Planned', prompt: 'plan'}\n"
        )
    )
    assert cfg.launch_target_columns() == frozenset({"Spec", "Planned"})


def test_launch_targets_exclude_non_prompt_transitions() -> None:
    """A script-only or no-op transition's destination is NOT a launch target."""
    cfg = load_transitions(
        _minimal_yaml(
            "  - {from: 'InProgress', to: 'PRCI', prompt: 'fix'}\n"
            "  - {from: 'Review', to: 'Merge', script: 'bin/check-merge-ready.sh'}\n"
            "  - {from: 'Merge', to: 'Done'}\n"
        )
    )
    # Only the prompt-bearing PRCI is a launch target; the Merge script gate and the
    # Done no-op are not (this is the merge=human-only preservation, DESIGN §8.0.5).
    targets = cfg.launch_target_columns()
    assert "PRCI" in targets
    assert "Merge" not in targets
    assert "Done" not in targets


def test_launch_targets_include_wild_to_prompt_destination() -> None:
    """A ``from='*'`` (wild-to) prompt entry contributes its concrete ``to_col``."""
    cfg = load_transitions(
        _minimal_yaml(
            "  - {from: '*', to: 'Cancel', prompt: 'teardown'}\n"
            "  - {from: 'Backlog', to: 'Spec', prompt: 'design'}\n"
        )
    )
    assert cfg.launch_target_columns() == frozenset({"Cancel", "Spec"})


def test_launch_targets_exclude_wild_from_no_concrete_target() -> None:
    """A ``to='*'`` (wild-from) prompt entry names no concrete destination → excluded."""
    cfg = load_transitions(
        _minimal_yaml(
            "  - {from: 'Blocked', to: '*', prompt: 'unblock'}\n"
            "  - {from: 'Backlog', to: 'Spec', prompt: 'design'}\n"
        )
    )
    # The wild-from entry has no single launch-target column; only Spec is collected.
    assert cfg.launch_target_columns() == frozenset({"Spec"})


def test_launch_targets_empty_when_no_prompts() -> None:
    """A whitelist of only no-op/script transitions has no launch targets."""
    cfg = load_transitions(
        _minimal_yaml(
            "  - {from: 'Planned', to: 'ReadyToDev'}\n"
            "  - {from: 'Review', to: 'Merge', script: 'bin/check.sh'}\n"
        )
    )
    assert cfg.launch_target_columns() == frozenset()


def test_launch_targets_default_flow_matches_poc_prompt_destinations() -> None:
    """The shipped DEFAULT_TRANSITIONS launch targets are exactly the prompt destinations."""
    from kanbanmate.core.transitions_defaults import default_transition_config

    targets = default_transition_config().launch_target_columns()
    # Prompt-bearing rows in DEFAULT_TRANSITIONS (genesis phase 26):
    # Backlog→Brainstorming, Brainstorming→Spec, Spec→Plan, ReadyToDev→PrepareFeature,
    # PrepareFeature→InProgress, PRCI→InProgress, PRCI→Review. Plan→Planned and
    # Planned→ReadyToDev are no-ops; the six skip-to-Done edges are no-ops; (*)→Cancel
    # is a no-op. Merge is a script gate (no prompt).
    assert targets == frozenset(
        {"Brainstorming", "Spec", "Plan", "PrepareFeature", "InProgress", "Review"}
    )
    # Merge stays human (script gate, not a prompt) → NOT a launch target.
    assert "Merge" not in targets
    # Done is never a launch target (the skip-to-Done edges are no-ops).
    assert "Done" not in targets


# ---------------------------------------------------------------------------
# TransitionConfig immutability
# ---------------------------------------------------------------------------


def test_transition_config_is_frozen() -> None:
    """``TransitionConfig`` is frozen — setting an attribute raises."""
    cfg = load_transitions("project: test\ndefaults: {}\ntransitions: []")
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
        cfg.concurrency_cap = 99  # type: ignore[misc]


def test_transition_is_frozen() -> None:
    """``Transition`` is frozen — setting an attribute raises."""
    t = Transition(from_col="A", to_col="B")
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
        t.prompt = "changed"  # type: ignore[misc]
