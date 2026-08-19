"""Unit tests for create-follow priming (acq-states phase 6.1 — failing-first).

Covers the five test groups of the frozen contract:

1. ``test_create_follow_enqueues_a_priming_run`` — POST /followed → 201 AND a
   pipeline_run row ``command='prime'`` created AND the spawn hook invoked.
   Reproduces the founding incident: a grab at 09:19:09 over an empty wanted
   queue returned rc=0 — a success report for an action that did nothing.

2. ``test_priming_failure_leaves_unverified_not_up_to_date`` — spawn raises →
   201 still, item.status == unverified (never up_to_date), warning logged.

3. ``test_priming_is_idempotent`` — a second POST while a prime run is running
   for the same followed_id does not spawn a second run.

4. ``test_running_prime_reads_verifying`` — GET /followed shows the
   override while the run row is open; closed run → derived status again.

INTENTIONALLY FAILING — the prime command does not exist yet; ``create_follow``
does not spawn anything; there is no ``verifying`` override. These
assertions pin the contract of phases 6.2/6.3 and will pass once those phases
are implemented.

**Mocking constraint**: this file does NOT mock ``subprocess.Popen`` globally
because the migration path in ``_fs_probe`` also uses it (via ``subprocess.run``)
and a global mock would break the acquire-store bootstrap. The priming gap is
verified through DB-side-effect assertions + the response ``status`` field.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.web.app import create_app
from personalscraper.web.auth.tokens import create_session_token
from personalscraper.web.routes import acquisition_triggers

# ---------------------------------------------------------------------------
# DDL (matching the real schemas — same as test_acquisition_write.py)
# ---------------------------------------------------------------------------

_ACQUIRE_DDL = """
CREATE TABLE IF NOT EXISTS followed_series (
    id                   INTEGER PRIMARY KEY,
    media_ref_json       TEXT    NOT NULL,
    title                TEXT    NOT NULL,
    active               INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    quality_profile_json TEXT,
    cadence_json         TEXT,
    added_at             INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS wanted (
    id              INTEGER PRIMARY KEY,
    followed_id     INTEGER REFERENCES followed_series(id) ON DELETE SET NULL,
    media_ref_json  TEXT    NOT NULL,
    kind            TEXT    NOT NULL CHECK (kind IN ('movie', 'episode')),
    season          INTEGER,
    episode         INTEGER,
    status          TEXT    NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'searching', 'grabbed', 'done', 'abandoned')),
    criteria_json   TEXT,
    enqueued_at     INTEGER NOT NULL,
    last_search_at  INTEGER,
    attempts        INTEGER NOT NULL DEFAULT 0,
    grabbed_hash    TEXT
);
"""

_PIPELINE_RUN_DDL = """
CREATE TABLE pipeline_run (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_uid      TEXT    UNIQUE NOT NULL,
    trigger      TEXT    NOT NULL,
    dry_run      INTEGER NOT NULL DEFAULT 0,
    started_at   REAL    NOT NULL,
    ended_at     REAL,
    outcome      TEXT,
    steps_json   TEXT,
    error        TEXT,
    pid          INTEGER,
    kind         TEXT    NOT NULL DEFAULT 'pipeline',
    command      TEXT    NULL,
    options_json TEXT    NULL,
    output_tail  TEXT    NULL
);

