"""Tests for the worktree permission-profile materialiser (:mod:`kanbanmate.adapters.perms`).

These assert the security invariants of DESIGN §10 directly against the materialised
``.claude/settings.json``: the mode is PINNED per profile (bug #39057), the merge command and
force-push / history-rewrite bans hold for ALL FOUR profiles (``docs`` / ``prepare`` / ``dev`` /
``check``), and ``bypassPermissions`` is always false. Each test writes into a real ``tmp_path``
worktree and reads the JSON back — the file the launched agent would actually read.

The four per-stage profiles are ported VERBATIM from the PoC (``tests/test_perms.py``), dropping
its fifth ``merge`` profile: KanbanMate has no agent profile that may merge (merge = human-only),
so the merge ban is universal.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
from pathlib import Path

import pytest

from kanbanmate.adapters.perms import (
    _KANBAN_HELPER_BINS,
    KANBAN_BIN_RELDIR,
    PROFILES,
    _resolve_heartbeat_bin,
    allow_list,
    build_settings,
    deny_list,
    ensure_manual_merge_mode,
    materialise_settings,
    pinned_mode,
    provision_worktree_bin,
    provision_worktree_skills,
    write_issue_pin,
)

# The banned command surfaces that MERGE-IS-HUMAN-ONLY (DESIGN §10) forbids for every profile.
# A profile is compliant when each fragment is absent from ``allow`` AND present in ``deny``.
_BANNED_FRAGMENTS: tuple[str, ...] = (
    "gh pr merge",  # PR merge — human only
    "push*--force",  # force-push (long flag)
    " -f",  # force-push (short flag, space-anchored)
    "--mirror",  # mirror-push (deletes remote refs)
    "git rebase",  # history rewrite
    "git reset --hard",  # history rewrite
    "--amend",  # history rewrite (commit amend)
)


def _read_settings(path: Path) -> dict[str, object]:
    """Load and return the JSON object written at ``path``.

    Args:
        path: The materialised ``settings.json`` path.

    Returns:
        The parsed settings dict.
    """
    # ``json.loads`` is typed ``Any``; assert the top-level shape so callers get a typed dict.
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _permissions(settings: dict[str, object]) -> dict[str, object]:
    """Return the ``permissions`` sub-object, asserting it is a dict.

    Args:
        settings: The full settings dict.

    Returns:
        The ``permissions`` mapping.
    """
    perms = settings["permissions"]
    assert isinstance(perms, dict)
    return perms


def _post_tool_use_entries(settings: dict[str, object]) -> list[dict[str, object]]:
    """Return the ``hooks.PostToolUse`` matcher entries, asserting the nested shape.

    Drilling through ``dict[str, object]`` would surface ``object`` at each step (un-indexable
    for mypy), so each level is narrowed with an ``isinstance`` assertion before descent.

    Args:
        settings: The full settings dict.

    Returns:
        The list of PostToolUse matcher-entry dicts.
    """
    hooks = settings["hooks"]
    assert isinstance(hooks, dict)
    entries = hooks["PostToolUse"]
    assert isinstance(entries, list)
    for entry in entries:
        assert isinstance(entry, dict)
    return entries


def _first_heartbeat_hook(settings: dict[str, object]) -> dict[str, object]:
    """Return the first inner hook dict under ``hooks.PostToolUse[0].hooks[0]``.

    Args:
        settings: The full settings dict.

    Returns:
        The inner hook mapping (``{"type": ..., "command": ...}``).
    """
    entry = _post_tool_use_entries(settings)[0]
    inner = entry["hooks"]
    assert isinstance(inner, list)
    hook = inner[0]
    assert isinstance(hook, dict)
    return hook


@pytest.mark.parametrize("profile", PROFILES)
def test_materialise_writes_valid_json(profile: str, tmp_path: Path) -> None:
    """``settings.json`` is written into ``<worktree>/.claude/`` and is valid JSON."""
    written = materialise_settings(profile, tmp_path)

    assert written == tmp_path / ".claude" / "settings.json"
    assert written.is_file()
    # Parsing must not raise — the file is well-formed JSON.
    settings = _read_settings(written)
    assert "permissions" in settings


@pytest.mark.parametrize("profile", PROFILES)
def test_default_mode_is_pinned(profile: str, tmp_path: Path) -> None:
    """``permissions.defaultMode`` is present and equals the profile's pinned value (#39057)."""
    settings = _read_settings(materialise_settings(profile, tmp_path))
    perms = _permissions(settings)

    assert "defaultMode" in perms
    assert perms["defaultMode"] == pinned_mode(profile)
    # A pinned mode is never a bypass value (it would skip the deny layer).
    assert "bypass" not in str(perms["defaultMode"]).lower()


@pytest.mark.parametrize("profile", PROFILES)
def test_banned_commands_not_permitted(profile: str, tmp_path: Path) -> None:
    """For ALL profiles, every banned command is absent from allow AND present in deny (§10)."""
    settings = _read_settings(materialise_settings(profile, tmp_path))
    perms = _permissions(settings)
    allow = perms["allow"]
    deny = perms["deny"]
    assert isinstance(allow, list)
    assert isinstance(deny, list)

    allow_blob = " ".join(str(entry) for entry in allow)
    deny_blob = " ".join(str(entry) for entry in deny)
    for fragment in _BANNED_FRAGMENTS:
        # MERGE IS HUMAN ONLY: the banned surface must never be in allow, and must be in deny.
        assert fragment not in allow_blob, f"{fragment!r} must not be allowed in {profile!r}"
        assert fragment in deny_blob, f"{fragment!r} must be denied in {profile!r}"


@pytest.mark.parametrize("profile", PROFILES)
def test_no_explicit_merge_entry_in_allow(profile: str, tmp_path: Path) -> None:
    """Neither profile lists a merge command in allow — KanbanMate v1 has no merge profile."""
    settings = _read_settings(materialise_settings(profile, tmp_path))
    allow = _permissions(settings)["allow"]
    assert isinstance(allow, list)
    assert not any("merge" in str(entry).lower() for entry in allow)


