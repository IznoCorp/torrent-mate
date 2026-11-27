"""The follows' routes: the nine operations of K3 P12 over the real services, end to end.

Each route parses the wire key and makes ONE call on ``FollowService`` or ``FollowCompleteness``;
the rules (requesters, quality and pause in force, soft removal, restore, the prime) are proved in
``tests/unit/app/acquisition``. These tests hold the wire: the contract's body per operation, the
statuses and ``Problem`` codes it declares, the rights each operation asks, the instance ceiling on
the writes, the own-scope of the acts and the membership filter of the reads.

The services are the composed ones, over the synthetic config: ``acquire.db``, ``app.db`` and the
supervisor's queue live under the test's temporary ``data_dir``, shared by every client of a test,
so two accounts of one test follow and read the same rows.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

import pytest
from _repo_paths import CONTRACT, SERVED_CONTRACT
from fastapi.testclient import TestClient

from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right
from personalscraper.app.supervisor.model import JobKind, RunTrigger, Settlement
from personalscraper.http_v1.routes import acquisition as acquisition_routes

ClientFactory = Callable[..., TestClient]

SILO: dict[str, Any] = {"title": "Silo", "kind": "show", "year": 2023, "provider": "tvdb", "providerId": 403245}
SILO_KEY = "tvdb:403245"
HEAT: dict[str, Any] = {"title": "Heat", "kind": "movie", "year": 1995, "provider": "tmdb", "providerId": 949}
HEAT_KEY = "tmdb:949"
#: A film held by a TVDB id only: TVDB numbers shows, so a lookup that takes ``tvdb:`` for a show's never finds it.
ODD: dict[str, Any] = {"title": "Odd", "kind": "movie", "year": 2001, "provider": "tvdb", "providerId": 777}
ODD_KEY = "tvdb:777"

#: The rights of a member who also sets its own quality (the seeded household role has no quality right).
MEMBER_WITH_QUALITY = frozenset(
    {
        Right.ACQUISITION_REQUEST,
        Right.ACQUISITION_FOLLOW,
        Right.ACQUISITION_PILOT_OWN,
        Right.ACQUISITION_QUALITY_OWN,
        Right.ACQUISITION_PAUSE_OWN,
    }
)

#: What a Follow carries whatever its kind: the contract's required properties.
FOLLOW_REQUIRED = {
    "addedAt",
    "ids",
    "kind",
    "nextAirDate",
    "poster",
    "searches",
    "showStatus",
    "status",
    "title",
    "year",
}
FOLLOW_STATUSES = {"disabled", "verifying", "to_grab", "acquiring", "pending", "unverified", "up_to_date", "ended"}


def _account_id(client: TestClient) -> str:
    """The signed-in account's key.

    Args:
        client: A signed-in client.

    Returns:
        Its account id.
    """
    return str(client.get("/auth/me").json()["id"])


def _follow(client: TestClient, body: dict[str, Any] = SILO) -> dict[str, Any]:
    """Follow a medium and return the answer.

    Args:
        client: A signed-in client.
        body: The create body.

    Returns:
        The follow as the contract's ``Follow``.
    """
    response = client.post("/acquisition/followed", json=body)
    assert response.status_code == 200, response.text
    follow: dict[str, Any] = response.json()
    return follow


def _settle_queued_primes(client: TestClient) -> None:
    """Settle every queued acquisition request, as a worker would once done: a later equal ask queues anew.

    Args:
        client: A client of the services whose queue is settled.
    """
    services: Any = client.app.state.services  # type: ignore[attr-defined]
    for request in services.runs.queue_view().acquisition_queued:
        request.admit(None, time.time())
        request.settle(Settlement.SUCCESS, time.time())
        with services.app_store.immediate():
            services.app_store.runs.save(request)


def _titles(client: TestClient) -> list[str]:
    """The titles of the follows the client reads.

    Args:
        client: A signed-in client.

    Returns:
        The titles, in the order served.
    """
    response = client.get("/acquisition/followed")
    assert response.status_code == 200, response.text
    return [one["title"] for one in response.json()]


# ── the nine operations, each as the contract writes it ─────────────────────


def test_a_show_is_followed_and_answers_its_follow(v1_client: ClientFactory) -> None:
    """``createFollow``: 200 and the follow with the caller as its one requester, nothing set yet."""
    client = v1_client()

    follow = _follow(client)

    assert FOLLOW_REQUIRED <= follow.keys()
    assert (follow["title"], follow["kind"], follow["year"]) == ("Silo", "show", 2023)
    assert follow["ids"] == {"tvdb": 403245}
    assert follow["status"] in FOLLOW_STATUSES
    assert follow["searches"] == 0
    assert follow["requesters"] == [{"id": _account_id(client), "name": "Account 1"}]
    assert (follow["ownQuality"], follow["quality"]) == (None, None)
    assert (follow["ownPaused"], follow["paused"]) == (False, False)
    assert isinstance(follow["addedAt"], int | float)


def test_a_show_with_no_cached_catalogue_carries_no_counts_never_a_null(v1_client: ClientFactory) -> None:
    """``aired`` and ``owned`` are integers in the contract: with no aired catalogue they are absent, not ``null``."""
    follow = _follow(v1_client())

    assert "aired" not in follow and "owned" not in follow


def test_a_film_is_followed_and_carries_no_show_block(v1_client: ClientFactory) -> None:
    """A film's follow has no ``aired``, ``owned`` nor a show status: the contract's shows-only properties."""
    follow = _follow(v1_client(), HEAT)

    assert follow["kind"] == "movie"
    assert follow["showStatus"] is None
    assert "aired" not in follow and "owned" not in follow


def test_a_film_held_by_a_tvdb_id_answers_on_every_item_route(v1_client: ClientFactory) -> None:
    """A key carries no kind: a ``tvdb:`` key names a show first and a film when no show holds it, on every route."""
    client = v1_client(rights=MEMBER_WITH_QUALITY)
    _follow(client, ODD)
    item = f"/acquisition/followed/{ODD_KEY}"

    answers = {
        "updateFollow": client.patch(item, json={"status": "disabled"}),
        "setAcquisitionPause": client.put(f"{item}/pause", json={"paused": False}),
        "setAcquisitionQuality": client.put(f"{item}/quality", json={"profile": "1080p"}),
        "readFollowCompleteness": client.get(f"{item}/completeness"),
        "deleteFollow": client.delete(item),
        "restoreFollow": client.post(f"{item}/restore"),
    }

    assert {name: response.status_code for name, response in answers.items()} == dict.fromkeys(answers, 200)
    assert answers["readFollowCompleteness"].json()["kind"] == "movie"
    assert answers["restoreFollow"].json()["ids"] == {"tvdb": 777}


def test_following_a_followed_medium_joins_it_never_a_409(v1_client: ClientFactory) -> None:
    """Another account asking for the same medium becomes a second requester of the one follow."""
    first, second = v1_client(), v1_client(role="requester")

    _follow(first)
    joined = _follow(second)

    assert {one["id"] for one in joined["requesters"]} == {_account_id(first), _account_id(second)}
    assert _titles(first) == ["Silo"]


def test_a_create_without_an_identity_is_a_400_naming_it(v1_client: ClientFactory) -> None:
    """A follow with no identity has no sheet to open: ``request.invalid``, never a row."""
    client = v1_client()

    response = client.post("/acquisition/followed", json={"title": "Silo", "kind": "show"})

    assert response.status_code == 400
    assert response.json()["code"] == "request.invalid"
    assert _titles(client) == []


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"provider": "plex"}, "provider"),
        ({"provider": "imdb", "providerId": 3}, "providerId"),
        ({"kind": "anime"}, "kind"),
        ({"providerId": 0}, "providerId"),
    ],
)
def test_a_create_that_names_no_medium_is_a_400_naming_the_field(
    v1_client: ClientFactory, change: dict[str, Any], field: str
) -> None:
    """A provider, an id or a kind the contract cannot hold: ``request.invalid`` naming the field."""
    response = v1_client().post("/acquisition/followed", json={**SILO, **change})

    assert response.status_code == 400
    assert response.json()["code"] == "request.invalid"
    assert field in response.json()["params"]["fields"]


def _added_at_of(client: TestClient) -> float:
    """The epoch the one follow the client reads was added at.

    Args:
        client: A signed-in client holding one follow.

    Returns:
        Its ``addedAt``.
    """
    return float(client.get("/acquisition/followed").json()[0]["addedAt"])


@pytest.mark.parametrize(
    ("age_seconds", "fresh"),
    [
        (0, True),
        (23 * 3600 + 59 * 60 + 59, True),
        (24 * 3600, False),
        (24 * 3600 + 1, False),
    ],
)
def test_a_follow_is_fresh_for_a_day_less_a_second(
    v1_client: ClientFactory, monkeypatch: pytest.MonkeyPatch, age_seconds: int, fresh: bool
) -> None:
    """``fresh`` is read against the clock: true at 23 h 59 min 59 s, false from 24 h (the bound itself is stale)."""
    client = v1_client()
    _follow(client)
    added_at = _added_at_of(client)
    monkeypatch.setattr(acquisition_routes, "_now", lambda: added_at + age_seconds)

    assert client.get("/acquisition/followed").json()[0]["fresh"] is fresh


def _admits_null(schema: dict[str, Any]) -> bool:
    """Whether a JSON schema accepts ``null``, in any of the forms a contract or a generated document writes.

    Args:
        schema: A schema.

    Returns:
        ``True`` when ``null`` is a declared type or a branch.
    """
    declared = schema.get("type")
    if declared == "null" or (isinstance(declared, list) and "null" in declared):
        return True
    return any(_admits_null(branch) for key in ("anyOf", "oneOf") for branch in schema.get(key, []))


@pytest.mark.parametrize(
    ("document", "schema"), [(CONTRACT, "Follow"), (SERVED_CONTRACT, "FollowModel")], ids=["contract", "served"]
)
def test_follow_year_admits_null_in_the_contract_and_in_the_served_document(document: Any, schema: str) -> None:
    """A follow with no known year is served ``null``: both documents say so, never an integer only."""
    follow = json.loads(document.read_text(encoding="utf-8"))["components"]["schemas"][schema]

    assert "year" in follow["required"]
    assert _admits_null(follow["properties"]["year"])


def test_a_follow_with_no_year_is_served_a_null_year(v1_client: ClientFactory) -> None:
    """``createFollow`` without a year: the follow's ``year`` is present and ``null``, on the create and on the read."""
    client = v1_client()
    without_year = {key: value for key, value in SILO.items() if key != "year"}

    created = _follow(client, without_year)

    assert "year" in created and created["year"] is None
    assert client.get("/acquisition/followed").json()[0]["year"] is None


