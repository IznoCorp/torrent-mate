"""Web server configuration model (tm-shell feature).

See docs/features/tm-shell/DESIGN.md §4.3.
"""

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
        session_ttl_hours: JWT session cookie lifetime in hours.
        cookie_secure: When True, the session cookie has the Secure flag
            (requires HTTPS).
        dev_mode: When True, allows boot without a built SPA (Vite dev proxy).
    """

    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8710
    username: str = "izno"
    redis_url: str = "redis://127.0.0.1:6379/0"
    stream_key: str = "personalscraper:events"
    stream_maxlen: int = 10000
    session_ttl_hours: int = 720
    cookie_secure: bool = True
    dev_mode: bool = False
