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

import subprocess
import sys

_PROG = "kanban-update-main"


def _git(args: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
    """Run a ``git`` command in ``cwd`` and capture its output.

    Args:
        args: The git sub-command and its arguments (without the leading ``git``).
        cwd: The repository directory to run in.

    Returns:
        The completed process (``returncode`` checked by the caller).
    """
    # No --force / no merge anywhere (DESIGN §10): callers only pass fetch / status / pull --ff-only.
    return subprocess.run(
        ["git", "-C", cwd, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _is_dirty(dev_repo: str) -> bool:
    """Return whether ``dev_repo``'s working tree has uncommitted or untracked changes.

    ``git diff`` / ``git diff --cached`` only catch tracked changes, so ``status --porcelain``
    is also consulted to catch untracked files that could conflict after a pull.

    Args:
        dev_repo: The dev clone directory to inspect.

    Returns:
        ``True`` when the tree is dirty (tracked or untracked changes present).
    """
    if _git(["diff", "--quiet"], dev_repo).returncode != 0:
        return True
    if _git(["diff", "--cached", "--quiet"], dev_repo).returncode != 0:
        return True
    porcelain = _git(["status", "--porcelain"], dev_repo)
    return bool(porcelain.stdout.strip())


def _current_branch(dev_repo: str) -> str:
    """Return ``dev_repo``'s current branch name (empty on detached/unknown HEAD).

    Args:
        dev_repo: The dev clone directory to inspect.

    Returns:
        The abbreviated current branch name, or ``""`` when it cannot be resolved.
    """
    result = _git(["rev-parse", "--abbrev-ref", "HEAD"], dev_repo)
    return result.stdout.strip() if result.returncode == 0 else ""


def _update_dev_clone(dev_repo: str) -> int:
    """Fast-forward ``dev_repo`` on ``main`` when both guards pass; else skip-warn.

    Args:
        dev_repo: The operator's dev clone directory.

    Returns:
        Always ``0`` — a skip is best-effort, not a failure (DESIGN §10). A failed
        ``pull --ff-only`` is reported but still returns ``0`` so a post-merge hook never
        blocks on the operator's local clone state.
    """
    if _is_dirty(dev_repo):
        print(
            f"WARNING: skipping dev clone update — working tree is dirty in {dev_repo}",
            file=sys.stderr,
        )
        print(
            f"  Run 'git -C {dev_repo} pull --ff-only' manually after committing your changes.",
            file=sys.stderr,
        )
        return 0
    branch = _current_branch(dev_repo)
    if branch != "main":
        print(
            f"WARNING: skipping dev clone update — {dev_repo} is on branch {branch!r}, not 'main'",
            file=sys.stderr,
        )
        print(
            "  Switch to main and run 'git pull --ff-only' manually when ready.",
            file=sys.stderr,
        )
        return 0
    print(f"Fast-forwarding dev clone on main: {dev_repo}")
    # --ff-only is a strict fast-forward: it REFUSES to create a merge commit (DESIGN §10).
    pull = _git(["pull", "--ff-only"], dev_repo)
    if pull.returncode != 0:
        print(f"WARNING: dev clone fast-forward failed: {pull.stderr.strip()}", file=sys.stderr)
    return 0


def _resolve_from_registry() -> tuple[str, str] | None:
    """Resolve ``(base_clone, dev_repo)`` from the single registered project (defect 12).

    Reads the ``projects.json`` under the runtime root (``$KANBAN_ROOT`` when set, else
    ``~/.kanban``) — the km-worktree-helper-root fix, #1. v1 registers exactly one project, so the
    SINGLE entry's ``clone`` is the base clone and its ``dev_repo_path`` the dev clone (``""`` when
    the operator never passed ``--dev-repo-path``). Returns ``None`` (the caller falls back to the
    usage error) when the registry is absent, empty, or ambiguous (>1 project) — in those cases the
    operator must pass an explicit ``<base_clone>``.

    Returns:
        A ``(base_clone, dev_repo)`` tuple from the registry, or ``None`` when it cannot resolve.
    """
    # Lazy import (leaf entrypoint): the registry helpers live in the CLI module; importing them at
    # call time keeps this bin importable without eagerly pulling the CLI surface.
    from kanbanmate.bin._pin import _registry_root
    from kanbanmate.cli.init import _load_registry, _projects_path

    registry = _load_registry(_projects_path(_registry_root()))
    if len(registry) != 1:
        # No project (run init first) or >1 (ambiguous → require an explicit arg).
        return None
    entry = next(iter(registry.values()))
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

    # Step 1: always fetch origin/main in the base clone (no working tree to clobber).
    print(f"Fetching origin/main in base clone: {base_clone}")
    fetch = _git(["fetch", "origin", "main"], base_clone)
    if fetch.returncode != 0:
        print(f"{_PROG}: base fetch failed: {fetch.stderr.strip()}", file=sys.stderr)
        return 1

    # Step 2: optionally fast-forward the operator's dev clone (best-effort).
    if not dev_repo:
        return 0
    return _update_dev_clone(dev_repo)


if __name__ == "__main__":
    raise SystemExit(main())
