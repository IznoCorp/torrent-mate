"""Shared tracker title-quality parser — symmetry across lacale/c411/torr9.

TORRENT-TRACKERS-03: the three tracker clients encode quality markers
(resolution, codec, source, audio, container format) in the release *title*,
not as structured fields. They now all feed the single shared parser
:func:`personalscraper.api.tracker._quality.parse_title_quality`. Before this,
torr9 parsed nothing (all quality fields left ``None``) and c411 reached across
the family boundary into ``LaCaleClient._parse_title``.

These tests prove (a) the parser extracts the expected tokens and (b) each
client's ``_parse_item`` surfaces the SAME tokens on a shared title fixture —
in particular torr9, which previously dropped them.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from personalscraper.api.tracker._quality import parse_title_quality
from personalscraper.api.tracker.c411 import C411Client
from personalscraper.api.tracker.lacale import LaCaleClient
from personalscraper.api.tracker.torr9 import Torr9Client
from personalscraper.core.event_bus import EventBus

# Shared title fixtures spanning the token families the ranker consumes.
_SHARED_TITLES = [
    "Inception.2010.MULTi.TRUEFRENCH.HDR.2160p.UHD.BluRay.DTS-HD.MA.5.1.H265-XANTAR",
    "The.Robot.Wild.2024.MULTi.1080p.WEB-DL.DDP5.1.x265-GROUP",
    "Some.Show.S01E02.720p.HDTV.x264-AAC",
    "Random.title.no.metadata",
]

# Fields the shared parser owns and every client must surface identically.
_QUALITY_FIELDS = ("resolution", "codec", "source", "audio", "format")


def _torr9_result_quality(title: str) -> dict[str, str | None]:
    client = Torr9Client(username="u", password="p", event_bus=EventBus())
    r = client._parse_item({"title": title, "id": "1", "file_size_bytes": 100})
    return {f: getattr(r, f) for f in _QUALITY_FIELDS}


def _lacale_result_quality(title: str) -> dict[str, str | None]:
    client = LaCaleClient(MagicMock())
    r = client._parse_item({"title": title, "guid": "g", "size": 100})
    return {f: getattr(r, f) for f in _QUALITY_FIELDS}


def _c411_result_quality(title: str) -> dict[str, str | None]:
    client = C411Client(MagicMock())
    r = client._parse_item({"title": title, "guid": "hash"})
    return {f: getattr(r, f) for f in _QUALITY_FIELDS}


class TestTrackerQualityParser:
    """Direct coverage of the shared token table."""

    def test_full_quality_title_all_fields(self) -> None:
        """A UHD BluRay title yields resolution+codec+source+audio."""
        out = parse_title_quality("Inception.2010.2160p.BluRay.DTS-HD.H265-XANTAR")
        assert out["resolution"] == "2160p"
        assert out["codec"] == "H265"
        assert out["source"] is not None and "bluray" in out["source"].lower()
        assert out["audio"] == "DTS-HD"

    def test_web_dl_x265(self) -> None:
        """A 1080p WEB-DL x265 title yields resolution+codec+source."""
        out = parse_title_quality("Movie.2024.1080p.WEB-DL.DDP5.1.x265-GRP")
        assert out["resolution"] == "1080p"
        assert out["codec"] == "x265"
        assert out["source"] is not None and "web" in out["source"].lower()

    def test_no_markers_all_none(self) -> None:
        """A title with no recognizable markers yields all-None fields."""
        assert parse_title_quality("Random.title.no.metadata") == {
            "resolution": None,
            "codec": None,
            "source": None,
            "audio": None,
            "format": None,
        }


class TestTrackerQualitySymmetry:
    """torr9/lacale/c411 surface the SAME quality tokens on a shared title."""

    @pytest.mark.parametrize("title", _SHARED_TITLES)
    def test_all_three_clients_agree_with_shared_parser(self, title: str) -> None:
        """Each client's _parse_item surfaces the same tokens as the shared parser."""
        expected = {f: parse_title_quality(title).get(f) for f in _QUALITY_FIELDS}
        assert _torr9_result_quality(title) == expected
        assert _lacale_result_quality(title) == expected
        assert _c411_result_quality(title) == expected

    def test_torr9_now_parses_quality_tokens(self) -> None:
        """Regression: torr9 previously left every quality field None."""
        quality = _torr9_result_quality(_SHARED_TITLES[0])
        assert quality["resolution"] == "2160p"
        assert quality["codec"] == "H265"
        assert quality["source"] is not None
        assert quality["audio"] == "DTS-HD"
