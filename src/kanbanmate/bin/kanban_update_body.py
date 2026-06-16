"""Agent helper: the SANCTIONED issue-body write path (§29.1).

``kanban-update-body <issue> (--set-field <key> <value> | --append-section <heading>)`` is the
ONLY way an orchestrated agent may write a ticket's body. The hardened prompts route every body
write-back through this helper (raw ``gh issue edit`` is denied for all profiles — see
:mod:`kanbanmate.adapters.perms`) because this helper:

* is **PINNED** to the launched issue (``<worktree>/.claude/kanban-issue``, written at provision
  time): it REFUSES any other ``<issue>`` when a pin file is present, so a misattributed agent can
  never write to another ticket (R1 enforcement). With no pin file (operator running by hand
  outside a worktree) it falls back to unpinned behaviour.
* **PRESERVES** the ``**roadmap**`` / ``**codename**`` / ``**design**`` / ``**plans**`` binding
  markers — ``--set-field`` rewrites exactly one in place, ``--append-section`` touches none.
* **VALIDATES** body↔title ``[CODE]`` coherence AFTER the edit and BEFORE the write: a mismatch
  exits non-zero and writes nothing, so a body write can never desync the ticket↔roadmap binding.

``--set-field <key> <value>`` sets a single ``**key**: value`` marker (the codename / design /
plans / roadmap write-backs). ``--append-section <heading>`` reads the section text from STDIN and
appends it under the markdown heading (the brainstorm-output APPEND path — never an overwrite).

This is a leaf entrypoint (DESIGN §3.2): it wires the GitHub adapter from the loaded token and the
per-clone registry, fetches the current body via the board adapter (mandatory connect+read
timeouts on every request), applies a pure transform from :mod:`kanbanmate.core.body_edit`,
validates, then patches the body back. On bad/missing arguments, a pin mismatch, or a coherence
failure it fails cleanly (non-zero exit, clear stderr) and never crashes the calling agent shell.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from kanbanmate.adapters.github.client import GithubClient
from kanbanmate.adapters.github.token import load_token
from kanbanmate.bin._pin import _registry_root, check_pin, parse_issue_arg
from kanbanmate.cli.init import ProjectEntry, _load_registry, _projects_path
from kanbanmate.core.body_edit import (
    append_section,
    set_field,
    validate_roadmap_matches_title,
)

_PROG = "kanban-update-body"


@dataclass(frozen=True)
class _Args:
    """Parsed command-line arguments for :func:`main`.

    Attributes:
        issue: The target issue number (checked against the worktree pin).
        field_key: The ``--set-field`` marker key, or ``None``.
        field_value: The ``--set-field`` marker value, or ``None``.
        section_heading: The ``--append-section`` markdown heading, or ``None`` (text from stdin).
    """

    issue: int
    field_key: str | None
    field_value: str | None
    section_heading: str | None


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``kanban-update-body``.

    Returns:
        The configured :class:`argparse.ArgumentParser`. ``--set-field`` (two values: key + value)
        and ``--append-section`` (one value: the heading) are mutually exclusive and one is
        REQUIRED.
    """
    parser = argparse.ArgumentParser(
        prog=_PROG,
        description="The sanctioned issue-body write path (pinned, marker-preserving).",
    )
    # ``parse_issue_arg`` strips a defensive leading ``#`` (defect 3) before int-parsing, so a
    # ``kanban-update-body #151 …`` typed by habit still resolves; argparse surfaces a bad value
    # as a usage error (exit 2).
    parser.add_argument(
        "issue", type=parse_issue_arg, help="Target issue number (must match the worktree pin)."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--set-field",
        nargs=2,
        metavar=("KEY", "VALUE"),
        dest="set_field",
        default=None,
        help="Set a single **key**: value marker in place (codename/design/plans/roadmap).",
    )
    mode.add_argument(
        "--append-section",
        metavar="HEADING",
        dest="append_section",
        default=None,
        help="Append the markdown HEADING + stdin text under it (e.g. '## Brainstorm').",
    )
    return parser


