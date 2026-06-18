"""Parse + look up the per-project transition whitelist (``transitions.yml``).

A transition is keyed by ``(from_col, to_col)``. The dispatcher whitelists moves:
a pair that is present runs its action (prompt and/or script) or is an allowed
no-op (both null); a pair that is ABSENT is rejected (the runner rolls the card
back). Wildcard ``'*'`` matches any column on the unspecified side; an explicit
pair always wins over a wildcard for the same concrete move.

This module is part of the **functional core** — it takes a YAML *string* (not
a path) so it stays I/O-free. Reading the ``transitions.yml`` file off the clone
is the wiring/loader's job (phase 12.9), exactly mirroring how
:func:`~kanbanmate.core.columns.load_columns` takes a string today.

.. important::

   **Divergence from the PoC (load-bearing).** The PoC's ``load_transitions``
   takes a **path** and reads it via ``Path(path).read_text()``
   (``transitions.py:93``). NEW's ``core/`` MUST NOT do I/O (the layering guard
   rejects a ``Path.read_text`` in ``core/``). So NEW splits it:
   ``load_transitions(yaml_text: str)`` parses a STRING (mirroring
   :func:`core.columns.load_columns`), and the wiring (phase 12.9) does the
   ``read_text``.
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

# Allowed ``claude --permission-mode`` values for a launched session (verified
# via ``claude --help`` v2.1.156). The default is "auto" (headless-safe: it never
# hangs and STILL enforces ``permissions.deny``). "bypassPermissions" is
# intentionally absent — it skips the deny layer entirely, which would break
# merge=human-only / no-force-push, so it is BANNED below.
#
# .. note::
#
#    Phase 9's :mod:`kanbanmate.adapters.perms` pins the mode to ``"auto"`` for
#    both profiles but does NOT export a full permission-mode allow-set. This
#    frozenset is the authoritative definition; ``perms.py`` references it
#    implicitly via its ``_PINNED_MODE`` values (which are always ``"auto"``, a
#    member of this set). If ``perms.py`` later needs the allow-set, it should
#    import from here rather than redefine it.
_ALLOWED_PERMISSION_MODES: frozenset[str] = frozenset(
    {"default", "acceptEdits", "auto", "dontAsk", "plan"}
)


@dataclass(frozen=True)
class Transition:
    """A single whitelisted ``(from_col, to_col)`` transition entry.

    Each entry binds a source-destination column pair to its action: a launch
    prompt, a mechanical script, both (script gate then prompt), or neither (an
    allowed no-op). The wildcard ``'*'`` on either side means "any column".
    """

    from_col: str
    """The source column key whose departure triggers this transition."""

    to_col: str
    """The destination column key the card is moved into."""

    profile: str = ""
    """Permission profile name (one of ``"docs"`` / ``"prepare"`` / ``"dev"`` /
    ``"check"``) for the launched agent session. Empty fails loud at launch
    (transitions-only model, DESIGN §8.0.6/§10: no column default, no global
    default)."""

    prompt: str | None = None
    """Launch prompt template (with ``{{placeholders}}``) the agent receives.
    ``None`` means no prompt — the transition is either a script-only action or
    an allowed no-op (both ``prompt`` and ``script`` ``None``)."""

    script: str | None = None
    """Mechanical script to run. On a launch transition this is a pre-launch
    *gate* (run first; launch only on exit 0). On a script-only transition
    (``prompt`` is ``None``) this IS the action. ``None`` when neither gate nor
    script action is configured."""

    advance: str = "stop"
    """Post-action column advance directive. ``"stop"`` means stay in the current
    column; ``"auto:<column>"`` means auto-advance the card to ``<column>`` after
    a successful action (consumed by phase 13)."""

    on_fail: str = ""
    """Failure routing directive. ``""`` means no special handling;
    ``"move:<column>"`` moves the card to ``<column>`` on failure;
    ``"rollback"`` returns the card to ``from_col`` (consumed by phase 13)."""

    permission_mode: str = "auto"
    """The ``claude --permission-mode`` value for the launched agent session.
    Must be a member of :data:`_ALLOWED_PERMISSION_MODES`. Default ``"auto"`` is
    headless-safe — it never hangs on a permission prompt while still enforcing
    the concrete ``permissions.deny`` list."""

    @property
    def has_action(self) -> bool:
        """Return ``True`` if this transition has a prompt or script to run."""
        return bool(self.prompt) or bool(self.script)


def _expand_side(value: object, side: str, raw: object) -> list[str]:
    """Normalise one side (``from`` or ``to``) of a raw entry into column keys.

    A side accepts three shapes: a single ``str`` column key, a ``list[str]`` of
    column keys (expanded into the cartesian product by the caller), or the
    wildcard string ``"*"``. A list is concrete columns ONLY — the bare ``"*"``
    is the wildcard and may NOT appear inside a list, otherwise the wildcard's
    "any column" precedence tier would leak into the explicit table.

    Args:
        value: The raw ``from``/``to`` value as parsed from YAML.
        side: The literal ``"from"`` or ``"to"`` (used only for error messages).
        raw: The full raw entry (used only for error messages).

    Returns:
        A non-empty list of concrete column keys (a single-element list for a
        bare ``str``/``"*"``; the list members for a ``list``).

    Raises:
        ValueError: If the value is an empty list, a list with a non-string or
            empty member, or a list containing the ``"*"`` wildcard.
    """
    # A bare string (concrete column OR the "*" wildcard) is a 1-element set.
    if isinstance(value, str):
        return [value]

    if isinstance(value, list):
        # Fail-CLOSED: an empty list whitelists nothing — almost certainly an
        # authoring error, so reject it rather than silently produce zero edges.
        if not value:
            raise ValueError(f"transitions.yml: empty '{side}' list in entry: {raw!r}")
        for member in value:
            # A list member must be a NON-empty concrete column key. The wildcard
            # belongs on its own (bare "*"), never mixed into a concrete list.
            if not isinstance(member, str) or not member:
                raise ValueError(
                    f"transitions.yml: '{side}' list members must be non-empty "
                    f"strings, got {member!r} in entry: {raw!r}"
                )
            if member == "*":
                raise ValueError(
                    f"transitions.yml: '*' wildcard may not appear inside a "
                    f"'{side}' list (a list is concrete columns) in entry: {raw!r}"
                )
        return value

    raise ValueError(
        f"transitions.yml: '{side}' must be a string, a list of strings, or "
        f"'*', got {value!r} in entry: {raw!r}"
    )


@dataclass(frozen=True)
class TransitionConfig:
    """Parsed ``transitions.yml``: the IMMUTABLE whitelist + parsed defaults.

    The three lookup tables are populated by :func:`load_transitions`; callers
    use :meth:`get` to resolve a concrete move. The config is frozen — once
    parsed it never mutates, so the daemon can hold a single reference for the
    lifetime of the process.
    """

    project: str
    """The ``project:`` header from ``transitions.yml`` (e.g. ``"owner/repo"``).
    Empty string when absent."""

    concurrency_cap: int
    """Maximum concurrent agent sessions across the whole project (defaults-block
    ``concurrency_cap``)."""

    move_rate_limit_per_hour: int = 10
    """Per-item AUTO/bot move rate limit per hour (backstop against runaway
    auto-advance loops). Defaults-block ``move_rate_limit_per_hour``."""

    # Internal lookup tables — populated by load_transitions, not by callers.
    _explicit: dict[tuple[str, str], Transition] | None = None
    _wild_to: dict[str, Transition] | None = None
    _wild_from: dict[str, Transition] | None = None

    def get(self, from_col: str, to_col: str) -> Transition | None:
        """Resolve ``(from, to)`` with wildcard precedence.

        Explicit ``(from, to)`` pair wins over ``(from, *)``, which wins over
        ``(*, to)``. Returns ``None`` when the pair is not whitelisted (the
        caller MUST roll the card back).

        Args:
            from_col: The source column key the card departed.
            to_col: The destination column key the card arrived in.

        Returns:
            The matching :class:`Transition`, or ``None`` if the pair is not
            whitelisted.
        """
        assert self._explicit is not None  # guaranteed post-load_transitions
        assert self._wild_from is not None
        assert self._wild_to is not None

        # Explicit pair wins unconditionally.
        t = self._explicit.get((from_col, to_col))
        if t is not None:
            return t
        # (from, *) — any destination from this source.
        t = self._wild_from.get(from_col)
        if t is not None:
            return t
        # (*, to) — any source into this destination.
        return self._wild_to.get(to_col)

    def launch_target_columns(self) -> frozenset[str]:
        """Return the set of column keys a prompt-bearing transition can launch into.

        These are the destinations (``to_col``) of every PROMPT-bearing transition in
        the whitelist — i.e. every move that fires an agent launch. Used by the
        ticket-create guard (a new card may not be dropped straight into a launch
        column) and as a coarse signal elsewhere. NOTE: the agent ``kanban-move``
        re-fire guard is PAIR-aware (it checks whether the specific ``(from, to)`` pair
        is prompt-bearing, mirroring ``core.intent``), NOT this destination-only set —
        a move INTO a launch-target column from a column that has no prompt-bearing edge
        to it (e.g. ``Merge → Review``) is legitimately allowed.

        Both the explicit pairs and the ``from='*'`` wild-to entries contribute their
        concrete ``to_col``. A ``to='*'`` wild-from entry is **excluded**: it has no
        concrete destination, so it names no single launch-target column (its
        destination is resolved at move time, not statically known here). A
        script-only or no-op transition (no ``prompt``) is also excluded — it launches
        no agent, so its destination is not a launch target. Since the autonomous-merge
        change, the ``Review → Merge`` row is a PROMPT-bearing agent stage, so ``Merge``
        IS a launch target (the merge agent fires when a card lands there).

        Returns:
            The frozen set of column keys that are the destination of at least one
            prompt-bearing whitelisted transition.
        """
        assert self._explicit is not None  # guaranteed post-load_transitions
        assert self._wild_to is not None
        # Explicit prompt-bearing pairs + the (*, to) wild-to prompt entries both name
        # a concrete destination; collect those. (*, to) lives in _wild_to, keyed by
        # to_col, so its destination is the key itself.
        targets = {t.to_col for t in self._explicit.values() if t.prompt}
        targets |= {t.to_col for t in self._wild_to.values() if t.prompt}
        return frozenset(targets)


def load_transitions(yaml_text: str) -> TransitionConfig:
    """Parse a ``transitions.yml`` document string into a :class:`TransitionConfig`.

    The document is expected to contain an optional ``project`` header, an
    optional ``defaults`` mapping (``concurrency_cap``, ``move_rate_limit_per_hour``),
    and a ``transitions`` sequence. Each transition entry must have at least
    ``from`` and ``to`` column keys.

    Each side (``from``/``to``) accepts a single ``str``, a ``list[str]`` of
    concrete column keys, or the wildcard ``"*"``. A list is expanded at load
    into the **cartesian product** of ``(from × to)`` concrete edges — e.g.
    ``[a, b] → [c, d]`` becomes the four explicit entries ``a→c``, ``a→d``,
    ``b→c``, ``b→d`` — each carrying the SAME action fields verbatim. A list is
    pure authoring sugar: an expanded pair is an ordinary **explicit** entry, so
    precedence is unchanged (explicit, incl. list-expanded, > ``(from, *)`` >
    ``(*, to)``; see :meth:`~TransitionConfig.get`).

    Validation is fail-CLOSED: any invalid ``permission_mode``, a ``'*'->'*'``
    wildcard pair, or a **duplicate concrete pair** (two list-expanded and/or
    explicit rows colliding on the same key) aborts the load with a
    :class:`ValueError` — no silent last-wins, and no session ever launches with
    an unvalidated whitelist.

    Args:
        yaml_text: The raw ``transitions.yml`` document as a string.

    Returns:
        A fully populated :class:`TransitionConfig` ready for :meth:`~TransitionConfig.get`
        lookups.

    Raises:
        ValueError: If any entry is missing ``from`` or ``to``; uses a malformed
            ``from``/``to`` list (empty, non-string member, or a ``"*"`` inside a
            list); has a non-string ``permission_mode`` (YAML bool/int/None); uses
            ``bypassPermissions``; specifies an unknown ``permission_mode``; uses
            the ``'*' -> '*'`` wildcard pair; or produces a duplicate concrete
            pair via list expansion and/or overlapping explicit rows.
    """
    data = yaml.safe_load(yaml_text) or {}
    project: str = data.get("project") or ""
    defaults = data.get("defaults") or {}
    # The loader fallback is aligned to the rendered template default of 3 (#4). Before #4 the
    # loader fell back to 2 while the renderer wrote 3 — a confusing asymmetry where a
    # transitions.yml whose ``defaults:`` block was hand-stripped would silently cap at 2, NOT the
    # documented 3. One default, one surface.
    cap: int = int(defaults.get("concurrency_cap", 3))
    move_rate_limit: int = int(defaults.get("move_rate_limit_per_hour", 10))

    explicit: dict[tuple[str, str], Transition] = {}
    wild_to: dict[str, Transition] = {}  # keyed by to_col (from == '*')
    wild_from: dict[str, Transition] = {}  # keyed by from_col (to == '*')

    for raw in data.get("transitions") or []:
        # Every entry MUST declare from and to (the pair is the lookup key).
        if raw.get("from") is None or raw.get("to") is None:
            raise ValueError(f"transitions.yml: entry missing 'from' or 'to': {raw!r}")

        # ── permission_mode validation (fail-CLOSED) ──────────────────────
        permission_mode = raw.get("permission_mode", "auto")

        # 1. Non-string FIRST: YAML coerces ``no``/``yes``/``off`` → bool,
        #    ``5`` → int, ``null`` → None — all of which crash on ``.lower()``.
        if not isinstance(permission_mode, str):
            raise ValueError(
                f"transitions.yml: permission_mode must be a string, got "
                f"{permission_mode!r} (note: YAML turns no/yes/off into "
                f"booleans — quote it)"
            )

        # 2. ``bypassPermissions`` is BANNED — it skips the deny layer entirely,
        #    which would break merge=human-only / no-force-push.
        if "bypass" in permission_mode.lower():
            raise ValueError(
                f"transitions.yml: permission_mode {permission_mode!r} is banned "
                f"(bypassPermissions skips the deny layer)"
            )

        # 3. Unknown mode — not in the allow-set.
        if permission_mode not in _ALLOWED_PERMISSION_MODES:
            raise ValueError(
                f"transitions.yml: unknown permission_mode {permission_mode!r}; "
                f"allowed: {sorted(_ALLOWED_PERMISSION_MODES)}"
            )

        # ── Expand from/to into concrete pairs (cartesian product) ────────
        # A list authors several edges that share one action; a single str/"*"
        # is a 1-element side. The per-pair body below runs UNCHANGED for each
        # concrete pair so all the validation + routing applies identically.
        from_cols = _expand_side(raw["from"], "from", raw)
        to_cols = _expand_side(raw["to"], "to", raw)

        for from_col in from_cols:
            for to_col in to_cols:
                t = Transition(
                    from_col=from_col,
                    to_col=to_col,
                    profile=raw.get("profile", ""),
                    prompt=raw.get("prompt"),
                    script=raw.get("script"),
                    advance=raw.get("advance", "stop"),
                    on_fail=raw.get("on_fail", ""),
                    permission_mode=permission_mode,
                )

                # ── Route into lookup tables ─────────────────────────────
                # Duplicate-pair rejection: each table key may be claimed once.
                # Two list-expanded and/or explicit rows colliding on the same
                # key are a fail-CLOSED error (no silent last-wins), so the
                # whitelist is unambiguous about which action a move triggers.
                if t.from_col == "*" and t.to_col == "*":
                    raise ValueError("transitions.yml: '*'->'*' is not allowed")
                if t.from_col == "*":
                    # Wildcard source — indexed by destination.
                    if t.to_col in wild_to:
                        raise ValueError(f"transitions.yml: duplicate wildcard '*'->{t.to_col!r}")
                    wild_to[t.to_col] = t
                elif t.to_col == "*":
                    # Wildcard destination — indexed by source.
                    if t.from_col in wild_from:
                        raise ValueError(f"transitions.yml: duplicate wildcard {t.from_col!r}->'*'")
                    wild_from[t.from_col] = t
                else:
                    if (t.from_col, t.to_col) in explicit:
                        raise ValueError(
                            f"transitions.yml: duplicate transition {t.from_col!r}->{t.to_col!r}"
                        )
                    explicit[(t.from_col, t.to_col)] = t

    return TransitionConfig(
        project=project,
        concurrency_cap=cap,
        move_rate_limit_per_hour=move_rate_limit,
        _explicit=explicit,
        _wild_to=wild_to,
        _wild_from=wild_from,
    )
