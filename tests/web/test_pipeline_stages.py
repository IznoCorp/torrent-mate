"""Tests for ``GET /api/pipeline/stages`` — the Flow Board stock aggregation.

P0-A semantics: each station shows the CURRENT STOCK of media at that
position in the staging area (single-position axiom — the same verdict the
per-stage lists use), while the last run's throughput lives only in the
response header fields (``run_uid`` / ``updated_at`` / ``run_processed``).
Seeds a temp staging tree + a temp ``library.db`` via the real indexer
migrations and asserts stocks, blocked counts, header fields, the live-run
active station and fail-soft behaviour.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from personalscraper.conf.models.staging import StagingDirConfig
from personalscraper.config import Settings
from personalscraper.indexer import migrations as _migrations_pkg
from personalscraper.indexer.db import apply_migrations
from personalscraper.web.auth.passwords import hash_password
from personalscraper.web.deps import require_session

TEST_USERNAME = "stages-test"
TEST_PASSWORD = "stages-test-password"
TEST_HASH = hash_password(TEST_PASSWORD)
TEST_SECRET = "pipeline-stages-test-secret"

_T0 = 1750000000.0  # 2025-06-15T12:26:40+00:00

#: The eight Flow Board stations, in board order (web/staging/stages.py).
_EXPECTED_KEYS = ["arrival", "sorting", "cleaning", "matching", "scraping", "trailers", "verify", "dispatch"]

_MOVIE_NFO = """<?xml version="1.0" encoding="UTF-8"?>
<movie>
    <title>Fight Club</title>
    <year>1999</year>
    <uniqueid type="tmdb" default="true">550</uniqueid>
    <category source="personalscraper">movies</category>
</movie>
"""


def _mount_guarded(app: FastAPI, router: APIRouter) -> None:
    """Mount *router* behind the session-guard perimeter, mirroring app.py (R14)."""
    guarded_api = APIRouter(dependencies=[Depends(require_session)])
    guarded_api.include_router(router)
    app.include_router(guarded_api)


def _staging_dirs() -> list[StagingDirConfig]:
    """Return the movie/tvshow/ingest staging layout used by the stock tests."""
    return [
        StagingDirConfig(id=1, name="movies", file_type="movie"),
        StagingDirConfig(id=2, name="tvshows", file_type="tvshow"),
        StagingDirConfig(id=97, name="temp", role="ingest"),
    ]


def _make_client(test_config, db_path: Path, data_dir: Path, staging_dir: Path | None = None) -> TestClient:
    """Build an authenticated ``TestClient`` with pipeline routes wired to *db_path*."""
    cfg = test_config.model_copy(
        update={
            "paths": test_config.paths.model_copy(
                update={"data_dir": data_dir, **({"staging_dir": staging_dir} if staging_dir else {})}
            ),
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
    from personalscraper.web.routes.pipeline import router as pipeline_router

    app.include_router(auth_router)
    _mount_guarded(app, pipeline_router)

    client = TestClient(app, base_url="https://testserver")
    resp = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 204, f"Login failed: {resp.status_code}"
    return client


def _fresh_db(tmp_path: Path) -> Path:
    """Create an empty migrated ``library.db`` (schema only, no rows)."""
    db_path = tmp_path / "stages.db"
    conn = sqlite3.connect(str(db_path))
    migrations_dir = Path(_migrations_pkg.__file__).parent
    apply_migrations(conn, migrations_dir)
    conn.commit()
    conn.close()
    return db_path


def _insert_run(
    db_path: Path,
    *,
    run_uid: str,
    started_at: float,
    ended_at: float | None,
    outcome: str | None,
    steps: list[dict[str, object]],
    pid: int | None = None,
    kind: str = "pipeline",
) -> None:
    """Insert one ``pipeline_run`` row with a ``steps_json`` payload."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO pipeline_run "
        "(run_uid, trigger, dry_run, started_at, ended_at, outcome, "
        "steps_json, error, pid, kind, command, options_json, output_tail) "
        "VALUES (?, 'web', 0, ?, ?, ?, ?, NULL, ?, ?, NULL, NULL, NULL)",
        (run_uid, started_at, ended_at, outcome, json.dumps(steps), pid, kind),
    )
    conn.commit()
    conn.close()


