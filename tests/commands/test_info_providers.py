"""CLI tests for ``personalscraper info providers``."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from tests.commands._e2e_helpers import assert_no_python_traceback, run_cli
from tests.fixtures.settings_stub import make_typed_settings_stub

if TYPE_CHECKING:
    import pytest


def test_info_providers_lists_configured_providers(monkeypatch):
    """``info providers`` exits 0 and prints circuit state for each provider."""
    from personalscraper.api.metadata.registry import ProviderStatus, RegistryProviderName

    mock_instance = MagicMock()
    mock_instance.status.return_value = {
        "tmdb": ProviderStatus(
            provider_name=RegistryProviderName("tmdb"),
            circuit_state="CLOSED",
            failure_count_recent=0,
            last_success_at=None,
            last_failure_at=None,
        ),
        "tvdb": ProviderStatus(
            provider_name=RegistryProviderName("tvdb"),
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


def test_info_providers_exits_nonzero_on_missing_creds_real_validation(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    """``info providers`` exits non-zero through the REAL validator (ACC-04b).

    Phase 25.1 regression test — the previous version of this test mocked
    ``ProviderRegistry`` to raise ``RegistryConfigError([])`` and would
    still pass if env validation were silently removed. This version
    drives a real :class:`ProviderRegistry` boot with a typed
    :class:`Settings` stub whose ``tmdb_api_key`` is empty — the real
    ``_check_missing_credentials`` arm of ``_validation.py`` must fire and
    surface ``RegistryConfigError`` mentioning ``tmdb``.
    """
    from personalscraper.config import Settings

    # Real Settings with TMDB credential explicitly empty (but all other
    # required fields populated). The remaining fields stay non-empty so
    # only the TMDB credential check fails — pinning the assertion to a
    # single, named failure mode.
    stub = Settings(
        qbit_password="dummy_qbit_password",
        tmdb_api_key="",  # ← the regression target
        tvdb_api_key="dummy_tvdb_key",
        telegram_bot_token="dummy_telegram_token",
        telegram_chat_id="dummy_chat_id",
        healthcheck_url="https://example.invalid/ping/dummy",
    )
    # Also clear the env var so the real ``_credential_value`` lookup
    # cannot recover from os.environ (mirrors the real "user forgot
    # to set TMDB_API_KEY" scenario the validator is meant to catch).
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.setattr("personalscraper.config.get_settings", lambda: stub)

    result = run_cli(["info", "providers"])

    assert result.exit_code != 0, f"expected non-zero exit; got {result.exit_code}, stderr={result.stderr!r}"
    # ``RegistryConfigError`` is emitted verbatim by ``info_providers`` via
    # ``typer.echo(str(exc), err=True)`` — the header line includes the
    # class name so the assertion remains stable across message tweaks.
    assert "RegistryConfigError" in result.stderr
    # Pin the SPECIFIC failure mode this test exercises: the
    # ``missing_credentials`` code with the ``TMDB_API_KEY`` env-var name
    # must appear in stderr. This rules out a coincidental pass where
    # another ConfigIssue family fires (e.g. empty_chain_section if the
    # autouse fixtures inject an empty ProvidersConfig) — the test would
    # then no longer detect a regression that silently drops the env
    # credential check.
    assert "missing_credentials" in result.stderr, (
        f"expected missing_credentials issue code in stderr; got: {result.stderr!r}"
    )
    assert "TMDB_API_KEY" in result.stderr, (
        f"expected TMDB_API_KEY env-var name in stderr; got: {result.stderr!r}"
    )


def test_info_providers_uses_config_override_with_real_bad_config(tmp_path: Path) -> None:
    """``info providers --config <bad_config>`` surfaces the underlying loader error.

    Phase 25.1 — exercises the ``--config`` override path end-to-end through
    the real ``info_providers`` body (no ``ProviderRegistry`` mock). A
    malformed ``providers.json5`` triggers either a pydantic validation
    failure (from ``ProvidersConfig.model_validate``) or a json5 parse
    error — both produce a non-zero exit with a user-readable message
    (no raw Python traceback).
    """
    bad_config = tmp_path / "bad_providers.json5"
    bad_config.write_text(
        '{\n  "providers": {\n    "Searchable": {"nonexistent_provider_xyz_999": 1}\n  }\n}\n',
    )

    # No ProviderRegistry mock — the real ``info_providers`` body has to
    # cope with the real loader. We do still need a Settings stub because
    # the command always calls ``get_settings()`` before reaching the
    # config-override branch.
    with patch(
        "personalscraper.config.get_settings",
        return_value=make_typed_settings_stub(),
    ):
        result = run_cli(["info", "providers", "--config", str(bad_config)])

    assert result.exit_code != 0
    # User-friendly: no raw "Traceback (most recent call last):" line.
    assert_no_python_traceback(result)


# Phase 25.5 — failure-path for malformed --config + real load_config.
#
# This sits next to the over-mock fixes because both 25.1 and 25.5 share
# the same scaffolding (real Settings, no ProviderRegistry mock).
def test_top_level_config_override_malformed_dir_exits_with_friendly_error(
    tmp_path: Path,
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    """``personalscraper --config <bad_dir> info`` exits non-zero via load_config.

    Phase 25.5 — the previous test suite never asserted the failure-path
    of ``load_config`` when invoked through the global ``--config`` flag.
    A directory that exists but is missing ``config.json5`` must produce a
    ``ConfigNotFoundError`` that the CLI catches and renders as a friendly
    ``"Config error: …"`` line on stderr (NOT a raw Python traceback).

    Catches: regression where the CLI callback accidentally swallows or
    re-raises the loader exception without the typer-friendly mapping.

    The ``tests/commands/conftest.py`` autouse fixture short-circuits
    ``load_config`` to return ``test_config`` so most CLI tests don't need
    a real config on disk. This test EXPLICITLY undoes that patch so the
    real loader runs against a directory missing ``config.json5``.
    """
    # Undo the autouse ``patch()`` from tests/commands/conftest.py so the
    # real ``load_config`` runs against the bad directory. Without this,
    # the autouse patches resolve_config_path → fake path and load_config
    # → returns test_config unconditionally, hiding the very failure-path
    # this test exercises.
    import importlib  # noqa: PLC0415

    from personalscraper.conf import loader as _loader  # noqa: PLC0415

    fresh = importlib.reload(_loader)
    monkeypatch.setattr("personalscraper.conf.loader.resolve_config_path", fresh.resolve_config_path)
    monkeypatch.setattr("personalscraper.conf.loader.load_config", fresh.load_config)

    # Directory exists but is empty — ``config.json5`` missing.
    empty_dir = tmp_path / "empty-config-dir"
    empty_dir.mkdir()

    result = run_cli(["--config", str(empty_dir), "info"])

    assert result.exit_code != 0
    # Typer-friendly output: no raw traceback.
    assert_no_python_traceback(result)
    # The CLI maps ConfigNotFoundError → "Config error: ..." on stderr.
    assert "Config error" in result.stderr or "Config error" in result.output
