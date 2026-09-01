#!/usr/bin/env python3
"""Invariant 10 — the frame does not name the domain — and now something counts it.

B-100. The invariant was written on 2026-08-26 with the operator and **no arm
counted any of it**. `CLAUDE.md`'s own line applies without softening: every rule
has an arm, or it is a sentence in a file — and this repository has watched
exactly that happen to `data-*` names, four of which simply stayed.

WHAT THE INVARIANT SAYS. `ui/`, `lib/` and `app/` may carry the application's
SHAPE — a shell, a page host, an address model, a component vocabulary — and not
its SUBJECT. Three exceptions are named because they cannot be anything else:
`lib/addresses.ts` (an address IS the page's identity, D1), `routes/*` (a route
names the page it mounts), and whatever table the shell reads to compose
navigation.

HOW IT IS COUNTED. The domain's vocabulary is the FEATURE DIRECTORY NAMES,
derived from the tree and never listed here: a hand-enumerated corpus is the
shape this register counts, and a tenth feature joins the vocabulary by
existing. Comments are stripped per line before counting, because a comment
naming a feature is a comment explaining WHY the frame does not, and refusing it
would push the explanation out of the file.

⚠ THE STRIPPER IS PER LINE AND THAT IS DELIBERATE. The first attempt at this
measurement, made by hand at L10's close, stripped `//.*` under `re.DOTALL` —
which swallows a file from its first comment to its end — and reported **0**. A
measurement that read nothing, in the wave that filed three entries about
exactly that.

IT IS A RATCHET, PER DIRECTORY, REFUSED UPWARD. Not an interdiction: a shared
component that genuinely needs a domain word is one reviewed line, not a wall —
the invariant says so itself. What is refused is the count going UP without
anybody deciding.

AND THE BASELINE IS READ, NOT ASSUMED. `frame-domain-baseline.json` carries the
per-directory ceiling and the REASON each one is not zero. The entry that asked
for this arm set two requirements that must not be trimmed: the refusal carries
its readable reason, the way `code-vocabulary.txt` does, or it gets worked
around; and the ceiling is not seeded at the current value without being read.
Every number below was read — `lib/queue.ts` alone is 169, and the invariant's
own text calls that « not one reviewed line » and refuses to pretend otherwise.

WHAT THIS ARM DOES NOT READ:

  - THE THREE NAMED EXCEPTIONS, which are exempt by the invariant itself and
    listed here by path.
  - `features/` ITSELF. A feature naming its own domain is the point of a
    feature.
  - THE SAME THING THE INVARIANT'S OWN PROSE COUNTS, and the difference is
    worth stating rather than discovering. § 3 records `lib/queue.ts` at **169**
    domain words; this arm reads **6** there. The invariant's figure came from a
    broader notion of « domain word » — the queue's whole subject vocabulary —
    while this counts the nine FEATURE NAMES, which is the only vocabulary that
    can be derived rather than listed. The narrower measure is what a ratchet
    can hold honestly; the broader one is a judgement, and a judgement in a gate
    becomes a list someone maintains by hand.
  - TEST FILES. A test names what it tests.
  - WHETHER A WORD IS USED AS A DOMAIN WORD. `system` in `app/` may be
    `systemStatus` or `system.exit`; this counts the token. The ratchet is what
    makes that acceptable — it holds a number steady rather than judging a
    word — and a directory whose count must RISE is a line someone writes down
    here with a reason.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DESIGN = ROOT / "frontend" / "maquette" / "design" / "src"
FEATURES = DESIGN / "features"
BASELINE = ROOT / "scripts" / "frame-domain-baseline.json"

# The frame: the three directories the invariant names. `engine/` is the dying
# JavaScript and `styles/`, `mocks/`, `i18n/` are not the frame.
FRAME = ("ui", "lib", "app")

# Named by the invariant, quoted from it: an address IS the page's identity, a
# route names the page it mounts, and the shell reads a table to compose
# navigation.
# ONLY what the invariant itself names. `lib/engine-drawing.ts` stood here and
# the invariant does not name it: it was added because it carried words, which
# is the exact move an exemption exists to prevent. Its words are counted now
# and sit inside `lib/`'s recorded ceiling like every other file's.
EXEMPT = {
    "lib/addresses.ts": "an address IS the page's identity (D1)",
}

# PER LINE, never with DOTALL. See the warning in the header — the same
# expression under DOTALL swallows a file from its first comment to its end.
LINE_COMMENT = re.compile(r"//.*$")
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


# The address model, where every page's SHORT id is declared. It is read the way
# `boundaries_addressing.py` reads it, so the two guards share one spelling of
# the same fact.
ADDRESS_MODEL = DESIGN / "lib" / "addresses.ts"
PAGE_ALIAS = re.compile(r'^\s{2}(\w+):\s*"/', re.MULTILINE)


def domain_vocabulary() -> list[str]:
    """Returns the domain's words: the feature names AND the page aliases.

    THE ALIASES ARE THE HALF THAT WAS MISSING, and without them this arm could
    not see the domain being named at all. The frame does not write
    `acquisition`; it writes `acq`. `app/page-host.tsx` IS a table keyed
    `acq / sys / arr / maint / cfg`, `app/store.ts` carries `page: "acq"`, and
    `acqLibMedItem` in `ui/` — whose ceiling is ZERO — passed. Seven of the nine
    are refused by no other guard either: `scripts/code-abbreviations.txt` holds
    `cfg` and `rel` and none of the rest.

    Both halves are DERIVED — the feature directories from the tree, the aliases
    from `lib/addresses.ts` — so a tenth feature joins by existing and a renamed
    page joins by being declared. Nothing here is a list somebody maintains.

    Returns:
        The words, sorted, with no duplicates.
    """
    features = {path.name for path in FEATURES.iterdir() if path.is_dir() and not path.name.startswith(".")}
    aliases = set(PAGE_ALIAS.findall(ADDRESS_MODEL.read_text(encoding="utf-8"))) if ADDRESS_MODEL.is_file() else set()
    return sorted(features | aliases)


def strip_comments(source: str) -> str:
    """Removes comments, and only comments.

    IT SCANS RATHER THAN SUBSTITUTES, because a `//` or a `/*` inside a STRING
    is not a comment and the regex version could not tell. Both shapes are live
    in this tree: `lib/relay.ts` builds `` `${scheme}//${globalThis.location.host}` ``
    and everything after the `//` on that line — `globalThis`, `location`,
    `host`, `RELAY_PATH` — was unread. The block form is worse: `const opener =
    "/*";` swallowed the file to the next `*/`.

    The header already warns that a `DOTALL` line stripper eats a file from its
    first comment onward. The per-line version fixed that and kept a hole of its
    own; this one has neither, because it is not a pattern.

    Args:
        source: One file's text.

    Returns:
        The same text with comment spans blanked and every string left whole.
    """
    out = []
    index, size = 0, len(source)
    quote = None
    while index < size:
        character = source[index]
        if quote:
            out.append(character)
            if character == "\\" and index + 1 < size:
                out.append(source[index + 1])
                index += 2
                continue
            if character == quote:
                quote = None
            # A `'` OR `"` STRING CANNOT CONTAIN A RAW NEWLINE, and that is the
            # language's rule rather than a tolerance. Reaching one means the
            # quote was never a string opener — which happens on every REGEX
            # LITERAL holding a quote, and this file's own
            # `/url\(["']?(.+?)["']?\)/` is one. The scanner opened a string
            # there and stayed in it for thirty lines: `//` is not a comment
            # inside a string, so every comment it passed was emitted as code
            # and its words were counted. Measured on 2026-09-01, that is two
            # `media` in a comment reported as domain words in the frame, and
            # the guard went RED over prose. Only a backtick spans lines.
            elif character == "\n" and quote != "`":
                quote = None
            index += 1
            continue
        if character in "\"'`":
            quote = character
            out.append(character)
            index += 1
            continue
        if source.startswith("//", index):
            end = source.find("\n", index)
            index = size if end == -1 else end
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            index = size if end == -1 else end + 2
            continue
        out.append(character)
        index += 1
    return "".join(out)


# WORDS INSIDE A NAME, not only words standing alone — and TOKENISED rather
# than matched by a regex. A first version matched `\bword\b` and walked
# straight past `acquisitionLibraryMedia`, which names three domains and
# contains no word boundary at all; that is precisely how a domain word reaches
# the frame, as part of an identifier. The second version used lookarounds with
# `re.IGNORECASE` — under which `[a-z]` matches capitals too, so the lookahead
# rejected every camelCase boundary it was written to accept, and the mutation
# passed a second time. Splitting the identifier is what the rest of this
# repository's name guards do, and it has no such trap.
IDENTIFIER = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
# `from "…"`, `import "…"` and `import("…")` — the quoted half only. The
# keyword is kept so the expression cannot eat an ordinary string.
MODULE_SPECIFIER = re.compile(r"""(\bfrom\s+|\bimport\s*\(?\s*)["'][^"']*["']""")
WORD_BREAK = re.compile(r"[_$]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

# What the frame must carry for a count to mean anything. The three directories
# hold thousands of identifiers between them; a reader that returns a handful
# has stopped reading the tree, and every ceiling below would then be satisfied
# by a measurement of nothing — which is the shape this repository counts
# seventy-three times over.
# PER DIRECTORY, and that is the whole point. A single sum let `ui/` be read as
# nothing while `app/` carried the total alone — and `ui/`'s ceiling is ZERO, so
# a reader that had stopped reading it satisfied that ceiling perfectly and the
# sum stayed far above any floor. Each directory now vouches for itself.
# Each value is HALF the measured corpus, rounded down to the hundred: ui/ read
# 3362, lib/ 2608, app/ 3980 on the day this was written. Half is a margin a
# refactor can spend and a broken reader cannot — losing half a directory's
# identifiers is not a refactor.
IDENTIFIER_FLOOR = {"ui": 1600, "lib": 1300, "app": 1900}


def words_of(source: str) -> list[str]:
    """Splits a source into the lower-cased words its identifiers are built from.

    Args:
        source: One file's text, comments already stripped.

    Returns:
        Every word, in order, so a count over them is a count of words and not
        of regex matches.
    """
    # A MODULE SPECIFIER IS A FILE PATH, not a name the code chose. Both of
    # `ui/`'s hits were `../lib/store-access` and `../../lib/engine-drawing`,
    # naming the FRAME's own `lib/` directory — the word collides with the
    # library page's alias and means the opposite thing. Counting a path would
    # make `ui/`'s ceiling of ZERO a function of where a file happens to sit.
    # The imported NAMES are untouched: only the quoted specifier is blanked.
    source = MODULE_SPECIFIER.sub(lambda match: match.group(0)[0] + '""', source)
    words = []
    for identifier in IDENTIFIER.findall(source):
        words += [part.lower() for part in WORD_BREAK.split(identifier) if part]
    return words


def count_directory(directory: str, words: list[str]) -> tuple[int, dict, int]:
    """Counts domain words in one frame directory, outside comments.

    Args:
        directory: One of `FRAME`.
        words: The domain vocabulary.

    Returns:
        A `(total, per_file, identifiers_read)` triple. `per_file` names only
        the files that carry any — the list a reader needs to act on the number
        — and the identifier count is what says the corpus was read at all.
    """
    root = DESIGN / directory
    vocabulary = set(words)
    total, per_file, seen = 0, {}, 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
            continue
        relative = str(path.relative_to(DESIGN))
        if relative in EXEMPT:
            continue
        # A TEST NAMES WHAT IT TESTS. `lib/addresses.test.ts` mentions ten
        # feature names because it exercises the address model, which is the
        # invariant's own first exception; counting it would make the ceiling
        # rise every time that model gained a case.
        if path.name.endswith((".test.ts", ".test.tsx")):
            continue
        body = words_of(strip_comments(path.read_text(encoding="utf-8")))
        seen += len(body)
        found = sum(1 for word in body if word in vocabulary)
        if found:
            per_file[relative] = found
            total += found
    return total, per_file, seen


def main() -> int:
    """Counts the frame's domain words and refuses the count going up.

    Returns:
        Zero when every directory is at or under its recorded ceiling.
    """
    words = domain_vocabulary()
    if len(words) < 5:
        print(
            f"check-frame-domain: {len(words)} feature(s) found under "
            f"{FEATURES} — the domain vocabulary IS the feature names, so a "
            "corpus this small means the tree was not read and every count "
            "below is meaningless.",
            file=sys.stderr,
        )
        return 1
    if not BASELINE.exists():
        print(
            f"check-frame-domain: {BASELINE.name} is absent. This arm is a "
            "ratchet and a ratchet with no baseline holds nothing — write "
            "one, with the reason each directory is not zero.",
            file=sys.stderr,
        )
        return 1

    recorded = json.loads(BASELINE.read_text(encoding="utf-8"))
    violations = 0
    measured, seen_words = {}, {}
    for directory in FRAME:
        total, per_file, seen = count_directory(directory, words)
        measured[directory] = total
        seen_words[directory] = seen
        ceiling = recorded.get(directory, {}).get("ceiling")
        if ceiling is None:
            violations += 1
            print(
                f"  {directory}/: no ceiling recorded. A directory the "
                "baseline does not name is a directory this arm cannot "
                "refuse.",
                file=sys.stderr,
            )
            continue
        if total > ceiling:
            violations += 1
            worst = sorted(per_file.items(), key=lambda pair: -pair[1])[:4]
            print(
                f"  {directory}/: {total} domain word(s) against a ceiling of "
                f"{ceiling}. The frame carries the application's SHAPE and "
                "not its SUBJECT (invariant 10). Heaviest: "
                + ", ".join(f"{name} ({count})" for name, count in worst)
                + ". Move the word into the feature that owns it, or raise "
                f"the ceiling in {BASELINE.name} with the reason — the "
                "invariant blesses a reviewed line and refuses a drift.",
                file=sys.stderr,
            )
        elif total < ceiling:
            print(
                f"  note: {directory}/ carries {total} against a ceiling of "
                f"{ceiling} — lower it. A ceiling nobody lowers becomes room "
                "for a defect nobody notices."
            )

    for directory, floor in IDENTIFIER_FLOOR.items():
        if seen_words[directory] >= floor:
            continue
        violations += 1
        print(
            f"  {directory}/ yielded {seen_words[directory]} identifier "
            f"word(s), under the floor of {floor}. Every ceiling above is a "
            "MAXIMUM, so a "
            "reader that has stopped reading satisfies all of them at once "
            "— which is the shape this register counts seventy-three times. A "
            "comment stripper that swallows a file from its first comment to "
            "its end reports exactly this.",
            file=sys.stderr,
        )
    print(
        "check-frame-domain: "
        + ", ".join(f"{directory}/ {measured[directory]}" for directory in FRAME)
        + f" domain word(s) outside comments, over a vocabulary of "
        f"{len(words)} feature name(s) and page alias(es) "
        f"({', '.join(words)})"
        + ", read from "
        + ", ".join(f"{directory}/ {seen_words[directory]}" for directory in FRAME)
        + " identifier word(s) (floors "
        + ", ".join(f"{directory}/ {IDENTIFIER_FLOOR[directory]}" for directory in FRAME)
        + f"), {len(EXEMPT)} file(s) exempt by the invariant itself "
        f"({', '.join(sorted(EXEMPT))})"
    )
    if violations:
        print(f"check-frame-domain: {violations} violation(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
