"""Config editor API read endpoints (config-editor feature).

Four read-only GET endpoints under ``/api/config/*`` serving the visual
config editor data contract defined in
``docs/features/config-editor/plan/phase-02-backend-routes.md`` §2.2:

- ``GET /schema`` → :class:`ConfigSchemaResponse`
- ``GET /files`` → :class:`FilesResponse`
- ``GET /files/{name}`` → :class:`FileContent`
- ``GET /status`` → :class:`ConfigStatusResponse`

All routes are guarded by ``require_session`` inherited from the parent
``guarded_api`` router (registration in app.py, sub-phase 2.4).  Auth
dependencies are NOT added here — they are wired at registration time
(mirroring maintenance.py).

**Config directory resolution**: The config directory is resolved at request
time via :func:`personalscraper.conf.loader.resolve_config_path`, which reads
the ``PERSONALSCRAPER_CONFIG`` environment variable (or falls back to
``./config/``).  Storing the config dir on ``app.state`` at ``create_app``
time is out of scope for this sub-phase; the env-var-driven resolution is
deterministic per process.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import cast

from fastapi import APIRouter, HTTPException, Request

from personalscraper.conf.loader import (
    _LOCAL_FILENAME,
    _MASTER_FILENAME,
    _load_json5_file,
    resolve_config_path,
)
from personalscraper.conf.models.config import Config
from personalscraper.logger import get_logger
from personalscraper.web.models.config import (
    ConfigSchemaResponse,
    ConfigStatusResponse,
    FileContent,
    FileInfo,
    FilesResponse,
)

router = APIRouter(prefix="/api/config", tags=["config"])
logger = get_logger(__name__)

#: Top-level config keys whose modification requires a web process restart.
#: Unknown keys default to ``True`` at lookup time (fail-safe).  See
#: docs/features/config-editor/plan/phase-02-backend-routes.md §2.4.
RESTART_IMPACT: dict[str, bool] = {
    "web": True,
    "paths": True,
    "indexer": True,
    # All others → False ("effective next run"):
    "disks": False,
    "categories": False,
    "custom_categories": False,
    "category_rules": False,
    "anime_rule": False,
    "genre_mapping": False,
    "staging_dirs": False,
    "library": False,
    "scraper": False,
    "ingest": False,
    "fuzzy_match": False,
    "trailers": False,
    "thresholds": False,
    "metadata": False,
    "providers": False,
    "torrent": False,
    "tracker": False,
    "ranking": False,
    "notify": False,
    "acquire": False,
    "watch_seed": False,
}


def restart_required_for(key: str) -> bool:
    """Return whether changing *key* requires a web process restart.

    Unknown keys default to ``True`` (fail-safe: if we don't know, assume a
    restart is needed).

    Args:
        key: Top-level config key name.

    Returns:
        ``True`` if a restart is required, ``False`` otherwise.
    """
    return RESTART_IMPACT.get(key, True)


def _config_dir() -> Path:
    """Resolve the active config directory at request time.

    Uses :func:`resolve_config_path` which reads ``PERSONALSCRAPER_CONFIG``
    (env-var driven, deterministic per process).  Caching the result on app
    state is deferred to a future sub-phase.

    Returns:
        Absolute path to the config directory.
    """
    return resolve_config_path()


def _sha256(path: Path) -> str:
    """Return the hex-encoded SHA-256 digest of *path* contents.

    Args:
        path: Absolute path to a file.

    Returns:
        64-character lowercase hex string.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── Ownership computation (shared by /schema and /files) ───────────────────


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


# ── Shadowed keys (local.json5 overrides) ──────────────────────────────────


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


# ── Boot snapshot (lazy, per app instance) ─────────────────────────────────


