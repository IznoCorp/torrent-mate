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
SOURCE_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".json")

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
            targets.append(str(resolved.relative_to(absolute_root)))
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

# Invariant 6. A file at or above the block ceiling must be listed below with
# the lot that converts it; the soft ceiling only warns.
BLOCK_LINES = 400
WARN_LINES = 250

# Files over the block ceiling, each with the lot that converts it. Generated
# by `--arm size --list-grandfathered`, never maintained by hand: a list typed
# out drifts from the tree it describes, and this repository has already
# watched a hand-kept number drift by seven inside the pull request that
# introduced it as a control.
GRANDFATHERED = {
    "engine/legacy.js": "L13 — the engine dies by subtraction, surface by surface",
    "engine/states.js": "L13 — the scenario table goes with the engine it drives",
    "app/shell.tsx": "L05 — routing, then L13 for what is left of the boot",
    "features/acquisition/page.tsx": "L07 — the surface converts, then L09 takes its data",
    "features/library/page.tsx": "L07, then L09",
    "features/media/media-screen.tsx": "L07, then L09",
    "features/arrivals/resolution-screen.tsx": "L07, then L09",
}


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
    print(f"  size: ceiling {BLOCK_LINES}, {len(over)} at or over it "
          f"({len(GRANDFATHERED)} recorded), {len(warn)} above the {WARN_LINES} warning")
    for module in sorted(warn):
        print(f"    [WARN] {module}: {warn[module]} non-blank lines", file=sys.stderr)
    for module in unrecorded:
        print(f"    {module}: {over[module]} non-blank lines, over the ceiling and "
              f"recorded against no lot", file=sys.stderr)
    for module in stale:
        print(f"    {module}: recorded as grandfathered and is no longer over the "
              f"ceiling — the list describes a tree that has moved", file=sys.stderr)
    return len(unrecorded) + len(stale)


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


def arm_addressing(root: Path) -> int:
    """Refuse a page identity in a query, a dial in a path, or an undeclared screen.

    Invariant 1 says the URL and the interface never contradict each other, and
    D1 says which half carries what: the PATH carries the identity — which thing
    is being looked at — and the QUERY carries the state — how it is being
    looked at. `/library/breaking-bad?sort=recent`, never `?page=lib` and never
    `/library/sort/recent`.

    R69 checks this at runtime, in a browser, over the states it drives. This
    checks it offline, over the SOURCE, on every `make check`. The two do not
    overlap: a rule reads what the interface DID, this reads what it is allowed
    to declare, and the cheaper of the two to act on is this one.

    It extends this guard rather than sitting beside it as a second script —
    L02's lesson, paid for once already.

    It also holds the SCREEN paths, and that is a contract with three ends: the
    `SCREEN_PATHS` table declares them, the route files serve them, and this
    reads both and refuses a difference. A screen is a layer over the home
    frame rather than a page of its own, so a route the table does not carry
    resolves to the not-found page underneath the screen — invisible until the
    screen closes, which is why an offline reader is what catches it.

    Args:
        root: The directory to read.

    Returns:
        The number of violations.
    """
    violations = []
    model = root / "lib" / "addresses.ts"
    declaration = model.read_text(encoding="utf-8") if model.is_file() else ""
    # The dial names come from the model itself, never from a list written
    # here: a second list is how the two drift, and this one would drift
    # silently because nothing renders it.
    dials = set(re.findall(r'parameter:\s*"([^"]+)"', declaration))
    dials.update(re.findall(r'PANEL_PARAMETER = "([^"]+)"', declaration))
    pages = set(re.findall(r'^\s{2}(\w+):\s*"/', declaration, re.M))
    # The same reading, one level over: the page table's VALUES are the paths a
    # page claims, and the screen table's entries are the paths a screen does.
    page_paths = set(re.findall(r'^\s{2}\w+:\s*"(/[^"]*)"', declaration, re.M))
    screen_paths = set(re.findall(r'^\s{2}"(/[^"]*)"', declaration, re.M))

    routes = root / "routes"
    files = sorted(routes.glob("*.tsx")) + sorted(routes.glob("*.ts")) if routes.is_dir() else []
    served = set()
    for file in files:
        module = file.relative_to(root).as_posix()
        text = file.read_text(encoding="utf-8")
        for path in re.findall(r'^\s*path:\s*"([^"]+)"', text, re.M):
            served.add(path)
            # A dial promoted into the path — the shape D1 names and forbids.
            for segment in [s for s in path.split("/") if s and not s.startswith("$")]:
                if segment in dials:
                    violations.append(
                        f'{module}: "{path}" puts the dial « {segment} » in the PATH — '
                        f"a dial is state, and state travels in the query")
        # A page identity declared as a search parameter — the shape D1
        # replaced. `page` by name, and any id the page table carries.
        #
        # Read out of the `SearchParams` BODY rather than line by line: these
        # types are written on ONE line as often as on several, and a
        # line-anchored pattern saw only the first key. It was written that way
        # first, and the mutation that puts `page` back went straight past it —
        # a guard that reads half of what it claims to read is the shape this
        # whole file exists to refuse.
        declared = set()
        for body in re.findall(r"type\s+\w*SearchParams\w*\s*=\s*\{([^}]*)\}", text, re.S):
            declared.update(re.findall(r"(\w+)\s*\??\s*:", body))
        for name in re.findall(r'for \(const name of \[([^\]]*)\]', text):
            declared.update(re.findall(r'"(\w+)"', name))
        for name in sorted(declared & (pages | {"page"})):
            violations.append(
                f"{module}: declares « {name} » as a search parameter — "
                f"a page is an identity, and identity travels in the path")

    # A route that is neither a page's path nor the root is a SCREEN, and the
    # model has to say so — the two ends are compared, never merged.
    screen_routes = {path for path in served if path not in page_paths and path != "/"}
    for path in sorted(screen_routes - screen_paths):
        violations.append(
            f'lib/addresses.ts: "{path}" is served by a route and declared by no SCREEN_PATHS '
            f"entry — it would resolve to the not-found page underneath its screen")
    for path in sorted(screen_paths - screen_routes):
        violations.append(
            f'lib/addresses.ts: SCREEN_PATHS declares "{path}", which no route serves — '
            f"a declaration outliving its route is how the table stops describing the tree")
    print(f"  addressing: {len(files)} route file(s), {len(dials)} dial(s), "
          f"{len(pages)} page(s), {len(screen_paths)} screen(s), {len(violations)} violation(s)")
    for entry in violations:
        print("    " + entry, file=sys.stderr)
    return len(violations)


def arm_tree(root: Path) -> int:
    """Refuse a file outside every declared bucket, and refuse `data.ts` returning.

    Args:
        root: The directory to read.

    Returns:
        The number of files with no bucket, plus one if the hub is back.
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
    print(f"  tree: {len(BUCKETS)} declared bucket(s), {len(strays)} file(s) outside them")
    for entry in strays:
        print("    " + entry, file=sys.stderr)
    return len(strays)


ARMS = {
    "cycles": arm_cycles,
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
