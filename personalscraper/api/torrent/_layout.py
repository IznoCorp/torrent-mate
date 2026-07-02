"""Typed .torrent layout primitives for structural matching (RP10a).

See docs/features/watch-seed/DESIGN.md §RP10a.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class MatchVerdict(enum.Enum):
    """Outcome of :func:`structural_match`."""

    MATCH = "match"
    PIECE_LENGTH_MISMATCH = "piece_length_mismatch"
    FILE_LIST_MISMATCH = "file_list_mismatch"
    ROOT_NAME_MISMATCH = "root_name_mismatch"
    V2_HYBRID = "v2_hybrid"


@dataclass(frozen=True, slots=True)
class TorrentLayout:
    """Immutable file-tree layout extracted from a .torrent's ``info`` dict.

    Attributes:
        name: ``info.name`` — the root directory (multi-file) or base filename
            (single-file). Structural matching requires identical names; a
            renamed root cannot match without linking (D11).
        piece_length: ``info.piece length`` in bytes.
        files: Ordered list of ``(relative_path, size)`` — the slash-separated
            path joined to ``name/`` at the torrent root, with the declared
            byte size.
        total_size: Sum of every file's declared size (computed, not parsed).
        meta_version: ``info.meta version`` if present (1 = v1, 2 = v2/hybrid),
            or ``1`` when absent (default v1).
    """

    name: str
    piece_length: int
    files: list[tuple[str, int]]
    total_size: int
    meta_version: int = 1


def structural_match(local: TorrentLayout, candidate: TorrentLayout) -> MatchVerdict:
    """Full-match strict comparator (DESIGN D4).

    Returns MATCH only when piece_length, file-list (relative paths + sizes
    + order), and root name are all identical.  Rejects v2/hybrid on either
    side (a v2 local can never full-match under v1 semantics).

    Args:
        local: The source torrent's layout (from the local qBit copy).
        candidate: The remotely-fetched candidate's layout.

    Returns:
        ``MatchVerdict.MATCH`` or the first mismatch reason encountered,
        in priority order: v2_hybrid → piece_length → root_name → file_list.
    """
    # Reject v2/hybrid on either side — v2 has a different info-dict shape
    # and can never structurally match under v1 semantics.
    if local.meta_version == 2 or candidate.meta_version == 2:
        return MatchVerdict.V2_HYBRID

    if local.piece_length != candidate.piece_length:
        return MatchVerdict.PIECE_LENGTH_MISMATCH

    if local.name != candidate.name:
        return MatchVerdict.ROOT_NAME_MISMATCH

    if len(local.files) != len(candidate.files):
        return MatchVerdict.FILE_LIST_MISMATCH

    for (local_path, local_size), (cand_path, cand_size) in zip(local.files, candidate.files):
        if local_path != cand_path or local_size != cand_size:
            return MatchVerdict.FILE_LIST_MISMATCH

    return MatchVerdict.MATCH
