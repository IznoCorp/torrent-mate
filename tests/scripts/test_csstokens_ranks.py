"""Tests for the frame's ranked-list arm.

WHAT IT HAS TO CATCH, and every case below is a defect that stood in the tree
while the list's own sentence — « every rank the frame paints is named here
once » — sat above it: a rank declared and never recorded (four of them), a rank
recorded with no file so the prose beside it implied the wrong one, and a rank
that MOVES on one side only, which is the direction a list rots in.

The arm reads the repository by default, so every reader takes its root as an
argument and every test hands it a tree of its own. An arm whose readers only
ever read the repository is an arm nothing can put a known defect in front of —
and this one was written for a claim that had gone false unnoticed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "csstokens_ranks.py"


def load():
    """Imports the arm, despite its module living beside a hyphenated guard."""
    spec = importlib.util.spec_from_file_location("csstokens_ranks", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


arm = load()

LIST = """/* ── THE RANKED LIST, AND IT IS ONE LIST ──────────

     30  the action button          `addAction` (ui/variants/frame.ts)
     40  the shell's top bar        `.topbar` (index.html)
     50  the tab bar `tabBar` (ui/variants/frame.ts) · the harness's buttons `.hbtn` (styles/harness.css)
*/
"""

# The stacking details a tree of this size has: none, unless a case says so.
NO_EXEMPTION: dict[tuple[str, int], str] = {}


def tree(root: Path, css: str = "", variants: str = "", markup: str = "",
         ranked: str = LIST) -> tuple[Path, Path]:
    """Writes a maquette small enough to reason about.

    Args:
        root: The directory to write into.
        css: One stylesheet's contents, written as `styles/harness.css`.
        variants: One source's contents, written as `ui/variants/frame.ts`.
        markup: The shell's markup, written as `index.html` beside the sources.
        ranked: The ranked list, written as `ui/variants/ranked.ts`.

    Returns:
        The list's path and the sources' root, in the order the arm takes them.
    """
    design = root / "src"
    (design / "styles").mkdir(parents=True)
    (design / "ui" / "variants").mkdir(parents=True)
    (design / "styles" / "harness.css").write_text(css, encoding="utf-8")
    (design / "ui" / "variants" / "frame.ts").write_text(variants, encoding="utf-8")
    (design / "ui" / "variants" / "ranked.ts").write_text(ranked, encoding="utf-8")
    (root / "index.html").write_text(markup, encoding="utf-8")
    return design / "ui" / "variants" / "ranked.ts", design


class TestWhatTheListRecords:
    """The parse, because everything else rests on it."""

    def test_every_entry_is_read_with_its_file(self, tmp_path: Path) -> None:
        """Four sites over three lines, each with its file.

        SEVERAL SITES PER LINE is the shape the list is written in — four things
        share rank 60 — and a reader that took one entry per line saw the first
        of each line and silently lost the rest.
        """
        entries, findings = arm.recorded(tree(tmp_path)[0])

        assert findings == []
        assert entries[("addAction", 30)] == "ui/variants/frame.ts"
        assert entries[(".topbar", 40)] == "index.html"
        assert entries[("tabBar", 50)] == "ui/variants/frame.ts"
        assert entries[(".hbtn", 50)] == "styles/harness.css"
        assert len(entries) == 4

    def test_one_site_recorded_at_two_ranks_is_a_finding(self, tmp_path: Path) -> None:
        """A list that says two things about one site records neither."""
        entry = "     30  the action button          `addAction` (ui/variants/frame.ts)"
        twice = LIST.replace(entry, entry.replace("30", "31", 1) + "\n" + entry)
        _, findings = arm.recorded(tree(tmp_path, ranked=twice)[0])

        assert any("recorded at 31 and at 30" in one for one in findings)


class TestWhatTheSourcesDeclare:
    """The reading, and the two traps it was written after."""

    def test_a_stylesheet_names_the_selector_of_its_block(self, tmp_path: Path) -> None:
        """The finding has to say WHICH block, or it names a file and a number."""
        css = ".hbtn {\n  position: fixed;\n  z-index: 53;\n}\n"
        found = arm.declared(tree(tmp_path, css=css)[1])

        assert (".hbtn", 53, "styles/harness.css:3") in found

    def test_a_rank_written_in_a_comment_is_not_a_declaration(self, tmp_path: Path) -> None:
        """The list's own prose spends ranks that no longer exist."""
        css = "/* it used to be z-index: 47, under the bar */\n.hbtn {\n  z-index: 53;\n}\n"
        variants = ('// the sheet was z-47 under the bar\nexport const tabBar = cva(\n'
                    '  "bottombar fixed z-50",\n);\n')
        found = arm.declared(tree(tmp_path, css=css, variants=variants)[1])

        assert [rank for _, rank, _ in found] == [53, 50]

    def test_the_shell_markup_is_read_at_the_utility_s_own_line(self, tmp_path: Path) -> None:
        """A class attribute here wraps, and the rank is rarely on its first line."""
        markup = ('<!-- a comment\n     over three\n     lines -->\n'
                  '<header\n  class="topbar relative\n         z-40 flex"\n>\n')
        found = arm.declared(tree(tmp_path, markup=markup)[1])

        assert found == [(".topbar", 40, "index.html:6")]


