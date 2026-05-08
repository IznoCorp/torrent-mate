"""AuthMethod implementations.

Implements DESIGN S3.4: BearerAuth, ApiKeyAuth (header OR query),
LoginAuth (Basic Auth), and NoAuth. Each class satisfies the
AuthMethod Protocol from _policy.py.
"""

from typing import Literal

import requests

from personalscraper.logger import get_logger

ApiKeyLocation = Literal["header", "query"]

log = get_logger("api.auth")


class BearerAuth:
    """Bearer token authentication.

    Applies an Authorization: Bearer <token> header at transport init.
    """

    def __init__(self, token: str) -> None:
        self._token = token

    def apply(self, session: requests.Session) -> None:
        session.headers["Authorization"] = f"Bearer {self._token}"

    def auth_params(self) -> dict[str, str]:
        return {}


class ApiKeyAuth:
    """API key authentication, header or query parameter.

    Single class, two locations. Header mode mutates the session
    at init. Query mode returns the key as a per-request param.
    """

    def __init__(self, key: str, *, param: str = "api_key", location: ApiKeyLocation = "header") -> None:
        # ``location`` is statically constrained to Literal["header","query"], but
        # JSON-driven config or callers using ``# type: ignore`` can still pass
        # arbitrary strings. Both ``apply()`` and ``auth_params()`` would then
        # fall through their explicit branches and emit no header / no param —
        # every request would 401 with no breadcrumb. Fail-fast at construction
        # so the misconfiguration surfaces immediately, with a warning logged
        # before raising so operators see the actionable hint in alerting.
        if location not in ("header", "query"):
            log.warning(
                "api_key_auth_invalid_location",
                param=param,
                location=location,
                hint="location must be 'header' or 'query'.",
            )
            raise ValueError(f"ApiKeyAuth.location must be 'header' or 'query', got {location!r}")
        self._key = key
        self._param = param
        self._location: ApiKeyLocation = location

    def apply(self, session: requests.Session) -> None:
        if self._location == "header":
            session.headers[self._param] = self._key

    def auth_params(self) -> dict[str, str]:
        if self._location == "query":
            return {self._param: self._key}
        return {}


class LoginAuth:
    """Username/password authentication via HTTP Basic Auth.

    Used by qBittorrent admin endpoint and similar services.
    """

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    def apply(self, session: requests.Session) -> None:
        session.auth = (self._username, self._password)

    def auth_params(self) -> dict[str, str]:
        return {}


class NoAuth:
    """No authentication — no-op for both apply() and auth_params()."""

    def apply(self, session: requests.Session) -> None:
        pass

    def auth_params(self) -> dict[str, str]:
        return {}
