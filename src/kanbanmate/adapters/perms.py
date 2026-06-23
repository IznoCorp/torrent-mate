"""Materialise a worktree's ``.claude/settings.json`` permission profile (DESIGN §10).

A launched agent reads ``<worktree>/.claude/settings.json`` on startup. A restrictive
``permissions.defaultMode`` alone would BLOCK the agent on the very Bash commands the
orchestrated workflow needs (``git``, ``gh``, ``make``, the kanban helpers) — so the
profile's ``permissions.allow`` must be a CONCRETE, materialised list, and the mode is
PINNED into ``permissions.defaultMode``. Pinning the mode in the worktree file (not only
via a CLI flag) mitigates Claude Code bug #39057, where a mid-session mode reset could
silently widen permissions: a reset cannot widen past a file-pinned mode + concrete deny.

Four per-stage profiles (DESIGN §10) — one per autonomous ``/implement:*`` stage, named by
the matched ``(from, to)`` transition (``transitions.yml``):

* ``docs`` — read/write files + a minimal shell (``mkdir``/``ls``/``cat`` for the doc stages'
  ``docs/features/<codename>/`` tree + reading carried artifacts) + git read + local commit +
  ``gh issue`` + kanban helpers. NO push, NO PR ops, NO broad ``Bash``. This is the MOST
  RESTRICTIVE floor: the kill-switch downgrades every profile to ``docs``, and an unknown profile
  name degrades to it (see :func:`allow_list`).
* ``prepare`` — code edits + full git (including push to create/maintain a branch) + kanban
  helpers. NO ``gh`` (no PR ops yet — this is the create-branch stage).
* ``dev`` — code edits + full git (including push to open/maintain a PR) + ``gh`` (but NEVER
  merge) + ``make`` + kanban helpers + broad Bash for build/test.
* ``check`` — read-only-ish: ``Read`` + git read + ``gh`` read. The script-gate profile
  (typically no agent).

* ``merge`` — the autonomous Review→Merge stage (operator decision). Broad ``dev``-like surface,
  but it is the SOLE profile whose deny-list lifts EXACTLY ``gh pr merge`` (see
  :data:`_MERGE_PROFILE_LIFTED` / :func:`deny_list`) so it may squash-merge a green, mergeable PR.
  ``--admin``, ``--merge``/``--rebase`` strategies, direct pushes to ``main``, force-push, history
  rewrite, ref deletion, and the api/graphql/github-curl merge paths ALL stay denied even here.

The deny-list is applied to every profile. For the four non-merge profiles it is the FULL ban set
(DESIGN §10 — merge is human-only there): ``gh pr merge`` (and every reachable merge path),
direct-main-push, force-push (incl. ``--mirror`` / ``--force-with-lease``), branch/ref deletion,
and history rewrite (``rebase`` / ``reset --hard`` / ``commit --amend`` / ``push -f`` /
``filter-branch`` / reflog-prune). The ``merge`` profile gets that same set minus the single
``Bash(gh pr merge*)`` entry. Deny wins over allow. ``bypassPermissions`` is banned everywhere (it
would skip the deny layer entirely) — and refused outright when the daemon runs under root.

DEFENSE-IN-DEPTH: a string-prefix Bash deny-list cannot be made complete (an agent on the same OS
user has many equivalents). For the autonomous merge stage the deny-list narrows the merge surface
to a single squash path; GitHub branch protection (require status checks + block force-push /
deletion / direct-push on the default branch) remains the authoritative boundary and should be
configured. This list raises the bar against the routine / accidental paths an agent emits.

Layering: this is an ``adapters`` module — it performs filesystem I/O and may import ``core``
and ``ports`` but never ``app`` / ``daemon`` / ``cli`` (DESIGN §3.2). ``app`` wires it in.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Name of the heartbeat console-script shim (``[project.scripts]`` in pyproject.toml). The
# PostToolUse hook bakes the RESOLVED absolute path to this shim so the heartbeat fires even in
# a PATH-less agent environment (#25, port of the PoC ``perms._heartbeat_bin``).
_HEARTBEAT_SHIM = "kanban-heartbeat"

# The agent-facing kanban helper console scripts ([project.scripts]) that a launched agent invokes
# BY NAME from its worktree (the bare ``kanban`` CLI is intentionally excluded — agents never drive
# the daemon). These are symlinked into ``<worktree>/.claude/kanban-bin/`` (see
# :func:`provision_worktree_bin`) and that dir is prepended to the agent's PATH so the helpers
# always resolve from THE ENGINE'S OWN interpreter — independent of the agent's pyenv-global python
# (the live-e2e finding: pyenv shims dispatch per ACTIVE version, so a stale 3.11 global breaks any
# entry point added after that install, e.g. ``kanban-update-body``).
_KANBAN_HELPER_BINS: tuple[str, ...] = (
    "kanban-move",
    "kanban-comment",
    "kanban-progress",
    "kanban-update-body",
    "kanban-session-end",
    # kanban-done is the universal terminal action (Option 1, #1): every launched agent runs it as
    # its FINAL step, so it must be symlinked into EVERY worktree's kanban-bin regardless of profile.
    "kanban-done",
    "kanban-heartbeat",
    "kanban-update-main",
)

# The per-worktree helper-symlink dir, RELATIVE to a worktree root. The launch prepends its ABSOLUTE
# form to the agent's PATH (see app/actions); :func:`provision_worktree_bin` joins it under the
# worktree. It holds ONLY kanban-* symlinks → zero impact on the project's own python/pip.
KANBAN_BIN_RELDIR = ".claude/kanban-bin"


def _resolve_console_bin(name: str) -> str | None:
    """Resolve the absolute path to a console-script ``name`` — FAIL-SOFT to ``None``.

    Resolution order matches the PoC's heartbeat resolution (``engine/perms.py::_heartbeat_bin``):
    :func:`shutil.which` first (the shim on PATH — the common installed case), then a fallback to
    THE ENGINE'S OWN interpreter scripts dir (the ``bin``/``Scripts`` sibling of
    :data:`sys.executable`, where ``pip install`` drops console scripts). Resolving against
    ``sys.executable`` is the whole point of the pyenv fix: it pins every helper to the interpreter
    that is ACTUALLY RUNNING the daemon, not whatever ``pyenv global`` the agent's shell inherits.

    Args:
        name: The console-script name (e.g. ``"kanban-update-body"``).

    Returns:
        The absolute path to the shim if it can be located (on ``PATH`` or in the engine's scripts
        dir), else ``None`` so the caller can FAIL-SOFT (skip / bare command).
    """
    found = shutil.which(name)
    direct = Path(sys.executable).resolve().parent / name
    # A pyenv/rbenv-style SHIM (its resolved path sits under a ``shims/`` dir) is doubly wrong as a
    # helper target: it re-dispatches per the agent's ACTIVE pyenv version — DEFEATING the very
    # ``sys.executable`` pin this function exists for — and it HANGS in ``pyenv-which`` /
    # ``pyenv-exec`` under concurrent load (the ``kanban-done`` finalize stall that left a finished
    # agent stranded). When ``which`` lands on such a shim, prefer the engine interpreter's OWN
    # console script beside ``sys.executable`` whenever it exists — it bypasses pyenv entirely.
    if found and Path(found).parent.name == "shims" and direct.is_file():
        return str(direct)
    # Primary: the resolved path on PATH (the common installed case — mirrors the PoC's path).
    if found:
        return str(Path(found).resolve())
    # Fallback: the engine interpreter's scripts dir (``pip install`` drops console scripts beside
    # the python executable). Covers a venv whose ``bin/`` is not exported on the agent's PATH.
    if direct.is_file():
        return str(direct)
    return None


def _resolve_heartbeat_bin() -> str | None:
    """Resolve the absolute path to the ``kanban-heartbeat`` shim — FAIL-SOFT to ``None``.

    The PoC baked the ABSOLUTE path to ``bin/kanban-heartbeat`` (resolved from the skill root)
    into the worktree PostToolUse hook (``engine/perms.py::_heartbeat_bin``). NEW installs the shim
    as a console-script entry point (``[project.scripts]``: ``kanban-heartbeat``), resolved via the
    shared :func:`_resolve_console_bin` (PATH then the engine's scripts dir) — that covers a venv
    whose ``bin/`` is not on the agent's ``PATH``.

    The agent's launch environment may strip ``PATH`` to a minimal set, which silently no-ops the
    heartbeat shim (and so defeats the reaper's freshness signal). Baking the absolute path makes
    the hook robust to a PATH-less environment, matching the PoC.

    Returns:
        The absolute path to the shim if it can be located (on ``PATH`` or in the interpreter's
        scripts dir), else ``None`` so the caller can FAIL-SOFT to the bare command.
    """
    return _resolve_console_bin(_HEARTBEAT_SHIM)


# Pinned permission mode per profile (DESIGN §10; bug #39057 mitigation). The mode is written
# EXPLICITLY into ``permissions.defaultMode`` so a mid-session reset cannot silently widen the
# granted permissions: it can only fall back to this fixed value, which still enforces the
# concrete ``permissions.deny`` below. ``auto`` keeps the agent headless-safe (it never hangs on
# a permission prompt for the orchestrated surface) while still honouring the concrete
# ``permissions.deny`` below. Edit-accept-only default modes can still hang an unattended
# agent on non-edit prompts (the PoC's unattended-hang reason). ``bypassPermissions`` is
# never a value here — it would skip the deny layer (banned, §10).
_PINNED_MODE: dict[str, str] = {
    "docs": "auto",
    "prepare": "auto",
    "dev": "auto",
    "check": "auto",
    # 'merge' is the autonomous Review→Merge stage (operator decision: the merge transition
    # squash-merges a green, mergeable PR). Same pinned mode as the other stages.
    "merge": "auto",
    # 'triage' is the fast-track classifier (skiff feature). Same pinned mode.
    "triage": "auto",
}

# Fallback mode for an unknown profile name — the strictest pinned value. Unknown profiles also
# fall back to the ``docs`` allow-list (see :func:`allow_list`), so the whole settings object
# degrades safe rather than failing open.
_FALLBACK_MODE = "auto"

_PROVISION_DIRS = ("skills", "commands", "agents")

# The per-worktree issue-pin file (R1 enforcement, phase 29.1). Written under the worktree's
# ``.claude/`` at provision time; the kanban-* agent helpers read it (when present) and REFUSE a
# mismatched ``<issue>`` argument so a misattributed agent can never write to another ticket. The
# path is RELATIVE to a worktree root — :func:`write_issue_pin` joins it under the worktree, and the
# bin-side reader walks up from the cwd to find it.
ISSUE_PIN_RELPATH = ".claude/kanban-issue"

# The per-worktree PROJECT-pin file (ingress-multiproject §7). Written under the worktree's
# ``.claude/`` at provision time in a MULTI-PROJECT deployment; the kanban-* helpers read it (when
# present) so they resolve the SAME per-project store sub-root the daemon used (breadcrumbs/state
# must land in the right sub-root — the km-root invariant extended to multi-project). Absent in an
# N=1 deployment (the helpers fall back to the sole registry entry — byte-identical back-compat).
# Kept in lock-step with the bin-side reader ``bin/_pin._PROJECT_PIN_FILENAME``.
PROJECT_PIN_RELPATH = ".claude/kanban-project"

# Dev cruft excluded from the per-launch copy (keeps it small + avoids leaking caches/state).
_COPY_IGNORE = shutil.ignore_patterns(
    ".git",
    "__pycache__",
    "*.pyc",
    ".mypy_cache",
    ".pytest_cache",
    ".coverage",
    "node_modules",
    ".DS_Store",
)

# Universal deny-list — applied to EVERY profile (DESIGN §10). Merge is human-only; force-push
# and history rewrite are banned for ALL orchestrated sessions. Deny wins over allow. Ported
# verbatim from the PoC ``engine/perms.py`` ``_DENY`` (the authoritative ban set).
#
# DEFENSE-IN-DEPTH ONLY: a string-prefix Bash deny-list CANNOT be made complete (a determined
# agent on the same OS user has many equivalents and can bypass tool gating entirely). The REAL
# boundary for "merge is human-only" is GitHub branch protection (require PR review, block
# force-push + deletion on the default branch). Configure it on every orchestrated repo. This
# list raises the bar against the routine / accidental paths an agent would actually emit.
#
# Pattern design (covers ``git push`` AND ``git -C <dir> push``, flag-immediate OR after args):
#   - LONG flags (``--force``, ``--delete``) never appear inside a branch name, so a free glob
#     (``git push*--force*``) safely catches both positions.
#   - SHORT flags / symbols (``-f``, ``-d``, ``+``, ``:``) DO appear as substrings of real
#     branch names, so they are anchored on the SPACE before the token (``git push* -f*``) —
#     " -f" cannot occur mid-branch-name, so the agent's own ``git push -u origin <branch>`` is
#     NEVER denied, while the flag/refspec forms are.
_DENY: tuple[str, ...] = (
    # Issue-body writes — the SANCTIONED path is the pinned ``kanban-update-body`` helper
    # (§29.1), which preserves the **roadmap**/**codename**/**design**/**plans** markers and
    # validates body↔title coherence. A raw ``gh issue edit`` would bypass the pin + the marker
    # preservation, so it is denied for ALL profiles. ``gh issue view``/``list`` stay allowed: the
    # broad ``Bash(gh issue*)`` allow glob covers ``edit`` too, but deny wins over allow, so this
    # single deny entry is surgical (it removes only the write path).
    "Bash(gh issue edit*)",
    # PR merge — gh CLI, the github-curl helper, the REST API, and the GraphQL mutation
    "Bash(gh pr merge*)",
    "Bash(*pr-merge*)",  # the github-curl gh-api.sh pr-merge path used by pr-review
    "Bash(gh api*merge*)",  # gh api -X PUT .../pulls/N/merge
    "Bash(*mergePullRequest*)",  # gh api graphql mutation
    # gh pr merge HARDENING — these STAY denied even for the autonomous ``merge`` profile (only the
    # bare ``Bash(gh pr merge*)`` above is lifted, see :data:`_MERGE_PROFILE_LIFTED`). The merge
    # stage may ONLY squash-merge a green, mergeable PR: NO ``--admin`` (bypasses branch protection +
    # required status checks → could merge red/un-reviewed code), and NO non-squash strategy
    # (``--merge`` commit / ``--rebase`` rewrite — the latter is otherwise universally banned).
    "Bash(gh pr merge*--admin*)",
    "Bash(gh pr merge*--merge*)",
    "Bash(gh pr merge*--rebase*)",
    # ``gh pr merge`` also accepts the SHORT strategy aliases ``-m`` (--merge) and ``-r`` (--rebase);
    # the long-flag globs above miss them, so a merge-stage agent running ``gh pr merge <pr> -r``
    # would slip past the lifted bare ``Bash(gh pr merge*)`` and rebase-merge (history rewrite) or
    # ``-m`` a merge commit — defeating the squash-only invariant. Space-anchored so they never
    # false-match a branch name. ``-s`` (--squash) is deliberately NOT denied — it is the one
    # sanctioned strategy. These STAY denied for the merge profile (not in _MERGE_PROFILE_LIFTED).
    "Bash(gh pr merge* -m*)",
    "Bash(gh pr merge* -r*)",
    # force-push — long --force / --force-with-lease (free) + short -f / +refspec
    # (space-anchored), for ``git push`` and ``git -C <dir> push``.
    "Bash(git push*--force*)",
    "Bash(git -C*push*--force*)",
    "Bash(git push* -f*)",
    "Bash(git -C*push* -f*)",
    "Bash(git push* +*)",
    "Bash(git -C*push* +*)",
    # mirror-push — ``git push --mirror`` pushes ALL refs AND DELETES remote refs absent
    # locally, bypassing the force/delete patterns above; it is strictly worse than --force.
    # --mirror is a long flag (never a branch-name substring) so a free glob is safe.
    "Bash(git push*--mirror*)",
    "Bash(git -C*push*--mirror*)",
    # direct push to the default branch — NO agent (incl. the autonomous ``merge`` stage) ever
    # pushes to ``main``; it merges via the PR (``gh pr merge --squash``). GitHub branch protection
    # (block direct push to the default branch) is the AUTHORITATIVE boundary; these globs cover the
    # routine + known forms as defense-in-depth (a string-prefix deny-list cannot be made complete —
    # see the module docstring). Forms covered: ``git push … origin main``, the short ``<src>:main``
    # refspec, AND the fully-qualified ``<src>:refs/heads/main`` / ``+refs/heads/main`` /
    # ``refs/heads/main`` refspec (round-2 audit), for ``git push`` and ``git -C <dir> push``. The
    # merge agent's own push (the merge-main-IN commit to its OWN feature branch) targets neither, so
    # it is unaffected; only a push whose destination ref is the default branch is blocked.
    "Bash(git push*origin main*)",
    "Bash(git -C*push*origin main*)",
    "Bash(git push*:main*)",
    "Bash(git -C*push*:main*)",
    "Bash(git push*refs/heads/main*)",
    "Bash(git -C*push*refs/heads/main*)",
    # branch deletion — long --delete (free) + short -d + colon-refspec (space-anchored)
    "Bash(git push*--delete*)",
    "Bash(git -C*push*--delete*)",
    "Bash(git push* -d*)",
    "Bash(git -C*push* -d*)",
    "Bash(git push* :*)",
    "Bash(git -C*push* :*)",
    "Bash(git branch -D*)",
    "Bash(git branch --delete*)",
    # ref deletion via the plumbing command — ``git update-ref -d refs/heads/<x>`` deletes a
    # ref below ``git branch -D``, so it must be banned too. --delete is a long flag (free
    # glob); -d is space-anchored (a benign ``git update-ref refs/heads/foo <sha>`` is NOT
    # over-blocked); for ``git update-ref`` and the ``git -C`` form.
    "Bash(git update-ref* -d*)",
    "Bash(git update-ref*--delete*)",
    "Bash(git -C*update-ref* -d*)",
    "Bash(git -C*update-ref*--delete*)",
    # history rewrite (DESIGN §10 bans it for ALL profiles)
    "Bash(git rebase*)",
    "Bash(git reset --hard*)",
    "Bash(git commit*--amend*)",
    "Bash(git filter-branch*)",
    "Bash(git filter-repo*)",
    # history-destruction completeness — pruning the reflog then ``gc --prune`` makes
    # rewritten / dangling commits unrecoverable. ``git reflog expire*`` (plain ``git reflog``
    # stays allowed) and ``git gc*--prune*`` (plain ``git gc`` / ``--aggressive`` without
    # --prune stay allowed).
    "Bash(git reflog expire*)",
    "Bash(git gc*--prune*)",
    # runtime-root secrets — the daemon's ``launch_secret`` (HMAC key for the ad-hoc-launch op-token)
    # and the webhook secret live in the kanban runtime root, OUTSIDE every worktree. An agent has no
    # legitimate reason to read them; denying the obvious read paths (the Read tool + a cat/grep via
    # Bash) keeps a broad-Bash agent from minting a forged launch op-token. Defense-in-depth (a same-
    # uid string-deny cannot be airtight — the real boundary is OS isolation / a distinct uid).
    # Read tool: deny any path ENDING in the secret file name (path-anchored, no trailing *).
    "Read(*launch_secret)",
    "Read(*webhook_secret)",
    # Bash: deny the common file-read VERBS against the secret path — path-anchored (no trailing *) so
    # we block ``cat <root>/launch_secret`` (the forge vector) WITHOUT over-blocking a commit message
    # or a source grep that merely mentions the token (this repo self-hosts: 12+ files reference these
    # names, and a leading+trailing ``*`` glob would hard-deny `git commit -m '…launch_secret…'`).
    "Bash(cat *launch_secret)",
    "Bash(cat *webhook_secret)",
    "Bash(head *launch_secret)",
    "Bash(head *webhook_secret)",
    "Bash(tail *launch_secret)",
    "Bash(tail *webhook_secret)",
    "Bash(less *launch_secret)",
    "Bash(less *webhook_secret)",
    "Bash(more *launch_secret)",
    "Bash(more *webhook_secret)",
)

# The SINGLE deny entry lifted for the ``merge`` profile (and ONLY that profile, see
# :func:`deny_list`). ``gh pr merge`` is the squash-merge path the autonomous Review→Merge stage
# uses. Note ``gh pr merge`` (space) is matched ONLY by ``Bash(gh pr merge*)`` — the github-curl
# ``Bash(*pr-merge*)`` (hyphen), ``Bash(gh api*merge*)``, and ``Bash(*mergePullRequest*)`` entries
# do NOT match it and stay banned even for ``merge``, so the lift is exactly one path.
_MERGE_PROFILE_LIFTED: frozenset[str] = frozenset({"Bash(gh pr merge*)"})

# Concrete per-profile ``permissions.allow`` lists (DESIGN §10). The first four (docs/prepare/dev/
# check) are ported VERBATIM from the PoC ``engine/perms.py`` ``_PROFILE_ALLOW``; ``merge`` is the
# autonomous merge stage added later (operator decision — see :data:`_MERGE_PROFILE_LIFTED`).
#
# docs    — Read/Edit + git read + local commit + ``gh issue`` + kanban helpers. NO push, NO PR
#           ops, NO merge. This is the floor the kill-switch downgrades every profile to, and the
#           fallback for an unknown profile name (see :func:`allow_list`).
# prepare — code edits + full git (branch create + push) + kanban helpers. NO ``gh`` (no PR ops
#           yet — the create-branch stage).
# dev     — code edits + full git (including push to open/maintain a PR) + gh (but NOT merge,
#           which the deny-list blocks) + make + kanban helpers + broad Bash for build/test.
# check   — read-only-ish: Read + git read + gh read. The script-gate profile (typically no agent).
#
# No profile lists a literal merge command in ``allow``; for the four non-merge profiles the
# deny-list blocks merge regardless of any broad ``Bash(gh *)`` glob (deny wins over allow), so
# merge stays human-only there. The ``merge`` profile reaches ``gh pr merge --squash`` only because
# its deny-list lifts that one entry (NOT via an allow change) — see :func:`deny_list`.
_PROFILE_ALLOW: dict[str, tuple[str, ...]] = {
    "docs": (
        "Read",
        "Edit",
        # Minimal shell the doc stages need (hybrid flow, DESIGN §13): the design/plan stages run
        # `mkdir -p docs/features/<codename>/plan` and `ls`/`cat` the prior stage's carried
        # artifacts. Without these the headless docs session is DENIED and stalls on a permission
        # prompt it cannot answer. The minimum only — NOT a broad ``Bash``: docs still has no push /
        # gh-write, so the blast radius stays local-FS read + dir-create (the deny-list applies too).
        "Bash(mkdir*)",
        "Bash(ls*)",
        "Bash(cat*)",
        "Bash(git add*)",
        "Bash(git commit*)",
        "Bash(git status*)",
        "Bash(git log*)",
        "Bash(git diff*)",
        "Bash(gh issue*)",
        "Bash(kanban-comment*)",
        "Bash(kanban-done*)",
        "Bash(kanban-move*)",
        "Bash(kanban-progress*)",
        "Bash(kanban-update-body*)",
    ),
    "prepare": (
        "Read",
        "Edit",
        "Bash(git *)",
        "Bash(kanban-comment*)",
        "Bash(kanban-done*)",
        "Bash(kanban-move*)",
        "Bash(kanban-progress*)",
        "Bash(kanban-update-body*)",
    ),
    "dev": (
        "Read",
        "Edit",
        "Bash(git *)",
        "Bash(gh *)",
        "Bash(make *)",
        "Bash(kanban-comment*)",
        "Bash(kanban-done*)",
        "Bash(kanban-move*)",
        "Bash(kanban-progress*)",
        "Bash(kanban-update-body*)",
        "Bash",
    ),
    # check is the script-gate profile (typically no agent), but kanban-done is the UNIVERSAL
    # terminal action (#1) — every profile must allow it so any launched agent can end cleanly.
    "check": (
        "Read",
        "Bash(gh *)",
        "Bash(git *)",
        "Bash(kanban-done*)",
    ),
    # merge — the autonomous Review→Merge stage (operator decision). Same broad surface as ``dev``
    # (git merge-main-in + gh + make for the local gate + kanban helpers); what makes it special is
    # NOT the allow-list but the per-profile deny-list: ``merge`` is the ONLY profile whose deny
    # OMITS ``gh pr merge`` (see :data:`_MERGE_PROFILE_LIFTED` / :func:`deny_list`), so it — and only
    # it — may squash-merge a PR. Force-push, rebase, history rewrite, ref deletion, and every OTHER
    # merge path (api/graphql/github-curl) stay BANNED even here.
    "merge": (
        "Read",
        "Edit",
        "Bash(git *)",
        "Bash(gh *)",
        "Bash(make *)",
        "Bash(kanban-comment*)",
        "Bash(kanban-done*)",
        "Bash(kanban-move*)",
        "Bash(kanban-progress*)",
        "Bash(kanban-update-body*)",
        "Bash",
    ),
    # triage — the skiff fast-track classifier (read-only). It reads the ticket + a quick code peek
    # + the sensitive-paths config, then records its decision (the **track** body field + the route
    # breadcrumb). It NEVER edits source, pushes, or merges: no ``Edit``, no broad ``Bash`` — only
    # read + code-search verbs + the kanban decision/terminal helpers. The universal deny-list applies
    # unchanged, so merge / force-push / history-rewrite stay banned.
    "triage": (
        "Read",
        "Bash(cat*)",
        "Bash(ls*)",
        "Bash(grep*)",
        "Bash(rg*)",
        "Bash(git status*)",
        "Bash(git log*)",
        "Bash(git diff*)",
        "Bash(git show*)",
        "Bash(gh issue view*)",
        "Bash(kanban-comment*)",
        "Bash(kanban-update-body*)",
        "Bash(kanban-route*)",
        "Bash(kanban-done*)",
    ),
}

# Re-exported from ``core.profiles`` (helm DESIGN §13 layering fix): the validator lives in core and
# cannot import adapters, so the canonical name-set sits in core. ``core.profiles.PROFILES`` includes
# ``merge`` (the autonomous merge stage, operator decision — supersedes the historical
# merge=human-only floor for THIS stage only; every other profile still bans all merge paths).
# Existing callers of ``perms.PROFILES`` are unaffected.
from kanbanmate.core.profiles import PROFILES as PROFILES  # noqa: E402, PLC0414


def allow_list(profile: str) -> list[str]:
    """Return the CONCRETE ``permissions.allow`` list for ``profile``.

    Unknown profiles fall back to ``docs`` — the MOST RESTRICTIVE floor — so the settings
    degrade safe rather than failing open. This is a deliberate, documented improvement over the
    PoC, which fell back to ``dev`` (the broad profile): degrading to the minimal ``docs`` list on
    an unknown name is the conservative, fail-closed choice consistent with the genesis security
    stance. The shipped transitions name all four profiles, so this fallback is a safety net only.

    Args:
        profile: The profile name (case-sensitive); any known profile in
            :data:`~kanbanmate.core.profiles.PROFILES` — ``"docs"``, ``"prepare"``, ``"dev"``,
            ``"check"``, ``"merge"``, or ``"triage"``. An unknown name degrades to ``"docs"``.

    Returns:
        A new list of allow-entry strings for the profile.
    """
    return list(_PROFILE_ALLOW.get(profile, _PROFILE_ALLOW["docs"]))


def deny_list(profile: str = "") -> list[str]:
    """Return the ``permissions.deny`` list for ``profile``.

    Every profile EXCEPT ``merge`` gets the full universal ban set (DESIGN §10): merge, force-push,
    branch/ref deletion, and history rewrite are banned. The ``merge`` profile — the autonomous
    Review→Merge stage (operator decision) — is the SOLE exception: its deny-list omits ONLY
    :data:`_MERGE_PROFILE_LIFTED` (the ``gh pr merge`` path) so it can squash-merge. Every OTHER ban
    — force-push, rebase, ``reset --hard``, ``--amend``, ``--mirror``, branch/ref deletion, AND the
    other merge paths (``gh api …merge``, the GraphQL mutation, the github-curl ``pr-merge``) — stays
    in force even for ``merge``, so that stage may squash-merge a clean PR and do nothing else.

    Args:
        profile: The profile name. ``"merge"`` lifts the ``gh pr merge`` ban; any other value
            (including the default empty string) returns the full universal ban set.

    Returns:
        A new list of deny-entry strings.
    """
    if profile == "merge":
        return [entry for entry in _DENY if entry not in _MERGE_PROFILE_LIFTED]
    return list(_DENY)


def pinned_mode(profile: str) -> str:
    """Return the PINNED ``permissions.defaultMode`` value for ``profile``.

    The mode is fixed per profile and written explicitly into the worktree settings (DESIGN
    §10; bug #39057): a mid-session reset can only fall back to this value, never wider.
    Unknown profiles fall back to the strictest pinned mode.

    Args:
        profile: The profile name.

    Returns:
        The pinned mode string (never a bypass value).
    """
    return _PINNED_MODE.get(profile, _FALLBACK_MODE)


def build_settings(
    profile: str, *, issue: int | None = None, permission_mode: str | None = None
) -> dict[str, object]:
    """Build the ``.claude/settings.json`` dict for ``profile`` deterministically.

    The mode is pinned to the profile value, the allow-list is concrete and per-profile, and
    the deny-list is the universal ban set (merge / force-push / history rewrite). The result
    is built in a stable key order so a re-materialise produces byte-identical output.

    ``bypassPermissions`` is rejected up front for any profile name containing ``"bypass"`` and
    is always written as ``False`` (it would otherwise skip the deny layer — banned, §10).

    When ``issue`` is provided, a ``hooks.PostToolUse`` entry is added with matcher ``"*"`` and
    a command string ``<resolved-abs-shim> <issue>`` (DESIGN §8.3). The hook fires after every
    tool the agent uses so a working agent's heartbeat is refreshed on each action and never
    stales out of the reaper's ``HEARTBEAT_TTL`` window. The shim's ABSOLUTE path is resolved at
    materialisation time (#25, via :func:`_resolve_heartbeat_bin`) and ``shlex.quote``'d so the
    heartbeat fires even in a PATH-less agent environment — an unresolvable shim FAILS SOFT to the
    bare ``kanban-heartbeat <issue>`` command with a logged warning. The command is a STRING (not
    an exec-form array) — per the Claude Code hook schema the command IS the whole shell line. The
    shim always exits 0 (fail-soft), so the hook never blocks or influences the agent.

    Args:
        profile: The permission profile name (``"docs"``, ``"prepare"``, ``"dev"``, or
            ``"check"``).
        issue: The ticket issue number to bake into the PostToolUse heartbeat hook command.
            When ``None`` (default), no ``hooks`` block is emitted.

    Returns:
        A settings dict with ``permissions.defaultMode`` / ``allow`` / ``deny``,
        ``bypassPermissions: false``, ``enabledMcpjsonServers: ["kanban"]`` (pre-trusts the
        project-scoped ``kanban`` MCP server for headless agents, conduit §8.2), and optionally
        ``hooks.PostToolUse``.

    Raises:
        ValueError: If ``profile`` names a bypass mode (banned, §10).
    """
    # A bypass profile would skip the deny layer entirely — refuse it loudly (§10).
    if "bypass" in profile.lower():
        raise ValueError(f"bypassPermissions profile is banned (DESIGN §10): {profile!r}")
    # The per-transition permission_mode (minor (a)) overrides the profile's pinned default when
    # supplied — the CLI flag already emits the transition mode, so the worktree settings must agree
    # (previously _PINNED_MODE hardwired 'auto', a latent mismatch since all shipped rows use auto).
    # A bypass mode is rejected here too (it would skip the deny layer, §10); an empty/None mode
    # falls back to the profile's pinned value.
    if permission_mode and "bypass" in permission_mode.lower():
        raise ValueError(f"bypassPermissions mode is banned (DESIGN §10): {permission_mode!r}")
    default_mode = permission_mode if permission_mode else pinned_mode(profile)
    settings: dict[str, object] = {
        "permissions": {
            "defaultMode": default_mode,
            "allow": allow_list(profile),
            # Profile-aware: 'merge' lifts ONLY the gh-pr-merge ban; every other profile gets the
            # full universal ban set (deny wins over allow, so merge stays human-only elsewhere).
            "deny": deny_list(profile),
        },
        # Explicitly false everywhere: bypass would skip permissions.deny (DESIGN §10).
        "bypassPermissions": False,
        # Pre-trust the project-scoped ``kanban`` MCP server (conduit §8.2). Project ``.mcp.json``
        # servers are untrusted by default and these agents run non-interactively, so without this the
        # agent would block on an approval prompt. Scoped to the single named server (NOT a blanket
        # ``enableAllProjectMcpServers``) so only ``kanban`` is loaded without a prompt.
        "enabledMcpjsonServers": ["kanban"],
    }
    if issue is not None:
        # PostToolUse "*" → the heartbeat command after every tool (DESIGN §8.3). Claude Code
        # command-hooks have NO ``args`` field: the command IS the whole shell line, run via the
        # shell — so the issue is baked into the command STRING. The issue is cast to ``int`` (zero
        # shell-injection surface). The shim always exits 0 (fail-soft), so the hook never blocks
        # or influences the agent.
        #
        # #25 PORT (PoC ``perms.py::build_settings:300``) — bake the RESOLVED absolute shim path,
        # ``shlex.quote``'d, NOT the bare ``kanban-heartbeat``: the agent's launch env may strip
        # PATH, silently no-opping a bare-command hook and defeating the reaper's freshness signal.
        # FAIL-SOFT: an unresolvable shim degrades to the bare command with a LOGGED warning (the
        # heartbeat is best-effort liveness, never a launch blocker).
        resolved = _resolve_heartbeat_bin()
        if resolved is not None:
            heartbeat_command = f"{shlex.quote(resolved)} {int(issue)}"
        else:
            logger.warning(
                "kanban-heartbeat shim not found on PATH or in the interpreter scripts dir; "
                "baking the bare command into the PostToolUse hook (heartbeat fires only if the "
                "shim is on the agent's PATH)"
            )
            heartbeat_command = f"{_HEARTBEAT_SHIM} {int(issue)}"
        settings["hooks"] = {
            "PostToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": heartbeat_command,
                        }
                    ],
                }
            ]
        }
    return settings


def materialise_settings(
    profile: str,
    worktree_path: str | Path,
    *,
    issue: int | None = None,
    permission_mode: str | None = None,
) -> Path:
    """Write ``<worktree>/.claude/settings.json`` for ``profile``; return the written path.

    Creates ``<worktree>/.claude/`` if missing and writes the settings as pretty JSON. The
    agent reads it on startup, so it does not block on a permission prompt for the orchestrated
    Bash commands. Idempotent — overwriting an existing file is fine and deterministic.

    When ``issue`` is provided, a ``hooks.PostToolUse`` entry is injected (DESIGN §8.3) so the
    agent's tool activity refreshes its liveness heartbeat — a working agent never stales out of
    the reaper's ``HEARTBEAT_TTL`` window.

    Refuses to run under root with a bypass-equivalent intent: ``bypassPermissions`` refuses
    under root (DESIGN §10, non-root daemon). The settings written here always pin
    ``bypassPermissions: false``, but we still guard the root case so the design invariant is
    enforced at the materialisation boundary rather than relied upon downstream.

    Args:
        profile: The permission profile name (``"docs"``, ``"prepare"``, ``"dev"``, or
            ``"check"``).
        worktree_path: Absolute path to the git worktree root the agent runs in.
        issue: The ticket issue number to bake into the PostToolUse heartbeat hook command.
            When ``None`` (default), no ``hooks`` block is written.

    Returns:
        The path to the written ``settings.json``.

    Raises:
        ValueError: If ``profile`` names a bypass mode (banned, §10).
        PermissionError: If invoked as root (uid 0) — the daemon and agents run non-root
            (DESIGN §10; ``bypassPermissions`` refuses under root).
    """
    # Non-root invariant (DESIGN §10): the daemon and its agents must run non-root so a stray
    # bypass can never elevate. We assert it at the boundary that writes the agent's settings.
    # ``os.geteuid`` is POSIX-only; on a platform without it we cannot be root, so skip.
    geteuid = getattr(os, "geteuid", None)
    if geteuid is not None and geteuid() == 0:
        raise PermissionError(
            "materialise_settings refuses to run as root (DESIGN §10: non-root daemon; "
            "bypassPermissions refuses under root)"
        )

    settings = build_settings(profile, issue=issue, permission_mode=permission_mode)
    claude_dir = Path(worktree_path) / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    path = claude_dir / "settings.json"
    # Pretty JSON + trailing newline; sort_keys keeps re-materialise byte-identical.
    path.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def provision_worktree_skills(worktree: str | Path, config_dir: str | Path | None) -> list[Path]:
    """COPY the project's skills/commands/agents into ``<worktree>/.claude/``.

    A worktree is a clone checkout of the repo, where ``.claude/`` is gitignored — so the
    launched agent has none of the ``/implement:*`` skills (they live in the config repo).
    This provisions them so the column prompt (``/implement:phase``, …) actually resolves.

    We COPY rather than symlink so a write the agent makes inside its worktree stays in the
    worktree and CANNOT propagate through a symlink to mutate the shared config repo. Dev
    cruft (caches, .git) is excluded. The orchestrator OWNS these dirs in the (ephemeral)
    worktree: each launch REFRESHES them from ``config_dir`` so the agent runs current skills;
    ``settings.json`` (not a provisioned dir) is never touched.

    SECURITY CAVEAT: this is NOT a sandbox. The agent runs as the same OS user and, on the
    ``dev`` profile, has broad Bash — it can still reach the real config (or ``~/.kanban``)
    by ABSOLUTE path. Isolating a possibly-malicious agent (e.g. a prompt-injected public issue)
    requires a separate execution boundary (dedicated user / container). The copy only closes
    the in-scope symlink-write-through and prevents accidental shared-config corruption.

    Args:
        worktree: Absolute path to the git worktree the agent runs in.
        config_dir: Path to the project's ``.claude`` directory (the source of
            ``skills``/``commands``/``agents``). When empty/None, provisioning is disabled.

    Returns:
        The list of provisioned ``.claude/`` subdirectory paths (for logging/tests).
        No-op (empty list) when ``config_dir`` is empty/None or no source subdir exists.
    """
    if not config_dir:
        return []
    src_root = Path(config_dir)
    claude_dir = Path(worktree) / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    provisioned: list[Path] = []
    for name in _PROVISION_DIRS:
        src = src_root / name
        if not src.is_dir():
            continue
        dest = claude_dir / name
        # refresh: drop any prior provisioned copy/symlink so the agent runs CURRENT skills
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        elif dest.is_dir():
            shutil.rmtree(dest)
        shutil.copytree(src, dest, ignore=_COPY_IGNORE)
        provisioned.append(dest)
    return provisioned


def provision_worktree_bin(worktree: str | Path) -> Path:
    """SYMLINK the engine's own kanban-* console scripts into ``<worktree>/.claude/kanban-bin/``.

    A launched agent's tmux session inherits the shell environment where ``pyenv global`` may be a
    DIFFERENT python than the one running the daemon. pyenv shims dispatch per ACTIVE version, so a
    kanban-* entry point installed under the engine's interpreter but ABSENT from the agent's
    pyenv-global install exits 127 ("command not found") — the live-e2e ``kanban-update-body`` case
    (added in phase 29, missing from a stale 3.11 global). Others "work" only by luck of an older
    editable install whose entry points predate the new helper.

    This provisions a dedicated helper dir holding SYMLINKS to the RESOLVED ABSOLUTE console scripts
    of THE ENGINE'S OWN interpreter (resolved like the heartbeat shim: :func:`shutil.which` then the
    ``sys.executable`` scripts dir — see :func:`_resolve_console_bin`). The launch prepends this dir
    to the agent's ``PATH`` (see ``app/actions``), so every helper resolves from the engine's python
    regardless of the agent's pyenv-global version. The dir contains ONLY kanban-* symlinks → ZERO
    impact on the project's own python/pip.

    FAIL-SOFT + IDEMPOTENT: a helper that does not resolve is SKIPPED with a logged warning (never
    raised — the launch must not fail on a missing helper), and each launch REFRESHES the symlinks
    (a stale link is unlinked and re-created) so the agent always points at the current engine
    interpreter's scripts. Bare-relative the symlink TARGET is the absolute resolved path, so the
    link works no matter the cwd the agent walks into.

    Args:
        worktree: Absolute path to the git worktree the agent runs in.

    Returns:
        The path to the provisioned ``.claude/kanban-bin/`` directory (created even when no helper
        resolves, so the PATH prefix is always a real dir — an empty dir is harmless).
    """
    bin_dir = Path(worktree) / KANBAN_BIN_RELDIR
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in _KANBAN_HELPER_BINS:
        link = bin_dir / name
        # Refresh: drop any prior symlink/file so a stale target (e.g. a previous interpreter's
        # path) is replaced with the current engine interpreter's resolved script. ``is_symlink``
        # is checked first because a BROKEN symlink fails ``is_file``/``exists`` yet must be cleared.
        if link.is_symlink() or link.exists():
            link.unlink()
        target = _resolve_console_bin(name)
        if target is None:
            # FAIL-SOFT: a missing helper is a warning, never a launch blocker. The doctor
            # helper-shims check surfaces the same condition with a remediation hint.
            logger.warning(
                "kanban helper %r did not resolve on PATH or in the engine scripts dir; "
                "skipping its worktree symlink (agent will get 'command not found' if it needs it)",
                name,
            )
            continue
        link.symlink_to(target)
    return bin_dir


def write_issue_pin(worktree: str | Path, issue: int) -> Path:
    """Write the launched ``issue`` number into the worktree's pin file (R1 enforcement, §29.1).

    A launched agent's worktree is pinned to the single issue it was launched for: the kanban-*
    agent helpers (``kanban-update-body`` / ``kanban-move`` / ``kanban-comment`` /
    ``kanban-progress``) read this file (when present) and REFUSE a mismatched ``<issue>``
    argument, so a misattributed agent can never write to another ticket. The file holds just the
    integer issue number (one line). The pin is REQUIRED because R1 ("only touch your own ticket")
    is not enforceable by prompt wording alone (phase 29 adversarial verdict).

    Creates ``<worktree>/.claude/`` if missing. Idempotent — overwriting an existing pin with the
    same value is byte-identical; a relaunch for the same issue re-writes the same number.

    Args:
        worktree: Absolute path to the git worktree the agent runs in.
        issue: The launched issue number to pin the worktree to.

    Returns:
        The path to the written pin file.
    """
    claude_dir = Path(worktree) / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    path = claude_dir / "kanban-issue"
    # Just the integer (cast guards any caller passing a str-like) + trailing newline.
    path.write_text(f"{int(issue)}\n", encoding="utf-8")
    return path


def write_project_pin(worktree: str | Path, project_id: str) -> Path:
    """Write the launched ``project_id`` into the worktree's project-pin file (multi-project §7).

    In a MULTI-PROJECT deployment a launched agent's worktree is pinned to its project node id so the
    kanban-* helpers resolve the EXACT registry entry (``resolve_by_project_id``) — no issue-number
    collision ambiguity (two repos can both carry ``#5``) — AND target the SAME per-project store
    sub-root the daemon wrote to. The file holds just the project node id (one line). Absent in an
    N=1 deployment (the launch only calls this when ``Deps.multi_project`` is set), so single-project
    worktrees stay byte-identical and the helpers fall back to the sole entry.

    Creates ``<worktree>/.claude/`` if missing. Idempotent — a relaunch re-writes the same id.

    Args:
        worktree: Absolute path to the git worktree the agent runs in.
        project_id: The launched project's Project v2 node id to pin the worktree to.

    Returns:
        The path to the written project-pin file.
    """
    claude_dir = Path(worktree) / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    path = claude_dir / "kanban-project"
    path.write_text(f"{project_id}\n", encoding="utf-8")
    return path


def write_mcp_registration(
    worktree: str | Path, *, root: Path, issue: int, project_id: str | None, multi_project: bool
) -> Path:
    """Write ``<worktree>/.mcp.json`` registering the project-scoped ``kanban`` MCP server (conduit §8.1).

    Claude Code reads ``.mcp.json`` from the project root, so the launched headless agent gets the
    board-surface MCP server without any extra setup. The server is invoked as
    ``kanban mcp --root <root> --issue <n>`` (the same console-script the daemon installs); the issue
    pins the server to the single ticket the worktree was launched for. ``--project <project_id>`` is
    appended to ``args`` ONLY when ``multi_project`` is true (the per-project disambiguation the bins
    use) — an N=1 deployment omits it and the server resolves the sole registry entry.

    Mirrors the JSON-write idiom of :func:`materialise_settings` / :func:`write_issue_pin`: it creates
    ``<worktree>`` if missing, writes pretty JSON (``indent=2``) with a trailing newline, and returns
    the written path. Idempotent — a relaunch re-writes byte-identical content.

    Args:
        worktree: Absolute path to the git worktree the agent runs in (the ``.mcp.json`` project root).
        root: The kanban runtime root the MCP server reads state from (baked into ``--root``).
        issue: The launched issue number the server is pinned to (baked into ``--issue``).
        project_id: The launched project's ``ProjectV2`` node id; appended as ``--project`` only when
            ``multi_project`` is true (ignored otherwise — may be ``None`` in an N=1 deployment).
        multi_project: Whether the daemon drives >1 enabled project; gates the ``--project`` arg.

    Returns:
        The path to the written ``.mcp.json``.
    """
    # The base invocation: ``kanban mcp --root <root> --issue <n>`` (conduit §8.1). ``issue`` is cast
    # to ``int`` so the emitted arg is a clean integer string (zero injection surface).
    args = ["mcp", "--root", str(root), "--issue", str(int(issue))]
    # Multi-project (§7): append the per-project disambiguator so the server resolves the EXACT
    # registry entry (two repos can both carry ``#5``). N=1 omits it → the sole entry is used.
    if multi_project and project_id:
        args += ["--project", project_id]
    config = {"mcpServers": {"kanban": {"command": "kanban", "args": args}}}
    worktree_path = Path(worktree)
    worktree_path.mkdir(parents=True, exist_ok=True)
    path = worktree_path / ".mcp.json"
    # Pretty JSON + trailing newline, mirroring the neighbouring perms writers.
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


def ensure_manual_merge_mode(worktree: str | Path) -> bool:
    """Force the worktree's IMPLEMENTATION.md into MANUAL merge mode (DESIGN §10: merge is
    human-only).

    A kanban-launched ``/implement:pr-review`` reads ``**PR merge**:`` from IMPLEMENTATION.md
    and, in ``auto`` mode, squash-merges UNATTENDED. Since the Review column auto-triggers
    pr-review, we pin the worktree to ``manual`` so it hands off instead of merging in the
    REVIEW stage. (The sanctioned merge is the SEPARATE autonomous Review→Merge stage under the
    ``merge`` profile, which squash-merges via ``gh pr merge`` — not the pr-review skill's own
    terminal merge step, which stays disabled here.) Defense-in-depth ALONGSIDE the deny-list
    (which blocks merge commands for every NON-merge profile): the prompt's "without merging" is
    advisory, this is the mechanism.

    No-op (returns False) when IMPLEMENTATION.md is absent — we never create a malformed file;
    the deny-list still blocks the real merge path. Returns True when the field was set.

    Args:
        worktree: Absolute path to the git worktree the agent runs in.

    Returns:
        True when the ``**PR merge**: manual`` field was set (either replacing an existing
        ``**PR merge**:`` line in place or appended), False when IMPLEMENTATION.md is absent
        (no file created).
    """
    impl = Path(worktree) / "IMPLEMENTATION.md"
    if not impl.is_file():
        return False
    field = "**PR merge**: manual"
    lines = impl.read_text().splitlines()
    for i, line in enumerate(lines):
        if line.startswith("**PR merge**:"):
            lines[i] = field
            break
    else:
        lines.append(field)
    impl.write_text("\n".join(lines) + "\n")
    return True