CREATE INDEX idx_pipeline_run_started ON pipeline_run(started_at);
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_acquire_db(db_path: Path) -> None:
    """Create a temp acquire.db and apply the base schema.

    Migrations (``apply_migrations`` in the store's ``_ensure_open`` path) add
    later columns (kind, poster_url, etc.) on top.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    apply_pragmas(conn)
    conn.executescript(_ACQUIRE_DDL)
    conn.commit()
    conn.close()


def _seed_followed(
    conn: sqlite3.Connection,
    idx: int,
    title: str,
    active: bool = True,
    tvdb_id: int | None = None,
) -> int:
    """Insert a followed_series row and return its id."""
    now = int(time.time())
    tid = tvdb_id if tvdb_id is not None else 360000 + idx
    cur = conn.execute(
        "INSERT INTO followed_series (media_ref_json, title, active, added_at) VALUES (?, ?, ?, ?)",
        (json.dumps({"tvdb_id": tid, "tmdb_id": 1000 + idx}), title, 1 if active else 0, now),
    )
    return cur.lastrowid


def _make_auth_cookie(username: str = "izno", secret: str = "testsecret") -> dict[str, str]:
    """Create a ``tm_session`` cookie dict for a TestClient request."""
    token = create_session_token(username, secret, 24)
    return {"tm_session": token}


def _auth_cookies() -> dict[str, str]:
    """Return auth cookies for the TestClient."""
    return _make_auth_cookie()


def _xrw_headers() -> dict[str, str]:
    """Return headers with the required ``X-Requested-With`` value."""
    return {"X-Requested-With": "TorrentMate"}


def _count_prime_runs(indexer_path: Path, followed_id: int) -> int:
    """Count prime runs for a given follow in the pipeline_run table."""
    conn = sqlite3.connect(str(indexer_path))
    apply_pragmas(conn)
    row = conn.execute(
        "SELECT COUNT(*) FROM pipeline_run WHERE command = 'prime' AND options_json = ?",
        (json.dumps({"followed_id": followed_id}),),
    ).fetchone()
    conn.close()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# Client fixture (mirrors test_acquisition_write.py)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def spawned_primes(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Record priming spawns instead of detaching a REAL acquisition runner.

    ``_spawn_prime_runner`` is the spawn hook the contract names. Patching it
    is mandatory, not cosmetic: the real hook detaches
    ``python -m personalscraper.web.acquisition.runner``, which loads the
    OPERATOR's config (not the synthetic test one) and chains detect → search →
    grab against the production DBs and the trackers.

    The stub returns this process' pid so the reserved run row looks alive to
    the idempotence guard — exactly like a freshly spawned runner.

    Returns:
        The list of ``followed_id`` values the handler asked to prime.
    """
    calls: list[int] = []

    def _fake_spawn(run_uid: str, followed_id: int) -> int:
        calls.append(followed_id)
        return os.getpid()

    monkeypatch.setattr(acquisition_triggers, "_spawn_prime_runner", _fake_spawn)
    return calls


@pytest.fixture
def client(test_config: Any, tmp_path: Path) -> TestClient:
    """Build a TestClient with temp acquire.db + library.db.

    The synthetic Config is pointed at temp DB paths so the store's
    ``build_acquire_store`` opens real on-disk files.
    """
    config = test_config

    # Point acquire.db at a temp file.
    acquire_path = tmp_path / "acquire.db"
    config.acquire.db_path = acquire_path
    _create_acquire_db(acquire_path)

    # Point library.db at a temp file (needed by app boot + priming writes).
    indexer_path = tmp_path / "library.db"
    config.indexer.db_path = indexer_path
    conn = sqlite3.connect(str(indexer_path))
    apply_pragmas(conn)
    conn.executescript(_PIPELINE_RUN_DDL)
    conn.commit()
    conn.close()

    data_dir = config.paths.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    app = create_app(config, settings)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test cases — POST /api/acquisition/followed priming
# ---------------------------------------------------------------------------


