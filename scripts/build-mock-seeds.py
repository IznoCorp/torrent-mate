#!/usr/bin/env python3
"""Builds the mock layer's seeds from the maquette engine's fixtures.

WHY THE SEEDS ARE A COPY AND NOT AN IMPORT (D-L08-7). The engine dies — by
subtraction at L09, entirely at L13 — so a mock layer importing it would die
with it, which is backwards. And an import would make the correspondence check
VACUOUS: comparing a derivation against the thing it was derived from at run
time proves nothing. A committed copy CAN drift from its source, and holding
that it does not is a check with something to do.

NOTHING IS PROJECTED ANY MORE. A projection was a rename of keys and a regroup of
positional arrays into named fields, never a re-derivation; every served family
has since been converted — its literal left the engine and its committed seed is
what the mock layer answers — so no family is rebuilt from a fixture, and
`fixture-projections.json` declares only each seed's file and its join.

THE JOIN IS THE ONE STEP THAT ADDS A VALUE, and it is declared, never implied.
A list item carries a title; the contract wants the medium's provider identity
and its poster beside it, and the fixture holds both only in OTHER families,
keyed by title. A family that declares `join` in `fixture-projections.json`
gets those fields: `ids` from the media sheet its title
resolves to, `poster` from the exact poster key, `title` from an entry's own
key. A joined field is re-derived on every run, so it cannot drift. The
resolver COPIES the engine's `sheetFor` — the exact title,
then the title without its year, then the normalised key, then the prefix of a
title a list truncated — and it lives here only until the engine's resolver is
gone; a title it cannot resolve joins `null`, which is what the seed knows.

A STANDING DUTY. `scripts/refresh-maquette-fixture.py` rewrites `FOLLOWS` from
the live `acquire.db`. After it runs the seeds must be rebuilt in the same
commit, or `--check` goes red — which is wanted, and is said here so a red guard
after a data refresh is read as the reminder it is.

Usage:
    python3 scripts/build-mock-seeds.py --write   # (re)build every seed
    python3 scripts/build-mock-seeds.py --check   # report drift, exit 1
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import unicodedata
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAQUETTE = ROOT / "frontend" / "maquette"
REGISTER = MAQUETTE / "fixture-register.json"
PROJECTIONS = MAQUETTE / "fixture-projections.json"
SEEDS = MAQUETTE / "design" / "src" / "mocks" / "seeds"
EXTRACTOR = ROOT / "scripts" / "extract-maquette-fixtures.mjs"

# The classes whose families become a seed. `interface` and `unserved` do not:
# routing a label or a long-press delay through a mock would have the interface
# asking a server for its own words.
SEEDED_CLASSES = ("served", "asset")


# Every family, read ONCE. One process per family meant a hundred and forty
# node starts over a 35 198-line file, and the guard reading this module took
# 66 s — against 31 s for the twelve repository guards put together.
_FIXTURES: dict | None = None


def fixtures() -> dict:
    """Reads every fixture family out of the engine, in one pass.

    Returns:
        `{family: value}` for every family the extractor finds.

    Raises:
        SystemExit: When the extractor fails.
    """
    global _FIXTURES
    if _FIXTURES is None:
        result = subprocess.run(
            ["node", str(EXTRACTOR), "--all"],
            capture_output=True, text=True, cwd=ROOT,
        )
        if result.returncode != 0:
            raise SystemExit(
                f"build-mock-seeds: the extractor failed: {result.stderr.strip()}")
        _FIXTURES = json.loads(result.stdout)
    return _FIXTURES


def fixture(name: str) -> object:
    """Reads one fixture family out of the engine.

    Args:
        name: The family's name, qualified when it sits inside a function.

    Returns:
        The family's value.

    Raises:
        SystemExit: When the engine declares no such family.
    """
    everything = fixtures()
    if name not in everything:
        raise SystemExit(
            f"build-mock-seeds: the engine declares no fixture family named {name!r}")
    return everything[name]


# The engine's own title arithmetic, spelled once. A year in brackets is not part
# of a title's identity; accents and punctuation are not part of its key; and a
# list that truncated a title is still pointing at the medium whose key it
# begins, provided enough of it is left to mean anything.
YEAR_SUFFIX = re.compile(r"\s*\((?:19|20)\d{2}\)\s*")
COMBINING_MARKS = re.compile("[\u0300-\u036f]")
NOT_LETTER_OR_DIGIT = re.compile(r"[\W_]+")
TRUNCATED_TITLE_FLOOR = 6


def base_title(title: object) -> str:
    """A title without the year in brackets that distinguishes two releases."""
    return YEAR_SUFFIX.sub(" ", str(title)).strip()


def normalised_key(title: object) -> str:
    """A title's key: no year, no accent, no punctuation, lower case."""
    decomposed = unicodedata.normalize("NFD", base_title(title))
    return NOT_LETTER_OR_DIGIT.sub(" ", COMBINING_MARKS.sub("", decomposed)).strip().lower()


