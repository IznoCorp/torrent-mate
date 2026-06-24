"""Tests for /api/board/* routes (anchor §12.7)."""

from __future__ import annotations

import pathlib
from collections.abc import Callable, Generator
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from kanbanmate.adapters.store.fs_board import FsBoardStateStore, seed_board
from kanbanmate.http.config_api import app

COLUMNS = ["Backlog", "InProgress", "Done"]

_FAKE_ENTRY = MagicMock()
_FAKE_ENTRY.board_backend = "native"
_FAKE_ENTRY.project_id = "pid"
_FAKE_ENTRY.repo = "o/r"
_FAKE_ENTRY.clone = "/tmp/clone"
_FAKE_ENTRY.enabled = True


@pytest.fixture()
def seeded_store(tmp_path: pathlib.Path) -> FsBoardStateStore:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=COLUMNS,
        placement={"item1": "Backlog", "item2": "InProgress"},
        order={"Backlog": ["item1"], "InProgress": ["item2"], "Done": []},
    )
    return s


@pytest.fixture()
def client(
    tmp_path: pathlib.Path, seeded_store: FsBoardStateStore
) -> Generator[TestClient, None, None]:
    """TestClient with patched entry resolution and store injection."""
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=_FAKE_ENTRY),
        patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store),
        patch("kanbanmate.http.board_routes._nudge"),
    ):
        yield TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/board/state
# ---------------------------------------------------------------------------


def test_board_state_returns_version_and_cards(client: TestClient) -> None:
    resp = client.get("/api/board/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 1
    assert "Backlog" in data["columns"]
    cards_by_id = {c["item_id"]: c for c in data["cards"]}
    assert "item1" in cards_by_id
    assert cards_by_id["item1"]["column_key"] == "Backlog"
    assert cards_by_id["item1"]["index"] == 0


def test_board_state_joins_issue_identity(
    seeded_store: FsBoardStateStore,
) -> None:
    """GET /state JOINs the forge issue set → cards carry issue_number + title (DESIGN §10)."""
    from kanbanmate.core.domain import BoardSnapshot, Ticket

    fake_forge = MagicMock()
    fake_forge.snapshot.return_value = BoardSnapshot(
        tickets=(
            Ticket(
                item_id="item1",
                issue_number=42,
                title="First",
                column_key="Backlog",
                body="",
                is_closed=True,
            ),
            Ticket(
                item_id="item2", issue_number=43, title="Second", column_key="InProgress", body=""
            ),
        ),
        fetched_at=0.0,
    )
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=_FAKE_ENTRY),
        patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store),
        patch("kanbanmate.http.board_routes._get_forge", return_value=fake_forge),
    ):
        with TestClient(app) as c:
            resp = c.get("/api/board/state")
    assert resp.status_code == 200
    body = resp.json()
    cards_by_id = {card["item_id"]: card for card in body["cards"]}
    assert cards_by_id["item1"]["issue_number"] == 42
    assert cards_by_id["item1"]["title"] == "First"
    assert cards_by_id["item2"]["issue_number"] == 43
    # ensign: the closed-issue flag rides the same forge JOIN onto each card.
    assert cards_by_id["item1"]["is_closed"] is True
    assert cards_by_id["item2"]["is_closed"] is False
    assert body["identity_degraded"] is False, (
        "identity is NOT degraded when the forge JOIN succeeds"
    )


def test_board_state_forge_failure_is_failsoft(seeded_store: FsBoardStateStore) -> None:
    """A forge outage must not break the local board read — placement served, identity null (§10)."""
    failing_forge = MagicMock()
    failing_forge.snapshot.side_effect = RuntimeError("GitHub down")
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=_FAKE_ENTRY),
        patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store),
        patch("kanbanmate.http.board_routes._get_forge", return_value=failing_forge),
    ):
        with TestClient(app) as c:
            resp = c.get("/api/board/state")
    assert resp.status_code == 200, "forge failure must not 5xx a local read"
    body = resp.json()
    cards_by_id = {card["item_id"]: card for card in body["cards"]}
    assert cards_by_id["item1"]["column_key"] == "Backlog"
    assert cards_by_id["item1"]["issue_number"] is None, "identity is null when the forge is down"
    assert cards_by_id["item1"]["is_closed"] is False, "is_closed defaults False when forge is down"
    assert body["identity_degraded"] is True, (
        "the response must flag degraded identity so the SPA distinguishes 'GitHub down' from "
        "'card has no identity'"
    )


