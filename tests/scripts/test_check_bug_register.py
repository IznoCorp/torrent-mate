r"""How the register's guard finds an entry's body, and where it lost one (B-346).

WHAT IT PAID FOR. `BODY_HEAD` was `^\\*\\*([BE]-\\d{3})\\b`, so any paragraph that
merely OPENED with an identifier was read as that entry's body head. A paragraph
inside B-310 beginning « **B-249's FAMILY… » therefore did two things at once:
it ended B-310's body — 9 740 characters cut to 3 065, losing the mechanism, the
device readings and everything after them — and, being the FIRST head bearing
that identifier, it became « B-249's body » and discarded B-249's real one,
which sits six thousand lines further down. The closure arm was blind to two
entries at once, and refused a `fixed #573` for a body it could not see.

The holds below drive `entry_bodies` on small synthetic registers, so each one
names a single property, and then read the real `BUGS.md` once as a corpus floor
— an arm that finds no body and reports clean is the shape this repository
counts.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "check-bug-register.py"

# Well below the 294 bodies the register holds today: a floor says « the parser
# has not silently emptied », never « the register has exactly this many ».
BODY_FLOOR = 200


def load_guard():
    """Import the guard by path — its file name carries hyphens."""
    specification = importlib.util.spec_from_file_location("check_bug_register", GUARD)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


# The register as the defect met it: a paragraph inside B-310 opening with
# B-249's identifier, and B-249's own entry six thousand lines further down.
TRUNCATED_AND_STOLEN = (
    "**B-310 — the bottom panel is seen again.**\n"
    "The mechanism, first paragraph.\n\n"
    "**B-249's FAMILY is the same shape.** A paragraph inside B-310.\n\n"
    "THE DEVICE READINGS, which used to be cut off here.\n\n"
    "**B-311 — something else entirely.**\nAnother entry.\n\n"
    "**B-249 — the screen flashes when a sheet action closes the sheet.**\n"
    "THE REAL BODY of B-249, written where the entry lives.\n"
)


def test_a_paragraph_naming_another_entry_does_not_end_the_one_it_lives_in() -> None:
    """THE DEFECT THIS FILE WAS WRITTEN FOR, from the truncation side."""
    bodies = load_guard().entry_bodies(TRUNCATED_AND_STOLEN)

    assert "THE DEVICE READINGS" in bodies["B-310"], bodies["B-310"]
    assert "B-249's FAMILY" in bodies["B-310"], "the paragraph left B-310's body"


def test_a_paragraph_naming_another_entry_does_not_claim_that_identifier() -> None:
    """The same defect from the theft side: B-249's real body is further down."""
    bodies = load_guard().entry_bodies(TRUNCATED_AND_STOLEN)

    assert "THE REAL BODY" in bodies["B-249"], bodies["B-249"]


def test_both_spellings_of_a_real_head_are_read() -> None:
    """The register writes `**B-NNN — ` 279 times and `**B-NNN** —` once."""
    register = "**B-160** — a half-open socket.\nThe first body.\n\n**B-161 — the other spelling.**\nThe second body.\n"
    bodies = load_guard().entry_bodies(register)

    assert "The first body" in bodies["B-160"], bodies.get("B-160")
    assert "The second body" in bodies["B-161"], bodies.get("B-161")


def test_a_summary_naming_several_entries_does_not_stand_in_for_a_body() -> None:
    """A wave's recap sits above the entries it recaps; the entry has its own.

    Measured on the real register: the recap « **B-050, B-059 and B-070 — three
    angles on one mechanism** » is 980 characters and B-050's own body is 924,
    so choosing the longest span picks the recap. The head that names ONE entry
    is what distinguishes them.
    """
    register = (
        "**B-050, B-059 and B-070 — three angles on one mechanism.**\n"
        "A RECAP, and a long one: " + "padding. " * 40 + "\n\n"
        "**B-050 — the guard that watches module size has grown.**\n"
        "THE ENTRY ITSELF, shorter than the recap above it.\n"
    )
    bodies = load_guard().entry_bodies(register)

    assert "THE ENTRY ITSELF" in bodies["B-050"], bodies["B-050"]


