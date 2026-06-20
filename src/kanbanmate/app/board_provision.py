"""Board provisioning shell for bridge's "Sync board" action (helm PR 2).

Reads the board's current Status options, diffs them against the desired
``columns.yml`` set, and — on apply — re-provisions the options via the shipped
:meth:`Seeder.ensure_columns` (which preserves option ids so cards are never
orphaned). This is the ONLY board-mutating path bridge adds; it writes Status
options only — never cards, never PRs, never merges (CLAUDE.md autonomy floor).

The registry resolution (``projects.json`` → ``project_id`` / option fallback)
lives in the HTTP caller, NOT here: the layering guard forbids ``app`` from
importing ``cli`` (``tests/test_layering.py`` ``FORBIDDEN["app"] = ["cli", …]``).
So this shell takes an already-resolved ``project_id`` + a ``fallback_options``
list, and builds the production seeder via ``adapters`` (app→adapters allowed).

Layering: ``app`` is the imperative shell — it may import ``core`` and ``adapters``
and the ports, but not ``cli`` / ``daemon``. ``core`` stays pure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kanbanmate.core.columns_diff import ColumnDiff, diff_columns
from kanbanmate.ports.board import Seeder


@dataclass(frozen=True)
class ProvisionResult:
    """Outcome of a :func:`provision_board` call.

    Args:
        applied: ``True`` when the board was mutated (apply); ``False`` for a dry-run.
        diff: The classified column diff (always populated).
        option_map: The ``{column: option_id}`` map after apply; empty on dry-run.
    """

    applied: bool
    diff: ColumnDiff
    option_map: dict[str, str] = field(default_factory=dict)


def _build_seeder(project_id: str) -> Seeder:
    """Build the production GitHub seeder for ``project_id`` (mirrors cli/seed.py:413).

    Imported lazily so this module stays importable (and the dry-run path stays
    usable with an injected fake) without a live token present.

    Args:
        project_id: The Project v2 node id to bind the client to.

    Returns:
        A :class:`~kanbanmate.adapters.github.client.GithubClient` bound to the project.
    """
    from kanbanmate.adapters.github.client import GithubClient  # noqa: PLC0415
    from kanbanmate.adapters.github.token import load_token  # noqa: PLC0415

    return GithubClient(load_token(), project_id=project_id)


def _current_options(seeder: Seeder, project_id: str, fallback: list[str]) -> list[str]:
    """Read the board's current Status option names, in board order.

    Uses the optional ``status_options`` probe (cli/seed.py:313 pattern); falls back
    to the caller-supplied ``fallback`` (the registry entry's recorded option-map keys)
    when the seeder lacks the probe.

    Args:
        seeder: The Seeder driving provisioning.
        project_id: The Project v2 node id.
        fallback: The current option names to use when no live probe is available.

    Returns:
        The current option names, board order.
    """
    probe = getattr(seeder, "status_options", None)
    if callable(probe):
        return list(probe(project_id).keys())
    return list(fallback)


def provision_board(
    *,
    project_id: str,
    desired_columns: list[str],
    fallback_options: list[str] | None = None,
    renames: dict[str, str] | None = None,
    dry_run: bool,
    seeder: Seeder | None = None,
) -> ProvisionResult:
    """Diff (and optionally apply) the board's Status options against the desired columns.

    Args:
        project_id: The Project v2 node id whose Status field to inspect/shape.
        desired_columns: The desired column names, board order (the ``columns.yml`` set).
        fallback_options: Current option names to use when the seeder has no
            ``status_options`` probe (the registry entry's option-map keys).
        renames: Optional operator-asserted ``{old: new}`` map (see :func:`diff_columns`).
        dry_run: When ``True``, compute + return the diff WITHOUT mutating the board.
        seeder: Injected Seeder (tests). Defaults to the production GitHub client.

    Returns:
        A :class:`ProvisionResult`.
    """
    active = seeder if seeder is not None else _build_seeder(project_id)
    current = _current_options(active, project_id, fallback_options or [])
    diff = diff_columns(current, desired_columns, renames=renames)

    if dry_run:
        return ProvisionResult(applied=False, diff=diff)

    option_map = active.ensure_columns(project_id, desired_columns)
    return ProvisionResult(applied=True, diff=diff, option_map=option_map)
