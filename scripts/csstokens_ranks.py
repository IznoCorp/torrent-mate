#!/usr/bin/env python3
"""The frame's ranked list, and the arm that holds it to what is declared.

WHY IT IS A FILE, AND WHY IT IS THIS FILE'S NEIGHBOUR. `check-css-tokens.py` is
the arm that reads the maquette's stylesheets against a declared record, so this
is its subject; it also stands at 742 non-blank lines against a 800-line soft
warning, and its two other arms — `csstokens_login.py`, `csstokens_motion.py` —
already live in modules of their own for exactly that reason. Imported by
`check-css-tokens.py` and by nothing else, so it runs wherever that guard runs:
`make check`, the repository guards `run.sh` lists, and CI.

WHAT IT READS. `ui/variants/frame.ts` opens on a ranked list that says « every
rank the frame paints is named here once ». Nothing counted it, and the sentence
was false for four ranks a finger meets — the settings save bar at 40, the skip
link at 60, the harness's desktop switch at 70, and the harness panel at 60,
whose entry named no file while the prose beside it implied the wrong one. A
claim with no arm is a sentence in a file, and this repository has watched that
happen often enough to stop writing it down and start counting it.

HOW IT COUNTS. Every entry of that list is `<rank> <what it is> `<site>`
(<file>)`, where the site is a variant's exported name or a CSS selector. The
arm then reads:

  * every `z-index: <n>` in `design/src/styles/*.css`, with the selector of the
    block that declares it;
  * every `z-<n>` or `z-[<n>]` utility in `design/src/**/*.ts(x)`, with the
    exported name of the variant that carries it;
  * every such utility in the shell's own markup, `design/index.html` and
    `design/refonte.html`, with the identity class of the element wearing it.
    THAT ARM IS NOT AN EXTRA. The shell's markup lives in `index.html` because
    the engine captures its containers before React renders — so the frame's own
    header and its install proposal declare their ranks there and nowhere else,
    and both were missing from the list while the list claimed to hold every one.

Comments are stripped from both before anything is read, because the list's own
prose spends `z-47` and `z-index: 41` describing ranks that no longer exist, and
an arm that counted those would report the history as the state.

IT REFUSES BOTH DIRECTIONS. A declaration the list does not name at that rank is
a rank nobody recorded; an entry naming a site nothing declares at that rank any
more is a record that outlived its subject. The second half is the one that
would otherwise rot silently — and it is the half that catches a rank MOVED
rather than added.

WHAT IS NOT A FRAME RANK is named in the same list, under its own heading, and
read the same way: a stacking detail local to one box is still a number someone
chose, and « it is only local » is the sentence a real rank would hide behind.
"""
import pathlib
import re
import sys

DESIGN = pathlib.Path(__file__).resolve().parents[1] / "frontend/maquette/design/src"
LIST_FILE = DESIGN / "ui/variants/frame.ts"

# THE SHELL'S OWN MARKUP. `index.html` carries the phone frame, the topbar, the
# drawer and the layer hosts; `refonte.html` is what is left of the fragment.
SHELL_MARKUP = ("index.html", "refonte.html")

# A CLASS ATTRIBUTE, across the lines it is written over: the shell's are long
# enough to wrap, and a single-line reader would have missed the install
# proposal's rank, which is on the attribute's second line.
CLASS_ATTRIBUTE = re.compile(r'class="([^"]*)"', re.DOTALL)

# ONE ENTRY OF THE RANKED LIST: the rank, what it is, its site in backticks, and
# the file that declares it. The site is a variant's exported name or a CSS
# selector; the two are told apart by the leading `.` or `:` of a selector.
ENTRY = re.compile(r"^\s{5}(\d+)\s+\S.*?\s+`([^`]+)`\s+\(([^)]+)\)\s*$")

# A `z-index` declaration, and the opening of a block, so the selector that
# carries one can be found by walking back to the nearest block that opened.
DECLARED = re.compile(r"\bz-index\s*:\s*(-?\d+)")
OPENS = re.compile(r"^(?!\s*@)(.*?)\s*\{\s*$")

