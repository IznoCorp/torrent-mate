"""Unit tests for the GitHub board adapter.

A fake GraphQL transport routes by the operation embedded in the query string and
returns **real captured fixture JSON** (loaded from ``fixtures/`` on disk, modelled
on the exact shapes GitHub Projects v2 returns — Hardening H6), so no test touches
the network and the parsers are exercised against production-like data. A fake REST
transport records ``(method, path, body)`` tuples. The tests assert:

- ``snapshot()`` parses tickets (ids, titles, column keys, issue numbers / draft);
- ``cheap_probe()`` returns a stable, change-sensitive token;
- ``move_card()`` resolves the column to an option id and builds the right
  ``updateProjectV2ItemFieldValue`` variables;
- ``comment()`` POSTs to the correct REST endpoint with the right body;
- the **default** transport carries both a connect and a read timeout (the
  mandatory network-timeout-safety rule, CLAUDE.md);
- token scope validation accepts ``project``/``repo`` and rejects ``admin:org_hook``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from kanbanmate.adapters.github._parsers import GitHubHTTPError, GraphQLError
from kanbanmate.adapters.github.client import GithubClient, Timeouts, UrllibTransport
from kanbanmate.adapters.github.types import IssueContext
from kanbanmate.adapters.github.token import (
    TokenScopeError,
    parse_scopes,
    validate_scopes,
)
from kanbanmate.core.domain import BoardSnapshot

_FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    """Load a real captured GitHub response fixture from ``fixtures/`` (H6).

    Args:
        name: The fixture file name (e.g. ``board_snapshot_page1.json``).

    Returns:
        The decoded JSON object, shaped exactly as the live GitHub API returns it.
    """
    data: dict[str, Any] = json.loads((_FIXTURES / name).read_text())
    return data


# ---------------------------------------------------------------------------
# Fixtures: real captured GraphQL/REST responses loaded from disk (H6)
# ---------------------------------------------------------------------------


def _board_items_response() -> dict[str, Any]:
    """Page 1 of the real captured board snapshot (Done Issue + In Progress draft)."""
    return _load_fixture("board_snapshot_page1.json")


def _board_items_page2_response() -> dict[str, Any]:
    """Page 2 of the real captured board snapshot (Backlog Issue + a PR, no Status)."""
    return _load_fixture("board_snapshot_page2.json")


def _cheap_probe_response() -> dict[str, Any]:
    """The real captured 5-newest-items probe response."""
    return _load_fixture("cheap_probe.json")


def _move_ok_response() -> dict[str, Any]:
    """The real captured successful move-mutation response."""
    return _load_fixture("move_mutation.json")


def _comment_rest_response() -> dict[str, Any]:
    """The real captured REST issue-comment-create (201) response body."""
    return _load_fixture("comment_rest.json")


def _status_field_response() -> dict[str, Any]:
    """The Status single-select field with its option map."""
    return {
        "data": {
            "node": {
                "fields": {
                    "nodes": [
                        {"name": "Title"},  # a non-single-select field (no options)
                        {
                            "id": "PVTSSF_STATUS",
                            "name": "Status",
                            "options": [
                                {"id": "opt_backlog", "name": "Backlog"},
                                {"id": "opt_inprogress", "name": "In Progress"},
                                {"id": "opt_done", "name": "Done"},
                            ],
                        },
                    ]
                }
            }
        }
    }


def _issue_context_response() -> dict[str, Any]:
    """The real captured issue-context GraphQL response (body + 2 comments + linked issue)."""
    return _load_fixture("issue_context.json")


def _issue_state_response() -> dict[str, Any]:
    """The real captured issue-state GraphQL response (CLOSED issue)."""
    return _load_fixture("issue_state_closed.json")


# ---------------------------------------------------------------------------
# Fakes: transports that record calls and return fixtures (no network)
# ---------------------------------------------------------------------------


class FakeGraphQL:
    """A GraphQL transport that routes by operation and records every payload.

    Routing inspects the query text for a discriminating token (the operation
    name or a unique field) so a single fake serves probe, snapshot, status-field,
    and move calls.
    """

    def __init__(self) -> None:
        """Initialise an empty call log."""
        self.calls: list[dict[str, Any]] = []

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return the fixture matching the payload's query; record the payload."""
        self.calls.append(payload)
        query = payload["query"]
        if "updateProjectV2ItemFieldValue" in query:
            return _move_ok_response()
        if "createProjectV2StatusUpdate" in query:
            # The create mutation returns the new status-update node id.
            return {"data": {"createProjectV2StatusUpdate": {"statusUpdate": {"id": "PVTSU_NEW"}}}}
        if "updateProjectV2StatusUpdate" in query:
            # The update mutation echoes the refreshed status-update node id.
            return {"data": {"updateProjectV2StatusUpdate": {"statusUpdate": {"id": "PVTSU_OLD"}}}}
        if "deleteProjectV2StatusUpdate" in query:
            # The delete mutation echoes the deleted status-update node id (phase-36).
            # The payload field is ``deletedStatusUpdateId`` — the type has NO
            # ``statusUpdate`` field (selecting it makes GitHub reject the mutation).
            return {"data": {"deleteProjectV2StatusUpdate": {"deletedStatusUpdateId": "PVTSU_OLD"}}}
        # Cheap probe: items(first: 100) selecting only updatedAt, with NO pageInfo
        # (the snapshot also reads items(first: 100) but requests pageInfo for paging).
        if "items(first: 100" in query and "pageInfo" not in query:
            return _cheap_probe_response()
        if "ProjectV2SingleSelectField" in query and "options" in query:
            return _status_field_response()
        if "issue(number:" in query and "state" in query:
            # issue_state: open/closed probe (the #13 dependency-gate fallback).
            return _issue_state_response()
        if "CROSS_REFERENCED_EVENT" in query:
            # issue_context: issue body + comments + timelineItems with cross-refs.
            return _issue_context_response()
        if "items(first: 100" in query or "pageInfo" in query:
            # The real captured snapshot spans two pages; route by the cursor the
            # client threads from page 1's ``endCursor`` so the parser is exercised
            # against the genuine two-page shape (page 1 hasNextPage=true).
            after = payload.get("variables", {}).get("after")
            return _board_items_page2_response() if after else _board_items_response()
        raise AssertionError(f"unexpected GraphQL query: {query[:80]}")

    def last_with(self, marker: str) -> dict[str, Any]:
        """Return the most recent recorded payload whose query contains ``marker``."""
        for payload in reversed(self.calls):
            if marker in payload["query"]:
                return payload
        raise AssertionError(f"no recorded call containing {marker!r}")


