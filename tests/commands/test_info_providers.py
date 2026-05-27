"""CLI tests for ``personalscraper info providers``."""

from __future__ import annotations

from unittest.mock import MagicMock

from tests.commands._e2e_helpers import run_cli


def test_info_providers_lists_configured_providers(monkeypatch):
    """``info providers`` exits 0 and prints circuit state for each provider."""
    from personalscraper.api.metadata.registry import ProviderName, ProviderStatus

    mock_instance = MagicMock()
    mock_instance.status.return_value = {
        "tmdb": ProviderStatus(
            name=ProviderName("tmdb"),
            circuit_state="CLOSED",
            failure_count_recent=0,
            last_success_at=None,
            last_failure_at=None,
        ),
        "tvdb": ProviderStatus(
            name=ProviderName("tvdb"),
            circuit_state="CLOSED",
            failure_count_recent=0,
            last_success_at=None,
            last_failure_at=None,
        ),
    }
    mock_instance.close = MagicMock()

    monkeypatch.setattr(
        "personalscraper.api.metadata.registry.ProviderRegistry",
        MagicMock(return_value=mock_instance),
    )

    result = run_cli(["info", "providers"])

    assert result.exit_code == 0
    assert "tmdb" in result.stdout
    assert "tvdb" in result.stdout
    assert "circuit=" in result.stdout


def test_info_providers_exits_nonzero_on_missing_creds(monkeypatch):
    """``info providers`` exits non-zero when RegistryConfigError is raised at boot."""
    from personalscraper.api.metadata.registry._errors import RegistryConfigError

    monkeypatch.setattr(
        "personalscraper.api.metadata.registry.ProviderRegistry",
        MagicMock(side_effect=RegistryConfigError([])),
    )

    result = run_cli(["info", "providers"])

    assert result.exit_code != 0
    assert "RegistryConfigError" in result.stderr


def test_info_providers_uses_config_override(monkeypatch, tmp_path):
    """``info providers --config <bad_config>`` exits non-zero with RegistryConfigError."""
    from personalscraper.api.metadata.registry._errors import RegistryConfigError

    # Create a broken providers.json5 fixture that triggers validation failure.
    bad_config = tmp_path / "bad_providers.json5"
    bad_config.write_text('{\n  "providers": {\n    "Searchable": {"nonexistent_provider_xyz": 1}\n  }\n}\n')

    monkeypatch.setattr(
        "personalscraper.api.metadata.registry.ProviderRegistry",
        MagicMock(side_effect=RegistryConfigError([])),
    )

    result = run_cli(["info", "providers", "--config", str(bad_config)])

    assert result.exit_code != 0
    assert "RegistryConfigError" in result.stderr
