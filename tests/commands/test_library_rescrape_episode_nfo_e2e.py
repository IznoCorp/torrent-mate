"""E2E: ``library-rescrape --only nfo`` repairs episode NFOs (absent, empty, unreadable).

A tmp library with one TV show whose episodes cover every NFO state; providers are
mocked. ``--dry-run`` must leave the library byte-identical and list what it would write.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from personalscraper.api.metadata._base import EpisodeInfo, SeasonDetails
from tests.commands._e2e_helpers import fs_snapshot, mock_tmdb_client, mock_tvdb_client, run_cli

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"

_TVSHOW_NFO = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<tvshow><title>Show</title><uniqueid type="tvdb">121361</uniqueid></tvshow>\n'
)
_GOOD_EPISODE_NFO = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    "<episodedetails><title>Kept</title><season>1</season><episode>4</episode>"
    '<uniqueid type="tvdb">1</uniqueid></episodedetails>\n'
)
_TITLES = {1: "One", 2: "Two", 3: "Three", 4: "Four"}


def _build_show(disk_base: Path) -> Path:
    """Create ``Show (2008)`` with E01 no NFO, E02 empty, E03 truncated, E04 conformant."""
    show = disk_base / "cat_tv_shows" / "Show (2008)"
    season = show / "Saison 01"
    season.mkdir(parents=True)
    (show / "tvshow.nfo").write_text(_TVSHOW_NFO)
    (show / "poster.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    for n, title in _TITLES.items():
        (season / f"Show - S01E0{n} - {title}.mkv").write_bytes(b"x")
    (season / "Show - S01E02 - Two.nfo").write_bytes(b"")
    (season / "Show - S01E03 - Three.nfo").write_text("<episodedetails><title>Thr")
    (season / "Show - S01E04 - Four.nfo").write_text(_GOOD_EPISODE_NFO)
    return show


def _mock_providers(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / ".data").mkdir(exist_ok=True)
    mock_tmdb_client(monkeypatch)
    tvdb = mock_tvdb_client(monkeypatch)
    tvdb.get_series_episodes.return_value = SeasonDetails(
        provider="tvdb",
        tv_id="121361",
        season_number=1,
        episodes=[
            EpisodeInfo(episode_number=n, title=t, overview="", season_number=1, external_ids={"tvdb": str(900 + n)})
            for n, t in _TITLES.items()
        ],
    )


def _run(test_config, *args: str):
    with patch(_PATCH_LOAD_CONFIG, return_value=test_config):
        return run_cli(["library-rescrape", "--only", "nfo", *args])


def test_dry_run_lists_episode_nfos_and_writes_nothing(tmp_path, test_config, monkeypatch) -> None:
    """--dry-run: library byte-identical, the three broken episode NFOs listed in the report."""
    _mock_providers(monkeypatch, tmp_path)
    disk_base = tmp_path / "drive_a"
    _build_show(disk_base)
    before = fs_snapshot(disk_base)

    result = _run(test_config, "--dry-run")

    assert result.exit_code == 0, result.output
    assert fs_snapshot(disk_base) == before
    data = json.loads((tmp_path / ".data" / "library_rescrape.json").read_text())
    actions = [a for item in data["items"] for a in item["actions_taken"]]
    assert sorted(actions) == [
        "episode_nfo_regenerated: Saison 01/Show - S01E01 - One.nfo",
        "episode_nfo_regenerated: Saison 01/Show - S01E02 - Two.nfo",
        "episode_nfo_regenerated: Saison 01/Show - S01E03 - Three.nfo",
    ]
    assert data["error_count"] == 0, data


def test_live_run_regenerates_absent_empty_and_unreadable_only(tmp_path, test_config, monkeypatch) -> None:
    """Live: E01-E03 get a parseable NFO next to the video; the conformant E04 is untouched."""
    _mock_providers(monkeypatch, tmp_path)
    show = _build_show(tmp_path / "drive_a")
    season = show / "Saison 01"

    result = _run(test_config)

    assert result.exit_code == 0, result.output
    for n in (1, 2, 3):
        root = ET.parse(season / f"Show - S01E0{n} - {_TITLES[n]}.nfo").getroot()  # noqa: S314
        assert root.tag == "episodedetails"
        assert root.findtext("title") == _TITLES[n]
    assert (season / "Show - S01E04 - Four.nfo").read_text() == _GOOD_EPISODE_NFO

    # Idempotent: a second run finds nothing to repair.
    again = _run(test_config, "--dry-run")
    assert again.exit_code == 0, again.output
    data = json.loads((tmp_path / ".data" / "library_rescrape.json").read_text())
    assert data["items"] == []