def test_the_follows_are_listed_with_the_contracts_shape(v1_client: ClientFactory) -> None:
    """``readFollows``: 200, an array of ``Follow``."""
    client = v1_client()
    _follow(client)
    _follow(client, HEAT)

    response = client.get("/acquisition/followed")

    assert response.status_code == 200
    assert sorted(one["title"] for one in response.json()) == ["Heat", "Silo"]
    assert all(FOLLOW_REQUIRED <= one.keys() for one in response.json())


def test_the_data_dial_of_the_maquette_is_ignored(v1_client: ClientFactory) -> None:
    """``scenario`` is the maquette's dial, not an operation's parameter: v1 answers the one body it holds."""
    client = v1_client()
    _follow(client)

    plain = client.get("/acquisition/followed").json()
    dialled = client.get("/acquisition/followed", params={"scenario": "loaded"}).json()

    assert dialled == plain


def test_the_follow_is_paused_by_its_generic_pause_and_resumed(v1_client: ClientFactory) -> None:
    """``updateFollow``: ``disabled`` pauses the sole requester's follow, ``up_to_date`` resumes it."""
    client = v1_client()
    _follow(client)

    paused = client.patch(f"/acquisition/followed/{SILO_KEY}", json={"status": "disabled"})
    resumed = client.patch(f"/acquisition/followed/{SILO_KEY}", json={"status": "up_to_date"})

    assert (paused.status_code, paused.json()["paused"], paused.json()["ownPaused"]) == (200, True, True)
    assert (resumed.status_code, resumed.json()["paused"]) == (200, False)


