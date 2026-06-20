"""Tests for :mod:`kanbanmate.core.placeholders`.

Ported from the PoC ``tests/test_placeholders.py`` and extended with fail-loud
cases for whitespace tolerance, non-string coercion, and intermediate-node type
errors (phase 12.1).
"""

from __future__ import annotations

import pytest

from kanbanmate.core.placeholders import (
    KNOWN_PLACEHOLDERS,
    fill,
    unknown_placeholders,
)

# ---------------------------------------------------------------------------
# Shared test context (mirrors the PoC CTX)
# ---------------------------------------------------------------------------

CTX: dict[str, object] = {
    "ticket": {"title": "Add RP1", "number": 42, "body": "details"},
    "code": "RP1",
    "branch": "feat/rp1",
    "column": {"from": "Backlog", "to": "In Progress"},
}


# ---------------------------------------------------------------------------
# Ported PoC assertions (4 cases)
# ---------------------------------------------------------------------------


def test_fills_nested_and_flat() -> None:
    """A template with flat keys, dotted paths, and plain text substitutes
    every token, including whitespace inside the braces."""
    out = fill("{{code}} / {{ticket.title}} #{{ticket.number}} -> {{ column.to }}", CTX)
    assert out == "RP1 / Add RP1 #42 -> In Progress"


def test_unknown_placeholder_raises() -> None:
    """A reference to a key absent from the context raises KeyError."""
    with pytest.raises(KeyError, match="nope"):
        fill("{{nope}}", CTX)


def test_unknown_nested_raises() -> None:
    """A dotted path whose leaf segment is absent raises KeyError for the
    whole path (not just the missing segment)."""
    with pytest.raises(KeyError, match="ticket\\.missing"):
        fill("{{ticket.missing}}", CTX)


def test_plain_text_unchanged() -> None:
    """A template with no placeholders is returned unchanged."""
    assert fill("no placeholders here", CTX) == "no placeholders here"


# ---------------------------------------------------------------------------
# Extended fail-loud cases (phase 12.1 additions)
# ---------------------------------------------------------------------------


def test_whitespace_padded_substitutes() -> None:
    """A ``{{ x }}`` token with whitespace inside the braces still substitutes."""
    assert fill("{{  code  }}", CTX) == "RP1"


def test_non_string_value_coerced() -> None:
    """A resolved value that is not a string is ``str()``-coerced."""
    ctx: dict[str, object] = {"num": 42, "flag": True}
    assert fill("{{num}}", ctx) == "42"
    assert fill("{{flag}}", ctx) == "True"


def test_intermediate_not_mapping_raises() -> None:
    """A dotted path where an intermediate segment is not a ``Mapping`` raises
    ``KeyError`` for the whole path."""
    ctx: dict[str, object] = {"a": "plain_string"}
    with pytest.raises(KeyError, match="a\\.b"):
        fill("{{a.b}}", ctx)


# ---------------------------------------------------------------------------
# bridge (helm PR 2): known-placeholder set + unknown finder
# ---------------------------------------------------------------------------


def test_known_placeholders_match_launch_context_keys() -> None:
    # Drift guard: the exposed set must equal the dispatch context keys.
    # Update BOTH this literal and KNOWN_PLACEHOLDERS if launch_context changes.
    expected = {
        "code",
        "title",
        "branch",
        "ticket_body",
        "script_output",
        "issue_body",
        "comments",
        "codename",
        "design_path",
        "plan_paths",
        "base_clone",
        "dev_repo_path",
    }
    assert set(KNOWN_PLACEHOLDERS) == expected
    assert all(isinstance(v, str) and v for v in KNOWN_PLACEHOLDERS.values())


def test_unknown_placeholders_flags_typos() -> None:
    tmpl = "Implement {{code}} ({{codename}}); base {{baze}} and {{also_bad}}."
    assert unknown_placeholders(tmpl) == ["baze", "also_bad"]


def test_unknown_placeholders_empty_when_all_known() -> None:
    assert unknown_placeholders("ticket {{code}} — {{title}}") == []


def test_unknown_placeholders_handles_dotted_paths() -> None:
    # Only the first segment is matched against the known set.
    assert unknown_placeholders("{{ticket.title}}") == ["ticket"]
