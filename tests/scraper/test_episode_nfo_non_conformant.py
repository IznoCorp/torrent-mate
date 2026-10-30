"""An existing but non-conformant episode NFO is rewritten, never skipped."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from personalscraper.scraper.nfo_generator import NFOGenerator
from tests.scraper.test_regression_dev2_episode_ids import _make_mixin

_GOOD = '<?xml version="1.0"?><episodedetails><title>Kept</title><uniqueid type="tvdb">9001</uniqueid></episodedetails>'


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
    [b"", b"<episodedetails><title>cut", b"<movie><title>X</title></movie>"],
    ids=["empty", "truncated", "wrong-root"],
)
def test_non_conformant_existing_nfo_is_rewritten(tmp_path: Path, content: bytes) -> None:
    """Empty, unparseable and wrong-root NFOs are regenerated like an absent one."""
    nfo_path, _ = _run(tmp_path, content)
    root = ET.parse(nfo_path).getroot()  # noqa: S314
    assert root.tag == "episodedetails"
    assert root.findtext("title") == "Pilot"


def test_conformant_existing_nfo_is_upgraded_not_rewritten(tmp_path: Path) -> None:
    """A conformant NFO keeps its content (upgrade-in-place only)."""
    nfo_path, _ = _run(tmp_path, _GOOD.encode())
    assert ET.parse(nfo_path).getroot().findtext("title") == "Kept"  # noqa: S314


def test_absent_nfo_is_written(tmp_path: Path) -> None:
    """Sanity: an absent NFO is still generated."""
    nfo_path, _ = _run(tmp_path, None)
    assert ET.parse(nfo_path).getroot().findtext("title") == "Pilot"  # noqa: S314
