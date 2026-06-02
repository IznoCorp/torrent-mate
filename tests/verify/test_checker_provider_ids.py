"""Phase 9 verify checks — provider-IDs episode-NFO hardening.

Three new ``check_tvshow`` checks land in this phase :

- ``episode_canonical_uniqueid_present`` (ERROR) — episode NFOs must
  carry the canonical ``<uniqueid>`` matching the show's
  ``tvshow.nfo`` default.
- ``episode_xref_secondary_id_present`` (WARNING) — the non-canonical
  TVDB/TMDb family should also be present.
- ``episode_xref_imdb_id_present`` (WARNING) — IMDb uniqueid feeds
  the future tracker-search flow.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from personalscraper.conf.models.config import Config
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.verify.checker import MediaChecker
from personalscraper.verify.checks.base import Severity


@pytest.fixture()
def checker(test_config: Config) -> MediaChecker:
    """Build a :class:`MediaChecker` with the project's canonical patterns."""
    return MediaChecker(NamingPatterns(), test_config)


def _build_show(
    tmp_path: Path,
    *,
    canonical_family: str,
    episode_uniqueids: list[tuple[str, str, bool]],
) -> Path:
    """Build a minimal TV show directory for the per-episode checks."""
    show_dir = tmp_path / "Show (2024)"
    show_dir.mkdir()
    season = show_dir / "Saison 01"
    season.mkdir()
    (season / "S01E01 - Pilot.mkv").write_bytes(b"\x00" * 1024)

    root = ET.Element("tvshow")
    ET.SubElement(root, "title").text = "Show"
    ET.SubElement(root, "year").text = "2024"
    uid = ET.SubElement(root, "uniqueid")
    uid.set("type", canonical_family)
    uid.set("default", "true")
    uid.text = "9001"
    ET.SubElement(root, "genre").text = "Drame"
    ET.ElementTree(root).write(show_dir / "tvshow.nfo", encoding="unicode")
    (show_dir / "poster.jpg").write_bytes(b"\xff")
    (show_dir / "landscape.jpg").write_bytes(b"\xff")

    ep_root = ET.Element("episodedetails")
    ET.SubElement(ep_root, "title").text = "Pilot"
    for kind, value, is_default in episode_uniqueids:
        element = ET.SubElement(ep_root, "uniqueid")
        element.set("type", kind)
        if is_default:
            element.set("default", "true")
        element.text = value
    ET.ElementTree(ep_root).write(season / "S01E01 - Pilot.nfo", encoding="unicode")
    return show_dir


def _result_by_name(results: list, name: str):  # type: ignore[no-untyped-def]
    return next((r for r in results if r.name == name), None)


def test_check_canonical_uniqueid_pass_when_all_have_canonical(checker: MediaChecker, tmp_path: Path) -> None:
    """Episode NFO carrying the canonical (tvdb) uniqueid passes the ERROR check."""
    show_dir = _build_show(
        tmp_path,
        canonical_family="tvdb",
        episode_uniqueids=[("tvdb", "9001", True)],
    )
    results = checker.check_tvshow(show_dir)
    check = _result_by_name(results, "episode_canonical_uniqueid_present")
    assert check is not None
    assert check.passed is True
    assert check.severity == Severity.ERROR


def test_check_canonical_uniqueid_fail_when_missing(checker: MediaChecker, tmp_path: Path) -> None:
    """Episode NFO without canonical uniqueid → ERROR check fails."""
    show_dir = _build_show(
        tmp_path,
        canonical_family="tvdb",
        episode_uniqueids=[("imdb", "tt0000001", False)],
    )
    results = checker.check_tvshow(show_dir)
    check = _result_by_name(results, "episode_canonical_uniqueid_present")
    assert check is not None
    assert check.passed is False
    assert check.severity == Severity.ERROR
    assert "tvdb" in check.message


def test_check_canonical_uniqueid_pass_when_no_episodes_yet(checker: MediaChecker, tmp_path: Path) -> None:
    """No episode NFO on disk → check passes silently (no work to do)."""
    show_dir = tmp_path / "Show (2024)"
    show_dir.mkdir()
    root = ET.Element("tvshow")
    ET.SubElement(root, "title").text = "Show"
    ET.SubElement(root, "year").text = "2024"
    uid = ET.SubElement(root, "uniqueid")
    uid.set("type", "tvdb")
    uid.set("default", "true")
    uid.text = "9001"
    ET.SubElement(root, "genre").text = "Drame"
    ET.ElementTree(root).write(show_dir / "tvshow.nfo", encoding="unicode")
    (show_dir / "poster.jpg").write_bytes(b"\xff")
    (show_dir / "landscape.jpg").write_bytes(b"\xff")

    results = checker.check_tvshow(show_dir)
    check = _result_by_name(results, "episode_canonical_uniqueid_present")
    assert check is not None
    assert check.passed is True


def test_check_xref_secondary_warning_when_tmdb_missing(checker: MediaChecker, tmp_path: Path) -> None:
    """TVDB-canonical show + episode NFO without TMDb → WARNING."""
    show_dir = _build_show(
        tmp_path,
        canonical_family="tvdb",
        episode_uniqueids=[("tvdb", "9001", True)],
    )
    results = checker.check_tvshow(show_dir)
    check = _result_by_name(results, "episode_xref_secondary_id_present")
    assert check is not None
    assert check.passed is False
    assert check.severity == Severity.WARNING
    assert "tmdb" in check.message