# A `z-` utility, in either spelling Tailwind accepts. `z-auto`, `z-full` and a
# variant-prefixed `md:z-10` are deliberately not read: the first two carry no
# rank, and the third is a rank at one width, which the list does not model and
# which nothing in the maquette declares today.
UTILITY = re.compile(r"(?<![\w-])z-(?:\[(\d+)\]|(\d+))(?![\w-])")

EXPORTED = re.compile(r"^export const (\w+)")


def without_comments(text: str, line_comments: bool) -> str:
    """Blanks a source's comments, keeping every line where it was.

    THE LINES ARE KEPT so a finding can name the one it was read on. Blanking is
    per character rather than per line for the same reason: a declaration
    sharing its line with a trailing comment is still read.

    Args:
        text: The source.
        line_comments: Whether `//` opens a comment, which is true of
            TypeScript and false of CSS.

    Returns:
        The same text with every comment replaced by spaces.
    """
    out = list(text)
    index = 0
    while index < len(text):
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            end = len(text) if end < 0 else end + 2
            for position in range(index, end):
                if out[position] != "\n":
                    out[position] = " "
            index = end
            continue
        if line_comments and text.startswith("//", index):
            end = text.find("\n", index)
            end = len(text) if end < 0 else end
            for position in range(index, end):
                out[position] = " "
            index = end
            continue
        index += 1
    return "".join(out)


def recorded(list_file: pathlib.Path | None = None) -> tuple[dict[tuple[str, int], str], list[str]]:
    """Reads the ranked list.

    Args:
        list_file: The file the list is read from; the frame's variants by
            default. A parameter so a test can hand it a list of its own —
            an arm whose readers only ever read the repository is an arm
            nothing can put a known defect in front of.

    Returns:
        The entries as `(site, rank) -> file`, and the findings raised by the
        list itself — a missing list, or the same site recorded twice.
    """
    list_file = LIST_FILE if list_file is None else list_file
    findings: list[str] = []
    if not list_file.exists():
        return {}, [f"{list_file} does not exist — the ranked list is the record."]
    entries: dict[tuple[str, int], str] = {}
    seen: dict[str, int] = {}
    for line in list_file.read_text(encoding="utf-8").split("\n"):
        found = ENTRY.match(line)
        if not found:
            continue
        rank, site, where = int(found.group(1)), found.group(2), found.group(3)
        if site in seen and seen[site] != rank:
            findings.append(f"`{site}` is recorded at {seen[site]} and at {rank}.")
        seen[site] = rank
        entries[(site, rank)] = where
    if not entries:
        findings.append(f"{list_file.name} records no rank — the list's shape has moved.")
    return entries, findings


def selector_of(lines: list[str], index: int) -> str:
    """The selector of the block a line sits in.

    Args:
        lines: The stylesheet, comments already blanked.
        index: The line the declaration was read on.

    Returns:
        The nearest selector above it, or an empty string.
    """
    for back in range(index, -1, -1):
        opens = OPENS.match(lines[back].rstrip())
        if opens and opens.group(1).strip():
            return opens.group(1).strip().split(",")[0].strip()
    return ""


