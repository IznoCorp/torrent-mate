#!/usr/bin/env python3
"""What a surface DECLARES against what it WEARS — the two arms that ask it.

Split out of `check-markup-contracts.py` at L10-bis, on a SUBJECT and not on a
line count. The four arms that stayed there all read what the markup EMITS and
ask whether something understands it. These two ask the opposite question, from
the two ends of the same seam:

  ARM 5  a typed variant declared and called by nobody — a vocabulary word the
         surface never says.
  ARM 6  a painting element carrying no class at a site nobody listed — a
         surface saying nothing where a word was needed.

They are siblings because B-138 and B-139 were one defect seen twice: an element
left bare, and the variant that should have dressed it left orphaned. Neither
was visible to any instrument, and for the same reason — nothing emitted, so
there was nothing to be inconsistent with.

Read by `check-markup-contracts.py`, which is the entry point the gate and
`tests/scripts/test_check_markup_contracts.py` both drive.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from markup_text import ROOT, SOURCES  # noqa: E402

HARNESS = ROOT / "frontend" / "maquette" / "harness"

# `export const addFooterAction = cva(` — a typed variant DECLARED. ARM 5
# asks whether anything CALLS it, which is the question the other four
# cannot ask: they all read what the markup EMITS, and a variant nobody
# calls emits nothing to be read. That is why three of them sat green over
# a button the browser was painting itself.
DECLARED_VARIANT = re.compile(r"^export const (\w+) = cva\(", re.MULTILINE)

def variant_declaring_files() -> list[Path]:
    """Returns the files that DECLARE typed variants, in a fixed order.

    Returns:
        Every `variants.ts` under `design/src` plus the members of
        `ui/variants/`, which is one `variants.ts` split by subject when it
        crossed the module ceiling. Derived by walking the tree rather than
        listed: a hand-enumerated corpus is the shape this repository counts,
        and a sixth feature folder joins it by existing.
    """
    files = set(SOURCES.rglob("variants.ts"))
    files |= set((SOURCES / "ui" / "variants").glob("*.ts"))
    return sorted(files)


def variant_reading_files() -> list[Path]:
    """Returns every source that could CALL a variant.

    Returns:
        Every `.ts` and `.tsx` file under `design/src` outside `engine/`. The
        dying engine is excluded because it is hand-written JavaScript that
        imports nothing from the typed side (D5), so counting it would only
        dilute the corpus.
    """
    return sorted(path for path in SOURCES.rglob("*")
                  if path.is_file() and path.suffix in {".ts", ".tsx"}
                  and "engine" not in path.relative_to(SOURCES).parts)


# An IMPORT of the name from a `variants` module. A raw word match was the first
# reader here and nine of the 120 variants were already immune to it: `body`,
# `section`, `screen`, `scrollport`, `segment`, `option`, `suggestions`,
# `releaseName` and `panelField` each have an incidental word somewhere in the
# tree that survives deleting every genuine usage. Four of those dress the
# primary containers — the very ones whose loss IS the B-139 photograph — and
# `releaseName` was laundered by `contract/types.d.ts`, a file GENERATED from
# the backend's OpenAPI: a schema field name satisfying « something calls this
# variant ».
VARIANT_IMPORT = re.compile(
    r"import\s*(?:type\s*)?\{([^}]*)\}\s*from\s*[\"']([^\"']*variants[^\"']*)[\"']")


def names_variant(body: str, name: str) -> bool:
    """Says whether a reader genuinely names one variant.

    An IMPORT of the name from a `variants` module, or a CALL of it. A bare word
    anywhere in the file is not enough, and the nine variants that were immune to
    the first reader are why.

    Args:
        body: One reader file's text.
        name: The variant's exported name.

    Returns:
        True when the file imports the name from a variants module, or calls it.
    """
    for names, _ in VARIANT_IMPORT.findall(body):
        if re.search(rf"\b{re.escape(name)}\b", names):
            return True
    return bool(re.search(rf"\b{re.escape(name)}\s*\(", body))


def check_orphan_variants() -> int:
    """ARM 5: refuses a typed variant that is declared and called by nobody.

    THE DEFECT CLASS, and it was photographed before it was measured. Three
    variants of `features/acquisition/variants.ts` each returned exactly one
    grep hit — their own declaration. So the footer's button carried no class
    at all, the browser painted it with its own defaults — light ground, dark
    text — and what the operator saw on 2026-08-28 was a white rectangle on a
    dark screen (B-139).

    WHY NO OTHER ARM COULD SEE IT. The four above read what the markup EMITS
    and ask whether anything understands it. A variant nobody calls emits
    nothing: no attribute, no class, no selection, nothing to be inconsistent
    with. The declaration reads as coverage and covers nothing, which is
    `BUGS.md` § *Guards green over what they do not read* seen from the side
    nobody was standing on.

    WHAT THIS ARM DOES NOT READ, and the honesty matters more than the arm:

      - IT MATCHES A NAME, NOT A CALL. A variant imported and never invoked
        counts as used here. Telling the two apart needs the type checker, not
        a text reader — and the defect met in the field was a variant no file
        so much as named.
      - IT SAYS NOTHING ABOUT WHETHER THE VARIANT IS RIGHT. That the footer's
        button now carries `text-primary` is this arm's business; that
        `text-primary` is the correct colour is the oracle's and a reviewer's.
      - IT READS `variants.ts` FILES ONLY. A `cva` declared inside a component
        is outside its corpus, deliberately: the contract held here is « the
        vocabulary a surface declares is the vocabulary it uses », and a
        variant declared where it is used cannot break it.

    THE FLOOR IS A HARD ZERO, with no baseline and no exemption list, and it
    was seeded by removing the last orphan rather than by recording it:
    `searchIcon` duplicated a live rule of `base.css` and could never be
    applied, since `<Icon>` takes no class of its own. A floor that records
    what exists is pre-satisfied and can never fall (B-075).

    Returns:
        1 when any declared variant is called by nobody, 0 otherwise.
    """
    declaring = variant_declaring_files()
    reading = variant_reading_files()
    if not declaring or not reading:
        print("check-markup-contracts: no variant declaration or no reader "
              f"under {SOURCES} — the corpus is empty, so « every variant is "
              "called » would mean nothing", file=sys.stderr)
        return 1

    text_of = {path: path.read_text(encoding="utf-8") for path in reading}
    declared = 0
    orphans = []
    for path in declaring:
        for name in DECLARED_VARIANT.findall(text_of[path]):
            declared += 1
            called = any(names_variant(body, name)
                         for other, body in text_of.items() if other != path)
            if not called:
                orphans.append((path, name))

    for path, name in orphans:
        relative = str(path.relative_to(ROOT))
        print(f"  {relative}: `{name}` is exported and named by no other file. "
              "The element it was written for therefore carries no class, and "
              "the browser paints it with its own defaults — which on a dark "
              "screen is a white rectangle (B-139). Wire it, or remove it and "
              "write in its place why nothing can call it.", file=sys.stderr)

    if orphans:
        print(f"\ncheck-markup-contracts: {len(orphans)} declared variant(s) "
              "nobody names. This arm holds a HARD ZERO: there is no baseline "
              "to record them in, because a floor set where the count already "
              "sits can never fall.", file=sys.stderr)
        return 1

    print(f"check-markup-contracts: {declared} typed variant(s) declared in "
          f"{len(declaring)} file(s), every one named by at least one of "
          f"{len(reading)} reader(s) — floor 0.")
    return 0


# THE ELEMENTS THAT PAINT AND CARRY NO CLASS, each with the reason it is
# allowed. A COUNT would have been the easy instrument and the wrong one: six
# is six whether the bare element is a poster image its parent constrains or a
# retry button on a dark error surface, and a ratchet on a number permits
# trading one for the other silently. What is refused here is an UNLISTED site.
#
# Keyed by file and tag rather than by line, because a line moves when anything
# above it does and a guard that has to be re-baselined after every edit is a
# guard people re-baseline without reading.
#
# EVERY ONE OF THE FIVE `legacy` REASONS DIES AT L13. They are painted today by
# `src/styles/legacy.css`, which goes when the engine does — and on that day
# each becomes a real bare element unless its surface has been converted first.
# That is the same latency B-223's `.t` and `.k` carry, and naming it here is
# what makes it findable then rather than reportable by the operator.
BARE_ALLOWED = {
    ("ui/state-surfaces.tsx", "button"): (
        1, "the error surface's retry, painted by `.surferr button` "
           "(legacy.css:445) until L13"),
    ("features/acquisition/page.tsx", "button"): (
        1, "the « connect TMDB » action, inside the same `surfaceError()` and "
           "painted by the same `.surferr button` until L13"),
    ("features/acquisition/add-screen.tsx", "button"): (
        2, "the two `.segmini` segment controls, painted by "
           "`.segmini button` (legacy.css:1553). The engine emits `.segmini` "
           "too, which is why its rules were left in `legacy.css` with a date "
           "of death rather than converted (D-L07-5)"),
    ("app/drawer.tsx", "button"): (
        1, "the `.segmini` appearance control — one SITE, drawn once per "
           "appearance — painted by "
           "`.segmini button` and `.segmini button[aria-pressed=\"true\"]`, "
           "exactly as `add-screen.tsx`'s two are. The engine emits `.segmini` "
           "too, which is why its rules stayed in `legacy.css` with a date of "
           "death rather than converting with the drawer (D-L07-5)"),
    ("ui/panel/index.tsx", "img"): (
        1, "the panel's poster, painted by `.sheetposter img` "
           "(legacy.css:1929) until L13"),
    ("features/media/media-cast.tsx", "img"): (
        1, "a cast portrait, and this one is NOT latent: `castPortrait()` "
           "constrains it with `[&_img]:w-full [&_img]:h-full "
           "[&_img]:object-cover [&_img]:block`, so the parent dresses it "
           "entirely. An image its parent fully constrains is fine, and saying "
           "so is the work as much as fixing is"),
}

# The extractor, and the floor beneath what it reads. A parse that returns
# nothing agrees with a tree that has no painted element in it.
BARE_EXTRACTOR = HARNESS / "bare_elements.mjs"
PAINTED_FLOOR = 40


def typescript_package() -> Path | None:
    """Finds a TypeScript installation the extractor can require.

    Returns:
        The package directory, or None where neither tree is installed.
    """
    for candidate in (ROOT / "frontend" / "maquette" / "design" / "node_modules",
                      ROOT / "frontend" / "node_modules"):
        package = candidate / "typescript"
        if package.is_dir():
            return package
    return None


def check_bare_elements() -> int:
    """ARM 6: refuses a painting element left with no class at an unlisted site.

    THE SIBLING OF ARM 5, and the entry that asked for both says why: one asks
    which variants are never called, the other which elements never call one.
    B-138 and B-139 were each a single element left bare, and neither was
    visible to any instrument — a tag with no class emits nothing for the four
    markup arms to read, and `theme.css` deliberately does not import a
    preflight, so a bare tag keeps the user agent's own painting BY DESIGN.
    That decision was right, and it is exactly what makes bare tags a category
    worth counting.

    IT IS A PARSER, NOT A REGEX, and the reason is the same one `rename.mjs`
    gives: an attribute list spans lines, a `className` may be a template
    literal or a conditional, and an element can be written inside a template
    string a text reader sees as prose. `does this element carry a class` has a
    node kind for an answer.

    WHAT IT DOES NOT READ:

      - A `<div>` or a `<span>`. The user agent paints them nothing, so a bare
        one is not a candidate; the corpus is controls, fields, links and
        images.
      - AN ELEMENT CARRYING A SPREAD. `{...props}` may carry `className` and
        this reader cannot know. The number skipped for that reason is PRINTED
        rather than described, so the blind spot is a figure someone can watch
        move.
      - WHETHER A LISTED SITE'S REASON IS STILL TRUE. Five of the six reasons
        below are « painted by `legacy.css` until L13 ». Nothing here re-reads
        that stylesheet; when it dies, these five become real and this list is
        where they are written down.
      - The engine and the shell. `index.html` is hand-written markup and
        `engine/legacy.js` is the dying JavaScript; neither is TSX.

    Returns:
        1 when a painting element is bare at an unlisted site, 0 otherwise.
    """
    package = typescript_package()
    if package is None:
        print("check-markup-contracts: no TypeScript installation under "
              "frontend/ — this arm parses TSX and cannot answer without one. "
              "Reporting « not installed » rather than « no violation », "
              "because the two are indistinguishable in a log.", file=sys.stderr)
        return 1

    files = sorted(str(path) for path in SOURCES.rglob("*.tsx"))
    try:
        completed = subprocess.run(
            ["node", str(BARE_EXTRACTOR), str(package), *files],
            capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as failure:
        print(f"check-markup-contracts: the bare-element extractor could not "
              f"run ({failure}). An arm that cannot run has not passed.",
              file=sys.stderr)
        return 1
    if completed.returncode != 0:
        print("check-markup-contracts: the bare-element extractor failed — "
              f"{completed.stderr.strip()[:400]}", file=sys.stderr)
        return 1

    reading = json.loads(completed.stdout)
    found: dict[tuple[str, str], list[int]] = {}
    for finding in reading["findings"]:
        relative = str(Path(finding["file"]).relative_to(SOURCES))
        found.setdefault((relative, finding["tag"]), []).append(finding["line"])

    violations = 0
    if reading["elements"] < PAINTED_FLOOR:
        violations += 1
        print(f"  {SOURCES}: {reading['elements']} painting element(s) read, "
              f"under the floor of {PAINTED_FLOOR}. This arm starts at zero "
              "violations, so a parse that returned nothing reports the same "
              "word as one that read the tree.", file=sys.stderr)

    for site, lines in sorted(found.items()):
        relative, tag = site
        allowed = BARE_ALLOWED.get(site)
        if allowed is None:
            violations += 1
            print(f"  {relative}:{', '.join(str(one) for one in lines)}: "
                  f"<{tag}> carries no class. The prototype imports no "
                  "preflight (`theme.css`, L07), so a bare tag keeps the user "
                  "agent's own painting — a light ground and a system border on "
                  "a dark surface, which is what the operator photographed "
                  "(B-139). Dress it, or add it to `BARE_ALLOWED` with the "
                  "reason its own painting is right.", file=sys.stderr)
            continue
        budget, reason = allowed
        if len(lines) > budget:
            violations += 1
            print(f"  {relative}: {len(lines)} bare <{tag}> against {budget} "
                  f"allowed ({reason}). The allowance is a ceiling and never a "
                  "target.", file=sys.stderr)

    stale = [f"{site[0]} <{site[1]}>" for site, (budget, _) in BARE_ALLOWED.items()
             if len(found.get(site, [])) < budget]
    for entry in sorted(stale):
        print(f"  note: {entry} is allowed more bare elements than it has. "
              "Tighten the allowance — a ceiling nobody lowers becomes room "
              "for a defect nobody notices.")

    if violations:
        print(f"\ncheck-markup-contracts: {violations} bare-element "
              "violation(s).", file=sys.stderr)
        return 1

    print(f"check-markup-contracts: {reading['elements']} painting element(s) "
          f"parsed in {len(files)} TSX file(s) (floor {PAINTED_FLOOR}), "
          f"{reading['spreads']} skipped for a spread — "
          f"{sum(len(one) for one in found.values())} bare, every one at a "
          f"listed site with its reason. Five of those reasons expire at L13.")
    return 0
