"""Design-contract tests for ``api/_activation.py`` — provider activation.

Pin point for DESIGN §8.7: ``resolve_active`` returns only the providers that
are both ``enabled`` AND have their credentials present in the environment.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest

from personalscraper.api._activation import resolve_active


@dataclass
class _FakeProvider:
    enabled: bool = True


class TestProviderActivationContract:
    """``resolve_active`` — DESIGN §8.7."""

    def test_enabled_with_creds_is_active(self) -> None:
        """Provider listed only when ``enabled=True`` AND env carries the key.

        Design: docs/archive/features/api-unify/DESIGN.md#87-api_activationpy--provider-activation
        Contract: ``resolve_active`` returns the codenames of providers that
        are both ``enabled=True`` in config AND have their required
        environment credentials set. Other providers are silently dropped.
        """
        env = {"TMDB_API_KEY": "key123"}
        providers = {"tmdb": _FakeProvider(enabled=True)}

        active = resolve_active(providers, "metadata", env=env)

        assert active == ["tmdb"]

    def test_enabled_missing_creds_emits_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Missing creds drop the provider and log a WARNING.

        Design: docs/archive/features/api-unify/DESIGN.md#87-api_activationpy--provider-activation
        Contract: ``enabled=True`` plus missing env credentials excludes the
        provider from the active list and emits a single WARNING log so the
        operator notices the misconfiguration on startup.
        """
        caplog.set_level(logging.WARNING)
        env: dict[str, str] = {}
        providers = {"tmdb": _FakeProvider(enabled=True)}

        active = resolve_active(providers, "metadata", env=env)

        assert active == []
        assert any("tmdb" in record.message.lower() for record in caplog.records)
