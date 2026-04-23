"""JSON5 config loader with path resolution and validation warnings.

Resolution order for config path: CLI override > $PERSONALSCRAPER_CONFIG > ./config.json5.
Warnings are non-blocking: they are logged but do not prevent config from loading.
"""

import os
from pathlib import Path

import json5

from personalscraper.conf.models import Config
from personalscraper.logger import get_logger

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
    1. A custom_category ID has no disk accepting it → likely dead config.
    2. A category ID is referenced by disks/rules/mappings but not in
       ``config.categories`` → default label will be used.
    3. A disk path does not exist on the filesystem → disk unmounted.

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
