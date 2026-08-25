"""R80 — a typed variant and the residue rule shadowing it say the same thing.

THE DEFECT, AND IT IS INVISIBLE BY CONSTRUCTION. `src/styles/legacy.css` is
deliberately UNLAYERED so it wins over `@layer utilities` on the markup the
dying engine draws (D10). It also lands on markup COMPONENTS draw: several
shared identity anchors carry BOTH a residue rule and a typed variant, and an
unlayered normal declaration beats every cascade layer whatever the
specificity. On those elements the utility loses. The declarations agree today,
term for term, so nothing renders wrongly and the oracle says so — what is
unheld is the day one of them drifts. Edit the variant and the screen does not
move; edit it wrongly and no gate speaks. That is B-067.

WHAT THIS RULE DOES, AND WHY IT NEEDS A BROWSER. It pairs each residue selector
with the typed variant wearing the same identity anchor, then renders TWO
probes side by side in the real document: one carrying the anchor classes
alone, which the residue styles, and one carrying the variant's utilities
alone, which Tailwind styles. It then compares `getComputedStyle` for exactly
the properties the residue DECLARES. A textual comparison could not do this:
`flex: 0 0 auto` and `flex-none` are the same computed value written two ways,
`rounded-full` resolves through `--radius-full`, and a guard that had to know
Tailwind's mapping would be a table someone maintains by hand — which is the
shape of guard this repository keeps finding green over what it does not read.

MEASURED UNDER BOTH MOTION PREFERENCES, and that is not thoroughness for its
own sake. Part of the residue sits inside
`@media (prefers-reduced-motion: no-preference)`, and a utility carries no such
condition unless it is written `motion-safe:`. Under `reduce` the residue rule
drops out and an unconditional utility keeps applying — the two sides agree
exactly under one preference and disagree under the other. That is how the
hero's entrance animation was found running for a reader who had asked for no
motion, against invariant 14, with every other instrument green.

WHAT IT DOES NOT READ, said here rather than discovered later:

  - A residue selector with NO variant of the same anchor is not compared, and
    the count of those is PRINTED. They are the engine's own markup, which is
    the residue's whole purpose.
  - A DESCENDANT selector (`.sechead .t`) is named and counted, never staged.
    The anchors it would pair on are one and two letters long — `t`, `d`, `k`,
    `n`, `lb` — and they collide across contexts: `.dcard .t` and `.sechead .t`
    would both pair with `sectionTitle()`, and only one of them is that
    variant. Telling the real pair from the collision needs the DOCUMENT — does
    a component actually draw this variant inside that ancestor — and the
    answer varies with which state happens to be on screen. A rule whose corpus
    depends on that is a rule that reports different things on different days.
    Four such pairs stand today and they are printed by name every run.
  - A QUALIFIER the variant does not emit is not a divergence. `.screen.open`,
    `.sheet.dragging` and their kind are written by the ENGINE through
    `classList`, so there is no branch to compare and the residue says so in
    its own comments. They are counted and named, not refused.
  - A pair where a declared property reads EMPTY on both probes is NOT counted
    as agreement. It is reported as unmeasurable, because two empty strings
    comparing equal is exactly the pre-satisfied hold this project has paid for.
  - A FACTORY whose base string cannot be read is a VIOLATION and never a skip.
    A factory that drops out of the table takes its pair with it, and the run
    reports one comparison fewer with nothing red — which is what happened
    three times before the comment stripper landed. The base is read from
    double-quoted literals; a factory built any other way must say so out loud.

IT DIES WITH D10. When L13 removes the residue there is nothing left to shadow
a variant, and this rule goes in the same move as the decision that makes it
necessary.
"""
import asyncio
import pathlib
import re
import sys

from common import BAR, Journal, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESIDUE = ROOT / "design" / "src" / "styles" / "legacy.css"
# WHERE A FACTORY MAY BE DECLARED: anywhere in the component tree. Named by
# SHAPE and not by file, for the reason `common.py` gives about the design's
# sources — a tuple of paths misses the factory written tomorrow. A first
# version of this read `ui/variants*.ts` and `features/*/variants.ts` and found
# 44 factories while missing the three files that hold the shared vocabulary,
# so it paired ONE anchor out of the eight it was written for and reported no
# divergence. The engine is excluded: it draws its markup by hand and owns no
# variant.
_COMPONENTS = ROOT / "design" / "src"
VARIANT_SOURCES = sorted(
    path for extension in ("*.ts", "*.tsx")
    for path in _COMPONENTS.rglob(extension)
    if "engine" not in path.relative_to(_COMPONENTS).parts
)

