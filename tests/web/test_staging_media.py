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

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from personalscraper.conf.models.staging import StagingDirConfig
from personalscraper.config import Settings
from personalscraper.indexer import migrations as _migrations_pkg
from personalscraper.indexer.db import apply_migrations
from personalscraper.web.auth.passwords import hash_password
from personalscraper.web.deps import require_session

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


def _mount_guarded(app: FastAPI, router: APIRouter) -> None:
    """Mount *router* behind the session-guard perimeter, mirroring app.py (R14)."""
    guarded_api = APIRouter(dependencies=[Depends(require_session)])
    guarded_api.include_router(router)
    app.include_router(guarded_api)


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

    app = FastAPI()
    app.state.config = cfg
    app.state.settings = settings

    from personalscraper.web.auth.routes import router as auth_router
    from personalscraper.web.routes.staging import router as staging_router

    app.include_router(auth_router)
    _mount_guarded(app, staging_router)

    client = TestClient(app, base_url="https://testserver")
    resp = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 204, f"Login failed: {resp.status_code}"
    return client


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
    assert _stage(unmatched, "matching") == "pending"
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
    # No NFO → the stray trailer/poster must NOT push a downstream stage to done.
    assert _stage(item, "matching") == "pending"
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

    # Everything not yet scraped is "at/awaiting" the scraping stage.
    awaiting_scrape = client.get("/api/staging/media", params={"stage": "scraping"}).json()
    assert {i["folder"] for i in awaiting_scrape["items"]} == {"Unknown Film (2020)"}


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
    """A live run at the scrape step marks the frontier scraping stage active."""
    staging = tmp_path / "staging"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _seed_tree(staging)
    db_path = _fresh_db(tmp_path)
    # Hold the lock with this process's pid so the run reads as live.
    (data_dir / "pipeline.lock").write_text(str(os.getpid()))
    _insert_running_run(db_path, step="scrape")

    client = _make_client(test_config, staging_dir=staging, db_path=db_path, data_dir=data_dir)
    items = _by_folder(client.get("/api/staging/media").json())

    # The unscraped movie's scraping stage was pending → active under the live run.
    assert _stage(items["Unknown Film (2020)"], "scraping") == "active"
    # The already-scraped movie stays done, not active.
    assert _stage(items["Fight Club (1999)"], "scraping") == "done"


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
