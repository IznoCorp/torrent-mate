# Phase 3: result.media_path stale (bug #17)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Fix `scrape_tvshow()` to update `result.media_path` after folder rename.

**Architecture:** One-line fix — copy the pattern from `scrape_movie()` line 535.

**Tech Stack:** Python, pytest

---

## Task 1: Write reproducer test

**Files:**

- Modify: `tests/scraper/test_scraper.py`

- [ ] **Step 1: Write failing test**

```python
class TestScrapeTvshowMediaPath:
    """Test that scrape_tvshow updates result.media_path after rename."""

    @patch("personalscraper.scraper.scraper.ArtworkDownloader")
    @patch("personalscraper.scraper.scraper.NFOGenerator")
    @patch("personalscraper.scraper.scraper.TVDBClient")
    @patch("personalscraper.scraper.scraper.TMDBClient")
    def test_media_path_updated_after_rename(
        self, mock_tmdb_cls, mock_tvdb_cls, mock_nfo_cls, mock_art_cls, tmp_path: Path,
    ) -> None:
        """result.media_path should point to the NEW path after folder rename."""
        from personalscraper.config import Settings
        from personalscraper.scraper.scraper import Scraper

        # Create show dir with old name (needs rename)
        show_dir = tmp_path / "002-TVSHOWS" / "OldName (2025)"
        show_dir.mkdir(parents=True)
        (show_dir / "S01E01.mkv").write_bytes(b"\x00" * 1000)

        # Mock TMDB to return a different title (triggers rename)
        mock_tmdb = MagicMock()
        mock_tmdb.search_tv.return_value = [{"id": 123, "name": "NewName", "first_air_date": "2025-01-01"}]
        mock_tmdb.get_tv.return_value = {
            "name": "NewName", "id": 123, "seasons": [],
            "images": {"posters": [], "backdrops": []},
            "external_ids": {"imdb_id": "tt1234"},
        }
        mock_tmdb_cls.return_value = mock_tmdb

        mock_tvdb = MagicMock()
        mock_tvdb_cls.return_value = mock_tvdb

        mock_nfo = MagicMock()
        mock_nfo.generate_tvshow_nfo.return_value = "<tvshow/>"
        mock_nfo_cls.return_value = mock_nfo

        mock_art = MagicMock()
        mock_art.download_tvshow_artwork.return_value = []
        mock_art_cls.return_value = mock_art

        settings = MagicMock(spec=Settings)
        scraper = Scraper(settings, dry_run=False)

        result = scraper.scrape_tvshow(show_dir)

        # The folder should have been renamed
        expected_path = tmp_path / "002-TVSHOWS" / "NewName (2025)"
        assert result.media_path == expected_path
        # Old path should not exist
        assert not show_dir.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/scraper/test_scraper.py::TestScrapeTvshowMediaPath -v`
Expected: FAIL — `result.media_path` still points to old path

- [ ] **Step 3: Commit**

```bash
git add tests/scraper/test_scraper.py
git commit -m "v12.3.1: Add failing test for scrape_tvshow result.media_path after rename"
```

## Task 2: Fix the missing line

**Files:**

- Modify: `personalscraper/scraper/scraper.py:776`

- [ ] **Step 1: Add result.media_path update**

In `scrape_tvshow()`, after `show_dir = new_dir` (line 776), add:

```python
                    show_dir = new_dir
                    result.media_path = new_dir
```

This mirrors `scrape_movie()` line 535: `result.media_path = new_path`.

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/scraper/test_scraper.py::TestScrapeTvshowMediaPath -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add personalscraper/scraper/scraper.py
git commit -m "v12.3.2: Fix scrape_tvshow — update result.media_path after folder rename"
```
