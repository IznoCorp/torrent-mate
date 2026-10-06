"""The preprod's nightly purge: delete the torrents it owns whose seed obligation is met.

The preprod (``PERSONALSCRAPER_ENV=staging``) shares prod's torrent client in its own
category. Its downloads must not pile up, so each night it removes the completed
torrents it owns whose obligation the sweep has WRITTEN as met, and keeps every other
one, saying why. A torrent is purged only when all of these hold:

* it is in scope: the scope's category (other categories are never read, as for every
  scoped reader), every instance tag, and a save path under the scope's download root;
* its hash has an unreleased obligation in the preprod's acquire store whose
  ``satisfied_at`` is set — no obligation row keeps it (a tracker with no economy
  block keeps its downloads until its block is written, operator ruling O-3 B);
* its content path passes the sandbox guard (under the scope's download root, which
  is a marked, mounted preprod root, and not that root itself);
* fewer than ``max_purged`` torrents were purged before it in this run.

The removal is the client's own ``delete(hash, delete_files=True)``, never a
filesystem call from here. Then the obligation is released and the content path is
journaled. Fail-closed: any doubt (an unreadable store, a guard refusal, a client
error on the delete) keeps the torrent, with a verdict and a log line naming why.

Import direction: acquire/ only; the destruction journal (indexer/) arrives as the
``journal`` callable the composition root wires.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from personalscraper.acquire.events import PreprodPurgeCompleted
from personalscraper.api.torrent._base import scoped
from personalscraper.conf.environment import Environment, current_environment
from personalscraper.conf.sandbox_guard import SandboxGuardError, assert_within_sandbox, sandbox_roots
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.api.torrent._base import TorrentItem
    from personalscraper.conf.models.api_config import TorrentScope, TrackerProviderConfig
    from personalscraper.conf.models.config import Config
    from personalscraper.core.event_bus import EventBus

log = get_logger("acquire.preprod_purge")


class PurgeVerdict(StrEnum):
    """What the purge did with one torrent of its scope."""

    PURGED = "purged"
    KEPT_UNMET = "kept_unmet"
    KEPT_UNKNOWN = "kept_unknown"
    KEPT_OUT_OF_SCOPE = "kept_out_of_scope"
    KEPT_OUTSIDE_ROOT = "kept_outside_root"
    KEPT_CAP = "kept_cap"
    KEPT_CLIENT_ERROR = "kept_client_error"


@dataclass(frozen=True)
class PurgeDecision:
    """The purge's decision on one torrent.

    Attributes:
        info_hash: The torrent's info hash, as the client lists it.
        name: The torrent's display name.
        verdict: What was done with it (:attr:`PurgeVerdict.PURGED` in a dry run means « would be »).
        obligation_id: The ``seed_obligation`` row read for it, or ``None`` when none was.
    """

    info_hash: str
    name: str
    verdict: PurgeVerdict
    obligation_id: int | None


class _PurgeClient(Protocol):
    """The two client calls the purge makes: list the completed torrents, delete one."""

    def get_completed(self) -> list[TorrentItem]:
        """List the client's completed torrents."""
        ...

    def delete(self, hash: str, *, delete_files: bool = False) -> None:  # the client's own signature
        """Remove a torrent, and its files when *delete_files*."""
        ...


def _purgeable_without_obligation(tracker_cfg: TrackerProviderConfig | None) -> bool:
    """Say whether a completed torrent with no obligation row may be purged.

    Operator ruling O-3 B: never. A tracker with no ``economy`` block records no
    obligation at grab, and its downloads are kept until the block is written; a purge
    of a torrent whose obligation is not known is a possible hit-and-run on the
    tracker account. (Reading A would return ``tracker_cfg is not None and
    tracker_cfg.economy is None``.)

    Args:
        tracker_cfg: The configuration of the tracker the torrent came from, or
            ``None`` when no tag names a configured tracker.

    Returns:
        ``False``, whatever the tracker.
    """
    del tracker_cfg
    return False


def _require_staging() -> None:
    """Refuse to run outside the preprod.

    Raises:
        SandboxGuardError: ``PERSONALSCRAPER_ENV`` is not ``staging``.
    """
    env = current_environment()
    if env is not Environment.STAGING:
        raise SandboxGuardError(f"the preprod purge runs only under {Environment.STAGING.value!r}, not {env.value!r}")


