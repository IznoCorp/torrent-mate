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
import importlib.util
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
    # THE CONTRACT'S GENERATED TYPES, and a bucket of their own since L10-bis.
    # They lived under `mocks/` — the bucket L04 declared for « handlers and
    # fixture seeds » — and they are neither: they are the SHAPE of what the
    # interface may ask for, generated from `contract/openapi.json`. Filing them
    # with the fixtures made `lib/query-client.ts` import from `mocks/`, which
    # the boundaries arm had to be given a type-only exemption for (B-104).
    "contract": "the API contract's generated types — what the interface may ask for",
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

# THE LEDGER IS A FILE OF ITS OWN, and the reason is written in its header:
# which files the ceiling forgives, who owes each reduction, the size each was
# last recorded at, and the two documents that say which lots exist and which
# have landed. That is a subject, and this guard's subject is the module graph.
#
# IMPORTED AS A MODULE OBJECT, never member by member. A test that has to move
# the plan aside patches `ledger.PLAN`, and a `from … import PLAN` here would
# have bound a second name the reader below does not read — the shape a
# monkeypatch passes over in silence.
_LEDGER = importlib.util.spec_from_file_location(
    "frontend_size_ledger", Path(__file__).resolve().parent / "frontend_size_ledger.py")
ledger = importlib.util.module_from_spec(_LEDGER)
_LEDGER.loader.exec_module(ledger)

