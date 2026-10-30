"""An existing but non-conformant episode NFO is rewritten, never skipped."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from personalscraper.scraper.nfo_generator import NFOGenerator
from tests.scraper.test_regression_dev2_episode_ids import _make_mixin

_GOOD = (
    '<?xml version="1.0"?><episodedetails><title>Kept</title><season>1</season><episode>1</episode>'
    '<uniqueid type="tvdb">9001</uniqueid></episodedetails>'
)


def _run(tmp_path: Path, content: bytes | None) -> tuple[Path, Any]:
    show_dir = tmp_path / "Show"
    season_dir = show_dir / "Saison 01"
    season_dir.mkdir(parents=True)
    video = show_dir / "Show.S01E01.mkv"
    video.write_bytes(b"x")
    mixin = _make_mixin()
    mixin._nfo = NFOGenerator()  # type: ignore[assignment]
    mixin.dry_run = False
    matched = {
        video: {
            "season": 1,
            "episode": 1,
            "api_title": "Pilot",
            "still_path": "",
            "fallback": False,
            "tvdb_episode_id": "9001",
            "tmdb_episode_id": "5555",
        }
    }
    nfo_path = None
    # Pre-create the NFO at the name the scraper will compute.
    from personalscraper.naming_patterns import PATTERNS

    stem = PATTERNS.format("episode_video", Season=1, Episode=1, EpisodeTitle="Pilot")
    nfo_path = season_dir / f"{stem}.nfo"
    if content is not None:
        nfo_path.write_bytes(content)
    mixin._generate_episode_nfos(matched, show_dir, {"name": "Show", "networks": []})
    return nfo_path, mixin


@pytest.mark.parametrize(
    "content",
    [b"", b"<episodedetails><title>cut", b"<movie><title>X</title></movie>", b"<episodedetails/>"],
    ids=["empty", "truncated", "wrong-root", "root-only"],
)
def test_unusable_existing_nfo_is_rewritten(tmp_path: Path, content: bytes) -> None:
    """Empty, unparseable and wrong-root NFOs are regenerated like an absent one."""
    nfo_path, _ = _run(tmp_path, content)
    root = ET.parse(nfo_path).getroot()  # noqa: S314
    assert root.tag == "episodedetails"
    assert root.findtext("title") == "Pilot"


def test_usable_existing_nfo_is_upgraded_not_rewritten(tmp_path: Path) -> None:
    """A conformant NFO keeps its content and gains the missing xref id (upgrade-in-place)."""
    nfo_path, _ = _run(tmp_path, _GOOD.encode())
    root = ET.parse(nfo_path).getroot()  # noqa: S314
    assert root.findtext("title") == "Kept"
    ids = {u.get("type"): u.text for u in root.findall("uniqueid")}
    assert ids == {"tvdb": "9001", "tmdb": "5555"}


def test_absent_nfo_is_written(tmp_path: Path) -> None:
    """Sanity: an absent NFO is still generated."""
    nfo_path, _ = _run(tmp_path, None)
    assert ET.parse(nfo_path).getroot().findtext("title") == "Pilot"  # noqa: S314


def _season_pack_nfo(tmp_path: Path, content: bytes | None) -> Path:
    """Run the season-pack NFO writer over a show dir holding ``content`` at the range NFO path."""
    from personalscraper.naming_patterns import PATTERNS

    show_dir = tmp_path / "Show"
    season_dir = show_dir / PATTERNS.format("season_dir", Season=1)
    season_dir.mkdir(parents=True)
    video = show_dir / "Show.S01.COMPLETE.mkv"
    video.write_bytes(b"x")
    mixin = _make_mixin()
    mixin._nfo = NFOGenerator()  # type: ignore[assignment]
    mixin.dry_run = False
    info = {
        "season": 1,
        "episode": 1,
        "episode_end": 2,
        "api_title": "Pilot",
        "still_path": "",
        "is_season_pack": True,
    }
    stem = PATTERNS.format("episode_video_range", Season=1, EpisodeStart=1, EpisodeEnd=2, EpisodeTitle="Pilot")
    nfo_path = season_dir / f"{stem}.nfo"
    if content is not None:
        nfo_path.write_bytes(content)
    mixin._generate_season_pack_nfo(video, info, show_dir, "Show", "", "")
    return nfo_path


@pytest.mark.parametrize(
    "content",
    [b"", b"<movie><title>X</title></movie>"],
    ids=["empty", "wrong-root"],
)
def test_season_pack_unusable_nfo_is_regenerated(tmp_path: Path, content: bytes) -> None:
    """An empty or foreign-root season-pack NFO is rewritten, not skipped as existing."""
    nfo_path = _season_pack_nfo(tmp_path, content)
    root = ET.parse(nfo_path).getroot()  # noqa: S314
    assert root.tag == "episodedetails"
    assert root.findtext("title") == "Pilot"


def test_season_pack_usable_nfo_is_kept(tmp_path: Path) -> None:
    """A conformant season-pack NFO is left byte-identical."""
    nfo_path = _season_pack_nfo(tmp_path, _GOOD.encode())
    assert nfo_path.read_bytes() == _GOOD.encode()


def test_usable_multi_root_nfo_is_left_alone_without_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """The xref upgrade reads a single root: a multi-root NFO is skipped, no parse warning, file unchanged."""
    content = (
        "<episodedetails><title>A</title><season>1</season><episode>1</episode></episodedetails>\n"
        "<episodedetails><title>B</title><season>1</season><episode>2</episode></episodedetails>\n"
    ).encode()
    with caplog.at_level("DEBUG"):
        nfo_path, _ = _run(tmp_path, content)
    assert nfo_path.read_bytes() == content
    assert "xref_nfo_augment_parse_failed" not in caplog.text
