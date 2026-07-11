"""Tests for ``GET /api/pipeline/stages`` — the OBJ1 Flow Board aggregation.

Seeds a temp ``library.db`` via the real indexer migrations, then asserts the
nine-stage roll-up: per-step counts sourced from the latest ``pipeline_run``
``steps_json``, the Matching stage sourced from the live ``scrape_decision``
pending queue (split by ``trigger``), derived ring states, and the live run
state / active-stage highlighting.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

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


def _mount_guarded(app: FastAPI, router: APIRouter) -> None:
    """Mount *router* behind the session-guard perimeter, mirroring app.py (R14)."""
    guarded_api = APIRouter(dependencies=[Depends(require_session)])
    guarded_api.include_router(router)
    app.include_router(guarded_api)


def _make_client(test_config, db_path: Path, data_dir: Path) -> TestClient:
    """Build an authenticated ``TestClient`` with pipeline routes wired to *db_path*."""
    cfg = test_config.model_copy(
        update={
            "paths": test_config.paths.model_copy(update={"data_dir": data_dir}),
            "indexer": test_config.indexer.model_copy(update={"db_path": db_path}),
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
        'INSERT INTO scrape_decision '
        '(staging_path, media_kind, extracted_title, extracted_year, "trigger", '
        "candidates_json, status, created_at, updated_at) "
        "VALUES (?, 'movie', 'Some Title', 2020, ?, '[]', ?, ?, ?)",
        (staging_path, trigger, status, _T0, _T0),
    )
    conn.commit()
    conn.close()


def _stages_by_key(payload: dict) -> dict[str, dict]:
    """Index the ``stages`` array by its ``key`` for direct assertion access."""
    return {s["key"]: s for s in payload["stages"]}


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_stages_empty_db_all_idle(test_config, tmp_path: Path) -> None:
    """A migrated-but-empty DB yields nine idle stages and idle run state."""
    db_path = _fresh_db(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    client = _make_client(test_config, db_path, data_dir)

    resp = client.get("/api/pipeline/stages")
    assert resp.status_code == 200
    payload = resp.json()

    assert [s["key"] for s in payload["stages"]] == [
        "arrival",
        "staging",
        "cleaning",
        "sorting",
        "matching",
        "scraping",
        "trailers",
        "verify",
        "dispatch",
    ]
    assert payload["run_state"] == "idle"
    assert payload["run_uid"] is None
    for stage in payload["stages"]:
        assert stage["count"] == 0
        assert stage["state"] == "idle"
        assert stage["split"] is None


def test_stages_rolls_up_last_run_counts(test_config, tmp_path: Path) -> None:
    """Per-step counts + derived states come from the latest pipeline run."""
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

    client = _make_client(test_config, db_path, data_dir)
    payload = client.get("/api/pipeline/stages").json()
    stages = _stages_by_key(payload)

    assert payload["run_uid"] == "run-latest"
    assert payload["run_state"] == "idle"

    # Arrival (ingest): pure success → ok, no split.
    assert stages["arrival"]["count"] == 10
    assert stages["arrival"]["state"] == "ok"
    assert stages["arrival"]["split"] is None

    # Staging (sort): success + skip → split réussi/ignoré, state ok.
    assert stages["staging"]["count"] == 8
    assert stages["staging"]["state"] == "ok"
    split_labels = {s["label"]: s["count"] for s in stages["staging"]["split"]}
    assert split_labels == {"réussi": 8, "ignoré": 2}

    # Scraping (scrape): unmatched → attention state + attention count.
    assert stages["scraping"]["count"] == 5
    assert stages["scraping"]["state"] == "attention"
    assert stages["scraping"]["attention"] == 3
    scrape_split = {s["label"]: s["count"] for s in stages["scraping"]["split"]}
    assert scrape_split == {"réussi": 5, "sans correspondance": 3}

    # Dispatch: pure success → ok.
    assert stages["dispatch"]["count"] == 5
    assert stages["dispatch"]["state"] == "ok"

    # Stages with no step in this run stay idle.
    for key in ("cleaning", "sorting", "trailers", "verify"):
        assert stages[key]["count"] == 0
        assert stages[key]["state"] == "idle"


def test_stages_blocked_on_step_error(test_config, tmp_path: Path) -> None:
    """A step with error_count > 0 renders its stage blocked."""
    db_path = _fresh_db(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    _insert_run(
        db_path,
        run_uid="run-err",
        started_at=_T0 + 6000.0,
        ended_at=_T0 + 6100.0,
        outcome="error",
        steps=[{"name": "dispatch", "status": "error", "success_count": 2, "error_count": 3}],
    )

    client = _make_client(test_config, db_path, data_dir)
    stages = _stages_by_key(client.get("/api/pipeline/stages").json())

    assert stages["dispatch"]["state"] == "blocked"
    assert stages["dispatch"]["blocked"] == 3
    dispatch_split = {s["label"]: s["count"] for s in stages["dispatch"]["split"]}
    assert dispatch_split == {"réussi": 2, "erreur": 3}


def test_stages_matching_from_pending_decisions(test_config, tmp_path: Path) -> None:
    """Matching stage counts pending decisions split by trigger; resolved excluded."""
    db_path = _fresh_db(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    _insert_decision(db_path, staging_path="/s/a", trigger="ambiguous")
    _insert_decision(db_path, staging_path="/s/b", trigger="ambiguous")
    _insert_decision(db_path, staging_path="/s/c", trigger="below_threshold")
    _insert_decision(db_path, staging_path="/s/d", trigger="mid_band")
    # A resolved decision must NOT count toward the pending Matching backlog.
    _insert_decision(db_path, staging_path="/s/e", trigger="ambiguous", status="resolved")

    client = _make_client(test_config, db_path, data_dir)
    stages = _stages_by_key(client.get("/api/pipeline/stages").json())
    matching = stages["matching"]

    assert matching["count"] == 4
    assert matching["attention"] == 4
    assert matching["state"] == "attention"
    split = {s["label"]: s["count"] for s in matching["split"]}
    assert split == {"ambigu": 2, "sans correspondance": 1, "incertain": 1}


def test_stages_active_stage_when_running(test_config, tmp_path: Path) -> None:
    """A live run (lock held) marks its current step's stage active."""
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

    client = _make_client(test_config, db_path, data_dir)
    payload = client.get("/api/pipeline/stages").json()
    stages = _stages_by_key(payload)

    assert payload["run_state"] == "running"
    # scrape is the last (current) step → scraping stage is active.
    assert stages["scraping"]["state"] == "active"
    # A completed earlier step stays ok, not active.
    assert stages["arrival"]["state"] == "ok"


@pytest.mark.parametrize("missing", ["nonexistent.db"])
def test_stages_missing_db_is_all_idle(test_config, tmp_path: Path, missing: str) -> None:
    """A missing DB file fails soft: all stages idle, run state idle (no 500)."""
    db_path = tmp_path / missing
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    client = _make_client(test_config, db_path, data_dir)

    resp = client.get("/api/pipeline/stages")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["run_state"] == "idle"
    assert all(s["state"] == "idle" for s in payload["stages"])
