"""HTTP transport layer behind :class:`kanbanmate.adapters.github.client.GithubClient`.

Extracted from :mod:`kanbanmate.adapters.github.client` (19.1 LOC budget — client.py
had reached exactly the 1000-LOC hard ceiling, so no new method could land until the
self-contained transport concern was lifted out; mirrors the earlier
:mod:`kanbanmate.app.reaper` / :mod:`kanbanmate.app.depgate` / :mod:`kanbanmate.app.drain`
extractions). This is a behaviour-preserving move: the seam type aliases, the
transient-retry policy, and :class:`UrllibTransport` are byte-identical to their former
home.

Network-timeout safety (CLAUDE.md MANDATORY + DESIGN §3.3): :class:`UrllibTransport`
enforces **both a connect and a read timeout on every request** — including every
transient retry — so the daemon can never hang on I/O. The module exposes the GraphQL
and REST seams (``graphql`` / ``rest`` / ``rest_with_headers``) the client wires its
narrow port methods onto; tests inject a fake transport so no unit test touches the
network.

Layering: this module sits in ``adapters/github`` (same layer as the client) and imports
only the standard library plus :mod:`._parsers` (for :class:`GitHubHTTPError`). It MUST
NOT import from :mod:`.client`, so the client can import this module without a cycle.
"""

from __future__ import annotations

import http.client
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urlparse

from kanbanmate.adapters.github._parsers import GitHubHTTPError

# Transport seams. GraphQL POSTs a payload dict and returns decoded JSON; REST
# issues a method/path/body and returns decoded JSON (a dict, or a *list* for
# array-returning endpoints like ``list issue comments``, or {} for an empty 2xx
# body). The REST seam is therefore typed ``-> Any``: a GET-comments call yields a
# JSON array, while a POST/PATCH comment call yields an object.
GraphQLTransport = Callable[[dict[str, Any]], dict[str, Any]]
RestTransport = Callable[[str, str, "dict[str, Any] | None"], Any]
# The headers-bearing REST seam: same (method, path, body) call shape, but returns
# BOTH the decoded body AND the response headers (``dict(resp.getheaders())``) so the
# pager can read the ``Link`` header and follow ``rel="next"``. The body-only
# ``RestTransport`` stays the default for callers that do not paginate.
RestHeadersTransport = Callable[[str, str, "dict[str, Any] | None"], tuple[Any, dict[str, str]]]

_GRAPHQL_HOST = "api.github.com"
_GRAPHQL_PATH = "/graphql"
_REST_BASE = "https://api.github.com"
_USER_AGENT = "kanbanmate/0.1"

# Sane defaults (DESIGN §3.3): a generous-but-bounded connect, a longer read.
_DEFAULT_CONNECT_TIMEOUT = 5.0
_DEFAULT_READ_TIMEOUT = 30.0

# Transient-error retry (PoC ``client.py::_urlopen_json`` parity, #15, widened #2). The hot poll
# loop must survive a transient GitHub blip rather than failing the whole tick on the first
# attempt. Transient now covers the full retriable set: ``429`` (rate limit), ``500``/``502``/
# ``503``/``504`` (gateway/server), and a ``403`` whose body names the "secondary rate limit".
# Retry is BOUNDED: at most ``_MAX_ATTEMPTS`` tries with a ``0.5 * (attempt + 1)`` backoff, and a
# ``Retry-After`` header is honored but CLAMPED to a small per-request budget
# (``_RETRY_AFTER_BUDGET``, well under the per-action watchdog/``action_timeout``) so a long
# server-advised wait can never overrun the watchdog — the LOOP-level circuit breaker (#2) owns
# long waits, not the transport. The connect+read timeouts apply on EVERY attempt (each retry
# opens a fresh timed connection — CLAUDE.md Network Timeout Safety). Non-transient 4xx are NEVER
# retried (they raise immediately with the decoded body).
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_BASE = 0.5

# The transient status set worth a bounded retry (#2). ``403`` is special-cased (only the
# secondary-rate-limit variant is transient — a plain 403 is a permanent permission error).
_TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})

