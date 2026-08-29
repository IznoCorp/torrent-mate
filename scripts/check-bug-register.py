#!/usr/bin/env python3
"""The bug register's own index, held by four arms, plus the tool that stops the recurrence.

`BUGS.md` is the ground every figure about this work is drawn from, and until
2026-08-29 nothing read it. Seven identifiers — B-079 to B-085 — carried TWO rows
in the same table, one saying `fixed #505` and one saying `open`, and the count
handed to the operator that day announced 48 open entries where there were 42.
A register whose index contradicts itself makes every figure drawn from it false,
including a wave's account of its own closures.

  duplicate-row      one identifier, one row. This is B-102, and it is
                     unambiguous: the file's two indexes have different shapes —
                     the open index is a table, the closed index a bullet list —
                     so a duplicate row cannot be one entry seen from two places.
  status-vocabulary  a status outside the declared vocabulary. A typo makes a row
                     invisible to every count that greps for a word, and a
                     placeholder nobody filled in (`fixed #NNN`, met on B-219)
                     says a merge was never written down.
  invariant-numbers  B-103: two invariants carrying the same number in
                     `frontend-architecture.md`. Same family, same file: those
                     numbers are CITED, and a brief has already instructed a wave
                     on « invariant 10 » meaning the wrong one.
  corpus             THE NUMBER OF ROWS READ IS PRINTED, with a floor. An arm
                     that finds zero rows and reports clean is the shape this
                     repository has paid for seventy-three times
                     (`BUGS.md` § Guards green over what they do not read).

WHAT THIS GUARD DOES NOT READ, and the list is the point:

  - IT READS THE INDEX, NEVER THE BODIES. A row marked `open` whose body says
    « FIXED by #505 » is invisible to it once the duplicate is gone — and that is
    exactly the state B-079 to B-085 were in. Reconciling an index against prose
    is a text heuristic and fragile; naming the blind spot is worth more than an
    arm that gets it wrong and is believed.
  - IT READS `BUGS.md` ALONE. `BUGS-CLOSED.md` carries bodies moved out of it and
    is in no arm's corpus — only `--next` looks there, and only for a number.
  - IT CANNOT SEE ANOTHER BRANCH. The defect that repeated three times in
    twenty-four hours (B-147, then B-152, B-160, B-219 for a single entry) is not
    a duplicate row: it is two branches taking numbers from a register the other
    is writing. No guard on `main` can see a neighbouring branch. `--next` answers
    that, and it is a tool, not an arm.
  - IT DOES NOT HOLD RULE 2. « Exactly one bug may hold `fixing` » is a rule of
    the file this guard does not enforce; `status-vocabulary` accepts the word
    wherever it appears.
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTER = ROOT / "BUGS.md"
CLOSED_REGISTER = ROOT / "BUGS-CLOSED.md"
ARCHITECTURE = ROOT / "docs" / "reference" / "frontend-architecture.md"

# An index row: the identifier first, the status last and backticked. The
# backticks are what separates this table from the twelve-entry historical table
# further down the file, whose last column is a DATE and which carries no status
# at all. Reading both as one corpus would report a violation on a table that
# has no status to be wrong about.
INDEX_ROW = re.compile(r"^\|\s*([BE]-\d{3})\s*\|.*\|\s*`([^`]+)`\s*\|\s*$")

# Every identifier anywhere, for `--next`. A number is taken the moment it is
# WRITTEN, not the moment it reaches the index — a body referring to B-217 has
# reserved it even if its row has not landed yet.
ANY_IDENTIFIER = re.compile(r"\b([BE])-(\d{3})\b")

# The declared vocabulary of § Status vocabulary. `fixed #NNN` with a real number
# is the fifth; the literal `NNN` is a placeholder and is refused on purpose.
FIXED_STATUS = re.compile(r"^fixed #\d+$")
PLAIN_STATUSES = ("open", "fixing", "to confirm", "closed")

# The invariants live in one section of one file. The heading is matched rather
# than a line number so a section moving does not silently empty the corpus.
INVARIANTS_HEADING = re.compile(r"^## 3\. Invariants")
SECTION_HEADING = re.compile(r"^## ")
NUMBERED_ITEM = re.compile(r"^(\d+)\.\s+\S")

# The floor beneath the index. It is seeded WELL BELOW the count at the time of
# writing (measured: 214 status rows on 2026-08-29) and never at it: a floor set
# where the count already sits is pre-satisfied and can never fall, which is one
# of the shapes B-085 counts and the one this repository has met twice in two
# waves. What it defends against is a regex that stops matching — a column added,
# the backticks dropped — not an ordinary deletion.
INDEX_FLOOR = 150

# And the same for the invariants: fourteen are written today, and an arm that
# reads zero of them agrees with an arm that read all fourteen.
INVARIANT_FLOOR = 8


def read_index_rows(text):
    """Collect the register's index rows, in file order.

    Args:
        text: The whole of `BUGS.md`.

    Returns:
        A list of `(identifier, status, line_number)` tuples, one per row of the
        open index. The historical table, whose last column is a date rather
        than a backticked status, matches nothing here and is absent.
    """
    rows = []
    for number, line in enumerate(text.splitlines(), start=1):
        found = INDEX_ROW.match(line)
        if found:
            rows.append((found.group(1), found.group(2), number))
    return rows


def read_invariant_numbers(text):
    """Collect the numbers the invariants section gives its items.

    Args:
        text: The whole of `frontend-architecture.md`.

    Returns:
        A list of `(number, line_number)` tuples, in file order, for the
        top-level numbered items of § 3. Nested lists are indented and match
        nothing; a numbered item in any other section is outside the range.
    """
    numbers = []
    inside = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        if INVARIANTS_HEADING.match(line):
            inside = True
            continue
        if inside and SECTION_HEADING.match(line):
            break
        if not inside:
            continue
        found = NUMBERED_ITEM.match(line)
        if found:
            numbers.append((int(found.group(1)), line_number))
    return numbers


def arm_duplicate_row(rows):
    """Refuse an identifier carrying more than one row of the index.

    Args:
        rows: The index rows, as `read_index_rows` returns them.

    Returns:
        The number of identifiers refused.
    """
    seen = {}
    for identifier, status, line_number in rows:
        seen.setdefault(identifier, []).append((status, line_number))
    violations = 0
    for identifier, occurrences in sorted(seen.items()):
        if len(occurrences) == 1:
            continue
        violations += 1
        described = ", ".join(f"line {line_number} says `{status}`"
                              for status, line_number in occurrences)
        print(f"  BUGS.md: `{identifier}` carries {len(occurrences)} index rows "
              f"— {described}. One identifier, one row: a second row is not a "
              "second view of the entry, it is a second answer to the question "
              "« is this open? », and every count drawn from the index takes "
              "whichever it meets first.", file=sys.stderr)
    return violations


def arm_status_vocabulary(rows):
    """Refuse a status outside § Status vocabulary.

    Args:
        rows: The index rows, as `read_index_rows` returns them.

    Returns:
        The number of rows refused.
    """
    violations = 0
    for identifier, status, line_number in rows:
        if status in PLAIN_STATUSES or FIXED_STATUS.match(status):
            continue
        violations += 1
        print(f"  BUGS.md:{line_number}: `{identifier}` carries the status "
              f"`{status}`, which is outside the declared vocabulary "
              f"({', '.join(PLAIN_STATUSES)}, or `fixed #` followed by a pull "
              "request number). A status nobody declared is a row every count "
              "that greps for a word walks straight past, and `fixed #NNN` in "
              "particular is a placeholder saying the merge was never written "
              "down.", file=sys.stderr)
    return violations


def arm_invariant_numbers(numbers):
    """Refuse a duplicated or skipped invariant number.

    Args:
        numbers: The invariant numbers, as `read_invariant_numbers` returns them.

    Returns:
        The number of violations found.
    """
    violations = 0
    seen = {}
    for value, line_number in numbers:
        seen.setdefault(value, []).append(line_number)
    for value, lines in sorted(seen.items()):
        if len(lines) == 1:
            continue
        violations += 1
        print(f"  frontend-architecture.md: invariant {value} is written "
              f"{len(lines)} times, at lines {', '.join(str(one) for one in lines)}. "
              "These numbers are cited — in this file, in the register and in "
              "the maquette's own comments — so a repeated one sends a reader "
              "to the wrong invariant and a brief has already instructed a wave "
              "that way.", file=sys.stderr)
    expected = list(range(1, len(numbers) + 1))
    written = [value for value, _ in numbers]
    if sorted(written) != expected and not violations:
        missing = sorted(set(expected) - set(written))
        violations += 1
        print(f"  frontend-architecture.md: the invariants run "
              f"{written[0] if written else '-'} to {max(written) if written else '-'} "
              f"and {len(numbers)} are written, so the sequence has a gap at "
              f"{', '.join(str(one) for one in missing)}. A citation of a number "
              "nobody wrote points at nothing, which is the same defect as a "
              "number written twice seen from the other side.", file=sys.stderr)
    return violations


def arm_corpus(rows, numbers):
    """Print what was read, and refuse a corpus that has silently emptied.

    Args:
        rows: The index rows, as `read_index_rows` returns them.
        numbers: The invariant numbers, as `read_invariant_numbers` returns them.

    Returns:
        The number of violations found.
    """
    identifiers = {identifier for identifier, _, _ in rows}
    print(f"check-bug-register[corpus]: {len(rows)} index row(s) read in BUGS.md "
          f"(floor {INDEX_FLOOR}) for {len(identifiers)} identifier(s), and "
          f"{len(numbers)} invariant(s) in frontend-architecture.md "
          f"(floor {INVARIANT_FLOOR})")
    violations = 0
    if len(rows) < INDEX_FLOOR:
        violations += 1
        print(f"  BUGS.md: {len(rows)} index row(s) read, under the floor of "
              f"{INDEX_FLOOR}. Every other arm here starts at zero violations, "
              "so an index this guard can no longer parse — a column added, the "
              "backticks dropped — reports exactly the same word as one it read "
              "entirely.", file=sys.stderr)
    if len(numbers) < INVARIANT_FLOOR:
        violations += 1
        print(f"  frontend-architecture.md: {len(numbers)} invariant(s) read, "
              f"under the floor of {INVARIANT_FLOOR}. The section is found by "
              "its heading; a heading that is reworded empties the corpus "
              "without emptying the file.", file=sys.stderr)
    return violations


def print_next_identifier():
    """Print the next free identifier of each family.

    This is a tool, not an arm: it fails nothing. It exists because the defect it
    answers cannot be held by a guard at all — two branches taking numbers from a
    register the other is writing is invisible to anything reading `main`. What it
    removes is the guessing, and the guessing is what produced three collisions in
    twenty-four hours on a single entry.

    Returns:
        Zero, always.
    """
    highest = {}
    for path in (REGISTER, CLOSED_REGISTER):
        if not path.exists():
            continue
        for family, digits in ANY_IDENTIFIER.findall(path.read_text(encoding="utf-8")):
            value = int(digits)
            if value > highest.get(family, 0):
                highest[family] = value
    for family in ("B", "E"):
        taken = highest.get(family, 0)
        print(f"{family}-{taken + 1:03d}  (highest written: {family}-{taken:03d})")
    print("Read from BUGS.md and BUGS-CLOSED.md, on THIS branch. A number taken "
          "on another branch is invisible here — re-read origin/main before you "
          "write it down.", file=sys.stderr)
    return 0


ARMS = ("duplicate-row", "status-vocabulary", "invariant-numbers", "corpus")


def main():
    """Run the register's arms, or print the next free identifier.

    Returns:
        The process exit code: zero when every selected arm is clean.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--arm", choices=ARMS,
                        help="run one arm instead of all of them")
    parser.add_argument("--next", action="store_true", dest="next_identifier",
                        help="print the next free identifier of each family")
    arguments = parser.parse_args()

    if arguments.next_identifier:
        return print_next_identifier()

    rows = read_index_rows(REGISTER.read_text(encoding="utf-8"))
    numbers = read_invariant_numbers(ARCHITECTURE.read_text(encoding="utf-8"))
    selected = (arguments.arm,) if arguments.arm else ARMS

    violations = 0
    for arm in selected:
        if arm == "duplicate-row":
            violations += arm_duplicate_row(rows)
        elif arm == "status-vocabulary":
            violations += arm_status_vocabulary(rows)
        elif arm == "invariant-numbers":
            violations += arm_invariant_numbers(numbers)
        elif arm == "corpus":
            violations += arm_corpus(rows, numbers)

    if violations:
        print(f"check-bug-register: {violations} violation(s)", file=sys.stderr)
        return 1
    print("check-bug-register: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
