"""Design-contract tests for the scraper feature (codename: ``scraper``).

Pin points for ``docs/reference/scraping.md`` — NFO completeness invariants
and artwork-recovery semantics.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.nfo_utils import is_nfo_complete


class TestNfoInvariantsContract:
    """``is_nfo_complete`` — DESIGN scraping.md §NFO Invariants."""

    def test_complete_nfo_with_uniqueid_returns_true(self, tmp_path: Path) -> None:
        """Parsable XML with a non-empty <uniqueid> → True.

        Design: docs/reference/scraping.md#nfo-invariants
        Contract: ``is_nfo_complete`` returns True iff the NFO file is
        parsable XML and contains at least one ``<uniqueid>`` element with
        non-empty text. Used by fast-skip and corrupt-NFO detection.
        """
        nfo = tmp_path / "movie.nfo"
        nfo.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<movie>\n"
            '  <uniqueid type="tmdb" default="true">12345</uniqueid>\n'
            "  <title>Sample</title>\n"
            "</movie>\n",
            encoding="utf-8",
        )

        assert is_nfo_complete(nfo) is True

    def test_nfo_missing_uniqueid_returns_false(self, tmp_path: Path) -> None:
        """Parsable XML without any non-empty <uniqueid> → False.

        Design: docs/reference/scraping.md#nfo-invariants
        Contract: An NFO with no ``<uniqueid>`` element (or with one whose
        text is empty/whitespace) is treated as incomplete and re-scraped.
        """
        nfo = tmp_path / "movie.nfo"
        nfo.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<movie><title>Sample</title></movie>\n',
            encoding="utf-8",
        )

        assert is_nfo_complete(nfo) is False

    def test_corrupt_nfo_returns_false(self, tmp_path: Path) -> None:
        """Unparsable XML → False (does not raise).

        Design: docs/reference/scraping.md#nfo-invariants
        Contract: A corrupt or non-XML NFO returns False rather than
        raising — the scraper relies on this to trigger re-scraping
        instead of crashing the pipeline.
        """
        nfo = tmp_path / "movie.nfo"
        nfo.write_text("not an xml file at all", encoding="utf-8")

        assert is_nfo_complete(nfo) is False
