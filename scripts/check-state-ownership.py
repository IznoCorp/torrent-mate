#!/usr/bin/env python3
"""Invariants 4 and 5 of the frontend plan: where state lives, and who fetches it.

  4. Server state is never copied into client state. Server data lives in its
     query cache, the address lives in the router, and only genuinely ephemeral
     interface state lives in a store.
  5. No data request inside a `useEffect`.

WHY THIS IS NOT AN ARM OF `check-frontend-boundaries.py`. That guard answers
« which module may import which », and these answer « where does a value live ».
Two subjects, two files — and the boundaries guard is 793 lines against a soft
ceiling of 800, so folding these in would have been a split somebody else had to
do later, on a line count instead of on a subject.

THE TWO ARMS HAVE OPPOSITE SHAPES, and that is the whole of what makes them
honest.

`server-state` STARTS ABOVE ZERO. The maquette's store is an open bag —
`type UiState = { page: string; [key: string]: unknown }` — so no type says what
is in it, and eleven of the thirty-nine keys written into it name server state.
The ceiling is refused UPWARD and lowered as surfaces convert. It cannot be
pre-satisfied: it has eleven real things to remove before it is at zero.

`effect-fetch` IS AT ZERO the day it is written, which is exactly the shape this
repository has paid for twenty-six times — a guard green because of what it does
not read. So it PRINTS ITS CORPUS and refuses a corpus below a declared floor. A
run that found no `useEffect` at all would otherwise report « no violation » and
mean « I read nothing ».

WHAT NEITHER ARM READS, said before what they do:

  - A key written through a VARIABLE — `write({ [name]: value })` — cannot be
    classified. It is REFUSED rather than skipped, and the refusal says why.
  - WHICH SURFACE a key belongs to. The arm reads the engine AND the component
    tree — the first version read only the components, counted 4 against a
    ceiling of 11, and a ceiling above its own count can never fall. It prints
    the two shares apart, but it cannot say which wave owes which key; that is
    the plan's, per surface.
  - Whether a key that looks like interface state secretly carries server state.
    No arm can judge that. The two lists are named and reviewed; a key on
    neither list is a violation, so a new one cannot arrive unclassified.
  - A request made outside a `useEffect` and outside the query cache. That is
    invariant 4's business through the store, and the cache's through its own
    hooks; a sweep for every `fetch(` would flag the seam that implements them.
"""
import argparse
import pathlib
import re
import sys

DESIGN_SOURCE_ROOT = (pathlib.Path(__file__).resolve().parent.parent
              / "frontend" / "maquette" / "design" / "src")

# The buckets a component or a hook lives in.
COMPONENT_BUCKETS = ("app", "features", "lib", "routes", "ui", "mocks")

# THE ENGINE IS READ TOO, AND THE FIRST VERSION OF THIS ARM DID NOT READ IT.
# That version counted 4 against a ceiling of 11 — a ceiling above its own count
# is pre-satisfied and can never fall, which is B-075's shape exactly, and it was
# caught by asking « what does this NOT read? » rather than by a failure.
#
# The engine writes seven of the eleven, and they are just as much server state
# sitting in the interface's bag: components READ them (`state.phase`,
# `state.pipe`) whoever wrote them. They leave as their surface converts, and
# whatever is left dies with the engine at L13. So the ceiling is on the UNION,
# and the two shares are printed apart — a total that hid where its members lived
# would be the same defect one directory over.
ENGINE_SOURCES = ("engine/legacy.js", "engine/states.js")

# THE STORE KEYS THAT NAME SERVER STATE. Each one is a value a server owns, kept
# in the interface's own bag — invariant 4's violation, one per name. They leave
# as their surface is wired, and the ceiling below follows them down.
SERVER_STATE_KEYS = {
    "libCount": "how many library rows have been asked for — a page cursor",
    "libErr": "whether the library read failed — query state",
    "libLoading": "whether the library read is in flight — query state",
    "libFailedOnce": "whether the simulated failure has already fired",
    "sugCount": "how many suggestions have been asked for — a page cursor",
    "sugGone": "which suggestions have been dismissed — server state",
    "sugLoading": "whether the suggestion read is in flight — query state",
    "phase": "loading / error / ready — query state, for every surface at once",
    "added": "what the add screen has added — server state",
    "notFound": "whether a lookup found nothing — the answer to a read",
    "pipe": "what the pipeline is doing — server state",
}

