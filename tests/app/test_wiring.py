"""Tests for the composition root (:mod:`kanbanmate.app.wiring`).

:func:`~kanbanmate.app.wiring.build_tick_config` parses the column model from a YAML string,
the transition whitelist from ``transitions_yaml``, and threads the kill-switch flag into
the resulting ``TickConfig``. These tests feed an explicit ``WiringConfig`` and assert the
parsed columns map and the threaded flag, exercising the complete function without touching
any I/O.  Also covers :func:`~kanbanmate.app.wiring.build_deps` threading ``config.repo`` into
``Deps.repo`` (phase 12.9).
"""

from __future__ import annotations

import pytest

from kanbanmate.app.actions import Deps
from kanbanmate.app.tick import TickConfig
from kanbanmate.app.wiring import WiringConfig, build_deps, build_tick_config
from kanbanmate.core.domain import ColumnClass
from kanbanmate.core.transitions_defaults import default_transition_config

_COLUMNS_YAML = """columns:
  - key: Backlog
    name: Backlog
  - key: InProgress
    name: In Progress
  - key: Cancel
    name: Cancel
    action: teardown
  - key: Done
    name: Done
"""


def _make_config(*, kill_switch: bool = False) -> WiringConfig:
    """Build a minimal :class:`WiringConfig` with the standard test columns YAML.

    Args:
        kill_switch: The static kill-switch flag to thread through.

    Returns:
        A ``WiringConfig`` suitable for feeding to :func:`build_tick_config`.
    """
    return WiringConfig(
        token="dummy",
        project_id="PVT_test",
        repo="owner/repo",
        clone_dir="/tmp/clone",
        columns_yaml=_COLUMNS_YAML,
        kill_switch=kill_switch,
    )


def test_build_tick_config_parses_columns_map() -> None:
    """The columns YAML is parsed into a key→Column mapping via ``load_columns``."""
    config = _make_config()

    tick_config = build_tick_config(config)

    assert isinstance(tick_config, TickConfig)
    columns = tick_config.columns
    assert "Backlog" in columns
    assert "InProgress" in columns
    assert "Cancel" in columns
    assert "Done" in columns
    # Verify column classes are resolved correctly. In the transitions-only model
    # (§8.0.6) every non-reactive column is INERT — only Cancel (action: teardown)
    # is reactive; the launch lives on the transition, not the column.
    assert columns["Backlog"].column_class == ColumnClass.INERT
    assert columns["InProgress"].column_class == ColumnClass.INERT
    assert columns["Cancel"].column_class == ColumnClass.REACTIVE
    assert columns["Done"].column_class == ColumnClass.INERT


def test_build_tick_config_threads_kill_switch_true() -> None:
    """When ``WiringConfig.kill_switch`` is ``True`` it lands in the ``TickConfig``."""
    config = _make_config(kill_switch=True)

    tick_config = build_tick_config(config)

    assert tick_config.kill_switch is True


def test_build_tick_config_threads_kill_switch_false() -> None:
    """When ``WiringConfig.kill_switch`` is ``False`` it lands in the ``TickConfig``."""
    config = _make_config(kill_switch=False)

    tick_config = build_tick_config(config)

    assert tick_config.kill_switch is False


def test_build_tick_config_returns_tick_config_with_sensible_defaults() -> None:
    """The returned ``TickConfig`` carries the default TTL, timeout, and column names."""
    config = _make_config()

    tick_config = build_tick_config(config)

    # Sensible defaults from the module-level constants are preserved.
    assert tick_config.heartbeat_ttl > 0
    assert tick_config.action_timeout > 0
    assert tick_config.blocked_column
    assert tick_config.reset_target


# ── transitions_yaml wiring ─────────────────────────────────────────────────

_TRANSITIONS_YAML = """project: test/example
defaults:
  concurrency_cap: 3
  move_rate_limit_per_hour: 10
transitions:
  - from: Backlog
    to: InProgress
    prompt: "/implement:phase {{code}}"
  - from: InProgress
    to: PRCI
    script: bin/check-pr-ready.sh
    on_fail: move:InProgress
  - from: PRCI
    to: InProgress
    prompt: "fix CI: {{title}}"
"""


