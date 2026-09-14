"""Projects invariant 8's fan-in arm onto the imports a·2 was about to add.

Run on the tree a·2 started from — L13a a·1's head, `79db420b3` — extracted
anywhere, and give its root as the argument:

    mkdir /tmp/l13a-projection
    git archive 79db420b3 scripts frontend/maquette/design/src | tar -x -C /tmp/l13a-projection
    python3 docs/features/maquette-l13/plan/fanin_projection.py /tmp/l13a-projection

It reads that tree with that tree's own `scripts/check-frontend-boundaries.py`
(`build_graph`, `bucket_of`, `feature_of`, `FAN_IN_CEILING`, `FAN_IN_EXEMPT`),
finds every product read of a `window.__` seam outside `engine/` and
`harness/` (the pass of the design's § 2.4, comments stripped, writes
excluded) and every such read inside `engine/`, and adds one import edge per
reader: to the owner phase-a02 first named, from the reading file — from
`engine/seams.ts` for an engine read, from `routes/media-sheet.tsx` for the
media screen's `__followActions`, and from `harness/publish.ts` for every
seam a rule reads. It prints, per owner, its importers today and projected.

On `79db420b3` it reads five modules over the ceiling: `app/history-bridge.ts`
1 → 9, `app/toast-host.ts` 1 → 9, `app/panel-host.ts` 1 → 7, `app/store.ts`
3 → 7, `features/acquisition/queries.ts` 2 → 5. On a later tree it reads what
that tree still has to move, which after a·2 is nothing.
"""
import collections
import importlib.util
import pathlib
import re
import sys

OWNERS = {
    "__store": "app/store.ts", "__toast": "app/toast-host.ts",
    "__bridge": "app/history-bridge.ts", "__screens": "app/history-bridge.ts",
    "__panel": "app/panel-host.ts", "__refillProducers": "app/panel-host.ts",
    "__queries": "lib/query-client.ts", "__dialog": "app/dialog-host.ts",
    "__followActions": "features/acquisition/queries.ts",
    "__suggestions": "features/acquisition/queries.ts",
    "__refillSuggestions": "features/acquisition/queries.ts",
    "__loadingDone": "app/entry.ts", "__entry": "app/entry.ts",
    "__queueActions": "lib/queue.ts", "__queue": "lib/queue.ts",
    "__refillEngineData": "app/engine-data.ts",
    "__releases": "features/releases/queries.ts",
    "__searchResults": "features/acquisition/search-queries.ts",
    "__settingLabels": "features/settings/labels.ts", "__address": "lib/addresses.ts",
    "__layers": "app/layer-registry.ts",
    "__settingsVerbs": "features/settings/panel-setting.ts",
    "__followVerbs": "features/acquisition/follow-verbs.ts",
    "__navigation": "app/navigation-seam.ts", "__popover": "app/popover-host.ts",
    "__stackedSurfaces": "lib/stacked-surface.ts",
    "__deleteLibraryItems": "features/library/queries.ts",
    "__episodeSaying": "features/media/popover-episode.ts",
    "__pendingDecisions": "features/arrivals/queries.ts",
    "__sortWays": "features/library/sorting.ts", "__mocks": "mocks/index.ts",
    "__gestures": "lib/press-arbitration.ts",
}

# The seams a rule reads, which the harness was to publish.
READ_BY_RULES = (
    "__store", "__toast", "__bridge", "__screens", "__panel", "__queries", "__dialog",
    "__followActions", "__suggestions", "__loadingDone", "__entry", "__queueActions",
    "__queue", "__releases", "__searchResults", "__settingLabels", "__layers",
    "__deleteLibraryItems", "__sortWays", "__mocks", "__gestures",
)

NAME = re.compile(r"window\.(__[A-Za-z0-9_]+)")
WRITE = re.compile(r"window\.(__[A-Za-z0-9_]+)\s*(=|\?\?=)(?!=)")


def strip_comments(text):
    """Blanks block and line comments, keeping the line structure."""
    text = re.sub(r"/\*.*?\*/", lambda found: "\n" * found.group(0).count("\n"), text, flags=re.S)
    return "\n".join(re.sub(r"(^|[^:\"'`])//.*$", r"\1", line) for line in text.split("\n"))


def readers(source_root):
    """Maps each seam name to the files that read it, engine reads under `engine/seams.ts`."""
    found = collections.defaultdict(set)
    for path in sorted(source_root.rglob("*")):
        if path.suffix not in (".ts", ".tsx", ".js") or ".test." in path.name:
            continue
        relative = path.relative_to(source_root).as_posix()
        if relative.startswith("harness/"):
            continue
        for line in strip_comments(path.read_text(encoding="utf-8")).split("\n"):
            writes = {match.start() for match in WRITE.finditer(line)}
            for match in NAME.finditer(line):
                if match.start() in writes or re.match(r"\s*:", line[match.end():]):
                    continue
                found[match.group(1)].add("engine/seams.ts" if relative.startswith("engine/") else relative)
    return found


def main():
    """Prints, per owner, its importers today and once a·2's edges are added."""
    tree = pathlib.Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(tree / "scripts"))
    specification = importlib.util.spec_from_file_location(
        "boundaries", tree / "scripts" / "check-frontend-boundaries.py")
    boundaries = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(boundaries)
    source_root = tree / "frontend" / "maquette" / "design" / "src"
    edges, _ = boundaries.build_graph(source_root)

    added = collections.defaultdict(set)
    for name, files in readers(source_root).items():
        if name not in OWNERS:
            continue
        for reader in files:
            if name == "__followActions" and reader == "features/media/media-screen.tsx":
                reader = "routes/media-sheet.tsx"
            if reader != OWNERS[name]:
                added[reader].add(OWNERS[name])
    for name in READ_BY_RULES:
        added["harness/publish.ts"].add(OWNERS[name])

    def importers_of(edge_map):
        importers = collections.defaultdict(set)
        for source, targets in edge_map.items():
            for target in set(targets):
                if boundaries.bucket_of(target) in ("ui", "lib") or target in boundaries.FAN_IN_EXEMPT:
                    continue
                importers[target].add(boundaries.feature_of(source) or boundaries.bucket_of(source))
        return importers

    today = importers_of(edges)
    merged = {source: list(targets) for source, targets in edges.items()}
    for source, targets in added.items():
        merged.setdefault(source, []).extend(targets)
    projected = importers_of(merged)
    for module in sorted(set(OWNERS.values())):
        if boundaries.bucket_of(module) in ("ui", "lib"):
            continue
        before, after = today.get(module, set()), projected.get(module, set())
        over = "  OVER" if len(after) > boundaries.FAN_IN_CEILING else ""
        print(f"{module}: today {len(before)} {sorted(before)} -> projected {len(after)} {sorted(after)}{over}")


if __name__ == "__main__":
    main()