@pytest.mark.parametrize("profile", PROFILES)
def test_bypass_permissions_false(profile: str, tmp_path: Path) -> None:
    """``bypassPermissions`` is explicitly false (it would skip the deny layer, §10)."""
    settings = _read_settings(materialise_settings(profile, tmp_path))
    assert settings["bypassPermissions"] is False


def test_dev_allow_list_is_concrete() -> None:
    """The ``dev`` allow-list is the broad build/test profile (full git + gh + make + Bash).

    Ported VERBATIM from the PoC ``test_dev_allow_list_is_concrete`` — the exact ordered list.
    """
    assert allow_list("dev") == [
        "Read",
        "Edit",
        "Bash(git *)",
        "Bash(gh *)",
        "Bash(make *)",
        "Bash(kanban-comment*)",
        "Bash(kanban-move*)",
        "Bash(kanban-progress*)",
        "Bash(kanban-update-body*)",
        "Bash",
    ]


def test_docs_allow_list_is_minimal_no_push_no_merge() -> None:
    """The ``docs`` allow-list is the minimal floor: git read/commit only, NO push / NO PR / NO merge.

    Ported VERBATIM from the PoC ``test_docs_allow_list_is_minimal_no_push_no_merge``.
    """
    assert allow_list("docs") == [
        "Read",
        "Edit",
        "Bash(git add*)",
        "Bash(git commit*)",
        "Bash(git status*)",
        "Bash(git log*)",
        "Bash(git diff*)",
        "Bash(gh issue*)",
        "Bash(kanban-comment*)",
        "Bash(kanban-move*)",
        "Bash(kanban-progress*)",
        "Bash(kanban-update-body*)",
    ]
    # docs lists NO broad git, NO push, NO PR ops, NO merge.
    assert "Bash(git *)" not in allow_list("docs")
    assert not any("push" in a for a in allow_list("docs"))
    assert not any("gh pr" in a for a in allow_list("docs"))
    assert not any("merge" in a.lower() for a in allow_list("docs"))


def test_prepare_allow_list_has_full_git_no_gh() -> None:
    """The ``prepare`` (create-branch) profile has full git (incl. push) but NO ``gh`` (no PR ops)."""
    prepare = allow_list("prepare")
    assert prepare == [
        "Read",
        "Edit",
        "Bash(git *)",
        "Bash(kanban-comment*)",
        "Bash(kanban-move*)",
        "Bash(kanban-progress*)",
        "Bash(kanban-update-body*)",
    ]
    # full git for the branch push, but no gh PR surface in this stage.
    assert "Bash(git *)" in prepare
    assert not any(a.startswith("Bash(gh") for a in prepare)


def test_check_allow_list_is_read_only_ish() -> None:
    """The ``check`` (script-gate) profile is read-only-ish: Read + git read + gh read, no Edit."""
    check = allow_list("check")
    assert check == [
        "Read",
        "Bash(gh *)",
        "Bash(git *)",
    ]
    assert "Edit" not in check


def test_docs_is_more_restrictive_than_dev() -> None:
    """The ``docs`` floor grants no push / no PR ops; ``dev`` adds full git + gh + broad Bash."""
    docs = allow_list("docs")
    dev = allow_list("dev")

    # docs carries only scoped git read/commit globs — never the broad ``Bash(git *)``.
    assert "Bash(git *)" not in docs
    assert "Bash(git commit*)" in docs
    # dev opens up full git + gh + broad Bash for build/test.
    assert "Bash(git *)" in dev
    assert "Bash(gh *)" in dev
    assert "Bash" in dev


def test_no_profile_allows_merge() -> None:
    """No profile lists a merge command in allow — KanbanMate has no merge profile (§10).

    Ported from the PoC ``test_profiles_allow_deny_and_merge_isolation`` (merge-isolation half),
    minus the dropped ``merge`` profile: here NO profile may merge.
    """
    for profile in ("docs", "prepare", "dev", "check"):
        assert not any("pr merge" in a for a in allow_list(profile)), (
            f"profile {profile!r} must not allow 'pr merge'"
        )
        assert not any("merge" in a.lower() for a in allow_list(profile)), (
            f"profile {profile!r} must not allow any merge command"
        )


def test_every_profile_denies_merge() -> None:
    """The universal deny-list bans every merge path for ALL four profiles (merge = human-only).

    Ported from the PoC ``test_every_profile_denies_merge_force_and_rewrite`` — but with NO
    ``merge``-profile exception (that profile is gone); every profile keeps the full deny-list.
    """
    universal = deny_list()
    for path in (
        "Bash(gh pr merge*)",
        "Bash(*pr-merge*)",
        "Bash(gh api*merge*)",
        "Bash(*mergePullRequest*)",
    ):
        assert path in universal, f"merge path {path!r} must be denied"
    # Every profile's materialised deny-list is the full universal one (no profile strips merge).
    for profile in PROFILES:
        settings = build_settings(profile)
        deny = _permissions(settings)["deny"]
        assert deny == universal, f"profile {profile!r}: expected the full universal deny-list"


def test_every_agent_profile_allows_kanban_progress() -> None:
    """Every AGENT (launching) profile can record milestones via kanban-progress (DESIGN §8.3).

    Ported from the PoC ``test_every_agent_profile_allows_kanban_progress`` — but ``check`` is a
    script-gate profile (no agent, no kanban helpers), so the assertion covers the three
    agent profiles that ship the helper.
    """
    for profile in ("docs", "prepare", "dev"):
        allow = allow_list(profile)
        assert "Bash(kanban-progress*)" in allow, profile
        # it sits alongside the existing kanban-comment / kanban-move allows.
        assert "Bash(kanban-comment*)" in allow and "Bash(kanban-move*)" in allow, profile


