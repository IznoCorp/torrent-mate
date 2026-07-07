"""Config editor API read and write endpoints (config-editor feature).

Nine endpoints under ``/api/config/*`` serving the visual config editor
data contract defined in
``docs/features/config-editor/plan/phase-02-backend-routes.md`` §2.2–2.3:

Read endpoints (sub-phase 2.2):
- ``GET /schema`` → :class:`ConfigSchemaResponse`
- ``GET /files`` → :class:`FilesResponse`
- ``GET /files/{name}`` → :class:`FileContent`
- ``GET /status`` → :class:`ConfigStatusResponse`

Write endpoints (sub-phase 2.3):
- ``POST /validate`` → :class:`ValidateResponse`
- ``PUT /files/{name}`` → :class:`PutFileResponse`
- ``GET /secrets`` → :class:`SecretsResponse`
- ``PUT /secrets`` → :class:`PutFileResponse`
- ``POST /restart-web`` → :class:`RestartResponse`

All routes are guarded by ``require_session`` inherited from the parent
``guarded_api`` router (registration in app.py, sub-phase 2.4).  Auth
dependencies are NOT added here — they are wired at registration time
(mirroring maintenance.py).

**Config directory resolution**: The config directory is resolved at request
time via :func:`personalscraper.conf.loader.resolve_config_path`, which reads
the ``PERSONALSCRAPER_CONFIG`` environment variable (or falls back to
``./config/``).
"""

from __future__ import annotations

import contextlib
import datetime
import hashlib
import os
import shlex
import subprocess
import tempfile
import threading
from datetime import timezone
from pathlib import Path
from typing import cast

import json5
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError as PydanticValidationError

from personalscraper.conf.envfile import read_env_catalog, write_env_keys
from personalscraper.conf.loader import (
    _LOCAL_FILENAME,
    _MASTER_FILENAME,
    ConfigLoadError,
    ConfigValidationError,
    _load_json5_file,
    resolve_config_path,
    validate_candidate,
)
from personalscraper.conf.models.config import Config
from personalscraper.logger import get_logger
from personalscraper.web.deps import require_x_requested_with
from personalscraper.web.models.config import (
    ConfigSchemaResponse,
    ConfigStatusResponse,
    FileContent,
    FileInfo,
    FilesResponse,
    PutFileRequest,
    PutFileResponse,
    RestartResponse,
    SecretEntry,
    SecretsPutRequest,
    SecretsResponse,
    ValidateRequest,
    ValidateResponse,
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

#: Module-level lock serializing config file writes.  Routes are sync
#: handlers running in the threadpool, so ``threading.Lock`` (not
#: ``asyncio.Lock``) is the correct primitive.
_write_lock = threading.Lock()


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


# ── Writable file names (write endpoints only) ─────────────────────────────


def _writable_file_names(config_dir: Path) -> set[str]:
    """Return the set of config file names that can be written to via PUT.

    Only overlay files and ``local.json5`` are writable — ``config.json5``
    (master) is read-only through the write endpoints.

    Args:
        config_dir: Absolute path to the config directory.

    Returns:
        Set of basenames that can be targeted by ``PUT /files/{name}``.
    """
    names: set[str] = {_LOCAL_FILENAME}
    master_path = config_dir / _MASTER_FILENAME
    if master_path.is_file():
        master = _load_json5_file(master_path)
        names.update(master.get("overlays", []))
    return names


# ── Shared staging guard ───────────────────────────────────────────────────


def _is_staging() -> bool:
    """Return ``True`` if the web process is in read-only staging mode.

    Reads the ``PERSONALSCRAPER_WEB_ROLE`` environment variable, defaulting
    to ``"prod"``.

    Returns:
        ``True`` when the role is ``"staging"``.
    """
    return os.environ.get("PERSONALSCRAPER_WEB_ROLE", "prod") == "staging"


# ── POST /validate ─────────────────────────────────────────────────────────


@router.post("/validate", response_model=ValidateResponse)
def validate_file(
    body: ValidateRequest,
    request: Request,
    _xrw: None = Depends(require_x_requested_with),
) -> ValidateResponse:
    """Validate a candidate config file without writing to disk.

    Calls :func:`~personalscraper.conf.loader.validate_candidate` with a
    single-file replacement.  On success returns warnings; on failure
    returns 422 with Pydantic error loc paths.

    Args:
        body: The validation request with ``file_name`` and ``values``.
        request: The incoming FastAPI request.

    Returns:
        A :class:`ValidateResponse` with any warnings from the validator.

    Raises:
        404: If *body.file_name* is not a known overlay or ``local.json5``.
        422: If the candidate values fail Pydantic validation, with detail
            carrying the error loc paths extracted from the underlying
            :class:`pydantic.ValidationError`.
    """
    config_dir = _config_dir()

    try:
        _, warnings = validate_candidate(config_dir, {body.file_name: body.values})
    except ConfigLoadError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown config file: {body.file_name!r}",
        )
    except ConfigValidationError as exc:
        cause = exc.__cause__
        if cause is not None and isinstance(cause, PydanticValidationError):
            detail = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in cause.errors()]
            raise HTTPException(status_code=422, detail=detail)
        raise HTTPException(status_code=422, detail=str(exc))

    return ValidateResponse(warnings=warnings)


