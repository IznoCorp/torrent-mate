"""Tests for ``GET /api/staging/media`` + the poster route (webui-overhaul OBJ2A).

Builds a temp staging tree (movies + TV show + ingest dir), points a copy of
the config at it plus a migrated temp ``library.db``, and asserts the
read-model: NFO enrichment, matching join from the ``scrape_decision`` queue,
the per-media pipeline timeline, filters / sort / pagination / counts, the
local poster route, the opt-in dispatch preview, live-run active-stage
highlighting, and fail-soft on a missing staging tree.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from personalscraper.conf.models.staging import StagingDirConfig
from personalscraper.config import Settings
from personalscraper.indexer import migrations as _migrations_pkg
from personalscraper.indexer.db import apply_migrations
from personalscraper.web.auth.passwords import hash_password
from tests.web._web_harness import guarded_client

TEST_USERNAME = "staging-test"
TEST_PASSWORD = "staging-test-password"
TEST_HASH = hash_password(TEST_PASSWORD)
TEST_SECRET = "staging-media-test-secret"

_T0 = 1750000000.0

_MOVIE_NFO = """<?xml version="1.0" encoding="UTF-8"?>
<movie>
    <title>Fight Club</title>
    <year>1999</year>
    <plot>An insomniac forms an underground fight club.</plot>
    <uniqueid type="tmdb" default="true">550</uniqueid>
    <uniqueid type="imdb" />
    <category source="personalscraper">movies</category>
</movie>
"""

_TVSHOW_NFO = """<?xml version="1.0" encoding="UTF-8"?>
<tvshow>
    <title>Breaking Bad</title>
    <year>2008</year>
    <plot>A chemistry teacher turns to making meth.</plot>
    <uniqueid type="tvdb" default="true">81189</uniqueid>
    <uniqueid type="tmdb">1396</uniqueid>
    <category source="personalscraper">tv_shows</category>
</tvshow>
"""


def _staging_dirs() -> list[StagingDirConfig]:
    """Return the movie/tvshow/ingest staging layout used by every test."""
    return [
        StagingDirConfig(id=1, name="movies", file_type="movie"),
        StagingDirConfig(id=2, name="tvshows", file_type="tvshow"),
        StagingDirConfig(id=97, name="temp", role="ingest"),
        StagingDirConfig(id=98, name="autres", file_type="other"),
    ]


def _make_client(test_config, *, staging_dir: Path, db_path: Path, data_dir: Path) -> TestClient:
    """Build an authenticated ``TestClient`` with staging routes wired to temp paths."""
    cfg = test_config.model_copy(
        update={
            "paths": test_config.paths.model_copy(update={"staging_dir": staging_dir, "data_dir": data_dir}),
            "indexer": test_config.indexer.model_copy(update={"db_path": db_path}),
            "staging_dirs": _staging_dirs(),
        },
    )
    web_cfg = cfg.web.model_copy(update={"username": TEST_USERNAME})
    cfg = cfg.model_copy(update={"web": web_cfg})

    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        web_password_hash=TEST_HASH,
        web_jwt_secret=TEST_SECRET,
    )

    from personalscraper.web.routes.staging import router as staging_router

    return guarded_client(
        config=cfg,
        settings=settings,
        routers=staging_router,
        login=(TEST_USERNAME, TEST_PASSWORD),
    )


def _fresh_db(tmp_path: Path) -> Path:
    """Create an empty migrated ``library.db`` (schema only, no rows)."""
    db_path = tmp_path / "staging.db"
    conn = sqlite3.connect(str(db_path))
    apply_migrations(conn, Path(_migrations_pkg.__file__).parent)
    conn.commit()
    conn.close()
    return db_path


def _write_video(path: Path, size: int = 16) -> None:
    """Write a small placeholder video file of *size* bytes."""
    path.write_bytes(b"\x00" * size)


def _seed_tree(staging_dir: Path, *, with_unmatched: bool = True) -> dict[str, Path]:
    """Create the standard staging tree; return the key media folders by name."""
    movies = staging_dir / "001-MOVIES"
    tvshows = staging_dir / "002-TVSHOWS"
    (staging_dir / "097-TEMP").mkdir(parents=True)

    # A fully-scraped movie: canonical NFO + poster + renamed video + trailer.
    # Names match what the scraper actually produces (real ``Obsession.nfo`` /
    # ``Obsession-poster.jpg`` / ``Obsession.mkv``) so the REAL verify gate passes
    # it — the read-model's ``verify`` state reflects that same gate (§méthode r6).
    fight = movies / "Fight Club (1999)"
    fight.mkdir(parents=True)
    (fight / "Fight Club.nfo").write_text(_MOVIE_NFO, encoding="utf-8")
    (fight / "Fight Club-poster.jpg").write_bytes(b"\xff\xd8\xff\x00poster")
    _write_video(fight / "Fight Club.mkv", size=2048)
    _write_video(fight / "Fight Club (1999)-trailer.mp4", size=32)

    folders = {"fight": fight}

    # An unscraped movie: video only (no nfo/poster/trailer).
    if with_unmatched:
        unmatched = movies / "Unknown Film (2020)"
        unmatched.mkdir(parents=True)
        _write_video(unmatched / "Unknown Film (2020).mkv", size=1024)
        folders["unmatched"] = unmatched

    # A fully-scraped TV show: nfo + poster + one season with a CANONICALLY
    # renamed episode (``SxxExx - Title.ext`` inside ``Saison NN/``) so the real
    # verify gate passes it.
    bb = tvshows / "Breaking Bad (2008)"
    (bb / "Saison 01").mkdir(parents=True)
    (bb / "tvshow.nfo").write_text(_TVSHOW_NFO, encoding="utf-8")
    (bb / "poster.jpg").write_bytes(b"\xff\xd8\xff\x00poster")
    _write_video(bb / "Saison 01" / "S01E01 - Pilot.mkv", size=4096)
    folders["bb"] = bb

    return folders


def _insert_decision(db_path: Path, *, staging_path: str, trigger: str = "ambiguous") -> None:
    """Insert one pending ``scrape_decision`` row for *staging_path*."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO scrape_decision "
        '(staging_path, media_kind, extracted_title, extracted_year, "trigger", '
        "candidates_json, status, created_at, updated_at) "
        "VALUES (?, 'movie', 'Unknown Film', 2020, ?, '[]', 'pending', ?, ?)",
        (staging_path, trigger, _T0, _T0),
    )
    conn.commit()
    conn.close()


def _insert_running_run(db_path: Path, *, step: str) -> None:
    """Insert a live (ended_at NULL) pipeline_run whose current step is *step*."""
    steps = [
        {"name": "ingest", "status": "done", "success_count": 3},
        {"name": step, "status": "running", "success_count": 1},
    ]
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO pipeline_run "
        "(run_uid, trigger, dry_run, started_at, ended_at, outcome, "
        "steps_json, error, pid, kind, command, options_json, output_tail) "
        "VALUES ('run-live', 'web', 0, ?, NULL, 'running', ?, NULL, ?, 'pipeline', NULL, NULL, NULL)",
        (_T0 + 100.0, json.dumps(steps), os.getpid()),
    )
    conn.commit()
    conn.close()


def _by_folder(payload: dict) -> dict[str, dict]:
    """Index the response items by their ``folder`` name."""
    return {i["folder"]: i for i in payload["items"]}


def _stage(item: dict, key: str) -> str:
    """Return the state of stage *key* in an item's timeline."""
    return next(s["state"] for s in item["stages"] if s["key"] == key)


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_empty_staging_yields_empty_list(test_config, tmp_path: Path) -> None:
    """A staging tree with only empty category dirs returns no items."""
    staging = tmp_path / "staging"
    for name in ("001-MOVIES", "002-TVSHOWS", "097-TEMP"):
        (staging / name).mkdir(parents=True)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=tmp_path / "data")
    (tmp_path / "data").mkdir(exist_ok=True)

    resp = client.get("/api/staging/media")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["items"] == []
    assert payload["total"] == 0
    assert payload["counts"]["total"] == 0


