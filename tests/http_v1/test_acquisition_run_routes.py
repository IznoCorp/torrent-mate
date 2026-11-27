"""The runs' routes: the five operations of K3 P13 over the real services, end to end.

``searchForFollow``, ``grabForFollow`` and ``runDetection`` answer 202 with the queued request's uid —
twice the same, never a 409 for « busy »; ``grabSeasonForFollow`` answers 201, then 200 ``reused``,
and an owned show nobody follows gets a one-off request, never a follow; ``readAcquisitionStatus``
answers the schedule. What each act does is proved in ``tests/unit/app/acquisition``; these tests
hold the wire: the bodies, the statuses and ``Problem`` codes, the rights, the instance ceiling and
the own scope.

The services are the composed ones over the synthetic config, as in ``test_acquisition_routes``; only
the library's owned shows are faked (``IndexedShows.held_show``), so no ``library.db`` is read.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from personalscraper.acquire.domain import WantedCandidate, WantedItem
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right
from personalscraper.app.acquisition.releases import release_handle
from personalscraper.app.acquisition.seasons import HeldShow, IndexedShows
from personalscraper.app.supervisor.model import (
    AcquisitionJob,
    JobKind,
    Lane,
    RunKind,
    RunOptions,
    RunRequest,
    RunTrigger,
    Settlement,
)
from personalscraper.conf.environment import Environment
from personalscraper.core.identity import MediaRef

ClientFactory = Callable[..., TestClient]

SILO: dict[str, Any] = {"title": "Silo", "kind": "show", "year": 2023, "provider": "tvdb", "providerId": 403245}
SILO_KEY = "tvdb:403245"
OWNED_KEY = "tvdb:4242"

#: The five operations as the interface calls them.
_CALLS: list[tuple[str, str]] = [
    ("POST", "/acquisition/detect"),
    ("POST", f"/acquisition/followed/{SILO_KEY}/search"),
    ("POST", f"/acquisition/followed/{SILO_KEY}/grab"),
    ("POST", f"/acquisition/follows/{SILO_KEY}/seasons/1/grab"),
    ("GET", "/acquisition/status"),
]
_WRITES = [call for call in _CALLS if call[0] != "GET"]


def _services(client: TestClient) -> Any:
    """The services a client's application runs on.

    Args:
        client: A client.

    Returns:
        The ``AppServices``.
    """
    return client.app.state.services  # type: ignore[attr-defined]


def _queued(client: TestClient) -> list[tuple[str, AcquisitionJob]]:
    """The acquisition requests waiting.

    Args:
        client: A client.

    Returns:
        ``(uid, job)`` each, oldest first.
    """
    runs = _services(client).app_store.runs
    return [(str(one.uid), one.job) for one in runs.queued(Lane.ACQUISITION)]


def _jobs(client: TestClient, kind: JobKind) -> list[tuple[str, AcquisitionJob]]:
    """The waiting requests of one pass.

    Args:
        client: A client.
        kind: The pass.

    Returns:
        ``(uid, job)`` each.
    """
    return [one for one in _queued(client) if one[1].kind is kind]


def _follow(client: TestClient) -> None:
    """Follow :data:`SILO`.

    Args:
        client: A signed-in client.
    """
    response = client.post("/acquisition/followed", json=SILO)
    assert response.status_code == 200, response.text


def _offer(client: TestClient, title: str, status: str = "available") -> tuple[int, str]:
    """Store one release found for an episode of the one follow.

    Args:
        client: A client of the services holding the follow.
        title: The release's name.
        status: The status the episode's row stands in.

    Returns:
        The wanted row and the release's handle.
    """
    open_store = _services(client).acquisition.triggers._open_store
    store = open_store()
    try:
        (row,) = store.follow.find_all_by_ref(MediaRef(tvdb_id=403245), kind="show")
        wanted_id = store.wanted.add(
            WantedItem(
                media_ref=row.media_ref,
                kind="episode",
                status=status,  # type: ignore[arg-type]
                enqueued_at=1_700_000_000,
                followed_id=row.id,
                season=1,
                episode=1,
            )
        )
        candidate = WantedCandidate(
            rank=1,
            provider="c411",
            title=title,
            info_hash="a" * 40,
            size_bytes=1,
            seeders=1,
            resolution=None,
            source=None,
            language=None,
            score=1,
            season=1,
            episode=1,
            searched_at=1,
        )
        store.candidates.replace(wanted_id, [candidate])
    finally:
        store.close()
    return wanted_id, release_handle(wanted_id, candidate)


@pytest.fixture
def owned_show(monkeypatch: pytest.MonkeyPatch) -> None:
    """The library owns :data:`OWNED_KEY` (season 1 aired 1–3, episode 1 held), nobody follows it.

    Args:
        monkeypatch: pytest's patcher.
    """
    held = HeldShow(
        title="Owned Show",
        year=2020,
        ref=MediaRef(tvdb_id=4242),
        aired=frozenset({(1, 1), (1, 2), (1, 3)}),
        owned=frozenset({(1, 1)}),
    )
    monkeypatch.setattr(IndexedShows, "held_show", lambda self, ref: held if ref.tvdb_id == 4242 else None)


# ── the five operations, each as the contract writes it ─────────────────────


def test_a_detection_is_queued_and_asked_twice_answers_one_run(v1_client: ClientFactory) -> None:
    """``runDetection``: 202 ``{runUid}``, the queued request's uid; asked again, the same, never 409."""
    client = v1_client(role="admin")

    first, second = client.post("/acquisition/detect"), client.post("/acquisition/detect")

    assert (first.status_code, second.status_code) == (202, 202)
    ((uid, job),) = _queued(client)
    assert (first.json(), second.json()) == ({"runUid": uid}, {"runUid": uid})
    assert job == AcquisitionJob(JobKind.DETECT)