# ── PUT /files/{name} ──────────────────────────────────────────────────────


@router.put("/files/{name}", response_model=PutFileResponse)
def put_file(
    name: str,
    body: PutFileRequest,
    request: Request,
    _xrw: None = Depends(require_x_requested_with),
) -> PutFileResponse:
    """Validate and atomically write a config overlay file.

    Order:
    1. Role check — 403 if staging (read-only).
    2. Existence check — 404 if *name* is not a writable file
       (overlays + local.json5; master is read-only through this endpoint).
    3. SHA-256 precondition — 412 if *body.base_sha256* ≠ current
       on-disk digest (empty string for a non-existent local.json5).
    4. Validate candidate via
       :func:`~personalscraper.conf.loader.validate_candidate` — 422
       with Pydantic error loc paths on failure (no backup created).
    5. Backup current file to ``.backups/{name}.{utc}.json5``, prune to
       10 most recent per file name.
    6. Atomic write via temp file + ``os.replace`` + ``fsync``,
       serialized with a module-level ``threading.Lock``.
    7. Return 200 with warnings and restart-required flag.

    Args:
        name: Config file basename (e.g. ``"paths.json5"``).
        body: Request payload with ``values`` and ``base_sha256``.
        request: The incoming FastAPI request.

    Returns:
        A :class:`PutFileResponse` with warnings and restart_required flag.

    Raises:
        403: If ``PERSONALSCRAPER_WEB_ROLE`` is ``"staging"``.
        404: If *name* is not a writable config file.
        412: If *body.base_sha256* does not match the current on-disk file
            digest.
        422: If the candidate values fail Pydantic validation.
    """
    if _is_staging():
        raise HTTPException(status_code=403, detail="read-only")

    config_dir = _config_dir()
    writable_names = _writable_file_names(config_dir)
    if name not in writable_names:
        raise HTTPException(status_code=404, detail=f"Unknown config file: {name!r}")

    file_path = config_dir / name

    # ── SHA-256 precondition ──
    if file_path.is_file():
        current_sha256 = _sha256(file_path)
    else:
        # local.json5 may not exist yet — empty string matches empty base.
        current_sha256 = ""

    if body.base_sha256 != current_sha256:
        raise HTTPException(status_code=412, detail="file modified since last read")

    # ── Validate candidate (before any filesystem mutation) ──
    try:
        _, warnings = validate_candidate(config_dir, {name: body.values})
    except ConfigLoadError:
        raise HTTPException(status_code=404, detail=f"Unknown config file: {name!r}")
    except ConfigValidationError as exc:
        cause = exc.__cause__
        if cause is not None and isinstance(cause, PydanticValidationError):
            detail = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in cause.errors()]
            raise HTTPException(status_code=422, detail=detail)
        raise HTTPException(status_code=422, detail=str(exc))

    # ── Serialized write section ──
    with _write_lock:
        # Backup existing file.
        if file_path.is_file():
            backup_dir = config_dir / ".backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            # Microsecond granularity: second-level timestamps collide (and
            # silently overwrite) when saves land within the same second.
            ts = datetime.datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup_path = backup_dir / f"{name}.{ts}.json5"
            backup_path.write_bytes(file_path.read_bytes())

            # Prune to 10 most recent backups per file name.
            backups = sorted(backup_dir.glob(f"{name}.*.json5"))
            if len(backups) > 10:
                for old in backups[:-10]:
                    old.unlink()

        # Atomic write with header comment.
        header = (
            f"// Written by TorrentMate config editor "
            f"{datetime.datetime.now(timezone.utc).isoformat()} "
            f"— hand-written comments are not preserved.\n"
        )
        content = header + json5.dumps(body.values, indent=2) + "\n"

        fd, tmp_name = tempfile.mkstemp(dir=str(config_dir), prefix=f".{name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, str(file_path))
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

    # ── Compute restart_required ──
    restart_required_flag = any(restart_required_for(k) for k in body.values)

    return PutFileResponse(warnings=warnings, restart_required=restart_required_flag)


# ── GET /secrets ───────────────────────────────────────────────────────────


@router.get("/secrets", response_model=SecretsResponse)
def get_secrets(request: Request) -> SecretsResponse:
    """Return the secret key catalog with ``is_set`` flags.

    Parses ``.env.example`` at the project root to enumerate known keys
    and their descriptions, then checks ``.env`` for which keys currently
    have a non-empty value.  Secret values are **never** included in the
    response.

    Args:
        request: The incoming FastAPI request.

    Returns:
        A :class:`SecretsResponse` with one :class:`SecretEntry` per key.
    """
    config_dir = _config_dir()
    repo_root = config_dir.parent

    env_example_path = repo_root / ".env.example"
    if not env_example_path.is_file():
        return SecretsResponse(secrets=[])

    catalog = read_env_catalog(env_example_path)

    # Parse .env for is_set flags — values are never read or returned.
    env_path = repo_root / ".env"
    env_set: set[str] = set()
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" in stripped:
                key, _, value = stripped.partition("=")
                if value:
                    env_set.add(key)

    secrets = [SecretEntry(key=key, description=desc, is_set=key in env_set) for key, desc in catalog.items()]
    return SecretsResponse(secrets=secrets)


# ── PUT /secrets ───────────────────────────────────────────────────────────


@router.put("/secrets", response_model=PutFileResponse)
def put_secrets(
    body: SecretsPutRequest,
    request: Request,
    _xrw: None = Depends(require_x_requested_with),
) -> PutFileResponse:
    """Write secret values to ``.env`` via atomic upsert.

    Only keys declared in ``.env.example`` are accepted.  Secret values are
    **never** logged.

    Args:
        body: Mapping of ``{KEY: value, ...}`` to upsert into ``.env``.
        request: The incoming FastAPI request.

    Returns:
        A :class:`PutFileResponse` with ``restart_required=True``.

    Raises:
        403: If ``PERSONALSCRAPER_WEB_ROLE`` is ``"staging"``.
        422: If any key in *body* is not in the catalog.  Values are
            **never** echoed in the error detail.
    """
    if _is_staging():
        raise HTTPException(status_code=403, detail="read-only")

    config_dir = _config_dir()
    repo_root = config_dir.parent

    env_example_path = repo_root / ".env.example"
    if not env_example_path.is_file():
        raise HTTPException(status_code=404, detail=".env.example not found")

    catalog = read_env_catalog(env_example_path)

    # Reject unknown keys — NEVER echo the value.
    unknown_keys = sorted(set(body.root.keys()) - set(catalog.keys()))
    if unknown_keys:
        raise HTTPException(
            status_code=422,
            detail={"unknown_keys": unknown_keys},
        )

    env_path = repo_root / ".env"
    logger.info("config_secrets_write", keys=sorted(body.root.keys()))
    write_env_keys(body.root, env_path)

    return PutFileResponse(warnings=[], restart_required=True)


# ── POST /restart-web ──────────────────────────────────────────────────────


@router.post("/restart-web", response_model=RestartResponse, status_code=202)
def restart_web(
    request: Request,
    _xrw: None = Depends(require_x_requested_with),
) -> RestartResponse:
    """Schedule a PM2 restart of the web process.

    The restart is handed off to a detached subprocess that sleeps 0.5 s
    (so the 202 response flushes first), then runs ``pm2 restart`` on the
    name configured in ``PERSONALSCRAPER_PM2_NAME``.

    Args:
        request: The incoming FastAPI request.

    Returns:
        202 with :class:`RestartResponse` ``{"status": "scheduled"}``.

    Raises:
        403: If ``PERSONALSCRAPER_WEB_ROLE`` is ``"staging"``.
        404: If ``PERSONALSCRAPER_PM2_NAME`` is not set in the environment.
    """
    if _is_staging():
        raise HTTPException(status_code=403, detail="read-only")

    pm2_name = os.environ.get("PERSONALSCRAPER_PM2_NAME")
    if not pm2_name:
        raise HTTPException(status_code=404, detail="restart not configured")

    subprocess.Popen(
        ["sh", "-c", f"sleep 0.5 && pm2 restart {shlex.quote(pm2_name)}"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    logger.info("config_restart_scheduled", pm2_name=pm2_name)
    return RestartResponse(status="scheduled")
