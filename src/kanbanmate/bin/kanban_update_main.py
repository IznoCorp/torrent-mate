"""Agent helper: post-merge ``main`` refresh of the base/dev clones (DESIGN §10).

``kanban-update-main [<base_clone> [<dev_repo>]]`` keeps local clones current after a human merges
a PR. When BOTH arguments are omitted it RESOLVES the base clone + dev clone from the ``kanban
init`` registry (``<root>/projects.json``, where ``<root>`` is ``$KANBAN_ROOT`` when set, else
``~/.kanban`` — the km-worktree-helper-root fix, #1) — the single registered project's ``clone``
and ``dev_repo_path`` (defect 12: three docstrings already claimed this registry resolution, but
the helper never read it). Explicit positional args still override the registry. Ported from the
PoC ``kanban-update-main`` bash script, preserving its exact, conservative semantics:

1. **Base clone** — always ``git fetch origin main`` (safe: a bare/base clone has no working tree
   to clobber). A failure here is fatal (exit ``1``).
2. **Dev clone (optional)** — fast-forward *only* when its working tree is clean **and** it is on
   ``main``; otherwise print a clear skip-warning and exit ``0`` (the dev update is best-effort).

Safety (DESIGN §10 — merge is human-only): this helper performs **no merge, no force, no history
rewrite**. The only mutating git call is ``git pull --ff-only`` (a strict fast-forward that
refuses to create a merge commit), and only after both guards pass.

This is a leaf entrypoint (DESIGN §3.2): it shells out to ``git`` on local clones (no GitHub
network call). Bad arguments fail cleanly (non-zero exit, clear stderr).
"""

from __future__ import annotations

import sys

from kanbanmate.adapters.workspace.base_sync import BaseFetchError, fetch_base, ff_dev_clone

_PROG = "kanban-update-main"


def _resolve_from_registry() -> tuple[str, str] | None:
    """Resolve ``(base_clone, dev_repo)`` from the resolved registry entry (defect 12; multi-project §7).

    Reads the ``projects.json`` under the runtime root (``$KANBAN_ROOT`` when set, else
    ``~/.kanban``) — the km-worktree-helper-root fix, #1 — and resolves the entry PROJECT-AWARELY via
    :func:`kanbanmate.bin._clone_config.resolve_entry`: a launched agent's worktree project pin /
    ``$KANBAN_PROJECT_ID`` selects the EXACT entry (multi-project), and an N=1 root keeps the sole
    entry (back-compat). The entry's ``clone`` is the base clone and its ``dev_repo_path`` the dev
    clone (``""`` when the operator never passed ``--dev-repo-path``). Returns ``None`` (the caller
    falls back to the usage error) when the entry cannot be resolved (no project, unknown pin, or
    N>1 with no pin) — in those cases the operator must pass an explicit ``<base_clone>``.

    Returns:
        A ``(base_clone, dev_repo)`` tuple from the registry, or ``None`` when it cannot resolve.
    """
    # Lazy import (leaf entrypoint): the resolver lives in the bin/_clone_config module; importing it
    # at call time keeps this bin importable without eagerly pulling the resolver chain.
    from kanbanmate.bin._clone_config import resolve_entry

    try:
        entry = resolve_entry()
    except RuntimeError:
        # No project (run init first), unknown pin, or >1 with no pin → require an explicit arg.
        return None
    return entry.clone, entry.dev_repo_path


def main(argv: list[str] | None = None) -> int:
    """Entry point: fetch ``origin/main`` in the base clone, optionally ff the dev clone.

    Args:
        argv: Optional argument vector (excluding the program name); defaults to
            :data:`sys.argv` ``[1:]``. Expects ``[<base_clone> [<dev_repo>]]`` — both optional:
            when omitted, they are resolved from the ``kanban init`` registry (defect 12).

    Returns:
        ``0`` when the base fetch succeeds (the dev update is best-effort and never fails the
        run); ``1`` when the base clone cannot be resolved (no arg AND no single registered
        project) or the base fetch fails.
    """
    raw_argv = sys.argv[1:] if argv is None else argv
    if not raw_argv:
        # No positional args → resolve the base + dev clones from the registry (defect 12).
        resolved = _resolve_from_registry()
        if resolved is None:
            print(
                f"Usage: {_PROG} <base_clone> [<dev_repo>] "
                "(or register exactly one project with `kanban init` to omit the args)",
                file=sys.stderr,
            )
            return 1
        base_clone, dev_repo = resolved
    else:
        base_clone = raw_argv[0]
        dev_repo = raw_argv[1] if len(raw_argv) > 1 else ""

    # Step 1: always fetch origin/main in the base clone (no working tree to clobber). The git work
    # lives in the workspace adapter (conduit §11.2) — the bin keeps its exact message + exit code.
    print(f"Fetching origin/main in base clone: {base_clone}")
    try:
        fetch_base(base_clone)
    except BaseFetchError as exc:
        print(f"{_PROG}: base fetch failed: {exc.stderr}", file=sys.stderr)
        return 1

    # Step 2: optionally fast-forward the operator's dev clone (best-effort; never fails the run).
    if not dev_repo:
        return 0
    ff_dev_clone(dev_repo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
