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
    # WHETHER THE DRAWER IS UP (L15). Its sibling `panelOpen` has been on this
    # list since the sheet moved, and for the same reason: a layer's open state
    # is what the operator has done on screen, and nothing a server told us. It
    # is asked of the STORE and never of the DOM — a caller asks in the middle
    # of its own task and the answer must be right at that instant, whatever
    # React has painted.
    "drawerOpen",
    # AND THE CONFIRMATION'S TWO (L15), for the same reason `panelOpen` and
    # `panelDescriptor` are here: a layer's open state and the FACTS it is
    # drawn from are what the interface is doing, not what a server said. The
    # descriptor carries a heading, blocks and actions — a producer's own
    # words about what it is about to do — and never a server's answer.
    "dialogOpen", "dialogDescriptor",
    # The add screen's two: which kind is being searched for, and which provider
    # the « identify by id » block names. Both are what the operator has chosen
    # on screen, and neither is anything a server told us. They were on NEITHER
    # list until an adversarial review of L09 read them: the arm could not see
    # the writes at all, so its promise that « a new key cannot arrive
    # unclassified » had already been broken three times over.
    "addKind", "idProv",
}

# What the union may be, and it is refused UPWARD. Lowered in the commit that
# converts a surface, never raised to let one through. It started at ELEVEN;
# L09 phase 6 took the Médiathèque's four — `libCount`, `libErr`, `libLoading`,
# `libFailedOnce`, all of them the query's — and the four names left this list
# with the keys, because a list that kept them would go on describing a store
# that no longer holds them.
SERVER_STATE_CEILING = 7

# And the COMPONENT share separately, because the union alone cannot see a
# component newly copying a key the engine already writes: the union stays 11
# and the copy — which is invariant 4's violation in its purest form, server
# state written by the interface itself — passes. Measured by mutation, not
# reasoned: writing `pipe` from a component left the union at 11 and the run
# green, while the component share went 4 → 5.
COMPONENT_SHARE_CEILING = 0

# THE ENGINE'S OWN CODE, LIVING IN A FEATURE'S DIRECTORY. L19 moved the dying
# engine's producers and its Découvrir feed to the features that own their
# subject, and the engine IMPORTS THEM BACK — `app/icons.ts`'s arrangement: one
# copy of every answer, read by both worlds, and the day the engine goes the
# feature loses an importer rather than a subject.
#
# Such a module is not a COMPONENT. It renders nothing, it is called from the
# engine's own render and its own delegation, and the store writes it carries
# are the writes the engine was already making, at the same moments. Counting
# them as « the interface copying server state » would be counting a relocation
# as a defect, and the wave that relocates would have to either leave the code
# in a file it is meant to empty or rewrite the paging — which is drawing, and
# L13's.
#
# WHAT MAKES THIS EXEMPTION CHECKABLE RATHER THAN A CLAIM, and it is the whole
# of it: an entry is honoured only while `engine/legacy.js` REALLY IMPORTS the
# module. Nobody can grant it to themselves by editing this list — the engine
# has to reach for the file — and the day the engine goes, every entry here
# stops being honoured on the same day, loudly, because the import goes with it.
# An entry naming a file the tree does not hold is refused outright.
ENGINE_OWNED = {
    "features/acquisition/discover-feed.ts": (
        "the discovery feed — the reserve, the pile and the gesture that spends "  # french-ok: none, and the page's own name is not written here for that reason
        "them. Its paging is by INDEX into a list it holds, and rewriting that "
        "is rewriting the deck (features/acquisition/queries.ts says so in its "
        "own words); it dies with the engine at L13."
    ),
}

# How many `useEffect` call sites the second arm must find before it may report
# anything at all. Raised as the tree grows; a corpus below it means the reader
# stopped reading, not that the tree got cleaner.
EFFECT_CORPUS_FLOOR = 5

# How a write into the interface's own store is spelled. THE CALL, not the call
# followed by a brace: requiring `({` meant a write whose argument was anything
# else — a variable, a spread, a one-line local wrapper — was not seen at all,
# and a wrapper is one line to write. Measured: `function write(patch) {
# writeUiState(patch); }` in `add-screen.tsx` made four component writes
# invisible, two of them of keys on neither list, under a green run.
# What marks the module that IMPLEMENTS the write, rather than one that calls
# it. Matched on the exported declaration, so a second module claiming the
# exemption would have to export a second `writeUiState` — which is a defect the
# `fan-in` and `one-address` arms would each have something to say about.
IS_THE_SEAM = "export function writeUiState"

WRITE_CALLS = (r"writeUiState\s*\(", r"__store\s*\.\s*write\s*\(",
               r"\bstore\s*\.\s*write\s*\(")

