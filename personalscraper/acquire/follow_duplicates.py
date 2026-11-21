"""The provider ids held by two or more follows: a read, nothing folded.

Before ``store.follow.add`` merged the ids a follow learns, one medium could be written
twice: stored ``{tvdb: X}``, then followed from its TMDB card as ``{tvdb: X, tmdb: Y}``,
a second row the whole-JSON unique index (migration ``004``) does not catch. This module
names those rows: one :class:`FollowDuplicate` per provider id that two or more rows hold,
inactive rows included. TVDB and TMDB number films and shows apart, so their ids are
grouped within one kind, and an IMDb id names one medium whatever the kind: a film and a
show sharing one, which ``add`` keeps on two rows (``acquire.follow.kind_conflict``), are
listed too. It writes nothing. What becomes of a duplicate is the operator's decision, and the
``acquisition-follow-duplicates`` command measures them first.

Imports: ``acquire/``, ``core/`` + stdlib only.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from personalscraper.acquire._ports import FollowSubStore
from personalscraper.acquire.domain import FollowKind
from personalscraper.acquire.store import _FollowSubStore
from personalscraper.core.sqlite import connect_read_only

FollowProvider = Literal["tvdb", "tmdb", "imdb"]

#: The order the groups are listed in, the lookup's own: tvdb, then tmdb, then imdb.
_PROVIDERS: tuple[FollowProvider, ...] = ("tvdb", "tmdb", "imdb")


@dataclass(frozen=True, slots=True)
class FollowDuplicate:
    """One provider id held by two or more ``followed_series`` rows.

    Attributes:
        provider: The provider the id belongs to.
        provider_id: The id, as stored (an ``int`` for TVDB and TMDB, a ``str`` for IMDb).
        kind: The rows' kind for a TVDB or TMDB id; ``None`` for an IMDb id, which
            names one medium across kinds.
        followed_ids: The rowids of the rows holding it, oldest first.
    """

    provider: FollowProvider
    provider_id: int | str
    kind: FollowKind | None
    followed_ids: tuple[int, ...]


def _listing_order(group: FollowDuplicate) -> tuple[int, str, bool, int | str]:
    """Return the sort key of a group: its provider's rank, its kind, then its id.

    The type flag keeps a TVDB or TMDB id stored as text (a row written by hand) from
    being compared with an integer id of the same provider: a ``TypeError`` would fail
    the whole read.

    Args:
        group: The group to place.

    Returns:
        ``(provider rank, kind, id is a string, id)``.
    """
    return (
        _PROVIDERS.index(group.provider),
        group.kind or "",
        isinstance(group.provider_id, str),
        group.provider_id,
    )


def find_follow_duplicates(store: FollowSubStore) -> list[FollowDuplicate]:
    """Name every provider id that two or more follow rows hold.

    Read only: one ``list_all`` over the follow sub-store, grouped in memory: a TVDB or
    TMDB id with the row's kind, an IMDb id alone. A row holding the same TVDB and TMDB
    ids as another appears in both groups.

    Args:
        store: The follow sub-store (``store.follow``, or :func:`open_follows_read_only`).

    Returns:
        The groups, by provider (tvdb, tmdb, imdb), kind, then id; empty when no id is
        shared.
    """
    holders: dict[tuple[FollowProvider, int | str, FollowKind | None], list[int]] = {}
    for follow in store.list_all():  # by rowid, so each group lists its rows oldest first
        assert follow.id is not None  # every stored row carries its rowid
        ref = follow.media_ref
        for provider, value in zip(_PROVIDERS, (ref.tvdb_id, ref.tmdb_id, ref.imdb_id), strict=True):
            if value is not None:
                kind = None if provider == "imdb" else follow.kind
                holders.setdefault((provider, value, kind), []).append(follow.id)
    groups = [
        FollowDuplicate(provider=provider, provider_id=value, kind=kind, followed_ids=tuple(ids))
        for (provider, value, kind), ids in holders.items()
        if len(ids) >= 2
    ]
    return sorted(groups, key=_listing_order)


@contextmanager
def open_follows_read_only(db_path: Path) -> Iterator[FollowSubStore]:
    """Open the follows of an ``acquire.db`` read only, for a report run outside the store.

    The store's own open takes the migration lock and migrates; a report must do neither,
    least of all against a copy of production's file. The connection is ``query_only``
    (:func:`~personalscraper.core.sqlite.connect_read_only`) and is closed on exit.

    Args:
        db_path: The ``acquire.db`` to read; it must exist (it is never created).

    Yields:
        A follow sub-store over the read-only connection.

    Raises:
        sqlite3.Error: The file cannot be opened, or is no database.
    """
    with closing(connect_read_only(db_path)) as conn:
        yield _FollowSubStore(conn)
