"""Pure config-introspection helpers for the config-editor routes.

Split out of :mod:`personalscraper.web.routes.config` (solidify — module-size
relief). These are side-effect-free helpers over a config directory: content
hashing, top-level-key → owning-file ownership, and local.json5 shadow
computation. They perform no FastAPI/request work, so the route module
(:mod:`personalscraper.web.routes.config`) re-imports and consumes them.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from personalscraper.conf.loader import (
    _LOCAL_FILENAME,
    _MASTER_FILENAME,
    _load_json5_file,
)
from personalscraper.logger import get_logger

logger = get_logger(__name__)


def _sha256(path: Path) -> str:
    """Return the hex-encoded SHA-256 digest of *path* contents.

    Args:
        path: Absolute path to a file.

    Returns:
        64-character lowercase hex string.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compute_ownership(config_dir: Path) -> dict[str, str]:
    """Compute the mapping of top-level keys → owning filename.

    Steps:

    1. Read the master ``config.json5`` and its ``overlays`` array.
    2. For each overlay file, json5-load it and map each top-level key
       (excluding ``__source__``) to that filename.
    3. Master-owned keys (everything in config.json5 except ``overlays``)
       map to ``"config.json5"``.

    Args:
        config_dir: Absolute path to the config directory.

    Returns:
        Dict mapping top-level key names to filenames (e.g.
        ``{"paths": "paths.json5"}``).
    """
    master = _load_json5_file(config_dir / _MASTER_FILENAME)
    overlay_names: list[str] = master.get("overlays", [])

    ownership: dict[str, str] = {}

    # Master-owned keys (everything except "overlays").
    for key in master:
        if key != "overlays":
            ownership[key] = _MASTER_FILENAME

    # Overlay-owned keys.
    for name in overlay_names:
        overlay_path = config_dir / name
        if overlay_path.is_file():
            overlay = _load_json5_file(overlay_path)
            for key in overlay:
                if key != "__source__":
                    ownership[key] = name

    return ownership


def _local_keys(config_dir: Path) -> set[str]:
    """Return the set of top-level keys defined in ``local.json5``.

    Fail-soft: returns an empty set if the file is missing or unreadable.

    Args:
        config_dir: Absolute path to the config directory.

    Returns:
        Set of top-level key names from local.json5, or empty set if the file
        does not exist.
    """
    local_path = config_dir / _LOCAL_FILENAME
    if not local_path.is_file():
        return set()
    try:
        local = _load_json5_file(local_path)
    except Exception:
        logger.warning("local_json5_unreadable", path=str(local_path))
        return set()
    return {k for k in local if k != "__source__"}


def _compute_shadowed_keys(owned_keys: list[str], local_keys_set: set[str]) -> list[str]:
    """Return the subset of *owned_keys* that are overridden by local.json5.

    Args:
        owned_keys: Keys owned by a specific file.
        local_keys_set: Keys present in local.json5.

    Returns:
        Sorted list of keys present in both sets.
    """
    return sorted(set(owned_keys) & local_keys_set)