def _insert_decision(
    db_path: Path,
    *,
    staging_path: str,
    trigger: str,
    status: str = "pending",
) -> None:
    """Insert one ``scrape_decision`` row (candidates_json is a minimal stub)."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO scrape_decision "
        '(staging_path, media_kind, extracted_title, extracted_year, "trigger", '
        "candidates_json, status, created_at, updated_at) "
        "VALUES (?, 'movie', 'Some Title', 2020, ?, '[]', ?, ?, ?)",
        (staging_path, trigger, status, _T0, _T0),
    )
    conn.commit()
    conn.close()


def _write_video(path: Path, size: int = 16) -> None:
    """Write a small placeholder video file of *size* bytes."""
    path.write_bytes(b"\x00" * size)


def _seed_stock_tree(staging_dir: Path) -> dict[str, Path]:
    """Seed a staging tree with one item per interesting position.

    - ``verified`` — canonical scraped movie → position ``dispatch``;
    - ``absent`` — unidentified movie → blocked at ``matching``;
    - ``temp`` — a folder still in the ingest dir → position ``arrival``.
    """
    movies = staging_dir / "001-MOVIES"
    (staging_dir / "002-TVSHOWS").mkdir(parents=True)
    temp = staging_dir / "097-TEMP"
    temp.mkdir(parents=True)

    verified = movies / "Fight Club (1999)"
    verified.mkdir(parents=True)
    (verified / "Fight Club.nfo").write_text(_MOVIE_NFO, encoding="utf-8")
    (verified / "Fight Club-poster.jpg").write_bytes(b"\xff\xd8\xff\x00poster")
    _write_video(verified / "Fight Club.mkv", size=2048)

    absent = movies / "Unknown Film (2020)"
    absent.mkdir(parents=True)
    _write_video(absent / "Unknown Film (2020).mkv", size=1024)

    arriving = temp / "Fresh.Download.2026.1080p"
    arriving.mkdir(parents=True)
    _write_video(arriving / "Fresh.Download.2026.1080p.mkv", size=512)

    return {"verified": verified, "absent": absent, "arriving": arriving}


def _stages_by_key(payload: dict) -> dict[str, dict]:
    """Index the ``stages`` array by its ``key`` for direct assertion access."""
    return {s["key"]: s for s in payload["stages"]}


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_stages_empty_db_all_idle(test_config, tmp_path: Path) -> None:
    """An empty DB + empty staging yields eight idle stations, idle run state."""
    db_path = _fresh_db(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    client = _make_client(test_config, db_path, data_dir, staging_dir=tmp_path / "staging-empty")

    resp = client.get("/api/pipeline/stages")
    assert resp.status_code == 200
    payload = resp.json()

    assert [s["key"] for s in payload["stages"]] == _EXPECTED_KEYS
    assert payload["run_state"] == "idle"
    assert payload["run_uid"] is None
    assert payload["run_processed"] is None
    for stage in payload["stages"]:
        assert stage["count"] == 0
        assert stage["state"] == "idle"
        assert stage["split"] is None


def test_station_counts_are_stock_not_last_run(test_config, tmp_path: Path) -> None:
    """Stations show the current stock; the last run's throughput stays in the header.

    Regression for « les compteurs traités sont confus » (P0-A.3): a past run
    that processed 10 items must NOT put a 10 on any station when the staging
    area is empty — throughput belongs to the header (``run_processed``).
    """
    db_path = _fresh_db(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    _insert_run(
        db_path,
        run_uid="run-latest",
        started_at=_T0 + 5000.0,
        ended_at=_T0 + 5600.0,
        outcome="success",
        steps=[
            {"name": "ingest", "status": "done", "success_count": 10},
            {"name": "sort", "status": "done", "success_count": 8, "skip_count": 2},
            {"name": "scrape", "status": "done", "success_count": 5, "unmatched_count": 3},
            {"name": "dispatch", "status": "done", "success_count": 5},
        ],
    )
    # An OLDER run must be ignored (latest wins by started_at).
    _insert_run(
        db_path,
        run_uid="run-old",
        started_at=_T0,
        ended_at=_T0 + 100.0,
        outcome="success",
        steps=[{"name": "ingest", "status": "done", "success_count": 999}],
    )

    client = _make_client(test_config, db_path, data_dir, staging_dir=tmp_path / "staging-empty")
    payload = client.get("/api/pipeline/stages").json()

    assert payload["run_uid"] == "run-latest"
    assert payload["run_state"] == "idle"
    # Header throughput = max over steps of success+error+unmatched (ingest: 10).
    assert payload["run_processed"] == 10
    # Stations carry ZERO of that past run — staging is empty, stocks are 0.
    for stage in payload["stages"]:
        assert stage["count"] == 0, f"station {stage['key']} leaked last-run throughput"


def test_station_stocks_match_positions(test_config, tmp_path: Path) -> None:
    """Each station's count is the number of media at that single position."""
    db_path = _fresh_db(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    staging = tmp_path / "staging"
    folders = _seed_stock_tree(staging)
    # One pending decision → the absent movie becomes 'à résoudre' (ambiguous).
    _insert_decision(db_path, staging_path=str(folders["absent"]), trigger="ambiguous")

    client = _make_client(test_config, db_path, data_dir, staging_dir=staging)
    payload = client.get("/api/pipeline/stages").json()
    stages = _stages_by_key(payload)

    assert stages["arrival"]["count"] == 1  # the ingest-dir folder
    assert stages["matching"]["count"] == 1  # the ambiguous movie
    assert stages["matching"]["blocked"] == 1
    assert stages["matching"]["state"] == "blocked"
    split = {s["label"]: s["count"] for s in stages["matching"]["split"]}
    assert split == {"à résoudre": 1}
    assert stages["dispatch"]["count"] == 1  # the verified movie
    assert stages["dispatch"]["state"] == "ok"
    # Nothing anywhere else — stocks are exact, never cumulative.
    for key in ("sorting", "cleaning", "scraping", "trailers", "verify"):
        assert stages[key]["count"] == 0, f"unexpected stock at {key}"
    # The board total reconciles with the staging scan (single source).
    assert sum(s["count"] for s in payload["stages"]) == 3


def test_stages_matching_split_a_qualifier(test_config, tmp_path: Path) -> None:
    """An unidentified item with NO pending decision splits as « à qualifier »."""
    db_path = _fresh_db(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    staging = tmp_path / "staging"
    _seed_stock_tree(staging)

    client = _make_client(test_config, db_path, data_dir, staging_dir=staging)
    stages = _stages_by_key(client.get("/api/pipeline/stages").json())

    assert stages["matching"]["count"] == 1
    split = {s["label"]: s["count"] for s in stages["matching"]["split"]}
    assert split == {"à qualifier": 1}


def test_stages_active_stage_when_running(test_config, tmp_path: Path) -> None:
    """A live run (lock held) marks its current step's station active."""
    db_path = _fresh_db(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Hold the lock with THIS test process's live pid so is_lock_held() is True.
    (data_dir / "pipeline.lock").write_text(str(os.getpid()))

    _insert_run(
        db_path,
        run_uid="run-live",
        started_at=_T0 + 7000.0,
        ended_at=None,
        outcome="running",
        steps=[
            {"name": "ingest", "status": "done", "success_count": 4},
            {"name": "scrape", "status": "running", "success_count": 1},
        ],
        pid=os.getpid(),
    )

    client = _make_client(test_config, db_path, data_dir, staging_dir=tmp_path / "staging-empty")
    payload = client.get("/api/pipeline/stages").json()
    stages = _stages_by_key(payload)

    assert payload["run_state"] == "running"
    # scrape is the last (current) step → the Scraping station is active.
    assert stages["scraping"]["state"] == "active"
    # Other empty stations stay idle.
    assert stages["arrival"]["state"] == "idle"


@pytest.mark.parametrize("missing", ["nonexistent.db"])
def test_stages_missing_db_is_all_idle(test_config, tmp_path: Path, missing: str) -> None:
    """A missing DB file fails soft: all stages idle, run state idle (no 500)."""
    db_path = tmp_path / missing
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    client = _make_client(test_config, db_path, data_dir, staging_dir=tmp_path / "staging-empty")

    resp = client.get("/api/pipeline/stages")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["run_state"] == "idle"
    assert all(s["state"] == "idle" for s in payload["stages"])
