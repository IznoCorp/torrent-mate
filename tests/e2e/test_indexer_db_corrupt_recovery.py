"""E2E test: corrupt DB mid-byte → quarantine → rebuild (DESIGN §15.5).

Scenario:
1. Create a real DB via open_db(event_bus=EventBus()), write a row.
2. Overwrite mid-bytes to corrupt the file.
3. Re-open with open_db(event_bus=EventBus()) → assert IndexerCorruptError raised AND
   ``<path>.corrupt-<ts>`` quarantine file exists.
4. Re-open with rebuild=True → assert open succeeds (fresh DB) AND the
   quarantine file is still present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import IndexerCorruptError, open_db


class TestCorruptDbRecovery:
    """Full E2E corrupt-recovery flow on a real filesystem."""

    def test_corrupt_quarantine_then_rebuild(self, tmp_path: Path) -> None:
        """Corrupt library.db is quarantined; rebuild=True opens a fresh database."""
        db_path = tmp_path / "library.db"

        # ---------------------------------------------------------------
        # Step 1: Create a real database and write a row
        # ---------------------------------------------------------------
        conn = open_db(db_path, event_bus=EventBus())
        conn.execute("CREATE TABLE IF NOT EXISTS test_sentinel (id INTEGER PRIMARY KEY, val TEXT)")
        conn.execute("INSERT INTO test_sentinel (val) VALUES ('hello')")
        conn.commit()
        conn.close()

        assert db_path.exists(), "DB file must exist after creation"

        # ---------------------------------------------------------------
        # Step 2: Corrupt the file by overwriting bytes in the middle
        # ---------------------------------------------------------------
        raw = bytearray(db_path.read_bytes())
        # SQLite page size is 4096 by default; corrupt page 2 onward
        corrupt_offset = 4096
        if len(raw) > corrupt_offset + 16:
            raw[corrupt_offset : corrupt_offset + 16] = b"\xde\xad\xbe\xef" * 4
        else:
            # File smaller than expected — overwrite from byte 100
            raw[100:116] = b"\xde\xad\xbe\xef" * 4
        db_path.write_bytes(bytes(raw))

        # ---------------------------------------------------------------
        # Step 3: Attempt open — expect IndexerCorruptError + quarantine
        # ---------------------------------------------------------------
        with pytest.raises(IndexerCorruptError) as exc_info:
            open_db(db_path, event_bus=EventBus())

        assert exc_info.value.db_path == db_path
        quarantine_path = exc_info.value.quarantine_path

        assert quarantine_path.exists(), "Quarantine file must exist after corruption"
        assert ".corrupt-" in quarantine_path.name, "Quarantine name must contain .corrupt-<ts>"

        # Original path must be gone (was renamed to quarantine)
        assert not db_path.exists(), "Original DB must no longer exist after quarantine"

        # ---------------------------------------------------------------
        # Step 4: rebuild=True → fresh DB opened, quarantine preserved
        # ---------------------------------------------------------------
        conn2 = open_db(db_path, rebuild=True, event_bus=EventBus())
        try:
            # A fresh DB has no tables yet — integrity check must pass
            row = conn2.execute("PRAGMA integrity_check").fetchone()
            assert row is not None
            assert row[0] == "ok", f"Fresh DB integrity check failed: {row[0]}"

            # The old test_sentinel table must not exist in the fresh DB
            tables = conn2.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='test_sentinel'"
            ).fetchall()
            assert tables == [], "Fresh DB must not contain old tables"
        finally:
            conn2.close()

        # Quarantine file must still be present after rebuild
        assert quarantine_path.exists(), "Quarantine file must be preserved after rebuild"

    def test_corrupt_refusal_without_rebuild(self, tmp_path: Path) -> None:
        """open_db refuses to create a fresh DB unless rebuild=True is passed."""
        db_path = tmp_path / "library.db"

        # Create then corrupt
        conn = open_db(db_path, event_bus=EventBus())
        conn.execute("CREATE TABLE x (id INTEGER)")
        conn.commit()
        conn.close()

        raw = bytearray(db_path.read_bytes())
        raw[100:200] = b"\xff" * 100
        db_path.write_bytes(bytes(raw))

        # First call without rebuild must raise
        with pytest.raises(IndexerCorruptError):
            open_db(db_path, event_bus=EventBus())

        # db_path was renamed — a second call on the same path creates a
        # new file (no corrupt file at that path now), so only assert the
        # first failure raised correctly.

    def test_quarantine_file_name_contains_unix_timestamp(self, tmp_path: Path) -> None:
        """Quarantine file name ends with a plausible unix timestamp."""
        import time

        db_path = tmp_path / "library.db"

        conn = open_db(db_path, event_bus=EventBus())
        conn.commit()
        conn.close()

        raw = bytearray(db_path.read_bytes())
        raw[100:200] = b"\xff" * 100
        db_path.write_bytes(bytes(raw))

        before = int(time.time()) - 2

        with pytest.raises(IndexerCorruptError) as exc_info:
            open_db(db_path, event_bus=EventBus())

        after = int(time.time()) + 2
        quarantine_name = exc_info.value.quarantine_path.name  # e.g. library.db.corrupt-1714300000
        ts_str = quarantine_name.rsplit("-", 1)[-1]
        ts = int(ts_str)
        assert before <= ts <= after, f"Timestamp {ts} not in expected range [{before}, {after}]"
