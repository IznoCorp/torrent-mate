"""Agent helper: post a timestamped progress note on a ticket (DESIGN §8.1).

``kanban-progress <issue> <line...>`` posts a short progress note on the ticket so the operator
can follow the agent from the board. Three surfaces, in precedence order:

* ``--stage <step-key>``: append the line to that step's **sticky** comment (one comment per
  ``(ticket, step)`` updated in place via the §8.1 HTML marker). The new line is prefixed with a
  UTC timestamp and appended under the existing sticky body (a single ``list`` call backs the
  create-or-append, reusing the §8.1 marker helpers from :mod:`kanbanmate.bin.kanban_comment`).
* **auto-stage** (no ``--stage``, persisted stage resolvable): resolve the stage from the
  persisted :class:`~kanbanmate.ports.store.TicketState.stage` (the launch column recorded per
  DESIGN §8.1.d — NEW's single-source replacement for the PoC's ``get_item_column``) and append
  to that stage's sticky.  This is the PoC ``kanban-progress`` auto-resolution contract.
* **free-form note** (no ``--stage``, no persisted stage): post a free-form, timestamped note
  via the board adapter's ``comment`` path (no marker, never edits) — the genuine no-stage
  fallback.

This is a leaf entrypoint (DESIGN §3.2): it wires the GitHub adapter from the loaded token and
the per-clone registry, then writes through the board adapter, whose injected urllib transport
applies the mandatory connect+read timeouts on every request. Fail-soft on the wiring/board path:
a GitHub error is reported (non-zero exit) and never crashes the calling agent shell.
"""

from __future__ import annotations

import sys
import time

from kanbanmate.adapters.github.client import GithubClient
from kanbanmate.adapters.github.token import load_token
from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.app.stage_signal import upsert_stage_comment
from kanbanmate.bin._pin import _registry_root, check_pin, parse_issue_arg, resolve_kanban_root
from kanbanmate.cli.init import (
    ProjectEntry,
    _load_registry,
    _projects_path,
)

_PROG = "kanban-progress"

# The flag that switches kanban-progress from a free-form note to a per-step sticky append.
_STAGE_FLAG = "--stage"


def _resolve_entry() -> ProjectEntry:
    """Resolve the single registered project from the per-clone registry.

    v1 runs one repo per clone (DESIGN §4.3), so the registry must hold exactly one
    entry; anything else is an operator misconfiguration we surface loudly. The registry is read
    from the runtime root resolved by :func:`_registry_root` (``$KANBAN_ROOT`` when set, else the
    ~/.kanban default — the km-worktree-helper-root fix, #1).

    Returns:
        The sole :class:`~kanbanmate.cli.init.ProjectEntry`.

    Raises:
        RuntimeError: When the registry does not hold exactly one project.
    """
    projects_path = _projects_path(_registry_root())
    registry = _load_registry(projects_path)
    if len(registry) != 1:
        raise RuntimeError(
            f"expected exactly one registered project in {projects_path}, found {len(registry)}"
        )
    return next(iter(registry.values()))


def _timestamped(line: str, now: float) -> str:
    """Prefix ``line`` with a compact UTC timestamp for the progress log.

    Args:
        line: The progress text the agent supplied.
        now: The wall-clock timestamp (``time.time()``) to render.

    Returns:
        ``"- <YYYY-MM-DD HH:MM:SSZ> <line>"`` — a single markdown list item.
    """
    stamp = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime(now))
    return f"- {stamp} {line}"


def append_to_stage(client: GithubClient, issue: int, stage: str, line: str, now: float) -> None:
    """Append a stamped ``line`` to the ``stage`` two-zone sticky on ``issue`` (DESIGN §8.1).

    Delegates to :func:`kanbanmate.app.stage_signal.upsert_stage_comment` with
    ``header=None`` so the dispatcher's producer-owned running header is PRESERVED and
    only the §8.1 BODY (``**Progress**``) gains the stamped line. When no sticky exists
    yet the upsert creates one carrying a minimal running header plus the line, so a
    progress note always has a home (the PoC ``kanban-progress`` append-or-create
    semantics). The whole append is backed by a single ``list_issue_comments`` call.

    Args:
        client: The wired GitHub board client.
        issue: The issue number carrying the sticky.
        stage: The step/column key owning the sticky (its marker key).
        line: The progress text to append (stamped by the upsert).
        now: The wall-clock timestamp for the stamped line's prefix.
    """
    # header=None preserves whatever producer header is already in place (or synthesises a
    # minimal running one on create); append=line lands a single stamped progress bullet.
    upsert_stage_comment(client, issue, stage, header=None, append=line, now=now)


