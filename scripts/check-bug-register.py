#!/usr/bin/env python3
"""The bug register's own index, held by five arms, plus the tool that stops the recurrence.

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
  - IT FINDS A BODY BY ITS HEAD, and three shapes are outside that reading
    (B-346): a group heading that uses no em dash (« **B-024 to B-029 arrived
    from an adversarial code review** ») starts no span and folds into the one
    before it; a paragraph opening with an identifier is a head only when
    nothing else claims that identifier; and the first of several entries named
    by one recap is the only one that recap can give a body to. All three
    LENGTHEN a span or leave one unread — never truncate one, which is the
    direction that cost this arm two entries at once.
  - IT DOES NOT HOLD RULE 2. « Exactly one bug may hold `fixing` » is a rule of
    the file this guard does not enforce; `status-vocabulary` accepts the word
    wherever it appears.
"""
import argparse
import pathlib
import re
import subprocess
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

# And the same for the invariants. This comment said « fourteen are written
# today » and the file held FIFTEEN — wrong on the day it was typed, in the very
# commit that renumbered them, because the author counted distinct NUMBERS on
# `main` (where 10 appeared twice) while the arm counts ITEMS. It is B-225's own
# class, shipped by the wave that closed B-225, and `stale-figure` could not see
# it: that arm reads its own module and says so. The count is printed by the
# corpus arm on every run; no number is written here.
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


# THE TWO INDEX TABLES, found by their headings rather than counted. The open
# index carries a status per row; the historical table at the foot of the file
# carries a DATE and no status at all, which is why `INDEX_ROW` is meant not to
# take it. A heading that is reworded empties a span here and the arms below say
# so loudly — the direction a corpus reader must always fail in.
INDEX_TABLE_HEADINGS = (re.compile(r"^## Open\s*$"),
                        re.compile(r"^## Closed entries — index\s*$"))

# Any LINE that opens with an identifier in a table cell, whether or not the
# reader could finish it. Line-anchored on purpose: `ANY_INDEX_ROW` below uses
# `\s*`, which crosses a newline, and that is what made a wrapped row still
# count as « opened » while nothing said which line it was (B-420).
ANY_ROW_LINE = re.compile(r"^\|\s*([BE]-\d{3})\b")

# A historical row: the last cell is a date, unbackticked, and that is the whole
# difference between it and a row whose status cell lost its backticks.
HISTORICAL_ROW = re.compile(r"^\|\s*[BE]-\d{3}\s*\|.*\|\s*\d{4}-\d{2}-\d{2}\s*\|\s*$")

# Any row that OPENS with an identifier, whether or not the reader could finish
# it. The difference between the two is the arm below.
ANY_INDEX_ROW = re.compile(r"^\|\s*([BE]-\d{3})\s*\|", re.MULTILINE)


def index_table_lines(lines):
    """The line numbers each index table occupies.

    Args:
        lines: `BUGS.md` split into lines, without their endings.

    Returns:
        A set of zero-based line indexes belonging to one of the index tables.
    """
    inside = set()
    for index, line in enumerate(lines):
        if not any(heading.match(line) for heading in INDEX_TABLE_HEADINGS):
            continue
        start = index + 1
        while start < len(lines) and not lines[start].startswith("|"):
            start += 1
        end = start
        while end < len(lines) and lines[end].startswith("|"):
            end += 1
        inside.update(range(start, end))
    return inside


def arm_unparsed_row(text, rows):
    r"""Refuses an index row the status reader could not take, BY NAME.

    THE BACKTICK IS A LOAD-BEARING PARSING TOKEN, and nothing read what it made
    the reader miss. `INDEX_ROW` requires the last cell backticked; a row that
    drops them is not reported, it simply DISAPPEARS, and the corpus count falls
    by one with no word said.

    That is not theoretical: re-injecting B-102's own defect — a second `open`
    row for B-079 — with the backticks left off gave `214 index row(s) read` and
    `clean`, exit 0. The same line WITH backticks gives one violation.

    AND IT USED TO GIVE THAT ONE DIAGNOSIS FOR EVERY CAUSE (B-420). A row wrapped
    over two lines is also refused here — `ANY_INDEX_ROW`'s `\s*` crosses the
    newline, so the row still opens with an identifier while `INDEX_ROW`, whose
    `.` does not, no longer reads it. The arm then said « a status cell without
    backticks » about a row whose backticks were all present, and named no line,
    on a file of nine thousand seven hundred. The two causes are separated now
    and the offending line is named.

    Args:
        text: The whole of `BUGS.md`.
        rows: The rows `INDEX_ROW` did take.

    Returns:
        The number of violations.
    """
    lines = text.splitlines()
    historical = 0
    named = 0
    for number, line in enumerate(lines, start=1):
        if not ANY_ROW_LINE.match(line):
            continue
        if INDEX_ROW.match(line):
            continue
        if HISTORICAL_ROW.match(line):
            historical += 1
            continue
        named += 1
        if not line.rstrip().endswith("|"):
            print(f"  BUGS.md:{number}: this index row is WRAPPED — it opens "
                  f"« {line.strip()[:60]}… » and does not end its last cell on "
                  "the same line. A table row is one line: wrapped, it is read "
                  "by no arm and rendered by no reader.", file=sys.stderr)
        else:
            print(f"  BUGS.md:{number}: this index row's status cell is not "
                  f"backticked — « {line.strip()[-60:]} ». The backtick is what "
                  "the reader parses on: without it the row is not refused, it "
                  "DISAPPEARS, and B-102's duplicate walks back in through the "
                  "spelling of its own status cell.", file=sys.stderr)

    opened = len(ANY_INDEX_ROW.findall(text))
    residual = opened - len(rows) - historical - named
    if residual > 0:
        print(f"  BUGS.md: {opened} row(s) open with an identifier, {len(rows)} "
              f"were read as index rows, {historical} are the historical table "
              f"and {named} were named above — {residual} could not be "
              "accounted for at all. The subtraction and the line-by-line read "
              "disagree, which means a row is malformed in a way neither "
              "describes.", file=sys.stderr)
        named += 1
    return named


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


