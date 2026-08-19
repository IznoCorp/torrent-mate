#!/usr/bin/env python3
"""Extract the prototype's application CSS into the stylesheet the app ships.

`frontend/maquette/design/refonte.html` is the product (product-intent §15). Its
`<style>` element is physically split in two, and only the second half ships:

- **BLOCK 1 — PROTOTYPE HARNESS**: the phone frame, the demo bars, the design
  notes, the scenario switch. Never extracted.
- **BLOCK 2 — APPLICATION CSS**: everything the app renders.

This script lifts BLOCK 2, scopes every rule under `.tm`, and writes
`frontend/src/styles/ps/app-surface.css`. The app imports that file; nobody
edits it. **Editing the generated file by hand is the defect, not a shortcut** —
`--check` re-runs the extraction and fails on any difference, which is the same
guard that protects `openapi.json` / `schema.d.ts`.

Extraction works from an ALLOWLIST, never a blocklist: `regions.json` →
`exportedSelectors` names what may ship, so a prototype-only helper can never
silently reach production by being forgotten. `frontend/maquette/harness/
export.py` is the other half of that contract — it fails on any BLOCK 2 class
that is neither on the allowlist nor classified as harness, so the two together
mean « listed and exported » and « exported and listed ».

Scoping under `.tm` rather than shipping bare selectors is what lets this
stylesheet coexist with the app's own: the prototype styles `.card`, and so
does half the web.

Usage:
    python3 scripts/extract-maquette-css.py            # write the stylesheet
    python3 scripts/extract-maquette-css.py --check    # fail on drift
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROTOTYPE = ROOT / "frontend" / "maquette" / "design" / "refonte.html"
REGIONS = ROOT / "frontend" / "maquette" / "regions.json"
OUTPUT = ROOT / "frontend" / "src" / "styles" / "ps" / "app-surface.css"

# The scope every rule is nested under. One class, on the app's own root.
SCOPE = ".tm"

HEADER = """/* GENERATED — do not edit.
 *
 * Extracted from `frontend/maquette/design/refonte.html` (BLOCK 2 — APPLICATION CSS)
 * by `scripts/extract-maquette-css.py`, and scoped under `{scope}`.
 *
 * The prototype IS the product (product-intent §15). A pixel changes there and
 * is extracted here; a hand edit to this file is reverted by the drift guard in
 * `make check`, because a retyped value does not merely risk drifting — it
 * CONCEALS a defect in the reference, since the copy becomes the only place
 * anyone ever looks.
 *
 * {count} rules, from {classes} allowlisted selectors.
 * {dropped} rules were dropped as prototype harness.
 *
 * Declared BOTH exported and harness, and read as exported because extraction
 * only ever looks at BLOCK 2: {ambiguous}.
 */
"""


def application_block(source: str) -> str:
    """Returns BLOCK 2 of the prototype's `<style>`, comments included.

    Args:
        source: The prototype's full text.

    Returns:
        The CSS text from BLOCK 2's header comment to the closing `</style>`.

    Raises:
        SystemExit: When the harness/app separation is not found — a prototype
            without it has nothing this script may safely ship.
    """
    i = source.find("BLOCK 2")
    if i < 0:
        sys.exit("BLOCK 2 not found: the maquette has lost its harness / "
                 "application separation, and nothing can be extracted without it.")
    # Back to the OPENER of the header comment: slicing on « BLOCK 2 » leaves an
    # orphan `*/` behind, and the header's own prose then parses as selectors.
    i = source.rfind("/*", 0, i)
    end = source.find("</style>", i)
    if end < 0:
        sys.exit("the maquette's `<style>` element never closes.")
    return source[i:end]


def contract() -> tuple[set[str], set[str]]:
    """The two lists `regions.json` keeps, and they are not symmetric.

    `exportedSelectors` is the allowlist: what may ship. `harnessSelectors` is
    the prototype's own chrome — the phone frame, the demo bars, the design
    notes — listed so its exclusion is EXPLICIT rather than implied. Some of it
    lives inside BLOCK 2 because it dresses the same surfaces, so it has to be
    dropped by name rather than refused: a harness class is not a forgotten
    export, and treating it as one would stop the extraction on every run.

    Returns:
        A `(exported, harness)` pair of selector sets.
    """
    import json

    with REGIONS.open(encoding="utf-8") as f:
        data = json.load(f)
    return set(data["exportedSelectors"]), set(data.get("harnessSelectors", []))


def rules(css: str) -> list[tuple[str, str, str]]:
    """Splits CSS into its rules, keeping at-rules whole.

    Comments are dropped: they document the prototype's decisions and belong
    with it, not in a generated file nobody reads.

    Args:
        css: The CSS text of BLOCK 2.

    Returns:
        A list of `(at_rule, selector, body)` triples. `at_rule` is the
        enclosing `@media` / `@supports` condition, or `""` at the top level.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    collected: list[tuple[str, str, str]] = []
    i = 0
    context = ""
    while i < len(css):
        opens = css.find("{", i)
        if opens < 0:
            break
        head = css[i:opens].strip()
        # Find this block's matching close, counting nesting.
        depth = 0
        j = opens
        while j < len(css):
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        body = css[opens + 1 : j]
        if head.startswith("@") and not head.startswith("@keyframes"):
            # A conditional group: recurse into it, carrying the condition.
            for _, sel, sub_body in rules(body):
                collected.append((head, sel, sub_body))
        elif head.startswith("@keyframes"):
            # Animations have no selector to allowlist and no scope to take.
            collected.append(("", head, body))
        elif head:
            collected.append((context, head, body))
        i = j + 1
    return collected