def test_board_state_409_when_not_native() -> None:
    entry = MagicMock()
    entry.board_backend = "github"
    with patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry):
        with TestClient(app) as c:
            resp = c.get("/api/board/state")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/board/move
# ---------------------------------------------------------------------------


def test_board_move_happy_path(client: TestClient, seeded_store: FsBoardStateStore) -> None:
    resp = client.post("/api/board/move", json={"item_id": "item1", "to_column": "Done"})
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    doc = seeded_store.load()
    assert doc["placement"]["item1"] == "Done"


def test_board_move_bad_column_returns_400(client: TestClient) -> None:
    resp = client.post("/api/board/move", json={"item_id": "item1", "to_column": "NoSuchCol"})
    assert resp.status_code == 400


def test_board_move_stale_version_returns_409(client: TestClient) -> None:
    resp = client.post(
        "/api/board/move", json={"item_id": "item1", "to_column": "Done", "if_version": 99}
    )
    assert resp.status_code == 409


def test_board_move_empty_item_id_returns_400(client: TestClient) -> None:
    """A missing/empty item_id is rejected fail-loud (never injects a phantom '' card)."""
    resp = client.post("/api/board/move", json={"to_column": "Done"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/board/reorder
# ---------------------------------------------------------------------------


def test_board_reorder_happy_path(client: TestClient, seeded_store: FsBoardStateStore) -> None:
    # Seed two items in Backlog.
    seeded_store.place_card("item2", "Backlog")  # move item2 to Backlog
    resp = client.post(
        "/api/board/reorder",
        json={
            "column_key": "Backlog",
            "ordered_item_ids": ["item2", "item1"],
        },
    )
    assert resp.status_code == 200
    doc = seeded_store.load()
    assert doc["order"]["Backlog"] == ["item2", "item1"]


def test_board_reorder_bad_column_returns_400(client: TestClient) -> None:
    resp = client.post(
        "/api/board/reorder", json={"column_key": "NoSuchCol", "ordered_item_ids": []}
    )
    assert resp.status_code == 400


def test_board_reorder_duplicate_items_returns_400(
    client: TestClient, seeded_store: FsBoardStateStore
) -> None:
    resp = client.post(
        "/api/board/reorder",
        json={
            "column_key": "Backlog",
            "ordered_item_ids": ["item1", "item1"],
        },
    )
    assert resp.status_code == 400


def test_board_reorder_non_list_ordered_item_ids_returns_400(client: TestClient) -> None:
    # A non-list ordered_item_ids (e.g. a bare string) must be rejected as a 400 BEFORE the store —
    # otherwise it would iterate its characters into the set/len logic and surface a misleading
    # "duplicate item ids" 400 (or corrupt the order).
    resp = client.post(
        "/api/board/reorder",
        json={"column_key": "Backlog", "ordered_item_ids": "item1"},
    )
    assert resp.status_code == 400
    assert "list of item id strings" in resp.json()["detail"]


def test_board_reorder_stale_version_returns_409(client: TestClient) -> None:
    """Reorder honours optimistic concurrency identically to move (typed VersionConflict → 409)."""
    resp = client.post(
        "/api/board/reorder",
        json={"column_key": "Backlog", "ordered_item_ids": ["item1"], "if_version": 99},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/board/place
# ---------------------------------------------------------------------------


def test_board_place_at_index(client: TestClient, seeded_store: FsBoardStateStore) -> None:
    # Move item2 to Backlog first so we can reorder.
    seeded_store.place_card("item2", "Backlog")
    resp = client.post(
        "/api/board/place", json={"item_id": "item2", "column_key": "Backlog", "index": 0}
    )
    assert resp.status_code == 200
    doc = seeded_store.load()
    assert doc["order"]["Backlog"][0] == "item2"


def test_board_place_out_of_range_index_returns_400(client: TestClient) -> None:
    """A wild/negative client index is rejected fail-loud (DESIGN §10 input contract)."""
    resp = client.post(
        "/api/board/place", json={"item_id": "item1", "column_key": "Backlog", "index": 999}
    )
    assert resp.status_code == 400


def test_board_place_stale_version_returns_409(client: TestClient) -> None:
    resp = client.post(
        "/api/board/place",
        json={"item_id": "item1", "column_key": "Backlog", "index": 0, "if_version": 99},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Mutations bump the nudge
# ---------------------------------------------------------------------------


def test_board_move_bumps_nudge(tmp_path: pathlib.Path, seeded_store: FsBoardStateStore) -> None:
    nudge_calls: list[int] = []
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=_FAKE_ENTRY),
        patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store),
        patch("kanbanmate.http.board_routes._nudge", side_effect=lambda: nudge_calls.append(1)),
    ):
        with TestClient(app) as c:
            c.post("/api/board/move", json={"item_id": "item1", "to_column": "Done"})
    assert nudge_calls, "move must bump the daemon nudge"


def _record_mirror(order: list[str]) -> Callable[..., dict[str, object]]:
    """Return a ``_mirror_to_github`` stub that records its call order, then returns a synced result.

    Split out so the side_effect APPENDS (returning None) and THEN returns the mirror dict in two
    statements — an ``append(...) or {...}`` one-liner trips mypy (``append`` returns None).
    """

    def _stub(*_a: object, **_k: object) -> dict[str, object]:
        order.append("mirror")
        return {"state": "synced", "detail": None}

    return _stub


def test_board_move_nudges_before_github_mirror(
    tmp_path: pathlib.Path, seeded_store: FsBoardStateStore
) -> None:
    """tug FIX 3: /api/board/move nudges the daemon BEFORE the synchronous GitHub mirror round-trip.

    Coupling the daemon-wake latency to GitHub speed (~0.5–1.5 s GraphQL) was the observed drag→agent
    lag. The local board.json write has already landed, so the cheap nudge must fire first; the mirror
    runs after (fail-soft). Records the call order of the injected ``_nudge`` + ``_mirror_to_github``.
    """
    order: list[str] = []
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=_FAKE_ENTRY),
        patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store),
        patch(
            "kanbanmate.http.board_routes._nudge",
            side_effect=lambda: order.append("nudge"),
        ),
        patch(
            "kanbanmate.http.board_routes._mirror_to_github",
            side_effect=_record_mirror(order),
        ),
    ):
        with TestClient(app) as c:
            resp = c.post("/api/board/move", json={"item_id": "item1", "to_column": "Done"})
    assert resp.status_code == 200
    assert order == ["nudge", "mirror"], order