def test_check_xref_secondary_pass_when_both_present(checker: MediaChecker, tmp_path: Path) -> None:
    """Both canonical + xref present → WARNING check passes."""
    show_dir = _build_show(
        tmp_path,
        canonical_family="tvdb",
        episode_uniqueids=[("tvdb", "9001", True), ("tmdb", "5001", False)],
    )
    results = checker.check_tvshow(show_dir)
    check = _result_by_name(results, "episode_xref_secondary_id_present")
    assert check is not None
    assert check.passed is True


def test_check_xref_imdb_warning_when_missing(checker: MediaChecker, tmp_path: Path) -> None:
    """Missing IMDb uniqueid on episode → WARNING check fails."""
    show_dir = _build_show(
        tmp_path,
        canonical_family="tvdb",
        episode_uniqueids=[("tvdb", "9001", True), ("tmdb", "5001", False)],
    )
    results = checker.check_tvshow(show_dir)
    check = _result_by_name(results, "episode_xref_imdb_id_present")
    assert check is not None
    assert check.passed is False
    assert check.severity == Severity.WARNING


def test_check_xref_imdb_pass_when_present(checker: MediaChecker, tmp_path: Path) -> None:
    """Episode NFO carrying IMDb uniqueid → WARNING check passes."""
    show_dir = _build_show(
        tmp_path,
        canonical_family="tvdb",
        episode_uniqueids=[
            ("tvdb", "9001", True),
            ("tmdb", "5001", False),
            ("imdb", "tt0000001", False),
        ],
    )
    results = checker.check_tvshow(show_dir)
    check = _result_by_name(results, "episode_xref_imdb_id_present")
    assert check is not None
    assert check.passed is True


def test_check_tvshow_total_checks_includes_new_three(checker: MediaChecker, tmp_path: Path) -> None:
    """A fully-set show emits the three new check rows alongside the legacy set."""
    show_dir = _build_show(
        tmp_path,
        canonical_family="tvdb",
        episode_uniqueids=[
            ("tvdb", "9001", True),
            ("tmdb", "5001", False),
            ("imdb", "tt0000001", False),
        ],
    )
    results = checker.check_tvshow(show_dir)
    names = {r.name for r in results}
    assert "episode_canonical_uniqueid_present" in names
    assert "episode_xref_secondary_id_present" in names
    assert "episode_xref_imdb_id_present" in names


def test_check_canonical_uniqueid_unparseable_episode_nfo(checker: MediaChecker, tmp_path: Path) -> None:
    """An unparseable episode NFO fails the canonical ERROR check ``(unparseable)``.

    The show NFO is valid (canonical family = tvdb) so the check runs, but the
    episode NFO bytes are corrupt — the canonical check treats an unparseable
    NFO as a missing canonical uniqueid and annotates the filename.
    """
    show_dir = _build_show(
        tmp_path,
        canonical_family="tvdb",
        episode_uniqueids=[("tvdb", "9001", True)],
    )
    # Corrupt the episode NFO on disk (was written valid by _build_show).
    ep_nfo = show_dir / "Saison 01" / "S01E01 - Pilot.nfo"
    ep_nfo.write_text("<episodedetails><title>broken", encoding="utf-8")  # truncated XML

    results = checker.check_tvshow(show_dir)
    check = _result_by_name(results, "episode_canonical_uniqueid_present")
    assert check is not None
    assert check.passed is False
    assert check.severity == Severity.ERROR
    assert "(unparseable)" in check.message


def test_check_canonical_uniqueid_none_family_passes_with_episodes(checker: MediaChecker, tmp_path: Path) -> None:
    """A show NFO with NO ``<uniqueid>`` → canonical family None → check passes.

    Episodes ARE present on disk, but with no derivable canonical family the
    canonical / secondary checks are no-ops (``passed=True``), exactly as the
    legacy ``check_tvshow``.
    """
    show_dir = tmp_path / "Show (2024)"
    show_dir.mkdir()
    season = show_dir / "Saison 01"
    season.mkdir()
    (season / "S01E01 - Pilot.mkv").write_bytes(b"\x00" * 1024)

    # Show NFO with NO uniqueid at all → _canonical_family returns None.
    root = ET.Element("tvshow")
    ET.SubElement(root, "title").text = "Show"
    ET.SubElement(root, "year").text = "2024"
    ET.SubElement(root, "genre").text = "Drame"
    ET.ElementTree(root).write(show_dir / "tvshow.nfo", encoding="unicode")
    (show_dir / "poster.jpg").write_bytes(b"\xff")
    (show_dir / "landscape.jpg").write_bytes(b"\xff")

    # An episode NFO IS present (so the "no episodes" early-out is NOT the reason).
    ep_root = ET.Element("episodedetails")
    ET.SubElement(ep_root, "title").text = "Pilot"
    ET.ElementTree(ep_root).write(season / "S01E01 - Pilot.nfo", encoding="unicode")

    results = checker.check_tvshow(show_dir)
    canonical = _result_by_name(results, "episode_canonical_uniqueid_present")
    secondary = _result_by_name(results, "episode_xref_secondary_id_present")
    assert canonical is not None and canonical.passed is True
    assert secondary is not None and secondary.passed is True