class TestCreateFollowPriming:
    """POST /api/acquisition/followed — enqueues a priming run on creation."""

    def test_create_follow_enqueues_a_priming_run(
        self, client: TestClient, tmp_path: Path, spawned_primes: list[int]
    ) -> None:
        """Creating a follow must prime it — catalog, queue, first search.

        Reproduces the founding incident: Furious was added at 09:18:50 while
        the detect cron had last run at 03:00:02. With no priming, the
        operator's « Rechercher » at 09:19:09 ran a grab over an empty wanted
        queue and returned rc=0 — a success report for an action that did
        nothing.
        """
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 789, "title": "Furious"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )

        assert resp.status_code == 201, resp.text
        data = resp.json()
        follow_id: int = data["id"]
        assert follow_id > 0

        # A prime run row must exist in pipeline_run (command='prime').
        indexer_path = tmp_path / "library.db"
        prime_count = _count_prime_runs(indexer_path, follow_id)
        assert prime_count == 1, (
            f"Expected 1 prime run row, found {prime_count}. create_follow did not enqueue a priming run."
        )

        # And the spawn hook ran for THIS follow — the row alone would only
        # prove an enqueue, not that the amorce was launched.
        assert spawned_primes == [follow_id], f"Expected a spawn for follow {follow_id}, got {spawned_primes}"

        # The immediate response shows the truth: verification is running.
        assert data["status"] == "verifying", f"Expected verifying on a freshly primed follow, got {data['status']!r}"

    def test_priming_failure_leaves_unverified_not_up_to_date(
        self,
        client: TestClient,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failed priming run must never leave the card looking healthy.

        When the spawn fails (OSError), the follow is still created (fail-soft:
        a spawn failure never blocks the 201), but the card reads
        ``unverified`` — never ``up_to_date``, and the failure IS logged.
        """
        caplog.set_level(logging.WARNING)

        def _spawn_boom(run_uid: str, followed_id: int) -> int:
            """Simulate a spawn that cannot fork (the fail-soft path)."""
            raise OSError("cannot spawn the priming runner")

        monkeypatch.setattr(acquisition_triggers, "_spawn_prime_runner", _spawn_boom)

        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 790, "title": "Unlucky Series"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )

        assert resp.status_code == 201, resp.text
        data = resp.json()

        # The follow was created (fail-soft: spawn failure never blocks 201).
        assert data["id"] > 0

        # Never up_to_date — the card is honest about not knowing.
        assert data["status"] == "unverified", f"A failed prime must read unverified, not {data['status']!r}"

        # A warning about the spawn failure must appear in the logs — a failed
        # amorce is loud (NE-DOIT-PAS-5), never a silent nothing.
        spawn_warnings = [
            r for r in caplog.records if r.levelno >= logging.WARNING and "spawn" in r.getMessage().lower()
        ]
        assert len(spawn_warnings) > 0, "A spawn failure must be logged at WARNING level or above."

    def test_priming_is_idempotent(self, client: TestClient, tmp_path: Path) -> None:
        """A concurrent prime on the same follow must not double-spawn.

        Reactivation (the existing inactive→active path) ALSO primes (§6
        contract). But if a prime run for this followed_id is already running
        (pipeline_run kind='maintenance' command='prime' ended_at IS NULL),
        the handler must NOT insert a second run — the only allowed refusal
        is the duplicate of the same action.

        The in-flight run is the one the first POST left open: its runner is
        stubbed to this (live) pid and never finalizes the row, which is
        exactly the state a real priming runner holds while it works.
        """
        # Step 1: Create a follow.
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 791, "title": "Idempotent Test"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        follow_id: int = resp.json()["id"]

        # Step 2: Deactivate the follow so reactivation is possible.
        conn = sqlite3.connect(str(tmp_path / "acquire.db"))
        apply_pragmas(conn)
        conn.execute("UPDATE followed_series SET active = 0 WHERE id = ?", (follow_id,))
        conn.commit()
        conn.close()

        # Step 3: the priming run of step 1 is still in flight (open row).
        indexer_path = tmp_path / "library.db"
        assert _count_prime_runs(indexer_path, follow_id) == 1, "Step 1 must have left one open priming run"

        # Step 4: Reactivate — must NOT insert a second prime run.
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 791, "title": "Idempotent Test"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )

        assert resp.status_code == 201, resp.text

        # The reactivation must see the running prime and NOT spawn a second.
        # FAILS TODAY: create_follow doesn't check for running prime runs,
        # so reactivation doesn't prevent a duplicate (and doesn't spawn any
        # prime at all — the gap is that idempotence is not enforced).
        prime_count = _count_prime_runs(indexer_path, follow_id)
        assert prime_count == 1, (
            f"Expected 1 prime run (idempotent), found {prime_count}. "
            "The existing prime run must prevent a second spawn."
        )

        # And the response must reflect the running prime.
        # FAILS TODAY: the status is derived (unverified), not overridden.
        status: str = resp.json()["status"]
        assert status == "verifying", f"Reactivation with a running prime must read verifying, got {status!r}"


# ---------------------------------------------------------------------------
# Test cases — GET /api/acquisition/followed  (verifying override)
# ---------------------------------------------------------------------------


class TestVerifying:
    """GET /api/acquisition/followed — ``verifying`` override."""

    def test_running_prime_reads_verifying(self, client: TestClient, tmp_path: Path) -> None:
        """GET /followed shows verifying while a prime run is open.

        Seed a follow + a running ``pipeline_run`` row (``command='prime'``,
        ``ended_at IS NULL``), then assert the card reads
        ``verifying``. Close the run → the derived status takes
        over again (``unverified`` for a follow with no catalog yet).
        """
        now = time.time()

        # Seed a follow.
        conn = sqlite3.connect(str(tmp_path / "acquire.db"))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Priming Now", active=True)
        conn.commit()
        conn.close()

        # Seed a running prime run for this follow.
        conn = sqlite3.connect(str(tmp_path / "library.db"))
        apply_pragmas(conn)
        conn.execute(
            "INSERT INTO pipeline_run "
            "(run_uid, trigger, dry_run, started_at, ended_at, pid, kind, command, options_json) "
            "VALUES (?, 'web', 0, ?, NULL, ?, 'maintenance', 'prime', ?)",
            (
                "prime-running-v1",
                now,
                os.getpid(),
                json.dumps({"followed_id": fid}),
            ),
        )
        conn.commit()
        conn.close()

        # GET /followed — the running prime must override the card status.
        resp = client.get(
            "/api/acquisition/followed",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200, resp.text
        items: list[dict[str, Any]] = resp.json()["items"]
        assert len(items) == 1, f"Expected 1 item, got {len(items)}"
        assert items[0]["id"] == fid
        assert items[0]["status"] == "verifying", f"Running prime must read verifying, got {items[0]['status']!r}"

        # Close the run → the derived status takes over again.
        conn = sqlite3.connect(str(tmp_path / "library.db"))
        apply_pragmas(conn)
        conn.execute(
            "UPDATE pipeline_run SET ended_at = ?, outcome = 'success' WHERE run_uid = ?",
            (time.time(), "prime-running-v1"),
        )
        conn.commit()
        conn.close()

        resp = client.get(
            "/api/acquisition/followed",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert items[0]["status"] != "verifying", (
            f"Closed prime run must no longer override, got {items[0]['status']!r}"
        )
        # With no catalog yet (aired_count=None), the derived status is unverified.
        assert items[0]["status"] == "unverified", (
            f"Without a catalog, closed prime → unverified, got {items[0]['status']!r}"
        )

    def test_dead_pid_prime_run_does_not_pin_verifying(self, client: TestClient, tmp_path: Path) -> None:
        """Regression (PR #320 review, F-M5): a crashed prime must not pin the card.

        The batched priming query filtered on ``ended_at IS NULL`` alone, which
        is NOT liveness: a runner that crashed (or was SIGKILLed) never gets to
        write ``ended_at``, so its row stays open forever. The card then read
        « vérification en cours » indefinitely while the 409 guard — which DOES
        check the pid — happily let a new run through: two answers to the same
        question. The reader now applies the same ``pid_is_alive`` authority.
        """
        now = time.time()

        conn = sqlite3.connect(str(tmp_path / "acquire.db"))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Crashed Prime", active=True)
        conn.commit()
        conn.close()

        # An open prime row whose pid is dead. Reserve a pid that cannot exist:
        # spawn a child, reap it, and reuse its (now free) pid.
        dead_pid = subprocess.Popen([sys.executable, "-c", ""]).pid
        os.waitpid(dead_pid, 0)

        conn = sqlite3.connect(str(tmp_path / "library.db"))
        apply_pragmas(conn)
        conn.execute(
            "INSERT INTO pipeline_run "
            "(run_uid, trigger, dry_run, started_at, ended_at, pid, kind, command, options_json) "
            "VALUES (?, 'web', 0, ?, NULL, ?, 'maintenance', 'prime', ?)",
            ("prime-crashed-v1", now, dead_pid, json.dumps({"followed_id": fid})),
        )
        conn.commit()
        conn.close()

        resp = client.get(
            "/api/acquisition/followed",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200, resp.text
        items: list[dict[str, Any]] = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["status"] != "verifying", (
            f"A dead-pid prime row is a stale row, not a live verification; got {items[0]['status']!r}"
        )
        assert items[0]["status"] == "unverified", f"The derived status must take over, got {items[0]['status']!r}"

    def test_pid_null_prime_run_does_not_pin_verifying(self, client: TestClient, tmp_path: Path) -> None:
        """A prime row whose runner never claimed a pid is stale, not live."""
        conn = sqlite3.connect(str(tmp_path / "acquire.db"))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Never Claimed", active=True)
        conn.commit()
        conn.close()

        conn = sqlite3.connect(str(tmp_path / "library.db"))
        apply_pragmas(conn)
        conn.execute(
            "INSERT INTO pipeline_run "
            "(run_uid, trigger, dry_run, started_at, ended_at, pid, kind, command, options_json) "
            "VALUES (?, 'web', 0, ?, NULL, NULL, 'maintenance', 'prime', ?)",
            ("prime-nopid-v1", time.time(), json.dumps({"followed_id": fid})),
        )
        conn.commit()
        conn.close()

        resp = client.get(
            "/api/acquisition/followed",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200, resp.text
        items: list[dict[str, Any]] = resp.json()["items"]
        assert items[0]["status"] == "unverified", (
            f"A pid-less prime row must not override the derived status, got {items[0]['status']!r}"
        )
