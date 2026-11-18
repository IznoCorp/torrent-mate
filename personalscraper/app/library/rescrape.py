"""``LibraryRescrape``: a medium's rescrape, asked through the run queue.

The rescrape is ``library.rescrape``: the method is authorised by ``@requires`` before it
asks anything. It starts nothing itself: the request is queued, and the supervisor's lease
is the only authority that runs it.
"""

from __future__ import annotations

from dataclasses import dataclass

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.library.facts import refuse_not_found
from personalscraper.app.library.identity import Provider, ref_key
from personalscraper.app.library.listing import held_of, open_reader
from personalscraper.app.supervisor.service import RunAsked, RunService
from personalscraper.core.identity import ItemId, MediaRef
from personalscraper.indexer.library_view import LibraryIndex
from personalscraper.logger import get_logger

log = get_logger("app.library.rescrape")

__all__ = ["LibraryRescrape", "RescrapeAccepted"]


@dataclass(frozen=True)
class RescrapeAccepted:
    """A medium's rescrape, accepted: waiting in the queue, or already running.

    Attributes:
        provider: The provider the medium was named at.
        provider_id: Its id there, as the wire named it.
        queued: Whether a request still waits in the queue (not yet admitted by the supervisor).
        run_uid: The uid of the lowest holding row's request (one request per row holding
            live files): the one queued now, or the equal one already waiting or running.
            Always the request's uid.
    """

    provider: Provider
    provider_id: str
    queued: bool
    run_uid: str | None


class LibraryRescrape:
    """Rescrapes one medium through the run queue."""

    def __init__(self, *, index: LibraryIndex, runs: RunService) -> None:
        """Hold the index and the run service; nothing is opened yet.

        Args:
            index: ``library.db``, read-only.
            runs: The in-process enqueue every starter of a run converges on.
        """
        self._index = index
        self._runs = runs

    @requires("rescrapeMedia")
    def request_rescrape(self, actor: Actor, ref: MediaRef) -> RescrapeAccepted:
        """Rescrape one medium: a queued request per holding row with live files.

        One rescrape request is asked per holding row with live files (a duplicate with
        files in both rows rescrapes both). An ask is never refused: an equal request
        already waiting or running answers it.

        Args:
            actor: Who asks; authorised by ``@requires`` (``library.rescrape``).
            ref: The medium, by the one id the wire names.

        Returns:
            The acceptance, naming the lowest holding row's request; queued when any of
            the requests still waits.

        Raises:
            AppNotFound: ``media.not_found`` when no row holding the id has a live file.
            AppForbidden: ``right.missing``, ``instance.forbidden_write`` or ``instance.read_only``.
            AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read.
        """
        provider, provider_id = ref_key(ref)
        with open_reader(self._index) as reader:
            holders, folders = held_of(reader, ref)
        live = sorted(row.item_id for row in holders if row.item_id in folders)
        if not live:
            raise refuse_not_found(provider.value)
        answers: list[RunAsked] = [self._runs.ask_rescrape(actor, item_id=ItemId(item_id)) for item_id in live]
        log.info("app.library.rescrape_asked", provider=provider.value, item_ids=live)
        return RescrapeAccepted(
            provider=provider,
            provider_id=provider_id,
            queued=any(answer.state == "queued" for answer in answers),
            run_uid=answers[0].uid,
        )
