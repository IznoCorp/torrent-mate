"""Tests for the « À traiter » read model (spec §3.1)."""

import sqlite3
from pathlib import Path

from personalscraper.web.acquisition.to_handle import build_to_handle


def _make_indexer(tmp_path: Path, rows: list[tuple]) -> Path:
    db = tmp_path / "library.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE scrape_decision (id INTEGER PRIMARY KEY, staging_path TEXT, "
        "media_kind TEXT, extracted_title TEXT, extracted_year INTEGER, trigger TEXT, "
        "candidates_json TEXT, status TEXT, created_at REAL)"
    )
    conn.executemany(
        "INSERT INTO scrape_decision (id, staging_path, media_kind, extracted_title, "
        "extracted_year, trigger, candidates_json, status, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db


def test_a_decision_backed_by_an_acquisition_is_an_item(tmp_path, acquire_store):
    """Une décision dont le chemin est porté par la spine EST une acquisition."""
    db = _make_indexer(
        tmp_path,
        [
            (1, "/staging/Top Chef S16E12", "tvshow", "Top Chef", 2010, "ambiguous", "[{},{},{}]", "pending", 1000.0),
        ],
    )
    acquire_store.provenance.upsert_grab(
        info_hash="abc",
        followed_id=42,
        kind="episode",
        media_ref=None,
        grabbed_at=800,
    )
    acquire_store.provenance.set_ingest(info_hash="abc", ingest_path="/staging/Top Chef S16E12", ingested_at=900)

    roll = build_to_handle(indexer_db=db, store=acquire_store)

    assert roll.orphan_count == 0
    assert len(roll.items) == 1
    item = roll.items[0]
    assert item.decision_id == 1
    assert item.followed_id == 42
    assert item.info_hash == "abc"
    assert item.title == "Top Chef"
    assert item.candidates_count == 3
    # §14.3 — l'étape est celle réellement atteinte, jamais une valeur par défaut.
    assert item.stage == "ingere"


def test_a_manual_drop_is_counted_but_never_listed(tmp_path, acquire_store):
    """Un dépôt manuel n'est pas une acquisition : compté, jamais affiché ici."""
    db = _make_indexer(
        tmp_path,
        [
            (7, "/staging/Un Film Posé À La Main", "movie", "Un Film", None, "unmatched", "[]", "pending", 1000.0),
        ],
    )

    roll = build_to_handle(indexer_db=db, store=acquire_store)

    assert roll.items == ()
    assert roll.orphan_count == 1


def test_a_resolved_decision_is_neither(tmp_path, acquire_store):
    """Une décision résolue n'est ni une acquisition ni un orphelin."""
    db = _make_indexer(
        tmp_path,
        [
            (9, "/staging/Déjà Résolu", "movie", "Déjà", None, "ambiguous", "[]", "resolved", 1000.0),
        ],
    )
    roll = build_to_handle(indexer_db=db, store=acquire_store)
    assert roll.items == ()
    assert roll.orphan_count == 0


def test_the_reason_is_french_never_a_raw_trigger(tmp_path, acquire_store):
    """NE-DOIT-PAS-4 : le verdict machine est mappé, jamais imprimé brut."""
    db = _make_indexer(
        tmp_path,
        [
            (1, "/s/a", "movie", "A", None, "ambiguous", "[{},{},{}]", "pending", 1.0),
            (2, "/s/b", "movie", "B", None, "unmatched", "[]", "pending", 2.0),
        ],
    )
    acquire_store.provenance.upsert_grab(
        info_hash="h1",
        followed_id=1,
        kind="movie",
        media_ref=None,
        grabbed_at=1,
    )
    acquire_store.provenance.set_ingest(info_hash="h1", ingest_path="/s/a", ingested_at=1)
    acquire_store.provenance.upsert_grab(
        info_hash="h2",
        followed_id=2,
        kind="movie",
        media_ref=None,
        grabbed_at=2,
    )
    acquire_store.provenance.set_ingest(info_hash="h2", ingest_path="/s/b", ingested_at=2)

    roll = build_to_handle(indexer_db=db, store=acquire_store)
    reasons = {i.decision_id: i.reason for i in roll.items}

    assert reasons[1] == "titre ambigu — 3 candidats proposés"
    assert reasons[2] == "aucun candidat — recherche manuelle prête"
    for reason in reasons.values():
        assert "ambiguous" not in reason and "unmatched" not in reason


def test_no_indexer_db_is_an_empty_rollup_not_a_crash(acquire_store):
    """Fail-soft : une base absente ne fait pas tomber la vue (§méthode)."""
    roll = build_to_handle(indexer_db=None, store=acquire_store)
    assert roll.items == ()
    assert roll.orphan_count == 0