# What a data request looks like inside an effect's body. The query cache's own
# hooks are included: moving a read into an effect through `fetchQuery` is the
# same defect wearing the cache's name.
REQUEST_IN_EFFECT = (
    r"\bfetch\s*\(", r"\bread\s*<", r"\bread\s*\(", r"\bsend\s*\(",
    r"fetchQuery\s*\(", r"prefetchQuery\s*\(", r"ensureQueryData\s*\(",
    # WHAT AN INFINITE QUERY IS PAGED WITH. `\bfetch\s*\(` does not match
    # `fetchNextPage(` — the `\(` needs a bracket where there is an `N` — so the
    # commonest read in a paged surface was outside the arm entirely.
    r"fetchNextPage\s*\(", r"fetchPreviousPage\s*\(", r"\brefetch\s*\(",
)

# Where a request is a violation and where it is not. A read WRITTEN in the
# effect's own body runs when the effect runs — that is invariant 5. A read
# inside a callback the effect merely REGISTERS (an observer, a paging door, an
# event listener) runs when that callback is called, which is a gesture, and
# refusing it would forbid infinite scrolling altogether. So the nested
# functions are blanked before the body is read.
NESTED_FUNCTION = re.compile(r"(\([^()]*\)|[A-Za-z_$][\w$]*)\s*=>\s*|\bfunction\b[^{]*")


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


def top_level_parts(literal: str) -> list[str]:
    """Splits an object literal on its own commas, ignoring nested ones.

    Args:
        literal: The literal, braces included.

    Returns:
        One string per property, in order.
    """
    parts, depth, start = [], 0, 1
    for index in range(1, len(literal) - 1):
        character = literal[index]
        if character in "{[(":
            depth += 1
        elif character in "}])":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append(literal[start:index])
            start = index + 1
    parts.append(literal[start:len(literal) - 1])
    return [part for part in parts if part.strip()]


def keys_written(source: str) -> tuple[list[str], list[str]]:
    """Reads the keys of every store-write in one module.

    THREE SPELLINGS, and the arm used to read one. `{ pipe: value }` was read;
    `{ pipe }` — the ES6 shorthand, which is the canonical form — was not, and
    neither was a write whose argument is not a literal at all. Both were
    proven by mutation to leave a component writing named server state under a
    green run.

    Args:
        source: The module's text, comments already blanked.

    Returns:
        The key names found, and the sites this arm CANNOT read — refused
        rather than skipped, because a key it cannot classify is a key that
        would otherwise leave the count meaning « the ones I could read ».
    """
    keys, unreadable = [], []
    # THE SEAM ITSELF is not a wrapper. `store-access.ts` holds the one function
    # every component writes through, and it necessarily forwards a patch it did
    # not compose. Reading it as a call made the arm refuse the file that
    # provides the very seam it reads.
    if IS_THE_SEAM in source:
        return keys, unreadable
    for pattern in WRITE_CALLS:
        for match in re.finditer(pattern, source):
            before = source[max(0, match.start() - 40):match.start()]
            if re.search(r"\b(function|const|let|var)\s+$", before):
                continue
            opening = source.index("(", match.start())
            argument = balanced_span(source, opening, "(", ")").strip()
            if not argument.startswith("{"):
                # A VARIABLE, A CALL, A SPREAD — anything whose keys are not
                # written here. This is where the one-line wrapper lived.
                unreadable.append(f"a write whose argument is not a literal "
                                  f"({argument[:40]}…)")
                continue
            brace = source.index("{", opening)
            literal = "{" + balanced_span(source, brace, "{", "}") + "}"
            for part in top_level_parts(literal):
                body = part.strip()
                if body.startswith("..."):
                    unreadable.append(f"a spread inside a write ({body[:40]}…)")
                elif re.match(r"^\[[^\]]+\]\s*:", body):
                    unreadable.append(f"a computed key ({body[:40]}…)")
                elif named := re.match(r"^([A-Za-z_$][\w$]*)\s*:", body):
                    keys.append(named.group(1))
                elif shorthand := re.match(r"^([A-Za-z_$][\w$]*)$", body):
                    keys.append(shorthand.group(1))
                else:
                    unreadable.append(f"a property this arm cannot name "
                                      f"({body[:40]}…)")
    return keys, unreadable


# How an import specifier is spelled, in either of the two forms that reach one:
# `import … from "spec"` and the side-effect `import "spec"`. Read on the BLANKED
# text and captured, never searched for as a substring of the whole file — see
# `engine_imports`.
IMPORT_SPECIFIER = re.compile(r"""(?:^|[\s;}])(?:from|import)\s*["']([^"']+)["']""",
                              re.M)


def imported_specifiers(source: str) -> set[str]:
    """Every module specifier a source file really imports.

    Args:
        source: The module's text, comments and all.

    Returns:
        The specifiers, comments excluded.
    """
    return set(IMPORT_SPECIFIER.findall(blanked(source)))


