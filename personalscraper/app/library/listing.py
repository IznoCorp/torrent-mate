"""The listing's orders, and the one the application computes itself: « missing ».

A page in ``RECENT`` or ``AZ`` is filtered, ordered, counted and cut by the indexer
(:meth:`LibraryReader.page <personalscraper.indexer.library_view.LibraryReader.page>`).
« Missing » crosses the aired catalogue in ``acquire.db``, which no query over
``library.db`` reaches: those rows are read whole (``live_items``) and ordered and paged
here, the one listing still computed in Python.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from contextlib import AbstractContextManager
from enum import StrEnum
from pathlib import Path

from personalscraper.app.errors import AppUnavailable, RefusalCode
from personalscraper.app.library.identity import ref_key
from personalscraper.core.identity import ItemId, MediaRef
from personalscraper.indexer.library_view import (
    LIBRARY_PAGE_SIZE,
    MEDIA_FOLDER_DEPTH,
    IndexItem,
    IndexUnavailable,
    LibraryIndex,
    LibraryReader,
)
from personalscraper.logger import get_logger

log = get_logger("app.library.listing")


class LibrarySort(StrEnum):
    """The listing's orders, by their wire values; ``RECENT`` is the order an absent ``sort`` asks for."""

    RECENT = "recent"
    AZ = "az"
    MISSING = "missing"


def resolve_media_folder(mount_path: str, folder: str) -> tuple[Path, Path] | None:
    """Resolve one media folder inside its disk, never anything outside it.

    The folder must resolve inside its disk's mount point, exactly ``MEDIA_FOLDER_DEPTH``
    segments below it (a media folder, never a category nor the disk itself), and be a
    directory: a symlink or a ``..`` leading elsewhere is refused, whatever it reaches.

    Args:
        mount_path: The disk's mount point, as the index names it.
        folder: The media folder below it, as the index names it.

    Returns:
        ``(the mount point, the folder)``, both resolved; ``None`` when the disk or the
        folder is not there, is not a directory, escapes, or when a symlink loops.
    """
    try:
        root = Path(mount_path).resolve(strict=True)
        directory = (root / folder).resolve(strict=True)
        if not directory.is_relative_to(root) or not directory.is_dir():
            return None
    except (OSError, RuntimeError):
        # Python 3.12's strict resolve raises RuntimeError, not OSError, on a symlink loop.
        return None
    if len(directory.relative_to(root).parts) != MEDIA_FOLDER_DEPTH:
        return None
    return root, directory


def ordered_by_missing(
    rows: Iterable[IndexItem],
    reversed_: bool,
    missing_of: Callable[[IndexItem], int | None],
) -> list[IndexItem]:
    """Order rows by the episodes they miss.

    The most episodes missing first, every row with nothing known (a movie, a show never
    catalogued) last; the sort is stable over the rows' own order (most recently added
    first). Reversing is a second pass over the result, never a second comparator (the
    maquette's rule).

    Args:
        rows: The rows, most recently added first.
        reversed_: Whether to read it the other way round.
        missing_of: How many aired episodes a row lacks, or ``None`` when nothing says.

    Returns:
        The ordered rows.
    """
    held = list(rows)
    missing = {row.item_id: missing_of(row) for row in held}
    held.sort(key=lambda row: (missing[row.item_id] is None, -(missing[row.item_id] or 0)))
    if reversed_:
        held.reverse()
    return held


def page_of(rows: Sequence[IndexItem], page: int, size: int = LIBRARY_PAGE_SIZE) -> Sequence[IndexItem]:
    """Cut one page out of ordered rows.

    Args:
        rows: The ordered rows.
        page: The page, zero based; a page past the end is empty.
        size: Rows per page.

    Returns:
        The page's rows.
    """
    return rows[page * size : (page + 1) * size]


def library_unavailable(exc: IndexUnavailable) -> AppUnavailable:
    """Log why ``library.db`` cannot be read, and build the refusal the wire answers.

    Args:
        exc: The indexer's refusal to open the index; its cause is the SQLite failure.

    Returns:
        The 503 ``library.unavailable`` refusal; it names no path and no SQLite text.
    """
    cause = exc.__cause__ or exc
    log.error("app.library.index_unavailable", error=type(cause).__name__, reason=str(cause))
    return AppUnavailable("The library index cannot be read.", code=RefusalCode.LIBRARY_UNAVAILABLE)


def open_reader(index: LibraryIndex) -> AbstractContextManager[LibraryReader]:
    """Open a reader over ``library.db`` (:meth:`LibraryIndex.reader`).

    Args:
        index: The library index.

    Returns:
        The reader, to be used as a context manager that closes it.

    Raises:
        AppUnavailable: ``library.unavailable`` when ``library.db`` is absent, cannot be
            opened or is not a database; the cause goes to the log, never to the wire.
    """
    try:
        return index.reader()
    except IndexUnavailable as exc:
        raise library_unavailable(exc) from exc


def holders_of(reader: LibraryReader, ref: MediaRef) -> list[IndexItem]:
    """Every row carrying the reference's id.

    Args:
        reader: The open index.
        ref: The medium.

    Returns:
        The holding rows, live or not, by id.
    """
    provider, provider_id = ref_key(ref)
    return reader.holders(provider.value, provider_id)


def held_of(reader: LibraryReader, ref: MediaRef) -> tuple[list[IndexItem], dict[ItemId, set[str]]]:
    """The rows holding a reference and the media folders of their live files.

    Args:
        reader: The open index.
        ref: The medium.

    Returns:
        ``(holders, {item_id: folders})``; a holder absent from the mapping has no live file.
    """
    holders = holders_of(reader, ref)
    return holders, reader.live_folders([row.item_id for row in holders])
