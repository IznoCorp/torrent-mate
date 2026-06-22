"""Tests for app/ops jobs primitive (bosun §11)."""

from __future__ import annotations

import datetime
import json
import sys
import time
from pathlib import Path
from typing import Any

from kanbanmate.app import ops


def _seed_queued(root: Path, argv: list[str]) -> str:
    """Write a queued spec WITHOUT spawning (test run_job in isolation)."""
    job_id = "20260621T120000-daemon-ab12"
    rec: dict[str, Any] = {
        "id": job_id,
        "type": "daemon",
        "actor": "op",
        "args_summary": "x",
        "state": "queued",
        "created_at": ops._now_iso(),
        "started_at": None,
        "ended_at": None,
        "exit_code": None,
        "stdout_tail": "",
        "error": None,
        "argv": argv,
        "cwd": None,
    }
    p = ops._record_path(root, job_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec), encoding="utf-8")
    return job_id


def test_run_job_success_marks_succeeded(tmp_path: Path) -> None:
    job_id = _seed_queued(tmp_path, ["python", "-c", "print('hello-from-job')"])
    code = ops.run_job(tmp_path, job_id)
    assert code == 0
    rec = ops.read_job(tmp_path, job_id)
    assert rec["state"] == "succeeded"
    assert rec["exit_code"] == 0
    assert "hello-from-job" in rec["stdout_tail"]
    assert rec["started_at"] and rec["ended_at"]


def test_run_job_persists_full_log_not_just_tail(tmp_path: Path) -> None:
    """The full stdout+stderr stream is durable in <id>.log; the record keeps only a bounded tail.

    Regression guard for review-c2: an early root cause in a long job must survive on disk even when
    it scrolls out of the 4 KiB record tail.
    """
    # Emit > _STDOUT_TAIL_BYTES on a SINGLE stream (stdout) so byte order follows program order
    # (mixing stdout+stderr would interleave unpredictably due to buffering). Also write one stderr
    # line to prove stderr is merged into the same durable log.
    script = (
        "import sys;"
        "print('STDERR-CAPTURED', file=sys.stderr);"
        "print('EARLY-MARKER');"
        "print('X' * 6000);"
        "print('LATE-MARKER')"
    )
    job_id = _seed_queued(tmp_path, ["python", "-c", script])
    code = ops.run_job(tmp_path, job_id)
    assert code == 0

    # The full log on disk carries the early stdout marker AND the stderr line — full output durable.
    full = ops._log_path(tmp_path, job_id).read_text(encoding="utf-8")
    assert "EARLY-MARKER" in full
    assert "LATE-MARKER" in full
    assert "STDERR-CAPTURED" in full  # stderr merged into the same log

    # The record tail is bounded and only carries the END of the stream (early marker scrolled out).
    rec = ops.read_job(tmp_path, job_id)
    assert len(rec["stdout_tail"]) <= ops._STDOUT_TAIL_BYTES
    assert "LATE-MARKER" in rec["stdout_tail"]
    assert "EARLY-MARKER" not in rec["stdout_tail"]


def test_run_job_failure_marks_failed(tmp_path: Path) -> None:
    job_id = _seed_queued(tmp_path, ["python", "-c", "import sys; sys.exit(3)"])
    code = ops.run_job(tmp_path, job_id)
    assert code == 3
    rec = ops.read_job(tmp_path, job_id)
    assert rec["state"] == "failed"
    assert rec["exit_code"] == 3