# The hard ceiling (seconds) on honoring a ``Retry-After`` header inside the transport (#2). Kept
# well under the default ``action_timeout`` (120 s) so a server-advised wait can never overrun the
# per-action watchdog and produce a spurious abort + abandoned worker thread. Longer waits are the
# LOOP-level circuit breaker's job, not the transport's.
_RETRY_AFTER_BUDGET = 15.0


def _is_transient(status: int, body: str) -> bool:
    """Return ``True`` for a retriable transient GitHub failure (#15, widened #2).

    A transient failure is one a brief backoff is likely to clear: a ``429`` rate limit, a
    ``500``/``502``/``503``/``504`` gateway/server error, or a ``403`` whose body names GitHub's
    "secondary rate limit". Any other status (incl. ``401``/``404``/a plain ``403``) is permanent —
    the caller must NOT retry it.

    Args:
        status: The HTTP response status code.
        body: The decoded response body (case-insensitively scanned for the
            secondary-rate-limit marker on a ``403``).

    Returns:
        ``True`` iff the failure is transient and worth a bounded retry.
    """
    if status in _TRANSIENT_STATUSES:
        return True
    return status == 403 and "secondary rate limit" in body.lower()


def _retry_delay(attempt: int, resp_headers: dict[str, str]) -> float:
    """Compute the bounded backoff before the next retry, honoring ``Retry-After`` (#2).

    GitHub may advise a ``Retry-After`` header (an integer number of seconds) on a 429/503. When
    present and parseable it is preferred over the geometric default — but CLAMPED to
    :data:`_RETRY_AFTER_BUDGET` so a long server-advised wait can never overrun the per-action
    watchdog (the loop-level circuit breaker owns long waits, #2). Without a usable header the
    delay falls back to ``_RETRY_BACKOFF_BASE * (attempt + 1)`` (the #15 curve).

    Args:
        attempt: The zero-based attempt index that just failed.
        resp_headers: The response headers (case-insensitive ``Retry-After`` lookup).

    Returns:
        The number of seconds to sleep before the next attempt, in ``[0, _RETRY_AFTER_BUDGET]``
        when a header is honored, else the geometric default.
    """
    # Headers are case-insensitive; scan for Retry-After without assuming canonical casing.
    raw = next((v for k, v in resp_headers.items() if k.lower() == "retry-after"), None)
    if raw is not None:
        try:
            advised = float(raw.strip())
        except (TypeError, ValueError):
            advised = None
        if advised is not None:
            # Clamp to the per-request budget; a negative/zero advice means "no wait".
            return max(0.0, min(advised, _RETRY_AFTER_BUDGET))
    return _RETRY_BACKOFF_BASE * (attempt + 1)


@dataclass(frozen=True)
class Timeouts:
    """Connect and read timeouts (seconds) applied to every network request.

    Both are mandatory and non-``None`` so the daemon never blocks indefinitely on
    a stalled connect or a stalled read (CLAUDE.md Network Timeout Safety).

    Attributes:
        connect: Seconds to wait for the TCP/TLS connection to be established.
        read: Seconds to wait for each subsequent socket read.
    """

    connect: float = _DEFAULT_CONNECT_TIMEOUT
    read: float = _DEFAULT_READ_TIMEOUT