def test_an_entry_written_without_the_dash_still_has_a_body() -> None:
    """Twelve entries are a sentence, not a title, and must not lose their body.

    « **B-165 is the one to keep.** » is the whole of that entry. Refusing every
    paragraph that is not a dash head would trade a tightening for a loosening —
    so a bare paragraph is a head exactly when nothing else claims its
    identifier.
    """
    register = (
        "**B-160 to B-178 — what an adversarial review found.**\nThe section.\n\n"
        "**B-165 is the one to keep.** THE WHOLE OF B-165, and it has no dash head.\n"
    )
    bodies = load_guard().entry_bodies(register)

    assert "THE WHOLE OF B-165" in bodies["B-165"], bodies.get("B-165")


def test_the_real_register_still_yields_a_body_for_most_of_its_entries() -> None:
    """The corpus floor: a parser that reads nothing must not report clean."""
    module = load_guard()
    bodies = module.entry_bodies((ROOT / "BUGS.md").read_text(encoding="utf-8"))

    assert len(bodies) >= BODY_FLOOR, f"only {len(bodies)} bodies read in BUGS.md"


# ── The index table's own lines (B-420) ─────────────────────────────────────
# `arm_unparsed_row` had ONE diagnosis for every cause and named no line. A row
# wrapped over two lines is refused by it — `ANY_INDEX_ROW`'s `\s*` crosses a
# newline while `INDEX_ROW`'s `.` does not — but it was reported as « a status
# cell without backticks », about a row whose backticks were all present, on a
# file of nine thousand seven hundred lines.

WELL_FORMED_TABLE = (
    "## Open\n\n"
    "| ID    | Defect        | Reported | Status |\n"
    "| ----- | ------------- | -------- | ------ |\n"
    "| B-001 | The first one | 1x       | `open` |\n"
    "| B-002 | The next one  | 1x       | `open` |\n"
)


def run_unparsed_arm(module, register, capsys):
    """Run the arm on a register and return its violation count and stderr."""
    violations = module.arm_unparsed_row(register, module.read_index_rows(register))
    return violations, capsys.readouterr().err


def test_a_wrapped_row_is_refused_by_name_and_called_wrapped(capsys) -> None:
    """THE DEFECT: the line is named, and the cause is the one that applies."""
    module = load_guard()
    register = WELL_FORMED_TABLE.replace(
        "| B-002 | The next one  | 1x       | `open` |\n",
        "| B-002 | The next one\n  wrapped onto a second line | 1x | `open` |\n",
    )

    violations, said = run_unparsed_arm(module, register, capsys)

    assert violations == 1, said
    assert "BUGS.md:6:" in said, said
    assert "WRAPPED" in said, said
    assert "backtick" not in said.lower(), f"the wrong cause was named:\n{said}"


def test_a_row_whose_status_lost_its_backticks_is_refused_by_name(capsys) -> None:
    """The cause the arm was written for, still named — and now with its line."""
    module = load_guard()
    register = WELL_FORMED_TABLE.replace(
        "| B-002 | The next one  | 1x       | `open` |",
        "| B-002 | The next one  | 1x       | open   |",
    )

    violations, said = run_unparsed_arm(module, register, capsys)

    assert violations == 1, said
    assert "BUGS.md:6:" in said, said
    assert "backticked" in said, said
    assert "WRAPPED" not in said, f"the wrong cause was named:\n{said}"


def test_the_historical_table_is_not_refused(capsys) -> None:
    """Its last cell is a DATE and carries no status — that is not a defect."""
    module = load_guard()
    register = WELL_FORMED_TABLE + (
        "\n## Closed entries — index\n\n"
        "| ID    | Defect        | Reported | Fixed      |\n"
        "| ----- | ------------- | -------- | ---------- |\n"
        "| B-003 | An old one    | 2x       | 2026-08-14 |\n"
    )

    violations, said = run_unparsed_arm(module, register, capsys)

    assert violations == 0, said


def test_the_real_register_passes_the_arm(capsys) -> None:
    """THE CONTROL: an arm that refused everything would pass the three above."""
    module = load_guard()
    register = (ROOT / "BUGS.md").read_text(encoding="utf-8")

    violations, said = run_unparsed_arm(module, register, capsys)

    assert violations == 0, said


