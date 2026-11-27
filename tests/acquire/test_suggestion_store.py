"""Migration 028 and the ``suggestion`` sub-store (K3 P11c, DESIGN § 2.11).

The deck a refresh builds is replaced wholesale in one transaction; a read pages it by the
row's own rising key, so a stale cursor never skips a row of a newer deck.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.acquire.domain import SuggestionRow
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.sqlite import apply_migrations, open_db

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "acquire" / "migrations"


def _row(provider_id: str, *, provider: str = "trakt", kind: str = "show", **extra: object) -> SuggestionRow:
    """A deck row, with every column a value unless the test overrides it.

    Args:
        provider_id: The suggested title's id at its provider.
        provider: The provider that recommended it.
        kind: ``"movie"`` or ``"show"``.
        **extra: Columns to override.

    Returns:
        The row, unpersisted (no ``id``).
    """
    fields: dict[str, object] = {
        "provider": provider,
        "provider_id": provider_id,
        "kind": kind,
        "title": f"Title {provider_id}",
        "year": 2020,
        "rating": None,
        "poster": None,
        "reason": "similar_to_owned",
        "seed_key": "tmdb:603",
        "refreshed_at": 1_800_000_000,
    }
    fields.update(extra)
    return SuggestionRow(**fields)  # type: ignore[arg-type]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield an acquire store on a fresh ``acquire.db``.

    Args:
        tmp_path: Pytest temp directory.

    Yields:
        The store; closed after the test.
    """
    opened = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield opened
    finally:
        opened.close()


class TestMigration028:
    """The script on a fresh store and on a 027 store."""

    def test_the_table_has_the_columns_the_design_names(self, store: ConcreteAcquireStore) -> None:
        """provider, provider_id, kind, title, year, rating, poster, reason code, seed key, refreshed_at."""
        conn = store._ensure_open()
        columns = {row[1] for row in conn.execute("PRAGMA table_info(suggestion)")}
        assert {
            "provider",
            "provider_id",
            "kind",
            "title",
            "year",
            "rating",
            "poster",
            "reason",
            "seed_key",
            "refreshed_at",
        } <= columns
        assert conn.execute("PRAGMA user_version").fetchone()[0] >= 28
        assert conn.execute("SELECT 1 FROM schema_version WHERE version = 28").fetchone() is not None
        assert {row[1] for row in conn.execute("PRAGMA table_info(suggestion_seed)")} == {"seed_key", "asked_at"}

    def test_a_027_store_gains_the_table_and_keeps_its_rows(self, tmp_path: Path) -> None:
        """Additive: a store migrated to 027 keeps its follow when 028 applies."""
        partial = tmp_path / "migrations"
        partial.mkdir()
        for script in MIGRATIONS_DIR.glob("*.sql"):
            if int(script.name.split("_", 1)[0]) <= 27:
                shutil.copy(script, partial / script.name)
        conn = open_db(tmp_path / "acquire.db")
        apply_migrations(conn, partial)
        conn.execute(
            "INSERT INTO followed_series (media_ref_json, title, active, added_at, kind) "
            "VALUES ('{\"tvdb_id\": 81189}', 'Breaking Bad', 1, 1, 'show')"
        )
        conn.commit()
        assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'suggestion'").fetchone() is None

        apply_migrations(conn, MIGRATIONS_DIR)

        assert conn.execute("SELECT title FROM followed_series").fetchall() == [("Breaking Bad",)]
        assert conn.execute("SELECT COUNT(*) FROM suggestion").fetchone()[0] == 0
        conn.close()

    @pytest.mark.parametrize(
        ("column", "value"),
        [("kind", "tv"), ("reason", "because")],
    )
    def test_a_bad_kind_or_reason_is_refused(self, store: ConcreteAcquireStore, column: str, value: str) -> None:
        """The CHECK constraints name the kinds and the reason codes the engine writes."""
        conn = store._ensure_open()
        values = {
            "provider": "trakt",
            "provider_id": "x",
            "kind": "show",
            "title": "T",
            "reason": "similar_to_owned",
            "seed_key": "tmdb:1",
            "refreshed_at": 1,
        }
        values[column] = value
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO suggestion (provider, provider_id, kind, title, reason, seed_key, refreshed_at) "
                "VALUES (:provider, :provider_id, :kind, :title, :reason, :seed_key, :refreshed_at)",
                values,
            )