class SheetResolver:
    """Finds the media sheet a title names, the way the engine's `sheetFor` does."""

    def __init__(self, sheets: dict) -> None:
        """Indexes the sheets by key, the first title of a key winning.

        Args:
            sheets: The media sheets, keyed by title.
        """
        self.sheets = sheets
        self.by_key: dict[str, dict] = {}
        for title, sheet in sheets.items():
            self.by_key.setdefault(normalised_key(title), sheet)

    def sheet_for(self, title: object) -> dict | None:
        """Resolves a title to its sheet.

        Args:
            title: The title a list item carries.

        Returns:
            The sheet, or None when no tier resolves it.
        """
        if title is None:
            return None
        direct = self.sheets.get(title) or self.sheets.get(base_title(title))
        if direct:
            return direct
        key = normalised_key(title)
        if key in self.by_key:
            return self.by_key[key]
        for known, sheet in self.by_key.items():
            if known.startswith(key + " ") and len(key) > TRUNCATED_TITLE_FLOOR:
                return sheet
        return None


def join_source(name: str) -> object:
    """The family a join reads from: its committed seed.

    Args:
        name: The family joined from.

    Returns:
        Its seed, before any join of its own.
    """
    return json.loads(file_for(name).read_text(encoding="utf-8"))


def joined(name: str, seed: object, join: dict) -> object:
    """Adds the declared fields to every entry of a seed.

    A field already present is removed first and joined again, so joining a seed
    twice is joining it once — which is what lets a converted family's committed
    seed be re-joined in place.

    Args:
        name: The family, for the error message.
        seed: Its seed.
        join: Its declaration — `entries` and `fields`.

    Returns:
        The seed with the joined fields.

    Raises:
        SystemExit: When the declaration names a place or a source this build
            does not know.
    """
    resolver = SheetResolver(join_source("SHEETS_RAW"))
    posters = join_source("POSTERS")
    fields: dict[str, str] = join["fields"]
    # Read only when a declaration asks for it: most joins never do.
    posters_high_definition = (join_source("POSTERS_HD")
                               if "posterHighDefinition" in fields.values() else {})

    def decorate(entry: object, key: str | None) -> dict:
        if not isinstance(entry, dict):
            raise SystemExit(f"build-mock-seeds: {name} joins onto an entry that is not an object")
        result = {field: value for field, value in entry.items() if field not in fields}
        for field, source in fields.items():
            if source == "ids":
                sheet = resolver.sheet_for(entry.get("title"))
                result[field] = sheet.get("ids") if sheet else None
            elif source == "poster":
                # The title, then its base title, as the engine's poster lookup
                # resolved a list item: a year suffix is not a word of the title.
                title = entry.get("title")
                result[field] = posters.get(title) or posters.get(base_title(title))
            elif source == "exactPoster":
                # A PROPOSITION asks for its own picture only: « Lucky (2006) » is
                # not « Lucky », and a base title would hand one the other's.
                result[field] = posters.get(entry.get("title"))
            elif source == "posterHighDefinition":
                # The picture a full-screen card shows, under the exact title the
                # engine's deck looked it up by — null when none was taken.
                result[field] = posters_high_definition.get(entry.get("title"))
            elif source == "key":
                result[field] = key
            else:
                raise SystemExit(f"build-mock-seeds: {name} joins {field!r} from {source!r}, "
                                 f"which is not a join source")
        return result

    entries = join["entries"]
    if entries == "$item" and isinstance(seed, list):
        return [decorate(entry, None) for entry in seed]
    if entries == "$value" and isinstance(seed, dict):
        return {key: decorate(entry, key) for key, entry in seed.items()}
    if entries.startswith("/") and entries.endswith("[]") and isinstance(seed, dict):
        field = entries[1:-2]
        return {**seed, field: [decorate(entry, None) for entry in seed[field]]}
    if entries.startswith("[]/") and isinstance(seed, list):
        # One level down in each element of a top-level list: `[]/key[]` joins
        # every element of the list under that key, `[]/key` the object under
        # it, in the elements that carry one.
        field = entries[3:].removesuffix("[]")
        if entries.endswith("[]"):
            return [{**element, field: [decorate(inner, None) for inner in element[field]]}
                    for element in seed]
        return [{**element, field: decorate(element[field], None)}
                if element.get(field) is not None else element for element in seed]
    raise SystemExit(f"build-mock-seeds: {name} joins at {entries!r}, which its seed does not have")


