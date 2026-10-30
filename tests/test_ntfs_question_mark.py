"""U+F025 (NTFS/macFUSE private-use stand-in for « ? ») equals « ? » at every name comparison site."""

from __future__ import annotations

import unicodedata

from personalscraper._fs_utils import fold_ntfs_question_mark, name_key, name_variants
from personalscraper.dispatch.media_index import _normalize_key
from personalscraper.dispatch.post_maintenance import _rel_path_variants
from personalscraper.indexer.repos.item_repo import _canonical_title

_PUA = ""
_WITH_PUA = f"Who Is Robin{_PUA} (2020)"
_WITH_QMARK = "Who Is Robin? (2020)"


def test_fold_maps_private_use_char_to_question_mark() -> None:
    """The private-use character becomes a real « ? »; a real « ? » is untouched."""
    assert fold_ntfs_question_mark(_WITH_PUA) == _WITH_QMARK
    assert fold_ntfs_question_mark(_WITH_QMARK) == _WITH_QMARK


def test_name_key_equates_both_spellings_and_unicode_forms() -> None:
    """Both spellings, in NFC or NFD, give one key."""
    nfd = unicodedata.normalize("NFD", _WITH_PUA.replace("Robin", "Rôbin"))
    nfc = unicodedata.normalize("NFC", _WITH_QMARK.replace("Robin", "Rôbin"))
    assert name_key(nfd) == name_key(nfc)


def test_name_variants_cover_each_character() -> None:
    """From either spelling the variants hold both spellings."""
    for source in (_WITH_PUA, _WITH_QMARK):
        variants = name_variants(source)
        assert _WITH_PUA in variants
        assert _WITH_QMARK in variants


def test_dispatch_lookup_key_equates_the_twins() -> None:
    """The dispatch index key of a U+F025 name equals that of its « ? » twin."""
    assert _normalize_key(_WITH_PUA) == _normalize_key(_WITH_QMARK)


def test_indexer_canonical_title_equates_the_twins() -> None:
    """The indexer's dedup title of a U+F025 name equals that of its « ? » twin."""
    assert _canonical_title(_WITH_PUA) == _canonical_title(_WITH_QMARK)


def test_refresh_path_variants_hold_both_characters() -> None:
    """A refresh given one spelling invalidates rows stored under the other."""
    for source in (f"series/{_WITH_PUA}", f"series/{_WITH_QMARK}"):
        variants = _rel_path_variants(source)
        assert f"series/{_WITH_PUA}" in variants
        assert f"series/{_WITH_QMARK}" in variants
