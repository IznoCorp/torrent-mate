"""Tests for the markup-contract guard.

THE PREVIOUS GUARD SHIPPED WITH NO TEST and an adversarial review defeated it
five ways within the hour. This one is held from the start, and the cases below
are the two dead controls it was written for plus the ways it could lie.

The contract it guards has three ends: markup emits `data-X="value"`, a handler
writes that value VERBATIM into a store field, readers compare the field. Move
two of the three and the control stops working while every other gate stays
green — which is what happened to the retry button on every error surface.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-markup-contracts.py"


def load():
    """Imports the guard, despite its hyphenated filename."""
    spec = importlib.util.spec_from_file_location("check_markup_contracts", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load()
# The anchor arm lives in `markup_anchors.py` beside the entry point, which
# imports it — so loading the guard puts it in `sys.modules`. The ratchet tests
# below patch the module that OWNS `write_baseline`'s globals: patching the
# re-export on the entry point would rebind a name that function never reads.
anchors = sys.modules["markup_anchors"]


class TestReadersOf:
    """Which literals count as « a reader understands this value »."""

    def test_a_strict_comparison_counts(self) -> None:
        """The ordinary shape."""
        assert "ready" in guard.readers_of("phase", 'state.phase === "ready"')

    def test_a_subscript_comparison_counts(self) -> None:
        """`x["pipe"] == "queued"` — the form a harness rule uses."""
        assert "queued" in guard.readers_of("pipe", 'got["pipe"] == "queued"')

    def test_a_default_written_in_an_object_counts(self) -> None:
        """`pipe: "idle"` is a reader too: it is what the field starts as."""
        assert "idle" in guard.readers_of("pipe", 'store.write({ pipe: "idle" })')

    def test_an_unrelated_field_does_not_leak(self) -> None:
        """`phase` must not collect what `hphase` compares."""
        assert guard.readers_of("phase", 'x.otherphase === "nope"') == set()


class TestTheContract:
    """The two dead controls, and the shapes that could hide one."""

    HANDLER = "store.write({ phase: closest.dataset.phase })"

    def test_a_value_no_reader_knows_is_refused(self) -> None:
        """B-031: `data-phase="prete"` wrote a phase nothing renders."""
        source = f'{self.HANDLER}\n<button data-phase="prete">Retry</button>\nx.phase === "ready"'

        assert "prete" not in guard.readers_of("phase", source)

    def test_a_value_a_reader_knows_is_accepted(self) -> None:
        """The repaired form."""
        source = f'{self.HANDLER}\n<button data-phase="ready">Retry</button>\nx.phase === "ready"'

        assert "ready" in guard.readers_of("phase", source)

    def test_a_COMMENT_does_not_make_a_value_known(self) -> None:
        """The mistake this guard made on its first run.

        `library.tsx` carries a comment describing a REJECTED first version —
        « gated it on `phase === "prete"` » — and reading it as code made the
        rule believe `prete` was understood, so it walked straight past the
        dead button it exists to catch. Three guards in this repository have
        now been fooled by a comment; this one is not.
        """
        commented = '// a first version gated it on `phase === "prete"`\nx.phase === "ready"'
        stripped = guard.COMMENT.sub(" ", commented)

        assert "prete" not in guard.readers_of("phase", stripped)
        assert "ready" in guard.readers_of("phase", stripped)

    def test_a_computed_value_is_not_judged(self) -> None:
        """`data-go="${id}"` cannot be checked, and must not be guessed at."""
        assert guard.EMITTED.search('data-go="${id}"') is None


class TestTheTreeItself:
    """The guard is only real if its scope is."""

    def test_the_maquette_has_no_dead_control(self) -> None:
        """Green on this repository; red here means a real dead button.

        `main([])` rather than `main()`: a caller in-process passes its own
        argument list — under a test runner `sys.argv` belongs to the
        runner, and a guard that reaches for it reads pytest's arguments.
        """
        assert guard.main([]) == 0

    def test_main_does_not_read_sys_argv_when_given_an_argv(self, monkeypatch) -> None:
        """An explicit argv is the only argv the guard may read.

        Whatever the runner put in `sys.argv` must not reach the guard when
        the caller passed its own list — this is the contract that broke.
        """
        monkeypatch.setattr(guard.sys, "argv", ["pytest", "-q", "--tb=short"])

        assert guard.main([]) == 0

    def test_the_summary_total_is_the_baseline_length(self, capsys) -> None:
        """The printed total counts each tolerated occurrence exactly once.

        `held` is a SUBSET of `selection`, so summing the three buckets
        counted the held occurrences twice and announced 974 tolerated
        against a baseline of 834 — a headline number that agreed with
        nothing. The baseline's own length is the oracle: every tolerated
        occurrence is one entry it owns.
        """
        expected = len(json.loads(guard.BASELINE.read_text(encoding="utf-8")))

        assert guard.main([]) == 0
        line = next(text for text in capsys.readouterr().out.splitlines() if "anchor occurrence(s) tolerated" in text)

        assert f"{expected} anchor occurrence(s) tolerated" in line

    def test_it_actually_found_forwarders_to_check(self) -> None:
        """A scope that empties would make « no violation » mean nothing."""
        sources = "\n".join(
            p.read_text(encoding="utf-8")
            for p in guard.SOURCES.rglob("*")
            if p.is_file() and p.suffix in {".js", ".ts", ".tsx"}
        )

        assert len(guard.FORWARDER.findall(guard.COMMENT.sub(" ", sources))) >= 5


class TestBaselineIdentity:
    """An occurrence is WHAT is selected and WHERE — never the selector string.

    Phase 2 rewrites the PREFIX of dozens of selectors
    (`'.screen.open .fback'` → `'[data-part="screen"][data-open] .fback'`)
    without moving the tokens those strings carry. An identity that
    includes the selector string sees each rewritten token as one removed
    and one added — a regeneration that refuses itself on its own
    committed baseline. The selector, like the line, is a display field.
    """

    FILE = "frontend/maquette/harness/actions.py"
    LINE = 42

    def _regenerate(self, monkeypatch, tmp_path, stored, fresh):
        """Wires `write_baseline` to a temp baseline and two faked readers.

        The subject of these tests is the ratchet — `fresh` held against
        `stored` on their identities — not the cross-check between the
        classifier subprocess and the guard's own extraction, which the
        real-tree regeneration exercises end to end. Both readers are
        therefore faked to return `fresh`, and the baseline path is faked
        into the test's temp directory.

        Args:
            monkeypatch: The pytest fixture.
            tmp_path: The pytest fixture.
            stored: The entries of the stored baseline.
            fresh: The entries both readers report now.

        Returns:
            The temp path the baseline is (or would be) written to.
        """
        baseline = tmp_path / "anchor-baseline.json"
        baseline.write_text(json.dumps(stored), encoding="utf-8")
        monkeypatch.setattr(anchors, "BASELINE", baseline)
        # The success message renders the baseline path relative to ROOT;
        # the real baseline lives under it, the test's temp one does not.
        monkeypatch.setattr(anchors, "ROOT", tmp_path)
        done = subprocess.CompletedProcess([], 0, json.dumps(fresh), "")
        monkeypatch.setattr(anchors.subprocess, "run", lambda *a, **k: done)
        findings = [
            (guard.entry_identity(e), e.get("selector", e.get("class")), f"{e['file']}:{e['line']}", False)
            for e in fresh
        ]
        monkeypatch.setattr(anchors, "collect_anchor_findings", lambda: findings)
        return baseline

    def _selection(self, selector, token, line=None):
        """Builds one selection entry, in the classifier's shape.

        Args:
            selector: The selector string — a display field.
            token: The class token the entry owns.
            line: The display line; default `LINE`.

        Returns:
            The entry dict.
        """
        return {
            "kind": "selection",
            "file": self.FILE,
            "line": line if line is not None else self.LINE,
            "selector": selector,
            "token": token,
        }

    def test_a_selector_prefix_rewrite_is_not_an_addition(self, monkeypatch, tmp_path):
        """The phase-2 shape: same token, new selector prefix.

        `.fback` under `.screen.open .fback` and under
        `[data-part="screen"][data-open] .fback` is the same occurrence —
        the same token in the same file. The regeneration must ACCEPT it:
        nothing added, and the fresh entry written with its new display
        selector.
        """
        stored = [self._selection(".screen.open .fback", ".fback")]
        fresh = [self._selection('[data-part="screen"][data-open] .fback', ".fback")]
        baseline = self._regenerate(monkeypatch, tmp_path, stored, fresh)

        assert guard.write_baseline() == 0
        assert json.loads(baseline.read_text(encoding="utf-8")) == fresh

    def test_a_genuinely_new_token_is_still_refused(self, monkeypatch, tmp_path):
        """A weaker key must not soften the ratchet: a NEW token is new debt.

        The same file presenting one more occurrence the stored baseline
        does not own — here `.probe-new`, a token it has never seen — must
        refuse the write and leave the stored baseline untouched.
        """
        stored = [self._selection(".screen.open .fback", ".fback")]
        fresh = stored + [self._selection(".probe-new", ".probe-new", line=self.LINE + 1)]
        baseline = self._regenerate(monkeypatch, tmp_path, stored, fresh)

        assert guard.write_baseline() == 1
        assert json.loads(baseline.read_text(encoding="utf-8")) == stored

    def test_a_fourth_occurrence_of_an_owned_token_is_an_addition(self, monkeypatch, tmp_path):
        """Multiplicity: three owned `.card`s gaining a fourth is one added.

        The identity is counted as a multiset — the same identity twice is
        two entries and must stay two, so a file with three baselined
        `.card`s presenting a fourth still refuses the write.
        """
        stored = [self._selection(".card", ".card", line=self.LINE + i) for i in range(3)]
        fresh = stored + [self._selection(".card", ".card", line=self.LINE + 9)]
        baseline = self._regenerate(monkeypatch, tmp_path, stored, fresh)

        assert guard.write_baseline() == 1
        assert json.loads(baseline.read_text(encoding="utf-8")) == stored


class TestEscapedPartSelections:
    r"""ARM 3's silent hole: a `data-part` selection written with escaped quotes.

    The selection side reads the harness as RAW TEXT. A selector hosted in a
    single-line double-quoted Python string carries its quotes ESCAPED —
    `'[data-part=\\"screen\\"]'` — and `PART_SELECTED` does not match a
    backslash where it expects a quote, so the selection is read by nothing.
    Ten of sub-phase 2.1's 63 selections were silently unread until their host
    strings were widened; nothing refused the shape, and the arm simply counted
    one fewer. A count nobody compares is a count nobody reads.
    """

    # The raw file text `[data-part=\"probe/part\"]` — the escaped shape, as it
    # appears inside a double-quoted Python string.
    ESCAPED = '[data-part=\\"probe/part\\"]'
    # The same selection written so the reader can read it.
    READABLE = '[data-part="probe/part"]'

    def _fixture(self, tmp_path, source):
        """Writes `source` as a fixture harness file.

        Args:
            tmp_path: The pytest fixture.
            source: The fixture file's text.

        Returns:
            The path written.
        """
        fixture = tmp_path / "fixture.py"
        fixture.write_text(source, encoding="utf-8")
        return fixture

    def test_a_held_escaped_selection_is_refused(self, tmp_path):
        r"""`SEL = "[data-part=\"probe/part\"]"` — the defect's plain shape."""
        fixture = self._fixture(tmp_path, f'SEL = "{self.ESCAPED}"\n')

        assert guard.escaped_part_selections(fixture) == [(1, f'SEL = "{self.ESCAPED}"')]

    def test_an_escaped_call_is_refused_and_read_by_nothing(self, tmp_path):
        """The measured shape: a selection call hosted in a `"…"` string.

        Both halves are asserted, because the refusal exists exactly because
        the reading fails: `part_selections` finds NOTHING here, and without
        the refusal that silence is the whole defect.
        """
        source = "await pg.evaluate(\"()=>document.querySelector('" + self.ESCAPED + "')\")\n"
        fixture = self._fixture(tmp_path, source)

        assert guard.part_selections(fixture) == []
        assert [line for line, _ in guard.escaped_part_selections(fixture)] == [1]

    def test_the_two_reading_shapes_are_not_refused(self, tmp_path):
        """A single-quoted selector inside a triple-quoted host needs no escape."""
        source = 'await pg.evaluate("""()=>document.querySelector(\'' + self.READABLE + '\')""")\n'
        fixture = self._fixture(tmp_path, source)

        assert guard.escaped_part_selections(fixture) == []
        assert guard.part_selections(fixture) == [(1, "probe/part")]

    def test_a_comment_is_refused_by_nothing(self, tmp_path):
        """A comment quoting the escaped shape is prose, not a selection."""
        fixture = self._fixture(tmp_path, f"# once written {self.ESCAPED}\n")

        assert guard.escaped_part_selections(fixture) == []

    def test_the_arm_exits_1_and_names_the_file(self, tmp_path, monkeypatch, capsys):
        """The refusal is the ARM's, not just the helper's.

        `harness_files` is patched on the entry point, which is the module
        whose globals `check_part_values` reads.
        """
        fixture = self._fixture(tmp_path, f'SEL = "{self.ESCAPED}"\n')
        monkeypatch.setattr(guard, "harness_files", lambda: [fixture])
        monkeypatch.setattr(guard, "ROOT", tmp_path)

        assert guard.check_part_values() == 1
        assert "fixture.py:1" in capsys.readouterr().err

    def test_the_harness_carries_no_escaped_selection(self):
        """Green on this repository: every selection is in a readable shape."""
        assert [(path, found) for path in guard.harness_files() if (found := guard.escaped_part_selections(path))] == []


