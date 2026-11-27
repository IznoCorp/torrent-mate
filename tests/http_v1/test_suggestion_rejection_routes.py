"""K3-G7 on v1: « Rejeter » a suggestion and its « Annuler », per account (the operator's ruling O-9 A).

A rejection is the rejecting account's: it leaves ITS deck and no other account's. The two accounts
here are two signed-in clients over the same ``app.db`` and ``acquire.db``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from personalscraper.acquire.domain import SuggestionRow
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right
from personalscraper.conf.models.config import Config

_REQUEST = frozenset({Right.ACQUISITION_REQUEST})
_LIBRARY = frozenset({Right.LIBRARY_READ})
_READ_ONLY = InstanceCeiling(forbidden=WRITE_RIGHTS, read_only=True)


@pytest.fixture(autouse=True)
def _production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts on a production instance: no ceiling from the environment.

    Args:
        monkeypatch: Pytest's monkeypatch fixture.
    """
    monkeypatch.delenv("PERSONALSCRAPER_WEB_ROLE", raising=False)
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "prod")


@pytest.fixture
def acquire(test_config: Config) -> Iterator[ConcreteAcquireStore]:
    """Open the ``acquire.db`` the services read, and fill its deck with three titles.

    Args:
        test_config: The synthetic configuration.

    Yields:
        The store.
    """
    store = build_acquire_store(test_config.acquire)
    store.suggestions.replace_deck(
        [_row("tmdb", "1", "show"), _row("trakt", "the-second-one", "movie"), _row("tmdb", "3", "show")]
    )
    try:
        yield store
    finally:
        store.close()


def _row(provider: str, provider_id: str, kind: str) -> SuggestionRow:
    """A deck row titled after its provider id.

    Args:
        provider: The recommending provider.
        provider_id: The title's id there.
        kind: ``movie`` or ``show``.

    Returns:
        The row.
    """
    return SuggestionRow(
        provider=provider,
        provider_id=provider_id,
        kind=kind,  # type: ignore[arg-type]
        title=f"Title {provider_id}",
        year=2021,
        rating=7.5,
        poster=None,
        reason="similar_to_owned",
        seed_key="tmdb:603",
        refreshed_at=1_800_000_000,
    )


def _deck(client: TestClient) -> list[dict[str, object]]:
    """The cards of the reader's first page.

    Args:
        client: The signed-in client.

    Returns:
        The cards.
    """
    response = client.get("/acquisition/suggestions")
    assert response.status_code == 200
    return response.json()["suggestions"]


def _titles(client: TestClient) -> list[object]:
    """The titles of the reader's first page, in order."""
    return [card["title"] for card in _deck(client)]


def _rejection(suggestion_id: object) -> str:
    """The address of one suggestion's rejection."""
    return f"/acquisition/suggestions/{suggestion_id}/rejection"


