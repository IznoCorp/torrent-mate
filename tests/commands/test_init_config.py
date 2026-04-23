"""Tests for personalscraper.commands.init_config."""

from __future__ import annotations

from pathlib import Path

import json5
import pytest

from personalscraper.commands.init_config import _backup_output, _load_dotenv, init_config

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent.parent / "conf" / "fixtures"
V14_ENV_SAMPLE = FIXTURES_DIR / "v14_env_sample.env"
EXAMPLE_JSON5 = Path(__file__).parent.parent.parent / "config.example.json5"


def _load_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a plain dict.

    Args:
        path: Path to the .env file.

    Returns:
        Dict mapping variable names to their string values.
    """
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


# ===========================================================================
# _load_dotenv helper
# ===========================================================================


class TestLoadDotenv:
    """Tests for the _load_dotenv helper."""

    def test_parses_key_value(self, tmp_path: Path) -> None:
        """Standard KEY=VALUE lines must be parsed correctly."""
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n", encoding="utf-8")
        result = _load_dotenv(env_file)
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_ignores_comments(self, tmp_path: Path) -> None:
        """Lines starting with # must be ignored."""
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\nFOO=bar\n", encoding="utf-8")
        result = _load_dotenv(env_file)
        assert "# comment" not in result
        assert result["FOO"] == "bar"

    def test_ignores_blank_lines(self, tmp_path: Path) -> None:
        """Blank lines must be ignored."""
        env_file = tmp_path / ".env"
        env_file.write_text("\nFOO=bar\n\n", encoding="utf-8")
        result = _load_dotenv(env_file)
        assert result == {"FOO": "bar"}

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        """Missing .env returns an empty dict (no error)."""
        result = _load_dotenv(tmp_path / "nonexistent.env")
        assert result == {}


# ===========================================================================
# _backup_output helper
# ===========================================================================


class TestBackupOutput:
    """Tests for the _backup_output helper."""

    def test_creates_v15_bak(self, tmp_path: Path) -> None:
        """_backup_output must create <name>.v15.bak."""
        output = tmp_path / "config.json5"
        output.write_text("{}", encoding="utf-8")
        _backup_output(output)
        assert (tmp_path / "config.json5.v15.bak").exists()
        assert not output.exists()

    def test_overwrites_existing_backup(self, tmp_path: Path) -> None:
        """Second call must overwrite the existing .v15.bak (idempotent)."""
        output = tmp_path / "config.json5"
        output.write_text('{"first": true}', encoding="utf-8")
        _backup_output(output)
        # Recreate output with new content.
        output.write_text('{"second": true}', encoding="utf-8")
        _backup_output(output)
        bak = tmp_path / "config.json5.v15.bak"
        assert bak.exists()
        assert json5.loads(bak.read_text(encoding="utf-8")) == {"second": True}


# ===========================================================================
# 4.7 — init_config: basic creation
# ===========================================================================


