"""Transmission client composing the atomic torrent capability protocols.

Wraps transmission-rpc with an HttpTransport pre-check: we issue a cheap
GET via the unified transport before instantiating transmission-rpc so
network/auth failures surface as a uniform ApiError instead of leaking the
library's exception types up the call stack. Composes
:class:`TorrentLister`, :class:`TorrentInspector`,
:class:`TorrentStateInspector`, :class:`TorrentController`,
:class:`TorrentAdder` and :class:`TorrentTagger` from
:mod:`personalscraper.api.torrent._contracts`. Deliberately omits
:class:`AuthenticatedClient` — the transmission-rpc library performs HTTP
Basic Auth per request without an explicit login step (DESIGN §4 — phase 13).
Also deliberately omits :class:`TorrentLimiter` — Transmission has no ratio/
bandwidth/seedtime limits API (D2/D8).

Transmission itself uses JSON-RPC 2.0 over a single POST endpoint with
HTTP Basic Auth and the CSRF session-id dance handled by the library.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import ClassVar

import transmission_rpc

from personalscraper.api._contracts import ApiError, ProviderName
from personalscraper.api.torrent._base import TorrentItem, TorrentLimits, TorrentSource
from personalscraper.api.torrent._contracts import (
    TorrentAdder,
    TorrentController,
    TorrentInspector,
    TorrentLister,
    TorrentStateInspector,
    TorrentTagger,
)
from personalscraper.api.torrent._errors import UnsupportedCapabilityError
from personalscraper.api.transport._auth import LoginAuth
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import TransportPolicy
from personalscraper.conf.models.api_config import TorrentClientEntry
from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger

log = get_logger("api.torrent.transmission")

# Status values that mean "download complete"
_COMPLETED_STATES = frozenset({transmission_rpc.Status.SEEDING, transmission_rpc.Status.SEED_PENDING})


class TransmissionClient(
    TorrentLister,
    TorrentInspector,
    TorrentStateInspector,
    TorrentController,
    TorrentAdder,
    TorrentTagger,
):
    """Transmission client wrapping transmission-rpc.

    Composes :class:`TorrentLister`, :class:`TorrentInspector`,
    :class:`TorrentStateInspector`, :class:`TorrentController`,
    :class:`TorrentAdder` and :class:`TorrentTagger`.
    Deliberately omits :class:`AuthenticatedClient` because
    transmission-rpc has no explicit login step (HTTP Basic Auth runs
    per-request). Also omits :class:`TorrentLimiter` — Transmission
    does not support ratio/bandwidth/seedtime limits (D2/D8).
    A pre-check via HttpTransport verifies reachability
    and credentials before the library client is instantiated.
    """

    REQUIRED_CREDS: ClassVar[list[str]] = ["TRANSMISSION_USERNAME", "TRANSMISSION_PASSWORD"]
    provider_name = "transmission"

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        """Initialize the Transmission RPC client.

        Args:
            host: Transmission RPC hostname.
            port: Transmission RPC port.
            username: HTTP Basic Auth username.
            password: HTTP Basic Auth password.
        """
        self._host = host
        self._port = port
        self._client = transmission_rpc.Client(
            host=host,
            port=port,
            username=username,
            password=password,
        )

    # -- Protocol: queries ---------------------------------------------------

    def get_completed(self) -> list[TorrentItem]:
        """List all completed torrents (status seeding or seed_pending).

        Returns:
            TorrentItem list for completed torrents.
        """
        torrents = self._client.get_torrents(
            arguments=[
                "id",
                "hashString",
                "name",
                "totalSize",
                "percentDone",
                "status",
                "downloadDir",
                "addedDate",
                "rateUpload",
                "uploadRatio",
                "labels",
                "error",
                "errorString",
            ]
        )
        return [_torrent_item(t) for t in torrents if t.status in _COMPLETED_STATES]

    def get_all_hashes(self) -> set[str]:
        """Return the set of all torrent hash strings in Transmission.

        Returns:
            Set of torrent hash strings (any status).
        """
        torrents = self._client.get_torrents(arguments=["hashString"])
        return {t.hash_string for t in torrents}

    def get_by_hashes(self, hashes: set[str]) -> list[TorrentItem]:
        """Return the :class:`TorrentItem` records for a specific hash set.

        Includes in-progress torrents (any status), unlike :meth:`get_completed`.

        Args:
            hashes: Info hashes to fetch. Empty set → ``[]`` (a bare
                ``get_torrents`` would return *all* torrents).

        Returns:
            The matching torrents as :class:`TorrentItem` records.
        """
        if not hashes:
            return []
        torrents = self._client.get_torrents(
            ids=list(hashes),
            arguments=[
                "id",
                "hashString",
                "name",
                "totalSize",
                "percentDone",
                "status",
                "downloadDir",
                "addedDate",
                "rateUpload",
                "uploadRatio",
                "labels",
                "error",
                "errorString",
            ],
        )
        return [_torrent_item(t) for t in torrents]

    def is_seeding(self, torrent: TorrentItem) -> bool:
        """Check if a torrent is seeding.

        Args:
            torrent: The torrent to check.

        Returns:
            True if the torrent is actively seeding.
        """
        try:
            t = self._client.get_torrent(torrent.hash, arguments=["status"])
            return t.status == transmission_rpc.Status.SEEDING
        except transmission_rpc.TransmissionError as exc:
            log.warning(
                "transmission_is_seeding_failed",
                hash=torrent.hash,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return False

    def get_content_path(self, torrent: TorrentItem) -> Path:
        """Resolve the filesystem path of a torrent's content.

        Single-file torrents return download_dir/filename.
        Multi-file torrents return download_dir/torrent_name.

        Args:
            torrent: The torrent to resolve.

        Returns:
            Path to the torrent's content on disk.

        Raises:
            ApiError: Torrent hash not found.
        """
        try:
            t = self._client.get_torrent(torrent.hash, arguments=["downloadDir", "name", "files"])
        except transmission_rpc.TransmissionError as exc:
            raise ApiError(
                provider=ProviderName.TRANSMISSION,
                http_status=404,
                message=f"Torrent {torrent.hash} not found: {exc}",
            ) from exc
        files = t.get_files()
        if len(files) == 1:
            return Path(t.download_dir) / files[0].name
        return Path(t.download_dir) / t.name

    # -- Protocol: mutations -------------------------------------------------

    def add(
        self,
        source: TorrentSource,
        *,
        category: str | None = None,
        tags: Sequence[str] = (),
        paused: bool = False,
        limits: TorrentLimits | None = None,
    ) -> str:
        """Add a torrent to Transmission (D1/D5/D7/D8).

        Labels encode category + tags per D5: ``labels = [category, *tags]`` so
        the read side (``_torrent_item``) recovers ``category = labels[0]`` and
        ``tags = labels[1:]``. This flat-labels scheme can only round-trip when
        a category is present: ``category=None`` with a non-empty ``tags`` is
        unrepresentable (the read side would promote the first tag to category),
        so it is rejected with ``ValueError`` rather than silently mangling the
        labels (no-silent-failure norm; review #6). ``category=None`` with no
        tags is fine (empty labels).

        Duplicate adds are idempotent (torrent-duplicate → return info_hash, no
        exception). Passing limits raises UnsupportedCapabilityError (D8 — no
        silent ignore).

        Args:
            source: TorrentSource — magnet or file bytes.
            category: Category (becomes labels[0]).
            tags: Tags (appended after category in labels). Requires a non-None
                ``category`` when non-empty (D5 round-trip constraint).
            paused: Add in paused state if True.
            limits: Must be None; raises if set (D8).

        Returns:
            info_hash of the added (or already-present) torrent.

        Raises:
            UnsupportedCapabilityError: limits is not None.
            ValueError: ``category`` is None while ``tags`` is non-empty
                (unrepresentable in Transmission's flat-labels round-trip, D5).
        """
        if limits is not None:
            raise UnsupportedCapabilityError(
                "TransmissionClient does not support transfer limits. "
                "Gate via isinstance(client, TorrentLimiter) before passing limits."
            )
        if category is None and tags:
            # D5 flat-labels (labels=[category, *tags]) cannot round-trip tags
            # without a category: _torrent_item would read the first tag back as
            # the category. Reject rather than silently lose/relabel (review #6).
            raise ValueError(
                "TransmissionClient.add requires a non-None category when tags are "
                "provided: labels=[category, *tags] cannot round-trip tags without "
                "a leading category (the first tag would be read back as the category)."
            )
        torrent_arg: str | bytes
        if source.magnet is not None:
            torrent_arg = source.magnet
        else:
            assert source.file_bytes is not None  # guaranteed by TorrentSource.__post_init__
            torrent_arg = source.file_bytes
        try:
            result = self._client.add_torrent(
                torrent=torrent_arg,
                labels=_labels(category, list(tags)),
                paused=paused,
            )
            log.debug(
                "transmission_add_ok",
                echoed_hash=result.hash_string,
                source_hash=source.info_hash,
            )
            if result.hash_string.lower() != source.info_hash.lower():
                log.warning(
                    "transmission_add_hash_mismatch",
                    echoed_hash=result.hash_string,
                    source_hash=source.info_hash,
                    hint=(
                        "Transmission echoed a hash_string that differs"
                        " from the source-derived info_hash."
                        " Returning source.info_hash as canonical (D6)."
                    ),
                )
            return source.info_hash
        except transmission_rpc.TransmissionError as exc:
            # D7 idempotence — match both the lib's result-key form
            # ("torrent-duplicate") and the human-readable daemon-error form
            # ("duplicate torrent"). A message like "duplicate label rejected"
            # matches neither token and correctly re-raises.
            msg = str(exc).lower()
            if "torrent-duplicate" in msg or "duplicate torrent" in msg:
                log.debug("transmission_add_duplicate", info_hash=source.info_hash)
                return source.info_hash
            raise

    def pause(self, hash: str) -> None:
        """Stop a torrent by hash.

        Args:
            hash: Torrent info hash.
        """
        self._client.stop_torrent(ids=hash)

    def resume(self, hash: str) -> None:
        """Start a torrent by hash.

        Args:
            hash: Torrent info hash.
        """
        self._client.start_torrent(ids=hash)

    def delete(self, hash: str, *, delete_files: bool = False) -> None:
        """Remove a torrent by hash.

        Args:
            hash: Torrent info hash.
            delete_files: If True, also delete the downloaded data.
        """
        self._client.remove_torrent(ids=hash, delete_data=delete_files)

    def add_tags(self, info_hash: str, tags: Sequence[str]) -> None:
        """Add tags to an existing Transmission torrent (idempotent, read-first).

        Transmission stores category + tags in one flat ``labels`` list:
        ``labels = [category, *tags]``. We read the current labels via
        :func:`_split_labels` (which treats an empty-string ``labels[0]`` as the
        no-category sentinel), compute the new tag set (union, preserving order),
        then write back via :func:`_labels`. On a category-less torrent the tag
        lands behind the sentinel (``["", *tags]``) so it stays readable as a
        tag (F-A). Adding an already-present tag is a no-op.

        Args:
            info_hash: Lowercase-hex info hash of the target torrent.
            tags: Tag strings to add.
        """
        if not tags:
            return
        try:
            t = self._client.get_torrent(info_hash, arguments=["labels"])
            current_labels: list[str] = list(getattr(t, "labels", None) or [])
            category, existing_tags = _split_labels(current_labels)
            new_tags = existing_tags[:]
            for tag in tags:
                if tag not in new_tags:
                    new_tags.append(tag)
            self._client.change_torrent(ids=info_hash, labels=_labels(category, new_tags))
        except transmission_rpc.TransmissionError as exc:
            raise ApiError(
                provider=ProviderName.TRANSMISSION,
                http_status=502,
                message=f"Transmission add_tags failed: {exc}",
            ) from exc

    def remove_tags(self, info_hash: str, tags: Sequence[str]) -> None:
        """Remove tags from an existing Transmission torrent (idempotent, read-first).

        Reads current labels via :func:`_split_labels` (empty-string ``labels[0]``
        is the no-category sentinel), removes the requested tags from the tag
        portion, then writes back via :func:`_labels`. Removing the last tag from
        a category-less torrent collapses the labels back to ``[]``. Removing an
        absent tag is a no-op.

        Args:
            info_hash: Lowercase-hex info hash of the target torrent.
            tags: Tag strings to remove.
        """
        if not tags:
            return
        try:
            t = self._client.get_torrent(info_hash, arguments=["labels"])
            current_labels: list[str] = list(getattr(t, "labels", None) or [])
            category, existing_tags = _split_labels(current_labels)
            tags_to_remove = set(tags)
            new_tags = [tag for tag in existing_tags if tag not in tags_to_remove]
            self._client.change_torrent(ids=info_hash, labels=_labels(category, new_tags))
        except transmission_rpc.TransmissionError as exc:
            raise ApiError(
                provider=ProviderName.TRANSMISSION,
                http_status=502,
                message=f"Transmission remove_tags failed: {exc}",
            ) from exc


# -- Factory entry point -----------------------------------------------------


def build_client(name: str, entry: TorrentClientEntry, env: Mapping[str, str]) -> "TransmissionClient":
    """Construct a TransmissionClient with pre-check.

    Args:
        name: Provider name (must be ``"transmission"``).
        entry: Client configuration from torrent.json5.
        env: Credential source.

    Returns:
        A TransmissionClient instance.

    Raises:
        ApiError: Missing required credentials or bad auth.
        ConnectionError: Transmission unreachable.
    """
    username = env.get("TRANSMISSION_USERNAME", "")
    password = env.get("TRANSMISSION_PASSWORD", "")
    if not username or not password:
        raise ApiError(
            provider=ProviderName.TRANSMISSION,
            http_status=0,
            message="Missing TRANSMISSION_USERNAME or TRANSMISSION_PASSWORD",
        )

    base_url = f"http://{entry.host}:{entry.port}"
    transport = HttpTransport(
        TransportPolicy(
            provider_name=f"{ProviderName.TRANSMISSION.value}-precheck",
            base_url=base_url,
            auth=LoginAuth(username, password),
            timeout_seconds=5,
        ),
        event_bus=EventBus(),
    )

    # Pre-check: POST a lightweight session_get to exercise auth + RPC stack.
    # 200 = reachable, 401 = bad creds, 409 = CSRF dance needed (normal).
    try:
        transport.post(
            "/transmission/rpc",
            data={
                "method": "session_get",
                "params": {"fields": ["version"]},
                "id": 1,
            },
        )
    except ApiError as e:
        if e.http_status == 401:
            raise
        if e.http_status != 409:
            raise

    log.debug("transmission_pre_check_ok", host=entry.host, port=entry.port)
    return TransmissionClient(entry.host, entry.port, username, password)


# -- Internal helpers --------------------------------------------------------


def _split_labels(labels: list[str]) -> tuple[str | None, list[str]]:
    """Split a flat Transmission labels list into (category, tags) (D5/F-A).

    Transmission stores ``labels = [category, *tags]`` flat. An empty-string at
    ``labels[0]`` is the no-category sentinel (written by :func:`_labels` when a
    category-less torrent carries tags): in that case ``labels[1:]`` are the
    tags and the category is ``None``. This keeps tags readable as tags on
    category-less torrents — the property the ingest skip (``SEED_PURE in
    tags``) depends on.

    Args:
        labels: The torrent's flat labels list.

    Returns:
        A ``(category, tags)`` pair: ``category`` is ``None`` when ``labels`` is
        empty or its first element is the empty-string sentinel; ``tags`` is the
        remaining labels.
    """
    if labels and labels[0] == "":
        return None, list(labels[1:])
    if labels:
        return labels[0], list(labels[1:])
    return None, []


def _labels(category: str | None, tags: list[str]) -> list[str]:
    """Build Transmission labels list from category and tags (D5/F-A).

    Round-trip: write ``labels=[category, *tags]``; read back with
    :func:`_split_labels`. Category is deduped if it also appears in tags.

    No-category sentinel (F-A): when ``category is None`` and ``tags`` is
    non-empty, the leading slot is an empty string (``["", *deduped_tags]``) so
    the read side recovers the tags as tags rather than promoting the first tag
    to the category slot. ``category is None`` with no tags stays ``[]``; a set
    ``category`` is unchanged (``[category, *deduped_tags]``).

    Args:
        category: Category string or None.
        tags: Tag strings.

    Returns:
        Ordered list ``[category, *deduped_tags]``, or ``["", *deduped_tags]``
        when ``category`` is ``None`` and ``tags`` is non-empty, or ``[]`` when
        both are empty.
    """
    deduped_tags: list[str] = []
    for tag in tags:
        if tag not in deduped_tags:
            deduped_tags.append(tag)
    if category is not None:
        # Category leads; dedupe a tag that equals the category.
        return [category, *(tag for tag in deduped_tags if tag != category)]
    if deduped_tags:
        # No-category sentinel: keep tags readable as tags (F-A).
        return ["", *deduped_tags]
    return []


def _torrent_item(t: transmission_rpc.Torrent) -> TorrentItem:
    """Map a transmission-rpc Torrent object to a TorrentItem."""
    content_path = ""
    if t.download_dir:
        files = t.get_files()
        if len(files) == 1:
            content_path = str(Path(t.download_dir) / files[0].name)
        elif t.name:
            content_path = str(Path(t.download_dir) / t.name)

    category, tags = _split_labels(list(getattr(t, "labels", None) or []))

    added_on = None
    if t.added_date:
        if isinstance(t.added_date, datetime):
            added_on = t.added_date
        else:
            added_on = datetime.fromtimestamp(t.added_date)

    # done_date is optional — not present on in-progress torrents.
    done_date = getattr(t, "done_date", None)
    completion_on: int | None = None
    if done_date:
        if isinstance(done_date, datetime):
            completion_on = int(done_date.timestamp())
        else:
            # transmission-rpc typically returns datetime; handle int defensively.
            completion_on = int(done_date)

    return TorrentItem(
        hash=t.hash_string,
        name=t.name,
        size_bytes=t.total_size,
        progress=float(t.percent_done),
        state=str(t.status),
        ratio=float(getattr(t, "ratio", 0.0) or 0.0),
        content_path=Path(content_path) if content_path else None,
        category=category,
        tags=tags,
        added_on=added_on,
        save_path=str(t.download_dir) if t.download_dir else "",
        completion_on=completion_on,
    )
