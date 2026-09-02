#!/usr/bin/env python3
"""A component is written once — no PascalCase function is declared in two files.

THE DEFECT THIS ENDS. `Icon` — one `<svg>` with six attributes — was written
out FOUR times under `frontend/maquette/design/src`: once in `ui/icon.tsx`,
where it belonged, and once privately in each of three screens, each copy
carrying a comment saying the extraction « is a follow-up of its own ». The
follow-up never came, because nothing counted the copies: a component copied
into a second file emits nothing a markup arm reads, imports nothing a
boundary arm reads, and renders exactly what the original renders, so every
instrument stayed green over it for four waves.

WHAT IT READS. Every `.ts` and `.tsx` file under the maquette's `src`, outside
the dying engine (`engine/`, which is subtracted from and never edited) and
the mock layer (`mocks/`, whose test doubles are free to shadow a name), for a
top-level `function <PascalCase>(` declaration — exported or not. A name
declared in more than one file is a violation. HARD ZERO, no allow-list: an
allow-list is a baseline, and a baseline is where the next copy hides.

WHAT IT DOES NOT READ, said before the arm so nobody reads more into it:
  - camelCase functions. `announce` is declared in four files and `isOpen` in
    two, each a private helper of its own module about its own subject; a hook
    written twice (`useStaging`, in `lib/queue.ts` and `features/arrivals/
    queries.ts`) is a finding for a reader, not a component for this arm.
  - a component copied under a DIFFERENT name. Two bodies compared by text
    would be a second instrument with its own blind spots; this one holds the
    NAME, which is what a reader greps.
  - a declaration inside a block comment, or a PascalCase helper in a `*.test.ts`
    file: both are read as declarations. Neither can hide a duplicate — the
    error is in the other direction, a red the reader must judge — and a
    comment-stripping pass here would be a second parser with its own defects.
  - arrow-function components (`const X = () => …`). Measured at zero
    top-level occurrences today; the shape is named here so the day the first
    one is written the hole is known rather than discovered.

A FLOOR ON THE CORPUS. A run that read no file, or found no declaration,
reports « no duplicate » and means « I measured nothing » — the reading this
repository counts under « guards green over what they do not read ».
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN_ROOT = ROOT / "frontend" / "maquette" / "design" / "src"
# The dying engine is only ever subtracted from; the mock layer's doubles may
# shadow the names they stand in for.
EXCLUDED_DIRECTORIES = ("engine", "mocks")
# `export default function X(` IS A DECLARATION, and the first version of this
# pattern refused only `export function` — so the commonest way a component is
# exported anywhere outside this repository was green, under a docstring saying
# « exported or not ». Nothing saw it because the corpus holds no such
# declaration today, which is the whole shape of a guard measured against the
# tree it was written on rather than against the shapes it claims to read.
DECLARATION = re.compile(
    r"^(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+([A-Z][A-Za-z0-9]*)\s*[(<]",
    re.MULTILINE)
# Well under the corpus, so a tree that halves is still read and a tree that
# vanishes is refused. The figures the guard PRINTS are the tree's; a second
# copy of them in this sentence would be the drift this repository names, so
# there is none here.
FLOOR_FILES = 60
FLOOR_DECLARATIONS = 30


def sources(root: Path) -> list[Path]:
    """Collect the files this guard reads, in a stable order.

    Args:
        root: The maquette's source root.

    Returns:
        Every `.ts` and `.tsx` file below it outside the excluded directories.
    """
    found: list[Path] = []
    for extension in (".ts", ".tsx"):
        for path in root.rglob("*" + extension):
            relative = path.relative_to(root).parts
            if relative and relative[0] in EXCLUDED_DIRECTORIES:
                continue
            found.append(path)
    return sorted(found)


def main() -> int:
    """Refuse a PascalCase function declared in more than one file.

    Returns:
        The number of names declared twice, or 1 when the corpus is under its floor.
    """
    declared: dict[str, list[str]] = {}
    files = sources(DESIGN_ROOT)
    declarations = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        for name in DECLARATION.findall(text):
            declarations += 1
            declared.setdefault(name, []).append(str(path.relative_to(DESIGN_ROOT)))
    twice = {name: paths for name, paths in sorted(declared.items()) if len(paths) > 1}
    print(f"  once: {declarations} PascalCase declaration(s) read over {len(files)} file(s) "
          f"(floors {FLOOR_DECLARATIONS} and {FLOOR_FILES}), {len(twice)} name(s) declared twice")
    if len(files) < FLOOR_FILES or declarations < FLOOR_DECLARATIONS:
        print("check-component-once: the corpus is under its floor — « no duplicate » "
              "would be a sentence about nothing", file=sys.stderr)
        return 1
    for name, paths in twice.items():
        print(f"    `{name}` is written out in {len(paths)} files: {', '.join(paths)} — "
              "a component two files draw is vocabulary and lives in `ui/`; two "
              "different things under one name are renamed, never allow-listed",
              file=sys.stderr)
    if twice:
        print(f"check-component-once: {len(twice)} violation(s)", file=sys.stderr)
        return len(twice)
    print("check-component-once: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
