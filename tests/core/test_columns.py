"""Tests for pure column-class resolution in :mod:`kanbanmate.core.columns`.

Covers the two non-launch column classes (DESIGN §8.0.6: REACTIVE / INERT — no
AGENT) resolving correctly from the single ``action: teardown`` flag, error
handling on malformed input, and a round-trip of the shipped
``kanbanmate/assets/columns.yml.tmpl`` default template, loaded as package data
via :mod:`importlib.resources` (the wheel-installability guard). In the
transitions-only model the template is a BARE column set: ``columns.yml`` carries
no launch config (``triggers_agent`` / ``permission_profile`` / ``interactive_only``
/ ``prompt``) — that all lives on the transition.
"""

from __future__ import annotations

import importlib.resources

import pytest

from kanbanmate.core.columns import BoardDefaults, load_board_defaults, load_columns
from kanbanmate.core.domain import ColumnClass

# The bundled default template, resolved as package data (a wheel / editable
# install ships it under ``kanbanmate/assets``), NOT a repo-relative path.
_TEMPLATE_RESOURCE = importlib.resources.files("kanbanmate") / "assets" / "columns.yml.tmpl"


def _template_text() -> str:
    """Return the bundled ``columns.yml`` template text (package data)."""
    return _TEMPLATE_RESOURCE.read_text(encoding="utf-8")


class TestResolveClass:
    """Resolution of the two non-launch column classes (DESIGN §8.0.6) from YAML flags."""

    def test_reactive_column(self) -> None:
        """``action: teardown`` resolves to ``ColumnClass.REACTIVE``."""
        columns = load_columns(
            "columns:\n  - key: Cancel\n    name: Cancel\n    action: teardown\n"
        )
        assert columns["Cancel"].column_class is ColumnClass.REACTIVE

    def test_inert_column(self) -> None:
        """A column with no ``action`` flag resolves to ``ColumnClass.INERT``."""
        columns = load_columns("columns:\n  - key: Done\n    name: Done\n")
        assert columns["Done"].column_class is ColumnClass.INERT

    def test_triggers_agent_flag_is_ignored(self) -> None:
        """``triggers_agent`` is a removed launch field — a column carrying it stays INERT.

        In the transitions-only model (§8.0.6) the launch lives on the transition,
        never on a column; the loader does not read ``triggers_agent`` at all, so it
        cannot promote a column to a (now non-existent) AGENT class.
        """
        columns = load_columns(
            "columns:\n  - key: InProgress\n    name: In Progress\n    triggers_agent: true\n"
        )
        assert columns["InProgress"].column_class is ColumnClass.INERT


class TestLoadColumns:
    """Structural behaviour of :func:`load_columns`."""

    def test_preserves_order(self) -> None:
        """The output mapping preserves the source document order."""
        columns = load_columns(
            "columns:\n"
            "  - key: A\n    name: Alpha\n"
            "  - key: B\n    name: Beta\n"
            "  - key: C\n    name: Gamma\n"
        )
        assert list(columns.keys()) == ["A", "B", "C"]

    def test_carries_name(self) -> None:
        """The human-readable name is carried through unchanged."""
        columns = load_columns("columns:\n  - key: ReadyToDev\n    name: Ready to dev\n")
        assert columns["ReadyToDev"].name == "Ready to dev"

    def test_rejects_non_mapping_document(self) -> None:
        """A document that is not a mapping is rejected."""
        with pytest.raises(ValueError, match="top-level 'columns'"):
            load_columns("- just\n- a\n- list\n")

    def test_rejects_missing_columns_sequence(self) -> None:
        """A document without a ``columns`` sequence is rejected."""
        with pytest.raises(ValueError, match="'columns' sequence"):
            load_columns("other: value\n")

    def test_rejects_entry_without_key(self) -> None:
        """An entry missing ``key`` is rejected."""
        with pytest.raises(ValueError, match="non-empty 'key'"):
            load_columns("columns:\n  - name: No Key\n")

    def test_rejects_entry_without_name(self) -> None:
        """An entry missing ``name`` is rejected."""
        with pytest.raises(ValueError, match="non-empty 'name'"):
            load_columns("columns:\n  - key: NoName\n")


class TestLaunchFieldsIgnored:
    """The removed launch fields (DESIGN §8.0.6) are not parsed onto the Column.

    ``columns.yml`` is a bare set in the transitions-only model. A column carrying
    legacy launch keys still LOADS (forward-compat for stale files) but the keys are
    inert: the :class:`Column` exposes no ``triggers_agent`` / ``permission_profile``
    / ``interactive_only`` attribute and the column resolves to INERT.
    """

    def test_legacy_launch_keys_are_ignored(self) -> None:
        """A column carrying every legacy launch key loads to a bare INERT Column."""
        columns = load_columns(
            "columns:\n"
            "  - key: InProgress\n"
            "    name: In Progress\n"
            "    triggers_agent: true\n"
            "    permission_profile: dev\n"
            "    interactive_only: true\n"
        )
        column = columns["InProgress"]
        assert column.column_class is ColumnClass.INERT
        # The launch fields were removed from the domain model entirely.
        assert not hasattr(column, "permission_profile")
        assert not hasattr(column, "interactive_only")


