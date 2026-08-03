"""Structured logging module — dual output (console + JSON file) via structlog."""

import io
import logging
import logging.config
import os
import re
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, TextIO, cast

import structlog
from structlog.types import ExcInfo, Processor

# Top-level exact-match for short, well-known secret field names.
_SECRET_KEY_EXACT_RE = re.compile(r"^(api[_-]?key|authorization|cookie|secret|token|password)$", re.IGNORECASE)
# Segment-boundary match for compound names like ``youtube_api_key``,
# ``tmdb_api_key``, ``tvdb_api_key``, ``cookies_file``, ``cookie_file``.
# Uses ``(^|[_-])`` as a segment boundary because ``_`` is a word character
# and ``\b`` does not fire between letters and underscores.
#
# Intentionally does NOT include bare ``cookie|secret|token|password`` — those
# are short exact-match names handled by ``_SECRET_KEY_EXACT_RE`` above.  The
# bare alternations caused over-matching on compound counters such as
# ``cookie_count``, ``token_count``, ``secret_count`` and ``password_count``,
# which are legitimate integer fields that must NOT be redacted.
# Compound FIELD names. ``(?!count)`` keeps the hard-won exclusion of legitimate
# counters (``token_count``, ``secret_count``…) while covering the names the
# process actually holds: qbit_password, telegram_bot_token, plex_token,
# web_jwt_secret, tr4ker_passkey, access_token…
_SECRET_KEY_COMPOUND_RE = re.compile(
    r"(?i)(^|[_\-])(api[_\-]?key|authorization|cookies?[_\-]file|passkey|password|token|secret|credentials?)"
    r"($|[_\-](?!count\b))"
)

# Known secret VALUES, registered at logging-configuration time.
#
# The last line of defence, and the only one that can work: a rule matching the
# SHAPE of a secret cannot see a key echoed back by a server inside an XML error
# body, embedded in a URL PATH, or dumped by a third-party library in a format
# nobody anticipated. Matching the value itself covers all of those at once.
# Populated from Settings — never hard-coded, never logged.
_SECRET_VALUES: set[str] = set()
# Below this length a "secret" is not distinctive enough to blind-replace
# (an 8-char token is already unlikely to occur by accident in a log line).
_MIN_SECRET_VALUE_LEN = 8

# Secret-bearing QUERY PARAMETERS inside a URL-ish string.
#
# The previous form was ``([?&])key=[^&]*`` — it required the separator to sit
# IMMEDIATELY before ``key=``, so ``?apikey=<secret>`` never matched (the char
# before ``key`` is an ``i``). That is exactly how four tr4ker API keys reached
# the production log in clear text on 2026-08-02, inside the ``url`` field of an
# ``api_error_body_unparsable`` event.
#
# This form matches the parameter NAME as a whole and redacts its value:
#   * the name may carry a prefix/suffix segment (``tmdb_api_key``, ``key_2``)
#     but the secret word must sit on a segment boundary, so ``monkey=`` and
#     ``turnkey_count=`` are NOT redacted (same over-matching lesson as above);
#   * separators and ``=`` are accepted percent-encoded (``%3F``/``%26``/``%3D``)
#     because a magnet's ``tr=`` payload carries its announce URL encoded, which
#     is where a tracker passkey hides;
#   * the parameter name is KEPT — a log line saying WHICH secret was elided is
#     useful; the value is what must never land on disk.
_URL_SECRET_PARAM_RE = re.compile(
    r"(?i)([?&#;]|%3F|%26|%23)"
    r"((?:[a-z0-9]+[_\-])?"
    r"(?:api[_\-]?key|authkey|passkey|torrent[_\-]?pass|key|token|secret|password|authorization|auth|"
    r"signature|sig|session|sid)"
    r"(?:[_\-]?[a-z0-9]+)?)"
    r"(=|%3D)[^&\s\"'\\;#]*"
)
# ``scheme://user:password@host`` — the other classic in-URL credential.
_URL_USERINFO_RE = re.compile(r"(//[^/:@\s]+):([^@/\s]+)@")


def _redact_in_url(value: str) -> str:
    """Redact credentials embedded in a URL-ish string.

    Covers secret-bearing query parameters (plain or percent-encoded) and
    ``user:password@`` userinfo. Applied to EVERY string in the event dict —
    a secret does not announce itself by the name of the field carrying it (the
    production leak rode in a field simply called ``url``).

    Args:
        value: Any string from the event dict.

    Returns:
        The string with credential values replaced by ``"***REDACTED***"``.
    """
    out = _URL_SECRET_PARAM_RE.sub(r"\1\2\3***REDACTED***", value)
    out = _URL_USERINFO_RE.sub(r"\1:***REDACTED***@", out)
    # Value-based pass LAST: catches what no shape rule can — a key echoed back
    # in a server error body, sitting in a URL path segment, or dumped by a
    # third-party library in an unforeseen format.
    for secret in _SECRET_VALUES:
        if secret in out:
            out = out.replace(secret, "***REDACTED***")
    return out


