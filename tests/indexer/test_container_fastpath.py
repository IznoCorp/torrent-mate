"""Tests for the container fast-path (DESIGN §11.4 implementation).

Covers:
- ``is_fastpath_supported`` accepts ``.mkv`` / ``.webm`` only.
- ``needs_pymediainfo_fallback`` triggers on HDR-capable + 4 K and on
  Atmos-capable + ≥ 8 channels; stays silent on SD content and stereo
  audio.
- ``extract_via_enzyme`` returns ``None`` for non-Matroska inputs.
- ``merge_hdr_atmos`` overlays pymediainfo's ``hdr_format`` and
  ``is_atmos`` onto the fast-path rows while preserving everything else.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.indexer._container_fastpath import (
    extract_via_enzyme,
    is_fastpath_supported,
    merge_hdr_atmos,
    needs_pymediainfo_fallback,
)
from personalscraper.indexer.schema import MediaStreamRow


def _row(
    *,
    kind: str,
    idx: int = 0,
    codec: str | None = None,
    height: int | None = None,
    channels: int | None = None,
    hdr_format: str | None = None,
    is_atmos: bool | None = None,
    is_default: bool | None = None,
    forced: bool | None = None,
    format: str | None = None,
) -> MediaStreamRow:
    return MediaStreamRow(
        id=0,
        file_id=0,
        idx=idx,
        kind=kind,  # type: ignore[arg-type]
        codec=codec,
        lang=None,
        channels=channels,
        width=None,
        height=height,
        duration_ms=None,
        bitrate=None,
        hdr_format=hdr_format,
        is_atmos=is_atmos,
        is_default=is_default,
        forced=forced,
        format=format,
    )


@pytest.mark.parametrize(
    "name,expected",
    [
        ("movie.mkv", True),
        ("movie.MKV", True),
        ("clip.webm", True),
        ("movie.mp4", False),
        ("clip.avi", False),
        ("subs.srt", False),
        ("poster.jpg", False),
    ],
)
def test_is_fastpath_supported(name: str, expected: bool) -> None:
    """Fast path accepts MKV / WebM and rejects every other container."""
    assert is_fastpath_supported(Path(name)) is expected


def test_needs_fallback_4k_hevc_triggers() -> None:
    """4 K HEVC video → fall back to pymediainfo for HDR detection."""
    rows = [_row(kind="video", codec="V_MPEGH/ISO/HEVC", height=2160)]
    assert needs_pymediainfo_fallback(rows) is True


def test_needs_fallback_4k_av1_triggers() -> None:
    """4 K AV1 video → fall back to pymediainfo for HDR detection."""
    rows = [_row(kind="video", codec="V_AV1", height=2160)]
    assert needs_pymediainfo_fallback(rows) is True


def test_needs_fallback_1080p_hevc_no_trigger() -> None:
    """1080p HEVC stays on fast path; modern HDR is rare below 4 K."""
    rows = [_row(kind="video", codec="V_MPEGH/ISO/HEVC", height=1080)]
    assert needs_pymediainfo_fallback(rows) is False


def test_needs_fallback_truehd_8ch_triggers() -> None:
    """TrueHD with ≥ 8 channels → fall back for Atmos detection."""
    rows = [_row(kind="audio", codec="A_TRUEHD", channels=8)]
    assert needs_pymediainfo_fallback(rows) is True


def test_needs_fallback_truehd_6ch_no_trigger() -> None:
    """TrueHD 5.1 (6 ch) is not Atmos — stay on fast path."""
    rows = [_row(kind="audio", codec="A_TRUEHD", channels=6)]
    assert needs_pymediainfo_fallback(rows) is False


def test_needs_fallback_eac3_8ch_triggers() -> None:
    """E-AC-3 with 8 channels → likely Atmos via JOC."""
    rows = [_row(kind="audio", codec="A_EAC3", channels=8)]
    assert needs_pymediainfo_fallback(rows) is True


def test_needs_fallback_aac_stereo_no_trigger() -> None:
    """Plain AAC stereo: nothing to fall back for."""
    rows = [_row(kind="audio", codec="A_AAC", channels=2)]
    assert needs_pymediainfo_fallback(rows) is False


def test_needs_fallback_empty_no_trigger() -> None:
    """No streams → no fallback."""
    assert needs_pymediainfo_fallback([]) is False


def test_extract_via_enzyme_returns_none_on_non_mkv(tmp_path: Path) -> None:
    """Non-Matroska inputs immediately return ``None``."""
    p = tmp_path / "movie.mp4"
    p.write_bytes(b"not really an mp4")
    assert extract_via_enzyme(p) is None


def test_extract_via_enzyme_returns_none_on_garbage_mkv(tmp_path: Path) -> None:
    """A file with the right extension but invalid contents returns ``None``."""
    p = tmp_path / "broken.mkv"
    p.write_bytes(b"definitely not an EBML stream")
    assert extract_via_enzyme(p) is None


def test_merge_hdr_atmos_overlays_only_two_fields() -> None:
    """``merge_hdr_atmos`` copies ``hdr_format`` + ``is_atmos`` and nothing else."""
    fast_video = _row(kind="video", idx=0, codec="V_MPEGH/ISO/HEVC", height=2160, is_default=True)
    fast_audio = _row(kind="audio", idx=0, codec="A_TRUEHD", channels=8, is_default=True)
    rich_video = _row(kind="video", idx=0, codec="HEVC", height=2160, hdr_format="Dolby Vision")
    rich_audio = _row(kind="audio", idx=0, codec="TrueHD", channels=8, is_atmos=True)

    merged = merge_hdr_atmos([fast_video, fast_audio], [rich_video, rich_audio])
    by_kind = {r.kind: r for r in merged}

    # HDR / Atmos overlaid from rich rows.
    assert by_kind["video"].hdr_format == "Dolby Vision"
    assert by_kind["audio"].is_atmos is True
    # Codec / dimensions / default flag preserved from fast rows.
    assert by_kind["video"].codec == "V_MPEGH/ISO/HEVC"
    assert by_kind["video"].is_default is True
    assert by_kind["audio"].codec == "A_TRUEHD"
    assert by_kind["audio"].is_default is True


def test_merge_hdr_atmos_keeps_unmatched_rows_as_is() -> None:
    """Rows that exist on only one side survive unchanged."""
    fast = _row(kind="video", idx=0, codec="V_MPEGH/ISO/HEVC", height=1080)
    rich = _row(kind="audio", idx=0, codec="EAC3", is_atmos=True)
    merged = merge_hdr_atmos([fast], [rich])
    assert len(merged) == 1
    assert merged[0].kind == "video"
    assert merged[0].codec == "V_MPEGH/ISO/HEVC"
