"""Tests for :mod:`kanbanmate.core.placeholders`.

Ported from the PoC ``tests/test_placeholders.py`` and extended with fail-loud
cases for whitespace tolerance, non-string coercion, and intermediate-node type
errors (phase 12.1).
"""

from __future__ import annotations

import pytest

from kanbanmate.core.placeholders import fill

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
