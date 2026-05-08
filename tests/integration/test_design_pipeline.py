"""Design-contract tests for pipeline-wide invariants (codename: ``pipeline``).

Pin points for ``docs/reference/pipeline-internals.md``.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.nfo_utils import is_nfo_complete


class TestScrapeFastSkipContract:
    """Scrape fast-skip — DESIGN pipeline-internals.md §Scrape fast-skip."""

    def test_complete_nfo_marks_target_skippable(self, tmp_path: Path) -> None:
        """A directory with a complete NFO triggers fast-skip.

        Design: docs/reference/pipeline-internals.md#scrape-fast-skip
        Contract: The scrape step uses ``is_nfo_complete`` on the NFO
        file in the target directory to decide whether to re-scrape.
        A complete NFO (parsable XML + non-empty <uniqueid>) signals
        "already scraped" and the step short-circuits without contacting
        any provider.
        """
        nfo = tmp_path / "movie.nfo"
        nfo.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<movie><uniqueid type="tmdb">42</uniqueid></movie>\n',
            encoding="utf-8",
        )

        assert is_nfo_complete(nfo) is True
