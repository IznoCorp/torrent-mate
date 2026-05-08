"""Design-contract tests for the trailers feature.

Pin points for ``docs/reference/trailers.md`` (codename: ``trailers``) — the
Plex-conformant trailer placement convention (movies flat, TV shows in a
``Trailers/`` subfolder).
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.trailers.placement import trailer_path_for


class TestTrailerPlacementContract:
    """Trailer placement — DESIGN trailers.md §Pipeline Step."""

    def test_movie_trailer_is_flat_next_to_media(self, tmp_path: Path) -> None:
        """Movie trailer lands flat next to the media folder.

        Design: docs/reference/trailers.md#pipeline-step
        Contract: For ``media_type='movie'`` the path is
        ``{media_dir}/{media_name}-trailer.{ext}`` per Plex Local Media
        Assets — no subfolder.
        """
        media_dir = tmp_path / "Fight Club (1999)"
        path = trailer_path_for(media_dir, "Fight Club (1999)", media_type="movie", ext="mp4")
        assert path == media_dir / "Fight Club (1999)-trailer.mp4"

    def test_tvshow_trailer_lands_in_trailers_subfolder(self, tmp_path: Path) -> None:
        """TV-show trailer lands in a Trailers/ subfolder.

        Design: docs/reference/trailers.md#pipeline-step
        Contract: For ``media_type='tvshow'`` the path is
        ``{media_dir}/Trailers/{media_name}.{ext}`` — the only convention
        Plex's TV Series agent recognises for show-level extras.
        """
        media_dir = tmp_path / "Breaking Bad (2008)"
        path = trailer_path_for(media_dir, "Breaking Bad (2008)", media_type="tvshow", ext="mp4")
        assert path == media_dir / "Trailers" / "Breaking Bad (2008).mp4"