def test_board_place_nudges_before_github_mirror(
    tmp_path: pathlib.Path, seeded_store: FsBoardStateStore
) -> None:
    """tug FIX 3: /api/board/place nudges before the GitHub mirror too (same coupling fix as move)."""
    order: list[str] = []
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=_FAKE_ENTRY),
        patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store),
        patch(
            "kanbanmate.http.board_routes._nudge",
            side_effect=lambda: order.append("nudge"),
        ),
        patch(
            "kanbanmate.http.board_routes._mirror_to_github",
            side_effect=_record_mirror(order),
        ),
    ):
        with TestClient(app) as c:
            resp = c.post(
                "/api/board/place",
                json={"item_id": "item2", "column_key": "Backlog", "index": 0},
            )
    assert resp.status_code == 200
    assert order == ["nudge", "mirror"], order


# ---------------------------------------------------------------------------
# POST /api/board/import — error mapping
# ---------------------------------------------------------------------------


def test_board_import_missing_columns_yaml_is_400_not_502(
    tmp_path: pathlib.Path, seeded_store: FsBoardStateStore
) -> None:
    """A missing/unreadable columns.yml is a local config error → 400, never a GitHub-blaming 502."""
    entry = MagicMock()
    entry.board_backend = "native"
    entry.project_id = "pid"
    entry.repo = "o/r"
    entry.clone = str(tmp_path)  # no .claude/kanban/columns.yml here
    entry.enabled = True
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry),
        patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store),
        patch("kanbanmate.http.board_routes._nudge"),
    ):
        with TestClient(app) as c:
            resp = c.post("/api/board/import", json={"dry_run": True})
    assert resp.status_code == 400, "local columns-config error must be 400, not 502"
    assert "columns config" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Mirror-on-move (board-view fix): a UI move must reach GitHub via the mirror
