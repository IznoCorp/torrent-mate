"""V14 → V15 migration utilities.

Three migration paths:
1. ``.env`` DISK*_DIR + V14 ``DISK_CATEGORIES`` → config.json5
   (via ``init-config --from-current``).
2. ``library_*.json`` files on disk: rewrite V14 label strings ("films" → "movies")
   to V15 IDs.
3. ``.category`` files in media dirs → ``<category>`` element in corresponding NFO
   + delete ``.category``.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# V14 label → V15 category ID mapping.
# Derived from the maintainer's V14 config (DISK_CATEGORIES in disk_scanner.py).
# "spectacles" maps to "standup" (V14 "spectacles" = stand-up / one-man-show).
# ---------------------------------------------------------------------------
V14_LABEL_TO_ID: dict[str, str] = {
    "films": "movies",
    "films animations": "movies_animation",
    "films documentaires": "movies_documentary",
    "series": "tv_shows",
    "series animations": "tv_shows_animation",
    "series documentaires": "tv_shows_documentary",
    "series animes": "anime",
    "spectacles": "standup",
    "theatres": "theater",
    "emissions": "tv_programs",
    "livres audios": "audiobooks",
}

# ---------------------------------------------------------------------------
# V14 known categories (inlined from genre_mapper.KNOWN_CATEGORIES).
# Phase 7 will delete genre_mapper.py; migration.py must be independent.
# ---------------------------------------------------------------------------
V14_KNOWN_CATEGORIES: frozenset[str] = frozenset(
    {
        "films",
        "films animations",
        "films documentaires",
        "spectacles",
        "theatres",
        "series",
        "series animations",
        "series documentaires",
        "series animes",
        "emissions",
        "livres audios",
    }
)

# ---------------------------------------------------------------------------
# V14 TMDB movie genre IDs → V15 category IDs.
# Inlined from GenreMapper (TMDB_ANIMATION=16, TMDB_DOCUMENTARY=99).
# ---------------------------------------------------------------------------
V14_TMDB_MOVIE_GENRE_MAP: dict[int, str] = {
    16: "movies_animation",  # Animation
    99: "movies_documentary",  # Documentary
}

# ---------------------------------------------------------------------------
# V14 TMDB TV genre IDs → V15 category IDs.
# Inlined from GenreMapper (TV_ANIMATION=16, DOCUMENTARY=99,
# REALITY=10764, TALK=10767, NEWS=10763).
# ---------------------------------------------------------------------------
V14_TMDB_TV_GENRE_MAP: dict[int, str] = {
    16: "tv_shows_animation",  # Animation (anime_rule fires first for JP origin)
    99: "tv_shows_documentary",  # Documentary
    10764: "tv_programs",  # Reality
    10767: "tv_programs",  # Talk
    10763: "tv_programs",  # News
}

# ---------------------------------------------------------------------------
# V14 TVDB genre IDs → V15 category IDs.
# Inlined from GenreMapper (ANIME=27, ANIMATION=17, DOCUMENTARY=3,
# REALITY=8, TALK_SHOW=10, NEWS=11).
# ---------------------------------------------------------------------------
V14_TVDB_GENRE_MAP: dict[int, str] = {
    27: "anime",  # Anime (dedicated TVDB genre)
    17: "tv_shows_animation",  # Animation
    3: "tv_shows_documentary",  # Documentary
    8: "tv_programs",  # Reality
    10: "tv_programs",  # Talk Show
    11: "tv_programs",  # News
}

# ---------------------------------------------------------------------------
# V14 disk → category labels mapping (inlined from disk_scanner.DISK_CATEGORIES).
# Phase 6 will remove DISK_CATEGORIES from disk_scanner.py; migration.py
# must remain independent.
# ---------------------------------------------------------------------------
_V14_DISK_CATEGORIES: dict[str, list[str]] = {
    "Disk1": [
        "films",
        "films animations",
        "films documentaires",
        "livres audios",
        "series",
        "series animations",
        "series documentaires",
        "spectacles",
        "theatres",
        "emissions",
    ],
    "Disk2": ["series", "series animes"],
    "Disk3": [
        "films",
        "films animations",
        "films documentaires",
        "livres audios",
        "series",
        "series animations",
        "series documentaires",
        "spectacles",
        "theatres",
        "emissions",
    ],
    "Disk4": [
        "films",
        "films animations",
        "series",
        "series animations",
        "series documentaires",
        "emissions",
    ],
}

# ---------------------------------------------------------------------------
# Known library JSON filenames and their field paths containing V14 labels.
# Used by migrate_library_json to know which fields to rewrite.
# ---------------------------------------------------------------------------
_LIBRARY_JSON_FIELD_PATHS: dict[str, list[str]] = {
    "library_index.json": ["items[].category"],
    "library_analysis.json": ["items[].category"],
    "library_rescrape.json": ["items[].category"],
    "library_recommendations.json": ["items[].category"],
    "library_validation.json": ["items[].category"],
}


def generate_config_from_env(
    env_values: dict[str, str],
    library_prefs_path: Path | None = None,
) -> dict[str, Any]:
    """Build a config.json5-compatible dict from V14 .env variables.

    Parses ``DISK1_DIR``..``DISK4_DIR``, ``STAGING_DIR``,
    ``TORRENT_COMPLETE_DIR`` from *env_values*.  Inlines the V14
    ``DISK_CATEGORIES`` mapping to produce V15-compatible disk entries.
    Pre-fills ``genre_mapping`` with V14 TMDB/TVDB genre ID tables.

    Args:
        env_values: Dict of V14 environment variable names to values.
        library_prefs_path: Optional path to ``library_preferences.json``.
            When provided, the file is parsed and merged into
            ``result["library"]``.

    Returns:
        A dict ready for ``Config.model_validate(...)`` acceptance.

    Raises:
        ValueError: If a required path variable (TORRENT_COMPLETE_DIR or
            STAGING_DIR) is absent and cannot be defaulted.
    """
    torrent_dir = env_values.get("TORRENT_COMPLETE_DIR", "")
    staging_dir = env_values.get("STAGING_DIR", "")

    # Build disks list from DISK{N}_DIR env vars.
    disks: list[dict[str, Any]] = []
    for n in range(1, 5):
        disk_path = env_values.get(f"DISK{n}_DIR", "").strip()
        if not disk_path:
            continue
        disk_key = f"Disk{n}"
        v14_labels = _V14_DISK_CATEGORIES.get(disk_key, [])
        # Map each V14 label to its V15 ID; skip unknown labels with a warning.
        v15_ids: list[str] = []
        seen: set[str] = set()
        for label in v14_labels:
            cid = V14_LABEL_TO_ID.get(label)
            if cid is None:
                logger.warning("Unknown V14 label '%s' for %s — skipping", label, disk_key)
                continue
            if cid not in seen:
                v15_ids.append(cid)
                seen.add(cid)
        disks.append(
            {
                "id": f"disk_{n}",
                "path": disk_path,
                "categories": v15_ids,
            }
        )

    # Build categories dict: each V15 ID → folder_name = V14 French label.
    # This preserves the existing folder names on disk (no rename needed).
    categories: dict[str, dict[str, Any]] = {}
    for label, cid in V14_LABEL_TO_ID.items():
        if cid not in categories:
            categories[cid] = {"folder_name": label}

    # Build genre_mapping from inlined V14 tables.
    genre_mapping: dict[str, Any] = {
        "tmdb_movies": {str(k): v for k, v in V14_TMDB_MOVIE_GENRE_MAP.items()},
        "tmdb_tv": {str(k): v for k, v in V14_TMDB_TV_GENRE_MAP.items()},
        "tvdb": {str(k): v for k, v in V14_TVDB_GENRE_MAP.items()},
        "default_movies_category": "movies",
        "default_tv_category": "tv_shows",
    }

    # Anime rule mirrors V14 behavior: Animation genre (16) + JP origin → anime.
    anime_rule: dict[str, Any] = {
        "enabled": True,
        "requires_genre_id": 16,
        "requires_origin_country": ["JP"],
        "maps_to": "anime",
        "applies_to": "tv",
    }

    # data_dir: V15 default is <staging>/.data (absolute, avoids CWD dependency).
    data_dir = str(Path(staging_dir) / ".data") if staging_dir else "./.data"

    result: dict[str, Any] = {
        "config_version": 1,
        "paths": {
            "torrent_complete_dir": torrent_dir,
            "staging_dir": staging_dir,
            "data_dir": data_dir,
        },
        "disks": disks,
        "custom_categories": [],
        "categories": categories,
        "category_rules": [],
        "anime_rule": anime_rule,
        "genre_mapping": genre_mapping,
        "library": {},
    }

    # Optionally merge library preferences.
    if library_prefs_path is not None and library_prefs_path.is_file():
        result["library"] = migrate_library_preferences(library_prefs_path)

    return result


def migrate_library_preferences(prefs_path: Path) -> dict[str, Any]:
    """Migrate V14 ``library_preferences.json`` → V15 ``LibraryPrefs`` dict.

    Reads the V14 JSON file (raw, without importing V14 Pydantic models) and
    maps it to the V15 ``LibraryPrefs`` schema.  The mapping is direct because
    V14 ``LibraryPreferences`` and V15 ``LibraryPrefs`` share identical field
    names; only the class names differ.

    After a successful parse the original file is NOT deleted here — the
    caller (``init_config``) is responsible for backup/delete lifecycle.

    Args:
        prefs_path: Path to ``library_preferences.json``.

    Returns:
        Dict suitable for ``LibraryPrefs.model_validate(...)`` and injectable
        as ``config["library"]`` in the result of ``generate_config_from_env``.

    Raises:
        ValueError: If the JSON cannot be parsed or is structurally invalid.
    """
    try:
        raw = json.loads(prefs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read library preferences from {prefs_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Expected a JSON object in {prefs_path}, got {type(raw).__name__}")

    # V14 → V15 field mapping is direct (same field names, different class names).
    # Build each sub-section defensively so missing sub-keys fall back to defaults.
    result: dict[str, Any] = {}

    for section in ("video", "audio", "subtitles"):
        if section in raw and isinstance(raw[section], dict):
            result[section] = raw[section]

    if "encoding_rules" in raw and isinstance(raw["encoding_rules"], list):
        result["encoding_rules"] = raw["encoding_rules"]

    return result


def migrate_library_json(file_path: Path, backup_suffix: str = ".v14.bak") -> None:
    """Rewrite V14 label strings to V15 IDs in a library JSON file.

    Reads the JSON file, replaces known V14 label strings with their V15 ID
    equivalents in ``items[].category`` fields, creates a backup with
    *backup_suffix*, then writes the modified content back.

    Skips files whose backup already exists (to avoid overwriting a manual
    backup).  Unknown labels are left in place with a WARN log.

    The function is a no-op on ``library_preferences.json`` — that file is
    handled by ``migrate_library_preferences``.

    Args:
        file_path: Path to the library JSON file to migrate.
        backup_suffix: Suffix appended to the original path for the backup.

    Raises:
        FileExistsError: If the backup file already exists.
        ValueError: If the file cannot be parsed as JSON.
    """
    if file_path.name == "library_preferences.json":
        logger.debug("Skipping library_preferences.json — handled by migrate_library_preferences")
        return

    backup_path = file_path.with_suffix(file_path.suffix + backup_suffix)
    if backup_path.exists():
        raise FileExistsError(
            f"Backup already exists: {backup_path}. "
            "Remove it manually before re-running migration."
        )

    try:
        raw_text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cannot read {file_path}: {exc}") from exc

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("Cannot parse JSON in %s (skipping): %s", file_path, exc)
        return

    if not isinstance(data, dict):
        logger.warning("Unexpected JSON structure in %s (not an object, skipping)", file_path)
        return

    modified = _rewrite_labels_in_items(data, file_path.name)

    # Write backup first, then overwrite original.
    backup_path.write_text(raw_text, encoding="utf-8")
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "Migrated %s → %d items rewritten (backup: %s)",
        file_path.name,
        modified,
        backup_path.name,
    )


def _rewrite_labels_in_items(data: dict[str, Any], filename: str) -> int:
    """Rewrite V14 labels in ``items[].category`` in place.

    Mutates *data* directly.  Returns the count of items whose ``category``
    field was rewritten.

    Args:
        data: Parsed JSON dict (top-level object from a library JSON file).
        filename: Filename for log messages only.

    Returns:
        Number of ``category`` fields rewritten.
    """
    items = data.get("items")
    if not isinstance(items, list):
        return 0

    modified = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        label = item.get("category")
        if not isinstance(label, str):
            continue
        cid = V14_LABEL_TO_ID.get(label)
        if cid is None:
            logger.warning(
                "%s: Unknown V14 label '%s' in items[].category — left as-is",
                filename,
                label,
            )
            continue
        item["category"] = cid
        modified += 1

    return modified


def migrate_category_files(staging_root: Path, data_dir: Path | None = None) -> int:
    """Walk staging_root and migrate V14 ``.category`` files to NFO ``<category>`` elements.

    For each ``.category`` file found:

    - Reads the V14 label, maps to V15 ID via ``V14_LABEL_TO_ID``.
    - Finds the sibling NFO (``movie.nfo`` or ``tvshow.nfo``).
    - Inserts ``<category source="personalscraper">{ID}</category>`` after any
      ``<genre>`` elements (or at end of root element).
    - Writes the updated NFO and deletes the ``.category`` file.

    Skips (with WARN) if:

    - Label is unknown.
    - No NFO sibling is present.
    - NFO already has a ``<category source="personalscraper">`` element
      (idempotent).

    Refuses to run if a lock file is present at
    ``data_dir / "lock.json"`` (pipeline running).

    Args:
        staging_root: Root directory to search recursively for ``.category``
            files.
        data_dir: Optional data directory to check for a lock file.
            Defaults to ``staging_root / ".personalscraper"`` (V14 location)
            if not provided.

    Returns:
        Count of successfully migrated ``.category`` files.

    Raises:
        RuntimeError: If a pipeline lock file is detected.
    """
    # Default lock dir to V14 location if not provided.
    effective_data_dir = data_dir if data_dir is not None else staging_root / ".personalscraper"
    lock_file = effective_data_dir / "lock.json"
    if lock_file.exists():
        raise RuntimeError(
            f"Pipeline lock file detected at {lock_file}. "
            "Stop the pipeline before running migration."
        )

    migrated = 0
    for category_file in sorted(staging_root.rglob(".category")):
        label = category_file.read_text(encoding="utf-8").strip().lower()
        cid = V14_LABEL_TO_ID.get(label)
        if cid is None:
            logger.warning(
                "Unknown V14 label '%s' in %s — leaving .category in place",
                label,
                category_file,
            )
            continue

        parent = category_file.parent
        nfo_path = _find_nfo_sibling(parent)
        if nfo_path is None:
            logger.warning(
                "No NFO sibling for %s — leaving .category in place",
                category_file,
            )
            continue

        inserted = _insert_category_in_nfo(nfo_path, cid)
        if inserted is None:
            # Already present (idempotent) or parse error — skip.
            continue

        category_file.unlink()
        migrated += 1
        logger.info("Migrated %s → NFO <category>%s</category>", category_file, cid)

    return migrated


def _find_nfo_sibling(directory: Path) -> Path | None:
    """Return the first NFO file in *directory* (movie.nfo or tvshow.nfo).

    Checks ``movie.nfo`` first, then ``tvshow.nfo``, then any ``*.nfo`` file.

    Args:
        directory: Directory to search for an NFO file.

    Returns:
        Path to the NFO file, or None if not found.
    """
    for name in ("movie.nfo", "tvshow.nfo"):
        candidate = directory / name
        if candidate.is_file():
            return candidate
    # Fallback: any .nfo file in the directory.
    nfo_files = list(directory.glob("*.nfo"))
    return nfo_files[0] if nfo_files else None


def _insert_category_in_nfo(nfo_path: Path, category_id: str) -> bool | None:
    """Insert ``<category source="personalscraper">`` into an NFO file.

    Skips (returns None) if the element already exists or the NFO is unparseable.
    Returns True on successful write.

    Args:
        nfo_path: Path to the NFO file.
        category_id: V15 category ID to write.

    Returns:
        True if the NFO was updated, None if skipped (already present or error).
    """
    try:
        tree = ET.parse(nfo_path)  # noqa: S314
        root = tree.getroot()
    except (ET.ParseError, OSError) as exc:
        logger.warning("Cannot parse NFO %s: %s — skipping", nfo_path, exc)
        return None

    # Idempotency check: skip if element with source="personalscraper" already exists.
    for el in root.iter("category"):
        if el.get("source") == "personalscraper":
            logger.debug("NFO %s already has <category source=personalscraper> — skipping", nfo_path)
            return None

    # Build new element.
    new_el = ET.Element("category")
    new_el.set("source", "personalscraper")
    new_el.text = category_id

    # Insert after last <genre> element, or append at end of root.
    genre_indices = [i for i, child in enumerate(root) if child.tag == "genre"]
    if genre_indices:
        insert_pos = genre_indices[-1] + 1
        root.insert(insert_pos, new_el)
    else:
        root.append(new_el)

    # Preserve XML declaration if present and write back.
    ET.indent(root, space="  ")
    tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
    return True


def migrate_data_dir(staging_dir: Path) -> Path:
    """Move V14 ``.personalscraper/`` to V15 ``.data/`` atomically.

    Uses ``os.rename`` for an atomic same-filesystem move.  Falls back to
    ``shutil.move`` on ``OSError`` with errno ``EXDEV`` (cross-device), but
    callers should be aware that cross-filesystem moves are not atomic.

    Args:
        staging_dir: The staging directory that contains ``.personalscraper/``.

    Returns:
        Absolute path of the new ``.data/`` directory.

    Raises:
        RuntimeError: If the source does not exist, a lock file is present,
            the target already exists, or the source and staging dir are on
            different filesystems.
        FileNotFoundError: If ``.personalscraper/`` does not exist.
    """
    source = staging_dir / ".personalscraper"
    target = staging_dir / ".data"

    if not source.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source}")

    # Lock file check: refuse if pipeline is running.
    lock_file = source / "lock.json"
    if lock_file.exists():
        raise RuntimeError(
            f"Pipeline lock file detected at {lock_file}. "
            "Stop the pipeline before running migration."
        )

    if target.exists():
        raise FileExistsError(
            f"Target already exists: {target}. "
            "Remove it manually before running migration."
        )

    # Same-filesystem check to detect cross-mount scenarios early.
    source_dev = os.stat(source).st_dev
    staging_dev = os.stat(staging_dir).st_dev
    if source_dev != staging_dev:
        raise RuntimeError(
            f"Source ({source}) and staging dir ({staging_dir}) are on different "
            "filesystems. Manual move required."
        )

    try:
        os.rename(source, target)
    except OSError as exc:
        import errno

        if exc.errno == errno.EXDEV:
            # Cross-device link error despite same st_dev — unusual but handle gracefully.
            shutil.move(str(source), str(target))
        else:
            raise

    return target.resolve()
