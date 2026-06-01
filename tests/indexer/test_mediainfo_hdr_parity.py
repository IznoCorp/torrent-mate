"""HDR/Atmos granularity parity regression for the surviving pymediainfo path.

lib-fold Phase 4 drops the library ffprobe re-scan (``analyzer.analyze_library``,
which delegated to ``scraper/mediainfo.extract_stream_info``). DESIGN §4.5 requires
that the SURVIVING pymediainfo path populate ``media_stream.hdr_format`` and
``media_stream.is_atmos`` at the SAME granularity as the dropped ffprobe path:

- HDR: the dropped path emitted ``dolby_vision`` / ``hdr10plus`` / ``hdr10`` /
  ``hlg`` (``scraper/mediainfo.py``). The surviving
  :func:`personalscraper.indexer.mediainfo._normalise_hdr_format` emits the
  four equivalent labels ``"Dolby Vision"`` / ``"HDR10+"`` / ``"HDR10"`` /
  ``"HLG"`` (plus ``None`` for SDR).
- Atmos: :func:`personalscraper.indexer.mediainfo._detect_atmos` returns a
  bool (``True``/``False``, never ``None`` for an audio track).

This module PINS that granularity so a future change to ``_normalise_hdr_format``
that collapses two formats into one (e.g. mapping Dolby Vision onto HDR10) fails
loudly. The assertions reflect the REAL function behaviour, not an idealised
mapping — the value of the test is locking the current granularity honestly.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from personalscraper.indexer.mediainfo import _detect_atmos, _normalise_hdr_format


def _video_track(**kwargs: object) -> SimpleNamespace:
    """Build a minimal pymediainfo-style video track stub.

    Only the attributes read by :func:`_normalise_hdr_format` are exposed; all
    default to ``None`` so each parametrised case sets exactly the fields that
    a real pymediainfo Video track would carry for that HDR flavour.

    Args:
        **kwargs: Overrides for ``hdr_format`` / ``hdr_format_commercial`` /
            ``transfer_characteristics``.

    Returns:
        A namespace mirroring the ``getattr`` surface of a pymediainfo track.
    """
    defaults: dict[str, object] = {
        "hdr_format": None,
        "hdr_format_commercial": None,
        "transfer_characteristics": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _audio_track(**kwargs: object) -> SimpleNamespace:
    """Build a minimal pymediainfo-style audio track stub.

    Only the attributes read by :func:`_detect_atmos` are exposed; all default
    to ``None``.

    Args:
        **kwargs: Overrides for ``commercial_name`` / ``format_commercial`` /
            ``format_commercial_if_any`` / ``additionalfeatures``.

    Returns:
        A namespace mirroring the ``getattr`` surface of a pymediainfo track.
    """
    defaults: dict[str, object] = {
        "commercial_name": None,
        "format_commercial": None,
        "format_commercial_if_any": None,
        "additionalfeatures": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# HDR granularity — each of the four labels + SDR/None, from representative
# pymediainfo-style inputs (including transfer-characteristics-only variants).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("track", "expected"),
    [
        # Dolby Vision — distinct top-priority label.
        pytest.param(_video_track(hdr_format="Dolby Vision"), "Dolby Vision", id="dolby_vision-hdr_format"),
        pytest.param(
            _video_track(hdr_format="Dolby Vision / SMPTE ST 2086, HDR10 compatible"),
            "Dolby Vision",
            id="dolby_vision-with-hdr10-compat-blob",
        ),
        # HDR10+ — must NOT collapse into plain HDR10.
        pytest.param(_video_track(hdr_format_commercial="HDR10+"), "HDR10+", id="hdr10plus-commercial"),
        pytest.param(
            _video_track(hdr_format="SMPTE ST 2094 App 4, HDR10 Plus"),
            "HDR10+",
            id="hdr10plus-variant-spelling",
        ),
        # HDR10 — plain label, plus its PQ / SMPTE ST 2084 transfer variant.
        pytest.param(
            _video_track(hdr_format="HDR10 / SMPTE ST 2086"),
            "HDR10",
            id="hdr10-hdr_format",
        ),
        pytest.param(
            _video_track(transfer_characteristics="SMPTE ST 2084"),
            "HDR10",
            id="hdr10-transfer-smpte-st-2084",
        ),
        pytest.param(_video_track(transfer_characteristics="PQ"), "HDR10", id="hdr10-transfer-pq-exact"),
        # HLG — distinct label, plus its ARIB STD-B67 transfer variant.
        pytest.param(_video_track(transfer_characteristics="HLG"), "HLG", id="hlg-transfer"),
        pytest.param(
            _video_track(transfer_characteristics="ARIB STD-B67"),
            "HLG",
            id="hlg-transfer-arib-std-b67",
        ),
        # SDR / no HDR signal → None.
        pytest.param(_video_track(), None, id="sdr-empty"),
        pytest.param(
            _video_track(transfer_characteristics="BT.709"),
            None,
            id="sdr-bt709-transfer",
        ),
    ],
)
def test_normalise_hdr_format_pins_four_way_granularity(track: SimpleNamespace, expected: str | None) -> None:
    """Each HDR flavour resolves to its own canonical label (no collapse).

    Pins the four-way HDR distinction required by DESIGN §4.5 so that the
    surviving pymediainfo path stays at parity with the dropped ffprobe path.

    Args:
        track: A pymediainfo-style video track stub.
        expected: The canonical HDR label (or ``None`` for SDR).
    """
    assert _normalise_hdr_format(track) == expected


def test_normalise_hdr_format_labels_are_all_distinct() -> None:
    """The four HDR labels are mutually distinct — guards against silent merge.

    A regression that collapsed, e.g., Dolby Vision into HDR10 would make two
    of these comparisons fail; asserting the full distinct set makes the intent
    of the parity contract explicit.
    """
    labels = {
        _normalise_hdr_format(_video_track(hdr_format="Dolby Vision")),
        _normalise_hdr_format(_video_track(hdr_format_commercial="HDR10+")),
        _normalise_hdr_format(_video_track(hdr_format="HDR10")),
        _normalise_hdr_format(_video_track(transfer_characteristics="HLG")),
    }
    assert labels == {"Dolby Vision", "HDR10+", "HDR10", "HLG"}


# ---------------------------------------------------------------------------
# Atmos detection — True on any Atmos/JOC signal, False otherwise (never None).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("track", "expected"),
    [
        pytest.param(_audio_track(commercial_name="Dolby Atmos"), True, id="atmos-commercial-name"),
        pytest.param(
            _audio_track(format_commercial="Dolby TrueHD with Dolby Atmos"),
            True,
            id="atmos-format-commercial",
        ),
        pytest.param(_audio_track(additionalfeatures="JOC"), True, id="atmos-joc-additionalfeatures"),
        pytest.param(_audio_track(commercial_name="Dolby Digital"), False, id="plain-ac3-false"),
        pytest.param(_audio_track(), False, id="no-signal-false"),
    ],
)
def test_detect_atmos_contract(track: SimpleNamespace, expected: bool) -> None:
    """Atmos detection returns a bool — ``True`` on Atmos/JOC, ``False`` otherwise.

    The contract is ``bool`` (never ``None``) for an audio track: a negative
    answer is itself information, matching the parity requirement for
    ``media_stream.is_atmos``.

    Args:
        track: A pymediainfo-style audio track stub.
        expected: The expected boolean Atmos verdict.
    """
    result = _detect_atmos(track)
    assert result is expected
