#!/usr/bin/env python3
"""Keeps the maquette's follow fixture in step with `acquire.db`.

WHY THIS EXISTS. A harness rule compares what a card PRINTS against what the
database really holds — « the numbers come from acquire.db, not from the
mock-up » — because a card printing a number the engine never held would
otherwise pass. That rule is right, and it means the fixture is not decoration:
it is an assertion about live data, and live data moves. One real search ran,
Ted Lasso went from 10 attempts to 11, and a suite that had been 49/0 went red
without a line of code changing.

The answer is not to loosen the rule — a rule that tolerates any number stops
measuring. It is to let the fixture be REGENERATED from the database it claims
to mirror.

WHAT MOVES AND WHAT DOES NOT. Only the facts the database keeps changing are
rewritten: the attempt count, and the series' own status. `since` derives from
`added_at`, which never changes once a follow exists, and the titles are the
join key — neither is touched. Nothing here invents an entry: a fixture title
absent from the database is REPORTED, never silently dropped, because a fixture
drifting out of the database's vocabulary is exactly the kind of quiet rot this
script exists to surface.

Usage:
    python3 scripts/refresh-maquette-fixture.py --check   # report drift, exit 1
    python3 scripts/refresh-maquette-fixture.py --apply   # rewrite the fixture
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "frontend" / "maquette" / "design" / "src" / "engine" / "legacy.js"
ACQUIRE = ROOT / ".data" / "acquire.db"

# One entry of the FOLLOWS array, from its title to the end of its object.
# The FOLLOWS array, and nothing else in the file.
FOLLOWS = re.compile(r"\bconst FOLLOWS\s*=\s*\[", re.S)
TITLE = re.compile(r'(?<![\w$])t:\s*"(?P<title>(?:[^"\\]|\\.)*)"')


def entries(text):
    """Yields (start, end, title) for each object of the FOLLOWS array.

    A REGEX CANNOT DO THIS, and three shapes proved it. `.*?` stopping at the
    first `\n },` cut an entry short at a NESTED object, so its `searches:` was
    never reached and the drift it hid was reported as agreement. An entry
    without a trailing comma — the last one — let the body run out of the array
    entirely, so `--check` blamed the wrong title and `--apply` rewrote a value
    belonging to a DIFFERENT array. And an entry written on one line, or with
    `searches:` before `t:`, matched nothing at all and was dropped in silence,
    which the module docstring promises never happens.

    Braces are counted instead, and only inside FOLLOWS.

    Args:
        text: The fixture source.

    Yields:
        (start, end, title) for every top-level object of the array. `end` is
        exclusive and points just past the closing brace.

    Raises:
        SystemExit: When the array cannot be found — the caller must not treat
            "no entries" as "nothing drifted".
    """
    opening = FOLLOWS.search(text)
    if opening is None:
        raise SystemExit(
            "refresh-maquette-fixture: no `const FOLLOWS = [` in the fixture — "
            "refusing to report agreement about an array it could not find.")
    index = opening.end()
    depth = 0
    start = None
    while index < len(text):
        char = text[index]
        if char == "]" and depth == 0:
            return
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                chunk = text[start:index + 1]
                found = TITLE.search(chunk)
                if found:
                    yield start, index + 1, found.group("title")
                start = None
        elif char in "\"'":
            # Skip the string whole: a brace or a `t:` inside a title must not
            # move the walk.
            quote, index = char, index + 1
            while index < len(text) and text[index] != quote:
                index += 2 if text[index] == "\\" else 1
        index += 1


def live_facts(database: pathlib.Path) -> dict[str, dict[str, object]]:
    """Reads, per followed title, the facts the database really holds.

    Args:
        database: Path to ``acquire.db``.

    Returns:
        title → {"searches": int, "series": str | None}. Empty when the
        database is absent.
    """
    if not database.is_file():
        return {}
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    facts: dict[str, dict[str, object]] = {}
    try:
        rows = connection.execute(
            "SELECT title, media_ref_json, series_status FROM followed_series"
        ).fetchall()
        for row in rows:
            attempts = connection.execute(
                "SELECT sum(attempts) AS att FROM wanted WHERE media_ref_json = ?",
                (row["media_ref_json"],),
            ).fetchone()
            facts[row["title"]] = {
                "searches": attempts["att"] or 0,
                "series": row["series_status"],
            }
    finally:
        connection.close()
    return facts


SEARCHES = re.compile(r"(?<![\w$])searches:\s*(?P<n>\d+)")
SERIE = re.compile(r'(?<![\w$])serie:\s*(?P<v>null|"(?:[^"\\]|\\.)*")')


def as_js_string(value: str) -> str:
    """Renders a database value as a JavaScript double-quoted string.

    Interpolating it raw wrote broken JavaScript the moment a series status
    held a quote — `serie: "En "pause""` — and a backslash would have been
    eaten as an `re.sub` group reference.

    Args:
        value: The value as the database holds it.

    Returns:
        The value, quoted and escaped.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def drift(text: str, facts: dict[str, dict[str, object]]) -> list[tuple[str, str, str]]:
    """Lists every fixture value the database disagrees with.

    Args:
        text: The fixture source.
        facts: The live facts, keyed by title.

    Returns:
        One (title, field, message) per disagreement.
    """
    found: list[tuple[str, str, str]] = []
    for begin, stop, title in entries(text):
        body = text[begin:stop]
        # Only entries carrying a `searches:` are follow entries; the same shape
        # holds cards and releases elsewhere in the file.
        searches = SEARCHES.search(body)
        if not searches:
            continue
        real = facts.get(title)
        if real is None:
            found.append((title, "title", "absent from acquire.db"))
            continue
        if int(searches.group("n")) != int(real["searches"]):
            found.append(
                (title, "searches",
                 f"fixture {searches.group('n')} vs database {real['searches']}"))
        serie = SERIE.search(body)
        if serie and real["series"] is not None:
            spelled = as_js_string(str(real["series"]))
            if serie.group("v") != spelled:
                found.append((title, "serie", f"fixture {serie.group('v')} vs database {spelled}"))
    return found


