"""Tests for the structured JSONL log handler (#8): exc field + size rotation.

The handler is the writer half of the daemon log; ``kanban logs`` reads what it writes. These
tests cover the two #8 additions — an ``exc`` field carrying the traceback when a record is logged
with ``exc_info``, and a size-based rotation to ``<file>.1`` — plus the unchanged base record shape.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from kanbanmate.daemon.jsonl_log import MAX_LOG_BYTES, JSONLHandler


def _emit(handler: JSONLHandler, record: logging.LogRecord) -> None:
    """Drive one record through the handler."""
    handler.emit(record)


def _make_record(*, msg: str = "hi", exc_info: object = None) -> logging.LogRecord:
    """Build a log record, optionally carrying ``exc_info``."""
    record = logging.LogRecord(
        name="kanbanmate.daemon.loop",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=exc_info,  # type: ignore[arg-type]
    )
    return record


def test_emit_writes_base_fields(tmp_path: Path) -> None:
    """A plain record writes the ts/level/logger/msg fields and NO exc field."""
    log_path = tmp_path / "log" / "daemon.jsonl"
    handler = JSONLHandler(log_path)
    _emit(handler, _make_record(msg="hello"))

    line = log_path.read_text(encoding="utf-8").strip()
    data = json.loads(line)
    assert data["msg"] == "hello"
    assert data["level"] == "ERROR"
    assert data["logger"] == "kanbanmate.daemon.loop"
    assert "exc" not in data


def test_emit_includes_exc_field_when_exc_info_set(tmp_path: Path) -> None:
    """#8: a record logged with exc_info carries the formatted traceback in an ``exc`` field."""
    log_path = tmp_path / "log" / "daemon.jsonl"
    handler = JSONLHandler(log_path)
    try:
        raise ValueError("boom-cause")
    except ValueError:
        import sys

        record = _make_record(msg="tick raised; continuing", exc_info=sys.exc_info())
    _emit(handler, record)

    data = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert "exc" in data
    assert "ValueError" in data["exc"]
    assert "boom-cause" in data["exc"]
    assert "Traceback" in data["exc"]


def test_rotation_at_threshold(tmp_path: Path) -> None:
    """#8: once the log exceeds MAX_LOG_BYTES it rotates to ``<file>.1`` and starts fresh."""
    log_path = tmp_path / "log" / "daemon.jsonl"
    log_path.parent.mkdir(parents=True)
    # Pre-seed the file just past the threshold so the next emit triggers a rotation.
    log_path.write_text("x" * (MAX_LOG_BYTES + 1), encoding="utf-8")

    handler = JSONLHandler(log_path)
    _emit(handler, _make_record(msg="after-rotate"))

    rolled = log_path.with_suffix(log_path.suffix + ".1")
    assert rolled.exists(), "the oversized log should have been rotated to <file>.1"
    # The fresh file holds only the new line (the bulk moved to the rolled file).
    fresh = log_path.read_text(encoding="utf-8").strip()
    assert json.loads(fresh)["msg"] == "after-rotate"
    assert len(log_path.read_text(encoding="utf-8")) < MAX_LOG_BYTES


def test_no_rotation_below_threshold(tmp_path: Path) -> None:
    """A small log is NOT rotated — no ``<file>.1`` is created."""
    log_path = tmp_path / "log" / "daemon.jsonl"
    handler = JSONLHandler(log_path)
    _emit(handler, _make_record(msg="small"))

    assert not log_path.with_suffix(log_path.suffix + ".1").exists()
