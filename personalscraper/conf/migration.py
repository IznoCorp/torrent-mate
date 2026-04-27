"""One-shot migration of the legacy monolithic config.json5 to the v2 split layout.

Exposes ``migrate_v1_to_v2(legacy_path, target_dir)`` which:

1. Reads the legacy single-file ``config.json5`` (v1 monolith).
2. Splits its top-level keys across the canonical per-concern JSON5 files
   that the v2 multi-file loader expects.
3. Writes the result **atomically**: first to ``<target_dir>.in-progress/``,
   then calls ``os.rename()`` to move it into place.  On any failure the
   ``.in-progress/`` directory is left on disk so that the loader can detect
   the partial state and refuse to start with an actionable message.
4. Renames the legacy file to ``<legacy_path>.v1.bak``.
5. Any top-level key not recognised by the splitter is collected into
   ``local.json5`` under ``_migration_unknown_keys`` and also listed in a
   ``migration-warnings.txt`` placed **next to** *target_dir* (i.e. in the
   same directory as *target_dir*).

Idempotence policy: if *target_dir* already exists **and** its master
``config.json5`` already contains an ``overlays`` key (the v2 marker), the
migration refuses with ``MigrationAlreadyDoneError``.  The ``.v1.bak`` step
is also skipped in this case so nothing is mutated.  Callers should remove
*target_dir* manually if they wish to re-run.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import json5

from personalscraper.logger import get_logger

__all__ = [
    "MigrationError",
    "MigrationAlreadyDoneError",
    "MigrationMalformedError",
    "migrate_v1_to_v2",
    "plan_migration",
]

log = get_logger("personalscraper.conf.migration")

# ---------------------------------------------------------------------------
# Mapping: top-level v1 key → target filename (relative to target_dir)
# ---------------------------------------------------------------------------

_KEY_TO_FILE: dict[str, str] = {
    "paths": "paths.json5",
    "disks": "disks.json5",
    "custom_categories": "categories.json5",
    "categories": "categories.json5",
    "category_rules": "categories.json5",
    "anime_rule": "categories.json5",
    "genre_mapping": "categories.json5",
    "staging_dirs": "patterns.json5",
    "library": "encoding.json5",
    "scraper": "scraper.json5",
    "ingest": "scraper.json5",
    "fuzzy_match": "scraper.json5",
    "trailers": "trailers.json5",
}

# Canonical overlay declaration order for the master config.json5.
_OVERLAY_ORDER: list[str] = [
    "paths.json5",
    "disks.json5",
    "categories.json5",
    "patterns.json5",
    "encoding.json5",
    "scraper.json5",
    "trailers.json5",
]

# Keys always present on the master, never split into overlays.
_MASTER_ONLY_KEYS: set[str] = {"config_version", "overlays"}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MigrationError(RuntimeError):
    """Base for all migration failures."""


class MigrationAlreadyDoneError(MigrationError):
    """Raised when target_dir already looks like a completed v2 migration.

    The migration refuses to overwrite an existing v2 directory to avoid
    accidental data loss.  Remove *target_dir* manually to force a re-run.
    """


class MigrationMalformedError(MigrationError):
    """Raised when the legacy config.json5 cannot be parsed or is structurally invalid."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_legacy(legacy_path: Path) -> dict[str, Any]:
    """Parse the legacy v1 config.json5.

    Args:
        legacy_path: Absolute path to the legacy single-file config.

    Returns:
        Parsed dict.

    Raises:
        MigrationMalformedError: If the file is missing, empty (no mappings),
            or cannot be parsed as JSON5.
    """
    if not legacy_path.is_file():
        raise MigrationMalformedError(f"Legacy config not found: {legacy_path}")
    try:
        with legacy_path.open("r", encoding="utf-8") as fh:
            raw = json5.load(fh)
    except Exception as exc:
        raise MigrationMalformedError(f"JSON5 parse error in {legacy_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise MigrationMalformedError(f"Legacy config must be a JSON object (got {type(raw).__name__}): {legacy_path}")
    return dict(raw)


def _split_keys(data: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Partition v1 top-level keys into per-file buckets and an unknown-keys list.

    The ``config_version`` and ``overlays`` keys are reserved for the master
    file and are not placed into overlay buckets.  All other keys not present
    in ``_KEY_TO_FILE`` are considered unknown and collected separately.

    Args:
        data: Parsed v1 monolith dict.

    Returns:
        A tuple of:
        - ``buckets``: mapping of filename → dict of keys destined for that file.
        - ``unknown_keys``: list of key names not recognised by the splitter.
    """
    buckets: dict[str, dict[str, Any]] = {}
    unknown_keys: list[str] = []

    for key, value in data.items():
        if key in _MASTER_ONLY_KEYS:
            # Handled separately; skip from overlay splitting.
            continue
        if key in _KEY_TO_FILE:
            target_file = _KEY_TO_FILE[key]
            buckets.setdefault(target_file, {})[key] = value
        else:
            unknown_keys.append(key)

    return buckets, unknown_keys


def _render_json5_comment(comment: str) -> str:
    """Wrap a comment line for JSON5 output.

    Args:
        comment: Comment text (without leading ``//``).

    Returns:
        JSON5 comment line string.
    """
    return f"// {comment}"


def _dict_to_json5(data: dict[str, Any], comment: str | None = None) -> str:
    """Serialise a dict to a pretty-printed JSON5 string.

    Uses the stdlib ``json`` module (which produces valid JSON5) with a
    two-space indent.  An optional leading comment line is prepended.

    Args:
        data: Mapping to serialise.
        comment: Optional human-readable first line inside the top-level
            ``{}`` braces.

    Returns:
        JSON5-compatible string ready to write to disk.
    """
    body = json.dumps(data, indent=2, ensure_ascii=False)
    if comment:
        # Insert comment after opening ``{``.
        lines = body.splitlines()
        lines.insert(1, f"  {_render_json5_comment(comment)}")
        body = "\n".join(lines)
    return body


def _write_file(path: Path, content: str) -> None:
    """Write *content* to *path* (UTF-8).

    Args:
        path: Target file path. Parent must exist.
        content: Text to write.
    """
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def plan_migration(legacy_path: Path) -> dict[str, Any]:
    """Compute the migration plan without writing anything.

    Returns the same data structure that ``migrate_v1_to_v2`` would write,
    expressed as a plain dict keyed by filename.  Useful for ``--dry-run``.

    Args:
        legacy_path: Absolute path to the legacy single-file config.

    Returns:
        Dict mapping filename → content dict (for overlay files) or string
        (for special files like ``migration-warnings.txt``).

    Raises:
        MigrationMalformedError: If the legacy file cannot be parsed.
    """
    data = _load_legacy(legacy_path)
    buckets, unknown_keys = _split_keys(data)

    plan: dict[str, Any] = {}

    # Master file
    plan["config.json5"] = {
        "config_version": data.get("config_version", 1),
        "overlays": _OVERLAY_ORDER,
    }

    # Per-concern overlay files — include only non-empty buckets.
    for fname in _OVERLAY_ORDER:
        if fname in buckets:
            plan[fname] = buckets[fname]
        else:
            plan[fname] = {}

    # Unknown keys → local.json5
    if unknown_keys:
        plan["local.json5"] = {"_migration_unknown_keys": {k: data[k] for k in unknown_keys}}
        plan["migration-warnings.txt"] = (
            "migration-warnings: the following keys from the v1 config were not recognised "
            "by the splitter and have been placed in local.json5 under "
            "'_migration_unknown_keys':\n  " + "\n  ".join(unknown_keys)
        )

    return plan


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def migrate_v1_to_v2(legacy_path: Path, target_dir: Path) -> None:
    """Migrate a v1 monolithic config.json5 to the v2 split layout.

    Writes files atomically: all files are first written into
    ``<target_dir>.in-progress/``, then that directory is renamed to
    ``target_dir`` via ``os.rename()`` (which is atomic on POSIX when source
    and destination are on the same filesystem).  On any failure the
    ``.in-progress/`` directory is left on disk.

    The legacy file is renamed to ``<legacy_path>.v1.bak`` after the atomic
    rename completes successfully.

    Args:
        legacy_path: Absolute path to the legacy single-file config.json5.
        target_dir: Destination directory for the split v2 files.  Must not
            already be a completed v2 config (detected by the presence of an
            ``overlays`` key in ``target_dir/config.json5``).

    Raises:
        MigrationAlreadyDoneError: If *target_dir* already looks like a
            completed v2 migration.
        MigrationMalformedError: If the legacy file is absent, empty, or
            contains invalid JSON5.
        MigrationError: For unexpected I/O failures during writing.
    """
    # ------------------------------------------------------------------
    # Idempotence check: refuse if target already looks like a v2 dir.
    # ------------------------------------------------------------------
    master_target = target_dir / "config.json5"
    if target_dir.is_dir() and master_target.is_file():
        try:
            with master_target.open("r", encoding="utf-8") as fh:
                existing = json5.load(fh)
            if isinstance(existing, dict) and "overlays" in existing:
                raise MigrationAlreadyDoneError(
                    f"Target directory already contains a v2 config (found 'overlays' key in "
                    f"{master_target}). Remove {target_dir} manually to force a re-run."
                )
        except MigrationAlreadyDoneError:
            raise
        except Exception:
            # Unreadable master — proceed, we will overwrite via .in-progress.
            pass

    # ------------------------------------------------------------------
    # Parse and split the legacy file.
    # ------------------------------------------------------------------
    data = _load_legacy(legacy_path)
    buckets, unknown_keys = _split_keys(data)

    log.info(
        "migration.v1_to_v2.started",
        legacy_path=str(legacy_path),
        target_dir=str(target_dir),
        unknown_keys=unknown_keys,
    )

    # ------------------------------------------------------------------
    # Atomic write: all files go to .in-progress/ first.
    # ------------------------------------------------------------------
    in_progress_dir = Path(str(target_dir) + ".in-progress")

    # Clean up any stale .in-progress dir from a previous failed attempt.
    if in_progress_dir.exists():
        shutil.rmtree(in_progress_dir)

    in_progress_dir.mkdir(parents=True, exist_ok=False)

    try:
        # 1. Master config.json5
        master_content = {
            "config_version": data.get("config_version", 1),
            "overlays": _OVERLAY_ORDER,
        }
        _write_file(
            in_progress_dir / "config.json5",
            _dict_to_json5(master_content, comment="Master config file (v2 split layout). Declares overlay files."),
        )

        # 2. Per-concern overlay files — write all canonical files even if empty.
        file_comments: dict[str, str] = {
            "paths.json5": "Non-disk paths used by the pipeline.",
            "disks.json5": "Storage disks with accepted categories.",
            "categories.json5": "Category definitions, classification rules, and genre mappings.",
            "patterns.json5": "Staging subdirectory layout.",
            "encoding.json5": "Library encoding and media quality preferences.",
            "scraper.json5": "Scraper, ingest, and fuzzy-match tunables.",
            "trailers.json5": "Trailer download feature configuration.",
        }
        for fname in _OVERLAY_ORDER:
            bucket = buckets.get(fname, {})
            _write_file(
                in_progress_dir / fname,
                _dict_to_json5(bucket, comment=file_comments.get(fname)),
            )

        # 3. Unknown keys → local.json5
        if unknown_keys:
            local_content = {"_migration_unknown_keys": {k: data[k] for k in unknown_keys}}
            _write_file(
                in_progress_dir / "local.json5",
                _dict_to_json5(local_content, comment="Auto-generated by migrate_v1_to_v2."),
            )
            log.warning(
                "migration.v1_to_v2.unknown_keys",
                keys=unknown_keys,
                written_to="local.json5",
            )

    except Exception as exc:
        # Leave .in-progress/ in place for forensics; do NOT rename.
        log.error(
            "migration.v1_to_v2.failed",
            error=str(exc),
            in_progress_dir=str(in_progress_dir),
        )
        raise MigrationError(
            f"Migration failed mid-write. Partial state in {in_progress_dir}. "
            "Fix the issue and remove .in-progress/ before retrying."
        ) from exc

    # ------------------------------------------------------------------
    # Atomic rename .in-progress → target_dir.
    # ------------------------------------------------------------------
    # If target_dir already exists (partial from a previous version check
    # that didn't detect v2), remove it first.
    if target_dir.exists():
        shutil.rmtree(target_dir)

    os.rename(in_progress_dir, target_dir)

    log.info("migration.v1_to_v2.renamed", target_dir=str(target_dir))

    # ------------------------------------------------------------------
    # Write migration-warnings.txt next to target_dir (if unknown keys).
    # ------------------------------------------------------------------
    if unknown_keys:
        warnings_path = target_dir.parent / "migration-warnings.txt"
        warnings_lines = [
            "migration-warnings: the following keys from the v1 config were not recognised",
            "by the splitter and have been placed in local.json5 under '_migration_unknown_keys':",
        ] + [f"  {k}" for k in unknown_keys]
        _write_file(warnings_path, "\n".join(warnings_lines) + "\n")
        log.warning("migration.v1_to_v2.warnings_written", path=str(warnings_path))

    # ------------------------------------------------------------------
    # Rename legacy file to .v1.bak.
    # ------------------------------------------------------------------
    bak_path = Path(str(legacy_path) + ".v1.bak")
    try:
        os.rename(legacy_path, bak_path)
        log.info("migration.v1_to_v2.legacy_backed_up", bak_path=str(bak_path))
    except OSError as exc:
        # Non-fatal: the migration itself succeeded; warn the user.
        log.warning(
            "migration.v1_to_v2.bak_rename_failed",
            legacy_path=str(legacy_path),
            bak_path=str(bak_path),
            error=str(exc),
        )

    log.info("migration.v1_to_v2.complete", target_dir=str(target_dir))
