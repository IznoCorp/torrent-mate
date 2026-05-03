"""Backward-compatible scraper facade.

Implementation is split across service modules; this module preserves the
historic import and monkeypatch surface used by callers and tests.
"""

from __future__ import annotations

from personalscraper.conf import classifier as _classifier
from personalscraper.nfo_utils import is_nfo_complete as _is_nfo_complete
from personalscraper.scraper._shared import ScrapeResult, _find_video_file
from personalscraper.scraper.classifier import _parse_folder_name
from personalscraper.scraper.confidence import LOW_CONFIDENCE, MatchResult, match_movie, match_tvshow
from personalscraper.scraper.existing_validator import (
    _infer_year_from_child_names,
    _local_show_seasons,
    verify_tvshow_scrape_drift,
)
from personalscraper.scraper.mediainfo import extract_stream_info
from personalscraper.scraper.orchestrator import Scraper
from personalscraper.scraper.rename_service import (
    _cleanup_empty_release_dirs,
    _cleanup_stale_files,
    _merge_dirs,
    _rename_dir_case_safe,
)
from personalscraper.scraper.tmdb_client import TMDBClient
from personalscraper.scraper.tv_service import _tvdb_series_to_show_data
from personalscraper.scraper.tvdb_client import TVDBClient

__all__ = [
    "LOW_CONFIDENCE",
    "MatchResult",
    "ScrapeResult",
    "Scraper",
    "TMDBClient",
    "TVDBClient",
    "_cleanup_empty_release_dirs",
    "_cleanup_stale_files",
    "_classifier",
    "_find_video_file",
    "_infer_year_from_child_names",
    "_is_nfo_complete",
    "_local_show_seasons",
    "_merge_dirs",
    "_parse_folder_name",
    "_rename_dir_case_safe",
    "_tvdb_series_to_show_data",
    "extract_stream_info",
    "match_movie",
    "match_tvshow",
    "verify_tvshow_scrape_drift",
]