class TestDefaultTemplate:
    """The shipped default template round-trips through :func:`load_columns`.

    The template is read as **package data** via :mod:`importlib.resources`, so
    these tests double as the wheel-installability guard: they exercise exactly
    the path a ``pip``-installed engine takes to find ``columns.yml.tmpl``.
    """

    def test_template_is_loadable_package_data(self) -> None:
        """The default template ships as loadable ``kanbanmate`` package data."""
        # ``is_file`` on a Traversable proves the resource exists in the package
        # (the wheel-installability guard), not merely in the source tree.
        assert _TEMPLATE_RESOURCE.is_file()
        assert _template_text().strip() != ""

    def test_template_parses_to_fourteen_columns(self) -> None:
        """The default board has exactly 14 columns (genesis phase 26).

        The front of the flow gained ``Brainstorming`` (after Backlog) and ``Plan``
        (after Spec), splitting the former single brainstorm+design step so only one
        step is interactive. That brings the board from 12 to 14 columns.
        """
        columns = load_columns(_template_text())
        assert len(columns) == 14

    def test_template_includes_brainstorming_and_plan(self) -> None:
        """The board ships ``Brainstorming`` (after Backlog) and ``Plan`` (after Spec).

        Both are inert: the launch lives on the inbound transition, not the column.
        ``Brainstorming`` is the one interactive stage; ``Plan`` is autonomous.
        """
        columns = load_columns(_template_text())
        keys = list(columns.keys())
        assert "Brainstorming" in keys
        assert "Plan" in keys
        assert columns["Brainstorming"].name == "Brainstorming"
        assert columns["Plan"].name == "Plan"
        assert columns["Brainstorming"].column_class is ColumnClass.INERT
        assert columns["Plan"].column_class is ColumnClass.INERT
        # Flow order: Backlog < Brainstorming < Spec < Plan < Planned.
        assert keys.index("Backlog") < keys.index("Brainstorming") < keys.index("Spec")
        assert keys.index("Spec") < keys.index("Plan") < keys.index("Planned")

    def test_template_includes_prepare_feature(self) -> None:
        """The board ships a ``PrepareFeature`` inert column.

        It sits between ``ReadyToDev`` and ``InProgress`` (the create-branch stage).
        In the transitions-only model every column is inert except the reactive
        Cancel — the launch lives on the ``ReadyToDev → PrepareFeature`` transition.
        """
        columns = load_columns(_template_text())
        keys = list(columns.keys())
        assert "PrepareFeature" in keys
        assert columns["PrepareFeature"].name == "Prepare feature"
        assert columns["PrepareFeature"].column_class is ColumnClass.INERT
        # Placed between ReadyToDev and InProgress in display order.
        assert keys.index("ReadyToDev") < keys.index("PrepareFeature") < keys.index("InProgress")

    def test_template_former_agent_columns_are_inert(self) -> None:
        """In Progress, PR/CI and Review carry NO launch class — they are plain INERT (§8.0.6).

        In the transitions-only model these stages launch at their inbound
        transitions; the columns themselves are bare and inert.
        """
        columns = load_columns(_template_text())
        for key in ("InProgress", "PRCI", "Review"):
            assert columns[key].column_class is ColumnClass.INERT, key

    def test_template_reactive_column(self) -> None:
        """Cancel is the single reactive (teardown) column."""
        columns = load_columns(_template_text())
        reactive_keys = {k for k, c in columns.items() if c.column_class is ColumnClass.REACTIVE}
        assert reactive_keys == {"Cancel"}

    def test_template_carries_no_launch_fields(self) -> None:
        """The shipped ``columns.yml.tmpl`` is a BARE set — no launch config (§8.0.6).

        The raw template text must contain none of the removed launch keys
        (``triggers_agent`` / ``permission_profile`` / ``interactive_only`` /
        ``prompt:``) — they all live on the transition now. The loaded Column model
        likewise exposes no launch attributes (guaranteed by the domain model).
        """
        text = _template_text()
        for forbidden in ("triggers_agent", "permission_profile", "interactive_only", "prompt:"):
            assert forbidden not in text, forbidden
        columns = load_columns(text)
        sample = columns["InProgress"]
        assert not hasattr(sample, "permission_profile")
        assert not hasattr(sample, "interactive_only")
        # Cancel remains the single reactive column.
        assert columns["Cancel"].column_class is ColumnClass.REACTIVE

    def test_template_inert_columns(self) -> None:
        """All columns except the reactive Cancel are inert (human gates / terminals)."""
        columns = load_columns(_template_text())
        inert_keys = {k for k, c in columns.items() if c.column_class is ColumnClass.INERT}
        assert inert_keys == {
            "Backlog",
            "Brainstorming",
            "Spec",
            "Plan",
            "Planned",
            "ReadyToDev",
            "PrepareFeature",
            "InProgress",
            "PRCI",
            "Review",
            "Merge",
            "Done",
            "Blocked",
        }


