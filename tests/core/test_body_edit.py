"""Tests for the pure body-editing primitives (:mod:`kanbanmate.core.body_edit`, §29.1).

These pin the marker-preservation, section-append, and body↔title ``[CODE]`` coherence rules the
``kanban-update-body`` helper relies on — exercised directly (pure, no I/O).
"""

from __future__ import annotations

from kanbanmate.core.body_edit import (
    STATUS_BEGIN,
    STATUS_END,
    append_section,
    declares_dependency_on,
    roadmap_marker,
    set_field,
    set_status_header,
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


class TestSetStatusHeader:
    """``set_status_header`` (FIX 5) inserts/replaces a region-disjoint body-top status block."""

    def test_empty_body_gets_header_only(self) -> None:
        """An empty body becomes just the rendered status block (no leading blank lines)."""
        out = set_status_header(
            "",
            stage="Design",
            state="running",
            summary="agent dispatched (docs)",
            timestamp="2026-06-16 10:00",
        )
        assert out == (
            f"{STATUS_BEGIN}\n"
            "**KanbanMate status** — Design · running — agent dispatched (docs)\n"
            "_updated 2026-06-16 10:00_\n"
            f"{STATUS_END}"
        )

    def test_summary_omitted_when_empty(self) -> None:
        """An empty summary drops the ``— …`` clause entirely."""
        out = set_status_header(
            "", stage="Plan", state="done", summary="", timestamp="2026-06-16 10:00"
        )
        assert "**KanbanMate status** — Plan · done\n" in out
        assert " — \n" not in out  # no dangling em-dash clause

    def test_prepends_above_existing_content(self) -> None:
        """When absent, the block is PREPENDED at the TOP above all existing body content."""
        body = "Some description.\n\nmore text"
        out = set_status_header(
            body, stage="Design", state="running", summary="", timestamp="2026-06-16 10:00"
        )
        assert out.startswith(STATUS_BEGIN)
        assert out.endswith("Some description.\n\nmore text")
        assert STATUS_END in out

    def test_roundtrip_preserves_markers_and_brainstorm_section(self) -> None:
        """ADVERSARIAL: set header on a body with all 4 markers + a ## Brainstorm section.

        Every marker value and the WHOLE Brainstorm section must be byte-preserved, and the header
        present at the TOP — region-disjoint from the markers (the headline FIX-5 preservation rule).
        """
        body = (
            "Feature description line.\n\n"
            "**roadmap**: A1\n"
            "**codename**: helm\n"
            "**design**: docs/features/helm/DESIGN.md\n"
            "**plans**: docs/features/helm/plan/INDEX.md\n\n"
            "## Brainstorm\n\n"
            "Lots of brainstorm prose.\n- bullet one\n- bullet two\n"
        )
        out = set_status_header(
            body,
            stage="Plan",
            state="waiting",
            summary="waiting for your input",
            timestamp="2026-06-16 11:00",
        )
        # Header present at the TOP.
        assert out.startswith(STATUS_BEGIN)
        assert "**KanbanMate status** — Plan · waiting — waiting for your input" in out
        # Every marker value byte-preserved (parse_ticket_fields + roadmap_marker recover them).
        fields = parse_ticket_fields(out)
        assert fields["codename"] == "helm"
        assert fields["design_path"] == "docs/features/helm/DESIGN.md"
        assert fields["plan_paths"] == "docs/features/helm/plan/INDEX.md"
        assert roadmap_marker(out) == "A1"
        # The whole Brainstorm section is preserved verbatim.
        assert "## Brainstorm\n\nLots of brainstorm prose.\n- bullet one\n- bullet two" in out

    def test_second_call_replaces_not_duplicates(self) -> None:
        """A second call with a changed timestamp REPLACES the block — exactly one block remains."""
        body = "**roadmap**: A1\n\n## Brainstorm\n\nprose"
        once = set_status_header(
            body, stage="Design", state="running", summary="s", timestamp="2026-06-16 10:00"
        )
        twice = set_status_header(
            once, stage="Design", state="running", summary="s", timestamp="2026-06-16 12:00"
        )
        # Exactly one BEGIN and one END (no duplicate block).
        assert twice.count(STATUS_BEGIN) == 1
        assert twice.count(STATUS_END) == 1
        # The newer timestamp won (replaced in place).
        assert "_updated 2026-06-16 12:00_" in twice
        assert "_updated 2026-06-16 10:00_" not in twice
        # The marker + Brainstorm survived both writes.
        assert "**roadmap**: A1" in twice
        assert "## Brainstorm\n\nprose" in twice

    def test_identical_block_is_idempotent(self) -> None:
        """An identical block produces a byte-identical body (the app-layer diff-gate no-op)."""
        body = "**roadmap**: A1\n\nprose"
        once = set_status_header(
            body, stage="Design", state="running", summary="s", timestamp="2026-06-16 10:00"
        )
        twice = set_status_header(
            once, stage="Design", state="running", summary="s", timestamp="2026-06-16 10:00"
        )
        assert twice == once

    def test_malformed_double_begin_collapses_to_one_block(self) -> None:
        """A body carrying a malformed double block still yields ONE block after a write (count=1)."""
        malformed = (
            f"{STATUS_BEGIN}\nfirst\n{STATUS_END}\n\n"
            f"{STATUS_BEGIN}\nsecond\n{STATUS_END}\n\nbody text"
        )
        out = set_status_header(
            malformed, stage="Design", state="done", summary="", timestamp="2026-06-16 10:00"
        )
        # The first block is replaced; the second (malformed leftover) is left, so the regex on a
        # subsequent write collapses to a single canonical block.
        final = set_status_header(
            out, stage="Design", state="done", summary="", timestamp="2026-06-16 10:00"
        )
        # The body text is never lost.
        assert "body text" in final

    def test_summary_with_backslashes_is_literal(self) -> None:
        """A summary containing ``\\g`` / ``\\1`` is inserted literally (no regex backreference)."""
        out = set_status_header(
            "",
            stage="Design",
            state="running",
            summary=r"path\go and \1 ref",
            timestamp="2026-06-16 10:00",
        )
        assert r"path\go and \1 ref" in out

    def test_summary_with_literal_delimiter_stays_one_well_formed_block(self) -> None:
        """ADVERSARIAL (nit 5): a summary carrying the literal STATUS_END delimiter is de-fanged.

        Without stripping, the embedded ``STATUS_END`` would let a subsequent ``_STATUS_BLOCK`` match
        terminate early and split the block. The de-fang drops the delimiter literals from the field,
        so exactly ONE well-formed block survives a write AND a re-write — no orphaned tail.
        """
        body = "**roadmap**: A1\n\n## Brainstorm\n\nprose"
        once = set_status_header(
            body,
            stage="Design",
            state="running",
            summary=f"sneaky {STATUS_END} delimiter {STATUS_BEGIN} injected",
            timestamp="2026-06-16 10:00",
        )
        # Exactly one BEGIN/END pair — the injected delimiter literals were stripped from the field.
        assert once.count(STATUS_BEGIN) == 1
        assert once.count(STATUS_END) == 1
        # The surrounding prose/markers survive; the block is locatable + replaceable as one region.
        assert "**roadmap**: A1" in once
        assert "## Brainstorm\n\nprose" in once
        twice = set_status_header(
            once, stage="Design", state="done", summary="clean", timestamp="2026-06-16 12:00"
        )
        # A re-write still collapses to a single block (no split-block leftover from the first write).
        assert twice.count(STATUS_BEGIN) == 1
        assert twice.count(STATUS_END) == 1
        assert "**KanbanMate status** — Design · done — clean" in twice
        assert "**roadmap**: A1" in twice