def test_a_search_is_answered_en_file_with_the_runs_uid(v1_client: ClientFactory) -> None:
    """``searchForFollow`` (O-6 B): 202 ``{queued: true, runUid}``, no result in the answer; twice, one run."""
    client = v1_client()
    _follow(client)
    path = f"/acquisition/followed/{SILO_KEY}/search"

    first, second = client.post(path), client.post(path)

    assert (first.status_code, second.status_code) == (202, 202)
    ((uid, _),) = _jobs(client, JobKind.SEARCH)
    assert first.json() == second.json() == {"queued": True, "runUid": uid}


def test_a_grab_is_queued_and_asked_twice_answers_one_run(v1_client: ClientFactory) -> None:
    """``grabForFollow`` with no body: 202 ``{runUid}``, a grab of the follow naming no release."""
    client = v1_client()
    _follow(client)
    path = f"/acquisition/followed/{SILO_KEY}/grab"

    first, second = client.post(path), client.post(path, json={})

    assert (first.status_code, second.status_code) == (202, 202)
    ((uid, job),) = _jobs(client, JobKind.GRAB)
    assert first.json() == second.json() == {"runUid": uid}
    assert (job.release, job.wanted_id) == (None, None)


def test_a_chosen_release_goes_on_the_job_with_its_row(v1_client: ClientFactory) -> None:
    """``releaseId``: the job carries the release's name and the wanted row it was chosen on."""
    client = v1_client()
    _follow(client)
    wanted_id, handle = _offer(client, "Silo S01E01 1080p-AAA")

    response = client.post(f"/acquisition/followed/{SILO_KEY}/grab", json={"releaseId": handle})

    assert response.status_code == 202
    ((uid, job),) = _jobs(client, JobKind.GRAB)
    assert response.json() == {"runUid": uid}
    assert (job.release, job.wanted_id) == ("Silo S01E01 1080p-AAA", wanted_id)


