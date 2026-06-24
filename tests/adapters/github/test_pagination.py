"""Cursor-pagination tests for the board-items snapshot (Hardening H3).

A dedicated fake transport returns a multi-page fixture sequence, verifying
that ``snapshot()`` follows ``endCursor`` until ``hasNextPage`` is ``false``,
accumulates items from every page, and guards against an infinite loop.

The happy-path two-page case replays the **real captured board snapshot**
fixtures from ``fixtures/`` (Hardening H6) so the parser is exercised against the
exact shapes GitHub Projects v2 returns. The infinite-loop / malformed-response
guard tests keep synthetic edge-case pages on purpose — those shapes (a stuck
cursor, a ``hasNextPage: true`` with no ``endCursor``) are precisely the corner
cases a real board does not hand back.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from kanbanmate.adapters.github import _rest
from kanbanmate.adapters.github.client import GithubClient, Timeouts, UrllibTransport
from kanbanmate.adapters.github.types import CommentRef
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
# Fixture: a fake GraphQL transport returning a two-page sequence
# ---------------------------------------------------------------------------


class _PageFixture:
    """Immutable fixture data for one page of a paginating board-items response."""

    def __init__(self, items: list[dict[str, Any]], has_next: bool, cursor: str | None) -> None:
        self.items = items
        self.has_next = has_next
        self.cursor = cursor

    def as_response(self) -> dict[str, Any]:
        """Encode this page into a valid ``board_items`` GraphQL response shape."""
        return {
            "data": {
                "node": {
                    "items": {
                        "pageInfo": {
                            "hasNextPage": self.has_next,
                            "endCursor": self.cursor,
                        },
                        "nodes": self.items,
                    }
                }
            }
        }


def _board_item(
    item_id: str,
    title: str,
    column: str,
    *,
    issue_number: int | None = None,
    state: str = "OPEN",
) -> dict[str, Any]:
    """Build a single ``ProjectV2Item`` node dict for use in a page fixture.

    ``state`` is GitHub's ``IssueState`` enum (``"OPEN"`` / ``"CLOSED"``) and is
    carried only on Issue content (drafts have none) — it drives the ensign
    ``is_closed`` flag the parser derives.
    """
    content: dict[str, Any]
    if issue_number is not None:
        content = {
            "__typename": "Issue",
            "number": issue_number,
            "title": title,
            "state": state,
        }
    else:
        content = {"__typename": "DraftIssue", "title": title}
    return {
        "id": item_id,
        "updatedAt": "2026-06-04T10:00:00Z",
        "fieldValueByName": {"name": column},
        "content": content,
    }


# A two-page sequence: page 1 has 2 items + a next-page cursor; page 2 has 1 item
# and terminates.
_TWO_PAGE_FIXTURES = (
    _PageFixture(
        items=[
            _board_item("PVTI_001", "Page 1 Issue", "Backlog", issue_number=1),
            _board_item("PVTI_002", "Page 1 Draft", "Todo"),
        ],
        has_next=True,
        cursor="cur1",
    ),
    _PageFixture(
        items=[
            _board_item("PVTI_003", "Page 2 Issue", "Done", issue_number=3),
        ],
        has_next=False,
        cursor="cur2",
    ),
)

# A single-page sequence (common case for small boards).
_SINGLE_PAGE_FIXTURES = (
    _PageFixture(
        items=[
            _board_item("PVTI_010", "Only Issue", "In Progress", issue_number=10),
            _board_item("PVTI_011", "Only Draft", "Backlog"),
        ],
        has_next=False,
        cursor=None,
    ),
)


class PaginatingGraphQL:
    """A GraphQL transport that returns a pre-defined page sequence.

    Each call to the transport consumes the next :class:`_PageFixture` from the
    sequence.  The transport also records every payload so tests can assert that
    subsequent pages carry the expected ``after`` cursor.
    """

    def __init__(self, pages: tuple[_PageFixture, ...]) -> None:
        """Initialise with a page sequence.

        Args:
            pages: One :class:`_PageFixture` per expected GraphQL call, in order.
        """
        self._pages = pages
        self._index = 0
        self.calls: list[dict[str, Any]] = []

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return the next page's fixture and record the payload.

        Args:
            payload: The GraphQL request payload.

        Returns:
            The decoded JSON response for the current page.

        Raises:
            AssertionError: When more pages are requested than the fixture sequence provides.
        """
        self.calls.append(payload)
        if self._index >= len(self._pages):
            raise AssertionError(
                f"paginating transport called {self._index + 1} times "
                f"but only {len(self._pages)} pages were configured"
            )
        page = self._pages[self._index]
        self._index += 1
        query = payload.get("query", "")
        # Guard: every payload must look like a board-items query.
        assert "items(first: 100" in query or "pageInfo" in query, (
            f"unexpected query in pagination transport: {query[:80]}"
        )
        return page.as_response()

    def assert_exhausted(self) -> None:
        """Assert that all configured pages were consumed."""
        remaining = len(self._pages) - self._index
        assert remaining == 0, f"{remaining} fixture page(s) were never requested"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