class TestInitConfigCreate:
    """Tests for init_config creating a new config file."""

    def test_creates_config_from_example_non_interactive(self, tmp_path: Path) -> None:
        """Non-interactive run with example must create config.json5."""
        output = tmp_path / "config.json5"
        init_config(
            EXAMPLE_JSON5,
            output,
            interactive=False,
            from_current=False,
            force=False,
        )
        assert output.exists()

    def test_output_is_valid_json5(self, tmp_path: Path) -> None:
        """Written config.json5 must parse as JSON5."""
        output = tmp_path / "config.json5"
        init_config(EXAMPLE_JSON5, output, interactive=False, from_current=False, force=False)
        content = output.read_text(encoding="utf-8")
        parsed = json5.loads(content)
        assert isinstance(parsed, dict)

    def test_exits_2_if_output_exists_without_force(self, tmp_path: Path) -> None:
        """Exit code 2 if output exists and --force not set."""
        output = tmp_path / "config.json5"
        output.write_text("{}", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            init_config(EXAMPLE_JSON5, output, interactive=False, from_current=False, force=False)
        assert exc_info.value.code == 2

    def test_force_backs_up_existing(self, tmp_path: Path) -> None:
        """--force must create .v15.bak of the existing file."""
        output = tmp_path / "config.json5"
        output.write_text('{"original": true}', encoding="utf-8")
        init_config(EXAMPLE_JSON5, output, interactive=False, from_current=False, force=True)
        bak = tmp_path / "config.json5.v15.bak"
        assert bak.exists()
        assert output.exists()

    def test_force_idempotent_second_run_overwrites_bak(self, tmp_path: Path) -> None:
        """Running --force twice must overwrite the previous .v15.bak."""
        output = tmp_path / "config.json5"
        output.write_text('{"run": 1}', encoding="utf-8")
        init_config(EXAMPLE_JSON5, output, interactive=False, from_current=False, force=True)
        # Run again: output now exists (created by first run), bak already exists.
        init_config(EXAMPLE_JSON5, output, interactive=False, from_current=False, force=True)
        bak = tmp_path / "config.json5.v15.bak"
        assert bak.exists()
        assert output.exists()


# ===========================================================================
# 4.8 — --from-current --yes without .env
# ===========================================================================


class TestInitConfigFromCurrentMissingEnv:
    """Tests for error handling when --from-current --yes lacks required .env vars."""

    def test_exits_2_missing_disk1_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exit code 2 when DISK1_DIR is absent from .env and not in env."""
        output = tmp_path / "config.json5"
        env_file = tmp_path / ".env"
        # Only STAGING_DIR and TORRENT_COMPLETE_DIR, no DISK*_DIR.
        env_file.write_text(
            f"STAGING_DIR={tmp_path}\nTORRENT_COMPLETE_DIR={tmp_path / 'complete'}\n",
            encoding="utf-8",
        )
        # Isolate from any real DISK*_DIR in the process environment.
        monkeypatch.chdir(tmp_path)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR"]:
            monkeypatch.delenv(var, raising=False)

        with pytest.raises(SystemExit) as exc_info:
            init_config(
                EXAMPLE_JSON5,
                output,
                interactive=False,
                from_current=True,
                force=False,
            )
        assert exc_info.value.code == 2

    def test_exits_2_missing_staging_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exit code 2 when STAGING_DIR is absent."""
        output = tmp_path / "config.json5"
        env_file = tmp_path / ".env"
        env_file.write_text(
            f"DISK1_DIR={tmp_path / 'disk1'}\nTORRENT_COMPLETE_DIR={tmp_path / 'complete'}\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("STAGING_DIR", raising=False)
        monkeypatch.delenv("TORRENT_COMPLETE_DIR", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            init_config(
                EXAMPLE_JSON5,
                output,
                interactive=False,
                from_current=True,
                force=False,
            )
        assert exc_info.value.code == 2

    def test_error_message_mentions_missing_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Error message must mention the missing variable."""
        output = tmp_path / "config.json5"
        (tmp_path / ".env").write_text(
            f"STAGING_DIR={tmp_path}\nTORRENT_COMPLETE_DIR={tmp_path / 'complete'}\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR"]:
            monkeypatch.delenv(var, raising=False)

        with pytest.raises(SystemExit):
            init_config(
                EXAMPLE_JSON5,
                output,
                interactive=False,
                from_current=True,
                force=False,
            )
        captured = capsys.readouterr()
        assert "DISK1_DIR" in captured.err


# ===========================================================================
# 4.7 — --from-current with valid fixture .env
# ===========================================================================


class TestInitConfigFromCurrentValid:
    """Tests for --from-current with a valid V14 .env fixture."""

    def _setup_env(self, tmp_path: Path) -> Path:
        """Create a minimal valid .env pointing to tmp_path disks.

        Args:
            tmp_path: Temporary directory for this test.

        Returns:
            Path to the created .env file.
        """
        disk1 = tmp_path / "disk1"
        disk1.mkdir()
        env_file = tmp_path / ".env"
        env_file.write_text(
            f"DISK1_DIR={disk1}\nSTAGING_DIR={tmp_path}\nTORRENT_COMPLETE_DIR={tmp_path / 'complete'}\n",
            encoding="utf-8",
        )
        return env_file

    def test_creates_config_json5(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--from-current must create config.json5 in the output path."""
        self._setup_env(tmp_path)
        output = tmp_path / "config.json5"
        monkeypatch.chdir(tmp_path)
        # Isolate from real environment to avoid picking up real DISK*_DIR.
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(
            EXAMPLE_JSON5,
            output,
            interactive=False,
            from_current=True,
            force=False,
        )
        assert output.exists()

    def test_output_has_at_least_one_disk(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Output config must have at least 1 disk from the env."""
        self._setup_env(tmp_path)
        output = tmp_path / "config.json5"
        monkeypatch.chdir(tmp_path)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, output, interactive=False, from_current=True, force=False)
        parsed = json5.loads(output.read_text(encoding="utf-8"))
        assert len(parsed["disks"]) >= 1

    def test_output_paths_set_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """paths.staging_dir must match the STAGING_DIR in .env."""
        self._setup_env(tmp_path)
        output = tmp_path / "config.json5"
        monkeypatch.chdir(tmp_path)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, output, interactive=False, from_current=True, force=False)
        parsed = json5.loads(output.read_text(encoding="utf-8"))
        assert str(tmp_path) in parsed["paths"]["staging_dir"]


# ===========================================================================
# 2.5 — _folder_to_name helper
# ===========================================================================


class TestFolderToName:
    """Tests for the _folder_to_name helper."""

    from personalscraper.commands.init_config import _folder_to_name

    def test_strips_nnn_prefix_and_lowercases(self) -> None:
        """'001-MOVIES' must yield 'movies'."""
        from personalscraper.commands.init_config import _folder_to_name

        assert _folder_to_name("001-MOVIES") == "movies"

    def test_multi_segment_name(self) -> None:
        """'002-TVSHOWS' must yield 'tvshows'."""
        from personalscraper.commands.init_config import _folder_to_name

        assert _folder_to_name("002-TVSHOWS") == "tvshows"

    def test_no_nnn_prefix_returns_lower(self) -> None:
        """Folder without NNN- prefix is lowercased as-is."""
        from personalscraper.commands.init_config import _folder_to_name

        assert _folder_to_name("MOVIES") == "movies"

    def test_three_digit_id_97(self) -> None:
        """'097-TEMP' must yield 'temp'."""
        from personalscraper.commands.init_config import _folder_to_name

        assert _folder_to_name("097-TEMP") == "temp"


# ===========================================================================
# 2.5 — _build_staging_dirs_from_env helper
# ===========================================================================


class TestBuildStagingDirsFromEnv:
    """Tests for the _build_staging_dirs_from_env helper."""

    def test_returns_8_entries(self) -> None:
        """Must always return exactly 8 entries."""
        from personalscraper.commands.init_config import _build_staging_dirs_from_env

        result = _build_staging_dirs_from_env({})
        assert len(result) == 8

    def test_canonical_defaults_when_no_env_vars(self) -> None:
        """Without legacy env vars, canonical defaults are used."""
        from personalscraper.commands.init_config import _build_staging_dirs_from_env

        result = _build_staging_dirs_from_env({})
        ids = [e["id"] for e in result]
        assert ids == [1, 2, 3, 4, 5, 6, 97, 98]
        names = [e["name"] for e in result]
        assert names == ["movies", "tvshows", "ebooks", "audio", "apps", "android", "temp", "autres"]

    def test_custom_movies_dir_name_overrides_default(self) -> None:
        """MOVIES_DIR_NAME env var must override the id=1 entry name."""
        from personalscraper.commands.init_config import _build_staging_dirs_from_env

        result = _build_staging_dirs_from_env({"MOVIES_DIR_NAME": "001-FILMS"})
        movies_entry = next(e for e in result if e["id"] == 1)
        assert movies_entry["name"] == "films"

    def test_ingest_role_preserved(self) -> None:
        """The id=97 entry must always have role='ingest'."""
        from personalscraper.commands.init_config import _build_staging_dirs_from_env

        result = _build_staging_dirs_from_env({})
        ingest = next(e for e in result if e["id"] == 97)
        assert ingest.get("role") == "ingest"

    def test_android_entry_always_android(self) -> None:
        """The id=6 entry has no env var override and is always 'android'."""
        from personalscraper.commands.init_config import _build_staging_dirs_from_env

        result = _build_staging_dirs_from_env({"APPS_DIR_NAME": "005-CUSTOM"})
        android_entry = next(e for e in result if e["id"] == 6)
        assert android_entry["name"] == "android"

    def test_file_types_correct(self) -> None:
        """file_type values must match canonical spec."""
        from personalscraper.commands.init_config import _build_staging_dirs_from_env

        result = _build_staging_dirs_from_env({})
        by_id = {e["id"]: e for e in result}
        assert by_id[1]["file_type"] == "movie"
        assert by_id[2]["file_type"] == "tvshow"
        assert by_id[97]["file_type"] is None
        assert by_id[98]["file_type"] == "other"


# ===========================================================================
# 2.5 — --from-current emits staging_dirs
# ===========================================================================


class TestInitConfigFromCurrentStagingDirs:
    """Tests that --from-current emits a staging_dirs section."""

    def _setup_env(self, tmp_path: Path) -> None:
        """Create a minimal valid .env in tmp_path.

        Args:
            tmp_path: Temporary directory for this test.
        """
        disk1 = tmp_path / "disk1"
        disk1.mkdir()
        (tmp_path / ".env").write_text(
            f"DISK1_DIR={disk1}\nSTAGING_DIR={tmp_path}\nTORRENT_COMPLETE_DIR={tmp_path / 'complete'}\n",
            encoding="utf-8",
        )

    def test_from_current_emits_staging_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--from-current must emit a staging_dirs section with 8 entries."""
        self._setup_env(tmp_path)
        output = tmp_path / "config.json5"
        monkeypatch.chdir(tmp_path)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, output, interactive=False, from_current=True, force=False)
        parsed = json5.loads(output.read_text(encoding="utf-8"))

        assert "staging_dirs" in parsed, "staging_dirs section must be present in generated config"
        assert len(parsed["staging_dirs"]) == 8, "staging_dirs must have exactly 8 entries"

    def test_from_current_staging_dirs_has_correct_ids(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """staging_dirs entries must have ids 1-6, 97, 98."""
        self._setup_env(tmp_path)
        output = tmp_path / "config.json5"
        monkeypatch.chdir(tmp_path)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, output, interactive=False, from_current=True, force=False)
        parsed = json5.loads(output.read_text(encoding="utf-8"))
        ids = sorted(e["id"] for e in parsed["staging_dirs"])
        assert ids == [1, 2, 3, 4, 5, 6, 97, 98]

    def test_from_current_respects_custom_dir_name_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MOVIES_DIR_NAME in .env must override the movies staging entry name."""
        disk1 = tmp_path / "disk1"
        disk1.mkdir()
        (tmp_path / ".env").write_text(
            f"DISK1_DIR={disk1}\nSTAGING_DIR={tmp_path}\n"
            f"TORRENT_COMPLETE_DIR={tmp_path / 'complete'}\n"
            "MOVIES_DIR_NAME=001-FILMS\n",
            encoding="utf-8",
        )
        output = tmp_path / "config.json5"
        monkeypatch.chdir(tmp_path)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, output, interactive=False, from_current=True, force=False)
        parsed = json5.loads(output.read_text(encoding="utf-8"))
        movies = next(e for e in parsed["staging_dirs"] if e["id"] == 1)
        assert movies["name"] == "films"
