"""Tests for the no-French guard.

THE GUARD HAD NONE. It is the most-invoked check in the project, it is over a
thousand lines, and a single review session found four defects in it by hand:
an empty `french-ok:` reason that granted what the module docstring says it must
refuse, a pragma window that licensed a literal's neighbours, three scopes no
arm read, and two `id=` spellings the markup arm could not see.

`CLAUDE.md` says a rule with no arm is a sentence in a file. The same applies to
the arm itself: a guard whose own correctness nothing holds is a sentence about
correctness.

These test the DECIDING functions rather than driving the whole script over the
repository — the script resolves its scopes from module-level constants, so an
end-to-end test would have to plant violations in the real tree and could leave
them behind if it failed.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-no-french.py"


def load():
    """Imports the guard as a module, despite its hyphenated filename."""
    spec = importlib.util.spec_from_file_location("check_no_french", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load()
# Arm 10 lives in `nofrench_dictionary.py` beside the entry point, which imports
# it — so loading the guard puts it in `sys.modules`. The dictionary tests patch
# the module that OWNS the arm's globals: patching the re-export on the entry
# point would rebind a name the arm never reads.
dictionary = sys.modules["nofrench_dictionary"]
aspell = pytest.mark.skipif(shutil.which("aspell") is None, reason="aspell absent — the dictionary arm fail-softs")


class TestPragma:
    """`# french-ok: <reason>` — the one escape hatch, and its exact reach."""

    def test_a_reason_grants(self) -> None:
        """The ordinary case."""
        lines = ['x = "en attente"  # french-ok: a state id, not copy']
        assert guard.pragma_on(lines, 1) == "a state id, not copy"

    def test_an_empty_reason_grants_NOTHING(self) -> None:
        """The module docstring: a pragma citing nothing is itself a violation.

        Two arms asked `is not None`, so a bare `french-ok:` silenced them. The
        function must return something FALSY so a truthiness test refuses it.
        """
        lines = ['x = "en attente"  # french-ok:']

        assert not guard.pragma_on(lines, 1)

    def test_the_line_above_counts(self) -> None:
        """A JSX attribute has no room for a trailing comment."""
        lines = ["// french-ok: the seam's own name", 'label="en attente"']
        assert guard.pragma_on(lines, 2) == "the seam's own name"

    def test_the_line_BELOW_does_not_count(self) -> None:
        """Licensing a neighbour is a bigger hole than the one it closed.

        The docstring once promised the line below, for wrapped literals.
        Implementing it gave every pragma a three-line grant, so a brand-new
        French literal parked beside any existing pragma became invisible.
        """
        lines = ['label="en attente"', "// french-ok: belongs to the NEXT literal"]

        assert guard.pragma_on(lines, 1) is None

    def test_a_pragma_inside_a_string_is_not_a_pragma(self) -> None:
        """One literal reading `"# french-ok: …"` used to license its neighbours."""
        lines = ['message = "# french-ok: not a pragma, just text"']
        assert guard.pragma_on(lines, 1) is None


class TestFrenchStrings:
    """The arm that keeps interface copy out of the code."""

    def test_a_french_sentence_is_refused(self) -> None:
        """A tool message in French is the defect this arm exists for."""
        reason = guard.offending_string("Le fichier est introuvable dans la configuration")
        assert reason

    def test_an_english_sentence_passes(self) -> None:
        """And the same sentence in English is not."""
        assert not guard.offending_string("The file is missing from the configuration")

    def test_quoted_ui_copy_is_stripped_before_judging(self) -> None:
        """French inside « … » quotes the app's own output and is allowed."""
        assert not guard.offending_string("the card prints « Prochaine recherche » here")