def canonical(value: object) -> str:
    """Serializes a seed the one way this repository will ever serialize one."""
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def seeded_families() -> list[str]:
    """The families a seed can still be BUILT for, in a stable order.

    A CONVERTED FAMILY IS NOT ONE OF THEM, and that is D5 rather than an
    exception. Once L09 wires the surface that read a fixture, the fixture is
    deleted from `legacy.js` — so there is nothing left to re-derive the seed
    FROM, and asking for one raises. The seed itself stays: it is what the mock
    layer answers with, and it is now held by the contract's schema and by the
    oracle's rendering rather than by the engine's own literal. The register
    says which, and why, in each entry's `converted`.

    Returns:
        The families whose seed can be re-derived from the engine today.
    """
    families = json.loads(REGISTER.read_text(encoding="utf-8"))["families"]
    return sorted(name for name, entry in families.items()
                  if entry["class"] in SEEDED_CLASSES and not entry.get("converted"))


def converted_families() -> list[str]:
    """The SEEDED families whose fixture the engine no longer declares, in order.

    SEEDED, and the qualifier is the whole of it. `converted` records a decision
    — the engine stopped declaring this family, and here is why — and that
    decision can be taken about a family that never had a seed at all. L15 took
    one: `icons` was `interface`, the frame draws with it, and it moved OUT of
    the engine into `app/icons.ts` rather than into the mock layer. Both callers
    of this function are about SEED FILES — what was not re-derived, and which
    files to keep — so a family with no seed has no business in either, and
    including it demanded a seed file for a drawing.

    Returns:
        Their names, so a caller can print what it did NOT compare rather than
        leaving the absence to be read as a pass.
    """
    families = json.loads(REGISTER.read_text(encoding="utf-8"))["families"]
    return sorted(name for name, entry in families.items()
                  if entry["class"] in SEEDED_CLASSES and entry.get("converted"))


def file_for(name: str) -> Path:
    """The seed file one family is written to.

    DECLARED, NEVER DERIVED FROM THE FAMILY NAME. The families are the ENGINE's
    and carry its spelling — one is French, several are abbreviated — while
    these files are new, and a new file is named in English and written out in
    full on the day it is written. Deriving the name would have carried the
    engine's spelling into a tree that has to outlive it.

    Args:
        name: The family.

    Returns:
        The seed file.

    Raises:
        SystemExit: When the family declares no file name — a seed named by
            nobody is a name nobody chose.
    """
    declared = json.loads(PROJECTIONS.read_text(encoding="utf-8"))["families"]
    chosen = declared.get(name, {}).get("file")
    if not chosen:
        raise SystemExit(
            f"build-mock-seeds: {name} is served and {PROJECTIONS.name} declares no `file` "
            f"for it. A seed file is named deliberately, in English, and never derived from "
            f"the engine's own spelling")
    return SEEDS / (chosen + ".json")