def test_a_status_outside_the_enum_is_a_400(v1_client: ClientFactory) -> None:
    """``updateFollow``'s status is the contract's enum, never a free string (K3-G10)."""
    client = v1_client()
    _follow(client)

    response = client.patch(f"/acquisition/followed/{SILO_KEY}", json={"status": "acquiring"})

    assert response.status_code == 400
    assert response.json()["code"] == "request.invalid"


def test_the_generic_pause_of_a_shared_follow_is_refused_with_its_code(v1_client: ClientFactory) -> None:
    """Others asked for it too: 403 ``acquisition.follow_shared`` (each pauses it for itself)."""
    first, second = v1_client(), v1_client(role="requester")
    _follow(first)
    _follow(second)

    response = first.patch(f"/acquisition/followed/{SILO_KEY}", json={"status": "disabled"})

    assert response.status_code == 403
    assert response.json()["code"] == "acquisition.follow_shared"
    assert response.json()["params"] == {"followedId": SILO_KEY}


def test_a_follow_is_left_and_the_last_to_leave_removes_it(v1_client: ClientFactory) -> None:
    """``deleteFollow``: 200 ``{ok: true}``; the follow leaves the listing; a second delete is a 404."""
    client = v1_client()
    _follow(client)

    deleted = client.delete(f"/acquisition/followed/{SILO_KEY}")
    again = client.delete(f"/acquisition/followed/{SILO_KEY}")

    assert (deleted.status_code, deleted.json()) == (200, {"ok": True})
    assert _titles(client) == []
    assert (again.status_code, again.json()["code"]) == (404, "acquisition.not_found")


