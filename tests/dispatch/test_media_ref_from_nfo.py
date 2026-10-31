"""``media_ref_from_nfo`` and ``_as_int``: the provider-id read behind ``ItemDispatched.media_ref``.

The read runs AFTER the move, so it must be total — a hostile or malformed NFO
yields ``None`` / a partial reference, never an exception.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.core.identity import MediaRef
from personalscraper.dispatch._identity import _as_int, media_ref_from_nfo


def _show_nfo(*uniqueids: str) -> str:
    """Return a ``tvshow.nfo`` body holding the given ``<uniqueid>`` elements."""
    return '<?xml version="1.0" encoding="UTF-8"?><tvshow><title>Show</title>' + "".join(uniqueids) + "</tvshow>"


def _write_show(folder: Path, *uniqueids: str) -> Path:
    """Create ``folder`` with a ``tvshow.nfo`` carrying ``uniqueids`` and return it."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "tvshow.nfo").write_text(_show_nfo(*uniqueids), encoding="utf-8")
    return folder


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("27205", 27205),
        (" 42 ", 42),
        (7, 7),
        ("0", None),
        ("abc", None),
        ("", None),
        (None, None),
        ("²", None),  # str.isdigit() is True for superscripts, int() raises
        ("٣", None),  # Arabic-Indic digit: isdigit() and int() accept it, ASCII only here
        ("1_0", None),
        ("-5", None),
    ],
)
def test_as_int_is_total_and_ascii_decimal_only(value: object, expected: int | None) -> None:
    """Only a positive ASCII decimal string is an id; every other value is ``None``."""
    assert _as_int(value) == expected


@pytest.mark.parametrize(
    ("uniqueids", "expected"),
    [
        (('<uniqueid type="tvdb">²</uniqueid>',), None),
        (('<uniqueid type="tvdb">0</uniqueid>',), None),
        (('<uniqueid type="tvdb">abc</uniqueid>',), None),
        (('<uniqueid type="imdb">tt0903747</uniqueid>',), MediaRef(imdb_id="tt0903747")),
        (('<uniqueid type="imdb">   </uniqueid>',), None),
        ((), None),
        (
            ('<uniqueid type="tvdb">²</uniqueid>', '<uniqueid type="imdb">tt1</uniqueid>'),
            MediaRef(imdb_id="tt1"),
        ),
    ],
)
def test_media_ref_from_nfo_reads_usable_ids_only(
    tmp_path: Path, uniqueids: tuple[str, ...], expected: MediaRef | None
) -> None:
    """Unusable ids are dropped; a folder with none yields ``None``; nothing raises."""
    folder = _write_show(tmp_path / "show", *uniqueids)
    assert media_ref_from_nfo("tvshow", folder) == expected


def test_media_ref_from_nfo_unreadable_nfo_is_none(tmp_path: Path) -> None:
    """A garbage / non-XML NFO is ``None``, not an exception."""
    folder = tmp_path / "show"
    folder.mkdir()
    (folder / "tvshow.nfo").write_bytes(b"\xff\xfe\x00 not xml at all")
    assert media_ref_from_nfo("tvshow", folder) is None


def test_media_ref_from_nfo_missing_folder_is_none(tmp_path: Path) -> None:
    """A folder that does not exist is skipped, not raised on."""
    assert media_ref_from_nfo("tvshow", tmp_path / "absent") is None


def test_media_ref_from_nfo_unusable_ids_fall_through_to_next_folder(tmp_path: Path) -> None:
    """Ids present but unusable in the first folder → the next folder is tried."""
    first = _write_show(tmp_path / "dest", '<uniqueid type="tvdb">²</uniqueid>')
    second = _write_show(tmp_path / "staging", '<uniqueid type="tvdb">371980</uniqueid>')
    assert media_ref_from_nfo("tvshow", first, second) == MediaRef(tvdb_id=371980)


def test_media_ref_from_nfo_destination_wins_over_staging(tmp_path: Path) -> None:
    """Different ids in destination and staging → the destination's ids (it is what the index sees)."""
    dest = _write_show(tmp_path / "dest", '<uniqueid type="tvdb">111</uniqueid>')
    staging = _write_show(tmp_path / "staging", '<uniqueid type="tvdb">222</uniqueid>')
    assert media_ref_from_nfo("tvshow", dest, staging) == MediaRef(tvdb_id=111)
