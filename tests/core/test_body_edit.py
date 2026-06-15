"""Tests for the pure body-editing primitives (:mod:`kanbanmate.core.body_edit`, §29.1).

These pin the marker-preservation, section-append, and body↔title ``[CODE]`` coherence rules the
``kanban-update-body`` helper relies on — exercised directly (pure, no I/O).
"""

from __future__ import annotations

from kanbanmate.core.body_edit import (
    append_section,
    declares_dependency_on,
    roadmap_marker,
    set_field,
    title_code,
    validate_roadmap_matches_title,
)
from kanbanmate.core.ticket_fields import parse_ticket_fields


class TestSetField:
    """``set_field`` rewrites one marker in place or appends it, preserving the others."""

    def test_replaces_existing_marker_in_place(self) -> None:
        """An existing ``**key**: …`` line is rewritten in place; other markers survive."""
        body = "Desc\n\n**roadmap**: A1\n\n**design**: old/path.md"
        out = set_field(body, "design", "new/path.md")
        assert "**design**: new/path.md" in out
        assert "**roadmap**: A1" in out  # untouched
        assert "old/path.md" not in out

    def test_appends_marker_when_absent(self) -> None:
        """A missing marker is appended as its own paragraph (parser-visible)."""
        body = "Some description"
        out = set_field(body, "codename", "my-feature")
        assert out.endswith("**codename**: my-feature")
        assert parse_ticket_fields(out)["codename"] == "my-feature"

    def test_set_field_into_empty_body(self) -> None:
        """Setting a field on an empty body yields just the marker line."""
        assert set_field("", "roadmap", "A1") == "**roadmap**: A1"

    def test_only_first_occurrence_replaced(self) -> None:
        """Only the FIRST occurrence is rewritten (markers are single-valued)."""
        body = "**plans**: a.md\n**plans**: b.md"
        out = set_field(body, "plans", "c.md")
        # First line rewritten; the (malformed) duplicate is left as-is.
        assert out.splitlines()[0] == "**plans**: c.md"


class TestAppendSection:
    """``append_section`` appends under a heading WITHOUT touching any marker (the APPEND path)."""

    def test_appends_under_heading_preserving_markers(self) -> None:
        """The brainstorm append preserves the seeded description + the ``**roadmap**`` marker."""
        body = "Original feature description\n\n**roadmap**: A1"
        out = append_section(body, "## Brainstorm", "Requirements:\n- one\n- two")
        assert "Original feature description" in out
        assert "**roadmap**: A1" in out  # marker preserved
        assert "## Brainstorm" in out
        assert "Requirements:" in out
        # roadmap is still parseable after the append.
        assert parse_ticket_fields(out)["codename"] == ""
        assert "A1" == roadmap_marker(out)

    def test_append_into_empty_body(self) -> None:
        """Appending a section to an empty body yields heading + text only."""
        out = append_section("", "## Brainstorm", "hello")
        assert out == "## Brainstorm\n\nhello"


class TestTitleCode:
    """``title_code`` extracts the authoritative ``[CODE]`` bracket."""

    def test_extracts_bracket(self) -> None:
        assert title_code("[A1] My feature") == "A1"

    def test_none_without_bracket(self) -> None:
        assert title_code("No bracket here") is None


class TestValidateRoadmapMatchesTitle:
    """The post-write coherence gate: body ``**roadmap**`` must equal the title ``[CODE]``."""

    def test_match_returns_none(self) -> None:
        """Matching codes pass (no error)."""
        assert validate_roadmap_matches_title("**roadmap**: A1", "[A1] Feature") is None

    def test_mismatch_returns_error(self) -> None:
        """A divergent code returns a clear error message."""
        err = validate_roadmap_matches_title("**roadmap**: B2", "[A1] Feature")
        assert err is not None
        assert "A1" in err and "B2" in err

    def test_skips_when_marker_absent(self) -> None:
        """No ``**roadmap**`` marker → the check is skipped (a later write may add it)."""
        assert validate_roadmap_matches_title("just prose", "[A1] Feature") is None

    def test_skips_when_title_has_no_bracket(self) -> None:
        """No title ``[CODE]`` bracket → the check is skipped (cannot mismatch)."""
        assert validate_roadmap_matches_title("**roadmap**: A1", "no bracket") is None


class TestDeclaresDependencyOn:
    """The §29.3 direction filter: detect a DOWNSTREAM dependent's body (the #91 poisoning)."""

    def test_numeric_form_detected(self) -> None:
        """``Depends on #91`` declares a dependency on #91 (downstream → True)."""
        assert declares_dependency_on("O1 text.\n\nDepends on #91", issue=91, code=None) is True

    def test_numeric_form_no_false_prefix_match(self) -> None:
        """``Depends on #911`` must NOT match #91 (word-boundary guard)."""
        assert declares_dependency_on("Depends on #911", issue=91, code=None) is False

    def test_code_form_detected(self) -> None:
        """``Depends on A1`` declares a dependency on code A1 (downstream → True)."""
        assert declares_dependency_on("Depends on A1", issue=91, code="A1") is True

    def test_code_form_no_false_substring_match(self) -> None:
        """``Depends on A12`` must NOT match code A1 (word-boundary guard)."""
        assert declares_dependency_on("Depends on A12", issue=91, code="A1") is False

    def test_upstream_source_not_filtered(self) -> None:
        """A body that does NOT mention us is an upstream/unrelated source (keep → False)."""
        assert declares_dependency_on("Some upstream spec.", issue=91, code="A1") is False

    def test_multi_ref_depends_line(self) -> None:
        """A multi-ref ``Depends on #5, #91`` still matches #91."""
        assert declares_dependency_on("Depends on #5, #91", issue=91, code=None) is True

    def test_empty_body_is_false(self) -> None:
        """An empty linked body is never a dependent."""
        assert declares_dependency_on("", issue=91, code="A1") is False