# A rule head, once comments are stripped: everything up to `{`, then the body.
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)
COMMENT = re.compile(r"/\*.*?\*/", re.S)

# A selector this rule can build a probe for. Two shapes and no more:
#   `.a` / `.a.b`      one element wearing one or two classes
#   `.a .b`            one element inside another
# Anything with a pseudo-class, an attribute, a combinator or an element name
# is left alone: the probe would have to reproduce a state or a structure this
# rule does not know how to stage, and a probe built wrong reports a divergence
# that is the probe's, not the interface's.
COMPOUND = re.compile(r"^\.([\w-]+)(?:\.([\w-]+))?$")
DESCENDANT = re.compile(r"^\.([\w-]+)\s+\.([\w-]+)$")

# A declaration's property name, read off a rule body.
PROPERTY = re.compile(r"(?:^|[;{])\s*([a-zA-Z-][\w-]*)\s*:", re.M)

# `export const NAME = cva(` — the factory, wherever it is declared.
FACTORY = re.compile(r"export const ([A-Za-z_$][\w$]*)\s*=\s*cva\s*\(")

# A double-quoted class-list literal. The sources write every one of them with
# double quotes; a single-quoted one would be missed, so the count of factories
# read is printed and held above zero.
LITERAL = re.compile(r'"((?:\\.|[^"\\])*)"')


def strip_comments(text):
    """Returns the stylesheet with its comments removed."""
    return COMMENT.sub(" ", text)


def balanced(text, start):
    """Returns the index just past the `(` opened at `start`.

    Args:
        text: The source.
        start: The index OF the opening parenthesis.

    Returns:
        The index one past the matching `)`.
    """
    depth = 0
    index = start
    while index < len(text):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return len(text)


def split_top_level(text):
    """Splits a call's arguments on TOP-LEVEL commas.

    Args:
        text: The text between a call's parentheses.

    Returns:
        The arguments, as written.
    """
    parts, current, depth, quote = [], [], 0, None
    for index, character in enumerate(text):
        if quote:
            current.append(character)
            if character == quote and text[index - 1] != "\\":
                quote = None
            continue
        if character in "\"'`":
            quote = character
        elif character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(character)
    parts.append("".join(current))
    return parts


def without_comments(text):
    """Blank out a TypeScript source's comments, keeping every offset.

    THIS IS NOT TIDINESS, IT IS THE READER'S CORRECTNESS. A `cva()` call's
    first argument is separated from the rest by a TOP-LEVEL COMMA, and this
    repository's comments are full of commas. One comment's comma ended the
    first argument after four characters, so a factory's base came out EMPTY,
    its anchor vanished from the table, and its pair simply stopped being
    compared. Nothing failed — the rule printed one pair fewer.

    Quotes and templates are tracked, so a `//` inside a class-name literal is
    not mistaken for a comment. Lengths are preserved so nothing downstream has
    to care that anything was removed.

    Args:
        text: A TypeScript source.

    Returns:
        The same text with every comment replaced by spaces of equal length.
    """
    out = list(text)
    index, quote, length = 0, None, len(text)
    while index < length:
        character = text[index]
        if quote:
            if character == "\\":
                index += 2
                continue
            if character == quote:
                quote = None
            index += 1
            continue
        if character in "\"'`":
            quote = character
            index += 1
            continue
        if character == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] != "\n":
                out[index] = " "
                index += 1
            continue
        if character == "/" and index + 1 < length and text[index + 1] == "*":
            end = text.find("*/", index + 2)
            end = length if end == -1 else end + 2
            for blank in range(index, end):
                if out[blank] != "\n":
                    out[blank] = " "
            index = end
            continue
        index += 1
    return "".join(out)