def test_every_agent_profile_allows_kanban_update_body() -> None:
    """Every AGENT (launching) profile allows the sanctioned body-write helper (§29.1).

    The hardened prompts route every body write-back through ``kanban-update-body``; if a profile
    did not allow it, the agent would be steered back to the (now-denied) raw ``gh issue edit``.
    """
    for profile in ("docs", "prepare", "dev"):
        assert "Bash(kanban-update-body*)" in allow_list(profile), profile


def test_gh_issue_edit_is_denied_universally() -> None:
    """``gh issue edit`` is denied for ALL profiles (§29.1): body writes go through the helper.

    ``gh issue view``/``list`` stay allowed (the broad ``Bash(gh issue*)`` allow on docs covers
    them); deny wins over allow, so the single ``Bash(gh issue edit*)`` deny is surgical.
    """
    universal = deny_list()
    assert "Bash(gh issue edit*)" in universal
    for profile in PROFILES:
        deny = _permissions(build_settings(profile))["deny"]
        assert "Bash(gh issue edit*)" in deny, profile  # type: ignore[operator]


def test_write_issue_pin_writes_integer(tmp_path: Path) -> None:
    """``write_issue_pin`` writes the integer issue into ``<worktree>/.claude/kanban-issue``."""
    path = write_issue_pin(tmp_path, 42)
    assert path == tmp_path / ".claude" / "kanban-issue"
    assert path.read_text(encoding="utf-8").strip() == "42"


def test_write_issue_pin_is_idempotent(tmp_path: Path) -> None:
    """Re-pinning the same issue is byte-identical (a relaunch re-writes the same number)."""
    first = write_issue_pin(tmp_path, 7).read_text(encoding="utf-8")
    second = write_issue_pin(tmp_path, 7).read_text(encoding="utf-8")
    assert first == second == "7\n"


def test_unknown_profile_degrades_to_docs() -> None:
    """An unknown profile name falls back to ``docs`` — the strictest list — not failing open.

    A deliberate improvement over the PoC (which fell back to ``dev``): degrade to the minimal
    floor on an unknown name (fail-closed), consistent with the genesis security stance.
    """
    assert allow_list("nonexistent") == allow_list("docs")


def test_bypass_profile_name_is_rejected() -> None:
    """A profile name containing 'bypass' is refused outright (banned, §10)."""
    with pytest.raises(ValueError, match="bypass"):
        build_settings("bypassPermissions")


# ---------------------------------------------------------------------------
# Sub-phase 9.1 — explicit "auto" pinned-mode assertions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("profile", "expected"),
    [("docs", "auto"), ("prepare", "auto"), ("dev", "auto"), ("check", "auto")],
)
def test_pinned_mode_is_auto_for_all_profiles(profile: str, expected: str) -> None:
    """Every defined profile pins ``defaultMode`` to ``"auto"`` (headless-safe, §9.1)."""
    assert pinned_mode(profile) == expected


def test_unknown_profile_fallback_is_auto() -> None:
    """Unknown profiles fall back to ``"auto"`` — the strictest pinned value."""
    assert pinned_mode("nonexistent") == "auto"


def test_fallback_mode_is_literal_auto() -> None:
    """The fallback constant itself is ``"auto"`` — not derived dynamically."""
    from kanbanmate.adapters import perms as _mod  # noqa: PLC0415 — test-only import

    assert _mod._FALLBACK_MODE == "auto"


@pytest.mark.parametrize("profile", PROFILES)
def test_build_settings_writes_auto_default_mode(profile: str) -> None:
    """``build_settings`` writes ``permissions.defaultMode == "auto"`` for every profile."""
    settings = build_settings(profile)
    perms = _permissions(settings)
    assert perms["defaultMode"] == "auto"


@pytest.mark.parametrize("profile", PROFILES)
def test_build_settings_writes_auto_with_issue(profile: str) -> None:
    """``build_settings`` with issue= still writes ``defaultMode == "auto"``."""
    settings = build_settings(profile, issue=7)
    perms = _permissions(settings)
    assert perms["defaultMode"] == "auto"


def test_build_settings_per_transition_mode_overrides_pinned_default() -> None:
    """A per-transition ``permission_mode`` overrides the profile's pinned default (minor (a)).

    The CLI launch flag emits the transition mode; the worktree's ``defaultMode`` must agree
    rather than the profile's hardwired pinned value.
    """
    settings = build_settings("dev", permission_mode="plan")
    assert _permissions(settings)["defaultMode"] == "plan"


def test_build_settings_empty_mode_falls_back_to_pinned() -> None:
    """An empty/None ``permission_mode`` falls back to the profile's pinned default (minor (a))."""
    assert _permissions(build_settings("dev", permission_mode=None))["defaultMode"] == "auto"
    assert _permissions(build_settings("dev", permission_mode=""))["defaultMode"] == "auto"


def test_build_settings_rejects_bypass_permission_mode() -> None:
    """A bypass ``permission_mode`` is rejected (it would skip the deny layer, §10 / minor (a))."""
    with pytest.raises(ValueError):
        build_settings("dev", permission_mode="bypassPermissions")


def test_no_profile_or_fallback_ever_yields_accept_edits() -> None:
    """Regression: NO profile, NO fallback, EVER yields ``"acceptEdits"`` (the banned mode).

    The PoC's unattended-hang reason: ``acceptEdits`` only auto-accepts edits and can still
    hang an unattended agent on other prompts. ``auto`` is the headless-safe default (§9.1).
    """
    # Every defined profile.
    for profile in PROFILES:
        assert pinned_mode(profile) != "acceptEdits", f"{profile!r} must not yield acceptEdits"
    # Unknown profile (fallback path).
    assert pinned_mode("unknown") != "acceptEdits", "fallback must not yield acceptEdits"
    # Bogus profile — still never acceptEdits.
    assert pinned_mode("bogus") != "acceptEdits", "bogus profile must not yield acceptEdits"
    # The _FALLBACK_MODE constant itself.
    from kanbanmate.adapters import perms as _mod  # noqa: PLC0415 — test-only import

    assert _mod._FALLBACK_MODE != "acceptEdits"


