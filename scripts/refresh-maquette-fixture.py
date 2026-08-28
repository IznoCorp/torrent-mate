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
import json
import pathlib
import re
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
# WHERE `FOLLOWS` LIVES SINCE L09. It was an array in `legacy.js`, and the
# Acquisition deck read it from there; the deck reads `/api/acquisition/followed`
# now and the fixture was deleted (D5 — the engine dies by subtraction). The
# seed is what the mock layer answers with, so it is what may drift from the
# operator's own database.
#
# A JSON TARGET IS NOT A WEAKER ONE. The walker this replaces existed because a
# JavaScript array has to be parsed by hand, and it had been wrong twice — one
# version cut an entry short at a nested object, another matched nothing at all
# and dropped a field in silence. What it guarded against is unchanged and is
# below: an absent file, an absent array and an unknown title each REFUSE rather
# than report agreement.
FIXTURE = (ROOT / "frontend" / "maquette" / "design" / "src" / "mocks" / "seeds"
           / "follows.json")

# The seed's own names for the two facts the database owns, and for the title
# they hang on. They are the CONTRACT's, which is what the projection renamed
# them to; the engine's were `t`, `searches` and `serie`.
SEED_TITLE = "title"
SEED_SEARCHES = "searches"
SEED_STATUS = "showStatus"
ACQUIRE = ROOT / ".data" / "acquire.db"

# One entry of the FOLLOWS array, from its title to the end of its object.
# The FOLLOWS array, and nothing else in the file.
FOLLOWS = re.compile(r"\bconst FOLLOWS\s*=\s*\[", re.S)
TITLE = re.compile(r'(?<![\w$])t:\s*"(?P<title>(?:[^"\\]|\\.)*)"')


def seeded(text: str) -> list[dict]:
    """Reads the seeded follows, refusing anything that is not the array.

    Args:
        text: The seed file's contents.

    Returns:
        The entries.

    Raises:
        SystemExit: When the file is not an array of objects — the caller must
            not treat « no entries » as « nothing drifted », which is the whole
            reason this refuses instead of returning an empty list.
    """
    try:
        held = json.loads(text)
    except json.JSONDecodeError as broken:
        raise SystemExit(
            f"refresh-maquette-fixture: {FIXTURE.name} does not parse ({broken}) — "
            "refusing to report agreement about a file it could not read.")
    if not isinstance(held, list) or not held:
        raise SystemExit(
            f"refresh-maquette-fixture: {FIXTURE.name} is not a non-empty array — "
            "refusing to report agreement about an array it could not find.")
    if any(not isinstance(entry, dict) or SEED_TITLE not in entry for entry in held):
        raise SystemExit(
            f"refresh-maquette-fixture: an entry of {FIXTURE.name} carries no "
            f"`{SEED_TITLE}` — refusing to compare entries it cannot name.")
    return held


def drift(text: str, facts: dict[str, dict[str, object]]) -> list[tuple[str, str, str]]:
    """Every value the seed holds that the database contradicts.

    Args:
        text: The seed file's contents.
        facts: What the database holds, by title.

    Returns:
        One entry per disagreement: the title, the field, and what was measured.
    """
    found: list[tuple[str, str, str]] = []
    for entry in seeded(text):
        title = entry[SEED_TITLE]
        held = facts.get(title)
        if held is None:
            # A TITLE THE DATABASE DOES NOT KNOW is not a value to rewrite, and
            # saying so is the point: it survives every `--apply` and stays
            # visible until a human decides what it is.
            found.append((title, "title", "the database follows nothing by that name"))
            continue
        if entry.get(SEED_SEARCHES) != held["searches"]:
            found.append((title, SEED_SEARCHES,
                          f"« {entry.get(SEED_SEARCHES)} » vs {held['searches']}"))
        if held["series"] is not None and entry.get(SEED_STATUS) != held["series"]:
            found.append((title, SEED_STATUS,
                          f"« {entry.get(SEED_STATUS)} » vs {held['series']}"))
    return found


def rewrite(text: str, facts: dict[str, dict[str, object]]) -> str:
    """Writes the database's values into the seed, keeping everything else.

    A TITLE THE DATABASE DOES NOT KNOW IS LEFT ALONE, which is why `--apply`
    can still finish with drift outstanding and says so.

    Args:
        text: The seed file's contents.
        facts: What the database holds, by title.

    Returns:
        The seed, rewritten.
    """
    held = seeded(text)
    for entry in held:
        known = facts.get(entry[SEED_TITLE])
        if known is None:
            continue
        entry[SEED_SEARCHES] = known["searches"]
        if known["series"] is not None and SEED_STATUS in entry:
            entry[SEED_STATUS] = known["series"]
    return json.dumps(held, ensure_ascii=False, indent=2) + "\n"


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