def _split_stage(argv: list[str]) -> tuple[str | None, list[str]]:
    """Split ``--stage <key>`` out of ``argv``; return ``(stage, remaining)``.

    Args:
        argv: The raw argument vector (excluding the program name).

    Returns:
        A ``(stage, remaining)`` pair: ``stage`` is the step key when ``--stage`` was given
        (else ``None``); ``remaining`` is ``argv`` with the flag and its value removed.

    Raises:
        ValueError: When ``--stage`` is given without a following value.
    """
    if _STAGE_FLAG not in argv:
        return None, argv
    idx = argv.index(_STAGE_FLAG)
    if idx + 1 >= len(argv):
        raise ValueError(f"{_STAGE_FLAG} requires a step key")
    stage = argv[idx + 1]
    remaining = argv[:idx] + argv[idx + 2 :]
    return stage, remaining


def main(argv: list[str] | None = None) -> int:
    """Entry point: post a timestamped progress note on a ticket.

    Three modes, in precedence order:

    1. ``--stage <key>`` — explicit override: append to that step's sticky.
    2. **auto-stage** — no ``--stage``, but a persisted
       :class:`~kanbanmate.ports.store.TicketState.stage` is resolvable: resolve
       the stage from the ticket's persisted launch column (DESIGN §8.1.d — NEW's
       single-source replacement for the PoC's ``get_item_column``) and append to
       that stage's sticky.  This restores the PoC ``kanban-progress`` contract
       where the agent never needed to pass a stage.
    3. **free-form note** — no ``--stage`` AND no persisted stage: post a free-form,
       timestamped note (no marker, never edits).

    Either way the write goes through the board adapter, whose injected urllib
    transport applies the mandatory connect+read timeouts on every request.

    Failure handling: a usage error exits ``2``; any wiring/board failure is
    reported to stderr and exits ``1`` — never a traceback that would crash the
    calling agent.

    Args:
        argv: Optional argument vector (excluding the program name); defaults to
            :data:`sys.argv` ``[1:]``. Expects ``<issue> <line...>`` with optional
            ``--stage <key>``.

    Returns:
        ``0`` on success, ``2`` on a usage error, ``1`` on any other failure.
    """
    raw_argv = sys.argv[1:] if argv is None else argv
    try:
        stage, rest = _split_stage(raw_argv)
    except ValueError as exc:
        print(f"{_PROG}: {exc}", file=sys.stderr)
        return 2
    if len(rest) < 2:
        print(f"usage: {_PROG} <issue> <line...> [--stage <step-key>]", file=sys.stderr)
        return 2
    try:
        issue = parse_issue_arg(rest[0])
    except ValueError:
        print(f"{_PROG}: issue must be an integer, got {rest[0]!r}", file=sys.stderr)
        return 2
    line = " ".join(rest[1:])

    # Pin enforcement (R1, §29.1): refuse a mismatched issue when the worktree is pinned (absent
    # pin → unpinned operator use). Checked BEFORE any GitHub call so no note is ever posted.
    pin_error = check_pin(issue)
    if pin_error is not None:
        print(f"{_PROG}: {pin_error}", file=sys.stderr)
        return 1

    try:
        entry = _resolve_entry()
        client = GithubClient(load_token(), project_id=entry.project_id, repo=entry.repo)
        now = time.time()
        if stage is not None:
            # Explicit --stage <key> override: append to that step's sticky.
            append_to_stage(client, issue, stage, line, now)
        else:
            # Auto-resolve the stage from the persisted TicketState.stage (DESIGN §8.1.d),
            # matching the PoC kanban-progress auto-resolution contract. The launch column
            # recorded on the ticket is NEW's single-source replacement for the PoC's
            # get_item_column — same semantics, different store key.
            # Resolve the store root from $KANBAN_ROOT (#1 km-root fix); None → ~/.kanban default.
            store = FsStateStore(resolve_kanban_root())
            state = store.load(issue)
            resolved_stage: str | None = state.stage if state and state.stage else None
            if resolved_stage:
                append_to_stage(client, issue, resolved_stage, line, now)
                stage = resolved_stage  # for the progress label
            else:
                # No persisted stage either — genuine free-form note fallback.
                client.comment(issue, _timestamped(line, now))
    except Exception as exc:  # noqa: BLE001 — never crash the caller; report + exit non-zero.
        print(f"{_PROG}: {exc}", file=sys.stderr)
        return 1

    label = f"[{stage}]" if stage is not None else "(note)"
    print(f"progress #{issue} {label}: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
