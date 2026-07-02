"""qBittorrent client composing the atomic torrent capability protocols.

Wraps qbittorrentapi.Client with anti-ban protection (lockout file, pre-check)
and maps qBit API responses to TorrentItem dataclasses. Composes
:class:`TorrentLister`, :class:`TorrentInspector`, :class:`AuthenticatedClient`,
:class:`TorrentStateInspector`, :class:`TorrentController`, :class:`TorrentAdder`,
:class:`TorrentLimiter`, :class:`TorrentTagger`, and :class:`TorrentInjector` from
:mod:`personalscraper.api.torrent._contracts` (DESIGN §4 — phase 13, D1/D2/D8).

Provider-specific exceptions (QBitAuthLockoutError, LoginFailed, Forbidden403Error,
APIConnectionError) are preserved — they carry actionable user guidance in the
ingest step. This is the allowed escape hatch documented in _base.py.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import ClassVar

import qbittorrentapi
import requests

from personalscraper.api._contracts import ApiError, ProviderName
from personalscraper.api.torrent._base import TorrentItem, TorrentLimits, TorrentSource, _bencode_info_hash
from personalscraper.api.torrent._contracts import (
    AuthenticatedClient,
    TorrentAdder,
    TorrentController,
    TorrentInjector,
    TorrentInspector,
    TorrentLimiter,
    TorrentLister,
    TorrentStateInspector,
    TorrentTagger,
)
from personalscraper.conf.models.api_config import TorrentClientEntry
from personalscraper.logger import get_logger

log = get_logger("api.torrent.qbittorrent")

_LOCKOUT_FILE = Path.home() / ".cache" / "personalscraper" / "qbit_auth_lockout"
_LOCKOUT_DURATION_SECONDS = 3600


class QBitAuthLockoutError(Exception):
    """Raised when auth is blocked by a lockout file from a prior failure."""


class QBitClient(
    TorrentLister,
    TorrentInspector,
    AuthenticatedClient,
    TorrentStateInspector,
    TorrentController,
    TorrentAdder,
    TorrentLimiter,
    TorrentTagger,
    TorrentInjector,
):
    """qBittorrent client wrapping qbittorrentapi.Client.

    Composes the full set of atomic torrent capabilities
    (:class:`TorrentLister`, :class:`TorrentInspector`,
    :class:`AuthenticatedClient`, :class:`TorrentStateInspector`,
    :class:`TorrentController`, :class:`TorrentAdder`,
    :class:`TorrentLimiter`, :class:`TorrentTagger`,
    :class:`TorrentInjector`). Login is handled by :func:`build_client` —
    this class assumes an already-authenticated underlying client.
    """

    REQUIRED_CREDS: ClassVar[list[str]] = ["QBIT_USERNAME", "QBIT_PASSWORD"]
    provider_name = ProviderName.QBITTORRENT.value

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        """Initialize the qBittorrent API client.

        Args:
            host: qBittorrent Web UI hostname.
            port: qBittorrent Web UI port.
            username: Login username.
            password: Login password.
        """
        self._host = host
        self._port = port
        self._client = qbittorrentapi.Client(
            host=host,
            port=port,
            username=username,
            password=password,
            REQUESTS_ARGS={"timeout": 30},
            VERIFY_WEBUI_CERTIFICATE=False,
        )

    # -- Protocol: queries ---------------------------------------------------

    def get_completed(self) -> list[TorrentItem]:
        """List all completed torrents.

        Returns:
            TorrentItem list for torrents with progress == 1.0.
        """
        return [_torrent_item(t) for t in self._client.torrents_info(status_filter="completed")]

    def get_all_hashes(self) -> set[str]:
        """Return the set of all torrent info hashes in qBittorrent.

        Returns:
            Set of torrent hash strings (any state).
        """
        return {t.hash for t in self._client.torrents_info()}

    def is_seeding(self, torrent: TorrentItem) -> bool:
        """Check if a torrent is actively seeding.

        Uses state_enum.is_uploading which covers uploading, stalledUP,
        forcedUP, and queuedUP states.

        Args:
            torrent: The torrent to check.

        Returns:
            True if the torrent is seeding.
        """
        raw = self._client.torrents_info(hashes=torrent.hash)
        if not raw:
            return False
        return raw[0].state_enum.is_uploading

    def get_content_path(self, torrent: TorrentItem) -> Path:
        """Resolve the filesystem path of a torrent's content.

        Args:
            torrent: The torrent to resolve.

        Returns:
            Path to the torrent's content on disk.

        Raises:
            ApiError: Torrent hash not found in qBittorrent.
        """
        raw = self._client.torrents_info(hashes=torrent.hash)
        if not raw:
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=404,
                message=f"Torrent {torrent.hash} not found",
            )
        return Path(raw[0].content_path)

    def list_files(self, info_hash: str) -> list[tuple[str, int]]:
        """Return ``(name, size)`` for every file in a torrent.

        Wraps qBittorrent ``torrents/files`` endpoint via
        :meth:`qbittorrentapi.Client.torrents_files`.

        Args:
            info_hash: V1 info-hash of an active torrent.

        Returns:
            Ordered list of ``(relative_path, byte_size)`` for each file.

        Raises:
            ApiError: Torrent hash not found in qBittorrent (404).
        """
        try:
            files = self._client.torrents_files(torrent_hash=info_hash)
        except qbittorrentapi.NotFound404Error as exc:
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=404,
                message=f"Torrent {info_hash} not found",
            ) from exc
        return [(entry.name, entry.size) for entry in files]

    def properties(self, info_hash: str) -> dict[str, object]:
        """Return the raw ``torrents/properties`` dict for *info_hash*.

        Wraps qBittorrent ``torrents/properties`` endpoint via
        :meth:`qbittorrentapi.Client.torrents_properties`.

        Args:
            info_hash: V1 info-hash of an active torrent.

        Returns:
            The full properties dictionary. The ``piece_size`` key is
            the torrent's ``piece_length`` in bytes.

        Raises:
            ApiError: Torrent hash not found in qBittorrent (404).
        """
        try:
            props = self._client.torrents_properties(torrent_hash=info_hash)
        except qbittorrentapi.NotFound404Error as exc:
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=404,
                message=f"Torrent {info_hash} not found",
            ) from exc
        return dict(props)

    # -- Protocol: mutations -------------------------------------------------

    def pause(self, hash: str) -> None:
        """Pause a torrent by hash.

        Args:
            hash: Torrent info hash.
        """
        self._client.torrents_pause(torrent_hashes=hash)

    def resume(self, hash: str) -> None:
        """Resume a torrent by hash.

        Args:
            hash: Torrent info hash.
        """
        self._client.torrents_resume(torrent_hashes=hash)

    def delete(self, hash: str, *, delete_files: bool = False) -> None:
        """Delete a torrent by hash.

        Args:
            hash: Torrent info hash.
            delete_files: If True, also delete the downloaded files.
        """
        self._client.torrents_delete(torrent_hashes=hash, delete_files=delete_files)

    def add(
        self,
        source: TorrentSource,
        *,
        category: str | None = None,
        tags: Sequence[str] = (),
        paused: bool = False,
        limits: TorrentLimits | None = None,
    ) -> str:
        """Add a torrent to qBittorrent (D1/D6/D7/D8).

        Applies category, tags, paused state, and limits inline in one
        torrents_add call. A duplicate add raises ``Conflict409Error``, which
        is mapped to idempotent success returning the existing info_hash (D7).
        The ``torrents_add`` return value is inspected: a str ``"Ok."`` is
        success and a str ``"Fails."`` (generic failure — bad magnet, disk
        full, bad save path) raises ``ApiError`` so the failure is observable
        rather than a silent fake-success (D8). A non-str result (the
        ``TorrentsAddedMetadata`` mapping returned by qBit Web API v2.14.0+ on
        a 2xx body) is treated as success, since HTTP failures are already
        raised as typed exceptions before the result is read. 401/403 and
        corrupt-payload (415 / torrent-file) errors also surface as ApiError.

        D10: qBit uses its own default save path; no savepath arg needed.

        Args:
            source: TorrentSource — magnet or file bytes.
            category: Category label.
            tags: Tag strings.
            paused: Add in paused state if True.
            limits: Optional transfer limits applied inline (D8 — qBit
                composes TorrentLimiter, so limits are always honored).

        Returns:
            info_hash of the added (or already-present) torrent.

        Raises:
            ApiError: qBittorrent returns 401/403, a corrupt-payload error
                (415 / torrent-file), or a non-``"Ok."`` result (e.g.
                ``"Fails."``).
        """
        kwargs: dict[str, object] = {
            "category": category,
            "tags": list(tags),
            "is_paused": paused,
            **_limit_kwargs(limits),
        }
        if source.magnet is not None:
            kwargs["urls"] = source.magnet
        else:
            kwargs["torrent_files"] = source.file_bytes
        try:
            result = self._client.torrents_add(**kwargs)  # type: ignore[arg-type,type-var]
        except qbittorrentapi.Conflict409Error:
            # The torrent is already present — qBit signals a duplicate by
            # raising 409. This is the real D7 path: idempotent success.
            log.debug("qbit_add_duplicate", info_hash=source.info_hash)
            return source.info_hash
        except qbittorrentapi.Forbidden403Error as exc:
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=403,
                message=f"qBittorrent add forbidden: {exc}",
            ) from exc
        except (qbittorrentapi.LoginFailed, qbittorrentapi.Unauthorized401Error) as exc:
            # A real 401 on torrents_add is Unauthorized401Error (HTTP401Error
            # MRO), a DISTINCT class from LoginFailed — neither subclasses the
            # other, so both must be caught explicitly. LoginFailed is kept
            # defensively; Unauthorized401Error is the one the daemon actually
            # raises here. Both map to a uniform 401 ApiError (D8).
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=401,
                message=f"qBittorrent add unauthorized: {exc}",
            ) from exc
        except qbittorrentapi.UnsupportedMediaType415Error as exc:
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=415,
                message=f"qBittorrent rejected corrupt torrent payload: {exc}",
            ) from exc
        except qbittorrentapi.TorrentFileError as exc:
            # TorrentFileError is the base of the torrent-file family
            # (TorrentFileNotFoundError / TorrentFilePermissionError) — a
            # corrupt or unreadable .torrent must be observable (D8).
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=0,
                message=f"qBittorrent could not read torrent file: {exc}",
            ) from exc
        # torrents_add has two success shapes (qbittorrent-api 2025.11.x):
        #   * a plain-text body → the str "Ok." (current qBit) or "Fails." on a
        #     generic failure (bad magnet, disk full, bad save path);
        #   * a JSON body → a ``TorrentsAddedMetadata`` mapping (qBit Web API
        #     v2.14.0+). The lib only returns that object on a 2xx response —
        #     every HTTP failure (401/403/409/415/4xx/5xx) is already raised as
        #     a typed exception above and caught. So a NON-str result is always
        #     a success; only a str must be matched against the "Ok." sentinel
        #     (case/period-tolerant). A "Fails." string raises so we never
        #     report a silent fake-success (D8); a metadata object must NOT be
        #     str()-compared (it would never equal "ok" → a successful add would
        #     be misreported as failure — review #3).
        if not isinstance(result, str) or result.strip().rstrip(".").lower() == "ok":
            return source.info_hash
        raise ApiError(
            provider=ProviderName.QBITTORRENT,
            http_status=0,
            message=f"qBittorrent add failed (result={result!r})",
        )

    def inject(
        self,
        torrent_bytes: bytes,
        *,
        save_path: str,
        recheck: bool = True,
        paused: bool = True,
    ) -> str:
        """Inject a .torrent at *save_path*, add paused, optionally recheck.

        Uses :meth:`qbittorrentapi.Client.torrents_add` with *save_path*,
        ``is_skip_checking=False``, and ``is_paused`` per *paused*. The info-hash
        is computed from *torrent_bytes* via :func:`_bencode_info_hash` before the
        add — needed for idempotent return on duplicate (Conflict409) and for the
        recheck. A duplicate add (``Conflict409Error``) is idempotent success
        (same contract as :meth:`add`): still issue the recheck when *recheck* is
        True, return the computed *info_hash*. A ``"Fails."`` result from
        ``torrents_add`` maps to ``ApiError`` (same as :meth:`add`).

        Recheck (via :meth:`~qbittorrentapi.Client.torrents_recheck`) is issued
        but NOT polled for completion — state polling is the caller's
        responsibility (CrossSeedService, Phase 4).

        Args:
            torrent_bytes: Raw .torrent file content.
            save_path: Absolute path to existing data directory.
            recheck: Run recheck after adding (default True). Does NOT poll —
                the caller must verify completion.
            paused: Add in paused state (default True).

        Returns:
            The torrent's v1 info-hash.

        Raises:
            ApiError: qBittorrent returns 401/403, a corrupt-payload error
                (415 / torrent-file), or a ``"Fails."`` result.
        """
        info_hash = _bencode_info_hash(torrent_bytes)
        try:
            result = self._client.torrents_add(
                torrent_files=torrent_bytes,
                save_path=save_path,
                is_skip_checking=False,
                is_paused=paused,
            )
        except qbittorrentapi.Conflict409Error:
            # Duplicate — idempotent success (same contract as add() D7).
            log.debug("qbit_inject_duplicate", info_hash=info_hash)
            if recheck:
                self._client.torrents_recheck(torrent_hashes=info_hash)
            return info_hash
        except qbittorrentapi.Forbidden403Error as exc:
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=403,
                message=f"qBittorrent inject forbidden: {exc}",
            ) from exc
        except (qbittorrentapi.LoginFailed, qbittorrentapi.Unauthorized401Error) as exc:
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=401,
                message=f"qBittorrent inject unauthorized: {exc}",
            ) from exc
        except qbittorrentapi.UnsupportedMediaType415Error as exc:
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=415,
                message=f"qBittorrent rejected corrupt torrent payload: {exc}",
            ) from exc
        except qbittorrentapi.TorrentFileError as exc:
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=0,
                message=f"qBittorrent could not read torrent file: {exc}",
            ) from exc
        # Same result handling as add(): "Ok." / TorrentsAddedMetadata → success;
        # "Fails." → ApiError.
        if isinstance(result, str) and result.strip().rstrip(".").lower() != "ok":
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=0,
                message=f"qBittorrent inject failed (result={result!r})",
            )
        if recheck:
            self._client.torrents_recheck(torrent_hashes=info_hash)
        return info_hash

    def apply_limits(self, info_hash: str, limits: TorrentLimits) -> None:
        """Apply transfer limits to an existing torrent (D2/§5.4).

        Only non-None fields trigger API calls. For share limits, only the
        fields that are explicitly set are included in the call — no ``-2``
        global-reset sentinel is sent for an unspecified field. When all
        fields of ``TorrentLimits`` are None, no API calls are made at all
        (true no-op).

        Args:
            info_hash: Lowercase hex info_hash of the target torrent.
            limits: Limits to apply.
        """
        share_kwargs: dict[str, object] = {}
        if limits.ratio is not None:
            share_kwargs["ratio_limit"] = limits.ratio
        if limits.seed_time_minutes is not None:
            share_kwargs["seeding_time_limit"] = limits.seed_time_minutes
        if share_kwargs:
            self._client.torrents_set_share_limits(torrent_hashes=info_hash, **share_kwargs)  # type: ignore[arg-type]
        if limits.up_bytes_per_s is not None:
            self._client.torrents_set_upload_limit(torrent_hashes=info_hash, limit=limits.up_bytes_per_s)
        if limits.down_bytes_per_s is not None:
            self._client.torrents_set_download_limit(torrent_hashes=info_hash, limit=limits.down_bytes_per_s)

    def add_tags(self, info_hash: str, tags: Sequence[str]) -> None:
        """Add tags to an existing torrent in qBittorrent (idempotent).

        Wraps ``qbittorrentapi.torrents_addTags``. Tags already present on
        the torrent are silently ignored by the qBittorrent API — idempotent
        by the server's own semantics.

        Args:
            info_hash: Lowercase-hex info hash of the target torrent.
            tags: Tag strings to add.
        """
        if not tags:
            return
        try:
            self._client.torrents_addTags(torrent_hashes=info_hash, tags=",".join(tags))
        except qbittorrentapi.APIError as exc:
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=502,
                message=f"qBittorrent add_tags failed: {exc}",
            ) from exc

    def remove_tags(self, info_hash: str, tags: Sequence[str]) -> None:
        """Remove tags from an existing torrent in qBittorrent (idempotent).

        Wraps ``qbittorrentapi.torrents_removeTags``. Absent tags are silently
        ignored by the qBittorrent API — idempotent by the server's own
        semantics.

        Args:
            info_hash: Lowercase-hex info hash of the target torrent.
            tags: Tag strings to remove.
        """
        if not tags:
            return
        try:
            self._client.torrents_removeTags(torrent_hashes=info_hash, tags=",".join(tags))
        except qbittorrentapi.APIError as exc:
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=502,
                message=f"qBittorrent remove_tags failed: {exc}",
            ) from exc

    # -- Auth ----------------------------------------------------------------

    def login(self) -> None:
        """Log in to qBittorrent API.

        Checks for a lockout file before attempting auth. On login failure,
        writes a lockout file to prevent cron/launchd from accumulating
        failed attempts that trigger qBittorrent's IP ban.

        Raises:
            QBitAuthLockoutError: Recent auth failure lockout is active.
            ApiError: Provider-uniform error per DESIGN §1.1. http_status=401 for invalid
                credentials (`LoginFailed`), 403 for IP-ban (`Forbidden403Error`).
        """
        _check_lockout()
        try:
            self._client.auth_log_in()
        except qbittorrentapi.LoginFailed as exc:
            _set_lockout("login_failed")
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=401,
                message=f"qBittorrent login failed: {exc}",
            ) from exc
        except qbittorrentapi.Forbidden403Error as exc:
            log.error("qbit_ip_banned", hint="Unban IP in qBit > Preferences > Web UI, or restart qBit")
            raise ApiError(
                provider=ProviderName.QBITTORRENT,
                http_status=403,
                message=f"qBittorrent IP banned: {exc}",
            ) from exc
        log.debug("qbit_connected", host=self._host, port=self._port)

    def logout(self) -> None:
        """Log out from qBittorrent API."""
        try:
            self._client.auth_log_out()
        except (qbittorrentapi.APIConnectionError, OSError) as e:
            # Logout failure on a long-lived qBit daemon is always abnormal
            # (network drop, daemon killed). Log at warning — a debug event
            # would be silently dropped by prod log tiers.
            log.warning("qbit_logout_failed", error=str(e))


# -- Factory entry point -----------------------------------------------------


def build_client(name: str, entry: TorrentClientEntry, env: Mapping[str, str]) -> "QBitClient":
    """Construct and authenticate a QBitClient.

    Args:
        name: Provider name (must be ``"qbittorrent"``).
        entry: Client configuration from torrent.json5.
        env: Credential source.

    Returns:
        An authenticated QBitClient instance.

    Raises:
        ApiError: Provider-uniform error per DESIGN §1.1. http_status=0 for missing creds
            or unreachable host (network), 401 for bad credentials, 403 for IP-ban.
        QBitAuthLockoutError: Auth lockout active from prior failure.
    """
    username = env.get("QBIT_USERNAME", "")
    password = env.get("QBIT_PASSWORD", "")
    if not username or not password:
        raise ApiError(
            provider=ProviderName.QBITTORRENT,
            http_status=0,
            message="Missing QBIT_USERNAME or QBIT_PASSWORD",
        )

    try:
        resp = requests.get(f"http://{entry.host}:{entry.port}/", timeout=5)
        log.debug("qbit_pre_check_ok", status=resp.status_code)
    except (requests.ConnectionError, requests.Timeout) as exc:
        raise ApiError(
            provider=ProviderName.QBITTORRENT,
            http_status=0,
            message=f"qBittorrent unreachable at {entry.host}:{entry.port}: {exc}",
        ) from exc

    client = QBitClient(entry.host, entry.port, username, password)
    client.login()
    return client


# -- Internal helpers --------------------------------------------------------


def _torrent_item(t: qbittorrentapi.TorrentDictionary) -> TorrentItem:
    """Map a qBittorrent torrent dictionary to a TorrentItem."""
    content_path = t.content_path or ""
    raw_tags = getattr(t, "tags", "") or ""
    tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
    return TorrentItem(
        hash=t.hash,
        name=t.name,
        size_bytes=t.total_size,
        progress=float(t.progress),
        state=t.state,
        ratio=float(t.ratio or 0.0),
        content_path=Path(content_path) if content_path else None,
        category=t.category if t.category else None,
        tags=tags,
        added_on=datetime.fromtimestamp(t.added_on) if t.added_on else None,
    )


def _check_lockout() -> None:
    """Raise QBitAuthLockoutError if a recent auth failure lockout is active."""
    if not _LOCKOUT_FILE.exists():
        return
    try:
        age = time.time() - _LOCKOUT_FILE.stat().st_mtime
        if age < _LOCKOUT_DURATION_SECONDS:
            remaining = int(_LOCKOUT_DURATION_SECONDS - age)
            log.warning(
                "qbit_auth_lockout_active",
                remaining_seconds=remaining,
                lockout_file=str(_LOCKOUT_FILE),
            )
            raise QBitAuthLockoutError(
                f"Auth lockout active ({remaining}s remaining). Fix credentials and delete {_LOCKOUT_FILE} to retry."
            )
        _LOCKOUT_FILE.unlink(missing_ok=True)
    except OSError as e:
        log.warning("qbit_lockout_read_failed", error=str(e))


def _set_lockout(reason: str) -> None:
    """Write a lockout file to prevent further auth attempts."""
    try:
        _LOCKOUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LOCKOUT_FILE.write_text(reason)
        log.error(
            "qbit_auth_lockout_set",
            reason=reason,
            duration_seconds=_LOCKOUT_DURATION_SECONDS,
            lockout_file=str(_LOCKOUT_FILE),
            hint=f"Fix credentials in .env, then delete {_LOCKOUT_FILE} to retry",
        )
    except OSError as e:
        # Lockout file write failure is a security-control regression: the next
        # caller will retry and may trip the IP-ban path again. Log loudly with
        # the actionable hint so operators see it in alerting.
        log.error(
            "qbit_lockout_write_failed",
            error=str(e),
            hint="Cannot enforce auth lockout — credentials may keep retrying. Check filesystem permissions on "
            f"{_LOCKOUT_FILE.parent}.",
        )


def _limit_kwargs(limits: TorrentLimits | None) -> dict[str, object]:
    """Build qBittorrent limit kwargs from a TorrentLimits instance.

    Only non-None fields are included to avoid overwriting client defaults
    with zeros.

    Args:
        limits: TorrentLimits or None.

    Returns:
        Dict of torrents_add kwargs for limits; empty if limits is None.
    """
    if limits is None:
        return {}
    out: dict[str, object] = {}
    if limits.ratio is not None:
        out["ratio_limit"] = limits.ratio
    if limits.seed_time_minutes is not None:
        out["seeding_time_limit"] = limits.seed_time_minutes
    if limits.up_bytes_per_s is not None:
        out["upload_limit"] = limits.up_bytes_per_s
    if limits.down_bytes_per_s is not None:
        out["download_limit"] = limits.down_bytes_per_s
    return out