def test_deny_list_is_shared_across_profiles() -> None:
    """The deny-list is universal — no profile strips a ban (KanbanMate v1 has no merge profile)."""
    universal = deny_list()
    assert "Bash(gh pr merge*)" in universal
    # build_settings embeds the same universal deny-list for all profiles.
    for profile in PROFILES:
        perms = _permissions(build_settings(profile))
        assert perms["deny"] == universal


def test_materialise_is_idempotent(tmp_path: Path) -> None:
    """Re-materialising the same profile yields byte-identical output (overwrite is fine)."""
    first = materialise_settings("docs", tmp_path)
    content_a = first.read_text(encoding="utf-8")
    second = materialise_settings("docs", tmp_path)
    content_b = second.read_text(encoding="utf-8")

    assert first == second
    assert content_a == content_b


# ---------------------------------------------------------------------------
# Sub-phase 9.2 — materialise_settings round-trip: verify "auto" on disk
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("profile", PROFILES)
def test_materialise_writes_literal_auto(profile: str, tmp_path: Path) -> None:
    """The materialised file on disk carries ``defaultMode == "auto"`` (literal, not via
    the ``pinned_mode`` indirection — DESIGN §10 H4 direct-on-disk invariant)."""
    settings = _read_settings(materialise_settings(profile, tmp_path))
    assert _permissions(settings)["defaultMode"] == "auto"


@pytest.mark.parametrize("profile", PROFILES)
def test_materialise_deny_list_present_and_non_empty(profile: str, tmp_path: Path) -> None:
    """The deny-list in the materialised file is present and non-empty."""
    settings = _read_settings(materialise_settings(profile, tmp_path))
    deny = _permissions(settings)["deny"]
    assert isinstance(deny, list)
    assert len(deny) > 0, f"deny list is empty for {profile!r}"


@pytest.mark.parametrize("profile", PROFILES)
def test_materialise_with_issue_heartbeat_ends_with_kanban_heartbeat(
    profile: str, tmp_path: Path
) -> None:
    """The heartbeat command in the materialised file ends with
    ``kanban-heartbeat <issue>`` (unaffected by the mode flip, §9.2)."""
    written = materialise_settings(profile, tmp_path, issue=7)
    settings = _read_settings(written)
    cmd = _first_heartbeat_hook(settings)["command"]
    assert isinstance(cmd, str)
    assert cmd.endswith("kanban-heartbeat 7"), (
        f"heartbeat command must end with 'kanban-heartbeat 7', got {cmd!r}"
    )


@pytest.mark.parametrize("profile", PROFILES)
def test_materialise_without_issue_no_hooks(profile: str, tmp_path: Path) -> None:
    """Without ``issue=``, the materialised file has no ``hooks`` key."""
    settings = _read_settings(materialise_settings(profile, tmp_path))
    assert "hooks" not in settings


# ---------------------------------------------------------------------------
# H4 heartbeat hook (PostToolUse) — DESIGN §8.3
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("issue", [7, 42, 1234])
def test_build_settings_with_issue_injects_post_tool_use_hook(issue: int) -> None:
    """When ``issue`` is provided, ``build_settings`` includes a ``hooks.PostToolUse`` block."""
    settings = build_settings("dev", issue=issue)

    hooks = settings.get("hooks")
    assert isinstance(hooks, dict), "hooks block must be present when issue is given"
    assert "PostToolUse" in hooks
    post_tool_use = hooks["PostToolUse"]
    assert isinstance(post_tool_use, list)
    assert len(post_tool_use) == 1


def test_heartbeat_hook_matcher_is_wildcard() -> None:
    """The PostToolUse entry matches ``"*"`` — fires after EVERY tool the agent uses."""
    settings = build_settings("docs", issue=7)
    entry = _post_tool_use_entries(settings)[0]
    assert entry["matcher"] == "*"


def test_heartbeat_hook_command_is_string_not_array() -> None:
    """The hook ``command`` is a STRING (command-string form), NOT an exec-form array.

    Per DESIGN §8.3 and the Claude Code hook schema: command-hooks have ``"type": "command"``
    with the full shell line in ``command`` — there is no ``args`` field. The issue is baked
    into the command string by the dispatcher.
    """
    settings = build_settings("dev", issue=7)
    hook = _first_heartbeat_hook(settings)

    assert hook["type"] == "command"
    cmd = hook["command"]
    assert isinstance(cmd, str), f"command must be a STRING, got {type(cmd).__name__}"
    assert "kanban-heartbeat" in cmd
    assert "7" in cmd


@pytest.mark.parametrize("issue", [7, 42, 99])
def test_heartbeat_hook_command_contains_issue_number(issue: int) -> None:
    """The baked command string includes the exact issue number passed at launch time."""
    settings = build_settings("docs", issue=issue)
    cmd = _first_heartbeat_hook(settings)["command"]
    assert isinstance(cmd, str)
    assert str(issue) in cmd


def test_build_settings_without_issue_has_no_hooks_block() -> None:
    """When ``issue`` is None (the default), no ``hooks`` key is emitted at all."""
    settings = build_settings("docs")  # issue=None default
    assert "hooks" not in settings


def test_materialise_settings_with_issue_writes_hook(tmp_path: Path) -> None:
    """The heartbeat hook is materialised into the worktree ``settings.json`` file."""
    written = materialise_settings("dev", tmp_path, issue=7)
    settings = _read_settings(written)

    hooks = settings["hooks"]
    assert isinstance(hooks, dict)
    assert "PostToolUse" in hooks
    cmd = _first_heartbeat_hook(settings)["command"]
    assert isinstance(cmd, str)
    assert "kanban-heartbeat" in cmd
    assert "7" in cmd


