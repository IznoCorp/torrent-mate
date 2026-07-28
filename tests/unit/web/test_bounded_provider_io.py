"""D1 + D5-m23 — the request-scoped provider registry is BOUNDED and CLOSED.

Two gaps this pins, both previously documented as open in the route:

* **M6 / D1 — unbounded I/O.** The enrichment built its providers with the
  pipeline's retry policy (``max_attempts=4`` + exponential backoff over a 10 s
  / 15 s timeout), synchronously, inside the request. A host that accepted the
  TCP connection and never answered burned ~60-75 s per lookup and ~2 minutes
  for a two-provider enrichment, holding the worker thread throughout. The fix
  is a construction seam — ``retry`` threaded through the registry factory — not
  a mutation of ``client._transport._policy`` (frozen, private, and on TVDB
  merely reading ``_transport`` fires the bootstrap login).
* **m23 / D5 — leaked registry.** Nothing closed it, so each provider's
  ``requests.Session`` (and its connection pool) waited on the garbage
  collector. The seam is a context manager whose ``finally`` runs on the success
  AND the exception path.

No real sleeps here: the bound is asserted on the ATTEMPT COUNT the transport is
configured for (and on the attempts a failing call actually makes), which is
what turns minutes into seconds.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from personalscraper.api.transport._policy import RetryPolicy
from personalscraper.web.acquisition.service import _REQUEST_RETRY, scoped_provider_clients


class TestPolicyOverrideSeam:
    """The override reaches both metadata clients through construction."""

    def test_tmdb_policy_takes_the_retry_override(self) -> None:
        """``TMDBClient.policy(retry=…)`` wins over the provider default."""
        from personalscraper.api.metadata.tmdb import TMDBClient

        policy = TMDBClient.policy("k", retry=RetryPolicy(max_attempts=1))

        assert policy.retry.max_attempts == 1
        assert policy.timeout_seconds == 10.0, "the existing timeout must NOT change"

    def test_tmdb_policy_default_is_untouched(self) -> None:
        """Every pipeline path (no override) keeps the retrying policy."""
        from personalscraper.api.metadata.tmdb import TMDBClient

        assert TMDBClient.policy("k").retry.max_attempts == 4

    def test_tvdb_policy_takes_the_retry_override(self) -> None:
        """``TVDBClient.policy(retry=…)`` wins, timeout preserved."""
        from personalscraper.api.metadata.tvdb import TVDBClient

        policy = TVDBClient.policy("jwt", retry=RetryPolicy(max_attempts=1))

        assert policy.retry.max_attempts == 1
        assert policy.timeout_seconds == 15.0

    def test_tvdb_client_stores_the_override_without_logging_in(self) -> None:
        """The client keeps the policy for its LAZY transport — no bootstrap fired.

        Reading ``_transport`` would trigger the ``POST /login``; the constructor
        must therefore store the retry rather than build anything.
        """
        from personalscraper.api.metadata.tvdb import TVDBClient

        client = TVDBClient("key", retry=RetryPolicy(max_attempts=1), event_bus=MagicMock())

        assert client._retry_policy.max_attempts == 1
        assert client._TVDBClient__transport is None  # type: ignore[attr-defined]

    def test_registry_forwards_the_override_to_the_built_client(self) -> None:
        """End of the seam: a registry built with ``retry`` yields bounded clients."""
        captured: dict[str, Any] = {}

        def _fake_build_providers(
            names: list[str],
            settings: object,
            cb_policy: object,
            event_bus: object,
            retry: object = None,
        ) -> dict[str, object]:
            captured["retry"] = retry
            return {}

        from personalscraper.api.metadata.registry import _factory

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(_factory, "build_providers", _fake_build_providers)
            from personalscraper.api.metadata.registry import ProviderRegistry

            providers_config = MagicMock()
            providers_config.model_dump.return_value = {}
            try:
                ProviderRegistry(
                    settings=MagicMock(),
                    event_bus=MagicMock(),
                    cb_policy=MagicMock(),
                    providers_config=providers_config,
                    retry=RetryPolicy(max_attempts=1),
                )
            except Exception:  # noqa: BLE001 — validation of a mock config may reject; the capture is what matters
                pass

        assert captured["retry"] is not None
        assert captured["retry"].max_attempts == 1


class TestRequestScopeIsBounded:
    """The web seam declares the bound the route promises."""

    def test_request_retry_is_a_single_attempt(self) -> None:
        """One attempt: the worst case is the sum of the two timeouts, not 4× each."""
        assert _REQUEST_RETRY.max_attempts == 1

    def test_slow_provider_is_called_once_not_four_times(self) -> None:
        """A dead provider costs ONE attempt per client — the bound, in attempts.

        Uses the real ``HttpTransport`` retry loop against a session that always
        raises a timeout, so the assertion is on the machinery that used to burn
        the minutes, with no real sleeping.
        """
        import requests

        from personalscraper.api._contracts import ApiError
        from personalscraper.api.transport._auth import NoAuth
        from personalscraper.api.transport._http import HttpTransport
        from personalscraper.api.transport._policy import TransportPolicy

        attempts = {"n": 0}

        def _always_timeout(*_args: object, **_kwargs: object) -> object:
            attempts["n"] += 1
            raise requests.Timeout("connected, never answered")

        policy = TransportPolicy(
            provider_name="fake",
            base_url="https://fake.example",
            auth=NoAuth(),
            timeout_seconds=1.0,
            retry=_REQUEST_RETRY,
        )
        transport = HttpTransport(policy, event_bus=MagicMock())
        transport._session.request = _always_timeout  # type: ignore[method-assign]

        with pytest.raises((ApiError, requests.RequestException)):
            transport.get("/anything")

        assert attempts["n"] == 1, f"bounded to one attempt; made {attempts['n']}"

    def test_default_policy_would_have_retried(self) -> None:
        """Control: the SAME transport with the pipeline default makes 4 attempts.

        This is what the request path used to pay, per provider, with backoff.
        """
        import requests

        from personalscraper.api._contracts import ApiError
        from personalscraper.api.transport._auth import NoAuth
        from personalscraper.api.transport._http import HttpTransport
        from personalscraper.api.transport._policy import TransportPolicy

        attempts = {"n": 0}

        def _always_timeout(*_args: object, **_kwargs: object) -> object:
            attempts["n"] += 1
            raise requests.Timeout("connected, never answered")

        policy = TransportPolicy(
            provider_name="fake",
            base_url="https://fake.example",
            auth=NoAuth(),
            timeout_seconds=1.0,
            retry=RetryPolicy(max_attempts=4, initial_wait=0.0, max_wait=0.0),
        )
        transport = HttpTransport(policy, event_bus=MagicMock())
        transport._session.request = _always_timeout  # type: ignore[method-assign]

        with pytest.raises((ApiError, requests.RequestException)):
            transport.get("/anything")

        assert attempts["n"] == 4


class TestRegistryIsClosed:
    """m23 — ``close()`` runs on EVERY path out of the scope."""

    @staticmethod
    def _request_with(app_context: MagicMock) -> MagicMock:
        """A fake FastAPI request whose app state carries config + settings."""
        request = MagicMock()
        request.app.state.config = MagicMock()
        request.app.state.settings = MagicMock()
        return request

    @staticmethod
    def _patched_context(mp: pytest.MonkeyPatch) -> MagicMock:
        """Patch ``_build_app_context`` to return a spy-able AppContext."""
        app_context = MagicMock()
        app_context.provider_registry.get.side_effect = lambda name: f"{name}-client"
        import personalscraper.cli_helpers as cli_helpers

        mp.setattr(cli_helpers, "_build_app_context", lambda *a, **kw: app_context)
        return app_context

    def test_close_is_called_on_the_success_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Normal exit releases the registry AND the acquisition handle."""
        app_context = self._patched_context(monkeypatch)

        with scoped_provider_clients(self._request_with(app_context)) as (tmdb, tvdb):
            assert (tmdb, tvdb) == ("tmdb-client", "tvdb-client")
            app_context.provider_registry.close.assert_not_called()

        app_context.provider_registry.close.assert_called_once()
        app_context.acquire.close.assert_called_once()

    def test_close_is_called_when_the_body_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The exception path must not leak the sockets — and must propagate."""
        app_context = self._patched_context(monkeypatch)

        with pytest.raises(RuntimeError, match="boom"), scoped_provider_clients(self._request_with(app_context)):
            raise RuntimeError("boom")

        app_context.provider_registry.close.assert_called_once()

    def test_a_failing_close_never_masks_the_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Teardown is fail-soft: a broken close is logged, not raised at the client."""
        app_context = self._patched_context(monkeypatch)
        app_context.provider_registry.close.side_effect = RuntimeError("socket already dead")

        with scoped_provider_clients(self._request_with(app_context)) as clients:
            assert clients == ("tmdb-client", "tvdb-client")

        app_context.provider_registry.close.assert_called_once()

    def test_builder_failure_raises_502(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unbuildable registry is still a 502 — behaviour preserved."""
        from fastapi import HTTPException

        import personalscraper.cli_helpers as cli_helpers

        def _boom(*_a: object, **_kw: object) -> object:
            raise RuntimeError("no config")

        monkeypatch.setattr(cli_helpers, "_build_app_context", _boom)

        with pytest.raises(HTTPException) as exc_info:  # noqa: PT012 — the with-block IS the call
            with scoped_provider_clients(MagicMock()):
                pass

        assert exc_info.value.status_code == 502

    def test_the_scope_passes_the_bounded_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The seam is what applies the bound — not the caller, not a mutation."""
        captured: dict[str, Any] = {}
        app_context = MagicMock()
        app_context.provider_registry.get.side_effect = lambda name: name

        def _capture(*_a: object, **kwargs: object) -> object:
            captured.update(kwargs)
            return app_context

        import personalscraper.cli_helpers as cli_helpers

        monkeypatch.setattr(cli_helpers, "_build_app_context", _capture)

        with scoped_provider_clients(MagicMock()):
            pass

        assert captured["provider_retry"] is _REQUEST_RETRY
