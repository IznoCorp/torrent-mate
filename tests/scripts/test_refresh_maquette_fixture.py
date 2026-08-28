"""Tests for the maquette fixture refresher.

The fixture is not decoration: a harness rule compares what a card PRINTS
against what ``acquire.db`` really holds, so the fixture is an assertion about
live data — and live data moves. One real search took the suite from 49/0 to
48/1 without a line of code changing. These tests hold the refresher that keeps
the two in step.

WHAT IT READS MOVED AT L09, and these moved with it. ``FOLLOWS`` was an array in
``legacy.js`` and the Acquisition deck read it there; the deck reads
``/api/acquisition/followed`` now and the fixture was deleted, so the seed the
mock layer answers with is what may drift from the operator's database.

The four shapes below the fold were the JavaScript walker's blind spots — a
nested object, an entry on one line, a field order, a missing trailing comma —
and a JSON parser reads all four. They are not deleted for being fixed: they are
replaced by the shapes that can still fool a reader of JSON, which is a
different list, and « no entries » is on both.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "refresh-maquette-fixture.py"

# The accented title and the French date the seed really carries, each written
# ONCE and referred to by name. They are data — a media title and a rendered
# date — and the tests below need them to prove the tool round-trips what it
# does not own; repeating the literal would put the same fact in the file nine
# times over.
ACCENTED_TITLE = "L'Odyssée"  # french-ok: a media title the seed carries
FRENCH_DATE = "4 août"  # french-ok: a rendered date the seed carries, untouched by the tool
PAUSED = 'En "pause"'  # french-ok: a series status, quoted to prove it round-trips
OTHER_FRENCH_DATE = "6 août"  # french-ok: the second entry's rendered date

# The seed's own names for the two facts the database owns, and one field the
# tool must never touch — kept in the fixture so « surgical » is measured rather
# than asserted about the two it does own.
FIXTURE = [
    {
        "title": "Ted Lasso",
        "showStatus": "Continuing",
        "since": FRENCH_DATE,
        "searches": 10,
        "kind": "show",
        "year": 2020,
    },
    {
        "title": ACCENTED_TITLE,
        "showStatus": None,
        "since": OTHER_FRENCH_DATE,
        "searches": 14,
        "kind": "movie",
        "year": 2026,
    },
]


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
    """Runs the refresher against the temporary seed and database."""
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            *flags,
            f"--database={tmp_path / 'acquire.db'}",
            f"--fixture={tmp_path / 'follows.json'}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def setup(tmp_path: Path, rows: list[tuple[str, int | None, str | None]]) -> Path:
    """Writes the seed and the database, and returns the seed's path."""
    seed = tmp_path / "follows.json"
    seed.write_text(json.dumps(FIXTURE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    make_database(tmp_path / "acquire.db", rows)
    return seed


def held(seed: Path) -> dict[str, dict]:
    """What the seed holds, by title."""
    return {entry["title"]: entry for entry in json.loads(seed.read_text(encoding="utf-8"))}


def test_check_reports_drift_and_fails(tmp_path: Path) -> None:
    """The count moved in the database: that is a drift, and it is named."""
    setup(tmp_path, [("Ted Lasso", 11, "Continuing"), (ACCENTED_TITLE, 14, None)])

    result = run(tmp_path, "--check")

    assert result.returncode == 1
    assert "Ted Lasso" in result.stdout
    assert "« 10 » vs 11" in result.stdout


def test_check_passes_when_they_agree(tmp_path: Path) -> None:
    """No drift, no noise."""
    setup(tmp_path, [("Ted Lasso", 10, "Continuing"), (ACCENTED_TITLE, 14, None)])

    result = run(tmp_path, "--check")

    assert result.returncode == 0
    assert "agrees" in result.stdout


def test_apply_rewrites_only_the_drifted_value(tmp_path: Path) -> None:
    """A refresh is surgical: what it does not own is left exactly as it was."""
    seed = setup(tmp_path, [("Ted Lasso", 11, "Continuing"), (ACCENTED_TITLE, 14, None)])

    result = run(tmp_path, "--apply")

    assert result.returncode == 0
    after = held(seed)
    assert after["Ted Lasso"]["searches"] == 11
    assert after[ACCENTED_TITLE]["searches"] == 14
    # The four fields the database says nothing about, read back one by one: a
    # rewriter that dropped them would still satisfy every assertion above.
    assert after["Ted Lasso"]["since"] == FRENCH_DATE
    assert after["Ted Lasso"]["kind"] == "show"
    assert after["Ted Lasso"]["year"] == 2020
    assert after[ACCENTED_TITLE]["showStatus"] is None


def test_apply_then_check_is_clean(tmp_path: Path) -> None:
    """The repair actually converges rather than reporting that it did."""
    setup(tmp_path, [("Ted Lasso", 11, "Continuing"), (ACCENTED_TITLE, 14, None)])

    assert run(tmp_path, "--apply").returncode == 0

    assert run(tmp_path, "--check").returncode == 0


def test_a_title_the_database_does_not_know_is_reported_not_dropped(tmp_path: Path) -> None:
    """A seed drifting out of the database's vocabulary must be visible."""
    setup(tmp_path, [("Ted Lasso", 10, "Continuing")])

    result = run(tmp_path, "--check")

    assert result.returncode == 1
    assert ACCENTED_TITLE in result.stdout
    assert "follows nothing by that name" in result.stdout


def test_an_unknown_title_survives_apply_and_still_fails(tmp_path: Path) -> None:
    """`--apply` cannot repair it, so it must not swallow it either."""
    seed = setup(tmp_path, [("Ted Lasso", 11, "Continuing")])

    result = run(tmp_path, "--apply")

    assert result.returncode == 1
    assert "left for a human" in result.stdout
    assert held(seed)[ACCENTED_TITLE]["searches"] == 14


def test_a_missing_database_verifies_nothing_and_says_so(tmp_path: Path) -> None:
    """An absent database is a check that could not run, not a pass."""
    (tmp_path / "follows.json").write_text(json.dumps(FIXTURE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = run(tmp_path, "--check")

    assert result.returncode == 0
    assert "nothing verified" in result.stdout


def test_series_status_follows_the_database(tmp_path: Path) -> None:
    """The series' own status drifts too, and moves with the count."""
    seed = setup(tmp_path, [("Ted Lasso", 10, "Ended"), (ACCENTED_TITLE, 14, None)])

    assert run(tmp_path, "--check").returncode == 1
    assert run(tmp_path, "--apply").returncode == 0

    assert held(seed)["Ted Lasso"]["showStatus"] == "Ended"


# --- The shapes a reader of JSON can still be fooled by ----------------------
#
# The walker's four blind spots were shapes of JavaScript, and a parser reads
# all four. These are what is left: a file that holds no array, one that holds
# an array of the wrong thing, one that does not parse at all, and an entry
# with no name to compare by. Each must REFUSE — « no entries » reported as
# « nothing drifted » is the false pass this whole file exists for, and it is
# reachable from every one of them.

NOT_AN_ARRAY = '{"follows": []}'
EMPTY_ARRAY = "[]"
NOT_OBJECTS = '["Ted Lasso", ACCENTED_TITLE]'
NO_TITLE = '[{"searches": 10, "showStatus": "Continuing"}]'
BROKEN = '[{"title": "Ted Lasso",]'


@pytest.mark.parametrize(
    ("shape", "why"),
    [
        (NOT_AN_ARRAY, "an object wrapping the array is not the array"),
        (EMPTY_ARRAY, "an empty array is not agreement"),
        (NOT_OBJECTS, "an array of titles carries no value to compare"),
        (NO_TITLE, "an entry with no title cannot be named"),
        (BROKEN, "a file that does not parse was not read"),
    ],
)
def test_a_seed_it_cannot_read_is_refused_never_agreed_with(tmp_path: Path, shape: str, why: str) -> None:
    """A shape the parser cannot read must never be reported as agreement."""
    (tmp_path / "follows.json").write_text(shape, encoding="utf-8")
    make_database(tmp_path / "acquire.db", [("Ted Lasso", 11, "Continuing")])

    result = run(tmp_path, "--check")

    assert result.returncode != 0, f"{why}: reported agreement — {result.stdout}"
    assert "agrees" not in result.stdout, why


def test_apply_refuses_the_same_shapes_rather_than_writing_over_them(tmp_path: Path) -> None:
    """`--apply` is the destructive half, so it refuses first and writes nothing."""
    seed = tmp_path / "follows.json"
    seed.write_text(NOT_AN_ARRAY, encoding="utf-8")
    make_database(tmp_path / "acquire.db", [("Ted Lasso", 11, "Continuing")])

    result = run(tmp_path, "--apply")

    assert result.returncode != 0
    assert seed.read_text(encoding="utf-8") == NOT_AN_ARRAY


def test_a_quote_in_the_series_status_stays_readable(tmp_path: Path) -> None:
    """Interpolating raw wrote broken JavaScript; JSON must round-trip it."""
    seed = setup(tmp_path, [("Ted Lasso", 10, PAUSED), (ACCENTED_TITLE, 14, None)])

    assert run(tmp_path, "--apply").returncode == 0

    assert held(seed)["Ted Lasso"]["showStatus"] == PAUSED


def test_the_seed_stays_the_shape_the_bundler_reads(tmp_path: Path) -> None:
    """It is imported by the mock layer, so it must remain an array of objects."""
    seed = setup(tmp_path, [("Ted Lasso", 11, "Continuing"), (ACCENTED_TITLE, 14, None)])

    assert run(tmp_path, "--apply").returncode == 0

    rewritten = json.loads(seed.read_text(encoding="utf-8"))
    assert isinstance(rewritten, list) and len(rewritten) == 2
    assert all(isinstance(entry, dict) for entry in rewritten)
    # And the accents are still accents rather than escapes: the seed is read
    # by a human as often as by a bundler.
    assert ACCENTED_TITLE in seed.read_text(encoding="utf-8")
