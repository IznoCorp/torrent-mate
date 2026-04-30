"""Tests for personalscraper.conf.migration — golden parity and happy path."""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.conf.loader import load_config, load_config_dir
from personalscraper.conf.migration import (
    MigrationAlreadyDoneError,
    migrate_v1_to_v2,
    plan_migration,
)
from personalscraper.conf.models import Config

# ---------------------------------------------------------------------------
# Fixtures: minimal v1 monolith
# ---------------------------------------------------------------------------

_MINIMAL_V1 = """\
{{
    config_version: 1,
    paths: {{
        torrent_complete_dir: "{complete}",
        staging_dir: "{staging}",
        data_dir: "{data}",
    }},
    disks: [
        {{
            id: "disk_a",
            path: "{disk_a}",
            categories: ["movies", "tv_shows"],
        }},
    ],
    staging_dirs: [
        {{ id: 1, name: "movies", file_type: "movie" }},
        {{ id: 2, name: "tvshows", file_type: "tvshow" }},
        {{ id: 3, name: "ebooks", file_type: "ebook" }},
        {{ id: 4, name: "audio", file_type: "audio" }},
        {{ id: 5, name: "apps", file_type: "app" }},
        {{ id: 6, name: "android", file_type: "app" }},
        {{ id: 97, name: "temp", file_type: null, role: "ingest" }},
        {{ id: 98, name: "autres", file_type: "other" }},
    ],
}}
"""


def _write_v1(tmp_path: Path) -> Path:
    """Write a minimal v1 monolith config to tmp_path/config.json5.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Path to the written config.json5.
    """
    legacy = tmp_path / "config.json5"
    content = _MINIMAL_V1.format(
        complete=tmp_path / "complete",
        staging=tmp_path / "staging",
        data=tmp_path / ".data",
        disk_a=tmp_path / "disk_a",
    )
    legacy.write_text(content, encoding="utf-8")
    return legacy


# ---------------------------------------------------------------------------
# plan_migration
# ---------------------------------------------------------------------------


class TestPlanMigration:
    """Tests for plan_migration (dry-run helper)."""

    def test_returns_all_overlay_files(self, tmp_path: Path) -> None:
        """plan_migration must include all canonical overlay filenames."""
        legacy = _write_v1(tmp_path)
        plan = plan_migration(legacy)
        expected = {
            "config.json5",
            "paths.json5",
            "disks.json5",
            "categories.json5",
            "patterns.json5",
            "encoding.json5",
            "scraper.json5",
            "trailers.json5",
            "indexer.json5",
        }
        assert expected.issubset(plan.keys())

    def test_master_contains_overlays_key(self, tmp_path: Path) -> None:
        """Master config.json5 in the plan must declare the overlays key."""
        legacy = _write_v1(tmp_path)
        plan = plan_migration(legacy)
        assert "overlays" in plan["config.json5"]
        assert isinstance(plan["config.json5"]["overlays"], list)

    def test_paths_in_paths_file(self, tmp_path: Path) -> None:
        """Paths key must land in paths.json5."""
        legacy = _write_v1(tmp_path)
        plan = plan_migration(legacy)
        assert "paths" in plan["paths.json5"]

    def test_disks_in_disks_file(self, tmp_path: Path) -> None:
        """Disks key must land in disks.json5."""
        legacy = _write_v1(tmp_path)
        plan = plan_migration(legacy)
        assert "disks" in plan["disks.json5"]

    def test_staging_dirs_in_patterns_file(self, tmp_path: Path) -> None:
        """staging_dirs key must land in patterns.json5."""
        legacy = _write_v1(tmp_path)
        plan = plan_migration(legacy)
        assert "staging_dirs" in plan["patterns.json5"]

    def test_indexer_in_indexer_file(self, tmp_path: Path) -> None:
        """Indexer key must land in indexer.json5."""
        legacy = _write_v1(tmp_path)
        raw = legacy.read_text(encoding="utf-8")
        raw = raw.replace(
            "    staging_dirs:",
            '    indexer: { db_path: ".personalscraper/library.db" },\n    staging_dirs:',
        )
        legacy.write_text(raw, encoding="utf-8")

        plan = plan_migration(legacy)

        assert "indexer" in plan["indexer.json5"]

    def test_does_not_write_disk(self, tmp_path: Path) -> None:
        """plan_migration must not create any files on disk."""
        legacy = _write_v1(tmp_path)
        plan_migration(legacy)
        # Only the legacy file should exist; target_dir not touched.
        assert not (tmp_path / "config").exists()


# ---------------------------------------------------------------------------
# migrate_v1_to_v2 — happy path
# ---------------------------------------------------------------------------


