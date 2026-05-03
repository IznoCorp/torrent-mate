"""JSON5 config loader with path resolution and validation warnings.

The project uses a v2 split-config layout: a directory (default
``./config/``) that contains a master ``config.json5`` plus a
set of per-concern overlay files (``paths.json5``, ``disks.json5``,
``indexer.json5`` …) listed in the master's ``overlays`` key.

Resolution order applied by :func:`resolve_config_path`:
  1. ``--config`` CLI override (highest priority)
  2. ``$PERSONALSCRAPER_CONFIG`` environment variable
  3. ``./config/`` if it contains a ``config.json5``
  4. Legacy ``./config.json5`` single-file fallback (deprecated, emits warning)

:func:`load_config` dispatches automatically on the resolved path: directory →
:func:`load_config_dir` (v2 split), file → legacy v1 monolithic loader.

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
import warnings
from pathlib import Path
from typing import Any

import json5

from personalscraper.conf.models import Config
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
    "collect_warnings",
]

_MASTER_FILENAME = "config.json5"
_LOCAL_FILENAME = "local.json5"

log = get_logger("personalscraper.conf.loader")

#: Preferred location for the v2 split-config directory.
DEFAULT_CONFIG_DIR: Path = Path("./config")
#: Legacy single-file path; resolved only when the v2 directory is absent.
DEFAULT_LEGACY_CONFIG_PATH: Path = Path("./config.json5")
#: Backwards-compatible alias kept for tests / callers that still import it.
DEFAULT_CONFIG_PATH: Path = DEFAULT_LEGACY_CONFIG_PATH
ENV_CONFIG_PATH: str = "PERSONALSCRAPER_CONFIG"


class ConfigNotFoundError(FileNotFoundError):
    """Raised when the config file does not exist at the resolved path."""


class ConfigValidationError(ValueError):
    """Raised when config file fails JSON5 parsing or Pydantic validation."""


def resolve_config_path(cli_override: Path | None = None) -> Path:
    """Resolve the active config location using CLI > env > v2 dir > legacy file.

    The returned path may point at either a directory (v2 split layout) or a
    single file (legacy v1 monolithic). :func:`load_config` dispatches on the
    file/dir distinction, so callers do not need to know which layout the user
    has installed.

    Args:
        cli_override: Path passed via --config CLI option. Takes highest priority.
            May point at a directory (split layout) or a single file (legacy).

    Returns:
        Resolved absolute path. Existence is verified by the loader, not here.
    """
    if cli_override is not None:
        return cli_override.expanduser().resolve()
    env = os.environ.get(ENV_CONFIG_PATH)
    if env:
        return Path(env).expanduser().resolve()
    # Prefer the v2 split layout when it carries a master config.json5.  This
    # makes the directory the default for fresh installs while letting an
    # existing legacy ``config.json5`` keep working until it is removed.
    candidate_dir = DEFAULT_CONFIG_DIR.expanduser().resolve()
    if (candidate_dir / _MASTER_FILENAME).is_file():
        return candidate_dir
    return DEFAULT_LEGACY_CONFIG_PATH.expanduser().resolve()


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


def load_config_dir(config_dir: Path) -> Config:
    """Load and merge a v2 split-config directory into a validated Config.

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
    master_path = config_dir / _MASTER_FILENAME
    if not master_path.is_file():
        raise ConfigNotFoundError(
            f"No config.json5 found in {config_dir}. "
            "Run 'personalscraper init-config' to create one from the example template."
        )

    master = _load_json5_file(master_path)

    # Collect overlay dicts in declared order.
    overlay_names: list[str] = master.pop("overlays", [])
    overlay_dicts: list[dict[str, Any]] = []
    for name in overlay_names:
        overlay_path = config_dir / name
        parsed = _load_json5_file(overlay_path)
        # Attach source sentinel so merge_overlays can identify local.json5.
        parsed["__source__"] = overlay_path
        overlay_dicts.append(parsed)

    # Optional local.json5 — missing is fine, not an error.
    local_path = config_dir / _LOCAL_FILENAME
    if local_path.is_file():
        local_dict = _load_json5_file(local_path)
        local_dict["__source__"] = local_path
        overlay_dicts.append(local_dict)

    # Merge: master is the base; overlays applied in order.
    merged = merge_overlays(master, *overlay_dicts)

    # Validate through pydantic.
    try:
        config = Config.model_validate(merged)
    except Exception as exc:
        raise ConfigValidationError(f"Validation error merging config in {config_dir}:\n{exc}") from exc

    # Emit non-blocking warnings — same as v1 loader.
    for warning in collect_warnings(config):
        log.warning(warning)

    # Non-blocking category-orphan startup check (DESIGN §17.2).
    _check_category_orphans(config)

    return config