def test_a_release_no_stored_set_holds_is_a_400_naming_it(v1_client: ClientFactory) -> None:
    """A handle that names nothing: ``request.invalid`` on ``releaseId``, nothing queued."""
    client = v1_client()
    _follow(client)

    response = client.post(f"/acquisition/followed/{SILO_KEY}/grab", json={"releaseId": "1:0000000000000000"})

    assert response.status_code == 400
    assert (response.json()["code"], response.json()["params"]) == ("request.invalid", {"fields": ["releaseId"]})
    assert _jobs(client, JobKind.GRAB) == []


@pytest.mark.parametrize("status", ["pending", "searching", "grabbed", "done", "abandoned"])
def test_a_pick_on_an_unavailable_row_is_a_409_and_queues_nothing(v1_client: ClientFactory, status: str) -> None:
    """A pick the row cannot honour is refused at ask time (O-14): ``acquisition.release_unavailable``, never a 202."""
    client = v1_client()
    _follow(client)
    _, handle = _offer(client, "Silo S01E01 1080p-AAA", status)

    response = client.post(f"/acquisition/followed/{SILO_KEY}/grab", json={"releaseId": handle})

    assert (response.status_code, response.json().get("code")) == (409, "acquisition.release_unavailable")
    assert response.json()["params"] == {"followedId": SILO_KEY}
    assert _jobs(client, JobKind.GRAB) == []


@pytest.mark.parametrize("act", ["search", "grab"])
def test_two_rows_under_one_key_are_a_409_and_queue_nothing(v1_client: ClientFactory, act: str) -> None:
    """Two rows hold the key: ``follow.ambiguous``, no pass asked of either."""
    client = v1_client(role="admin")
    _follow(client)
    store = _services(client).acquisition.triggers._open_store()
    try:
        with store.follow._conn as conn:
            conn.execute(
                "INSERT INTO followed_series (media_ref_json, title, active, added_at, kind) VALUES (?, ?, 1, 1, ?)",
                (json.dumps({"tvdb_id": 403245, "tmdb_id": 1, "imdb_id": None}), "Silo again", "show"),
            )
    finally:
        store.close()
    before = _queued(client)

    response = client.post(f"/acquisition/followed/{SILO_KEY}/{act}")

    assert (response.status_code, response.json()["code"]) == (409, "follow.ambiguous")
    assert _queued(client) == before


def test_a_release_named_by_its_name_is_not_the_contracts_body(v1_client: ClientFactory) -> None:
    """``releaseName`` is gone from the contract: the body names a handle."""
    client = v1_client()
    _follow(client)

    response = client.post(f"/acquisition/followed/{SILO_KEY}/grab", json={"releaseName": "Silo"})

    assert response.status_code == 400


def test_a_season_is_taken_201_then_reused_200(v1_client: ClientFactory) -> None:
    """``grabSeasonForFollow``: 201 with the prime's uid, then 200 ``reused``, nothing more queued."""
    client = v1_client()
    _follow(client)
    path = f"/acquisition/follows/{SILO_KEY}/seasons/1/grab"

    first, second = client.post(path), client.post(path)

    assert first.status_code == 201, first.text
    body = first.json()
    # ``queued`` means WAITING on the pipeline, which no acquisition pass does: its own lane takes no lock.
    assert (body["season"], body["queued"], body["reused"], body["absorbedCount"]) == (1, False, False, 0)
    assert body["runUid"] in [uid for uid, _ in _jobs(client, JobKind.PRIME)]
    assert second.status_code == 200, second.text
    assert second.json() == {"season": 1, "absorbedCount": 0, "queued": False, "runUid": None, "reused": True}


def test_an_owned_unfollowed_show_gets_a_request_never_a_follow(v1_client: ClientFactory, owned_show: None) -> None:
    """A season of an owned show nobody follows: 201, a one-off request, and ``readFollows`` lists nothing."""
    client = v1_client()

    response = client.post(f"/acquisition/follows/{OWNED_KEY}/seasons/1/grab")

    assert response.status_code == 201, response.text
    assert (response.json()["queued"], response.json()["absorbedCount"]) == (False, 2)
    assert client.get("/acquisition/followed").json() == []
    assert len(_jobs(client, JobKind.PRIME)) == 1


