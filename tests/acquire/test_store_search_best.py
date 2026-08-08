"""record_search_outcome(best=) — the persisted last-search summary (addition A)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a fresh AcquireStore on a temp acquire.db and close it afterwards."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


def _add_wanted(store: ConcreteAcquireStore) -> int:
    """Insert one movie wanted row and return its id."""
    return store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tmdb_id=550),
            kind="movie",  # type: ignore[arg-type]
            status="pending",  # type: ignore[arg-type]
            enqueued_at=1,
        )
    )


def _best_json(store: ConcreteAcquireStore, wanted_id: int) -> str | None:
    """Read the raw persisted column."""
    cur = store.wanted._conn.execute(  # noqa: SLF001 — column truth, not API echo
        "SELECT last_search_best_json FROM wanted WHERE id = ?", (wanted_id,)
    )
    return cur.fetchone()[0]


def test_best_summary_round_trips(store: ConcreteAcquireStore) -> None:
    """The chosen-candidate snapshot lands in the column as JSON."""
    wid = _add_wanted(store)

    store.wanted.record_search_outcome(
        wid,
        "available",
        42,
        best={"title": "X.1080p.WEB-DL", "resolution": "1080p", "source": "WEB-DL", "seeders": 42},
    )

    raw = _best_json(store, wid)
    assert raw is not None
    assert json.loads(raw)["resolution"] == "1080p"


def test_a_choseless_pass_clears_the_summary(store: ConcreteAcquireStore) -> None:
    """The column describes the LAST pass — never a stale earlier one."""
    wid = _add_wanted(store)
    store.wanted.record_search_outcome(wid, "available", 42, best={"resolution": "1080p"})

    store.wanted.record_search_outcome(wid, "no_candidates", 0)

    assert _best_json(store, wid) is None
