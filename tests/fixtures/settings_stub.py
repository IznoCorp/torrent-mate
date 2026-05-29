"""Typed :class:`Settings` stub for CLI E2E tests.

Replaces the historical ``mock_settings.return_value = MagicMock()`` hack
(see feat/registry sub-phase 3.1 / phase-09 §9.1) with a real, typed
:class:`Settings` instance carrying dummy credential values. This lets
``ProviderRegistry`` boot through ``_build_app_context`` without the
autouse patch (``_patch_provider_registry_for_cli_tests``) that used to
short-circuit registry construction in CLI tests.

Why a real :class:`Settings` (not a ``MagicMock``):
    The provider builders (``TMDBClient.policy``, ``TVDBClient``) read
    credential attributes off ``settings`` and feed them into
    :class:`TransportPolicy`, which JSON-serialises its fields. A
    ``MagicMock`` is not JSON-serialisable — that is exactly the
    failure mode the old autouse fixture papered over. A real
    :class:`Settings` with non-empty dummy strings passes the
    ``missing_credentials`` boot check and the JSON serialiser alike.

Use ``make_typed_settings_stub()`` inline in tests (preferred — minimal
diff over the legacy pattern) or inject the ``typed_settings_stub``
fixture into test signatures.
"""

from __future__ import annotations

import pytest

from personalscraper.config import Settings

# Dummy credential strings — non-empty so ``validate_config`` accepts
# them in ``missing_credentials`` checks, and JSON-serialisable so
# ``TransportPolicy.model_dump_json`` does not choke on a ``MagicMock``.
_DUMMY_QBIT_PASSWORD = "dummy_qbit_password"
_DUMMY_TMDB_API_KEY = "dummy_tmdb_key"
_DUMMY_TVDB_API_KEY = "dummy_tvdb_key"
_DUMMY_TELEGRAM_BOT_TOKEN = "dummy_telegram_token"
_DUMMY_TELEGRAM_CHAT_ID = "dummy_chat_id"
_DUMMY_HEALTHCHECK_URL = "https://example.invalid/ping/dummy"


def make_typed_settings_stub() -> Settings:
    """Return a fully-populated :class:`Settings` stub for CLI tests.

    Every credential field is set to a deterministic, non-empty dummy
    string. The stub is safe to feed into ``ProviderRegistry`` because
    all values are JSON-serialisable (unlike a ``MagicMock``) and pass
    the ``missing_credentials`` boot check.

    Returns:
        A real :class:`Settings` instance — not a mock.
    """
    return Settings(
        qbit_password=_DUMMY_QBIT_PASSWORD,
        tmdb_api_key=_DUMMY_TMDB_API_KEY,
        tvdb_api_key=_DUMMY_TVDB_API_KEY,
        telegram_bot_token=_DUMMY_TELEGRAM_BOT_TOKEN,
        telegram_chat_id=_DUMMY_TELEGRAM_CHAT_ID,
        healthcheck_url=_DUMMY_HEALTHCHECK_URL,
    )


@pytest.fixture
def typed_settings_stub() -> Settings:
    """Pytest fixture wrapping :func:`make_typed_settings_stub`.

    Provided for tests that prefer dependency injection over inline
    construction. Equivalent to calling ``make_typed_settings_stub()``
    inside the test body.

    Returns:
        A real :class:`Settings` instance with dummy credentials.
    """
    return make_typed_settings_stub()