class FakeRest:
    """A REST transport that records ``(method, path, body)`` and replays a fixture.

    Returns the real captured 201 issue-comment-create body (H6) on a comment POST
    so the transport hands back production-like JSON; any other path yields ``{}``
    (an empty 2xx body), matching the live transport's empty-body contract.
    """

    def __init__(self) -> None:
        """Initialise an empty call log."""
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def __call__(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        """Record the call and replay the captured comment body for comment POSTs."""
        self.calls.append((method, path, body))
        if method == "POST" and path.endswith("/comments"):
            return _comment_rest_response()
        return {}


def _client(graphql: FakeGraphQL, rest: FakeRest) -> GithubClient:
    """Build a :class:`GithubClient` wired to the supplied fake transports."""
    return GithubClient(
        token="tok",
        project_id="PVT_PROJECT",
        repo="IznoCorp/demo",
        graphql_transport=graphql,
        rest_transport=rest,
    )


# ---------------------------------------------------------------------------
# BoardReader: snapshot + cheap_probe
# ---------------------------------------------------------------------------


def test_snapshot_parses_tickets() -> None:
    """``snapshot`` maps the real captured board pages into typed tickets.

    Asserts the parsed :class:`Ticket` fields match the fixture's real values
    EXACTLY across both captured pages (H6): a Done Issue, an In Progress draft,
    a Backlog Issue, and a PullRequest item that carries neither a number nor a
    Status — the real shape the synthetic fixtures never exercised.
    """
    client = _client(FakeGraphQL(), FakeRest())
    snap = client.snapshot()

    assert isinstance(snap, BoardSnapshot)
    assert snap.fetched_at > 0
    # Page 1 (2 items) + page 2 (2 items) = 4 tickets, all kept (each has an id).
    assert len(snap.tickets) == 4

    done_issue, draft, backlog_issue, pr_item = snap.tickets

    # Page 1, item 1 — a Done Issue. Its body is carried so the dependency gate
    # (DESIGN §9) can read ``Depends on #N`` references off it.
    assert done_issue.item_id == "PVTI_lADOBpVuBM4Ae2-IzgABcDE"
    assert done_issue.issue_number == 7
    assert done_issue.title == "Bootstrap the polling engine"
    assert done_issue.column_key == "Done"
    assert done_issue.body == "Kick off the engine.\n\nDepends on #4"

    # Page 1, item 2 — a DraftIssue has no issue number nor body but keeps its title/column.
    assert draft.item_id == "PVTI_lADOBpVuBM4Ae2-IzgABcDF"
    assert draft.issue_number is None
    assert draft.title == "Sketch the heartbeat hook"
    assert draft.column_key == "In Progress"
    assert draft.body == ""

    # Page 2, item 1 — a Backlog Issue.
    assert backlog_issue.item_id == "PVTI_lADOBpVuBM4Ae2-IzgABcDG"
    assert backlog_issue.issue_number == 12
    assert backlog_issue.title == "Wire the GitHub adapter"
    assert backlog_issue.column_key == "Backlog"

    # Page 2, item 2 — a PullRequest with no Status set: no number, empty title,
    # empty column. The real shape the parser must survive (the H6 variance guard).
    assert pr_item.item_id == "PVTI_lADOBpVuBM4Ae2-IzgABcDH"
    assert pr_item.issue_number is None
    assert pr_item.title == ""
    assert pr_item.column_key == ""
    # A non-Issue (PullRequest) carries no body — the gate must see "" not raise.
    assert pr_item.body == ""


def test_snapshot_follows_real_end_cursor_across_pages() -> None:
    """The snapshot threads the real captured ``endCursor`` and stops on page 2.

    The captured page-1 fixture reports ``hasNextPage: true`` with a genuine
    base64 cursor (``"Mg"``); page 2 reports ``hasNextPage: false``. The loop must
    fetch page 1 with no cursor, then page 2 with ``after="Mg"`` (the real value).
    """
    graphql = FakeGraphQL()
    _client(graphql, FakeRest()).snapshot()

    board_calls = [c for c in graphql.calls if "items(first: 100" in c["query"]]
    assert len(board_calls) == 2, "two-page board must fetch exactly twice"
    # Page 1 carries no cursor; page 2 carries page 1's real endCursor.
    assert board_calls[0]["variables"]["after"] is None
    assert board_calls[1]["variables"]["after"] == "Mg"


def test_cheap_probe_token_is_stable_and_change_sensitive() -> None:
    """``cheap_probe`` returns a deterministic token derived from item timestamps."""
    client = _client(FakeGraphQL(), FakeRest())
    token = client.cheap_probe()

    # The token is the newline-joined, SORTED ``updatedAt`` stamps of the fixture's
    # items (sorting makes it independent of GitHub's return order; the query no longer
    # orders by UPDATED_AT — invalid for ProjectV2ItemOrderField — so the client sorts).
    assert token == (
        "2026-06-03T22:10:00Z\n"
        "2026-06-04T07:40:18Z\n"
        "2026-06-04T07:55:01Z\n"
        "2026-06-04T08:29:54Z\n"
        "2026-06-04T08:31:12Z"
    )
    # Idempotent for the same board state.
    assert client.cheap_probe() == token


# ---------------------------------------------------------------------------
# BoardWriter: move_card + comment
# ---------------------------------------------------------------------------


def test_move_card_builds_mutation_variables() -> None:
    """``move_card`` resolves the column to an option id and builds move variables."""
    graphql = FakeGraphQL()
    client = _client(graphql, FakeRest())

    client.move_card("PVTI_001", "In Progress")

    mutation = graphql.last_with("updateProjectV2ItemFieldValue")
    variables = mutation["variables"]
    assert variables["projectId"] == "PVT_PROJECT"
    assert variables["itemId"] == "PVTI_001"
    assert variables["fieldId"] == "PVTSSF_STATUS"
    assert variables["optionId"] == "opt_inprogress"


def test_move_card_caches_status_field() -> None:
    """The Status field is resolved once and reused across moves (one fields query)."""
    graphql = FakeGraphQL()
    client = _client(graphql, FakeRest())

    client.move_card("PVTI_001", "In Progress")
    client.move_card("PVTI_002", "Done")

    field_queries = [c for c in graphql.calls if "ProjectV2SingleSelectField" in c["query"]]
    assert len(field_queries) == 1, "Status field must be cached after first resolution"


def test_move_card_rejects_unknown_column() -> None:
    """An unknown column key fails loud rather than moving to a wrong option."""
    client = _client(FakeGraphQL(), FakeRest())
    with pytest.raises(KeyError, match="unknown column 'Nope'"):
        client.move_card("PVTI_001", "Nope")


def _confirmed_move_transport(returned_name: object) -> object:
    """A GraphQL transport: answers the Status-field query, then a move whose response carries
    ``returned_name`` as the resulting single-select value (a dict, or ``None`` for no value)."""

    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        q = payload["query"]
        if "ProjectV2SingleSelectField" in q and "options" in q:
            return _status_field_response()
        if "updateProjectV2ItemFieldValue" in q:
            value = {"name": returned_name} if returned_name is not None else None
            return {
                "data": {
                    "updateProjectV2ItemFieldValue": {
                        "projectV2Item": {"id": "PVTI_001", "fieldValueByName": value}
                    }
                }
            }
        raise AssertionError(f"unexpected query: {q[:60]}")

    return transport


def test_move_card_confirmed_returns_status_name() -> None:
    """``move_card_confirmed`` returns the Status name read out of the mutation response (read-your-write)."""
    client = _client(_confirmed_move_transport("In Progress"), FakeRest())  # type: ignore[arg-type]
    assert client.move_card_confirmed("PVTI_001", "In Progress") == "In Progress"


def test_move_card_confirmed_none_when_value_absent() -> None:
    """A mutation response with no single-select value yields ``None`` (caller → 'unconfirmed')."""
    client = _client(_confirmed_move_transport(None), FakeRest())  # type: ignore[arg-type]
    assert client.move_card_confirmed("PVTI_001", "In Progress") is None


def test_move_card_confirmed_rejects_unknown_column() -> None:
    """Unknown column fails loud (same guard as move_card) before any mutation."""
    client = _client(FakeGraphQL(), FakeRest())
    with pytest.raises(KeyError, match="unknown column 'Nope'"):
        client.move_card_confirmed("PVTI_001", "Nope")


# ---------------------------------------------------------------------------
# ProjectStatusReporter: rolling status-update create + update (phase-24 §24.2)
# ---------------------------------------------------------------------------


def test_create_status_update_maps_domain_health_to_github_wire_enum() -> None:
    """``create_status_update`` MAPS the domain health name to GitHub's wire enum before the mutation.

    Callers pass KanbanMate's domain health (``ACTIVE``); the adapter is the boundary that translates
    it to GitHub's fixed ``ProjectV2StatusUpdateStatus`` (``ON_TRACK``) — sending the domain name raw
    would be an invalid-enum GraphQL error.
    """
    graphql = FakeGraphQL()
    client = _client(graphql, FakeRest())

    new_id = client.create_status_update("PVT_PROJECT", "the dashboard body", "ACTIVE")

    assert new_id == "PVTSU_NEW"
    mutation = graphql.last_with("createProjectV2StatusUpdate")
    variables = mutation["variables"]
    assert variables["projectId"] == "PVT_PROJECT"
    assert variables["body"] == "the dashboard body"
    assert variables["status"] == "ON_TRACK"  # ACTIVE (domain) → ON_TRACK (GitHub wire)


def test_update_status_update_maps_domain_health_to_github_wire_enum() -> None:
    """``update_status_update`` MAPS the domain health to the wire enum (WAITING → AT_RISK)."""
    graphql = FakeGraphQL()
    client = _client(graphql, FakeRest())

    client.update_status_update("PVTSU_OLD", "refreshed body", "WAITING")

    mutation = graphql.last_with("updateProjectV2StatusUpdate")
    variables = mutation["variables"]
    assert variables["statusUpdateId"] == "PVTSU_OLD"
    assert variables["body"] == "refreshed body"
    assert variables["status"] == "AT_RISK"  # WAITING (domain) → AT_RISK (GitHub wire)


def test_status_health_maps_all_domain_names_to_wire_enum() -> None:
    """The full domain→wire health map is exhaustive and correct (the adapter boundary contract)."""
    from kanbanmate.adapters.github.client import _to_github_status
    from kanbanmate.core.status_update import STATUS_VALUES

    expected = {
        "INACTIVE": "INACTIVE",
        "BLOCKED": "OFF_TRACK",
        "WAITING": "AT_RISK",
        "ACTIVE": "ON_TRACK",
        "COMPLETE": "COMPLETE",
    }
    # Every domain health value has a wire mapping.
    assert set(expected) == set(STATUS_VALUES)
    for domain, wire in expected.items():
        assert _to_github_status(domain) == wire


def test_delete_status_update_issues_mutation_by_id() -> None:
    """``delete_status_update`` issues ``deleteProjectV2StatusUpdate`` with the orphaned id (phase-36)."""
    graphql = FakeGraphQL()
    client = _client(graphql, FakeRest())

    client.delete_status_update("PVTSU_OLD")

    mutation = graphql.last_with("deleteProjectV2StatusUpdate")
    assert mutation["variables"] == {"statusUpdateId": "PVTSU_OLD"}
    # The payload selection MUST be ``deletedStatusUpdateId`` — the
    # ``DeleteProjectV2StatusUpdatePayload`` type has NO ``statusUpdate`` field, so
    # the old ``statusUpdate { id }`` selection made GitHub reject EVERY delete
    # (orphans stacked up, observed live: 52). Lock the correct selection in.
    assert "deletedStatusUpdateId" in mutation["query"]
    assert "statusUpdate {" not in mutation["query"]


def test_delete_status_update_errors_response_raises_graphql_error() -> None:
    """An ``errors``-bearing delete response raises ``GraphQLError`` (the caller swallows it, §36)."""

    def fake_graphql(_payload: dict[str, Any]) -> dict[str, Any]:
        return {"errors": [{"message": "Could not resolve to a ProjectV2StatusUpdate"}]}

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="o/r",
        graphql_transport=fake_graphql,
        rest_transport=FakeRest(),
    )
    with pytest.raises(GraphQLError, match="Could not resolve to a ProjectV2StatusUpdate"):
        client.delete_status_update("PVTSU_STALE")


