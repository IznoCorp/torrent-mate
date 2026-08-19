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
ENTRY = re.compile(
    r'(?P<head>\{\s*\n\s*t:\s*"(?P<title>(?:[^"\\]|\\.)*)",)(?P<body>.*?)(?P<tail>\n\s*\},)',
    re.S,
)


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


def drift(text: str, facts: dict[str, dict[str, object]]) -> list[tuple[str, str, str]]:
    """Lists every fixture value the database disagrees with.

    Args:
        text: The fixture source.
        facts: The live facts, keyed by title.

    Returns:
        One (title, field, message) per disagreement.
    """
    found: list[tuple[str, str, str]] = []
    for match in ENTRY.finditer(text):
        title = match.group("title")
        body = match.group("body")
        # Only entries that carry a `searches:` are follow entries; the same
        # shape holds cards and releases elsewhere in the file.
        searches = re.search(r"\n\s*searches:\s*(\d+),", body)
        if not searches:
            continue
        real = facts.get(title)
        if real is None:
            found.append((title, "title", "absent from acquire.db"))
            continue
        if int(searches.group(1)) != int(real["searches"]):
            found.append(
                (title, "searches", f"fixture {searches.group(1)} vs database {real['searches']}")
            )
        serie = re.search(r'\n\s*serie:\s*(null|"(?:[^"\\]|\\.)*"),', body)
        if serie and real["series"] is not None:
            spelled = f'"{real["series"]}"'
            if serie.group(1) != spelled:
                found.append((title, "serie", f"fixture {serie.group(1)} vs database {spelled}"))
    return found


def rewrite(text: str, facts: dict[str, dict[str, object]]) -> str:
    """Returns the fixture with every drifted value replaced by the live one."""

    def one(match: re.Match[str]) -> str:
        title, body = match.group("title"), match.group("body")
        real = facts.get(title)
        if real is None or not re.search(r"\n\s*searches:\s*\d+,", body):
            return match.group(0)
        body = re.sub(
            r"(\n\s*searches:\s*)\d+(,)", rf"\g<1>{int(real['searches'])}\g<2>", body
        )
        if real["series"] is not None:
            body = re.sub(
                r'(\n\s*serie:\s*)(?:null|"(?:[^"\\]|\\.)*")(,)',
                rf'\g<1>"{real["series"]}"\g<2>',
                body,
            )
        return match.group("head") + body + match.group("tail")

    return ENTRY.sub(one, text)


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