# ── Where a row may be written, and in what order (B-421) ───────────────────
# A `| B-NNN |` line after the first body head is READ by every arm — `INDEX_ROW`
# is `re.MULTILINE` and matches anywhere — and invisible to a reader, because the
# Markdown table ends at the first line that is not a row. Nothing refused that,
# and nothing held the index's order either.

TWO_TABLES = (
    "## Open\n\n"
    "| ID    | Defect        | Reported | Status |\n"
    "| ----- | ------------- | -------- | ------ |\n"
    "| B-001 | The first one | 1x       | `open` |\n"
    "| B-002 | The next one  | 1x       | `open` |\n"
    "\n**B-001 — the first one, at length.**\nIts body.\n"
    "\n## Closed entries — index\n\n"
    "| ID    | Defect        | Reported | Fixed      |\n"
    "| ----- | ------------- | -------- | ---------- |\n"
    "| B-900 | An old one    | 2x       | 2026-08-14 |\n"
)


def test_a_row_written_below_the_table_is_refused_by_name(capsys) -> None:
    """THE DEFECT: in every figure the guard prints, and on no rendered page."""
    module = load_guard()
    register = TWO_TABLES.replace(
        "**B-001 — the first one, at length.**",
        "| B-003 | Re-glued by a merge | 1x | `open` |\n\n**B-001 — the first one, at length.**",
    )

    violations = module.arm_row_placement(register)
    said = capsys.readouterr().err

    assert violations == 1, said
    assert "OUTSIDE both index tables" in said, said
    assert "B-003" in said, said


def test_the_two_tables_own_their_own_rows(capsys) -> None:
    """THE CONTROL: an arm refusing every row would pass the hold above."""
    module = load_guard()

    violations = module.arm_row_placement(TWO_TABLES)

    assert violations == 0, capsys.readouterr().err


def test_a_reworded_heading_is_loud_rather_than_quiet(capsys) -> None:
    """An arm whose subject has gone must refuse, never report clean.

    The two readings are different and both are held: rewording ONE heading
    leaves the other table found, and every row of the lost one is then refused
    as written outside a table — loud, and pointing at the right lines. Losing
    BOTH leaves the arm with no subject at all, and it says so rather than
    passing, which is the shape this register counts.
    """
    module = load_guard()

    one_lost = module.arm_row_placement(TWO_TABLES.replace("## Open", "## Ouvert"))
    said = capsys.readouterr().err
    assert one_lost == 2, said
    assert "OUTSIDE both index tables" in said, said

    both_lost = module.arm_row_placement(
        TWO_TABLES.replace("## Open", "## Ouvert").replace("## Closed entries — index", "## Entrees fermees")
    )
    said = capsys.readouterr().err
    assert both_lost == 1, said
    assert "neither index table was found" in said, said


def test_a_new_descent_in_the_index_is_refused(capsys) -> None:
    """The ratchet: the register is not sorted, and must not get less sorted."""
    module = load_guard()
    register = TWO_TABLES.replace(
        "| B-001 | The first one | 1x       | `open` |\n| B-002 | The next one  | 1x       | `open` |\n",
        "| B-002 | The next one  | 1x       | `open` |\n| B-001 | The first one | 1x       | `open` |\n",
    )

    violations = module.arm_index_order(register)
    said = capsys.readouterr().err

    assert violations == 1, said
    assert "B-002 is followed by B-001" in said, said


def test_the_real_register_passes_both_arms(capsys) -> None:
    """THE CONTROL that matters most: the file as the operator wrote it.

    The open index is NOT sorted — B-023 -> B-013, B-346 -> B-339 and
    B-371 -> B-331 — and the seam where it gives way to the historical table is
    a descent too. Requiring a sort would refuse the register; the ratchet
    freezes what is there and reads each table on its own.
    """
    module = load_guard()
    register = (ROOT / "BUGS.md").read_text(encoding="utf-8")

    assert module.arm_row_placement(register) == 0, capsys.readouterr().err
    assert module.arm_index_order(register) == 0, capsys.readouterr().err