# ---------------------------------------------------------------------------


def _clone_with_columns(tmp_path: pathlib.Path) -> pathlib.Path:
    """A clone dir with a .claude/kanban/columns.yml mapping the test COLUMNS (key==name here)."""
    ck = tmp_path / "clone" / ".claude" / "kanban"
    ck.mkdir(parents=True)
    ck.joinpath("columns.yml").write_text(
        "columns:\n" + "".join(f"  - key: {c}\n    name: {c}\n    class: inert\n" for c in COLUMNS),
        encoding="utf-8",
    )
    return tmp_path / "clone"


def _entry_with_clone(clone: pathlib.Path) -> MagicMock:
    e = MagicMock()
    e.board_backend = "native"
    e.project_id = "pid"
    e.repo = "o/r"
    e.clone = str(clone)
    e.enabled = True
    e.board_mirror = True
    return e


def _confirming_forge(returns: str | None) -> MagicMock:
    """A mock forge whose move_card_confirmed returns ``returns`` (the Status GitHub recorded)."""
    forge = MagicMock()
    forge.move_card_confirmed.return_value = returns
    return forge


def test_board_move_mirrors_to_github(
    tmp_path: pathlib.Path, seeded_store: FsBoardStateStore
) -> None:
    """A /api/board/move writes native AND mirrors to GitHub, verified read-your-write (state=synced)."""
    entry = _entry_with_clone(_clone_with_columns(tmp_path))
    mock_forge = _confirming_forge("Done")  # mutation confirms Done
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry),
        patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store),
        patch("kanbanmate.http.board_routes._get_forge", return_value=mock_forge),
        patch("kanbanmate.http.board_routes._nudge"),
    ):
        with TestClient(app) as c:
            resp = c.post("/api/board/move", json={"item_id": "item1", "to_column": "Done"})
    assert resp.status_code == 200
    assert resp.json()["mirror_state"] == "synced"
    assert resp.json()["mirror_degraded"] is False
    # display name (key==name here); verification is read-your-write, no separate snapshot call
    mock_forge.move_card_confirmed.assert_called_once_with("item1", "Done")
    mock_forge.snapshot.assert_not_called()


def test_board_move_mirror_uses_display_name_when_key_differs(
    tmp_path: pathlib.Path, seeded_store: FsBoardStateStore
) -> None:
    """The mirror maps the column KEY → Status display NAME (catches a key/name mapping regression)."""
    ck = tmp_path / "clone" / ".claude" / "kanban"
    ck.mkdir(parents=True)
    # Key "Done" but display name "Terminé" — the mirror MUST send the name, not the key.
    ck.joinpath("columns.yml").write_text(
        "columns:\n"
        "  - key: Backlog\n    name: Backlog\n    class: inert\n"
        "  - key: InProgress\n    name: InProgress\n    class: inert\n"
        "  - key: Done\n    name: Terminé\n    class: inert\n",
        encoding="utf-8",
    )
    entry = _entry_with_clone(tmp_path / "clone")
    mock_forge = _confirming_forge("Terminé")  # GitHub confirms the display name
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry),
        patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store),
        patch("kanbanmate.http.board_routes._get_forge", return_value=mock_forge),
        patch("kanbanmate.http.board_routes._nudge"),
    ):
        with TestClient(app) as c:
            resp = c.post("/api/board/move", json={"item_id": "item1", "to_column": "Done"})
    assert resp.json()["mirror_state"] == "synced"
    mock_forge.move_card_confirmed.assert_called_once_with("item1", "Terminé")


