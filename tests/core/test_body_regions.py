"""Adversarial tests for core/body_regions — split/merge round-trips and region safety.

Style mirrors tests/core/test_body_edit.py: class-per-concern, adversarial cases.
"""

from __future__ import annotations

from kanbanmate.core.body_edit import STATUS_BEGIN, STATUS_END
from kanbanmate.core.body_regions import BodyRegions, merge_body_regions, split_body_regions


_STATUS_BLOCK = f"{STATUS_BEGIN}\n**KanbanMate status** — Design · running\n{STATUS_END}"
_MARKERS = "**roadmap**: A1\n**codename**: tiller\n**design**: docs/features/tiller/DESIGN.md"
_BRAINSTORM = "## Brainstorm\n\nNeeds interactive terminal."
_FREEFORM = "Operator description of the feature.\n\nWith paragraphs."


def _full_body() -> str:
    return f"{_STATUS_BLOCK}\n\n{_FREEFORM}\n\n{_MARKERS}\n\n{_BRAINSTORM}"


class TestSplitRoundTrip:
    """merge(split(body), freeform=split(body).freeform) == body (up to whitespace)."""

    def test_round_trip_full_body(self) -> None:
        body = _full_body()
        regions = split_body_regions(body)
        merged = merge_body_regions(regions, new_freeform=regions.freeform)
        # All key content must survive (exact whitespace may differ by reassembly).
        assert "**KanbanMate status**" in merged
        assert "**roadmap**: A1" in merged
        assert "**codename**: tiller" in merged
        assert "## Brainstorm" in merged
        assert _FREEFORM.strip() in merged

    def test_round_trip_empty_body(self) -> None:
        regions = split_body_regions("")
        merged = merge_body_regions(regions, new_freeform="")
        assert merged == ""

    def test_round_trip_markers_only(self) -> None:
        body = "**roadmap**: B2\n**codename**: test"
        regions = split_body_regions(body)
        merged = merge_body_regions(regions, new_freeform=regions.freeform)
        assert "**roadmap**: B2" in merged
        assert "**codename**: test" in merged


class TestDisjointness:
    """Editing freeform must not alter protected regions."""

    def test_marker_preserved_when_freeform_changed(self) -> None:
        body = f"{_FREEFORM}\n\n{_MARKERS}"
        regions = split_body_regions(body)
        merged = merge_body_regions(regions, new_freeform="Completely new description.")
        assert "**roadmap**: A1" in merged
        assert "**codename**: tiller" in merged
        assert "Completely new description." in merged
        assert _FREEFORM not in merged  # old freeform replaced

    def test_status_block_preserved_when_freeform_changed(self) -> None:
        body = f"{_STATUS_BLOCK}\n\n{_FREEFORM}"
        regions = split_body_regions(body)
        merged = merge_body_regions(regions, new_freeform="New prose.")
        assert STATUS_BEGIN in merged
        assert STATUS_END in merged
        assert "New prose." in merged

    def test_brainstorm_preserved_when_freeform_changed(self) -> None:
        body = f"{_FREEFORM}\n\n{_BRAINSTORM}"
        regions = split_body_regions(body)
        merged = merge_body_regions(regions, new_freeform="Replaced.")
        assert "## Brainstorm" in merged
        assert "Needs interactive terminal." in merged


class TestDefang:
    """STATUS_BEGIN/END literals in freeform are stripped before merge."""

    def test_defang_status_begin_in_freeform(self) -> None:
        evil_freeform = f"Legit prose {STATUS_BEGIN} injected"
        regions = BodyRegions(freeform=evil_freeform)
        merged = merge_body_regions(regions, new_freeform=evil_freeform)
        # The literal delimiter must not appear inside freeform prose.
        assert merged.count(STATUS_BEGIN) == 0

    def test_defang_status_end_in_freeform(self) -> None:
        evil_freeform = f"Legit prose {STATUS_END} injected"
        regions = BodyRegions(freeform=evil_freeform)
        merged = merge_body_regions(regions, new_freeform=evil_freeform)
        assert merged.count(STATUS_END) == 0

    def test_defang_injected_codename_marker_in_freeform(self) -> None:
        # An operator must not shadow the real **codename** by smuggling one into freeform.
        regions = BodyRegions(markers={"codename": "**codename**: tiller"})
        evil_freeform = "notes\n**codename**: hijacked"
        merged = merge_body_regions(regions, new_freeform=evil_freeform)
        # The injected marker line is dropped; only the real protected marker survives.
        assert "**codename**: hijacked" not in merged
        assert "**codename**: tiller" in merged
        assert merged.count("**codename**") == 1
        assert "notes" in merged

    def test_defang_injected_design_marker_in_freeform(self) -> None:
        regions = BodyRegions(markers={"design": "**design**: docs/real/DESIGN.md"})
        evil_freeform = "notes\n**design**: ../evil"
        merged = merge_body_regions(regions, new_freeform=evil_freeform)
        assert "**design**: ../evil" not in merged
        assert "**design**: docs/real/DESIGN.md" in merged
        assert merged.count("**design**") == 1

    def test_non_preserved_marker_kept_in_freeform(self) -> None:
        # Only PRESERVED_MARKERS keys are stripped; an arbitrary **key** stays as prose.
        regions = BodyRegions()
        merged = merge_body_regions(regions, new_freeform="see **note**: keep me")
        assert "**note**: keep me" in merged

    def test_defang_injected_brainstorm_heading_in_freeform(self) -> None:
        regions = BodyRegions(brainstorm="## Brainstorm\n\nReal brainstorm.")
        evil_freeform = "notes\n## Brainstorm\n\nfake brainstorm"
        merged = merge_body_regions(regions, new_freeform=evil_freeform)
        # The injected heading line is dropped; the real protected section survives.
        assert "Real brainstorm." in merged
        assert merged.count("## Brainstorm") == 1
        assert "notes" in merged


class TestMissingSections:
    """Absent sections produce no gaps or errors."""

    def test_no_status_block(self) -> None:
        body = f"{_FREEFORM}\n\n**roadmap**: X"
        regions = split_body_regions(body)
        assert regions.status_block is None
        merged = merge_body_regions(regions, new_freeform="Updated.")
        assert STATUS_BEGIN not in merged

    def test_no_brainstorm(self) -> None:
        body = f"{_FREEFORM}\n\n**roadmap**: X"
        regions = split_body_regions(body)
        assert regions.brainstorm is None

    def test_no_markers(self) -> None:
        body = _FREEFORM
        regions = split_body_regions(body)
        assert regions.markers == {}
        merged = merge_body_regions(regions, new_freeform="OK")
        assert "**" not in merged
