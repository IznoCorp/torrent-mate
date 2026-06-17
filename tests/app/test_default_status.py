"""Tests for the No-Status normalization step (:mod:`kanbanmate.app.default_status`).

The step heals every snapshot item with no Status (``column_key == ""``) into the board's
first/entry column, derived from the column model (NOT hardcoded). The contract:
idempotent (an item already in a column is untouched), fail-soft (a write error is logged +
swallowed, never raised into the tick), rate-limit-aware (the heal is a ``bookkeeping=True``
move excluded from the forward-advance budget), multi-project (per-project column + writer),
and never fires an agent (the entry column is non-triggering — verified end-to-end via
:func:`~kanbanmate.app.tick.tick`).
"""

from __future__ import annotations

from kanbanmate.app.actions import Deps
from kanbanmate.app.default_status import _default_column, normalize_default_status
from kanbanmate.app.tick import TickConfig
from kanbanmate.core.antiloop import AntiLoopState
from kanbanmate.core.columns import load_columns
from kanbanmate.core.domain import BoardSnapshot, Ticket

# A board whose first column NAME differs from its KEY, so a test can prove the heal targets the
# NAME (what ``move_card`` resolves against) and never the key. ``Entry``/"Inbox" is the entry edge.
_RENAMED_COLUMNS_YAML = """
columns:
  - key: Entry
    name: Inbox
  - key: InProgress
    name: In Progress
"""

# The default board whose first column is ``Backlog`` (key == name) — the live-template shape.
_DEFAULT_COLUMNS_YAML = """
columns:
  - key: Backlog
    name: Backlog
  - key: InProgress
    name: In Progress
"""


class _FakeBoardWriter:
    """A :class:`~kanbanmate.ports.board.BoardWriter` recording ``move_card`` calls.

    Records ``(item_id, column)`` per call so a test can assert the exact heal target. When an
    ``item_id`` is listed in ``raise_for`` the call raises, exercising the per-item fail-soft path.
    """

    def __init__(self, *, raise_for: set[str] | None = None) -> None:
        """Store the optional set of item ids whose ``move_card`` must raise.

        Args:
            raise_for: Item ids for which ``move_card`` raises a ``RuntimeError`` (simulating a
                transient GitHub write failure). Defaults to none (every write succeeds).
        """
        self.moves: list[tuple[str, str]] = []
        self._raise_for = raise_for or set()

    def move_card(self, item_id: str, column_key: str) -> None:
        """Record the move, or raise when ``item_id`` is scripted to fail.

        Args:
            item_id: The card to move.
            column_key: The destination Status option NAME (the heal target).

        Raises:
            RuntimeError: When ``item_id`` is in the configured ``raise_for`` set.
        """
        if item_id in self._raise_for:
            raise RuntimeError(f"simulated move_card failure for {item_id}")
        self.moves.append((item_id, column_key))

    def comment(self, issue_number: int, body: str) -> None:  # noqa: ARG002
        """Unused by the normalization step (recorded only for Protocol completeness)."""
        return None

    def list_issue_comments(self, issue_number: int):  # type: ignore[no-untyped-def]  # noqa: ARG002
        """Unused by the normalization step."""
        return []

    def update_comment(self, comment_id: str, body: str) -> None:  # noqa: ARG002
        """Unused by the normalization step."""
        return None


def _deps(writer: _FakeBoardWriter) -> Deps:
    """Build a :class:`Deps` whose only exercised member is ``board_writer``.

    Every other port is ``None`` cast through ``object`` — the normalization step touches ONLY
    ``deps.board_writer`` (no store, no reader), so the unused ports never resolve.

    Args:
        writer: The fake board writer recording the heals.

    Returns:
        A :class:`Deps` wired with ``writer`` and placeholder ports (never called here).
    """
    placeholder = object()
    return Deps(
        board_writer=writer,  # type: ignore[arg-type]
        board_reader=placeholder,  # type: ignore[arg-type]
        workspace=placeholder,  # type: ignore[arg-type]
        sessions=placeholder,  # type: ignore[arg-type]
        store=placeholder,  # type: ignore[arg-type]
        clock=placeholder,  # type: ignore[arg-type]
        pull_requests=placeholder,  # type: ignore[arg-type]
    )


def _config(yaml_text: str = _DEFAULT_COLUMNS_YAML) -> TickConfig:
    """Build a :class:`TickConfig` from a columns document.

    Args:
        yaml_text: The ``columns.yml`` source defining the column model (and so the derived
            default/entry column — its first entry).

    Returns:
        A :class:`TickConfig` with the parsed column model (other fields at their defaults).
    """
    return TickConfig(columns=load_columns(yaml_text))


