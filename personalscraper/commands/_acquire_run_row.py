"""Run-row recording for the acquisition CLIs (§5 / §1 observability).

``follow detect`` and ``grab`` historically wrote NO ``pipeline_run`` row: the
03:00 / 03:20 PM2 crons were invisible everywhere (the Dashboard schedulers
showed « Jamais exécuté » forever) and a manual web grab had no numeric result —
only a raw output tail. ``acquisition_run_row`` closes both gaps:

* **Self-owned row** (cron / human CLI): when ``PERSONALSCRAPER_RUN_UID`` is NOT
  set, the context manager inserts a ``pipeline_run`` row (``kind='maintenance'``,
  ``command=<cli>``, ``trigger='cron'`` under PM2, else ``'cli'``) and finalizes
  it success/error on exit — the schedulers panel and the acquisition surface
  read it.
* **Externally-owned row** (web runner): when ``PERSONALSCRAPER_RUN_UID`` IS set,
  the web runner already reserved + finalizes the row; the CLI only APPENDS its
  structured numeric result to that same row via ``record_counts``.

Either way, ``record_counts`` persists the §5 « résultat chiffré » (« X nouveaux
détectés, Z récupérés », …) as a ``steps_json`` entry with a ``counts`` mapping —
epoch timestamps, per the pipeline_run invariant.

Fail-soft everywhere: an unreadable indexer DB degrades to no recording, never
a crashed cron.
"""

from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter

if TYPE_CHECKING:
    from collections.abc import Iterator

    from personalscraper.conf.models.config import Config

log = get_logger(__name__)


class AcquisitionRunRecorder:
    """Record one acquisition CLI run into ``pipeline_run`` (fail-soft)."""

    def __init__(self, writer: PipelineRunWriter | None, run_uid: str, command: str, owns_row: bool) -> None:
        """Initialize the recorder.

        Args:
            writer: The pipeline-run writer, or ``None`` when recording is
                unavailable (no indexer DB) — every method no-ops.
            run_uid: The run identifier (self-generated or the web runner's).
            command: The CLI command name (``'follow-detect'`` / ``'grab'``).
            owns_row: Whether this recorder inserted (and must finalize) the row.
        """
        self._writer = writer
        self.run_uid = run_uid
        self._command = command
        self._owns_row = owns_row
        self._started_at = time.time()

    def record_counts(self, counts: dict[str, int]) -> None:
        """Persist the run's structured numeric result (§5 « résultat chiffré »).

        Args:
            counts: Count mapping (e.g. ``{"detectes": 3, "recuperes": 1}``).
        """
        if self._writer is None:
            return
        try:
            self._writer.update_step(
                self.run_uid,
                self._command,
                self._started_at,
                time.time(),
                "success",
                counts=counts,
            )
        except Exception as exc:  # noqa: BLE001 — observability must never crash the CLI
            log.warning("acquire_run_counts_failed", run_uid=self.run_uid, error=str(exc))

    def finalize(self, *, error: str | None = None) -> None:
        """Finalize the self-owned row (no-op for an externally-owned row).

        Args:
            error: The failure description, or ``None`` on success.
        """
        if self._writer is None or not self._owns_row:
            return
        try:
            self._writer.finalize(self.run_uid, "error" if error else "success", error=error)
        except Exception as exc:  # noqa: BLE001 — observability must never crash the CLI
            log.warning("acquire_run_finalize_failed", run_uid=self.run_uid, error=str(exc))


@contextmanager
def acquisition_run_row(config: Config, command: str) -> Iterator[AcquisitionRunRecorder]:
    """Record this CLI invocation as a ``pipeline_run`` row (see module doc).

    Args:
        config: The loaded config (``indexer.db_path`` hosts the run table).
        command: The CLI command name (``'follow-detect'`` / ``'grab'``).

    Yields:
        An :class:`AcquisitionRunRecorder` — call ``record_counts`` with the
        run's numeric result; finalization is automatic.
    """
    db_path = config.indexer.db_path
    external_uid = os.environ.get("PERSONALSCRAPER_RUN_UID")

    writer: PipelineRunWriter | None = None
    owns_row = False
    run_uid = external_uid or uuid.uuid4().hex
    # isinstance guard (finding 10.5/C1): a mocked config would stringify to a
    # '<MagicMock …>' filesystem path and leak a junk file — record only when
    # the db path is a real path-like value.
    if isinstance(db_path, (str, Path)):
        try:
            writer = PipelineRunWriter(db_path)
            if external_uid is None:
                # PM2 sets PM2_HOME for its children — a scheduled cron app; a
                # human shell has no PM2 env. The web runner path always carries
                # PERSONALSCRAPER_RUN_UID, so it never reaches this branch.
                trigger = "cron" if os.environ.get("PM2_HOME") else "cli"
                writer.insert(
                    run_uid,
                    trigger=trigger,
                    dry_run=False,
                    pid=os.getpid(),
                    kind="maintenance",
                    command=command,
                    if_absent=True,
                )
                owns_row = True
        except Exception as exc:  # noqa: BLE001 — observability must never crash the CLI
            log.warning("acquire_run_insert_failed", command=command, error=str(exc))
            writer = None

    recorder = AcquisitionRunRecorder(writer, run_uid, command, owns_row)
    try:
        yield recorder
    except BaseException as exc:
        recorder.finalize(error=str(exc) or type(exc).__name__)
        raise
    recorder.finalize()
