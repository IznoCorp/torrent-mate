#!/usr/bin/env python3
"""Refuses the defect classes that let a module tree rot — one arm each.

Corpus: `frontend/maquette/design/src`, every `.ts`, `.tsx` and `.js` file.
**The production app under `frontend/src` is deliberately NOT read** — it is
ARCHIVED at switchover (`product-intent.md` §15), so a guard over it would
hold an object about to stop existing. That is the operator's arbitration of
2026-08-22, and it is the same carve-out the French guard already makes.

ARM `cycles` — an import cycle.

THE DEFECT CLASS. A cycle makes every other dependency rule unenforceable,
because the cycle *is* the violation: once A needs B and B needs A, no
statement about layering, ownership or fan-in can be true of either. It also
fails at runtime in a way that reads as anything but a cycle — one of the two
modules evaluates against a half-built namespace, so a binding is `undefined`
at exactly the moment something reads it.

Two lived here, and what they were is worth keeping. `data.ts` imported the
panel component for ONE type, and the panel component imported `data.ts` back
for its own — while a byte-identical declaration of that same type already
sat in `seams.ts`. The cycle's whole substance was a duplicate. The second
was a screen importing the navigation verb from the shell that renders that
screen; the verb knew only a path, so it belonged with the domain-free
helpers and never with the shell.

A TYPE-ONLY EDGE COUNTS. `import type` is erased at runtime, so a cycle made
of them cannot fail at boot — and it is still refused here, deliberately. It
is the shape both of the cycles above actually had, it says the same thing
about ownership that a value edge says, and « this one is only types » is an
exemption that would have kept both.

WHAT THE READER SEES, and it is the question worth asking of any guard: it
resolves every RELATIVE specifier — `import … from`, `export … from`, and a
bare side-effect `import "./x"`, which is a real edge and spells itself with
no `from` at all. A bare specifier (`react`, `@tanstack/store`) is not a
local edge and is ignored. Resolution tries the literal path, then the four
source extensions, then `/index.*`, and finally the `.js`-means-`.ts` form
the TypeScript bundler resolution uses — the engine imports its seam that
way, and a resolver blind to it would report a missing target as no edge at
all, which is the silent half of this failure mode.

An UNRESOLVED relative specifier is reported as its own violation rather than
dropped. A specifier that resolves to nothing is a broken import; counting it
as « no edge » is how a reader stays green over a tree it cannot read.

Exit code: 0 when every arm run is clean, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DESIGN_SRC = Path("frontend/maquette/design/src")

# The extensions a specifier may resolve to, in the order the bundler tries.
#
# `.d.ts` IS ON THE LIST, and it was not. A declaration file is a legitimate
# import target — the maquette's generated contract types are one — and a
# resolver blind to it reports « unresolved import », which this arm counts as
# a violation. That is the right posture for an import resolving to nothing;
# it is the wrong answer for an import resolving to a file the reader cannot
# see. It is tried LAST, so a `contract-types.ts` would still win over a
# `contract-types.d.ts` the way the bundler resolves it.
SOURCE_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".json", ".d.ts")

# Every local import shape. Group 1 is the specifier in each case:
#   `import x from "./a"` · `export { y } from "../b"` · `import "./c"`
IMPORT_PATTERN = re.compile(
    r"""(?:^|\n)\s*
        (?:import|export)\b
        (?:                        # either a binding list, then `from`
            [\s\S]*?\bfrom\s*
          |                        # or nothing at all — a side-effect import
            \s*
        )
        ["']([^"']+)["']""",
    re.VERBOSE,
)


def source_files(root: Path) -> list[Path]:
    """Collect every module file under a root, sorted for a stable report.

    Args:
        root: The directory to walk.

    Returns:
        Every `.ts`, `.tsx` and `.js` file below `root`, sorted by path.
    """
    found: list[Path] = []
    for extension in (".ts", ".tsx", ".js"):
        found.extend(root.rglob("*" + extension))
    return sorted(found)


def resolve(importer: Path, specifier: str) -> Path | None:
    """Resolve one relative specifier to the file it names.

    Args:
        importer: The file the specifier was written in.
        specifier: The specifier's text, relative (starting with a dot).

    Returns:
        The resolved file, or None when nothing on disk answers it.
    """
    target = (importer.parent / specifier).resolve()
    candidates = [target]
    candidates += [target.with_suffix(extension) for extension in SOURCE_EXTENSIONS]
    candidates += [target / ("index" + extension) for extension in SOURCE_EXTENSIONS]
    # `./seams.js` naming `seams.ts` — the bundler resolution the engine uses.
    if target.suffix in (".js", ".jsx"):
        candidates += [target.with_suffix(".ts"), target.with_suffix(".tsx")]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def build_graph(root: Path) -> tuple[dict[str, list[str]], list[str]]:
    """Resolve every relative import under a root into a directed graph.

    Args:
        root: The directory whose modules form the graph.

    Returns:
        `(edges, unresolved)` — the graph as `{module: [imported modules]}`
        with paths relative to `root`, and every relative specifier that
        resolved to nothing, each named with the file that wrote it.
    """
    absolute_root = root.resolve()
    edges: dict[str, list[str]] = {}
    unresolved: list[str] = []
    for file in source_files(root):
        name = str(file.relative_to(root))
        text = file.read_text(encoding="utf-8")
        targets: list[str] = []
        for specifier in IMPORT_PATTERN.findall(text):
            if not specifier.startswith("."):
                continue  # a package, not a local edge
            resolved = resolve(file, specifier)
            if resolved is None:
                unresolved.append(f"{name}: {specifier}")
                continue
            # AN IMPORT THAT LEAVES THE TREE is not a module of this graph.
            # It used to CRASH here, which was the right failure to have — the
            # guard refused to judge what it could not read. It is ANSWERED
            # rather than swallowed: outside imports are collected, and the
            # `tree` arm holds them against a named list.
            try:
                targets.append(str(resolved.relative_to(absolute_root)))
            except ValueError:
                OUTSIDE_IMPORTS.setdefault(name, set()).add(str(resolved))
        edges[name] = targets
    return edges, unresolved


def find_cycles(edges: dict[str, list[str]]) -> list[tuple[str, ...]]:
    """Walk the graph and collect every simple cycle, deduplicated.

    A cycle is reported once whatever the node it is entered from: the node
    sequence is rotated to start at its alphabetically smallest member before
    it is recorded, so `a → b → a` and `b → a → b` are one finding.

    Args:
        edges: The graph, `{module: [imported modules]}`.

    Returns:
        Each cycle as a tuple of module names, sorted.
    """
    cycles: set[tuple[str, ...]] = set()

    def walk(node: str, stack: list[str]) -> None:
        for target in edges.get(node, []):
            if target in stack:
                body = stack[stack.index(target) :]
                pivot = body.index(min(body))
                cycles.add(tuple(body[pivot:] + body[:pivot]))
            elif target in edges:
                walk(target, stack + [target])

    for node in edges:
        walk(node, [node])
    return sorted(cycles)


# WHAT MAY IMPORT FROM OUTSIDE `design/src`, and it is one file.
#
# `engine/engine-shape.ts` reads `frontend/maquette/fixture-projections.json` —
# the projection L08 DECLARED, which the seed builder and the correspondence
# guard read too. It inverts that declaration to hand contract-shaped data to
# the engine's own markup producers, and it dies with them at L13. Importing the
# declaration rather than copying it is the point: a copy is a second definition
# of one thing, and the drift between them would be invisible, each staying
# internally consistent while describing different data.
#
# NAMED HERE SO THE NEXT ONE IS A DECISION. The maquette BECOMES the app, so a
# module reaching outside the tree makes it non-self-contained.
OUTSIDE_IMPORTS_ALLOWED = {
    "engine/engine-shape.ts": {"frontend/maquette/fixture-projections.json"},
    # Its test reads the same declaration, and for the same reason: asking
    # the declaration what names must not survive is what keeps the
    # assertion from being a list in the test file that rots.
    "engine/engine-shape.test.ts": {"frontend/maquette/fixture-projections.json"},
    # The conformance test reads the CONTRACT itself, because that is its
    # subject: it holds what a handler answers against what the contract
    # requires, and the generated types cannot answer for it — a TypeScript type
    # carries no `required` list at runtime. Importing the contract rather than
    # restating its required fields is the same decision as the two above: a
    # copy is a second definition, and the drift between them is invisible.
    #
    # THIS ENTRY IS ALSO B-122's PROOF. That defect made the arm compare an
    # absolute path against a relative allowance, so it could not refuse a new
    # outside import on this machine at all. This one was refused the moment it
    # was written.
    "mocks/contract-conformance.test.ts": {"frontend/maquette/contract/openapi.json"},
}

# Filled by `build_graph`: importer -> the absolute paths it reaches outside the
# tree. Module level because several arms build the graph and each would
# otherwise re-derive it.
OUTSIDE_IMPORTS: dict[str, set[str]] = {}


def is_test(module: str) -> bool:
    """Tells whether a module is a test rather than something that ships.

    Args:
        module: The module's path, as the graph names it.

    Returns:
        True for a `*.test.ts` / `*.test.tsx`.
    """
    return module.endswith(".test.ts") or module.endswith(".test.tsx")


def arm_cycles(root: Path) -> int:
    """Report every import cycle, and every specifier that resolves to nothing.

    Args:
        root: The directory to read.

    Returns:
        The number of violations — cycles plus unresolved specifiers.
    """
    edges, unresolved = build_graph(root)
    cycles = find_cycles(edges)
    print(f"  cycles: {len(edges)} modules read, {len(cycles)} cycle(s)")
    for cycle in cycles:
        print("    " + " → ".join(cycle) + " → " + cycle[0], file=sys.stderr)
    for entry in unresolved:
        print(f"    unresolved import — {entry}", file=sys.stderr)
    return len(cycles) + len(unresolved)


# The buckets a file may live in, and what each one is for. A file outside
# them has no owner, which is the state the whole lot exists to end.
BUCKETS = {
    "app": "boot, providers, the router tree, the page host",
    "routes": "one address, one file — thin: it loads and composes",
    "features": "one folder per subject: its page, its screens, its slice",
    "ui": "primitives with no domain knowledge",
    "lib": "domain-free helpers that render nothing",
    "styles": "tokens and base (L06/L07)",
    "mocks": "handlers and fixture seeds (L08)",
    "i18n": "the interface's French, as resources",
    "engine": "LEGACY — the dying engine and what boots it. Dies with L13",
}

# A module outside `ui/` and `lib/` imported by more than this many FEATURES is
# refused. The number is the architecture file's own intent: it is the guard
# « that would have stopped `data.ts` at four importers instead of seventeen ».
# `ui/` and `lib/` are exempt by that same sentence, which is why the store
# hooks and the navigation door were put there rather than carved out here.
FAN_IN_CEILING = 4

# What `mocks/` may not reach. It may read `lib/` — domain-free helpers — and
# its own seeds, and nothing else.
MOCKS_MAY_NOT_IMPORT = ("features", "routes", "engine", "ui", "app", "styles", "i18n")

# Invariant 6. A file at or above the block ceiling must be listed below with
# the lot that converts it; the soft ceiling only warns.
BLOCK_LINES = 400
WARN_LINES = 250

# Files over the block ceiling, each with the lot that OWES the reduction. The
# membership is generated by `--arm size --list-grandfathered`, never
# maintained by hand: a list typed out drifts from the tree it describes, and
# this repository has already watched a hand-kept number drift by seven inside
# the pull request that introduced it as a control.
#
# THE LABEL IS NOT A COMMENT, and it used not to be read at all (B-073). The
# arm was careful about the list's composition — it refuses a file over the
# ceiling with no entry, and an entry for a file back under it — and never once
# looked at the VALUE. Four entries named L07 for two waves after L07 landed,
# and all four had GROWN in it. A label naming a lot that is already `LANDED`
# promises a reduction nobody owes any more.
#
# So the value names the lot that STILL owes it, and only that lot. « L07, then
# L09 » was the shape that hid the defect: a label carrying two lots, one spent
# and one owed, with nothing to say which was which.
# A file NOBODY WRITES is not a module of this tree, and the size ceiling does
# not apply to it. Invariant 6's reason is « an agent modifying a component
# opens one file »; a generated artefact is opened by no one and edited by no
# one, so a ceiling on it would say nothing about the tree's health and would
# only ever be answered by a grandfather entry promising a reduction nobody
# owes.
#
# WHAT MAKES THIS EXEMPTION SAFE RATHER THAN A HOLE, and it is the whole
# difference: it is not a path someone may add themselves to. The value names
# the command that produces the file and the two checks that hold it — one
# regenerating it byte for byte where the generator is installed, one holding it
# against the contract by structure wherever this guard runs. Naming only the
# first left the exemption unproven on every machine that reads it, which is the
# same distance between a proof and a claim the whole lot is about.
GENERATED = {
    "mocks/contract-types.d.ts": (
        "npm run generate-contract-types — from frontend/maquette/contract/openapi.json. Held two ways: `make check-contract-types` regenerates it and refuses any difference, which needs the generator and runs only where it is installed; and `scripts/check-mock-seeds.py --arm generated` holds it against the contract by structure, needs neither node nor the generator, and runs wherever the guards do — which is where THIS exemption is read."
    ),
}

GRANDFATHERED = {
    "engine/legacy.js": "L13 — the engine dies by subtraction, surface by surface",
    "engine/states.js": "L13 — the scenario table goes with the engine it drives",
    "features/acquisition/page.tsx": "L09 — the data layer takes it (L07 converted the surface)",
    "features/library/page.tsx": "L09 — the data layer takes it (L07 converted the surface)",
    "features/media/media-screen.tsx": "L09 — the data layer takes it (L07 converted the surface)",
    "features/arrivals/resolution-screen.tsx": "L09 — the data layer takes it (L07 converted the surface)",
}

# The plan is the authority on a lot's status, and it says it in one word.
# `#### L07 — Tailwind and CVA, surface by surface · `LANDED` · *depended on …*`
#
# ANCHORED ON THIS FILE, not on the working directory. `--root` exists so the
# arms can be pointed at a copy of the tree, and the tests do exactly that from
# a scratch directory — but the PLAN is one document wherever the corpus is. A
# relative path here made the arm exit 1 from any directory but the repository
# root, blaming the plan for being unreadable: « unreadable is a violation »
# turns a wrong path into a hard failure with a message that names the wrong
# culprit.
# The repository root, so a path can be NAMED the way the allowance list
# writes it whatever the checkout is called.
REPOSITORY = Path(__file__).resolve().parent.parent
PLAN = REPOSITORY / "docs" / "reference" / "frontend-architecture.md"
LOT_HEADING = re.compile(r"^####\s+(L\d\d)\b[^\n]*?·\s*`(NOT STARTED|IN PROGRESS|LANDED)`", re.M)

# THE LABEL'S GRAMMAR: the lot that OWES the reduction, then a dash, then why.
# Anchored at the start on purpose. A label may go on to mention a lot that has
# already run — « L09 … (L07 converted the surface) » is worth keeping, because
# the reader wants to know a conversion already happened — and reading every
# mention would refuse exactly that sentence. What may never be spent is the
# lot the entry LEADS with: that one is the promise.
#
# « L07, then L09 » is the shape this refuses, and it is the shape all four
# entries wore. The debt is owed by ONE lot; a label carrying two, with nothing
# saying which half is spent, is what let the promise expire unnoticed.
OWED_LOT = re.compile(r"^(L\d\d)\b")


def plan_lots() -> tuple[set[str], set[str]]:
    """Read the lots the plan declares, and which of them have landed.

    BOTH SETS, and the first one is not decoration. Holding a label only
    against the LANDED set leaves « L19 — the data layer takes it » green for
    ever: the plan declares L01 to L13 and nothing else, so a lot that will
    never run is a promise nobody can call in — B-073's own defect wearing a
    different disguise.

    Returns:
        A `(declared, landed)` pair of lot codes. BOTH EMPTY when the plan
        cannot be read — and the caller treats that as its own violation
        rather than as « no lot has landed », which is the reading that would
        make this hold pass for the one reason it must never pass for.
    """
    if not PLAN.is_file():
        return set(), set()
    found = LOT_HEADING.findall(PLAN.read_text(encoding="utf-8"))
    return {lot for lot, _ in found}, {lot for lot, status in found if status == "LANDED"}


def feature_of(module: str) -> str | None:
    """Name the feature a module belongs to, or None when it is not in one.

    Args:
        module: A path relative to the corpus root, POSIX-style.

    Returns:
        The feature's folder name, or None for `app/`, `ui/`, `lib/`, …
    """
    parts = module.split("/")
    return parts[1] if len(parts) > 2 and parts[0] == "features" else None


def bucket_of(module: str) -> str:
    """Name the top-level bucket a module lives in."""
    return module.split("/")[0]


def arm_layering(root: Path) -> int:
    """Refuse `ui/` or `lib/` importing a feature, and one feature importing another.

    Args:
        root: The directory to read.

    Returns:
        The number of forbidden edges.
    """
    edges, _ = build_graph(root)
    violations = []
    for source, targets in sorted(edges.items()):
        source_bucket = bucket_of(source)
        source_feature = feature_of(source)
        for target in sorted(set(targets)):
            target_bucket = bucket_of(target)
            if source_bucket in ("ui", "lib") and target_bucket in ("features", "routes"):
                violations.append(f"{source} → {target} ({source_bucket}/ must know no feature)")
            target_feature = feature_of(target)
            if source_feature and target_feature and source_feature != target_feature:
                violations.append(
                    f"{source} → {target} (two features never import each other; "
                    f"they compose in the route)")
    print(f"  layering: {len(edges)} modules read, {len(violations)} forbidden edge(s)")
    for entry in violations:
        print("    " + entry, file=sys.stderr)
    return len(violations)


# THE ONE MODULE EVERY WIRED SURFACE IMPORTS, and it is exempt because that is
# its subject rather than a symptom. `engine/engine-shape.ts` inverts the
# projection L08 declared, so that data from the mock layer can be handed to the
# markup producers still living in `legacy.js`. Every surface L09 wires needs it,
# by construction — and it DIES WITH THOSE PRODUCERS at L13, taking this
# exemption with it.
#
# It is not in `ui/` or `lib/`, which the arm already skips, because lifetime is
# what decides where it lives: `engine/` is the bucket L13 empties, and a
# conversion INTO the engine's shape has no meaning after the engine.
#
# AND HERE IS THE ARGUMENT AGAINST IT, because an exemption that only records its
# own defence is half a record. This arm is the one guard that acts BEFORE the
# defect exists — the plan calls it « the one that would have stopped `data.ts`
# at four importers instead of seventeen » — and this module sits at 13 against a
# ceiling of 4. « It dies at L13 » is available to anything, and L13 has three
# unstarted lots in front of it; it is the argument `data.ts` could have made.
#
# What makes it different, and it is the whole of the difference: `data.ts` was a
# hub of DATA, so every importer was coupled to every other through the values it
# held. This is one exported pure function over a declaration — no state, no
# ordering, nothing an importer can observe about another importer. A god module
# couples; a shared pure conversion does not.
#
# That is a judgement, not a measurement, so it is the OPERATOR'S to confirm and
# it is written here to be found rather than argued once in a commit message. If
# the answer is no, the split is per family and it is mechanical.
FAN_IN_EXEMPT = frozenset({"engine/engine-shape.ts"})


def arm_fan_in(root: Path) -> int:
    """Refuse a module outside `ui/` and `lib/` that too many features import.

    Args:
        root: The directory to read.

    Returns:
        The number of modules over the ceiling.
    """
    edges, _ = build_graph(root)
    importers: dict[str, set[str]] = {}
    for source, targets in edges.items():
        for target in set(targets):
            if bucket_of(target) in ("ui", "lib"):
                continue
            if target in FAN_IN_EXEMPT:
                continue
            importers.setdefault(target, set()).add(feature_of(source) or bucket_of(source))
    over = {m: f for m, f in importers.items() if len(f) > FAN_IN_CEILING}
    highest = max((len(f) for f in importers.values()), default=0)
    print(f"  fan-in: ceiling {FAN_IN_CEILING} feature(s), highest is {highest}, "
          f"{len(over)} over")
    for module, features in sorted(over.items()):
        print(f"    {module} imported by {len(features)} features: "
              f"{', '.join(sorted(features))}", file=sys.stderr)
    return len(over)


def arm_size(root: Path, listing: bool = False) -> int:
    """Refuse a module over the ceiling that is not grandfathered with its lot.

    Args:
        root: The directory to read.
        listing: When true, print the grandfathered list as it would be
            regenerated and refuse nothing — the list is derived, never typed.

    Returns:
        The number of files over the block ceiling with no recorded lot.
    """
    sizes = {}
    for file in source_files(root):
        module = file.relative_to(root).as_posix()
        if module in GENERATED:
            continue
        sizes[module] = sum(1 for line in file.read_text(encoding="utf-8").splitlines()
                            if line.strip())
    over = {m: n for m, n in sizes.items() if n >= BLOCK_LINES}
    warn = {m: n for m, n in sizes.items() if WARN_LINES <= n < BLOCK_LINES}
    if listing:
        print("  GRANDFATHERED = {")
        for module, count in sorted(over.items(), key=lambda kv: -kv[1]):
            lot = GRANDFATHERED.get(module, "?? — NO LOT RECORDED")
            print(f'      "{module}": "{lot}",   # {count} non-blank lines')
        print("  }")
        return 0
    unrecorded = sorted(m for m in over if m not in GRANDFATHERED)
    stale = sorted(m for m in GRANDFATHERED if m not in over)

    # THE LABEL IS READ (B-073). Membership was held from both ends and the
    # VALUE from neither, so four entries promised a lot that had landed.
    declared_lots, landed = plan_lots()
    spent: list[str] = []
    unnamed: list[str] = []
    invented: list[str] = []
    for module in sorted(GRANDFATHERED):
        if module not in over:
            continue                      # already reported as stale, above
        owed = OWED_LOT.match(GRANDFATHERED[module])
        if owed is None:
            unnamed.append(module)
            continue
        if owed.group(1) not in declared_lots and declared_lots:
            invented.append(f"{module} — its label leads with {owed.group(1)}, "
                            f"which the plan does not declare")
        elif owed.group(1) in landed:
            spent.append(f"{module} — its label leads with {owed.group(1)}, already `LANDED`")
    unreadable = not landed

    # An exemption nobody counts is indistinguishable from an oversight, so the
    # generated files are PRINTED on every run rather than merely skipped — and
    # an entry naming a file that is not there is a violation, because a stale
    # exemption is one that has stopped describing the tree.
    absent = sorted(name for name in GENERATED if not (root / name).is_file())
    print(f"  size: ceiling {BLOCK_LINES}, {len(over)} at or over it "
          f"({len(GRANDFATHERED)} recorded; the plan declares {len(declared_lots)} lot(s), "
          f"{len(landed)} of them LANDED), {len(warn)} above the {WARN_LINES} warning, "
          f"{len(GENERATED)} generated file(s) exempt")
    for name in absent:
        print(f"    {name}: recorded as generated and is not in the tree — the "
              f"exemption has stopped describing anything", file=sys.stderr)
    for module in sorted(warn):
        print(f"    [WARN] {module}: {warn[module]} non-blank lines", file=sys.stderr)
    for module in unrecorded:
        print(f"    {module}: {over[module]} non-blank lines, over the ceiling and "
              f"recorded against no lot", file=sys.stderr)
    for module in stale:
        print(f"    {module}: recorded as grandfathered and is no longer over the "
              f"ceiling — the list describes a tree that has moved", file=sys.stderr)
    for entry in spent:
        print(f"    {entry}: the lot that would have reduced it has been and gone, so "
              f"the entry promises nothing. Re-label it with the lot that OWES the "
              f"reduction, or let the ceiling refuse the file", file=sys.stderr)
    for entry in invented:
        print(f"    {entry}: a lot that will never run is a promise nobody can call in",
              file=sys.stderr)
    for entry in unnamed:
        print(f"    {entry}: its label leads with no lot, and a label nobody can act on "
              f"is the state B-073 found this list in", file=sys.stderr)
    if unreadable:
        # NOT « no lot has landed ». A reader that finds nothing and reports
        # clean is the exact shape this arm was written to end: the hold would
        # pass for the one reason it must never pass for.
        print("    docs/reference/frontend-architecture.md: no lot status could be read, so « the label leads "
              "with a lot that has not landed » is a sentence this arm cannot check",
              file=sys.stderr)
    return (len(unrecorded) + len(stale) + len(spent) + len(unnamed)
            + len(invented) + len(absent) + int(unreadable))


# `any` in a type position, an assertion to it, and the two suppressions. Not
# the WORD `any`, which is ordinary prose — this reads the type syntax around
# it, so a comment saying « any component » is not a violation.
TYPING_ESCAPES = (
    re.compile(r":\s*any\b"),
    re.compile(r"\bas\s+any\b"),
    re.compile(r"<any\b"),
    re.compile(r"@ts-ignore"),
    re.compile(r"@ts-expect-error"),
)


def arm_typing(root: Path) -> int:
    """Refuse `any` and the type-checker suppressions, from a floor of zero.

    The engine is exempt and it is the only exemption: `legacy.js` is
    JavaScript that `tsc` does not check at all, so the question does not
    arise there. It dies with L13.

    Args:
        root: The directory to read.

    Returns:
        The number of escapes found.
    """
    found = []
    for file in source_files(root):
        module = file.relative_to(root).as_posix()
        if bucket_of(module) == "engine":
            continue
        for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
            for pattern in TYPING_ESCAPES:
                if pattern.search(line):
                    found.append(f"{module}:{number}: {line.strip()[:70]}")
    print(f"  typing: {len(found)} escape(s) — the floor is a hard zero")
    for entry in found:
        print("    " + entry, file=sys.stderr)
    return len(found)


def arm_duplicate_import(root: Path) -> int:
    """Refuse one file importing the same module twice.

    It is the symptom the hub left behind — six files imported `data.ts` once
    for its types and once for its values — and it survives its cause, so it
    is held on its own.

    Args:
        root: The directory to read.

    Returns:
        The number of (file, module) pairs imported more than once.
    """
    edges, _ = build_graph(root)
    duplicates = []
    for source, targets in sorted(edges.items()):
        seen: dict[str, int] = {}
        for target in targets:
            seen[target] = seen.get(target, 0) + 1
        duplicates += [f"{source} imports {t} {n} times" for t, n in sorted(seen.items()) if n > 1]
    print(f"  duplicate-import: {len(duplicates)} pair(s)")
    for entry in duplicates:
        print("    " + entry, file=sys.stderr)
    return len(duplicates)


def arm_one_address(root: Path) -> int:
    """Refuse a route file declaring more than one path, or an address declared twice.

    Args:
        root: The directory to read.

    Returns:
        The number of violations.
    """
    routes = root / "routes"
    violations = []
    addresses: dict[str, list[str]] = {}
    files = sorted(routes.glob("*.tsx")) + sorted(routes.glob("*.ts")) if routes.is_dir() else []
    for file in files:
        module = file.relative_to(root).as_posix()
        declared = re.findall(r'^\s*path:\s*"([^"]+)"', file.read_text(encoding="utf-8"), re.M)
        if len(declared) > 1:
            violations.append(f"{module} declares {len(declared)} paths: {', '.join(declared)}")
        for address in declared:
            addresses.setdefault(address, []).append(module)
    for address, holders in sorted(addresses.items()):
        if len(holders) > 1:
            violations.append(f'the address "{address}" is declared in {", ".join(holders)}')
    print(f"  one-address: {len(files)} route file(s), {len(addresses)} address(es), "
          f"{len(violations)} violation(s)")
    for entry in violations:
        print("    " + entry, file=sys.stderr)
    return len(violations)


# THE ADDRESS MODEL'S ARM LIVES IN ITS OWN FILE. It carries a reader for
# JavaScript object literals and a bracket-matcher over the engine's page
# table — 560 lines of machinery no other arm here touches — and this file was
# 79 lines from a hard ceiling that exits 1. Split on the SUBJECT, so the two
# halves each answer one question: this one reads imports and file sizes, that
# one reads what the source is allowed to DECLARE as an address.
from boundaries_addressing import arm_addressing  # noqa: E402




def echoed_ancestor(relative: str, ancestors: set[str], corpus: str) -> str | None:
    """Name the ancestor directory a path re-uses the name of, or None.

    A tree copied under its own path is the shape this reads: eleven tracked
    files sat at `design/frontend/maquette/design/src/…` for two waves, read by
    nothing, drifting from the originals they mirrored — and three of them had
    already stopped agreeing with the live file at the same name (B-065). It
    lied to no gate, because every reader roots at `design/src` and never sees
    it; what it does is answer a future search with a stale contract at a
    plausible address.

    THE REPETITION IS ONLY VISIBLE FROM ABOVE, and that is the whole reason
    this takes the ancestors as an argument. Read from `design/` alone the copy
    spells `frontend/maquette/design/src/…` — five distinct segments, nothing
    repeated, and a first version of this hold reported it clean. What repeats
    is the enclosing tree's OWN name, one level down.

    Args:
        relative: A path relative to the corpus's parent, POSIX-style.
        ancestors: The directory names the corpus's parent lives in.
        corpus: The corpus directory's own name — `src`.

    Returns:
        The re-used ancestor name, or None when no directory echoes one.
    """
    segments = relative.split("/")[:-1]
    # The corpus itself opens the path of every file it holds, and that first
    # `src/` is where the files are SUPPOSED to be. A second one below it is
    # the same defect wearing the other half of the address.
    if segments and segments[0] == corpus:
        segments = segments[1:]
    for segment in segments:
        if segment == corpus or segment in ancestors:
            return segment
    return None


def arm_tree(root: Path) -> int:
    """Refuse a file outside every declared bucket, `data.ts` returning, or a tree copied under itself.

    Args:
        root: The directory to read.

    Returns:
        The number of files with no bucket, plus one if the hub is back, plus
        one per source file sitting under a repeated directory name.
    """
    strays = []
    for file in source_files(root):
        module = file.relative_to(root).as_posix()
        if "/" not in module:
            strays.append(f"{module} — a loose file at the root belongs to no bucket")
        elif bucket_of(module) not in BUCKETS:
            strays.append(f"{module} — « {bucket_of(module)}/ » is not a declared bucket")
    hub = (root / "data.ts").exists()
    if hub:
        strays.append("data.ts is back — it is not slimmed, it stops existing")

    # READ ABOVE THE CORPUS, deliberately. Every other hold here roots at
    # `design/src`, and that is exactly why a copy of `design/src` sitting at
    # `design/frontend/maquette/design/src` was invisible to all of them for
    # two waves: it is not IN the corpus, it is BESIDE it wearing its name.
    #
    # `node_modules/` and `dist/` are SKIPPED BY NAME, and the skip is not
    # tidiness: `source_files()` walks everything below its root, a dependency
    # tree passes through a hundred repeated directory names, and an arm that
    # reported those would be muted within a day. They are also the two
    # directories nobody edits.
    enclosing = root.parent
    ignored = {"node_modules", "dist"}
    ancestors = {part for part in enclosing.parts if part not in ("/", "..", ".")}
    nested = 0
    if enclosing.is_dir():
        for file in source_files(enclosing):
            relative = file.relative_to(enclosing).as_posix()
            if ignored & set(relative.split("/")[:-1]):
                continue
            echoed = echoed_ancestor(relative, ancestors, root.name)
            if echoed is not None:
                nested += 1
                strays.append(
                    f"{relative} — a directory under {enclosing.as_posix()}/ is named "
                    f"« {echoed}/ » again: a tree copied under its own path is read by "
                    f"nothing and drifts from the one it mirrors")
    # AN IMPORT THAT LEAVES THE TREE, held against a named list. It used to make
    # `build_graph` CRASH, which was the right failure to have — the guard
    # refused to judge what it could not read — and this answers it rather than
    # swallowing it. The maquette BECOMES the app, so a module reaching outside
    # `design/src` makes it non-self-contained, and the next one is a decision.
    build_graph(root)
    for importer, reached in sorted(OUTSIDE_IMPORTS.items()):
        allowed = OUTSIDE_IMPORTS_ALLOWED.get(importer, set())
        for target in sorted(reached):
            # NAMED FROM THE REPOSITORY ROOT, computed — not by cutting the
            # path on this checkout's own DIRECTORY NAME. It used to split on
            # « PersonalScraper/ », which is what the operator's clone happens
            # to be called; the CI runner checks out into `torrent-mate/`, the
            # split matched nothing, and every allowed reach was compared as an
            # ABSOLUTE path against a relative allowance. Two violations there,
            # none here, over an identical tree — a guard that answers
            # differently by machine is measuring the machine.
            relative = str(Path(target).resolve().relative_to(REPOSITORY))
            if relative not in allowed:
                strays.append(
                    f"{importer} imports {relative}, outside `design/src`. Add it to "
                    f"OUTSIDE_IMPORTS_ALLOWED with its reason, or keep it inside.")
    print(f"  outside-imports: {len(OUTSIDE_IMPORTS)} module(s) reach outside the tree, "
          f"{len(OUTSIDE_IMPORTS_ALLOWED)} named")
    print(f"  tree: {len(BUCKETS)} declared bucket(s), {len(strays)} file(s) outside them "
          f"({nested} under a repeated directory)")
    for entry in strays:
        print("    " + entry, file=sys.stderr)
    return len(strays)



# THE ONE FILE UNDER `mocks/` THAT IS NOT A MOCK, and the exemption is narrow on
# purpose. `mocks/contract-types.d.ts` is GENERATED from
# `frontend/maquette/contract/openapi.json` — it describes the CONTRACT, not a
# fixture, and it happens to sit in this bucket because that is where L08's
# generator writes it. Its placement is questionable and is recorded as such
# (B-104); moving it is a rename with five ends and belongs to its own change,
# not to the phase that first needed to import it.
#
# WHAT MAKES THE EXEMPTION SAFE IS THE TYPE-ONLY CONDITION, not the file name.
# The defect this arm exists to refuse is a module reading a SEED directly, so
# that a fixture survives its own removal while the rendering stays identical.
# A `.d.ts` carries no runtime value at all and a type-only edge is erased by
# the compiler, so nothing can travel it — the same reasoning `app/reference.d.ts`
# already states for its own type-only imports of every feature.
# Matched on the STEM so the graph's own spelling of a `.d.ts` module —
# `mocks/contract-types.d.ts`, `mocks/contract-types.d` or
# `mocks/contract-types` depending on how it was resolved — cannot make
# this exemption silently miss and the guard silently refuse.
CONTRACT_TYPES_EXEMPT = ("mocks/contract-types",)


def type_only_import(root: Path, source: str, target: str) -> bool:
    """Tells whether a module imports another with `import type` and nothing else.

    A VALUE import of the same file would be refused: the exemption is about
    what can travel the edge, never about which file is at its end.

    Args:
        root: The directory being read.
        source: The importing module, as the graph names it.
        target: The imported module, as the graph names it.

    Returns:
        True when every import of `target` in `source` is type-only.
    """
    # The graph names a module by its path WITH its suffix, so nothing is
    # appended here. A first version added one and looked for
    # `lib/query-client.ts.ts`, found nothing, and answered « not type-only » —
    # a reader that misses its target answers the safe-looking thing.
    path = root / source
    if not path.is_file():
        return False
    leaf = target.rsplit("/", 1)[-1].removesuffix(".ts").removesuffix(".d")
    text = path.read_text(encoding="utf-8")
    found = re.findall(rf"^\s*import\s+(type\s+)?[^;]*?['\"][^'\"]*{re.escape(leaf)}['\"]",
                       text, re.MULTILINE)
    return bool(found) and all(kind for kind in found)


def arm_mocks(root: Path) -> int:
    """Refuse anything but `app/` importing `mocks/`, and `mocks/` importing a feature.

    AND THE OTHER DIRECTION IS THE ENGINE. The layer keeps its own copy of the
    frozen clock precisely because the engine dies and a layer importing it
    would die with it — and a harness rule compares the two. Let `mocks/` import
    `engine/` and that rule compares a value against its own source, which is
    vacuously true forever. `ui/` is refused for the layering reason: a mock
    layer that knew a component would be a second place where a surface's shape
    is decided.

    THE DEFECT CLASS, and it is L09's whole proof at stake. A feature importing
    a mock seed directly is how a fixture survives its own removal: the surface
    renders identically, the seed is never wired through the network seam, and
    « the oracle proves the wiring at zero divergence » becomes a sentence about
    nothing. It has to be refused before it can happen, because afterwards it is
    invisible — the rendering is the same either way.

    The other direction is the layering rule read once more: a mock layer that
    knew a feature would be a second place where a surface's shape is decided.

    Args:
        root: The directory to read.

    Returns:
        The number of forbidden edges.
    """
    edges, _ = build_graph(root)
    violations = []
    importers = 0
    for source, targets in sorted(edges.items()):
        source_bucket = bucket_of(source)
        for target in sorted(set(targets)):
            if (any(target.startswith(exempt) for exempt in CONTRACT_TYPES_EXEMPT)
                    and type_only_import(root, source, target)):
                continue
            # A TEST MAY READ A SEED, and that is the opposite of the defect
            # this arm refuses. The defect is a COMPONENT reading one: it would
            # render identically while never going through the network seam, so
            # nothing would measure the wiring. A test reading the committed
            # seed is the oracle OUTSIDE the tool — the artefact is held byte
            # for byte against `legacy.js` by `check-mock-seeds.py`, and
            # asserting against anything else would be asserting against the
            # code under test. A test renders nothing and ships nowhere.
            if is_test(source):
                continue
            if bucket_of(target) == "mocks" and source_bucket not in ("mocks", "app"):
                violations.append(
                    f"{source} → {target}: only `app/` may import `mocks/` — a feature "
                    f"reading a seed directly never goes through the network seam, and "
                    f"then nothing measures the wiring")
            if bucket_of(target) == "mocks" and source_bucket == "app":
                importers += 1
            if source_bucket == "mocks" and bucket_of(target) in MOCKS_MAY_NOT_IMPORT:
                violations.append(
                    f"{source} → {target}: `mocks/` may read `lib/` and its own seeds, and "
                    f"nothing else. Importing `{bucket_of(target)}/` from here is what the "
                    f"decision behind the layer's own copies forbids — a clock read from the "
                    f"dying engine would make the rule that compares the two vacuously true")
    # A COUNT PRINTED AND NEVER COMPARED is the shape the ratchet doctrine
    # names. Zero importers means the layer is wired to nothing, which is the
    # state a deleted boot line or a botched build produces — and it passed.
    if importers < 1:
        violations.append(
            "no module under `app/` imports `mocks/` — the layer is built and wired to "
            "nothing, and a guard that only counts cannot tell that from a healthy tree")
    print(f"  mocks: {importers} import(s) from app/, {len(violations)} forbidden edge(s)")
    for entry in violations:
        print("    " + entry, file=sys.stderr)
    return len(violations)


def arm_reference_slice(root: Path) -> int:
    """Refuse a slice that declares a member the engine no longer publishes.

    WHY IT EXISTS. Each feature declares the slice of `window.__referentiel` it
    reads, and the global's own type is their intersection — so a member left in
    a slice after L09 deleted the fixture behind it is a TYPE THAT LIES. Nothing
    else catches it: the declaration compiles, the reader is gone, and the next
    person to add a reader gets `undefined` at run time with the compiler's
    blessing. Four were left after the conversions — `SEARCH`, `derivedFollows`,
    `SYNOPSIS`, `RELEASES`.

    WHAT IT DOES NOT READ, said before what it does: only members whose name is
    written in the engine's own vocabulary — a slice also declares TYPES, and a
    type's field names are not published on anything. It compares the member
    names of the `Reference` types alone, which is the level `__referentiel` is
    an object of.

    Args:
        root: The directory to read.

    Returns:
        The number of members nothing publishes.
    """
    engine = root / "engine" / "legacy.js"
    if not engine.is_file():
        print("  reference-slice: the engine is gone — this arm has no subject", file=sys.stderr)
        return 1
    text = engine.read_text(encoding="utf-8")
    start = text.index("window.__referentiel = {")
    depth, cursor = 0, start
    while cursor < len(text):
        if text[cursor] == "{":
            depth += 1
        elif text[cursor] == "}":
            depth -= 1
            if depth == 0:
                break
        cursor += 1
    block = text[start:cursor]
    published = set(re.findall(r"^\s*([A-Za-z_$][\w$]*)[,:]", block, re.MULTILINE))
    published |= set(re.findall(r"get ([A-Za-z_$][\w$]*)\(\)", block))

    stale: list[str] = []
    read = 0
    for path in sorted((root / "features").glob("*/reference.ts")):
        source = path.read_text(encoding="utf-8")
        for declaration in re.finditer(
            r"export type \w*Reference = [^{]*\{(.*?)^\};", source, re.S | re.MULTILINE
        ):
            for member in re.findall(r"^  ([A-Za-z_$][\w$]*)\??:", declaration.group(1),
                                     re.MULTILINE):
                read += 1
                if member not in published:
                    stale.append(
                        f"{path.relative_to(root).as_posix()}: `{member}` is declared and the "
                        f"engine publishes nothing by that name — a type that lies")
    print(f"  reference-slice: {read} declared member(s) read against "
          f"{len(published)} published, {len(stale)} stale")
    # A CORPUS OF NOTHING would print « 0 stale » and mean « I read nothing ».
    if read == 0:
        stale.append("no slice member was read at all — the arm found no `…Reference` type")
    for entry in stale:
        print("    " + entry, file=sys.stderr)
    return len(stale)


ARMS = {
    "reference-slice": arm_reference_slice,
    "cycles": arm_cycles,
    "mocks": arm_mocks,
    "layering": arm_layering,
    "fan-in": arm_fan_in,
    "size": arm_size,
    "typing": arm_typing,
    "duplicate-import": arm_duplicate_import,
    "one-address": arm_one_address,
    "addressing": arm_addressing,
    "tree": arm_tree,
}


def main() -> int:
    """Run the requested arms over the maquette's module tree."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arm",
        choices=sorted(ARMS),
        help="run one arm instead of all of them",
    )
    parser.add_argument(
        "--list-grandfathered",
        action="store_true",
        help="print the size arm's grandfathered list as it would be regenerated",
    )
    parser.add_argument("--root", default=DESIGN_SRC, type=Path)
    arguments = parser.parse_args()

    if not arguments.root.exists():
        print(f"check-frontend-boundaries: root not found: {arguments.root}", file=sys.stderr)
        return 2

    print(f"check-frontend-boundaries: {arguments.root}")
    if arguments.list_grandfathered:
        arm_size(arguments.root, listing=True)
        return 0
    selected = [arguments.arm] if arguments.arm else sorted(ARMS)
    violations = sum(ARMS[name](arguments.root) for name in selected)
    if violations:
        print(f"check-frontend-boundaries: {violations} violation(s)", file=sys.stderr)
        return 1
    print("check-frontend-boundaries: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