@pytest.mark.parametrize("profile", PROFILES)
def test_heartbeat_hook_preserves_3_2_invariants(profile: str) -> None:
    """When the heartbeat hook is added, the 3.2 security invariants remain intact:
    defaultMode pinned, bypassPermissions false, and the universal ban set present."""
    settings = build_settings(profile, issue=7)
    perms = _permissions(settings)

    # 3.2 invariant: defaultMode pinned to profile value (bug #39057 mitigation).
    assert "defaultMode" in perms
    assert perms["defaultMode"] == pinned_mode(profile)
    assert "bypass" not in str(perms["defaultMode"]).lower()

    # 3.2 invariant: bypassPermissions explicitly false (it would skip the deny layer).
    assert settings["bypassPermissions"] is False

    # 3.2 invariant: universal ban set present — merge/force-push/history-rewrite denied.
    deny = perms["deny"]
    assert isinstance(deny, list)
    deny_blob = " ".join(str(entry) for entry in deny)
    for fragment in _BANNED_FRAGMENTS:
        assert fragment in deny_blob, f"{fragment!r} must be denied in {profile!r}"

    # 3.2 invariant: no merge entry in allow for any profile.
    allow = perms["allow"]
    assert isinstance(allow, list)
    assert not any("merge" in str(entry).lower() for entry in allow)


# ---------------------------------------------------------------------------
# Sub-phase 9.3 — deny still wins + no-hang invariant + bypass still banned
# ---------------------------------------------------------------------------


# ── 9.3.1: Deny-holds-under-auto ───────────────────────────────────────────


@pytest.mark.parametrize("profile", PROFILES)
def test_deny_holds_under_auto_identical_to_deny_list(profile: str) -> None:
    """For every profile under ``auto``, the deny-list is identical to ``deny_list()``.

    The mode flip stripped NOTHING from the deny-list — deny wins over allow regardless of
    ``defaultMode``. This locks in the invariant (§9.3).
    """
    deny_in_settings = _permissions(build_settings(profile))["deny"]
    assert deny_in_settings == deny_list(), (
        f"deny list for {profile!r} must be identical to deny_list(); "
        f"the mode flip must strip nothing"
    )


def test_deny_holds_all_merge_paths() -> None:
    """Every merge path is present in the deny-list — MERGE IS HUMAN ONLY (DESIGN §10).

    Checks every known merge path: ``gh pr merge``, the github-curl helper, the REST API,
    and the GraphQL mutation.
    """
    deny = deny_list()
    merge_paths = (
        "Bash(gh pr merge*)",  # gh CLI merge
        "Bash(*pr-merge*)",  # github-curl gh-api.sh pr-merge path
        "Bash(gh api*merge*)",  # gh api -X PUT .../pulls/N/merge
        "Bash(*mergePullRequest*)",  # gh api graphql mergePullRequest mutation
    )
    for path in merge_paths:
        assert path in deny, f"merge path {path!r} must be in deny_list()"


def test_deny_holds_all_force_push_forms() -> None:
    """Every force-push form is in the deny-list.

    Covers long flags (``--force``, ``--force-with-lease``), short flag (``-f``),
    refspec (``+``), and mirror (``--mirror``) — for both ``git push`` and
    ``git -C <dir> push``.
    """
    deny = deny_list()
    force_forms = (
        "Bash(git push*--force*)",
        "Bash(git -C*push*--force*)",
        "Bash(git push* -f*)",
        "Bash(git -C*push* -f*)",
        "Bash(git push* +*)",
        "Bash(git -C*push* +*)",
        "Bash(git push*--mirror*)",
        "Bash(git -C*push*--mirror*)",
    )
    for form in force_forms:
        assert form in deny, f"force-push form {form!r} must be in deny_list()"


def test_deny_holds_all_branch_ref_deletion() -> None:
    """Every branch/ref deletion path is in the deny-list.

    Covers ``git push --delete`` / ``-d`` / colon-refspec, ``git branch -D`` / ``--delete``,
    and ``git update-ref -d`` / ``--delete`` (including the ``-C`` directory form).
    """
    deny = deny_list()
    deletion_paths = (
        "Bash(git push*--delete*)",
        "Bash(git -C*push*--delete*)",
        "Bash(git push* -d*)",
        "Bash(git -C*push* -d*)",
        "Bash(git push* :*)",
        "Bash(git -C*push* :*)",
        "Bash(git branch -D*)",
        "Bash(git branch --delete*)",
        "Bash(git update-ref* -d*)",
        "Bash(git update-ref*--delete*)",
        "Bash(git -C*update-ref* -d*)",
        "Bash(git -C*update-ref*--delete*)",
    )
    for path in deletion_paths:
        assert path in deny, f"deletion path {path!r} must be in deny_list()"


def test_deny_holds_all_history_rewrite() -> None:
    """Every history-rewrite and history-destruction path is in the deny-list.

    Covers rebase, hard reset, commit amend, filter-branch, filter-repo, reflog expiry,
    and gc --prune.
    """
    deny = deny_list()
    rewrite_paths = (
        "Bash(git rebase*)",
        "Bash(git reset --hard*)",
        "Bash(git commit*--amend*)",
        "Bash(git filter-branch*)",
        "Bash(git filter-repo*)",
        "Bash(git reflog expire*)",
        "Bash(git gc*--prune*)",
    )
    for path in rewrite_paths:
        assert path in deny, f"history-rewrite path {path!r} must be in deny_list()"


# ── 9.3.2: No-hang invariant ───────────────────────────────────────────────


