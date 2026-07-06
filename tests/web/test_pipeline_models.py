"""Unit tests for pipeline API Pydantic models."""

from __future__ import annotations

from personalscraper.web.models.pipeline import (
    PipelineOutcome,
    PipelineState,
    RunRequest,
    RunResponse,
    StatusResponse,
    WatcherRequest,
    WatcherResponse,
)


class TestPipelineModels:
    """Round-trip instantiation and serialization for every model."""

    def test_pipeline_state_enum(self) -> None:
        """``PipelineState`` enum members have the expected string values."""
        assert PipelineState.idle.value == "idle"
        assert PipelineState.running.value == "running"
        assert PipelineState.paused.value == "paused"

    def test_pipeline_outcome_enum(self) -> None:
        """``PipelineOutcome`` enum members have the expected string values."""
        assert PipelineOutcome.success.value == "success"
        assert PipelineOutcome.killed.value == "killed"

    def test_run_request_defaults(self) -> None:
        """``RunRequest`` defaults ``dry_run`` to ``False``."""
        req = RunRequest()
        assert req.dry_run is False
        assert req.model_dump() == {"dry_run": False}

    def test_watcher_request(self) -> None:
        """``WatcherRequest`` round-trips through ``model_dump``."""
        req = WatcherRequest(enabled=True)
        assert req.model_dump() == {"enabled": True}

    def test_run_response(self) -> None:
        """``RunResponse`` round-trips through ``model_dump``."""
        resp = RunResponse(run_uid="abc-123")
        assert resp.model_dump() == {"run_uid": "abc-123"}

    def test_status_response_full(self) -> None:
        """``StatusResponse`` serializes all fields correctly, including enums."""
        resp = StatusResponse(
            state=PipelineState.running,
            run_uid="abc-123",
            step="scrape",
            paused=False,
            watcher_enabled=True,
            pid=12345,
        )
        d = resp.model_dump()
        assert d["state"] == "running"
        assert d["run_uid"] == "abc-123"
        assert d["step"] == "scrape"
        assert d["paused"] is False
        assert d["watcher_enabled"] is True
        assert d["pid"] == 12345

    def test_watcher_response(self) -> None:
        """``WatcherResponse`` round-trips through ``model_dump``."""
        resp = WatcherResponse(watcher_enabled=False)
        assert resp.model_dump() == {"watcher_enabled": False}