class TestHeldPartSelections:
    """ARM 3's own held blind spot: a `data-part` selection no call names.

    The arm read a selection only where it was the literal ARGUMENT of a
    selection call. The harness holds selectors as readily as it passes them
    — `screen_port = '[data-part="screen"][data-open] .port'` handed to a
    helper, the `R14_CASES` and `layers` tables a loop walks, a ternary whose
    result a `querySelector` is given one line later. Every one of those is a
    selection, and a value renamed in the markup would leave them all
    selecting nothing while the arm printed a green count and said nothing.

    It is the ANCHOR arm's blind spot one attribute over, so it is read
    through the anchor arm's extraction — `held_literals` — and not through a
    second reader that would drift from it.
    """

    # A held selection whose value no source emits: the defect, minimal.
    HELD = '[data-part="probe/held"]'

    def _fixture(self, tmp_path, source):
        """Writes `source` as a fixture harness file.

        Args:
            tmp_path: The pytest fixture.
            source: The fixture file's text.

        Returns:
            The path written.
        """
        fixture = tmp_path / "fixture.py"
        fixture.write_text(source, encoding="utf-8")
        return fixture

    def test_a_held_selection_is_read(self, tmp_path) -> None:
        """`SEL = '[data-part="probe/held"]'` — held, named by no call.

        Both halves are asserted, because the reading exists exactly where
        the call pass is blind: `part_selections` finds NOTHING here, and
        that silence was the whole defect.
        """
        fixture = self._fixture(tmp_path, f"SEL = '{self.HELD}'\n")

        assert guard.part_selections(fixture) == []
        assert guard.held_part_selections(fixture) == [(1, "probe/held")]

    def test_the_arm_refuses_a_held_value_no_source_emits(self, tmp_path, monkeypatch, capsys) -> None:
        """The refusal is the ARM's, not just the helper's.

        `harness_files` is patched on the entry point, which is the module
        whose globals `check_part_values` reads.
        """
        fixture = self._fixture(tmp_path, f"SEL = '{self.HELD}'\n")
        monkeypatch.setattr(guard, "harness_files", lambda: [fixture])
        monkeypatch.setattr(guard, "ROOT", tmp_path)

        assert guard.check_part_values() == 1
        err = capsys.readouterr().err

        assert "fixture.py:1" in err
        assert "probe/held" in err

    def test_a_passed_selection_is_not_counted_twice(self, tmp_path) -> None:
        """A call's own argument belongs to the call pass, and to it alone.

        Counting it on both passes would inflate the printed number by
        exactly the population the arm already read — the way summing the
        anchor arm's buckets once announced 974 against a baseline of 834.
        """
        fixture = self._fixture(tmp_path, f"querySelector('{self.HELD}')\n")

        assert guard.part_selections(fixture) == [(1, "probe/held")]
        assert guard.held_part_selections(fixture) == []

    def test_a_comment_holding_a_selection_is_read_by_nothing(self, tmp_path) -> None:
        """A comment quoting a selector is prose — in Python and in the JS."""
        # One fixture path, so the two shapes are written and read in turn.
        assert guard.held_part_selections(self._fixture(tmp_path, f"# held '{self.HELD}'\n")) == []
        embedded = f'X = """// held \'{self.HELD}\'"""\n'

        assert guard.held_part_selections(self._fixture(tmp_path, embedded)) == []

    def test_a_computed_value_is_skipped_whole(self, tmp_path) -> None:
        """`[data-part="${k}"]` names no literal, and must not be half-read."""
        assert guard.held_part_selections(self._fixture(tmp_path, "SEL = '[data-part=\"${k}\"] .port'\n")) == []

    def test_the_repository_holds_selections_the_call_pass_never_saw(self) -> None:
        """Non-vacuity: this pass reads something on the real harness.

        A pass that finds nothing everywhere is a pass proving nothing, and
        its green would be indistinguishable from an oversight.
        """
        found = {path.name for path in guard.harness_files() if guard.held_part_selections(path)}

        assert len(found) >= 4, found

    def test_the_printed_line_breaks_the_count_down(self, capsys) -> None:
        """A total nobody can break down is a total nobody can tell is short."""
        assert guard.check_part_values() == 0
        line = next(text for text in capsys.readouterr().out.splitlines() if "data-part selection(s) checked" in text)

        assert "of them held)" in line


