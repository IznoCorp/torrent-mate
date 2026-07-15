"""Unit tests for the §7 provider-ID identity guard (dispatch/_identity.py).

A REPLACE destroys the on-disk target, so it must be verified by provider-ID:
a same-named DIFFERENT movie must never be overwritten. These tests exercise
:func:`replace_identity_conflict` directly with on-disk NFO fixtures.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from personalscraper.dispatch._identity import replace_identity_conflict


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
