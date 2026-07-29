"""Tests for resolve_followed_tvdb — anti-split provenance resolver.

A staging show folder that came from a followed series (its grabbed episodes are
in the wanted queue) must resolve the follow's TVDB id, so the scrape forces that
id instead of re-matching a duplicate TVDB entry. Precision-first: it asserts an
id ONLY when a single follow's tvdb covers the folder AND the title matches —
otherwise it abstains (None) and the free match takes over.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.acquire.domain import WantedItem
from personalscraper.core.identity import MediaRef
from personalscraper.scraper.follow_provenance import resolve_followed_tvdb


def _show_dir(tmp_path: Path, folder: str, eps: list[tuple[int, int]]) -> Path:
    """Create a show folder with one .mkv per (season, episode)."""
    d = tmp_path / folder
    d.mkdir()
    for s, e in eps:
        (d / f"{folder}.S{s:02d}E{e:02d}.MULTi.1080p.WEB.x265-GRP.mkv").write_bytes(b"")
    return d


def _grabbed(tvdb: int, followed_id: int, eps: list[tuple[int, int]]) -> list[WantedItem]:
    """Build grabbed episode WantedItems for a follow."""
    return [
        WantedItem(
            media_ref=MediaRef(tvdb_id=tvdb),
            kind="episode",
            status="grabbed",
            enqueued_at=0,
            followed_id=followed_id,
            season=s,
            episode=e,
        )
        for s, e in eps
    ]


class TestResolveFollowedTvdb:
    """resolve_followed_tvdb over the followed-series provenance."""

    def test_rooster_grabbed_episodes_resolve_follow_tvdb(self, tmp_path: Path) -> None:
        """ACC-01: a followed show's grabbed episodes resolve the follow's tvdb."""
        eps = [(1, 6), (1, 7), (1, 8), (1, 9), (1, 10)]
        show = _show_dir(tmp_path, "Rooster Fighter", eps)
        grabbed = _grabbed(457770, 14, eps)
        assert resolve_followed_tvdb(show, grabbed, {14: "Rooster"}) == 457770

    def test_partial_episode_overlap_still_resolves(self, tmp_path: Path) -> None:
        """A folder whose episodes are a subset of the follow's grabbed set resolves."""
        show = _show_dir(tmp_path, "Rooster Fighter", [(1, 6), (1, 7)])
        grabbed = _grabbed(457770, 14, [(1, 6), (1, 7), (1, 8)])
        assert resolve_followed_tvdb(show, grabbed, {14: "Rooster"}) == 457770

    def test_two_follows_sharing_episode_abstains(self, tmp_path: Path) -> None:
        """ACC-02: two follows both grabbed S01E06 → ambiguous → None."""
        show = _show_dir(tmp_path, "Some Show", [(1, 6)])
        grabbed = _grabbed(111, 1, [(1, 6)]) + _grabbed(222, 2, [(1, 6)])
        titles = {1: "Some Show", 2: "Some Show"}
        assert resolve_followed_tvdb(show, grabbed, titles) is None

    def test_dissimilar_title_abstains(self, tmp_path: Path) -> None:
        """ACC-02: the folder title must match the follow title (guard)."""
        show = _show_dir(tmp_path, "Rooster Fighter", [(1, 6)])
        grabbed = _grabbed(457770, 14, [(1, 6)])
        assert resolve_followed_tvdb(show, grabbed, {14: "Breaking Bad"}) is None

    def test_no_grabbed_returns_none(self, tmp_path: Path) -> None:
        """ACC-03: an empty grabbed set yields None (free match)."""
        show = _show_dir(tmp_path, "Rooster Fighter", [(1, 6)])
        assert resolve_followed_tvdb(show, [], {}) is None

    def test_no_episode_in_folder_returns_none(self, tmp_path: Path) -> None:
        """A folder with no parseable episode yields None."""
        d = tmp_path / "Mystery"
        d.mkdir()
        (d / "readme.txt").write_bytes(b"")
        grabbed = _grabbed(457770, 14, [(1, 6)])
        assert resolve_followed_tvdb(d, grabbed, {14: "Mystery"}) is None

    def test_grabbed_without_tvdb_is_ignored(self, tmp_path: Path) -> None:
        """A grabbed wanted with no tvdb_id cannot force anything."""
        show = _show_dir(tmp_path, "Rooster Fighter", [(1, 6)])
        grabbed = [
            WantedItem(
                media_ref=MediaRef(tmdb_id=999),
                kind="episode",
                status="grabbed",
                enqueued_at=0,
                followed_id=14,
                season=1,
                episode=6,
            )
        ]
        assert resolve_followed_tvdb(show, grabbed, {14: "Rooster Fighter"}) is None

    def test_episode_not_in_grabbed_abstains(self, tmp_path: Path) -> None:
        """A folder episode NOT covered by any grabbed wanted → None (not this follow)."""
        show = _show_dir(tmp_path, "Rooster Fighter", [(1, 11)])
        grabbed = _grabbed(457770, 14, [(1, 6), (1, 7)])
        assert resolve_followed_tvdb(show, grabbed, {14: "Rooster"}) is None