def test_create_status_update_errors_response_raises_graphql_error() -> None:
    """An ``errors``-bearing create response raises ``GraphQLError`` (fail-loud at the adapter)."""

    def fake_graphql(_payload: dict[str, Any]) -> dict[str, Any]:
        return {"errors": [{"message": "Could not resolve to a ProjectV2"}]}

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="o/r",
        graphql_transport=fake_graphql,
        rest_transport=FakeRest(),
    )
    with pytest.raises(GraphQLError, match="Could not resolve to a ProjectV2"):
        client.create_status_update("PVT", "body", "ACTIVE")


def test_update_status_update_errors_response_raises_graphql_error() -> None:
    """An ``errors``-bearing update response raises ``GraphQLError`` (the stale-id signal)."""

    def fake_graphql(_payload: dict[str, Any]) -> dict[str, Any]:
        return {"errors": [{"message": "Could not resolve to a ProjectV2StatusUpdate"}]}

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="o/r",
        graphql_transport=fake_graphql,
        rest_transport=FakeRest(),
    )
    with pytest.raises(GraphQLError, match="Could not resolve to a ProjectV2StatusUpdate"):
        client.update_status_update("PVTSU_STALE", "body", "ACTIVE")


def test_comment_posts_to_rest_endpoint() -> None:
    """``comment`` POSTs the body to the issue-comments REST endpoint.

    Uses issue 7 (the Done issue from the captured board snapshot) and the real
    captured comment body so the path matches the fixture's ``issue_url`` (H6).
    """
    rest = FakeRest()
    client = _client(FakeGraphQL(), rest)

    client.comment(7, "Agent launched in worktree `ticket-7`.")

    assert rest.calls == [
        (
            "POST",
            "/repos/IznoCorp/demo/issues/7/comments",
            {"body": "Agent launched in worktree `ticket-7`."},
        )
    ]


def test_comment_rest_fixture_is_real_201_shape() -> None:
    """The captured comment fixture is the real REST 201 body GitHub returns (H6).

    Pins the production shape so a parser added later (e.g. sticky-comment id
    bookkeeping) is exercised against the fields GitHub actually sends.
    """
    fixture = _comment_rest_response()
    assert fixture["node_id"].startswith("IC_")
    assert fixture["issue_url"].endswith("/issues/7")
    assert fixture["user"]["type"] == "Bot"
    assert fixture["body"] == "Agent launched in worktree `ticket-7`."


# ---------------------------------------------------------------------------
# Pull-request operations (DESIGN §8.2): find_open_pr, close_pr,
# close_open_pr_for_branch
# ---------------------------------------------------------------------------


def test_find_open_pr_returns_number_when_pr_exists() -> None:
    """``find_open_pr`` returns the open PR number when one exists for the branch.

    The REST GET path qualifies ``head`` with the repo owner so a same-named
    branch in a fork does not match (port of the PoC behaviour).
    """
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def fake_rest(method: str, path: str, body: dict[str, Any] | None) -> Any:
        calls.append((method, path, body))
        if method == "GET" and "/pulls" in path and "state=open" in path:
            return [{"number": 42, "state": "open", "head": {"ref": "feat/x"}}]
        return {}

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="IznoCorp/demo",
        graphql_transport=FakeGraphQL(),
        rest_transport=fake_rest,
    )
    result = client.find_open_pr("feat/x")

    assert result == 42
    assert len(calls) == 1
    assert calls[0][0] == "GET"
    assert "state=open" in calls[0][1]
    # The head is qualified with the owner so a fork branch does not match.
    assert "head=IznoCorp:feat/x" in calls[0][1]
    # The page-1 path is built by `_rest.list_open_pulls_for_branch` (16.3),
    # which appends ``per_page=100`` (the 16.2 pagination contract).
    assert "per_page=100" in calls[0][1]


def test_find_open_pr_returns_none_when_no_open_pr() -> None:
    """``find_open_pr`` returns ``None`` when the listing is empty (no open PR)."""

    def fake_rest(method: str, path: str, body: dict[str, Any] | None) -> Any:
        if method == "GET" and "/pulls" in path:
            return []  # empty — no open PR
        return {}

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="IznoCorp/demo",
        graphql_transport=FakeGraphQL(),
        rest_transport=fake_rest,
    )
    assert client.find_open_pr("feat/nonexistent") is None


