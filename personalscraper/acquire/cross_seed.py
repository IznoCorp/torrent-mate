"""Cross-seeding engine — thin orchestration over RP10a+b + existing ports.

This module lives in ``acquire/`` per DESIGN §Architecture: it depends
downward on ``api/`` ports + ``acquire.db``, never importing triage packages.
"""

from __future__ import annotations

import time as _time_module
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from personalscraper.acquire.domain import SeedObligation
from personalscraper.acquire.events import CrossSeedInjected, CrossSeedRejected
from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api.torrent._base import TorrentItem, _bencode_info_hash, parse_torrent_layout
from personalscraper.api.torrent._layout import MatchVerdict, TorrentLayout, structural_match
from personalscraper.api.tracker._errors import TorrentFetchError, TrackerAuthError
from personalscraper.api.tracker._fetch import resolve_source
from personalscraper.core._contracts import CircuitOpenError
from personalscraper.core.event_bus import EventBus
from personalscraper.core.tags import SEED_PURE
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire.store import ConcreteAcquireStore
    from personalscraper.api.torrent._contracts import (
        TorrentController,
        TorrentInjector,
        TorrentLister,
        TorrentTagger,
    )
    from personalscraper.api.tracker._base import TrackerResult
    from personalscraper.api.tracker._registry import TrackerRegistry
    from personalscraper.conf.models.config import Config

logger = get_logger(__name__)

# Recheck verification timeout and poll interval (seconds).
_VERIFY_TIMEOUT_S = 120
_VERIFY_POLL_INTERVAL_S = 2


@dataclass
class CrossSeedResult:
    """Result of one :meth:`CrossSeedService.check` call.

    Attributes:
        injected: Info-hashes of successfully injected cross-seeds.
        rejected: ``(candidate_hash_or_id, tracker, reason)`` triples for
            each candidate that was considered but rejected.
        skipped: ``True`` when the entire check was skipped (kill-switch,
            not-found, seed-pure, etc.).
        skip_reason: Machine-readable reason for the skip, or ``None``.
    """

    injected: list[str] = field(default_factory=list)
    rejected: list[tuple[str, str, str]] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None


@dataclass
class SweepResult:
    """Result of one :meth:`CrossSeedService.sweep` call (X2 — back-catalog).

    Attributes:
        checked: Number of torrents where :meth:`CrossSeedService.check` was
            actually invoked.
        injected: Total number of successfully injected cross-seeds across
            all checked torrents.
        quota_exhausted: ``True`` when the sweep stopped early because the
            daily quota was reached.
    """

    checked: int = 0
    injected: int = 0
    quota_exhausted: bool = False


