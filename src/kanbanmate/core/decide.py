"""Pure decision function: a transition plus context yields an Action.

This is the policy core of the daemon (DESIGN §3.1, §8).  Given a single
:class:`~kanbanmate.core.domain.Transition`, the column model, and a context
object carrying the anti-loop state and runtime flags, :func:`decide` chooses
exactly one :class:`~kanbanmate.core.domain.Action` describing what the
imperative shell should do.

The function is **pure**: it reads only its arguments and never touches a clock
or the filesystem.  The current time is supplied through
:class:`DecideContext.now`, and the anti-loop verdict is obtained by calling
:func:`kanbanmate.core.antiloop.is_blocked` with that injected ``now``.

**Transitions-only model (DESIGN §8.0.6, genesis phase 20).** The agent launches
**at the transition** ``(from, to)`` — never at a column. ``transitions.yml`` is
the SOLE trigger model; ``columns.yml`` carries NO launch configuration. There is
no per-column autonomy gate, no dormant stage, and no destination-only
column-class fallback. A :class:`~kanbanmate.core.transitions.TransitionConfig`
whitelist is **always** supplied (the daemon falls back to the built-in
``DEFAULT_TRANSITIONS`` when a board ships no ``transitions.yml`` — see
:mod:`kanbanmate.app.wiring`), so ``ctx.transitions`` must never be ``None``.

Decision rules (DESIGN §8.0.3 verdicts + §8.0.6 transitions-only), in fixed
precedence so each transition maps to exactly one action:

1. a **reactive → backlog** transition (Cancel → Backlog) → :attr:`ActionKind.RESET`;
2. the destination is a **reactive** column (e.g. Cancel) → :attr:`ActionKind.TEARDOWN`;
3. the concrete ``(from, to)`` move is classified against the whitelist (a faithful
   port of the PoC ``decide_transition``):

   * the pair is **absent** from the whitelist → :attr:`ActionKind.ROLLBACK`
     (bounce the card back to ``from_col``); but a **first-contact** item
     (``from_column is None``) has no origin to bounce to, so it falls through to
     :attr:`ActionKind.NOOP`;
   * the pair is whitelisted with **no action** (neither prompt nor script) →
     :attr:`ActionKind.NOOP`;
   * the pair carries a **script but no prompt** → :attr:`ActionKind.RUN_SCRIPT`;
   * the pair carries a **prompt** (optionally script-gated) → :attr:`ActionKind.LAUNCH`
     **unconditionally** — PoC parity: every whitelisted prompt-transition launches
     an interactive, resumable agent. There is no destination-column-class check;
4. the anti-loop guard trips for the destination **or** the kill-switch is set →
   :attr:`ActionKind.BLOCK` (these guards take precedence over LAUNCH).

The destination/origin columns are resolved from the transition's column tokens
via :func:`kanbanmate.core.columns.resolve_column` (name preferred, key fallback)
so the GitHub adapter's Status option NAMES classify correctly against the
key-indexed column model — and, crucially, so a whitelist authored in column
**keys** matches a board move authored in column **names**.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kanbanmate.core.antiloop import AntiLoopConfig, AntiLoopState, is_blocked
from kanbanmate.core.columns import resolve_column
from kanbanmate.core.domain import Action, ActionKind, Column, ColumnClass, Transition
from kanbanmate.core.transitions import TransitionConfig

# The default column a Cancel → reset transition returns the ticket to (DESIGN
# §8.2 / §9). The reset target is configurable so non-default boards can rename
# their entry column, but the engine ships pointing at ``Backlog``.
DEFAULT_RESET_TARGET = "Backlog"


@dataclass(frozen=True)
class DecideContext:
    """Immutable runtime context the decision rules need.

    Bundling these into one frozen object keeps :func:`decide` a two-positional
    function (transition, columns) plus a single context, and makes the pure
    boundary explicit: everything time- or state-dependent enters through here.

    Attributes:
        antiloop_state: The current anti-loop state, consulted via
            :func:`kanbanmate.core.antiloop.is_blocked` to suppress runaway loops
            and the daemon reacting to its own moves.
        kill_switch: When ``True`` (the ``~/.kanban/PAUSE`` kill-switch is
            present), every launch-class decision is downgraded to
            :attr:`ActionKind.BLOCK` and no agent is started.
        now: The current timestamp (POSIX seconds), injected so the function
            stays pure; forwarded to the anti-loop guard's sliding windows.
        reset_target: The inert column key a reactive (Cancel) card must move
            back into to count as a reset.  Defaults to ``Backlog``.
        antiloop_config: Optional anti-loop tunables; defaults to the standard
            :class:`AntiLoopConfig`.
        unattended_hours: DEAD for launch-gating (genesis phase 20). The PoC has
            no unattended-window gate — every whitelisted stage launches — so the
            former "launch outside the window → BLOCK" gate was a column-era
            divergence and is REMOVED from the decision rules. The field is kept
            only because the wiring/tick layer still threads it through; nothing
            in :func:`decide` reads it. Slated for full removal once the upstream
            plumbing stops carrying it.
        transitions: The per-(from,to) transition whitelist — the SOLE trigger
            model (DESIGN §8.0.6). It is the source of truth for the
            launch/run_script/noop/rollback split: the concrete resolved-key move
            is looked up via
            :meth:`~kanbanmate.core.transitions.TransitionConfig.get` and
            classified (a port of the PoC ``decide_transition``). A whitelist is
            ALWAYS supplied (the daemon falls back to ``DEFAULT_TRANSITIONS`` when
            a board ships no ``transitions.yml``); ``None`` is a misconfiguration
            and :func:`decide` raises rather than silently degrading.
    """

    antiloop_state: AntiLoopState = field(default_factory=AntiLoopState)
    kill_switch: bool = False
    now: float = 0.0
    reset_target: str = DEFAULT_RESET_TARGET
    antiloop_config: AntiLoopConfig = field(default_factory=AntiLoopConfig)
    unattended_hours: tuple[int, int] | None = None
    transitions: TransitionConfig | None = None


def _reason_for(kind: ActionKind, transition: Transition) -> str:
    """Build a human-readable explanation for a chosen action.

    Args:
        kind: The action kind that was selected.
        transition: The transition being decided on.

    Returns:
        A short audit string naming the ticket, the move, and the verdict.
    """
    move = f"{transition.from_column or '∅'} → {transition.to_column}"
    return f"{kind.value} for #{transition.ticket.issue_number} ({move})"


def _launch_is_blocked(transition: Transition, ctx: DecideContext) -> bool:
    """Return whether any BLOCK guard suppresses a LAUNCH verdict.

    A whitelisted prompt-transition launches unconditionally UNLESS a BLOCK guard
    trips: the anti-loop window has fired (the daemon would react to its own move,
    or a runaway loop), or the kill-switch (``~/.kanban/PAUSE``) is set. Either one
    suppresses the launch; their relative order does not matter since they both
    yield the same BLOCK verdict.

    The kill-switch's "downgrade all profiles to docs" intent is realised
    operatively here — under PAUSE no LaunchAction is ever produced (the daemon
    separately forces the docs profile), so there is nothing to run at an
    elevated profile.

    Args:
        transition: The detected column movement under consideration.
        ctx: The runtime context (anti-loop state, kill-switch, ``now``, …).

    Returns:
        ``True`` when at least one guard trips (the launch must become a BLOCK);
        ``False`` when nothing blocks the launch.
    """
    blocked = is_blocked(
        ctx.antiloop_state,
        transition.ticket.item_id,
        transition.to_column,
        now=ctx.now,
        config=ctx.antiloop_config,
    )
    return ctx.kill_switch or blocked


def decide(transition: Transition, columns: dict[str, Column], ctx: DecideContext) -> Action:
    """Choose the single :class:`Action` a transition warrants.

    The rules are evaluated in a fixed precedence so each transition maps to
    exactly one action (DESIGN §8.0.3 + §8.0.6). The precedence is, in order:

    1. **Reactive routing FIRST.** A card leaving a reactive column (Cancel) back
       to the reset target (Backlog) yields RESET; a card moving INTO a reactive
       column yields TEARDOWN. These mirror the PoC's runner intercepting
       ``(*, Cancel)`` / ``(Cancel, Backlog)`` mechanically *before*
       ``decide_transition``, so they win first — the whitelist never gets to roll
       a Cancel move back.
    2. **Whitelist verdict** (port of the PoC ``decide_transition``). The concrete
       move is looked up on the **resolved column keys** (so a key-authored
       whitelist matches a name-authored board move). An absent pair rolls back
       (except a first-contact ``from_column is None`` item, which has no origin to
       bounce to and falls through to NOOP); a no-action pair is a NOOP; a
       script-only pair is RUN_SCRIPT; a prompt-bearing pair LAUNCHes
       **unconditionally** (PoC parity — there is no destination-column-class gate).
    3. **BLOCK guards.** A LAUNCH verdict is downgraded to BLOCK when the anti-loop
       window or the kill-switch trips.

    Args:
        transition: The detected column movement to decide on.
        columns: The board column model, keyed by column key, used to resolve
            the destination (and origin) columns for the reactive routing.
        ctx: The runtime context (anti-loop state, kill-switch, ``now``, the
            transition whitelist, …).

    Returns:
        Exactly one :class:`Action`; its ``reason`` records why it was chosen.

    Raises:
        ValueError: When ``ctx.transitions`` is ``None``. A whitelist is the SOLE
            trigger model and is always supplied by the wiring (the daemon falls
            back to ``DEFAULT_TRANSITIONS``); a ``None`` here is a wiring bug, and
            the function refuses to silently degrade to a column model (DESIGN
            §8.0.6).
    """
    ticket = transition.ticket
    # Resolve via name-then-key so the GitHub adapter's Status option NAMES (e.g.
    # "In Progress") classify against the key-indexed model (e.g. "InProgress").
    # A bare ``columns.get`` would miss every column whose name != key. The same
    # resolution feeds the whitelist lookup below, so a whitelist authored in keys
    # matches a board move authored in names (the load-bearing column-keying seam).
    destination = resolve_column(columns, transition.to_column)
    origin = (
        resolve_column(columns, transition.from_column)
        if transition.from_column is not None
        else None
    )

    # ── Precedence 1: reactive routing FIRST (KEEP) ──────────────────────────
    # These win before the whitelist (mirroring the PoC runner intercepting
    # (*, Cancel) / (Cancel, Backlog) before decide_transition), so a Cancel move
    # is never rolled back as "un-whitelisted".
    #
    # Reset: leaving a reactive column (Cancel) back to the reset target (Backlog)
    # wipes the ticket so a later agent move starts fresh (DESIGN §8.2). Compare
    # the *resolved* destination's key against the configured reset target so the
    # rule holds whether the transition carries the option NAME (adapter) or the
    # key, mirroring the name/key resolution above.
    if (
        origin is not None
        and origin.column_class is ColumnClass.REACTIVE
        and destination is not None
        and destination.key == ctx.reset_target
    ):
        return Action(
            kind=ActionKind.RESET, ticket=ticket, reason=_reason_for(ActionKind.RESET, transition)
        )

    # Teardown: the destination itself is reactive (e.g. Cancel).
    if destination is not None and destination.column_class is ColumnClass.REACTIVE:
        return Action(
            kind=ActionKind.TEARDOWN,
            ticket=ticket,
            reason=_reason_for(ActionKind.TEARDOWN, transition),
        )

    # ── Precedence 2: whitelist verdict (port of decide_transition) ──────────
    # The whitelist is the SOLE source of truth for the
    # launch/run_script/noop/rollback split (DESIGN §8.0.6). A whitelist is ALWAYS
    # supplied (the daemon falls back to DEFAULT_TRANSITIONS); a ``None`` here is a
    # wiring bug — refuse to silently degrade to a column model.
    if ctx.transitions is None:
        raise ValueError(
            "decide() requires a transition whitelist (ctx.transitions is None); "
            "the wiring must supply DEFAULT_TRANSITIONS when no transitions.yml is present "
            "(DESIGN §8.0.6 — there is no column-class fallback)."
        )

    # Look the move up on the RESOLVED column KEYS (destination.key / origin.key
    # when resolvable, else the raw token) so a key-authored whitelist matches a
    # name-authored board move.
    to_key = destination.key if destination is not None else transition.to_column
    # ``from_column`` is ``None`` for a first-contact item; keep that None so the
    # rollback carve-out below can detect "no origin to bounce to".
    from_key: str | None
    if transition.from_column is None:
        from_key = None
    elif origin is not None:
        from_key = origin.key
    else:
        from_key = transition.from_column

    # ``get`` needs a concrete from key; a first-contact item has none, so it
    # is treated as unlisted (which the carve-out below downgrades to NOOP).
    t = ctx.transitions.get(from_key, to_key) if from_key is not None else None

    if t is None:
        # Un-whitelisted (or absent) pair → bounce the card back to its
        # origin. But a first-contact item (from_column is None ⇒ from_key is
        # None by construction above) has no origin to bounce to — the PoC's
        # webhook had a from=None record+skip leniency; NEW's diff yields
        # from_column=None for a first-seen item — so it falls through to a
        # recording NOOP instead of rolling back. Guarding on ``from_key`` (not
        # ``transition.from_column``) also narrows it to ``str`` for the
        # ROLLBACK bounce target below.
        if from_key is None:
            return Action(
                kind=ActionKind.NOOP,
                ticket=ticket,
                reason=_reason_for(ActionKind.NOOP, transition),
            )
        # ROLLBACK carries the from_col as its bounce target (the load-bearing
        # dual use of Action.to_column, mirroring the PoC Decision.column). The
        # target MUST be the display NAME (defect 2): the board snapshot reports the
        # GitHub option NAME as ``Ticket.column_key``, so a baseline recorded as the
        # stable KEY (e.g. ``InProgress``) never equals the snapshot NAME ("In
        # Progress") and the diff RE-FIRES the rollback every poll — an endless recap
        # comment loop. ``origin.name`` (when the column resolved) makes the move
        # target and the recorded baseline NAME-consistent; ``from_key`` is the
        # fallback only when the column model could not resolve the origin.
        rollback_target = origin.name if origin is not None else from_key
        return Action(
            kind=ActionKind.ROLLBACK,
            ticket=ticket,
            reason=_reason_for(ActionKind.ROLLBACK, transition),
            to_column=rollback_target,
        )

    if not t.has_action:
        # Whitelisted but no action (allowed no-op) → record the column only.
        return Action(
            kind=ActionKind.NOOP,
            ticket=ticket,
            reason=_reason_for(ActionKind.NOOP, transition),
            to_column=to_key,
        )

    if t.script and not t.prompt:
        # Script-only transition — mechanical runner, no LLM. Carry the
        # routing fields for the action layer (12.5) + phase 13 to consume.
        return Action(
            kind=ActionKind.RUN_SCRIPT,
            ticket=ticket,
            reason=_reason_for(ActionKind.RUN_SCRIPT, transition),
            to_column=to_key,
            script=t.script,
            on_fail=t.on_fail,
            advance=t.advance,
            profile=t.profile,
            permission_mode=t.permission_mode,
        )

    # Prompt-bearing transition (optionally script-gated) → LAUNCH, subject only
    # to the BLOCK guards below. PoC parity (DESIGN §8.0.6): a whitelisted prompt
    # ALWAYS launches an interactive, resumable agent — there is NO per-column
    # autonomy gate and NO dormant stage. The launch is a transition concern in
    # full: prompt/profile/permission_mode/script/advance/on_fail all ride along
    # from the matched transition.
    if _launch_is_blocked(transition, ctx):
        return Action(
            kind=ActionKind.BLOCK,
            ticket=ticket,
            reason=_reason_for(ActionKind.BLOCK, transition),
        )
    return Action(
        kind=ActionKind.LAUNCH,
        ticket=ticket,
        reason=_reason_for(ActionKind.LAUNCH, transition),
        to_column=to_key,
        prompt=t.prompt,
        script=t.script,
        on_fail=t.on_fail,
        advance=t.advance,
        profile=t.profile,
        permission_mode=t.permission_mode,
    )