def test_board_move_mirror_unconfirmed_when_confirm_mismatches(
    tmp_path: pathlib.Path, seeded_store: FsBoardStateStore
) -> None:
    """The mutation returns but GitHub confirms a DIFFERENT Status → state=unconfirmed.

    The silent-no-op case the operator asked to catch: trusting the HTTP 200 would falsely claim
    success. The read-your-write confirmation proves the remote state and downgrades to 'unconfirmed'.
    """
    entry = _entry_with_clone(_clone_with_columns(tmp_path))
    mock_forge = _confirming_forge("Backlog")  # GitHub still shows Backlog, not Done
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry),
        patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store),
        patch("kanbanmate.http.board_routes._get_forge", return_value=mock_forge),
        patch("kanbanmate.http.board_routes._nudge"),
    ):
        with TestClient(app) as c:
            resp = c.post("/api/board/move", json={"item_id": "item1", "to_column": "Done"})
    body = resp.json()
    assert resp.status_code == 200
    assert body["mirror_state"] == "unconfirmed"
    assert body["mirror_degraded"] is True
    assert "expected 'Done'" in body["mirror_detail"]


def test_board_move_mirror_unconfirmed_when_confirm_none(
    tmp_path: pathlib.Path, seeded_store: FsBoardStateStore
) -> None:
    """A mutation response carrying no Status value (None) → state=unconfirmed (not synced)."""
    entry = _entry_with_clone(_clone_with_columns(tmp_path))
    mock_forge = _confirming_forge(None)
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry),
        patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store),
        patch("kanbanmate.http.board_routes._get_forge", return_value=mock_forge),
        patch("kanbanmate.http.board_routes._nudge"),
    ):
        with TestClient(app) as c:
            resp = c.post("/api/board/move", json={"item_id": "item1", "to_column": "Done"})
    assert resp.json()["mirror_state"] == "unconfirmed"
    assert resp.json()["mirror_degraded"] is True


def test_board_move_mirror_disabled_not_degraded(
    tmp_path: pathlib.Path, seeded_store: FsBoardStateStore
) -> None:
    """board_mirror=False → state=disabled, not degraded, and the forge is never called."""
    entry = _entry_with_clone(_clone_with_columns(tmp_path))
    entry.board_mirror = False
    mock_forge = MagicMock()
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry),
        patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store),
        patch("kanbanmate.http.board_routes._get_forge", return_value=mock_forge),
        patch("kanbanmate.http.board_routes._nudge"),
    ):
        with TestClient(app) as c:
            resp = c.post("/api/board/move", json={"item_id": "item1", "to_column": "Done"})
    assert resp.json()["mirror_state"] == "disabled"
    assert resp.json()["mirror_degraded"] is False
    mock_forge.move_card_confirmed.assert_not_called()


def test_board_move_mirror_failure_sets_degraded(
    tmp_path: pathlib.Path, seeded_store: FsBoardStateStore
) -> None:
    """A mirror failure is fail-soft: native still saved, response flags mirror_degraded=True."""
    entry = _entry_with_clone(_clone_with_columns(tmp_path))
    mock_forge = MagicMock()
    mock_forge.move_card_confirmed.side_effect = RuntimeError("GitHub down")
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry),
        patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store),
        patch("kanbanmate.http.board_routes._get_forge", return_value=mock_forge),
        patch("kanbanmate.http.board_routes._nudge"),
    ):
        with TestClient(app) as c:
            resp = c.post("/api/board/move", json={"item_id": "item1", "to_column": "Done"})
    assert resp.status_code == 200, "mirror failure must not fail the move (native is authority)"
    assert resp.json()["mirror_state"] == "failed"
    assert resp.json()["mirror_degraded"] is True
    assert seeded_store.load()["placement"]["item1"] == "Done", "native write still landed"


def test_board_move_missing_to_column_returns_400(client: TestClient) -> None:
    """to_column is required (explicit field-presence check)."""
    resp = client.post("/api/board/move", json={"item_id": "item1"})
    assert resp.status_code == 400
    assert "to_column" in resp.json()["detail"]


