"""Decision runner — thin config over the shared runner engine.

Executable as ``python -m personalscraper.web.decisions.runner``. Reads its
configuration from environment variables (set by the POST handler in
``personalscraper.web.routes.decisions``), validates the ``scrape_decision`` row,
then delegates the run-row / spawn / stream / requeue / finalize lifecycle to
:func:`personalscraper.web._runner_engine.run_spawn_stream`.

Lock ownership (R11 / webui-ux phase 4): the ``scrape-resolve`` CLI acquires the
SCOPED per-staging-item scrape lock
(:func:`~personalscraper.lock.acquire_scrape_resolve_lock`) for its lifetime — NOT
the global ``pipeline.lock``. That scoped lock is fail-closed against the global
lock (distinct items resolve in parallel; any global holder makes the resolve back
off), so this runner does NOT hold any lock on the child's behalf. Instead it
PROBES ``pipeline.lock`` before each spawn (visibility + pacing only — the child's
claim stays the sole safety authority) and re-queues on the child's exit-3
lock-busy signal, generalised through the engine's ``probe_lock_each_iter`` /
``requeue_on_exit3`` policy.

Environment contract (canonical — match the spawner):

* ``PERSONALSCRAPER_RUN_UID`` — mandatory, the ``run_uid`` hex string.
* ``PERSONALSCRAPER_DECISION_ID`` — mandatory, the ``scrape_decision.id``.
* ``PERSONALSCRAPER_DECISION_PROVIDER`` — mandatory, ``"tmdb"`` or ``"tvdb"``.
* ``PERSONALSCRAPER_DECISION_PROVIDER_ID`` — mandatory, the provider numeric ID.

Exit codes:

* ``0`` — the CLI subprocess completed successfully.
* ``1`` — the CLI subprocess exited non-zero (error) or the queue deadline passed.
* ``2`` — misconfiguration (missing env, missing/non-pending decision, config load
  failure, DB failure, spawn failure).
* ``143`` — runner killed via SIGTERM.
"""

from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
import sys
from types import FrameType
from typing import cast

from personalscraper.conf.loader import load_config
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.lock import is_lock_held
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.web._runner_engine import (
    OUTCOME_ERROR,
    OUTCOME_KILLED,
    SIGTERM_EXIT_CODE,
    RunnerSpec,
    run_spawn_stream,
)
from personalscraper.web._runner_engine import (
    RingBuffer as _RingBuffer,
)
from personalscraper.web._runner_engine import (
    get_redis as _get_redis,
)
from personalscraper.web._runner_engine import (
    kill_child_group as _kill_child_group,
)
from personalscraper.web._runner_engine import (
    redis_publish_line as _redis_publish_line,  # noqa: F401 — re-export for test/seam parity
)

log = get_logger(__name__)

#: Outcome string used for CLI exit-code-0 success.
OUTCOME_SUCCESS = "success"


def _read_mandatory_env() -> tuple[str, int, str, int]:
    """Read the four mandatory runner env vars; exit 2 on missing.

    Returns:
        A ``(run_uid, decision_id, provider, provider_id)`` tuple.

    Raises:
        SystemExit: 2 when any required env var is missing or has an invalid
            integer value.
    """
    missing: list[str] = []
    for var in (
        "PERSONALSCRAPER_RUN_UID",
        "PERSONALSCRAPER_DECISION_ID",
        "PERSONALSCRAPER_DECISION_PROVIDER",
        "PERSONALSCRAPER_DECISION_PROVIDER_ID",
    ):
        if not os.environ.get(var):
            missing.append(var)
    if missing:
        log.error(
            "decision_runner_missing_env",
            missing=missing,
            hint="The spawner MUST set all four PERSONALSCRAPER_DECISION_* vars",
        )
        sys.exit(2)

    run_uid = os.environ["PERSONALSCRAPER_RUN_UID"]

    try:
        decision_id = int(os.environ["PERSONALSCRAPER_DECISION_ID"])
    except ValueError:
        log.error(
            "decision_runner_bad_decision_id",
            value=os.environ["PERSONALSCRAPER_DECISION_ID"],
        )
        sys.exit(2)

    provider = os.environ["PERSONALSCRAPER_DECISION_PROVIDER"]

    try:
        provider_id = int(os.environ["PERSONALSCRAPER_DECISION_PROVIDER_ID"])
    except ValueError:
        log.error(
            "decision_runner_bad_provider_id",
            value=os.environ["PERSONALSCRAPER_DECISION_PROVIDER_ID"],
        )
        sys.exit(2)

    return run_uid, decision_id, provider, provider_id