class TestDeck:
    """``store.suggestions``: the deck's writer and its paged reader."""

    def test_an_empty_store_has_no_deck(self, store: ConcreteAcquireStore) -> None:
        """Nothing was ever refreshed: no row, no date."""
        assert store.suggestions.after(None, 10) == []
        assert store.suggestions.refreshed_at() is None

    def test_replace_deck_writes_every_column_and_reads_in_insertion_order(self, store: ConcreteAcquireStore) -> None:
        """A row comes back as written, with the key the store gave it, the first written first."""
        written = _row("b", year=1999, rating=7.5, poster="https://img/b.jpg", reason="similar_to_followed")
        store.suggestions.replace_deck([written, _row("a")])

        rows = store.suggestions.after(None, 10)

        assert [r.provider_id for r in rows] == ["b", "a"]
        first = rows[0]
        assert first.id is not None and rows[1].id is not None and first.id < rows[1].id
        assert (first.year, first.rating, first.poster, first.reason) == (
            1999,
            7.5,
            "https://img/b.jpg",
            "similar_to_followed",
        )
        assert (first.provider, first.kind, first.title, first.seed_key) == ("trakt", "show", "Title b", "tmdb:603")
        assert store.suggestions.refreshed_at() == 1_800_000_000

    def test_a_refresh_replaces_the_whole_deck(self, store: ConcreteAcquireStore) -> None:
        """The previous deck goes; the new rows carry later keys than every old one."""
        store.suggestions.replace_deck([_row("old1"), _row("old2")])
        old_last = store.suggestions.after(None, 10)[-1].id
        assert old_last is not None

        store.suggestions.replace_deck([_row("new", refreshed_at=1_800_000_500)])

        rows = store.suggestions.after(None, 10)
        assert [r.provider_id for r in rows] == ["new"]
        assert rows[0].id is not None and rows[0].id > old_last
        assert store.suggestions.refreshed_at() == 1_800_000_500

    def test_an_empty_deck_clears_it(self, store: ConcreteAcquireStore) -> None:
        """A refresh that found nothing leaves no suggestion."""
        store.suggestions.replace_deck([_row("a")])
        store.suggestions.replace_deck([])
        assert store.suggestions.after(None, 10) == []
        assert store.suggestions.refreshed_at() is None

    def test_the_seeds_asked_are_remembered_across_decks(self, store: ConcreteAcquireStore) -> None:
        """A refresh notes the time of the seeds it asked; the next deck's replacement keeps the others' times."""
        assert store.suggestions.seeds_asked_at() == {}

        store.suggestions.replace_deck([_row("a")], asked_seeds={"tmdb:1": 100, "tmdb:2": 100})
        store.suggestions.replace_deck([_row("b")], asked_seeds={"tmdb:2": 200, "tmdb:3": 200})
        store.suggestions.replace_deck([_row("c")])

        assert store.suggestions.seeds_asked_at() == {"tmdb:1": 100, "tmdb:2": 200, "tmdb:3": 200}

    def test_a_refused_replacement_leaves_the_seed_times(self, store: ConcreteAcquireStore) -> None:
        """The seeds are written in the deck's transaction: a rollback keeps both."""
        store.suggestions.replace_deck([_row("keep")], asked_seeds={"tmdb:1": 100})

        with pytest.raises(sqlite3.IntegrityError):
            store.suggestions.replace_deck([_row("dup"), _row("dup")], asked_seeds={"tmdb:1": 999, "tmdb:2": 999})

        assert store.suggestions.seeds_asked_at() == {"tmdb:1": 100}

    def test_after_pages_by_the_last_key_read(self, store: ConcreteAcquireStore) -> None:
        """``after`` returns the rows past a key, ``limit`` at most, in order, without overlap."""
        store.suggestions.replace_deck([_row(str(i)) for i in range(5)])

        first = store.suggestions.after(None, 2)
        second = store.suggestions.after(first[-1].id, 2)
        third = store.suggestions.after(second[-1].id, 2)
        fourth = store.suggestions.after(third[-1].id, 2)

        assert [r.provider_id for r in first + second + third] == ["0", "1", "2", "3", "4"]
        assert [len(first), len(second), len(third), len(fourth)] == [2, 2, 1, 0]

    def test_a_duplicate_title_leaves_the_previous_deck(self, store: ConcreteAcquireStore) -> None:
        """A title is in a deck once (provider, id, kind): a duplicate rolls the replacement back."""
        store.suggestions.replace_deck([_row("keep")])

        with pytest.raises(sqlite3.IntegrityError):
            store.suggestions.replace_deck([_row("dup"), _row("dup")])

        assert [r.provider_id for r in store.suggestions.after(None, 10)] == ["keep"]

    def test_the_same_id_of_a_film_and_a_show_are_two_titles(self, store: ConcreteAcquireStore) -> None:
        """TMDB numbers films and shows apart: the kind is part of the identity."""
        store.suggestions.replace_deck([_row("1", provider="tmdb", kind="movie"), _row("1", provider="tmdb")])
        assert len(store.suggestions.after(None, 10)) == 2