def test_run_job_non_oserror_marks_failed_not_stuck_running(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """A runner crash outside the OSError family is recorded as failed — never wedged at running.

    Without the broad ``except``, a non-OSError (e.g. ValueError) would escape ``run_job``, leaving
    the record at state="running" forever (the UI poller can then only time out). Assert the record
    is finalised as failed with the error captured.
    """
    job_id = _seed_queued(tmp_path, ["python", "-c", "print('x')"])

    def _boom(*_a: object, **_k: object) -> object:
        raise ValueError("malformed argv")

    monkeypatch.setattr("kanbanmate.app.ops.subprocess.run", _boom)
    code = ops.run_job(tmp_path, job_id)
    assert code == 1
    rec = ops.read_job(tmp_path, job_id)
    assert rec["state"] == "failed"
    assert rec["exit_code"] == 1
    assert "malformed argv" in rec["error"]
    assert rec["ended_at"]  # finalised, not left running


def test_list_jobs_newest_first_and_filtered(tmp_path: Path) -> None:
    _seed_queued(tmp_path, ["true"])  # seed first record for multi-record listing
    # second record, different id/type
    rec: dict[str, Any] = {
        "id": "20260621T130000-redeploy-cd34",
        "type": "redeploy",
        "actor": "op",
        "args_summary": "target=prod",
        "state": "queued",
        "created_at": ops._now_iso(),
        "started_at": None,
        "ended_at": None,
        "exit_code": None,
        "stdout_tail": "",
        "error": None,
        "argv": ["true"],
        "cwd": None,
    }
    ops._record_path(tmp_path, rec["id"]).write_text(json.dumps(rec), encoding="utf-8")
    all_jobs = ops.list_jobs(tmp_path)
    assert [j["id"] for j in all_jobs][0] == "20260621T130000-redeploy-cd34"  # newest first
    only_daemon = ops.list_jobs(tmp_path, type="daemon")
    assert {j["type"] for j in only_daemon} == {"daemon"}


def test_create_job_record_readable_after_spawn(tmp_path: Path) -> None:
    """create_job returns immediately; the record is readable (detached runner owns completion)."""
    job_id = ops.create_job(
        tmp_path,
        type="daemon",
        actor="op",
        argv=[sys.executable, "-c", "print('detached-ok')"],
        args_summary="probe",
    )
    rec = ops.read_job(tmp_path, job_id)  # readable straight away (queued or running)
    assert rec["id"] == job_id
    assert rec["state"] in {"queued", "running", "succeeded"}
    # Poll briefly for completion without a wall-clock sleep dependency in CI:
    for _ in range(50):
        rec = ops.read_job(tmp_path, job_id)
        if rec["state"] in {"succeeded", "failed"}:
            break
        time.sleep(0.1)
    assert rec["state"] == "succeeded"
    assert "detached-ok" in rec["stdout_tail"]


def test_read_job_unknown_raises(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        ops.read_job(tmp_path, "nope")


def test_read_job_reaps_stale_queued_record(tmp_path: Path) -> None:
    """A record stuck 'queued' past the spawn deadline is lazily reaped to 'failed' on read.

    Models a detached runner that died before run_job() (broken venv / ImportError / OOM). Without
    the reaper the UI poller can only time out; with it, read_job surfaces a terminal failed state.
    """
    # Seed a queued record whose created_at is well past the spawn deadline, no started_at.
    job_id = "20200101T000000-daemon-dead"
    stale_iso = (
        datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=ops._SPAWN_DEADLINE_S + 10)
    ).isoformat()
    rec: dict[str, Any] = {
        "id": job_id,
        "type": "daemon",
        "actor": "op",
        "args_summary": "x",
        "state": "queued",
        "created_at": stale_iso,
        "started_at": None,
        "ended_at": None,
        "exit_code": None,
        "stdout_tail": "",
        "error": None,
        "argv": ["true"],
        "cwd": None,
    }
    ops._record_path(tmp_path, job_id).parent.mkdir(parents=True, exist_ok=True)
    ops._record_path(tmp_path, job_id).write_text(json.dumps(rec), encoding="utf-8")

    out = ops.read_job(tmp_path, job_id)
    assert out["state"] == "failed"
    assert out["error"] == "runner failed to start (see <id>.log)"
    assert out["ended_at"]
    # Persisted: a second read sees the terminal state directly, and list_jobs reflects it too.
    assert ops.read_job(tmp_path, job_id)["state"] == "failed"
    assert {j["state"] for j in ops.list_jobs(tmp_path) if j["id"] == job_id} == {"failed"}


def test_read_job_does_not_reap_fresh_queued_record(tmp_path: Path) -> None:
    """A freshly-queued record (within the spawn deadline) is left untouched by read_job."""
    job_id = _seed_queued(tmp_path, ["true"])  # created_at = now
    out = ops.read_job(tmp_path, job_id)
    assert out["state"] == "queued"  # not reaped — still inside the spawn window


def test_read_job_folds_log_tail_when_record_has_no_output(tmp_path: Path) -> None:
    """When stdout_tail and error are empty, read_job folds in the durable <id>.log tail.

    Models the pre-run_job crash window: the child wrote its import traceback to the inherited log
    fd but never reached run_job to populate stdout_tail. The operator must still see the cause.
    """
    job_id = _seed_queued(tmp_path, ["true"])  # state=queued, stdout_tail="" , error=None
    # The detached child's traceback only ever reached <id>.log.
    ops._log_path(tmp_path, job_id).write_text(
        "Traceback (most recent call last):\nModuleNotFoundError: No module named 'kanbanmate'\n",
        encoding="utf-8",
    )
    out = ops.read_job(tmp_path, job_id)
    assert "ModuleNotFoundError" in out["stdout_tail"]


def test_read_job_keeps_existing_tail_over_log(tmp_path: Path) -> None:
    """A record that already captured stdout_tail is NOT overwritten by the log tail."""
    job_id = _seed_queued(tmp_path, ["true"])
    rec = ops.read_job(tmp_path, job_id)
    rec["state"] = "succeeded"
    rec["stdout_tail"] = "REAL-CAPTURED-OUTPUT"
    ops._write_record(tmp_path, job_id, rec)
    ops._log_path(tmp_path, job_id).write_text("DIFFERENT-LOG-CONTENT", encoding="utf-8")
    out = ops.read_job(tmp_path, job_id)
    assert out["stdout_tail"] == "REAL-CAPTURED-OUTPUT"


def test_create_job_rejects_unknown_type(tmp_path: Path) -> None:
    """create_job fails loud on a non-_JOB_TYPES type (server-side programming error guard)."""
    import pytest

    with pytest.raises(ValueError, match="unknown job type"):
        ops.create_job(
            tmp_path,
            type="not-a-real-type",
            actor="op",
            argv=["true"],
            args_summary="x",
        )
    # The guard runs before any disk write → no ops dir/record created for the rejected type.
    assert not ops._ops_dir(tmp_path).exists()
