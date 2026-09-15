#!/usr/bin/env python3
"""Builds the mock layer's seeds from the maquette engine's fixtures.

WHY THE SEEDS ARE A COPY AND NOT AN IMPORT (D-L08-7). The engine dies — by
subtraction at L09, entirely at L13 — so a mock layer importing it would die
with it, which is backwards. And an import would make the correspondence check
VACUOUS: comparing a derivation against the thing it was derived from at run
time proves nothing. A committed copy CAN drift from its source, and holding
that it does not is a check with something to do.

WHAT A PROJECTION IS, AND WHAT IT IS NOT. A rename of keys and a regroup of
positional arrays into named fields. Never a re-derivation: no value is
recomputed, reformatted, parsed or split. Where a fixture holds a pre-formatted
string the contract carries it verbatim and the demand register asks the backend
for the underlying fact — because a mock returning exactly what the fixture
returns is what makes L09 provable at zero divergence, and a decomposition here
would forfeit that for a contract nobody is building yet.

THE RENAMES ARE SCOPED BY PATH, and that is not fussiness. `n` means `name`
inside a cast list and `number` inside an episode list, both within one family:
a flat recursive rename corrupts `SHEETS_RAW` in silence, which is the exact
shape of failure this repository has paid for twice.

THE JOIN IS THE ONE STEP THAT ADDS A VALUE, and it is declared, never implied.
A list item carries a title; the contract wants the medium's provider identity
and its poster beside it, and the fixture holds both only in OTHER families,
keyed by title. A family that declares `join` in `fixture-projections.json`
gets those fields after its projection: `ids` from the media sheet its title
resolves to, `poster` from the exact poster key, `title` from an entry's own
key. The lossless comparison reads the projection BEFORE the join, so a join
cannot hide a lost value, and a joined field is re-derived on every build, so
it cannot drift. The resolver COPIES the engine's `sheetFor` — the exact title,
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


def projection_for(name: str, declared: dict, shorthands: dict) -> dict:
    """Resolves one family's projection, expanding any shorthand it names.

    Sixteen families share one of two shapes. Writing the map out sixteen times
    is sixteen places for one copy to drift, and the drift would be invisible —
    each copy would still be internally consistent.

    Args:
        name: The family's name, for the error message.
        declared: What `fixture-projections.json` holds for it.
        shorthands: The `$shorthands` block.

    Returns:
        The projection, with `rename`, `tuples`, `opaque` and `keyedByData`.

    Raises:
        SystemExit: When it names a shorthand that does not exist.
    """
    resolved = dict(declared)
    for key in [key for key in declared if key.startswith("$")]:
        if key not in shorthands:
            raise SystemExit(
                f"build-mock-seeds: {name} names the shorthand {key!r}, which "
                f"{PROJECTIONS.name} does not declare")
        resolved.pop(key)
        for field, value in shorthands[key].items():
            resolved.setdefault(field, value)
    return {
        "rename": resolved.get("rename", {}),
        "tuples": resolved.get("tuples", {}),
        "opaque": set(resolved.get("opaque", [])),
        "keyedByData": bool(resolved.get("keyedByData", False)),
    }


def matches(pattern: str, path: str) -> bool:
    """Answers whether a scoped rename path matches the path being walked.

    `*` stands for exactly one key segment — `/eps/*[]` reaches every season's
    episode list without naming the twenty-two season numbers, which are data.

    Args:
        pattern: The path written in the projection.
        path: The path the walk has reached.

    Returns:
        True when they describe the same place.
    """
    if pattern == path:
        return True
    if "*" not in pattern:
        return False
    expected = pattern.split("/")
    actual = path.split("/")
    if len(expected) != len(actual):
        return False
    return all(want in ("*", "*[]") and (want != "*[]" or have.endswith("[]"))
               or want == have
               for want, have in zip(expected, actual))


def regroup(value: list, fields: list[str], where: str) -> dict:
    """Turns a positional array into an object with named fields.

    Args:
        value: The array.
        fields: The field names, in position order.
        where: The path, for the error message.

    Returns:
        The object.

    Raises:
        SystemExit: When the array is not the length the field list expects —
            a silent truncation is how a value disappears from a seed.
    """
    if not isinstance(value, list) or len(value) != len(fields):
        raise SystemExit(
            f"build-mock-seeds: at {where}, a tuple of {len(fields)} field(s) was "
            f"declared and the fixture holds {value!r}")
    return dict(zip(fields, value))


def project(value: object, plan: dict, path: str = "") -> object:
    """Applies one family's projection to its value.

    Args:
        value: The value being walked.
        plan: The resolved projection.
        path: Where the walk has reached, in the projection's own notation.

    Returns:
        The projected value.
    """
    if isinstance(value, dict):
        renames: dict[str, str] = {}
        for pattern, mapping in plan["rename"].items():
            if matches(pattern, path):
                renames.update(mapping)
        projected = {}
        for key, inner in value.items():
            name = renames.get(key, key)
            if key in plan["opaque"]:
                # The operator's own configuration lives under here, and its
                # keys are `name`, `path`, `id`. A renamer walking in would
                # rewrite the configuration rather than the contract.
                projected[name] = inner
                continue
            if key in plan["tuples"]:
                projected[name] = regroup(inner, plan["tuples"][key], f"{path}/{key}")
                continue
            projected[name] = project(inner, plan, f"{path}/{key}")
        return projected
    if isinstance(value, list) and path == "":
        # The two selectors name the same PLACE — the array at the projection's
        # root — and are kept apart because they name different SHAPES: a family
        # whose top-level value is a list of tuples, and a family keyed by data
        # each of whose entries is one. A single name would leave the reader of
        # `fixture-projections.json` unable to tell which of the two they are
        # looking at.
        selector = "$value[]" if plan["keyedByData"] else "$item"
        if selector in plan["tuples"]:
            return [regroup(item, plan["tuples"][selector], selector) for item in value]
    if isinstance(value, list):
        return [project(item, plan, path + "[]") for item in value]
    return value


def seed_of(name: str, plan: dict) -> object:
    """Reads a family and projects it into its contract shape.

    A family whose top-level keys are DATA — a title, a name — has its entries
    projected and its keys left exactly as they are.

    Args:
        name: The family.
        plan: Its resolved projection.

    Returns:
        The seed.
    """
    value = fixture(name)
    if plan["keyedByData"]:
        if not isinstance(value, dict):
            raise SystemExit(
                f"build-mock-seeds: {name} is declared keyed by data and is not a map")
        return {key: project(entry, plan) for key, entry in value.items()}
    return project(value, plan)


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


def join_source(name: str, projected: dict[str, object]) -> object:
    """The family a join reads from: projected in this run, or its committed seed.

    Args:
        name: The family joined from.
        projected: The families projected in this run.

    Returns:
        Its seed, before any join of its own.
    """
    if name in projected:
        return projected[name]
    return json.loads(file_for(name).read_text(encoding="utf-8"))


def joined(name: str, seed: object, join: dict, projected: dict[str, object]) -> object:
    """Adds the declared fields to every entry of a seed.

    A field already present is removed first and joined again, so joining a seed
    twice is joining it once — which is what lets a converted family's committed
    seed be re-joined in place.

    Args:
        name: The family, for the error message.
        seed: Its seed.
        join: Its declaration — `entries` and `fields`.
        projected: The families projected in this run.

    Returns:
        The seed with the joined fields.

    Raises:
        SystemExit: When the declaration names a place or a source this build
            does not know.
    """
    resolver = SheetResolver(join_source("SHEETS_RAW", projected))
    posters = join_source("POSTERS", projected)
    fields: dict[str, str] = join["fields"]
    # Read only when a declaration asks for it: most joins never do.
    posters_high_definition = (join_source("POSTERS_HD", projected)
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


def leaves(value: object) -> list:
    """Collects every leaf value, so two structures can be compared by content.

    THIS IS THE LOSSLESS CHECK'S WHOLE MECHANISM, and it is stronger than
    comparing key lists. A dropped key takes its values with it; an altered
    value shows up directly; a rename moves no leaf and a regroup moves none
    either, so both pass — correctly. What it cannot see is two keys of the
    same type swapped for one another, and that is what the declared rename map
    is for: it is data a human reads.

    Args:
        value: The structure.

    Returns:
        Every scalar in it, in walk order.
    """
    found: list = []
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
        else:
            found.append(current)
    return found


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


_PROJECTED: dict[str, object] | None = None


def projected_seeds() -> dict[str, object]:
    """Every family a seed can be built for, projected, before any join.

    Returns:
        `{family: seed}`.

    Raises:
        SystemExit: When a projection loses a value.
    """
    global _PROJECTED
    if _PROJECTED is not None:
        return _PROJECTED
    declared = json.loads(PROJECTIONS.read_text(encoding="utf-8"))
    shorthands = declared["$shorthands"]
    plans = declared["families"]
    projected: dict[str, object] = {}
    for name in seeded_families():
        if name not in plans:
            raise SystemExit(
                f"build-mock-seeds: {name} is served and {PROJECTIONS.name} declares no "
                f"projection for it")
        plan = projection_for(name, plans[name], shorthands)
        raw = fixture(name)
        seed = seed_of(name, plan)
        before, after = sorted(map(repr, leaves(raw))), sorted(map(repr, leaves(seed)))
        if before != after:
            lost = [value for value in before if value not in after][:5]
            gained = [value for value in after if value not in before][:5]
            raise SystemExit(
                f"build-mock-seeds: the projection of {name} is not lossless — "
                f"{len(before)} leaf value(s) in, {len(after)} out; "
                f"lost {lost}, gained {gained}")
        projected[name] = seed
    _PROJECTED = projected
    return projected


def build() -> dict[str, str]:
    """Builds every seed, and refuses a projection that loses a value.

    Returns:
        `{path: text}` for every seed.
    """
    plans = json.loads(PROJECTIONS.read_text(encoding="utf-8"))["families"]
    projected = projected_seeds()
    built: dict[str, str] = {}
    for name, seed in projected.items():
        join = plans[name].get("join")
        if join:
            seed = joined(name, seed, join, projected)
        built[str(file_for(name))] = canonical(seed)
    return built


def rejoined() -> dict[str, str]:
    """Re-joins every CONVERTED family that declares a join, from its committed seed.

    A converted family cannot be re-derived from the engine, but its joined
    fields still can: they come from other families, and they are removed and
    joined again so they cannot drift from those families.

    Returns:
        `{path: text}` for every such seed.
    """
    plans = json.loads(PROJECTIONS.read_text(encoding="utf-8"))["families"]
    projected = projected_seeds()
    texts: dict[str, str] = {}
    for name in converted_families():
        join = plans.get(name, {}).get("join")
        if not join:
            continue
        path = file_for(name)
        seed = json.loads(path.read_text(encoding="utf-8"))
        texts[str(path)] = canonical(joined(name, seed, join, projected))
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
