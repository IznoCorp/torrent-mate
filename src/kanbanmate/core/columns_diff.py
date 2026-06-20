"""Pure column-set diff for the bridge "Sync board" preview (helm PR 2).

Computes the change set between the board's CURRENT Status options and the
DESIRED ``columns.yml`` order, classifying each difference as add / rename /
reorder / remove. Removals are surfaced separately and NEVER applied (a removal
would null every card still in that column — the operator removes via GitHub if
intended). RENAME is operator-asserted via the ``renames`` map (a name-only diff
cannot infer it), mirroring how the GUI edits a column name in place.

Pure functional core: stdlib only, no I/O (DESIGN §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColumnChange:
    """One classified difference between current and desired columns.

    Args:
        kind: One of ``"add"`` / ``"rename"`` / ``"reorder"`` / ``"remove"``.
        column: The current (or, for ``add``, the new) column name the change concerns.
        to: For ``rename``, the new name; otherwise ``None``.
        from_pos: For ``reorder``, the 0-based index in ``current``; otherwise ``None``.
        to_pos: For ``reorder``, the 0-based index in ``desired``; otherwise ``None``.
    """

    kind: str
    column: str
    to: str | None = None
    from_pos: int | None = None
    to_pos: int | None = None


@dataclass(frozen=True)
class ColumnDiff:
    """The full classified diff returned by :func:`diff_columns`.

    Args:
        changes: Applicable changes (add / rename / reorder), in a stable order.
        removals: Columns present on the board but not desired — surfaced, never applied.
        is_noop: ``True`` when ``changes`` and ``removals`` are both empty.
    """

    changes: list[ColumnChange] = field(default_factory=list)
    removals: list[ColumnChange] = field(default_factory=list)
    is_noop: bool = True


def diff_columns(
    current: list[str],
    desired: list[str],
    *,
    renames: dict[str, str] | None = None,
) -> ColumnDiff:
    """Classify the difference between current and desired column sets.

    Args:
        current: The board's current Status option names, in board order.
        desired: The desired column names, in board order (the ``columns.yml`` set).
        renames: Optional operator-asserted ``{old_name: new_name}`` map. Each entry
            reclassifies the (remove old, add new) pair as a single ``rename``.

    Returns:
        A :class:`ColumnDiff`. ``changes`` carries add/rename/reorder; ``removals``
        carries every current column absent from ``desired`` (minus any renamed away).
    """
    renames = dict(renames or {})
    renamed_from = set(renames)
    renamed_to = set(renames.values())

    changes: list[ColumnChange] = []
    # Renames first, in board order of the OLD name.
    for old in current:
        if old in renames:
            changes.append(ColumnChange(kind="rename", column=old, to=renames[old]))

    # Adds: desired names neither present in current nor produced by a rename.
    current_set = set(current)
    for name in desired:
        if name not in current_set and name not in renamed_to:
            changes.append(ColumnChange(kind="add", column=name))

    # Removals: current names neither desired nor renamed away.
    desired_set = set(desired)
    removals = [
        ColumnChange(kind="remove", column=name)
        for name in current
        if name not in desired_set and name not in renamed_from
    ]

    # Reorder: compare the post-rename projection of current against desired,
    # restricted to names common to both, by index.
    projected = [renames.get(name, name) for name in current]
    projected_set = set(projected)
    common_current = [n for n in projected if n in desired_set]
    common_desired = [n for n in desired if n in projected_set]
    if common_current != common_desired:
        for to_pos, name in enumerate(common_desired):
            from_pos = common_current.index(name)
            if from_pos != to_pos:
                changes.append(
                    ColumnChange(kind="reorder", column=name, from_pos=from_pos, to_pos=to_pos)
                )

    is_noop = not changes and not removals
    return ColumnDiff(changes=changes, removals=removals, is_noop=is_noop)
