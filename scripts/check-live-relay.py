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

# And how many of them must DECLARE A READ. A poll lives beside a `useQuery`,
# and eleven files hold one today.
READING_FILES_FLOOR = 8

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

# A POLL WRITTEN AS A SELF-RESCHEDULING `setTimeout`. The arm ruled `setTimeout`
# out because « a delay happens once » — true of the relay's backoff, false of
# the standard way to write a poll with backoff, which is a callback that
# re-arms itself. Matched by NAME: a `setTimeout(name, …)` inside the body of a
# binding called `name`. The relay's own `setTimeout(connect, delay)` is not one
# — `connect` does not call `retry` directly, `retry` calls `connect` — and it
# is the only shape in this tree that comes close.
# Read over a BRACE-MATCHED body rather than a run of non-semicolons. The first
# version used `[^;]{0,400}?`, which cannot cross a statement — so it matched
# `function poll() { setTimeout(poll, 1000) }` and missed every shape anyone
# writes in a semicolon-using codebase, including the two the comment above
# names: a callback that does work before re-arming, and one wrapped in an
# arrow. It was armed against the case that never occurs.
NAMED_BINDING = re.compile(r"(?:const|let|function)\s+(\w+)\s*[=({]")

# EVERY SPELLING THAT REACHES THE WHOLE CACHE, and the first version knew two of
# them. `invalidateQueries({ queryKey: [] })` was the worst miss: an empty key
# array matches every query, and it also matched the `named` counter — so a
# whole-cache reload INCREMENTED the number this arm prints as evidence that it
# is working. `resetQueries`, `removeQueries`, `refetchQueries` and `clear` were
# invisible entirely, and `refetchQueries` is worse than an invalidation because
# it refires the network at once.
CACHE_WIDE = (
    (re.compile(r"invalidateQueries\s*\(\s*(\)|\{\s*\})", re.DOTALL),
     "names no key, so it invalidates the WHOLE cache"),
    # `[^}]*?` STOPS AT THE FIRST `}`, so a nested object before the key hid a
    # genuine whole-cache reload: `invalidateQueries({ meta: { a: 1 },
    # queryKey: [] })`. The scan is brace-aware instead — see `arm_named_invalidation`.
    (re.compile(r"invalidateQueries\s*\(\s*(?=\{)", re.DOTALL),
     "@@ARGUMENT@@names an EMPTY key, which matches every query in the cache"),
    # `type:` NARROWS, it does not widen — `{ queryKey: K, type: "active" }` is
    # ordinary and correct, and flagging it told its author to delete a correct
    # narrowing. Only a selector with NO key is cache-wide.
    (re.compile(r"invalidateQueries\s*\(\s*\{(?![^}]*?queryKey)[^}]*?"
                r"\b(?:predicate|type)\s*:", re.DOTALL),
     "selects by predicate or by type and names no key at all"),
    # R3-9: these three are only cache-wide when they are given NO key. A
    # `removeQueries({ queryKey: [...] })` evicting one sheet after a delete is
    # correct, and flagging it told its author the opposite of the truth.
    (re.compile(r"\b(?:resetQueries|removeQueries|refetchQueries)\s*\(\s*(?:\)|\{\s*\})",
                re.DOTALL),
     "reaches every query, because it is given no key"),
    (re.compile(r"\b(?:resetQueries|removeQueries|refetchQueries)"
                r"\s*\(\s*\{[^}]*?queryKey\s*:\s*\[\s*\]", re.DOTALL),
     "is given an EMPTY key, which matches every query"),
    # ANCHORED ON A CACHE, not on any receiver. `Map.clear()`, `Set.clear()` and
    # `localStorage.clear()` are ordinary; there are none in this tree today, so
    # the unanchored form was vacuous now and a false diagnosis the first time
    # anyone wrote one.
    (re.compile(r"\b(?:queryClient|queryCache|getQueryCache\(\))"
                r"\s*\.\s*clear\s*\(\s*\)"),
     "empties the query cache outright"),
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
    for path in files:
        source = path.read_text(encoding="utf-8")
        for found in NAMED_BINDING.finditer(source):
            name = found.group(1)
            body = brace_body(source, found.end() - 1)
            if body is None:
                continue
            rearms = re.search(
                rf"setTimeout\s*\(\s*(?:{name}\b"
                rf"|(?:async\s*)?\([^)]*\)\s*=>[^;]{{0,120}}?\b{name}\s*\()",
                body)
            if rearms is None:
                continue
            violations += 1
            line = source[: found.start()].count("\n") + 1
            print(f"  {path.relative_to(ROOT)}:{line}: `{name}` re-arms itself "
                  "with `setTimeout`. A delay happens once; a callback that "
                  "reschedules itself is a poll, and it is the shape a search "
                  "for `setInterval` can never find.")
    # THE SUBJECT IS FLOORED, not only the sweep. 60 against 124 files is a real
    # floor against total collapse and blind to targeted loss: a poll would be
    # written in a `queries.ts`, in `lib/queue.ts` or in a component — 13 files
    # of the 124. Deleting every one of them leaves 111, comfortably above 60,
    # with the arm having lost its whole subject and printing a reassuring
    # three-digit number.
    reads = [path for path in files if path.name.endswith("queries.ts")
             or path.name == "queue.ts"]
    print(f"check-live-relay[no-polling]: {len(files)} TypeScript file(s) read "
          f"outside the dying engine (floor {POLLING_CORPUS_FLOOR}), of which "
          f"{len(reads)} declare reads (floor {READING_FILES_FLOOR}) — "
          f"{violations} poll(s)")
    if len(reads) < READING_FILES_FLOOR:
        print(f"check-live-relay[no-polling]: {len(reads)} file(s) declare a "
              f"read, under the floor of {READING_FILES_FLOOR}. A poll is "
              "written where reads are; a corpus that kept its size and lost "
              "its subject reports the same word as a complete one.",
              file=sys.stderr)
        return 1
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
        # COMMENTS ARE NOT CODE, and the sibling arm has known that since it was
        # written. A doc comment naming `invalidateQueries()` in the forbidden
        # form broke this one — and this file's own prose does exactly that.
        raw = path.read_text(encoding="utf-8")
        text = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
        text = "\n".join(re.sub(r"//.*$", "", line) for line in text.splitlines())
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
        # READ OVER THE WHOLE FILE, never line by line. Every pattern that has
        # to see `invalidateQueries(` AND its argument needed them on one
        # PHYSICAL line — so `invalidateQueries({\n  queryKey: [],\n})`, which
        # is what any formatter produces once the call passes the line budget,
        # produced no violation AND no movement in the number this arm prints as
        # its evidence. Total silence on the arm's central subject.
        for pattern, what in CACHE_WIDE:
            for found in pattern.finditer(text):
                if what.startswith("@@ARGUMENT@@"):
                    # THE WHOLE ARGUMENT, brace-matched, so a nested object
                    # before the key cannot end the scan early.
                    argument = brace_body(text, found.end())
                    if argument is None:
                        continue
                    if re.search(r"queryKey\s*:\s*\[\s*\]", argument) is None:
                        continue
                    what = what.removeprefix("@@ARGUMENT@@")
                violations += 1
                number = text[: found.start()].count("\n") + 1
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
    """Every `Event` subclass, from the registry AND from the source.

    TWO ORACLES, COMPARED. The bus keeps `_EVENT_CLASS_REGISTRY`, populated by
    `__init_subclass__` — the authoritative answer, and the one the wire
    actually carries. The regex is a re-implementation of it, and a
    re-implementation that agrees today is one nobody can tell is wrong: it
    requires a column-zero `class`, a single base spelled exactly `Event`, and
    both on one physical line, so an event subclassing another event or
    declaring a second base would be registered by the bus and invisible here.

    The two are compared rather than one being trusted. They agree at 48 today;
    the day they do not, the disagreement is the finding.

    Returns:
        (the class names, None) — or (None, why) when neither can answer.
    """
    if not PACKAGE.is_dir():
        return None, str(PACKAGE)
    from_source = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        from_source |= set(EVENT_BASE.findall(path.read_text(encoding="utf-8")))
    try:
        sys.path.insert(0, str(ROOT))
        import importlib
        importlib.import_module("personalscraper.events")
        registry = set(importlib.import_module(
            "personalscraper.core.event_bus")._EVENT_CLASS_REGISTRY)
    except Exception:                      # noqa: BLE001 - any import failure
        # The registry needs the package importable; a tree without its
        # dependencies still gets the source answer, and says so.
        print("check-live-relay[map-completeness]: the event registry could not "
              "be imported — the corpus is the source scan alone, which is a "
              "re-implementation nothing is cross-checking here.",
              file=sys.stderr)
        return from_source, None
    if registry != from_source:
        # THE DISAGREEMENT IS THE FINDING, and it used to be printed and thrown
        # away — the same shape as the unresolved-key count two arms over. It is
        # returned so the caller can refuse.
        return registry | from_source, (
            "the bus registry and the source scan disagree — only in the "
            f"registry: {sorted(registry - from_source)}; only in the source: "
            f"{sorted(from_source - registry)}. The registry is what the wire "
            "carries; the scan is a regex that cannot see a subclassed or "
            "multi-base event, and one of the two is now wrong about this tree")
    return registry, None


def brace_body(source, opened):
    """Returns the `{ … }` block that starts at or after `opened`, or None.

    Args:
        source: The file's text.
        opened: Where to start looking.

    Returns:
        The block including its braces, or None when there is no balanced one.
    """
    start = source.find("{", opened)
    if start == -1:
        return None
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    return None


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
    unresolved = []
    files = sorted(FEATURES.glob("*/live.ts"))
    for path in files:
        source = path.read_text(encoding="utf-8")
        # `export const` COUNTS. The harvest was anchored on a bare `const`, so
        # a key constant a sibling module imports raised `KeyError` out of
        # `make check` with a traceback and nothing about the map.
        constants = dict(re.findall(
            r'^(?:export )?const (\w+) = \["([^"]+)"', source, re.MULTILINE))
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
        # first, silently lost a rule. `fanout.py` carried the same reader and
        # was repaired in the same move — an earlier version of this comment
        # said so before it was true, which is its own kind of defect.
        for block in rule_objects(rules):
            found_types = re.search(r"types:\s*\[(.*?)\]", block, re.DOTALL)
            found_keys = re.search(r"keys:\s*\[(.*?)\]", block, re.DOTALL)
            if found_types is None or found_keys is None:
                continue
            mapped |= set(re.findall(r'"([^"]+)"', found_types.group(1)))
            for name in re.findall(r"\b([A-Z_][A-Z0-9_]*_KEY)\b", found_keys.group(1)):
                if name not in constants:
                    unresolved.append((path.relative_to(ROOT), name))
                    continue
                refreshed.add(constants[name])
        if marker:
            # READ AS AN OBJECT, like the rules above. This half kept the exact
            # adjacency defect the rules half was repaired for — `types` then
            # `keys`, in that order, nothing between — so moving `because`
            # between them lost every exempt type in the file. Silently, where
            # the loss cannot be seen: five of them are mapped by another
            # feature, so `emitted - mapped - exempt` was unchanged and the arm
            # stayed green.
            for block in rule_objects(source[marker.start():]):
                found_types = re.search(r"types:\s*\[(.*?)\]", block, re.DOTALL)
                found_keys = re.search(r"keys:\s*\[(.*?)\]", block, re.DOTALL)
                if found_types is None:
                    continue
                exempt_types |= set(re.findall(r'"([^"]+)"', found_types.group(1)))
                if found_keys is not None:
                    exempt_keys |= set(re.findall(r'"([^"]+)"', found_keys.group(1)))
                break
    return mapped, exempt_types, refreshed, exempt_keys, len(files), unresolved


def read_addresses():
    """Every address ANY module asks the cache for.

    THE CORPUS WAS THREE FILENAMES — `features/**/queries.ts`,
    `search-queries.ts` and `lib/queue.ts` — and nothing enforces that query
    keys live there. `app/engine-data.ts` already declared four the arm never
    read; a `mutations.ts` or a component-level `useQuery` would be four more.
    A hand-named corpus is the shape this register counts, and it was one.
    """
    found = {}
    for path in sorted(DESIGN.rglob("*")):
        if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
            continue
        if ENGINE in path.parents:
            continue
        source = path.read_text(encoding="utf-8")
        addresses = set(re.findall(r'queryKey:\s*\[\s*"([^"]+)"', source))
        addresses |= {value for name, value in
                      re.findall(r'^export const (\w*[Kk]ey) = .*?\["([^"]+)"',
                                 source, re.MULTILINE)}
        # `useSystemRead(address)` keys on its argument, so the addresses are
        # the literals handed to it — read them rather than reporting a
        # variable, which would be an address this arm cannot check.
        # `useSystemRead<Fact[]>("…")` keys on its argument. The generic used
        # to be matched with `[^>]*`, which breaks on a NESTED one —
        # `useSystemRead<Record<string, Fact>>` yielded nothing, and seven of
        # the twenty-four addresses hang on this one pattern.
        addresses |= set(re.findall(
            r'useSystemRead<.*?>\(\s*"([^"]+)"', source, re.DOTALL))
        addresses |= set(re.findall(
            r'prefetchQuery\(\s*\{\s*queryKey:\s*\[\s*"([^"]+)"', source))
        # A CACHE KEY IS NOT ALWAYS SPELLED `queryKey:`. `app/engine-data.ts`
        # declares its four under `key:` in a table it hands to
        # `fetchQuery`/`setQueryData` — read by no version of this arm until
        # now, and every one of them an address a surface really holds.
        addresses |= set(re.findall(
            r'^\s*key:\s*\[\s*"(/api/[^"]+)"', source, re.MULTILINE))
        for address in addresses:
            found.setdefault(address, str(path.relative_to(ROOT)))
    return found


def arm_map_completeness():
    """Refuses an event or an address that is neither claimed nor exempted."""
    # THE COUNTER IS DECLARED BEFORE ANYTHING CAN ADD TO IT. Two defects in
    # this arm have now been a `violations` used before its assignment — the
    # first survived because its loop was empty, and only `make lint` could see
    # either. The declaration goes first, once.
    violations = 0
    emitted, disagreement = backend_events()
    if emitted is not None and disagreement is not None:
        print(f"  {disagreement}")
        violations += 1
    missing_source = disagreement if emitted is None else None
    if emitted is None:
        print(f"check-live-relay[map-completeness]: {missing_source} is not "
              "there — this arm compares against the backend's own event "
              "classes, and cannot answer without them.", file=sys.stderr)
        return 1
    mapped, exempt_types, refreshed, exempt_keys, tables, unresolved = declared()
    addresses = read_addresses()
    for where, name in unresolved:
        violations += 1
        print(f"  {where}: a rule names `{name}`, which no `const` in that file "
              "declares. Its key is unread, so the address it would refresh "
              "reads as unrefreshed or, worse, as covered by another rule.")

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
          f"{len(refreshed)} refreshed, {len(exempt_keys)} exempt, and the two "
          f"overlap by {len(refreshed & exempt_keys)}. AN ADDRESS CAN BE BOTH: "
          "a rule's prefix may already cover a read that an exemption also "
          "names, so the two counts sum past the total by exactly the overlap "
          "printed beside them rather than by an error")
    return 1 if violations else 0