def load_config(path: Path | None = None) -> Config:
    """Load and validate the project configuration, dispatching on layout.

    Behaviour by resolved-path type:

    * **Directory** → treated as a v2 split-config root and forwarded to
      :func:`load_config_dir`. The directory must contain a ``config.json5``
      master file declaring the overlay list.
    * **File** → treated as the legacy v1 monolithic ``config.json5`` and
      parsed in-place. A ``DeprecationWarning`` is emitted so the user sees
      the migration instruction; the value is still loaded successfully.

    Emits non-blocking warnings via :func:`collect_warnings` after successful
    validation. The config is returned regardless of warnings.

    Args:
        path: Explicit path to a config file or split-config directory. If
            ``None``, :func:`resolve_config_path` is called to determine
            which layout is active.

    Returns:
        Validated :class:`~personalscraper.conf.models.Config` instance.

    Raises:
        ConfigNotFoundError: If neither a file nor a directory exists at the
            resolved path.
        ConfigValidationError: If JSON5 parsing or Pydantic validation fails.
    """
    resolved = path if path is not None else resolve_config_path()

    # v2 split layout: dispatch to the directory loader.  This is the default
    # path for fresh installs (DEFAULT_CONFIG_DIR) and any caller passing the
    # directory explicitly.
    if resolved.is_dir():
        return load_config_dir(resolved)

    if not resolved.is_file():
        raise ConfigNotFoundError(
            f"No config file or split-config directory at {resolved}. "
            "Run 'personalscraper init-config' to create one from the example template."
        )

    # v1 single-file config is deprecated in favour of the v2 split-directory layout.
    # Emit a DeprecationWarning so users see the migration instruction at call site.
    warnings.warn(
        "v1 single-file config is deprecated and will be removed in 0.10.0; run "
        "`personalscraper config migrate-to-v2 <legacy-path> <target-dir>` to migrate",
        DeprecationWarning,
        stacklevel=2,
    )
    log.warning("config_v1_deprecated", path=str(resolved), removal_version="0.10.0")

    with resolved.open("r", encoding="utf-8") as f:
        try:
            raw = json5.load(f)
        except Exception as exc:
            raise ConfigValidationError(f"JSON5 parse error in {resolved}: {exc}") from exc
    try:
        config = Config.model_validate(raw)
    except Exception as exc:
        raise ConfigValidationError(f"Validation error in {resolved}:\n{exc}") from exc

    # Emit non-blocking warnings — do not raise, just log.
    # The warning text is used as the event so stdlib caplog records carry it.
    for warning in collect_warnings(config):
        log.warning(warning)

    # Non-blocking category-orphan startup check (DESIGN §17.2).
    _check_category_orphans(config)

    return config


def collect_warnings(config: Config) -> list[str]:
    """Collect non-fatal configuration warnings.

    Three warning types (acceptance criterion #12):
    1. A custom_category ID has no disk accepting it -> likely dead config.
    2. A category ID is referenced by disks/rules/mappings but not in
       ``config.categories`` -> default label will be used.
    3. A disk path does not exist on the filesystem -> disk unmounted.

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
    db_path = config.indexer.db_path.expanduser()
    if not db_path.is_absolute():
        # Relative paths are resolved against CWD at call time — same as the
        # rest of the project's path handling.
        db_path = Path.cwd() / db_path

    if not db_path.is_file():
        # No database yet — nothing to check.
        return

    try:
        conn = sqlite3.connect(str(db_path))
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