@pytest.mark.parametrize("profile", PROFILES)
def test_no_hang_invariant_default_mode_is_auto(profile: str) -> None:
    """For every profile, ``defaultMode`` is ``"auto"`` — the one mode that is BOTH
    unattended-safe AND deny-enforcing.

    The mode must NOT be ``"acceptEdits"`` (which can hang an unattended agent on non-edit
    prompts — the PoC's unattended-hang reason) and must NOT be any ``bypass`` variant
    (which skips the deny layer entirely — banned, §10).

    The RUNTIME no-hang guarantee is validated end-to-end in the phase-11 e2e (a real
    headless ``claude`` launch against a card), not in this unit test.
    """
    perms = _permissions(build_settings(profile))
    default_mode = perms["defaultMode"]

    assert default_mode == "auto", (
        f"defaultMode for {profile!r} must be 'auto', got {default_mode!r}"
    )
    # The positive assert above narrows ``default_mode`` to ``Literal["auto"]`` for mypy, so the
    # negative regression guards below read it through ``str(...)`` to keep them runtime checks
    # (and to keep the named "acceptEdits" reference the phase-9 gate grep depends on) without
    # tripping mypy's ``comparison-overlap`` under ``python_version = 3.12``.
    assert str(default_mode) != "acceptEdits", (
        f"defaultMode for {profile!r} must NOT be 'acceptEdits' (the banned mode)"
    )
    assert "bypass" not in str(default_mode).lower(), (
        f"defaultMode for {profile!r} must not contain 'bypass', got {default_mode!r}"
    )


# ── 9.3.3: Bypass-still-banned regression ──────────────────────────────────


def test_bypass_profile_name_variant_is_rejected() -> None:
    """A profile name like ``"bypassXYZ"`` raises ``ValueError`` — the guard is
    substring-based, not an allow-list check.

    The bypass ban is unaffected by the mode flip — assert it still holds (§9.3).
    """
    with pytest.raises(ValueError, match="bypass"):
        build_settings("bypassXYZ")


def test_materialise_refuses_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``materialise_settings`` under a faked root uid 0 raises ``PermissionError``.

    The non-root invariant (DESIGN §10) guards the materialisation boundary: the daemon
    and agents run non-root so a stray bypass can never elevate. The guard is unaffected
    by the mode flip — assert it still holds.

    Uses ``monkeypatch`` to simulate ``os.geteuid() == 0`` without actually running as root.
    """
    # Simulate root by patching os.geteuid to return 0.
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    with pytest.raises(PermissionError, match="root"):
        materialise_settings("docs", tmp_path)


# ---------------------------------------------------------------------------
# Phase 14.4 — provision_worktree_skills + ensure_manual_merge_mode
# ---------------------------------------------------------------------------


def _build_fake_config_dir(root: Path) -> Path:
    """Build a fake config directory with skills/commands/agents subdirs and sentinel files.

    Args:
        root: The parent directory to create the config tree under.

    Returns:
        The ``root`` path (for chaining).
    """
    for name in ("skills", "commands", "agents"):
        d = root / name
        d.mkdir(parents=True)
        (d / f"{name}_sentinel.md").write_text(f"content of {name}\n")
    return root


# ── provision_worktree_skills ──────────────────────────────────────────────


def test_provision_copies_config_dirs(tmp_path: Path) -> None:
    """skills/commands/agents are COPIED (not symlinked) into the worktree .claude/."""
    config_dir = _build_fake_config_dir(tmp_path / "config")
    worktree = tmp_path / "wt"
    worktree.mkdir()
    provisioned = provision_worktree_skills(worktree, config_dir)
    claude = worktree / ".claude"
    for name in ("skills", "commands", "agents"):
        dest = claude / name
        assert dest.is_dir(), f"{name} must be provisioned as a directory"
        assert not dest.is_symlink(), f"{name} must be a real COPY, never a symlink"
        sentinel = dest / f"{name}_sentinel.md"
        assert sentinel.is_file()
        assert sentinel.read_text() == f"content of {name}\n"
    assert {p.name for p in provisioned} == {"skills", "commands", "agents"}


def test_provision_writes_do_not_propagate_to_config(tmp_path: Path) -> None:
    """SECURITY: a write inside the worktree copy must NOT reach the shared config dir."""
    config_dir = _build_fake_config_dir(tmp_path / "config")
    worktree = tmp_path / "wt"
    worktree.mkdir()
    provision_worktree_skills(worktree, config_dir)

    # An agent edits a skill body in ITS worktree copy...
    (worktree / ".claude" / "skills" / "skills_sentinel.md").write_text("HACKED\n")
    (worktree / ".claude" / "skills" / "evil.md").write_text("planted\n")

    # ...the shared config is untouched (a symlink would have propagated both writes).
    assert (config_dir / "skills" / "skills_sentinel.md").read_text() == "content of skills\n"
    assert not (config_dir / "skills" / "evil.md").exists()


def test_provision_refreshes_and_skips_missing(tmp_path: Path) -> None:
    """Second call re-copies present dirs and skips missing subdirs (no crash)."""
    config_dir = tmp_path / "config"
    # Build all three dirs for the first call
    for name in ("skills", "commands", "agents"):
        d = config_dir / name
        d.mkdir(parents=True)
        (d / f"{name}_v1.md").write_text("v1\n")
    worktree = tmp_path / "wt"
    worktree.mkdir()

    first = provision_worktree_skills(worktree, config_dir)
    assert len(first) == 3

    # Drop agents from config_dir, update skills content
    shutil.rmtree(config_dir / "agents")
    (config_dir / "skills" / "skills_v1.md").write_text("v2\n")
    (config_dir / "skills" / "skills_v2.md").write_text("new\n")

    second = provision_worktree_skills(worktree, config_dir)
    assert len(second) == 2  # agents skipped (src not a dir)
    assert {p.name for p in second} == {"skills", "commands"}

    # skills dest was REFRESHED — carries v2 content and the new file
    skills_dest = worktree / ".claude" / "skills"
    assert (skills_dest / "skills_v1.md").read_text() == "v2\n"
    assert (skills_dest / "skills_v2.md").read_text() == "new\n"


def test_provision_excludes_dev_cruft(tmp_path: Path) -> None:
    """Caches / .git / pyc are NOT copied into the worktree (keeps it small + no leak)."""
    config_dir = tmp_path / "config"
    skills_dir = config_dir / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "real.md").write_text("real\n")
    (skills_dir / "__pycache__").mkdir()
    (skills_dir / "__pycache__" / "cached.pyc").write_text("cache\n")
    (skills_dir / ".git").mkdir()
    (skills_dir / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

    worktree = tmp_path / "wt"
    worktree.mkdir()
    provision_worktree_skills(worktree, config_dir)

    skills_copy = worktree / ".claude" / "skills"
    assert (skills_copy / "real.md").exists()
    assert not (skills_copy / "__pycache__").exists()
    assert not (skills_copy / ".git").exists()


def test_provision_noop_without_config_dir(tmp_path: Path) -> None:
    """Empty/None config_dir disables provisioning entirely (returns [])."""
    worktree = tmp_path / "wt"
    worktree.mkdir()
    assert provision_worktree_skills(worktree, "") == []
    assert provision_worktree_skills(worktree, None) == []
    assert not (worktree / ".claude" / "skills").exists()


def test_provision_preserves_settings_json(tmp_path: Path) -> None:
    """settings.json (not a provisioned dir) is preserved across a refresh."""
    config_dir = _build_fake_config_dir(tmp_path / "config")
    worktree = tmp_path / "wt"
    worktree.mkdir()

    # Write a settings.json BEFORE provisioning
    claude_dir = worktree / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text('{"key": "original"}\n')

    # Run provision twice
    provision_worktree_skills(worktree, config_dir)
    provision_worktree_skills(worktree, config_dir)

    # settings.json still exists and is untouched
    settings_path = claude_dir / "settings.json"
    assert settings_path.exists()
    assert not settings_path.is_symlink()
    assert settings_path.read_text() == '{"key": "original"}\n'


# ── provision_worktree_bin (phase 38: pyenv-proof helper PATH) ───────────────


def _fake_engine_bin_dir(root: Path) -> Path:
    """Build a fake engine ``bin/`` holding every kanban-* helper script, return the dir.

    Args:
        root: The parent directory to create the ``bin/`` tree under.

    Returns:
        The created ``bin/`` directory holding one executable per helper name.
    """
    bin_dir = root / "engine-bin"
    bin_dir.mkdir(parents=True)
    for name in _KANBAN_HELPER_BINS:
        script = bin_dir / name
        script.write_text("#!/bin/sh\necho hi\n")
        script.chmod(0o755)
    return bin_dir


def test_provision_bin_symlinks_all_helpers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Every kanban-* helper is symlinked into <worktree>/.claude/kanban-bin/ → engine scripts."""
    engine_bin = _fake_engine_bin_dir(tmp_path)
    # Resolve every helper to the fake engine bin via shutil.which.
    monkeypatch.setattr(
        "kanbanmate.adapters.perms.shutil.which",
        lambda name: str(engine_bin / name),
    )
    worktree = tmp_path / "wt"
    worktree.mkdir()

    bin_dir = provision_worktree_bin(worktree)

    assert bin_dir == worktree / KANBAN_BIN_RELDIR
    assert bin_dir.is_dir()
    for name in _KANBAN_HELPER_BINS:
        link = bin_dir / name
        assert link.is_symlink(), f"{name} must be a symlink"
        # The link points at the RESOLVED engine script (the engine's own interpreter scripts).
        assert Path(link).resolve() == (engine_bin / name).resolve()


