"""Tests for unified pipeline history with kind filter (maint-dash feature).

Covers the ``?kind=`` query parameter on ``GET /api/pipeline/history`` and
the extended ``RunDetail`` fields (``kind``, ``command``, ``options_json``,
``output_tail``) on ``GET /api/pipeline/history/{run_uid}``.

Seeds the database via the real indexer migrations (:func:`apply_migrations`)
rather than a hand-rolled ``CREATE TABLE`` to prevent schema drift.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.indexer import migrations as _migrations_pkg
from personalscraper.indexer.db import apply_migrations
from personalscraper.web.auth.passwords import hash_password
from tests.web._web_harness import guarded_client

TEST_USERNAME = "unified-test"
TEST_PASSWORD = "unified-test-password"
TEST_HASH = hash_password(TEST_PASSWORD)
TEST_SECRET = "unified-history-test-secret"


# ── Timestamp baseline for deterministic sort assertions ─────────────────────
_T0 = 1750000000.0  # 2025-06-15T12:26:40+00:00


def _make_client(test_config, db_path: Path, data_dir: Path) -> TestClient:
    """Build an authenticated ``TestClient`` with pipeline routes wired to *db_path*.

    Args:
        test_config: Synthetic ``Config`` fixture.
        db_path: Path to the seeded test database.
        data_dir: Temp ``.data/`` directory for sentinel files.

    Returns:
        Authenticated ``TestClient`` ready for history route assertions.
    """
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

    from personalscraper.web.routes.pipeline import router as pipeline_router

    return guarded_client(
        config=cfg,
        settings=settings,
        routers=pipeline_router,
        login=(TEST_USERNAME, TEST_PASSWORD),
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def unified_history_db(tmp_path: Path) -> Path:
    """Create a temp ``library.db`` via real migrations, seeded with both run kinds.

    Applies all indexer migrations (001–012) so the schema is the canonical
    one — no hand-rolled ``CREATE TABLE`` that can drift from the migrations.

    Seeds 3 ``pipeline`` rows + 2 ``maintenance`` rows.  Maintenance rows
    have ``command``, ``options_json``, and ``output_tail`` populated;
    pipeline rows have ``steps_json`` and ``None`` for maintenance columns.

    Args:
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        Absolute path to the populated database file.
    """
    db_path = tmp_path / "unified_history.db"
    conn = sqlite3.connect(str(db_path))
    migrations_dir = Path(_migrations_pkg.__file__).parent
    apply_migrations(conn, migrations_dir)

    now = _T0
    rows = [
        # ── 3 pipeline rows ──────────────────────────────────────────────
        (
            "p1-aaa111",  # run_uid
            "cli",  # trigger
            0,  # dry_run
            now,  # started_at
            now + 120.5,  # ended_at
            "success",  # outcome
            json.dumps(
                [
                    {
                        "name": "ingest",
                        "status": "done",
                        "started_at": now,
                        "ended_at": now + 60.0,
                    },
                    {
                        "name": "sort",
                        "status": "done",
                        "started_at": now + 60.0,
                        "ended_at": now + 120.5,
                    },
                ]
            ),
            None,  # error
            12345,  # pid
            "pipeline",  # kind
            None,  # command
            None,  # options_json
            None,  # output_tail
        ),
        (
            "p2-bbb222",
            "web",
            1,
            now + 1000.0,
            now + 1060.0,
            "error",
            json.dumps(
                [
                    {
                        "name": "ingest",
                        "status": "error",
                        "started_at": now + 1000.0,
                        "ended_at": now + 1060.0,
                    }
                ]
            ),
            "Something went wrong",
            12346,
            "pipeline",
            None,
            None,
            None,
        ),
        (
            "p3-ccc333",
            "watcher",
            0,
            now + 2000.0,
            None,  # still running
            None,
            json.dumps(
                [
                    {
                        "name": "ingest",
                        "status": "running",
                        "started_at": now + 2000.0,
                        "ended_at": None,
                    }
                ]
            ),
            None,
            12347,
            "pipeline",
            None,
            None,
            None,
        ),
        # ── 2 maintenance rows ───────────────────────────────────────────
        (
            "m1-ddd444",
            "web",
            1,  # dry_run=True
            now + 3000.0,
            now + 3060.0,
            "success",
            None,  # steps_json — maintenance rows have no steps
            None,  # error
            None,  # pid — maintenance actions are not subprocess-tracked
            "maintenance",
            "library-clean",
            json.dumps({"dry_run": True}),
            "Cleaned 5 orphan items.\nDone.",
        ),
        (
            "m2-eee555",
            "web",
            0,  # dry_run=False
            now + 4000.0,
            now + 4010.0,
            "success",
            None,
            None,
            None,
            "maintenance",
            "library-rescrape",
            json.dumps({"targets": ["tt123456"]}),
            "Rescraped 1 item.\nDone.",
        ),
    ]
    conn.executemany(
        "INSERT INTO pipeline_run "
        "(run_uid, trigger, dry_run, started_at, ended_at, outcome, "
        "steps_json, error, pid, kind, command, options_json, output_tail) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def unified_history_client(
    test_config,
    unified_history_db: Path,
    tmp_path: Path,
) -> TestClient:
    """Authenticated ``TestClient`` pointed at the unified-history test database.

    Args:
        test_config: Synthetic ``Config`` fixture.
        unified_history_db: Path to the pre-seeded test database.
        tmp_path: Pytest temporary directory.

    Returns:
        Authenticated ``TestClient`` with history routes served.
    """
    data_dir = tmp_path / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return _make_client(test_config, unified_history_db, data_dir)


# ── GET /api/pipeline/history — kind filter ───────────────────────────────────


class TestUnifiedHistoryList:
    """``GET /api/pipeline/history`` with ``?kind=`` query parameter."""

    def test_default_returns_all_kinds(self, unified_history_client: TestClient) -> None:
        """Default (no ``?kind``) → both pipeline + maintenance rows, total 5."""
        resp = unified_history_client.get("/api/pipeline/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["runs"]) == 5
        kinds = {r["kind"] for r in data["runs"]}
        assert kinds == {"pipeline", "maintenance"}

    def test_kind_all_returns_all(self, unified_history_client: TestClient) -> None:
        """``?kind=all`` (explicit) → both kinds, total 5."""
        resp = unified_history_client.get("/api/pipeline/history", params={"kind": "all"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["runs"]) == 5

    def test_kind_pipeline_returns_only_pipeline(self, unified_history_client: TestClient) -> None:
        """``?kind=pipeline`` → only ``kind='pipeline'`` rows, total 3."""
        resp = unified_history_client.get("/api/pipeline/history", params={"kind": "pipeline"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["runs"]) == 3
        for run in data["runs"]:
            assert run["kind"] == "pipeline"
            assert run["command"] is None

    def test_kind_maintenance_returns_only_maintenance(self, unified_history_client: TestClient) -> None:
        """``?kind=maintenance`` → only ``kind='maintenance'`` rows, each has command."""
        resp = unified_history_client.get("/api/pipeline/history", params={"kind": "maintenance"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["runs"]) == 2
        for run in data["runs"]:
            assert run["kind"] == "maintenance"
            assert run["command"] is not None

    def test_invalid_kind_returns_400(self, unified_history_client: TestClient) -> None:
        """``?kind=invalid`` → 400 with allowed values in detail."""
        resp = unified_history_client.get("/api/pipeline/history", params={"kind": "invalid"})
        assert resp.status_code == 400
        assert "Invalid kind" in resp.json()["detail"]

    def test_pagination_with_kind_filter(self, unified_history_client: TestClient) -> None:
        """``?kind=maintenance&limit=1&offset=1`` → 1 row, total stays 2."""
        resp = unified_history_client.get(
            "/api/pipeline/history",
            params={
                "kind": "maintenance",
                "limit": 1,
                "offset": 1,
                "sort": "started_at",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["runs"]) == 1
        # Second maintenance row (offset=1 with started_at ASC) is m2-eee555.
        assert data["runs"][0]["run_uid"] == "m2-eee555"


# ── GET /api/pipeline/history/{run_uid} — detail with kind fields ────────────


class TestUnifiedHistoryDetail:
    """``GET /api/pipeline/history/{run_uid}`` with extended maintenance fields."""

    def test_detail_maintenance_run_populates_all_fields(self, unified_history_client: TestClient) -> None:
        """Detail of a maintenance run → kind, command, options_json, output_tail."""
        resp = unified_history_client.get("/api/pipeline/history/m1-ddd444")
        assert resp.status_code == 200
        data = resp.json()
        assert data["kind"] == "maintenance"
        assert data["command"] == "library-clean"
        assert data["options_json"] is not None
        # options_json is stored as a JSON string in the DB column.
        assert "dry_run" in data["options_json"]
        assert data["output_tail"] == "Cleaned 5 orphan items.\nDone."
        # Maintenance runs have no pipeline steps.
        assert data["steps"] == []

    def test_detail_pipeline_run_has_kind_pipeline_command_none(self, unified_history_client: TestClient) -> None:
        """Detail of a pipeline run → kind='pipeline', command=None, steps populated."""
        resp = unified_history_client.get("/api/pipeline/history/p1-aaa111")
        assert resp.status_code == 200
        data = resp.json()
        assert data["kind"] == "pipeline"
        assert data["command"] is None
        assert data["options_json"] is None
        assert data["output_tail"] is None
        # Pipeline runs have steps.
        assert len(data["steps"]) == 2
        assert data["steps"][0]["name"] == "ingest"
        assert data["steps"][1]["name"] == "sort"

    def test_detail_legacy_steps_have_null_summary(self, unified_history_client: TestClient) -> None:
        """webui-ux 2.2: legacy ``steps_json`` (no counts) → summary fields null (fail-soft)."""
        resp = unified_history_client.get("/api/pipeline/history/p1-aaa111")
        assert resp.status_code == 200
        data = resp.json()
        # The seeded p1-aaa111 steps predate Phase 2.2 — the response still
        # parses, with the new summary fields defaulting to None.
        step = data["steps"][0]
        assert step["success_count"] is None
        assert step["skip_count"] is None
        assert step["error_count"] is None
        assert step["unmatched_count"] is None
        assert step["counts"] is None

    def test_detail_persisted_summary_round_trips(self, test_config, tmp_path: Path) -> None:
        """webui-ux 2.2: a steps_json entry WITH counts surfaces on the detail read."""
        db_path = tmp_path / "summary.db"
        conn = sqlite3.connect(str(db_path))
        migrations_dir = Path(_migrations_pkg.__file__).parent
        apply_migrations(conn, migrations_dir)
        steps = json.dumps(
            [
                {
                    "name": "scrape",
                    "status": "success",
                    "started_at": _T0,
                    "ended_at": _T0 + 5.0,
                    "success_count": 3,
                    "skip_count": 1,
                    "error_count": 0,
                    "unmatched_count": 2,
                    "counts": {"downloaded": 3, "bot_detected": 1},
                }
            ]
        )
        conn.execute(
            "INSERT INTO pipeline_run "
            "(run_uid, trigger, dry_run, started_at, ended_at, outcome, "
            "steps_json, error, pid, kind, command, options_json, output_tail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "sum-run-1",
                "web",
                0,
                _T0,
                _T0 + 5.0,
                "success",
                steps,
                None,
                999,
                "pipeline",
                None,
                None,
                None,
            ),
        )
        conn.commit()
        conn.close()

        data_dir = tmp_path / ".data"
        data_dir.mkdir(parents=True, exist_ok=True)
        client = _make_client(test_config, db_path, data_dir)

        resp = client.get("/api/pipeline/history/sum-run-1")
        assert resp.status_code == 200
        step = resp.json()["steps"][0]
        assert step["success_count"] == 3
        assert step["skip_count"] == 1
        assert step["error_count"] == 0
        assert step["unmatched_count"] == 2
        assert step["counts"] == {"downloaded": 3, "bot_detected": 1}

    def test_detail_step_reasons_round_trip(self, test_config, tmp_path: Path) -> None:
        """§8: persisted per-step reason strings surface on the detail read.

        A legacy entry without ``reasons`` still parses (field defaults None).
        """
        db_path = tmp_path / "reasons.db"
        conn = sqlite3.connect(str(db_path))
        migrations_dir = Path(_migrations_pkg.__file__).parent
        apply_migrations(conn, migrations_dir)
        steps = json.dumps(
            [
                {
                    "name": "ingest",
                    "status": "success",
                    "started_at": _T0,
                    "ended_at": _T0 + 2.0,
                    "skip_count": 2,
                    "reasons": ["Film X : espace disque insuffisant", "Série Y : contenu introuvable"],
                },
                {"name": "sort", "status": "success", "started_at": _T0 + 2.0, "ended_at": _T0 + 3.0},
            ]
        )
        conn.execute(
            "INSERT INTO pipeline_run "
            "(run_uid, trigger, dry_run, started_at, ended_at, outcome, "
            "steps_json, error, pid, kind, command, options_json, output_tail) "
            "VALUES (?, 'web', 0, ?, ?, 'success', ?, NULL, 999, 'pipeline', NULL, NULL, NULL)",
            ("reasons-run-1", _T0, _T0 + 3.0, steps),
        )
        conn.commit()
        conn.close()

        data_dir = tmp_path / ".data"
        data_dir.mkdir(parents=True, exist_ok=True)
        client = _make_client(test_config, db_path, data_dir)

        resp = client.get("/api/pipeline/history/reasons-run-1")
        assert resp.status_code == 200
        steps_out = resp.json()["steps"]
        assert steps_out[0]["reasons"] == [
            "Film X : espace disque insuffisant",
            "Série Y : contenu introuvable",
        ]
        # A step with no reasons key → None (legacy-safe).
        assert steps_out[1]["reasons"] is None

    def test_detail_second_maintenance_run(self, unified_history_client: TestClient) -> None:
        """Detail of the second maintenance run → different command and options."""
        resp = unified_history_client.get("/api/pipeline/history/m2-eee555")
        assert resp.status_code == 200
        data = resp.json()
        assert data["kind"] == "maintenance"
        assert data["command"] == "library-rescrape"
        assert data["options_json"] is not None
        assert "targets" in data["options_json"]
        assert data["output_tail"] == "Rescraped 1 item.\nDone."
        assert data["dry_run"] is False

    def test_detail_404_unknown_uid(self, unified_history_client: TestClient) -> None:
        """A non-existent ``run_uid`` → 404.

        Regression: kind filter must not interfere with detail lookup.
        """
        resp = unified_history_client.get("/api/pipeline/history/nonexistent")
        assert resp.status_code == 404

    def test_detail_db_error_is_not_404(self, test_config, tmp_path: Path) -> None:
        """An operational DB error surfaces as 500, NOT a bogus 404 (Finding F).

        An un-migrated / broken DB (here: the ``pipeline_run`` table is absent)
        must not masquerade every run as "not found" — the detail route
        distinguishes a genuinely absent row (404) from a query failure (500).
        """
        broken_db = tmp_path / "broken.db"
        conn = sqlite3.connect(str(broken_db))
        conn.execute("CREATE TABLE unrelated (x INTEGER)")
        conn.commit()
        conn.close()

        data_dir = tmp_path / ".data"
        data_dir.mkdir(parents=True, exist_ok=True)
        client = _make_client(test_config, broken_db, data_dir)

        resp = client.get("/api/pipeline/history/any-run-uid")
        assert resp.status_code != 404
        assert resp.status_code == 500


# ── Guards ────────────────────────────────────────────────────────────────────


class TestUnifiedHistoryGuards:
    """Auth guards still apply on history routes."""

    def test_history_list_401_without_session(self, test_config, unified_history_db: Path, tmp_path: Path) -> None:
        """GET /api/pipeline/history without session → 401."""
        data_dir = tmp_path / ".data"
        data_dir.mkdir(parents=True, exist_ok=True)
        cfg = test_config.model_copy(
            update={
                "paths": test_config.paths.model_copy(update={"data_dir": data_dir}),
                "indexer": test_config.indexer.model_copy(update={"db_path": unified_history_db}),
            },
        )
        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            web_password_hash=TEST_HASH,
            web_jwt_secret=TEST_SECRET,
        )
        from personalscraper.web.routes.pipeline import router as pipeline_router

        client = guarded_client(config=cfg, settings=settings, routers=pipeline_router, with_auth=False)

        resp = client.get("/api/pipeline/history")
        assert resp.status_code == 401

    def test_history_detail_401_without_session(self, test_config, unified_history_db: Path, tmp_path: Path) -> None:
        """GET /api/pipeline/history/{uid} without session → 401."""
        data_dir = tmp_path / ".data"
        data_dir.mkdir(parents=True, exist_ok=True)
        cfg = test_config.model_copy(
            update={
                "paths": test_config.paths.model_copy(update={"data_dir": data_dir}),
                "indexer": test_config.indexer.model_copy(update={"db_path": unified_history_db}),
            },
        )
        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            web_password_hash=TEST_HASH,
            web_jwt_secret=TEST_SECRET,
        )
        from personalscraper.web.routes.pipeline import router as pipeline_router

        client = guarded_client(config=cfg, settings=settings, routers=pipeline_router, with_auth=False)

        resp = client.get("/api/pipeline/history/p1-aaa111")
        assert resp.status_code == 401
