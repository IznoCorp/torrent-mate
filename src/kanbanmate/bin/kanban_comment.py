"""Agent helper: post a *sticky* (or free-form) comment on a ticket (DESIGN §8.1).

A sticky comment keeps **one comment per (ticket, stage)** updated in place. The
comment self-identifies via a hidden HTML marker embedding the stage's column key::

    <!-- kanban:step=<column-key> -->

``kanban-comment --sticky <stage-key> <issue> <body...>`` appends the body as a
stamped progress line to that stage's two-zone sticky (DESIGN §8.1): it lists the
issue's comments, locates the comment carrying that exact marker, and **edits it in
place** when found (preserving the producer-owned header) or **creates** a fresh
running-header sticky carrying the line when absent — a durable progress surface that
does not spam the timeline. ``--append`` skips the marker lookup entirely and simply
posts a free-form note (no marker, no edit).

**Bare-positional default (PoC parity).** ``kanban-comment <issue> <msg>`` (no mode
flag) defaults to ``--append`` — a free-form ``client.comment`` with no marker lookup
— matching the PoC ``kanban-comment`` contract.  The explicit ``--append`` flag is
still accepted for clarity; ``--sticky <STEP>`` remains the two-zone capability.

The rich two-zone subsystem lives in :mod:`kanbanmate.core.stage_comment` (pure
render/locate/split/compose) and :mod:`kanbanmate.app.stage_signal` (the single I/O
upsert orchestrator); this leaf only wires the GitHub adapter and delegates to them.

This is a leaf entrypoint (DESIGN §3.2): it wires the GitHub adapter from the loaded
token and the per-clone registry, then delegates the sticky upsert to the app layer.
On bad/missing arguments it fails cleanly (non-zero exit, clear stderr message) and
never lets an unexpected error crash the calling agent shell.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from kanbanmate.adapters.github.client import GithubClient
from kanbanmate.app.stage_signal import upsert_stage_comment
from kanbanmate.bin._pin import check_pin, parse_issue_arg
from kanbanmate.cli.init import ProjectEntry
from kanbanmate.core.stage_comment import HeaderInfo

_PROG = "kanban-comment"


@dataclass(frozen=True)
class _Args:
    """Parsed command-line arguments for :func:`main`.

    Attributes:
        issue: The target issue number.
        body: The visible comment body (joined from the message words).
        step: The sticky step/column key, or ``None`` in append mode.
        append: ``True`` to post a free-form note (no marker lookup).
    """

    issue: int
    body: str
    step: str | None
    append: bool


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``kanban-comment``.

    Returns:
        The configured :class:`argparse.ArgumentParser`. ``--sticky`` and
        ``--append`` are mutually exclusive; ``--sticky`` carries the step key.
    """
    parser = argparse.ArgumentParser(
        prog=_PROG,
        description="Post a sticky (per-stage) or free-form comment on a ticket.",
    )
    # ``parse_issue_arg`` strips a defensive leading ``#`` (defect 3) before int-parsing, so a
    # ``kanban-comment #151 …`` typed by habit still resolves; argparse surfaces a bad value as a
    # usage error (exit 2).
    parser.add_argument("issue", type=parse_issue_arg, help="Target issue number.")
    parser.add_argument("message", nargs="+", help="Comment body (one or more words).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--sticky",
        "-s",
        metavar="STEP",
        dest="step",
        default=None,
        help="Sticky mode: keep one comment per (ticket, STEP) edited in place.",
    )
    mode.add_argument(
        "--append",
        action="store_true",
        help="Append mode: post a free-form note (no marker, never edits).",
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
    return _Args(
        issue=int(ns.issue),
        body=" ".join(ns.message),
        step=ns.step,
        append=bool(ns.append),
    )


def _resolve_entry() -> ProjectEntry:
    """Resolve the registry entry this helper acts on (project-aware, ingress-multiproject §7).

    Thin delegate to the shared :func:`kanbanmate.bin._clone_config.resolve_entry` (the ONE source
    of truth, now multi-project-aware: project pin / ``$KANBAN_PROJECT_ID`` → exact entry, else the
    N=1 sole entry, else fail loud). Kept as a module-level name so existing tests that monkeypatch
    ``_resolve_entry`` on this module keep working.

    Returns:
        The resolved :class:`~kanbanmate.cli.init.ProjectEntry`.

    Raises:
        RuntimeError: When no project is registered, the pinned project is unknown, or N>1 with no
            pin to disambiguate (see :func:`kanbanmate.bin._clone_config.resolve_entry`).
    """
    from kanbanmate.bin._clone_config import resolve_entry

    return resolve_entry()


def _resolve_entry_token(entry: ProjectEntry) -> str:
    """Resolve the PER-ENTRY GitHub token for ``entry`` (multi-org §6, #4).

    Thin delegate to the shared :func:`kanbanmate.bin._clone_config.resolve_entry_token` (the ONE
    resolver, which the daemon also uses) so a second org's agent authenticates with that org's PAT.
    Kept as a module-level name so tests can monkeypatch it.

    Args:
        entry: The resolved registry entry (its ``token_ref`` selects the token file).

    Returns:
        The resolved token string for this entry.
    """
    from kanbanmate.bin._clone_config import resolve_entry_token

    return resolve_entry_token(entry)


def main(argv: list[str] | None = None) -> int:
    """Entry point: post a sticky or free-form comment on a ticket.

    Resolves the target repository and project from the per-clone registry, builds
    a :class:`~kanbanmate.adapters.github.client.GithubClient` from the loaded token,
    then performs the sticky upsert (``--sticky``) or a plain create (``--append`` or
    the bare-positional default — PoC parity: ``kanban-comment <issue> <msg>`` ≡
    ``kanban-comment <issue> --append <msg>``).

    The sticky path delegates to :func:`kanbanmate.app.stage_signal.upsert_stage_comment`
    with the message as a stamped progress line and a running header, so an absent
    sticky is created with a producer-owned 🟡 header while an existing one keeps its
    header and gains the new line (the two-zone §8.1 contract).

    Failure handling: argument errors exit non-zero via ``argparse``; any other
    error (no token, no registry, GitHub I/O) is caught and reported to stderr with
    a non-zero exit so the calling agent shell is never crashed by a traceback.

    Args:
        argv: Optional argument vector (excluding the program name); defaults to
            :data:`sys.argv` ``[1:]``.

    Returns:
        ``0`` on success, ``2`` on a usage error, ``1`` on any other failure.
    """
    raw_argv = sys.argv[1:] if argv is None else argv
    try:
        args = _parse_args(raw_argv)
    except SystemExit as exc:  # argparse already printed usage to stderr.
        return int(exc.code) if isinstance(exc.code, int) else 2

    # Pin enforcement (R1, §29.1): refuse a mismatched issue when the worktree is pinned (absent
    # pin → unpinned operator use). Checked BEFORE any GitHub call so no comment is ever posted.
    pin_error = check_pin(args.issue)
    if pin_error is not None:
        print(f"{_PROG}: {pin_error}", file=sys.stderr)
        return 1

    try:
        entry = _resolve_entry()
        # Resolve the PER-ENTRY token (#4): a second org's entry carries a ``token_ref`` so its agent
        # authenticates with that org's PAT instead of the shared default (which would 401). N=1 /
        # no token_ref → the shared token (byte-identical to the historical ``load_token()``).
        client = GithubClient(
            _resolve_entry_token(entry), project_id=entry.project_id, repo=entry.repo
        )
        # Bare-positional defaults to free-form (PoC parity): when neither --sticky nor
        # --append is given, the implicit default is append mode — a plain client.comment
        # with no marker lookup, matching the PoC kanban-comment contract.
        if args.append or args.step is None:
            # Append mode (explicit or bare-positional default): free-form note, no
            # marker, no lookup.
            client.comment(args.issue, args.body)
        else:
            # Sticky mode: append the body as a stamped progress line to the stage's
            # two-zone sticky. An absent sticky is created with a running 🟡 header
            # (the app-layer upsert preserves an existing producer header when found).
            upsert_stage_comment(
                client,
                args.issue,
                args.step,
                header=HeaderInfo(stage=args.step, status="running"),
                append=args.body,
            )
    except Exception as exc:  # noqa: BLE001 — never crash the caller; report + exit non-zero.
        print(f"{_PROG}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
