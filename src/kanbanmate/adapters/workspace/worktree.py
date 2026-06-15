"""Git-worktree adapter implementing the :class:`~kanbanmate.ports.workspace.Workspace` Protocol.

Ported from the PoC ``engine/worktree.py``. All git invocations use argv lists
(no ``shell=True``) so paths containing spaces are safe without manual
``shlex.quote``. The adapter never passes ``--force`` during normal lifecycle;
only the Cancel teardown (``force=True``) may force-remove a dirty worktree.

Layering: adapters MAY import ``kanbanmate.ports.*`` and ``kanbanmate.core.*``;
MUST NOT import ``app``, ``daemon``, or ``cli``.
"""

from __future__ import annotations

import fcntl
import os
import re
import shlex
import subprocess
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from collections.abc import Generator

Runner = Callable[..., "subprocess.CompletedProcess[Any]"]

# Per-script wall-clock cap (seconds). Long enough for ``gh pr checks`` to settle,
# short enough to fail fast on a wedged network — the daemon tick MUST NOT block on a
# hung transition script (network/hang safety, CLAUDE.md MANDATORY).
SCRIPT_TIMEOUT = 120

# Per-git-invocation wall-clock cap (seconds, #6). EVERY ``git`` call in this adapter must carry a
# timeout: the network-touching ones (``git fetch origin <base>``) can hang on a half-open socket,
# and a hung git invocation outside the per-action watchdog (e.g. the launch gate's pre-create
# ``ensure_worktree`` called directly on the tick thread) would freeze the daemon — the never-hang
# guarantee must hold for git too, not just the urllib client. 120s matches the script cap: long
# enough for a slow fetch, short enough to fail fast on a wedged network.
GIT_TIMEOUT = 120

# Sanitiser for lock resource names: replaces any character NOT in the safe set
# with ``_`` so a resource name (e.g. ``repo__owner/name``) cannot escape the
# ``<kanban_root>/locks/`` directory via path traversal (port of PoC
# ``engine/locks.py:15``).
_SAFE_RESOURCE = re.compile(r"[^A-Za-z0-9._-]+")

# Package root for resolving relative ``script:`` transition entries (e.g.
# ``bin/check-pr-ready.sh``), the PoC ``_SKILL_ROOT`` parity (engine/scripts.py:19).
# ``worktree.py`` lives at ``src/kanbanmate/adapters/workspace/worktree.py`` → three
# parents up is ``src/kanbanmate/``, which contains the shipped ``bin/check-*.sh``
# package data. Resolving against the PACKAGE (not the per-repo clone) means the gate
# scripts are found regardless of which clone the daemon drives, and they survive a
# clone re-creation — a relative entry never points into a target repo that has no
# ``bin/`` of its own (defect 1: the campaign's PR/CI + Merge gates were dead because
# the scripts resolved against the target clone, where they do not exist).
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent


