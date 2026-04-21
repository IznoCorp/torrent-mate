"""E2E test for init-config --from-current full V14 → V15 migration.

Sets up a realistic V14 staging structure in a tmp_path, runs init_config
with from_current=True, and asserts the full set of migration outcomes:
- config.json5 created and loadable
- .personalscraper/ moved to .data/
- library_*.json rewritten with V15 IDs
- .category files removed, NFOs updated
- semantic equivalence: disks, categories, paths match the V14 source
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from personalscraper.commands.init_config import init_config
from personalscraper.conf.ids import BUILTIN_CATEGORY_IDS
from personalscraper.conf.loader import load_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXAMPLE_JSON5 = Path(__file__).parent.parent.parent / "config.example.json5"


def _make_nfo(directory: Path, filename: str = "movie.nfo") -> Path:
    """Create a minimal NFO file in *directory*.

    Args:
        directory: Target directory.
        filename: NFO filename.

    Returns:
        Path to the created NFO file.
    """
    nfo = directory / filename
    nfo.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<movie>\n"
        "  <title>Test Media</title>\n"
        "  <genre>Action</genre>\n"
        "</movie>\n",
        encoding="utf-8",
    )
    return nfo


def _make_library_index(data_dir: Path) -> None:
    """Create a minimal library_index.json with V14 labels.

    Args:
        data_dir: Directory to write the file into.
    """
    data = {
        "scanned_at": "2024-01-01T00:00:00+00:00",
        "disk_filter": None,
        "category_filter": None,
        "item_count": 2,
        "items": [
            {"path": "/Volumes/Disk1/films/Movie A (2020)", "disk": "Disk1", "category": "films"},
            {"path": "/Volumes/Disk1/series/Show B", "disk": "Disk1", "category": "series"},
        ],
    }
    (data_dir / "library_index.json").write_text(json.dumps(data), encoding="utf-8")


def _make_library_preferences(data_dir: Path) -> None:
    """Create a library_preferences.json with V14 structure.

    Args:
        data_dir: Directory to write the file into.
    """
    prefs = {
        "video": {
            "preferred_codec": "hevc",
            "fallback_codecs": ["av1"],
            "rejected_codecs": ["mpeg2", "mpeg4"],
            "preferred_resolution": "1080p",
            "max_size_movie_gb": 4.0,
            "max_size_episode_gb": 2.0,
        },
        "audio": {
            "profile_priority": ["multi", "vf", "vostfr", "vo"],
            "min_channels": 2,
            "preferred_codec": None,
        },
        "subtitles": {
            "required_languages": ["fra"],
            "preferred_languages": ["fra", "eng"],
            "warn_if_missing": True,
        },
        "encoding_rules": [],
    }
    (data_dir / "library_preferences.json").write_text(json.dumps(prefs), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def v14_staging(tmp_path: Path) -> dict[str, Path]:
    """Build a complete V14 staging structure in tmp_path.

    Structure created:
    - tmp_path/.env              — V14 env with DISK1_DIR, STAGING_DIR, etc.
    - tmp_path/.personalscraper/ — V14 data dir with library_*.json + prefs
    - tmp_path/films/Inception (2010)/.category + movie.nfo
    - tmp_path/series/Breaking Bad/.category + tvshow.nfo
    - tmp_path/spectacles/Dave Chappelle/.category + movie.nfo
    - tmp_path/disk1/            — fake disk mount point

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Dict with named paths: staging, output, disk1, data_dir.
    """
    staging = tmp_path
    disk1 = tmp_path / "disk1"
    disk1.mkdir()

    # Write .env
    env_content = f"DISK1_DIR={disk1}\nSTAGING_DIR={staging}\nTORRENT_COMPLETE_DIR={tmp_path / 'complete'}\n"
    (staging / ".env").write_text(env_content, encoding="utf-8")

    # Create V14 data dir
    data_dir = staging / ".personalscraper"
    data_dir.mkdir()
    _make_library_index(data_dir)
    _make_library_preferences(data_dir)

    # Create media directories with .category + NFO
    for folder, label, nfo_name in [
        ("films/Inception (2010)", "films", "movie.nfo"),
        ("series/Breaking Bad", "series", "tvshow.nfo"),
        ("spectacles/Dave Chappelle (2020)", "spectacles", "movie.nfo"),
    ]:
        media_dir = staging / folder
        media_dir.mkdir(parents=True)
        _make_nfo(media_dir, nfo_name)
        (media_dir / ".category").write_text(label, encoding="utf-8")

    output = staging / "config.json5"
    return {
        "staging": staging,
        "output": output,
        "disk1": disk1,
        "data_dir": staging / ".data",
    }


# ---------------------------------------------------------------------------
# E2E tests
# ---------------------------------------------------------------------------


class TestInitConfigE2E:
    """Full E2E tests for init-config --from-current migration."""

    def test_config_json5_created(self, v14_staging: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
        """config.json5 must be created after migration."""
        monkeypatch.chdir(v14_staging["staging"])
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, v14_staging["output"], interactive=False, from_current=True, force=False)
        assert v14_staging["output"].exists()

    def test_load_config_passes(self, v14_staging: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
        """load_config() must succeed on the generated config.json5."""
        monkeypatch.chdir(v14_staging["staging"])
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, v14_staging["output"], interactive=False, from_current=True, force=False)
        cfg = load_config(v14_staging["output"])
        assert cfg is not None

    def test_data_dir_moved(self, v14_staging: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
        """.personalscraper/ must be moved to .data/ after migration."""
        staging = v14_staging["staging"]
        monkeypatch.chdir(staging)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, v14_staging["output"], interactive=False, from_current=True, force=False)
        assert not (staging / ".personalscraper").exists()
        assert (staging / ".data").exists()

    def test_library_index_labels_rewritten(
        self, v14_staging: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """library_index.json must have V15 IDs after migration."""
        staging = v14_staging["staging"]
        monkeypatch.chdir(staging)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, v14_staging["output"], interactive=False, from_current=True, force=False)

        index_path = staging / ".data" / "library_index.json"
        assert index_path.exists()
        data = json.loads(index_path.read_text(encoding="utf-8"))
        for item in data["items"]:
            assert item["category"] in BUILTIN_CATEGORY_IDS, f"Category '{item['category']}' is not a builtin V15 ID"

    def test_library_index_backup_created(self, v14_staging: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
        """library_index.json.v14.bak must exist after migration."""
        staging = v14_staging["staging"]
        monkeypatch.chdir(staging)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, v14_staging["output"], interactive=False, from_current=True, force=False)
        bak = staging / ".data" / "library_index.json.v14.bak"
        assert bak.exists()

    def test_library_preferences_merged_into_config(
        self, v14_staging: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Library preferences must be present in config.library after migration."""
        staging = v14_staging["staging"]
        monkeypatch.chdir(staging)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, v14_staging["output"], interactive=False, from_current=True, force=False)
        cfg = load_config(v14_staging["output"])
        assert cfg.library.video.preferred_codec == "hevc"
        assert cfg.library.subtitles.required_languages == ["fra"]

    def test_category_files_deleted(self, v14_staging: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
        """.category files must be deleted after NFO migration."""
        staging = v14_staging["staging"]
        monkeypatch.chdir(staging)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, v14_staging["output"], interactive=False, from_current=True, force=False)
        remaining = list(staging.rglob(".category"))
        assert remaining == [], f".category files not deleted: {remaining}"

    def test_nfo_contains_category_element(self, v14_staging: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
        """NFOs must contain <category source="personalscraper"> after migration."""
        staging = v14_staging["staging"]
        monkeypatch.chdir(staging)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, v14_staging["output"], interactive=False, from_current=True, force=False)

        nfo = staging / "films" / "Inception (2010)" / "movie.nfo"
        root = ET.parse(nfo).getroot()  # noqa: S314
        cat_els = [el for el in root.iter("category") if el.get("source") == "personalscraper"]
        assert len(cat_els) == 1
        assert cat_els[0].text == "movies"

    def test_standup_nfo_category_element(self, v14_staging: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
        """Spectacles → standup mapping must appear in NFO."""
        staging = v14_staging["staging"]
        monkeypatch.chdir(staging)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, v14_staging["output"], interactive=False, from_current=True, force=False)

        nfo = staging / "spectacles" / "Dave Chappelle (2020)" / "movie.nfo"
        root = ET.parse(nfo).getroot()  # noqa: S314
        cat_els = [el for el in root.iter("category") if el.get("source") == "personalscraper"]
        assert len(cat_els) == 1
        assert cat_els[0].text == "standup"

    def test_config_has_disk1(self, v14_staging: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
        """Config must have disk_1 pointing to DISK1_DIR from .env."""
        staging = v14_staging["staging"]
        monkeypatch.chdir(staging)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, v14_staging["output"], interactive=False, from_current=True, force=False)
        cfg = load_config(v14_staging["output"])
        disk_ids = [d.id for d in cfg.disks]
        assert "disk_1" in disk_ids

    def test_config_disk1_path_matches_env(self, v14_staging: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
        """disk_1.path must match DISK1_DIR from .env."""
        staging = v14_staging["staging"]
        monkeypatch.chdir(staging)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, v14_staging["output"], interactive=False, from_current=True, force=False)
        cfg = load_config(v14_staging["output"])
        disk1 = next(d for d in cfg.disks if d.id == "disk_1")
        assert disk1.path == v14_staging["disk1"]

    def test_config_categories_use_v14_folder_names(
        self, v14_staging: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Category folder_names must be V14 French labels (preserve on-disk names)."""
        staging = v14_staging["staging"]
        monkeypatch.chdir(staging)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        init_config(EXAMPLE_JSON5, v14_staging["output"], interactive=False, from_current=True, force=False)
        cfg = load_config(v14_staging["output"])
        # The movies category must have folder_name "films" (V14 label).
        assert cfg.category("movies").folder_name == "films"
        assert cfg.category("standup").folder_name == "spectacles"

    def test_idempotent_with_force(self, v14_staging: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
        """Running --force after first run must overwrite config and backup."""
        staging = v14_staging["staging"]
        monkeypatch.chdir(staging)
        for var in ["DISK1_DIR", "DISK2_DIR", "DISK3_DIR", "DISK4_DIR", "STAGING_DIR", "TORRENT_COMPLETE_DIR"]:
            monkeypatch.delenv(var, raising=False)

        # First run.
        init_config(EXAMPLE_JSON5, v14_staging["output"], interactive=False, from_current=True, force=False)
        assert v14_staging["output"].exists()

        # Second run with --force: config exists but .data already moved so
        # use from_current=False to avoid re-running migrations.
        init_config(EXAMPLE_JSON5, v14_staging["output"], interactive=False, from_current=False, force=True)
        bak = staging / "config.json5.v15.bak"
        assert bak.exists()
        assert v14_staging["output"].exists()
