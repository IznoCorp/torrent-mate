"""Async jobs primitive for privileged/long ops (bosun §11).

A privileged or long-running op runs as a DETACHED process (own session/process group, §11.3) that
writes a JSON status file under ``<root>/ops/<id>.json``; the UI polls ``GET /api/ops/{id}``. The
record IS the per-op audit trail (who/when/what/exit), durable on disk. Quick reads never use a job.

Layering: ``app`` imperative shell — filesystem writes + ``subprocess`` spawn; imports ``core`` only.
"""

from __future__ import annotations

import datetime
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any

_OPS_DIRNAME = "ops"
_GC_KEEP = 50  # keep the newest N records (DESIGN §11.2 / open-question 1)
_GC_MAX_AGE_DAYS = 14  # prune anything older than this
_STDOUT_TAIL_BYTES = 4096  # last ~4 KiB of stdout copied into the record (DESIGN §11.1)
# A record stuck at state="queued" longer than this (with no started_at) means the detached runner
# died BEFORE reaching run_job — a broken venv, an ImportError in a module ops_exec imports, an OOM
# or interpreter spawn failure. run_job never ran to finalise it, so read_job lazily reaps it as
# failed (bosun review-c3). Generous enough to never race a slow-but-healthy spawn.
_SPAWN_DEADLINE_S = 60.0