def _require_scope(config: Config) -> TorrentScope:
    """Return the active client's scope, refusing an absent or empty one.

    A blank category or tag would widen the listing to torrents the preprod does not
    own (a qBittorrent ``tag=""`` filter lists the untagged torrents, i.e. prod's).

    Args:
        config: The loaded configuration.

    Returns:
        The active client's scope.

    Raises:
        SandboxGuardError: No scope, a blank category, no instance tag, or a blank one.
    """
    scope = config.torrent.active_scope()
    if scope is None:
        raise SandboxGuardError("the preprod purge needs a client scope; the active client has none")
    if not scope.category.strip():
        raise SandboxGuardError("the client scope's category is empty")
    if not scope.instance_tags or any(not tag.strip() for tag in scope.instance_tags):
        raise SandboxGuardError("the client scope has an empty instance tag set or an empty tag")
    return scope


def _in_scope(item: TorrentItem, scope: TorrentScope) -> bool:
    """Say whether a torrent of the scope's category carries every instance tag and is saved under the root.

    Args:
        item: A torrent of the scope's category.
        scope: The preprod's scope.

    Returns:
        ``True`` when every instance tag is on the torrent and its real save path is
        the download root or under it.
    """
    if not all(tag in item.tags for tag in scope.instance_tags):
        return False
    if not item.save_path:
        return False
    save = Path(os.path.realpath(item.save_path))
    root = Path(os.path.realpath(scope.download_root))
    return save == root or save.is_relative_to(root)


def _tracker_of(item: TorrentItem, config: Config) -> TrackerProviderConfig | None:
    """Return the configuration of the first tag that names a configured tracker.

    Args:
        item: The torrent.
        config: The loaded configuration.

    Returns:
        That tracker's configuration, or ``None``.
    """
    for tag in item.tags:
        tracker_cfg = config.tracker.providers.get(tag)
        if tracker_cfg is not None:
            return tracker_cfg
    return None


def _guard_content_path(config: Config, item: TorrentItem, scope: TorrentScope) -> Path | None:
    """Return the torrent's content path when the purge may destroy it, else ``None`` (logged).

    Args:
        config: The loaded configuration, naming the preprod's roots.
        item: The torrent.
        scope: The preprod's scope; the content must lie under its download root, the
            same root ``_in_scope`` judged the save path against.

    Returns:
        The content path, when it is under a marked, mounted preprod root, under the
        scope's download root, and is not a root itself; ``None`` otherwise.
    """
    content_path = item.content_path
    if content_path is None:
        log.warning("acquire.preprod_purge.guard_refused", info_hash=item.hash, reason="no content path")
        return None
    try:
        assert_within_sandbox(config, content_path, Environment.STAGING)
        real = Path(os.path.realpath(content_path))
        if not real.is_relative_to(Path(os.path.realpath(scope.download_root))):
            raise SandboxGuardError(f"{content_path} is not under the download root {scope.download_root}")
        if any(real == Path(os.path.realpath(root)) for root in sandbox_roots(config)):
            raise SandboxGuardError(f"{content_path} is a sandbox root itself")
    except (SandboxGuardError, OSError) as exc:
        log.warning("acquire.preprod_purge.guard_refused", info_hash=item.hash, path=str(content_path), reason=str(exc))
        return None
    return content_path


def purge_preprod_downloads(
    store: AcquireStore,
    client: _PurgeClient,
    config: Config,
    *,
    now: int,
    dry_run: bool,
    max_purged: int,
    event_bus: EventBus,
    journal: Callable[[Path], None],
) -> list[PurgeDecision]:
    """Remove the preprod's completed torrents whose seed obligation is written as met.

    Args:
        store: The preprod's acquire store (``store.seed`` is read, and written unless *dry_run*).
        client: The shared torrent client.
        config: The loaded preprod configuration (its client scope and roots).
        now: Unix epoch seconds stamped as ``released_at``.
        dry_run: When ``True``, decide and report only: no delete, no release, no journal.
        max_purged: The most torrents this run purges; the next met ones are kept at the cap.
        event_bus: Bus the one :class:`PreprodPurgeCompleted` of the run is emitted on.
        journal: Records one destruction, given the content path the client deleted;
            called once per purged torrent, never in a dry run.

    Returns:
        One :class:`PurgeDecision` per completed torrent of the scope's category, in
        the client's order.

    Raises:
        SandboxGuardError: Outside ``staging``, or the active client has no usable
            scope — both before any client call.
        Exception: Whatever ``client.get_completed`` raises; nothing was deleted.
    """
    _require_staging()
    scope = _require_scope(config)
    items = scoped(client.get_completed(), scope)

    decisions: list[PurgeDecision] = []
    purged = 0
    for item in items:
        decision = _decide(
            store, client, config, item, scope, now=now, dry_run=dry_run, cap_reached=purged >= max_purged
        )
        decisions.append(decision)
        log.info(
            "acquire.preprod_purge.decision",
            info_hash=item.hash,
            verdict=decision.verdict.value,
            obligation_id=decision.obligation_id,
            dry_run=dry_run,
        )
        if decision.verdict is PurgeVerdict.PURGED:
            purged += 1
            if not dry_run:
                _record(store, journal, item, decision.obligation_id, now)

    kept = len(decisions) - purged
    log.info("acquire.preprod_purge.completed", purged=purged, kept=kept, dry_run=dry_run)
    event_bus.emit(PreprodPurgeCompleted(purged=purged, kept=kept, dry_run=dry_run))
    return decisions


