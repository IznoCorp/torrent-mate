"""Active torrent client resolver.

Implements DESIGN §5.3: build_active_torrent_client() reads cfg.active,
validates the chosen client is enabled and credentialed, constructs and
returns the single TorrentClient instance the pipeline uses.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from personalscraper.api._activation import PROVIDER_CREDS
from personalscraper.api._contracts import ApiError
from personalscraper.api.torrent._base import TorrentClient
from personalscraper.conf.models.api_config import TorrentConfig

_CLIENT_IMPL: dict[str, str] = {
    "qbittorrent": "personalscraper.api.torrent.qbittorrent",
    "transmission": "personalscraper.api.torrent.transmission",
}


def build_active_torrent_client(
    cfg: TorrentConfig,
    env: Mapping[str, str] | None = None,
) -> TorrentClient:
    """Read cfg.active, validate creds, return single TorrentClient instance.

    Args:
        cfg: Parsed torrent.json5 configuration.
        env: Credential source (defaults to os.environ for testability).

    Returns:
        A concrete TorrentClient for the active provider.

    Raises:
        ValueError: cfg.active empty, not in cfg.clients, or chosen client disabled.
        ApiError: Chosen client missing required credentials.
        NotImplementedError: Chosen client not yet implemented.
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

    import importlib
    from typing import cast

    mod = importlib.import_module(module_path)
    return cast(TorrentClient, mod.build_client(cfg.active, cfg.clients[cfg.active], env))
