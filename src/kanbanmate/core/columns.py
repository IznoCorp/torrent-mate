"""Pure column-class resolution from the ``columns.yml`` model (DESIGN §8.0.6).

This module turns the user-editable ``columns.yml`` board template into the
immutable :class:`~kanbanmate.core.domain.Column` objects the daemon reasons
about.  It is part of the functional core: the only input is a YAML *string*
and the only output is a mapping of column key to :class:`Column`.  No file I/O
happens here — reading the template off disk is the caller's (adapter's) job.

In the transitions-only model (DESIGN §8.0.6) a column carries **no** launch
configuration — the agent launches at the transition, never at a column — so
``columns.yml`` is a bare column SET: ``key`` / ``name`` plus the single
**non-launch** classification flag the architecture still needs:

* ``action: teardown``  -> :attr:`ColumnClass.REACTIVE` (the Cancel teardown)
* neither               -> :attr:`ColumnClass.INERT` (human gate / terminal)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from kanbanmate.core.domain import Column, ColumnClass


def _resolve_class(entry: dict[str, Any]) -> ColumnClass:
    """Resolve the :class:`ColumnClass` of a single column entry (DESIGN §8.0.6).

    A column is either REACTIVE (it declares a mechanical dispatcher side-effect
    via ``action: teardown`` — the Cancel column) or INERT (everything else: a
    human gate or terminal column). There is no launch-related class: the agent
    launches at the transition, never at a column.

    Args:
        entry: The parsed mapping for one column from ``columns.yml``.

    Returns:
        ``REACTIVE`` when ``action`` equals ``"teardown"``, otherwise ``INERT``.
    """
    # A reactive column declares a dispatcher side-effect via ``action``.
    if entry.get("action") == "teardown":
        return ColumnClass.REACTIVE
    return ColumnClass.INERT


def load_columns(yaml_text: str) -> dict[str, Column]:
    """Parse a ``columns.yml`` document into keyed :class:`Column` objects.

    The document is expected to contain a top-level ``columns`` sequence, each
    item a mapping with at least ``key`` and ``name``.  The column class is
    derived from the optional ``action`` flag (see :func:`_resolve_class`):
    ``action: teardown`` → REACTIVE, else INERT.  Parsing is purely functional: a
    YAML string in, an ordered mapping out, with no side effects.

    In the transitions-only model (DESIGN §8.0.6) ``columns.yml`` carries **no**
    launch configuration: ``triggers_agent``, ``permission_profile``,
    ``interactive_only`` and ``prompt`` are not read — the launch lives entirely
    on the ``(from, to)`` transition (``transitions.yml``).

    Args:
        yaml_text: The raw ``columns.yml`` document as a string.

    Returns:
        A mapping of column ``key`` to its :class:`Column`, preserving the order
        of the source document.

    Raises:
        ValueError: If the document is not a mapping, lacks a ``columns``
            sequence, or any entry is missing ``key`` or ``name``.
    """
    document: Any = yaml.safe_load(yaml_text)
    if not isinstance(document, dict):
        raise ValueError("columns.yml must be a mapping with a top-level 'columns' key")

    raw_columns: Any = document.get("columns")
    if not isinstance(raw_columns, list):
        raise ValueError("columns.yml must contain a 'columns' sequence")

    result: dict[str, Column] = {}
    for entry in raw_columns:
        if not isinstance(entry, dict):
            raise ValueError("each column entry must be a mapping")
        key = entry.get("key")
        name = entry.get("name")
        if not isinstance(key, str) or not key:
            raise ValueError("each column entry must have a non-empty 'key'")
        if not isinstance(name, str) or not name:
            raise ValueError(f"column '{key}' must have a non-empty 'name'")
        result[key] = Column(
            key=key,
            name=name,
            column_class=_resolve_class(entry),
        )
    return result


def resolve_column(columns: dict[str, Column], token: str) -> Column | None:
    """Resolve a board column *token* to its :class:`Column`, by name then key.

    The daemon receives a column reference in two shapes that must both land on
    the same model column (the critical name/key seam, DESIGN §8 / §9):

    * the GitHub adapter emits the Status option **NAME** (e.g. ``"In Progress"``)
      as :attr:`~kanbanmate.core.domain.Ticket.column_key`, because that is what
      the Projects v2 ``fieldValueByName`` API returns;
    * configuration, persisted baselines, and the engine's own move targets use
      the stable **key** (e.g. ``"InProgress"``).

    Resolving against the raw ``key``-indexed mapping alone misses every column
    whose ``name`` differs from its ``key`` (``InProgress``/``"In Progress"``,
    ``PRCI``/``"PR/CI"`` in the shipped template), so a real board move would
    never resolve to its model column. This helper bridges that gap by matching on
    **name first** (the adapter's emission, the common production path) and falling
    back to **key** (config / engine / test inputs), keeping the lookup pure (no
    I/O — it only reads its arguments).

    Args:
        columns: The board column model keyed by column key (from
            :func:`load_columns`).
        token: The column reference to resolve — either a Status option name or a
            column key.

    Returns:
        The matching :class:`Column`, or ``None`` when ``token`` matches neither a
        known name nor a known key (an unknown column — the caller should log it
        rather than silently NOOP).
    """
    # Name first: the production path. The adapter emits the GitHub option NAME,
    # so prefer a name match to classify a real board move correctly.
    for column in columns.values():
        if column.name == token:
            return column
    # Key fallback: config/engine/test inputs reference the stable key.
    return columns.get(token)


def resolve_target_column(columns: dict[str, Column], target: str) -> Column:
    """Resolve a caller-supplied ``target`` (a column ``key`` *or* ``name``) to its :class:`Column`.

    Shared by the CLI move path and the ``conduit`` MCP ``move`` tool. The operator/agent may name
    the destination by either its stable ``key`` (e.g. ``"Backlog"``) or its human-readable ``name``
    (e.g. ``"In Progress"``). Both map to the same column.

    Args:
        columns: The loaded column model (keyed by column ``key``).
        target: The destination column, given as a ``key`` or a ``name``.

    Returns:
        The matching :class:`Column`.

    Raises:
        KeyError: When ``target`` matches no column key or name.
    """
    if target in columns:
        return columns[target]
    for column in columns.values():
        if column.name == target:
            return column
    known = ", ".join(sorted(columns)) or "(none)"
    raise KeyError(f"unknown column {target!r}; known columns: {known}")


@dataclass(frozen=True)
class BoardDefaults:
    """Board-wide concurrency and rate-limit knobs (DESIGN §6 / §7).

    OLD carried these per-transition (``transitions.py:57,97``); NEW surfaces
    them once at board level in a ``defaults:`` block inside ``columns.yml`` —
    no second config file needed. Parsed by :func:`load_board_defaults` from the
    same document the column model already loads.

    Attributes:
        concurrency_cap: Max concurrent agent sessions before a launch diverts to
            the queue (DESIGN §7 / gate 13.5). OLD had no literal default (the
            transition REQUIRED it); NEW picks a conservative 3.
        move_rate_limit_per_hour: Max AUTO/bot moves per ticket within the hour
            before the ticket is parked in Blocked (DESIGN §6 / gate 13.6).
            Port of ``transitions.py:97`` default 10.
    """

    concurrency_cap: int = 3
    move_rate_limit_per_hour: int = 10


def _coerce_positive_int(value: Any, key: str, default: int) -> int:
    """Coerce a YAML value to a positive ``int``, rejecting bools.

    bool is a subclass of int in Python, so ``isinstance(True, int)`` is
    ``True`` — a YAML ``yes``/``no`` would silently become 1/0. We reject
    bools explicitly to catch this footgun (spec 13.4 step 2).

    Args:
        value: The raw YAML value (may be ``None``, a bool, an int, or
            something else entirely).
        key: The config key name for error messages.
        default: The fallback value when ``value`` is ``None``.

    Returns:
        The validated positive integer.

    Raises:
        ValueError: If the value is a bool, not an int, or not positive.
    """
    if value is None:
        return default
    # Reject bools BEFORE the int check: bool is a subclass of int.
    if isinstance(value, bool):
        raise ValueError(
            f"defaults.{key} must be a positive integer, not a boolean ({value!r}); "
            f"YAML yes/no → True/False — use a literal integer instead"
        )
    if not isinstance(value, int):
        raise ValueError(
            f"defaults.{key} must be a positive integer, got {type(value).__name__} ({value!r})"
        )
    if value <= 0:
        raise ValueError(f"defaults.{key} must be a positive integer, got {value}")
    return value


def load_board_defaults(yaml_text: str) -> BoardDefaults:
    """Parse an optional top-level ``defaults:`` block from a ``columns.yml`` document.

    The block is a mapping with two optional keys — ``concurrency_cap`` and
    ``move_rate_limit_per_hour`` — each an ``int`` > 0. Missing keys fall back
    to the :class:`BoardDefaults` dataclass defaults. An absent ``defaults:``
    block yields all defaults, so existing ``columns.yml`` files without the
    block still load. The function is PURE: a YAML string in, a value object
    out, with no I/O (mirrors :func:`load_columns`).

    Args:
        yaml_text: The raw ``columns.yml`` document as a string.

    Returns:
        A :class:`BoardDefaults` with the parsed (or defaulted) values.

    Raises:
        ValueError: If a value is not a positive int, or is a YAML bool
            (``yes``/``no`` → ``True``/``False`` — the bool-is-int footgun).
    """
    document: Any = yaml.safe_load(yaml_text)
    if not isinstance(document, dict):
        return BoardDefaults()  # non-mapping document → all defaults

    defaults_block: Any = document.get("defaults")
    if defaults_block is None or not isinstance(defaults_block, dict):
        return BoardDefaults()  # absent or non-mapping → all defaults

    cap = _coerce_positive_int(
        defaults_block.get("concurrency_cap"),
        "concurrency_cap",
        BoardDefaults.concurrency_cap,
    )
    rate = _coerce_positive_int(
        defaults_block.get("move_rate_limit_per_hour"),
        "move_rate_limit_per_hour",
        BoardDefaults.move_rate_limit_per_hour,
    )
    return BoardDefaults(concurrency_cap=cap, move_rate_limit_per_hour=rate)