def test_a_removed_follow_comes_back_as_it_was(v1_client: ClientFactory) -> None:
    """``restoreFollow``: the year, the date it was followed since and the searches survive the removal."""
    client = v1_client()
    before = _follow(client)
    client.delete(f"/acquisition/followed/{SILO_KEY}")

    restored = client.post(f"/acquisition/followed/{SILO_KEY}/restore")

    assert restored.status_code == 200
    body = restored.json()
    assert (body["title"], body["year"], body["addedAt"], body["searches"]) == (
        before["title"],
        before["year"],
        before["addedAt"],
        before["searches"],
    )
    assert _titles(client) == ["Silo"]


def test_nothing_removed_under_a_key_is_not_restorable(v1_client: ClientFactory) -> None:
    """``restoreFollow`` of a medium never followed: 404 ``follow.not_restorable``."""
    response = v1_client().post("/acquisition/followed/tvdb:1/restore")

    assert response.status_code == 404
    assert response.json()["code"] == "follow.not_restorable"
    assert response.json()["params"] == {"followedId": "tvdb:1"}


def test_the_quality_floor_the_caller_sets_is_in_force(v1_client: ClientFactory) -> None:
    """``setAcquisitionQuality``: the caller's floor is its own and, alone, the one in force; ``null`` clears it."""
    client = v1_client(rights=MEMBER_WITH_QUALITY)
    _follow(client)

    set_floor = client.put(f"/acquisition/followed/{SILO_KEY}/quality", json={"profile": "1080p"})
    cleared = client.put(f"/acquisition/followed/{SILO_KEY}/quality", json={"profile": None})

    assert (set_floor.status_code, set_floor.json()["ownQuality"], set_floor.json()["quality"]) == (
        200,
        "1080p",
        "1080p",
    )
    assert (cleared.json()["ownQuality"], cleared.json()["quality"]) == (None, None)


def test_a_floor_outside_the_enum_is_a_400(v1_client: ClientFactory) -> None:
    """The floor is the whole of the operation: ``480p`` is no profile (K3-G3)."""
    client = v1_client(rights=MEMBER_WITH_QUALITY)
    _follow(client)

    response = client.put(f"/acquisition/followed/{SILO_KEY}/quality", json={"profile": "480p"})

    assert response.status_code == 400
    assert response.json()["code"] == "request.invalid"


def test_the_pause_the_caller_sets_is_its_own_and_pauses_the_follow_when_alone(v1_client: ClientFactory) -> None:
    """``setAcquisitionPause``: its own ask paused, and the follow paused once every holder asked."""
    client = v1_client()
    _follow(client)

    response = client.put(f"/acquisition/followed/{SILO_KEY}/pause", json={"paused": True})

    assert response.status_code == 200
    assert (response.json()["ownPaused"], response.json()["paused"]) == (True, True)


