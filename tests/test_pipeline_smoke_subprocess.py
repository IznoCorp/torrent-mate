"""Fresh-shell pipeline smoke tests — subprocess realism layer.

These tests are the regression net that **all** the api-unify bugs
fixed in phase 27 commits 1-6 should have been caught by. They run
``personalscraper`` as a subprocess in a stripped-down environment
(only PATH + a temporary HOME and PYTHONPATH) so:

1. The CLI must exercise its own ``load_dotenv()`` bootstrap (BUG #5).
2. The configuration loader must run against actual ``config/*.json5``
   files on disk, not against pytest mocks (BUG #1).
3. The legacy QBIT_HOST/QBIT_PORT env-var deprecation warning fires
   when those legacy vars are set (BUG #6).
4. The provider activation surface and CLI command-tree print the
   expected commands without hitting any ``AttributeError`` from
   typed-vs-dict mismatches (BUGS #8, #10, #11).

Each test is fast (~0.4-1s) because we only invoke ``personalscraper info``
or ``personalscraper --version``, both of which load the config but do
not hit any external API.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _python_path() -> str:
    """Build a PYTHONPATH that includes the repo root + this Python's site-packages.

    The fresh-shell tests run with ``env -i``-style cleared environment,
    so we need to manually surface the import path so ``personalscraper``
    and its third-party dependencies (typer, dotenv, pydantic, ...) can
    be imported.
    """
    return ":".join([str(REPO_ROOT), *(p for p in sys.path if p)])


def _make_minimal_config(tmp_path: Path) -> Path:
    """Copy ``config.example/`` into *tmp_path* / ``config`` and stamp paths.

    Produces a self-contained, valid config directory that the loader
    accepts. Disks point at ``tmp_path`` subdirs so the staged data
    directories pass the existence checks.
    """
    src = REPO_ROOT / "config.example"
    dst = tmp_path / "config"
    shutil.copytree(src, dst)

    # Rewrite paths.json5 to use tmp_path
    (tmp_path / "torrents").mkdir()
    (tmp_path / "staging").mkdir()
    paths_file = dst / "paths.json5"
    paths_file.write_text(
        "{\n"
        "  paths: {\n"
        f'    torrent_complete_dir: "{tmp_path / "torrents"}",\n'
        f'    staging_dir: "{tmp_path / "staging"}",\n'
        f'    data_dir: "{tmp_path / ".data"}",\n'
        "  },\n"
        "}\n",
        encoding="utf-8",
    )

    # Rewrite disks.json5 to point at tmp_path/disk_a so disk presence checks pass.
    disk_dir = tmp_path / "disk_a"
    disk_dir.mkdir()
    disks_file = dst / "disks.json5"
    disks_file.write_text(
        "{\n"
        "  disks: [\n"
        "    {\n"
        '      id: "disk_a",\n'
        f'      path: "{disk_dir}",\n'
        '      categories: ["movies", "tv_shows", "movies_animation", "tv_shows_animation",\n'
        '                   "movies_documentary", "tv_shows_documentary", "anime",\n'
        '                   "standup", "theater", "tv_programs", "audiobooks"],\n'
        "    },\n"
        "  ],\n"
        "}\n",
        encoding="utf-8",
    )

    # The default categories.json5 uses 11 builtin IDs that match the disks list.
    return dst


@pytest.fixture
def fresh_env(tmp_path: Path) -> Iterator[tuple[Path, dict[str, str]]]:
    """Build a stripped-down env + a self-contained config directory.

    Yields ``(config_dir, env_dict)`` where:
    - ``config_dir`` is a temp dir holding a complete ``config/`` tree
      from ``config.example/`` with paths/disks rewritten to tmp_path.
    - ``env_dict`` is a minimal env (PATH, HOME, PYTHONPATH only) plus
      the bare-minimum credentials any provider activation step needs.
    """
    config_dir = _make_minimal_config(tmp_path)

    # Provide minimum credentials so provider activation does not warn
    # about missing required vars on the always-on providers (TMDB,
    # TVDB, qBittorrent). Real values are not needed — provider clients
    # are not invoked by ``info`` or ``--version``.
    env: dict[str, str] = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
        "PYTHONPATH": _python_path(),
        "HOME": str(tmp_path),
        "TMDB_API_KEY": "fake-tmdb-key",
        "TVDB_API_KEY": "fake-tvdb-key",
        "QBIT_USERNAME": "fake",
        "QBIT_PASSWORD": "fake",
    }
    yield config_dir, env


def _run(args: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a personalscraper invocation in a fresh subprocess.

    Invokes the CLI via ``python -c "from personalscraper.cli import app; app()"``
    instead of ``python -m personalscraper`` because the package does not
    ship a ``__main__.py`` (the entry point is the typer ``app`` registered
    via ``pyproject.toml`` scripts). The ``-c`` form mimics what the
    installed ``personalscraper`` binary does at runtime.
    """
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from personalscraper.cli import app; app()",
            *args,
        ],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


