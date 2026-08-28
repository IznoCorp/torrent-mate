#!/usr/bin/env python3
"""The live relay's three source questions, none of which needs a browser.

L10's contract has three clauses. R91 measures the first against the query cache
and R92/R93 measure the second in a browser; what is left is what a READER of
the tree can answer, and these are the arms that answer it.

  no-polling          « no polling remains where an event exists » — the third
                      clause, and the only one this repository can hold
                      statically.
  named-invalidation  an invalidation names its keys. One `invalidateQueries()`
                      with no argument is a reload, and it would undo L09.
  map-completeness    every event the backend emits is mapped or exempted, and
                      every address a surface READS is refreshed or exempted.

EACH ARM SAYS WHAT IT DOES NOT READ BEFORE IT SAYS WHAT IT DOES, and one of
them starts at zero — which is the dangerous shape this repository has counted
forty times (`BUGS.md` § Guards green over what they do not read). An arm
written the day its subject does not exist reports « no violation » and means « I
read nothing », and the two are indistinguishable in a log. So `no-polling`
PRINTS ITS CORPUS and refuses one below a floor: the same defence
`check-state-ownership.py`'s `effect-fetch` arm gives its own reasoning for.

WHAT NONE OF THESE ARMS READS:

  - Whether an invalidation reaches the right entries. A key is a prefix and its
    width is a judgement about the data; only R91 can see it, and only against a
    live cache.
  - Whether the map is RIGHT. `map-completeness` holds that every event and
    every address is ACCOUNTED FOR — mapped or deliberately not. It cannot say
    that `ItemProgressed` should refresh staging rather than the pipeline
    status; that is what each rule's `because` line is for, and what a reviewer
    reads.
  - Anything about the transport. The socket, the backoff and the replay are
    R93's, in a browser.
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DESIGN = ROOT / "frontend" / "maquette" / "design" / "src"
FEATURES = DESIGN / "features"
LIBRARY = DESIGN / "lib"
# The dying engine keeps its own hand-written JavaScript until L13 (D5, D-L07-5)
# and is read by no arm here: a long-press `setTimeout` is a delay, not a poll,
# and rewriting the engine to satisfy a guard is the opposite of subtraction.
ENGINE = DESIGN / "engine"

# WHERE THE BACKEND'S EVENTS ARE — DERIVED, NEVER LISTED. This was a tuple of
# six files, and a hand-enumerated corpus is the shape `BUGS.md` counts: nine
# real `Event` subclasses lived outside it — three in `core/circuit.py`, six in
# `api/metadata/registry/_events.py` — and every one of them reaches the browser,
# because `RedisEventPublisher` subscribes to the BASE `Event` class and the
# relay broadcasts every entry with no type filter. The arm was holding 40 of 48
# and could not report the eight it never saw.
#
# AND IT MATCHED ANY TOP-LEVEL CLASS, not an `Event` subclass, so
# `StepItemStatus` — a `StrEnum` of status literals carried as a FIELD of
# `ItemProgressed` — counted as an event. It inflated the total by one and, worse,
# masked a dead rule: a feature named it, `mapped - emitted` was empty, and both
# directions of this arm went quiet over a name the bus can never emit.
PACKAGE = ROOT / "personalscraper"
EVENT_BASE = re.compile(r"^class (\w+)\(Event\)", re.MULTILINE)

# The floor beneath `no-polling`'s corpus. It is the number of TypeScript files
# the arm must have read for its answer to mean anything, and it is set well
# under the count at the time of writing (measured: 118) so an ordinary deletion
# does not trip it — while a scope that has silently become empty does. A floor
# posted AT the current value would be pre-satisfied and would prove nothing,
# which is one of the forms B-085 counts.
POLLING_CORPUS_FLOOR = 60

# What `map-completeness` must have read for its answer to mean anything. Nine
# feature tables exist and 24 addresses are declared; a floor under both catches
# a parser that has silently stopped reading part of the tree.
TABLE_FLOOR = 8
ADDRESS_FLOOR = 20

# What a poll looks like. `setTimeout` is NOT here: a delay happens once, and
# the relay's own backoff is a schedule of them. A poll is a repetition.
POLLING = (
    (re.compile(r"\brefetchInterval\b"), "refetchInterval"),
    (re.compile(r"\bsetInterval\s*\("), "setInterval"),
    (re.compile(r"\brefetchIntervalInBackground\b"), "refetchIntervalInBackground"),
)

# EVERY SPELLING THAT REACHES THE WHOLE CACHE, and the first version knew two of
# them. `invalidateQueries({ queryKey: [] })` was the worst miss: an empty key
# array matches every query, and it also matched the `named` counter — so a
# whole-cache reload INCREMENTED the number this arm prints as evidence that it
# is working. `resetQueries`, `removeQueries`, `refetchQueries` and `clear` were
# invisible entirely, and `refetchQueries` is worse than an invalidation because
# it refires the network at once.
CACHE_WIDE = (
    (re.compile(r"invalidateQueries\s*\(\s*(\)|\{\s*\})"),
     "names no key, so it invalidates the WHOLE cache"),
    (re.compile(r"invalidateQueries\s*\(\s*\{[^}]*queryKey\s*:\s*\[\s*\]"),
     "names an EMPTY key, which matches every query in the cache"),
    (re.compile(r"invalidateQueries\s*\(\s*\{[^}]*\b(predicate|type)\s*:"),
     "selects by predicate or by type rather than by key"),
    (re.compile(r"\b(resetQueries|removeQueries|refetchQueries)\s*\("),
     "reaches every query it is not given a key for"),
    (re.compile(r"queryClient\s*\.\s*clear\s*\("),
     "empties the cache outright"),
)


def sources():
    """Every TypeScript file of the maquette outside the dying engine."""
    return [path for path in sorted(DESIGN.rglob("*"))
            if path.is_file() and path.suffix in {".ts", ".tsx"}
            and ENGINE not in path.parents]


def arm_no_polling():
    """Refuses a poll where an event exists, and prints what it read."""
    files = sources()
    violations = 0
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("//", "*", "/*")):
                continue
            for pattern, name in POLLING:
                if pattern.search(line):
                    violations += 1
                    print(f"  {path.relative_to(ROOT)}:{number}: `{name}` — the "
                          "live relay is what refreshes this. A clock beside an "
                          "event is a second answer to one question, and the "
                          "two disagree the moment the network is slow.")
    print(f"check-live-relay[no-polling]: {len(files)} TypeScript file(s) read "
          f"outside the dying engine, floor {POLLING_CORPUS_FLOOR} — "
          f"{violations} poll(s)")
    if len(files) < POLLING_CORPUS_FLOOR:
        print(f"check-live-relay[no-polling]: the corpus is {len(files)} file(s), "
              f"under the floor of {POLLING_CORPUS_FLOOR}. This arm starts at "
              "zero violations, so a corpus that has silently emptied reports "
              "the same word as one that read everything.", file=sys.stderr)
        return 1
    return 1 if violations else 0


def arm_named_invalidation():
    """Refuses an invalidation that names no key."""
    files = sources()
    violations = 0
    named = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        # A NAMED INVALIDATION IS ONE WITH A KEY THAT IS NOT AN EMPTY ARRAY.
        # Counting every `queryKey:` made `queryKey: []` evidence of health; a
        # first repair demanded a `[` and then missed `queryKey: key`, which is
        # how every rule of the map is written — the count fell from 6 to 1 and
        # said so, which is the whole point of printing it.
        named += len([
            one for one in re.findall(
                r"invalidateQueries\s*\(\s*\{\s*queryKey\s*:\s*([^,}\n]+)", text)
            if one.strip() not in {"[]", "[ ]"}
        ])
        for number, line in enumerate(text.splitlines(), 1):
            for pattern, what in CACHE_WIDE:
                if pattern.search(line):
                    violations += 1
                    print(f"  {path.relative_to(ROOT)}:{number}: this {what}. "
                          "That is a reload under another name, and it undoes "
                          "what L09 built.")
    print(f"check-live-relay[named-invalidation]: {named} invalidation(s) name a "
          f"key, {violations} name none")
    if named == 0:
        print("check-live-relay[named-invalidation]: no invalidation names a key "
              "anywhere — this arm would report « no violation » having found "
              "nothing to read.", file=sys.stderr)
        return 1
    return 1 if violations else 0


def backend_events():
    """Every `Event` subclass in the package, wherever it is declared.

    Returns:
        (the class names, None) — or (None, why) when the package is not there.
    """
    if not PACKAGE.is_dir():
        return None, str(PACKAGE)
    found = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        found |= set(EVENT_BASE.findall(path.read_text(encoding="utf-8")))
    return found, None


def rule_objects(source):
    """Yields each `{ … }` literal of a rules array, brace-matched.

    Args:
        source: The portion of a `live.ts` holding the rules.

    Yields:
        The text of each object literal, braces included.
    """
    depth, start = 0, None
    for index, character in enumerate(source):
        if character == "{":
            if depth == 0:
                start = index
            depth += 1
        elif character == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                yield source[start:index + 1]
                start = None


def declared():
    """Reads every feature's rules and exemptions out of its `live.ts`.

    Returns:
        (mapped types, exempt types, refreshed addresses, exempt addresses,
         how many `live.ts` files were read).
    """
    mapped, exempt_types = set(), set()
    refreshed, exempt_keys = set(), set()
    files = sorted(FEATURES.glob("*/live.ts"))
    for path in files:
        source = path.read_text(encoding="utf-8")
        constants = dict(re.findall(r'^const (\w+) = \["([^"]+)"', source, re.MULTILINE))
        # SPLIT ON THE EXEMPTIONS OBJECT, never on the word. The first
        # occurrence of « Exemptions » in every one of these files is the TYPE
        # IMPORT on line 1 — splitting there left `rules` holding an import
        # statement, and the arm reported 3 refreshed addresses out of 24 while
        # printing a confident number nobody could tell was short.
        marker = re.search(r"^export const \w+LiveExemptions", source, re.MULTILINE)
        rules = source[:marker.start()] if marker else source
        # EACH RULE OBJECT IS READ AS A UNIT, and `types` / `keys` are found
        # inside it in any order. The pattern used to require them adjacent and
        # in that order, and a non-greedy `.*?` does not FAIL on a violation —
        # it walks forward into the next rule and pairs one rule's types with
        # another's keys. Moving `because` between them, or writing `keys`
        # first, silently lost a rule. `fanout.py` carries the same reader, so
        # both went quiet together.
        for block in rule_objects(rules):
            found_types = re.search(r"types:\s*\[(.*?)\]", block, re.DOTALL)
            found_keys = re.search(r"keys:\s*\[(.*?)\]", block, re.DOTALL)
            if found_types is None or found_keys is None:
                continue
            mapped |= set(re.findall(r'"([^"]+)"', found_types.group(1)))
            for name in re.findall(r"\b([A-Z_][A-Z0-9_]*_KEY)\b", found_keys.group(1)):
                refreshed.add(constants[name])
        if marker:
            tail = source[marker.start():]
            block = re.search(r"types:\s*\[(.*?)\],\s*keys:\s*\[(.*?)\]", tail, re.DOTALL)
            if block:
                exempt_types |= set(re.findall(r'"([^"]+)"', block.group(1)))
                exempt_keys |= set(re.findall(r'"([^"]+)"', block.group(2)))
    return mapped, exempt_types, refreshed, exempt_keys, len(files)


def read_addresses():
    """Every address a surface asks the cache for, per feature file."""
    found = {}
    for path in sorted(list(FEATURES.rglob("queries.ts"))
                       + list(FEATURES.rglob("search-queries.ts"))
                       + [LIBRARY / "queue.ts"]):
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        addresses = set(re.findall(r'queryKey:\s*\[\s*"([^"]+)"', source))
        addresses |= {value for name, value in
                      re.findall(r'^export const (\w*[Kk]ey) = .*?\["([^"]+)"',
                                 source, re.MULTILINE)}
        # `useSystemRead(address)` keys on its argument, so the addresses are
        # the literals handed to it — read them rather than reporting a
        # variable, which would be an address this arm cannot check.
        addresses |= set(re.findall(r'useSystemRead<[^>]*>\(\s*"([^"]+)"', source))
        for address in addresses:
            found.setdefault(address, str(path.relative_to(ROOT)))
    return found


def arm_map_completeness():
    """Refuses an event or an address that is neither claimed nor exempted."""
    emitted, missing_source = backend_events()
    if emitted is None:
        print(f"check-live-relay[map-completeness]: {missing_source} is not "
              "there — this arm compares against the backend's own event "
              "classes, and cannot answer without them.", file=sys.stderr)
        return 1
    mapped, exempt_types, refreshed, exempt_keys, tables = declared()
    addresses = read_addresses()
    violations = 0

    # THE ADDRESS SIDE HAD NO FLOOR, and B-159 — this arm's own recorded defect
    # — was not zero: it read 3 addresses out of 24 and printed the number
    # confidently. A defence that trips only at emptiness cannot see the failure
    # that actually happened. The floor is under the count at the time of
    # writing and well above what a single parse failure would leave.
    if tables < TABLE_FLOOR or len(addresses) < ADDRESS_FLOOR:
        print(f"check-live-relay[map-completeness]: {tables} table(s) against a "
              f"floor of {TABLE_FLOOR}, {len(addresses)} address(es) against "
              f"{ADDRESS_FLOOR} — a corpus that has PARTIALLY emptied reports "
              "the same word as a complete one, which is how this arm's own "
              "B-159 went unread for a wave.", file=sys.stderr)
        return 1

    for event in sorted(emitted - mapped - exempt_types):
        violations += 1
        print(f"  {event}: the backend emits it, it reaches the browser, and no "
              "feature's rules or exemptions name it. An event nobody handles is "
              "not an error; an event nobody can COUNT is how a map silently "
              "stops covering its subject.")
    for event in sorted(mapped - emitted):
        violations += 1
        print(f"  {event}: a rule names it and the backend emits nothing by that "
              "name — the rule is dead, and its surface will never refresh.")
    for address, where in sorted(addresses.items()):
        # COMPARED FOR EQUALITY, not by string prefix. Both sides are a key's
        # FIRST ELEMENT, so `startswith` made any address that merely extends a
        # refreshed one silently covered: `/api/media-requests` by `/api/media`,
        # `/api/library/items-summary` by `/api/library/items`. Sibling paths
        # sharing a stem are ordinary REST.
        if address in refreshed | exempt_keys:
            continue
        violations += 1
        print(f"  {address} ({where}): a surface reads it and no event refreshes "
              "it, and no exemption says why. `staleTime: Infinity` with no "
              "focus and no reconnect refetch means it is stale for the life of "
              "the process (B-154).")

    # THE TWO SETS OVERLAP, and the print says so rather than letting two
    # numbers that sum past the total read as an error. `ItemProgressed` is
    # mapped by one feature and exempt in another, which is correct: an event
    # means something to one surface and nothing to its neighbour.
    claimed = emitted & (mapped | exempt_types)
    print(f"check-live-relay[map-completeness]: {len(emitted)} backend event(s), "
          f"{len(claimed)} accounted for — {len(emitted & mapped)} named by a "
          f"rule somewhere, {len(emitted & exempt_types)} named by an exemption "
          f"somewhere, and the two sets overlap by "
          f"{len(emitted & mapped & exempt_types)}; "
          f"{len(addresses)} address(es) read across {tables} feature table(s) — "
          f"{len(refreshed)} refreshed, {len(exempt_keys)} exempt")
    return 1 if violations else 0


ARMS = {
    "no-polling": arm_no_polling,
    "named-invalidation": arm_named_invalidation,
    "map-completeness": arm_map_completeness,
}


def main():
    """Runs one arm, or all of them."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=sorted(ARMS),
                        help="run one arm; all of them by default")
    arguments = parser.parse_args()
    wanted = [arguments.arm] if arguments.arm else sorted(ARMS)
    worst = 0
    for name in wanted:
        worst = max(worst, ARMS[name]())
    if worst == 0:
        print("check-live-relay: clean")
    return worst


if __name__ == "__main__":
    sys.exit(main())