class TestWhatItRefuses:
    """One case per direction the record and the sources can disagree."""

    def test_the_two_saying_the_same_thing_pass(self, tmp_path: Path) -> None:
        """The baseline, so a tightening cannot quietly refuse a true list."""
        ranked, design = tree(
            tmp_path,
            css=".hbtn {\n  z-index: 50;\n}\n",
            variants='export const tabBar = cva("bottombar z-50");\n',
            markup='<header class="topbar z-40"></header>\n',
            ranked=LIST.replace("     30  the action button          `addAction`"
                                " (ui/variants/frame.ts)\n", ""))

        assert arm.ranks_arm(ranked, design, NO_EXEMPTION) == 0

    def test_a_stacking_detail_the_arm_exempts_is_not_refused(self, tmp_path: Path) -> None:
        """The exemption's whole purpose, and it is not a blanket."""
        ranked, design = tree(tmp_path, css=".st .d {\n  z-index: 1;\n}\n",
                              ranked="/* ── THE RANKED LIST ──\n\n     30  x `y` (z)\n*/\n")

        assert arm.disagreements({}, [(".st .d", 1, "styles/legacy.css:2")],
                                 {(".st .d", 1): "a dot on its own connector"}) == []
        assert arm.disagreements({}, [(".st .d", 9, "styles/legacy.css:2")],
                                 {(".st .d", 1): "a dot on its own connector"}) != []

    def test_a_site_both_ranked_and_exempt_is_refused(self, tmp_path: Path) -> None:
        """One or the other: two records of one site is how they drift apart."""
        findings = arm.disagreements({("viewTabs", 30): "ui/variants/controls.ts"},
                                     [("viewTabs", 30, "ui/variants/controls.ts:1")],
                                     {("viewTabs", 30): "sticky over its own body"})

        assert any("BOTH a frame rank" in one for one in findings)

    def test_a_rank_declared_and_not_recorded_is_refused(self, tmp_path: Path) -> None:
        """The finding the whole arm exists for: a rank nobody wrote down.

        THE ASSERTION NAMES THE READING, not the exit code. Written against
        `ranks_arm` alone this test passed with its own half of the arm deleted,
        because the other half refused the same tree for the other reason.
        """
        entries = {(".newthing", 99): "somewhere"}
        sites = [(".newthing", 58, "styles/harness.css:2")]

        findings = arm.disagreements(entries, sites, NO_EXEMPTION)

        assert len(findings) == 2
        assert "declares 58, the ranked list records 99" in findings[0]

    def test_a_rank_nobody_recorded_at_all_is_refused(self, tmp_path: Path) -> None:
        """A site the list has never heard of, so only one half can speak."""
        findings = arm.disagreements({}, [(".newthing", 58, "styles/harness.css:2")],
                                     NO_EXEMPTION)

        assert len(findings) == 1
        assert "declares 58 and the ranked list does not name it" in findings[0]

    def test_a_recorded_rank_nothing_declares_is_refused(self, tmp_path: Path) -> None:
        """The direction that rots silently: the sources moved, the list did not."""
        findings = arm.disagreements({(".hbtn", 53): "styles/harness.css"}, [], NO_EXEMPTION)

        assert len(findings) == 1
        assert "outlived its subject" in findings[0]

    def test_the_two_halves_are_read_over_a_whole_tree(self, tmp_path: Path) -> None:
        """And the arm still refuses end to end, over files rather than tuples."""
        ranked, design = tree(tmp_path, css=".newthing {\n  z-index: 58;\n}\n")

        assert arm.ranks_arm(ranked, design, NO_EXEMPTION) == 1

    def test_a_list_that_records_nothing_is_refused(self, tmp_path: Path) -> None:
        """A parse that reads zero entries would otherwise report « all clear »."""
        ranked, design = tree(tmp_path, ranked="/* the shape moved */\n")

        assert arm.ranks_arm(ranked, design, NO_EXEMPTION) == 1