def test_a_co_requesters_pause_leaves_the_follow_running(v1_client: ClientFactory) -> None:
    """Two ask, one pauses: its own ask is paused, the follow is not (round 10 Q6)."""
    first, second = v1_client(), v1_client(role="requester")
    _follow(first)
    _follow(second)

    response = first.put(f"/acquisition/followed/{SILO_KEY}/pause", json={"paused": True})

    assert (response.json()["ownPaused"], response.json()["paused"]) == (True, False)


def test_a_requester_is_moved_to_another_account(v1_client: ClientFactory) -> None:
    """``reassignRequester``: 200 and the acquisition's requesters after the move."""
    owner, target, admin = v1_client(), v1_client(role="requester"), v1_client(role="admin")
    _follow(owner)

    response = admin.post(
        "/acquisition/requesters/reassign",
        json={"kind": "follow", "acquisition": SILO_KEY, "from": _account_id(owner), "to": _account_id(target)},
    )

    assert response.status_code == 200
    assert response.json()["requesters"] == [{"id": _account_id(target), "name": "Account 2"}]


def test_a_reassign_to_an_unknown_account_is_a_404(v1_client: ClientFactory) -> None:
    """The target must be an account of the roster: 404 ``account.unknown``."""
    owner, admin = v1_client(), v1_client(role="admin")
    _follow(owner)

    response = admin.post(
        "/acquisition/requesters/reassign",
        json={"kind": "follow", "acquisition": SILO_KEY, "from": _account_id(owner), "to": "account-nobody"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "account.unknown"


def test_a_reassign_of_a_card_names_the_same_acquisition(v1_client: ClientFactory) -> None:
    """``kind: card`` names the subject by its key as a follow does; a follow's card is its follow."""
    owner, target, admin = v1_client(), v1_client(role="requester"), v1_client(role="admin")
    _follow(owner)

    response = admin.post(
        "/acquisition/requesters/reassign",
        json={"kind": "card", "acquisition": SILO_KEY, "from": _account_id(owner), "to": _account_id(target)},
    )

    assert response.status_code == 200
    assert [one["id"] for one in response.json()["requesters"]] == [_account_id(target)]


def test_a_reassign_that_turns_the_follow_on_is_primed_under_the_system_trigger(v1_client: ClientFactory) -> None:
    """The prime a reassign leaves in the queue is the system's: it carries the system trigger, not the web's.

    Who asks it is proved in ``tests/unit/app/acquisition``: here the system actor is attributed to the
    first Admin, which is the reassigning one.
    """
    owner, target, admin = v1_client(), v1_client(role="requester"), v1_client(role="admin")
    _follow(owner)
    _settle_queued_primes(owner)
    owner.put(f"/acquisition/followed/{SILO_KEY}/pause", json={"paused": True})
    services: Any = admin.app.state.services  # type: ignore[attr-defined]
    before = {r.uid for r in services.runs.queue_view().acquisition_queued}

    admin.post(
        "/acquisition/requesters/reassign",
        json={"kind": "follow", "acquisition": SILO_KEY, "from": _account_id(owner), "to": _account_id(target)},
    )

    fresh = [
        r for r in services.runs.queue_view().acquisition_queued if r.uid not in before and r.job.kind is JobKind.PRIME
    ]
    assert [r.trigger for r in fresh] == [RunTrigger.SYSTEM]


def test_the_completeness_of_a_follow_without_a_catalogue_is_unknown(v1_client: ClientFactory) -> None:
    """``readFollowCompleteness``: no aired catalogue cached, so no seasons and ``source: unknown``."""
    client = v1_client()
    follow = _follow(client)

    response = client.get(f"/acquisition/followed/{SILO_KEY}/completeness")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == follow["title"] and body["kind"] == "show"
    assert (body["seasons"], body["source"], body["providerCatalogEmpty"]) == ([], "unknown", False)
    assert isinstance(body["followedId"], int)


# ── what is refused, and to whom ────────────────────────────────────────────

_CALLS: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/acquisition/followed", None),
    ("POST", "/acquisition/followed", SILO),
    ("PATCH", f"/acquisition/followed/{SILO_KEY}", {"status": "disabled"}),
    ("DELETE", f"/acquisition/followed/{SILO_KEY}", None),
    ("POST", f"/acquisition/followed/{SILO_KEY}/restore", None),
    ("PUT", f"/acquisition/followed/{SILO_KEY}/quality", {"profile": "720p"}),
    ("PUT", f"/acquisition/followed/{SILO_KEY}/pause", {"paused": True}),
    ("POST", "/acquisition/requesters/reassign", {"kind": "follow", "acquisition": SILO_KEY, "from": "a", "to": "b"}),
    ("GET", f"/acquisition/followed/{SILO_KEY}/completeness", None),
]
_WRITES = [call for call in _CALLS if call[0] != "GET"]


@pytest.mark.parametrize(("method", "path", "body"), _CALLS)
def test_without_a_session_every_operation_is_401(
    v1_client: ClientFactory, method: str, path: str, body: dict[str, Any] | None
) -> None:
    """No session: 401 ``auth.required``, before any rule is looked at."""
    response = v1_client(role=None).request(method, path, json=body)

    assert response.status_code == 401
    assert response.json()["code"] == "auth.required"


@pytest.mark.parametrize(("method", "path", "body"), _WRITES)
def test_without_its_right_a_write_is_403_naming_the_right(
    v1_client: ClientFactory, method: str, path: str, body: dict[str, Any] | None
) -> None:
    """A role holding only ``library.read`` is refused every write: ``right.missing``."""
    response = v1_client(rights=frozenset({Right.LIBRARY_READ})).request(method, path, json=body)

    assert response.status_code == 403
    assert response.json()["code"] == "right.missing"


@pytest.mark.parametrize(
    ("method", "path", "body", "right"),
    [
        ("POST", "/acquisition/followed", SILO, "acquisition.request"),
        ("PATCH", f"/acquisition/followed/{SILO_KEY}", {"status": "disabled"}, "acquisition.follow"),
        ("DELETE", f"/acquisition/followed/{SILO_KEY}", None, "acquisition.follow"),
        ("POST", f"/acquisition/followed/{SILO_KEY}/restore", None, "acquisition.follow"),
        ("PUT", f"/acquisition/followed/{SILO_KEY}/quality", {"profile": "720p"}, "acquisition.quality.own"),
        ("PUT", f"/acquisition/followed/{SILO_KEY}/pause", {"paused": True}, "acquisition.pause.own"),
        (
            "POST",
            "/acquisition/requesters/reassign",
            {"kind": "follow", "acquisition": SILO_KEY, "from": "a", "to": "b"},
            "acquisition.reassign",
        ),
    ],
)
def test_the_read_only_instance_refuses_every_write_even_to_an_admin(
    v1_client: ClientFactory, method: str, path: str, body: dict[str, Any] | None, right: str
) -> None:
    """Under the read-only ceiling: 403 ``instance.forbidden_write`` naming the right, and nothing written."""
    ceiling = InstanceCeiling(forbidden=WRITE_RIGHTS, read_only=True)
    client = v1_client(role="admin", ceiling=ceiling)

    response = client.request(method, path, json=body)

    assert response.status_code == 403
    assert response.json()["code"] == "instance.forbidden_write"
    assert response.json()["params"]["right"] == right
    assert _titles(client) == []


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("DELETE", "", None),
        ("PATCH", "", {"status": "disabled"}),
        ("PUT", "/quality", {"profile": "720p"}),
        ("PUT", "/pause", {"paused": True}),
    ],
)
def test_an_act_on_a_follow_the_caller_did_not_ask_for_is_refused(
    v1_client: ClientFactory, method: str, suffix: str, body: dict[str, Any] | None
) -> None:
    """Own-scoped: 403 ``acquisition.not_requester`` naming the follow, and the follow is untouched."""
    owner, stranger = v1_client(), v1_client(rights=MEMBER_WITH_QUALITY)
    _follow(owner)

    response = stranger.request(method, f"/acquisition/followed/{SILO_KEY}{suffix}", json=body)

    assert response.status_code == 403
    assert response.json()["code"] == "acquisition.not_requester"
    assert response.json()["params"] == {"followedId": SILO_KEY}
    assert _titles(owner) == ["Silo"]


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("PATCH", "", {"status": "disabled"}),
        ("DELETE", "", None),
        ("PUT", "/pause", {"paused": True}),
        ("GET", "/completeness", None),
    ],
)
def test_an_unknown_follow_is_a_404(
    v1_client: ClientFactory, method: str, suffix: str, body: dict[str, Any] | None
) -> None:
    """No follow answers the key: 404 ``acquisition.not_found`` naming it."""
    response = v1_client(role="admin").request(method, f"/acquisition/followed/tvdb:99{suffix}", json=body)

    assert response.status_code == 404
    assert response.json()["code"] == "acquisition.not_found"
    assert response.json()["params"] == {"followedId": "tvdb:99"}


