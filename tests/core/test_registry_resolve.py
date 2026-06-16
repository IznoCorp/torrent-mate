"""Tests for the pure registry resolvers (ingress-multiproject §2.2 / §9).

Covers ``resolve_by_project_id`` / ``resolve_by_repo`` / ``resolve_by_issue`` (with + without a
repo hint, the collision case) / ``enabled_entries`` / ``safe_project_id``. Uses the concrete
:class:`~kanbanmate.cli.init.ProjectEntry` (it satisfies the ``ProjectEntryLike`` Protocol).
"""

from __future__ import annotations

from kanbanmate.cli.init import ProjectEntry
from kanbanmate.core.registry_resolve import (
    enabled_entries,
    resolve_by_issue,
    resolve_by_project_id,
    resolve_by_repo,
    safe_project_id,
)


def _entry(pid: str, repo: str, *, enabled: bool = True) -> ProjectEntry:
    """Build a minimal :class:`ProjectEntry` for resolver tests."""
    return ProjectEntry(
        repo=repo,
        clone=f"/clones/{pid}",
        project_id=pid,
        status_field_node_id="F",
        enabled=enabled,
    )


def _registry(*entries: ProjectEntry) -> dict[str, ProjectEntry]:
    return {e.project_id: e for e in entries}


def test_resolve_by_project_id_exact_hit() -> None:
    reg = _registry(_entry("PVT_A", "o/r1"), _entry("PVT_B", "o/r2"))
    assert resolve_by_project_id(reg, "PVT_B") is reg["PVT_B"]


def test_resolve_by_project_id_miss_is_none() -> None:
    reg = _registry(_entry("PVT_A", "o/r1"))
    assert resolve_by_project_id(reg, "PVT_NOPE") is None


def test_resolve_by_project_id_value_scan_fallback() -> None:
    """A drifted key (entry.project_id != registry key) still resolves via the value scan."""
    entry = _entry("PVT_REAL", "o/r1")
    reg = {"DRIFTED_KEY": entry}
    assert resolve_by_project_id(reg, "PVT_REAL") is entry


def test_resolve_by_repo_case_insensitive_multi() -> None:
    """One repo can back several boards; the match is case-insensitive + sorted by project_id."""
    reg = _registry(_entry("PVT_B", "Owner/Repo"), _entry("PVT_A", "owner/repo"))
    matches = resolve_by_repo(reg, "OWNER/REPO")
    assert [e.project_id for e in matches] == ["PVT_A", "PVT_B"]


def test_resolve_by_repo_no_match_empty() -> None:
    reg = _registry(_entry("PVT_A", "o/r1"))
    assert resolve_by_repo(reg, "o/other") == []


def test_resolve_by_issue_n1_fast_path_ignores_hint() -> None:
    """N=1: the sole enabled entry is returned, hint ignored (back-compat)."""
    reg = _registry(_entry("PVT_A", "o/r1"))
    assert resolve_by_issue(reg, 5) is reg["PVT_A"]
    assert resolve_by_issue(reg, 5, repo_hint="anything") is reg["PVT_A"]


def test_resolve_by_issue_collision_needs_hint() -> None:
    """N>1: issue #5 exists on two boards → the repo hint disambiguates."""
    reg = _registry(_entry("PVT_A", "o/r1"), _entry("PVT_B", "o/r2"))
    # No hint → ambiguous → None.
    assert resolve_by_issue(reg, 5) is None
    # Hint resolves the right board.
    assert resolve_by_issue(reg, 5, repo_hint="o/r2") is reg["PVT_B"]


def test_resolve_by_issue_ambiguous_repo_hint_is_none() -> None:
    """A repo backing >1 board is still ambiguous via a repo hint (need a project_id)."""
    reg = _registry(_entry("PVT_A", "o/r1"), _entry("PVT_B", "o/r1"))
    assert resolve_by_issue(reg, 5, repo_hint="o/r1") is None


def test_resolve_by_issue_empty_registry_is_none() -> None:
    assert resolve_by_issue({}, 5) is None


def test_resolve_by_issue_skips_disabled_for_n1_collapse() -> None:
    """A disabled entry is not counted: one enabled + one disabled collapses to the N=1 fast path."""
    reg = _registry(_entry("PVT_A", "o/r1"), _entry("PVT_B", "o/r2", enabled=False))
    assert resolve_by_issue(reg, 5) is reg["PVT_A"]


def test_enabled_entries_filters_and_sorts() -> None:
    reg = _registry(
        _entry("PVT_C", "o/r3"),
        _entry("PVT_A", "o/r1", enabled=False),
        _entry("PVT_B", "o/r2"),
    )
    assert [e.project_id for e in enabled_entries(reg)] == ["PVT_B", "PVT_C"]


def test_safe_project_id_sanitises_base64ish_node_id() -> None:
    """A node id with '='/'/' is confined to a single filesystem-safe slug (no path escape)."""
    slug = safe_project_id("PVT_kwHOA/b+c=")
    assert "/" not in slug and "+" not in slug and "=" not in slug
    # The sanitised stem is preserved; a short id-hash is appended for collision resistance (#6).
    assert slug.startswith("PVT_kwHOA_b_c_-")


def test_safe_project_id_empty_falls_back_to_underscore() -> None:
    # The sanitised stem of an all-unsafe id is "_"/"___" (char-by-char), but a deterministic id-hash
    # is appended so distinct ids never share a sub-root (#6) — assert on the stem prefix.
    assert safe_project_id("").startswith("_-")
    assert safe_project_id("///").startswith("___-")


def test_safe_project_id_distinct_ids_differing_only_in_unsafe_chars_no_collision() -> None:
    """#6: two ids whose sanitised stems COLLIDE still get distinct sub-roots (the hash disambiguates).

    ``"a/b"`` and ``"a+b"`` both sanitise to the stem ``"a_b"``; without the id-hash suffix they
    would share ``<root>/projects/a_b`` and silently cross-contaminate state. The appended hash of
    the full id makes the two slugs distinct.
    """
    one = safe_project_id("a/b")
    two = safe_project_id("a+b")
    assert one != two
    # Both keep the same sanitised stem (only the hash suffix differs).
    assert one.startswith("a_b-") and two.startswith("a_b-")


def test_safe_project_id_is_deterministic() -> None:
    """The slug is PURE: the same id always yields the same slug (daemon-writes == helper-reads)."""
    assert safe_project_id("PVT_xyz=") == safe_project_id("PVT_xyz=")


def test_owner_derived_from_repo_when_org_blank() -> None:
    """ProjectEntry.owner derives the org from the repo slug when ``org`` is empty."""
    assert _entry("PVT_A", "acme/widgets").owner() == "acme"


def test_owner_explicit_wins() -> None:
    entry = ProjectEntry(
        repo="acme/widgets",
        clone="/c",
        project_id="PVT_A",
        status_field_node_id="F",
        org="explicit-org",
    )
    assert entry.owner() == "explicit-org"
