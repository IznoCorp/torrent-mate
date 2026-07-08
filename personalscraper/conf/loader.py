"""JSON5 config loader with path resolution and validation warnings.

The project uses a split-config layout: a directory (default ``./config/``)
that contains a master ``config.json5`` plus a set of per-concern overlay
files (``paths.json5``, ``disks.json5``, ``indexer.json5`` ...) listed in the
master's ``overlays`` key.

Resolution order applied by :func:`resolve_config_path`:
  1. ``--config`` CLI override (highest priority)
  2. ``$PERSONALSCRAPER_CONFIG`` environment variable
  3. ``./config/``

:func:`load_config` requires the resolved path to be a config directory.

Warnings are non-blocking: they are logged but do not prevent the config from
loading.

Startup checks (non-blocking, warning-only):
  - Category-orphan check (DESIGN §17.2): if ``library.db`` exists, the loader
    queries ``SELECT DISTINCT category_id FROM media_item`` and compares the
    result against the union of declared category IDs in the loaded config.
    Any orphan IDs are logged via the ``indexer.config.category_orphan`` event.
    The loader does NOT refuse to start — the user must run
    ``personalscraper config migrate-category`` to resolve the mismatch.
"""

import os
import sqlite3
from pathlib import Path
from typing import Any

import json5
import pydantic

from personalscraper.conf.models.config import Config
from personalscraper.conf.overlay import ConfigConflictError, ConfigLoadError, merge_overlays
from personalscraper.logger import get_logger

__all__ = [
    "ConfigNotFoundError",
    "ConfigValidationError",
    "ConfigConflictError",
    "ConfigLoadError",
    "resolve_config_path",
    "load_config",
    "load_config_dir",
    "validate_candidate",
    "collect_warnings",
]

_MASTER_FILENAME = "config.json5"
_LOCAL_FILENAME = "local.json5"

log = get_logger("personalscraper.conf.loader")

#: Preferred location for the split-config directory.
DEFAULT_CONFIG_DIR: Path = Path("./config")
ENV_CONFIG_PATH: str = "PERSONALSCRAPER_CONFIG"


class ConfigNotFoundError(FileNotFoundError):
    """Raised when the config file does not exist at the resolved path."""


class ConfigValidationError(ValueError):
    """Raised when config file fails JSON5 parsing or Pydantic validation."""


def resolve_config_path(cli_override: Path | None = None) -> Path:
    """Resolve the active config directory using CLI > env > default.

    Resolution order:
      1. ``--config`` CLI override (highest priority)
      2. ``$PERSONALSCRAPER_CONFIG`` environment variable
      3. ``./config/`` relative to CWD (backwards-compatible)
      4. ``<pkg_root>/config/`` (fallback — works when CWD is not the repo root,
         e.g. running from the staging directory)

    Args:
        cli_override: Path passed via --config CLI option. Takes highest priority.
            Must point at a config directory.

    Returns:
        Resolved absolute path. Existence is verified by the loader, not here.
    """
    if cli_override is not None:
        return cli_override.expanduser().resolve()
    env = os.environ.get(ENV_CONFIG_PATH)
    if env:
        return Path(env).expanduser().resolve()

    cwd_config = DEFAULT_CONFIG_DIR.expanduser().resolve()
    if cwd_config.is_dir():
        return cwd_config

    pkg_root = Path(__file__).resolve().parent.parent.parent
    return pkg_root / "config"