def _boot_hashes(request: Request) -> dict[str, str]:
    """Return the boot-time SHA-256 snapshot, capturing it on first access.

    The snapshot is stored on ``request.app.state.config_boot_hashes`` and
    computed once per app instance (lazy, guarded by ``getattr``).

    Args:
        request: The incoming FastAPI request.

    Returns:
        Dict mapping filename → sha256 hex digest at boot time.
    """
    if not getattr(request.app.state, "config_boot_hashes", None):
        config_dir = _config_dir()
        hashes: dict[str, str] = {}

        # Master.
        master_path = config_dir / _MASTER_FILENAME
        if master_path.is_file():
            hashes[_MASTER_FILENAME] = _sha256(master_path)

        # Overlays.
        master = _load_json5_file(master_path)
        for name in master.get("overlays", []):
            overlay_path = config_dir / name
            if overlay_path.is_file():
                hashes[name] = _sha256(overlay_path)

        # Local.
        local_path = config_dir / _LOCAL_FILENAME
        if local_path.is_file():
            hashes[_LOCAL_FILENAME] = _sha256(local_path)

        request.app.state.config_boot_hashes = hashes
        logger.debug("config_boot_hashes_captured", count=len(hashes))

    return cast("dict[str, str]", request.app.state.config_boot_hashes)


# ── Cache key for the (immutable) schema/ownership/impact aggregate ────────

_SCHEMA_CACHE_KEY = "_config_schema_response"


# ── GET /schema ────────────────────────────────────────────────────────────


@router.get("/schema", response_model=ConfigSchemaResponse)
def get_schema(request: Request) -> ConfigSchemaResponse:
    """Return the JSON Schema, key ownership, and restart-impact map.

    Computes the JSON Schema from ``Config.model_json_schema()``, derives
    key ownership from the overlays array in master config.json5, and
    returns the static RESTART_IMPACT map.

    The result is cached on ``request.app.state`` (lazy, first access).

    Args:
        request: The incoming FastAPI request.

    Returns:
        A :class:`ConfigSchemaResponse` with schema, ownership, and restart
        impact data.
    """
    if not getattr(request.app.state, _SCHEMA_CACHE_KEY, None):
        config_dir = _config_dir()
        json_schema = Config.model_json_schema()
        ownership = _compute_ownership(config_dir)
        response = ConfigSchemaResponse(
            json_schema=json_schema,
            ownership=ownership,
            restart_impact=dict(RESTART_IMPACT),
        )
        setattr(request.app.state, _SCHEMA_CACHE_KEY, response)

    return cast(ConfigSchemaResponse, getattr(request.app.state, _SCHEMA_CACHE_KEY))


# ── GET /files ─────────────────────────────────────────────────────────────


@router.get("/files", response_model=FilesResponse)
def get_files(request: Request) -> FilesResponse:
    """Return metadata for every file in the config overlays array.

    Lists the master config.json5, each declared overlay, and local.json5
    (if present).  For each file computes the SHA-256 digest, filesystem
    stat info, and shadowed keys (keys overridden by local.json5).

    Args:
        request: The incoming FastAPI request.

    Returns:
        A :class:`FilesResponse` with one :class:`FileInfo` per file.
    """
    config_dir = _config_dir()
    local_keys_set = _local_keys(config_dir)
    files: list[FileInfo] = []

    # Master.
    master_path = config_dir / _MASTER_FILENAME
    master = _load_json5_file(master_path)
    master_owned = [k for k in master if k != "overlays"]
    master_st = master_path.stat()
    files.append(
        FileInfo(
            name=_MASTER_FILENAME,
            owned_keys=master_owned,
            sha256=_sha256(master_path),
            mtime=master_st.st_mtime,
            size=master_st.st_size,
            shadowed_keys=_compute_shadowed_keys(master_owned, local_keys_set),
        )
    )

    # Overlays (in declared order).
    for name in master.get("overlays", []):
        overlay_path = config_dir / name
        if overlay_path.is_file():
            overlay = _load_json5_file(overlay_path)
            overlay_owned = [k for k in overlay if k != "__source__"]
            overlay_st = overlay_path.stat()
            files.append(
                FileInfo(
                    name=name,
                    owned_keys=overlay_owned,
                    sha256=_sha256(overlay_path),
                    mtime=overlay_st.st_mtime,
                    size=overlay_st.st_size,
                    shadowed_keys=_compute_shadowed_keys(overlay_owned, local_keys_set),
                )
            )

    # Local (if present).
    local_path = config_dir / _LOCAL_FILENAME
    if local_path.is_file():
        try:
            local = _load_json5_file(local_path)
        except Exception:
            local = {}
        local_owned = [k for k in local if k != "__source__"]
        local_st = local_path.stat()
        files.append(
            FileInfo(
                name=_LOCAL_FILENAME,
                owned_keys=local_owned,
                sha256=_sha256(local_path),
                mtime=local_st.st_mtime,
                size=local_st.st_size,
                shadowed_keys=[],  # local.json5 cannot shadow itself
            )
        )

    return FilesResponse(files=files)


