"""#18 — ranking editor: the language and provider criteria actually score.

Two new categorical axes ship with the ranking editor:

  * ``language`` — the marker parsed off the release title (MULTI/VFF/VOSTFR),
    so the operator's « prefer Multi » preference is expressible; and
  * ``provider`` — the tracker wire name (tr4ker/c411/c411), so a healthy-ratio
    tracker (tr4ker ~5.17, freeleech) can be favoured over a poorer one (c411).

Both are config-only on the engine side (``field`` is a free string; the engine
does ``getattr(result, field)`` then a ``values`` lookup). These tests pin the
behaviour AND that the TRACKED template carries the criteria (else it never ships).
"""

from __future__ import annotations

from pathlib import Path

import json5

from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import (
    RankingConfig,
    RankingCriterion,
    rank,
)


def _result(
    *,
    provider: str = "c411",
    language: str | None = None,
    is_freeleech: bool = False,
    tid: str = "t",
) -> TrackerResult:
    """A TrackerResult differing only on the axes under test."""
    return TrackerResult(
        provider=provider,
        tracker_id=tid,
        title=f"Movie 2024 {language or ''}".strip(),
        size=ByteSize(4_000_000_000),
        seeders=10,
        leechers=0,
        language=language,
        is_freeleech=is_freeleech,
    )


class TestLanguageCriterion:
    """A ``field: "language"`` criterion scores the parsed marker."""

    def test_multi_beats_vostfr(self) -> None:
        """MULTI (20) outscores VOSTFR (6) at equal everything else."""
        cfg = RankingConfig(
            criteria=[
                RankingCriterion(
                    field="language",
                    weight=2,
                    values={"MULTI": 20, "VOSTFR": 6},
                )
            ],
            min_seeders=1,
        )
        multi = _result(language="MULTI", tid="multi")
        sub = _result(language="VOSTFR", tid="sub")
        ranked = rank([sub, multi], cfg)
        assert ranked[0][0].tracker_id == "multi"
        assert ranked[0][1] == 40  # 20 * weight 2
        assert ranked[1][1] == 12  # 6 * weight 2

    def test_no_language_marker_scores_zero(self) -> None:
        """A release with no language token gets no language points (None → skip)."""
        cfg = RankingConfig(
            criteria=[RankingCriterion(field="language", weight=2, values={"MULTI": 20})],
            min_seeders=1,
        )
        ((_, score),) = rank([_result(language=None)], cfg)
        assert score == 0


class TestProviderCriterion:
    """A ``field: "provider"`` criterion favours the healthy-ratio tracker."""

    def test_tr4ker_outscores_c411(self) -> None:
        """tr4ker (15) beats c411 (5) on the provider axis alone."""
        cfg = RankingConfig(
            criteria=[RankingCriterion(field="provider", weight=1, values={"tr4ker": 15, "c411": 5})],
            min_seeders=1,
        )
        tr = _result(provider="tr4ker", tid="tr")
        c4 = _result(provider="c411", tid="c4")
        ranked = rank([c4, tr], cfg)
        assert ranked[0][0].tracker_id == "tr"
        assert ranked[0][1] == 15
        assert ranked[1][1] == 5

    def test_tr4ker_freeleech_stacks_provider_and_bonus(self) -> None:
        """A freeleech tr4ker release earns BOTH the provider score and the bonus."""
        cfg = RankingConfig(
            criteria=[RankingCriterion(field="provider", weight=1, values={"tr4ker": 15})],
            min_seeders=1,
        )
        ((_, score),) = rank([_result(provider="tr4ker", is_freeleech=True)], cfg)
        assert score == 25  # 15 provider + 10 freeleech bonus


class TestCaseInsensitiveCategoricalLookup:
    """Review defect 2: a differently-cased release token still scores its value."""

    def test_audio_lowercase_token_scores(self) -> None:
        """A « dts-hd » release scores the « DTS-HD » criterion value (case-insensitive)."""
        cfg = RankingConfig(
            criteria=[RankingCriterion(field="audio", weight=2, values={"DTS-HD": 10})],
            min_seeders=1,
        )
        result = TrackerResult(
            provider="c411",
            tracker_id="t",
            title="Film 2024 dts-hd",
            size=ByteSize(4_000_000_000),
            seeders=10,
            leechers=0,
            audio="dts-hd",
        )
        ((_, score),) = rank([result], cfg)
        assert score == 20  # 10 * weight 2 — NOT 0

    def test_codec_uppercase_token_scores(self) -> None:
        """A « X265 » release scores the « x265 » criterion value (case-insensitive)."""
        cfg = RankingConfig(
            criteria=[RankingCriterion(field="codec", weight=3, values={"x265": 10})],
            min_seeders=1,
        )
        result = TrackerResult(
            provider="c411",
            tracker_id="t",
            title="Film 2024 X265",
            size=ByteSize(4_000_000_000),
            seeders=10,
            leechers=0,
            codec="X265",
        )
        ((_, score),) = rank([result], cfg)
        assert score == 30  # 10 * weight 3 — NOT 0


class TestTemplateCarriesNewCriteria:
    """The TRACKED template ships the language + provider criteria (else no feature)."""

    def test_example_ranking_has_language_and_provider(self) -> None:
        """config.example/ranking.json5 declares both new criteria with values."""
        raw = json5.loads(Path("config.example/ranking.json5").read_text())
        fields = {c["field"]: c for c in raw["ranking"]["criteria"]}
        assert "language" in fields, "language criterion missing from template"
        assert fields["language"]["values"]["MULTI"] == 20
        assert "provider" in fields, "provider criterion missing from template"
        assert fields["provider"]["values"]["tr4ker"] == 15
        # The dead VFF/VFQ entries must be gone from the audio (codec) field.
        assert "VFF" not in fields["audio"]["values"]
