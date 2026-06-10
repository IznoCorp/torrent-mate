"""Concrete DeletePermit + SeedObligationRecorder over acquire/store (RP3).

Deletion-time resolver: joins on seed_obligation.dispatched_path (exact
match + descendants via :meth:`_SeedSubStore.find_active_under`).  Does NOT
use torrent-client content_path — those two trees never overlap after ingest
(DESIGN §7.2).

Fail-open contract: store absent / unreadable / lock-timeout / no-obligation
/ any lookup error → ALLOW. VETO only on positively-known unmet obligation.

Logging: personalscraper.logger.get_logger (NOT structlog.get_logger).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.core.delete_permit import (
    ALLOW,
    PermitDecision,
    veto,
)
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire.store import ConcreteAcquireStore

log = get_logger("acquire.delete_authority")


class DeleteAuthority:
    """Implements DeletePermit and SeedObligationRecorder over the acquire store.

    Injected into dispatch/run.py and maintenance/disk_cleaner.py at the
    composition root. Never imported by those modules directly.

    Attributes:
        _store: The ConcreteAcquireStore (or None if store is absent).
    """

    def __init__(self, store: "ConcreteAcquireStore | None") -> None:
        """Initialise with the acquire store.

        Args:
            store: The ConcreteAcquireStore, or None to use fail-open fallback.
        """
        self._store = store

    def may_delete(self, path: Path) -> PermitDecision:
        """Consult persisted seed obligations before permitting a deletion.

        Uses :meth:`_SeedSubStore.find_active_under` to match the deletion
        path AND its descendants (DESIGN §7.2): when disk_cleaner deletes a
        directory D and an obligation's dispatched_path is D/file.mkv, the
        resolver finds that obligation.  The LIKE is boundary-safe so D does
        NOT match D-other or Dx.

        Fail-open: any error → ALLOW.  VETO only when a positively-known
        unmet obligation exists AND the dispatched_path still exists on disk
        (path-exists guard makes stale obligations inert).  Seed-time only;
        ratio is deferred to C1.

        Args:
            path: Absolute path about to be deleted.

        Returns:
            ALLOW if permitted, veto(reason) if a live unmet obligation exists.
        """
        if self._store is None:
            log.debug("acquire.delete_authority.no_store", path=str(path))
            return ALLOW

        try:
            obligations = self._store.seed.find_active_under(path)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "acquire.delete_authority.lookup_failed",
                path=str(path),
                error=str(exc),
            )
            return ALLOW

        if not obligations:
            return ALLOW

        now = int(time.time())

        for obligation in obligations:
            # Path-exists guard: a stale obligation (crash before move,
            # dispatched_path for a file that was never created) is inert.
            dp = obligation.dispatched_path
            if dp is not None and not Path(dp).exists():
                log.debug(
                    "acquire.delete_authority.stale_obligation_inert",
                    path=str(path),
                    info_hash=obligation.info_hash,
                )
                continue

            # Seed-time check (ratio deferred to C1).
            seed_time_elapsed = now - obligation.added_at
            if seed_time_elapsed >= obligation.min_seed_time_s:
                continue

            # Positively-known unmet obligation → VETO.
            reason = (
                f"seeding obligation not met: tracker={obligation.source_tracker} "
                f"info_hash={obligation.info_hash[:8]}... "
                f"elapsed={seed_time_elapsed}s < required={obligation.min_seed_time_s}s"
            )
            log.warning(
                "acquire.delete_authority.veto",
                path=str(path),
                info_hash=obligation.info_hash,
                source_tracker=obligation.source_tracker,
                seed_time_elapsed=seed_time_elapsed,
                min_seed_time_s=obligation.min_seed_time_s,
            )
            return veto(reason)

        return ALLOW

    def record_dispatch(
        self,
        *,
        staging_source: Path,
        dispatched_dest: Path,
    ) -> None:
        """No-op at this phase — write-before-move logic added in Phase 5.

        Args:
            staging_source: Staging path of the media file.
            dispatched_dest: Destination path after dispatch.
        """
        # Phase 5 adds basename+size torrent correlation here.
        log.debug(
            "acquire.delete_authority.record_dispatch.noop",
            staging_source=str(staging_source),
            dispatched_dest=str(dispatched_dest),
        )


def build_delete_authority(
    store: "ConcreteAcquireStore | None",
) -> DeleteAuthority:
    """Build a DeleteAuthority over the given store.

    Args:
        store: The ConcreteAcquireStore, or None for fail-open no-op.

    Returns:
        A DeleteAuthority ready for injection into dispatch/maintenance.
    """
    return DeleteAuthority(store=store)


__all__ = ["DeleteAuthority", "build_delete_authority"]