def _load_json5_file(path: Path) -> dict[str, Any]:
    """Read and parse a single JSON5 file, returning a plain dict.

    Args:
        path: Absolute path to the JSON5 file.

    Returns:
        Parsed dict.

    Raises:
        ConfigLoadError: If the file does not exist or cannot be opened.
        ConfigValidationError: If the file contains invalid JSON5 syntax.
    """
    if not path.is_file():
        raise ConfigLoadError(f"Overlay file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        try:
            return dict(json5.load(fh))
        except Exception as exc:
            raise ConfigValidationError(f"JSON5 parse error in {path}: {exc}") from exc


def _build_config(
    config_dir: Path,
    replaced: dict[str, dict[str, Any]] | None = None,
) -> tuple[Config, list[str]]:
    """Shared core: read master, load/merge overlays, validate, collect warnings.

    Factored out so that both :func:`load_config_dir` (production loader) and
    :func:`validate_candidate` (read-only validation for the web config editor)
    share the same merge + Pydantic validation pipeline.  The only difference
    is the *replaced* parameter: when a filename is present in *replaced* the
    candidate dict is used **instead** of reading that file from disk.

    Args:
        config_dir: Path to the config directory (read-only).
        replaced: Optional mapping of overlay filenames (e.g. ``"paths.json5"``)
            to candidate dicts that replace the on-disk file content during
            validation.  ``None`` is equivalent to an empty dict (no
            substitution).

    Returns:
        (validated_config, warnings) tuple where *warnings* is the result of
        :func:`collect_warnings` on the validated config.

    Raises:
        ConfigNotFoundError: If ``config.json5`` does not exist in *config_dir*.
        ConfigLoadError: If a declared overlay file is missing or a key in
            *replaced* does not match any declared overlay or ``local.json5``.
        ConfigValidationError: If any file has invalid JSON5 syntax or the merged
            dict fails pydantic validation.
        ConfigConflictError: If two non-local overlays define the same top-level
            key.
    """
    if replaced is None:
        replaced = {}

    master_path = config_dir / _MASTER_FILENAME
    if not master_path.is_file():
        raise ConfigNotFoundError(
            f"No config.json5 found in {config_dir}. "
            "Run 'personalscraper init-config' to create one from the example template."
        )

    master = _load_json5_file(master_path)

    # Collect overlay dicts in declared order.
    overlay_names: list[str] = master.pop("overlays", [])

    # Validate replaced keys: every key must be a declared overlay or local.json5.
    valid_keys = set(overlay_names) | {_LOCAL_FILENAME}
    unknown = set(replaced) - valid_keys
    if unknown:
        raise ConfigLoadError(
            f"Replacement key(s) not in overlay set: {', '.join(sorted(unknown))}. "
            f"Valid overlay filenames are: {', '.join(sorted(valid_keys))}"
        )

    overlay_dicts: list[dict[str, Any]] = []
    for name in overlay_names:
        if name in replaced:
            # Use candidate dict instead of reading from disk.
            parsed = dict(replaced[name])
        else:
            overlay_path = config_dir / name
            parsed = _load_json5_file(overlay_path)
        # Attach source sentinel so merge_overlays can identify local.json5.
        parsed["__source__"] = config_dir / name
        overlay_dicts.append(parsed)

    # Optional local.json5 — missing is fine, not an error.
    local_path = config_dir / _LOCAL_FILENAME
    if _LOCAL_FILENAME in replaced:
        local_dict = dict(replaced[_LOCAL_FILENAME])
        local_dict["__source__"] = local_path
        overlay_dicts.append(local_dict)
    elif local_path.is_file():
        local_dict = _load_json5_file(local_path)
        local_dict["__source__"] = local_path
        overlay_dicts.append(local_dict)

    # Merge: master is the base; overlays applied in order.
    merged = merge_overlays(master, *overlay_dicts)

    # Resolve relative paths against config_dir.parent (repo root), not CWD.
    # ``init-config`` always places ``config/`` at the repo root, so
    # ``config_dir.parent`` is the project root by construction.
    #
    # The root is exposed as a ContextVar on ``paths_model`` so validators on
    # nested sub-models (PathConfig, IndexerConfig.db_path) can reach it without
    # threading ``context=`` through every field_validator.  ContextVar gives
    # each thread/async task its own value, so parallel config validation (e.g.
    # from the FastAPI threadpool) cannot cross-contaminate — the promotion
    # anticipated by the original comment is now done.
    import personalscraper.conf.models.paths as paths_model

    project_root = config_dir.parent.resolve()
    token = paths_model._PROJECT_ROOT.set(project_root)

    # Validate through pydantic.
    try:
        config = Config.model_validate(merged)
    except pydantic.ValidationError as exc:
        raise ConfigValidationError(f"Validation error merging config in {config_dir}:\n{exc}") from exc
    finally:
        paths_model._PROJECT_ROOT.reset(token)

    return config, collect_warnings(config)


def load_config_dir(config_dir: Path) -> Config:
    """Load and merge a split-config directory into a validated Config.

    Resolution order:
    1. ``<config_dir>/config.json5`` — master file; may declare an ``overlays``
       list of filenames to merge in order.
    2. Each filename listed under ``overlays`` in the master, resolved relative
       to *config_dir*.
    3. Optional ``<config_dir>/local.json5`` — merged last, last-wins semantics,
       never raises ``ConfigConflictError``.

    The ``overlays`` key itself is stripped from the merged dict before pydantic
    validation so it does not leak into the ``Config`` model.

    Args:
        config_dir: Path to the directory containing ``config.json5`` and the
            per-concern overlay files.

    Returns:
        Validated Config instance.

    Raises:
        ConfigNotFoundError: If ``config.json5`` does not exist in *config_dir*.
        ConfigLoadError: If any declared overlay file is missing.
        ConfigValidationError: If any file has invalid JSON5 syntax or the merged
            dict fails pydantic validation.
        ConfigConflictError: If two non-local overlays define the same top-level key.
    """
    config, warnings = _build_config(config_dir)

    # Emit non-blocking warnings.
    for warning in warnings:
        log.warning(warning)

    # Non-blocking category-orphan startup check (DESIGN §17.2).
    _check_category_orphans(config)

    return config


def validate_candidate(
    config_dir: Path,
    replaced: dict[str, dict[str, Any]],
) -> tuple[Config, list[str]]:
    """Validate a candidate config without touching the filesystem.

    Reads overlay files from *config_dir*, substitutes the values in
    *replaced* (mapping overlay filenames → replacement dicts) in memory,
    then runs the full merge + Pydantic validation pipeline.

    Differs from :func:`load_config_dir` in two ways:
    - Skips the category-orphan DB check (no DB touch).
    - Runs genuine filesystem probes (WAL-safety of db_path) that are real
      validation, not side effects.

    Args:
        config_dir: Path to the config directory (read-only).
        replaced: Mapping of overlay filenames (e.g. ``"paths.json5"``) to
            candidate dicts that replace the on-disk file content during
            validation.

    Returns:
        (validated_config, warnings) — same shape as :func:`load_config_dir`
        output, minus the orphan check.

    Raises:
        ConfigNotFoundError: If ``config.json5`` does not exist in *config_dir*.
        ConfigLoadError: If any declared overlay file is missing, or if a key
            in *replaced* does not match any declared overlay or ``local.json5``.
        ConfigValidationError: If any file has invalid JSON5 syntax or the merged
            dict fails pydantic validation.
        ConfigConflictError: If two non-local overlays define the same top-level
            key.
    """
    return _build_config(config_dir, replaced=replaced)


def load_config(path: Path | None = None) -> Config:
    """Load and validate the project configuration directory.

    Emits non-blocking warnings via :func:`collect_warnings` after successful
    validation. The config is returned regardless of warnings.

    Args:
        path: Explicit path to a split-config directory. If ``None``,
            :func:`resolve_config_path` is called to determine which directory
            is active.

    Returns:
        Validated :class:`~personalscraper.conf.models.Config` instance.

    Raises:
        ConfigNotFoundError: If the resolved path is not a directory.
        ConfigValidationError: If JSON5 parsing or Pydantic validation fails.
    """
    resolved = path if path is not None else resolve_config_path()
    if not resolved.is_dir():
        raise ConfigNotFoundError(
            f"No split-config directory at {resolved}. "
            "Run 'personalscraper init-config' to create one from the example template."
        )
    return load_config_dir(resolved)


#: Legacy env var names that were migrated to torrent.json5 in api-unify (0.11.0).
#: Their presence in ``os.environ`` after a migration is silently ignored by the
#: new code path, which would surprise users who haven't updated their ``.env``.
_LEGACY_TORRENT_ENV_VARS = (
    "QBIT_HOST",
    "QBIT_PORT",
    "TRANSMISSION_HOST",
    "TRANSMISSION_PORT",
)


def collect_warnings(config: Config) -> list[str]:
    """Collect non-fatal configuration warnings.

    Four warning types:
    1. A custom_category ID has no disk accepting it -> likely dead config.
    2. A category ID is referenced by disks/rules/mappings but not in
       ``config.categories`` -> default label will be used.
    3. A disk path does not exist on the filesystem -> disk unmounted.
    4. Legacy torrent host/port env vars (``QBIT_HOST``, ``QBIT_PORT``,
       ``TRANSMISSION_HOST``, ``TRANSMISSION_PORT``) are still present in
       ``os.environ`` -> they were migrated to ``config/torrent.json5`` in
       api-unify and are no longer read; the user should remove them from
       ``.env`` and verify the json5 values.

    Args:
        config: Validated Config instance to inspect.

    Returns:
        List of warning strings. Empty if config is fully consistent.
    """
    warnings: list[str] = []

    # Warning 1: custom category declared but no disk accepts it
    for cid in config.custom_categories:
        accepting = config.disks_accepting(cid)
        if not accepting:
            warnings.append(f"dead custom_category '{cid}': no disk accepts it")

    # Warning 2: category ID used somewhere but absent from config.categories
    # Collect all IDs that are referenced by disks, category_rules, genre_mapping,
    # anime_rule — these are "used" IDs. If not in categories dict, default label applies.
    used_ids: set[str] = set()
    for disk in config.disks:
        used_ids.update(disk.categories)
    for rule in config.category_rules:
        used_ids.add(rule.category)
    for mapping in (
        config.genre_mapping.tmdb_movies,
        config.genre_mapping.tmdb_tv,
        config.genre_mapping.tvdb,
    ):
        used_ids.update(mapping.values())
    used_ids.add(config.genre_mapping.default_movies_category)
    used_ids.add(config.genre_mapping.default_tv_category)
    used_ids.add(config.anime_rule.maps_to)

    for cid in used_ids:
        if cid not in config.categories:
            warnings.append(f"using default label for '{cid}'")

    # Warning 3: disk path does not exist on filesystem
    for disk in config.disks:
        if not disk.path.exists():
            warnings.append(f"disk '{disk.id}' path '{disk.path}' not mounted/present")

    # Warning 4: legacy torrent host/port env vars still present in os.environ
    legacy_env = [name for name in _LEGACY_TORRENT_ENV_VARS if os.environ.get(name)]
    if legacy_env:
        warnings.append(
            f"legacy env vars ignored by api-unify code path: {', '.join(legacy_env)}. "
            "Remove from .env and configure host/port in config/torrent.json5 instead."
        )

    return warnings


def _check_category_orphans(config: Config) -> None:
    """Run the category-orphan startup check described in DESIGN §17.2.

    If ``library.db`` exists at the configured ``indexer.db_path``, this
    function queries ``SELECT DISTINCT category_id FROM media_item`` and
    compares the result against the union of declared category IDs in the
    loaded config.  Any IDs present in the database but absent from the config
    are *orphans* — most likely caused by a category rename in ``categories.json5``
    without a corresponding ``personalscraper config migrate-category`` run.

    The check is **warning-only**: the loader does not refuse to start.  The
    user must run ``personalscraper config migrate-category --from OLD --to NEW``
    to repair orphan references.

    Args:
        config: Validated Config instance containing ``indexer.db_path`` and
            ``all_category_ids``.
    """
    db_path = config.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved before calling _warn_orphan_categories"
    db_path = db_path.expanduser()
    if not db_path.is_absolute():
        # By the time we get here, IndexerConfig._reject_external_mount has
        # already resolved relative db_paths against the project root, so a
        # still-relative value indicates a downstream model edit. Falling
        # back to CWD here keeps the orphan-check non-blocking — a wrong
        # path simply results in "no DB → nothing to check" below, never a
        # crash on startup.
        log.warning(
            "indexer.config.unexpected_relative_db_path",
            db_path=str(db_path),
            hint="Resolved against CWD as fallback; orphan check may not run. "
            "This indicates an IndexerConfig constructed outside load_config_dir.",
        )
        db_path = Path.cwd() / db_path

    if not db_path.is_file():
        # No database yet — nothing to check.
        return

    try:
        # Deferred local import (non-blocking startup orphan-check). Intentional,
        # documented upward dependency on indexer/ — guarded against import cycles
        # by being function-local; pre-existing boundary, see arch-cleanup-2 Phase 2.
        from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415  # layering: allow

        conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
        _apply_pragmas(conn)
        try:
            cursor = conn.execute("SELECT DISTINCT category_id FROM media_item")
            db_category_ids: set[str] = {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()
    except sqlite3.Error as exc:
        # Non-blocking: a corrupt or locked DB at startup must not crash the
        # CLI.  Log at warning level and continue.
        log.warning(
            "indexer.config.category_orphan_check_failed",
            db_path=str(db_path),
            error=str(exc),
        )
        return

    known_ids = config.all_category_ids
    orphan_ids = db_category_ids - known_ids
    if orphan_ids:
        log.warning(
            "indexer.config.category_orphan",
            orphan_category_ids=sorted(orphan_ids),
            hint=(
                "Run `personalscraper config migrate-category --from OLD --to NEW` "
                "to remap orphan category references in the database."
            ),
        )