class TestSplitIdentifier:
    """Names are judged by the words they are built from."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("followStatus", ["follow", "Status"]),
            ("follow_status", ["follow", "status"]),
            ("FollowStatus", ["Follow", "Status"]),
            ("data-follow-status", ["data", "follow", "status"]),
        ],
    )
    def test_splits(self, name: str, expected: list[str]) -> None:
        """camelCase, snake_case, PascalCase and kebab all decompose."""
        assert guard.split_identifier(name) == expected


class TestDictionaryArm:
    """The oracle from OUTSIDE the repository."""

    @aspell
    def test_a_french_only_word_is_a_suspect(self) -> None:
        """`calcul` is French and not English — the blacklist never knew it."""
        assert "calcul" in dictionary.dictionary_suspects({"calcul"})

    @aspell
    def test_an_english_word_is_not(self) -> None:
        """An ordinary English word must never be a suspect."""
        assert dictionary.dictionary_suspects({"status", "follow", "library"}) == set()

    @aspell
    def test_a_declared_exception_is_not(self) -> None:
        """Every exception carries its reason; none of them may be flagged."""
        assert dictionary.dictionary_suspects(set(dictionary.DICTIONARY_EXCEPTIONS)) == set()

    @aspell
    def test_a_word_BOTH_languages_know_is_invisible_to_this_arm(self) -> None:
        """The arm's own blind spot, pinned so nobody mistakes it for coverage.

        `corps` is French and lives in `frontend/src` today. English knows the
        word too, so no dictionary can see it — only the VOCABULARY arm's « is
        this a word we use? » can. This test exists so that limit is a recorded
        fact rather than a surprise.
        """
        assert dictionary.dictionary_suspects({"corps", "page", "route", "image"}) == set()

    def test_every_exception_carries_a_reason(self) -> None:
        """An exemption nobody can read is indistinguishable from an oversight."""
        empty = [w for w, reason in dictionary.DICTIONARY_EXCEPTIONS.items() if not reason.strip()]
        assert empty == []

    def test_no_dictionaries_measures_nothing_and_says_so(self, monkeypatch, capsys) -> None:
        """Fail SOFT, never silently: absence must not read as cleanliness."""

        def absent(*args, **kwargs):
            raise OSError("aspell not installed")

        monkeypatch.setattr(dictionary.subprocess, "run", absent)

        assert dictionary.dictionary_suspects({"calcul"}) == set()
        assert "measured" in capsys.readouterr().err


class TestTheGuardItself:
    """The script must run, and its ledger must refuse an empty scope."""

    def test_it_exits_zero_on_this_repository(self) -> None:
        """The gate is green on `main`; a red one here means a real violation."""
        done = subprocess.run(["python3", str(SCRIPT)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr[-2000:]

    def test_every_ledger_counter_is_declared(self) -> None:
        """A scope that empties must be visible AS ITSELF, so it needs a key."""
        assert "name words / dictionary" in guard.examined
        assert "interface text / app (exempt)" in guard.examined


class TestTheSelfDescription:
    """The arm that counts the arms — D12 of the 2026-08-19 handoff audit.

    THREE FILES CARRIED THREE DIFFERENT COUNTS AND NONE WAS RIGHT. The module
    docstring said « Four arms », `main` said « the four arms », the success
    line enumerated nine of them, and `CLAUDE.md` said « eleven » — while
    `main` actually called twelve. Each number had been typed by hand, so each
    drifted on its own schedule, and a reader who trusted « four » stopped
    looking for the other eight.

    The count is DERIVED now — `ARMS` is the single list and everything else
    reads its length — so these hold what prose still owns: the ENUMERATION in
    the docstring, and the sentence in `CLAUDE.md` that names the same number
    from another file entirely.
    """

    def test_no_arm_is_called_outside_the_list(self) -> None:
        """`main` walks `ARMS`; a bare call beside the loop would run undeclared."""
        assert guard.arms_bypassing_the_list() == []

    def test_the_docstring_enumerates_every_arm(self) -> None:
        """An arm nobody documented is an arm nobody knows to look for."""
        violations: list[str] = []
        guard.check_arm_count(violations)

        assert violations == []

    def test_a_missing_heading_is_refused(self, monkeypatch) -> None:
        """Mutation: drop one heading from the docstring and the arm must bite."""
        monkeypatch.setattr(guard, "__doc__", (guard.__doc__ or "").replace("**Test prose**", "**xx**"))
        violations: list[str] = []

        guard.check_arm_count(violations)

        assert any("Test prose" in v for v in violations), violations

    def test_the_docstrings_own_count_word_is_held(self, monkeypatch) -> None:
        """The word that said « Four » while twelve arms ran.

        An adversarial review defeated the first version of this arm in one
        line: it held the numbered HEADINGS and never the count word above
        them, so the docstring could be set back to « Four arms » and the gate
        stayed green — the headline defect surviving the arm named for it.
        """
        monkeypatch.setattr(
            guard,
            "__doc__",
            (guard.__doc__ or "").replace(
                f"{guard.NUMBER_WORDS[len(guard.ARMS)].capitalize()} arms, each with its own scope",
                "Four arms, each with its own scope",
            ),
        )
        violations: list[str] = []

        guard.check_arm_count(violations)

        assert any("Four arms" in v for v in violations), violations

    def test_an_arm_smuggled_through_a_helper_is_caught(self) -> None:
        """`main` must not reach into this module outside the loop.

        The first detector asked « is it named `check_*`? », and a helper named
        anything else walked straight past it. The question is now « does
        `main` call into this file at all? », which has no such hole.
        """
        source = guard.read(guard.Path(guard.__file__))
        assert "    for arm, _ in ARMS:" in source
        assert guard.arms_bypassing_the_list() == []

    def test_an_arm_defined_but_never_registered_is_caught(self) -> None:
        """The other direction: written, never run, and nothing would say so."""
        assert guard.unregistered_arms() == []

    def test_a_wrong_count_in_CLAUDE_md_is_refused(self, monkeypatch, tmp_path) -> None:
        """Mutation: the sentence in the OTHER file drifts, and the arm bites.

        This is the one that would have caught D9 — `CLAUDE.md` said eleven for
        as long as nothing read it from here.
        """
        fake = tmp_path / "CLAUDE.md"
        fake.write_text(
            "enforced by `scripts/check-no-french.py` (three arms, in `make check` and in CI):\n", encoding="utf-8"
        )
        monkeypatch.setattr(guard, "CLAUDE_MD", fake)
        violations: list[str] = []

        guard.check_arm_count(violations)

        assert any("CLAUDE.md" in v for v in violations), violations