def test_find_open_pr_no_roundtrip_on_empty_or_head_branch() -> None:
    """Empty / ``"HEAD"`` branch → ``None`` without a network round-trip."""

    def fake_rest(_method: str, _path: str, _body: dict[str, Any] | None) -> Any:
        raise AssertionError("transport must not be called for empty/HEAD branch")

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="IznoCorp/demo",
        graphql_transport=FakeGraphQL(),
        rest_transport=fake_rest,
    )
    # The transport is never called — the guard returns early.
    assert client.find_open_pr("") is None
    assert client.find_open_pr("HEAD") is None
    assert client.close_open_pr_for_branch("") is None
    assert client.close_open_pr_for_branch("HEAD") is None


def test_close_pr_issues_patch_state_closed() -> None:
    """``close_pr`` issues PATCH with ``{"state": "closed"}``, keeping the branch.

    The branch is NEVER touched — no DELETE / delete-ref call is made (close ≠
    delete-ref; the operator-decided Cancel semantics, DESIGN §8.2).
    """
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def fake_rest(method: str, path: str, body: dict[str, Any] | None) -> Any:
        calls.append((method, path, body))
        return {}

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="IznoCorp/demo",
        graphql_transport=FakeGraphQL(),
        rest_transport=fake_rest,
    )
    client.close_pr(42)

    assert len(calls) == 1
    assert calls[0][0] == "PATCH"
    assert calls[0][1] == "/repos/IznoCorp/demo/pulls/42"
    assert calls[0][2] == {"state": "closed"}
    # No DELETE call — the branch is KEPT (close ≠ delete-ref).
    assert not any(m == "DELETE" for m, _, _ in calls)


def test_close_open_pr_for_branch_composes_find_and_close() -> None:
    """``close_open_pr_for_branch`` finds the open PR, closes it, returns its number.

    The two-step compose: GET to resolve the PR, PATCH to close it.
    """
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def fake_rest(method: str, path: str, body: dict[str, Any] | None) -> Any:
        calls.append((method, path, body))
        if method == "GET" and "/pulls" in path:
            return [{"number": 99, "state": "open"}]
        return {}

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="IznoCorp/demo",
        graphql_transport=FakeGraphQL(),
        rest_transport=fake_rest,
    )
    result = client.close_open_pr_for_branch("feat/x")

    assert result == 99
    # Two calls: GET to find, PATCH to close.
    assert len(calls) == 2
    assert calls[0][0] == "GET"
    assert calls[1][0] == "PATCH"
    assert calls[1][2] == {"state": "closed"}
    # The branch is KEPT — no DELETE call.
    assert not any(m == "DELETE" for m, _, _ in calls)


def test_close_open_pr_for_branch_noop_when_no_open_pr() -> None:
    """``close_open_pr_for_branch`` is a no-op (returns ``None``) when no open PR exists.

    The PATCH must not be called — only the GET fires and returns empty.
    """

    def fake_rest(method: str, path: str, body: dict[str, Any] | None) -> Any:
        if method == "GET" and "/pulls" in path:
            return []  # empty listing — no open PR
        raise AssertionError("PATCH must not be called when find returns None")

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="IznoCorp/demo",
        graphql_transport=FakeGraphQL(),
        rest_transport=fake_rest,
    )
    assert client.close_open_pr_for_branch("feat/x") is None


# ---------------------------------------------------------------------------
# Issue context (GraphQL body + comments + linked issue) — ported from the PoC
# ---------------------------------------------------------------------------


def test_issue_context_returns_body_comments_and_linked_issue() -> None:
    """``issue_context`` returns a complete ``IssueContext`` from the GraphQL fixture.

    The fixture carries an issue body, two comments, and one cross-referenced
    Issue source — the parser must return all three fields populated.
    """
    graphql = FakeGraphQL()
    client = _client(graphql, FakeRest())

    ctx = client.issue_context(7)

    assert isinstance(ctx, IssueContext)
    assert ctx.body == "Kick off the engine.\n\nDepends on #4"
    assert ctx.comments == (
        "First comment — agent launched.",
        "Second comment — step completed.",
    )
    assert ctx.comment_dates == (
        "2026-06-20T10:15:00Z",
        "2026-06-20T11:30:00Z",
    )
    assert ctx.linked_issue_body == "This is the linked issue body — the upstream ticket."

    # Query carried the correct owner/name/number variables.
    call = graphql.last_with("CROSS_REFERENCED_EVENT")
    assert call["variables"] == {"owner": "IznoCorp", "name": "demo", "number": 7}


def test_issue_context_no_timeline_items_returns_none_linked() -> None:
    """No ``timelineItems`` nodes → ``linked_issue_body`` is ``None``."""

    def fake_graphql(_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "data": {
                "repository": {
                    "issue": {
                        "body": "just a body",
                        "comments": {"nodes": []},
                        "timelineItems": {"nodes": []},
                    }
                }
            }
        }

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="o/r",
        graphql_transport=fake_graphql,
        rest_transport=FakeRest(),
    )
    ctx = client.issue_context(1)
    assert ctx.body == "just a body"
    assert ctx.comments == ()
    assert ctx.linked_issue_body is None


def test_issue_context_cross_ref_source_without_body_returns_none() -> None:
    """A cross-reference whose ``source`` has no ``body`` → ``linked_issue_body`` is ``None``."""

    def fake_graphql(_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "data": {
                "repository": {
                    "issue": {
                        "body": "body",
                        "comments": {"nodes": []},
                        "timelineItems": {
                            "nodes": [
                                {"source": {"someOtherField": 42}},  # no 'body' key
                            ]
                        },
                    }
                }
            }
        }

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="o/r",
        graphql_transport=fake_graphql,
        rest_transport=FakeRest(),
    )
    ctx = client.issue_context(1)
    assert ctx.body == "body"
    assert ctx.linked_issue_body is None


def test_issue_context_errors_response_raises_graphql_error() -> None:
    """An ``errors``-bearing response raises ``GraphQLError`` via ``raise_for_errors``."""

    def fake_graphql(_payload: dict[str, Any]) -> dict[str, Any]:
        return {"errors": [{"message": "Could not resolve to a Repository"}]}

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="o/r",
        graphql_transport=fake_graphql,
        rest_transport=FakeRest(),
    )
    with pytest.raises(GraphQLError, match="Could not resolve to a Repository"):
        client.issue_context(999)


def test_parse_issue_context_none_guards_survive_missing_keys() -> None:
    """A direct ``parse_issue_context`` call on partial/incomplete dicts never crashes.

    Proves the defensive ``or {}`` drilling at every level: missing ``data``,
    ``repository``, ``issue``, ``comments.nodes``, and ``timelineItems.nodes`` all
    return an empty ``IssueContext`` rather than raising ``KeyError`` / ``TypeError``.
    """
    from kanbanmate.adapters.github._parsers import parse_issue_context

    # Completely empty response (no "data" key).
    assert parse_issue_context({}) == IssueContext(body="", comments=(), linked_issue_body=None)

    # "data" present but no "repository".
    assert parse_issue_context({"data": {}}) == IssueContext(
        body="", comments=(), linked_issue_body=None
    )

    # "repository" present but no "issue".
    assert parse_issue_context({"data": {"repository": {}}}) == IssueContext(
        body="", comments=(), linked_issue_body=None
    )

    # "issue" present but no body/comments/timelineItems.
    assert parse_issue_context({"data": {"repository": {"issue": {}}}}) == IssueContext(
        body="", comments=(), linked_issue_body=None
    )

    # comments without nodes.
    assert parse_issue_context(
        {"data": {"repository": {"issue": {"body": "x", "comments": {}}}}}
    ) == IssueContext(body="x", comments=(), linked_issue_body=None)


# ---------------------------------------------------------------------------
# Issue state (GraphQL open/closed probe; the #13 dependency-gate fallback)
# ---------------------------------------------------------------------------


