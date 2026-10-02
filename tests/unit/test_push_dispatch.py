"""Unit tests for ``personalscraper.push.dispatch`` — the per-account fan-out, with a fake sender."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from personalscraper.api.notify.fcm import PushMessage, PushOutcome, PushResult, classify
from personalscraper.app.store.store import build_app_store
from personalscraper.conf.models.config import Config
from personalscraper.push.dispatch import PushDispatcher
from personalscraper.push.store import SqlitePushSubscriptionStore

SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "reference" / "_samples" / "fcm"
MESSAGE = PushMessage(code="tracker.ratio_low", params={"tracker": "c411"}, link="/trackers/c411")


class _Sender:
    """Answers each token with a scripted result and records what it was asked."""

    def __init__(self, answers: dict[str, PushResult]) -> None:
        """Builds the fake.

        Args:
            answers: Token → result.
        """
        self.answers = answers
        self.sent: list[str] = []

    def send(self, token: str, message: PushMessage, *, validate_only: bool = False) -> PushResult:
        """Records the send and answers.

        Args:
            token: The token.
            message: The message.
            validate_only: Ignored.

        Returns:
            The scripted result.
        """
        self.sent.append(token)
        return self.answers[token]


@pytest.fixture
def store(test_config: Config, tmp_path: Path) -> Iterator[SqlitePushSubscriptionStore]:
    """A store holding four devices of alice and one of bob, from an ``AppStore`` on ``tmp_path``.

    Args:
        test_config: The synthetic Config fixture.
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    cfg = test_config.model_copy(update={"paths": test_config.paths.model_copy(update={"data_dir": tmp_path})})
    app_store = build_app_store(cfg)
    store = app_store.push
    for token in ("t1", "t2", "t3", "t4"):
        store.upsert(account_id="alice", token=token, platform="ios", user_agent=None, now=1.0)
    store.upsert(account_id="bob", token="b1", platform="android", user_agent=None, now=1.0)
    try:
        yield store
    finally:
        app_store.close()


def _run(store: SqlitePushSubscriptionStore, answers: dict[str, PushResult]):
    """Dispatches the message to alice.

    Args:
        store: The store.
        answers: Token → result.

    Returns:
        ``(report, sender)``.
    """
    sender = _Sender(answers)
    return PushDispatcher(sender, store, clock=lambda: 50.0).notify_account("alice", MESSAGE), sender


def test_fan_out_reaches_every_live_device_of_the_account_only(store: SqlitePushSubscriptionStore) -> None:
    """Four devices of alice, one send each; bob's device untouched; each outcome recorded."""
    ok = PushResult(PushOutcome.DELIVERED)
    report, sender = _run(store, {t: ok for t in ("t1", "t2", "t3", "t4")})
    assert sender.sent == ["t1", "t2", "t3", "t4"]
    assert (report.delivered, report.revoked, report.deferred, report.failed) == (4, 0, 0, 0)
    assert all(s.last_outcome == "delivered" and s.last_sent_at == 50.0 for s in store.live_for("alice"))
    assert store.live_for("bob")[0].last_sent_at is None


def test_a_dead_token_is_revoked_and_the_others_still_served(store: SqlitePushSubscriptionStore) -> None:
    """``token_dead`` revokes that subscription only."""
    ok, dead = PushResult(PushOutcome.DELIVERED), PushResult(PushOutcome.TOKEN_DEAD, fcm_error="UNREGISTERED")
    report, _ = _run(store, {"t1": ok, "t2": dead, "t3": ok, "t4": ok})
    assert (report.delivered, report.revoked) == (3, 1)
    assert [s.token for s in store.live_for("alice")] == ["t1", "t3", "t4"]


def test_misconfigured_stops_the_fan_out(store: SqlitePushSubscriptionStore) -> None:
    """Our credentials are wrong: no point trying the other devices; the channel is reported broken."""
    bad = PushResult(PushOutcome.MISCONFIGURED, fcm_error="THIRD_PARTY_AUTH_ERROR")
    report, sender = _run(store, {"t1": PushResult(PushOutcome.DELIVERED), "t2": bad})
    assert sender.sent == ["t1", "t2"]
    assert report.misconfigured is True and report.failed == 1 and report.delivered == 1
    assert len(store.live_for("alice")) == 4, "a channel fault never revokes a device"