def rewrite(text: str, facts: dict[str, dict[str, object]]) -> str:
    """Returns the fixture with every drifted value replaced by the live one.

    Entries are rewritten back to front so an earlier edit cannot move the
    offsets of a later one.
    """
    for begin, stop, title in sorted(entries(text), reverse=True):
        body = text[begin:stop]
        real = facts.get(title)
        if real is None or not SEARCHES.search(body):
            continue
        body = SEARCHES.sub(lambda m: f"searches: {int(real['searches'])}", body, count=1)
        if real["series"] is not None:
            spelled = as_js_string(str(real["series"]))
            body = SERIE.sub(lambda m: f"serie: {spelled}", body, count=1)
        text = text[:begin] + body + text[stop:]
    return text


def main() -> int:
    """Reports or repairs the fixture's drift against ``acquire.db``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift, exit 1 if any")
    parser.add_argument("--apply", action="store_true", help="rewrite the fixture in place")
    parser.add_argument("--database", type=pathlib.Path, default=ACQUIRE)
    parser.add_argument("--fixture", type=pathlib.Path, default=FIXTURE)
    options = parser.parse_args()
    if not (options.check or options.apply):
        parser.error("choose --check or --apply")

    facts = live_facts(options.database)
    if not facts:
        # Absent database is NOT a pass: it is a check that could not run, and
        # it says so rather than reporting success it did not establish.
        print(f"refresh-maquette-fixture: no database at {options.database} — nothing verified")
        return 0

    text = options.fixture.read_text(encoding="utf-8")
    found = drift(text, facts)
    if not found:
        print(f"refresh-maquette-fixture: fixture agrees with {options.database.name}")
        return 0

    for title, field, message in found:
        print(f"  {title} · {field}: {message}")
    if options.check:
        print(f"refresh-maquette-fixture: {len(found)} drift(s) — run with --apply")
        return 1

    stale = [f for f in found if f[1] == "title"]
    options.fixture.write_text(rewrite(text, facts), encoding="utf-8")
    remaining = drift(options.fixture.read_text(encoding="utf-8"), facts)
    print(f"refresh-maquette-fixture: rewrote {len(found) - len(stale)} value(s)")
    if remaining:
        # A title the database does not know cannot be repaired by rewriting a
        # number, so it survives on purpose and stays visible.
        print(f"refresh-maquette-fixture: {len(remaining)} left for a human")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