def test_board_import_happy_path_through_route(tmp_path: pathlib.Path) -> None:
    """A real (non-dry-run) import via the route returns {version, summary} and fires the nudge."""
    entry = _entry_with_clone(_clone_with_columns(tmp_path))
    nudged = []
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry),
        patch("kanbanmate.http.board_routes._get_store", return_value=MagicMock()),
        patch("kanbanmate.http.board_routes._kanban_root", return_value=tmp_path),
        patch("kanbanmate.adapters.github.token.load_entry_token", return_value="tok"),
        patch("kanbanmate.adapters.github.client.GithubClient", return_value=MagicMock()),
        patch(
            "kanbanmate.app.board_import.import_board",
            return_value={"version": 1, "summary": {"Backlog": 2}},
        ),
        patch("kanbanmate.http.board_routes._nudge", side_effect=lambda: nudged.append(1)),
    ):
        with TestClient(app) as c:
            resp = c.post("/api/board/import", json={"dry_run": False})
    assert resp.status_code == 200
    assert resp.json()["version"] == 1
    assert nudged, "a real import must nudge the daemon"


def test_board_import_forge_failure_returns_502(tmp_path: pathlib.Path) -> None:
    """A forge/import failure (after local columns.yml loads fine) is a 502, not a raw 500."""
    entry = _entry_with_clone(_clone_with_columns(tmp_path))
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry),
        patch("kanbanmate.http.board_routes._get_store", return_value=MagicMock()),
        patch("kanbanmate.http.board_routes._kanban_root", return_value=tmp_path),
        patch("kanbanmate.adapters.github.token.load_entry_token", return_value="tok"),
        patch("kanbanmate.adapters.github.client.GithubClient", return_value=MagicMock()),
        patch(
            "kanbanmate.app.board_import.import_board",
            side_effect=RuntimeError("GitHub snapshot failed"),
        ),
        patch("kanbanmate.http.board_routes._nudge"),
    ):
        with TestClient(app) as c:
            resp = c.post("/api/board/import", json={"dry_run": False})
    assert resp.status_code == 502, "a forge failure must map to 502"


# ---------------------------------------------------------------------------
# Item 2 — body excerpt on the card shape
# ---------------------------------------------------------------------------


def test_body_excerpt_strips_status_block_and_markers() -> None:
    """The excerpt drops the status-header block, markers, comments and headings — keeps prose."""
    from kanbanmate.core.body_edit import STATUS_BEGIN, STATUS_END
    from kanbanmate.http.board_routes import _body_excerpt

    body = (
        f"{STATUS_BEGIN}\nstage: Plan · health: ACTIVE\n{STATUS_END}\n"
        "**roadmap**: item 5\n"
        "**design**: docs/x.md\n"
        "<!-- a comment -->\n"
        "## Heading\n"
        "\n"
        "Implement the native board view with a mobile-first layout.\n"
        "More detail on the second line.\n"
    )
    excerpt = _body_excerpt(body)
    assert excerpt.startswith("Implement the native board view")
    assert "roadmap" not in excerpt
    assert "STATUS" not in excerpt and "stage:" not in excerpt
    assert "##" not in excerpt


def test_body_excerpt_truncates_long_prose() -> None:
    """A very long body is truncated to the excerpt cap with an ellipsis."""
    from kanbanmate.http.board_routes import _EXCERPT_MAX, _body_excerpt

    excerpt = _body_excerpt("word " * 200)
    assert len(excerpt) <= _EXCERPT_MAX
    assert excerpt.endswith("…")


def test_body_excerpt_empty_for_no_prose() -> None:
    """A draft item / all-marker body yields an empty excerpt (no crash)."""
    from kanbanmate.http.board_routes import _body_excerpt

    assert _body_excerpt("") == ""
    assert _body_excerpt("**codename**: anchor\n## Title\n") == ""


def test_board_state_card_carries_excerpt(seeded_store: FsBoardStateStore) -> None:
    """GET /state surfaces a body excerpt on each card (Item 2)."""
    from kanbanmate.core.domain import BoardSnapshot, Ticket

    fake_forge = MagicMock()
    fake_forge.snapshot.return_value = BoardSnapshot(
        tickets=(
            Ticket(
                item_id="item1",
                issue_number=42,
                title="First",
                column_key="Backlog",
                body="A concise description of the work.",
            ),
        ),
        fetched_at=0.0,
    )
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=_FAKE_ENTRY),
        patch("kanbanmate.http.board_routes._get_store", return_value=seeded_store),
        patch("kanbanmate.http.board_routes._get_forge", return_value=fake_forge),
    ):
        with TestClient(app) as c:
            resp = c.get("/api/board/state")
    cards_by_id = {card["item_id"]: card for card in resp.json()["cards"]}
    assert cards_by_id["item1"]["excerpt"] == "A concise description of the work."
    assert cards_by_id["item2"]["excerpt"] == ""  # not in the forge snapshot → empty