class TestImperativeEmission:
    """ARM 3's emission blind spot: an element built in script, not markup.

    The reader knew one syntactic position for an emission — the attribute
    written into markup or JSX as `data-part="value"`. A node the engine
    builds imperatively carries no such text: it is created, given a class
    and appended, so its anchor is an assignment. The episode popover is
    exactly that shape, and the arm would have called a whole contract
    broken — selected four times, emitted nowhere — while both of its ends
    were in place.

    A computed value stays unread on both forms, for the reason the arm
    already skips `${…}`: half-reading a name is worse than not reading it.
    """

    # The two imperative shapes, and a value no markup could carry.
    DATASET = 'el.dataset.part = "probe/imperative";\n'
    SET_ATTRIBUTE = 'el.setAttribute("data-part", "probe/imperative");\n'

    def _source(self, tmp_path, text):
        """Writes `text` as a fixture emission site.

        Args:
            tmp_path: The pytest fixture.
            text: The fixture file's source.

        Returns:
            The path written.
        """
        fixture = tmp_path / "fixture.js"
        fixture.write_text(text, encoding="utf-8")
        return fixture

    def test_a_dataset_assignment_emits(self, tmp_path) -> None:
        """`el.dataset.part = "…"` is an emission, in script rather than markup."""
        assert guard.emitted_part_values(self._source(tmp_path, self.DATASET)) == {"probe/imperative"}

    def test_a_set_attribute_call_emits(self, tmp_path) -> None:
        """`el.setAttribute("data-part", "…")` is the same emission, spelled out."""
        assert guard.emitted_part_values(self._source(tmp_path, self.SET_ATTRIBUTE)) == {"probe/imperative"}

    def test_a_computed_imperative_value_is_skipped_whole(self, tmp_path) -> None:
        """A value the script computes names no literal to compare against."""
        computed = 'el.dataset.part = kind;\nel.setAttribute("data-part", `part/${k}`);\n'

        assert guard.emitted_part_values(self._source(tmp_path, computed)) == set()

    def test_a_comment_holding_an_assignment_emits_nothing(self, tmp_path) -> None:
        """A comment describing the assignment is prose, and emits nothing."""
        assert guard.emitted_part_values(self._source(tmp_path, "// " + self.DATASET)) == set()

    def test_the_arm_accepts_a_selection_an_imperative_emission_satisfies(self, tmp_path, monkeypatch, capsys) -> None:
        """The whole arm, not just the helper: a contract in two halves holds.

        Both ends are fixtures — a harness file selecting the probe value and
        a source emitting it imperatively — so the assertion is about the
        reader, not about what the repository happens to contain.
        """
        harness = tmp_path / "fixture.py"
        harness.write_text("querySelector('[data-part=\"probe/imperative\"]')\n", encoding="utf-8")
        source = self._source(tmp_path, self.DATASET)
        monkeypatch.setattr(guard, "harness_files", lambda: [harness])
        monkeypatch.setattr(guard, "emission_files", lambda: [guard.SHELL, source])
        monkeypatch.setattr(guard, "ROOT", tmp_path)

        assert guard.check_part_values() == 0, capsys.readouterr().err

    def test_the_repository_emits_a_part_imperatively(self) -> None:
        """Non-vacuity: this reading finds something on the real sources.

        A pass that reads nothing anywhere is a pass whose green says
        nothing, and the engine builds the episode popover in script.
        """
        engine = guard.SOURCES / "engine" / "legacy.js"

        assert "episode/popover" in guard.emitted_part_values(engine)