# THE REPOSITORY ROOT, defined once and aliased here rather than recomputed. Two
# expressions producing one path is one path that can be wrong in one of them,
# and this file and the ledger anchor on the same directory by construction.
REPOSITORY = ledger.REPOSITORY


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
        if module in ledger.GENERATED:
            continue
        sizes[module] = sum(1 for line in file.read_text(encoding="utf-8").splitlines()
                            if line.strip())
    over = {m: n for m, n in sizes.items() if n >= BLOCK_LINES}
    warn = {m: n for m, n in sizes.items() if WARN_LINES <= n < BLOCK_LINES}
    if listing:
        # THE LIST IS DERIVED, NEVER TYPED — and since B-306 the count is
        # derived with it, by the same loop that measures the tree above. That
        # is what makes « the record and the reading cannot drift apart » a
        # property of the code rather than a promise about how it is used.
        print("  GRANDFATHERED = {")
        for module, count in sorted(over.items(), key=lambda kv: -kv[1]):
            lot = (ledger.grandfathered_label(module) if module in ledger.GRANDFATHERED
                   else "?? — NO LOT RECORDED")
            print(f'      "{module}": ("{lot}", {count}),')
        print("  }")
        return 0
    unrecorded = sorted(m for m in over if m not in ledger.GRANDFATHERED)
    stale = sorted(m for m in ledger.GRANDFATHERED if m not in over)

    # THE LABEL IS READ (B-073). Membership was held from both ends and the
    # VALUE from neither, so four entries promised a lot that had landed.
    declared_lots, landed = ledger.declared_and_landed_lots()
    spent: list[str] = []
    unnamed: list[str] = []
    invented: list[str] = []
    for module in sorted(ledger.GRANDFATHERED):
        if module not in over:
            continue                      # already reported as stale, above
        owed = ledger.OWED_LOT.match(ledger.grandfathered_label(module))
        if owed is None:
            unnamed.append(module)
            continue
        if owed.group(1) not in declared_lots and declared_lots:
            invented.append(f"{module} — its label leads with {owed.group(1)}, "
                            f"which the plan does not declare")
        elif owed.group(1) in landed:
            # « already landed », not « already `LANDED` ». The backticks quoted a
            # status TOKEN, and no such token exists any more: the word left the
            # plan on 2026-08-28. A message naming a spelling nobody can go and
            # look at sends its reader hunting for a word that is not there.
            spent.append(f"{module} — its label leads with {owed.group(1)}, "
                         f"which IMPLEMENTATION.md records as already landed")
    plan_unreadable = not declared_lots
    advancement_unreadable = not landed

    # THE COUNT IS READ (B-306). The label said who owed the reduction; nothing
    # said the reduction was happening, so a grandfathered file grew 77 lines
    # under a decision titled « dies by subtraction » and this arm printed clean.
    #
    # A file BELOW its record is the list working, not a violation — but it is
    # never silent: a record that has stopped describing the file is a record
    # nobody compared, which is the state B-073 found the labels in.
    grown: list[str] = []
    shrunk: list[str] = []
    for module in sorted(ledger.GRANDFATHERED):
        if module not in over:
            continue                      # already reported as stale, above
        recorded = ledger.grandfathered_count(module)
        reading = over[module]
        if reading > recorded:
            grown.append(f"{module} — recorded at {recorded} non-blank lines and "
                         f"reads {reading}, {reading - recorded} more. A "
                         f"grandfathered file is one that may not be EXTENDED; "
                         f"subtract the addition, or record the growth here with "
                         f"the decision that allows it")
        elif reading < recorded:
            shrunk.append(f"{module} — recorded at {recorded} and reads {reading}. "
                          f"Re-record it in THIS commit: a count re-recorded later "
                          f"is a count nobody compared")

    # An exemption nobody counts is indistinguishable from an oversight, so the
    # generated files are PRINTED on every run rather than merely skipped — and
    # an entry naming a file that is not there is a violation, because a stale
    # exemption is one that has stopped describing the tree.
    absent = sorted(name for name in ledger.GENERATED if not (root / name).is_file())
    # THE RECORDS ARE PRINTED, not merely held. A figure nobody reads is a
    # figure nobody compares — which is the whole of B-306 said once more — and
    # a reader of this line sees the engine shrinking wave by wave without
    # opening the guard.
    records = ", ".join(f"{module} {ledger.grandfathered_count(module)}→{over[module]}"
                        for module in sorted(ledger.GRANDFATHERED) if module in over)
    print(f"  size: ceiling {BLOCK_LINES}, {len(over)} at or over it "
          f"({len(ledger.GRANDFATHERED)} recorded; the plan declares {len(declared_lots)} lot(s), "
          f"and IMPLEMENTATION.md records {len(landed)} landed), "
          f"{len(warn)} above the {WARN_LINES} warning, "
          f"{len(ledger.GENERATED)} generated file(s) exempt"
          + (f" — grandfathered counts: {records}" if records else ""))
    for entry in shrunk:
        print(f"    [RE-RECORD] {entry}")
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
    for entry in grown:
        print(f"    {entry}", file=sys.stderr)
    # NEITHER EMPTINESS IS A PASS. A reader that finds nothing and reports clean
    # is the exact shape this arm was written to end: the hold would pass for the
    # one reason it must never pass for. Two documents, so two messages — a
    # single one naming a single file would send its reader to the file that was
    # fine.
    if plan_unreadable:
        print("    docs/reference/frontend-architecture.md: no lot heading could be read, so « the label "
              "leads with a lot the plan declares » is a sentence this arm cannot check",
              file=sys.stderr)
    if advancement_unreadable:
        print("    IMPLEMENTATION.md: no « Landed, in order » row could be read, so « the label leads "
              "with a lot that has not landed » is a sentence this arm cannot check",
              file=sys.stderr)
    return (len(unrecorded) + len(stale) + len(spent) + len(unnamed)
            + len(invented) + len(absent) + len(grown)
            + int(plan_unreadable) + int(advancement_unreadable))


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



# THE EXEMPTION THIS CONSTANT CARRIED IS GONE, AND SO IS ITS REASON (B-104).
# `mocks/contract-types.d.ts` was the API contract's generated types filed in
# the bucket L04 declared for « handlers and fixture seeds », and it is neither:
# it is the SHAPE of what the interface may ask for. Because it sat there,
# `lib/query-client.ts` imported from `mocks/` and this arm had to be told that
# a type-only edge to that one stem was allowed — an exemption whose own comment
# said « its placement is questionable » and « moving it belongs to its own
# change ». This is that change: the file is `contract/types.d.ts` now, a bucket
# of its own, and nothing outside `app/` imports `mocks/` any more.
#
# The tuple stays EMPTY rather than being deleted, so the next module that needs
# to reach into `mocks/` has to write its name here with a reason, in a diff
# somebody reads — which is what the exemption was for and what a deletion would
# have taken away.
CONTRACT_TYPES_EXEMPT = ()


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