# THE HEAD OF AN ENTRY'S BODY, AND THE DELIMITER IS PART OF IT (B-346).
# `^\*\*([BE]-\d{3})\b` alone made a head of any paragraph that merely OPENS with
# an identifier — `**B-249's FAMILY…` — which ended the entry that paragraph
# lives in and claimed the identifier it named. Measured: B-310's body was
# truncated from 9 740 characters to 3 065, B-249's real body was discarded
# entirely because `entry_bodies` kept the FIRST span, and the closure arm was
# blind to both entries at once, refusing a `fixed #573` for a body it could not
# see.
#
# THE REGISTER'S OWN GRAMMAR IS THE ANSWER, and it was counted before it was
# chosen: of 320 paragraphs opening with an identifier, 279 read `**B-NNN — `
# and one reads `**B-NNN** —`; the rest are prose (« **B-244 is closed with
# it.** ») or a heading naming several entries (« **B-180 to B-199 — the second
# review** »). So a PROPER head is an identifier, optionally followed by more
# identifiers joined by `,`, ` to ` or ` and `, then an em dash.
PROPER_BODY_HEAD = re.compile(
    r"^\*\*([BE]-\d{3})(?:(?:,| to | and )\s*[BE]-\d{3})*(?:\*\*)?\s+—",
    re.MULTILINE)

# Any paragraph opening with an identifier — the old rule, kept for ONE purpose.
# Twelve entries have never been written with the dash: their whole text is a
# sentence starting « **B-165 is the one to keep.** ». Refusing those outright
# would take twelve bodies away from the closure arm, which is a loosening in
# exchange for a tightening. So a bare paragraph is a head only when the
# identifier it names has NO proper head anywhere in the file — which is exactly
# the distinction the defect turned on: a paragraph may claim an entry that has
# no body of its own, never one that has.
ANY_BODY_HEAD = re.compile(r"^\*\*([BE]-\d{3})\b", re.MULTILINE)


# A head that names SEVERAL entries is a wave's summary section, never one
# entry's body: « **B-050, B-059 and B-070 — three angles on one mechanism** »
# stands above the three entries it recaps, and the first of them has a body of
# its own further down. `entry_bodies` prefers the body over the recap for that
# reason, and only that reason — the recap is 980 characters and the body 924,
# so « the longest span » picks the wrong one.
# re.MULTILINE is LOAD-BEARING here and not decoration: `pattern.match(text,
# pos)` leaves `^` unmatchable at any pos but zero without it, so the first
# version of this line answered « names one entry » for every head in the file
# and the preference below chose by length alone — which is the reading it was
# written to replace.
NAMES_SEVERAL = re.compile(r"^\*\*[BE]-\d{3}(?:,| to | and )\s*[BE]-\d{3}",
                           re.MULTILINE)


def body_heads(register):
    """Every body head in the register, in the order they appear.

    Args:
        register: The whole of `BUGS.md`.

    Returns:
        A list of `(identifier, offset, names_one_entry)`, one per head.
    """
    with_a_proper_head = {match.group(1)
                          for match in PROPER_BODY_HEAD.finditer(register)}
    heads = []
    for match in ANY_BODY_HEAD.finditer(register):
        identifier = match.group(1)
        if (PROPER_BODY_HEAD.match(register, match.start())
                or identifier not in with_a_proper_head):
            heads.append((identifier, match.start(),
                          NAMES_SEVERAL.match(register, match.start()) is None))
    return heads


def entry_bodies(register):
    """Splits the register into one text span per entry body.

    AND IT KEEPS THE LONGEST SPAN, not the first (B-346, the other half). Even
    under the grammar above, seventeen identifiers carry two heads today: the
    entry's own body, and a wave-summary section naming several entries at once
    (« **B-050, B-059 and B-070 — three angles on one mechanism** »). `setdefault`
    kept whichever came FIRST in the file, so a summary paragraph could stand in
    for a body it summarises, and the closure arm would then read three lines of
    recap where nine thousand characters of entry sit further down.

    Args:
        register: The whole of `BUGS.md`.

    Returns:
        A dict mapping identifier to the text from its body heading to the next.
    """
    heads = body_heads(register)
    ranked = {}
    for index, (identifier, start, names_one_entry) in enumerate(heads):
        end = heads[index + 1][1] if index + 1 < len(heads) else len(register)
        span = register[start:end]
        rank = (names_one_entry, len(span))
        if rank > ranked.get(identifier, ((False, -1), ""))[0]:
            ranked[identifier] = (rank, span)
    return {identifier: span for identifier, (_, span) in ranked.items()}


