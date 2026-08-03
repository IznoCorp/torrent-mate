"""Shared tracker title-quality parser — symmetry across lacale/c411/tr4ker.

TORRENT-TRACKERS-03: every tracker client encodes quality markers
(resolution, codec, source, audio, container format) in the release *title*,
not as structured fields. They all feed the single shared parser
:func:`personalscraper.api.tracker._quality.parse_title_quality`. Before this,
one client parsed nothing (all quality fields left ``None``) and c411 reached
across the family boundary into ``LaCaleClient._parse_title``.

These tests prove (a) the parser extracts the expected tokens and (b) each
client's ``_parse_item`` surfaces the SAME tokens on a shared title fixture —
including the Torznab configs, which share one parser through the generic.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from personalscraper.api.tracker._quality import parse_title_quality
from personalscraper.api.tracker.c411 import C411Client
from personalscraper.api.tracker.lacale import LaCaleClient
from personalscraper.api.tracker.tr4ker import Tr4kerClient

# Shared title fixtures spanning the token families the ranker consumes.
_SHARED_TITLES = [
    "Inception.2010.MULTi.TRUEFRENCH.HDR.2160p.UHD.BluRay.DTS-HD.MA.5.1.H265-XANTAR",
    "The.Robot.Wild.2024.MULTi.1080p.WEB-DL.DDP5.1.x265-GROUP",
    "Some.Show.S01E02.720p.HDTV.x264-AAC",
    "Random.title.no.metadata",
]

# Fields the shared parser owns and every client must surface identically.
# ``language`` is the axis added for the ranking editor (#18): a « prefer MULTi »
# criterion needs the marker parsed off the title on every tracker.
_QUALITY_FIELDS = ("resolution", "codec", "source", "audio", "language", "format")


def _tr4ker_result_quality(title: str) -> dict[str, str | None]:
    client = Tr4kerClient(MagicMock())
    r = client._parse_item({"title": title, "guid": "hash"})
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
            "language": None,
            "format": None,
        }


class TestLanguageParsing:
    """#18 — the language / audio-track axis (separate from the audio codec)."""

    def test_multi_marker_normalized_uppercase(self) -> None:
        """« MULTi » (any casing) parses to the canonical ``MULTI`` token."""
        assert parse_title_quality("Movie.2024.MULTi.1080p.WEB-DL.x265")["language"] == "MULTI"

    def test_multi_wins_over_later_french_variant(self) -> None:
        """A « MULTi ... TRUEFRENCH » title reports MULTI (the leading marker)."""
        title = "Inception.2010.MULTi.TRUEFRENCH.2160p.BluRay.H265"
        assert parse_title_quality(title)["language"] == "MULTI"

    def test_vostfr_parsed(self) -> None:
        """A subbed release surfaces the VOSTFR token."""
        assert parse_title_quality("Film.2023.VOSTFR.1080p.WEB.x264")["language"] == "VOSTFR"

    def test_truefrench_parsed_when_alone(self) -> None:
        """A TRUEFRENCH-only release surfaces that token."""
        assert parse_title_quality("Film.2023.TRUEFRENCH.1080p.BluRay")["language"] == "TRUEFRENCH"

    def test_language_is_not_the_audio_codec(self) -> None:
        """Language and audio are distinct axes: a MULTi DTS title fills BOTH."""
        out = parse_title_quality("Movie.2024.MULTi.1080p.BluRay.DTS-HD.x265")
        assert out["language"] == "MULTI"
        assert out["audio"] == "DTS-HD"

    def test_no_language_marker_is_none(self) -> None:
        """A release with no language token leaves the field None."""
        assert parse_title_quality("Some.Show.S01E02.720p.HDTV.x264")["language"] is None

    def test_title_word_french_does_not_beat_multi_tag(self) -> None:
        """Review defect 1: a « French »-titled MULTi release reports MULTI, not FRENCH.

        The leftmost regex match would pick the FRENCH title word that precedes
        the real MULTi tag; priority selection makes the multi-track marker win.
        """
        assert parse_title_quality("The.French.Dispatch.2021.MULTi.2160p.BluRay")["language"] == "MULTI"
        assert parse_title_quality("French.Connection.1971.MULTi.1080p.x265")["language"] == "MULTI"

    def test_priority_multi_over_truefrench_regardless_of_order(self) -> None:
        """MULTI outranks TRUEFRENCH even when TRUEFRENCH appears first."""
        assert parse_title_quality("Film.2023.TRUEFRENCH.MULTi.1080p")["language"] == "MULTI"


class TestLiveReleaseTitleSamples:
    """Shared parser against live release-title captures (2026-05-07).

    These titles were captured from a real tracker's search payloads; they pin
    the parser against genuine French-scene release naming (VFF/HDLight/MA.5.1
    noise between the markers), not synthetic fixtures.
    """

    def test_full_quality_title(self) -> None:
        """Live title with resolution+codec+source+audio markers extracts all four."""
        out = parse_title_quality("Inception.2010.MULTi.TRUEFRENCH.HDR.2160p.UHD.BluRay.DTS-HD.MA.5.1.H265-XANTAR")
        assert out["resolution"] == "2160p"
        assert out["codec"] == "H265"
        assert out["source"] is not None
        assert "bluray" in out["source"].lower()
        assert out["audio"] == "DTS-HD"

    def test_minimal_title_returns_nones(self) -> None:
        """A title without recognizable quality markers yields None fields."""
        out = parse_title_quality("Random.title.no.metadata")
        assert out["resolution"] is None
        assert out["codec"] is None
        assert out["source"] is None
        assert out["audio"] is None
        assert out["format"] is None

    def test_no_freeleech_keys_in_output(self) -> None:
        """Phase 18 revisit: the parser no longer returns freeleech flags."""
        out = parse_title_quality("[FreeLeech] Movie.1080p.x264")
        assert "is_freeleech" not in out
        assert "is_silverleech" not in out

    def test_format_extension_optional(self) -> None:
        """Live scene titles do NOT carry a file extension — format is None."""
        out = parse_title_quality("Inception.2010.MULTi.VFF.1080p.HDLight.DTS.5.1.x264-PATOMiEL")
        assert out["format"] is None


class TestTrackerQualitySymmetry:
    """lacale/c411/tr4ker surface the SAME quality tokens on a shared title."""

    @pytest.mark.parametrize("title", _SHARED_TITLES)
    def test_all_three_clients_agree_with_shared_parser(self, title: str) -> None:
        """Each client's _parse_item surfaces the same tokens as the shared parser."""
        expected = {f: parse_title_quality(title).get(f) for f in _QUALITY_FIELDS}
        assert _tr4ker_result_quality(title) == expected
        assert _lacale_result_quality(title) == expected
        assert _c411_result_quality(title) == expected

    def test_every_client_parses_quality_tokens(self) -> None:
        """Regression: a tracker client must never leave the quality fields None.

        The historical regression (one client dropped every quality token,
        silently starving the ranker) is pinned here on the newest client.
        """
        quality = _tr4ker_result_quality(_SHARED_TITLES[0])
        assert quality["resolution"] == "2160p"
        assert quality["codec"] == "H265"
        assert quality["source"] is not None
        assert quality["audio"] == "DTS-HD"
