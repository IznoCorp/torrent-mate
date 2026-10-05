"""``LibraryRescrape``: a medium's rescrape, launched through the maintenance path.

The rescrape is ``library.rescrape``: the method is authorised by ``@requires`` before it
opens anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.errors import AppConflict, AppInternalError
from personalscraper.app.library.facts import refuse_not_found
from personalscraper.app.library.identity import Provider, ref_key
from personalscraper.app.library.listing import held_of, open_reader
from personalscraper.app.maintenance.registry import REGISTRY, MaintenanceAction
from personalscraper.app.maintenance.service import LaunchedRun, launch_action, running_run
from personalscraper.core.identity import MediaRef
from personalscraper.indexer.library_view import LibraryIndex
from personalscraper.logger import get_logger

log = get_logger("app.library.rescrape")

__all__ = ["LibraryRescrape", "RescrapeAccepted"]

#: The maintenance action that rescrapes one index row.
_RESCRAPE_ITEM_ACTION: Final[str] = "library-rescrape-item"


@dataclass(frozen=True)
class RescrapeAccepted:
    """A medium's rescrape, accepted: launched, or already under way.

    Attributes:
        provider: The provider the medium was named at.
        provider_id: Its id there, as the wire named it.
        queued: Whether ``pipeline.lock`` was held: the run waits in the visible queue.
        run_uid: The run of the lowest holding row launched now (one run per row holding
            live files), else the lowest holding row's run already under way; ``None``
            when that run ended before it could be read.
    """

    provider: Provider
    provider_id: str
    queued: bool
    run_uid: str | None


class LibraryRescrape:
    """Rescrapes one medium through the maintenance path."""

    def __init__(self, *, index: LibraryIndex, index_db: Path, data_dir: Path) -> None:
        """Hold the index and the paths; nothing is opened yet.

        Args:
            index: ``library.db``, read-only.
            index_db: Path of ``library.db`` (it also holds the maintenance runs).
            data_dir: The pipeline data directory holding ``pipeline.lock``.
        """
        self._index = index
        self._index_db = index_db
        self._data_dir = data_dir

    @requires("rescrapeMedia")
    def request_rescrape(self, actor: Actor, ref: MediaRef) -> RescrapeAccepted:
        """Rescrape one medium: each row holding it with live files, through the maintenance path.

        One ``library-rescrape-item`` run is reserved and spawned per holding row with live
        files (a duplicate with files in both rows rescrapes both), no dry run first. A held
        ``pipeline.lock`` is no refusal: the runs wait in the visible queue. A row whose
        rescrape already runs is no refusal either: the ask is accepted on that run (the
        contract's ``rescrapeMedia`` declares no 409).

        Args:
            actor: Who asks; authorised by ``@requires`` (``library.rescrape``).
            ref: The medium, by the one id the wire names.

        Returns:
            The acceptance, naming the lowest holding row's launched run, else the lowest
            holding row's run already under way; queued when any of them waits on the
            pipeline.

        Raises:
            AppNotFound: ``media.not_found`` when no row holding the id has a live file.
            AppInternalError: When a runner cannot be spawned; the runs spawned before it
                stay live.
            AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read.
        """
        provider, provider_id = ref_key(ref)
        with open_reader(self._index) as reader:
            holders, folders = held_of(reader, ref)
        live = [row.item_id for row in holders if row.item_id in folders]
        if not live:
            raise refuse_not_found(provider.value)
        action = next(a for a in REGISTRY if a.id == _RESCRAPE_ITEM_ACTION)
        launched: list[LaunchedRun] = []
        running: list[LaunchedRun] = []
        for item_id in sorted(live):
            run, joined = self._launch_or_join(action, item_id, provider)
            (running if joined else launched).append(run)
        log.info("app.library.rescrape_launched", provider=provider.value, item_ids=sorted(live))
        answered = launched[0] if launched else running[0]
        return RescrapeAccepted(
            provider=provider,
            provider_id=provider_id,
            queued=any(run.queued for run in (*launched, *running)),
            run_uid=answered.run_uid,
        )

    def _launch_or_join(self, action: MaintenanceAction, item_id: int, provider: Provider) -> tuple[LaunchedRun, bool]:
        """Launch one row's rescrape, or join the one already running.

        The duplicate guard refuses while the row's rescrape runs; that run may end
        between the refusal and the read that names it, and the launch is then retried
        once.

        Args:
            action: The per-medium rescrape.
            item_id: The holding row.
            provider: The provider the medium is asked by, for the logs.

        Returns:
            The run, and whether it was joined rather than launched.

        Raises:
            AppInternalError: When a runner cannot be spawned, or when the row's rescrape is
                refused as running twice yet never found running.
        """
        options = {"item_id": item_id}
        for _attempt in range(2):
            try:
                return launch_action(action, options, db_path=self._index_db, data_dir=self._data_dir), False
            except AppConflict:
                run = running_run(action, options, db_path=self._index_db, data_dir=self._data_dir)
            if run is not None:
                # This row's rescrape is already running: the ask is accepted on that run.
                log.info("app.library.rescrape_already_running", provider=provider.value, item_id=item_id)
                return run, True
            log.info("app.library.rescrape_ended_before_read", provider=provider.value, item_id=item_id)
        raise AppInternalError("the rescrape was refused as running but no run was found")
