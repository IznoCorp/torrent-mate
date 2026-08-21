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
