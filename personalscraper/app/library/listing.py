"""The listing's orders, and the one the application computes itself: « missing ».

A page in ``RECENT`` or ``AZ`` is filtered, ordered, counted and cut by the indexer
(:meth:`LibraryReader.page <personalscraper.indexer.library_view.LibraryReader.page>`).
« Missing » crosses the aired catalogue in ``acquire.db``, which no query over
``library.db`` reaches: those rows are read whole (``live_items``) and ordered and paged
here, the one listing still computed in Python.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from enum import StrEnum
from pathlib import Path

from personalscraper.indexer.library_view import LIBRARY_PAGE_SIZE, MEDIA_FOLDER_DEPTH, IndexItem


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
