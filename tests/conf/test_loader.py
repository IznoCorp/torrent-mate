"""Tests for personalscraper.conf.loader."""

import json
import sqlite3
from pathlib import Path

import pytest

from personalscraper.conf.loader import (
    ENV_CONFIG_PATH,
    ConfigLoadError,
    ConfigNotFoundError,
    ConfigValidationError,
    _check_category_orphans,
    load_config,
    load_config_dir,
    resolve_config_path,
)
from personalscraper.conf.models import Config, IndexerConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_minimal_config(path: Path, tmp_path: Path) -> None:
    """Write a minimal valid config.json5 to the given path.

    Args:
        path: File path to write.
        tmp_path: Pytest tmp_path used for disk/staging/complete directories.
    """
    content = f"""{{
        config_version: 1,
        paths: {{
            torrent_complete_dir: "{tmp_path / "complete"}",
            staging_dir: "{tmp_path / "staging"}",
            data_dir: "{tmp_path / ".data"}",
        }},
        disks: [
            {{
                id: "disk_a",
                path: "{tmp_path / "disk_a"}",
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
    }}"""
    path.write_text(content, encoding="utf-8")


def _write_minimal_config_dir(path: Path, tmp_path: Path) -> Path:
    """Write a minimal split-config directory and return it."""
    path.mkdir(parents=True, exist_ok=True)
    _write_minimal_config(path / "config.json5", tmp_path)
    return path


# ---------------------------------------------------------------------------
# resolve_config_path
# ---------------------------------------------------------------------------