def test_a_season_of_a_medium_neither_followed_nor_owned_is_a_404(v1_client: ClientFactory, owned_show: None) -> None:
    """Nothing answers the key: 404 ``acquisition.not_found``."""
    response = v1_client().post("/acquisition/follows/tvdb:99/seasons/1/grab")

    assert (response.status_code, response.json()["code"]) == (404, "acquisition.not_found")


@pytest.mark.parametrize(
    ("season", "field"),
    [("0", "season"), ("-1", "season"), ("deux", "path.season"), ("10000", "season"), (str(2**63), "season")],
)
def test_a_season_that_is_not_one_is_a_400(v1_client: ClientFactory, season: str, field: str) -> None:
    """A season is numbered from 1 to 9999: ``request.invalid`` naming it, as the service or the path's parsing does."""
    response = v1_client().post(f"/acquisition/follows/{SILO_KEY}/seasons/{season}/grab")

    assert (response.status_code, response.json()["code"]) == (400, "request.invalid")
    assert response.json()["params"]["fields"] == [field]


def test_the_status_answers_the_cadence_and_the_next_search(v1_client: ClientFactory) -> None:
    """``readAcquisitionStatus``: 200 ``{cadence, nextSearch, runState}``, for any signed-in account."""
    response = v1_client(rights=frozenset({Right.LIBRARY_READ})).get("/acquisition/status")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"cadence", "nextSearch", "runState"}
    assert len(body["cadence"].split()) == 5


def test_the_last_season_number_is_still_a_season(v1_client: ClientFactory) -> None:
    """9999 holds the year-numbered seasons: taken like any other."""
    client = v1_client()
    _follow(client)

    response = client.post(f"/acquisition/follows/{SILO_KEY}/seasons/9999/grab")

    assert response.status_code == 201, response.text


