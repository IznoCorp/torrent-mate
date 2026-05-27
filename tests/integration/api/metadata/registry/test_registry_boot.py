"""ACC-04b equivalent boot assertion (DESIGN §10 + plan §1.1).

The CLI ``personalscraper info providers --config ...`` is delivered in Phase 4.
Until then, this integration test asserts the underlying behavior: ProviderRegistry
constructor raises RegistryConfigError when credentials are missing.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.api.metadata.registry._errors import RegistryConfigError
from personalscraper.api.transport._policy import CircuitPolicy
from personalscraper.conf.models.providers import ProvidersConfig


def _providers_config_requiring_tmdb() -> ProvidersConfig:
    """A providers config that references tmdb, requiring TMDB_API_KEY."""
    return ProvidersConfig(
        Searchable={"tmdb": 1, "tvdb": 2},
        MovieDetailsProvider={"tmdb": 1},
        TvDetailsProvider={"tvdb": 1},
        EpisodeFetcher={"tvdb": 1, "tmdb": 2},
        ArtworkProvider={"tmdb": 1},
        KeywordProvider={"tmdb": 1},
    )


class _MockEventBus:
    """Minimal EventBus stub — records emitted events."""

    def __init__(self) -> None:
        self.emitted: list[object] = []

    def emit(self, event: object) -> None:
        self.emitted.append(event)


def test_boot_raises_registry_config_error_when_tmdb_key_missing(monkeypatch):
    """ACC-04b: RegistryConfigError raised at boot if TMDB_API_KEY absent.

    Uses a SimpleNamespace settings stub (matching the unit-test conftest
    pattern) because pydantic-settings would read the .env file which may
    contain TMDB_API_KEY, making the credential appear present even after
    monkeypatch.delenv.
    """
    from personalscraper.api.metadata.registry import _factory, _validation

    # Bypass real provider instantiation — this test validates credential
    # checking, not provider imports. Use empty dict so validate_config
    # sees no instantiated providers for protocol_mismatch/unknown_provider
    # checks (which would add noise to the issue list).
    monkeypatch.setattr(
        _factory,
        "build_providers",
        lambda provider_names, settings_arg, cb_policy_arg, event_bus_arg: {},
    )
    # Restore real credential validation (don't patch _CRED_MAP like unit tests do).
    # But empty providers dict means no _check_empty_chain_sections triggers
    # (no empty chain sections with the config below).

    # If the real _check_unknown_providers fires (because providers dict is empty
    # but config references tmdb/tvdb), that would add noise. Bypass it.
    monkeypatch.setattr(_validation, "_check_unknown_providers", lambda *a: [])
    # Bypass locked_capability_orphan — tmdb is in ArtworkProvider + KeywordProvider
    # so it wouldn't trigger anyway, but be explicit.
    monkeypatch.setattr(_validation, "_check_locked_capability_orphans", lambda *a: [])
    # Bypass protocol_mismatch — no providers to check.
    monkeypatch.setattr(_validation, "_check_protocol_mismatch", lambda *a: [])

    # Settings stub: tmdb_api_key is empty → missing_credentials expected.
    settings = SimpleNamespace(
        tmdb_api_key="",
        tvdb_api_key="dummy",
    )
    cb_policy = CircuitPolicy(failure_threshold=5, cooldown_seconds=300)
    bus = _MockEventBus()

    with pytest.raises(RegistryConfigError) as exc:
        ProviderRegistry(
            settings=settings,
            event_bus=bus,
            cb_policy=cb_policy,
            providers_config=_providers_config_requiring_tmdb(),
        )

    # Assert that a missing_credentials issue mentions tmdb
    tmdb_issues = [i for i in exc.value.issues if i.code == "missing_credentials" and i.provider == "tmdb"]
    assert len(tmdb_issues) >= 1, (
        f"Expected at least one missing_credentials issue for tmdb, "
        f"got issues: {[(i.code, i.provider) for i in exc.value.issues]}"
    )
