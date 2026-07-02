"""Unit tests for structural_match (RP10a — DESIGN D4).

Covers positive match, each mismatch variant (piece length, root name, file list,
v2 hybrid), symmetry, plus two plan-extended cases: local v2 rejection and
order-sensitive file-list comparison.
"""

from __future__ import annotations

from personalscraper.api.torrent._layout import MatchVerdict, TorrentLayout, structural_match

# -- Fixtures ---------------------------------------------------------------

BASE = TorrentLayout(
    name="Release.Name.2024",
    piece_length=262144,
    files=[("Release.Name.2024.mkv", 1_000_000)],
    total_size=1_000_000,
)

IDENTICAL = TorrentLayout(
    name="Release.Name.2024",
    piece_length=262144,
    files=[("Release.Name.2024.mkv", 1_000_000)],
    total_size=1_000_000,
)

PIECE_DIFF = TorrentLayout(
    name="Release.Name.2024",
    piece_length=524288,  # different
    files=[("Release.Name.2024.mkv", 1_000_000)],
    total_size=1_000_000,
)

NAME_DIFF = TorrentLayout(
    name="Release.Name.2024.REPACK",  # renamed root
    piece_length=262144,
    files=[("Release.Name.2024.REPACK.mkv", 1_000_000)],
    total_size=1_000_000,
)

EXTRA_FILE = TorrentLayout(
    name="Release.Name.2024",
    piece_length=262144,
    files=[("Release.Name.2024.mkv", 1_000_000), ("Sample.mkv", 50_000)],  # extra
    total_size=1_050_000,
)

V2_HYBRID = TorrentLayout(
    name="Release.Name.2024",
    piece_length=262144,
    files=[("Release.Name.2024.mkv", 1_000_000)],
    total_size=1_000_000,
    meta_version=2,
)

# Extended fixtures (sub-phase 1.6 plan extras) — same files as EXTRA_FILE but
# reversed order so file-list length is identical but the zip comparison fails.

DIFF_ORDER = TorrentLayout(
    name="Release.Name.2024",
    piece_length=262144,
    files=[("Sample.mkv", 50_000), ("Release.Name.2024.mkv", 1_000_000)],
    total_size=1_050_000,
)


class TestStructuralMatch:
    """Unit tests for :func:`structural_match` — DESIGN D4 strict comparator."""

    # -- Positives ----------------------------------------------------------

    def test_identical_is_match(self) -> None:
        """BASE vs IDENTICAL (same every field) returns MATCH."""
        assert structural_match(BASE, IDENTICAL) == MatchVerdict.MATCH

    # -- Negatives (priority order) -----------------------------------------

    def test_piece_length_diff_rejected(self) -> None:
        """Different piece_length returns PIECE_LENGTH_MISMATCH."""
        assert structural_match(BASE, PIECE_DIFF) == MatchVerdict.PIECE_LENGTH_MISMATCH

    def test_root_name_diff_rejected(self) -> None:
        """Different root name returns ROOT_NAME_MISMATCH."""
        assert structural_match(BASE, NAME_DIFF) == MatchVerdict.ROOT_NAME_MISMATCH

    def test_extra_file_rejected(self) -> None:
        """Different file list (extra entry) returns FILE_LIST_MISMATCH."""
        assert structural_match(BASE, EXTRA_FILE) == MatchVerdict.FILE_LIST_MISMATCH

    def test_v2_hybrid_rejected(self) -> None:
        """Candidate with meta_version=2 returns V2_HYBRID."""
        assert structural_match(BASE, V2_HYBRID) == MatchVerdict.V2_HYBRID

    # -- Symmetry -----------------------------------------------------------

    def test_symmetric(self) -> None:
        """structural_match(a, b) == structural_match(b, a)."""
        assert structural_match(BASE, IDENTICAL) == structural_match(IDENTICAL, BASE)

    # -- Plan-extended (beyond skeleton) ------------------------------------

    def test_local_v2_also_rejected(self) -> None:
        """local.meta_version==2 also yields V2_HYBRID (1.3 clarification).

        The matcher rejects v2 on EITHER side — a v2 local can never
        full-match under v1 semantics, regardless of the candidate.
        """
        assert structural_match(V2_HYBRID, IDENTICAL) == MatchVerdict.V2_HYBRID

    def test_file_order_matters(self) -> None:
        """Same file set in different order returns FILE_LIST_MISMATCH.

        DESIGN D4 requires identical order, not just identical file sets.
        """
        assert structural_match(EXTRA_FILE, DIFF_ORDER) == MatchVerdict.FILE_LIST_MISMATCH