def apply_scope(selector: str) -> str:
    """Scopes one selector list under {SCOPE}.

    `:root` becomes the scope itself rather than a descendant of it: custom
    properties declared on the document's root must land on the app's root, or
    every `var()` under it resolves to nothing.

    Args:
        selector: A comma-separated selector list.

    Returns:
        The same list, each part scoped.
    """
    parts = []
    for part in selector.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith(":root") or part == "html" or part == "body":
            parts.append(SCOPE + part[len(part.split()[0]):] if " " in part else SCOPE)
        elif part.startswith("@"):
            parts.append(part)
        else:
            parts.append(f"{SCOPE} {part}")
    return ", ".join(parts)


def classes_of(selector: str) -> set[str]:
    """The class names a selector list mentions."""
    return set(re.findall(r"\.([a-zA-Z][\w-]*)", selector))


def build() -> str:
    """Builds the stylesheet the app ships.

    Returns:
        The full CSS text, header included.

    Raises:
        SystemExit: When a rule mentions a class the allowlist does not carry.
            That is the allowlist doing its job: a selector reaches production
            only by being listed, never by being forgotten.
    """
    source = PROTOTYPE.read_text(encoding="utf-8")
    allowed, harness = contract()
    allowed_classes = set()
    for s in allowed:
        allowed_classes |= classes_of(s)
    harness_classes = set()
    for s in harness:
        harness_classes |= classes_of(s)
    # A class on BOTH lists is a genuine contradiction in the contract, and it
    # is not hypothetical: eight of them are, because the prototype's demo bars
    # and the app's own bars share their names — one set lives in BLOCK 1, the
    # other in BLOCK 2. Extraction only ever looks at BLOCK 2, so the reading
    # that fits is « exported ». It is REPORTED rather than resolved in
    # silence: a contradiction nobody is told about is how the wrong reading
    # survives for a year.
    ambiguous = sorted(harness_classes & allowed_classes)
    harness_classes -= allowed_classes

    lines: list[str] = []
    kept = 0
    dropped = 0
    refused: dict[str, set[str]] = {}
    for condition, selector, body in rules(application_block(source)):
        classes = classes_of(selector)
        if classes and classes <= harness_classes:
            dropped += 1
            continue
        unknown = classes - allowed_classes - harness_classes
        if unknown:
            refused.setdefault(selector.strip(), set()).update(unknown)
            continue
        body = "\n".join(f"    {l.strip()}" for l in body.strip().splitlines() if l.strip())
        if not body:
            continue
        rule = f"{apply_scope(selector)} {{\n{body}\n}}"
        if condition:
            rule = f"{condition} {{\n" + "\n".join("  " + l for l in rule.splitlines()) + "\n}"
        lines.append(rule)
        kept += 1

    if refused:
        detail = "\n".join(f"  {sel} → {', '.join(sorted(cls))}"
                           for sel, cls in sorted(refused.items())[:20])
        sys.exit(
            "rules name classes that `regions.json` does not allow.\n"
            "Extraction works from an ALLOWLIST: add them to "
            "`exportedSelectors`, or classify them as harness.\n" + detail)

    # AND THE OTHER DIRECTION, which nothing checked: an allowlist entry naming
    # a class the prototype no longer declares. Only `expected - allowed` was
    # ever computed, so the list could grow stale and never shrink — five dead
    # French selectors (`.ep.en_attente` and friends) survived a whole renaming
    # campaign in it, matching nothing, under a green gate. An allowlist that
    # can only rot is the same failure as a map naming places the territory
    # does not have.
    declared = {cls for _, selector, _ in rules(application_block(source))
                for cls in classes_of(selector)}
    orphan = sorted(allowed_classes - declared - harness_classes)
    if orphan:
        sys.exit(
            "`exportedSelectors` names classes the prototype does not declare:\n"
            + "\n".join(f"  {cls}" for cls in orphan[:20])
            + "\nRemove them, or draw them in the maquette. An allowlist entry "
              "that matches nothing excuses nothing and hides its own staleness.")

    header = HEADER.format(scope=SCOPE, count=kept, classes=len(allowed),
                           dropped=dropped,
                           ambiguous=", ".join(ambiguous) or "none")
    return header + "\n" + "\n\n".join(lines) + "\n"


def main() -> int:
    """Extracts the application CSS, or reports that it has drifted.

    Returns:
        1 on drift under `--check`, 0 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit with an error if the file has drifted")
    args = parser.parse_args()

    expected = build()
    if args.check:
        if not OUTPUT.is_file():
            print(f"extract-maquette-css: {OUTPUT.relative_to(ROOT)} is missing — "
                  "run `python3 scripts/extract-maquette-css.py`.", file=sys.stderr)
            return 1
        current = OUTPUT.read_text(encoding="utf-8")
        if current != expected:
            print("extract-maquette-css: the stylesheet has DRIFTED from the maquette.\n"
                  "Editing this generated file by hand is the defect, "
                  "not a shortcut: change the maquette, then re-run\n"
                  "  python3 scripts/extract-maquette-css.py", file=sys.stderr)
            return 1
        print(f"extract-maquette-css: up to date ({len(expected.splitlines())} lines).")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"extract-maquette-css: {OUTPUT.relative_to(ROOT)} written "
          f"({len(expected.splitlines())} lines).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
