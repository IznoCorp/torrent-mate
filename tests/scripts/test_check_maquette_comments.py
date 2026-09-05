"""Holds on the arm that keeps a maquette comment readable out of context.

`CLAUDE.md` § Language has said for months that a maquette or harness comment
carries no reference to a session, a phase or a dated decision. Three hundred of
them do. The rule bound the whole time and nothing counted, which is the state
this repository's own register calls « a rule that is a sentence in a file » —
so the arm arrives with the debt frozen rather than with the debt cleared.

Every case below is a boundary the operator drew: what counts (a lot, a phase, a
date) and what must not (a register entry, a rule, a clause, a decision, a
path). A guard that counted `B-247` would make the register unciteable from a
comment, which is the opposite of what the rule is for.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_arm():
    """Imports the arm by path, the way `make check` invokes it.

    Returns:
        The module object.
    """
    spec = importlib.util.spec_from_file_location(
        "check_maquette_comments", ROOT / "scripts" / "check-maquette-comments.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_maquette_comments"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="arm")
def arm_fixture():
    """Provides the loaded arm.

    Returns:
        The module object.
    """
    return load_arm()


class TestWhatCounts:
    """The three things that name a wave rather than a thing."""

    @pytest.mark.parametrize("text,what", [
        ("the producer moved at L19", "a lot code"),
        ("it goes with the engine at L13, and it goes in one file", "a lot code"),
        ("the first pass of phase 6 missed it", "a phase"),
        ("phases 3 and 4 disagreed", "a phase"),
        ("arbitrated by the operator on 2026-08-29", "a date"),
    ])
    def test_a_temporal_reference_is_counted(self, arm, text, what) -> None:
        """Each one, and the arm says which kind it found."""
        found = arm.references(text)
        assert len(found) == 1, found
        assert what in found[0]

    def test_several_in_one_comment_are_several(self, arm) -> None:
        """The unit is the reference, not the comment."""
        assert len(arm.references("L19 moved it, L13 removes it, 2026-08-29")) == 3


class TestWhatMustNotCount:
    """The names that outlive the wave that wrote them — and stay citeable."""

    @pytest.mark.parametrize("text", [
        "B-247's producer half",
        "R103 refuses the gap",
        "DOIT-8 says nothing is replaced in silence",
        "§20 names the tunnel",
        "docs/reference/frontend-architecture.md",
        "features/acquisition/panel-follow.ts",
        "the 400-line ceiling",
        "a 260 ms wait",
        "L is a letter and 19 is a number",
    ])
    def test_it_is_not_a_temporal_reference(self, arm, text) -> None:
        """None of these is a wave."""
        assert arm.references(text) == []

    def test_a_decision_carries_a_lot_code_and_is_not_one(self, arm) -> None:
        """`D-L08-5` names a decision that stands until it is replaced.

        This is the operator's own boundary, and it is the one a naive pattern
        gets wrong: the lot code is INSIDE the decision's name.
        """
        assert arm.references("carried verbatim, D-L08-5") == []
        assert arm.references("D-L08-5 and then L19") != []


class TestItReadsCommentsAndNotCode:
    """A guard that read string literals would refuse code that quotes a lot."""

    def test_a_python_comment_is_read(self, arm) -> None:
        """The ordinary case."""
        assert list(arm.comments("x = 1  # moved at L19\n", ".py")) == [" moved at L19"]

    def test_a_python_docstring_is_read(self, arm) -> None:
        """Most of this repository's prose lives in one."""
        assert any("L19" in block
                   for block in arm.comments('"""moved at L19."""\n', ".py"))

    def test_a_python_string_literal_is_not(self, arm) -> None:
        """A rule may legitimately assert on the text « L19 »."""
        assert all("L19" not in block
                   for block in arm.comments('name = "L19"\n', ".py"))

    def test_a_line_comment_is_read(self, arm) -> None:
        """The TypeScript half."""
        assert list(arm.comments("const a = 1; // moved at L19\n", ".ts")) == [
            " moved at L19"]

    def test_a_block_comment_is_read(self, arm) -> None:
        """And the block form the maquette leans on."""
        assert list(arm.comments("/* moved at L19 */\n", ".ts")) == ["/* moved at L19 */"]

    def test_a_typescript_string_literal_is_not(self, arm) -> None:
        """The same protection on the other side."""
        assert list(arm.comments('const name = "L19";\n', ".ts")) == []


class TestTheRatchet:
    """Per file, refused upward, and never silent about a shrink."""

    def test_a_file_that_grows_is_a_violation(self, arm) -> None:
        """THE DEFECT the arm exists to refuse."""
        grown, shrunk = arm.compare({"a.ts": 3}, {"a.ts": 2})
        assert len(grown) == 1 and shrunk == []
        assert "a.ts" in grown[0] and "recorded at 2" in grown[0]

    def test_a_file_that_shrinks_is_printed_and_not_refused(self, arm) -> None:
        """Refusing a shrink would refuse the work the arm demands."""
        grown, shrunk = arm.compare({"a.ts": 1}, {"a.ts": 2})
        assert grown == [] and len(shrunk) == 1
        assert "a.ts" in shrunk[0]

    def test_a_file_at_its_record_is_neither(self, arm) -> None:
        """The ordinary case."""
        assert arm.compare({"a.ts": 2}, {"a.ts": 2}) == ([], [])

    def test_a_new_file_with_a_reference_is_a_violation(self, arm) -> None:
        """A file nobody recorded is recorded at zero, not skipped."""
        grown, _ = arm.compare({"new.ts": 1}, {})
        assert len(grown) == 1 and "recorded at 0" in grown[0]

    def test_the_total_cannot_hide_a_trade(self, arm) -> None:
        """PER FILE is the whole design: one file clearing three while another
        gains three leaves the total where it was, and the habit is per file."""
        grown, shrunk = arm.compare({"a.ts": 0, "b.ts": 3}, {"a.ts": 3, "b.ts": 0})
        assert len(grown) == 1 and len(shrunk) == 1


class TestItReadsTheRealTree:
    """A reader that stops reading reports clean, which is the failure to end."""

    def test_it_reads_the_maquette_and_finds_the_debt(self, arm) -> None:
        """The corpus is real, and the arm's own baseline is not zero."""
        counts, detail = arm.measure()
        assert sum(1 for _ in arm.sources()) > 250
        assert sum(counts.values()) > 200
        assert set(counts) == set(detail)

    def test_the_generated_file_is_exempt_and_named(self, arm) -> None:
        """A generated file is opened by no one, and its prose is held at its source."""
        assert "design/src/contract/types.d.ts" in arm.GENERATED
        assert "openapi.json" in arm.GENERATED["design/src/contract/types.d.ts"]
        assert all(relative != "design/src/contract/types.d.ts"
                   for relative, _, _ in arm.sources())

    def test_the_contract_is_read_at_its_source(self, arm) -> None:
        """`openapi.json` carries prose under the same rule, and it is read."""
        assert any(text for text in arm.contract_prose())
        counts, _ = arm.measure()
        assert arm.CONTRACT in counts

    def test_the_baseline_describes_the_tree(self, arm) -> None:
        """Every recorded file exists, and every count matches what is read.

        A record that no longer describes the tree is a record nobody compared,
        which is the state the size ledger's labels were found in.
        """
        import json
        recorded = json.loads(arm.BASELINE.read_text(encoding="utf-8"))["files"]
        counts, _ = arm.measure()
        assert counts == recorded
