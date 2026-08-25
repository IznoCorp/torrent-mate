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
DECLARED_COLLISIONS: dict[str, str] = {
    # EMPTY, AND IT IS A VERDICT RATHER THAN A DEFAULT. `grid` was here for one
    # phase, tolerated on the reasoning that the prototype declares
    # `display: grid` on it itself and wins unlayered. That reasoning was
    # incomplete and the omission was expensive: a colliding name does not
    # merely override one property, it brings its WHOLE RULE. The gallery's
    # `gap: var(--spacing-5)` landed on a floating action button that had
    # asked for nothing but `display: grid`, and the oracle read it as 250
    # divergences across nineteen states.
    #
    # The repair was to remove the collision — the gallery is `.gallery` now —
    # not to describe it better. A name that is both a utility and a class is
    # a hazard whatever the cascade happens to do about it today.
}

_CLASS_ATTRIBUTE = re.compile(r"class(?:Name)?\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|\{`([^`]*)`\}|\{\"([^\"]*)\"\})")
_CLASS_LIST_CALL = re.compile(r"classList\.(?:add|toggle|remove)\(([^)]*)\)")
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_INTERPOLATION = re.compile(r"\$\{[^}]*\}")


def prototype_rule_classes() -> set[str]:
    """Returns the class names the prototype DECLARES A RULE for.

    THE PREMISE MOVED, AND IT HAD TO. This hold used to read the classes the
    markup WORE, which was right for exactly as long as the markup wore no
    utilities. From the first converted surface the markup wears them
    deliberately, and every utility then read as a collision with itself.

    The hazard was never wearing a name — it is a name meaning two things. A
    class the prototype writes a RULE for, whose name is also a utility,
    carries its whole rule onto every element that asked only for the utility:
    the gallery's `gap` landed on a floating action button that had asked for
    `display: grid` alone, and the oracle read 250 divergences.

    Returns:
        Every class name with a rule of its own in the prototype's stylesheets.
    """
    names: set[str] = set()
    sources = [DESIGN / "refonte.html"]
    styles = DESIGN / "src" / "styles"
    if styles.is_dir():
        sources.extend(sorted(styles.glob("*.css")))
    for path in sources:
        if not path.exists():
            continue
        text = _CSS_COMMENT.sub(" ", path.read_text(encoding="utf-8"))
        for prelude in re.findall(r"([^{}]*)\{", text):
            # A utility written INSIDE an arbitrary value is not a selector.
            for name in re.findall(r"\.(-?[_a-zA-Z][\w-]*)", prelude):
                names.add(name)
    return names


def generated_utilities() -> set[str] | None:
    """Returns the utility class names Tailwind emitted into the built sheet.

    Reads the BUILD rather than guessing from the source, because what matters
    is the names that exist in the served document. Braces are matched rather
    than regex-scanned: `@layer utilities` contains nested `@media` blocks, and
    a pattern that stopped at the first `}` would read a fraction of it and
    call the rest absent.

    Returns:
        The utility names, or `None` when no build is present OR when its
        `@layer utilities` header cannot be found — both reported as a failure
        rather than as a pass.
    """
    built = sorted((DESIGN / "dist" / "vite").glob("*.css")) if (DESIGN / "dist" / "vite").exists() else []
    if not built:
        return None
    css = built[0].read_text(encoding="utf-8")
    opening = css.find("@layer utilities{")
    if opening < 0:
        # NOT AN EMPTY SET. The header is matched as a literal, so one space
        # from a different minifier or a Tailwind that reformats it would make
        # every collision test compare against nothing and pass — printing
        # « 0 utilitie(s) generated » as its only tell, which is a number
        # nobody compares. An unreadable build is a failure, like an absent one.
        return None
    index = opening + len("@layer utilities{")
    depth = 1
    while depth and index < len(css):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
        index += 1
    return set(re.findall(r"\.([a-zA-Z][\w-]*)(?=[,{:.\s])", css[opening:index]))