def test_transitions_yaml_wired_to_tick_config() -> None:
    """A ``WiringConfig`` with ``transitions_yaml`` produces a ``TickConfig`` with a populated ``TransitionConfig``."""
    config = _make_config()
    config = WiringConfig(
        token="dummy",
        project_id="PVT_test",
        repo="owner/repo",
        clone_dir="/tmp/clone",
        columns_yaml=_COLUMNS_YAML,
        transitions_yaml=_TRANSITIONS_YAML,
    )

    tick_config = build_tick_config(config)

    assert tick_config.transitions is not None
    # The whitelist resolves an explicit pair.
    t = tick_config.transitions.get("Backlog", "InProgress")
    assert t is not None
    assert t.prompt is not None
    assert "/implement:phase" in t.prompt


def test_transitions_yaml_absent_falls_back_to_default_flow() -> None:
    """When ``transitions_yaml`` is absent (``None``) the ``TickConfig.transitions`` falls back to
    the built-in ``DEFAULT_TRANSITIONS`` flow — a whitelist is ALWAYS supplied (DESIGN §8.0.6)."""
    config = _make_config()

    tick_config = build_tick_config(config)

    # A whitelist is always present; it is the shipped PoC default flow, never None.
    assert tick_config.transitions is not None
    # A known forward edge (Backlog → Triage) carries the skiff classifier prompt. skiff: Backlog
    # now → Triage; the interactive brainstorm moved to Triage → Brainstorming (the FULL lane head).
    backlog_to_triage = tick_config.transitions.get("Backlog", "Triage")
    assert backlog_to_triage is not None
    assert backlog_to_triage.prompt is not None
    triage_to_brainstorming = tick_config.transitions.get("Triage", "Brainstorming")
    assert triage_to_brainstorming is not None
    assert triage_to_brainstorming.prompt is not None
    assert "/implement:brainstorm" in triage_to_brainstorming.prompt
    # Another known edge (PrepareFeature → InProgress) resolves to the implement prompt.
    prepare_to_inprogress = tick_config.transitions.get("PrepareFeature", "InProgress")
    assert prepare_to_inprogress is not None
    assert prepare_to_inprogress.prompt is not None
    assert "/implement:phase" in prepare_to_inprogress.prompt


def test_transitions_yaml_default_fallback_equals_default_transition_config() -> None:
    """The no-``transitions.yml`` fallback is exactly :func:`default_transition_config` (the shipped
    PoC whitelist), so the wiring builds NO divergent second whitelist."""
    config = _make_config()

    tick_config = build_tick_config(config)

    expected = default_transition_config()
    assert tick_config.transitions is not None
    # Same resolved edges across the whole default flow (explicit, wildcard, and no-op rows).
    # skiff: the front-of-flow launch is now Backlog → Triage.
    for from_col, to_col in [
        ("Backlog", "Triage"),
        ("Triage", "Brainstorming"),
        ("PrepareFeature", "InProgress"),
        ("Review", "Merge"),
        ("Anything", "Cancel"),  # (*, Cancel) wildcard
        ("Cancel", "Backlog"),
    ]:
        got = tick_config.transitions.get(from_col, to_col)
        want = expected.get(from_col, to_col)
        assert got == want, f"{from_col}->{to_col}: {got!r} != {want!r}"


def test_explicit_transitions_yaml_wins_over_default_fallback() -> None:
    """An explicit ``transitions_yaml`` is parsed and used — the default fallback does NOT win."""
    config = WiringConfig(
        token="dummy",
        project_id="PVT_test",
        repo="owner/repo",
        clone_dir="/tmp/clone",
        columns_yaml=_COLUMNS_YAML,
        transitions_yaml=_TRANSITIONS_YAML,
    )

    tick_config = build_tick_config(config)

    assert tick_config.transitions is not None
    # The explicit file's project header is present (the default fallback ships an empty project).
    assert tick_config.transitions.project == "test/example"
    # The explicit file does NOT whitelist Backlog → Spec (only the default flow does), proving the
    # default fallback did not silently merge in.
    assert tick_config.transitions.get("Backlog", "Spec") is None
    # The explicit file's own edge resolves.
    explicit_edge = tick_config.transitions.get("Backlog", "InProgress")
    assert explicit_edge is not None
    assert explicit_edge.prompt is not None
    assert "/implement:phase" in explicit_edge.prompt


def test_malformed_transitions_yaml_raises_at_build_tick_config() -> None:
    """A malformed ``transitions.yml`` raises ``ValueError`` at wiring time (fail-closed)."""
    config = WiringConfig(
        token="dummy",
        project_id="PVT_test",
        repo="owner/repo",
        clone_dir="/tmp/clone",
        columns_yaml=_COLUMNS_YAML,
        transitions_yaml="garbage: [not valid transitions yaml",
    )

    with pytest.raises(ValueError):
        build_tick_config(config)