def _read_decision_row(db_path: str, decision_id: int) -> dict[str, object] | None:
    """Read the ``scrape_decision`` row by *decision_id*.

    Opens a short-lived ``sqlite3`` connection and returns ``id``,
    ``staging_path``, and ``status`` as a dict. Returns ``None`` when the row
    does not exist.

    Args:
        db_path: Path to the indexer SQLite database.
        decision_id: Primary key of the ``scrape_decision`` row.

    Returns:
        A dict with ``id``, ``staging_path``, and ``status`` keys, or ``None``
        when the row does not exist.
    """
    conn = sqlite3.connect(db_path, isolation_level=None)
    apply_pragmas(conn)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, staging_path, status FROM scrape_decision WHERE id = ?",
        (decision_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def _build_argv(staging_path: str, provider: str, provider_id: int, via: str) -> list[str]:
    """Build the ``scrape-resolve`` CLI argument list.

    Args:
        staging_path: Absolute path to the staging item.
        provider: Metadata provider name (``'tmdb'`` or ``'tvdb'``).
        provider_id: Numeric identifier assigned by the provider.
        via: Resolution provenance (``'pick'`` / ``'search_override'``), forwarded
            so ``resolution_json.via`` is accurate (F09).

    Returns:
        A command-line argument list starting with ``sys.executable``, suitable
        for ``subprocess.Popen``.
    """
    return [
        sys.executable,
        "-m",
        "personalscraper",
        "scrape-resolve",
        staging_path,
        "--provider",
        provider,
        "--id",
        str(provider_id),
        "--via",
        via,
    ]


def main() -> None:
    """Run the decision resolution subprocess (see module docstring).

    Reads env, validates the decision row exists and is ``'pending'`` (finalizing
    the route-reserved row ``'error'`` on any bad-row path so it is never left
    ``'running'`` — Finding A/F06), then hands the spawn / stream / requeue /
    finalize lifecycle to the shared engine. On a ``rc == 0`` finish the engine's
    ``on_success`` hook triggers the §4 pipeline continuation through the single
    trigger authority so the resolved media finishes trailers → verify →
    dispatch and leaves staging.
    """
    run_uid, decision_id, provider, provider_id = _read_mandatory_env()

    try:
        config = load_config()
    except Exception as exc:
        log.error("decision_runner_config_load_failed", run_uid=run_uid, error=str(exc))
        sys.exit(2)

    db_path = config.indexer.db_path
    if db_path is None:
        log.error("decision_runner_no_db_path", run_uid=run_uid)
        sys.exit(2)
    web_config = config.web

    options = {"decision_id": decision_id, "provider": provider, "provider_id": provider_id}
    options_json = json.dumps(options, sort_keys=True, separators=(",", ":"))

    # Resolution provenance (optional — legacy spawners omit it). Defaults to
    # 'pick' so an absent env var never breaks the run (F09).
    via = os.environ.get("PERSONALSCRAPER_DECISION_VIA", "pick")

    def _finalize_bad_row(error: str) -> None:
        """Ensure the row exists then finalize it 'error' (never left 'running')."""
        writer_err = PipelineRunWriter(db_path)
        writer_err.insert(
            run_uid,
            trigger="web",
            dry_run=False,
            pid=os.getpid(),
            kind="maintenance",
            command="scrape-resolve",
            options_json=options_json,
            if_absent=True,
        )
        writer_err.finalize(run_uid, OUTCOME_ERROR, error=error)

    # Read + validate the decision row BEFORE the guarded stream region — an
    # unguarded sqlite error here would kill the process and orphan the
    # route-reserved 'running' row forever, so finalize it 'error' first (F06).
    try:
        decision = _read_decision_row(str(db_path), decision_id)
    except sqlite3.Error as exc:
        _finalize_bad_row(f"Decision read failed: {exc}")
        log.error("decision_runner_decision_read_failed", run_uid=run_uid, decision_id=decision_id, error=str(exc))
        sys.exit(2)
    if decision is None:
        _finalize_bad_row(f"Decision {decision_id} not found")
        log.error("decision_runner_decision_not_found", run_uid=run_uid, decision_id=decision_id)
        sys.exit(2)
    if decision["status"] != "pending":
        _finalize_bad_row(f"Decision {decision_id} is '{decision['status']}', expected 'pending'")
        log.error(
            "decision_runner_decision_not_pending",
            run_uid=run_uid,
            decision_id=decision_id,
            status=decision["status"],
        )
        sys.exit(2)

    staging_path = cast(str, decision["staging_path"])
    argv = _build_argv(staging_path, provider, provider_id, via)

    writer = PipelineRunWriter(db_path)
    ring = _RingBuffer()
    child: dict[str, subprocess.Popen[str]] = {}

    def _on_sigterm(_signum: int, _frame: FrameType | None) -> None:
        """Terminate the child group (if any), finalize ``'killed'``."""
        proc_ref = child.get("proc")
        if proc_ref is not None:
            _kill_child_group(proc_ref)
        writer.finalize(run_uid, OUTCOME_KILLED, output_tail=ring.to_str())
        log.warning("decision_runner_killed", run_uid=run_uid, decision_id=decision_id)
        os._exit(SIGTERM_EXIT_CODE)

    signal.signal(signal.SIGTERM, _on_sigterm)

    def _continuation() -> None:
        """§4 — after a successful resolve, finish the media's pipeline.

        Trigger a continuation run through the single trigger authority
        (``pipeline.lock`` is the sole gate). A held lock defers the continuation
        (the in-flight run picks the freshly-scraped item up) — no second
        mechanism. The lazy import lets tests patch ``spawn_pipeline_run`` at its
        source module.
        """
        from personalscraper.web.pipeline_trigger import RESOLVE_CONTINUATION_TRIGGER, spawn_pipeline_run

        continuation_uid = spawn_pipeline_run(config.paths.data_dir, trigger_reason=RESOLVE_CONTINUATION_TRIGGER)
        log.info(
            "decision_runner_continuation",
            run_uid=run_uid,
            decision_id=decision_id,
            continuation_run_uid=continuation_uid,
            deferred=continuation_uid is None,
        )

    queue_timeout_s = float(os.environ.get("PERSONALSCRAPER_RESOLVE_QUEUE_TIMEOUT", "1800"))

    run_spawn_stream(
        RunnerSpec(
            writer=writer,
            run_uid=run_uid,
            kind="maintenance",
            command="scrape-resolve",
            options_json=options_json,
            dry_run=False,
            argv=argv,
            child=child,
            ring=ring,
            redis=_get_redis(web_config),
            stream_key=web_config.stream_key,
            stream_maxlen=web_config.stream_maxlen,
            event_prefix="decision_runner",
            log_context={"decision_id": decision_id},
            probe_lock_each_iter=True,
            requeue_on_exit3=True,
            is_lock_held_fn=is_lock_held,
            lock_file=config.paths.data_dir / "pipeline.lock",
            queue_timeout_s=queue_timeout_s,
            queue_timeout_error=(
                "Délai d'attente dépassé : pipeline.lock toujours tenu après "
                f"{int(queue_timeout_s)}s — résolution abandonnée, relancez-la."
            ),
            requeue_timeout_error=(
                "Délai d'attente dépassé : verrou toujours occupé après "
                f"{int(queue_timeout_s)}s de tentatives — résolution abandonnée."
            ),
            on_success=_continuation,
        )
    )


if __name__ == "__main__":
    main()
