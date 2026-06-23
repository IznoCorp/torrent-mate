"""Tests for :mod:`kanbanmate.core.ticket_fields`.

Ported from the PoC ``parse_ticket_fields`` semantics: ``**key**: value`` Markdown-bold
field markers parsed from the ticket body, with the ``design``→``design_path`` and
``plans``→``plan_paths`` key remapping and comma-normalise for plan paths.
"""

from __future__ import annotations

from kanbanmate.core.ticket_fields import parse_ticket_fields


def test_all_three_markers_parsed_correctly() -> None:
    """A body with all 3 markers returns the correct dict with key remapping."""
    body = (
        "**codename**: genesis\n"
        "**design**: docs/features/genesis/DESIGN.md\n"
        "**plans**: docs/plan-1.md, docs/plan-2.md\n"
    )
    result = parse_ticket_fields(body)
    assert result == {
        "codename": "genesis",
        "design_path": "docs/features/genesis/DESIGN.md",
        "plan_paths": "docs/plan-1.md, docs/plan-2.md",
        "track": "",
    }


def test_design_marker_remapped_to_design_path() -> None:
    """The body ``**design**`` key is remapped to the ``design_path`` result key."""
    result = parse_ticket_fields("**design**: path/to/design.md")
    assert result["design_path"] == "path/to/design.md"
    assert "design" not in result  # the raw body key is never a result key


def test_plans_marker_remapped_to_plan_paths() -> None:
    """The body ``**plans**`` key is remapped to the ``plan_paths`` result key."""
    result = parse_ticket_fields("**plans**: a.md, b.md")
    assert result["plan_paths"] == "a.md, b.md"
    assert "plans" not in result


def test_missing_markers_default_to_empty_string() -> None:
    """A body with no markers returns all four keys as empty strings."""
    result = parse_ticket_fields("Just a regular issue body with no markers.")
    assert result == {"codename": "", "design_path": "", "plan_paths": "", "track": ""}


def test_partial_markers_others_empty() -> None:
    """A body with only some markers fills the present ones and defaults the rest."""
    result = parse_ticket_fields("**codename**: genesis")
    assert result["codename"] == "genesis"
    assert result["design_path"] == ""
    assert result["plan_paths"] == ""


def test_plans_comma_normalised() -> None:
    """``**plans**: a.md, b.md`` strips each path and re-joins with ``\", \"``."""
    result = parse_ticket_fields("**plans**: a.md,  b.md , c.md")
    assert result["plan_paths"] == "a.md, b.md, c.md"


def test_plans_single_path_no_trailing_comma() -> None:
    """A single plan path has no trailing comma or spaces."""
    result = parse_ticket_fields("**plans**: only-one.md")
    assert result["plan_paths"] == "only-one.md"


def test_plans_empty_value_yields_empty_string() -> None:
    """``**plans**:`` with an empty or whitespace-only value yields ``\"\"``."""
    result = parse_ticket_fields("**plans**:   ")
    assert result["plan_paths"] == ""


def test_unknown_key_silently_ignored() -> None:
    """An unknown ``**foo**:`` marker is silently ignored (does not crash)."""
    result = parse_ticket_fields("**codename**: genesis\n**foo**: ignored\n")
    assert result["codename"] == "genesis"
    assert result["design_path"] == ""
    assert result["plan_paths"] == ""


def test_none_body_treated_as_empty() -> None:
    """``None`` is treated as the empty string — all keys default to ``\"\"``."""
    result = parse_ticket_fields(None)
    assert result == {"codename": "", "design_path": "", "plan_paths": "", "track": ""}


def test_empty_body_defaults_all_keys() -> None:
    """An empty string body defaults all keys to ``\"\"`` (no crash)."""
    result = parse_ticket_fields("")
    assert result == {"codename": "", "design_path": "", "plan_paths": "", "track": ""}


def test_markers_interleaved_with_free_text() -> None:
    """Markers interleaved with free-text paragraphs are still parsed correctly."""
    body = (
        "Here is a description of the feature.\n\n"
        "**codename**: genesis\n\n"
        "Some more text.\n\n"
        "**design**: docs/DESIGN.md\n\n"
        "And a final note.\n\n"
        "**plans**: docs/plan/phase-1.md, docs/plan/phase-2.md\n"
    )
    result = parse_ticket_fields(body)
    assert result["codename"] == "genesis"
    assert result["design_path"] == "docs/DESIGN.md"
    assert result["plan_paths"] == "docs/plan/phase-1.md, docs/plan/phase-2.md"


def test_return_type_is_dict_str_str() -> None:
    """The return type annotation ``dict[str, str]`` holds — every key and value is a string."""
    result = parse_ticket_fields("**codename**: genesis")
    for k, v in result.items():
        assert isinstance(k, str)
        assert isinstance(v, str)


def test_parses_the_track_field() -> None:
    """The body ``**track**`` marker is parsed as-is into the result dict."""
    body = "**codename**: skiff\n**track**: express\n"
    fields = parse_ticket_fields(body)
    assert fields["track"] == "express"


def test_track_defaults_to_empty_when_absent() -> None:
    """Missing ``**track**`` defaults to ``""`` (no crash)."""
    assert parse_ticket_fields("**codename**: x")["track"] == ""