class TestReject:
    """``POST /acquisition/suggestions/{suggestionId}/rejection``."""

    def test_the_card_leaves_the_rejecting_accounts_deck_only(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """O-9 A: a household member's « rejeter » hides nothing from the other accounts."""
        mine, theirs = v1_client(rights=_REQUEST), v1_client(role="household")
        second = _deck(mine)[1]["id"]

        response = mine.post(_rejection(second))

        assert (response.status_code, response.json()) == (200, {"ok": True})
        assert _titles(mine) == ["Title 1", "Title 3"]
        assert _titles(theirs) == ["Title 1", "Title the-second-one", "Title 3"]

    def test_a_rejection_outlives_the_decks_refresh(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """The deck is replaced wholesale by a refresh; a title it brings back stays rejected."""
        client = v1_client(rights=_REQUEST)
        client.post(_rejection(_deck(client)[0]["id"]))

        acquire.suggestions.replace_deck([_row("tmdb", "9", "show"), _row("tmdb", "1", "show")])

        assert _titles(client) == ["Title 9"]

    def test_rejecting_what_is_already_rejected_answers_the_same(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """A rejection is a state: asked twice, it is held once and answers 200 both times."""
        client = v1_client(rights=_REQUEST)
        first = _deck(client)[0]["id"]

        answers = [client.post(_rejection(first)).status_code for _ in range(2)]
        client.delete(_rejection(first))

        assert answers == [200, 200]
        assert _titles(client)[0] == "Title 1"

    def test_a_card_the_deck_does_not_hold_is_not_found(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """404 ``suggestion.not_found``: a title no card of the deck bears."""
        response = v1_client(rights=_REQUEST).post(_rejection("show:tmdb:999"))

        assert (response.status_code, response.json()["code"]) == (404, "suggestion.not_found")

    def test_the_kind_is_part_of_the_cards_identity(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """TMDB numbers films and shows apart: the film ``1`` is not the deck's show ``1``."""
        client = v1_client(rights=_REQUEST)

        response = client.post(_rejection("movie:tmdb:1"))

        assert (response.status_code, response.json()["code"]) == (404, "suggestion.not_found")
        assert _titles(client)[0] == "Title 1"

    @pytest.mark.parametrize("suggestion_id", ["Dune", "show:tmdb", "series:tmdb:1", "show::1", "show:tmdb:"])
    def test_a_malformed_id_is_request_invalid_naming_it(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore, suggestion_id: str
    ) -> None:
        """400 ``request.invalid`` naming ``suggestionId``, for the rejection and for its undo."""
        client = v1_client(rights=_REQUEST)

        for response in (client.post(_rejection(suggestion_id)), client.delete(_rejection(suggestion_id))):
            assert (response.status_code, response.json()["code"]) == (400, "request.invalid")
            assert response.json()["params"]["fields"] == ["suggestionId"]

    def test_a_replayed_key_answers_the_first_answer_and_applies_nothing(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """The outbox replays a held « rejeter »: after an « Annuler », the replay rejects nothing again."""
        client = v1_client(rights=_REQUEST)
        first = _deck(client)[0]["id"]
        headers = {"Idempotency-Key": "reject-once"}
        client.post(_rejection(first), headers=headers)
        client.delete(_rejection(first))

        replay = client.post(_rejection(first), headers=headers)

        assert (replay.status_code, replay.json()) == (200, {"ok": True})
        assert _titles(client)[0] == "Title 1"


class TestUndo:
    """``DELETE /acquisition/suggestions/{suggestionId}/rejection``."""

    def test_the_card_is_back_at_its_place(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """« Annuler » undoes the rejection."""
        client = v1_client(rights=_REQUEST)
        second = _deck(client)[1]["id"]
        client.post(_rejection(second))

        response = client.delete(_rejection(second))

        assert (response.status_code, response.json()) == (200, {"ok": True})
        assert _titles(client) == ["Title 1", "Title the-second-one", "Title 3"]

    def test_a_rejection_is_undone_even_once_the_deck_dropped_the_card(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """The undo reads the account's rejection, never the deck: a refresh in between changes nothing."""
        client = v1_client(rights=_REQUEST)
        first = _deck(client)[0]["id"]
        client.post(_rejection(first))
        acquire.suggestions.replace_deck([_row("tmdb", "9", "show")])

        assert client.delete(_rejection(first)).status_code == 200

    def test_what_the_account_did_not_reject_is_not_found(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore
    ) -> None:
        """404 ``suggestion.not_found``: nothing to undo, and another account's rejection is not the caller's."""
        mine, theirs = v1_client(rights=_REQUEST), v1_client(role="household")
        first = _deck(mine)[0]["id"]
        mine.post(_rejection(first))

        response = theirs.delete(_rejection(first))

        assert (response.status_code, response.json()["code"]) == (404, "suggestion.not_found")
        assert _titles(mine)[0] == "Title the-second-one"


class TestTheDoor:
    """The rights the two writes ask, and the instance ceiling."""

    @pytest.mark.parametrize("method", ["post", "delete"])
    def test_a_session_and_the_request_right_are_asked(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore, method: str
    ) -> None:
        """No session: 401; without ``acquisition.request``: 403 ``right.missing``."""
        anonymous = getattr(v1_client(role=None), method)(_rejection("show:tmdb:1"))
        unrighted = getattr(v1_client(rights=_LIBRARY), method)(_rejection("show:tmdb:1"))

        assert anonymous.status_code == 401
        assert (unrighted.status_code, unrighted.json()["code"]) == (403, "right.missing")

    @pytest.mark.parametrize("method", ["post", "delete"])
    def test_a_read_only_instance_refuses_the_write(
        self, v1_client: Callable[..., TestClient], acquire: ConcreteAcquireStore, method: str
    ) -> None:
        """The read-only instance refuses both writes: 403 ``instance.forbidden_write``."""
        client = v1_client(rights=_REQUEST, ceiling=_READ_ONLY)

        response = getattr(client, method)(_rejection("show:tmdb:1"))

        assert (response.status_code, response.json()["code"]) == (403, "instance.forbidden_write")
