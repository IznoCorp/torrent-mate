#!/usr/bin/env python3
"""Holds Tailwind's scan inside the maquette, and its names off the prototype's.

TWO FAILURES, AND NEITHER ANNOUNCES ITSELF.

The first is the leak. Tailwind v4 scans the project root AUTOMATICALLY, and an
`@source` rule ADDS to that scan rather than replacing it. That is not a
subtlety — it is the exact mechanism that once put 936 bytes of this prototype
into the production bundle, and it was measured again while this guard was
being written: narrowing the `@source` list to five directories changed the
generated output by nothing at all, down to the file hash. `source(none)` is
what confines; naming your sources does not.

The second is the collision. Tailwind generates a utility for any candidate
word it finds, and the prototype's own vocabulary overlaps it — `grid`,
`block`, `table`, `hidden`, `fixed` are all class names somebody might choose
AND utilities Tailwind ships. Today the prototype's rules are unlayered and
Tailwind's sit in `@layer utilities`, so the prototype wins every conflict; but
that is a property of the cascade, not a decision anybody took, and it stops
protecting the moment a colliding class has NO rule of its own for the property
the utility sets. The oracle cannot be the answer: it measures 33 named regions
out of a whole document, so a collision on an unmeasured element passes.

Exit code is the verdict: 0 when every hold passes, 1 naming what broke.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESIGN = ROOT / "frontend" / "maquette" / "design"
THEME = DESIGN / "src" / "styles" / "theme.css"
PRODUCTION_ENTRY = ROOT / "frontend" / "src" / "styles" / "globals.css"

# The directories the maquette's scan may name. `engine`, `i18n` and `styles`
# are absent on purpose — see the reason written at the `@source` block itself.
ALLOWED_SOURCES = {
    "../../index.html",
    "../app",
    "../features",
    "../lib",
    "../routes",
    "../ui",
}

# Class names that ARE Tailwind utilities and are worn by the prototype anyway,
# each with the reason it is tolerated. A name reaches this table by being
# written here, in review — never by being discovered.
DECLARED_COLLISIONS = {
    "grid": (
        "The gallery grid. The prototype declares `display: grid` on it itself, "
        "unlayered, so it wins over `@layer utilities` — and the value Tailwind "
        "would set is the same one. It disappears when the gallery converts."
    ),
}

_CLASS_ATTRIBUTE = re.compile(r"class(?:Name)?\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|\{`([^`]*)`\}|\{\"([^\"]*)\"\})")
_CLASS_LIST_CALL = re.compile(r"classList\.(?:add|toggle|remove)\(([^)]*)\)")
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_INTERPOLATION = re.compile(r"\$\{[^}]*\}")


def worn_class_names() -> set[str]:
    """Returns every class name the maquette's markup actually wears.

    Reads the component tree, the shell document and the legacy engine — the
    engine included, because it still draws markup and a collision on what it
    draws breaks just as loudly. Template interpolations are blanked rather
    than guessed at: a name assembled at runtime is not a name this can read,
    and pretending otherwise would put junk in the comparison.

    Returns:
        The class names, as written.
    """
    names: set[str] = set()
    files = list((DESIGN / "src").rglob("*.tsx"))
    files += [DESIGN / "index.html", DESIGN / "src" / "engine" / "legacy.js"]
    for path in files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for match in _CLASS_ATTRIBUTE.finditer(text):
            written = " ".join(group for group in match.groups() if group)
            for name in _INTERPOLATION.sub(" ", written).split():
                if re.fullmatch(r"[a-zA-Z][\w-]*", name):
                    names.add(name)
        for match in _CLASS_LIST_CALL.finditer(text):
            names.update(re.findall(r"[\"']([\w-]+)[\"']", match.group(1)))
    return names


def generated_utilities() -> set[str] | None:
    """Returns the utility class names Tailwind emitted into the built sheet.

    Reads the BUILD rather than guessing from the source, because what matters
    is the names that exist in the served document. Braces are matched rather
    than regex-scanned: `@layer utilities` contains nested `@media` blocks, and
    a pattern that stopped at the first `}` would read a fraction of it and
    call the rest absent.

    Returns:
        The utility names, or `None` when no build is present — reported as a
        skip rather than as a pass.
    """
    built = sorted((DESIGN / "dist" / "vite").glob("*.css")) if (DESIGN / "dist" / "vite").exists() else []
    if not built:
        return None
    css = built[0].read_text(encoding="utf-8")
    opening = css.find("@layer utilities{")
    if opening < 0:
        return set()
    index = opening + len("@layer utilities{")
    depth = 1
    while depth and index < len(css):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
        index += 1
    return set(re.findall(r"\.([a-zA-Z][\w-]*)(?=[,{:.\s])", css[opening:index]))


def main() -> int:
    """Runs the four holds and prints the verdict.

    Returns:
        0 when every hold passes, 1 when any fails.
    """
    failures: list[str] = []
    holds = 0

    if not THEME.exists():
        print(f"tailwind confinement: {THEME} not found — nothing to confine, and a pass here would mean nothing")
        return 1
    theme = THEME.read_text(encoding="utf-8")

    # Hold 1 — the automatic scan is OFF. This is the confinement itself.
    holds += 1
    if "source(none)" not in theme:
        failures.append(
            "  the maquette's entry does not carry `source(none)`, so Tailwind "
            "scans the project root automatically — which is how 936 bytes of "
            "this prototype reached the production bundle. An `@source` list "
            "does not replace that scan; it adds to it."
        )

    # Hold 2 — every named source is one of the allowed ones, and none climbs out.
    holds += 1
    # Comments stripped FIRST. This file explains the confinement in prose and
    # quotes production's own `@source not "../../maquette"` while doing so —
    # so a scan of the raw text reported the maquette scanning itself. A guard
    # that reads its own documentation as code is a guard that fails on being
    # explained.
    named = set(re.findall(r'@source\s+(?:not\s+)?"([^"]+)"', _CSS_COMMENT.sub(" ", theme)))
    stray = named - ALLOWED_SOURCES
    if stray:
        failures.append(
            "  the maquette scans "
            + ", ".join(sorted(stray))
            + " — not in the allowed set. `src/engine`, `src/i18n` and "
            "`src/styles` are excluded on purpose: they carry no class "
            "attribute, so every candidate they yield is a false one, and a "
            "false candidate is a NAME that can collide."
        )

    # Hold 3 — production still refuses to scan the maquette. The other end.
    holds += 1
    if PRODUCTION_ENTRY.exists():
        production = PRODUCTION_ENTRY.read_text(encoding="utf-8")
        if '@source not "../../maquette"' not in production:
            failures.append(
                f"  {PRODUCTION_ENTRY.relative_to(ROOT)} no longer excludes the "
                "maquette from its own scan. The confinement has two ends and "
                "this is the one that leaked."
            )
    else:
        failures.append(f"  {PRODUCTION_ENTRY} not found — the other end of the confinement cannot be read")

    # Hold 4 — no undeclared collision between a utility and a worn class name.
    holds += 1
    utilities = generated_utilities()
    if utilities is None:
        print(
            "tailwind confinement: no build under design/dist/vite — run "
            "`npm run build` first. Skipped rather than passed.",
            file=sys.stderr,
        )
        return 1
    collisions = (utilities & worn_class_names()) - set(DECLARED_COLLISIONS)
    if collisions:
        failures.append(
            "  " + ", ".join(sorted(collisions)) + " — worn by the prototype's markup AND generated as a Tailwind "
            "utility. The prototype wins today only because its rules are "
            "unlayered; that stops being true the moment such a class has no "
            "rule of its own for the property the utility sets. Declare it in "
            "DECLARED_COLLISIONS with its reason, or rename it."
        )

    if failures:
        print(f"tailwind confinement: {len(failures)} violation(s) over {holds} hold(s).")
        print("\n".join(failures))
        return 1
    print(
        f"tailwind confinement: {holds} hold(s), no violation — "
        f"{len(utilities)} utilitie(s) generated, "
        f"{len(DECLARED_COLLISIONS)} declared collision(s), scan confined."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
