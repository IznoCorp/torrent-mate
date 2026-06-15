"""Tests for :mod:`kanbanmate.cli.logs` — the structured-JSONL ``kanban logs [issue]`` reader.

The reader points at a configurable ``root``, so each test writes a ``<root>/log/daemon.jsonl`` under
``tmp_path`` and asserts the parsed/filtered/tail-truncated entries. Coverage: no-log, unfiltered
read, issue filtering, malformed-line tolerance, tail truncation, and per-ticket log path surfacing.
"""

from __future__ import annotations

import json
from pathlib import Path

from kanbanmate.cli.logs import DAEMON_LOG_FILENAME, LOG_DIRNAME, logs, resolve_logs


def _write_log(root: Path, lines: list[str]) -> Path:
    """Write raw ``lines`` to ``<root>/log/daemon.jsonl`` and return the path."""
    log_dir = root / LOG_DIRNAME
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / DAEMON_LOG_FILENAME
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_resolve_logs_absent_file(tmp_path: Path) -> None:
    """An absent daemon log yields an empty view flagged not-present."""
    view = resolve_logs(tmp_path)

    assert view.entries == []
    assert view.daemon_log_exists is False
    assert view.daemon_log == tmp_path / LOG_DIRNAME / DAEMON_LOG_FILENAME


def test_resolve_logs_reads_all_entries(tmp_path: Path) -> None:
    """Without an issue filter, every well-formed JSONL record is returned in file order."""
    _write_log(
        tmp_path,
        [
            json.dumps({"issue": 1, "msg": "a"}),
            json.dumps({"issue": 2, "msg": "b"}),
        ],
    )

    view = resolve_logs(tmp_path)

    assert view.daemon_log_exists is True
    assert [e["msg"] for e in view.entries] == ["a", "b"]


def test_resolve_logs_filters_by_issue(tmp_path: Path) -> None:
    """An issue filter keeps only matching records and resolves the per-ticket log path."""
    _write_log(
        tmp_path,
        [
            json.dumps({"issue": 1, "msg": "for-1"}),
            json.dumps({"issue": 2, "msg": "for-2"}),
            json.dumps({"issue": 1, "msg": "also-1"}),
        ],
    )
    # Materialise the per-ticket log so its presence is surfaced.
    (tmp_path / LOG_DIRNAME / "ticket-1.log").write_text("session output", encoding="utf-8")

    view = resolve_logs(tmp_path, issue=1)

    assert [e["msg"] for e in view.entries] == ["for-1", "also-1"]
    assert view.ticket_log == tmp_path / LOG_DIRNAME / "ticket-1.log"
    assert view.ticket_log_exists is True


def test_resolve_logs_skips_malformed_lines(tmp_path: Path) -> None:
    """A torn/non-JSON line is skipped rather than aborting the read."""
    _write_log(
        tmp_path,
        [
            json.dumps({"issue": 1, "msg": "good"}),
            "{not valid json",
            "",
            json.dumps({"issue": 1, "msg": "also-good"}),
        ],
    )

    view = resolve_logs(tmp_path)

    assert [e["msg"] for e in view.entries] == ["good", "also-good"]


def test_resolve_logs_tail_truncates(tmp_path: Path) -> None:
    """Only the most recent ``tail`` entries are returned."""
    _write_log(tmp_path, [json.dumps({"issue": 1, "n": n}) for n in range(10)])

    view = resolve_logs(tmp_path, tail=3)

    assert [e["n"] for e in view.entries] == [7, 8, 9]


def test_logs_renders_entries_and_paths(tmp_path: Path) -> None:
    """``logs`` renders filtered entries as compact JSON and surfaces the ticket-log path."""
    _write_log(tmp_path, [json.dumps({"issue": 5, "msg": "hello"})])

    rendered = logs(tmp_path, issue=5)

    assert '"msg": "hello"' in rendered
    assert "ticket-5.log" in rendered


def test_logs_no_entries_message(tmp_path: Path) -> None:
    """An empty / absent log renders an explicit no-entries message."""
    rendered = logs(tmp_path)

    assert "(no log entries)" in rendered


def test_logs_renders_exc_field_on_own_lines(tmp_path: Path) -> None:
    """#8: an entry with an ``exc`` field renders the traceback on indented lines, not as JSON soup.

    The exc field carries a multi-line traceback; embedding it in the compact JSON line would
    escape the newlines into an unreadable ``\\n`` string. The renderer pulls it out so the
    operator sees WHY a tick failed.
    """
    exc_text = "Traceback (most recent call last):\n  ...\nValueError: boom-cause"
    _write_log(
        tmp_path,
        [json.dumps({"msg": "tick raised; continuing", "level": "ERROR", "exc": exc_text})],
    )

    rendered = logs(tmp_path)

    # The entry's base fields render compactly, WITHOUT the exc field inline.
    assert '"msg": "tick raised; continuing"' in rendered
    assert '"exc"' not in rendered  # exc is pulled OUT of the JSON line
    # The traceback is rendered readably on its own indented lines.
    assert "ValueError: boom-cause" in rendered
    assert "    Traceback (most recent call last):" in rendered


def test_resolve_logs_filter_by_issue_and_tail_combined(tmp_path: Path) -> None:
    """#11: ``kanban logs <issue> --tail N`` filters by issue THEN keeps the most recent N.

    The two operations compose: only the matching-issue records are kept, and of those only the
    last ``tail`` are returned (the daemon JSONL is the polling-model replacement for the PoC
    ``dispatch.jsonl``; the filter+tail is the operator's window into it).
    """
    lines = []
    for n in range(6):
        lines.append(json.dumps({"issue": 1, "n": n}))  # 6 records for issue 1
        lines.append(json.dumps({"issue": 2, "n": n}))  # interleaved noise for issue 2
    _write_log(tmp_path, lines)

    view = resolve_logs(tmp_path, issue=1, tail=2)

    # Only issue-1 records, and only the last 2 of them.
    assert all(e["issue"] == 1 for e in view.entries)
    assert [e["n"] for e in view.entries] == [4, 5]


def test_resolve_logs_surfaces_ticket_log_path_not_body(tmp_path: Path) -> None:
    """#11: the per-ticket session log is surfaced by PATH (operator tails it), its body is NOT dumped.

    The polling model intentionally avoids inlining an unbounded session log — ``kanban logs``
    reports the path + presence, leaving the body for the operator to ``tail`` themselves.
    """
    _write_log(tmp_path, [json.dumps({"issue": 5, "msg": "tick"})])
    ticket_log = tmp_path / LOG_DIRNAME / "ticket-5.log"
    ticket_log.write_text("UNBOUNDED SESSION TRANSCRIPT BODY", encoding="utf-8")

    view = resolve_logs(tmp_path, issue=5)
    rendered = logs(tmp_path, issue=5)

    # The path + presence are surfaced...
    assert view.ticket_log == ticket_log
    assert view.ticket_log_exists is True
    assert "ticket-5.log" in rendered
    # ...but the session-log BODY is never dumped into the output.
    assert "UNBOUNDED SESSION TRANSCRIPT BODY" not in rendered