def declared(design: pathlib.Path | None = None) -> list[tuple[str, int, str]]:
    """Every rank the maquette declares, with the site that declares it.

    Args:
        design: The sources' root; the maquette's `src` by default. The shell's
            markup is read from its parent.

    Returns:
        `(site, rank, where)` triples, `where` being the file and line.
    """
    design = DESIGN if design is None else design
    found: list[tuple[str, int, str]] = []
    for sheet in sorted((design / "styles").glob("*.css")):
        lines = without_comments(sheet.read_text(encoding="utf-8"), False).split("\n")
        for number, line in enumerate(lines):
            hit = DECLARED.search(line)
            if hit:
                site = selector_of(lines, number)
                found.append((site, int(hit.group(1)),
                              f"{sheet.relative_to(design)}:{number + 1}"))
    for source in sorted(design.rglob("*.ts")) + sorted(design.rglob("*.tsx")):
        lines = without_comments(source.read_text(encoding="utf-8"), True).split("\n")
        for number, line in enumerate(lines):
            for hit in UTILITY.finditer(line):
                site = ""
                for back in range(number, -1, -1):
                    name = EXPORTED.match(lines[back])
                    if name:
                        site = name.group(1)
                        break
                found.append((site, int(hit.group(1) or hit.group(2)),
                              f"{source.relative_to(design)}:{number + 1}"))
    for name in SHELL_MARKUP:
        markup = design.parent / name
        if not markup.exists():
            continue
        # THE NEWLINES ARE KEPT, and that is not a detail: a comment replaced
        # by one space collapses every line it spanned, and the two findings
        # this arm was written for then named lines 66 and 90 short of where
        # they are. A finding that points at the wrong line costs its reader
        # the search the finding existed to save.
        text = re.sub(r"<!--.*?-->",
                      lambda hit: "\n" * hit.group(0).count("\n"),
                      markup.read_text(encoding="utf-8"), flags=re.DOTALL)
        for attribute in CLASS_ATTRIBUTE.finditer(text):
            classes = attribute.group(1).split()
            for hit in UTILITY.finditer(attribute.group(1)):
                site = f".{classes[0]}" if classes else ""
                # THE LINE OF THE UTILITY, not of the attribute it sits in:
                # a class attribute here wraps over three lines and the rank is
                # rarely on the first.
                line = text.count("\n", 0, attribute.start(1) + hit.start()) + 1
                found.append((site, int(hit.group(1) or hit.group(2)), f"{name}:{line}"))
    return found


def disagreements(entries: dict[tuple[str, int], str],
                  sites: list[tuple[str, int, str]]) -> list[str]:
    """Where the record and the sources do not say the same thing.

    A FUNCTION OF ITS OWN, and it was not: both halves lived inside the arm,
    which returns one integer for the whole reading. A test could then only
    assert « something was refused » — and two of this arm's own tests passed
    with the half they were written for deleted, because the OTHER half fired
    on the same tree. A verdict that cannot say WHICH reading refused is a
    verdict no mutation can be aimed at.

    Args:
        entries: The ranked list, as `(site, rank) -> file`.
        sites: What the sources declare, as `(site, rank, where)`.

    Returns:
        One finding per disagreement, in reading order.
    """
    findings: list[str] = []
    for site, rank, where in sites:
        if (site, rank) not in entries:
            recorded_rank = next((other for name, other in entries if name == site), None)
            if recorded_rank is None:
                findings.append(
                    f"{where} — `{site}` declares {rank} and the ranked list does not "
                    "name it. Every rank the frame paints is named there once, with "
                    "the file that declares it; a stacking detail local to one box "
                    "is named there too, under its own heading.")
            else:
                findings.append(
                    f"{where} — `{site}` declares {rank}, the ranked list records "
                    f"{recorded_rank}. A rank moves in the list and in the source in "
                    "one step, or the record is the previous version.")
    for (site, rank), where in sorted(entries.items()):
        if not any(name == site and other == rank for name, other, _ in sites):
            findings.append(
                f"the ranked list records `{site}` at {rank} in {where}, and nothing "
                "declares it there any more — a record that outlived its subject is "
                "read as current by the next session.")
    return findings


def ranks_arm(list_file: pathlib.Path | None = None,
              design: pathlib.Path | None = None) -> int:
    """Holds the frame's ranked list to what the maquette declares.

    Args:
        list_file: The file the list is read from; the frame's variants by
            default.
        design: The sources' root; the maquette's `src` by default.

    Returns:
        1 when a rank is declared that the list does not name, or named that
        nothing declares; 0 otherwise.
    """
    entries, findings = recorded(list_file)
    sites = declared(design)
    findings = findings + disagreements(entries, sites)
    for finding in findings:
        print(f"  {finding}", file=sys.stderr)
    if findings:
        print(f"\nranks: {len(findings)} finding(s) — `ui/variants/frame.ts`'s ranked "
              "list is the frame's z-order record, and it is only a record while it "
              "says the same thing as the stylesheets.", file=sys.stderr)
        return 1
    print(f"ranks: {len(entries)} recorded, {len(sites)} declared — the list and the "
          "sources say the same thing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(ranks_arm())