def test_issue_state_returns_true_when_closed() -> None:
    """``issue_state`` returns ``True`` for a CLOSED issue (the fixture carries ``state: CLOSED``)."""
    graphql = FakeGraphQL()
    client = _client(graphql, FakeRest())

    result = client.issue_state(7)

    assert result is True
    # Query carried the correct owner/name/number variables.
    call = graphql.last_with("state")
    assert call["variables"] == {"owner": "IznoCorp", "name": "demo", "number": 7}


def test_issue_state_returns_false_when_open() -> None:
    """``issue_state`` returns ``False`` for an OPEN issue."""

    def fake_graphql(_payload: dict[str, Any]) -> dict[str, Any]:
        return {"data": {"repository": {"issue": {"number": 7, "state": "OPEN"}}}}

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="o/r",
        graphql_transport=fake_graphql,
        rest_transport=FakeRest(),
    )
    assert client.issue_state(7) is False


def test_issue_state_returns_false_when_missing_state() -> None:
    """A missing ``state`` field → ``False`` (conservative: undecidable is NOT done)."""

    def fake_graphql(_payload: dict[str, Any]) -> dict[str, Any]:
        return {"data": {"repository": {"issue": {"number": 7}}}}

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="o/r",
        graphql_transport=fake_graphql,
        rest_transport=FakeRest(),
    )
    assert client.issue_state(7) is False


def test_issue_state_returns_false_when_null_issue() -> None:
    """A ``null`` issue node (no such issue) → ``False``."""

    def fake_graphql(_payload: dict[str, Any]) -> dict[str, Any]:
        return {"data": {"repository": {"issue": None}}}

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="o/r",
        graphql_transport=fake_graphql,
        rest_transport=FakeRest(),
    )
    assert client.issue_state(999) is False


def test_issue_state_errors_response_raises_graphql_error() -> None:
    """An ``errors``-bearing response raises ``GraphQLError`` via ``raise_for_errors``."""

    def fake_graphql(_payload: dict[str, Any]) -> dict[str, Any]:
        return {"errors": [{"message": "Could not resolve to a Repository"}]}

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="o/r",
        graphql_transport=fake_graphql,
        rest_transport=FakeRest(),
    )
    with pytest.raises(GraphQLError, match="Could not resolve to a Repository"):
        client.issue_state(999)


def test_parse_issue_closed_none_guards_survive_missing_keys() -> None:
    """A direct ``parse_issue_closed`` call on partial/incomplete dicts never crashes.

    Proves the defensive ``or {}`` drilling at every level: missing ``data``,
    ``repository``, ``issue``, and empty ``state`` all return ``False`` rather
    than raising ``KeyError`` / ``TypeError``. A CLOSED state returns ``True``
    (case-insensitive); an OPEN state returns ``False``.
    """
    from kanbanmate.adapters.github._parsers import parse_issue_closed

    # Completely empty response (no "data" key).
    assert parse_issue_closed({}) is False

    # "data" present but no "repository".
    assert parse_issue_closed({"data": {}}) is False

    # "repository" present but no "issue".
    assert parse_issue_closed({"data": {"repository": {}}}) is False

    # "issue" present but no "state".
    assert parse_issue_closed({"data": {"repository": {"issue": {}}}}) is False

    # "issue" with null state.
    assert parse_issue_closed({"data": {"repository": {"issue": {"state": None}}}}) is False

    # Empty string state.
    assert parse_issue_closed({"data": {"repository": {"issue": {"state": ""}}}}) is False

    # OPEN → False.
    assert parse_issue_closed({"data": {"repository": {"issue": {"state": "OPEN"}}}}) is False

    # CLOSED → True.
    assert parse_issue_closed({"data": {"repository": {"issue": {"state": "CLOSED"}}}}) is True

    # Case-insensitive: lowercase "closed" → True.
    assert parse_issue_closed({"data": {"repository": {"issue": {"state": "closed"}}}}) is True


# ---------------------------------------------------------------------------
# Fail-loud error paths (GraphQLError, GitHubHTTPError, no-Status ValueError)
# ---------------------------------------------------------------------------


def test_graphql_error_raised_on_errors_array() -> None:
    """A GraphQL response with a non-empty ``errors`` array raises ``GraphQLError``.

    The ``raise_for_errors`` guard is exercised through ``cheap_probe`` (a read
    path), proving that a failed query/mutation never passes silently — the daemon
    sees a loud exception rather than a half-empty or misleading result.
    """

    def fake_graphql(_payload: dict[str, Any]) -> dict[str, Any]:
        return {"errors": [{"message": "Something went wrong"}]}

    client = GithubClient(
        token="tok",
        project_id="PVT",
        graphql_transport=fake_graphql,
        rest_transport=FakeRest(),
    )
    with pytest.raises(GraphQLError, match="Something went wrong"):
        client.cheap_probe()


def test_http_error_raised_on_400_status() -> None:
    """An HTTP >=400 response raises ``GitHubHTTPError`` carrying status and body.

    The transport's ``_request`` raises ``GitHubHTTPError(status, raw_body)`` on
    any status >= 400. A fake REST transport that mimics this behaviour proves
    that the error propagates through the client (here via ``comment``) and that
    the caller can inspect ``.status`` and ``.body`` for the real GitHub
    diagnosis (e.g. "Bad credentials").
    """

    def fake_rest(_method: str, _path: str, _body: dict[str, Any] | None) -> Any:
        raise GitHubHTTPError(401, '{"message": "Bad credentials"}')

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="o/r",
        graphql_transport=FakeGraphQL(),
        rest_transport=fake_rest,
    )
    with pytest.raises(GitHubHTTPError, match="Bad credentials") as exc_info:
        client.comment(7, "test body")
    assert exc_info.value.status == 401
    assert exc_info.value.body == '{"message": "Bad credentials"}'


def test_value_error_on_no_status_field() -> None:
    """A project with no Status single-select field raises ``ValueError``.

    Exercised through ``move_card``, which calls ``_resolve_status_field`` →
    ``parse_status_field``. The guard protects against a misconfigured or
    malformed project where GitHub's auto-created Status field is absent — the
    daemon must fail loud rather than silently skip every move.
    """

    def fake_graphql(_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "data": {
                "node": {
                    "fields": {
                        "nodes": [
                            {"name": "Title"},
                        ]
                    }
                }
            }
        }

    client = GithubClient(
        token="tok",
        project_id="PVT",
        repo="o/r",
        graphql_transport=fake_graphql,
        rest_transport=FakeRest(),
    )
    with pytest.raises(ValueError, match="no Status single-select field"):
        client.move_card("PVTI_001", "In Progress")


# ---------------------------------------------------------------------------
# Network-timeout safety (CLAUDE.md MANDATORY)
# ---------------------------------------------------------------------------


def test_default_transport_sets_connect_and_read_timeouts() -> None:
    """The default urllib transport carries BOTH a connect and a read timeout.

    Proves the timeout-safety rule: a client built without an injected transport
    exposes non-``None`` connect and read budgets (so the daemon cannot hang on I/O).
    """
    client = GithubClient(token="tok", project_id="PVT", repo="o/r")
    timeouts = client.transport_timeouts

    assert timeouts.connect is not None and timeouts.connect > 0
    assert timeouts.read is not None and timeouts.read > 0


def test_urllib_transport_honours_custom_timeouts() -> None:
    """A custom :class:`Timeouts` is propagated to the transport verbatim."""
    transport = UrllibTransport("tok", timeouts=Timeouts(connect=1.5, read=7.0))
    assert transport.timeouts.connect == 1.5
    assert transport.timeouts.read == 7.0


# ---------------------------------------------------------------------------
# Transport transient-retry (#15, PoC ``_urlopen_json`` parity)
# ---------------------------------------------------------------------------


