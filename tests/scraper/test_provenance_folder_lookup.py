"""Tests for the provenance identity seed reaching the scrape (#30).

Regression for the 2026-08-06 « The Odyssey » incident: the film's TMDB id was
recorded at grab, yet the scrape free-matched by title, drew 27 candidates, tied
at 1.0 and queued an ambiguity — because the identity seed was keyed on the FILE
the sorter had moved, while the resolver looked up the media FOLDER.

Two layers, both covered here:

- :func:`personalscraper.sorter.run.media_root_for` — the sorter now records the
  media folder, so the seed is written where the scrape will look for it.
- :func:`personalscraper.scraper.run.lookup_ref_for_folder` — the resolver also
  accepts a seed recorded one level deeper, so rows already in the DB resolve
  without a migration.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

from personalscraper.core.identity import MediaRef
from personalscraper.scraper.run import lookup_ref_for_folder
from personalscraper.sorter.run import media_root_for

STAGING = Path("/staging")


# ---------------------------------------------------------------------------
# media_root_for — what the sorter records
# ---------------------------------------------------------------------------


def test_single_file_movie_records_the_media_folder() -> None:
    """REGRESSION: a single-file movie must record its FOLDER, not the file.

    The exact shape the sorter produced on 2026-08-06:
    ``001-MOVIES/The Odyssey (2026)/[Cosplayground].The.Odyssey.Part.1…mp4``.
    """
    dest = STAGING / "001-MOVIES" / "The Odyssey (2026)" / "[Cosplayground].The.Odyssey.Part.1.2026-ONYXA.mp4"
    assert media_root_for(dest, STAGING) == STAGING / "001-MOVIES" / "The Odyssey (2026)"


def test_tv_release_records_the_show_folder() -> None:
    """A TV release dropped under its show folder records the show folder."""
    dest = STAGING / "002-TVSHOWS" / "Star Trek Strange New Worlds" / "Star.Trek.S04E03.WEB.H264-SUPPLY"
    assert media_root_for(dest, STAGING) == STAGING / "002-TVSHOWS" / "Star Trek Strange New Worlds"


def test_movie_directory_is_already_the_media_folder() -> None:
    """A movie moved as a DIRECTORY is its own media folder — never its category."""
    dest = STAGING / "001-MOVIES" / "Marjorie Prime (2017)"
    assert media_root_for(dest, STAGING) == STAGING / "001-MOVIES" / "Marjorie Prime (2017)"


def test_file_directly_in_a_category_dir_is_its_own_unit() -> None:
    """No media folder to speak of → the destination is kept unchanged."""
    dest = STAGING / "004-AUDIO" / "album.flac"
    assert media_root_for(dest, STAGING) == dest


def test_path_outside_staging_is_kept_unchanged() -> None:
    """Nothing to reason about outside the staging root — never invent a path."""
    dest = Path("/elsewhere/whatever/file.mkv")
    assert media_root_for(dest, STAGING) == dest


# ---------------------------------------------------------------------------
# lookup_ref_for_folder — what the scrape resolves
# ---------------------------------------------------------------------------


def test_lookup_exact_folder_hit() -> None:
    """The nominal case: the seed is recorded on the folder itself."""
    folder = STAGING / "001-MOVIES" / "The Odyssey (2026)"
    index = {str(folder): MediaRef(tmdb_id=1368337)}
    ref = lookup_ref_for_folder(index, folder)
    assert ref is not None
    assert ref.tmdb_id == 1368337


def test_lookup_tolerates_a_seed_recorded_on_the_file() -> None:
    """REGRESSION: a legacy row keyed on the FILE must still resolve.

    This is the miss that sent « The Odyssey » to a free title match.
    """
    folder = STAGING / "001-MOVIES" / "The Odyssey (2026)"
    index = {str(folder / "[Cosplayground].The.Odyssey.Part.1.2026-ONYXA.mp4"): MediaRef(tmdb_id=1368337)}
    ref = lookup_ref_for_folder(index, folder)
    assert ref is not None
    assert ref.tmdb_id == 1368337


def test_lookup_does_not_swallow_a_sibling_with_a_longer_name() -> None:
    """LOAD-BEARING: the fallback compares path PARTS, never a string prefix.

    A plain ``startswith`` would make « The Odyssey (2026) » claim the seed of
    « The Odyssey (2026) Remastered » — a wrong identity forced onto a wrong film.
    """
    folder = STAGING / "001-MOVIES" / "The Odyssey (2026)"
    sibling = STAGING / "001-MOVIES" / "The Odyssey (2026) Remastered" / "release.mkv"
    index = {str(sibling): MediaRef(tmdb_id=999999)}
    assert lookup_ref_for_folder(index, folder) is None


def test_lookup_miss_returns_none() -> None:
    """An untracked folder resolves to nothing — the scrape then free-matches."""
    index = {str(STAGING / "001-MOVIES" / "Other (2020)"): MediaRef(tmdb_id=42)}
    assert lookup_ref_for_folder(index, STAGING / "001-MOVIES" / "The Odyssey (2026)") is None


def test_lookup_matches_across_unicode_forms() -> None:
    """MacFUSE hands out NFD paths while the DB stores NFC — both must resolve.

    The two forms are built explicitly, never typed as literals: a source file is
    saved in ONE normalisation form, so writing the accented name on both sides
    would compare a string to itself and prove nothing.
    """
    name = "L'Odyssee (2026)".replace("Odyssee", "Odyss\u00e9e")
    nfc_folder = Path(unicodedata.normalize("NFC", str(STAGING / "001-MOVIES" / name)))
    nfd_key = unicodedata.normalize("NFD", str(STAGING / "001-MOVIES" / name / "release.mkv"))

    # Guard: the fixture must genuinely straddle the two forms, else it is vacuous.
    assert nfd_key != unicodedata.normalize("NFC", nfd_key), "fixture must exercise NFC vs NFD"

    index = {nfd_key: MediaRef(tmdb_id=1368337)}
    ref = lookup_ref_for_folder(index, nfc_folder)
    assert ref is not None
    assert ref.tmdb_id == 1368337
