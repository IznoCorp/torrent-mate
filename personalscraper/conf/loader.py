"""JSON5 config loader with path resolution and validation warnings.

Resolution order for the v1 (single-file) loader:
  CLI override > $PERSONALSCRAPER_CONFIG > ./config.json5

Resolution order for the v2 (multi-file) loader:
  1. <config_dir>/config.json5   — master, declares overlay list
  2. Each file named in the master ``overlays`` key, in order
  3. Optional <config_dir>/local.json5 — gitignored, last-wins machine overrides

Warnings are non-blocking: they are logged but do not prevent the config from
loading.
"""

import os
from pathlib import Path

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

DEFAULT_CONFIG_PATH: Path = Path("./config.json5")
ENV_CONFIG_PATH: str = "PERSONALSCRAPER_CONFIG"


class ConfigNotFoundError(FileNotFoundError):
    """Raised when the config file does not exist at the resolved path."""


class ConfigValidationError(ValueError):
    """Raised when config file fails JSON5 parsing or Pydantic validation."""


def resolve_config_path(cli_override: Path | None = None) -> Path:
    """Resolve the config file path using CLI > env > default precedence.

    Args:
        cli_override: Path passed via --config CLI option. Takes highest priority.

    Returns:
        Resolved absolute Path to the config file.
    """
    if cli_override is not None:
        return cli_override.expanduser().resolve()
    env = os.environ.get(ENV_CONFIG_PATH)
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_CONFIG_PATH.expanduser().resolve()


def _load_json5_file(path: Path) -> dict:
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
            return dict(json5.load(fh))  # type: ignore[arg-type]
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
    overlay_names: list[str] = master.pop("overlays", [])  # type: ignore[assignment]
    overlay_dicts: list[dict] = []
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

    return config


def load_config(path: Path | None = None) -> Config:
    """Load and validate config.json5 from the given path.

    Emits non-blocking warnings via ``collect_warnings`` after successful
    validation. The config is returned regardless of warnings.

    Args:
        path: Explicit path to config file. If None, ``resolve_config_path()``
            is called to determine the path.

    Returns:
        Validated Config instance.

    Raises:
        ConfigNotFoundError: If the file does not exist.
        ConfigValidationError: If JSON5 parsing or Pydantic validation fails.
    """
    resolved = path if path is not None else resolve_config_path()
    if not resolved.is_file():
        raise ConfigNotFoundError(
            f"No config file at {resolved}. Run 'personalscraper init-config' to create one from the example template."
        )
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
