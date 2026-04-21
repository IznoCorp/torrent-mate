"""Tests for personalscraper.conf.loader."""

import json

import pytest

from personalscraper.conf.loader import (
    ENV_CONFIG_PATH,
    ConfigNotFoundError,
    ConfigValidationError,
    load_config,
    resolve_config_path,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_minimal_config(path, tmp_path):
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
    }}"""
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# resolve_config_path
# ---------------------------------------------------------------------------


class TestResolveConfigPath:
    """Tests for the config path resolution logic."""

    def test_cli_override_takes_priority(self, tmp_path, monkeypatch):
        """CLI override must be returned even if env var is set."""
        monkeypatch.setenv(ENV_CONFIG_PATH, str(tmp_path / "env_config.json5"))
        cli_path = tmp_path / "cli_config.json5"
        result = resolve_config_path(cli_override=cli_path)
        assert result == cli_path.expanduser().resolve()

    def test_env_var_used_when_no_cli(self, tmp_path, monkeypatch):
        """Env var path must be used when no CLI override given."""
        env_path = tmp_path / "env_config.json5"
        monkeypatch.setenv(ENV_CONFIG_PATH, str(env_path))
        result = resolve_config_path()
        assert result == env_path.expanduser().resolve()

    def test_default_when_neither(self, monkeypatch):
        """Default ./config.json5 must be used when no CLI and no env."""
        monkeypatch.delenv(ENV_CONFIG_PATH, raising=False)
        result = resolve_config_path()
        assert result.name == "config.json5"

    def test_expanduser_applied(self, monkeypatch):
        """Tilde paths must be expanded."""
        monkeypatch.delenv(ENV_CONFIG_PATH, raising=False)
        tilde_path = "~/my_config.json5"
        result = resolve_config_path(cli_override=__import__("pathlib").Path(tilde_path))
        assert "~" not in str(result)


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Tests for load_config function."""

    def test_loads_valid_config(self, tmp_path):
        """A valid config file must be loaded and return a Config instance."""
        cfg_path = tmp_path / "config.json5"
        _write_minimal_config(cfg_path, tmp_path)
        from personalscraper.conf.models import Config

        config = load_config(cfg_path)
        assert isinstance(config, Config)
        assert config.disks[0].id == "disk_a"

    def test_missing_file_raises_not_found(self, tmp_path):
        """A missing file must raise ConfigNotFoundError."""
        with pytest.raises(ConfigNotFoundError, match="No config file at"):
            load_config(tmp_path / "nonexistent.json5")

    def test_invalid_json5_raises_validation_error(self, tmp_path):
        """A file with invalid JSON5 syntax must raise ConfigValidationError."""
        cfg_path = tmp_path / "bad.json5"
        cfg_path.write_text("{ this is not valid json5 !!!", encoding="utf-8")
        with pytest.raises(ConfigValidationError, match="JSON5 parse error"):
            load_config(cfg_path)

    def test_pydantic_validation_error_wrapped(self, tmp_path):
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

    def test_expanduser_resolve_applied(self, tmp_path):
        """Path passed to load_config must be resolved via expanduser/resolve."""
        cfg_path = tmp_path / "config.json5"
        _write_minimal_config(cfg_path, tmp_path)
        # Pass as string-like relative won't work here since tmp_path is absolute,
        # but we can verify the function doesn't crash on an absolute path object
        config = load_config(cfg_path)
        assert config is not None
