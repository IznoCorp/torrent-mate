r"""Test helper — write a media placeholder whose SIZE is real and whose bytes are not.

WHY THIS EXISTS, measured on 2026-08-26. Thirty-eight fixture sites wrote a
placeholder video with `write_bytes(b"\x00" * 200 * 1024 * 1024)` — two hundred
megabytes of REAL zeroes, allocated block by block. One `make test` pass left
13 GB across 47 049 files under `/tmp/pytest-of-izno`, pytest keeps the last
three passes by default, and the machine's boot volume filled up. The comment
above one of those lines read « small but enough for tests ».

WHAT THE TESTS ACTUALLY NEED is the SIZE: the library checks refuse a video
under a minimum, the disk cleaner acts above a threshold. None of them reads
the content. A sparse file answers `stat().st_size` with the full figure and
costs one block on disk, and a read of it returns the same zeroes byte for
byte — so nothing about any test's meaning changes.

The small placeholders (a kilobyte, a thousand bytes) are deliberately left as
they are: they cost nothing, and rewriting them would be churn with no defect
behind it.

WHERE THE SPARSENESS STOPS, measured rather than assumed. `rsync` re-expands a
sparse file unless it is told not to, and no capability's flag tuple carries
`--sparse` — so the tests that really DISPATCH write dense copies on the
destination side: 315 MB for four of them. For those, the saving comes from
`tmp_path_retention_policy` and not from this helper. Both halves were needed;
neither alone would have been enough.
"""

from __future__ import annotations

from pathlib import Path


def write_placeholder_media(path: Path, size: int) -> Path:
    """Creates a file that reports `size` bytes while occupying almost none.

    Args:
        path: Where to write. Its parent must already exist.
        size: The size the file must report, in bytes.

    Returns:
        The same path, so a caller can chain.
    """
    with path.open("wb") as handle:
        handle.truncate(size)
    return path