def test_new_ticket_creates_issue_at_backlog(tmp_path: pathlib.Path) -> None:
    """POST /api/board/new-ticket creates the issue, adds it to the project and sets Status=Backlog."""
    entry = _entry_with_clone(_clone_with_columns(tmp_path))
    forge = MagicMock()
    forge.create_issue.return_value = ("ISSUE_NODE", 77)
    forge.add_to_project.return_value = "item-new"
    forge.move_card_confirmed.return_value = "Backlog"
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry),
        patch("kanbanmate.http.board_routes._get_forge", return_value=forge),
        patch("kanbanmate.http.board_routes._nudge"),
    ):
        with TestClient(app) as c:
            resp = c.post(
                "/api/board/new-ticket",
                json={"title": "  Add dark mode  ", "body": "It would be nice."},
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["number"] == 77
    assert data["url"] == "https://github.com/o/r/issues/77"
    assert data["column"] == "Backlog"
    assert data["status_confirmed"] is True
    forge.create_issue.assert_called_once_with("o/r", "Add dark mode", "It would be nice.", [])
    forge.add_to_project.assert_called_once_with("pid", "ISSUE_NODE")
    forge.move_card_confirmed.assert_called_once_with("item-new", "Backlog")


def test_new_ticket_requires_title(tmp_path: pathlib.Path) -> None:
    """A blank title is a 400 (no GitHub call)."""
    entry = _entry_with_clone(_clone_with_columns(tmp_path))
    forge = MagicMock()
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry),
        patch("kanbanmate.http.board_routes._get_forge", return_value=forge),
    ):
        with TestClient(app) as c:
            resp = c.post("/api/board/new-ticket", json={"title": "   "})
    assert resp.status_code == 400
    forge.create_issue.assert_not_called()


def test_new_ticket_move_failure_returns_partial_success(tmp_path: pathlib.Path) -> None:
    """If Status=Backlog fails AFTER the issue exists, return 200 status_confirmed=false (NO 502).

    A 502 would invite a retry → a DUPLICATE issue. The issue already exists and is on the board,
    so the endpoint reports partial success and lets the operator fix the status instead.
    """
    entry = _entry_with_clone(_clone_with_columns(tmp_path))
    forge = MagicMock()
    forge.create_issue.return_value = ("ISSUE_NODE", 88)
    forge.add_to_project.return_value = "item-new"
    forge.move_card_confirmed.side_effect = KeyError("Backlog")  # status option drift
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry),
        patch("kanbanmate.http.board_routes._get_forge", return_value=forge),
        patch("kanbanmate.http.board_routes._nudge"),
    ):
        with TestClient(app) as c:
            resp = c.post("/api/board/new-ticket", json={"title": "Idea"})
    assert resp.status_code == 200, "issue was created → must not 502 (would duplicate on retry)"
    assert resp.json()["number"] == 88
    assert resp.json()["status_confirmed"] is False


def test_new_ticket_no_backlog_column_is_400(tmp_path: pathlib.Path) -> None:
    """No Backlog column configured → 400 (never silently dump into a possibly-triggering column)."""
    ck = tmp_path / "clone" / ".claude" / "kanban"
    ck.mkdir(parents=True)
    ck.joinpath("columns.yml").write_text(
        "columns:\n"
        "  - key: Brainstorming\n    name: Brainstorming\n    class: inert\n"
        "  - key: Done\n    name: Done\n    class: inert\n",
        encoding="utf-8",
    )
    entry = _entry_with_clone(tmp_path / "clone")
    forge = MagicMock()
    with (
        patch("kanbanmate.http.board_routes._resolve_entry", return_value=entry),
        patch("kanbanmate.http.board_routes._get_forge", return_value=forge),
    ):
        with TestClient(app) as c:
            resp = c.post("/api/board/new-ticket", json={"title": "Idea"})
    assert resp.status_code == 400
    forge.create_issue.assert_not_called()
