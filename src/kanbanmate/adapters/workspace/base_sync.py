"""Post-merge ``main`` refresh of the base/dev clones (DESIGN §10, conduit §11.2).

This adapter holds the local-git side of the ``kanban-update-main`` helper: fetching ``origin/main``
into the base clone and best-effort fast-forwarding the operator's dev clone. It was relocated here
(out of ``bin/kanban_update_main.py``) so the ``mcp`` board surface (conduit) can reuse the exact same
subprocess semantics via a permitted layer (``adapters``) instead of reaching into ``bin`` — a
behaviour-preserving move, the subprocess shape and the human-facing warnings are reproduced verbatim.

Safety (DESIGN §10 — merge is human-only): no merge, no force, no history rewrite. The only mutating
git call is ``git pull --ff-only`` (a strict fast-forward that refuses to create a merge commit), and
only after the dirty/branch guards pass. ``git fetch origin main`` is safe on a bare/base clone (no
working tree to clobber).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class BaseFetchError(RuntimeError):
    """The base-clone ``git fetch origin main`` exited non-zero.

    Carries the command's trimmed ``stderr`` so the caller can surface it in its own message
    (the bin formats ``"<prog>: base fetch failed: <stderr>"`` and returns exit ``1``).

    Attributes:
        stderr: The trimmed standard-error text of the failed fetch.
    """

    def __init__(self, stderr: str) -> None:
        """Store the failed fetch's trimmed stderr and build the message.

        Args:
            stderr: The trimmed standard-error text of the failed ``git fetch``.
        """
        super().__init__(stderr)
        self.stderr = stderr


def _git(args: list[str], cwd: str | Path) -> subprocess.CompletedProcess[str]:
    """Run a ``git`` command in ``cwd`` and capture its output.

    Reproduces the original ``bin/kanban_update_main._git`` subprocess shape verbatim
    (``capture_output=True``, ``text=True``, ``check=False``) so the relocated flow stays
    byte-for-byte equivalent.

    Args:
        args: The git sub-command and its arguments (without the leading ``git``).
        cwd: The repository directory to run in.

    Returns:
        The completed process (``returncode`` checked by the caller).
    """
    # No --force / no merge anywhere (DESIGN §10): callers only pass fetch / status / pull --ff-only.
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _is_dirty(repo: str | Path) -> bool:
    """Return whether ``repo``'s working tree has uncommitted or untracked changes.

    ``git diff`` / ``git diff --cached`` only catch tracked changes, so ``status --porcelain``
    is also consulted to catch untracked files that could conflict after a pull.

    Args:
        repo: The dev clone directory to inspect.

    Returns:
        ``True`` when the tree is dirty (tracked or untracked changes present).
    """
    if _git(["diff", "--quiet"], repo).returncode != 0:
        return True
    if _git(["diff", "--cached", "--quiet"], repo).returncode != 0:
        return True
    porcelain = _git(["status", "--porcelain"], repo)
    return bool(porcelain.stdout.strip())


def _current_branch(repo: str | Path) -> str:
    """Return ``repo``'s current branch name (empty on detached/unknown HEAD).

    Args:
        repo: The dev clone directory to inspect.

    Returns:
        The abbreviated current branch name, or ``""`` when it cannot be resolved.
    """
    result = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
    return result.stdout.strip() if result.returncode == 0 else ""


def fetch_base(clone: str | Path) -> None:
    """Fetch ``origin/main`` into the base ``clone`` (safe — no working tree to clobber).

    Mirrors step 1 of ``kanban-update-main``: a base/bare clone has no working tree, so the
    fetch can never clobber local work. A non-zero exit is fatal — it raises
    :class:`BaseFetchError` carrying the trimmed ``stderr`` so the caller can keep its exact
    failure message and exit code.

    Args:
        clone: The base clone directory to fetch into.

    Raises:
        BaseFetchError: When ``git fetch origin main`` exits non-zero.
    """
    fetch = _git(["fetch", "origin", "main"], clone)
    if fetch.returncode != 0:
        raise BaseFetchError(fetch.stderr.strip())


def ff_dev_clone(repo: str | Path) -> None:
    """Fast-forward ``repo`` on ``main`` when both guards pass; else print a skip-warning.

    Mirrors ``kanban-update-main._update_dev_clone`` verbatim (DESIGN §10 — best-effort): the
    fast-forward only runs when the working tree is clean AND ``repo`` is on ``main``; otherwise a
    clear skip-warning is printed to ``stderr`` and the function returns without raising. A failed
    ``git pull --ff-only`` is likewise reported on ``stderr`` but never raised, so a post-merge hook
    is never blocked by the operator's local clone state.

    ALL diagnostics (the progress line included) go to ``stderr``, never ``stdout``: the ``conduit``
    ``update_main`` MCP tool calls this from inside the stdio MCP server, whose ``stdout`` carries the
    JSON-RPC frames — a stray ``stdout`` write would corrupt the protocol stream the client parses.

    Args:
        repo: The operator's dev clone directory.
    """
    if _is_dirty(repo):
        print(
            f"WARNING: skipping dev clone update — working tree is dirty in {repo}",
            file=sys.stderr,
        )
        print(
            f"  Run 'git -C {repo} pull --ff-only' manually after committing your changes.",
            file=sys.stderr,
        )
        return
    branch = _current_branch(repo)
    if branch != "main":
        print(
            f"WARNING: skipping dev clone update — {repo} is on branch {branch!r}, not 'main'",
            file=sys.stderr,
        )
        print(
            "  Switch to main and run 'git pull --ff-only' manually when ready.",
            file=sys.stderr,
        )
        return
    # stderr (not stdout): see the module/function docstring — stdout is the MCP JSON-RPC stream.
    print(f"Fast-forwarding dev clone on main: {repo}", file=sys.stderr)
    # --ff-only is a strict fast-forward: it REFUSES to create a merge commit (DESIGN §10).
    pull = _git(["pull", "--ff-only"], repo)
    if pull.returncode != 0:
        print(f"WARNING: dev clone fast-forward failed: {pull.stderr.strip()}", file=sys.stderr)