def test_missing_staging_dir_fails_soft(test_config, tmp_path: Path) -> None:
    """A staging root that does not exist yields an empty list, never a 500."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    client = _make_client(
        test_config,
        staging_dir=tmp_path / "does-not-exist",
        db_path=_fresh_db(tmp_path),
        data_dir=data_dir,
    )
    resp = client.get("/api/staging/media")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_missing_trailer_filter_excludes_items_with_a_trailer(test_config, tmp_path: Path) -> None:
    """A1: ``missing_trailer=true`` keeps only items lacking a trailer file.

    The seed tree has a movie WITH a trailer (Fight Club) and items WITHOUT one
    (Breaking Bad, Unknown Film). The filter must drop the former and keep the
    latter — the operator's "what still needs a trailer" view.
    """
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    payload = client.get("/api/staging/media", params={"missing_trailer": "true"}).json()
    folders = {item["relative_path"].split("/")[-1] for item in payload["items"]}

    assert "Fight Club (1999)" not in folders, "an item WITH a trailer must be filtered out"
    assert "Breaking Bad (2008)" in folders
    assert "Unknown Film (2020)" in folders
    # Every surviving item genuinely lacks a trailer.
    assert all(item["has_trailer"] is False for item in payload["items"])
    # The chip counts are still computed over the FULL set (Fight Club counts).
    assert payload["counts"]["with_trailer"] >= 1


def test_enriches_movie_and_tvshow(test_config, tmp_path: Path) -> None:
    """A scraped movie + TV show carry NFO metadata, ids, poster, seasons."""
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    payload = client.get("/api/staging/media").json()
    items = _by_folder(payload)

    fight = items["Fight Club (1999)"]
    assert fight["media_kind"] == "movie"
    assert fight["match"] == "matched"
    assert fight["title"] == "Fight Club"
    assert fight["year"] == 1999
    assert fight["provider_ids"] == {"tmdb": "550"}
    assert fight["has_nfo"] and fight["has_poster"] and fight["has_trailer"]
    assert fight["poster_url"] == f"/api/staging/media/{fight['id']}/poster"
    assert _stage(fight, "scraping") == "done"
    assert _stage(fight, "trailers") == "done"
    # Canonical (real verify passes) → verify done, no blocked reason (§méthode r6).
    assert _stage(fight, "verify") == "done"
    assert fight["blocked_reason"] is None
    assert _stage(fight, "dispatch") == "pending"
    # Verified → its single position is Dispatch (awaiting the next run).
    assert fight["position_stage"] == "dispatch"
    assert fight["position_state"] == "pending"

    bb = items["Breaking Bad (2008)"]
    assert bb["media_kind"] == "tvshow"
    assert bb["match"] == "matched"
    assert bb["provider_ids"] == {"tvdb": "81189", "tmdb": "1396"}
    assert bb["seasons"] == [{"season": 1, "label": "Saison 01", "episode_count": 1}]
    assert bb["episode_count"] == 1
    assert bb["has_trailer"] is False
    # Fully scraped: the trailers step has run even though it produced no trailer
    # file, so it is ``done`` (not ``pending``) — a missing trailer must not
    # strand the downstream ``verify`` behind it (timeline monotonicity).
    assert _stage(bb, "trailers") == "done"
    assert _stage(bb, "verify") == "done"
    assert bb["blocked_reason"] is None

    unmatched = items["Unknown Film (2020)"]
    assert unmatched["match"] == "absent"
    assert unmatched["has_nfo"] is False
    assert unmatched["year"] == 2020
    # Not identified → its single position is Identification, blocked with an
    # actionable reason (P0-A.1/A.5); downstream stages are pending.
    assert unmatched["position_stage"] == "matching"
    assert unmatched["position_state"] == "blocked"
    assert unmatched["blocked_reason"] is not None
    assert _stage(unmatched, "matching") == "blocked"
    assert _stage(unmatched, "scraping") == "pending"


def test_verify_blocked_on_unrenamed_episodes(test_config, tmp_path: Path) -> None:
    """A matched TV show whose episodes are NOT renamed reads ``verify: blocked`` + reason.

    Regression for product-intent.md §méthode rule 6: the read-model used to call
    such an item "Vérification : Fait" (it had an NFO + ids + a poster + a video),
    while the pipeline verify — the real dispatch gate — blocks it (unrenamed
    episodes). The UI must tell the truth: ``verify`` is ``blocked``, never ``done``,
    and carries a human French ``blocked_reason``. This is the exact Top Chef case.
    """
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    show = staging / "002-TVSHOWS" / "Top Chef (2026)"
    (show / "Saison 17").mkdir(parents=True)
    (show / "tvshow.nfo").write_text(_TVSHOW_NFO, encoding="utf-8")
    (show / "poster.jpg").write_bytes(b"\xff\xd8\xff\x00poster")
    # Raw release name, NOT the canonical ``SxxExx - Title.ext`` form.
    _write_video(show / "Saison 17" / "Top.Chef.S17E10.FRENCH.1080p.WEB-laRoulade.mkv", size=4096)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    item = _by_folder(client.get("/api/staging/media").json())["Top Chef (2026)"]
    # It IS matched (NFO + ids) — the exact "identified but not dispatchable" trap.
    assert item["match"] == "matched"
    assert _stage(item, "verify") != "done"
    assert _stage(item, "verify") == "blocked"
    assert item["blocked_reason"] is not None
    assert "épisode" in item["blocked_reason"].lower()
    _assert_monotonic(item)


def test_verify_blocked_on_unrenamed_movie_video(test_config, tmp_path: Path) -> None:
    """A matched movie whose video keeps its raw release name reads ``verify: blocked``.

    ``verify`` does not enforce movie video renaming, but the library convention (and
    ``check-media-complete``) does — the read-model reuses that same definition, so a
    ``Title (Year)/raw.release.name.mkv`` item is ``blocked`` at verify, not ``done``.
    """
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    movie = staging / "001-MOVIES" / "Fight Club (1999)"
    movie.mkdir(parents=True)
    (movie / "Fight Club.nfo").write_text(_MOVIE_NFO, encoding="utf-8")
    (movie / "Fight Club-poster.jpg").write_bytes(b"\xff\xd8\xff\x00poster")
    # Raw release name instead of the canonical ``Fight Club.mkv``.
    _write_video(movie / "Fight.Club.1999.1080p.BluRay.x264-AMIABLE.mkv", size=2048)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    item = _by_folder(client.get("/api/staging/media").json())["Fight Club (1999)"]
    assert item["match"] == "matched"
    assert _stage(item, "verify") == "blocked"
    assert item["blocked_reason"] is not None
    assert "vidéo" in item["blocked_reason"].lower()


def _assert_monotonic(item: dict) -> None:
    """Assert a timeline never shows ``done`` after an earlier non-``done`` stage."""
    seen_incomplete = False
    for step in item["stages"]:
        if step["state"] == "skipped":
            continue
        if step["state"] != "done":
            seen_incomplete = True
        elif seen_incomplete:
            raise AssertionError(
                f"stage {step['key']!r} is 'done' after an earlier incomplete stage: "
                f"{[(s['key'], s['state']) for s in item['stages']]}"
            )


def test_timeline_monotonic_with_stray_downstream_artifacts(test_config, tmp_path: Path) -> None:
    """A legacy folder with a poster + trailer but no NFO keeps ``trailers`` pending.

    Regression for the drift-unlink #3 symptom: stray downstream artefacts
    (a leftover poster/trailer from a partial scrape) must not light a later
    stage ``done`` while ``matching``/``scraping`` are still pending. The whole
    timeline is asserted monotonic.
    """
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    movies = staging / "001-MOVIES"
    (staging / "097-TEMP").mkdir(parents=True)
    # Legacy partial scrape: artwork + trailer on disk, but no NFO → unmatched.
    partial = movies / "Obsession (2026)"
    partial.mkdir(parents=True)
    (partial / "poster.jpg").write_bytes(b"\xff\xd8\xff\x00poster")
    _write_video(partial / "Obsession (2026).mkv", size=2048)
    _write_video(partial / "Obsession (2026)-trailer.mp4", size=32)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    item = _by_folder(client.get("/api/staging/media").json())["Obsession (2026)"]
    assert item["match"] == "absent"
    assert item["has_poster"] is True
    assert item["has_trailer"] is True
    # No NFO → the stray trailer/poster must NOT push a downstream stage to done:
    # the item's single position is Identification (blocked, actionable).
    assert item["position_stage"] == "matching"
    assert _stage(item, "matching") == "blocked"
    assert _stage(item, "scraping") == "pending"
    assert _stage(item, "trailers") == "pending"
    assert _stage(item, "verify") == "pending"
    _assert_monotonic(item)


def test_detects_mediaelch_named_artwork(test_config, tmp_path: Path) -> None:
    """A movie scraped with MediaElch naming ({name}-poster.jpg, {name}.nfo) is detected."""
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    movie = staging / "001-MOVIES" / "Heat (1995)"
    movie.mkdir(parents=True)
    # Non-canonical, movie-name-prefixed artwork + NFO (MediaElch fallback).
    (movie / "Heat.nfo").write_text(_MOVIE_NFO, encoding="utf-8")
    (movie / "Heat-poster.jpg").write_bytes(b"\xff\xd8\xff\x00poster")
    _write_video(movie / "Heat (1995).mkv", size=2048)

    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)
    items = _by_folder(client.get("/api/staging/media").json())
    heat = items["Heat (1995)"]
    assert heat["has_nfo"] is True
    assert heat["has_poster"] is True
    assert heat["poster_url"] is not None
    assert heat["match"] == "matched"
    assert heat["provider_ids"] == {"tmdb": "550"}


def test_counts_reflect_full_set(test_config, tmp_path: Path) -> None:
    """The counts block aggregates over the whole staging set."""
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    counts = client.get("/api/staging/media").json()["counts"]
    assert counts["total"] == 3
    assert counts["matched"] == 2
    assert counts["absent"] == 1
    assert counts["scraped"] == 2
    assert counts["with_trailer"] == 1


def test_pending_decision_blocks_matching(test_config, tmp_path: Path) -> None:
    """A pending decision marks the media ambiguous and blocks its matching stage."""
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    folders = _seed_tree(staging)
    db_path = _fresh_db(tmp_path)
    _insert_decision(db_path, staging_path=str(folders["unmatched"]))

    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)
    items = _by_folder(client.get("/api/staging/media").json())

    unmatched = items["Unknown Film (2020)"]
    assert unmatched["match"] == "ambiguous"
    assert unmatched["decision_id"] is not None
    assert unmatched["decision_trigger"] == "ambiguous"
    assert _stage(unmatched, "matching") == "blocked"
    # The blocked stage feeds the awaiting-action count.
    assert client.get("/api/staging/media").json()["counts"]["awaiting_action"] == 1


def test_filters_kind_match_stage(test_config, tmp_path: Path) -> None:
    """Kind / match / stage filters narrow the result set."""
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    tv = client.get("/api/staging/media", params={"kind": "tvshow"}).json()
    assert [i["folder"] for i in tv["items"]] == ["Breaking Bad (2008)"]

    matched = client.get("/api/staging/media", params={"match": "absent"}).json()
    assert [i["folder"] for i in matched["items"]] == ["Unknown Film (2020)"]

    # The stage filter matches the item's SINGLE position (P0-A.1): the
    # unidentified movie is at Identification — and nowhere else.
    at_matching = client.get("/api/staging/media", params={"stage": "matching"}).json()
    assert {i["folder"] for i in at_matching["items"]} == {"Unknown Film (2020)"}
    # The two verified items await Dispatch; the unidentified one is NOT there.
    at_dispatch = client.get("/api/staging/media", params={"stage": "dispatch"}).json()
    assert {i["folder"] for i in at_dispatch["items"]} == {"Fight Club (1999)", "Breaking Bad (2008)"}
    # No stock sits at scraping in this tree — the list is exact, not cumulative.
    at_scraping = client.get("/api/staging/media", params={"stage": "scraping"}).json()
    assert at_scraping["items"] == []


def test_each_item_has_exactly_one_position(test_config, tmp_path: Path) -> None:
    """P0-A.1 axiom: across all stage filters, each item appears exactly once.

    Regression for the operator's « Top Chef en Vérification ET en Dispatch »:
    with the old cumulative filter (state in pending/active/blocked), a
    verify-blocked item matched ?stage=verify AND ?stage=dispatch. The single
    position makes every item appear in exactly one stage list.
    """
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    # The Top Chef shape: matched show whose episodes keep raw release names →
    # blocked at verify by the real gate.
    top_chef = staging / "002-TVSHOWS" / "Top Chef (2026)"
    (top_chef / "Saison 17").mkdir(parents=True)
    (top_chef / "tvshow.nfo").write_text(_TVSHOW_NFO, encoding="utf-8")
    (top_chef / "poster.jpg").write_bytes(b"\xff\xd8\xff\x00poster")
    _write_video(top_chef / "Saison 17" / "Top.Chef.S17E10.FRENCH.1080p.WEB.mkv", size=4096)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    all_stages = ["arrival", "sorting", "cleaning", "matching", "scraping", "trailers", "verify", "dispatch"]
    seen: dict[str, list[str]] = {}
    for stage in all_stages:
        payload = client.get("/api/staging/media", params={"stage": stage}).json()
        for item in payload["items"]:
            seen.setdefault(item["folder"], []).append(stage)

    total = client.get("/api/staging/media").json()["counts"]["total"]
    assert len(seen) == total, f"every staged item must appear in exactly one stage list: {seen}"
    multi = {folder: stages for folder, stages in seen.items() if len(stages) != 1}
    assert not multi, f"items at more than one position: {multi}"

    # Top Chef sits at verify (blocked, with its reason) — and ONLY at verify.
    assert seen["Top Chef (2026)"] == ["verify"]
    at_verify = client.get("/api/staging/media", params={"stage": "verify"}).json()
    top = next(i for i in at_verify["items"] if i["folder"] == "Top Chef (2026)")
    assert top["position_state"] == "blocked"
    assert top["blocked_reason"] is not None


def test_sort_and_pagination(test_config, tmp_path: Path) -> None:
    """Title sort orders A→Z; pagination slices the sorted list."""
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    titles = [i["title"] for i in client.get("/api/staging/media", params={"sort": "title"}).json()["items"]]
    assert titles == sorted(titles, key=str.casefold)

    page1 = client.get("/api/staging/media", params={"sort": "title", "page": 1, "page_size": 2}).json()
    assert len(page1["items"]) == 2
    assert page1["total"] == 3
    page2 = client.get("/api/staging/media", params={"sort": "title", "page": 2, "page_size": 2}).json()
    assert len(page2["items"]) == 1


def test_active_stage_when_run_live(test_config, tmp_path: Path) -> None:
    """A live run whose step maps to an item's position marks it active."""
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    db_path = _fresh_db(tmp_path)
    # Hold the lock with this process's pid so the run reads as live.
    (data_dir / "pipeline.lock").write_text(str(os.getpid()))
    _insert_running_run(db_path, step="dispatch")

    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)
    items = _by_folder(client.get("/api/staging/media").json())

    # The verified movie awaits dispatch → its position goes active under the run.
    fight = items["Fight Club (1999)"]
    assert fight["position_stage"] == "dispatch"
    assert fight["position_state"] == "active"
    assert _stage(fight, "dispatch") == "active"
    # A blocked item is NOT lit active — it needs the operator, not the run.
    assert items["Unknown Film (2020)"]["position_state"] == "blocked"