class GitWorktreeWorkspace:
    """Idempotent per-ticket git worktree management on the integration base.

    Worktrees are checked out DETACHED on ``origin/<base>`` and live as
    siblings of the clone directory under ``<clone>/../worktrees/ticket-<n>``.
    Branch creation is owned downstream by ``implement:create-branch`` — this
    adapter only ensures, removes, and discovers branches.

    Attributes:
        clone_dir: The local clone of the repo (base of all worktrees for it).
        repo_slug: The ``owner/name`` slug used for the per-repo lock resource
            name (falls back to the clone dir basename when empty).
        kanban_root: The state-store root where ``locks/`` lives (defaults to
            the clone's parent so a lock dir always resolves next to the
            worktrees without needing explicit config).
    """

    def __init__(
        self,
        clone_dir: str | Path,
        *,
        runner: Runner = subprocess.run,
        repo: str = "",
        kanban_root: str | Path | None = None,
    ) -> None:
        """Initialise the worktree adapter.

        Args:
            clone_dir: Path to the local clone (the worktree base repo).
            runner: Subprocess runner (injected for tests). Defaults to
                :func:`subprocess.run`.
            repo: The ``owner/name`` slug identifying the repo. When empty,
                falls back to the clone directory basename so the per-repo
                lock is still per-clone. Defaults to ``""``.
            kanban_root: The state-store root where ``locks/`` lives. When
                ``None``, defaults to the clone's parent directory so a lock
                directory always resolves next to the worktrees without
                needing explicit config. Defaults to ``None``.
        """
        self._clone = Path(clone_dir)
        self._runner = runner
        self._repo = repo
        # Default kanban_root to the clone's parent so a lock dir always
        # resolves next to the worktrees without needing explicit config.
        self._kanban_root = Path(kanban_root) if kanban_root is not None else self._clone.parent

    # ------------------------------------------------------------------
    # Lock helpers (ported from PoC engine/locks.py:18-44)
    # ------------------------------------------------------------------

    def _repo_resource(self) -> str:
        """Return the per-repo lock resource name.

        The resource name is ``repo__<repo>`` when ``self._repo`` is
        truthy, otherwise ``repo__<clone_basename>``. The lock's own
        sanitiser turns ``owner/name`` → ``owner_name``, so
        ``repo__IznoCorp/demo`` becomes a file named
        ``repo__IznoCorp_demo.lock``.
        """
        if self._repo:
            return f"repo__{self._repo}"
        return f"repo__{self._clone.name}"

    @contextmanager
    def _resource_lock(self, resource: str) -> "Generator[None, None, None]":
        """Hold an exclusive advisory lock on *resource* for the duration of the block.

        Args:
            resource: A logical resource name (e.g. ``"repo__IznoCorp_demo"``).
                Non ``[A-Za-z0-9._-]`` chars are replaced with ``_`` so the name
                cannot escape the locks directory.

        Blocks until the lock is acquired; releases on exit (even on exception).
        A flock failure is NOT silently swallowed — it propagates as an
        :class:`OSError`.
        """
        locks = self._kanban_root / "locks"
        locks.mkdir(parents=True, exist_ok=True)
        safe = _SAFE_RESOURCE.sub("_", resource)
        path = locks / f"{safe}.lock"
        fh = path.open("a+")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            fh.close()

    # ------------------------------------------------------------------
    # Workspace Protocol methods
    # ------------------------------------------------------------------

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
                helper is installed that reads the token at fetch time (never
                persisted in ``.git/config``). The helper keeps ``origin``
                tokenless and resets any inherited helper chain so a
                global/system helper cannot shadow ours. ``None`` → no helper
                (public).

        Returns:
            The absolute :class:`~pathlib.Path` to the clone directory.
        """
        with self._resource_lock(self._repo_resource()):
            self._clone.mkdir(parents=True, exist_ok=True)
            if not (self._clone / ".git").exists():
                self._runner(["git", "init", str(self._clone)], check=True, timeout=GIT_TIMEOUT)
            # Set origin idempotently, INDEPENDENT of the init-vs-existing branch:
            # probe whether origin exists and `add` it if absent, else `set-url`.
            # This self-heals a clone left in a partial state (`.git` present but
            # origin missing — e.g. a crash between `git init` and `remote add`),
            # which the old branch-coupled logic could never recover (it would run
            # `set-url` against a missing remote and fail every re-run).
            has_origin = (
                self._runner(
                    [
                        "git",
                        "-C",
                        str(self._clone),
                        "remote",
                        "get-url",
                        "origin",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=GIT_TIMEOUT,
                ).returncode
                == 0
            )
            verb = "set-url" if has_origin else "add"
            self._runner(
                ["git", "-C", str(self._clone), "remote", verb, "origin", repo_url],
                check=True,
                timeout=GIT_TIMEOUT,
            )
            if token_path:
                # Credential helper reads the token from the file at fetch time (no token in config).
                host = urlparse(repo_url).hostname or "github.com"
                cred = f"credential.https://{host}"
                helper = (
                    '!f() { test "$1" = get && printf "password=%s\\n" '
                    f'"$(cat {shlex.quote(str(token_path))})"; }}; f'
                )
                self._runner(
                    [
                        "git",
                        "-C",
                        str(self._clone),
                        "config",
                        "--replace-all",
                        f"{cred}.username",
                        "x-access-token",
                    ],
                    check=True,
                    timeout=GIT_TIMEOUT,
                )
                # Make OUR file helper AUTHORITATIVE: an empty "" entry FIRST resets the inherited
                # helper chain for this host (git treats "" as "clear the list"), so a global/system
                # helper (osxkeychain / git-credential-manager) cannot shadow ours and make the
                # headless fetch auth with the wrong keychain token or prompt interactively.
                # --replace-all (not plain `config`) collapses any prior values to a single "" so a
                # RE-RUN (key then multi-valued ["", helper]) does not abort with exit 5; the
                # subsequent --add re-appends the file helper -> always exactly ["", <file helper>].
                self._runner(
                    [
                        "git",
                        "-C",
                        str(self._clone),
                        "config",
                        "--replace-all",
                        f"{cred}.helper",
                        "",
                    ],
                    check=True,
                    timeout=GIT_TIMEOUT,
                )
                self._runner(
                    ["git", "-C", str(self._clone), "config", "--add", f"{cred}.helper", helper],
                    check=True,
                    timeout=GIT_TIMEOUT,
                )
            self._runner(
                ["git", "-C", str(self._clone), "fetch", "origin", base],
                check=True,
                timeout=GIT_TIMEOUT,
            )
        return self._clone.resolve()

    def ensure_worktree(self, ticket: int, base: str = "main") -> Path:
        """Ensure a detached worktree on ``origin/<base>`` exists for *ticket*.

        Idempotent: an already-registered worktree is reused without re-adding
        or re-fetching. Never passes ``--force``.

        Args:
            ticket: The issue number; names the worktree ``ticket-<n>``.
            base: The integration base branch to check out detached.

        Returns:
            The absolute :class:`~pathlib.Path` to the worktree directory.
        """
        target = (self._clone.parent / "worktrees" / f"ticket-{ticket}").resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        existing = self._worktree_paths()
        if str(target) in existing:
            return target

        with self._resource_lock(self._repo_resource()):
            # The bare ``git fetch origin <base>`` touches the network and ran WITHOUT a timeout
            # before #6 — and ``ensure_worktree`` is called directly on the tick thread by the launch
            # gate pre-create (outside the per-action watchdog), so a half-open fetch here would
            # freeze the daemon. The timeout makes the never-hang guarantee hold for git too.
            self._runner(
                ["git", "-C", str(self._clone), "fetch", "origin", base],
                check=True,
                timeout=GIT_TIMEOUT,
            )
            self._runner(
                [
                    "git",
                    "-C",
                    str(self._clone),
                    "worktree",
                    "add",
                    "--detach",
                    str(target),
                    f"origin/{base}",
                ],
                check=True,
                timeout=GIT_TIMEOUT,
            )
        return target

    def worktree_exists(self, ticket: int) -> bool:
        """Return whether *ticket*'s worktree is still registered (replay-safety probe).

        Reads the clone's worktree REGISTRY via ``git worktree list --porcelain``
        (the same listing :meth:`ensure_worktree` consults) and tests membership
        of the ``ticket-<n>`` target path. Crucially it runs ``git -C <clone>``
        — NEVER ``git -C <worktree>`` — so it never hits the exit-128 "not a
        working tree" failure when the worktree is already gone (the noisy
        replay path the teardown guard avoids; phase 28.1).

        Args:
            ticket: The issue number whose worktree presence to probe.

        Returns:
            ``True`` iff a worktree named ``ticket-<n>`` is registered on the
            clone; ``False`` otherwise.
        """
        target = (self._clone.parent / "worktrees" / f"ticket-{ticket}").resolve()
        return str(target) in self._worktree_paths()

    def has_unpushed_work(self, ticket: int) -> bool:
        """Return whether *ticket*'s worktree holds uncommitted or unpushed work (#9).

        Two cheap, timed ``git -C <worktree>`` probes, FAIL-CLOSED to "no unpushed work" on any
        error (a gone/unprobeable worktree has nothing to protect):

        1. ``git status --porcelain`` — any non-empty output means uncommitted/untracked changes,
           EXCEPT the orchestrator's own merge-mode pin (phase 35): the launch step
           :func:`~kanbanmate.adapters.perms.ensure_manual_merge_mode` rewrites the
           ``**PR merge**:`` line of IMPLEMENTATION.md on EVERY launch, so a freshly launched but
           otherwise idle worktree always shows `` M IMPLEMENTATION.md``. Treating that pin as
           unpushed work false-positived the Done-arrival reclaim forever (every reclaim downgraded
           to Blocked even when the agent made zero commits). So when the porcelain output's ONLY
           entry is a modified IMPLEMENTATION.md, we diff that file and ignore it IFF the only
           changed content lines are ``**PR merge**:`` pin lines. ANY other modified/untracked path,
           or any non-pin diff content, still counts as real unpushed work.
        2. ``git log @{u}..HEAD`` (or, with NO upstream, ``git log origin/HEAD..HEAD``) — any commit
           listed means the branch is AHEAD of the remote (unpushed commits).

        Used by the Done-arrival reclaim to downgrade to Blocked + a sticky instead of silently
        destroying unpushed work (rank-9 verdict). Conservative by design: a true "ahead/dirty"
        signal returns ``True``; everything else (clean, fully pushed, gone, probe error) is
        ``False`` so the normal reclaim proceeds.

        Args:
            ticket: The issue number whose worktree to inspect.

        Returns:
            ``True`` iff the worktree has uncommitted changes or unpushed commits.
        """
        if not self.worktree_exists(ticket):
            return False
        target = (self._clone.parent / "worktrees" / f"ticket-{ticket}").resolve()
        # Probe 1: uncommitted / untracked changes (dirty working tree).
        try:
            status = self._runner(
                ["git", "-C", str(target), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
                timeout=GIT_TIMEOUT,
            )
            # Keep the porcelain output's per-line leading status columns intact (rstrip only): a
            # worktree-modified file is `` M <path>`` and the leading space is column 1 (the staged
            # status), so a full ``.strip()`` would corrupt the XY-column parsing below.
            porcelain = (status.stdout or "").rstrip("\n")
            if porcelain.strip():
                # Ignore the orchestrator's own merge-mode pin (phase 35): when the SOLE dirty
                # entry is a modified IMPLEMENTATION.md and its diff touches ONLY ``**PR merge**:``
                # lines, the dirtiness was authored by ``ensure_manual_merge_mode`` at launch, not
                # by the agent — so it must NOT count as unpushed work.
                if not self._only_merge_mode_pin_dirty(target, porcelain):
                    return True
        except Exception:  # noqa: BLE001 — fail-closed: an unprobeable worktree protects nothing
            return False
        # Probe 2: commits ahead of the upstream (unpushed). Prefer the configured upstream
        # (``@{u}``); when the branch has none, compare against ``origin/HEAD`` so a never-pushed
        # branch with local commits still reads as ahead. ``check=False`` so a missing ref does not
        # raise — an empty/parse-failure result is treated as "not ahead" (fail-closed).
        for upstream in ("@{u}", "origin/HEAD"):
            try:
                ahead = self._runner(
                    ["git", "-C", str(target), "log", "--oneline", f"{upstream}..HEAD"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=GIT_TIMEOUT,
                )
            except Exception:  # noqa: BLE001 — fail-closed on a probe error
                return False
            if ahead.returncode == 0:
                # A successful rev walk: ahead iff it listed any commit.
                return bool((ahead.stdout or "").strip())
        # Neither ref resolved (detached/no upstream/no origin HEAD) — treat as not-ahead.
        return False

    def remove_worktree(self, ticket: int, *, force: bool = False) -> None:
        """Remove the worktree for *ticket*.

        The normal lifecycle never forces; ``force=True`` is reserved for the
        Cancel teardown, where an aborted ticket's worktree usually has
        uncommitted changes.

        Args:
            ticket: The issue number whose worktree to remove.
            force: When ``True``, pass ``--force`` to remove a dirty worktree
                (teardown only).
        """
        target = (self._clone.parent / "worktrees" / f"ticket-{ticket}").resolve()
        argv = ["git", "-C", str(self._clone), "worktree", "remove"]
        if force:
            argv.append("--force")
        argv.append(str(target))
        self._runner(argv, check=True, timeout=GIT_TIMEOUT)

    def discover_branch(self, ticket: int) -> str | None:
        """Return the current branch of *ticket*'s worktree, if any.

        We DISCOVER the branch (set by ``implement:create-branch``) rather than
        create it. A freshly created detached worktree reports ``"HEAD"`` —
        that is mapped to ``None``, matching the Protocol's ``str | None``
        contract. An empty result is also mapped to ``None``.

        A GONE worktree (defect 10) — e.g. a ticket reap-torn-down then re-dragged
        Blocked → InProgress → PR/CI — must NOT raise: ``git -C <gone> rev-parse``
        exits 128, and a raised ``CalledProcessError`` would propagate through
        ``run_check_script`` past the watchdog and STRAND the card in PR/CI with no
        routing. Instead we report ``None`` (the caller maps it to ``KANBAN_BRANCH=""``,
        the check scripts' HONEST-fail path → exit 1 → ``on_fail`` routes the card,
        never a strand). The probe is fail-CLOSED to ``None`` on a missing directory
        OR any subprocess error.

        Args:
            ticket: The issue number whose worktree to inspect.

        Returns:
            The abbreviated branch name (e.g. ``feat/foo``), or ``None`` when the
            worktree is detached / has no named branch / is GONE / the probe failed.
        """
        target = (self._clone.parent / "worktrees" / f"ticket-{ticket}").resolve()
        # ``check=False`` (defect 10): a GONE worktree makes ``git -C <gone> rev-parse`` exit 128;
        # with ``check=True`` that raised ``CalledProcessError``, propagated through
        # ``run_check_script`` past the watchdog, and STRANDED the card in PR/CI. ``check=False`` +
        # the non-zero-rc guard below maps it to ``None`` instead — the caller routes on
        # ``KANBAN_BRANCH=""`` (the scripts' honest-fail path), never a strand. A raised runner
        # (an injected/mock runner that throws, or a subprocess spawn error) is likewise swallowed.
        try:
            res = self._runner(
                ["git", "-C", str(target), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
                timeout=GIT_TIMEOUT,
            )
        except Exception:
            # The worktree is gone / git could not be spawned → no branch (honest-fail routing).
            return None
        # A non-zero rc (e.g. exit 128 "not a working tree" on a removed worktree) → no branch,
        # never raise: the caller routes on KANBAN_BRANCH="" rather than stranding the card.
        if getattr(res, "returncode", 0) != 0:
            return None
        branch = (res.stdout or "").strip()
        if branch in ("", "HEAD"):
            return None
        return branch

    def delete_branch(self, ticket: int, branch: str) -> None:
        """Force-delete the local *branch* in *ticket*'s clone (teardown only).

        Runs ``git -C <clone> branch -D <branch>`` as an argv list (never
        ``shell=True``). Fail-soft and replay-safe: ``check=False`` means a
        missing branch (git exits 1 "branch not found", or 128) does NOT raise,
        and any subprocess-level error is swallowed too — a second teardown
        destroys nothing and never raises (DESIGN §8.2 / PoC ``engine/teardown``
        step 4). ``""`` (no branch) and ``"HEAD"`` (a detached worktree) have no
        feature branch to delete, so they are clean no-ops.

        Args:
            ticket: The issue number whose clone hosts the branch.
            branch: The local branch name to force-delete (``""``/``"HEAD"`` →
                no-op).
        """
        if not branch or branch == "HEAD":
            return
        # check=False so the expected non-zero rc on a replay (branch already
        # deleted) does not raise; wrap defensively so an injected runner that
        # raises is still swallowed (fail-soft, mirroring the PoC ``_soft``).
        try:
            self._runner(
                ["git", "-C", str(self._clone), "branch", "-D", branch],
                check=False,
                timeout=GIT_TIMEOUT,
            )
        except Exception:  # noqa: BLE001 — fail-soft: a branch-delete failure never aborts teardown
            pass

    def run_transition_script(
        self, ticket: int, script: str, env: dict[str, str]
    ) -> tuple[int, str]:
        """Run a mechanical (no-LLM) transition *script* in *ticket*'s worktree.

        Ported from the PoC ``engine/scripts.py::run_transition_script``. The script
        runs as an argv-list subprocess (NEVER ``shell=True``) rooted in the per-ticket
        worktree, with *env* merged over the inherited environment (caller values win) so
        the check's ``KANBAN_REPO`` / ``KANBAN_BRANCH`` guards resolve. Stdout and stderr
        are merged so both diagnostics and CI summaries reach the caller. A relative
        *script* path is resolved against the PACKAGE ROOT (where the shipped
        ``bin/`` check scripts live as package data, PoC ``_SKILL_ROOT`` parity); an
        absolute path is used verbatim.

        The run is capped by :data:`SCRIPT_TIMEOUT` — a wedged script must never block the
        daemon tick (network/hang safety, CLAUDE.md MANDATORY). ``check`` is omitted so a
        non-zero exit does NOT raise: the exit code IS the verdict the caller routes on.

        Args:
            ticket: The issue number whose worktree roots the run (the ``cwd``).
            script: The script path (absolute, or relative to the package root).
            env: Extra environment variables merged on top of ``os.environ``.

        Returns:
            A ``(exit_code, combined_output)`` tuple — stdout and stderr concatenated.

        Raises:
            subprocess.TimeoutExpired: If the script exceeds :data:`SCRIPT_TIMEOUT`.
        """
        cwd = (self._clone.parent / "worktrees" / f"ticket-{ticket}").resolve()
        path = Path(script)
        if not path.is_absolute():
            # Relative entries (e.g. ``bin/check-pr-ready.sh``) resolve against the PACKAGE
            # ROOT, where the shipped check scripts live as package data — NOT against the
            # per-repo clone (defect 1: the target clone has no ``bin/`` of its own, so the
            # gate scripts were unreachable and both campaign gates failed silently). This
            # mirrors the PoC ``_SKILL_ROOT`` resolution (engine/scripts.py:19) and survives
            # clone re-creation. The ``cwd`` stays the per-ticket worktree so the scripts'
            # ``git``/``gh`` calls operate on the ticket's branch.
            path = (_PACKAGE_ROOT / script).resolve()
        merged_env = {**os.environ, **env}
        result = self._runner(
            [str(path)],
            cwd=str(cwd),
            env=merged_env,
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT,
        )
        combined = (result.stdout or "") + (result.stderr or "")
        return result.returncode, combined

    # ------------------------------------------------------------------
    # Internal helpers (ported from PoC engine/worktree.py)
    # ------------------------------------------------------------------

    def _only_merge_mode_pin_dirty(self, target: Path, porcelain: str) -> bool:
        """Return whether the worktree's ONLY dirtiness is the orchestrator's merge-mode pin (35).

        ``has_unpushed_work`` calls this when ``git status --porcelain`` is non-empty. It returns
        ``True`` (the dirtiness is ours, ignore it) only when BOTH hold:

        1. The porcelain output's SOLE entry is a MODIFIED (not added/deleted/untracked)
           ``IMPLEMENTATION.md`` — exactly the `` M IMPLEMENTATION.md`` line
           :func:`~kanbanmate.adapters.perms.ensure_manual_merge_mode` produces at launch. Any other
           path, any untracked (``??``) entry, or more than one entry → ``False`` (real work).
        2. ``git diff -- IMPLEMENTATION.md`` shows ONLY ``**PR merge**:`` content lines changed
           (added/removed). Diff hunk/header lines (``+++``/``---``/``@@``/``diff``/``index``) are
           ignored; a single non-pin ``+``/``-`` content line → ``False`` (the agent edited the file
           too, so the worktree holds genuine uncommitted work).

        Conservative / fail-closed: on any probe error this returns ``False`` so the caller treats
        the worktree as dirty (protecting possibly-real work), matching ``has_unpushed_work``'s
        fail-closed stance. The pin-detection logic mirrors the field
        :func:`~kanbanmate.adapters.perms.ensure_manual_merge_mode` rewrites (``**PR merge**:``).

        Args:
            target: The resolved worktree path.
            porcelain: The ``git status --porcelain`` output with per-line status columns intact
                (trailing newline stripped, but NOT the leading XY columns), known non-empty.

        Returns:
            ``True`` iff the sole dirtiness is the merge-mode pin on IMPLEMENTATION.md.
        """
        # Step 1: the porcelain must contain EXACTLY one entry, and it must be a modified
        # IMPLEMENTATION.md. ``splitlines()`` yields one line per changed path (columns intact);
        # more than one path means other work is present.
        lines = porcelain.splitlines()
        if len(lines) != 1:
            return False
        entry = lines[0]
        # Porcelain status fields are columns 1-2 (XY), the path follows after one space. A modified
        # (not staged-new/deleted/untracked) IMPLEMENTATION.md is `` M IMPLEMENTATION.md`` (worktree
        # modified) — accept the space+M form and the path exactly. Anything else is real work.
        if entry[3:] != "IMPLEMENTATION.md":
            return False
        xy = entry[:2]
        # Only an UNSTAGED or STAGED modification counts as the pin (M in either column). Reject
        # additions/deletions/renames/untracked (??), which are never the pin's signature.
        if "M" not in xy or "?" in xy:
            return False

        # Step 2: diff the file and confirm every CONTENT change is a ``**PR merge**:`` pin line.
        try:
            diff = self._runner(
                ["git", "-C", str(target), "diff", "--", "IMPLEMENTATION.md"],
                capture_output=True,
                text=True,
                check=True,
                timeout=GIT_TIMEOUT,
            )
        except Exception:  # noqa: BLE001 — fail-closed: an unprobeable diff protects nothing
            return False

        saw_pin_change = False
        for line in (diff.stdout or "").splitlines():
            # Skip the unified-diff frame: file headers (``+++``/``---``), hunk headers (``@@``),
            # and the ``diff``/``index``/``old``/``new`` metadata lines. Only ``+``/``-`` CONTENT
            # lines describe an actual change.
            if line.startswith(("+++", "---", "@@", "diff ", "index ", "old ", "new ")):
                continue
            if line.startswith(("+", "-")):
                content = line[1:].strip()
                # A pin change is an added/removed ``**PR merge**:`` line. A blank content line
                # (e.g. a trailing-newline artefact) is benign and ignored; anything else is a real
                # agent edit, so the worktree holds genuine work.
                if content.startswith("**PR merge**:"):
                    saw_pin_change = True
                    continue
                if content == "":
                    continue
                return False
        # Only treat the worktree as "pin-only dirty" when we actually saw a pin change AND nothing
        # else — an empty diff (no content lines) is NOT the pin signature, so fall through to real.
        return saw_pin_change

    def _worktree_paths(self) -> set[str]:
        """Return the set of absolute worktree paths registered on the clone.

        Parses ``git worktree list --porcelain`` output, collecting every
        ``worktree ``-prefixed line.
        """
        res = self._runner(
            ["git", "-C", str(self._clone), "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            timeout=GIT_TIMEOUT,
        )
        paths: set[str] = set()
        for line in (res.stdout or "").splitlines():
            if line.startswith("worktree "):
                paths.add(line[len("worktree ") :].strip())
        return paths