def test_build_deps_wires_repo_to_deps() -> None:
    """``build_deps`` threads ``config.repo`` into ``Deps.repo`` so ``RunScriptAction``'s
    ``KANBAN_REPO`` env is populated (phase 12.9)."""
    config = _make_config()

    deps = build_deps(config)

    assert isinstance(deps, Deps)
    assert deps.repo == "owner/repo"


def test_build_deps_threads_config_dir_to_deps() -> None:
    """``build_deps`` threads ``config.config_dir`` onto ``Deps.config_dir`` so the launch can
    provision skills/commands/agents into each worktree (phase 14.6)."""
    config = WiringConfig(
        token="dummy",
        project_id="PVT_test",
        repo="owner/repo",
        clone_dir="/tmp/clone",
        columns_yaml=_COLUMNS_YAML,
        config_dir="/tmp/clone/.claude",
    )

    deps = build_deps(config)

    assert deps.config_dir == "/tmp/clone/.claude"


def test_build_deps_default_config_dir_is_empty() -> None:
    """A ``WiringConfig`` without ``config_dir`` yields an empty ``Deps.config_dir`` (provisioning
    disabled) — back-compat with existing constructions."""
    deps = build_deps(_make_config())

    assert deps.config_dir == ""


class TestDefaultsThreading:
    """Tests that ``build_tick_config`` threads the AUTHORITATIVE transitions.yml defaults (#4)."""

    def test_defaults_land_on_tick_config(self) -> None:
        """Both ``concurrency_cap`` and ``move_rate_limit_per_hour`` land on ``TickConfig``."""
        config = _make_config()

        tick_config = build_tick_config(config)

        # No transitions.yml → the default fallback whitelist's cap/rate (3/10) are authoritative.
        assert tick_config.concurrency_cap == 3
        assert tick_config.move_rate_limit_per_hour == 10

    def test_transitions_yaml_defaults_are_authoritative(self) -> None:
        """#4: transitions.yml's ``defaults:`` block is the source of truth for cap + rate.

        Before #4 the wiring read these off columns.yml, so the rendered transitions.yml defaults
        block was DEAD CONFIG. Now an operator editing transitions.yml takes effect.
        """
        transitions_yaml = (
            "project: owner/repo\n"
            "defaults:\n"
            "  concurrency_cap: 6\n"
            "  move_rate_limit_per_hour: 15\n"
            "transitions: []\n"
        )
        config = WiringConfig(
            token="dummy",
            project_id="PVT_test",
            repo="owner/repo",
            clone_dir="/tmp/clone",
            columns_yaml=_COLUMNS_YAML,
            transitions_yaml=transitions_yaml,
        )

        tick_config = build_tick_config(config)

        assert tick_config.concurrency_cap == 6
        assert tick_config.move_rate_limit_per_hour == 15

    def test_transitions_yaml_wins_over_columns_yaml_defaults(self) -> None:
        """#4: when BOTH carry a ``defaults:`` block, transitions.yml wins (one authoritative surface)."""
        columns_with_defaults = """defaults:
  concurrency_cap: 9
  move_rate_limit_per_hour: 99
columns:
  - key: Backlog
    name: Backlog
  - key: Done
    name: Done
"""
        transitions_yaml = (
            "project: owner/repo\n"
            "defaults:\n"
            "  concurrency_cap: 6\n"
            "  move_rate_limit_per_hour: 15\n"
            "transitions: []\n"
        )
        config = WiringConfig(
            token="dummy",
            project_id="PVT_test",
            repo="owner/repo",
            clone_dir="/tmp/clone",
            columns_yaml=columns_with_defaults,
            transitions_yaml=transitions_yaml,
        )

        tick_config = build_tick_config(config)

        # transitions.yml (6/15) wins over the columns.yml block (9/99) — the columns block is dead.
        assert tick_config.concurrency_cap == 6
        assert tick_config.move_rate_limit_per_hour == 15

    def test_absent_defaults_block_yields_defaults_3_10(self) -> None:
        """No transitions.yml → the default fallback whitelist's cap/rate (3/10) are used."""
        config = _make_config()

        tick_config = build_tick_config(config)

        assert tick_config.concurrency_cap == 3
        assert tick_config.move_rate_limit_per_hour == 10