def test_with_dispatch_populates_preview(test_config, tmp_path: Path) -> None:
    """with_dispatch=true attaches a dispatch preview to each page item."""
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    payload = client.get("/api/staging/media", params={"with_dispatch": "true"}).json()
    for item in payload["items"]:
        assert item["dispatch_target"] is not None
        assert item["dispatch_target"]["mode"] in {"replace", "merge", "new", "unknown"}

    # Without the flag the preview stays absent (off the hot path).
    plain = client.get("/api/staging/media").json()
    assert all(i["dispatch_target"] is None for i in plain["items"])


def test_poster_route_serves_and_404s(test_config, tmp_path: Path) -> None:
    """The poster route serves the local poster and 404s on unknown/absent."""
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    items = _by_folder(client.get("/api/staging/media").json())
    fight_id = items["Fight Club (1999)"]["id"]
    unmatched_id = items["Unknown Film (2020)"]["id"]

    ok = client.get(f"/api/staging/media/{fight_id}/poster")
    assert ok.status_code == 200
    assert ok.headers["content-type"].startswith("image/")

    # A media with no local poster → 404.
    assert client.get(f"/api/staging/media/{unmatched_id}/poster").status_code == 404
    # An unknown id → 404 (never a path-traversal escape).
    assert client.get("/api/staging/media/deadbeefdeadbeef/poster").status_code == 404