def test_provision_bin_skips_unresolved_helper_fail_soft(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A helper that does NOT resolve is skipped with a warning — never raises (fail-soft)."""
    engine_bin = _fake_engine_bin_dir(tmp_path)
    missing = "kanban-update-body"

    def _which(name: str) -> str | None:
        if name == missing:
            return None  # simulate the stale-install gap (the live e2e case)
        return str(engine_bin / name)

    monkeypatch.setattr("kanbanmate.adapters.perms.shutil.which", _which)
    # The sys.executable fallback must also miss for the unresolved one.
    monkeypatch.setattr("kanbanmate.adapters.perms.Path.is_file", lambda self: False)
    worktree = tmp_path / "wt"
    worktree.mkdir()

    with caplog.at_level("WARNING"):
        bin_dir = provision_worktree_bin(worktree)  # must NOT raise

    # The missing helper has no symlink; the rest are present.
    assert not (bin_dir / missing).exists()
    for name in _KANBAN_HELPER_BINS:
        if name != missing:
            assert (bin_dir / name).is_symlink()
    assert any(missing in rec.message for rec in caplog.records)


def test_provision_bin_idempotent_refreshes_symlinks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A second launch REFRESHES the symlinks (re-points a stale target) without raising."""
    engine_bin_v1 = _fake_engine_bin_dir(tmp_path)
    monkeypatch.setattr(
        "kanbanmate.adapters.perms.shutil.which",
        lambda name: str(engine_bin_v1 / name),
    )
    worktree = tmp_path / "wt"
    worktree.mkdir()
    provision_worktree_bin(worktree)

    # A new interpreter's scripts dir (the pyenv switch the fix protects against).
    engine_bin_v2 = tmp_path / "engine-bin-v2"
    engine_bin_v2.mkdir()
    for name in _KANBAN_HELPER_BINS:
        (engine_bin_v2 / name).write_text("#!/bin/sh\necho v2\n")
    monkeypatch.setattr(
        "kanbanmate.adapters.perms.shutil.which",
        lambda name: str(engine_bin_v2 / name),
    )

    bin_dir = provision_worktree_bin(worktree)  # idempotent re-run

    for name in _KANBAN_HELPER_BINS:
        link = bin_dir / name
        assert link.is_symlink()
        # The stale v1 target was replaced with the current v2 engine script.
        assert Path(link).resolve() == (engine_bin_v2 / name).resolve()


# ── ensure_manual_merge_mode ────────────────────────────────────────────────


def test_ensure_manual_merge_replaces_existing_line(tmp_path: Path) -> None:
    """Replaces an existing ``**PR merge**: auto`` line IN PLACE with ``manual``."""
    worktree = tmp_path / "wt"
    worktree.mkdir()
    impl = worktree / "IMPLEMENTATION.md"
    impl.write_text("# Implementation\n\n**PR**: https://x/pull/1\n**PR merge**: auto\n\nbody\n")

    assert ensure_manual_merge_mode(worktree) is True

    text = impl.read_text()
    assert "**PR merge**: manual" in text
    assert "**PR merge**: auto" not in text
    # Verify replace-in-place: the line count is preserved, body content intact
    lines = text.splitlines()
    merge_line = next(ln for ln in lines if ln.startswith("**PR merge**:"))
    assert merge_line == "**PR merge**: manual"
    assert "body" in text


def test_ensure_manual_merge_appends_when_field_absent(tmp_path: Path) -> None:
    """Appends ``**PR merge**: manual`` when no such line exists in the file."""
    worktree = tmp_path / "wt"
    worktree.mkdir()
    impl = worktree / "IMPLEMENTATION.md"
    impl.write_text("# Implementation\n\nno merge field\n")

    assert ensure_manual_merge_mode(worktree) is True

    text = impl.read_text()
    assert "**PR merge**: manual" in text
    assert "no merge field" in text


def test_ensure_manual_merge_noop_without_file(tmp_path: Path) -> None:
    """Returns False and does NOT create IMPLEMENTATION.md when it is absent."""
    worktree = tmp_path / "wt"
    worktree.mkdir()

    assert ensure_manual_merge_mode(worktree) is False
    assert not (worktree / "IMPLEMENTATION.md").exists()


# ---------------------------------------------------------------------------
# #25 PORT — heartbeat hook bakes the RESOLVED absolute shim path (not a bare PATH command).
# The agent's launch env may strip PATH, silently no-opping a bare-command hook and defeating
# the reaper's freshness signal. The hook now bakes the resolved absolute shim path (shlex-quoted),
# falling soft to the bare command + a logged warning when the shim cannot be located.
# ---------------------------------------------------------------------------


def test_heartbeat_hook_bakes_resolved_absolute_shim_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The materialised hook command is the RESOLVED absolute shim path (shlex-quoted) + issue,
    NOT a bare ``kanban-heartbeat`` (#25)."""
    shim = tmp_path / "kanban-heartbeat"
    shim.write_text("#!/bin/sh\nexit 0\n")
    monkeypatch.setattr(
        "kanbanmate.adapters.perms.shutil.which",
        lambda name: str(shim) if name == "kanban-heartbeat" else None,
    )

    settings = build_settings("dev", issue=7)
    cmd = _first_heartbeat_hook(settings)["command"]

    assert isinstance(cmd, str)
    # The baked command carries the resolved ABSOLUTE path (not just the bare basename leading it).
    assert cmd.startswith(str(shim.resolve())), (
        f"command must start with the resolved absolute shim path, got {cmd!r}"
    )
    assert os.path.isabs(cmd.split()[0]), "the shim token must be an absolute path"
    assert cmd.endswith("kanban-heartbeat 7")


def test_heartbeat_hook_shim_path_is_shlex_quoted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A resolved shim path containing a space is ``shlex.quote``'d so the shell parses it as one
    token (the issue arg stays separate)."""
    spaced_dir = tmp_path / "dir with space"
    spaced_dir.mkdir()
    shim = spaced_dir / "kanban-heartbeat"
    shim.write_text("#!/bin/sh\nexit 0\n")
    monkeypatch.setattr("kanbanmate.adapters.perms.shutil.which", lambda name: str(shim))

    settings = build_settings("docs", issue=42)
    cmd = _first_heartbeat_hook(settings)["command"]

    assert isinstance(cmd, str)
    # shlex.split must recover exactly two tokens: the (un-quoted) shim path and the issue.
    tokens = shlex.split(cmd)
    assert tokens == [str(shim.resolve()), "42"], (
        f"a spaced shim path must be shlex-quoted into one token, got {tokens!r}"
    )


def test_heartbeat_hook_falls_back_to_bare_command_when_unresolvable(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An unresolvable shim FAILS SOFT to the bare ``kanban-heartbeat <issue>`` command with a
    logged warning — never a crash (#25 fail-soft)."""
    # Neither PATH (shutil.which → None) nor the interpreter scripts dir resolves the shim.
    monkeypatch.setattr("kanbanmate.adapters.perms.shutil.which", lambda name: None)
    monkeypatch.setattr("kanbanmate.adapters.perms.Path.is_file", lambda self: False)

    with caplog.at_level("WARNING"):
        settings = build_settings("dev", issue=7)
    cmd = _first_heartbeat_hook(settings)["command"]

    assert cmd == "kanban-heartbeat 7", (
        f"unresolvable shim must fall back to the bare command, got {cmd!r}"
    )
    assert any("kanban-heartbeat shim not found" in r.message for r in caplog.records), (
        "the fail-soft path must log a warning naming the unresolvable shim"
    )


def test_resolve_heartbeat_bin_returns_none_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """:func:`_resolve_heartbeat_bin` returns ``None`` (not a crash) when the shim is nowhere."""
    monkeypatch.setattr("kanbanmate.adapters.perms.shutil.which", lambda name: None)
    monkeypatch.setattr("kanbanmate.adapters.perms.Path.is_file", lambda self: False)

    assert _resolve_heartbeat_bin() is None


def test_resolve_heartbeat_bin_resolves_via_which(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """:func:`_resolve_heartbeat_bin` returns the absolute on-PATH path when ``which`` finds it."""
    shim = tmp_path / "kanban-heartbeat"
    shim.write_text("#!/bin/sh\nexit 0\n")
    monkeypatch.setattr("kanbanmate.adapters.perms.shutil.which", lambda name: str(shim))

    assert _resolve_heartbeat_bin() == str(shim.resolve())