_JOB_TYPES = frozenset(
    {"redeploy", "daemon", "project_add", "wizard_bootstrap", "wizard_provision"}
)


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 ``...Z`` string (timezone-aware)."""
    return datetime.datetime.now(datetime.UTC).isoformat()


def _now_compact() -> str:
    """Return the current UTC time as a compact ``YYYYMMDDTHHMMSS`` stamp (for job ids)."""
    return datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")


def _ops_dir(root: Path) -> Path:
    """Return ``<root>/ops`` (created on demand by writers)."""
    return root / _OPS_DIRNAME


def _record_path(root: Path, job_id: str) -> Path:
    """Return the JSON record path ``<root>/ops/<job_id>.json``."""
    return _ops_dir(root) / f"{job_id}.json"


def _log_path(root: Path, job_id: str) -> Path:
    """Return the combined stdout/stderr log path ``<root>/ops/<job_id>.log``."""
    return _ops_dir(root) / f"{job_id}.log"


def _generate_job_id(type: str) -> str:
    """Generate a unique job id: ``<compact-UTCstamp>-<type>-<rand4>``.

    Uses ``os.urandom``-backed ``secrets.token_hex(2)`` for the random suffix (4 hex chars).

    Args:
        type: One of ``_JOB_TYPES``.

    Returns:
        The generated job id string.
    """
    stamp = _now_compact()
    rand4 = secrets.token_hex(2)
    return f"{stamp}-{type}-{rand4}"


def create_job(
    root: Path,
    *,
    type: str,
    actor: str,
    argv: list[str],
    args_summary: str,
    cwd: str | None = None,
) -> str:
    """Write the queued job spec, spawn the detached runner, return the job id.

    Args:
        root: The kanban runtime root (``<root>/ops/`` holds the records).
        type: One of ``_JOB_TYPES``.
        actor: The authenticated operator login (for the audit trail).
        argv: The server-constructed command to exec (never client-supplied — DESIGN §11.4).
        args_summary: A short, sanitised description of the args (e.g. ``"target=prod"``).
        cwd: Working directory for the spawned process, or ``None`` for the current one.

    Returns:
        The generated job id ``<UTCstamp>-<type>-<rand4>``.

    Raises:
        ValueError: When ``type`` is not one of ``_JOB_TYPES`` (a server-side programming error —
            every call site is server-constructed with a literal, so this fails loud rather than
            writing an untyped record).
    """
    if type not in _JOB_TYPES:
        raise ValueError(f"unknown job type {type!r} (expected one of {sorted(_JOB_TYPES)})")
    job_id = _generate_job_id(type)
    rec = {
        "id": job_id,
        "type": type,
        "actor": actor,
        "args_summary": args_summary,
        "state": "queued",
        "created_at": _now_iso(),
        "started_at": None,
        "ended_at": None,
        "exit_code": None,
        "stdout_tail": "",
        "error": None,
        "argv": argv,
        "cwd": cwd,
    }
    _ops_dir(root).mkdir(parents=True, exist_ok=True)
    _record_path(root, job_id).write_text(json.dumps(rec, indent=2), encoding="utf-8")

    # Spawn the detached runner (DESIGN §11.3). start_new_session=True is the crux:
    # a pm2 restart of the config app signals only its own process group — the
    # detached runner owns its own group and survives (DESIGN §3.2, §11.3).
    # Open the log explicitly and close the parent's copy after the spawn: the child inherits its own
    # fd, so the parent (the long-lived UI server) must not leak a handle per job.
    log_fh = open(_log_path(root, job_id), "wb")
    try:
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "kanbanmate.cli.ops_exec",
                job_id,
                "--root",
                str(root),
            ],
            start_new_session=True,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            cwd=cwd,
        )
    finally:
        log_fh.close()

    return job_id


def read_job(root: Path, job_id: str) -> dict[str, Any]:
    """Return the parsed job record, or raise ``FileNotFoundError`` if unknown.

    Two read-time fixes surface a runner that died BEFORE :func:`run_job` could finalise the record
    (a broken venv / ImportError / OOM / interpreter spawn failure — bosun review-c3):

    * **Lazy reap of a stale ``queued`` record:** when ``state == "queued"`` and the spawn deadline
      (:data:`_SPAWN_DEADLINE_S` since ``created_at``, no ``started_at``) has elapsed, the runner
      never reached ``run_job`` to flip the record — it is transitioned to ``failed`` with a clear
      error and persisted, so the UI poller learns the truth instead of timing out forever.
    * **Fold the ``<id>.log`` tail into the response:** whenever the record carries no captured
      output (empty ``stdout_tail`` AND no ``error``), the tail of the durable ``<id>.log`` — which
      DID capture the child's spawn/import traceback (the child inherited that log fd) — is folded
      into ``stdout_tail`` so the operator sees the real failure rather than an empty record.

    Args:
        root: The kanban runtime root.
        job_id: The job identifier.

    Returns:
        The parsed job record as a dict (possibly reaped / log-augmented; see above).

    Raises:
        FileNotFoundError: When no record exists for ``job_id``.
    """
    p = _record_path(root, job_id)
    if not p.is_file():
        raise FileNotFoundError(f"Unknown job '{job_id}'")
    rec: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))

    # Lazy reap: a record still "queued" past the spawn deadline means the detached runner died
    # before run_job ran. Finalise it as failed and persist so subsequent reads (and list_jobs) see
    # the terminal state — pointing at the durable log for the captured cause.
    if rec.get("state") == "queued" and not rec.get("started_at") and _spawn_deadline_passed(rec):
        rec["state"] = "failed"
        rec["ended_at"] = _now_iso()
        rec["exit_code"] = rec.get("exit_code")  # stays None — the runner never produced one
        rec["error"] = "runner failed to start (see <id>.log)"
        _write_record(root, job_id, rec)

    # Fold the durable log tail in when the record captured nothing of its own — covers the
    # pre-run_job crash window where the child's traceback only ever reached <id>.log.
    if not rec.get("stdout_tail") and not rec.get("error"):
        tail = _log_tail(root, job_id)
        if tail:
            rec["stdout_tail"] = tail
    return rec


def _spawn_deadline_passed(rec: dict[str, Any]) -> bool:
    """True when a ``queued`` record's ``created_at`` is older than :data:`_SPAWN_DEADLINE_S`.

    Fail-soft: an unparseable / absent ``created_at`` is treated as NOT past the deadline (never
    reap a record whose age cannot be established).

    Args:
        rec: The parsed job record.

    Returns:
        ``True`` when the spawn deadline has elapsed, else ``False``.
    """
    try:
        created = datetime.datetime.fromisoformat(rec.get("created_at", ""))
    except (TypeError, ValueError):
        return False
    return (datetime.datetime.now(datetime.UTC) - created).total_seconds() > _SPAWN_DEADLINE_S


def _log_tail(root: Path, job_id: str) -> str:
    """Return the bounded tail of ``<root>/ops/<job_id>.log`` (empty on any read error).

    Args:
        root: The kanban runtime root.
        job_id: The job identifier.

    Returns:
        The last :data:`_STDOUT_TAIL_BYTES` of the log (``errors="replace"`` so a binary byte never
        raises), or ``""`` when the log is absent / unreadable.
    """
    try:
        text = _log_path(root, job_id).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) > _STDOUT_TAIL_BYTES:
        text = text[-_STDOUT_TAIL_BYTES:]
    return text


def list_jobs(
    root: Path,
    *,
    type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return records newest-first, optionally filtered by ``type``, capped at ``limit``.

    Args:
        root: The kanban runtime root.
        type: When set, return only records matching this job type.
        limit: Maximum number of records to return (default 50).

    Returns:
        A list of job record dicts, sorted newest-first.
    """
    ops_dir = _ops_dir(root)
    if not ops_dir.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for child in ops_dir.iterdir():
        if not child.name.endswith(".json"):
            continue
        try:
            rec = json.loads(child.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Corrupt record — skip rather than failing the whole listing.
            continue
        if type is not None and rec.get("type") != type:
            continue
        records.append(rec)
    # Sort by created_at descending (newest first); records without the field sort last.
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return records[:limit]


def gc_jobs(root: Path) -> None:
    """Keep the newest 50 records + prune those older than 14 days; fail-soft (DESIGN §11.2).

    Args:
        root: The kanban runtime root.
    """
    try:
        _gc_jobs_impl(root)
    except Exception:
        # Fail-soft: a GC failure must never block the tick or crash the daemon.
        pass


def _gc_jobs_impl(root: Path) -> None:
    """Inner GC logic — separated so the outer wrapper stays fail-soft."""
    ops_dir = _ops_dir(root)
    if not ops_dir.is_dir():
        return

    now = datetime.datetime.now(datetime.UTC)
    cutoff = now - datetime.timedelta(days=_GC_MAX_AGE_DAYS)

    # Collect all .json record files with their parsed created_at.
    entries: list[tuple[Path, datetime.datetime | None]] = []
    for child in ops_dir.iterdir():
        if not child.name.endswith(".json"):
            continue
        try:
            rec = json.loads(child.read_text(encoding="utf-8"))
            created = datetime.datetime.fromisoformat(rec.get("created_at", ""))
        except (json.JSONDecodeError, OSError, ValueError):
            # Can't parse — treat as unknown age (keep unless over the count cap).
            created = None
        entries.append((child, created))

    # Sort by created_at descending (newest first); None-sort at the end.
    entries.sort(
        key=lambda e: (e[1] is None, e[1] or datetime.datetime.min.replace(tzinfo=datetime.UTC)),
        reverse=True,
    )

    # Determine which to delete: anything beyond the _GC_KEEP newest, or older than the age cutoff.
    to_delete: list[Path] = []
    for i, (path, created) in enumerate(entries):
        if i >= _GC_KEEP:
            to_delete.append(path)
        elif created is not None and created < cutoff:
            to_delete.append(path)

    for path in to_delete:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # Individual unlink failure should not block the rest.
            pass


def run_job(root: Path, job_id: str) -> int:
    """Runner body: mark running → exec argv → tail stdout → mark succeeded/failed; return exit code.

    The inner command's stdout+stderr are streamed to the durable ``<root>/ops/<job_id>.log`` file
    (so the FULL output survives for post-mortem of a failed privileged job — DESIGN §11.3), while a
    bounded tail of the same stream is mirrored into ``rec["stdout_tail"]`` for the quick UI view.
    Without this the root cause of a long failing job (npm ci errors, a deploy.sh ``fail()`` near the
    top, a git-clone auth error) would scroll out of the 4 KiB tail and be unrecoverable (review-c2).

    Args:
        root: The kanban runtime root.
        job_id: The job identifier.

    Returns:
        The process exit code (0 for success).
    """
    rec = read_job(root, job_id)

    # Mark running.
    rec["state"] = "running"
    rec["started_at"] = _now_iso()
    _write_record(root, job_id, rec)

    exit_code: int = 0
    error: str | None = None
    stdout_tail: str = ""

    log_path = _log_path(root, job_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Stream the inner command's stdout+stderr straight to the durable <id>.log (full output on
        # disk), then read the bounded tail back for the record. The detached ops_exec process emits
        # nothing of its own, so this file holds exactly the job's output.
        with log_path.open("w", encoding="utf-8") as log_fh:
            proc = subprocess.run(
                rec["argv"],
                cwd=rec.get("cwd") or None,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=None,  # No timeout — jobs may be long-running.
            )
        exit_code = proc.returncode
        # Read the tail back from the durable log (errors='replace' so a binary byte never crashes
        # the finaliser); the full stream stays on disk for post-mortem.
        try:
            combined = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            combined = ""
        if len(combined) > _STDOUT_TAIL_BYTES:
            combined = combined[-_STDOUT_TAIL_BYTES:]
        stdout_tail = combined
    except FileNotFoundError as exc:
        # The command itself doesn't exist (argv[0] not found).
        exit_code = 127
        error = f"Command not found: {exc}"
    except PermissionError as exc:
        exit_code = 126
        error = f"Permission denied: {exc}"
    except OSError as exc:
        exit_code = 1
        error = f"OS error: {exc}"
    except Exception as exc:
        # Any other runner crash (e.g. a malformed argv raising ValueError, a capture-handling
        # error, MemoryError) MUST still finalise the record as failed — otherwise the job stays
        # wedged at state="running" forever and the UI poller can only ever time out, never learn
        # the job actually crashed. Record it as a failure rather than letting the exception escape.
        exit_code = 1
        error = f"Runner error: {exc!r}"

    # Finalise the record.
    rec["state"] = "succeeded" if exit_code == 0 else "failed"
    rec["ended_at"] = _now_iso()
    rec["exit_code"] = exit_code
    rec["stdout_tail"] = stdout_tail
    rec["error"] = error
    _write_record(root, job_id, rec)

    return exit_code


def _write_record(root: Path, job_id: str, rec: dict[str, Any]) -> None:
    """Atomically write the job record to disk.

    Writes to a temp file then renames (atomic on the same filesystem) so a concurrent reader
    never sees a half-written record.
    """
    p = _record_path(root, job_id)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    os.replace(tmp, p)
