"""App-layer No-Status normalization step (default-status, fail-soft, idempotent).

A ticket's DEFAULT Status is the board's first/entry column (``Backlog`` on the shipped
template). No item may sit in GitHub's "No Status" bucket. When the daemon snapshots an
item that is on the board WITHOUT a Status single-select value, this step AUTO-ASSIGNS it
the default column on that tick, so "No Status" becomes self-healing (the operator no
longer fixes such items by hand).

A statusless item is represented as ``Ticket.column_key == ""`` (the empty string): the
GitHub read maps a null ``fieldValueByName`` to ``""`` (``_parsers``), and the diff/decide
path is a silent dead-end for these items (a recording NOOP that never advances), so today
they sit in No Status forever. This step is the cure: it is wired into the tick AFTER the
snapshot and BEFORE the diff/decide loop, so it pre-seeds the in-memory baseline
(``next_columns``) for any item it heals.

**Design properties** (mirroring :func:`kanbanmate.app.health_reporter.apply_health`):

* **Idempotent.** Only items with ``column_key == ""`` are touched; an item already in any
  column is skipped. Once healed its snapshot column is non-empty next poll, so it is never
  re-written; the same-tick baseline advance also stops the immediately-following diff loop
  acting on it.
* **Fail-soft.** Per-item try/except (one bad card never drops the rest) plus an outer
  try/except so ANY exception is logged WARNING and swallowed — it NEVER raises into
  :func:`kanbanmate.app.tick.tick` or blocks a launch. The normalization is a healing
  side-effect, never load-bearing.
* **Rate-limit-aware.** The move is recorded with ``bookkeeping=True`` (the runaway-loop
  dedup marker only) and does NOT feed ``store.record_move_for_item`` — so a normalization
  never eats into the per-ticket forward-advance or rate-limit budgets the auto-advance /
  fix-CI loops gate on (the same separation the reaper's Blocked-park took, reaper.py).
* **No agent fired.** The default column is the board's first/entry column, which is
  non-triggering: launches ride ``from→to`` transitions (e.g. ``Backlog → Brainstorming``),
  never an arrival INTO the entry column. The baseline-name advance means the next tick's
  diff sees the item already in the default column and emits no transition.

Layering: ``app`` may import ``core`` + ``ports`` + ``adapters`` but MUST NOT import ``cli``
or ``daemon`` (DESIGN §3.2). This module imports only ``core`` types + speaks to GitHub
exclusively through the injected :class:`~kanbanmate.ports.board.BoardWriter` (whose
production ``move_card`` carries its mandatory connect+read timeouts).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kanbanmate.core.antiloop import record_move

if TYPE_CHECKING:  # pragma: no cover - import only for type checking (no runtime cycle)
    from kanbanmate.app.actions import Deps
    from kanbanmate.app.tick import TickConfig
    from kanbanmate.core.antiloop import AntiLoopState
    from kanbanmate.core.domain import BoardSnapshot, Column

logger = logging.getLogger(__name__)


def _default_column(config: TickConfig) -> Column | None:
    """Return the board's first/entry column — the No-Status normalization target.

    The default/entry column is DERIVED, NOT hardcoded: it is the FIRST column in the parsed
    column model, which preserves ``columns.yml`` source order
    (:func:`kanbanmate.core.columns.load_columns` builds an insertion-ordered dict). This is
    strictly more robust than reusing ``config.reset_target`` (a hardcoded ``"Backlog"``
    literal default never overridden by wiring) and honours the "derive the first/default
    column from columns config" constraint — a board whose first column is renamed still works.

    Multi-project: each project's ``TickConfig.columns`` comes from its own clone
    ``columns.yml`` (registry wiring), so this derivation is automatically per-project.

    Args:
        config: The per-tick policy inputs; ``config.columns`` is the order-preserving
            ``{key: Column}`` model.

    Returns:
        The first :class:`~kanbanmate.core.domain.Column`, or ``None`` for an (impossible)
        empty column set — the caller then no-ops fail-soft.
    """
    return next(iter(config.columns.values()), None)


def normalize_default_status(
    deps: Deps,
    config: TickConfig,
    *,
    snapshot: BoardSnapshot,
    next_columns: dict[str, str],
    antiloop: AntiLoopState,
    now: float,
    kill_switch: bool,
) -> AntiLoopState:
    """Auto-assign the default column to every snapshot item with no Status (fail-soft).

    Wholly **fail-soft**: ANY exception is logged WARNING and swallowed — it NEVER raises
    into :func:`kanbanmate.app.tick.tick` or blocks a launch (mirrors
    :func:`kanbanmate.app.health_reporter.apply_health`). Mutates ``next_columns`` in place
    (the baseline advance) and returns the threaded ``antiloop`` (it records its own moves
    for the runaway-loop backstop only — see the module docstring).

    The destination passed to ``move_card`` is the default column's **`.name`** (NOT its
    ``.key``): the writer resolves the destination via ``StatusField.options[column_key]``
    keyed by the GitHub option NAME (``_parsers.parse_status_field``), so a first column
    whose key differs from its name (e.g. key ``ReadyToDev`` / name "Ready to dev") would
    ``KeyError`` if the key were passed. The in-memory baseline records the SAME name the
    snapshot reports next tick (``fieldValueByName.name``), keeping the baseline
    name-consistent so the next diff sees no transition.

    Args:
        deps: The injected adapter bundle — ``deps.board_writer.move_card`` issues the heal.
        config: The per-tick policy inputs; ``config.columns`` derives the default column.
        snapshot: The board snapshot taken this tick (the card→column view to heal).
        next_columns: The in-memory diff baseline (item_id → column name), mutated in place
            so the same-tick diff loop + the next tick both see the healed column.
        antiloop: The threaded anti-loop state; a heal refreshes its target-keyed dedup
            recency marker (runaway backstop) via a ``bookkeeping=True`` move.
        now: The tick's wall-clock (POSIX) time, stamped on the dedup recency marker.
        kill_switch: When ``True`` (``~/.kanban/PAUSE`` active) the daemon makes NO board
            moves (DESIGN §10 floor) — the step records nothing.

    Returns:
        The threaded :class:`~kanbanmate.core.antiloop.AntiLoopState` (a new instance per
        recorded heal, the input otherwise).
    """
    try:
        # Derive the entry column from the (order-preserving) column model; an empty column
        # set yields None → nothing to normalize (fail-soft no-op).
        default = _default_column(config)
        if default is None:
            return antiloop
        for ticket in snapshot.tickets:
            # IDEMPOTENT: an item already in ANY column is left untouched. Only the empty-string
            # (No Status) sentinel is healed, so a re-poll of a healed card never re-writes it.
            if ticket.column_key != "":
                continue
            # Under PAUSE the daemon makes no board moves (DESIGN §10 floor) — leave the item
            # in No Status; a resume heals it on a later tick.
            if kill_switch:
                continue
            try:
                # Reuse the existing move mutation; pass the NAME (not the key) — see the
                # name/key seam note in the docstring.
                deps.board_writer.move_card(ticket.item_id, default.name)
                # Baseline advance (name-consistent with the snapshot's next emission) so the
                # same-tick diff + the next tick both see the item already in the default column.
                next_columns[ticket.item_id] = default.name
                # Runaway-loop backstop ONLY: refresh the target-keyed dedup recency marker but
                # EXCLUDE this heal from the per-ticket forward-advance / rate-limit budgets
                # (bookkeeping=True). A normalization write must not consume the budget the
                # auto-advance / fix-CI loops gate on (the reaper's Blocked-park decision).
                antiloop = record_move(
                    antiloop, ticket.item_id, default.name, now=now, bookkeeping=True
                )
            except Exception:  # noqa: BLE001 — per-item fail-soft: one bad write never drops the rest
                # Leave the baseline UNADVANCED for the failed item so it retries next tick.
                logger.warning(
                    "default-status: assign %s to item %s failed; continuing",
                    default.name,
                    ticket.item_id,
                    exc_info=True,
                )
        return antiloop
    except Exception:  # noqa: BLE001 — healing side-effect only: NEVER raise into the tick / block a launch
        logger.warning(
            "default-status: normalization failed; No-Status items left as-is", exc_info=True
        )
        return antiloop
