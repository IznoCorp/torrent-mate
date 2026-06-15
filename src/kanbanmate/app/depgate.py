"""Imperative-shell resolver for the hybrid dependency gate (#13, DESIGN §9).

Extracted from :mod:`kanbanmate.app.tick` (tick.py was at the 1000-LOC hard ceiling once the
17.4 rollback-bookkeeping / teardown-reset wiring landed; the dependency-gate resolver is a
cohesive, self-contained seam that lifts out cleanly). The resolver turns the PURE tri-state
:class:`~kanbanmate.core.dependency_gate.DependencyVerdict` into a final ``(ready, reason)`` by
resolving only the UNKNOWN (off-board) deps via a LIVE ``issue_state`` probe — keeping that I/O
out of the pure core while preserving the snapshot-primary perf property.

Layering: ``app`` may import ``core``, ``ports`` and ``adapters`` (DESIGN §3.2); this module names
only the pure verdict value object plus the adapter bundle (:class:`~kanbanmate.app.actions.Deps`).
"""

from __future__ import annotations

import logging

from kanbanmate.app.actions import Deps
from kanbanmate.core.dependency_gate import DependencyVerdict

logger = logging.getLogger(__name__)


def resolve_dependency_gate(verdict: DependencyVerdict, deps: Deps) -> tuple[bool, str]:
    """Resolve the tri-state dependency verdict into a final ``(ready, reason)`` (#13).

    Snapshot-primary, live-fallback, fail-soft (DESIGN §9). The pure
    :class:`~kanbanmate.core.dependency_gate.DependencyVerdict` already decided every
    on-board dep; this imperative helper only resolves the UNKNOWN (off-board) deps it
    could not — keeping the I/O out of the pure core:

    * **Hard block** when ``verdict.met`` is ``False`` (an on-board dep is not done):
      no live query can satisfy it, so return immediately (ZERO ``issue_state`` calls).
    * **Fast pass** when ``verdict.unresolved`` is empty: the snapshot fully decided the
      gate (the perf property — ZERO queries in the common all-on-board case).
    * **Live fallback** for each unresolved dep: ``issue_state(n)`` CLOSED → that dep is
      MET; OPEN → UNMET. The launch proceeds iff EVERY unresolved dep resolves CLOSED.
      A throwing/slow ``issue_state`` leaves the dep UNMET (fail-soft — never launch on
      an undecidable dep). Each call inherits the client's connect+read timeouts.

    Args:
        verdict: The pure tri-state verdict from
            :func:`~kanbanmate.core.dependency_gate.evaluate`.
        deps: The injected adapter bundle; ``deps.board_reader.issue_state`` is the
            live off-board probe.

    Returns:
        A ``(ready, reason)`` pair: ``ready`` is ``True`` iff the gate is satisfied
        (snapshot + fallback); ``reason`` is a human-readable explanation for the
        block comment / log line.
    """
    # Hard block: an on-board dep is not done — unresolvable by a live query.
    if not verdict.met:
        return False, verdict.reason
    # Common case: the snapshot fully decided the gate — no live query needed.
    if not verdict.unresolved:
        return True, verdict.reason
    # Live fallback ONLY for the off-board (UNKNOWN) deps. Each dep is CLOSED→met /
    # OPEN→unmet; a probe that raises is fail-soft UNMET (conservative).
    still_unmet: list[int] = []
    for number in verdict.unresolved:
        try:
            closed = deps.board_reader.issue_state(number)
        except Exception:  # noqa: BLE001 — fail-soft: an undecidable dep is never launched on
            logger.warning(
                "dependency gate: live issue_state(#%s) failed; treating dep as UNMET", number
            )
            closed = False
        if not closed:
            still_unmet.append(number)
    if still_unmet:
        unmet_str = ", ".join(f"#{n}" for n in still_unmet)
        return False, f"blocked by unmet off-board dependencies (still open): {unmet_str}"
    return True, verdict.reason