# The floor under hold 4's read of the build. The current build yields 209
# utilities; the figure exists to catch a build or a read that collapsed, not
# to track the number, so it sits far below and moves only when it bites.
UTILITY_FLOOR = 100


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
    # EVERY HOLD BELOW READS THE CODE, NOT THE PROSE. The two holds that search
    # a stylesheet for a literal were written against raw text first, and both
    # were vacuous: these files explain the confinement in comments and quote
    # the very strings the holds look for. Hold 2 failed loudly on it — it
    # reported the maquette scanning itself. Hold 1 failed SILENTLY, and only a
    # mutation found it: removing `source(none)` from the code left the guard
    # green, because the sentence explaining `source(none)` was still there.
    declarations = _CSS_COMMENT.sub(" ", theme)

    # Hold 1 — the automatic scan is OFF. This is the confinement itself.
    holds += 1
    if "source(none)" not in declarations:
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
    named = set(re.findall(r'@source\s+(?:not\s+)?"([^"]+)"', declarations))
    # A HOLD THAT ONLY SUBTRACTS PASSES ON AN EMPTY SET. Deleting every
    # `@source` line leaves no stray and read as clean, while the scan it
    # describes had stopped existing. What is allowed must also be THERE.
    if not named:
        failures.append(
            "  the theme entry names no `@source` at all. `source(none)` alone "
            "confines the scan to nothing; the allowed directories are what "
            "make it scan the design. A missing set is not an empty violation."
        )
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
        production = _CSS_COMMENT.sub(" ", PRODUCTION_ENTRY.read_text(encoding="utf-8"))
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
            "tailwind confinement: no readable build under design/dist/vite — "
            "run `npm run build` first, and if one is there, its "
            "`@layer utilities` header could not be found. Refused rather "
            "than passed.",
            file=sys.stderr,
        )
        return 1
    # AND A FLOOR UNDER THE COUNT. A build that yields a handful of utilities
    # is a build this hold did not really read; the collision test would then
    # compare against almost nothing and report clean.
    if len(utilities) < UTILITY_FLOOR:
        failures.append(
            f"  the build yielded {len(utilities)} utilitie(s), under the floor "
            f"of {UTILITY_FLOOR}. Either the build is a fraction of itself or "
            "this hold read a fraction of the build — both are measurements "
            "nobody should trust, and neither is « no collision »."
        )
    collisions = (utilities & prototype_rule_classes()) - set(DECLARED_COLLISIONS)
    if collisions:
        failures.append(
            "  " + ", ".join(sorted(collisions)) + " — worn by the prototype's markup AND generated as a Tailwind "
            "utility. The prototype wins today only because its rules are "
            "unlayered; that stops being true the moment such a class has no "
            "rule of its own for the property the utility sets. Declare it in "
            "DECLARED_COLLISIONS with its reason, or rename it."
        )

    # Hold 5 — every declared token actually reaches the built stylesheet.
    #
    # A plain `@theme` block is TREE-SHAKEN: Tailwind emits only the tokens its
    # own utilities reference, and hand-written CSS spending them through
    # `var()` is invisible to it. That is not a theoretical hole — it deleted
    # the entire scale from the served document during phase 2, and 2 236 of
    # the oracle's 2 739 measurements collapsed to zero padding and `normal`
    # gaps. `@theme static` is the answer, and this hold is what keeps it true:
    # the oracle DOES catch it, at 25 seconds and 2 236 divergences, which is a
    # terrible way to learn that a keyword went missing.
    holds += 1
    # A token declared `initial` is a REMOVAL — `--spacing: initial` turns
    # Tailwind's multiplier off — so its absence from the build is what it asks
    # for, not a tree-shaken token.
    declared_tokens = {
        name for name, value in re.findall(
            r"^\s*(--[a-z0-9-]+)\s*:\s*([^;]+);", declarations, re.M)
        if value.strip() != "initial"
    }
    built = sorted((DESIGN / "dist" / "vite").glob("*.css"))
    if declared_tokens and built:
        emitted = built[0].read_text(encoding="utf-8")
        absent = sorted(name for name in declared_tokens if f"{name}:" not in emitted)
        if absent:
            failures.append(
                "  " + ", ".join(absent) + " — declared in the theme block and ABSENT from the built "
                "stylesheet. A plain `@theme` is tree-shaken; every `var()` in "
                "hand-written CSS then resolves to nothing. Use `@theme static` "
                "for as long as anything outside a component reads a token."
            )

    # Hold 6 — no class name is split across a string concatenation.
    #
    # Tailwind's scanner reads CANDIDATES out of raw text. A class broken over
    # `"…" + "…"` exists in no single literal, so it is never generated — and
    # NOTHING ELSE SEES IT. The media sheet's legibility gradient was split
    # that way and its `::after` came out with no background at all, while the
    # oracle stayed green: it measures the element's own computed style and its
    # rectangle, and a missing pseudo-element changes neither. Only R26 caught
    # it, by reading `getComputedStyle(bg, "::after")`.
    #
    # The test is the one thing that distinguishes the two cases: a literal
    # ending in a SPACE is a clean break between class names; a literal ending
    # in any other character continues the name into the next one.
    #
    # THE VOCABULARY IS A FAMILY, NOT A FILENAME, and a glob on `variants.ts`
    # alone is blind to most of it: `ui/variants.ts` is a BARREL, and the
    # shared primitives live in `ui/variants/{controls,layout,surfaces}.ts` —
    # measured, 54 of 89 concatenation sites, every shared primitive among
    # them. Read that way the hold stays green over a class cut in half in
    # that directory, which is the exact defect it exists to refuse. The
    # predicate is the one the two markup readers already carry: a file NAMED
    # for the vocabulary, or any file inside a directory named for it.
    #
    # WHAT IT DOES NOT SEE, said here so the next reader does not over-trust
    # it: the cut must fall at END OF LINE. `"a" + "b"` on one line, a template
    # literal, and `.concat()` are all invisible to this hold.
    #
    # AND IT REFUSES AN EMPTY READ. A hold that finds no source to read is a
    # hold that passes because it looked nowhere, and this one has already had
    # its corpus move out from under it once.
    holds += 1
    split: list[str] = []
    sources = [path for path in sorted((DESIGN / "src").rglob("*.ts"))
               if path.name.endswith("variants.ts") or path.parent.name == "variants"]
    if not sources:
        failures.append(
            "  the split-class hold read NO source file. The vocabulary is "
            "named by `*variants.ts` or by a `variants/` directory under "
            f"{(DESIGN / 'src').relative_to(ROOT)}; neither matched, so this "
            "hold measured nothing rather than finding nothing.")
    for path in sources:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            tail = re.search(r'"([^"]*)"\s*\+\s*$', line)
            if tail and tail.group(1) and not tail.group(1).endswith(" "):
                split.append(
                    f"  {path.relative_to(ROOT)}:{number} — a class name is cut "
                    f"by the concatenation after `…{tail.group(1)[-30:]}`. "
                    "Keep it in ONE literal, however long: the scanner reads "
                    "text, and half a name generates nothing."
                )
    if split:
        failures.extend(split)

    if failures:
        print(f"tailwind confinement: {len(failures)} violation(s) over {holds} hold(s).")
        print("\n".join(failures))
        return 1
    print(
        f"tailwind confinement: {holds} hold(s), no violation — "
        f"{len(utilities)} utilitie(s) generated, "
        f"{len(DECLARED_COLLISIONS)} declared collision(s), "
        f"{len(declared_tokens)} token(s) declared and all emitted, scan confined, "
        f"{len(sources)} vocabulary file(s) read for split class names."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