def engine_imports(root: pathlib.Path, relative: str) -> bool:
    """Whether the dying engine really imports a module claiming to be its own.

    THE EXEMPTION IS ONLY AS GOOD AS THIS. A module may be listed in
    `ENGINE_OWNED` and mean nothing: what makes it the engine's is that the
    engine reaches for it. That is a fact in a file, not a claim in a list, and
    it expires by itself the day `legacy.js` goes.

    WHICH IS WHY THE FACT IS PARSED AND NOT SEARCHED FOR. This read used to ask
    whether the specifier appeared ANYWHERE in the engine's text, which a
    comment naming the path satisfies just as well as an import — and the engine
    is full of comments naming feature paths, so the exemption would have
    outlived the import that justifies it, silently, in the one file whose whole
    purpose is to shrink. The specifiers are extracted from the blanked source,
    so a commented-out import is exactly as dead here as a deleted one.

    Args:
        root: The tree being read.
        relative: The module's path, as `ENGINE_OWNED` writes it.

    Returns:
        True when `engine/legacy.js` imports it.
    """
    engine = root / "engine" / "legacy.js"
    if not engine.is_file():
        return False
    stem = "../" + relative.removesuffix(".ts").removesuffix(".tsx")
    # The same module can be spelled four ways by a resolver that fills in the
    # extension and the folder index; all four name one file, and none of them
    # is a prose mention.
    wanted = {stem, stem + ".js", stem + ".ts", stem + "/index"}
    return bool(wanted & imported_specifiers(engine.read_text(encoding="utf-8")))


def arm_server_state(root: pathlib.Path) -> int:
    """Counts the store keys that name server state, and refuses the count going up."""
    by_component: dict[str, set[str]] = {}
    by_engine: set[str] = set()
    unclassified: list[str] = []
    computed: list[str] = []

    for relative, text in sources(root):
        keys, unreadable = keys_written(blanked(text))
        computed.extend(f"{relative}: {site} — this arm cannot classify it, "
                        f"so it refuses it" for site in unreadable)
        engine_owned = relative in ENGINE_OWNED and engine_imports(root, relative)
        for key in keys:
            if key in SERVER_STATE_KEYS:
                if engine_owned:
                    by_engine.add(key)
                    continue
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

    # AN EXEMPTION NOBODY COUNTS is indistinguishable from an oversight, so the
    # list is PRINTED on every run — and an entry naming a file the tree does
    # not hold, or one the engine has stopped importing, is refused rather than
    # quietly skipped: a stale exemption has stopped describing anything.
    stale = sorted(
        name for name in ENGINE_OWNED
        if not (root / name).is_file() or not engine_imports(root, name))
    print(f"  engine-owned: {len(ENGINE_OWNED)} module(s) exempt because the dying "
          f"engine imports them back, {len(stale)} stale")
    for name in sorted(ENGINE_OWNED):
        print(f"      {name}: {ENGINE_OWNED[name]}")

    violations = sorted(set(unclassified)) + sorted(set(computed)) + [
        f"{name}: recorded as the engine's own and the engine does not import it "
        f"(or the file is gone) — the exemption has stopped describing anything"
        for name in stale]
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


def without_nested_functions(body: str) -> str:
    """Blanks every function declared inside a body, keeping its own statements.

    Args:
        body: The effect callback's text.

    Returns:
        The same text with each nested function's body replaced by spaces, so a
        search reads only what runs when the effect runs.
    """
    kept = list(body)
    index = 0
    while index < len(body):
        match = NESTED_FUNCTION.search(body, index)
        if match is None:
            break
        brace = body.find("{", match.end() - 1)
        if brace == -1:
            break
        # An arrow with an EXPRESSION body — `() => void listing.fetchNextPage()`
        # — has no brace of its own; the next brace belongs to something else.
        # Its own extent is the rest of the statement, so it is blanked to the
        # next top-level `;` or `)`.
        if body[match.end():brace].strip() not in ("", ")"):
            end = match.end()
            depth = 0
            while end < len(body) and not (depth == 0 and body[end] in ";,"):
                if body[end] in "({[":
                    depth += 1
                elif body[end] in ")}]":
                    if depth == 0:
                        break
                    depth -= 1
                end += 1
        else:
            span = balanced_span(body, brace, "{", "}")
            end = brace + len(span) + 2
        for position in range(match.start(), min(end, len(body))):
            kept[position] = " "
        index = max(end, match.end())
    return "".join(kept)


def arm_effect_fetch(root: pathlib.Path) -> int:
    """Refuses a data request inside a `useEffect`, and refuses an empty corpus."""
    corpus = 0
    violations: list[str] = []
    for relative, text in sources(root):
        source = blanked(text)
        # `useLayoutEffect` TOO, and it was outside the corpus entirely: the
        # string does not contain `useEffect`, so the arm neither checked those
        # bodies nor counted them — the floor that is its whole defence against
        # reading nothing was under-reporting on the day it landed.
        for match in re.finditer(r"\buse(?:Layout)?Effect\s*\(", source):
            corpus += 1
            body = balanced_span(source, source.index("(", match.start()), "(", ")")
            running = without_nested_functions(body)
            for pattern in REQUEST_IN_EFFECT:
                if re.search(pattern, running):
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