class TestHeldSelectors:
    """The instrument's second blind spot: selectors held outside a call.

    A selector held in a variable or a table is read by nothing today —
    `selection_calls` names only the literal ARGUMENT of a selection call —
    yet it breaks at L07 exactly like the occurrences already baselined.
    The held pass reads every selector-shaped string literal outside a
    selection call, and the false-positive rule — every class token
    emitted by a design site as a class= / className= token, OR selector
    structure (a combinator, an attribute block, a comma list) — is a
    RULE, not a list of exceptions. `.json5` fails both.
    """

    def _held(self, tmp_path, source, emitted=frozenset()):
        """Writes `source` as a fixture harness file and reads it back.

        Args:
            tmp_path: The pytest fixture.
            source: The fixture file's text.
            emitted: The class tokens the design sites emit, faked for the
                test — the false-positive rule's emission half is decided
                by this set.

        Returns:
            The `(line, content)` pairs `held_occurrences` found.
        """
        fixture = tmp_path / "fixture.py"
        fixture.write_text(source, encoding="utf-8")
        return guard.held_occurrences(fixture, emitted)

    def test_a_variable_holding_a_selector_yields_its_tokens(self, tmp_path):
        """`SEL = ".foo .bar"` then `querySelector(SEL)`: two occurrences.

        The call's argument is a variable, so the first pass names nothing;
        the held pass reads the definition the variable holds.
        """
        found = self._held(tmp_path, 'SEL = ".foo .bar"\nquerySelector(SEL)\n')

        assert found == [(1, ".foo .bar")]
        assert guard.class_tokens(".foo .bar") == [".foo", ".bar"]

    def test_a_file_extension_is_not_a_selector(self, tmp_path):
        """`.json5` — nothing emits the class, and it has no structure."""
        assert self._held(tmp_path, 'EXT = ".json5"\n') == []

    def test_an_emitted_token_qualifies_without_structure(self, tmp_path):
        """`.sact` passes on emission — and fails without it."""
        assert self._held(tmp_path, 'SEL = ".sact"\n', {"sact"}) == [(1, ".sact")]
        assert self._held(tmp_path, 'SEL = ".sact"\n') == []

    def test_a_call_argument_is_not_held(self, tmp_path):
        """The first pass already reads the literal argument."""
        assert self._held(tmp_path, 'querySelector(".card")\n', {"card"}) == []

    def test_structure_qualifies_even_when_nothing_emits_the_token(self, tmp_path):
        """A combinator is selector structure, whatever the emission says."""
        assert self._held(tmp_path, 'SEL = ".probe-held .card"\n') == [(1, ".probe-held .card")]

    def test_an_attribute_block_is_selector_structure(self, tmp_path):
        """`[data-panel]` is a selector, so `.tile[data-panel]` qualifies."""
        assert self._held(tmp_path, 'SEL = ".tile[data-panel]"\n') == [(1, ".tile[data-panel]")]

    def test_a_method_call_shape_is_not_a_selector(self, tmp_path):
        """`.render(` names a method, not a class."""
        assert self._held(tmp_path, 'SEL = ".render("\n', {"render"}) == []

    def test_a_comment_mention_is_read_by_nothing(self, tmp_path):
        """A comment quoting a selector is prose, not a selection."""
        assert self._held(tmp_path, "# mentions '.sact'\n", {"sact"}) == []
        assert self._held(tmp_path, 'X = """// mentions \'.sact\'"""\n', {"sact"}) == []

    def test_the_classifier_counts_held_occurrences_separately(self, tmp_path):
        """The two populations are reported apart, and summed."""
        fixture = tmp_path / "fixture.py"
        fixture.write_text('SEL = ".foo .bar"\nquerySelector(SEL)\nquerySelector(".screen")\n')
        run = subprocess.run(
            [sys.executable, str(SCRIPT.parent / "classify-rule-anchors.py"), "--tokens", str(tmp_path)],
            capture_output=True,
            text=True,
        )

        assert run.returncode == 0, run.stderr
        assert "2 class token occurrences held outside any selection call" in run.stdout
        assert "3 class token occurrences total" in run.stdout