class _RedactingTracebackFormatter:
    """Render a rich traceback, then scrub credentials from the text.

    structlog ConsoleRenderer formats exceptions itself, bypassing the processor
    chain so this is the only place console tracebacks can be redacted.
    show_locals=False additionally stops the frame-locals dump that leaked
    merged_params to PM2 in production.
    """

    def __init__(self) -> None:
        self._inner = structlog.dev.RichTracebackFormatter(show_locals=False)

    def __call__(self, sio: TextIO, exc_info: ExcInfo) -> None:
        buf = io.StringIO()
        self._inner(buf, exc_info)
        sio.write(_redact_in_url(buf.getvalue()))


def register_secret_values(*values: str | None) -> None:
    """Register secret values to blind-replace in every logged string.

    Call once at configuration time with the process's real credentials. Values
    shorter than :data:`_MIN_SECRET_VALUE_LEN` are ignored — replacing a short
    string everywhere would mangle unrelated log lines for no security gain.

    Args:
        *values: Candidate secret values; ``None``/empty/short ones are skipped.
    """
    for value in values:
        if value and len(value) >= _MIN_SECRET_VALUE_LEN:
            _SECRET_VALUES.add(value)


def redact_secrets(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Recursively redact secret-looking values from the event dict.

    Two independent layers, because either alone has a hole: secret-looking
    FIELD NAMES are redacted wholesale, and every string is additionally
    scrubbed for credentials embedded in a URL (see :func:`_redact_in_url`) —
    which is how an API key reached the production log inside a field named
    ``url``.

    Args:
        _logger: Unused — required by the structlog processor interface.
        _method_name: Unused — required by the structlog processor interface.
        event_dict: The structlog event dict to sanitize.

    Returns:
        A new dict with secret values replaced by ``"***REDACTED***"``.
    """

    def _is_secret_key(key: Any) -> bool:
        # A non-str key (an int season number, say) cannot be a secret NAME —
        # and must never reach the regexes: ``re.match`` raises TypeError on it,
        # which would turn a log call into a crash.
        if not isinstance(key, str):
            return False
        return bool(_SECRET_KEY_EXACT_RE.match(key) or _SECRET_KEY_COMPOUND_RE.search(key))

    def _walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: ("***REDACTED***" if _is_secret_key(k) else _walk(v)) for k, v in obj.items()}
        # Tuples and sets carry secrets too — a stdlib record's ``args`` IS a
        # tuple, and that is the shape every ``logger.warning("%s", url)`` takes.
        if isinstance(obj, tuple):
            return tuple(_walk(x) for x in obj)
        if isinstance(obj, (set, frozenset)):
            return {_walk(x) for x in obj}
        if isinstance(obj, list):
            return [_walk(x) for x in obj]
        if isinstance(obj, str):
            return _redact_in_url(obj)
        if isinstance(obj, bytes):
            return _redact_in_url(obj.decode("utf-8", "replace")).encode()
        return obj

    result: dict[str, Any] = _walk(event_dict)
    return result


LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"

# Settings fields whose VALUE is a credential. Kept as names (never values) so
# this module imports nothing at module scope and stays safe to import anywhere.
_SETTINGS_SECRET_FIELDS = (
    "qbit_password",
    "tmdb_api_key",
    "tvdb_api_key",
    "youtube_api_key",
    "telegram_bot_token",
    "plex_token",
    "web_password_hash",
    "web_jwt_secret",
)


def _register_settings_secrets() -> None:
    """Feed the process's real credentials to the value-based redactor.

    Fail-soft by construction: logging must never be the thing that breaks a
    command. If settings cannot be loaded (no ``.env``, partial environment),
    the shape-based rules still apply — only the value-based safety net is
    unavailable.
    """
    try:
        from personalscraper.config import get_settings  # noqa: PLC0415 — avoid an import cycle at module scope

        settings = get_settings()
    except Exception:  # noqa: BLE001 — logging setup must never raise
        return
    register_secret_values(*(getattr(settings, name, None) for name in _SETTINGS_SECRET_FIELDS))
    # Per-provider tracker credentials live in the environment under their own
    # names (C411_API_KEY, TR4KER_API_KEY/PASSKEY…), not on Settings.
    for env_name, env_value in os.environ.items():
        if _SECRET_KEY_EXACT_RE.match(env_name) or _SECRET_KEY_COMPOUND_RE.search(env_name):
            register_secret_values(env_value)


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure structlog + stdlib logging for dual output.

    Sets up two handlers: colored console (dev) and JSON Lines file (ops).
    foreign_pre_chain captures stdlib logs (requests, urllib3, qbittorrent-api).

    Args:
        verbose: If True, set log level to DEBUG.
        quiet: If True, set log level to WARNING. Ignored if verbose is True.
    """
    LOGS_DIR.mkdir(exist_ok=True)
    _register_settings_secrets()

    if verbose:
        log_level = "DEBUG"
    elif quiet:
        log_level = "WARNING"
    else:
        log_level = "INFO"

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
    ]

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processors": [
                        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                        structlog.processors.format_exc_info,
                        # AFTER format_exc_info, never before: that processor
                        # renders the traceback into an ``exception`` STRING, so
                        # a redaction running earlier never sees it. A live path
                        # proves it matters — ``acquire/airing.py`` logs with
                        # ``exc_info=True`` and ``api/transport/_http.py``
                        # re-raises ``requests.RequestException`` verbatim, whose
                        # message carries « Max retries exceeded with url:
                        # …&apikey=<secret> ».
                        redact_secrets,
                        structlog.processors.JSONRenderer(),
                    ],
                    # Redaction MUST be in the foreign chain too: a stdlib record
                    # (urllib3, requests, qbittorrentapi, httpx) never goes
                    # through ``structlog.configure``'s processors, so without
                    # this it reaches the file in clear text. urllib3 logs the
                    # full URL at WARNING on retry — no -v needed.
                    "foreign_pre_chain": [*shared_processors, redact_secrets],
                },
                "colored": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processors": [
                        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                        redact_secrets,
                        # ``show_locals=False``: structlog's rich traceback dumps
                        # every local of every frame by default — including
                        # ``merged_params = {'apikey': …}`` inside the transport.
                        # The console is captured by PM2, so those locals land in
                        # a file on disk. Six such leaks were found live.
                        structlog.dev.ConsoleRenderer(
                            colors=True,
                            exception_formatter=_RedactingTracebackFormatter(),
                        ),
                    ],
                    "foreign_pre_chain": [*shared_processors, redact_secrets],
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "colored",
                    "level": log_level,
                },
                "file": {
                    "class": "logging.handlers.TimedRotatingFileHandler",
                    "filename": str(LOGS_DIR / "personalscraper.json"),
                    "when": "midnight",
                    "backupCount": 30,
                    "formatter": "json",
                    "level": "DEBUG",
                },
            },
            "loggers": {
                "": {
                    "handlers": ["console", "file"],
                    "level": "DEBUG",
                    "propagate": True,
                },
                # Third-party loggers default to WARNING to reduce noise.
                # qbittorrentapi INFO surfaces session lifecycle events (login, logout, cookie refresh)
                # that aid ingest debugging without DEBUG-level request traces.
                "rebulk": {"level": "DEBUG" if verbose else "WARNING"},
                "guessit": {"level": "DEBUG" if verbose else "WARNING"},
                "urllib3": {"level": "DEBUG" if verbose else "WARNING"},
                "requests": {"level": "DEBUG" if verbose else "WARNING"},
                "qbittorrentapi": {"level": "DEBUG" if verbose else "INFO"},
                "httpcore": {"level": "DEBUG" if verbose else "WARNING"},
                "httpx": {"level": "DEBUG" if verbose else "WARNING"},
                # enzyme mislabels a benign condition (an unrecognised/vendor
                # EBML element id while parsing an MKV — parsing continues
                # normally) as logger.error(), its only call above WARNING.
                # Left unsilenced, this floods personalscraper.json with
                # level="error" lines that health-check's log scanner treats
                # as real anomalies. extract_via_enzyme() already reports its
                # own failures via our structured logger, so silencing enzyme
                # entirely loses no diagnostic signal.
                "enzyme": {"level": "CRITICAL"},
            },
        }
    )

    structlog.configure(
        processors=shared_processors
        + [
            redact_secrets,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger.

    Args:
        name: Logger name (typically module name, e.g. "ingest").

    Returns:
        A BoundLogger instance with the given name.
    """
    # structlog.get_logger() returns Any; cast to the concrete wrapper we configure above.
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


def cleanup_old_logs(logs_dir: Path = LOGS_DIR, retention_days: int = 30) -> int:
    """Delete log files older than retention_days.

    Complement to TimedRotatingFileHandler's backupCount for time-based cleanup.

    Args:
        logs_dir: Directory containing log files.
        retention_days: Delete files older than this many days.

    Returns:
        Number of files deleted.
    """
    import time

    if not logs_dir.exists():
        return 0
    cutoff = time.time() - (retention_days * 86400)
    deleted = 0
    for f in logs_dir.iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
        except OSError as exc:
            # File may be locked by active log handler, or real FS error
            structlog.get_logger("logger").debug("cannot_delete_log", file=f.name, error=str(exc))
    return deleted