class TestLoadBoardDefaults:
    """Tests for :func:`load_board_defaults` — the board-wide defaults block parser."""

    def test_explicit_defaults_block(self) -> None:
        """An explicit ``defaults:`` block is parsed into a ``BoardDefaults``."""
        defaults = load_board_defaults(
            "defaults:\n"
            "  concurrency_cap: 5\n"
            "  move_rate_limit_per_hour: 20\n"
            "columns:\n"
            "  - key: Done\n"
            "    name: Done\n"
        )
        assert isinstance(defaults, BoardDefaults)
        assert defaults.concurrency_cap == 5
        assert defaults.move_rate_limit_per_hour == 20

    def test_absent_defaults_block_yields_dataclass_defaults(self) -> None:
        """An absent ``defaults:`` block yields the ``BoardDefaults`` dataclass defaults (3 / 10)."""
        defaults = load_board_defaults("columns:\n  - key: Done\n    name: Done\n")
        assert defaults.concurrency_cap == 3
        assert defaults.move_rate_limit_per_hour == 10

    def test_partial_defaults_block_falls_back(self) -> None:
        """A ``defaults:`` block with only one key fills the other from the dataclass default."""
        defaults = load_board_defaults(
            "defaults:\n  concurrency_cap: 7\ncolumns:\n  - key: Done\n    name: Done\n"
        )
        assert defaults.concurrency_cap == 7
        assert defaults.move_rate_limit_per_hour == 10  # default

    def test_non_mapping_document_yields_all_defaults(self) -> None:
        """A document that is not a mapping at all falls back to all defaults."""
        defaults = load_board_defaults("- just a list\n")
        assert defaults.concurrency_cap == 3
        assert defaults.move_rate_limit_per_hour == 10

    def test_non_mapping_defaults_block_yields_all_defaults(self) -> None:
        """A ``defaults:`` key that is not a mapping falls back to all defaults."""
        defaults = load_board_defaults(
            "defaults: not-a-mapping\ncolumns:\n  - key: Done\n    name: Done\n"
        )
        assert defaults.concurrency_cap == 3
        assert defaults.move_rate_limit_per_hour == 10

    def test_non_int_raises_value_error(self) -> None:
        """A non-int value (e.g. a string) raises ``ValueError``."""
        with pytest.raises(ValueError, match="must be a positive integer"):
            load_board_defaults(
                "defaults:\n"
                "  concurrency_cap: five\n"  # string, not int
                "columns:\n"
                "  - key: Done\n"
                "    name: Done\n"
            )

    def test_zero_raises_value_error(self) -> None:
        """A value of ``0`` raises ``ValueError`` (a runaway backstop must not silently accept 0)."""
        with pytest.raises(ValueError, match="must be a positive integer"):
            load_board_defaults(
                "defaults:\n  concurrency_cap: 0\ncolumns:\n  - key: Done\n    name: Done\n"
            )

    def test_negative_raises_value_error(self) -> None:
        """A negative value raises ``ValueError``."""
        with pytest.raises(ValueError, match="must be a positive integer"):
            load_board_defaults(
                "defaults:\n"
                "  move_rate_limit_per_hour: -1\n"
                "columns:\n"
                "  - key: Done\n"
                "    name: Done\n"
            )

    def test_yaml_bool_yes_raises_value_error(self) -> None:
        """A YAML ``yes`` (→ ``True`` in Python, a bool subclass of int) raises ``ValueError``.

        This is the bool-is-int footgun: without the explicit bool guard,
        ``True`` coerces to ``1`` and a dangerous silent default leaks through.
        """
        with pytest.raises(ValueError, match="YAML yes/no"):
            load_board_defaults(
                "defaults:\n  concurrency_cap: yes\ncolumns:\n  - key: Done\n    name: Done\n"
            )

    def test_yaml_bool_no_raises_value_error(self) -> None:
        """A YAML ``no`` (→ ``False`` → ``0``) raises ``ValueError``."""
        with pytest.raises(ValueError, match="YAML yes/no"):
            load_board_defaults(
                "defaults:\n"
                "  move_rate_limit_per_hour: no\n"
                "columns:\n"
                "  - key: Done\n"
                "    name: Done\n"
            )

    def test_template_round_trips_to_documented_values(self) -> None:
        """The shipped ``columns.yml.tmpl`` round-trips to the documented defaults (3 / 10)."""
        defaults = load_board_defaults(_template_text())
        assert defaults.concurrency_cap == 3
        assert defaults.move_rate_limit_per_hour == 10