class _FakeSocket:
    """A fake live socket that records the read timeout the transport sets on it."""

    def __init__(self) -> None:
        """Start with no recorded timeout."""
        self.read_timeout: float | None = None

    def settimeout(self, value: float) -> None:
        """Record the read budget the transport lowered the socket to."""
        self.read_timeout = value


class _FakeResponse:
    """A fake ``http.client`` response yielding a scripted status + body (+ optional headers)."""

    def __init__(
        self, status: int, body: str, headers: list[tuple[str, str]] | None = None
    ) -> None:
        """Store the scripted status, body, and any response headers (e.g. Retry-After)."""
        self.status = status
        self._body = body
        self._headers = headers or []

    def read(self) -> bytes:
        """Return the scripted body bytes (the transport decodes them)."""
        return self._body.encode()

    def getheaders(self) -> list[tuple[str, str]]:
        """Return the scripted response headers (empty unless a test scripts Retry-After)."""
        return self._headers


class _FakeConnection:
    """A fake ``HTTPSConnection`` scripting a sequence of ``(status, body)`` responses.

    One instance is reused across every attempt of a single request (the transport
    opens a fresh connection per attempt, so the factory below hands back the same
    recorder). Each ``getresponse`` pops the next scripted response; ``connect_timeouts``
    and ``read_timeouts`` accumulate one entry PER attempt so a test can assert both
    budgets were applied on every retry.
    """

    def __init__(self, responses: list[Any]) -> None:
        """Script the response sequence and init the per-attempt timeout ledgers.

        Each entry is a ``(status, body)`` pair or a ``(status, body, headers)`` triple.
        """
        self._responses = responses
        self._index = 0
        self.connect_timeouts: list[float] = []
        self.read_timeouts: list[float | None] = []
        self.sock: _FakeSocket | None = None

    def request(
        self, method: str, path: str, *, body: bytes | None, headers: dict[str, str]
    ) -> None:  # noqa: ARG002
        """Open a fresh fake socket for this attempt (mirrors a real connect)."""
        self.sock = _FakeSocket()

    def getresponse(self) -> _FakeResponse:
        """Record the read timeout the transport set, then return the next response.

        A scripted entry may be a ``(status, body)`` pair or a ``(status, body, headers)`` triple
        (the latter scripts a ``Retry-After`` for the #2 backoff tests).
        """
        assert self.sock is not None
        self.read_timeouts.append(self.sock.read_timeout)
        entry = self._responses[self._index]
        self._index += 1
        if len(entry) == 3:
            status, body, headers = entry
            return _FakeResponse(status, body, headers)
        status, body = entry
        return _FakeResponse(status, body)

    def close(self) -> None:
        """No-op close (the transport always closes in a finally block)."""


def _patch_transport(
    monkeypatch: pytest.MonkeyPatch, responses: list[Any]
) -> tuple[_FakeConnection, list[float]]:
    """Patch ``http.client.HTTPSConnection`` + ``time.sleep`` for a retry test.

    Returns the single :class:`_FakeConnection` recorder (reused across attempts) and
    the list that captures every backoff sleep so the test can assert the bounded
    ``0.5*(attempt+1)`` schedule without actually sleeping.
    """
    import http.client as http_client
    import time as time_mod

    conn = _FakeConnection(responses)
    sleeps: list[float] = []

    def _factory(host: str, *, timeout: float) -> _FakeConnection:
        # Record the connect budget applied on THIS attempt (one entry per retry).
        conn.connect_timeouts.append(timeout)
        return conn

    monkeypatch.setattr(http_client, "HTTPSConnection", _factory)
    # ``client.py`` calls ``time.sleep`` against the stdlib module, so patching it there
    # captures the backoff schedule and keeps the test instant (no real sleeping).
    monkeypatch.setattr(time_mod, "sleep", lambda s: sleeps.append(s))
    return conn, sleeps


