"""Regression tests for phase 4 of the ``provider-ids`` feature.

DEV #2 root cause layer 5 : the drift validator's check #4 only
verified that a sibling ``.nfo`` *existed* alongside every episode
video — never that the NFO carried a canonical ``<uniqueid>``. That
allowed ``scrape_fast_skip`` to perpetuate the empty-NFO state
introduced by layers 1-4. This file pins the hardened check in place :

- A NFO with no ``<uniqueid>`` at all triggers drift.
- A NFO with only an off-family uniqueid (e.g. ``imdb`` on a
  TVDB-canonical show) triggers drift.
- A NFO with the canonical ``<uniqueid>`` is accepted regardless of
  whether xref uniqueids are also present.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper.existing_validator import verify_tvshow_scrape_drift


def _patterns() -> NamingPatterns:
    return NamingPatterns()


def _build_show_dir(
    root: Path,
    *,
    canonical_family: str = "tvdb",
    canonical_id: str = "12345",
    extra_uniqueid: tuple[str, str] | None = None,
    episode_uniqueids: list[tuple[str, str, bool]] | None = None,
) -> tuple[Path, Path]:
    """Build a fully-formed show directory ready for the drift check.

    Args:
        root: Base ``tmp_path`` from the test.
        canonical_family: The provider written as ``<uniqueid default="true">``.
        canonical_id: Numeric ID associated with the canonical family.
        extra_uniqueid: Optional ``(type, id)`` tuple written as a
            non-default uniqueid on ``tvshow.nfo``.
        episode_uniqueids: List of ``(type, id, is_default)`` tuples
            written into the episode-level NFO. Empty list ⇒ NFO with
            no ``<uniqueid>`` at all. ``None`` ⇒ no sibling NFO file
            (legacy missing-NFO case kept for differential coverage).

    Returns:
        ``(show_dir, tvshow_nfo)`` paths so the caller can re-write
        either before invoking the drift check.
    """
    patterns = _patterns()
    show_dir = root / patterns.format("movie_dir", Title="Show", Year="2020")
    show_dir.mkdir()
    season_dir = show_dir / "Saison 01"
    season_dir.mkdir()
    episode_video = season_dir / "S01E01 - Pilot.mkv"
    episode_video.write_bytes(b"x")
    (show_dir / patterns.tvshow_poster).write_bytes(b"poster")
    (show_dir / patterns.tvshow_landscape).write_bytes(b"landscape")

    tvshow_lines = ['<?xml version="1.0"?>', "<tvshow>", "<title>Show</title>", "<year>2020</year>"]
    tvshow_lines.append(f'<uniqueid type="{canonical_family}" default="true">{canonical_id}</uniqueid>')
    if extra_uniqueid is not None:
        kind, value = extra_uniqueid
        tvshow_lines.append(f'<uniqueid type="{kind}">{value}</uniqueid>')
    tvshow_lines.append("</tvshow>")
    tvshow_nfo = show_dir / "tvshow.nfo"
    tvshow_nfo.write_text("\n".join(tvshow_lines), encoding="utf-8")

    if episode_uniqueids is not None:
        ep_lines = ['<?xml version="1.0"?>', "<episodedetails>", "<title>Pilot</title>"]
        for kind, value, is_default in episode_uniqueids:
            default_attr = ' default="true"' if is_default else ""
            ep_lines.append(f'<uniqueid type="{kind}"{default_attr}>{value}</uniqueid>')
        ep_lines.append("</episodedetails>")
        (season_dir / "S01E01 - Pilot.nfo").write_text("\n".join(ep_lines), encoding="utf-8")

    return show_dir, tvshow_nfo


# ---------------------------------------------------------------------------
# 4.1 (a) — RED : missing canonical uniqueid on episode NFO
# ---------------------------------------------------------------------------


def test_verify_drift_rejects_episode_nfo_without_canonical_uniqueid(tmp_path: Path) -> None:
    """Episode NFO with zero ``<uniqueid>`` tags → drift fail.

    Pre-fix : the validator only checked that the sibling NFO file
    existed, so this case slipped through and the broken state
    persisted across runs. Post-fix : the validator returns
    ``episode_nfo_missing_canonical_uniqueid``.
    """
    show_dir, tvshow_nfo = _build_show_dir(
        tmp_path,
        canonical_family="tvdb",
        episode_uniqueids=[],
    )
    valid, reason = verify_tvshow_scrape_drift(show_dir, tvshow_nfo, _patterns())

    assert valid is False
    assert reason.startswith("episode_nfo_missing_canonical_uniqueid")


def test_verify_drift_rejects_episode_nfo_with_wrong_family_uniqueid(tmp_path: Path) -> None:
    """TVDB-canonical show + episode NFO carrying only an ``imdb`` uniqueid → drift fail.

    The xref-only NFO does not satisfy the canonical-family invariant
    (DESIGN §3 hierarchy). Pre-fix : the legacy check accepted it.
    Post-fix : the validator returns
    ``episode_nfo_missing_canonical_uniqueid``.
    """
    show_dir, tvshow_nfo = _build_show_dir(
        tmp_path,
        canonical_family="tvdb",
        episode_uniqueids=[("imdb", "tt0000001", True)],
    )
    valid, reason = verify_tvshow_scrape_drift(show_dir, tvshow_nfo, _patterns())

    assert valid is False
    assert reason.startswith("episode_nfo_missing_canonical_uniqueid")


# ---------------------------------------------------------------------------
# 4.1 (b) — Acceptance : canonical uniqueid only is enough
# ---------------------------------------------------------------------------


def test_verify_drift_accepts_episode_nfo_with_canonical_uniqueid_only(tmp_path: Path) -> None:
    """Canonical TVDB uniqueid + no xref uniqueid → drift OK.

    Xref enrichment (TMDb / IMDb episode IDs) is best-effort — the
    drift validator must not punish episodes whose xref lookup
    returned no data.
    """
    show_dir, tvshow_nfo = _build_show_dir(
        tmp_path,
        canonical_family="tvdb",
        episode_uniqueids=[("tvdb", "9001", True)],
    )
    valid, reason = verify_tvshow_scrape_drift(show_dir, tvshow_nfo, _patterns())

    assert valid is True, f"unexpected drift reason: {reason}"
    assert reason == "ok"


# ---------------------------------------------------------------------------
# 4.1 (c) — Acceptance : full uniqueid set
# ---------------------------------------------------------------------------


def test_verify_drift_accepts_episode_nfo_with_full_uniqueids(tmp_path: Path) -> None:
    """TVDB + TMDb + IMDb uniqueids on the episode NFO → drift OK."""
    show_dir, tvshow_nfo = _build_show_dir(
        tmp_path,
        canonical_family="tvdb",
        episode_uniqueids=[
            ("tvdb", "9001", True),
            ("tmdb", "5005", False),
            ("imdb", "tt0000001", False),
        ],
    )
    valid, reason = verify_tvshow_scrape_drift(show_dir, tvshow_nfo, _patterns())

    assert valid is True, f"unexpected drift reason: {reason}"
    assert reason == "ok"


# ---------------------------------------------------------------------------
# 4.1 (d) — TMDb-canonical show requires TMDb canonical uniqueid on episodes
# ---------------------------------------------------------------------------


def test_verify_drift_rejects_tvdb_episode_uniqueid_on_tmdb_canonical_show(tmp_path: Path) -> None:
    """TMDB-canonical show + episode NFO carrying only TVDB → drift fail.

    Symmetric of the TVDB-canonical case : the canonical family read
    from ``tvshow.nfo`` determines what the episode NFOs must carry.
    """
    show_dir, tvshow_nfo = _build_show_dir(
        tmp_path,
        canonical_family="tmdb",
        episode_uniqueids=[("tvdb", "9001", False)],
    )
    valid, reason = verify_tvshow_scrape_drift(show_dir, tvshow_nfo, _patterns())

    assert valid is False
    assert reason.startswith("episode_nfo_missing_canonical_uniqueid")