# ── GET /files/{name} ──────────────────────────────────────────────────────


def _valid_file_names(config_dir: Path) -> set[str]:
    """Return the set of valid config file names for this config directory.

    Args:
        config_dir: Absolute path to the config directory.

    Returns:
        Set of basenames that can be requested via ``GET /files/{name}``.
    """
    names = {_MASTER_FILENAME, _LOCAL_FILENAME}
    master_path = config_dir / _MASTER_FILENAME
    if master_path.is_file():
        master = _load_json5_file(master_path)
        names.update(master.get("overlays", []))
    return names


@router.get("/files/{name}", response_model=FileContent)
def get_file(name: str, request: Request) -> FileContent:
    """Return the parsed contents of a single config file.

    Args:
        name: Config file basename (e.g. ``"paths.json5"``).
        request: The incoming FastAPI request.

    Returns:
        A :class:`FileContent` with parsed values, SHA-256, and shadowed keys.

    Raises:
        404: If *name* is not a declared overlay, ``local.json5``, or
            ``config.json5``.
    """
    config_dir = _config_dir()
    valid_names = _valid_file_names(config_dir)

    if name not in valid_names:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown config file: {name!r}. Valid files: {', '.join(sorted(valid_names))}",
        )

    file_path = config_dir / name
    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Config file {name!r} is declared but does not exist on disk",
        )

    values = _load_json5_file(file_path)
    # Remove internal sentinels.
    values = {k: v for k, v in values.items() if k != "__source__"}

    local_keys_set = _local_keys(config_dir)
    owned_keys = list(values.keys())
    shadowed = _compute_shadowed_keys(owned_keys, local_keys_set)

    return FileContent(
        name=name,
        values=values,
        sha256=_sha256(file_path),
        shadowed_keys=shadowed,
    )


# ── GET /status ────────────────────────────────────────────────────────────


@router.get("/status", response_model=ConfigStatusResponse)
def get_status(request: Request) -> ConfigStatusResponse:
    """Return deployment status: role, read-only flag, and stale file detection.

    Compares current on-disk SHA-256 digests against the boot-time snapshot
    (captured lazily on first access).  A file is *stale* when its current
    digest differs from boot time.  *restart_required* is ``True`` when any
    stale file exists.

    Args:
        request: The incoming FastAPI request.

    Returns:
        A :class:`ConfigStatusResponse` with role, read_only, restart_required,
        and stale_files.
    """
    role = os.environ.get("PERSONALSCRAPER_WEB_ROLE", "prod")
    read_only = role == "staging"

    boot = _boot_hashes(request)
    config_dir = _config_dir()

    stale_files: list[str] = []
    for name, boot_hash in boot.items():
        file_path = config_dir / name
        if file_path.is_file():
            current_hash = _sha256(file_path)
            if current_hash != boot_hash:
                stale_files.append(name)

    # restart_required = any stale file (simplified: True if anything changed).
    restart_required = len(stale_files) > 0

    return ConfigStatusResponse(
        role=role,
        read_only=read_only,
        restart_required=restart_required,
        stale_files=sorted(stale_files),
    )