def test_transport_retries_502_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 502 followed by a 200 retries once and returns the decoded body (#15)."""
    conn, sleeps = _patch_transport(monkeypatch, [(502, "bad gateway"), (200, '{"ok": true}')])
    transport = UrllibTransport("tok", timeouts=Timeouts(connect=2.0, read=9.0))

    body = transport.rest("GET", "/x", None)

    assert body == {"ok": True}
    # Exactly one bounded backoff of 0.5*(0+1) before the successful retry.
    assert sleeps == [0.5]
    # The connect AND read timeouts were applied on EVERY attempt (both the 502 and the 200).
    assert conn.connect_timeouts == [2.0, 2.0]
    assert conn.read_timeouts == [9.0, 9.0]


def test_transport_persistent_502_raises_after_three_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A persistent 502 raises ``GitHubHTTPError`` after exactly 3 attempts (#15)."""
    conn, sleeps = _patch_transport(monkeypatch, [(502, "bad gateway")] * 3)
    transport = UrllibTransport("tok")

    with pytest.raises(GitHubHTTPError) as exc_info:
        transport.rest("GET", "/x", None)

    assert exc_info.value.status == 502
    # Three attempts → two bounded backoffs (0.5, 1.0); the final attempt raises (no 3rd sleep).
    assert sleeps == [0.5, 1.0]
    assert len(conn.read_timeouts) == 3


def test_transport_retries_secondary_rate_limit_403(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 403 whose body names the secondary rate limit retries, then succeeds (#15)."""
    conn, sleeps = _patch_transport(
        monkeypatch,
        [(403, '{"message": "You have exceeded a secondary rate limit"}'), (200, "{}")],
    )
    transport = UrllibTransport("tok")

    body = transport.rest("GET", "/x", None)

    assert body == {}
    assert sleeps == [0.5]
    assert len(conn.read_timeouts) == 2


def test_transport_non_transient_403_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 403 with a DIFFERENT body raises IMMEDIATELY — no retry, no backoff (#15)."""
    conn, sleeps = _patch_transport(
        monkeypatch, [(403, '{"message": "Resource not accessible by integration"}')]
    )
    transport = UrllibTransport("tok")

    with pytest.raises(GitHubHTTPError) as exc_info:
        transport.rest("GET", "/x", None)

    assert exc_info.value.status == 403
    # Permanent 4xx: surfaced on the first attempt, no backoff sleep.
    assert sleeps == []
    assert len(conn.read_timeouts) == 1


def test_transport_non_transient_404_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 404 raises immediately and is not retried (only 502 / secondary-rate are, #15)."""
    conn, sleeps = _patch_transport(monkeypatch, [(404, '{"message": "Not Found"}')])
    transport = UrllibTransport("tok")

    with pytest.raises(GitHubHTTPError) as exc_info:
        transport.rest("GET", "/x", None)

    assert exc_info.value.status == 404
    assert sleeps == []
    assert len(conn.read_timeouts) == 1


# ---------------------------------------------------------------------------
# Transport transient-set widening + Retry-After (#2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [429, 500, 503, 504])
def test_transport_widened_transient_statuses_retry(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """429/500/503/504 are now transient and retried, then succeed (#2)."""
    conn, sleeps = _patch_transport(monkeypatch, [(status, "transient"), (200, "{}")])
    transport = UrllibTransport("tok")

    body = transport.rest("GET", "/x", None)

    assert body == {}
    assert sleeps == [0.5]  # one bounded backoff before the successful retry
    assert len(conn.read_timeouts) == 2


def test_transport_honors_retry_after_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 with a Retry-After header sleeps the advised seconds (within budget), then retries (#2)."""
    conn, sleeps = _patch_transport(
        monkeypatch,
        [(429, "slow down", [("Retry-After", "7")]), (200, "{}")],
    )
    transport = UrllibTransport("tok")

    body = transport.rest("GET", "/x", None)

    assert body == {}
    # The advised 7 s is honored (well under the per-request budget), replacing the 0.5 default.
    assert sleeps == [7.0]
    assert len(conn.read_timeouts) == 2


def test_transport_clamps_retry_after_to_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """An oversized Retry-After is CLAMPED to the per-request budget (#2 — never overruns watchdog)."""
    from kanbanmate.adapters.github._transport import _RETRY_AFTER_BUDGET

    conn, sleeps = _patch_transport(
        monkeypatch,
        [(503, "down", [("Retry-After", "600")]), (200, "{}")],
    )
    transport = UrllibTransport("tok")

    body = transport.rest("GET", "/x", None)

    assert body == {}
    # 600 s advised → clamped to the small per-request budget (loop circuit breaker owns long waits).
    assert sleeps == [_RETRY_AFTER_BUDGET]
    assert len(conn.read_timeouts) == 2


def test_transport_retry_after_case_insensitive_and_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lowercased header name is honored; a malformed value falls back to the geometric curve (#2)."""
    # Lowercased header name → still honored.
    _conn1, sleeps1 = _patch_transport(
        monkeypatch, [(429, "x", [("retry-after", "3")]), (200, "{}")]
    )
    UrllibTransport("tok").rest("GET", "/x", None)
    assert sleeps1 == [3.0]

    # Malformed value → geometric fallback (0.5 on the first attempt).
    _conn2, sleeps2 = _patch_transport(
        monkeypatch, [(429, "x", [("Retry-After", "soon")]), (200, "{}")]
    )
    UrllibTransport("tok").rest("GET", "/x", None)
    assert sleeps2 == [0.5]


# ---------------------------------------------------------------------------
# Token scope validation (DESIGN §10): project + repo only
# ---------------------------------------------------------------------------


def test_validate_scopes_accepts_project_and_repo() -> None:
    """The exact ``{project, repo}`` scope set is accepted."""
    validate_scopes(parse_scopes("project, repo"))  # must not raise


def test_validate_scopes_accepts_subset() -> None:
    """A fine-grained PAT reporting fewer/no scopes is accepted (subset rule)."""
    validate_scopes(parse_scopes(""))  # empty header -> empty set -> OK
    validate_scopes(parse_scopes("repo"))


def test_validate_scopes_rejects_admin_org_hook() -> None:
    """An over-broad ``admin:org_hook`` scope is refused (DESIGN §10)."""
    with pytest.raises(TokenScopeError, match="admin:org_hook"):
        validate_scopes(parse_scopes("project, repo, admin:org_hook"))


# ---------------------------------------------------------------------------
# Seeder: project / columns / labels / issue mutations (DESIGN §4.3)
# ---------------------------------------------------------------------------


class SeederGraphQL:
    """A GraphQL transport routing the Seeder operations and recording payloads.

    Returns inline fixture JSON for each Seeder query/mutation by inspecting the
    query text, so no Seeder test touches the network.
    """

    def __init__(
        self, *, existing_project: str | None = None, existing_description: str | None = None
    ) -> None:
        """Initialise the call log, an optional pre-existing project + its description."""
        self.calls: list[dict[str, Any]] = []
        self._existing_project = existing_project
        # The project's current shortDescription the read returns (None → empty).
        self._existing_description = existing_description

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return the fixture matching the payload's query; record the payload."""
        self.calls.append(payload)
        q = payload["query"]
        if "projectsV2(first: 100)" in q:
            nodes = (
                [{"id": self._existing_project, "title": "demo", "number": 1}]
                if self._existing_project
                else []
            )
            return {"data": {"organization": {"projectsV2": {"nodes": nodes}}}}
        if "organization(login:" in q and "{ id }" in q:
            return {"data": {"organization": {"id": "ORG_NODE"}}}
        if "createProjectV2" in q:
            return {"data": {"createProjectV2": {"projectV2": {"id": "PVT_FRESH"}}}}
        if "shortDescription" in q and "updateProjectV2" not in q:
            # The idempotency read: return the canned current description (or null).
            return {"data": {"node": {"shortDescription": self._existing_description}}}
        if "updateProjectV2(input:" in q:
            desc = payload["variables"]["shortDescription"]
            return {
                "data": {"updateProjectV2": {"projectV2": {"id": "PVT", "shortDescription": desc}}}
            }
        if "ProjectV2SingleSelectField" in q and "updateProjectV2Field" not in q:
            return _status_field_response()
        if "updateProjectV2Field" in q:
            options = payload["variables"]["options"]
            return {
                "data": {
                    "updateProjectV2Field": {
                        "projectV2Field": {
                            "options": [
                                {"id": f"opt_{i}", "name": o["name"]} for i, o in enumerate(options)
                            ]
                        }
                    }
                }
            }
        if "items(first: 100" in q and "fieldValueByName" in q and "content" not in q:
            return {"data": {"node": {"items": {"pageInfo": {"hasNextPage": False}, "nodes": []}}}}
        if "repository(owner:" in q and "labels(first: 100)" in q:
            return {
                "data": {
                    "repository": {
                        "id": "REPO_NODE",
                        "labels": {"nodes": [{"id": "lbl_existing", "name": "wave:1"}]},
                    }
                }
            }
        if "linkProjectV2ToRepository" in q:
            return {"data": {"linkProjectV2ToRepository": {"repository": {"id": "REPO_NODE"}}}}
        if "createLabel" in q:
            name = payload["variables"]["name"]
            return {"data": {"createLabel": {"label": {"id": f"lbl_{name}", "name": name}}}}
        if "createIssue" in q:
            return {"data": {"createIssue": {"issue": {"id": "ISSUE_NODE", "number": 7}}}}
        if "updateIssue(" in q:
            return {"data": {"updateIssue": {"issue": {"id": "ISSUE_NODE", "number": 7}}}}
        if "addProjectV2ItemById" in q:
            return {"data": {"addProjectV2ItemById": {"item": {"id": "PVTI_NEW"}}}}
        raise AssertionError(f"unexpected Seeder query: {q[:80]}")

    def last_with(self, marker: str) -> dict[str, Any]:
        """Return the most recent recorded payload whose query contains ``marker``."""
        for payload in reversed(self.calls):
            if marker in payload["query"]:
                return payload
        raise AssertionError(f"no recorded call containing {marker!r}")


def _seeder(graphql: SeederGraphQL) -> GithubClient:
    """Build a Seeder-only :class:`GithubClient` (no project_id/repo baked in)."""
    return GithubClient(token="tok", graphql_transport=graphql, rest_transport=FakeRest())


def test_ensure_project_creates_fresh_when_absent() -> None:
    """``ensure_project`` creates a new org Project when none of the title exists."""
    graphql = SeederGraphQL(existing_project=None)
    project_id = _seeder(graphql).ensure_project("IznoCorp", "demo")

    assert project_id == "PVT_FRESH"
    # The create mutation was driven with the resolved org owner id.
    assert graphql.last_with("createProjectV2")["variables"]["ownerId"] == "ORG_NODE"


def test_ensure_project_reuses_existing_by_title() -> None:
    """``ensure_project`` reuses an existing project of the same title (idempotent)."""
    graphql = SeederGraphQL(existing_project="PVT_OLD")
    project_id = _seeder(graphql).ensure_project("IznoCorp", "demo")

    assert project_id == "PVT_OLD"
    # No project was created when one already matched.
    assert not any("createProjectV2" in c["query"] for c in graphql.calls)


def test_ensure_columns_replaces_options_preserving_existing_ids() -> None:
    """``ensure_columns`` REPLACEs the option set, preserving existing option ids.

    The fixture's Status field is Backlog/In Progress/Done; requesting an extra
    new column (Spec) forces the update mutation, where existing options must
    carry their id (preserved) and the new one must omit it (created fresh).
    """
    graphql = SeederGraphQL()
    target = ["Backlog", "Spec", "In Progress", "Done"]
    option_map = _seeder(graphql).ensure_columns("PVT", target)

    # The returned map covers the requested columns (ids from the update response).
    assert set(option_map) == set(target)
    # The update sent the full target list; existing options carry their id, new ones do not.
    options = graphql.last_with("updateProjectV2Field")["variables"]["options"]
    by_name = {o["name"]: o for o in options}
    assert by_name["Backlog"]["id"] == "opt_backlog"  # preserved existing id
    assert "id" not in by_name["Spec"]  # new column created fresh (no id)


def test_ensure_columns_is_idempotent_when_already_shaped() -> None:
    """When the option set already equals the target, no update mutation is sent."""
    graphql = SeederGraphQL()
    # The fixture's Status field is exactly Backlog/In Progress/Done in that order.
    _seeder(graphql).ensure_columns("PVT", ["Backlog", "In Progress", "Done"])

    assert not any("updateProjectV2Field" in c["query"] for c in graphql.calls)


def test_status_options_returns_parsed_option_map() -> None:
    """``status_options`` returns the board's ``{name: id}`` Status-option map.

    This is the seed Backlog-landing guard's option probe
    (``cli/seed.py:_known_status_options`` reaches it via ``getattr``). It reads the
    same fields query ``ensure_columns`` uses and parses it through
    ``parse_status_option_map``, so the explicit ``--project-id`` seed path can be
    guarded against a board missing the ``Backlog`` option (no half-seed).
    """
    graphql = SeederGraphQL()
    options = _seeder(graphql).status_options("PVT")

    # The fixture's Status field is Backlog/In Progress/Done with their option ids.
    assert options == {
        "Backlog": "opt_backlog",
        "In Progress": "opt_inprogress",
        "Done": "opt_done",
    }


def test_ensure_labels_creates_only_missing() -> None:
    """``ensure_labels`` creates absent labels and reuses existing ones."""
    graphql = SeederGraphQL()
    result = _seeder(graphql).ensure_labels("IznoCorp/demo", ["wave:1", "wave:2"])

    assert result == {"wave:1": "lbl_existing", "wave:2": "lbl_wave:2"}
    # Only the missing label was created (wave:1 already exists in the fixture).
    created = [c for c in graphql.calls if "createLabel" in c["query"]]
    assert len(created) == 1
    assert created[0]["variables"]["name"] == "wave:2"


def test_create_issue_returns_node_and_number() -> None:
    """``create_issue`` returns the new issue's node id and number."""
    node_id, number = _seeder(SeederGraphQL()).create_issue(
        "IznoCorp/demo", "[RP1] Title", "body", ["wave:1"]
    )
    assert node_id == "ISSUE_NODE"
    assert number == 7


def test_add_to_project_returns_item_id() -> None:
    """``add_to_project`` returns the new project item id."""
    item_id = _seeder(SeederGraphQL()).add_to_project("PVT", "ISSUE_NODE")
    assert item_id == "PVTI_NEW"


def test_link_to_repo_resolves_repo_node_and_links() -> None:
    """``link_to_repo`` resolves the repo node id then runs ``linkProjectV2ToRepository``."""
    graphql = SeederGraphQL()
    _seeder(graphql).link_to_repo("PVT_x", "IznoCorp/demo")

    link_calls = [c for c in graphql.calls if "linkProjectV2ToRepository" in c["query"]]
    assert len(link_calls) == 1
    # The repo slug was resolved to its node id (REPO_NODE) before linking.
    assert link_calls[0]["variables"] == {"projectId": "PVT_x", "repositoryId": "REPO_NODE"}


def test_update_project_description_sets_when_empty() -> None:
    """``update_project_description`` writes the default when the board has no description (§33)."""
    graphql = SeederGraphQL(existing_description=None)  # empty board description
    _seeder(graphql).update_project_description("PVT_x", "Kanban by KanbanMate (o/r)")

    # The read ran first, then the mutation set the description.
    mutations = [c for c in graphql.calls if "updateProjectV2(input:" in c["query"]]
    assert len(mutations) == 1
    assert mutations[0]["variables"] == {
        "projectId": "PVT_x",
        "shortDescription": "Kanban by KanbanMate (o/r)",
    }


def test_update_project_description_skips_when_already_set() -> None:
    """An existing non-empty description is never overwritten — the mutation is skipped (§33)."""
    graphql = SeederGraphQL(existing_description="Operator's own description")
    _seeder(graphql).update_project_description("PVT_x", "Kanban by KanbanMate (o/r)")

    # The read ran, but NO update mutation (idempotent — operator description preserved).
    assert not any("updateProjectV2(input:" in c["query"] for c in graphql.calls)


# ---------------------------------------------------------------------------
# Branch-protection probe (doctor; fail-soft 404 → False)
# ---------------------------------------------------------------------------


def test_branch_protection_on_true_on_protection_body() -> None:
    """A 2xx protection body → ``branch_protection_on`` returns True.

    The REST seam returns a body carrying ``required_status_checks``; the client
    hands it to the pure parser and returns its verdict (protected).
    """

    def fake_rest(method: str, path: str, _body: dict[str, Any] | None) -> Any:
        assert method == "GET"
        assert path == "/repos/IznoCorp/demo/branches/main/protection"
        return {"required_status_checks": {"strict": True, "contexts": ["ci"]}}

    client = GithubClient(
        token="tok",
        repo="IznoCorp/demo",
        graphql_transport=FakeGraphQL(),
        rest_transport=fake_rest,
    )
    assert client.branch_protection_on("main") is True


def test_branch_protection_on_false_on_404_no_raise() -> None:
    """A 404 (branch not protected) → returns False WITHOUT raising (fail-soft).

    The ``.../protection`` endpoint 404s when protection is off; the client must
    catch the ``GitHubHTTPError`` and treat it as "off" rather than propagating —
    doctor's branch check is advisory and must never crash.
    """

    def fake_rest(_method: str, _path: str, _body: dict[str, Any] | None) -> Any:
        raise GitHubHTTPError(404, '{"message": "Branch not protected"}')

    client = GithubClient(
        token="tok",
        repo="IznoCorp/demo",
        graphql_transport=FakeGraphQL(),
        rest_transport=fake_rest,
    )
    # No raise — the 404 is swallowed and reported as "off".
    assert client.branch_protection_on("main") is False


def test_branch_protection_on_false_on_403_no_raise() -> None:
    """A 403 (no admin permission to read protection) → False, no raise."""

    def fake_rest(_method: str, _path: str, _body: dict[str, Any] | None) -> Any:
        raise GitHubHTTPError(403, '{"message": "Resource not accessible"}')

    client = GithubClient(
        token="tok",
        repo="IznoCorp/demo",
        graphql_transport=FakeGraphQL(),
        rest_transport=fake_rest,
    )
    assert client.branch_protection_on("main") is False


def test_branch_protection_on_defaults_to_main() -> None:
    """The default branch argument is ``main``."""
    seen: dict[str, str] = {}

    def fake_rest(_method: str, path: str, _body: dict[str, Any] | None) -> Any:
        seen["path"] = path
        return {"enforce_admins": {"enabled": True}}

    client = GithubClient(
        token="tok",
        repo="IznoCorp/demo",
        graphql_transport=FakeGraphQL(),
        rest_transport=fake_rest,
    )
    assert client.branch_protection_on() is True
    assert seen["path"] == "/repos/IznoCorp/demo/branches/main/protection"


def test_close_issue_query_selects_issue_id() -> None:
    """The closeIssue mutation selects ``issue { id }`` (valid on CloseIssuePayload) by node id."""
    from kanbanmate.adapters.github import _queries

    q = _queries.close_issue("NODE_1")
    assert "closeIssue" in q["query"]
    assert "issue { id }" in q["query"]
    assert q["variables"] == {"id": "NODE_1"}
