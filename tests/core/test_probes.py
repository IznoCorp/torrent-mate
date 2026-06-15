"""Tests for :mod:`kanbanmate.core.probes` — the pure branch-protection parser.

The parser is PURE (no I/O): it turns an already-decoded GitHub
``branches/{b}/protection`` body (or a raw JSON string, for back-compat) into a
boolean. These tests cover the three real body shapes — a protected branch (one
test per protection field, alone), the 404 "Branch not protected" message-only
body, and the empty/non-dict/invalid-JSON degenerate cases — plus the JSON-string
back-compat path ported from the PoC ``cli/probes.py:59-79``.
"""

from __future__ import annotations

import json

import pytest

from kanbanmate.core.probes import parse_branch_protection_on


@pytest.mark.parametrize(
    "field",
    ["required_status_checks", "enforce_admins", "required_pull_request_reviews"],
)
def test_protected_when_any_protection_field_present(field: str) -> None:
    """A body carrying ANY single protection field → protection is ON."""
    body = {field: {"enabled": True}}
    assert parse_branch_protection_on(body) is True


def test_protected_with_full_protection_body() -> None:
    """A realistic protected-branch body (all fields) → True."""
    body = {
        "url": "https://api.github.com/repos/o/r/branches/main/protection",
        "required_status_checks": {"strict": True, "contexts": ["ci"]},
        "enforce_admins": {"enabled": True},
        "required_pull_request_reviews": {"required_approving_review_count": 1},
    }
    assert parse_branch_protection_on(body) is True


def test_message_only_404_body_is_off() -> None:
    """The 404 "Branch not protected" message-only body → protection is OFF."""
    body = {"message": "Branch not protected", "documentation_url": "https://docs..."}
    assert parse_branch_protection_on(body) is False


def test_empty_dict_is_off() -> None:
    """An empty object carries no protection field → OFF."""
    assert parse_branch_protection_on({}) is False


def test_non_dict_is_off() -> None:
    """A non-mapping payload (list, int, None) → OFF, never raises."""
    assert parse_branch_protection_on([]) is False
    assert parse_branch_protection_on(42) is False
    assert parse_branch_protection_on(None) is False


def test_message_with_protection_field_is_on() -> None:
    """A body with both a ``message`` AND a protection field → ON (field wins)."""
    body = {"message": "something", "enforce_admins": {"enabled": True}}
    assert parse_branch_protection_on(body) is True


# ---------------------------------------------------------------------------
# JSON-string back-compat (the PoC ``gh api`` output shape)
# ---------------------------------------------------------------------------


def test_json_string_protected_is_on() -> None:
    """A raw JSON STRING carrying a protection field → ON (back-compat)."""
    raw = json.dumps({"required_status_checks": {"strict": True}})
    assert parse_branch_protection_on(raw) is True


def test_json_string_message_only_is_off() -> None:
    """A raw JSON STRING of the 404 message-only body → OFF (back-compat)."""
    raw = json.dumps({"message": "Branch not protected"})
    assert parse_branch_protection_on(raw) is False


def test_invalid_json_string_is_off() -> None:
    """An invalid JSON string → OFF (never raises)."""
    assert parse_branch_protection_on("not json at all {{{") is False
    assert parse_branch_protection_on("") is False
