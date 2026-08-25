"""Tests for the no-abbreviation guard.

The rule is `docs/reference/code-naming.md`: a declared name is written out in
full. The guard reads the three roots with `ast`, refuses a name built from a
word on the blacklist, and freezes the standing debt PER FILE.

Each case here holds one property the guard would be worthless without: that a
new occurrence is refused wherever it lands, that a file reaching zero must
leave the record, that the two word files cannot contradict each other, that an
entry with no reason is itself a violation, and — the one that matters most —
that a corpus reading to nothing is a violation rather than a pass. A guard
that measures nothing and reports « nothing grew » is the shape this repository
keeps finding under a green gate.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-code-abbreviations.py"


def load():
    """Imports the guard, despite its hyphenated filename."""
    spec = importlib.util.spec_from_file_location("check_code_abbreviations", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load()


class TestWordCutting:
    """A name is cut on its separators, then on its case boundaries."""

    def test_snake_case_is_cut_on_its_underscores(self) -> None:
        """An underscore separates words."""
        assert guard.words_of("media_dir_path") == ["media", "dir", "path"]

    def test_camel_case_is_cut_on_its_capitals(self) -> None:
        """A capital starts a word."""
        assert guard.words_of("mediaDirPath") == ["media", "dir", "path"]

    def test_an_acronym_run_is_one_word_and_not_four_letters(self) -> None:
        """`HTTPTransport` is `http` and `transport` — never `h`, `t`, `t`, `p`."""
        assert guard.words_of("HTTPTransport") == ["http", "transport"]

    def test_a_digit_run_is_its_own_word(self) -> None:
        """A run of digits is a word, and never letters."""
        assert guard.words_of("spacing8Step") == ["spacing", "8", "step"]


class TestDeclaredNames:
    """Every shape that DECLARES a name is read, and a use is not one."""

    def test_the_declaring_shapes_are_all_read(self) -> None:
        """Class, function, parameter, local, loop target, `except … as`, alias."""
        source = (
            "import os.path as msg_alias\n"
            "class CfgHolder:\n"
            "    def run(self, num_of):\n"
            "        idx_here = 1\n"
            "        for pos_loop in ():\n"
            "            pass\n"
            "        try:\n"
            "            pass\n"
            "        except ValueError as err_caught:\n"
            "            print(err_caught)\n"
            "        return idx_here, pos_loop, num_of\n"
        )
        found = {name for name, _ in guard.declared_names(ast.parse(source))}
        assert {"msg_alias", "CfgHolder", "run", "num_of", "idx_here", "pos_loop", "err_caught"} <= found

    def test_a_name_only_USED_is_not_a_declaration(self) -> None:
        """The guard reads declarations; a third-party spelling is not ours."""
        found = {name for name, _ in guard.declared_names(ast.parse("print(cfg.value)\n"))}
        assert "cfg" not in found


class TestListArm:
    """The two word files are held well formed, and against each other."""

    def test_a_word_in_both_files_is_a_violation(self, capsys) -> None:
        """One file would quietly win, and which one depends on read order."""
        violations = guard.arm_lists({"cfg": "configuration"}, {"cfg": "it is fine"}, [])
        captured = capsys.readouterr()
        assert violations == 1
        assert "refused AND kept" in captured.err

    def test_an_entry_with_no_reason_is_a_violation(self, tmp_path, capsys) -> None:
        """An exemption nobody justified is indistinguishable from an oversight."""
        listing = tmp_path / "words.txt"
        listing.write_text("# a comment\nzzz =\n", encoding="utf-8")
        words, complaints = guard.read_word_file(listing)
        assert words == {}
        assert len(complaints) == 1 and "says nothing" in complaints[0]

    def test_a_word_listed_twice_is_a_violation(self, tmp_path) -> None:
        """A list that repeats itself is a list nobody is reading."""
        listing = tmp_path / "words.txt"
        listing.write_text("cfg = configuration\ncfg = configuration\n", encoding="utf-8")
        _, complaints = guard.read_word_file(listing)
        assert len(complaints) == 1 and "listed twice" in complaints[0]

    def test_a_missing_file_is_a_violation_not_an_empty_list(self, tmp_path) -> None:
        """No list read means the arm cannot be checked — never that nothing is refused."""
        words, complaints = guard.read_word_file(tmp_path / "absent.txt")
        assert words == {}
        assert len(complaints) == 1 and "is missing" in complaints[0]

    def test_the_repository_s_own_two_files_are_well_formed(self, capsys) -> None:
        """The lists this repository ships are held to their own rule."""
        refused, first = guard.read_word_file(guard.REFUSED_FILE)
        allowed, second = guard.read_word_file(guard.ALLOWED_FILE)
        assert guard.arm_lists(refused, allowed, first + second) == 0, capsys.readouterr().err
        assert refused and allowed


class TestNamesArm:
    """The ratchet, and the floor under it."""

    def test_an_empty_corpus_is_a_violation_not_a_pass(self, monkeypatch, capsys) -> None:
        """« Nothing grew » about nothing is the reading this guard exists to refuse."""
        monkeypatch.setattr(guard, "CORPUS", ("does-not-exist",))
        violations = guard.arm_names({"cfg": "configuration"}, listing=False)
        captured = capsys.readouterr()
        assert violations == 1
        assert "the corpus is empty" in captured.err

    def test_a_file_over_its_recorded_count_is_a_violation(self, monkeypatch, tmp_path, capsys) -> None:
        """The ratchet only turns one way."""
        record = tmp_path / "baseline.json"
        record.write_text(json.dumps({"what": "", "total": 0, "files": {}}), encoding="utf-8")
        monkeypatch.setattr(guard, "BASELINE_FILE", record)
        violations = guard.arm_names({"cfg": "configuration"}, listing=False)
        captured = capsys.readouterr()
        assert violations >= 1
        assert "recorded" in captured.err

    def test_a_file_that_reached_zero_must_leave_the_record(self, monkeypatch, tmp_path, capsys) -> None:
        """A record describing a tree that has moved is a record nobody can trust."""
        record = tmp_path / "baseline.json"
        live = json.loads(
            (Path(guard.ROOT) / "scripts" / "code-abbreviations-baseline.json").read_text(encoding="utf-8")
        )
        # A path that carries none of the refused words — its live count is zero.
        live["files"]["scripts/nothing-of-the-sort.py"] = 4
        record.write_text(json.dumps(live), encoding="utf-8")
        monkeypatch.setattr(guard, "BASELINE_FILE", record)
        refused, _ = guard.read_word_file(guard.REFUSED_FILE)
        violations = guard.arm_names(refused, listing=False)
        captured = capsys.readouterr()
        assert violations == 1, captured.err
        assert "leaves the record" in captured.err

    def test_the_repository_reads_clean_against_its_own_record(self, capsys) -> None:
        """The armed guard is green on the tree it lands with."""
        refused, _ = guard.read_word_file(guard.REFUSED_FILE)
        violations = guard.arm_names(refused, listing=False)
        captured = capsys.readouterr()
        assert violations == 0, captured.err
        # The summary shows its numbers — a green line that prints nothing is a
        # green line nobody can hold against the tree.
        assert "declared name(s) over" in captured.out