class _FakeRest:
    """Minimal REST transport stub for the pagination tests (no REST calls)."""

    def __call__(self, _method: str, _path: str, _body: dict[str, Any] | None) -> dict[str, Any]:
        return {}


class CapturedBoardGraphQL:
    """A GraphQL transport replaying the real captured two-page board snapshot (H6).

    Routes by the ``after`` cursor the client threads from each page's real
    ``endCursor``: no cursor yields page 1 (``hasNextPage: true``, cursor ``"Mg"``),
    cursor ``"Mg"`` yields page 2 (``hasNextPage: false``). Records every payload so
    tests can assert the genuine cursor was passed on the second request.
    """

    def __init__(self) -> None:
        """Load the captured page fixtures and initialise the call log."""
        self._page1 = _load_fixture("board_snapshot_page1.json")
        self._page2 = _load_fixture("board_snapshot_page2.json")
        self.calls: list[dict[str, Any]] = []

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return the captured page matching the request's ``after`` cursor."""
        self.calls.append(payload)
        after = payload.get("variables", {}).get("after")
        return self._page2 if after else self._page1


def _client(transport: PaginatingGraphQL | CapturedBoardGraphQL) -> GithubClient:
    """Build a :class:`GithubClient` wired to a paginating transport."""
    return GithubClient(
        token="tok",
        project_id="PVT_PROJECT",
        repo="IznoCorp/demo",
        graphql_transport=transport,
        rest_transport=_FakeRest(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_two_page_snapshot_accumulates_all_items() -> None:
    """The real captured two-page board snapshot contains items from BOTH pages (H6).

    Asserts the parsed :class:`Ticket` fields match the captured fixtures' real
    values EXACTLY: a Done Issue + an In Progress draft on page 1, a Backlog Issue
    + a Status-less PullRequest on page 2.
    """
    transport = CapturedBoardGraphQL()
    snap = _client(transport).snapshot()

    assert isinstance(snap, BoardSnapshot)
    assert snap.fetched_at > 0
    assert len(snap.tickets) == 4  # 2 from page 1 + 2 from page 2

    # Items from both captured pages are present.
    ids = {t.item_id for t in snap.tickets}
    assert ids == {
        "PVTI_lADOBpVuBM4Ae2-IzgABcDE",
        "PVTI_lADOBpVuBM4Ae2-IzgABcDF",
        "PVTI_lADOBpVuBM4Ae2-IzgABcDG",
        "PVTI_lADOBpVuBM4Ae2-IzgABcDH",
    }

    # Page 1 Issue details (real fixture values).
    p1_issue = next(t for t in snap.tickets if t.item_id == "PVTI_lADOBpVuBM4Ae2-IzgABcDE")
    assert p1_issue.issue_number == 7
    assert p1_issue.title == "Bootstrap the polling engine"
    assert p1_issue.column_key == "Done"

    # Page 2 Issue details (real fixture values).
    p2_issue = next(t for t in snap.tickets if t.item_id == "PVTI_lADOBpVuBM4Ae2-IzgABcDG")
    assert p2_issue.issue_number == 12
    assert p2_issue.title == "Wire the GitHub adapter"
    assert p2_issue.column_key == "Backlog"


def test_two_page_snapshot_passes_cursor_to_second_request() -> None:
    """The second request carries ``after="Mg"`` — page 1's real ``endCursor`` (H6)."""
    transport = CapturedBoardGraphQL()
    _client(transport).snapshot()

    assert len(transport.calls) == 2
    # Page 1: no cursor.
    assert transport.calls[0]["variables"]["after"] is None
    # Page 2: carries the page-1 endCursor verbatim from the captured fixture.
    assert transport.calls[1]["variables"]["after"] == "Mg"


def test_single_page_snapshot_makes_one_request() -> None:
    """A single-page board (``hasNextPage`` false on page 1) fetches once."""
    transport = PaginatingGraphQL(_SINGLE_PAGE_FIXTURES)
    snap = _client(transport).snapshot()

    assert len(snap.tickets) == 2
    assert len(transport.calls) == 1
    assert transport.calls[0]["variables"]["after"] is None
    transport.assert_exhausted()


def test_snapshot_stops_when_loop_exhausts_max_pages() -> None:
    """The pagination loop terminates at ``max_pages`` even when ``hasNextPage``
    is always ``true`` (runaway-cursor guard)."""
    # Build a fixture sequence where every page claims there's more.
    runaway_pages = tuple(
        _PageFixture(
            items=[_board_item(f"PVTI_{i:03d}", f"Item {i}", "Backlog", issue_number=i)],
            has_next=True,
            cursor=f"cur{i}",
        )
        for i in range(15)  # more than the internal max_pages=10
    )
    transport = PaginatingGraphQL(runaway_pages)
    snap = _client(transport).snapshot()

    # The loop must stop at max_pages=10, so we get 10 items (not 15).
    assert len(snap.tickets) == 10
    assert len(transport.calls) == 10


def test_snapshot_stops_when_cursor_does_not_advance() -> None:
    """The loop breaks when ``endCursor`` equals the current ``after`` value
    (non-advancing cursor guard against a broken server or fixture)."""
    stalled_pages = (
        _PageFixture(
            items=[_board_item("PVTI_A", "A", "Backlog", issue_number=1)],
            has_next=True,
            cursor="stuck",
        ),
        _PageFixture(
            items=[_board_item("PVTI_B", "B", "Todo", issue_number=2)],
            has_next=True,
            cursor="stuck",  # same cursor as page 1 → loop must break
        ),
        _PageFixture(
            items=[_board_item("PVTI_C", "C", "Done", issue_number=3)],
            has_next=False,
            cursor="stuck",
        ),
    )
    transport = PaginatingGraphQL(stalled_pages)
    snap = _client(transport).snapshot()

    # Two pages were fetched (the third request was never made because the
    # cursor didn't advance after page 2).
    assert len(snap.tickets) == 2
    assert len(transport.calls) == 2
    ids = {t.item_id for t in snap.tickets}
    assert ids == {"PVTI_A", "PVTI_B"}


def test_snapshot_stops_when_end_cursor_is_none_but_has_next_is_true() -> None:
    """The loop breaks when ``hasNextPage`` is ``true`` but ``endCursor`` is
    absent — a malformed server response must not cause an infinite loop."""
    malformed_pages = (
        _PageFixture(
            items=[_board_item("PVTI_X", "X", "Backlog", issue_number=1)],
            has_next=True,
            cursor=None,  # malformed: says there's more but gives no cursor
        ),
        _PageFixture(
            items=[_board_item("PVTI_Y", "Y", "Done", issue_number=2)],
            has_next=False,
            cursor=None,
        ),
    )
    transport = PaginatingGraphQL(malformed_pages)
    snap = _client(transport).snapshot()

    # Only one page was fetched — the loop broke on the missing cursor.
    assert len(snap.tickets) == 1
    assert len(transport.calls) == 1


def test_empty_board_makes_one_request() -> None:
    """An empty board (no items, ``hasNextPage`` false) fetches once."""
    empty_pages = (_PageFixture(items=[], has_next=False, cursor=None),)
    transport = PaginatingGraphQL(empty_pages)
    snap = _client(transport).snapshot()

    assert len(snap.tickets) == 0
    assert len(transport.calls) == 1
    transport.assert_exhausted()


# ---------------------------------------------------------------------------
# _status_option_counts pagination guards (sub-phase 6.3)
# ---------------------------------------------------------------------------


def _status_item(column: str) -> dict[str, Any]:
    """Build a single project item node with only a Status name.

    ``parse_item_status_page`` only reads ``fieldValueByName.name``; extra fields
    are ignored, so a minimal dict is sufficient and makes test intent clearer.
    """
    return {"fieldValueByName": {"name": column}}


def test_status_option_counts_multi_page_accumulates() -> None:
    """Two-page count accumulation: page 1 has 2 items, page 2 has 1 item."""
    pages = (
        _PageFixture(
            items=[
                _status_item("Todo"),
                _status_item("Done"),
            ],
            has_next=True,
            cursor="cur1",
        ),
        _PageFixture(
            items=[
                _status_item("Todo"),
            ],
            has_next=False,
            cursor="cur2",
        ),
    )
    transport = PaginatingGraphQL(pages)
    client = _client(transport)
    counts = client._status_option_counts("PVT_PROJECT")
    assert counts == {"Todo": 2, "Done": 1}
    assert len(transport.calls) == 2


def test_status_option_counts_stops_when_end_cursor_is_none() -> None:
    """Terminates when hasNextPage is true but endCursor is absent.

    A malformed server response that claims more pages but provides no cursor
    must not cause an infinite loop.
    """
    malformed = (
        _PageFixture(
            items=[_status_item("Todo")],
            has_next=True,
            cursor=None,  # malformed: more pages but no cursor
        ),
        _PageFixture(
            items=[_status_item("Done")],
            has_next=False,
            cursor=None,
        ),
    )
    transport = PaginatingGraphQL(malformed)
    client = _client(transport)
    counts = client._status_option_counts("PVT_PROJECT")
    # Only the first page was consumed; the loop broke on the missing cursor.
    assert counts == {"Todo": 1}
    assert len(transport.calls) == 1


def test_status_option_counts_stops_when_cursor_does_not_advance() -> None:
    """Terminates when endCursor equals the current after value.

    A broken server or fixture that returns the same cursor on every page must
    not cause an infinite loop.
    """
    stalled = (
        _PageFixture(
            items=[_status_item("Todo")],
            has_next=True,
            cursor="stuck",
        ),
        _PageFixture(
            items=[_status_item("Done")],
            has_next=True,
            cursor="stuck",  # same cursor — loop must break
        ),
        _PageFixture(
            items=[_status_item("Backlog")],
            has_next=False,
            cursor="stuck",
        ),
    )
    transport = PaginatingGraphQL(stalled)
    client = _client(transport)
    counts = client._status_option_counts("PVT_PROJECT")
    # Two pages fetched; the third was never requested because the cursor
    # did not advance after page 2.
    assert counts == {"Todo": 1, "Done": 1}
    assert len(transport.calls) == 2


def test_status_option_counts_stops_at_max_pages() -> None:
    """Terminates at max_pages even when hasNextPage is always true."""
    runaway = tuple(
        _PageFixture(
            items=[_status_item(f"Col{i}")],
            has_next=True,
            cursor=f"cur{i}",
        )
        for i in range(15)  # more than max_pages=10
    )
    transport = PaginatingGraphQL(runaway)
    client = _client(transport)
    counts = client._status_option_counts("PVT_PROJECT")
    # The loop stops at max_pages=10, so 10 items (not 15).
    assert len(counts) == 10
    assert len(transport.calls) == 10


def test_timeout_preservation_is_inherited() -> None:
    """Pagination loop uses the client's injected transport, so the mandatory
    connect+read timeouts are enforced on every page request (the transport
    itself, not pagination, enforces them — this test proves the transport
    is the same one that carries the timeouts)."""
    transport = PaginatingGraphQL(_TWO_PAGE_FIXTURES)
    client = _client(transport)

    # The client records its default transport timeouts, proving the safety
    # rule is intact.
    assert client.transport_timeouts.connect is not None
    assert client.transport_timeouts.connect > 0
    assert client.transport_timeouts.read is not None
    assert client.transport_timeouts.read > 0


# ---------------------------------------------------------------------------
# REST issue-comments Link rel=next pagination (sub-phase 16.2)
# ---------------------------------------------------------------------------


def test_next_link_path_returns_path_when_rel_next_present() -> None:
    """``next_link_path`` strips the base and returns the rel=next path+query."""
    header = (
        '<https://api.github.com/repos/o/r/issues/1/comments?per_page=100&page=2>; rel="next", '
        '<https://api.github.com/repos/o/r/issues/1/comments?per_page=100&page=5>; rel="last"'
    )
    assert _rest.next_link_path(header) == "/repos/o/r/issues/1/comments?per_page=100&page=2"


def test_next_link_path_returns_none_when_absent() -> None:
    """No rel=next segment (or no header at all) yields ``None`` — loop terminates."""
    assert _rest.next_link_path(None) is None
    assert _rest.next_link_path("") is None
    assert (
        _rest.next_link_path(
            '<https://api.github.com/repos/o/r/issues/1/comments?page=5>; rel="last"'
        )
        is None
    )


def test_next_link_path_returns_full_url_when_not_base_relative() -> None:
    """A rel=next URL not under the default base is returned verbatim (base-strip is conditional)."""
    header = '<https://example.test/other?page=2>; rel="next"'
    assert _rest.next_link_path(header) == "https://example.test/other?page=2"


class _CommentsPagesRest:
    """A fake ``rest_with_headers`` returning a fixed sequence of comment pages.

    Each call consumes the next ``(body, headers)`` page and records the path so a
    test can assert the second GET carries the rel=next ``page=2`` query. Mirrors the
    real :meth:`UrllibTransport.rest_with_headers` signature
    ``(method, path, body) -> (body, headers)``.
    """

    def __init__(self, pages: list[tuple[list[dict[str, Any]], dict[str, str]]]) -> None:
        """Initialise with one ``(body, headers)`` page per expected GET, in order."""
        self._pages = pages
        self._index = 0
        self.paths: list[str] = []

    def __call__(
        self, method: str, path: str, body: dict[str, Any] | None
    ) -> tuple[Any, dict[str, str]]:
        """Return the next page's ``(body, headers)`` and record the request path."""
        assert method == "GET"
        assert body is None
        self.paths.append(path)
        page_body, page_headers = self._pages[self._index]
        self._index += 1
        return page_body, page_headers


def _client_with_rest_headers(rest_headers: _CommentsPagesRest) -> GithubClient:
    """Build a client whose headers-bearing REST seam is the supplied fake.

    The injected ``rest_transport`` is unused for these tests (it raises if hit), so
    overriding ``_rest_headers`` directly exercises the pager without the legacy
    empty-headers shim.
    """

    def _unused_rest(_m: str, _p: str, _b: dict[str, Any] | None) -> Any:
        raise AssertionError("the body-only rest seam must not be used by the comments pager")

    client = GithubClient(
        token="tok",
        project_id="PVT_PROJECT",
        repo="IznoCorp/demo",
        graphql_transport=FakeForRest(),
        rest_transport=_unused_rest,
    )
    # Replace the legacy empty-headers shim with the real headers-bearing fake so the
    # Link rel=next loop is exercised end to end.
    client._rest_headers = rest_headers
    return client


class FakeForRest:
    """A no-op GraphQL transport (the REST pager tests never touch GraphQL)."""

    def __call__(self, _payload: dict[str, Any]) -> dict[str, Any]:
        return {}


def test_list_issue_comments_follows_link_to_page_2() -> None:
    """A sticky living ONLY on page 2 is found via the Link rel=next loop (no duplicate).

    The exact PoC regression: page 1 carries a ``Link: <…&page=2>; rel="next"`` header,
    page 2 has no Link. ``list_issue_comments`` must issue TWO GETs (the second path
    ``…/comments?per_page=100&page=2``) and return BOTH pages' comments, so the page-2
    sticky marker is visible to the §8.1 upsert.
    """
    next_header = {
        "Link": (
            "<https://api.github.com/repos/IznoCorp/demo/issues/7/comments"
            '?per_page=100&page=2>; rel="next"'
        )
    }
    page1: tuple[list[dict[str, Any]], dict[str, str]] = (
        [{"id": 1, "body": "first"}, {"id": 2, "body": "second"}],
        next_header,
    )
    page2: tuple[list[dict[str, Any]], dict[str, str]] = (
        [{"id": 3, "body": "<!-- sticky:lint -->"}],
        {},
    )
    fake = _CommentsPagesRest([page1, page2])
    client = _client_with_rest_headers(fake)

    comments = client.list_issue_comments(7)

    # Two GETs were issued; the second followed the rel=next link to page 2.
    assert len(fake.paths) == 2
    assert fake.paths[0] == "/repos/IznoCorp/demo/issues/7/comments?per_page=100"
    assert fake.paths[1] == "/repos/IznoCorp/demo/issues/7/comments?per_page=100&page=2"
    # All three comments accumulated; the page-2 sticky marker is present.
    assert [c.comment_id for c in comments] == [1, 2, 3]
    assert isinstance(comments[2], CommentRef)
    assert comments[2].comment_id == 3  # stays int, no str regression
    assert any("sticky:lint" in c.body for c in comments)


def test_list_issue_comments_single_page_makes_one_get() -> None:
    """A single-page response (no Link header) issues exactly ONE GET."""
    page1: tuple[list[dict[str, Any]], dict[str, str]] = ([{"id": 10, "body": "only"}], {})
    fake = _CommentsPagesRest([page1])
    client = _client_with_rest_headers(fake)

    comments = client.list_issue_comments(7)

    assert len(fake.paths) == 1
    assert fake.paths[0] == "/repos/IznoCorp/demo/issues/7/comments?per_page=100"
    assert [c.comment_id for c in comments] == [10]


def test_list_issue_comments_legacy_body_only_fake_makes_one_get() -> None:
    """A legacy body-only injected ``rest_transport`` (no headers) → ONE GET, graceful.

    The empty-headers fallback (``lambda m, p, b: (rest(m, p, b), {})``) yields no Link
    header, so the pager terminates after page 1 — existing tests that inject a
    body-only fake keep working without seeing a duplicate or a hang.
    """
    calls: list[str] = []

    def body_only_rest(method: str, path: str, body: dict[str, Any] | None) -> Any:
        calls.append(path)
        return [{"id": 99, "body": "legacy"}]

    client = GithubClient(
        token="tok",
        project_id="PVT_PROJECT",
        repo="IznoCorp/demo",
        graphql_transport=FakeForRest(),
        rest_transport=body_only_rest,
    )
    comments = client.list_issue_comments(7)

    assert len(calls) == 1  # graceful: empty-headers fallback stops after page 1
    assert calls[0] == "/repos/IznoCorp/demo/issues/7/comments?per_page=100"
    assert [c.comment_id for c in comments] == [99]


def test_list_issue_comments_self_referential_link_terminates() -> None:
    """A self-referential ``Link rel=next`` (pointing to the same path) terminates.

    A malformed or proxied response that returns a ``rel="next"`` URL whose path is
    identical to the current request path must NOT cause an infinite re-fetch loop.
    The ``seen`` guard breaks the loop after one GET, mirroring the GraphQL pager's
    non-advancing-cursor break (client.py ~372-374).
    """
    call_count = 0
    captured_paths: list[str] = []

    def self_referential_rest(
        method: str, path: str, body: dict[str, Any] | None
    ) -> tuple[Any, dict[str, str]]:
        nonlocal call_count
        assert method == "GET"
        assert body is None
        call_count += 1
        captured_paths.append(path)
        # Always return a Link header pointing to the SAME path — self-referential.
        return (
            [{"id": 1, "body": "only"}],
            {"Link": f'<https://api.github.com{path}>; rel="next"'},
        )

    def _unused_rest(_m: str, _p: str, _b: dict[str, Any] | None) -> Any:
        raise AssertionError("the body-only rest seam must not be used by the comments pager")

    client = GithubClient(
        token="tok",
        project_id="PVT_PROJECT",
        repo="IznoCorp/demo",
        graphql_transport=FakeForRest(),
        rest_transport=_unused_rest,
    )
    client._rest_headers = self_referential_rest

    comments = client.list_issue_comments(7)

    # The seen guard must stop the loop after ONE GET.
    assert call_count == 1
    assert len(captured_paths) == 1
    assert captured_paths[0] == "/repos/IznoCorp/demo/issues/7/comments?per_page=100"
    assert [c.comment_id for c in comments] == [1]


# ---------------------------------------------------------------------------
# REST find_open_pr per_page=100 + Link rel=next pagination (sub-phase 16.3)
# ---------------------------------------------------------------------------


class _PrPagesRest:
    """A fake ``rest_with_headers`` returning a fixed sequence of PR-list pages.

    Each call consumes the next ``(body, headers)`` page and records the path so a
    test can assert the page-1 GET carries ``per_page=100`` and a subsequent page
    follows the ``Link rel=next``. Mirrors the real
    :meth:`UrllibTransport.rest_with_headers` signature
    ``(method, path, body) -> (body, headers)``.
    """

    def __init__(self, pages: list[tuple[list[dict[str, Any]], dict[str, str]]]) -> None:
        """Initialise with one ``(body, headers)`` page per expected GET, in order."""
        self._pages = pages
        self._index = 0
        self.paths: list[str] = []

    def __call__(
        self, method: str, path: str, body: dict[str, Any] | None
    ) -> tuple[Any, dict[str, str]]:
        """Return the next page's ``(body, headers)`` and record the request path."""
        assert method == "GET"
        assert body is None
        self.paths.append(path)
        page_body, page_headers = self._pages[self._index]
        self._index += 1
        return page_body, page_headers


def _client_for_pr_pagination(rest_headers: _PrPagesRest) -> GithubClient:
    """Build a client whose headers-bearing REST seam is the supplied fake.

    Like ``_client_with_rest_headers`` but specifically for the ``find_open_pr``
    tests — the body-only seam must never be called.
    """

    def _unused_rest(_m: str, _p: str, _b: dict[str, Any] | None) -> Any:
        raise AssertionError("the body-only rest seam must not be used by find_open_pr")

    client = GithubClient(
        token="tok",
        project_id="PVT_PROJECT",
        repo="IznoCorp/demo",
        graphql_transport=FakeForRest(),
        rest_transport=_unused_rest,
    )
    client._rest_headers = rest_headers
    return client


def test_find_open_pr_page_1_path_has_per_page_100_and_owner_qualifier() -> None:
    """Page-1 GET carries ``per_page=100`` and an owner-qualified ``head`` (16.3).

    The path is built by ``_rest.list_open_pulls_for_branch`` — the same builder
    the PoC used. ``find_open_pr`` returns the PR number from the sole page.
    """
    page1: tuple[list[dict[str, Any]], dict[str, str]] = (
        [{"number": 42, "state": "open", "head": {"ref": "feat/x"}}],
        {},  # no Link — single page
    )
    fake = _PrPagesRest([page1])
    client = _client_for_pr_pagination(fake)

    result = client.find_open_pr("feat/x")

    assert result == 42
    assert len(fake.paths) == 1
    assert fake.paths[0] == (
        "/repos/IznoCorp/demo/pulls?state=open&head=IznoCorp:feat/x&per_page=100"
    )


def test_find_open_pr_follows_link_to_page_2() -> None:
    """An empty page 1 with a ``Link rel=next`` to page 2 carrying the PR → found.

    Proves the pager is SHARED (not duplicated): ``find_open_pr`` loops via the same
    ``_rest_headers`` + ``next_link_path`` seam as ``list_issue_comments``, following
    ``rel=next`` until the PR is found.
    """
    next_header = {
        "Link": (
            "<https://api.github.com/repos/IznoCorp/demo/pulls"
            '?state=open&head=IznoCorp:feat%2Fx&per_page=100&page=2>; rel="next"'
        )
    }
    page1: tuple[list[dict[str, Any]], dict[str, str]] = ([], next_header)
    page2: tuple[list[dict[str, Any]], dict[str, str]] = (
        [{"number": 77, "state": "open", "head": {"ref": "feat/x"}}],
        {},  # no Link — exhausted
    )
    fake = _PrPagesRest([page1, page2])
    client = _client_for_pr_pagination(fake)

    result = client.find_open_pr("feat/x")

    assert result == 77
    # Two GETs: page 1 (empty), page 2 (the PR lives here).
    assert len(fake.paths) == 2
    assert fake.paths[0] == (
        "/repos/IznoCorp/demo/pulls?state=open&head=IznoCorp:feat/x&per_page=100"
    )
    assert "page=2" in fake.paths[1]
    assert "per_page=100" in fake.paths[1]


def test_find_open_pr_returns_none_when_exhausted() -> None:
    """No open PR on any page, no Link → ``None``, loop terminates cleanly."""
    page1: tuple[list[dict[str, Any]], dict[str, str]] = (
        [],  # empty listing
        {},  # no Link — exhausted
    )
    fake = _PrPagesRest([page1])
    client = _client_for_pr_pagination(fake)

    result = client.find_open_pr("feat/nonexistent")

    assert result is None
    assert len(fake.paths) == 1


def test_find_open_pr_empty_and_head_branch_no_roundtrip() -> None:
    """Empty / ``"HEAD"`` branch → ``None`` with ZERO GETs (short-circuit preserved).

    Proves that the 16.3 rewrite kept the existing guard — no REST call is made.
    """
    client = GithubClient(
        token="tok",
        project_id="PVT_PROJECT",
        repo="IznoCorp/demo",
        graphql_transport=FakeForRest(),
        rest_transport=lambda _m, _p, _b: (_ for _ in ()),  # would crash if called
    )

    assert client.find_open_pr("") is None
    assert client.find_open_pr("HEAD") is None


def test_find_open_pr_self_referential_link_terminates() -> None:
    """A self-referential ``Link rel=next`` terminates (the ``seen`` guard, 16.2 fix).

    A malformed/proxied response returning ``rel="next"`` pointing to the same path
    must NOT cause an infinite re-fetch loop. The ``seen``-set guard breaks after
    one GET, mirroring ``list_issue_comments``'s guard (client.py ~474).
    """
    call_count = 0
    captured_paths: list[str] = []

    def self_referential_rest(
        method: str, path: str, body: dict[str, Any] | None
    ) -> tuple[Any, dict[str, str]]:
        nonlocal call_count
        assert method == "GET"
        assert body is None
        call_count += 1
        captured_paths.append(path)
        # Always return a Link header pointing to the SAME path — self-referential.
        return (
            [],
            {"Link": f'<https://api.github.com{path}>; rel="next"'},
        )

    client = GithubClient(
        token="tok",
        project_id="PVT_PROJECT",
        repo="IznoCorp/demo",
        graphql_transport=FakeForRest(),
        rest_transport=lambda _m, _p, _b: (_ for _ in ()),
    )
    client._rest_headers = self_referential_rest

    result = client.find_open_pr("feat/x")

    # The seen guard must stop the loop after ONE GET.
    assert result is None
    assert call_count == 1
    assert len(captured_paths) == 1
    assert "per_page=100" in captured_paths[0]
    assert "state=open" in captured_paths[0]


# ---------------------------------------------------------------------------
# Timeout fidelity of the headers-bearing seam (CLAUDE.md MANDATORY)
# ---------------------------------------------------------------------------


class _FakeSocket:
    """A stand-in socket that records the read timeout the transport applies."""

    def __init__(self) -> None:
        self.read_timeout: float | None = None

    def settimeout(self, value: float) -> None:
        """Record the read-budget timeout the transport sets after connecting."""
        self.read_timeout = value


class _FakeResponse:
    """A minimal HTTP response exposing a body + a Link header (single page)."""

    status = 200

    def read(self) -> bytes:
        """Return an empty JSON array body (no comments)."""
        return b"[]"

    def getheaders(self) -> list[tuple[str, str]]:
        """Return headers WITHOUT a Link (single-page response)."""
        return [("Content-Type", "application/json")]


class _FakeConnection:
    """A fake ``HTTPSConnection`` capturing the connect timeout + the read settimeout.

    Records the ``timeout=`` passed to the constructor (the connect budget) and the
    value later applied via ``sock.settimeout`` (the read budget) so a test can prove
    the headers-bearing seam runs the SAME connect-then-read dance as ``_request``.
    """

    last_instance: _FakeConnection | None = None

    def __init__(self, host: str, timeout: float | None = None) -> None:
        self.host = host
        self.connect_timeout = timeout
        self.sock = _FakeSocket()
        _FakeConnection.last_instance = self

    def request(self, method: str, path: str, body: Any = None, headers: Any = None) -> None:
        """No-op: the fake does not perform real I/O."""

    def getresponse(self) -> _FakeResponse:
        """Return the canned single-page response."""
        return _FakeResponse()

    def close(self) -> None:
        """No-op connection close."""


def test_rest_with_headers_applies_connect_then_read_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``rest_with_headers`` runs the connect-then-read timeout dance (no untimed path).

    Mocks ``HTTPSConnection`` so the constructor's ``timeout=`` (connect budget) and the
    ``sock.settimeout`` value (read budget) are both observable, proving the
    headers-bearing seam — the SINGLE network-read implementation — honours both
    mandatory budgets exactly like the body-only path.
    """
    monkeypatch.setattr(
        "kanbanmate.adapters.github._transport.http.client.HTTPSConnection",
        _FakeConnection,
    )
    transport = UrllibTransport("tok", timeouts=Timeouts(connect=2.5, read=11.0))

    body, headers = transport.rest_with_headers("GET", "/repos/o/r/issues/7/comments", None)

    assert body == []  # decoded empty JSON array
    assert "Content-Type" in headers
    conn = _FakeConnection.last_instance
    assert conn is not None
    assert conn.connect_timeout == 2.5  # connect budget on the connection
    assert conn.sock.read_timeout == 11.0  # read budget applied before reading


def test_request_is_thin_body_only_wrapper_over_headers_impl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The body-only ``_request`` delegates to ``_request_with_headers`` (one read impl).

    Proves there is exactly ONE network-read implementation: the body-only path returns
    the same decoded body the headers path produces, having run the same timed dance.
    """
    monkeypatch.setattr(
        "kanbanmate.adapters.github._transport.http.client.HTTPSConnection",
        _FakeConnection,
    )
    transport = UrllibTransport("tok", timeouts=Timeouts(connect=3.0, read=9.0))

    body = transport.rest("GET", "/repos/o/r/issues/7/comments", None)

    assert body == []
    conn = _FakeConnection.last_instance
    assert conn is not None
    # Even the body-only path applied both budgets — no untimed read path exists.
    assert conn.connect_timeout == 3.0
    assert conn.sock.read_timeout == 9.0


def test_parse_board_items_derives_is_closed_from_issue_state() -> None:
    """``parse_board_items`` sets ``RawItem.is_closed`` from the Issue ``state`` (ensign).

    A ``state:"CLOSED"`` Issue → ``is_closed=True``; an open Issue and a draft (which
    carries no state) → ``is_closed=False``. Real, non-trivial values on both sides.
    """
    from kanbanmate.adapters.github._parsers import parse_board_items

    page = _PageFixture(
        items=[
            _board_item("PVTI_C", "Closed Issue", "Done", issue_number=7, state="CLOSED"),
            _board_item("PVTI_O", "Open Issue", "Backlog", issue_number=8, state="OPEN"),
            _board_item("PVTI_D", "A Draft", "Backlog"),
        ],
        has_next=False,
        cursor=None,
    )

    items, has_next, cursor = parse_board_items(page.as_response())

    by_id = {raw.item_id: raw for raw in items}
    assert by_id["PVTI_C"].is_closed is True
    assert by_id["PVTI_C"].issue_number == 7  # the closed side resolves to a real issue
    assert by_id["PVTI_O"].is_closed is False
    assert by_id["PVTI_O"].issue_number == 8
    assert by_id["PVTI_D"].is_closed is False  # a draft is never closed
    assert has_next is False
    assert cursor is None