def base_register(path):
    """Reads the register as it stands at the branch point with origin/main.

    Args:
        path: The register being checked. A copy outside the repository has no
            branch point, and this says so by answering None rather than
            silently comparing against `BUGS.md`.

    Returns:
        The base text, or None when git cannot reach it.
    """
    try:
        tracked = path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return None
    for base in ("origin/main", "main"):
        merge = subprocess.run(["git", "merge-base", "HEAD", base],
                               capture_output=True, text=True, check=False,
                               cwd=ROOT)
        if merge.returncode != 0:
            continue
        show = subprocess.run(
            ["git", "show", f"{merge.stdout.strip()}:{tracked}"],
            capture_output=True, text=True, check=False, cwd=ROOT)
        if show.returncode == 0:
            return show.stdout
    return None


def arm_closure(register, path):
    """Refuses an entry whose status moved to `fixed` with its body untouched.

    THIS IS THE ARM FOR RULE 3 ITSELF, and it exists because the wave that
    hardened that rule broke it: B-042 shipped marked `fixed #516` with a body
    BYTE-IDENTICAL to the base. Nothing said what had been established, or how.
    A reviewer found it; no arm could.

    It compares against the branch point rather than requiring a marker word,
    because there is no marker word to require: an entry filed AND closed inside
    one wave was never open elsewhere and writes no « CLOSED » paragraph, while
    an entry inherited from `main` must say what changed. The difference is
    exactly « did this pull request write anything about it », and only the base
    can answer that.

    Args:
        register: The whole of the register, as it stands.
        path: Where it was read from, so the branch point is the same file's.

    Returns:
        The number of violations.
    """
    base = base_register(path)
    if base is None:
        print("  [closure] git could not reach the branch point, so this arm "
              "read nothing. It refuses rather than passes: an arm that cannot "
              "see its subject and reports success is the shape this register "
              "counts. Fetch the history (`fetch-depth: 0`) or run it in a "
              "clone that has `origin/main`.", file=sys.stderr)
        return 1

    # THE BASE MAY LIST AN IDENTIFIER TWICE — `main` carries B-079 to B-085
    # both as `fixed #505` and as `open`, the duplication the `duplicate-row`
    # arm refuses and this wave cleaned up. Keeping the last row read all seven
    # as open on the base and closed here, and accused this branch of seven
    # silent closures it never made. An identifier the base calls closed
    # ANYWHERE was closed before this branch.
    was = {}
    for identifier, status, _ in read_index_rows(base):
        if not was.get(identifier, "").startswith("fixed"):
            was[identifier] = status
    now = {identifier: status
           for identifier, status, _ in read_index_rows(register)}
    base_bodies, bodies = entry_bodies(base), entry_bodies(register)

    closed_here = [identifier for identifier, status in now.items()
                   if status.startswith("fixed")
                   and not was.get(identifier, "").startswith("fixed")]
    silent = [identifier for identifier in closed_here
              if identifier in base_bodies
              and bodies.get(identifier) == base_bodies[identifier]]
    for identifier in silent:
        print(f"  [closure] {identifier} moved to `{now[identifier]}` and its "
              "body is byte-identical to the branch point. Rule 3 asks for an "
              "instrument that RAN; a status reading « fixed » over an "
              "unchanged body says nothing about what was established, or how. "
              "Write the closure in the entry.", file=sys.stderr)
    if not silent:
        print(f"check-bug-register[closure]: {len(now)} status(es) read "
              f"against the branch point, {len(closed_here)} closed by this "
              "branch, each with a body that changed")
    return len(silent)


ARMS = ("duplicate-row", "status-vocabulary", "invariant-numbers",
        "unparsed-row", "corpus", "closure")


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
    # THE DOOR A PROBE NEEDS. Every arm here reads one hard-coded file, so the
    # only way to ask « would this guard catch that? » was to damage the real
    # register and hope to undo it. A copy is the honest way to ask, and an arm
    # nobody can point at a copy is an arm nobody tests.
    parser.add_argument("--register", type=pathlib.Path, default=REGISTER,
                        help="read this register instead of BUGS.md")
    arguments = parser.parse_args()

    if arguments.next_identifier:
        return print_next_identifier()

    register = arguments.register.read_text(encoding="utf-8")
    rows = read_index_rows(register)
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
        elif arm == "unparsed-row":
            violations += arm_unparsed_row(register, rows)
        elif arm == "corpus":
            violations += arm_corpus(rows, numbers)
        elif arm == "closure":
            violations += arm_closure(register, arguments.register)

    if violations:
        print(f"check-bug-register: {violations} violation(s)", file=sys.stderr)
        return 1
    print("check-bug-register: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
