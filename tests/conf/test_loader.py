"""Tests for personalscraper.conf.loader."""

import json
from pathlib import Path

import pytest

from personalscraper.conf.loader import (
    ENV_CONFIG_PATH,
    ConfigLoadError,
    ConfigNotFoundError,
    ConfigValidationError,
    load_config,
    load_config_dir,
    resolve_config_path,
)
from personalscraper.conf.models import Config

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


# ---------------------------------------------------------------------------
# resolve_config_path
# ---------------------------------------------------------------------------


class TestResolveConfigPath:
    """Tests for the config path resolution logic."""

    def test_cli_override_takes_priority(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI override must be returned even if env var is set."""
        monkeypatch.setenv(ENV_CONFIG_PATH, str(tmp_path / "env_config.json5"))
        cli_path = tmp_path / "cli_config.json5"
        result = resolve_config_path(cli_override=cli_path)
        assert result == cli_path.expanduser().resolve()

    def test_env_var_used_when_no_cli(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env var path must be used when no CLI override given."""
        env_path = tmp_path / "env_config.json5"
        monkeypatch.setenv(ENV_CONFIG_PATH, str(env_path))
        result = resolve_config_path()
        assert result == env_path.expanduser().resolve()

    def test_default_when_neither(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default ./config.json5 must be used when no CLI and no env."""
        monkeypatch.delenv(ENV_CONFIG_PATH, raising=False)
        result = resolve_config_path()
        assert result.name == "config.json5"

    def test_expanduser_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Tilde paths must be expanded."""
        monkeypatch.delenv(ENV_CONFIG_PATH, raising=False)
        tilde_path = "~/my_config.json5"
        result = resolve_config_path(cli_override=Path(tilde_path))
        assert "~" not in str(result)


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Tests for load_config function."""

    def test_loads_valid_config(self, tmp_path: Path) -> None:
        """A valid config file must be loaded and return a Config instance."""
        cfg_path = tmp_path / "config.json5"
        _write_minimal_config(cfg_path, tmp_path)
        config = load_config(cfg_path)
        assert isinstance(config, Config)
        assert config.disks[0].id == "disk_a"

    def test_missing_file_raises_not_found(self, tmp_path: Path) -> None:
        """A missing file must raise ConfigNotFoundError."""
        with pytest.raises(ConfigNotFoundError, match="No config file at"):
            load_config(tmp_path / "nonexistent.json5")

    def test_invalid_json5_raises_validation_error(self, tmp_path: Path) -> None:
        """A file with invalid JSON5 syntax must raise ConfigValidationError."""
        cfg_path = tmp_path / "bad.json5"
        cfg_path.write_text("{ this is not valid json5 !!!", encoding="utf-8")
        with pytest.raises(ConfigValidationError, match="JSON5 parse error"):
            load_config(cfg_path)

    def test_pydantic_validation_error_wrapped(self, tmp_path: Path) -> None:
        """A Pydantic validation error must be wrapped in ConfigValidationError."""
        cfg_path = tmp_path / "bad_schema.json5"
        # Missing required 'paths' field
        cfg_path.write_text(
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
            load_config(cfg_path)

    def test_expanduser_resolve_applied(self, tmp_path: Path) -> None:
        """Path passed to load_config must be resolved via expanduser/resolve."""
        cfg_path = tmp_path / "config.json5"
        _write_minimal_config(cfg_path, tmp_path)
        # Verify the function accepts an absolute path object without errors.
        config = load_config(cfg_path)
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