def test_a_quota_stops_and_defers_the_rest(store: SqlitePushSubscriptionStore) -> None:
    """QUOTA_EXCEEDED is the project's: the untried devices are deferred behind the same back-off."""
    quota = PushResult(PushOutcome.QUOTA_EXCEEDED, retry_after_seconds=120.0, fcm_error="QUOTA_EXCEEDED")
    report, sender = _run(store, {"t1": quota})
    assert sender.sent == ["t1"]
    assert report.deferred == 4 and report.retry_after_seconds == 120.0


class _Answer:
    """An FCM answer, enough for ``classify``."""

    def __init__(self, status: int, body: Any) -> None:
        """Builds the answer.

        Args:
            status: HTTP status.
            body: JSON body.
        """
        self.status_code = status
        self.headers: dict[str, str] = {}
        self._body = body

    def json(self) -> Any:
        """Returns the JSON body."""
        return self._body


def test_a_429_without_an_fcm_detail_stops_the_fan_out(store: SqlitePushSubscriptionStore) -> None:
    """Google's bare ``RESOURCE_EXHAUSTED`` is the project's quota too: classified once, the rest deferred."""
    answer = _Answer(429, {"error": {"code": 429, "message": "Quota exceeded.", "status": "RESOURCE_EXHAUSTED"}})
    report, sender = _run(store, {t: classify(answer) for t in ("t1", "t2", "t3", "t4")})  # type: ignore[arg-type]
    assert sender.sent == ["t1"]
    assert report.deferred == 4 and report.retry_after_seconds == 60.0


def test_a_sender_id_mismatch_revokes_nothing_and_stops(store: SqlitePushSubscriptionStore) -> None:
    """ONE Firebase project (F-2): a mismatch is our misconfiguration, never four dead tokens."""
    raw = json.loads((SAMPLES / "sender-id-mismatch-403.json").read_text())
    result = classify(_Answer(raw["status"], raw["body"]))  # type: ignore[arg-type]
    report, sender = _run(store, {t: result for t in ("t1", "t2", "t3", "t4")})
    assert sender.sent == ["t1"]
    assert report.misconfigured is True and report.revoked == 0
    assert len(store.live_for("alice")) == 4


def test_a_device_deferral_does_not_stop_the_others(store: SqlitePushSubscriptionStore) -> None:
    """UNAVAILABLE for one device: the others are still tried, the longest back-off reported."""
    ok = PushResult(PushOutcome.DELIVERED)
    report, sender = _run(
        store,
        {
            "t1": PushResult(PushOutcome.RETRY_LATER, retry_after_seconds=30.0, fcm_error="UNAVAILABLE"),
            "t2": PushResult(PushOutcome.RETRY_LATER, retry_after_seconds=10.0, fcm_error="INTERNAL"),
            "t3": ok,
            "t4": ok,
        },
    )
    assert len(sender.sent) == 4
    assert (report.deferred, report.delivered, report.retry_after_seconds) == (2, 2, 30.0)


def test_nothing_is_retried_inside(store: SqlitePushSubscriptionStore) -> None:
    """One send per device, whatever the answer (NE-DOIT-PAS-8)."""
    answers = {
        "t1": PushResult(PushOutcome.UNREACHABLE),
        "t2": PushResult(PushOutcome.REJECTED, fcm_error="INVALID_ARGUMENT"),
        "t3": PushResult(PushOutcome.RETRY_LATER, fcm_error="UNAVAILABLE"),
        "t4": PushResult(PushOutcome.DELIVERED),
    }
    report, sender = _run(store, answers)
    assert sorted(sender.sent) == ["t1", "t2", "t3", "t4"]
    assert (report.failed, report.deferred, report.delivered) == (2, 1, 1)
    counts = {s.token: s.failure_count for s in store.live_for("alice")}
    assert counts == {"t1": 1, "t2": 1, "t3": 0, "t4": 0}


def test_an_account_without_devices_sends_nothing(store: SqlitePushSubscriptionStore) -> None:
    """No subscription, no send, an empty report."""
    sender = _Sender({})
    report = PushDispatcher(sender, store).notify_account("carol", MESSAGE)
    assert sender.sent == [] and report.delivered == report.failed == 0 and not report.misconfigured