def test_enqueue_non_identified_creates_pending_decision(test_config, tmp_path: Path) -> None:
    """POST .../enqueue turns an absent movie into a pending 'manual' scrape decision."""
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    movies = staging / "001-MOVIES"
    (staging / "097-TEMP").mkdir(parents=True)
    unknown = movies / "Mystery Film (2021)"
    unknown.mkdir(parents=True)
    _write_video(unknown / "Mystery Film (2021).mkv", size=1024)
    db_path = _fresh_db(tmp_path)
    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)

    media_id = media_id_for("001-MOVIES/Mystery Film (2021)")
    resp = client.post(
        f"/api/staging/media/{media_id}/enqueue",
        headers={"X-Requested-With": "TorrentMate"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["media_kind"] == "movie"
    assert body["title"] == "Mystery Film"
    # C18: the response carries the created decision id so the client can open
    # the resolution deck positioned on it.
    assert isinstance(body["decision_id"], int)

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        'SELECT id, media_kind, status, "trigger" FROM scrape_decision WHERE staging_path LIKE ?',
        ("%Mystery Film (2021)",),
    ).fetchone()
    conn.close()
    assert row == (body["decision_id"], "movie", "pending", "manual")


def test_enqueue_requires_x_requested_with(test_config, tmp_path: Path) -> None:
    """The enqueue POST is CSRF-guarded — 400 without X-Requested-With."""
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    movies = staging / "001-MOVIES"
    (staging / "097-TEMP").mkdir(parents=True)
    (movies / "NoHeader (2021)").mkdir(parents=True)
    _write_video(movies / "NoHeader (2021)" / "NoHeader (2021).mkv", size=512)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)
    media_id = media_id_for("001-MOVIES/NoHeader (2021)")
    assert client.post(f"/api/staging/media/{media_id}/enqueue").status_code == 400


