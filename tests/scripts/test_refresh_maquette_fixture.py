"""Tests for the maquette fixture refresher.

The fixture is not decoration: a harness rule compares what a card PRINTS
against what ``acquire.db`` really holds, so the fixture is an assertion about
live data — and live data moves. One real search took the suite from 49/0 to
48/1 without a line of code changing. These tests hold the refresher that keeps
the two in step.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "refresh-maquette-fixture.py"

FIXTURE = """\
  const FOLLOWS = [
    {
      t: "Ted Lasso",
      serie: "Continuing",
      since: "4 août",
      searches: 10,
      k: "show",
      y: 2020,
    },
    {
      t: "L'Odyssée",
      serie: null,
      since: "6 août",
      searches: 14,
      k: "movie",
      y: 2026,
    },
  ];
"""


def make_database(path: Path, rows: list[tuple[str, int | None, str | None]]) -> None:
    """Builds a minimal ``acquire.db`` holding ``(title, attempts, status)``."""
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE followed_series (title TEXT, media_ref_json TEXT, series_status TEXT)")
    connection.execute("CREATE TABLE wanted (media_ref_json TEXT, attempts INTEGER)")
    for title, attempts, status in rows:
        ref = f"ref:{title}"
        connection.execute("INSERT INTO followed_series VALUES (?, ?, ?)", (title, ref, status))
        if attempts is not None:
            connection.execute("INSERT INTO wanted VALUES (?, ?)", (ref, attempts))
    connection.commit()
    connection.close()


def run(tmp_path: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    """Runs the refresher against the temporary fixture and database."""
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            *flags,
            f"--database={tmp_path / 'acquire.db'}",
            f"--fixture={tmp_path / 'legacy.js'}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def setup(tmp_path: Path, rows: list[tuple[str, int | None, str | None]]) -> Path:
    """Writes the fixture and the database, and returns the fixture path."""
    fixture = tmp_path / "legacy.js"
    fixture.write_text(FIXTURE, encoding="utf-8")
    make_database(tmp_path / "acquire.db", rows)
    return fixture


def test_check_reports_drift_and_fails(tmp_path: Path) -> None:
    """The count moved in the database: that is a drift, and it is named."""
    setup(tmp_path, [("Ted Lasso", 11, "Continuing"), ("L'Odyssée", 14, None)])

    result = run(tmp_path, "--check")

    assert result.returncode == 1
    assert "Ted Lasso" in result.stdout
    assert "fixture 10 vs database 11" in result.stdout


def test_check_passes_when_they_agree(tmp_path: Path) -> None:
    """No drift, no noise."""
    setup(tmp_path, [("Ted Lasso", 10, "Continuing"), ("L'Odyssée", 14, None)])

    result = run(tmp_path, "--check")

    assert result.returncode == 0
    assert "agrees" in result.stdout


def test_apply_rewrites_only_the_drifted_value(tmp_path: Path) -> None:
    """A refresh is surgical: the entry that agreed is left byte-for-byte."""
    fixture = setup(tmp_path, [("Ted Lasso", 11, "Continuing"), ("L'Odyssée", 14, None)])

    result = run(tmp_path, "--apply")

    assert result.returncode == 0
    body = fixture.read_text(encoding="utf-8")
    assert "searches: 11," in body
    assert "searches: 14," in body
    assert 'since: "4 août",' in body
    assert "serie: null," in body


def test_apply_then_check_is_clean(tmp_path: Path) -> None:
    """The repair actually converges rather than reporting that it did."""
    setup(tmp_path, [("Ted Lasso", 11, "Continuing"), ("L'Odyssée", 14, None)])

    assert run(tmp_path, "--apply").returncode == 0

    assert run(tmp_path, "--check").returncode == 0


def test_a_title_the_database_does_not_know_is_reported_not_dropped(tmp_path: Path) -> None:
    """A fixture drifting out of the database's vocabulary must be visible."""
    setup(tmp_path, [("Ted Lasso", 10, "Continuing")])

    result = run(tmp_path, "--check")

    assert result.returncode == 1
    assert "L'Odyssée" in result.stdout
    assert "absent from acquire.db" in result.stdout


def test_a_missing_database_verifies_nothing_and_says_so(tmp_path: Path) -> None:
    """An absent database is a check that could not run, not a pass."""
    (tmp_path / "legacy.js").write_text(FIXTURE, encoding="utf-8")

    result = run(tmp_path, "--check")

    assert result.returncode == 0
    assert "nothing verified" in result.stdout


def test_series_status_follows_the_database(tmp_path: Path) -> None:
    """The series' own status drifts too, and moves with the count."""
    fixture = setup(tmp_path, [("Ted Lasso", 10, "Ended"), ("L'Odyssée", 14, None)])

    assert run(tmp_path, "--check").returncode == 1
    assert run(tmp_path, "--apply").returncode == 0

    assert 'serie: "Ended",' in fixture.read_text(encoding="utf-8")
