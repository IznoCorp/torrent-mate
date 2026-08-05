"""Tests du contrôle de complétude de la spine (« tout doit être daté, et différenciable »).

Ce garde-fou existe parce que le même bug a été remonté TROIS fois et déclaré corrigé
trois fois : chaque vérification portait sur les champs qui venaient d'être touchés,
jamais sur les quatre étapes ensemble. Il ne compte donc QUE ce qui est réparable — une
étape sans aucune source reste un constat, pas une anomalie — et c'est cette distinction
que les tests éprouvent, dans les deux sens.
"""

from __future__ import annotations

import importlib.util as _util
import json
import sqlite3
import sys
import time
from pathlib import Path

from personalscraper.core.sqlite import apply_migrations as apply_acquire_migrations
from personalscraper.indexer.db import apply_migrations as apply_indexer_migrations

_REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = _util.spec_from_file_location("check_spine_complete", _REPO_ROOT / "scripts" / "check-spine-complete.py")
assert _spec is not None and _spec.loader is not None
_mod = _util.module_from_spec(_spec)
sys.modules["check_spine_complete"] = _mod
_spec.loader.exec_module(_mod)
collect_gaps = _mod.collect_gaps

NOW = int(time.time())
_REF = json.dumps({"tvdb_id": 555, "tmdb_id": None, "imdb_id": None})


def _dbs(tmp_path: Path) -> tuple[sqlite3.Connection, sqlite3.Connection]:
    """Deux bases temporaires avec les VRAIES chaînes de migration."""
    acquire = sqlite3.connect(str(tmp_path / "acquire.db"))
    apply_acquire_migrations(acquire, _REPO_ROOT / "personalscraper" / "acquire" / "migrations")
    indexer = sqlite3.connect(str(tmp_path / "library.db"))
    apply_indexer_migrations(indexer, _REPO_ROOT / "personalscraper" / "indexer" / "migrations")
    indexer.commit()
    acquire.execute(
        "INSERT INTO followed_series (id, media_ref_json, title, active, kind, added_at) "
        "VALUES (1, ?, 'Silo', 1, 'show', ?)",
        (_REF, NOW),
    )
    acquire.commit()
    return acquire, indexer


def _wanted(conn: sqlite3.Connection, wid: int, *, hash_: str, season: int | None, last_search: int | None) -> None:
    """Une ligne wanted grabée."""
    conn.execute(
        "INSERT INTO wanted (id, followed_id, media_ref_json, kind, season, episode, status, enqueued_at, "
        "grabbed_hash, last_search_at) VALUES (?,1,?,?,?,5,'done',?,?,?)",
        (wid, _REF, "episode" if season is not None else "movie", season, NOW, hash_, last_search),
    )
    conn.commit()


def _spine(conn: sqlite3.Connection, hash_: str, **cols: object) -> None:
    """Une ligne de spine, avec seulement les colonnes fournies."""
    keys = ["info_hash", *cols]
    values = [hash_, *cols.values()]
    placeholders = ",".join("?" * len(keys))
    conn.execute(f"INSERT INTO staging_provenance ({','.join(keys)}) VALUES ({placeholders})", values)  # noqa: S608
    conn.commit()


def _fields(gaps: list[object]) -> list[str]:
    """Les champs signalés."""
    return sorted(g.field for g in gaps)  # type: ignore[attr-defined]


def test_a_missing_grab_instant_with_a_search_behind_it_is_reported(tmp_path: Path) -> None:
    """« Récupéré · inconnue » alors que la recherche qui a grabbé est datée : réparable."""
    acquire, indexer = _dbs(tmp_path)
    _wanted(acquire, 1, hash_="aabb11", season=3, last_search=1_785_800_000)
    _spine(acquire, "aabb11", season=3, episode=5, status="dispatched", dispatched_at=NOW)

    assert "grabbed_at" in _fields(collect_gaps(acquire, indexer, {}))


def test_a_missing_grab_instant_with_no_source_at_all_is_not_an_anomaly(tmp_path: Path) -> None:
    """Sans aucune source, « inconnue » est un constat prouvé — le contrôle se tait.

    C'est ce qui empêche le garde-fou de réclamer l'impossible et donc d'être ignoré.
    """
    acquire, indexer = _dbs(tmp_path)
    _wanted(acquire, 1, hash_="aabb11", season=3, last_search=None)
    _spine(acquire, "aabb11", season=3, episode=5, status="dispatched", dispatched_at=NOW)

    assert "grabbed_at" not in _fields(collect_gaps(acquire, indexer, {}))


def test_a_journey_that_cannot_be_told_apart_is_reported(tmp_path: Path) -> None:
    """Une série sans saison/épisode alors que sa ligne wanted les porte : indiscernable."""
    acquire, indexer = _dbs(tmp_path)
    _wanted(acquire, 1, hash_="aabb11", season=3, last_search=1_785_800_000)
    _spine(acquire, "aabb11", grabbed_at=1, status="dispatched", dispatched_at=NOW)

    assert "identity" in _fields(collect_gaps(acquire, indexer, {}))


def test_a_movie_is_never_asked_for_an_episode(tmp_path: Path) -> None:
    """Le contre-cas : un film n'a pas d'épisode et n'en manque donc aucun."""
    acquire, indexer = _dbs(tmp_path)
    _wanted(acquire, 1, hash_="m0v1e0", season=None, last_search=1_785_800_000)
    _spine(acquire, "m0v1e0", grabbed_at=1, status="dispatched", dispatched_at=NOW)

    assert "identity" not in _fields(collect_gaps(acquire, indexer, {}))


def test_a_missing_ingest_instant_present_in_the_tracker_is_reported(tmp_path: Path) -> None:
    """Le tracker date l'ingestion exactement : la laisser vide est réparable."""
    acquire, indexer = _dbs(tmp_path)
    _wanted(acquire, 1, hash_="aabb11", season=3, last_search=1)
    _spine(acquire, "aabb11", grabbed_at=1, season=3, episode=5, status="dispatched", dispatched_at=NOW)
    tracker = {"AABB11": {"name": "Silo.S03E05-GRP", "date": "2026-08-05T03:42:47.238007"}}

    assert "ingested_at" in _fields(collect_gaps(acquire, indexer, tracker))


def test_a_complete_and_distinguishable_journey_reports_nothing(tmp_path: Path) -> None:
    """L'état visé : rien à dire. Une règle qui ne se tait jamais ne prouve rien."""
    acquire, indexer = _dbs(tmp_path)
    _wanted(acquire, 1, hash_="aabb11", season=3, last_search=1_785_800_000)
    _spine(
        acquire,
        "aabb11",
        grabbed_at=1_785_800_000,
        ingested_at=1_785_800_100,
        scraped_at=1_785_800_200,
        dispatched_at=1_785_800_300,
        season=3,
        episode=5,
        status="dispatched",
    )

    assert collect_gaps(acquire, indexer, {}) == []