def test_enqueue_seeds_candidates_from_provider(test_config, tmp_path: Path) -> None:
    """§3 guard — enqueue seeds provider candidates so the deck opens WITH proposals.

    Regression (product-intent post-mortem): the enqueue path hard-coded
    ``candidates_json="[]"`` and returned no candidate info, so a manually-resolved item
    opened the resolution deck on an EMPTY grid. Enqueue must now run the same provider
    search helper as ``POST /decisions/{id}/search`` and persist the result. This test
    fails on the old implementation (no ``candidates_seeded`` field; ``candidates_json``
    stays ``"[]"``).
    """
    from unittest.mock import patch

    from personalscraper.scraper.decision_candidate import DecisionCandidate
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    movies = staging / "001-MOVIES"
    (staging / "097-TEMP").mkdir(parents=True)
    (movies / "Mystery Film (2021)").mkdir(parents=True)
    _write_video(movies / "Mystery Film (2021)" / "Mystery Film (2021).mkv", size=1024)
    db_path = _fresh_db(tmp_path)
    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)

    media_id = media_id_for("001-MOVIES/Mystery Film (2021)")
    dummy = [DecisionCandidate(provider="tmdb", provider_id=1234, title="Mystery Film", year=2021, score=0.88)]
    # Patch the shared search helper (bypasses the provider stack) — proves enqueue
    # reuses it and persists its result, deterministically.
    with patch("personalscraper.web.decisions.search.search_candidates", return_value=dummy):
        resp = client.post(
            f"/api/staging/media/{media_id}/enqueue",
            headers={"X-Requested-With": "TorrentMate"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidates_seeded"] is True
    assert body["candidates_count"] == 1

    # Candidates persisted on the decision row → the deck opens WITH proposals.
    conn = sqlite3.connect(str(db_path))
    (candidates_json,) = conn.execute(
        "SELECT candidates_json FROM scrape_decision WHERE id = ?",
        (body["decision_id"],),
    ).fetchone()
    conn.close()
    seeded = json.loads(candidates_json)
    assert len(seeded) == 1
    assert seeded[0]["title"] == "Mystery Film"


def test_enqueue_fail_soft_when_provider_unavailable(test_config, tmp_path: Path) -> None:
    """§3 fail-soft — a provider outage still enqueues, but ``candidates_seeded=False``.

    The decision is created (never lost) with an empty candidate list so the UI can show
    an explicit "no automatic proposal" state instead of a success it cannot back.
    """
    from unittest.mock import patch

    from personalscraper.web.decisions.search import ProviderSearchError
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    movies = staging / "001-MOVIES"
    (staging / "097-TEMP").mkdir(parents=True)
    (movies / "Offline Film (2019)").mkdir(parents=True)
    _write_video(movies / "Offline Film (2019)" / "Offline Film (2019).mkv", size=1024)
    db_path = _fresh_db(tmp_path)
    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)

    media_id = media_id_for("001-MOVIES/Offline Film (2019)")
    with patch(
        "personalscraper.web.decisions.search.search_candidates",
        side_effect=ProviderSearchError("TMDB down"),
    ):
        resp = client.post(
            f"/api/staging/media/{media_id}/enqueue",
            headers={"X-Requested-With": "TorrentMate"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["candidates_seeded"] is False
    assert body["candidates_count"] == 0

    conn = sqlite3.connect(str(db_path))
    (candidates_json,) = conn.execute(
        "SELECT candidates_json FROM scrape_decision WHERE id = ?",
        (body["decision_id"],),
    ).fetchone()
    conn.close()
    assert json.loads(candidates_json) == []


def test_enqueue_other_without_kind_returns_400(test_config, tmp_path: Path) -> None:
    """T1.2 — an unsorted (AUTRES) item cannot be enqueued without the operator's type.

    The sort mis-typed it into 098-AUTRES; only the operator can say what it really is.
    Without a media_kind the request is a 400 and the folder is left untouched.
    """
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    item = staging / "098-AUTRES" / "Mystery.Blob.2020-GRP"
    item.mkdir(parents=True)
    _write_video(item / "blob.mkv", size=512)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    media_id = media_id_for("098-AUTRES/Mystery.Blob.2020-GRP")
    resp = client.post(
        f"/api/staging/media/{media_id}/enqueue",
        headers={"X-Requested-With": "TorrentMate"},
    )
    assert resp.status_code == 400
    assert "AUTRES" in resp.json()["detail"]
    assert item.exists()  # left untouched


def test_enqueue_other_with_kind_reclasses_to_movies_and_seeds(test_config, tmp_path: Path) -> None:
    """T1.2 — an AUTRES item + operator type is physically reclassed to MOVIES and seeded.

    Guards the §3 safety net end to end: the folder leaves 098-AUTRES for 001-MOVIES
    under a clean 'Title (Year)' name (so it later dispatches correctly), the decision
    points at the new location, and candidates are seeded. Red on the old impl, which
    had no resolve path for 'other' items at all.
    """
    from unittest.mock import patch

    from personalscraper.scraper.decision_candidate import DecisionCandidate
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    (staging / "001-MOVIES").mkdir(parents=True)
    item = staging / "098-AUTRES" / "Some.Unsorted.Movie.2021.1080p-GRP"
    item.mkdir(parents=True)
    _write_video(item / "movie.mkv", size=1024)
    db_path = _fresh_db(tmp_path)
    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)

    media_id = media_id_for("098-AUTRES/Some.Unsorted.Movie.2021.1080p-GRP")
    dummy = [DecisionCandidate(provider="tmdb", provider_id=42, title="Some Unsorted Movie", year=2021, score=0.9)]
    with patch("personalscraper.web.decisions.search.search_candidates", return_value=dummy):
        resp = client.post(
            f"/api/staging/media/{media_id}/enqueue",
            json={"media_kind": "movie"},
            headers={"X-Requested-With": "TorrentMate"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["media_kind"] == "movie"
    assert body["candidates_seeded"] is True

    # Physically reclassed: gone from AUTRES, now under MOVIES with a clean name.
    assert not item.exists()
    moved = list((staging / "001-MOVIES").iterdir())
    assert len(moved) == 1
    assert "Some Unsorted Movie" in moved[0].name

    # The decision points at the new location under MOVIES.
    conn = sqlite3.connect(str(db_path))
    (staging_path_val,) = conn.execute(
        "SELECT staging_path FROM scrape_decision WHERE id = ?",
        (body["decision_id"],),
    ).fetchone()
    conn.close()
    assert "001-MOVIES" in staging_path_val


def test_enqueue_other_seeds_search_with_cleaned_title(test_config, tmp_path: Path) -> None:
    """The AUTRES enqueue seeds the provider search with the CLEANED title, not the raw name.

    Red on the previous impl: the search (and the decision's ``extracted_title``)
    used the raw pre-reclass release name (``The.Wild.Robot.2024…-FW``), which never
    matches any provider title — so every AUTRES resolve opened on an empty deck
    (proven live on the Wild Robot fixture). The reclass already computes the clean
    ``Title (Year)``; the seeded search and the decision must reuse it (§3: the deck
    opens WITH proposals).
    """
    from unittest.mock import patch

    from personalscraper.scraper.decision_candidate import DecisionCandidate
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    (staging / "001-MOVIES").mkdir(parents=True)
    raw = "The.Wild.Robot.2024.MULTi.1080p.WEB.x264-FW"
    item = staging / "098-AUTRES" / raw
    item.mkdir(parents=True)
    _write_video(item / f"{raw}.mkv", size=1024)
    db_path = _fresh_db(tmp_path)
    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)

    dummy = [DecisionCandidate(provider="tmdb", provider_id=42, title="The Wild Robot", year=2024, score=0.9)]
    with patch("personalscraper.web.decisions.search.search_candidates", return_value=dummy) as search_mock:
        resp = client.post(
            f"/api/staging/media/{media_id_for(f'098-AUTRES/{raw}')}/enqueue",
            json={"media_kind": "movie"},
            headers={"X-Requested-With": "TorrentMate"},
        )

    assert resp.status_code == 200, resp.text
    # The search ran on the cleaned title + year, never the raw release name.
    call = search_mock.call_args
    searched_title, searched_year = call.args[2], call.args[3]
    assert searched_title == "The Wild Robot", f"search seeded with {searched_title!r}"
    assert searched_year == 2024

    # The decision row carries the cleaned title too (drives the deck's header +
    # prefilled manual search).
    conn = sqlite3.connect(str(db_path))
    title_val, year_val = conn.execute(
        "SELECT extracted_title, extracted_year FROM scrape_decision WHERE id = ?",
        (resp.json()["decision_id"],),
    ).fetchone()
    conn.close()
    assert title_val == "The Wild Robot"
    assert year_val == 2024


def test_enqueue_reopens_a_previously_resolved_item(test_config, tmp_path: Path) -> None:
    """Re-enqueuing a resolved-but-still-non-identified item re-opens it to pending.

    Root-cause regression (operator report). Before the fix the manual enqueue no-oped
    on a ``resolved`` row (upsert's WHERE
    guard protected the operator verdict), so the 'À résoudre' deck stayed EMPTY even
    though the toast promised '5 propositions'. The legacy items Obsession/Ferrari were
    exactly this: resolved once, still non-identified, un-re-resolvable.
    """
    from unittest.mock import patch

    from personalscraper.scraper.decision_candidate import DecisionCandidate
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    item = staging / "001-MOVIES" / "Legacy Film (2020)"
    item.mkdir(parents=True)
    _write_video(item / "Legacy Film (2020).mkv", size=1024)
    db_path = _fresh_db(tmp_path)

    # Seed an already-RESOLVED decision for this exact staging path (the legacy state).
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO scrape_decision (staging_path, media_kind, extracted_title, "
        'extracted_year, "trigger", candidates_json, status, resolution_json, '
        "created_at, updated_at, resolved_at) "
        "VALUES (?, 'movie', 'Legacy Film', 2020, 'ambiguous', '[]', 'resolved', "
        "?, ?, ?, ?)",
        (str(item), '{"provider":"tmdb","provider_id":1}', _T0, _T0, _T0),
    )
    conn.commit()
    conn.close()

    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)
    media_id = media_id_for("001-MOVIES/Legacy Film (2020)")
    dummy = [DecisionCandidate(provider="tmdb", provider_id=7, title="Legacy Film", year=2020, score=0.9)]
    with patch("personalscraper.web.decisions.search.search_candidates", return_value=dummy):
        resp = client.post(
            f"/api/staging/media/{media_id}/enqueue",
            headers={"X-Requested-With": "TorrentMate"},
        )
    assert resp.status_code == 200, resp.text

    # Re-opened to pending with the fresh candidate → back in the 'À résoudre' deck.
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT status, candidates_json, resolution_json FROM scrape_decision WHERE staging_path = ?",
        (str(item),),
    ).fetchone()
    conn.close()
    assert row["status"] == "pending"
    assert "7" in row["candidates_json"]
    assert row["resolution_json"] is None


# ── Continue endpoint tests ────────────────────────────────────────────────────


def test_continue_matched_spawns_run(test_config, tmp_path: Path) -> None:
    """A matched movie with provider-identified NFO spawns a pipeline run.

    POST /api/staging/media/{id}/continue → 202, ok=True, run_uid present
    (hex UUID), deferred=False. The subprocess.Popen call MUST carry
    ``--trigger-reason=scrape-resolve`` in its argv.
    """
    from unittest.mock import patch

    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    media_id = media_id_for("001-MOVIES/Fight Club (1999)")
    with patch("personalscraper.web.pipeline_trigger.subprocess.Popen") as mock_popen:
        resp = client.post(
            f"/api/staging/media/{media_id}/continue",
            headers={"X-Requested-With": "TorrentMate"},
        )

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["media_id"] == media_id
    assert body["deferred"] is False
    assert body["detail"] == "Reprise lancée — le média termine son pipeline (vérification → dispatch)."

    # run_uid is uuid4().hex (32 lowercase hex chars).
    run_uid = body["run_uid"]
    assert isinstance(run_uid, str)
    assert len(run_uid) == 32
    assert all(c in "0123456789abcdef" for c in run_uid)

    # Popen was called with --trigger-reason=scrape-resolve in the argv.
    mock_popen.assert_called_once()
    call_args = mock_popen.call_args[0][0]
    assert any("--trigger-reason=scrape-resolve" in arg for arg in call_args)


def test_continue_not_matched_returns_422(test_config, tmp_path: Path) -> None:
    """An item without a provider-identified NFO returns 422 with the FR detail.

    The route requires ``match == "matched"`` (NFO present WITH provider IDs).
    An absent item has no NFO at all → 422, not 404.
    """
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    media_id = media_id_for("001-MOVIES/Unknown Film (2020)")
    resp = client.post(
        f"/api/staging/media/{media_id}/continue",
        headers={"X-Requested-With": "TorrentMate"},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"] == "Ce média n'est pas encore identifié — résolvez le matching d'abord."


def test_continue_unknown_media_returns_404(test_config, tmp_path: Path) -> None:
    """A bogus media id returns 404 with the English detail."""
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "001-MOVIES").mkdir(parents=True)
    (staging / "097-TEMP").mkdir(parents=True)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    resp = client.post(
        "/api/staging/media/deadbeefdeadbeef/continue",
        headers={"X-Requested-With": "TorrentMate"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Media not found"


def test_continue_requires_x_requested_with(test_config, tmp_path: Path) -> None:
    """The continue POST is CSRF-guarded — 400 without X-Requested-With.

    Mirrors ``test_enqueue_requires_x_requested_with``: the dependency runs
    before the route handler, so a valid media_id is needed to reach the guard,
    but the item itself does not need to be matched.
    """
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    movies = staging / "001-MOVIES"
    (staging / "097-TEMP").mkdir(parents=True)
    (movies / "NoHeader (2021)").mkdir(parents=True)
    _write_video(movies / "NoHeader (2021)" / "NoHeader (2021).mkv", size=512)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)
    media_id = media_id_for("001-MOVIES/NoHeader (2021)")
    assert client.post(f"/api/staging/media/{media_id}/continue").status_code == 400


def test_continue_deferred_when_lock_held(test_config, tmp_path: Path) -> None:
    """When the pipeline lock is held, returns 202 with deferred=True, run_uid=None.

    Patches ``is_lock_held`` (imported by pipeline_trigger) to True so
    ``spawn_pipeline_run`` returns None without spawning.  The detail MUST
    contain "En file" and Popen MUST NOT be called.
    """
    from unittest.mock import patch

    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    media_id = media_id_for("001-MOVIES/Fight Club (1999)")
    with patch("personalscraper.web.pipeline_trigger.is_lock_held", return_value=True):
        with patch("personalscraper.web.pipeline_trigger.subprocess.Popen") as mock_popen:
            resp = client.post(
                f"/api/staging/media/{media_id}/continue",
                headers={"X-Requested-With": "TorrentMate"},
            )

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["media_id"] == media_id
    assert body["run_uid"] is None
    assert body["deferred"] is True
    assert "En file" in body["detail"]
    mock_popen.assert_not_called()


# ── Discard endpoint tests ─────────────────────────────────────────────────────


def test_discard_other_artifact_moves_to_quarantine_and_journals(test_config, tmp_path: Path) -> None:
    """A non-media 'other' artifact is moved to _quarantine/ with a journal entry.

    Seeds a folder in 098-AUTRES, discards it, and asserts the quarantine move,
    ``journaled=True``, and the correct FR success detail (§7).
    """
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    item = staging / "098-AUTRES" / "random.subs.pack-GRP"
    item.mkdir(parents=True)
    _write_video(item / "subs.srt", size=64)
    db_path = _fresh_db(tmp_path)
    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)

    media_id = media_id_for("098-AUTRES/random.subs.pack-GRP")
    resp = client.post(
        f"/api/staging/media/{media_id}/discard",
        headers={"X-Requested-With": "TorrentMate"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["media_id"] == media_id
    assert body["journaled"] is True
    assert body["quarantine_path"] is not None
    assert "_quarantine" in body["quarantine_path"]
    assert body["detail"] == ("Artefact mis en quarantaine — trace écrite au journal des suppressions.")

    # Folder was physically moved, not deleted in-place.
    assert not item.exists()
    quarantine_dir = Path(body["quarantine_path"])
    assert quarantine_dir.exists()
    assert quarantine_dir.is_dir()


def test_discard_journal_row_written(test_config, tmp_path: Path) -> None:
    """After a discard, ``destructive_op`` contains exactly one row for this delete.

    Direct SELECT on the journal table — the row is the audit trail (§7).
    """
    import sqlite3

    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    item = staging / "098-AUTRES" / "junk.folder-GRP"
    item.mkdir(parents=True)
    _write_video(item / "notes.txt", size=32)
    db_path = _fresh_db(tmp_path)
    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)

    media_id = media_id_for("098-AUTRES/junk.folder-GRP")
    resp = client.post(
        f"/api/staging/media/{media_id}/discard",
        headers={"X-Requested-With": "TorrentMate"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["journaled"] is True

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT op, path, actor, detail FROM destructive_op WHERE actor = 'web' AND op = 'delete'"
    ).fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0]["op"] == "delete"
    assert rows[0]["actor"] == "web"
    assert str(item) in rows[0]["path"]
    assert "Discard non-media artifact" in rows[0]["detail"]


def test_discard_movie_or_tvshow_returns_422(test_config, tmp_path: Path) -> None:
    """A scrapable (movie/tvshow) item returns 422 with the FR directive detail.

    The operator must use resolve or pipeline-restart, not discard, for
    identifiable media.
    """
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    media_id = media_id_for("001-MOVIES/Fight Club (1999)")
    resp = client.post(
        f"/api/staging/media/{media_id}/discard",
        headers={"X-Requested-With": "TorrentMate"},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"] == (
        "Cet élément est un média identifiable — utilisez "
        "'Rechercher / résoudre' ou 'Relancer le pipeline', pas 'Ignorer'."
    )


def test_discard_unknown_media_returns_404(test_config, tmp_path: Path) -> None:
    """A bogus media id returns 404 with the English detail."""
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "001-MOVIES").mkdir(parents=True)
    (staging / "097-TEMP").mkdir(parents=True)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    resp = client.post(
        "/api/staging/media/deadbeefdeadbeef/discard",
        headers={"X-Requested-With": "TorrentMate"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "No media matches this id"


def test_discard_requires_x_requested_with(test_config, tmp_path: Path) -> None:
    """The discard POST is CSRF-guarded — 400 without X-Requested-With.

    Mirrors ``test_continue_requires_x_requested_with``: the dependency runs
    before the route handler, so a valid media_id is needed to reach the guard,
    but the item itself can be anything — including an 'other' artifact.
    """
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    item = staging / "098-AUTRES" / "NoHeader.Item-GRP"
    item.mkdir(parents=True)
    _write_video(item / "file.bin", size=32)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)
    media_id = media_id_for("098-AUTRES/NoHeader.Item-GRP")
    assert client.post(f"/api/staging/media/{media_id}/discard").status_code == 400


def test_discard_journal_unwritable_returns_503(test_config, tmp_path: Path) -> None:
    """B4 — when the destructive-op journal is unreachable, the discard is REFUSED (503).

    The probe runs BEFORE the irreversible move so the operator knows immediately,
    not after the folder is already gone.  A db_path pointing into a non-existent
    directory triggers the fail-soft path (sqlite3.connect raises OperationalError
    → probe returns False → 503).
    """
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    item = staging / "098-AUTRES" / "journal.unwritable-GRP"
    item.mkdir(parents=True)
    _write_video(item / "data.bin", size=64)

    # Bootstrap with a valid db so the client / login works, then swap the
    # db_path on the app's config to a path whose parent directory does not
    # exist — ``sqlite3.connect()`` will raise OperationalError.
    db_path = _fresh_db(tmp_path)
    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)

    bogus_db = tmp_path / "nonexistent" / "library.db"
    app = client.app if hasattr(client, "app") else None
    if app is None:
        app = client._app  # type: ignore[attr-defined]
    app.state.config.indexer.db_path = bogus_db

    media_id = media_id_for("098-AUTRES/journal.unwritable-GRP")
    resp = client.post(
        f"/api/staging/media/{media_id}/discard",
        headers={"X-Requested-With": "TorrentMate"},
    )

    assert resp.status_code == 503, resp.text
    body = resp.json()
    assert body["detail"] == "Journal des suppressions indisponible — suppression refusée."
    # B4 — the folder is still there (refused before the move).
    assert item.exists()


def test_discard_journal_record_silent_failure_journaled_false(test_config, tmp_path: Path) -> None:
    """When ``record_destruction`` silently fails, the response has ``journaled=False`` + ATTENTION.

    §7 honesty regression: ``record_destruction`` is fail-soft — the quarantine
    move always succeeds, but a journal failure must be surfaced to the operator.
    Monkeypatches ``record_destruction`` to no-op (simulating a swallowed write
    failure) while keeping the journal table itself writable.
    """
    from unittest.mock import patch

    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    item = staging / "098-AUTRES" / "journal.silent.fail-GRP"
    item.mkdir(parents=True)
    _write_video(item / "data.bin", size=64)
    db_path = _fresh_db(tmp_path)
    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)

    media_id = media_id_for("098-AUTRES/journal.silent.fail-GRP")
    with patch("personalscraper.web.routes.staging.record_destruction") as mock_record:
        # record_destruction is a no-op (silent failure — the journal IS writable
        # but the write itself is dropped).
        resp = client.post(
            f"/api/staging/media/{media_id}/discard",
            headers={"X-Requested-With": "TorrentMate"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["media_id"] == media_id
    assert body["journaled"] is False
    assert body["detail"] == (
        "Artefact mis en quarantaine — ATTENTION : l'écriture au journal des suppressions a échoué."
    )
    mock_record.assert_called_once()
    # The quarantine move still happened — journal failure never breaks the destroy.
    assert not item.exists()
    assert Path(body["quarantine_path"]).exists()


# ── Sub-phase 7.1 new tests ────────────────────────────────────────────────────


def test_continue_and_discard_403_when_staging_role(test_config, tmp_path: Path, monkeypatch) -> None:
    """T#2 — staging role returns 403 on both continue AND discard, folder untouched.

    ``PERSONALSCRAPER_WEB_ROLE=staging`` makes every write endpoint refuse with
    403 ``"read-only"`` detail.  Both endpoints must refuse, and the folder must
    not be touched.
    """
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    # Also seed an "other" item for the discard test.
    (staging / "098-AUTRES").mkdir(parents=True, exist_ok=True)
    junk = staging / "098-AUTRES" / "staging-role-test-GRP"
    junk.mkdir(parents=True)
    _write_video(junk / "data.bin", size=32)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")

    # Continue → 403, folder untouched.
    fight_id = media_id_for("001-MOVIES/Fight Club (1999)")
    resp_continue = client.post(
        f"/api/staging/media/{fight_id}/continue",
        headers={"X-Requested-With": "TorrentMate"},
    )
    assert resp_continue.status_code == 403
    assert resp_continue.json()["detail"] == "read-only"
    assert (staging / "001-MOVIES" / "Fight Club (1999)").exists()

    # Discard → 403, folder untouched.
    junk_id = media_id_for("098-AUTRES/staging-role-test-GRP")
    resp_discard = client.post(
        f"/api/staging/media/{junk_id}/discard",
        headers={"X-Requested-With": "TorrentMate"},
    )
    assert resp_discard.status_code == 403
    assert resp_discard.json()["detail"] == "read-only"
    assert junk.exists()


def test_discard_quarantine_collision_suffixes(test_config, tmp_path: Path) -> None:
    """T#1 — a second item with the same name gets ``_1`` suffix (and ``_2`` on third).

    The collision handling suffixes the quarantine destination when a folder with
    the same media_id already sits in ``_quarantine/``.  Each suffix increments.
    """
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    (staging / "098-AUTRES").mkdir(parents=True)
    db_path = _fresh_db(tmp_path)
    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)

    media_id = media_id_for("098-AUTRES/collision.test-GRP")

    # First discard: lands directly at _quarantine/<media_id>
    item1 = staging / "098-AUTRES" / "collision.test-GRP"
    item1.mkdir(parents=True)
    _write_video(item1 / "a.bin", size=16)
    resp1 = client.post(
        f"/api/staging/media/{media_id}/discard",
        headers={"X-Requested-With": "TorrentMate"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["quarantine_path"].endswith(f"_quarantine/{media_id}")
    assert not item1.exists()

    # Second discard (same name): lands at _quarantine/<media_id>_1
    item2 = staging / "098-AUTRES" / "collision.test-GRP"
    item2.mkdir(parents=True)
    _write_video(item2 / "b.bin", size=16)
    resp2 = client.post(
        f"/api/staging/media/{media_id}/discard",
        headers={"X-Requested-With": "TorrentMate"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["quarantine_path"].endswith(f"_quarantine/{media_id}_1")
    assert not item2.exists()

    # Third discard: lands at _quarantine/<media_id>_2
    item3 = staging / "098-AUTRES" / "collision.test-GRP"
    item3.mkdir(parents=True)
    _write_video(item3 / "c.bin", size=16)
    resp3 = client.post(
        f"/api/staging/media/{media_id}/discard",
        headers={"X-Requested-With": "TorrentMate"},
    )
    assert resp3.status_code == 200
    assert resp3.json()["quarantine_path"].endswith(f"_quarantine/{media_id}_2")
    assert not item3.exists()


def test_continue_nfo_without_provider_ids_returns_422(test_config, tmp_path: Path) -> None:
    """T#5 — an NFO present but with no provider ids returns 422.

    An NFO that parsed ok but carries zero ``<uniqueid>`` elements is not a
    "matched" item — the operator must resolve it first.  This is the distinct
    "NFO present but empty" case, not the "no NFO at all" case.
    """
    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    movie = staging / "001-MOVIES" / "Empty NFO Film (2020)"
    movie.mkdir(parents=True)
    # NFO with title + year but NO uniqueid elements.
    _EMPTY_IDS_NFO = """<?xml version="1.0" encoding="UTF-8"?>
<movie>
    <title>Empty NFO Film</title>
    <year>2020</year>
    <plot>Has an NFO but no provider ids.</plot>
</movie>
"""
    (movie / "movie.nfo").write_text(_EMPTY_IDS_NFO, encoding="utf-8")
    _write_video(movie / "Empty NFO Film (2020).mkv", size=1024)
    client = _make_client(test_config, staging_dir=staging, db_path=_fresh_db(tmp_path), data_dir=data_dir)

    media_id = media_id_for("001-MOVIES/Empty NFO Film (2020)")
    resp = client.post(
        f"/api/staging/media/{media_id}/continue",
        headers={"X-Requested-With": "TorrentMate"},
    )
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert "NFO illisible" in detail
    assert "movie.nfo" in detail


def test_discard_move_failure_returns_500_and_no_journal(test_config, tmp_path: Path) -> None:
    """B1 — when ``shutil.move`` raises, returns 500 with FR detail, no journal row.

    Monkeypatches ``shutil.move`` to raise ``OSError``; the response must carry
    the folder name and error class, and the ``destructive_op`` table must stay
    empty (journal write is strictly AFTER a successful move).
    """
    from unittest.mock import patch

    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    item = staging / "098-AUTRES" / "move.fail-GRP"
    item.mkdir(parents=True)
    _write_video(item / "data.bin", size=64)
    db_path = _fresh_db(tmp_path)
    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)

    media_id = media_id_for("098-AUTRES/move.fail-GRP")
    with patch("personalscraper.web.routes.staging.shutil.move", side_effect=OSError("Disk full")):
        resp = client.post(
            f"/api/staging/media/{media_id}/discard",
            headers={"X-Requested-With": "TorrentMate"},
        )

    assert resp.status_code == 500, resp.text
    detail = resp.json()["detail"]
    assert "Échec de la mise en quarantaine" in detail
    assert "move.fail-GRP" in detail
    assert "OSError" in detail
    assert "Aucun journal écrit" in detail

    # The folder was NOT moved (move raised before completing).
    assert item.exists()

    # No journal row was written.
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT COUNT(*) FROM destructive_op WHERE actor = 'web'").fetchone()
    conn.close()
    assert rows[0] == 0


def test_discard_readback_exact_detail_match(test_config, tmp_path: Path) -> None:
    """B2 — read-back matches the fresh row only (exact detail), ignoring stale rows.

    Seeds an OLD journal row with the SAME source path but a DIFFERENT destination
    in ``detail``.  After a fresh discard, ``journaled`` must still be ``True``
    — the exact-detail match ignores the stale row.
    """
    import sqlite3
    import time as _time

    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    item = staging / "098-AUTRES" / "stale.row-GRP"
    item.mkdir(parents=True)
    _write_video(item / "data.bin", size=64)
    db_path = _fresh_db(tmp_path)

    # Seed an old row with the same source path but a different detail (a past
    # discard of an identically-named but different item).
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO destructive_op (ts, op, path, actor, detail, run_uid) VALUES (?, 'delete', ?, 'web', ?, NULL)",
        (
            _time.time() - 3600,
            str(item),
            "Discard non-media artifact: stale.row-GRP -> /tmp/old/quarantine/deadbeefdeadbeef",
        ),
    )
    conn.commit()
    conn.close()

    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)
    media_id = media_id_for("098-AUTRES/stale.row-GRP")
    resp = client.post(
        f"/api/staging/media/{media_id}/discard",
        headers={"X-Requested-With": "TorrentMate"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # The fresh row MUST be found (exact detail match) despite the stale row
    # with the same source path.
    assert body["journaled"] is True
    assert body["detail"] == ("Artefact mis en quarantaine — trace écrite au journal des suppressions.")


def test_discard_journal_fail_readback_not_fooled_by_stale_row(test_config, tmp_path: Path) -> None:
    """B3 — a stale row with the same path does NOT fake ``journaled=True``.

    Seeds an old ``destructive_op`` row with the SAME source path but a
    DIFFERENT detail, then patches ``record_destruction`` to no-op (simulating
    a silent journal-write failure).  The exact-detail read-back must NOT match
    the stale row — ``journaled`` must be ``False``.  A path-only read-back
    would incorrectly return True.
    """
    import sqlite3
    import time as _time
    from unittest.mock import patch

    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (staging / "097-TEMP").mkdir(parents=True)
    item = staging / "098-AUTRES" / "stale.row-fail-GRP"
    item.mkdir(parents=True)
    _write_video(item / "data.bin", size=64)
    db_path = _fresh_db(tmp_path)

    # Seed a stale row with the same source path but a different detail (an old,
    # unrelated discard of a same-named folder).
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO destructive_op (ts, op, path, actor, detail, run_uid) VALUES (?, 'delete', ?, 'web', ?, NULL)",
        (
            _time.time() - 3600,
            str(item),
            "Discard non-media artifact: stale.row-fail-GRP -> /tmp/old/quarantine/ffffffffffffffff",
        ),
    )
    conn.commit()
    conn.close()

    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)
    media_id = media_id_for("098-AUTRES/stale.row-fail-GRP")

    # record_destruction is a no-op — the fresh row is NEVER written.
    with patch(
        "personalscraper.web.routes.staging.record_destruction",
        return_value=None,
    ):
        resp = client.post(
            f"/api/staging/media/{media_id}/discard",
            headers={"X-Requested-With": "TorrentMate"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # The exact-detail read-back must NOT find the stale row (different detail).
    # A path-only read-back would incorrectly return True here.
    assert body["journaled"] is False
    assert "ATTENTION" in body["detail"]


def test_continue_deferred_writes_marker_and_read_model_exposes_it(
    test_config,
    tmp_path: Path,
) -> None:
    """A1 — a deferred continue writes ``.continuation-requested``; read-model exposes it.

    When the pipeline lock is held, the continue endpoint writes a marker file
    in the media folder.  The read-model then exposes ``continuation_requested_at``
    on the staging item.  A successful re-spawn (subsequent continue call that
    starts the pipeline) consumes (unlinks) the marker; the read-model never
    unlinks it — it is display-only.
    """
    from unittest.mock import patch

    from personalscraper.web.staging.read_model import media_id_for

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    db_path = _fresh_db(tmp_path)
    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)

    media_id = media_id_for("001-MOVIES/Fight Club (1999)")
    fight_dir = staging / "001-MOVIES" / "Fight Club (1999)"

    # 1. Deferred continue writes the marker.
    with patch("personalscraper.web.pipeline_trigger.is_lock_held", return_value=True):
        with patch("personalscraper.web.pipeline_trigger.subprocess.Popen"):
            resp = client.post(
                f"/api/staging/media/{media_id}/continue",
                headers={"X-Requested-With": "TorrentMate"},
            )
    assert resp.status_code == 202, resp.text
    assert resp.json()["deferred"] is True
    marker = fight_dir / ".continuation-requested"
    assert marker.exists()
    marker_ts = float(marker.read_text(encoding="utf-8").strip())
    assert marker_ts > 0

    # 2. Read-model exposes continuation_requested_at from the marker file.
    items = _by_folder(client.get("/api/staging/media").json())
    fight = items["Fight Club (1999)"]
    assert fight["continuation_requested_at"] == marker_ts

    # 3. A SECOND continue (successful this time) unsets the marker.
    with patch("personalscraper.web.pipeline_trigger.subprocess.Popen"):
        resp2 = client.post(
            f"/api/staging/media/{media_id}/continue",
            headers={"X-Requested-With": "TorrentMate"},
        )
    assert resp2.status_code == 202, resp.text
    assert resp2.json()["deferred"] is False
    # The marker was consumed by the successful continue call.
    assert not marker.exists()


def test_continue_stale_marker_surfaced_by_read_model(test_config, tmp_path: Path) -> None:
    """A1 — a stale marker from a prior session IS surfaced by the read-model.

    The read-model never auto-unlinks the marker — it is display-only.  Only a
    subsequent successful continue call consummates it.  A stale marker (from a
    prior deferral, even on a now-verified item) stays visible so the operator
    knows a continue was requested.
    """
    import time as _time

    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    db_path = _fresh_db(tmp_path)

    # Write a stale marker on a verified (not blocked) item.
    fight_dir = staging / "001-MOVIES" / "Fight Club (1999)"
    marker = fight_dir / ".continuation-requested"
    stale_ts = _time.time() - 7200
    marker.write_text(str(stale_ts), encoding="utf-8")
    assert marker.exists()

    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)
    items = _by_folder(client.get("/api/staging/media").json())
    fight = items["Fight Club (1999)"]

    # The marker is surfaced for display — the « Reprise demandée » chip.
    assert fight["continuation_requested_at"] == stale_ts
    # The marker file survives (read-model never unlinks it).
    assert marker.exists()
