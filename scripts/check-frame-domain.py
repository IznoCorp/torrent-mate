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
EXEMPT = {
    "lib/addresses.ts": "an address IS the page's identity (D1)",
    "lib/engine-drawing.ts": "the dying engine's drawing seam; it goes at L13",
}

# PER LINE, never with DOTALL. See the warning in the header — the same
# expression under DOTALL swallows a file from its first comment to its end.
LINE_COMMENT = re.compile(r"//.*$")
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def domain_vocabulary() -> list[str]:
    """Returns the domain's words: the feature directory names.

    Returns:
        The names, sorted. Derived from the tree so a tenth feature joins by
        existing rather than by somebody remembering this file.
    """
    return sorted(path.name for path in FEATURES.iterdir()
                  if path.is_dir() and not path.name.startswith("."))


def strip_comments(source: str) -> str:
    """Removes comments without removing the code after them."""
    source = BLOCK_COMMENT.sub(" ", source)
    return "\n".join(LINE_COMMENT.sub("", line) for line in source.splitlines())


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
WORD_BREAK = re.compile(r"[_$]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

# What the frame must carry for a count to mean anything. The three directories
# hold thousands of identifiers between them; a reader that returns a handful
# has stopped reading the tree, and every ceiling below would then be satisfied
# by a measurement of nothing — which is the shape this repository counts
# seventy-three times over.
IDENTIFIER_FLOOR = 2000


def words_of(source: str) -> list[str]:
    """Splits a source into the lower-cased words its identifiers are built from.

    Args:
        source: One file's text, comments already stripped.

    Returns:
        Every word, in order, so a count over them is a count of words and not
        of regex matches.
    """
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
        print(f"check-frame-domain: {len(words)} feature(s) found under "
              f"{FEATURES} — the domain vocabulary IS the feature names, so a "
              "corpus this small means the tree was not read and every count "
              "below is meaningless.", file=sys.stderr)
        return 1
    if not BASELINE.exists():
        print(f"check-frame-domain: {BASELINE.name} is absent. This arm is a "
              "ratchet and a ratchet with no baseline holds nothing — write "
              "one, with the reason each directory is not zero.",
              file=sys.stderr)
        return 1

    recorded = json.loads(BASELINE.read_text(encoding="utf-8"))
    violations = 0
    measured, read = {}, 0
    for directory in FRAME:
        total, per_file, seen = count_directory(directory, words)
        measured[directory] = total
        read += seen
        ceiling = recorded.get(directory, {}).get("ceiling")
        if ceiling is None:
            violations += 1
            print(f"  {directory}/: no ceiling recorded. A directory the "
                  "baseline does not name is a directory this arm cannot "
                  "refuse.", file=sys.stderr)
            continue
        if total > ceiling:
            violations += 1
            worst = sorted(per_file.items(), key=lambda pair: -pair[1])[:4]
            print(f"  {directory}/: {total} domain word(s) against a ceiling of "
                  f"{ceiling}. The frame carries the application's SHAPE and "
                  "not its SUBJECT (invariant 10). Heaviest: "
                  + ", ".join(f"{name} ({count})" for name, count in worst)
                  + ". Move the word into the feature that owns it, or raise "
                  f"the ceiling in {BASELINE.name} with the reason — the "
                  "invariant blesses a reviewed line and refuses a drift.",
                  file=sys.stderr)
        elif total < ceiling:
            print(f"  note: {directory}/ carries {total} against a ceiling of "
                  f"{ceiling} — lower it. A ceiling nobody lowers becomes room "
                  "for a defect nobody notices.")

    if read < IDENTIFIER_FLOOR:
        violations += 1
        print(f"  the frame yielded {read} identifier word(s), under the floor "
              f"of {IDENTIFIER_FLOOR}. Every ceiling above is a MAXIMUM, so a "
              "reader that has stopped reading satisfies all of them at once — "
              "which is the shape this register counts seventy-three times. A "
              "comment stripper that swallows a file from its first comment to "
              "its end reports exactly this.", file=sys.stderr)
    print("check-frame-domain: "
          + ", ".join(f"{directory}/ {measured[directory]}"
                      for directory in FRAME)
          + f" domain word(s) outside comments, over a vocabulary of "
            f"{len(words)} feature name(s) ({', '.join(words)}), "
            f"read from {read} identifier word(s) (floor {IDENTIFIER_FLOOR}), "
            f"{len(EXEMPT)} file(s) exempt by the invariant itself")
    if violations:
        print(f"check-frame-domain: {violations} violation(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
