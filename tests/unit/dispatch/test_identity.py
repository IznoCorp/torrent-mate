"""Unit tests for the §7 provider-ID identity guard (dispatch/_identity.py).

A destructive dispatch verifies the target by provider-ID before overwriting
it: a same-named DIFFERENT media must never be destroyed. These tests exercise
:func:`replace_identity_conflict` (movie REPLACE, ``<title>.nfo``) and
:func:`merge_identity_conflict` (TV MERGE, ``tvshow.nfo``) directly with on-disk
NFO fixtures.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from personalscraper.dispatch._identity import merge_identity_conflict, replace_identity_conflict


def _write_movie_nfo(
    movie_dir: Path, *, tmdb: str | None = None, imdb: str | None = None, tvdb: str | None = None
) -> None:
    """Write a minimal but complete movie NFO with the given provider IDs.

    Args:
        movie_dir: The movie folder (created if absent).
        tmdb: TMDB id, or ``None`` to omit.
        imdb: IMDB id, or ``None`` to omit.
        tvdb: TVDB id, or ``None`` to omit.
    """
    movie_dir.mkdir(parents=True, exist_ok=True)
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = movie_dir.name
    for provider, value in (("tmdb", tmdb), ("imdb", imdb), ("tvdb", tvdb)):
        if value is not None:
            uid = ET.SubElement(root, "uniqueid")
            uid.set("type", provider)
            uid.text = value
    ET.ElementTree(root).write(movie_dir / f"{movie_dir.name}.nfo", encoding="utf-8", xml_declaration=True)


def test_same_tmdb_id_allows_replace(tmp_path: Path) -> None:
    """Matching TMDB id on both sides → no conflict (allow)."""
    staging = tmp_path / "staging" / "Le Robot sauvage (2024)"
    target = tmp_path / "disk" / "Le Robot sauvage (2024)"
    _write_movie_nfo(staging, tmdb="1184918")
    _write_movie_nfo(target, tmdb="1184918")
    assert replace_identity_conflict(staging, target) is None


def test_different_tmdb_id_blocks_replace(tmp_path: Path) -> None:
    """Different TMDB id (same-named different movie) → block (§7).

    Red-on-old: the movie replace path resolved the target by NAME and
    overwrote it with zero identity check — a same-named different film would
    be destroyed. The guard now blocks with a French reason.
    """
    staging = tmp_path / "staging" / "Ferrari (2023)"
    target = tmp_path / "disk" / "Ferrari (2023)"
    _write_movie_nfo(staging, tmdb="1000000")  # Michael Mann's Ferrari
    _write_movie_nfo(target, tmdb="999999")  # a DIFFERENT Ferrari
    reason = replace_identity_conflict(staging, target)
    assert reason is not None
    assert "TMDB" in reason
    assert "999999" in reason and "1000000" in reason


def test_conflict_on_any_shared_provider(tmp_path: Path) -> None:
    """A mismatch on IMDB blocks even when TMDB is absent on one side."""
    staging = tmp_path / "staging" / "X (2024)"
    target = tmp_path / "disk" / "X (2024)"
    _write_movie_nfo(staging, imdb="tt1111111")
    _write_movie_nfo(target, imdb="tt2222222")
    assert replace_identity_conflict(staging, target) is not None


def test_missing_target_nfo_fails_open(tmp_path: Path) -> None:
    """A legacy target with no NFO cannot be verified → allow (fail-open).

    Blocking here would break every legitimate replace of a legacy no-NFO
    folder (the documented judgment call).
    """
    staging = tmp_path / "staging" / "Obsession (1976)"
    target = tmp_path / "disk" / "Obsession (1976)"
    _write_movie_nfo(staging, tmdb="12345")
    target.mkdir(parents=True, exist_ok=True)  # no NFO
    assert replace_identity_conflict(staging, target) is None


def test_disjoint_providers_allow(tmp_path: Path) -> None:
    """No shared provider between the two NFOs → cannot conflict (allow)."""
    staging = tmp_path / "staging" / "Y (2024)"
    target = tmp_path / "disk" / "Y (2024)"
    _write_movie_nfo(staging, tmdb="555")
    _write_movie_nfo(target, imdb="tt0000555")
    assert replace_identity_conflict(staging, target) is None


def _write_tvshow_nfo(
    show_dir: Path, *, tvdb: str | None = None, tmdb: str | None = None, imdb: str | None = None
) -> None:
    """Write a minimal but complete ``tvshow.nfo`` with the given provider IDs.

    A TV show's identity lives in the show-root ``tvshow.nfo`` (Kodi
    convention), a ``<tvshow>`` root with one ``<uniqueid>`` per provider —
    unlike a movie's ``<title>.nfo``.

    Args:
        show_dir: The show folder (created if absent).
        tvdb: TVDB id, or ``None`` to omit.
        tmdb: TMDB id, or ``None`` to omit.
        imdb: IMDB id, or ``None`` to omit.
    """
    show_dir.mkdir(parents=True, exist_ok=True)
    root = ET.Element("tvshow")
    ET.SubElement(root, "title").text = show_dir.name
    for provider, value in (("tvdb", tvdb), ("tmdb", tmdb), ("imdb", imdb)):
        if value is not None:
            uid = ET.SubElement(root, "uniqueid")
            uid.set("type", provider)
            uid.text = value
    ET.ElementTree(root).write(show_dir / "tvshow.nfo", encoding="utf-8", xml_declaration=True)


def test_merge_same_tvdb_id_allows(tmp_path: Path) -> None:
    """Matching TVDB id on both sides → no conflict (allow)."""
    staging = tmp_path / "staging" / "Fallout (2024)"
    target = tmp_path / "disk" / "Fallout (2024)"
    _write_tvshow_nfo(staging, tvdb="106011")
    _write_tvshow_nfo(target, tvdb="106011")
    assert merge_identity_conflict(staging, target) is None


def test_merge_different_tvdb_id_blocks(tmp_path: Path) -> None:
    """Different TVDB id (same-named different show) → block (§7).

    The TV merge path resolved the target by NAME and overwrote its episodes
    with zero identity check — a same-named different series would be destroyed.
    The guard now blocks with a French reason naming the TVDB mismatch.
    """
    staging = tmp_path / "staging" / "The Office (2005)"
    target = tmp_path / "disk" / "The Office (2005)"
    _write_tvshow_nfo(staging, tvdb="73244")  # The Office (US)
    _write_tvshow_nfo(target, tvdb="78107")  # The Office (UK) — DIFFERENT show
    reason = merge_identity_conflict(staging, target)
    assert reason is not None
    assert "TVDB" in reason
    assert "73244" in reason and "78107" in reason


def test_merge_conflict_on_any_shared_provider(tmp_path: Path) -> None:
    """A mismatch on TMDB blocks even when TVDB is absent on one side."""
    staging = tmp_path / "staging" / "X (2024)"
    target = tmp_path / "disk" / "X (2024)"
    _write_tvshow_nfo(staging, tmdb="111111")
    _write_tvshow_nfo(target, tmdb="222222")
    assert merge_identity_conflict(staging, target) is not None


def test_merge_missing_target_nfo_fails_open(tmp_path: Path) -> None:
    """A legacy target show with no ``tvshow.nfo`` cannot be verified → allow.

    Blocking here would break every legitimate merge into a legacy no-NFO show
    folder (the documented judgment call, §8).
    """
    staging = tmp_path / "staging" / "Columbo (1971)"
    target = tmp_path / "disk" / "Columbo (1971)"
    _write_tvshow_nfo(staging, tvdb="12345")
    target.mkdir(parents=True, exist_ok=True)  # no tvshow.nfo
    assert merge_identity_conflict(staging, target) is None


def test_merge_disjoint_providers_allow(tmp_path: Path) -> None:
    """No shared provider between the two show NFOs → cannot conflict (allow)."""
    staging = tmp_path / "staging" / "Y (2024)"
    target = tmp_path / "disk" / "Y (2024)"
    _write_tvshow_nfo(staging, tvdb="555")
    _write_tvshow_nfo(target, imdb="tt0000555")
    assert merge_identity_conflict(staging, target) is None