class TestMigrateV1ToV2:
    """Tests for migrate_v1_to_v2 in the normal success flow."""

    def test_creates_target_dir(self, tmp_path: Path) -> None:
        """migrate_v1_to_v2 must create target_dir."""
        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"
        migrate_v1_to_v2(legacy, target)
        assert target.is_dir()

    def test_writes_master_and_overlays(self, tmp_path: Path) -> None:
        """All canonical overlay files plus master must be written."""
        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"
        migrate_v1_to_v2(legacy, target)
        expected = {
            "config.json5",
            "paths.json5",
            "disks.json5",
            "categories.json5",
            "patterns.json5",
            "encoding.json5",
            "scraper.json5",
            "trailers.json5",
            "indexer.json5",
        }
        written = {f.name for f in target.iterdir() if f.is_file()}
        assert expected.issubset(written)

    def test_v1_bak_written(self, tmp_path: Path) -> None:
        """Legacy file must be renamed to .v1.bak after success."""
        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"
        migrate_v1_to_v2(legacy, target)
        assert not legacy.exists()
        assert (tmp_path / "config.json5.v1.bak").is_file()

    def test_no_in_progress_dir_after_success(self, tmp_path: Path) -> None:
        """.in-progress/ must not exist after a successful migration."""
        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"
        migrate_v1_to_v2(legacy, target)
        assert not Path(str(target) + ".in-progress").exists()

    def test_golden_parity_v1_config_eq_v2_config(self, tmp_path: Path) -> None:
        """Config loaded from v1 monolith must equal Config loaded from v2 split dir."""
        legacy = _write_v1(tmp_path)
        # Load v1 directly.
        config_v1: Config = load_config(legacy)

        # Migrate; legacy is now .v1.bak — read from bak for reload.
        target = tmp_path / "config"
        migrate_v1_to_v2(legacy, target)

        # Load v2.
        config_v2: Config = load_config_dir(target)

        # Field-by-field equality for a readable failure message.
        # Use type(config_v1).model_fields (class access) to avoid the
        # PydanticDeprecationWarning raised when accessing model_fields on an instance.
        for field_name in type(config_v1).model_fields:
            v1_val = getattr(config_v1, field_name)
            v2_val = getattr(config_v2, field_name)
            assert v1_val == v2_val, (
                f"Field '{field_name}' differs between v1 and v2 config:\n  v1: {v1_val!r}\n  v2: {v2_val!r}"
            )

    def test_idempotent_refuses_on_existing_v2(self, tmp_path: Path) -> None:
        """A second migration on an already-migrated directory must raise MigrationAlreadyDoneError."""
        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"
        migrate_v1_to_v2(legacy, target)

        # Write a new legacy-looking file to try migrating again.
        legacy2 = _write_v1(tmp_path)
        with pytest.raises(MigrationAlreadyDoneError, match="overlays"):
            migrate_v1_to_v2(legacy2, target)


# ---------------------------------------------------------------------------
# Unknown keys → local.json5
# ---------------------------------------------------------------------------


class TestUnknownKeys:
    """Tests for the unknown-key handling path."""

    def test_unknown_key_lands_in_local_json5(self, tmp_path: Path) -> None:
        """An unrecognised v1 key must end up in local.json5 under _migration_unknown_keys."""
        legacy = tmp_path / "config.json5"
        content = _MINIMAL_V1.format(
            complete=tmp_path / "complete",
            staging=tmp_path / "staging",
            data=tmp_path / ".data",
            disk_a=tmp_path / "disk_a",
        )
        # Inject an unknown key.
        content = content.replace("config_version: 1,", "config_version: 1,\n    my_unknown_key: 42,")
        legacy.write_text(content, encoding="utf-8")

        target = tmp_path / "config"
        migrate_v1_to_v2(legacy, target)

        import json5

        local = json5.loads((target / "local.json5").read_text(encoding="utf-8"))
        assert "my_unknown_key" in local["_migration_unknown_keys"]
        assert local["_migration_unknown_keys"]["my_unknown_key"] == 42

    def test_unknown_key_writes_warnings_txt(self, tmp_path: Path) -> None:
        """migration-warnings.txt must be written next to target_dir when unknown keys present."""
        legacy = tmp_path / "config.json5"
        content = _MINIMAL_V1.format(
            complete=tmp_path / "complete",
            staging=tmp_path / "staging",
            data=tmp_path / ".data",
            disk_a=tmp_path / "disk_a",
        )
        content = content.replace("config_version: 1,", "config_version: 1,\n    extra_key: true,")
        legacy.write_text(content, encoding="utf-8")

        target = tmp_path / "config"
        migrate_v1_to_v2(legacy, target)

        warnings_path = tmp_path / "migration-warnings.txt"
        assert warnings_path.is_file()
        text = warnings_path.read_text(encoding="utf-8")
        assert "extra_key" in text

    def test_multiple_unknown_keys(self, tmp_path: Path) -> None:
        """Multiple unknown keys must all appear in local.json5 and warnings.txt."""
        legacy = tmp_path / "config.json5"
        content = _MINIMAL_V1.format(
            complete=tmp_path / "complete",
            staging=tmp_path / "staging",
            data=tmp_path / ".data",
            disk_a=tmp_path / "disk_a",
        )
        content = content.replace(
            "config_version: 1,",
            "config_version: 1,\n    alpha: 1,\n    beta: 2,",
        )
        legacy.write_text(content, encoding="utf-8")

        target = tmp_path / "config"
        migrate_v1_to_v2(legacy, target)

        import json5

        local = json5.loads((target / "local.json5").read_text(encoding="utf-8"))
        unknown = local["_migration_unknown_keys"]
        assert "alpha" in unknown
        assert "beta" in unknown
        warnings_text = (tmp_path / "migration-warnings.txt").read_text(encoding="utf-8")
        assert "alpha" in warnings_text
        assert "beta" in warnings_text

    def test_no_local_json5_when_no_unknown_keys(self, tmp_path: Path) -> None:
        """local.json5 must NOT be written when all keys are recognised.

        migration-warnings.txt is always written (contains the media_index.json
        deprecation notice), but local.json5 is only written for unknown keys.
        """
        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"
        migrate_v1_to_v2(legacy, target)
        assert not (target / "local.json5").exists()
        # warnings.txt is always written: it carries the media_index.json notice.
        warnings_path = tmp_path / "migration-warnings.txt"
        assert warnings_path.is_file()
        assert "media_index.json" in warnings_path.read_text(encoding="utf-8")
