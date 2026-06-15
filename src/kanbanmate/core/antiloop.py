"""Pure anti-loop guard: target-keyed dedup + per-ticket rate limit (DESIGN §3.3).

Ported and adapted from the PoC ``engine/cap.py`` and the ``state.py``
``is_recent_bot_move`` / ``move_count_for_item_last_hour`` pair.  The PoC mixed
two concerns under one filesystem-backed module; here they are distilled into a
*pure* core strategy with the I/O removed:

* **Target-keyed guard** — a move the daemon itself just made into ``target_col``
  is "recent" for :attr:`AntiLoopConfig.recent_ttl` seconds.  Re-acting on it would
  feed an autonomous loop (the daemon reacting to its own writes), so it is blocked.
* **Per-ticket rate limit** — a single ticket may only accumulate
  :attr:`AntiLoopConfig.rate_limit` automatic moves within
  :attr:`AntiLoopConfig.rate_window` seconds.  Beyond that, further moves are blocked
  as a runaway-loop backstop (PoC spec §6).

The module is side-effect-free: callers pass the immutable :class:`AntiLoopState`
and the current ``now`` (a wall-clock / POSIX float); no clock or filesystem is touched
inside the core.  Recording a move returns a *new* state rather than mutating.

**The net is in-memory (#19/#20 — DESIGN §6).** :class:`AntiLoopState` is carried in
:class:`~kanbanmate.app.tick.PersistedState` *in memory only* — a daemon restart wipes it.
That is intentional: the PRIMARY idempotence backstop is the diff-against-persisted-baseline
(a move recorded in persisted state produces no diff next poll, DESIGN §6); this anti-loop
net is the SECONDARY defense-in-depth guard. After a restart the first tick re-syncs from the
board (every card looks like first-contact) and the net rebuilds as moves recur — losing it is
harmless.

**The ``bookkeeping`` flag (#19 PORT — restored for rollback first-classness).** A *rollback*
bounce (phase 12: an un-whitelisted / ``on_fail:rollback`` move that bounces the card BACK to
``from_col``) is a daemon-issued board move that MUST NOT be deduped/re-triggered as a fresh
bot-move, NOR itself be blocked by the recent-target net. :func:`record_move` therefore takes a
``bookkeeping`` flag (port of the PoC ``state.py:117-149`` ``record_bot_move(bookkeeping=...)``):
a bookkeeping move is recorded for the idempotency baseline (its ``(ticket, target)`` recency
marker IS set) but is EXCLUDED from the rate-limit counter feed (only genuine auto-loop moves
count — dovetails with 17.5 #16), and a subsequent identical-target check treats the entry as
"already handled — do not re-trigger" rather than "recently launched — block". For a rollback
the diff-baseline advance (12.8) stays the PRIMARY no-re-trigger mechanism; the bookkeeping tag
is the SECONDARY guard ensuring the net does not fight a legitimate rollback.

**Two distinct move counters — feed them with DAEMON-issued AUTO/bot moves only (#16 KEEP+DOC).**
There are TWO anti-runaway counters, and BOTH count daemon-issued AUTO/bot moves ONLY — NEVER a
human/agent launch, NEVER a bookkeeping move (rollback / park = ``record_bot_move(bookkeeping=True)``
in the PoC):

* this module's in-memory :class:`AntiLoopState` (``move_times`` — fed by :func:`record_move` with
  ``bookkeeping=False``): the SECONDARY defense-in-depth runaway-loop net (DESIGN §6), wiped on
  restart;
* the DURABLE per-issue rate-limit counter ``StateStore.record_move_for_item`` (the PoC
  ``move_rate_limit_per_hour`` backstop, port ``runner.py:504-518``): survives a restart and is what
  parks a runaway ticket / blocks-as-comment.

The DAEMON's AUTO/bot move sites that MUST feed ``record_move_for_item`` are: the
``advance:auto`` move and the within-cap ``on_fail:move`` bounce (both in
:mod:`kanbanmate.app.script_route` — port of the PoC ``_auto_move`` :230-247, which fed the per-item
counter and was NOT anti-loop-recorded) and the reaper's park-in-Blocked (:mod:`kanbanmate.app.reaper`,
guarded so it never runs past the cap). The PoC counted ONLY these auto/bot moves — a human driving
a ticket through the ~7-step flow in one hour NEVER trips the limit; only a runaway AUTO loop does.
EXCLUDED from BOTH counters: a human/agent ``LaunchAction`` (not a daemon auto-move) and any
``bookkeeping`` move (the fix-CI park + the rollback bounce — ``record_move(..., bookkeeping=True)``).
Any FUTURE daemon-issued AUTO/bot ``move_card`` MUST likewise feed ``record_move_for_item`` so the
durable §6 backstop stays accurate.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace

# Defaults mirror the PoC (state.py ``_BOT_MOVE_TTL`` / ``_RATE_WINDOW`` and the
# ``move_rate_limit_per_hour`` transition default).
_DEFAULT_RECENT_TTL = 600.0  # seconds a self-made move stays "recent" (dedup window)
_DEFAULT_RATE_WINDOW = 3600.0  # seconds the per-ticket rate counter spans (1 hour)
_DEFAULT_RATE_LIMIT = 10  # max automatic moves per ticket within the rate window


@dataclass(frozen=True)
class AntiLoopConfig:
    """Tunables for the anti-loop guard.

    Attributes:
        recent_ttl: Seconds during which a move the daemon made into a given
            target column is treated as "recent" and therefore deduplicated.
        rate_window: Sliding-window width, in seconds, over which a ticket's
            automatic moves are counted for the rate limit.
        rate_limit: Maximum number of automatic moves a single ticket may make
            within ``rate_window`` before further moves are blocked.
    """

    recent_ttl: float = _DEFAULT_RECENT_TTL
    rate_window: float = _DEFAULT_RATE_WINDOW
    rate_limit: int = _DEFAULT_RATE_LIMIT


@dataclass(frozen=True)
class AntiLoopState:
    """Immutable record of recent automatic moves, keyed for the two guards.

    Attributes:
        recent_targets: Maps ``(ticket_id, target_col)`` to the timestamp of the
            last automatic move the daemon made into that column for that ticket.
            Powers the target-keyed dedup guard.  A ``bookkeeping`` move (#19,
            e.g. a rollback bounce) sets this marker too — it is "already handled,
            do not re-trigger".
        move_times: Maps ``ticket_id`` to the timestamps of its recent automatic
            moves (any target).  Powers the per-ticket rate limit.  **Bookkeeping
            moves are NOT recorded here** — only a genuine auto-loop move feeds the
            rate-limit counter (#19; the PoC counted auto/bot moves only).
    """

    recent_targets: Mapping[tuple[str, str], float] = field(default_factory=dict)
    move_times: Mapping[str, tuple[float, ...]] = field(default_factory=dict)


def is_blocked(
    state: AntiLoopState,
    ticket_id: str,
    target_col: str,
    *,
    now: float,
    config: AntiLoopConfig | None = None,
) -> bool:
    """Return whether an automatic move of ``ticket_id`` into ``target_col`` is blocked.

    A move is blocked when **either** guard trips:

    1. The daemon already moved this ticket into ``target_col`` within the last
       :attr:`AntiLoopConfig.recent_ttl` seconds (target-keyed dedup).
    2. The ticket has already made :attr:`AntiLoopConfig.rate_limit` or more
       automatic moves within the last :attr:`AntiLoopConfig.rate_window` seconds
       (per-ticket rate limit).

    The function is pure: it reads only ``state`` and the supplied ``now``.

    Args:
        state: The current anti-loop state.
        ticket_id: Stable identifier of the ticket being moved (GraphQL node id).
        target_col: The destination column key of the prospective move.
        now: The current timestamp (wall-clock / POSIX seconds), supplied by
            the caller.
        config: Optional tunables; defaults to :class:`AntiLoopConfig`.

    Returns:
        ``True`` if the move should be blocked, ``False`` if it is permitted.
    """
    cfg = config or AntiLoopConfig()

    # Guard 1 — target-keyed dedup: skip a move we ourselves made recently.
    last_target_ts = state.recent_targets.get((ticket_id, target_col))
    if last_target_ts is not None and (now - last_target_ts) < cfg.recent_ttl:
        return True

    # Guard 2 — per-ticket rate limit over the sliding window.
    recent_moves = sum(
        1 for ts in state.move_times.get(ticket_id, ()) if (now - ts) < cfg.rate_window
    )
    return recent_moves >= cfg.rate_limit


def record_move(
    state: AntiLoopState,
    ticket_id: str,
    target_col: str,
    *,
    now: float,
    bookkeeping: bool = False,
) -> AntiLoopState:
    """Return a new state recording an automatic move into ``target_col``.

    The ``(ticket_id, target_col)`` recency marker is ALWAYS refreshed (the
    target-keyed dedup guard's idempotency baseline). The per-ticket rate-limit
    feed depends on ``bookkeeping``:

    * ``bookkeeping=False`` (default — a genuine auto-loop move, e.g. the reaper's
      move-to-Blocked): ``now`` is appended to the ticket's rate-limit timestamps,
      so the move counts toward the per-ticket rate limit.
    * ``bookkeeping=True`` (#19 — a rollback bounce / anti-double-session revert):
      the move is recorded for the dedup baseline ONLY and is EXCLUDED from the
      rate-limit counter feed (``move_times`` is left unchanged). The PoC counted
      auto/bot moves only (state.py:117-149); a legitimate rollback must not eat
      into the runaway-loop budget, and a later identical-target check treats the
      marker as "already handled — do not re-trigger" rather than "recently
      launched — block" (the recency check returns ``True`` either way, but the
      rate-limit counter is the discriminator).

    The input state is left untouched (the core is immutable).

    Args:
        state: The current anti-loop state.
        ticket_id: Stable identifier of the moved ticket.
        target_col: The destination column key of the move just performed.
        now: The timestamp (wall-clock / POSIX seconds) at which the move
            occurred.
        bookkeeping: When ``True``, record the dedup marker but DO NOT feed the
            per-ticket rate-limit counter (#19, for rollback first-classness).

    Returns:
        A new :class:`AntiLoopState` with the recency marker recorded, and the
        rate-limit timestamp appended only when ``bookkeeping`` is ``False``.
    """
    new_targets = dict(state.recent_targets)
    new_targets[(ticket_id, target_col)] = now

    if bookkeeping:
        # Bookkeeping move (rollback bounce): recorded for the dedup baseline ONLY.
        # Do NOT feed the rate-limit counter — a legitimate rollback must not be
        # counted as a runaway auto-loop move (#19; PoC counted auto/bot moves only).
        return replace(state, recent_targets=new_targets)

    new_times = dict(state.move_times)
    new_times[ticket_id] = (*new_times.get(ticket_id, ()), now)

    return replace(state, recent_targets=new_targets, move_times=new_times)


def forget(state: AntiLoopState, ticket_id: str) -> AntiLoopState:
    """Return a new state with every anti-loop entry for ``ticket_id`` dropped (#22 PORT).

    Pure teardown reset: when a ticket is ABANDONED (the Cancel
    :class:`~kanbanmate.app.actions.TeardownAction` path) its accumulated in-memory
    rate-limit timestamps and recency markers must NOT persist in memory. The PoC's
    exhaustive ``purge_ticket`` (state.py:427-479) ZEROED the on-disk ``moves/``
    history on the Cancel/reset teardown; NEW's rate-limit history lives in this
    volatile in-memory state (no on-disk ``moves`` for it), which ``release_slot``
    cannot reach — so a cancelled ticket's timestamps would otherwise survive until
    the next daemon restart. :func:`forget` is the in-memory analogue: drop every
    ``(ticket_id, *)`` recency marker AND the ticket's ``move_times`` entry.

    **Abandonment-only (matching the PoC).** This fires on the Cancel
    ``TeardownAction`` path ONLY — NOT on the reaper's stale-agent teardown. The
    reaper parks the card in Blocked with ``keep_budgets=True`` (the ticket MAY
    continue), so its in-memory runaway-loop accumulator MUST survive (DESIGN §6);
    the PoC's reaper ``_move_to_blocked`` likewise used the slot-only
    ``release_slot`` and never zeroed ``moves/``. See the NOTE in
    :func:`kanbanmate.app.reaper.reap_stale_agents`.

    The input state is left untouched (the core is immutable); a ticket with no
    recorded entries is a clean no-op (returns an equivalent state).

    Args:
        state: The current anti-loop state.
        ticket_id: The torn-down ticket whose entries to drop.

    Returns:
        A new :class:`AntiLoopState` with every entry keyed on ``ticket_id``
        removed from both indices.
    """
    new_targets = {key: ts for key, ts in state.recent_targets.items() if key[0] != ticket_id}
    new_times = {tid: times for tid, times in state.move_times.items() if tid != ticket_id}
    return replace(state, recent_targets=new_targets, move_times=new_times)
