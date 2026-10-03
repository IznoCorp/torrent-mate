"""Unit tests for ``personalscraper.app.services`` and its builder in ``app.composition``."""

from __future__ import annotations

from personalscraper.app.composition import build_app_services
from personalscraper.app.library.service import LibraryService
from personalscraper.app.services import AppServices
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus


def test_build_app_services_is_inert(test_config: Config) -> None:
    """The builder opens nothing: a fresh bus, and ``close`` is safe to call."""
    services = build_app_services(test_config, Settings(_env_file=None))  # type: ignore[call-arg]

    assert isinstance(services, AppServices)
    assert isinstance(services.event_bus, EventBus)
    services.close()


def test_each_build_has_its_own_bus(test_config: Config) -> None:
    """Two builds share no bus (one per process, never a module global)."""
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert (
        build_app_services(test_config, settings).event_bus is not build_app_services(test_config, settings).event_bus
    )


def test_the_library_service_is_built_inert(test_config: Config) -> None:
    """The library service is built over the configured stores without opening them; no key, no client."""
    services = build_app_services(test_config, Settings(_env_file=None))  # type: ignore[call-arg]

    assert isinstance(services.library, LibraryService)
    assert test_config.acquire.db_path is not None
    assert not test_config.acquire.db_path.exists()
    services.close()