# THE STORE KEYS THAT ARE GENUINELY THE INTERFACE'S. A key on neither list is a
# violation: that is what stops a new one arriving unclassified, and it is why
# this arm holds a NAMED INVENTORY rather than only a number.
INTERFACE_STATE_KEYS = {
    "page", "filter", "sugOrder", "q", "selMode", "selected", "acqTab",
    "sugMode", "resolveTarget", "panelOpen", "scen", "pill", "tmdb", "profile",
    "relatedTitle", "addQ", "addMode", "panelDescriptor", "kind", "too",
    "notes", "libLens", "libCat", "libMode", "followMode", "maintTopic",
    "sortKey", "sortReversed",
}

# What the union may be, and it is refused UPWARD. Lowered in the commit that
# converts a surface, never raised to let one through.
SERVER_STATE_CEILING = 11

# And the COMPONENT share separately, because the union alone cannot see a
# component newly copying a key the engine already writes: the union stays 11
# and the copy — which is invariant 4's violation in its purest form, server
# state written by the interface itself — passes. Measured by mutation, not
# reasoned: writing `pipe` from a component left the union at 11 and the run
# green, while the component share went 4 → 5.
COMPONENT_SHARE_CEILING = 4

# How many `useEffect` call sites the second arm must find before it may report
# anything at all. Raised as the tree grows; a corpus below it means the reader
# stopped reading, not that the tree got cleaner.
EFFECT_CORPUS_FLOOR = 3

# How a write into the interface's own store is spelled.
WRITE_CALLS = (r"writeUiState\s*\(\s*\{", r"__store\s*\.\s*write\s*\(\s*\{",
               r"\bstore\s*\.\s*write\s*\(\s*\{")

# What a data request looks like inside an effect's body. The query cache's own
# hooks are included: moving a read into an effect through `fetchQuery` is the
# same defect wearing the cache's name.
REQUEST_IN_EFFECT = (
    r"\bfetch\s*\(", r"\bread\s*<", r"\bread\s*\(", r"\bsend\s*\(",
    r"fetchQuery\s*\(", r"prefetchQuery\s*\(", r"ensureQueryData\s*\(",
)


def sources(root: pathlib.Path):
    """Yields every module a component or a hook may live in.

    Args:
        root: The `design/src` directory.

    Yields:
        (relative path, text) for each source, test files excluded — a test may
        legitimately write anything it wants into a fake store.
    """
    for bucket in COMPONENT_BUCKETS:
        for path in sorted((root / bucket).rglob("*")):
            if path.suffix not in (".ts", ".tsx") or not path.is_file():
                continue
            if path.name.endswith(".test.ts") or path.name.endswith(".test.tsx"):
                continue
            yield path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")


def blanked(source: str) -> str:
    """Blanks comments so a pattern cannot match prose.

    A guard that counted its own documentation is not hypothetical here: one
    did, and a named incident could be restored by writing it in a comment.

    Args:
        source: The module's text.

    Returns:
        The text with line and block comments replaced by spaces of equal length.
    """
    without_block = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), source,
                           flags=re.S)
    return re.sub(r"//[^\n]*", lambda m: " " * len(m.group(0)), without_block)


def balanced_span(source: str, opened_at: int, opener: str, closer: str) -> str:
    """Returns the text between one bracket and the one that closes it.

    Args:
        source: The text to walk.
        opened_at: The index of the opening bracket.
        opener: The opening bracket.
        closer: The closing bracket.

    Returns:
        The span, brackets excluded. Empty when it never closes.
    """
    depth = 0
    for index in range(opened_at, len(source)):
        if source[index] == opener:
            depth += 1
        elif source[index] == closer:
            depth -= 1
            if depth == 0:
                return source[opened_at + 1:index]
    return ""


def keys_written(source: str) -> tuple[list[str], list[str]]:
    """Reads the keys of every store-write literal in one module.

    Args:
        source: The module's text, comments already blanked.

    Returns:
        The key names found, and the sites whose key is COMPUTED — refused
        rather than skipped, because a key this arm cannot classify is a key
        that would otherwise leave the count meaning « the ones I could read ».
    """
    keys, computed = [], []
    for pattern in WRITE_CALLS:
        for match in re.finditer(pattern, source):
            brace = source.index("{", match.start())
            literal = balanced_span(source, brace, "{", "}")
            if re.search(r"\[[^\]]+\]\s*:", literal):
                computed.append(literal[:60])
                continue
            keys.extend(re.findall(r"(?:^|[,{\s])([A-Za-z_$][\w$]*)\s*:", literal))
    return keys, computed