def _snapshot(*tickets: Ticket) -> BoardSnapshot:
    """Wrap tickets into a :class:`BoardSnapshot`."""
    return BoardSnapshot(tickets=tuple(tickets), fetched_at=0.0)


def _statusless(item_id: str = "PVTI_1", issue: int | None = 1) -> Ticket:
    """A snapshot item with NO Status (``column_key == ""``) — the heal target."""
    return Ticket(item_id=item_id, issue_number=issue, title="t", column_key="")


# ---------------------------------------------------------------------------
# 1. Statusless item → assigned the default column once
# ---------------------------------------------------------------------------


def test_statusless_item_assigned_default_once() -> None:
    """A No-Status item is moved to the default column exactly once + baseline + dedup marker."""
    writer = _FakeBoardWriter()
    next_columns: dict[str, str] = {}
    out = normalize_default_status(
        _deps(writer),
        _config(),
        snapshot=_snapshot(_statusless()),
        next_columns=next_columns,
        antiloop=AntiLoopState(),
        now=1000.0,
        kill_switch=False,
    )
    # Healed exactly once, to the default column NAME ("Backlog").
    assert writer.moves == [("PVTI_1", "Backlog")]
    # Baseline advanced (name-consistent) so the same-tick diff + next tick see it healed.
    assert next_columns == {"PVTI_1": "Backlog"}
    # The runaway-loop dedup recency marker is present (target-keyed by NAME).
    assert ("PVTI_1", "Backlog") in out.recent_targets


# ---------------------------------------------------------------------------
# 2. Item already in a column is untouched
# ---------------------------------------------------------------------------


def test_item_with_status_untouched() -> None:
    """An item already in a column is skipped — no move, no baseline mutation."""
    writer = _FakeBoardWriter()
    next_columns: dict[str, str] = {}
    in_progress = Ticket(item_id="PVTI_2", issue_number=2, title="t", column_key="In Progress")
    out = normalize_default_status(
        _deps(writer),
        _config(),
        snapshot=_snapshot(in_progress),
        next_columns=next_columns,
        antiloop=AntiLoopState(),
        now=1000.0,
        kill_switch=False,
    )
    assert writer.moves == []
    assert next_columns == {}
    assert out.recent_targets == {}


# ---------------------------------------------------------------------------
# 3. Idempotence across ticks
# ---------------------------------------------------------------------------


def test_idempotent_across_ticks() -> None:
    """Tick 1 heals the item; a tick-2 snapshot (now in the column) makes ZERO moves."""
    cfg = _config()
    writer1 = _FakeBoardWriter()
    next_columns: dict[str, str] = {}
    normalize_default_status(
        _deps(writer1),
        cfg,
        snapshot=_snapshot(_statusless()),
        next_columns=next_columns,
        antiloop=AntiLoopState(),
        now=1000.0,
        kill_switch=False,
    )
    assert writer1.moves == [("PVTI_1", "Backlog")]
    # Tick 2: the board now reports the item in "Backlog" (non-empty), so no heal.
    writer2 = _FakeBoardWriter()
    healed = Ticket(item_id="PVTI_1", issue_number=1, title="t", column_key="Backlog")
    normalize_default_status(
        _deps(writer2),
        cfg,
        snapshot=_snapshot(healed),
        next_columns=next_columns,
        antiloop=AntiLoopState(),
        now=2000.0,
        kill_switch=False,
    )
    assert writer2.moves == []


# ---------------------------------------------------------------------------
# 4. Default-column derivation (renamed first column → NAME, not key)
# ---------------------------------------------------------------------------


def test_default_column_derived_uses_name_not_key() -> None:
    """A renamed first column (key Entry / name Inbox) heals to the NAME — proves no hardcoding."""
    writer = _FakeBoardWriter()
    cfg = _config(_RENAMED_COLUMNS_YAML)
    # The derivation itself returns the first column object.
    default = _default_column(cfg)
    assert default is not None
    assert default.key == "Entry"
    assert default.name == "Inbox"
    next_columns: dict[str, str] = {}
    normalize_default_status(
        _deps(writer),
        cfg,
        snapshot=_snapshot(_statusless()),
        next_columns=next_columns,
        antiloop=AntiLoopState(),
        now=1000.0,
        kill_switch=False,
    )
    # The heal target is the NAME "Inbox", NOT the key "Entry" and NOT a hardcoded "Backlog".
    assert writer.moves == [("PVTI_1", "Inbox")]
    assert next_columns == {"PVTI_1": "Inbox"}


# ---------------------------------------------------------------------------
# 5. Empty column set → no-op
# ---------------------------------------------------------------------------