@pytest.mark.parametrize("key", ["silo", "plex:1", "tvdb:abc", "tvdb:", "tvdb:0"])
def test_a_malformed_key_is_a_400_naming_the_field(v1_client: ClientFactory, key: str) -> None:
    """The path's key is ``<provider>:<providerId>``: anything else is ``request.invalid`` on ``followedId``."""
    response = v1_client().delete(f"/acquisition/followed/{key}")

    assert response.status_code == 400
    assert response.json()["code"] == "request.invalid"
    assert response.json()["params"]["fields"] == ["followedId"]


def test_a_body_that_is_not_the_contracts_is_a_400(v1_client: ClientFactory) -> None:
    """A missing required field or a property the contract does not name: ``request.invalid``."""
    client = v1_client()

    missing = client.put(f"/acquisition/followed/{SILO_KEY}/pause", json={})
    extra = client.put(f"/acquisition/followed/{SILO_KEY}/pause", json={"paused": True, "since": "hier"})

    assert (missing.status_code, extra.status_code) == (400, 400)


# ── who reads what ──────────────────────────────────────────────────────────


def test_a_read_is_filtered_on_membership_never_refused(v1_client: ClientFactory) -> None:
    """An account that did not ask for a follow reads a 200 without it: the follow is not its to see."""
    owner, stranger = v1_client(), v1_client(role="requester")
    _follow(owner)

    assert _titles(stranger) == []
    assert _titles(owner) == ["Silo"]


