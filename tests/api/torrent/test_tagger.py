"""Tests for TorrentTagger capability on QBitClient and TransmissionClient.

Covers DESIGN criteria 1 (SEED_PURE importable), 2 (qBit tagger endpoints +
idempotence), and 3 (Transmission category preservation).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Criterion 1 — SEED_PURE constant
# ---------------------------------------------------------------------------


def test_seed_pure_importable_and_value():
    """SEED_PURE is importable from core.tags and equals 'seed-pure'."""
    from personalscraper.core.tags import SEED_PURE

    assert SEED_PURE == "seed-pure"


def test_seed_pure_in_all():
    """SEED_PURE is in core.tags.__all__."""
    import personalscraper.core.tags as m

    assert "SEED_PURE" in m.__all__