class TestReviewHardening:
    """Regression tests for the PR #339 adversarial review (precision-first)."""

    def test_different_year_remake_does_not_force(self, tmp_path: Path) -> None:
        """Finding 1: a different-year remake must not force the follow's tvdb.

        An unfollowed 'X (1963)' folder must NOT get a followed 'X' (2005) tvdb
        via a coincidental shared episode — the year guard blocks it.
        """
        show = _show_dir(tmp_path, "Doctor Who (1963)", [(1, 6)])
        grabbed = _grabbed(78804, 5, [(1, 6)])  # followed Doctor Who (2005)
        titles = {5: "Doctor Who"}
        years = {5: 2005}
        assert resolve_followed_tvdb(show, grabbed, titles, years) is None

    def test_matching_year_still_resolves(self, tmp_path: Path) -> None:
        """A folder year that AGREES with the follow year still resolves."""
        show = _show_dir(tmp_path, "Rooster Fighter (2026)", [(1, 6)])
        grabbed = _grabbed(457770, 14, [(1, 6)])
        assert resolve_followed_tvdb(show, grabbed, {14: "Rooster"}, {14: 2026}) == 457770

    def test_coverage_all_required(self, tmp_path: Path) -> None:
        """Finding 1: every folder episode must be covered — a partial cover abstains."""
        show = _show_dir(tmp_path, "Rooster Fighter", [(1, 6), (1, 7)])
        grabbed = _grabbed(457770, 14, [(1, 6)])  # only E06 grabbed
        assert resolve_followed_tvdb(show, grabbed, {14: "Rooster"}) is None

    def test_recursive_saison_folder(self, tmp_path: Path) -> None:
        """Finding 4: episodes nested under 'Saison NN/' are parsed (recursive)."""
        d = tmp_path / "Rooster Fighter"
        (d / "Saison 01").mkdir(parents=True)
        (d / "Saison 01" / "Rooster Fighter.S01E06.mkv").write_bytes(b"")
        grabbed = _grabbed(457770, 14, [(1, 6)])
        assert resolve_followed_tvdb(d, grabbed, {14: "Rooster"}) == 457770

    def test_multi_episode_file(self, tmp_path: Path) -> None:
        """Finding 3: a multi-episode file (S01E06E07) contributes both episodes."""
        d = tmp_path / "Rooster Fighter"
        d.mkdir()
        (d / "Rooster Fighter.S01E06E07.mkv").write_bytes(b"")
        grabbed = _grabbed(457770, 14, [(1, 6), (1, 7)])
        assert resolve_followed_tvdb(d, grabbed, {14: "Rooster"}) == 457770

    def test_missing_folder_year_falls_back_to_title(self, tmp_path: Path) -> None:
        """No year in the folder ⇒ the year guard is inert (Rooster's real case)."""
        show = _show_dir(tmp_path, "Rooster Fighter", [(1, 6)])
        grabbed = _grabbed(457770, 14, [(1, 6)])
        assert resolve_followed_tvdb(show, grabbed, {14: "Rooster"}, {14: 2026}) == 457770