def test_the_right_to_see_others_lifts_the_filter(v1_client: ClientFactory) -> None:
    """``acquisition.see.others`` (the Admin holds it) reads every follow, requesters included."""
    owner, admin = v1_client(), v1_client(role="admin")
    followed = _follow(owner)

    follows = admin.get("/acquisition/followed").json()

    assert [one["title"] for one in follows] == ["Silo"]
    assert follows[0]["requesters"] == followed["requesters"]
    assert follows[0]["ownPaused"] is False


def test_pilot_any_does_not_lift_the_filter(v1_client: ClientFactory) -> None:
    """``acquisition.pilot.any`` is the acts' scope, not the reads': a pilot reads only what it asked for."""
    owner = v1_client()
    pilot = v1_client(
        rights=frozenset({Right.ACQUISITION_REQUEST, Right.ACQUISITION_FOLLOW, Right.ACQUISITION_PILOT_ANY})
    )
    _follow(owner)

    assert _titles(pilot) == []


def test_the_completeness_of_a_follow_that_is_not_the_callers_is_a_404(v1_client: ClientFactory) -> None:
    """A filtered read: the follow another account asked for does not exist for the caller."""
    owner, stranger = v1_client(), v1_client(role="requester")
    _follow(owner)

    response = stranger.get(f"/acquisition/followed/{SILO_KEY}/completeness")

    assert response.status_code == 404
    assert response.json()["code"] == "acquisition.not_found"


def test_the_readers_own_settings_are_its_own(v1_client: ClientFactory) -> None:
    """``ownPaused`` and ``ownQuality`` are the caller's: a see-others reader that asked for nothing reads none."""
    owner, admin = v1_client(), v1_client(role="admin")
    _follow(owner)
    owner.put(f"/acquisition/followed/{SILO_KEY}/pause", json={"paused": True})

    (as_admin,) = admin.get("/acquisition/followed").json()
    (as_owner,) = owner.get("/acquisition/followed").json()

    assert (as_owner["ownPaused"], as_owner["paused"]) == (True, True)
    assert (as_admin["ownPaused"], as_admin["paused"]) == (False, True)