def _decide(
    store: AcquireStore,
    client: _PurgeClient,
    config: Config,
    item: TorrentItem,
    scope: TorrentScope,
    *,
    now: int,
    dry_run: bool,
    cap_reached: bool,
) -> PurgeDecision:
    """Decide on one torrent of the scope's category, deleting it through the client when purged.

    Args:
        store: The preprod's acquire store.
        client: The shared torrent client.
        config: The loaded preprod configuration.
        item: The torrent.
        scope: The preprod's scope.
        now: Unix epoch seconds of the run (logged on a failed delete).
        dry_run: When ``True``, the client is never asked to delete.
        cap_reached: ``True`` once the run purged ``max_purged`` torrents.

    Returns:
        The decision.
    """

    def _kept(verdict: PurgeVerdict, obligation_id: int | None = None) -> PurgeDecision:
        return PurgeDecision(item.hash, item.name, verdict, obligation_id)

    if not _in_scope(item, scope):
        return _kept(PurgeVerdict.KEPT_OUT_OF_SCOPE)

    try:
        obligation = store.seed.find_active_by_hash(item.hash.lower())
    except Exception as exc:  # noqa: BLE001 — fail-closed: a store that cannot answer keeps the torrent
        log.warning("acquire.preprod_purge.store_unreadable", info_hash=item.hash, error=str(exc))
        return _kept(PurgeVerdict.KEPT_UNKNOWN)
    obligation_id = obligation.id if obligation is not None else None
    if obligation is None:
        if not _purgeable_without_obligation(_tracker_of(item, config)):
            return _kept(PurgeVerdict.KEPT_UNKNOWN)
    elif obligation.satisfied_at is None:
        return _kept(PurgeVerdict.KEPT_UNMET, obligation_id)

    if _guard_content_path(config, item, scope) is None:
        return _kept(PurgeVerdict.KEPT_OUTSIDE_ROOT, obligation_id)
    if cap_reached:
        return _kept(PurgeVerdict.KEPT_CAP, obligation_id)

    if not dry_run:
        try:
            client.delete(item.hash, delete_files=True)
        except Exception as exc:  # noqa: BLE001 — fail-closed: a refused delete keeps the torrent unmarked
            log.error("acquire.preprod_purge.delete_failed", info_hash=item.hash, now=now, error=str(exc))
            return _kept(PurgeVerdict.KEPT_CLIENT_ERROR, obligation_id)
    return _kept(PurgeVerdict.PURGED, obligation_id)


def _record(
    store: AcquireStore, journal: Callable[[Path], None], item: TorrentItem, obligation_id: int | None, now: int
) -> None:
    """Release the purged torrent's obligation and journal its content path (each failure logged).

    The torrent is already gone from the client: a failure here is logged, never
    raised, so the run goes on (the sweep releases a row whose torrent stays absent).

    Args:
        store: The preprod's acquire store.
        journal: The destruction journal.
        item: The purged torrent (its content path passed the guard).
        obligation_id: Its obligation row, or ``None`` when it had none.
        now: Unix epoch seconds stamped as ``released_at``.
    """
    if obligation_id is not None:
        try:
            store.seed.mark_released(obligation_id, now)
        except Exception as exc:  # noqa: BLE001 — the delete happened; the sweep will release the row
            log.error("acquire.preprod_purge.release_failed", info_hash=item.hash, error=str(exc))
    if item.content_path is not None:
        try:
            journal(item.content_path)
        except Exception as exc:  # noqa: BLE001 — a journal failure never undoes the delete it records
            log.error("acquire.preprod_purge.journal_failed", info_hash=item.hash, error=str(exc))


__all__ = ["PurgeDecision", "PurgeVerdict", "purge_preprod_downloads"]
