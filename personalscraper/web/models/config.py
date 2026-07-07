"""Pydantic request/response models for the config editor API.

See docs/features/config-editor/DESIGN.md §4.2 for the route contract these
models serve.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, RootModel


class FileInfo(BaseModel):
    """Metadata for a single config file listed in ``GET /api/config/files``.

    Attributes:
        name: Config file basename (e.g. ``"master.json5"``).
        owned_keys: Top-level keys owned by this file.
        sha256: Hex digest of the file contents on disk.
        mtime: Last modification time as a Unix timestamp (float).
        size: File size in bytes.
        shadowed_keys: Keys owned by this file that are overridden by
            ``local.json5``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    owned_keys: list[str]
    sha256: str
    mtime: float
    size: int
    shadowed_keys: list[str]


class FilesResponse(BaseModel):
    """Response body for ``GET /api/config/files``.

    Attributes:
        files: Metadata for every file in the config overlays array.
    """

    model_config = ConfigDict(extra="forbid")

    files: list[FileInfo]


class FileContent(BaseModel):
    """Response body for ``GET /api/config/files/{name}``.

    Attributes:
        name: Config file basename.
        values: Parsed JSON5 contents keyed by top-level key.
        sha256: Hex digest of the file contents on disk.
        shadowed_keys: Keys in this file overridden by ``local.json5``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    values: dict[str, Any]
    sha256: str
    shadowed_keys: list[str]


class ConfigSchemaResponse(BaseModel):
    """Response body for ``GET /api/config/schema``.

    Attributes:
        json_schema: JSON Schema for the merged config (generated via
            ``Config.model_json_schema()``).
        ownership: Mapping of each top-level key to the file that owns it.
        restart_impact: Mapping of each top-level key to whether changing
            it requires a web process restart.
    """

    model_config = ConfigDict(extra="forbid")

    json_schema: dict[str, Any]
    ownership: dict[str, str]
    restart_impact: dict[str, bool]


class PutFileRequest(BaseModel):
    """Request body for ``PUT /api/config/files/{name}``.

    Attributes:
        values: Key-value pairs to write into the config file.
        base_sha256: Expected SHA-256 digest of the file before the write
            (used for optimistic concurrency control — 412 if mismatched).
    """

    model_config = ConfigDict(extra="forbid")

    values: dict[str, Any]
    base_sha256: str


class PutFileResponse(BaseModel):
    """Response body for ``PUT /api/config/files/{name}``.

    Attributes:
        warnings: Validation warnings from ``validate_candidate()``.
        restart_required: Whether the changes affect a key flagged in the
            restart-impact map.
    """

    model_config = ConfigDict(extra="forbid")

    warnings: list[str]
    restart_required: bool


class ValidateRequest(BaseModel):
    """Request body for ``POST /api/config/validate``.

    Attributes:
        file_name: Config file basename to validate against.
        values: Candidate key-value pairs to validate.
    """

    model_config = ConfigDict(extra="forbid")

    file_name: str
    values: dict[str, Any]


class ValidateResponse(BaseModel):
    """Response body (200) for ``POST /api/config/validate``.

    Attributes:
        warnings: Validation warnings returned by ``validate_candidate()``.
    """

    model_config = ConfigDict(extra="forbid")

    warnings: list[str]


class ConfigStatusResponse(BaseModel):
    """Response body for ``GET /api/config/status``.

    Attributes:
        role: Deployment role (``"prod"`` or ``"staging"``).
        read_only: Whether the web process is in read-only mode.
        restart_required: Whether ``stale_files`` is non-empty.
        stale_files: Config filenames whose on-disk SHA-256 differs from the
            boot-time snapshot.
    """

    model_config = ConfigDict(extra="forbid")

    role: str
    read_only: bool
    restart_required: bool
    stale_files: list[str]


class SecretEntry(BaseModel):
    """A single secret key catalogued from ``.env.example``.

    Attributes:
        key: Environment variable name (e.g. ``"TMDB_API_KEY"``).
        description: Human-readable description from the catalog comment.
        is_set: Whether the key has a value in ``.env``.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    description: str
    is_set: bool


class SecretsResponse(BaseModel):
    """Response body for ``GET /api/config/secrets``.

    Attributes:
        secrets: All secret entries from the catalog. Values are never
            included.
    """

    model_config = ConfigDict(extra="forbid")

    secrets: list[SecretEntry]


class SecretsPutRequest(RootModel[dict[str, str]]):
    """Request body for ``PUT /api/config/secrets``.

    Wraps a flat ``{KEY: value, ...}`` mapping. Keys must exist in the
    secret catalog (``.env.example``). Values are the new secret strings.
    """


class RestartResponse(BaseModel):
    """Response body for ``POST /api/config/restart-web``.

    Attributes:
        status: Always ``"scheduled"`` — the restart has been handed off to
            the process manager.
    """

    model_config = ConfigDict(extra="forbid")

    status: str
