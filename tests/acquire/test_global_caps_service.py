"""Tests for global bandwidth caps at run start (O4/D5).

Covers :meth:`GrabOrchestrator.apply_global_caps` — the public method that
re-asserts global transfer limits from config on the torrent client — and the
service-level guarantee that :meth:`AcquisitionService.run` calls it exactly
once at run entry (D5: idempotent, self-healing re-assertion).

Mocking note: since Python 3.12 the runtime-checkable protocol
``isinstance`` check uses ``getattr_static``, which does NOT see MagicMock's
lazily-created attributes — a bare ``MagicMock`` FAILS the gate. Supported
clients are therefore plain stubs with ``apply_global_limits`` assigned as a
real (Mock) instance attribute, which ``getattr_static`` does see.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.orchestrator import GrabOrchestrator
from personalscraper.acquire.service import AcquisitionService, RunSummary
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api._contracts import ApiError
from personalscraper.conf.models.acquire import AcquireConfig, BandwidthConfig

# ── Helpers ────────────────────────────────────────────────────────────────────


class _StubClient:
    """Bare client stub; tests attach ``apply_global_limits`` per instance."""


def _supported_client() -> _StubClient:
    """Build a client stub that PASSES the GlobalRateLimiter runtime gate.

    Returns:
        A stub whose ``apply_global_limits`` is a ``MagicMock`` instance
        attribute — visible to ``getattr_static``, hence to the Python 3.12
        runtime-protocol ``isinstance`` check.
    """
    client = _StubClient()
    client.apply_global_limits = MagicMock()  # type: ignore[attr-defined]
    return client


def _orchestrator(client: object, bw: BandwidthConfig) -> GrabOrchestrator:
    """Build a GrabOrchestrator with mock deps around a given client + caps."""
    return GrabOrchestrator(
        tracker_registry=MagicMock(),
        torrent_client=client,  # type: ignore[arg-type]
        event_bus=MagicMock(),
        ranking=MagicMock(),
        bandwidth=bw,
    )


# ── GrabOrchestrator.apply_global_caps ─────────────────────────────────────────


def test_applies_global_caps_with_supported_client() -> None:
    """Caps configured + client supports GlobalRateLimiter → limits applied with config values."""
    client = _supported_client()
    bw = BandwidthConfig(global_down=5_000_000, global_up=1_000_000)
    orch = _orchestrator(client, bw)

    orch.apply_global_caps()

    client.apply_global_limits.assert_called_once_with(
        down_bytes_per_s=5_000_000,
        up_bytes_per_s=1_000_000,
    )


def test_noop_when_no_global_caps_configured() -> None:
    """Both global caps None → client never touched (D2: leave operator settings alone)."""
    client = _supported_client()
    bw = BandwidthConfig(global_down=None, global_up=None)
    orch = _orchestrator(client, bw)

    orch.apply_global_caps()

    client.apply_global_limits.assert_not_called()


def test_noop_when_client_none_or_unsupported() -> None:
    """Client None or lacking GlobalRateLimiter → no crash, nothing applied (D4/D5)."""
    bw = BandwidthConfig(global_down=5_000_000, global_up=None)

    # Client absent (search-only deployment) — must not crash.
    _orchestrator(None, bw).apply_global_caps()

    # Client present but NOT a GlobalRateLimiter (e.g. Transmission): the bare
    # stub has no apply_global_limits, so the runtime protocol gate fails.
    unsupported = _StubClient()
    _orchestrator(unsupported, bw).apply_global_caps()
    assert not hasattr(unsupported, "apply_global_limits")


def test_fail_soft_on_api_error() -> None:
    """ApiError from the client → warning logged, NO raise (D5: dead client never blocks the run)."""
    client = _supported_client()
    client.apply_global_limits.side_effect = ApiError(provider="qbittorrent", http_status=500, message="boom")  # type: ignore[attr-defined]
    bw = BandwidthConfig(global_down=5_000_000, global_up=1_000_000)
    orch = _orchestrator(client, bw)

    with patch("personalscraper.acquire.orchestrator.log") as mock_log:
        orch.apply_global_caps()  # must NOT raise

    mock_log.warning.assert_called_once()
    assert mock_log.warning.call_args.args[0] == "acquire.global_limits.failed"


# ── Service-level: run() re-asserts global caps at entry ───────────────────────


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


def test_service_run_calls_apply_global_caps_once(store: ConcreteAcquireStore) -> None:
    """AcquisitionService.run() calls apply_global_caps() exactly once at entry (D5)."""
    orch = MagicMock()
    config = MagicMock()
    config.acquire = AcquireConfig()  # real default cadence — see test_service.py._config()
    service = AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orch,
        event_bus=MagicMock(),
        config=config,
    )

    summary = service.run(limit=10)

    assert isinstance(summary, RunSummary)
    orch.apply_global_caps.assert_called_once_with()
