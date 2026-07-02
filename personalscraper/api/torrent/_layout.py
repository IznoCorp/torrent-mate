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
