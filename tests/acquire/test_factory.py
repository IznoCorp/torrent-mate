"""Unit tests for build_acquire_context — acquire-lobe RP5c + RP3 store wiring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire._ports import AcquireStore as AcquireStoreProtocol
from personalscraper.acquire.store import ConcreteAcquireStore


class TestBuildAcquireContext:
    """build_acquire_context() wires tracker_registry + a lazy store, propagates torrent_client."""

    def _minimal_config(self, tmp_path: Path | None = None) -> MagicMock:
        """Return a MagicMock config with the attributes build_acquire_context reads.

        Args:
            tmp_path: If given, sets a real ``acquire.db`` path so the lazily-
                built store can be opened; otherwise the store stays inert.
        """
        config = MagicMock()
        # build_tracker_registry reads config.tracker, config.ranking.
        # build_acquire_store reads config.acquire (a resolved db_path).
        if tmp_path is not None:
            config.acquire.db_path = tmp_path / "acquire.db"
        return config

    def test_store_is_a_lazy_acquire_store(self) -> None:
        """build_acquire_context fills the store slot with a live AcquireStore (lazy)."""
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
            mock_build.return_value = MagicMock()
            ctx = build_acquire_context(config, settings, event_bus=event_bus, cb_policy=cb_policy)

        assert ctx.store is not None
        assert isinstance(ctx.store, ConcreteAcquireStore)
        # Runtime-checkable protocol conformance (sub-store properties present).
        assert isinstance(ctx.store, AcquireStoreProtocol)

    def test_building_context_does_not_open_acquire_db(self, tmp_path: Path) -> None:
        """LAZINESS: building a context opens NO connection / db file (no boot I/O).

        Proves the regression fix at the factory level: the shared composition
        root must not open acquire.db (and thus must not take any lock) at boot,
        so unrelated commands are never serialized.
        """
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config(tmp_path)
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
            mock_build.return_value = MagicMock()
            ctx = build_acquire_context(config, settings, event_bus=event_bus, cb_policy=cb_policy)

        store = ctx.store
        assert isinstance(store, ConcreteAcquireStore)
        assert store._conn is None  # never opened
        assert not (tmp_path / "acquire.db").exists()  # no db file created at boot

    def test_context_close_propagates_to_store(self, tmp_path: Path) -> None:
        """AcquireContext.close() closes the lazily-built store (fail-soft)."""
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config(tmp_path)
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
            mock_build.return_value = MagicMock()
            ctx = build_acquire_context(config, settings, event_bus=event_bus, cb_policy=cb_policy)

        store = ctx.store
        assert isinstance(store, ConcreteAcquireStore)
        _ = store.follow  # open the connection
        assert store._conn is not None
        ctx.close()  # propagates to store.close()
        assert store._closed is True

    def test_torrent_client_none_when_not_passed(self) -> None:
        """torrent_client defaults to None when not supplied."""
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
            mock_build.return_value = MagicMock()
            ctx = build_acquire_context(config, settings, event_bus=event_bus, cb_policy=cb_policy)

        assert ctx.torrent_client is None

    def test_torrent_client_propagated_when_passed(self) -> None:
        """torrent_client is stored on the context when explicitly passed."""
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()
        fake_client = MagicMock()

        with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
            mock_build.return_value = MagicMock()
            ctx = build_acquire_context(
                config,
                settings,
                event_bus=event_bus,
                cb_policy=cb_policy,
                torrent_client=fake_client,
            )

        assert ctx.torrent_client is fake_client

    def test_delegates_to_build_tracker_registry(self) -> None:
        """build_acquire_context calls build_tracker_registry with config.tracker, config.ranking."""
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
            fake_registry = MagicMock()
            mock_build.return_value = fake_registry
            ctx = build_acquire_context(config, settings, event_bus=event_bus, cb_policy=cb_policy)

        mock_build.assert_called_once_with(
            config.tracker,
            config.ranking,
            settings=settings,
            event_bus=event_bus,
            cb_policy=cb_policy,
        )
        assert ctx.tracker_registry is fake_registry

    def test_delete_authority_is_attached(self, tmp_path: Path) -> None:
        """build_acquire_context attaches a DeleteAuthority to the context."""
        from personalscraper.acquire._factory import build_acquire_context
        from personalscraper.acquire.delete_authority import DeleteAuthority

        config = self._minimal_config(tmp_path)
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
            mock_build.return_value = MagicMock()
            ctx = build_acquire_context(config, settings, event_bus=event_bus, cb_policy=cb_policy)

        assert isinstance(ctx.delete_authority, DeleteAuthority)
        assert ctx.delete_authority._store is ctx.store

    def test_delete_authority_fail_open_when_store_unset(self) -> None:
        """DeleteAuthority built with store=None (no db_path) is fail-open."""
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config()  # no tmp_path → store is inert, but not None
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
            mock_build.return_value = MagicMock()
            ctx = build_acquire_context(config, settings, event_bus=event_bus, cb_policy=cb_policy)

        # The store is NOT None — it's a ConcreteAcquireStore. The factory builds
        # it unconditionally (guarded by config.acquire.db_path).  The delete_authority
        # borrows the same store handle, so it's present when the store is present.
        assert ctx.delete_authority is not None

    def test_tracker_config_error_surfaces(self) -> None:
        """TrackerConfigError from build_tracker_registry propagates unchanged."""
        from personalscraper.acquire._factory import build_acquire_context
        from personalscraper.api.tracker._errors import TrackerConfigError, TrackerConfigIssue

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        issue = TrackerConfigIssue(
            severity="error",
            code="missing_credentials",
            provider="lacale",
            message="no key",
        )
        with patch(
            "personalscraper.acquire._factory.build_tracker_registry",
            side_effect=TrackerConfigError([issue]),
        ):
            with pytest.raises(TrackerConfigError):
                build_acquire_context(config, settings, event_bus=event_bus, cb_policy=cb_policy)

    def test_economy_map_excludes_none_economy_providers(self, tmp_path: Path) -> None:
        """The economy map carries ONLY trackers whose ``economy`` is set (None excluded).

        DESIGN §7.2: ``record_dispatch`` resolves a tracker's seed obligation from
        this map. Activation-only trackers (``economy is None``) must be absent so
        their torrents record an honest tracker-unresolved MISS — they must NOT
        leak into ``DeleteAuthority._economy``.
        """
        from personalscraper.acquire._factory import build_acquire_context
        from personalscraper.conf.models.api_config import (
            TrackerEconomyConfig,
            TrackerProviderConfig,
        )

        econ = TrackerEconomyConfig(target_ratio=2.0, min_ratio=1.0, min_seed_time=259200)
        with_econ = TrackerProviderConfig(enabled=True, economy=econ)
        without_econ = TrackerProviderConfig(enabled=True, economy=None)

        config = self._minimal_config(tmp_path)
        # Real ProviderConfig-shaped tracker providers: one with economy, one None.
        config.tracker.providers = {"lacale": with_econ, "c411": without_econ}
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
            mock_build.return_value = MagicMock()
            ctx = build_acquire_context(config, settings, event_bus=event_bus, cb_policy=cb_policy)

        # Only the economy-bearing tracker is present; the value is the exact
        # TrackerEconomyConfig instance from the provider config.
        assert ctx.delete_authority._economy == {"lacale": econ}
        assert "c411" not in ctx.delete_authority._economy
