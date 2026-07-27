"""INDEXER-03: the two scan modes write ONE ``artwork_json`` truth.

The enrich scan mode (:func:`_inventory_artwork`) and the full/item-stage scan
mode (:func:`_artwork_inventory_movie` / :func:`_artwork_inventory_tvshow`) now
both classify artwork through the single canonical owner
(:mod:`personalscraper.core.artwork_naming`). This regression pins that they
produce a byte-identical ``artwork_json`` for the same directory — even when it
mixes the spellings the two modes used to disagree on: MediaElch's short
``-logo`` / ``-disc`` aliases (the item-stage flags missed them), the Kodi
``folder.jpg`` (enrich missed it), and per-season posters (enrich counted them
as the item poster, item-stage excluded them).
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.indexer.scanner._modes._item_stage import (
    _artwork_inventory_movie,
    _artwork_inventory_tvshow,
)
from personalscraper.indexer.scanner._modes.enrich import _inventory_artwork


def _make_union_fixture(tmp_path: Path) -> Path:
    """Create a directory exercising every spelling the modes used to split on."""
    media = tmp_path / "Heat (1995)"
    media.mkdir()
    (media / "folder.jpg").write_bytes(b"x")  # Kodi poster — enrich used to miss it
    (media / "Heat (1995)-fanart.jpg").write_bytes(b"x")  # scraper-prefixed fanart
    (media / "Heat (1995)-landscape.png").write_bytes(b"x")  # scraper-prefixed landscape
    (media / "Heat (1995)-logo.png").write_bytes(b"x")  # MediaElch clearlogo alias
    (media / "Heat (1995)-disc.png").write_bytes(b"x")  # MediaElch discart alias
    (media / "characterart.jpg").write_bytes(b"x")  # bare characterart
    (media / "season01-poster.jpg").write_bytes(b"x")  # per-season poster — excluded
    return media


def test_enrich_and_item_stage_write_identical_artwork_json(tmp_path: Path) -> None:
    """Both scan modes serialise the SAME ``artwork_json`` for one directory."""
    media = _make_union_fixture(tmp_path)

    enrich_inv = _inventory_artwork(str(media))
    assert enrich_inv is not None
    enrich_json = enrich_inv.model_dump_json()
    movie_json = _artwork_inventory_movie(media, "Heat").model_dump_json()
    tvshow_json = _artwork_inventory_tvshow(media).model_dump_json()

    # INDEXER-03: one truth, regardless of scan path or media type.
    assert enrich_json == movie_json == tvshow_json


def test_union_broadens_detection_as_intended(tmp_path: Path) -> None:
    """The union sees folder.jpg + MediaElch -logo/-disc and drops season posters."""
    media = _make_union_fixture(tmp_path)
    inv = _inventory_artwork(str(media))
    assert inv is not None

    assert inv.poster is True  # from folder.jpg (§9/INDEXER-03: enrich now sees it)
    assert inv.fanart is True
    assert inv.landscape is True
    assert inv.clearlogo is True  # from the MediaElch -logo alias (item-stage now sees it)
    assert inv.discart is True  # from the MediaElch -disc alias
    assert inv.characterart is True  # both modes now build the full 8 kinds


def test_season_posters_are_not_the_item_poster_in_either_mode(tmp_path: Path) -> None:
    """A directory holding ONLY a season poster is poster-less to both modes."""
    media = tmp_path / "Silo (2023)"
    media.mkdir()
    (media / "season01-poster.jpg").write_bytes(b"x")

    enrich_inv = _inventory_artwork(str(media))
    assert enrich_inv is not None
    assert enrich_inv.poster is False
    assert _artwork_inventory_movie(media, "Silo").poster is False
    assert _artwork_inventory_tvshow(media).poster is False