class TestResolveConfigPath:
    """Tests for the config path resolution logic."""

    def test_cli_override_takes_priority(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI override must be returned even if env var is set."""
        monkeypatch.setenv(ENV_CONFIG_PATH, str(tmp_path / "env_config"))
        cli_path = tmp_path / "cli_config"
        result = resolve_config_path(cli_override=cli_path)
        assert result == cli_path.expanduser().resolve()

    def test_env_var_used_when_no_cli(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env var path must be used when no CLI override given."""
        env_path = tmp_path / "env_config"
        monkeypatch.setenv(ENV_CONFIG_PATH, str(env_path))
        result = resolve_config_path()
        assert result == env_path.expanduser().resolve()

    def test_default_when_neither(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Default points to the split-config directory."""
        monkeypatch.delenv(ENV_CONFIG_PATH, raising=False)
        monkeypatch.chdir(tmp_path)

        result = resolve_config_path()
        assert result == (tmp_path / "config").resolve()

    def test_expanduser_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Tilde paths must be expanded."""
        monkeypatch.delenv(ENV_CONFIG_PATH, raising=False)
        tilde_path = "~/my_config"
        result = resolve_config_path(cli_override=Path(tilde_path))
        assert "~" not in str(result)


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Tests for load_config function."""

    def test_loads_valid_config(self, tmp_path: Path) -> None:
        """A valid config directory must be loaded and return a Config instance."""
        cfg_dir = _write_minimal_config_dir(tmp_path / "config", tmp_path)
        config = load_config(cfg_dir)
        assert isinstance(config, Config)
        assert config.disks[0].id == "disk_a"

    def test_missing_file_raises_not_found(self, tmp_path: Path) -> None:
        """A missing config directory must raise ConfigNotFoundError."""
        with pytest.raises(ConfigNotFoundError, match="No split-config directory"):
            load_config(tmp_path / "missing_config")

    def test_file_path_raises_not_found(self, tmp_path: Path) -> None:
        """A file path is rejected; config is directory-based only."""
        cfg_path = tmp_path / "config.json5"
        _write_minimal_config(cfg_path, tmp_path)
        with pytest.raises(ConfigNotFoundError, match="No split-config directory"):
            load_config(cfg_path)

    def test_invalid_json5_raises_validation_error(self, tmp_path: Path) -> None:
        """A file with invalid JSON5 syntax must raise ConfigValidationError."""
        cfg_dir = tmp_path / "bad_config"
        cfg_dir.mkdir()
        (cfg_dir / "config.json5").write_text("{ this is not valid json5 !!!", encoding="utf-8")
        with pytest.raises(ConfigValidationError, match="JSON5 parse error"):
            load_config(cfg_dir)

    def test_pydantic_validation_error_wrapped(self, tmp_path: Path) -> None:
        """A Pydantic validation error must be wrapped in ConfigValidationError."""
        cfg_dir = tmp_path / "bad_schema"
        cfg_dir.mkdir()
        # Missing required 'paths' field
        (cfg_dir / "config.json5").write_text(
            json.dumps(
                {
                    "disks": [
                        {
                            "id": "disk_a",
                            "path": str(tmp_path / "disk_a"),
                            "categories": ["movies"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ConfigValidationError, match="Validation error"):
            load_config(cfg_dir)

    def test_expanduser_resolve_applied(self, tmp_path: Path) -> None:
        """Path passed to load_config must work as an absolute directory."""
        cfg_dir = _write_minimal_config_dir(tmp_path / "config", tmp_path)
        # Verify the function accepts an absolute path object without errors.
        config = load_config(cfg_dir)
        assert config is not None


# ---------------------------------------------------------------------------
# load_config_dir  (v2 multi-file loader)
# ---------------------------------------------------------------------------


def _master_json5(tmp_path: Path, overlay_names: list[str] | None = None) -> str:
    """Return a master config.json5 body that declares the given overlay filenames.

    The master carries only the fields that are NOT delegated to overlay files
    so that tests can place different top-level keys in each overlay and avoid
    ``ConfigConflictError``.

    Args:
        tmp_path: Root directory used for disk/staging path literals.
        overlay_names: List of overlay filenames declared in the ``overlays``
            key.  If ``None``, no ``overlays`` key is written.

    Returns:
        JSON5 string suitable for writing to ``config.json5``.
    """
    overlays_fragment = ""
    if overlay_names is not None:
        names_literal = ", ".join(f'"{n}"' for n in overlay_names)
        overlays_fragment = f"overlays: [{names_literal}],"

    return f"""{{
        config_version: 1,
        {overlays_fragment}
        paths: {{
            torrent_complete_dir: "{tmp_path / "complete"}",
            staging_dir: "{tmp_path / "staging"}",
            data_dir: "{tmp_path / ".data"}",
        }},
        disks: [
            {{
                id: "disk_a",
                path: "{tmp_path / "disk_a"}",
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
    }}"""


class TestLoadConfigDir:
    """Tests for the v2 multi-file load_config_dir loader."""

    def test_happy_path_with_two_non_conflicting_overlays(self, tmp_path: Path) -> None:
        """config_dir with master + 2 non-conflicting overlays loads into a valid Config.

        The master owns ``paths``, ``disks``, and ``staging_dirs``.  Each overlay
        owns a distinct top-level key (``categories`` and ``genre_mapping``
        respectively) so no ConfigConflictError is raised.
        """
        cfg_dir = tmp_path / "cfg"
        cfg_dir.mkdir()

        # Master declares the two overlay filenames.
        (cfg_dir / "config.json5").write_text(
            _master_json5(tmp_path, overlay_names=["overlay_cats.json5", "overlay_anime.json5"]),
            encoding="utf-8",
        )

        # overlay_cats.json5 — defines the ``categories`` top-level key.
        (cfg_dir / "overlay_cats.json5").write_text(
            """{
                categories: {
                    movies: { folder_name: "Films" },
                },
            }""",
            encoding="utf-8",
        )

        # overlay_anime.json5 — defines the ``anime_rule`` top-level key.
        (cfg_dir / "overlay_anime.json5").write_text(
            """{
                anime_rule: {
                    enabled: true,
                    maps_to: "anime",
                    requires_origin_country: ["JP"],
                },
            }""",
            encoding="utf-8",
        )

        config = load_config_dir(cfg_dir)

        assert isinstance(config, Config)
        assert config.disks[0].id == "disk_a"
        # Overlay value surfaced correctly.
        assert config.category("movies").folder_name == "Films"
        assert config.anime_rule.enabled is True

    def test_missing_overlay_file_raises_config_load_error(self, tmp_path: Path) -> None:
        """A declared overlay file that is absent on disk must raise ConfigLoadError.

        The loader is strict: every filename listed in ``overlays`` must exist so
        that silent misconfiguration is caught early.
        """
        cfg_dir = tmp_path / "cfg"
        cfg_dir.mkdir()

        (cfg_dir / "config.json5").write_text(
            _master_json5(tmp_path, overlay_names=["ghost.json5"]),
            encoding="utf-8",
        )
        # ghost.json5 is intentionally NOT created.

        with pytest.raises(ConfigLoadError, match="ghost.json5"):
            load_config_dir(cfg_dir)

    def test_local_json5_overrides_without_conflict_error(self, tmp_path: Path) -> None:
        """local.json5 must override a key already set by a non-local overlay without error.

        The ``categories`` key is first set by ``overlay_cats.json5`` and then
        overridden by ``local.json5``.  This must succeed (last-wins) and the
        local value must be present in the resulting Config.
        """
        cfg_dir = tmp_path / "cfg"
        cfg_dir.mkdir()

        (cfg_dir / "config.json5").write_text(
            _master_json5(tmp_path, overlay_names=["overlay_cats.json5"]),
            encoding="utf-8",
        )

        # Non-local overlay sets categories.movies folder_name to "Films".
        (cfg_dir / "overlay_cats.json5").write_text(
            """{
                categories: {
                    movies: { folder_name: "Films" },
                },
            }""",
            encoding="utf-8",
        )

        # local.json5 overrides the same key with a machine-specific value.
        (cfg_dir / "local.json5").write_text(
            """{
                categories: {
                    movies: { folder_name: "Movies-Local" },
                },
            }""",
            encoding="utf-8",
        )

        # Must not raise ConfigConflictError.
        config = load_config_dir(cfg_dir)

        assert isinstance(config, Config)
        assert config.category("movies").folder_name == "Movies-Local"

    def test_missing_master_raises_config_not_found_error(self, tmp_path: Path) -> None:
        """load_config_dir on a directory without config.json5 must raise ConfigNotFoundError.

        There is no fallback: the master file is required for the v2 loader to
        know what overlays to apply.
        """
        cfg_dir = tmp_path / "empty_cfg"
        cfg_dir.mkdir()
        # Deliberately do NOT create config.json5.

        with pytest.raises(ConfigNotFoundError, match="No config.json5 found"):
            load_config_dir(cfg_dir)


# ---------------------------------------------------------------------------
# IndexerConfig round-trip
# ---------------------------------------------------------------------------


class TestIndexerConfigRoundTrip:
    """Tests for IndexerConfig pydantic model parse/validate/dump cycle."""

    def test_default_round_trip(self) -> None:
        """IndexerConfig with all defaults must serialise and re-parse cleanly."""
        cfg = IndexerConfig()
        dumped = cfg.model_dump()
        restored = IndexerConfig.model_validate(dumped)
        assert restored == cfg

    def test_custom_values_round_trip(self) -> None:
        """IndexerConfig with non-default values must survive a round-trip."""
        raw: dict[str, object] = {
            "db_path": "/tmp/test_library.db",
            "scan": {
                "nightly_mode": "full",
                "budget_seconds": 3600,
                "checkpoint_every_n_files": 500,
                "max_workers_total": 2,
                "racy_window_seconds": 5.0,
                "n_strikes_for_softdelete": 5,
                "read_rate_mb_per_sec": 80.0,
                "sequential_read_hint": False,
                "drop_indexes_during_full_scan": False,
            },
            "fingerprint": {
                "oshash": False,
                "xxh3_partial_bytes": 2097152,
                "compute_xxh3_on_racy": False,
            },
            "mediainfo": {
                "library_path": "/opt/homebrew/lib/libmediainfo.dylib",
                "extract_streams": False,
                "min_size_mb": 100,
                "parse_speed": 0.5,
                "defer_to_enrich": False,
            },
            "drift": {
                "merkle_per_disk": False,
                "verify_disks_each_scan": False,
                "sentinel_filename": ".my-sentinel",
            },
            "spotlight": {
                "probe_at_startup": False,
                "use_when_available": False,
            },
            "repair": {
                "queue_drain_on_scan_finish": False,
                "max_repair_seconds_per_drain": 600,
            },
            "log": {
                "scan_event_retention_days": 30,
                "deleted_item_retention_days": 180,
            },
        }
        cfg = IndexerConfig.model_validate(raw)
        assert cfg.scan.nightly_mode == "full"
        assert cfg.scan.budget_seconds == 3600
        assert cfg.fingerprint.xxh3_partial_bytes == 2097152
        assert cfg.mediainfo.library_path == "/opt/homebrew/lib/libmediainfo.dylib"
        assert cfg.drift.sentinel_filename == ".my-sentinel"
        assert cfg.spotlight.probe_at_startup is False
        assert cfg.repair.max_repair_seconds_per_drain == 600
        assert cfg.log.deleted_item_retention_days == 180

        # Dump and re-parse must produce an equal model.
        restored = IndexerConfig.model_validate(cfg.model_dump())
        assert restored == cfg

    def test_extra_fields_forbidden(self) -> None:
        """IndexerConfig must reject unknown top-level fields (extra='forbid')."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            IndexerConfig.model_validate({"unknown_key": True})

    def test_nightly_mode_enum_validation(self) -> None:
        """Invalid nightly_mode literal must raise ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            IndexerConfig.model_validate({"scan": {"nightly_mode": "turbo"}})

    def test_config_has_indexer_field(self, tmp_path: Path) -> None:
        """Config model must expose an ``indexer`` field of type IndexerConfig.

        When db_path is not explicitly set, it is derived from
        ``paths.data_dir / 'library.db'`` by the Config-level validator.
        """
        cfg_dir = _write_minimal_config_dir(tmp_path / "config", tmp_path)
        config = load_config(cfg_dir)
        assert isinstance(config.indexer, IndexerConfig)
        assert config.indexer.db_path.is_absolute()
        assert config.indexer.db_path.name == "library.db"
        assert config.indexer.db_path.parent.name == ".data"


# ---------------------------------------------------------------------------
# db_path external-mount validator
# ---------------------------------------------------------------------------


class TestIndexerDbPathValidator:
    """Tests for the db_path macFUSE / external mount rejection validator."""

    def test_internal_path_accepted(self) -> None:
        """A db_path on the home directory or project root must be accepted."""
        cfg = IndexerConfig.model_validate({"db_path": "/Users/izno/.data/library.db"})
        assert cfg.db_path == Path("/Users/izno/.data/library.db")

    def test_tmp_path_accepted(self) -> None:
        """A path under /tmp must be accepted (internal macOS volume)."""
        cfg = IndexerConfig.model_validate({"db_path": "/tmp/library.db"})
        assert cfg.db_path == Path("/tmp/library.db")

    def test_volumes_path_rejected(self) -> None:
        """A db_path starting with /Volumes/ must raise ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="/Volumes/"):
            IndexerConfig.model_validate({"db_path": "/Volumes/ExternalDisk/library.db"})

    def test_volumes_subfolder_rejected(self) -> None:
        """Any path under /Volumes/ sub-directories must be rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="external or macFUSE mount"):
            IndexerConfig.model_validate({"db_path": "/Volumes/USB1/data/lib.db"})

    def test_relative_path_resolved_to_absolute(self) -> None:
        """A relative path is accepted and resolved against CWD at load-time.

        The validator anchors db_path to an absolute path so every consumer
        (sqlite3.connect, indexer outbox, dispatch) sees the same file
        regardless of the calling process's CWD. Without this anchor the
        same config string produced different DB files depending on the
        entry point.
        """
        cfg = IndexerConfig.model_validate({"db_path": ".data/library.db"})
        assert cfg.db_path.is_absolute()
        assert cfg.db_path.name == "library.db"
        assert cfg.db_path.parent.name == ".data"

    def test_validator_in_isolation(self) -> None:
        """Calling the field_validator class method directly must work for /Volumes/ paths."""
        from pydantic import ValidationError

        # The validator is enforced via IndexerConfig; test it via model construction.
        with pytest.raises(ValidationError):
            IndexerConfig(db_path=Path("/Volumes/NAS/library.db"))


# ---------------------------------------------------------------------------
# Category-orphan startup check
# ---------------------------------------------------------------------------


def _make_library_db(db_path: Path, category_ids: list[str]) -> None:
    """Create a minimal library.db with a media_item table pre-populated.

    Args:
        db_path: Path where the SQLite file is created.
        category_ids: List of category_id values to insert as distinct rows.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE media_item (
            id          INTEGER PRIMARY KEY,
            category_id TEXT NOT NULL
        )
        """
    )
    for i, cid in enumerate(category_ids):
        conn.execute("INSERT INTO media_item (id, category_id) VALUES (?, ?)", (i, cid))
    conn.commit()
    conn.close()


class TestCategoryOrphanCheck:
    """Tests for the _check_category_orphans startup check."""

    def test_no_db_file_is_noop(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """When library.db does not exist the check must be silent.

        ``load_config`` itself calls ``_check_category_orphans`` once during
        construction with the configured (default-resolved) db_path. Those
        load-time warnings are unrelated to this test, so we clear caplog
        before exercising the explicit call we want to assert on.
        """
        import logging

        cfg_dir = _write_minimal_config_dir(tmp_path / "config", tmp_path)
        config = load_config(cfg_dir)

        # Override db_path to a nonexistent location.
        object.__setattr__(
            config.indexer,
            "db_path",
            tmp_path / "nonexistent" / "library.db",
        )

        caplog.clear()
        with caplog.at_level(logging.WARNING):
            _check_category_orphans(config)

        assert "category_orphan" not in caplog.text

    def test_known_categories_are_silent(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """When all DB category_ids are declared in config, no warning is emitted."""
        import logging

        cfg_dir = _write_minimal_config_dir(tmp_path / "config", tmp_path)
        config = load_config(cfg_dir)

        db_path = tmp_path / "library.db"
        # "movies" and "tv_shows" are builtin IDs — always in all_category_ids.
        _make_library_db(db_path, ["movies", "tv_shows"])
        object.__setattr__(config.indexer, "db_path", db_path)

        caplog.clear()
        with caplog.at_level(logging.WARNING):
            _check_category_orphans(config)

        assert "category_orphan" not in caplog.text

    def test_orphan_ids_logged_as_warning(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """When the DB contains a category_id not in config, a warning must be logged."""
        import logging

        cfg_dir = _write_minimal_config_dir(tmp_path / "config", tmp_path)
        config = load_config(cfg_dir)

        db_path = tmp_path / "library.db"
        # "movies_old" does not exist in any declared category.
        _make_library_db(db_path, ["movies", "movies_old"])
        object.__setattr__(config.indexer, "db_path", db_path)

        with caplog.at_level(logging.WARNING):
            _check_category_orphans(config)

        assert "indexer.config.category_orphan" in caplog.text
        assert "movies_old" in caplog.text

    def test_loader_calls_orphan_check_on_load(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """load_config must trigger the orphan check if library.db is present."""
        import logging

        cfg_dir = _write_minimal_config_dir(tmp_path / "config", tmp_path)
        cfg_path = cfg_dir / "config.json5"

        # Build a config to find the default db_path; patch it to tmp_path.
        # We do this by writing a config that sets the db_path to our DB.
        db_path = tmp_path / "library.db"
        _make_library_db(db_path, ["movies", "zombie_category"])

        # Write a config where indexer.db_path points at our test DB.
        content = f"""{{
            config_version: 1,
            paths: {{
                torrent_complete_dir: "{tmp_path / "complete"}",
                staging_dir: "{tmp_path / "staging"}",
                data_dir: "{tmp_path / ".data"}",
            }},
            disks: [
                {{
                    id: "disk_a",
                    path: "{tmp_path / "disk_a"}",
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
            indexer: {{
                db_path: "{db_path}",
            }},
        }}"""
        cfg_path.write_text(content, encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            load_config(cfg_dir)

        assert "indexer.config.category_orphan" in caplog.text
        assert "zombie_category" in caplog.text


# ---------------------------------------------------------------------------
# load_config_dir warning behaviour
# ---------------------------------------------------------------------------


class TestLoadConfigWarnings:
    """Tests that load_config_dir does not emit unrelated warnings."""

    def test_load_config_dir_does_not_emit_deprecation_warning(self, tmp_path: Path) -> None:
        """load_config_dir must NOT emit a DeprecationWarning."""
        cfg_dir = tmp_path / "cfg"
        cfg_dir.mkdir()
        (cfg_dir / "config.json5").write_text(
            _master_json5(tmp_path),
            encoding="utf-8",
        )

        # recwarn collects all warnings; we assert none are DeprecationWarning.
        import warnings as _warnings

        with _warnings.catch_warnings(record=True) as caught:
            _warnings.simplefilter("always")
            load_config_dir(cfg_dir)

        deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deprecation_warnings == [], (
            f"load_config_dir must not emit DeprecationWarning, but got: {deprecation_warnings}"
        )
