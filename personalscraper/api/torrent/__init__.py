"""Public API of the torrent family.

Names are resolved lazily so importing the package pulls no client.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from personalscraper.api.torrent._contracts import TorrentAdder as TorrentAdder
    from personalscraper.api.torrent._factory import build_active_torrent_client as build_active_torrent_client

#: Public name -> the module that defines it, imported on first access: an eager import here would
#: pull that module's tree into every ``import`` of the package (``--help`` included).
_LAZY: dict[str, str] = {
    "TorrentAdder": "personalscraper.api.torrent._contracts",
    "build_active_torrent_client": "personalscraper.api.torrent._factory",
}

__all__ = [
    "TorrentAdder",
    "build_active_torrent_client",
]


def __getattr__(name: str) -> Any:
    """Resolve a public name on first access (PEP 562).

    Args:
        name: The attribute looked up on the package.

    Returns:
        The object the name stands for.

    Raises:
        AttributeError: ``name`` is not one of this package's public names.
    """
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module), name)