def read_factories():
    """Reads every `cva()` factory into its anchor, its base and its branches.

    THE ANCHOR IS THE FIRST TOKEN of the base string, and that is not a guess:
    `ui/variants.ts` states the convention in its own header — « the original
    class name is kept at the front of every string, emptied of style » — and
    D4 wants an anchor to be exactly that.

    Returns:
        A `(factories, files_read, unread)` triple. `factories` maps an anchor
        class to a dict carrying the factory's name, its base class list, and
        its branches keyed by the branch's own leading token. `unread` names
        every factory whose base came out EMPTY — a factory the reader could
        not read is a pair that silently stops being compared, so it is a
        violation and never a skip.
    """
    factories = {}
    unread = []
    for path in VARIANT_SOURCES:
        text = without_comments(path.read_text(encoding="utf-8"))
        for found in FACTORY.finditer(text):
            opening = text.index("(", found.end() - 1)
            call = text[opening + 1:balanced(text, opening) - 1]
            arguments = split_top_level(call)
            base = " ".join(
                piece for literal in LITERAL.finditer(arguments[0])
                for piece in [literal.group(1)]
            ).split()
            if not base:
                unread.append(f"{found.group(1)}() in {path.name}")
                continue
            branches = {}
            for argument in arguments[1:]:
                for literal in LITERAL.finditer(argument):
                    tokens = literal.group(1).split()
                    if tokens:
                        branches.setdefault(tokens[0], tokens)
            factories[base[0]] = {
                "name": found.group(1),
                "file": path.name,
                "base": base,
                "branches": branches,
            }
    return factories, len(VARIANT_SOURCES), unread


def read_residue():
    """Reads the residue's probe-able selectors and the properties each declares.

    Returns:
        A (rules, total) pair. `rules` is a list of dicts describing one
        selector each; `total` is how many selectors the sheet declares in all,
        so the share this rule can stage is reported rather than implied.
    """
    text = strip_comments(RESIDUE.read_text(encoding="utf-8"))
    rules, total = [], 0
    for match in RULE.finditer(text):
        head, body = match.group(1), match.group(2)
        properties = [name.lower() for name in PROPERTY.findall(body)]
        if not properties:
            continue
        for selector in (piece.strip() for piece in head.split(",")):
            if not selector or selector.startswith("@"):
                continue
            total += 1
            compound = COMPOUND.match(selector)
            descendant = DESCENDANT.match(selector)
            if compound:
                classes = [c for c in compound.groups() if c]
                rules.append({"selector": selector, "shape": "compound",
                              "classes": classes, "properties": properties})
            elif descendant:
                rules.append({"selector": selector, "shape": "descendant",
                              "classes": [descendant.group(2)],
                              "ancestor": descendant.group(1),
                              "properties": properties})
    return rules, total


def pair_up(rules, factories):
    """Builds the probe cases: a residue selector beside the variant it shadows.

    Args:
        rules: What `read_residue()` returned.
        factories: What `read_factories()` returned.

    Returns:
        A (cases, unpaired, toggled, contextual) tuple. `unpaired` lists the
        residue selectors wearing an anchor no variant claims — the engine's
        own markup, which is the residue's whole purpose. `toggled` lists the
        qualifiers no variant emits: `.screen.open`, `.sheet.dragging` and
        their kind, which the ENGINE writes through `classList` and which
        therefore have no branch to compare against, by design. `contextual`
        lists the descendant selectors this rule declines to stage, and why is
        in the module docstring.
    """
    cases, unpaired, toggled, contextual = [], [], [], []
    for rule in rules:
        anchor = rule["classes"][0]
        factory = factories.get(anchor)
        if factory is None:
            unpaired.append(rule["selector"])
            continue
        if rule["shape"] == "descendant":
            contextual.append(f"{rule['selector']} ↔ {factory['name']}()")
            continue
        worn = list(rule["classes"])
        utilities = list(factory["base"])
        if len(worn) == 2:
            branch = factory["branches"].get(worn[1])
            if branch is None:
                toggled.append(f"{rule['selector']} ({factory['name']}() emits no « {worn[1]} »)")
                continue
            utilities += branch
        cases.append({
            **rule,
            "factory": factory["name"],
            "worn": worn,
            # The identity anchors are what the residue selects ON. The variant
            # keeps them at the front of its own string, so they have to come
            # OFF the utility probe or it would wear the residue rule too and
            # the comparison would hold a thing against itself.
            "utilities": [token for token in utilities if token not in set(worn)],
        })
    return cases, unpaired, toggled, contextual