class CrossSeedService:
    """Orchestrates cross-seed matching + injection for completed torrents.

    One instance per process lifetime, built in :func:`_build_app_context`.
    Depends on *ports* (protocols), not concrete tracker/transport
    implementations — inject fakes for testing.

    Attributes:
        _registry: Multi-tracker search coordinator.
        _lister: Torrent listing capability (read-only).
        _injector: Torrent injection capability.
        _controller: Torrent lifecycle control (resume, delete).
        _tagger: Torrent tagging capability.
        _store: The acquire store (cross_seed history + seed obligations).
        _config: The loaded application configuration.
        _event_bus: In-process event bus — ``CrossSeedInjected`` and
            ``CrossSeedRejected`` are emitted unconditionally per the
            emit-after-persist convention.
        _clock: Monotonic clock callable (default: :func:`time.monotonic`).
        _sleep: Sleep callable (default: :func:`time.sleep`).
    """

    def __init__(
        self,
        registry: TrackerRegistry,
        lister: TorrentLister,
        injector: TorrentInjector,
        controller: TorrentController,
        tagger: TorrentTagger,
        store: ConcreteAcquireStore,
        config: Config,
        event_bus: EventBus,
        clock: Callable[[], float] = _time_module.monotonic,
        sleep: Callable[[float], None] = _time_module.sleep,
    ) -> None:
        """Initialise with injected narrow dependencies.

        Args:
            registry: Multi-tracker search coordinator.
            lister: Torrent listing capability.
            injector: Torrent injection capability.
            controller: Torrent lifecycle control (resume, delete).
            tagger: Torrent tagging capability.
            store: The acquire store.
            config: The loaded application configuration.
            event_bus: In-process event bus for typed emission.
            clock: Monotonic clock callable (injectable for tests).
            sleep: Sleep callable (injectable for tests).
        """
        self._registry = registry
        self._lister = lister
        self._injector = injector
        self._controller = controller
        self._tagger = tagger
        self._store = store
        self._config = config
        self._event_bus = event_bus
        self._clock = clock
        self._sleep = sleep

    def check(self, info_hash: str) -> CrossSeedResult:
        """Per-completion cross-seed for a single torrent (X1 — D3).

        Implements the DESIGN §"Cross-seed engine flow":

        1. Global kill-switch check.
        2. Locate source torrent via :meth:`TorrentLister.get_completed`.
        3. Skip ``SEED_PURE``-tagged torrents.
        4. Read local layout via :meth:`TorrentInjector.list_files` +
           :meth:`TorrentInjector.properties`.
        5. Determine eligible target trackers (``cross_seed=true``, enabled,
           not origin, not recently searched).
        6. Search candidates by release name via
           :meth:`TrackerRegistry.search_candidates`, grouped by provider.
        7. For each candidate: fetch → parse → structural_match → inject →
           verify → resume + tag + obligation.

        Args:
            info_hash: V1 info-hash of the completed source torrent.

        Returns:
            A :class:`CrossSeedResult` describing injected/rejected/skipped.
        """
        result = CrossSeedResult()

        # 1. Global kill-switch.
        if not self._config.cross_seed.enabled:
            logger.info("acquire.cross_seed.skip", info_hash=info_hash, reason="disabled")
            result.skipped = True
            result.skip_reason = "disabled"
            return result

        # 2. Locate source TorrentItem.
        item = self._find_completed(info_hash)
        if item is None:
            logger.info("acquire.cross_seed.skip", info_hash=info_hash, reason="not_found")
            result.skipped = True
            result.skip_reason = "not_found"
            return result

        # 3. Skip SEED_PURE (it IS a cross-seed already).
        if SEED_PURE in item.tags:
            logger.info("acquire.cross_seed.skip", info_hash=info_hash, reason="seed_pure")
            result.skipped = True
            result.skip_reason = "seed_pure"
            return result

        # 4. Read local layout.
        local_layout = self._build_local_layout(item)
        if local_layout is None:
            logger.info("acquire.cross_seed.skip", info_hash=info_hash, reason="no_piece_size")
            result.skipped = True
            result.skip_reason = "no_piece_size"
            return result

        # Reject v2/hybrid local — can never structurally match under v1 semantics.
        if local_layout.meta_version == 2:
            logger.info("acquire.cross_seed.skip", info_hash=info_hash, reason="v2_hybrid")
            result.skipped = True
            result.skip_reason = "v2_hybrid"
            return result

        # 5. Determine eligible target trackers, excluding origin + recently searched.
        origin_tracker = self._resolve_origin(item)
        eligible = self._eligible_trackers(origin_tracker)
        exclude_days = self._config.cross_seed.exclude_recent_search_days
        remaining = [
            t for t in eligible if not self._store.cross_seed.was_searched_recently(info_hash, t, exclude_days)
        ]
        if not remaining:
            logger.info(
                "acquire.cross_seed.skip",
                info_hash=info_hash,
                reason="all_excluded_recent",
                eligible_count=len(eligible),
            )
            result.skipped = True
            result.skip_reason = "all_excluded_recent"
            return result

        # 6. Search candidates by release name (D7 — strongest signal).
        # The registry does not support per-tracker restriction, so we search
        # all managed trackers once and group results by provider.
        search_outcome = self._registry.search_candidates(item.name, MediaType.MOVIE)
        candidates_by_provider: dict[str, list["TrackerResult"]] = {}
        for r in search_outcome.results:
            candidates_by_provider.setdefault(r.provider, []).append(r)

        # Record search for each target tracker (history only — per-completion
        # searches are quota-exempt per DESIGN §Config).
        for tracker in remaining:
            self._store.cross_seed.record_search(info_hash, tracker)

        # 7-8. Per-tracker → per-candidate loop.
        # ONE injection per source torrent max (first match wins).
        for tracker in remaining:
            candidates = candidates_by_provider.get(tracker, [])
            if not candidates:
                logger.debug("acquire.cross_seed.no_candidates", info_hash=info_hash, tracker=tracker)
                continue

            for candidate in candidates:
                # 7. Fetch .torrent bytes (fail-soft per candidate).
                try:
                    source = resolve_source(candidate, self._registry.transports())
                except (TorrentFetchError, TrackerAuthError, CircuitOpenError, ApiError) as exc:
                    logger.warning(
                        "acquire.cross_seed.rejected",
                        info_hash=info_hash,
                        tracker=tracker,
                        reason="fetch_failed",
                        error=str(exc),
                    )
                    result.rejected.append((_candidate_id(candidate), tracker, "fetch_failed"))
                    self._event_bus.emit(
                        CrossSeedRejected(
                            info_hash=_candidate_id(candidate),
                            tracker=tracker,
                            reason="fetch_failed",
                            source_hash=info_hash,
                        )
                    )
                    continue

                # Cross-seed only works with .torrent file bytes (not magnets).
                if source.file_bytes is None:
                    logger.debug(
                        "acquire.cross_seed.rejected",
                        info_hash=info_hash,
                        tracker=tracker,
                        reason="magnet_not_supported",
                    )
                    result.rejected.append((_candidate_id(candidate), tracker, "magnet_not_supported"))
                    self._event_bus.emit(
                        CrossSeedRejected(
                            info_hash=_candidate_id(candidate),
                            tracker=tracker,
                            reason="magnet_not_supported",
                            source_hash=info_hash,
                        )
                    )
                    continue

                # Parse candidate layout.
                try:
                    candidate_layout = parse_torrent_layout(source.file_bytes)
                except ValueError as exc:
                    logger.warning(
                        "acquire.cross_seed.rejected",
                        info_hash=info_hash,
                        tracker=tracker,
                        reason="parse_failed",
                        error=str(exc),
                    )
                    result.rejected.append((_candidate_id(candidate), tracker, "parse_failed"))
                    self._event_bus.emit(
                        CrossSeedRejected(
                            info_hash=_candidate_id(candidate),
                            tracker=tracker,
                            reason="parse_failed",
                            source_hash=info_hash,
                        )
                    )
                    continue

                # Self-candidate guard: compute the candidate's v1 info-hash
                # and reject when it equals the source info_hash.  This covers
                # byte-identical same-hash releases cross-posted on other
                # trackers (injecting the same hash is always a no-op at best
                # and a recheck/delete hazard at worst) and the case where the
                # origin tracker is unresolvable and the search returns the
                # source torrent itself.
                # Wrapped in try/except ValueError — proceed without the guard
                # but log hash_uncomputable (belt-and-braces delete guard below
                # still protects against self-deletion when inject returns the
                # source hash).
                try:
                    candidate_hash = _bencode_info_hash(source.file_bytes)
                except ValueError:
                    logger.debug(
                        "acquire.cross_seed.hash_uncomputable",
                        info_hash=info_hash,
                        tracker=tracker,
                    )
                else:
                    if candidate_hash.lower() == info_hash.lower():
                        logger.info(
                            "acquire.cross_seed.rejected",
                            info_hash=info_hash,
                            tracker=tracker,
                            reason="self_candidate",
                        )
                        result.rejected.append((_candidate_id(candidate), tracker, "self_candidate"))
                        self._event_bus.emit(
                            CrossSeedRejected(
                                info_hash=_candidate_id(candidate),
                                tracker=tracker,
                                reason="self_candidate",
                                source_hash=info_hash,
                            )
                        )
                        continue

                # Structural match — strict full-match only (D4).
                verdict = structural_match(local_layout, candidate_layout)
                if verdict != MatchVerdict.MATCH:
                    logger.debug(
                        "acquire.cross_seed.rejected",
                        info_hash=info_hash,
                        tracker=tracker,
                        reason=verdict.value,
                    )
                    result.rejected.append((_candidate_id(candidate), tracker, verdict.value))
                    self._event_bus.emit(
                        CrossSeedRejected(
                            info_hash=_candidate_id(candidate),
                            tracker=tracker,
                            reason=verdict.value,
                            source_hash=info_hash,
                        )
                    )
                    continue

                # 8. MATCH → inject → verify → resume + tag + obligation.
                injected_hash = self._injector.inject(
                    source.file_bytes,
                    save_path=item.save_path,
                    recheck=True,
                    paused=True,
                )

                if self._verify_injection(injected_hash):
                    # Verified → resume, tag SEED_PURE, write obligation (D10).
                    self._controller.resume(injected_hash)
                    try:
                        self._tagger.add_tags(injected_hash, [SEED_PURE])
                    except Exception as exc:  # noqa: BLE001 — best-effort tagging
                        logger.warning(
                            "acquire.cross_seed.tag_failed",
                            info_hash=injected_hash,
                            error=str(exc),
                        )
                    self._write_obligation(injected_hash, tracker, item)
                    self._event_bus.emit(
                        CrossSeedInjected(
                            info_hash=injected_hash,
                            source_tracker=tracker,
                            source_hash=info_hash,
                            save_path=item.save_path,
                        )
                    )
                    logger.info(
                        "acquire.cross_seed.injected",
                        info_hash=info_hash,
                        injected_hash=injected_hash,
                        tracker=tracker,
                    )
                    result.injected.append(injected_hash)
                    # ONE injection per source torrent max — first match wins.
                    return result
                else:
                    # Recheck failed → remove injection, NO obligation (D10).
                    # Belt-and-braces: guard the delete when injected_hash equals
                    # the source info_hash (self-candidate that slipped through
                    # the early guard because _bencode_info_hash raised ValueError
                    # → hash_uncomputable).  Deleting the source torrent itself
                    # would be a catastrophic data-loss bug.
                    if injected_hash.lower() == info_hash.lower():
                        logger.error(
                            "acquire.cross_seed.self_delete_averted",
                            info_hash=info_hash,
                            injected_hash=injected_hash,
                            tracker=tracker,
                        )
                    else:
                        self._controller.delete(injected_hash, delete_files=False)
                    logger.warning(
                        "acquire.cross_seed.rejected",
                        info_hash=info_hash,
                        injected_hash=injected_hash,
                        tracker=tracker,
                        reason="recheck_failed",
                    )
                    result.rejected.append((injected_hash, tracker, "recheck_failed"))
                    self._event_bus.emit(
                        CrossSeedRejected(
                            info_hash=injected_hash,
                            tracker=tracker,
                            reason="recheck_failed",
                            source_hash=info_hash,
                        )
                    )
                    # Continue to next candidate in this tracker.

        return result

    def sweep(self) -> SweepResult:
        """Throttled back-catalog sweep over all completed torrents (X2 — D6).

        Iterates every completed torrent via :meth:`TorrentLister.get_completed`,
        skipping ``SEED_PURE``-tagged items.  For each eligible torrent:

        * **Quota gate** — checks
          :meth:`~personalscraper.acquire.store._CrossSeedSubStore.daily_searches_remaining`
          against ``max_searches_per_day``; stops early when quota is exhausted.
        * Calls :meth:`check` for the torrent.
        * Only counts a **quota unit** when :meth:`check` actually searched
          (i.e. the result was NOT skipped) — one unit per source torrent,
          even when ``check()`` queries several trackers.  This is documented
          in the :class:`~personalscraper.conf.models.watch_seed.CrossSeedConfig`
          docstring: the quota is per-source-torrent sweep operation.
        * Honours ``min_delay_between_searches_s`` by sleeping between
          quota-counted ``check()`` calls (not after skipped ones, not after
          the last).

        Per-completion searches (``check()`` called standalone) are
        **quota-exempt** — only the back-catalog sweep counts toward the
        daily cap.

        Global kill-switch: when ``cross_seed.enabled`` is ``False``, returns
        immediately with all fields zero and ``quota_exhausted=False``.

        Returns:
            A :class:`SweepResult` with counts for checked, injected, and
            whether the sweep stopped early due to quota exhaustion.
        """
        # Global kill-switch.
        if not self._config.cross_seed.enabled:
            logger.info("acquire.cross_seed.sweep.skip", reason="disabled")
            return SweepResult()

        logger.info("acquire.cross_seed.sweep.started")

        checked = 0
        injected = 0
        quota_exhausted = False
        max_per_day = self._config.cross_seed.max_searches_per_day
        delay = self._config.cross_seed.min_delay_between_searches_s
        need_sleep = False  # Set after a quota-counted check(); cleared on skip.

        try:
            completed = self._lister.get_completed()
        except Exception as exc:  # noqa: BLE001 — fail-soft, logged
            logger.warning(
                "acquire.cross_seed.sweep.lister_error",
                error=str(exc),
            )
            return SweepResult()

        for item in completed:
            # Skip SEED_PURE (cheap tag check — avoids wasted check() call).
            if SEED_PURE in item.tags:
                continue

            # Quota gate — stop if no daily searches remain.
            remaining = self._store.cross_seed.daily_searches_remaining(max_per_day)
            if remaining <= 0:
                quota_exhausted = True
                logger.info(
                    "acquire.cross_seed.sweep.quota_exhausted",
                    checked=checked,
                    injected=injected,
                    max_per_day=max_per_day,
                )
                break

            # Honour inter-search delay between quota-counted calls.
            if need_sleep:
                self._sleep(delay)

            result = self.check(item.hash)
            checked += 1
            injected += len(result.injected)

            if not result.skipped:
                # Count ONE quota unit per source torrent that was actually
                # searched (even if check() queried several trackers).
                self._store.cross_seed.increment_daily_count()
                need_sleep = True
            # If skipped, need_sleep stays as-is — no sleep before the next item.

        logger.info(
            "acquire.cross_seed.sweep.finished",
            checked=checked,
            injected=injected,
            quota_exhausted=quota_exhausted,
        )
        return SweepResult(
            checked=checked,
            injected=injected,
            quota_exhausted=quota_exhausted,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_completed(self, info_hash: str) -> TorrentItem | None:
        """Return the completed :class:`TorrentItem` for *info_hash*, or ``None``.

        Args:
            info_hash: V1 info-hash to locate.

        Returns:
            The matching :class:`TorrentItem` if found in completed torrents,
            else ``None``.
        """
        try:
            completed = self._lister.get_completed()
        except Exception as exc:  # noqa: BLE001 — fail-soft, logged
            logger.warning(
                "acquire.cross_seed.lister_error",
                info_hash=info_hash,
                error=str(exc),
            )
            return None
        for item in completed:
            if item.hash == info_hash:
                return item
        return None

    def _build_local_layout(self, item: TorrentItem) -> TorrentLayout | None:
        """Build a :class:`TorrentLayout` from the local torrent's metadata.

        Normalizes the qBittorrent :meth:`list_files` output to the same
        root-excluded frame that :func:`~personalscraper.api.torrent._base.parse_torrent_layout`
        produces (see :func:`_normalize_qbit_files` for the convention).

        Args:
            item: The source :class:`TorrentItem`.

        Returns:
            A :class:`TorrentLayout` built from the local torrent's file list
            and properties, or ``None`` if ``piece_size`` is missing from
            properties.
        """
        files = self._injector.list_files(item.hash)
        props = self._injector.properties(item.hash)
        piece_size_raw = props.get("piece_size")
        if piece_size_raw is None:
            logger.warning(
                "acquire.cross_seed.no_piece_size",
                info_hash=item.hash,
                properties_keys=list(props.keys()),
            )
            return None
        if isinstance(piece_size_raw, int):
            piece_length = piece_size_raw
        elif isinstance(piece_size_raw, str):
            piece_length = int(piece_size_raw)
        else:
            logger.warning(
                "acquire.cross_seed.no_piece_size",
                info_hash=item.hash,
                piece_size_type=type(piece_size_raw).__name__,
            )
            return None
        # Read meta_version from properties when available.
        # qBittorrent does not expose this in ``torrents/properties``, but
        # the fake injector in tests can inject it so the v2/hybrid skip is
        # exercised — and a future qBit API that DOES include it Just Works.
        meta_version_raw = props.get("meta_version")
        if meta_version_raw is not None:
            if isinstance(meta_version_raw, int):
                meta_version = meta_version_raw
            elif isinstance(meta_version_raw, str):
                meta_version = int(meta_version_raw)
            else:
                meta_version = 1
        else:
            meta_version = 1

        # Normalize qBit list_files output to the candidate frame: qBittorrent
        # ``torrents/files`` returns names INCLUDING the root folder for
        # multi-file torrents, while parse_torrent_layout yields root-excluded
        # paths.  Stripping the shared prefix and using it as the layout name
        # makes the two frames comparable.
        normalized_files, layout_name = _normalize_qbit_files(files, item.name)
        total_size = sum(size for _, size in normalized_files)
        return TorrentLayout(
            name=layout_name,
            piece_length=piece_length,
            files=normalized_files,
            total_size=total_size,
            meta_version=meta_version,
        )

    def _resolve_origin(self, item: TorrentItem) -> str | None:
        """Resolve the origin tracker from *item*'s tags.

        Intersects ``item.tags`` with the known tracker provider names from
        config. The first tag that names a configured tracker wins — same
        convention as :class:`DeleteAuthority._resolve_tracker`.

        Args:
            item: The source :class:`TorrentItem`.

        Returns:
            The origin tracker name, or ``None`` if unresolved.
        """
        known_trackers = set(self._config.tracker.providers.keys())
        for tag in item.tags:
            if tag in known_trackers:
                return tag
        logger.warning(
            "acquire.cross_seed.origin_unresolved",
            info_hash=item.hash,
            tags=item.tags,
        )
        return None

    def _eligible_trackers(self, origin: str | None) -> list[str]:
        """Return ordered list of eligible target tracker names.

        A tracker is eligible when it is enabled, has ``cross_seed=True``,
        and is not the origin tracker.  Order follows the configured
        ``tracker.priority`` list.

        Args:
            origin: The origin tracker name, or ``None``.

        Returns:
            Ordered list of eligible tracker names.
        """
        providers = self._config.tracker.providers
        eligible: list[str] = []
        for name in self._config.tracker.priority:
            provider_cfg = providers.get(name)
            if provider_cfg is None:
                continue
            if not provider_cfg.enabled:
                continue
            if not provider_cfg.cross_seed:
                continue
            if name == origin:
                continue
            eligible.append(name)
        return eligible

    def _verify_injection(self, injected_hash: str) -> bool:
        """Poll until *injected_hash* appears verified or timeout.

        Args:
            injected_hash: The info-hash of the injected torrent.

        Returns:
            ``True`` if the injection was verified (progress >= 1.0) within
            the module-level timeout, ``False`` otherwise.
        """
        deadline = self._clock() + _VERIFY_TIMEOUT_S
        while self._clock() < deadline:
            try:
                completed = self._lister.get_completed()
            except Exception as exc:  # noqa: BLE001 — fail-soft poll error
                logger.warning(
                    "acquire.cross_seed.verify_poll_error",
                    injected_hash=injected_hash,
                    error=str(exc),
                )
                self._sleep(_VERIFY_POLL_INTERVAL_S)
                continue
            for item in completed:
                if item.hash == injected_hash and item.progress >= 1.0:
                    return True
            self._sleep(_VERIFY_POLL_INTERVAL_S)
        logger.warning(
            "acquire.cross_seed.verify_timeout",
            injected_hash=injected_hash,
            timeout_s=_VERIFY_TIMEOUT_S,
        )
        return False

    def _write_obligation(self, injected_hash: str, tracker: str, source_item: TorrentItem) -> None:
        """Write a :class:`SeedObligation` for the verified cross-seed injection.

        Fail-soft: a store write error is logged and swallowed — a lost
        obligation degrades to fail-open at deletion time, same contract as
        :class:`DeleteAuthority.record_dispatch`.

        Obligation fields (D10): ``source_tracker`` is the *target* tracker
        (where the cross-seed was injected), ``min_seed_time_s`` /
        ``min_ratio`` are read from that tracker's
        :class:`TrackerEconomyConfig`, defaulting to 0 when absent (same
        convention as the delete authority).

        Args:
            injected_hash: The info-hash of the injected torrent.
            tracker: The target tracker name.
            source_item: The source :class:`TorrentItem` (for content path).
        """
        provider_cfg = self._config.tracker.providers.get(tracker)
        economy = provider_cfg.economy if provider_cfg else None
        min_seed_time_s = economy.min_seed_time if economy else 0
        min_ratio = economy.min_ratio if economy else 0.0

        dispatched_path = str(source_item.content_path) if source_item.content_path else source_item.save_path

        obligation = SeedObligation(
            info_hash=injected_hash,
            source_tracker=tracker,
            min_seed_time_s=min_seed_time_s,
            min_ratio=min_ratio,
            added_at=int(_time_module.time()),
            dispatched_path=dispatched_path,
        )
        try:
            self._store.seed.add(obligation)
        except Exception as exc:  # noqa: BLE001 — fail-soft store write
            logger.warning(
                "acquire.cross_seed.obligation_write_failed",
                info_hash=injected_hash,
                tracker=tracker,
                error=str(exc),
            )


def _normalize_qbit_files(
    files: list[tuple[str, int]],
    item_name: str,
) -> tuple[list[tuple[str, int]], str]:
    """Normalize qBittorrent ``list_files`` output to the candidate frame.

    qBittorrent ``torrents/files`` returns names that INCLUDE the torrent
    root folder for multi-file torrents (``"Root/inner.mkv"``), while
    :func:`~personalscraper.api.torrent._base.parse_torrent_layout` yields
    paths relative to ``info.name`` WITHOUT the root (``"inner.mkv"``).
    This function strips the shared root prefix so the two frames are
    comparable via :func:`~personalscraper.api.torrent._layout.structural_match`.

    Args:
        files: The ``(path, size)`` list from qBittorrent's ``list_files``.
        item_name: The torrent's display name from qBittorrent
            (``item.name``), used as a fallback when no shared root is found.

    Returns:
        A ``(normalized_files, layout_name)`` pair.  *layout_name* is either
        the shared root component stripped from the paths or *item_name* when
        no shared root exists.
    """
    if not files:
        return files, item_name

    # Single-file torrent: the entry name IS the filename, same as info.name
    # from the .torrent.  qBit does not prefix single-file paths with a root
    # component, so the frames already agree — leave as-is.
    if len(files) == 1 and "/" not in files[0][0]:
        return files, item_name

    # Multi-file or path-containing entries: compute the first path component
    # of every entry.  If ALL entries share the same first component, it is
    # the torrent root injected by qBit — strip it and use it as the layout
    # name (more truthful than the renameable qBit display name).
    first_components: list[str | None] = []
    for path, _size in files:
        if "/" in path:
            first_components.append(path.split("/", 1)[0])
        else:
            first_components.append(None)

    unique_roots = {c for c in first_components if c is not None}

    if len(unique_roots) == 1 and None not in first_components:
        # All entries share the same root prefix — strip it.
        root = unique_roots.pop()
        stripped: list[tuple[str, int]] = [(path[len(root) + 1 :], size) for path, size in files]
        return stripped, root

    # Mixed roots (e.g. "DirA/file1" + "DirB/file2") or entries without "/"
    # (e.g. flat multi-file at top level): leave paths as-is, use item.name.
    return files, item_name


def _candidate_id(candidate: object) -> str:
    """Return a stable identifier string for a tracker search result.

    Prefers ``info_hash`` (hex or base32) when available; falls back to
    a truncated download URL for results that carry no hash.

    Args:
        candidate: A :class:`~personalscraper.api.tracker._base.TrackerResult`
            or compatible object with ``info_hash`` and ``download_url``
            attributes.

    Returns:
        A human-readable identifier string (≤ 80 chars).
    """
    info_hash = getattr(candidate, "info_hash", None)
    if info_hash:
        return str(info_hash)[:80]
    download_url = getattr(candidate, "download_url", None)
    if download_url:
        return str(download_url)[:80]
    return "unknown"


__all__ = ["CrossSeedResult", "CrossSeedService", "SweepResult"]
