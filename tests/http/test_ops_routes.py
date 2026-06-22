"""Tests for the read-only jobs HTTP surface (bosun §11.4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")
from fastapi.testclient import TestClient  # noqa: E402


def _setup(tmp_path: Path) -> str:
    import kanbanmate.http.config_api as api_mod

    import kanbanmate.http.ops_routes  # noqa: F401  (registers routes)

    from kanbanmate.app import ops

    root = tmp_path / "root"
    root.mkdir()
    api_mod.app.state.kanban_root = root
    api_mod.app.state.auth = None  # auth disabled → middleware passes through
    job_id = "20260621T120000-daemon-ab12"
    rec: dict[str, object] = {
        "id": job_id,
        "type": "daemon",
        "actor": "op",
        "args_summary": "x",
        "state": "succeeded",
        "created_at": ops._now_iso(),
        "started_at": ops._now_iso(),
        "ended_at": ops._now_iso(),
        "exit_code": 0,
        "stdout_tail": "ok",
        "error": None,
    }
    ops._record_path(root, job_id).parent.mkdir(parents=True, exist_ok=True)
    ops._record_path(root, job_id).write_text(json.dumps(rec), encoding="utf-8")
    return job_id


def test_list_ops_returns_seeded_record(tmp_path: Path) -> None:
    job_id = _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod

    with TestClient(api_mod.app) as client:
        r = client.get("/api/ops")
        assert r.status_code == 200
        ids = [j["id"] for j in r.json()["jobs"]]
        assert job_id in ids


def test_get_op_unknown_404(tmp_path: Path) -> None:
    _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod

    with TestClient(api_mod.app) as client:
        assert client.get("/api/ops/nope").status_code == 404
