"""V14 → V15 migration utilities.

Three migration paths (Phase 4 will implement the functions):
1. ``.env`` DISK*_DIR + ``disk_scanner.DISK_CATEGORIES`` → config.json5
   (via ``init-config --from-current``).
2. ``library_*.json`` files on disk: rewrite V14 label strings ("films" → "movies")
   to V15 IDs.
3. ``.category`` files in media dirs → ``<category>`` element in corresponding NFO
   + delete ``.category``.
"""

from pathlib import Path

# Mapping V14 French label → V15 category ID.
# Derived from the maintainer's current V14 config (DISK_CATEGORIES in disk_scanner.py).
# Used by Phase 2 classifier equivalence tests and Phase 4 migration functions.
# NB: "spectacles" maps to "standup" (not "concerts") — V14 "spectacles" = stand-up / one-man-show.
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


def generate_config_from_env(env_values: dict[str, str]) -> dict:  # type: ignore[type-arg]
    """Build a config.json5-compatible dict from V14 .env variables.

    Reads DISK1_DIR..DISK4_DIR, STAGING_DIR, TORRENT_COMPLETE_DIR.
    Reuses V14 DISK_CATEGORIES mapping (fetched just-in-time since this
    is migration code — V14 structure is known).

    Args:
        env_values: Dict of V14 environment variable names → values.

    Returns:
        A dict suitable for serializing as config.json5.
    """
    raise NotImplementedError("Phase 4 will implement generate_config_from_env")


def migrate_library_json(file_path: Path, backup_suffix: str = ".v14.bak") -> None:
    """Rewrite V14 label strings to V15 IDs in a library JSON file.

    Reads the JSON file, replaces known V14 label strings with their V15 ID
    equivalents in known fields, creates a backup, then writes back.

    Args:
        file_path: Path to the library JSON file to migrate.
        backup_suffix: Suffix appended to the original path for the backup copy.

    Raises:
        NotImplementedError: Until Phase 4 implements this function.
    """
    raise NotImplementedError("Phase 4 will implement migrate_library_json")


def migrate_category_files(staging_root: Path) -> int:
    """Walk staging_root and migrate V14 ``.category`` files to NFO ``<category>`` elements.

    For each ``.category`` file found: read the V14 label, map to V15 ID via
    ``V14_LABEL_TO_ID``, insert ``<category source="personalscraper">{ID}</category>``
    in the sibling NFO, then delete the ``.category`` file.

    Args:
        staging_root: Root directory to search recursively for ``.category`` files.

    Returns:
        Count of successfully migrated ``.category`` files.

    Raises:
        NotImplementedError: Until Phase 4 implements this function.
    """
    raise NotImplementedError("Phase 4 will implement migrate_category_files")