def test_the_status_sends_the_schedule_it_is_given(v1_client: ClientFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole body, on a pinned environment and clock: the cadence AND the next search reach the wire."""
    client = v1_client()
    triggers = _services(client).acquisition.triggers
    monkeypatch.setattr(triggers, "_environment", lambda: Environment.PROD)
    noon = datetime(2026, 11, 27, 12, 0)
    monkeypatch.setattr(triggers, "_clock", noon.timestamp)

    response = client.get("/acquisition/status")

    assert response.json() == {
        "cadence": "20 3,15 * * *",
        "nextSearch": datetime(2026, 11, 27, 15, 10).astimezone().isoformat(),
        "runState": None,
    }


def test_the_status_follows_the_run_asked_until_it_settles(v1_client: ClientFactory) -> None:
    """``runUid``: queued, then running, then settled, read from the supervisor's queue (O-6 B)."""
    client = v1_client()
    _follow(client)
    uid = client.post(f"/acquisition/followed/{SILO_KEY}/search").json()["runUid"]
    runs = _services(client).app_store.runs

    def state() -> str | None:
        """The run's state as the status answers it."""
        answered: str | None = client.get("/acquisition/status", params={"runUid": uid}).json()["runState"]
        return answered

    assert state() == "queued"
    request = runs.get(uid)
    request.admit(None, 1.0)
    with _services(client).app_store.immediate():
        runs.save(request)
    assert state() == "running"
    request.settle(Settlement.SUCCESS, 2.0)
    with _services(client).app_store.immediate():
        runs.save(request)
    assert state() == "settled"


def test_a_uid_naming_no_acquisition_run_has_no_state(v1_client: ClientFactory) -> None:
    """An unknown uid, or the uid of a run that is not an acquisition's: ``runState`` null."""
    client = v1_client(role="admin")
    actor_run = RunRequest.ask(RunKind.PIPELINE, RunTrigger.WEB, RunOptions(), AccountId("someone"), 1.0)
    with _services(client).app_store.immediate():
        _services(client).app_store.runs.insert(actor_run)

    for uid in ("nothing", str(actor_run.uid)):
        response = client.get("/acquisition/status", params={"runUid": uid})
        assert (response.status_code, response.json()["runState"]) == (200, None), uid


# ── what is refused, and to whom ────────────────────────────────────────────


@pytest.mark.parametrize(("method", "path"), _CALLS)
def test_without_a_session_every_operation_is_401(v1_client: ClientFactory, method: str, path: str) -> None:
    """No session: 401 ``auth.required``."""
    response = v1_client(role=None).request(method, path)

    assert (response.status_code, response.json()["code"]) == (401, "auth.required")


@pytest.mark.parametrize(("method", "path"), _WRITES)
def test_without_its_right_an_ask_is_403_naming_the_right(v1_client: ClientFactory, method: str, path: str) -> None:
    """A role holding only ``library.read`` asks no pass: ``right.missing``."""
    client = v1_client(rights=frozenset({Right.LIBRARY_READ}))

    response = client.request(method, path)

    assert (response.status_code, response.json()["code"]) == (403, "right.missing")
    assert _queued(client) == []


@pytest.mark.parametrize(
    ("path", "right"),
    [
        (_WRITES[0][1], "pipeline.control"),
        (_WRITES[1][1], "acquisition.pilot.any"),
        (_WRITES[2][1], "acquisition.pilot.any"),
        (_WRITES[3][1], "acquisition.pilot.any"),
    ],
)
def test_the_read_only_instance_refuses_every_ask_even_to_an_admin(
    v1_client: ClientFactory, path: str, right: str
) -> None:
    """Under the read-only ceiling: 403 ``instance.forbidden_write``, and nothing queued."""
    ceiling = InstanceCeiling(forbidden=WRITE_RIGHTS, read_only=True)
    client = v1_client(role="admin", ceiling=ceiling)

    response = client.post(path)

    assert (response.status_code, response.json()["code"]) == (403, "instance.forbidden_write")
    assert response.json()["params"]["right"] == right
    assert _queued(client) == []


@pytest.mark.parametrize("path", [call[1] for call in _WRITES[1:]])
def test_an_ask_on_a_follow_the_caller_did_not_ask_for_is_refused(v1_client: ClientFactory, path: str) -> None:
    """Own-scoped: 403 ``acquisition.not_requester`` naming the follow, and nothing queued beyond its prime."""
    owner = v1_client()
    stranger = v1_client(rights=frozenset({Right.ACQUISITION_PILOT_OWN}))
    _follow(owner)
    before = _queued(owner)

    response = stranger.post(path)

    assert (response.status_code, response.json()["code"]) == (403, "acquisition.not_requester")
    assert response.json()["params"] == {"followedId": SILO_KEY}
    assert _queued(owner) == before


@pytest.mark.parametrize("path", [f"/acquisition/followed/tvdb:99/{act}" for act in ("search", "grab")])
def test_an_unknown_follow_is_a_404(v1_client: ClientFactory, path: str) -> None:
    """No follow answers the key: 404 ``acquisition.not_found``."""
    response = v1_client(role="admin").post(path)

    assert (response.status_code, response.json()["code"]) == (404, "acquisition.not_found")


@pytest.mark.parametrize("suffix", ["followed/silo/search", "followed/silo/grab", "follows/silo/seasons/1/grab"])
def test_a_malformed_key_is_a_400_naming_the_field(v1_client: ClientFactory, suffix: str) -> None:
    """The path's key is ``<provider>:<providerId>``."""
    response = v1_client().post(f"/acquisition/{suffix}")

    assert response.status_code == 400
    assert response.json()["params"]["fields"] == ["followedId"]