def arm_server_state(root: pathlib.Path) -> int:
    """Counts the store keys that name server state, and refuses the count going up."""
    by_component: dict[str, set[str]] = {}
    by_engine: set[str] = set()
    unclassified: list[str] = []
    computed: list[str] = []

    for relative, text in sources(root):
        keys, unreadable = keys_written(blanked(text))
        computed.extend(f"{relative}: a computed key ({site}…) — this arm cannot "
                        f"classify it, so it refuses it" for site in unreadable)
        for key in keys:
            if key in SERVER_STATE_KEYS:
                by_component.setdefault(key, set()).add(relative)
            elif key not in INTERFACE_STATE_KEYS:
                unclassified.append(f"{relative}: `{key}` is on neither list — "
                                    f"classify it as server or interface state")

    engine_write_sites = 0
    for relative in ENGINE_SOURCES:
        path = root / relative
        if not path.is_file():
            unclassified.append(f"{relative} is missing — this arm read less than it "
                                f"was written to read")
            continue
        source = blanked(path.read_text(encoding="utf-8"))
        keys, _ = keys_written(source)
        engine_write_sites += sum(len(re.findall(pattern, source))
                                  for pattern in WRITE_CALLS)
        by_engine.update(key for key in keys if key in SERVER_STATE_KEYS)

    union = set(by_component) | by_engine
    count = len(union)
    print(f"  server-state: {count} server-state key(s) in the interface's store, "
          f"ceiling {SERVER_STATE_CEILING} — {len(by_component)} written by a "
          f"component, {len(by_engine)} by the engine over {engine_write_sites} "
          f"write site(s)")
    for key in sorted(union):
        where = sorted(by_component.get(key, set())) or ["the engine"]
        print(f"      {key}: {SERVER_STATE_KEYS[key]} — {', '.join(where)}")

    violations = sorted(set(unclassified)) + sorted(set(computed))
    if count > SERVER_STATE_CEILING:
        violations.append(
            f"{count} server-state key(s) against a ceiling of {SERVER_STATE_CEILING}: "
            f"this count is refused UPWARD and lowered as surfaces convert")
    if len(by_component) > COMPONENT_SHARE_CEILING:
        violations.append(
            f"{len(by_component)} server-state key(s) written by a COMPONENT against a "
            f"ceiling of {COMPONENT_SHARE_CEILING}: the interface is copying server state "
            f"itself, which is invariant 4 in its purest form — and the union above cannot "
            f"see it when the engine already writes the same key")
    for entry in violations:
        print("    " + entry, file=sys.stderr)
    return len(violations)


def arm_effect_fetch(root: pathlib.Path) -> int:
    """Refuses a data request inside a `useEffect`, and refuses an empty corpus."""
    corpus = 0
    violations: list[str] = []
    for relative, text in sources(root):
        source = blanked(text)
        for match in re.finditer(r"\buseEffect\s*\(", source):
            corpus += 1
            body = balanced_span(source, source.index("(", match.start()), "(", ")")
            for pattern in REQUEST_IN_EFFECT:
                if re.search(pattern, body):
                    violations.append(
                        f"{relative}: a `useEffect` body matches `{pattern}` — invariant 5. "
                        f"A read belongs to the query cache, which decides when to make it")
                    break

    print(f"  effect-fetch: {corpus} useEffect call site(s) read, "
          f"{len(violations)} violation(s), corpus floor {EFFECT_CORPUS_FLOOR}")
    # A GUARD THAT FOUND NOTHING AND ONE THAT READ NOTHING PRINT THE SAME LINE.
    # This is what tells them apart.
    if corpus < EFFECT_CORPUS_FLOOR:
        violations.append(
            f"only {corpus} useEffect call site(s) found against a floor of "
            f"{EFFECT_CORPUS_FLOOR} — this arm read less than it did last time, so its "
            f"« no violation » means nothing")
    for entry in violations:
        print("    " + entry, file=sys.stderr)
    return len(violations)


ARMS = {"server-state": arm_server_state, "effect-fetch": arm_effect_fetch}


def main() -> int:
    """Runs the requested arms over the maquette's tree."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=sorted(ARMS),
                        help="run one arm instead of both")
    parser.add_argument("--root", default=DESIGN_SOURCE_ROOT, type=pathlib.Path)
    arguments = parser.parse_args()

    if not arguments.root.exists():
        print(f"check-state-ownership: root not found: {arguments.root}", file=sys.stderr)
        return 2

    print(f"check-state-ownership: {arguments.root}")
    selected = [arguments.arm] if arguments.arm else sorted(ARMS)
    violations = sum(ARMS[name](arguments.root) for name in selected)
    if violations:
        print(f"check-state-ownership: {violations} violation(s)", file=sys.stderr)
        return 1
    print("check-state-ownership: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
