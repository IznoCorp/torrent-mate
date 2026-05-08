"""Design-contract tests for the dispatch + verify subsystem.

Pin points for ``docs/reference/storage.md`` (codename: ``dispatch``) and
``docs/reference/pipeline-internals.md`` (codename: ``pipeline``).
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.dispatch._movie import replace


class TestMovieReplaceContract:
    """Movie replace semantics — DESIGN storage.md §Move Rules (dispatch)."""

    def test_replace_swaps_destination_atomically(self, tmp_path: Path) -> None:
        """Movie replace performs a transfer + atomic swap.

        Design: docs/reference/storage.md#move-rules-dispatch
        Contract: For a movie whose destination folder already exists on
        the target disk, ``replace`` transfers ``source`` into a temporary
        sibling and atomically swaps it for the existing destination.
        After a successful call the destination contains the source's
        files and the source path is gone — last-writer-wins as the move
        rule prescribes.
        """
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "movie.mkv").write_bytes(b"new")
        (dest / "movie.mkv").write_bytes(b"old")

        ok = replace(source, dest)

        assert ok is True
        assert dest.exists()
        assert (dest / "movie.mkv").read_bytes() == b"new"
        assert not source.exists()