def _parse_args(argv: list[str]) -> _Args:
    """Parse ``argv`` into a typed :class:`_Args`.

    Args:
        argv: The argument vector (excluding the program name).

    Returns:
        The parsed arguments.

    Raises:
        SystemExit: When ``argparse`` rejects the arguments (handled by ``main``).
    """
    ns = _build_parser().parse_args(argv)
    field_key: str | None = None
    field_value: str | None = None
    if ns.set_field is not None:
        field_key, field_value = ns.set_field[0], ns.set_field[1]
    return _Args(
        issue=int(ns.issue),
        field_key=field_key,
        field_value=field_value,
        section_heading=ns.append_section,
    )


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


def main(argv: list[str] | None = None) -> int:
    """Entry point: write a ticket's body via the sanctioned, pinned, validated path.

    Flow: parse args → enforce the worktree pin (refuse a mismatched issue) → fetch the current
    body + title → apply the pure ``--set-field`` / ``--append-section`` transform → validate
    body↔title ``[CODE]`` coherence → patch the body back. Stdin supplies the section text for
    ``--append-section``.

    Failure handling: argument errors exit ``2`` via ``argparse``; a pin mismatch or a coherence
    failure exits ``1`` with a clear stderr message and writes NOTHING; any wiring/board error is
    caught and reported (exit ``1``) — never a traceback that crashes the calling agent.

    Args:
        argv: Optional argument vector (excluding the program name); defaults to
            :data:`sys.argv` ``[1:]``.

    Returns:
        ``0`` on a successful write, ``2`` on a usage error, ``1`` on a pin mismatch / coherence
        failure / any other failure.
    """
    raw_argv = sys.argv[1:] if argv is None else argv
    try:
        args = _parse_args(raw_argv)
    except SystemExit as exc:  # argparse already printed usage to stderr.
        return int(exc.code) if isinstance(exc.code, int) else 2

    # Pin enforcement FIRST (R1, §29.1): refuse a mismatched issue BEFORE any GitHub call, so a
    # misattributed agent never even reads another ticket. Absent pin → unpinned (operator use).
    pin_error = check_pin(args.issue)
    if pin_error is not None:
        print(f"{_PROG}: {pin_error}", file=sys.stderr)
        return 1

    # Read the section text from stdin up front (before any network call) for --append-section.
    section_text = sys.stdin.read() if args.section_heading is not None else ""

    try:
        entry = _resolve_entry()
        client = GithubClient(load_token(), project_id=entry.project_id, repo=entry.repo)
        issue_ref = client.fetch_issue(args.issue)

        # Apply the pure transform: --set-field rewrites ONE marker; --append-section appends text
        # under a heading (markers untouched). Exactly one is set (argparse enforced the group).
        if args.field_key is not None and args.field_value is not None:
            new_body = set_field(issue_ref.body, args.field_key, args.field_value)
        else:
            assert args.section_heading is not None  # argparse guaranteed one mode; narrows mypy
            new_body = append_section(issue_ref.body, args.section_heading, section_text)

        # Post-write coherence gate (§29.1): never let a write desync the ticket↔roadmap binding.
        coherence_error = validate_roadmap_matches_title(new_body, issue_ref.title)
        if coherence_error is not None:
            print(f"{_PROG}: {coherence_error}", file=sys.stderr)
            return 1

        if not issue_ref.node_id:
            print(
                f"{_PROG}: could not resolve a node id for #{args.issue}; refusing the write",
                file=sys.stderr,
            )
            return 1
        client.update_issue_body(issue_ref.node_id, new_body)
    except Exception as exc:  # noqa: BLE001 — never crash the caller; report + exit non-zero.
        print(f"{_PROG}: {exc}", file=sys.stderr)
        return 1

    print(f"updated body of #{args.issue}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
