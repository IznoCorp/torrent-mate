"""Tests for the Health single-select field GraphQL surface + client (health-field).

Covers the new query builder, the two parsers, and the client's
``ensure_health_field`` / ``set_item_health`` against fake GraphQL transports.
"""

from __future__ import annotations

from typing import Any

import pytest

from kanbanmate.adapters.github import _parsers, _queries
from kanbanmate.adapters.github._parsers import GraphQLError
from kanbanmate.adapters.github.client import GithubClient
from kanbanmate.adapters.github.types import HealthField

PROJECT = "PVT_PROJECT"


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------


def test_create_field_single_select_builds_single_select_payload() -> None:
    """The builder emits a SINGLE_SELECT createProjectV2Field with the options payload."""
    options = [{"name": "ACTIVE", "color": "GREEN", "description": ""}]
    payload = _queries.create_project_field_single_select(PROJECT, "Health", options)
    assert "createProjectV2Field" in payload["query"]
    assert "SINGLE_SELECT" in payload["query"]
    assert payload["variables"] == {
        "projectId": PROJECT,
        "name": "Health",
        "options": options,
    }


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _fields_response(fields: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap field nodes in the status_option_map response shape."""
    return {"data": {"node": {"fields": {"nodes": fields}}}}


def test_parse_health_field_returns_field_when_present() -> None:
    """parse_health_field returns the 'Health' field id + {name: option_id}."""
    data = _fields_response(
        [
            {"name": "Status", "id": "STATUS_F", "options": [{"name": "Backlog", "id": "o1"}]},
            {
                "name": "Health",
                "id": "HEALTH_F",
                "options": [
                    {"name": "ACTIVE", "id": "a"},
                    {"name": "BLOCKED", "id": "b"},
                ],
            },
        ]
    )
    field = _parsers.parse_health_field(data)
    assert field == HealthField(field_id="HEALTH_F", options={"ACTIVE": "a", "BLOCKED": "b"})


def test_parse_health_field_returns_none_when_absent() -> None:
    """parse_health_field returns None when no 'Health' field is present."""
    data = _fields_response([{"name": "Status", "id": "S", "options": []}])
    assert _parsers.parse_health_field(data) is None


def test_parse_health_field_ignores_non_single_select_health() -> None:
    """A 'Health' field with NO options node (non-single-select) is treated as absent."""
    data = _fields_response([{"name": "Health", "id": "H_TEXT"}])  # no 'options' key
    assert _parsers.parse_health_field(data) is None


def test_parse_health_field_raises_on_errors() -> None:
    """parse_health_field raises GraphQLError on a non-empty errors array."""
    with pytest.raises(GraphQLError):
        _parsers.parse_health_field({"errors": [{"message": "boom"}]})


def test_parse_created_single_select_field_parses_ids() -> None:
    """parse_created_single_select_field reads the new field id + option ids."""
    data = {
        "data": {
            "createProjectV2Field": {
                "projectV2Field": {
                    "id": "NEW_F",
                    "name": "Health",
                    "options": [{"name": "ACTIVE", "id": "a"}, {"name": "WAITING", "id": "w"}],
                }
            }
        }
    }
    field = _parsers.parse_created_single_select_field(data)
    assert field == HealthField(field_id="NEW_F", options={"ACTIVE": "a", "WAITING": "w"})


def test_parse_created_single_select_field_raises_on_errors() -> None:
    """parse_created_single_select_field raises GraphQLError on errors."""
    with pytest.raises(GraphQLError):
        _parsers.parse_created_single_select_field({"errors": [{"message": "boom"}]})


# ---------------------------------------------------------------------------
# Client: ensure_health_field + set_item_health
# ---------------------------------------------------------------------------


def _all_options(field_id: str = "HEALTH_F") -> dict[str, Any]:
    """A fields response carrying a complete 5-option Health field."""
    return _fields_response(
        [
            {
                "name": "Health",
                "id": field_id,
                "options": [
                    {"name": "INACTIVE", "id": "i"},
                    {"name": "WAITING", "id": "w"},
                    {"name": "ACTIVE", "id": "a"},
                    {"name": "BLOCKED", "id": "b"},
                    {"name": "COMPLETE", "id": "c"},
                ],
            }
        ]
    )


class _Fake:
    """A GraphQL transport routing by operation, recording every payload."""

    def __init__(self, *, read: dict[str, Any], created: dict[str, Any] | None = None) -> None:
        """Store the canned read response + optional create response."""
        self.calls: list[dict[str, Any]] = []
        self._read = read
        self._created = created

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Route by query token; record the payload."""
        self.calls.append(payload)
        query = payload["query"]
        if "createProjectV2Field" in query:
            assert self._created is not None, "unexpected create call"
            return self._created
        if "updateProjectV2Field" in query:
            # Reconcile REPLACE → echo the merged options back.
            opts = payload["variables"]["options"]
            return {
                "data": {
                    "updateProjectV2Field": {
                        "projectV2Field": {
                            "options": [
                                {"name": o["name"], "id": o.get("id", f"new_{o['name']}")}
                                for o in opts
                            ]
                        }
                    }
                }
            }
        if "updateProjectV2ItemFieldValue" in query:
            return {"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "X"}}}}
        # Default: the status_option_map read.
        return self._read

    def count(self, marker: str) -> int:
        """Count recorded payloads whose query contains ``marker``."""
        return sum(1 for c in self.calls if marker in c["query"])


def _client(fake: _Fake) -> GithubClient:
    """Build a client wired to ``fake`` for GraphQL (REST untouched here)."""
    return GithubClient(token="tok", project_id=PROJECT, graphql_transport=fake)


def test_ensure_creates_field_when_absent() -> None:
    """Absent 'Health' → issue createProjectV2Field, return the parsed new ids."""
    created = {
        "data": {
            "createProjectV2Field": {
                "projectV2Field": {
                    "id": "NEW_F",
                    "options": [
                        {"name": n, "id": n.lower()}
                        for n in ("INACTIVE", "WAITING", "ACTIVE", "BLOCKED", "COMPLETE")
                    ],
                }
            }
        }
    }
    fake = _Fake(
        read=_fields_response([{"name": "Status", "id": "S", "options": []}]), created=created
    )
    client = _client(fake)
    field = client.ensure_health_field(PROJECT)
    assert field.field_id == "NEW_F"
    assert set(field.options) == {"INACTIVE", "WAITING", "ACTIVE", "BLOCKED", "COMPLETE"}
    assert fake.count("createProjectV2Field") == 1


def test_ensure_returns_existing_field_with_all_options_no_create() -> None:
    """Present 'Health' with all 5 options → NO create, return existing."""
    fake = _Fake(read=_all_options())
    client = _client(fake)
    field = client.ensure_health_field(PROJECT)
    assert field.field_id == "HEALTH_F"
    assert fake.count("createProjectV2Field") == 0


def test_ensure_reconciles_drifted_options_preserving_ids() -> None:
    """Present but drifted → REPLACE options, preserving existing ids."""
    drifted = _fields_response(
        [{"name": "Health", "id": "HEALTH_F", "options": [{"name": "ACTIVE", "id": "a"}]}]
    )
    fake = _Fake(read=drifted)
    client = _client(fake)
    field = client.ensure_health_field(PROJECT)
    assert field.field_id == "HEALTH_F"
    # The REPLACE was issued (not a create).
    assert fake.count("updateProjectV2Field") == 1
    assert fake.count("createProjectV2Field") == 0
    # The preserved option kept its id; new ones got fresh ids.
    assert field.options["ACTIVE"] == "a"
    assert "BLOCKED" in field.options


def test_ensure_is_cached_no_second_read() -> None:
    """A second ensure_health_field call hits the in-process cache (no second read)."""
    fake = _Fake(read=_all_options())
    client = _client(fake)
    client.ensure_health_field(PROJECT)
    client.ensure_health_field(PROJECT)
    # status_option_map read happened ONCE (the second call used the cache).
    assert fake.count("ProjectV2SingleSelectField") == 1


def test_set_item_health_issues_item_field_value_mutation() -> None:
    """set_item_health issues updateProjectV2ItemFieldValue with the value's option id."""
    fake = _Fake(read=_all_options())
    client = _client(fake)
    client.set_item_health("PVTI_1", "ACTIVE")
    move = next(c for c in fake.calls if "updateProjectV2ItemFieldValue" in c["query"])
    assert move["variables"]["fieldId"] == "HEALTH_F"
    assert move["variables"]["optionId"] == "a"  # ACTIVE → option id "a"
    assert move["variables"]["itemId"] == "PVTI_1"


def test_set_item_health_raises_on_mutation_errors() -> None:
    """set_item_health raises GraphQLError when the mutation response carries errors."""

    class _ErrFake(_Fake):
        def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
            self.calls.append(payload)
            if "updateProjectV2ItemFieldValue" in payload["query"]:
                return {"errors": [{"message": "nope"}]}
            return self._read

    fake = _ErrFake(read=_all_options())
    client = _client(fake)
    with pytest.raises(GraphQLError):
        client.set_item_health("PVTI_1", "ACTIVE")
