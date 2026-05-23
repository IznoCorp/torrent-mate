"""Active torrent client resolver.

Implements DESIGN §5.3: build_active_torrent_client() reads cfg.active,
validates the chosen client is enabled and credentialed, constructs and
returns the concrete client instance the pipeline uses.

The factory return type is ``QBitClient | TransmissionClient`` — the
union of concrete implementations, which mypy uses to verify that callers
only invoke capabilities actually present on both branches. This replaces
the former ``TorrentClientFull`` composite Protocol cast (DEV #38).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

from personalscraper.api._activation import PROVIDER_CREDS
from personalscraper.api._contracts import ApiError
from personalscraper.conf.models.api_config import TorrentConfig

if TYPE_CHECKING:
    from personalscraper.api.torrent.qbittorrent import QBitClient
    from personalscraper.api.torrent.transmission import TransmissionClient

_CLIENT_IMPL: dict[str, str] = {
    "qbittorrent": "personalscraper.api.torrent.qbittorrent",
    "transmission": "personalscraper.api.torrent.transmission",
}


def build_active_torrent_client(
    cfg: TorrentConfig,
    env: Mapping[str, str] | None = None,
) -> "QBitClient | TransmissionClient":
    """Read cfg.active, validate creds, return concrete torrent client instance.

    The return type is the union of the two supported implementations
    (``QBitClient | TransmissionClient``). Each concrete class composes
    only the atomic capability protocols it genuinely supports, so callers
    can narrow the returned union with ``isinstance`` when they need a
    capability not shared by all implementations (e.g. ``AuthenticatedClient``
    is only implemented by ``QBitClient``).

    Args:
        cfg: Parsed torrent.json5 configuration.
        env: Credential source (defaults to os.environ for testability).

    Returns:
        A concrete ``QBitClient`` or ``TransmissionClient`` for the active provider.

    Raises:
        ValueError: cfg.active empty, not in cfg.clients, or chosen client disabled.
        ApiError: Chosen client missing required credentials.
        ValueError: Chosen client not yet implemented.
    """
    if not cfg.active:
        raise ValueError("No active torrent client configured")

    if cfg.active not in cfg.clients:
        raise ValueError(f"Active torrent client {cfg.active!r} not found in torrent.clients")

    client_entry = cfg.clients[cfg.active]
    if not client_entry.enabled:
        raise ValueError(f"Torrent client {cfg.active!r} is disabled")

    if env is None:
        env = os.environ

    required = PROVIDER_CREDS.get(cfg.active, [])
    missing = [k for k in required if not env.get(k)]
    if missing:
        raise ApiError(
            provider=cfg.active,
            http_status=0,
            message=f"Missing required credentials: {', '.join(missing)}",
        )

    module_path = _CLIENT_IMPL.get(cfg.active)
    if module_path is None:
        raise ValueError(f"Unknown torrent client: {cfg.active!r}")

    import importlib  # noqa: PLC0415

    mod = importlib.import_module(module_path)
    # mod.build_client() returns Any (dynamic import); cast to the declared
    # union so mypy can verify capability calls at all call sites (DEV #38).
    return cast("QBitClient | TransmissionClient", mod.build_client(cfg.active, cfg.clients[cfg.active], env))
