"""Pure dependency gate: parse ``Depends on #N`` and evaluate against the board.

A ticket may declare blocking dependencies in its issue body using the
convention ``Depends on #N`` (case-insensitive, one or more references).  Before
an agent is launched, the daemon checks every referenced issue is already in a
terminal *done* column (``Done`` or ``Merge`` by default, DESIGN §9).  If any
dependency is unmet, the launch is gated.

This module is **pure**: an issue body string and a snapshot in, a frozen
:class:`DependencyVerdict` out, with **no I/O**.  It imports only :mod:`re` and
:mod:`dataclasses` from the standard library and the domain model from the
KanbanMate core layer.

**Tri-state contract (#13 hybrid gate).**  Each ``Depends on #N`` reference
resolves against the board snapshot to one of three states:

* **MET** — the dependency's card is in a *done* column (``Done``/``Merge``).
* **UNMET** — the dependency's card is on the board but *not* in a done column.
* **UNKNOWN** — the dependency's issue is **absent from the snapshot** (e.g. it
  was closed-as-not-planned or moved off the board), so the snapshot alone
  cannot decide it.

The returned :class:`DependencyVerdict` reports the aggregate over the
*decidable* deps (:attr:`~DependencyVerdict.met`) **plus** the UNKNOWN dep issue
numbers (:attr:`~DependencyVerdict.unresolved`) — it only *reports* which deps
the snapshot cannot decide; it does **not** query GitHub.  The gate is fully
satisfied iff :attr:`~DependencyVerdict.met` is ``True`` **and**
:attr:`~DependencyVerdict.unresolved` is empty (see
:meth:`~DependencyVerdict.fully_met`).  The imperative shell (``app/tick``)
resolves any ``unresolved`` deps via a live ``issue_state`` fallback before
deciding — keeping the I/O out of this pure layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from kanbanmate.core.domain import BoardSnapshot

# Column keys that satisfy a dependency: a dependency is met once its issue has
# reached a terminal "done" column (DESIGN §9: Done is terminal, Merge is the
# human merge gate after which work is complete).
DEFAULT_DONE_COLUMNS: frozenset[str] = frozenset({"Done", "Merge"})

# Matches "Depends on #123" / "depends on #7", tolerant of extra spaces. The
# issue number is captured; the rest of the line is ignored.
_DEPENDS_RE = re.compile(r"depends\s+on\s+#(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class DependencyVerdict:
    """The pure, tri-state outcome of evaluating a ticket's declared dependencies.

    Frozen value object (no I/O, hashable) returned by :func:`evaluate`. It splits
    the verdict into the part the snapshot can decide (:attr:`met`) and the part it
    cannot (:attr:`unresolved`), so the imperative shell can resolve the latter via
    a live ``issue_state`` query (#13 hybrid gate) without this layer ever doing I/O.

    Attributes:
        met: The aggregate over the **decidable** deps. ``True`` when there are no
            dependencies, or every *on-board* dep is in a done column; ``False`` as
            soon as any on-board dep is NOT in a done column (an UNMET dep). It does
            NOT account for the UNKNOWN deps — those are reported in
            :attr:`unresolved` for the caller to resolve. The gate is fully satisfied
            only when ``met`` is ``True`` AND ``unresolved`` is empty
            (:meth:`fully_met`).
        unresolved: The issue numbers of the deps the snapshot could NOT decide
            (UNKNOWN — absent from the board), in first-seen order. Empty when every
            dep was on the board. The caller queries each of these live; an
            undecidable dep must be treated conservatively (never launch on it).
        reason: A human-readable explanation suitable for a sticky comment. It
            enumerates the unmet on-board deps and any unresolved (off-board) deps,
            so the operator sees exactly what gates the launch.
    """

    met: bool
    unresolved: tuple[int, ...] = ()
    reason: str = ""

    def fully_met(self) -> bool:
        """Return ``True`` iff the gate is satisfied by the snapshot ALONE.

        The pure shortcut: no UNMET dep (:attr:`met`) AND no UNKNOWN dep
        (:attr:`unresolved` empty). When this is ``True`` the launch may proceed
        with ZERO live queries (the common all-on-board case — the perf property
        the tick relies on). When it is ``False`` the caller must inspect
        :attr:`met` (a hard block if ``False``) and resolve :attr:`unresolved`
        live before deciding.

        Returns:
            ``True`` when the snapshot alone fully satisfies the gate.
        """
        return self.met and not self.unresolved


def parse_dependencies(issue_body: str) -> list[int]:
    """Extract the issue numbers a body declares it depends on.

    Args:
        issue_body: The raw issue body markdown.  ``None``-safe only insofar as
            the caller passes a string; an empty string yields no dependencies.

    Returns:
        The referenced issue numbers in first-seen order, de-duplicated.
    """
    seen: dict[int, None] = {}
    for match in _DEPENDS_RE.finditer(issue_body):
        seen.setdefault(int(match.group(1)), None)
    return list(seen)


def evaluate(
    issue_body: str,
    snapshot: BoardSnapshot,
    done_columns: frozenset[str] = DEFAULT_DONE_COLUMNS,
) -> DependencyVerdict:
    """Resolve a ticket's declared dependencies against the board (tri-state, PURE).

    Each ``Depends on #N`` reference is resolved against the snapshot by issue
    number into one of three states (see the module docstring): MET (in a done
    column), UNMET (on the board, not done), or UNKNOWN (absent from the snapshot).
    This function is **pure** — it does no I/O. It reports the aggregate over the
    DECIDABLE deps plus the UNKNOWN dep numbers; the imperative shell resolves the
    UNKNOWN deps via a live ``issue_state`` query (#13 hybrid gate).

    Aggregate semantics:

    * No declared dependencies → ``DependencyVerdict(met=True)`` (the conservative
      default is satisfied: nothing gates the launch).
    * Any UNMET dep → ``met=False`` (a hard block; an on-board dep that is not done
      cannot be satisfied by a live query, so the caller need not resolve it).
    * UNKNOWN deps → recorded in ``unresolved`` (``met`` still reflects only the
      on-board deps). The gate is fully met iff ``met`` is ``True`` AND
      ``unresolved`` is empty (:meth:`DependencyVerdict.fully_met`); when
      ``unresolved`` is non-empty the caller must resolve those deps before
      deciding.

    Args:
        issue_body: The issue body to scan for ``Depends on #N`` references.
        snapshot: The current board state, used to look up each dependency's
            column by issue number.
        done_columns: The set of column keys that satisfy a dependency; defaults
            to ``{"Done", "Merge"}`` (DESIGN §9).

    Returns:
        A frozen :class:`DependencyVerdict` carrying the snapshot-decidable
        aggregate (:attr:`~DependencyVerdict.met`), the UNKNOWN dep numbers
        (:attr:`~DependencyVerdict.unresolved`), and a human-readable
        :attr:`~DependencyVerdict.reason`.
    """
    dependencies = parse_dependencies(issue_body)
    if not dependencies:
        return DependencyVerdict(met=True, reason="no declared dependencies")

    # Index the snapshot by issue number once for O(1) lookups below.
    column_by_issue: dict[int, str] = {
        ticket.issue_number: ticket.column_key
        for ticket in snapshot.tickets
        if ticket.issue_number is not None
    }

    unmet: list[str] = []  # on-board deps NOT in a done column (hard block).
    unresolved: list[int] = []  # deps absent from the snapshot (UNKNOWN — caller resolves live).
    for number in dependencies:
        column = column_by_issue.get(number)
        if column is None:
            # UNKNOWN: not on the board. The snapshot cannot decide it — defer to
            # the live fallback rather than treating it as unmet here (#13).
            unresolved.append(number)
        elif column not in done_columns:
            unmet.append(f"#{number} (in {column})")

    met = not unmet
    reason = _build_reason(dependencies, unmet, unresolved)
    return DependencyVerdict(met=met, unresolved=tuple(unresolved), reason=reason)


def _build_reason(
    dependencies: list[int],
    unmet: list[str],
    unresolved: list[int],
) -> str:
    """Compose the human-readable gate reason from the resolved dep partition.

    Args:
        dependencies: All declared dep issue numbers (first-seen order).
        unmet: Pre-formatted descriptions of the on-board, not-done deps.
        unresolved: Issue numbers of the UNKNOWN (off-board) deps.

    Returns:
        A sticky-comment-ready explanation. Enumerates unmet and/or unresolved
        deps when present; otherwise confirms all snapshot-decidable deps are met.
    """
    parts: list[str] = []
    if unmet:
        parts.append("blocked by unmet dependencies: " + ", ".join(unmet))
    if unresolved:
        parts.append(
            "unresolved off-board dependencies (checked live): "
            + ", ".join(f"#{n}" for n in unresolved)
        )
    if parts:
        return "; ".join(parts)
    return "all dependencies satisfied: " + ", ".join(f"#{n}" for n in dependencies)
