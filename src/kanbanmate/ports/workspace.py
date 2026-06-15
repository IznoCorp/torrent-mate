"""Workspace ports: per-ticket git worktree and tmux session boundaries.

These Protocols formalise the PoC's injectable subprocess seams
(``engine/worktree.py``, ``engine/tmux.py``) as abstract interfaces. The
production adapter (:mod:`kanbanmate.adapters.workspace`) shells out to ``git``
and ``tmux`` with ``shlex.quote`` on every interpolated path; tests inject a
fake runner.

Worktrees and sessions are keyed by the ticket's issue number — the same key
the filesystem :class:`~kanbanmate.ports.store.StateStore` uses — so the
dispatcher can correlate a card, its worktree and its session by one integer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Workspace(Protocol):
    """Idempotent per-ticket git worktree management on the integration base.

    The worktree is checked out DETACHED on ``origin/<base>``; branch creation
    is owned downstream by ``implement:create-branch``, so this port only
    ensures, removes, and DISCOVERS branches — it never creates them.
    """

    def ensure_clone(
        self, repo_url: str, base: str = "main", *, token_path: str | None = None
    ) -> Path:
        """Bootstraps the per-repo clone (the base of all worktrees).

        Idempotent and NON-DESTRUCTIVE: ``git init`` IN PLACE preserves
        untracked files such as the generated ``columns.yml`` — never
        re-clones. Self-heals a partial clone (origin missing). Fetches
        ``origin/<base>``.

        ``token_path`` (14.2) wires the credential helper; ``None`` →
        tokenless/public.

        Args:
            repo_url: The (tokenless) fetch URL, e.g.
                ``https://github.com/<org>/<repo>.git``.
            base: The integration base branch to fetch (default ``"main"``).
            token_path: Path to the access-token file; when set, a credential
                helper is installed so fetches authenticate without persisting
                the token. ``None`` → no helper (public). (Fully implemented
                in 14.2.)

        Returns:
            The absolute :class:`~pathlib.Path` to the clone directory.
        """
        ...

    def ensure_worktree(self, ticket: int, base: str = "main") -> Path:
        """Ensure a detached worktree on ``origin/<base>`` exists for ``ticket``.

        Idempotent: an already-registered worktree is reused without re-adding
        or re-fetching. Never passes ``--force``.

        Args:
            ticket: The issue number; names the worktree ``ticket-<n>``.
            base: The integration base branch to check out detached.

        Returns:
            The absolute :class:`~pathlib.Path` to the worktree directory.
        """
        ...

    def worktree_exists(self, ticket: int) -> bool:
        """Return whether ``ticket`` still has a registered worktree (replay-safety probe).

        A pure REGISTRY read (``git worktree list``) that NEVER runs ``git -C
        <worktree>`` against the worktree directory itself — so it does NOT emit
        an exit-128 "not a working tree" error when the worktree is already gone.
        The teardown path consults this BEFORE ``discover_branch`` /
        ``remove_worktree`` so a replay (second teardown) skips those steps
        cleanly instead of producing noisy ``git -C <gone>`` failures (phase
        28.1 replay-safety; also fixes the earlier e2e finding).

        Args:
            ticket: The issue number whose worktree presence to probe.

        Returns:
            ``True`` iff a worktree named ``ticket-<n>`` is still registered on
            the clone; ``False`` when it has been removed (or never existed).
        """
        ...

    def has_unpushed_work(self, ticket: int) -> bool:
        """Return whether ``ticket``'s worktree holds commits/changes not yet on a remote (#9).

        A CHEAP, conservative probe used by the Done-arrival reclaim (#9) to avoid silently
        destroying unpushed work: a worktree with uncommitted changes, OR commits ahead of its
        upstream (or no upstream at all while ahead of the base), is "unpushed". When this returns
        ``True`` the reclaim downgrades to Blocked + a sticky note instead of removing the worktree.

        It must be REPLAY-SAFE and FAIL-CLOSED: if the worktree is gone or the probe cannot run, it
        returns ``False`` (nothing to protect / unknown — let the normal teardown proceed) for the
        worktree-gone case, but a genuine "ahead/dirty" signal returns ``True``. Implementations run
        ``git -C <worktree>`` status/rev-list with a timeout (never ``shell=True``).

        Args:
            ticket: The issue number whose worktree to inspect.

        Returns:
            ``True`` iff the worktree has uncommitted changes or commits not on the remote;
            ``False`` when clean, fully pushed, or the worktree is gone/unprobeable.
        """
        ...

    def remove_worktree(self, ticket: int, *, force: bool = False) -> None:
        """Remove the worktree for ``ticket``.

        The normal lifecycle never forces; ``force=True`` is reserved for the
        Cancel teardown, where an aborted ticket's worktree usually has
        uncommitted changes.

        Args:
            ticket: The issue number whose worktree to remove.
            force: When ``True``, pass ``--force`` to remove a dirty worktree
                (teardown only).
        """
        ...

    def discover_branch(self, ticket: int) -> str | None:
        """Return the current branch of ``ticket``'s worktree, if any.

        We DISCOVER the branch (set by ``implement:create-branch``) rather than
        create it. A freshly created detached worktree has no branch yet.

        Args:
            ticket: The issue number whose worktree to inspect.

        Returns:
            The abbreviated branch name (e.g. ``feat/foo``), or ``None`` when
            the worktree is still detached / has no named branch.
        """
        ...

    def delete_branch(self, ticket: int, branch: str) -> None:
        """Force-delete the local ``branch`` (Cancel teardown only; DESIGN §8.2).

        The Cancel teardown force-deletes the cancelled ticket's local feature
        branch (``git branch -D``). The subprocess lives HERE in the adapter so
        :class:`~kanbanmate.app.actions.TeardownAction` stays free of
        ``subprocess`` — the action calls this seam instead of shelling out.

        Fail-soft and replay-safe: a missing branch (git rc 1/128 on a replay)
        is swallowed, and ``""``/``"HEAD"`` are no-ops (a detached worktree has
        no feature branch to delete). The deny-list that bans ``git branch -D``
        for LAUNCHED AGENTS does not apply: teardown runs in the dispatcher (no
        agent, no ``.claude/settings.json``), so this single mechanical
        transition is the only path that deletes a branch.

        Args:
            ticket: The issue number whose clone hosts the branch.
            branch: The local branch name to force-delete (``""``/``"HEAD"`` →
                no-op).
        """
        ...

    def run_transition_script(
        self, ticket: int, script: str, env: dict[str, str]
    ) -> tuple[int, str]:
        """Run a mechanical (no-LLM) transition ``script`` for ``ticket``.

        Folded onto :class:`Workspace` so :class:`~kanbanmate.app.actions.RunScriptAction`
        can discover the per-ticket worktree/branch and run the script through a SINGLE
        injected port (no extra :class:`Deps` field). The full contract is documented on
        :class:`ScriptRunner` below — the focused Protocol the production adapter also
        satisfies.

        Args:
            ticket: The issue number whose worktree roots the run (the ``cwd``).
            script: The script path to run (absolute, or relative to the clone/worktree).
            env: Extra environment variables merged on top of the inherited environment.

        Returns:
            A ``(exit_code, combined_output)`` tuple — stdout and stderr concatenated.
        """
        ...


class ScriptRunner(Protocol):
    """Run a mechanical (no-LLM) transition script for a ticket (DESIGN §11).

    A ``run_script`` transition (e.g. ``check-pr-ready.sh`` / ``check-merge-ready.sh``)
    spends no agent session — it runs a plain subprocess in the ticket's worktree and
    reports its exit code. The Protocol keeps the subprocess in the ADAPTER so
    :class:`~kanbanmate.app.actions.RunScriptAction` stays ``subprocess``-free (the
    action calls this seam instead of shelling out). The adapter MUST cap the run with a
    timeout so a wedged script never blocks the daemon tick.
    """

    def run_transition_script(
        self, ticket: int, script: str, env: dict[str, str]
    ) -> tuple[int, str]:
        """Run ``script`` for ``ticket`` and return ``(exit_code, combined_output)``.

        The script runs in the ticket's per-ticket worktree (the ``cwd``), with ``env``
        merged over the inherited environment so the check's hard-required
        ``KANBAN_REPO`` / ``KANBAN_BRANCH`` guards resolve. Stdout and stderr are merged
        so both diagnostic output and CI-check summaries are available to the caller. The
        subprocess is argv-list based (never ``shell=True``) and capped by a timeout.

        Args:
            ticket: The issue number whose worktree roots the run (the ``cwd``).
            script: The script path to run (absolute, or relative to the clone/worktree).
            env: Extra environment variables merged on top of the inherited environment
                (caller values win on collision).

        Returns:
            A ``(exit_code, combined_output)`` tuple — ``combined_output`` is the
            script's stdout and stderr concatenated.
        """
        ...


class Sessions(Protocol):
    """Detached tmux session lifecycle for launched agents.

    One session per ticket hosts the resumable ``claude`` process. The session
    name is the dispatcher's correlation key (e.g. ``ticket-<n>``).
    """

    def launch(self, name: str, cwd: str, command: str) -> str:
        """Create a detached tmux session ``name`` rooted at ``cwd`` running ``command``.

        Args:
            name: The session name (the dispatcher's correlation key).
            cwd: The working directory to root the session in (the worktree).
            command: The shell command line to run inside the session
                (typically the ``claude`` invocation).

        Returns:
            The session identifier (the ``name`` that was created), used by
            later :meth:`is_alive` / :meth:`kill` calls.
        """
        ...

    def capture(self, name: str) -> str:
        """Return the printable contents of session ``name``'s active pane.

        The launch flow polls this snapshot to detect the trust dialog or a
        ready REPL before typing the filled prompt (PoC ``engine/tmux.py``
        ``capture``). Without it the prompt would be typed before ``claude`` is
        ready and never submit — the exact launch bug this delivery path fixes.

        Args:
            name: The session name whose active pane to snapshot.

        Returns:
            The pane text (empty string when the pane has no output yet).
        """
        ...

    def send_text(self, name: str, text: str, *, literal: bool = True, enter: bool = False) -> None:
        """Send ``text`` to session ``name``, optionally followed by ``Enter``.

        The launch flow types the filled ``/implement:*`` prompt INTO the live
        REPL through this seam (PoC ``engine/tmux.py`` ``send_keys``), then
        submits it. ``enter=True`` sends a trailing ``Enter`` as a SEPARATE event
        so a literal prompt is typed first, then submitted.

        Args:
            name: The session name to type into.
            text: The literal text (``literal=True``) or the tmux key name
                (``literal=False``, e.g. ``"Enter"``).
            literal: When ``True`` (default), send raw text so slash-commands and
                spaces are typed verbatim; when ``False``, ``text`` is a key name.
            enter: When ``True``, send a trailing ``Enter`` key after ``text``.
        """
        ...

    def is_alive(self, name: str) -> bool:
        """Return whether the tmux session ``name`` currently exists.

        Args:
            name: The session name to probe.

        Returns:
            ``True`` iff the session exists.
        """
        ...

    def kill(self, name: str) -> None:
        """Kill the tmux session ``name``.

        Args:
            name: The session name to kill. Killing an absent session is the
                caller's concern (the teardown path tolerates it).
        """
        ...
