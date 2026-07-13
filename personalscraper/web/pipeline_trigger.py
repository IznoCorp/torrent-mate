"""Single authority for launching a pipeline run as a detached subprocess.

Both the web run endpoint (``POST /api/pipeline/run``) and the decisions runner's
§4 continuation — after a ``scrape-resolve`` completes, the media must FINISH its
pipeline (trailers → verify → dispatch), not merely gain an NFO — go through this
ONE function, so there is never a second trigger mechanism: ``pipeline.lock`` stays
the sole gate (single-trigger-authority invariant). When the lock is already held,
no new run is spawned and the caller is told so — the in-flight (or next) run picks
the freshly-prepared item up.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

from personalscraper.lock import is_lock_held
from personalscraper.logger import get_logger

logger = get_logger(__name__)


def spawn_pipeline_run(
    data_dir: Path,
    *,
    trigger_reason: str,
    dry_run: bool = False,
) -> str | None:
    """Spawn a detached ``personalscraper run`` unless a run already holds the lock.

    This is the single place any web-side caller starts a pipeline run. It never
    acquires ``pipeline.lock`` itself — the spawned ``personalscraper run`` process
    does — it only checks it, so the lock remains the one and only trigger gate.

    Args:
        data_dir: The configured data dir holding ``pipeline.lock``.
        trigger_reason: Value forwarded to ``--trigger-reason`` (e.g. ``"web"`` or
            ``"scrape-resolve"``) so the run is tagged by what triggered it.
        dry_run: When ``True``, append ``--dry-run``.

    Returns:
        The new run's ``run_uid`` when a run was spawned, or ``None`` when the
        pipeline lock is already held (a run is active; the item will be picked up
        by the current or next run).
    """
    if is_lock_held(data_dir / "pipeline.lock"):
        logger.info("pipeline_run_deferred_lock_held", trigger_reason=trigger_reason)
        return None

    run_uid = uuid.uuid4().hex
    cmd = [
        sys.executable,
        "-m",
        "personalscraper",
        "run",
        "--no-console",
        f"--trigger-reason={trigger_reason}",
    ]
    if dry_run:
        cmd.append("--dry-run")

    logger.info(
        "pipeline_run_spawned",
        run_uid=run_uid,
        trigger_reason=trigger_reason,
        dry_run=dry_run,
    )
    subprocess.Popen(  # noqa: S603 — fixed argv, no shell, first-party module invocation.
        cmd,
        start_new_session=True,
        env={**os.environ, "PERSONALSCRAPER_RUN_UID": run_uid},
    )
    return run_uid
