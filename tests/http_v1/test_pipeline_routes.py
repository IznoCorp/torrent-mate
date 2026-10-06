"""``runPipeline``: ``POST /pipeline/run`` queues a run through the in-process service."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right
from personalscraper.app.supervisor.model import RunTrigger
from personalscraper.app.supervisor.service import RunAsked


def test_a_run_is_asked_and_answers_queued_with_its_uid(v1_client: Callable[..., TestClient]) -> None:
    """The ask is queued, never run in the process: 200 ``queued`` and the request's uid."""
    client = v1_client(rights=frozenset({Right.PIPELINE_CONTROL}))

    response = client.post("/pipeline/run")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "queued"
    assert isinstance(body["uid"], str) and body["uid"]


def test_asking_twice_joins_the_waiting_request(v1_client: Callable[..., TestClient]) -> None:
    """An equal ask waiting in the queue answers the second one: the same uid comes back."""
    client = v1_client(rights=frozenset({Right.PIPELINE_CONTROL}))

    first = client.post("/pipeline/run")
    second = client.post("/pipeline/run")

    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json() == first.json()


def test_without_pipeline_control_it_is_forbidden(v1_client: Callable[..., TestClient]) -> None:
    """A role without the right: 403 ``right.missing`` naming ``pipeline.control``."""
    response = v1_client(rights=frozenset({Right.LIBRARY_READ})).post("/pipeline/run")

    assert response.status_code == 403
    assert response.json()["code"] == "right.missing"
    assert response.json()["params"] == {"rights": ["pipeline.control"]}


def test_without_a_session_is_auth_required(v1_client: Callable[..., TestClient]) -> None:
    """No session: 401 ``auth.required``."""
    assert v1_client(role=None).post("/pipeline/run").status_code == 401


def test_the_read_only_instance_refuses_it_even_to_an_admin(v1_client: Callable[..., TestClient]) -> None:
    """Under the read-only ceiling every write is refused, the Admin's too, and nothing is queued."""
    ceiling = InstanceCeiling(forbidden=WRITE_RIGHTS, read_only=True)

    response = v1_client(role="admin", ceiling=ceiling).post("/pipeline/run")

    assert response.status_code == 403
    assert response.json()["code"] == "instance.forbidden_write"
    assert response.json()["params"]["right"] == "pipeline.control"


def test_the_stored_request_is_a_web_one(v1_client: Callable[..., TestClient]) -> None:
    """The route asks as the web: the request left in the queue carries the ``WEB`` trigger."""
    client = v1_client(rights=frozenset({Right.PIPELINE_CONTROL}))

    uid = client.post("/pipeline/run").json()["uid"]

    queued = client.app.state.services.runs.queue_view().queued  # type: ignore[attr-defined]
    assert [(request.uid, request.trigger) for request in queued] == [(uid, RunTrigger.WEB)]


def test_the_answer_carries_the_state_of_the_request_that_answers(
    v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A joined request already running answers ``running`` with its own uid, not a hard-coded ``queued``.

    The route's own ask never promises a uid, so the service answers ``running`` to it only through a
    seam; the stub stands for that answer and shows the route passes the state through.
    """
    client = v1_client(rights=frozenset({Right.PIPELINE_CONTROL}))
    runs: Any = client.app.state.services.runs  # type: ignore[attr-defined]
    monkeypatch.setattr(runs, "ask_run", lambda *_a, **_k: RunAsked(uid="joined-uid", state="running", joined=True))

    body = client.post("/pipeline/run").json()

    assert body == {"state": "running", "uid": "joined-uid"}