def test_empty_column_set_is_noop() -> None:
    """An empty column model heals nothing and never raises (fail-soft)."""
    writer = _FakeBoardWriter()
    cfg = TickConfig(columns={})
    assert _default_column(cfg) is None
    next_columns: dict[str, str] = {}
    out = normalize_default_status(
        _deps(writer),
        cfg,
        snapshot=_snapshot(_statusless()),
        next_columns=next_columns,
        antiloop=AntiLoopState(),
        now=1000.0,
        kill_switch=False,
    )
    assert writer.moves == []
    assert next_columns == {}
    assert out.recent_targets == {}


# ---------------------------------------------------------------------------
# 6. Fail-soft on write error
# ---------------------------------------------------------------------------


def test_fail_soft_on_write_error() -> None:
    """One item's write raises; the exception is swallowed, the good item is still healed.

    The failed item's baseline is NOT advanced (so it retries next tick).
    """
    writer = _FakeBoardWriter(raise_for={"PVTI_BAD"})
    bad = _statusless(item_id="PVTI_BAD", issue=10)
    good = _statusless(item_id="PVTI_GOOD", issue=11)
    next_columns: dict[str, str] = {}
    # No raise propagates out of the function.
    out = normalize_default_status(
        _deps(writer),
        _config(),
        snapshot=_snapshot(bad, good),
        next_columns=next_columns,
        antiloop=AntiLoopState(),
        now=1000.0,
        kill_switch=False,
    )
    # The good item is healed; the bad item is absent from both the moves AND the baseline.
    assert writer.moves == [("PVTI_GOOD", "Backlog")]
    assert next_columns == {"PVTI_GOOD": "Backlog"}
    assert ("PVTI_BAD", "Backlog") not in out.recent_targets


# ---------------------------------------------------------------------------
# 7. Rate-limit budget untouched (bookkeeping move; no forward-advance feed)
# ---------------------------------------------------------------------------


def test_rate_limit_budget_untouched() -> None:
    """The heal records a bookkeeping move: dedup marker yes, per-ticket rate-limit feed no.

    Also guards (via the placeholder store) that ``record_move_for_item`` is never called —
    the placeholder ``object()`` store would ``AttributeError`` if the step touched it.
    """
    writer = _FakeBoardWriter()
    next_columns: dict[str, str] = {}
    out = normalize_default_status(
        _deps(writer),
        _config(),
        snapshot=_snapshot(_statusless()),
        next_columns=next_columns,
        antiloop=AntiLoopState(),
        now=1000.0,
        kill_switch=False,
    )
    # bookkeeping=True: the dedup recency marker IS set ...
    assert ("PVTI_1", "Backlog") in out.recent_targets
    # ... but the per-ticket rate-limit timestamp feed (move_times) is EXCLUDED.
    assert out.move_times == {}


# ---------------------------------------------------------------------------
# 8. PAUSE / kill-switch → no move
# ---------------------------------------------------------------------------


def test_kill_switch_suppresses_heal() -> None:
    """Under PAUSE the daemon makes no board moves; the item stays in No Status."""
    writer = _FakeBoardWriter()
    next_columns: dict[str, str] = {}
    out = normalize_default_status(
        _deps(writer),
        _config(),
        snapshot=_snapshot(_statusless()),
        next_columns=next_columns,
        antiloop=AntiLoopState(),
        now=1000.0,
        kill_switch=True,
    )
    assert writer.moves == []
    assert next_columns == {}
    assert out.recent_targets == {}


# ---------------------------------------------------------------------------
# 9. Multi-project: each statusless item heals to ITS project's first column via ITS writer
# ---------------------------------------------------------------------------


def test_multi_project_per_project_default() -> None:
    """Two projects with different first columns + different writers heal independently."""
    writer_a = _FakeBoardWriter()
    writer_b = _FakeBoardWriter()
    cfg_a = _config(_DEFAULT_COLUMNS_YAML)  # entry column "Backlog"
    cfg_b = _config(_RENAMED_COLUMNS_YAML)  # entry column "Inbox"
    next_a: dict[str, str] = {}
    next_b: dict[str, str] = {}
    normalize_default_status(
        _deps(writer_a),
        cfg_a,
        snapshot=_snapshot(_statusless(item_id="A1", issue=1)),
        next_columns=next_a,
        antiloop=AntiLoopState(),
        now=1000.0,
        kill_switch=False,
    )
    normalize_default_status(
        _deps(writer_b),
        cfg_b,
        snapshot=_snapshot(_statusless(item_id="B1", issue=2)),
        next_columns=next_b,
        antiloop=AntiLoopState(),
        now=1000.0,
        kill_switch=False,
    )
    # Project A healed to its own entry column via its own writer; no cross-talk.
    assert writer_a.moves == [("A1", "Backlog")]
    assert writer_b.moves == [("B1", "Inbox")]
    assert next_a == {"A1": "Backlog"}
    assert next_b == {"B1": "Inbox"}