class UrllibTransport:
    """Default HTTPS transport that enforces a connect *and* a read timeout.

    The standard library applies a single socket timeout to both the connect and
    subsequent reads. To honour the rule *literally* — distinct connect and read
    budgets on every request — we open an :class:`http.client.HTTPSConnection` with
    the connect timeout, then lower the live socket to the read timeout before
    reading the response body.
    """

    def __init__(self, token: str, *, timeouts: Timeouts | None = None):
        """Build the transport.

        Args:
            token: A GitHub PAT scoped ``project`` + ``repo`` (DESIGN §10).
            timeouts: Connect/read timeouts; defaults to :class:`Timeouts` (both
                non-``None``, per the timeout-safety rule).
        """
        self._token = token
        self._timeouts = timeouts or Timeouts()

    @property
    def timeouts(self) -> Timeouts:
        """The connect/read timeouts this transport applies to every request."""
        return self._timeouts

    def _request_with_headers(
        self,
        method: str,
        host: str,
        path: str,
        body: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> tuple[Any, dict[str, str]]:
        """Issue one HTTPS request, applying connect then read timeouts.

        This is the SINGLE network-read implementation: every body-only request
        (:meth:`_request`) is a thin wrapper that calls this and discards the
        headers, so there is exactly one place that performs the connect+read
        timeout dance — no second, untimed read path can exist (CLAUDE.md Network
        Timeout Safety). The headers it returns let the Link ``rel="next"`` pager
        follow pagination without opening an untimed socket.

        Args:
            method: HTTP method (``GET``/``POST``/``PATCH``).
            host: API host (``api.github.com``).
            path: Request path (with query string if any).
            body: JSON-serialisable body, or ``None`` for a bodyless request.
            headers: Request headers (auth + content negotiation).

        Returns:
            A ``(decoded_body, response_headers)`` pair. The body is a dict for
            object endpoints, a list for array endpoints (e.g. ``list issue
            comments``), or ``{}`` for an empty 2xx body. ``response_headers`` is
            ``dict(resp.getheaders())`` (the ``Link`` header lives here when the
            endpoint paginates).

        Raises:
            GitHubHTTPError: On a non-transient HTTP status >= 400 (immediately), or
                on a transient 502 / secondary-rate-limit failure that survives all
                :data:`_MAX_ATTEMPTS` retries — always carrying the decoded body.
        """
        data = json.dumps(body).encode() if body is not None else None
        # Bounded transient-retry loop (#15, PoC ``_urlopen_json`` parity). EVERY attempt opens a
        # fresh connection with the connect timeout AND lowers the live socket to the read timeout
        # before reading, so the mandatory connect+read discipline holds on each retry (no untimed
        # read path). A transient 502 / secondary-rate-limit failure sleeps ``0.5*(attempt+1)`` and
        # retries; any other status>=400, or the final attempt, raises with the decoded body.
        for attempt in range(_MAX_ATTEMPTS):
            status, raw, resp_headers = self._send_once(method, host, path, data, headers)
            if status < 400:
                decoded = json.loads(raw) if raw else {}
                return decoded, resp_headers
            if attempt < _MAX_ATTEMPTS - 1 and _is_transient(status, raw):
                # Transient blip: bounded backoff (honoring a clamped Retry-After, #2), then retry
                # on a fresh timed connection.
                time.sleep(_retry_delay(attempt, resp_headers))
                continue
            # Permanent failure, or transient but retries exhausted: surface the decoded body.
            raise GitHubHTTPError(status, raw)
        # Unreachable: the loop either returns a 2xx body or raises on the final attempt. Present
        # only so a static checker sees every path terminates.
        raise AssertionError("unreachable: retry loop did not return or raise")

    def _send_once(
        self,
        method: str,
        host: str,
        path: str,
        data: bytes | None,
        headers: dict[str, str],
    ) -> tuple[int, str, dict[str, str]]:
        """Perform ONE timed HTTPS round-trip, returning ``(status, body, headers)``.

        The single timed-read primitive behind :meth:`_request_with_headers`'s retry
        loop: it opens a connection with the connect timeout, lowers the live socket
        to the read timeout before reading, and always closes the connection. It does
        NOT raise on a 4xx/5xx — it returns the status and decoded body so the caller's
        retry loop can decide whether the failure is transient (CLAUDE.md Network
        Timeout Safety: both budgets apply on this every-attempt path).

        Args:
            method: HTTP method (``GET``/``POST``/``PATCH``).
            host: API host (``api.github.com``).
            path: Request path (with query string if any).
            data: The already-serialised request body bytes, or ``None``.
            headers: Request headers (auth + content negotiation).

        Returns:
            A ``(status, decoded_text, response_headers)`` triple; ``decoded_text``
            is the raw decoded body (the caller JSON-decodes only a 2xx body).
        """
        # Connect budget: the connection refuses to block past `connect` seconds.
        conn = http.client.HTTPSConnection(host, timeout=self._timeouts.connect)
        try:
            conn.request(method, path, body=data, headers=headers)
            # Read budget: now that we are connected, bound every subsequent read so
            # a half-open/slow response can never hang the daemon.
            if conn.sock is not None:
                conn.sock.settimeout(self._timeouts.read)
            resp = conn.getresponse()
            raw = resp.read().decode(errors="replace")
            return resp.status, raw, dict(resp.getheaders())
        finally:
            conn.close()

    def _request(
        self,
        method: str,
        host: str,
        path: str,
        body: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> Any:
        """Issue one HTTPS request and return the decoded body only.

        A thin wrapper over :meth:`_request_with_headers` that drops the response
        headers, kept so every existing body-only caller (``graphql`` / ``rest``)
        is unchanged. ALL the timeout discipline lives in
        :meth:`_request_with_headers`; this method introduces no second read path.

        Args:
            method: HTTP method (``GET``/``POST``/``PATCH``).
            host: API host (``api.github.com``).
            path: Request path (with query string if any).
            body: JSON-serialisable body, or ``None`` for a bodyless request.
            headers: Request headers (auth + content negotiation).

        Returns:
            The decoded JSON response body — a dict for object endpoints, a list
            for array endpoints (e.g. ``list issue comments``), or ``{}`` for an
            empty 2xx body.

        Raises:
            GitHubHTTPError: On any HTTP status >= 400, carrying the decoded body.
        """
        body_only, _headers = self._request_with_headers(method, host, path, body, headers)
        return body_only

    def graphql(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a GraphQL payload to ``/graphql`` and return the decoded JSON.

        Args:
            payload: A ``{"query": ..., "variables": ...}`` body.

        Returns:
            The decoded GraphQL response.
        """
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }
        # A GraphQL response is always a JSON object; the shared `_request` is typed
        # `-> Any` (REST may return a list), so narrow it back to a dict here.
        return cast(
            "dict[str, Any]", self._request("POST", _GRAPHQL_HOST, _GRAPHQL_PATH, payload, headers)
        )

    def _rest_target(self, path: str) -> tuple[str, str, dict[str, str]]:
        """Resolve a REST path into ``(host, rel_path, headers)`` for a request.

        Shared by :meth:`rest` and :meth:`rest_with_headers` so the host/path/header
        assembly is identical on both seams (the only difference is whether the
        caller keeps the response headers).

        Args:
            path: Path relative to the REST base, or a full URL.

        Returns:
            A ``(host, rel_path, headers)`` tuple ready for the request helpers.
        """
        parsed = urlparse(path if path.startswith("http") else _REST_BASE + path)
        host = parsed.netloc or _GRAPHQL_HOST
        rel = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }
        return host, rel, headers

    def rest(self, method: str, path: str, body: dict[str, Any] | None) -> Any:
        """Issue a REST request against ``api.github.com`` and return decoded JSON.

        Args:
            method: HTTP method.
            path: Path relative to the REST base, or a full URL.
            body: JSON body, or ``None``.

        Returns:
            The decoded JSON response — a dict, a list (array endpoints), or ``{}``
            for an empty 2xx body.
        """
        host, rel, headers = self._rest_target(path)
        return self._request(method, host, rel, body, headers)

    def rest_with_headers(
        self, method: str, path: str, body: dict[str, Any] | None
    ) -> tuple[Any, dict[str, str]]:
        """Issue a REST request and return BOTH the decoded body and the headers.

        Same host/path/headers assembly as :meth:`rest`, but returns the response
        headers alongside the body so the Link ``rel="next"`` pager can follow
        pagination. Routes through :meth:`_request_with_headers`, so it inherits the
        SAME mandatory connect+read timeouts as every other request — no untimed
        read path is introduced.

        Args:
            method: HTTP method.
            path: Path relative to the REST base, or a full URL.
            body: JSON body, or ``None``.

        Returns:
            A ``(decoded_body, response_headers)`` pair (headers carry ``Link`` when
            the endpoint paginates).
        """
        host, rel, headers = self._rest_target(path)
        return self._request_with_headers(method, host, rel, body, headers)