def arm_wired():
    """Refuses a rules table that is written and never handed to the relay.

    `declared()` reads all nine `features/*/live.ts` and counts their keys as
    refreshed. `app/live-updates.ts` imports six. A table that is WRITTEN and
    never imported refreshes nothing, and every other arm here counts it as
    coverage — an address it names reads as accounted for while the events that
    would refresh it reach an empty table.

    R91 would catch it, by a hold falling on « refreshes something ». R91 is a
    browser rule in the wave gate; this runs in `make check` and in the
    per-pull-request tier. The difference is a fifteen-phase attribution
    interval, which is what the cheap tier exists to close.

    WHAT IT DOES NOT READ: whether the rules are RIGHT, or whether the relay is
    installed at all. It reads one edge — table declared, table composed.

    Returns:
        1 when a non-empty table is not composed, 0 otherwise.
    """
    composer = DESIGN / "app" / "live-updates.ts"
    if not composer.is_file():
        print(f"check-live-relay[wired]: {composer} is not there — this arm "
              "compares tables against their composition and has nothing to "
              "compare against.", file=sys.stderr)
        return 1
    # COMMENTS ARE NOT CODE. Both halves used to be satisfied by prose — and
    # this composer opens with a twenty-seven-line comment discussing exactly
    # these tables by name.
    source = re.sub(r"/\*.*?\*/", "", composer.read_text(encoding="utf-8"),
                    flags=re.DOTALL)
    source = "\n".join(re.sub(r"//.*$", "", line) for line in source.splitlines())
    violations, checked = 0, 0
    for path in sorted(FEATURES.glob("*/live.ts")):
        exported = re.search(r"^export const (\w+LiveRules)[^=]*=\s*\[(\s*)\]",
                             path.read_text(encoding="utf-8"), re.MULTILINE)
        name = re.search(r"^export const (\w+LiveRules)",
                         path.read_text(encoding="utf-8"), re.MULTILINE)
        if name is None:
            continue
        checked += 1
        if exported is not None:
            continue                      # an empty table composes nothing
        # THE IMPORT IS MATCHED ACROSS LINES. Requiring the identifier and the
        # word `from` on ONE physical line made a wrapped import — what a
        # formatter produces the moment a second name joins it — read as « not
        # composed », and a guard that names the wrong defect is worse than one
        # that stays quiet.
        imported = re.search(
            rf"import\s*\{{[^}}]*\b{name.group(1)}\b[^}}]*\}}\s*from",
            source, re.DOTALL)
        if imported is None or f"...{name.group(1)}" not in source:
            violations += 1
            print(f"  {path.relative_to(ROOT)}: `{name.group(1)}` is declared "
                  "and not composed in `app/live-updates.ts`. Its events reach "
                  "an empty table, its addresses read as covered, and every "
                  "other arm here reports clean.")
    if checked < TABLE_FLOOR:
        print(f"check-live-relay[wired]: {checked} table(s) against a floor of "
              f"{TABLE_FLOOR} — a corpus that has emptied reports the same word "
              "as a complete one.", file=sys.stderr)
        return 1
    print(f"check-live-relay[wired]: {checked} table(s) declared, "
          f"{violations} not composed")
    return 1 if violations else 0


ARMS = {
    "no-polling": arm_no_polling,
    "wired": arm_wired,
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