class TestFreshShellSmoke:
    """Smoke tests that exercise the production startup path."""

    def test_info_command_succeeds_with_config_only_no_env_creds_exported(
        self, fresh_env: tuple[Path, dict[str, str]]
    ) -> None:
        """``personalscraper info`` runs cleanly when config + .env on disk only.

        Regression for BUG #5: pre-fix the CLI never called load_dotenv()
        and would crash with "Missing required credentials" because no
        provider could resolve env vars from a .env file alone.
        """
        config_dir, env = fresh_env

        # Write a .env in the cwd containing the creds — no exported env vars.
        env_file = config_dir.parent / ".env"
        env_file.write_text(
            "TMDB_API_KEY=from-env-file\n"
            "TVDB_API_KEY=from-env-file\n"
            "QBIT_USERNAME=from-env-file\n"
            "QBIT_PASSWORD=from-env-file\n",
            encoding="utf-8",
        )
        env_no_creds = {k: v for k, v in env.items() if k in {"PATH", "PYTHONPATH", "HOME"}}

        result = _run(
            ["--config", str(config_dir), "info"],
            env=env_no_creds,
            cwd=config_dir.parent,
        )
        assert result.returncode == 0, f"info failed:\nstdout={result.stdout}\nstderr={result.stderr}"
        # ``info`` always prints the disk lines if config loaded.
        assert "Disks" in result.stdout

    def test_version_command_runs_without_config(self, fresh_env: tuple[Path, dict[str, str]]) -> None:
        """``--version`` doesn't load config; must succeed with empty env."""
        _, env = fresh_env
        env_minimal = {k: v for k, v in env.items() if k in {"PATH", "PYTHONPATH", "HOME"}}

        result = _run(["--version"], env=env_minimal, cwd=Path.cwd())
        assert result.returncode == 0, f"version failed: {result.stderr}"
        # Typer prints just the version string by default (e.g. "0.11.0").
        # Check that it looks like a SemVer-ish identifier rather than empty.
        assert result.stdout.strip()
        assert "." in result.stdout

    def test_legacy_qbit_env_emits_deprecation_warning(self, fresh_env: tuple[Path, dict[str, str]]) -> None:
        """Setting QBIT_HOST / QBIT_PORT in env triggers the migration warning.

        Regression for BUG #6: pre-fix these legacy vars were silently
        ignored by the new code path (they used to feed the legacy
        Settings(BaseSettings)). The phase-27 loader emits a warning so
        users running ``personalscraper info`` immediately see they need
        to migrate to ``config/torrent.json5``.
        """
        config_dir, env = fresh_env
        env["QBIT_HOST"] = "localhost"
        env["QBIT_PORT"] = "8081"

        result = _run(
            ["--config", str(config_dir), "info"],
            env=env,
            cwd=config_dir.parent,
        )
        assert result.returncode == 0, f"info failed:\nstdout={result.stdout}\nstderr={result.stderr}"
        # Warning lands on stderr (structlog default).
        combined = result.stdout + result.stderr
        assert "legacy env vars ignored" in combined
        assert "QBIT_HOST" in combined or "QBIT_PORT" in combined

    def test_no_legacy_env_no_deprecation_warning(self, fresh_env: tuple[Path, dict[str, str]]) -> None:
        """Clean env (no legacy vars) → no migration warning emitted."""
        config_dir, env = fresh_env
        # Strip any inherited QBIT_HOST / QBIT_PORT
        env.pop("QBIT_HOST", None)
        env.pop("QBIT_PORT", None)

        result = _run(
            ["--config", str(config_dir), "info"],
            env=env,
            cwd=config_dir.parent,
        )
        assert result.returncode == 0
        combined = result.stdout + result.stderr
        assert "legacy env vars ignored" not in combined


class TestImportSmoke:
    """Bare ``import personalscraper`` in a fresh interpreter must succeed."""

    def test_import_loads_dotenv_into_environ(self, tmp_path: Path) -> None:
        """Importing ``personalscraper`` must populate os.environ from .env.

        Regression for BUG #5: this is the same contract as
        tests/test_dotenv_bootstrap.py but exercised in a different
        location to make sure it survives downstream test reorganisation.
        """
        env_file = tmp_path / ".env"
        env_file.write_text("PHASE27_SMOKE_SENTINEL=value-from-disk\n", encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import os; import personalscraper; print(os.environ.get('PHASE27_SMOKE_SENTINEL', '<MISSING>'))",
            ],
            cwd=tmp_path,
            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": _python_path(), "HOME": str(tmp_path)},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, f"import failed: {result.stderr}"
        assert "value-from-disk" in result.stdout

    def test_typed_models_construct_without_errors(self, tmp_path: Path) -> None:
        """All phase-27 typed models can be instantiated with their defaults.

        Regression for the model-extension layer (commit 1): if a frozen
        dataclass field had been mis-declared (e.g. mutable default
        instead of default_factory), this test would fail at import time
        rather than ten layers deep in the pipeline.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from personalscraper.api.metadata._base import "
                "ArtworkItem, EpisodeInfo, MediaDetails, SearchResult, "
                "SeasonDetails, SeasonInfo; "
                "import json; "
                "print(json.dumps({"
                "'mediadetails': MediaDetails(provider='x', provider_id='1').seasons == [], "
                "'episodeinfo': EpisodeInfo(episode_number=1).season_number == 0, "
                "'searchresult': SearchResult(provider='x', provider_id='1', title='x').original_title == '', "
                "'artwork': ArtworkItem(type='poster', url='').vote_average == 0.0, "
                "'seasoninfo': SeasonInfo(season_number=1).episode_count == 0, "
                "}))",
            ],
            cwd=tmp_path,
            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": _python_path(), "HOME": str(tmp_path)},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, f"models failed to construct: {result.stderr}"
        out = json.loads(result.stdout.strip())
        # Every default invariant holds.
        assert all(out.values()), out