class TestHarnessParses:
    r"""The precondition: a rule file Python cannot read is a violation.

    Sub-phase 4.1's hole, and it is the defect class this whole guard exists
    to end. A rewrite substituted `[data-part="suggestion/wrap"]` into
    selectors hosted in single-line DOUBLE-quoted Python strings: the raw `"`
    ended the literal, and `inter.py` and `mouse.py` STOPPED PARSING. Every
    instrument then read them and reported no violation — this guard exited
    0, `--write-baseline` wrote happily, `classify-rule-anchors.py` counted.
    Only running the rules would have fallen, and that pass takes sixteen
    minutes.

    Nothing raised because nothing PARSES: the arms read the harness as raw
    text, and `comment_masked` tokenizes — and `tokenize` does not raise on a
    stray quote, it simply re-lexes what follows. A reader that keeps going
    over a file the interpreter refuses reports a count one short, in
    silence.
    """

    # 4.1's exact shape: a raw `"` inside a `"…"` literal. The string ends at
    # `data-part=`, and the `probe` that follows is a NAME where Python
    # expects an operator.
    BROKEN = 'X = "()=>document.querySelector(\'[data-part="probe/x"]\')"\n'
    # The same selection, hosted so nothing needs escaping — the shape the
    # instruction in ARM 3's refusal asks for.
    READABLE = 'X = """()=>document.querySelector(\'[data-part="probe/x"]\')"""\n'

    def _fixture(self, tmp_path, source):
        """Writes `source` as a fixture harness file.

        Args:
            tmp_path: The pytest fixture.
            source: The fixture file's text.

        Returns:
            The path written.
        """
        fixture = tmp_path / "fixture.py"
        fixture.write_text(source, encoding="utf-8")
        return fixture

    def test_a_stray_quote_is_a_violation(self, tmp_path):
        """The defect, minimal: the file, the line and the parser's word."""
        fixture = self._fixture(tmp_path, self.BROKEN)

        found = guard.parse_failures([fixture])

        assert [(path, line) for path, line, _ in found] == [(fixture, 1)]
        assert "invalid syntax" in found[0][2]

    def test_a_file_that_parses_is_not_a_violation(self, tmp_path):
        """The same selection in a readable host owes the precondition nothing."""
        assert guard.parse_failures([self._fixture(tmp_path, self.READABLE)]) == []

    def test_every_instrument_reads_the_broken_file_and_says_nothing(self, tmp_path):
        """WHY the precondition exists — the oracle outside this guard.

        The raw-text readers walk the file happily: no escaped quote, so ARM
        3's refusal finds nothing, and `comment_masked` hands back text
        rather than raising, exactly as its documented fallback promises.
        Meanwhile the interpreter cannot read the file at all — so every rule
        it holds is dead and no instrument says so.
        """
        fixture = self._fixture(tmp_path, self.BROKEN)

        assert guard.escaped_part_selections(fixture) == []
        assert guard.comment_masked(self.BROKEN) == self.BROKEN
        with pytest.raises(SyntaxError):
            compile(self.BROKEN, "fixture.py", "exec")

    def test_the_precondition_exits_1_and_names_file_line_and_message(self, tmp_path, monkeypatch, capsys):
        """The refusal is the RUN's, not just the helper's.

        `harness_files` is patched on the entry point, which is the module
        whose globals the precondition reads.
        """
        fixture = self._fixture(tmp_path, self.BROKEN)
        monkeypatch.setattr(guard, "harness_files", lambda: [fixture])
        monkeypatch.setattr(guard, "ROOT", tmp_path)

        assert guard.check_harness_parses() == 1
        err = capsys.readouterr().err

        assert "fixture.py:1" in err
        assert "invalid syntax" in err

    def test_the_arms_still_run_over_the_corpus(self, tmp_path, monkeypatch):
        """One broken file must not hide what the arms would have said.

        The author sees everything at once: the run exits 1 for the parse
        failure AND every arm reports. An early return would trade one silent
        short count for another.
        """
        ran = []
        monkeypatch.setattr(guard, "check_harness_parses", lambda: 1)
        for arm in ("check_forwarded_values", "check_anchor_debt", "check_part_values", "check_state_attributes"):
            monkeypatch.setattr(guard, arm, lambda name=arm: ran.append(name) or 0)

        assert guard.main([]) == 1
        assert ran == ["check_forwarded_values", "check_anchor_debt", "check_part_values", "check_state_attributes"]

    def test_every_harness_file_parses(self):
        """Green on this repository: all 52 rule files are readable Python."""
        assert guard.parse_failures(guard.harness_files()) == []
