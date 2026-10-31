"""Web server configuration model (tm-shell feature).

See docs/features/tm-shell/DESIGN.md §4.3.
"""

from urllib.parse import urlsplit

from pydantic import Field, field_validator

from personalscraper.conf.models._base import _StrictModel


class WebConfig(_StrictModel):
    """TorrentMate web UI server configuration.

    Attributes:
        enabled: Global kill-switch. When False, the web server is disabled
            and ``personalscraper web`` exits immediately.
        host: Bind address for the uvicorn server.
        port: TCP port for the uvicorn server.
        username: Single-user login username for the web UI.
        redis_url: Redis connection URL for the event stream relay.
        stream_key: Redis Stream key for event publishing.
        stream_maxlen: Maximum number of entries retained in the Redis Stream.
        session_ttl_hours: v0's JWT session cookie lifetime in hours; goes with v0.
        session_idle_days: v1: a session ends after this many days unused; each use
            renews it. Positive: zero would end every session as it opens.
        cookie_secure: When True, the session cookie has the Secure flag
            (requires HTTPS).
        dev_mode: When True, allows boot without a built SPA (Vite dev proxy).
        v1_enabled: When True, the v1 interface is mounted under ``/api/v1``; only the
            preprod overlay sets it until the switchover (ruling O-K1-1).
        plex_forward_url: Where plex.tv sends the Plex sign-in window once the person
            confirms it — the interface's public address; ``None`` leaves the window on
            Plex. Configuration only, never derived from a request: a ``Host`` header is the
            caller's to forge.
    """

    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8710
    username: str = "izno"
    redis_url: str = "redis://127.0.0.1:6379/0"
    stream_key: str = "personalscraper:events"
    stream_maxlen: int = 10000
    session_ttl_hours: int = 720
    session_idle_days: int = Field(default=30, gt=0)
    cookie_secure: bool = True
    dev_mode: bool = False
    v1_enabled: bool = False
    plex_forward_url: str | None = None

    @field_validator("plex_forward_url")
    @classmethod
    def _absolute_web_address(cls, value: str | None) -> str | None:
        """Accept only an absolute ``http``/``https`` address.

        Args:
            value: The configured address, or ``None``.

        Returns:
            The address unchanged.

        Raises:
            ValueError: A relative address, a bare host or another scheme.
        """
        if value is None:
            return None
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("plex_forward_url must be an absolute http(s) address")
        return value