def build() -> dict[str, str]:
    """Builds every seed the engine can still re-derive — and there is none.

    NO FAMILY IS RECONSTRUCTIBLE. Every served family has been converted: its
    literal left the engine and its seed is what the mock layer answers with, so
    nothing is projected and `fixture-projections.json` declares no projection.
    A family the register marks seeded and not converted would be a family with
    no way to build its seed, and that is refused rather than skipped.

    Returns:
        `{}` — the seeds are the converted families' committed files.

    Raises:
        SystemExit: When the register names a seeded family that is not converted.
    """
    unconverted = seeded_families()
    if unconverted:
        raise SystemExit(
            f"build-mock-seeds: {', '.join(unconverted)} is seeded and not converted, and "
            f"nothing projects a fixture any more")
    return {}


def rejoined() -> dict[str, str]:
    """Re-joins every CONVERTED family that declares a join, from its committed seed.

    A converted family cannot be re-derived from the engine, but its joined
    fields still can: they come from other families, and they are removed and
    joined again so they cannot drift from those families.

    Returns:
        `{path: text}` for every such seed.
    """
    plans = json.loads(PROJECTIONS.read_text(encoding="utf-8"))["families"]
    texts: dict[str, str] = {}
    for name in converted_families():
        join = plans.get(name, {}).get("join")
        if not join:
            continue
        path = file_for(name)
        seed = json.loads(path.read_text(encoding="utf-8"))
        texts[str(path)] = canonical(joined(name, seed, join))
    return texts


def main() -> int:
    """Writes or checks every seed."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="(re)build every seed")
    group.add_argument("--check", action="store_true", help="report drift, exit 1")
    arguments = parser.parse_args()

    built = build()
    joined_again = rejoined()
    SEEDS.mkdir(parents=True, exist_ok=True)

    if arguments.write:
        for path, text in {**built, **joined_again}.items():
            Path(path).write_text(text, encoding="utf-8")
        # A seed whose family has left the register is deleted rather than left
        # behind: an orphan seed is a payload nothing can re-derive.
        #
        # A CONVERTED FAMILY'S SEED IS NOT AN ORPHAN, and deleting one is the
        # worst thing this script can do. Since L09 a family is deleted from
        # `legacy.js` the moment its surface reads the layer instead (D5) — so
        # it cannot be re-derived, `build()` does not build it, and the naive
        # reading of « not in built » is « delete the payload the mock layer
        # actually serves ». Measured: one `--write` removed twenty-one of them,
        # including every queue list and every decision.
        kept = {str(file_for(name)) for name in converted_families()}
        for existing in sorted(SEEDS.glob("*.json")):
            if str(existing) in built or str(existing) in kept:
                continue
            existing.unlink()
            print(f"  removed {existing.relative_to(ROOT)} — no family claims it")
        print(f"build-mock-seeds: wrote {len(built)} seed(s) to "
              f"{SEEDS.relative_to(ROOT)}")
        return 0

    drifted: list[str] = []
    for path, text in joined_again.items():
        if Path(path).read_text(encoding="utf-8") != text:
            drifted.append(f"{Path(path).relative_to(ROOT)}: its joined fields differ from "
                           f"the families they are joined from")
    for path, text in built.items():
        target = Path(path)
        if not target.is_file():
            drifted.append(f"{target.relative_to(ROOT)}: missing")
        elif target.read_text(encoding="utf-8") != text:
            drifted.append(f"{target.relative_to(ROOT)}: differs from the fixture it "
                           f"was taken from")
    for existing in sorted(SEEDS.glob("*.json")):
        if str(existing) not in built:
            drifted.append(f"{existing.relative_to(ROOT)}: no family claims it")
    print(f"build-mock-seeds: {len(built)} seed(s) re-derived, {len(drifted)} drifted")
    for entry in drifted:
        print(f"    {entry}", file=sys.stderr)
    return 1 if drifted else 0


if __name__ == "__main__":
    sys.exit(main())