MEASURE = """(cases) => {
  const host = document.createElement("div");
  host.setAttribute("data-probe", "residue");
  // Off the flow and out of the way: the probes must not disturb the page the
  // other rules and the oracle measure, and a layout-affecting host would be
  // its own defect. Removed again before this function returns.
  host.style.cssText = "position:absolute;left:-10000px;top:0;width:390px";
  document.body.appendChild(host);

  const make = (classes) => {
    const node = document.createElement("div");
    node.className = classes.join(" ");
    host.appendChild(node);
    return node;
  };
  const read = (node, properties) => {
    const style = getComputedStyle(node);
    const out = {};
    for (const property of properties) out[property] = style.getPropertyValue(property);
    return out;
  };

  const results = [];
  for (const one of cases) {
    // TWO SIBLINGS, SAME PARENT, SAME TAG. Everything that is not the classes
    // is held equal, so a difference in the reading is a difference in the CSS
    // and cannot be a difference in the context.
    const shadowed = make(one.worn);
    const twin = make(one.utilities);
    results.push({
      selector: one.selector,
      factory: one.factory,
      left: read(shadowed, one.properties),
      right: read(twin, one.properties),
    });
  }
  host.remove();
  return results;
}"""


async def main():
    """Stages every pair in the real document and holds the two sides equal."""
    journal = Journal("R80 — the residue and the variant it shadows agree")

    factories, files_read, unread = read_factories()
    rules, declared = read_residue()
    cases, unpaired, toggled, contextual = pair_up(rules, factories)

    journal.check("the variant sources are read",
                  files_read > 0 and len(factories) > 0 and not unread,
                  f"{len(factories)} factory(ies) over {files_read} component source(s)"
                  + (f"; UNREADABLE: {', '.join(unread)}" if unread else ""))
    journal.check("the residue is read",
                  declared > 0,
                  f"{declared} selector(s) declared, {len(rules)} of a shape this rule can read")
    # THE FLOOR, and it is the hold that matters most. A pairing that found
    # nothing would print « no divergence » and mean « I compared nothing » —
    # the reading this rule exists to refuse, and the reading a first version of
    # it actually produced: scanning `variants*.ts` alone it missed the three
    # files holding the shared vocabulary and paired ONE anchor out of eight.
    # Seven is B-067's own count of shared anchors, so the floor cannot drift
    # below the finding that put this rule here.
    journal.check("the shared anchors are found",
                  len(cases) >= 7,
                  f"{len(cases)} residue selector(s) shadow a typed variant; "
                  f"{len(unpaired)} wear an anchor no variant claims, "
                  f"{len(toggled)} carry an engine-written qualifier, "
                  f"{len(contextual)} are contextual")

    payload = [{
        "selector": case["selector"],
        "factory": case["factory"],
        "worn": case["worn"],
        "utilities": case["utilities"],
        "properties": case["properties"],
    } for case in cases]

    readings = {}
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        for preference in ("no-preference", "reduce"):
            _, page = await open_page(browser, reduced_motion=preference)
            readings[preference] = await page.evaluate(MEASURE, payload)
        await browser.close()

    for index, case in enumerate(cases):
        divergent, blind = [], []
        for preference, measured in readings.items():
            reading = measured[index]
            for prop in case["properties"]:
                left = reading["left"].get(prop, "")
                right = reading["right"].get(prop, "")
                if not left and not right:
                    blind.append(f"{prop} under {preference}")
                elif left != right:
                    divergent.append(
                        f"{prop} under {preference}: residue « {left} » vs variant « {right} »")
        journal.check(
            f"{case['selector']} ↔ {case['factory']}()",
            not divergent and not blind,
            "; ".join(divergent + [f"{entry}: neither side reads a value" for entry in blind])
            or f"{len(case['properties'])} propertie(s), identical under both motion preferences")

    print(f"\n{BAR}")
    print("NOT STAGED, and named rather than hidden:")
    print(f"  {len(contextual)} contextual pair(s): " + ", ".join(contextual))
    print(f"  {len(toggled)} engine-written qualifier(s): " + ", ".join(toggled))
    print(f"  {len(unpaired)} selector(s) the engine alone draws")
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
