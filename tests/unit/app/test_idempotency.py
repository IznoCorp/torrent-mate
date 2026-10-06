"""Unit tests for ``personalscraper.app.idempotency`` — a write's first answer, kept per (account, key, operation).

A claimed key is applied once: its answer is stored, a replay of the same request reads
it back, the same key with another request is refused, and a key still running is refused
to a concurrent duplicate. The rows are swept past their retention; a claim abandoned by a
crash is taken over once it is stale; a claim whose request failed is released.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.errors import AppConflict, RefusalCode
from personalscraper.app.idempotency.service import Claimed, IdempotencyService, Replay
from personalscraper.app.store.store import AppStore

_ACCOUNT = "account-one"
_OTHER_ACCOUNT = "account-two"
_KEY = "key-1"
_OPERATION = "POST /accounts"


class _Clock:
    """A settable epoch clock."""

    def __init__(self, now: float = 1_000_000.0) -> None:
        """Start at a fixed instant.

        Args:
            now: The starting epoch.
        """
        self.now = now

    def __call__(self) -> float:
        """Read the clock.

        Returns:
            The current epoch.
        """
        return self.now


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db`` on ``tmp_path``.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    app_store = AppStore(tmp_path / "app.db")
    try:
        yield app_store
    finally:
        app_store.close()


@pytest.fixture
def clock() -> _Clock:
    """A settable clock.

    Returns:
        The clock.
    """
    return _Clock()


@pytest.fixture
def service(store: AppStore, clock: _Clock) -> IdempotencyService:
    """The service over the fresh store, a one-hour retention and a one-minute pending limit.

    Args:
        store: The fresh store.
        clock: The settable clock.

    Returns:
        The service.
    """
    return IdempotencyService(store, retention_s=3600.0, pending_s=60.0, clock=clock)


def _claim(service: IdempotencyService, *, account: str = _ACCOUNT, fingerprint: str = "f1") -> Claimed | Replay:
    """Claim the test key for one account.

    Args:
        service: The service.
        account: The account claiming.
        fingerprint: The request's fingerprint.

    Returns:
        What the service answered.
    """
    return service.claim(account, _KEY, _OPERATION, fingerprint)


class TestFirstAndReplay:
    """The first request applies; a replay reads its answer back."""

    def test_a_new_key_is_claimed(self, service: IdempotencyService) -> None:
        """A key never seen is the caller's to apply."""
        assert isinstance(_claim(service), Claimed)

    def test_a_completed_key_replays_its_answer(self, service: IdempotencyService) -> None:
        """The same request with the same key answers the stored status, body and type."""
        claim = _claim(service)
        assert isinstance(claim, Claimed)
        service.complete(claim, 201, b'{"id":"x"}', "application/json")
        replay = _claim(service)
        assert replay == Replay(status=201, body=b'{"id":"x"}', content_type="application/json")

    def test_the_same_key_with_another_request_is_refused(self, service: IdempotencyService) -> None:
        """A key reused on a different request is refused ``request.key_reused``."""
        claim = _claim(service)
        assert isinstance(claim, Claimed)
        service.complete(claim, 200, b"{}", "application/json")
        with pytest.raises(AppConflict) as refused:
            _claim(service, fingerprint="f2")
        assert refused.value.code is RefusalCode.REQUEST_KEY_REUSED

    def test_a_key_is_scoped_to_its_account(self, service: IdempotencyService) -> None:
        """Another account's same key is its own: never handed the first account's answer."""
        claim = _claim(service)
        assert isinstance(claim, Claimed)
        service.complete(claim, 200, b'{"secret":1}', "application/json")
        assert isinstance(_claim(service, account=_OTHER_ACCOUNT), Claimed)

    def test_a_key_is_scoped_to_its_operation(self, service: IdempotencyService) -> None:
        """The same key on another method and path is another record."""
        claim = _claim(service)
        assert isinstance(claim, Claimed)
        service.complete(claim, 200, b"{}", "application/json")
        assert isinstance(service.claim(_ACCOUNT, _KEY, "DELETE /roles/r1", "f1"), Claimed)


class TestInFlight:
    """A key whose first request has not answered yet."""

    def test_a_duplicate_of_a_running_key_is_refused(self, service: IdempotencyService) -> None:
        """While the first runs, the same request is refused ``request.in_progress``, never applied."""
        assert isinstance(_claim(service), Claimed)
        with pytest.raises(AppConflict) as refused:
            _claim(service)
        assert refused.value.code is RefusalCode.REQUEST_IN_PROGRESS

    def test_concurrent_claims_grant_the_key_once(self, service: IdempotencyService) -> None:
        """Eight threads claiming one key at once: exactly one is granted it."""
        granted: list[Claimed | Replay] = []
        refused: list[AppConflict] = []
        start = threading.Barrier(8)

        def contend() -> None:
            """Claim the key once the others are ready."""
            start.wait()
            try:
                granted.append(_claim(service))
            except AppConflict as conflict:
                refused.append(conflict)

        threads = [threading.Thread(target=contend) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(granted) == 1
        assert len(refused) == 7

    def test_a_released_claim_is_claimed_again(self, service: IdempotencyService) -> None:
        """A request that failed (a 5xx) leaves nothing stored: the retry applies."""
        claim = _claim(service)
        assert isinstance(claim, Claimed)
        service.release(claim)
        assert isinstance(_claim(service), Claimed)

    def test_a_stale_claim_is_taken_over(self, service: IdempotencyService, clock: _Clock) -> None:
        """A claim left running past the pending limit (a crashed process) is the next caller's."""
        assert isinstance(_claim(service), Claimed)
        clock.now += 61.0
        assert isinstance(_claim(service), Claimed)

    def test_a_taken_over_claim_cannot_complete(self, service: IdempotencyService, clock: _Clock) -> None:
        """The abandoned claim's late answer never overwrites its successor's."""
        stale = _claim(service)
        assert isinstance(stale, Claimed)
        clock.now += 61.0
        fresh = _claim(service)
        assert isinstance(fresh, Claimed)
        service.complete(stale, 500, b"late", "application/json")
        service.complete(fresh, 200, b"fresh", "application/json")
        assert _claim(service) == Replay(status=200, body=b"fresh", content_type="application/json")


class TestRetention:
    """The records are kept a bounded time."""

    def test_a_record_past_retention_is_swept(
        self, service: IdempotencyService, store: AppStore, clock: _Clock
    ) -> None:
        """Past the retention, a record is deleted and its key is new again."""
        claim = _claim(service)
        assert isinstance(claim, Claimed)
        service.complete(claim, 200, b"{}", "application/json")
        clock.now += 3601.0
        other = service.claim(_OTHER_ACCOUNT, "another", _OPERATION, "f9")
        assert isinstance(other, Claimed)
        assert store.idempotency.count() == 1
        assert isinstance(_claim(service, fingerprint="f2"), Claimed)

    def test_a_record_within_retention_is_kept(self, service: IdempotencyService, clock: _Clock) -> None:
        """Just inside the retention, the replay still answers."""
        claim = _claim(service)
        assert isinstance(claim, Claimed)
        service.complete(claim, 204, b"", None)
        clock.now += 3599.0
        assert _claim(service) == Replay(status=204, body=b"", content_type=None)
