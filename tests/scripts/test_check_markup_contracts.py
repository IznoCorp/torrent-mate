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
import re
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


def load_values():
    """Imports the French guard's value arm, which is a plain module."""
    sys.path.insert(0, str(SCRIPT.parent))
    import nofrench_values

    return nofrench_values


guard = load()
# The anchor arm lives in `markup_anchors.py` beside the entry point, which
# imports it — so loading the guard puts it in `sys.modules`. The floor tests
# below patch the module that OWNS the arm's globals: patching the re-export on
# the entry point would rebind a name the arm never reads.
anchors = sys.modules["markup_anchors"]
# ARM 4 lives in `markup_states.py`, for the same reason and with the same
# consequence: its corpus is DERIVED, so the derivation's tests patch the module
# that reads the harness rather than the entry point that calls the arm.
states = sys.modules["markup_states"]


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

    def test_the_anchor_arm_reports_a_hard_zero(self, capsys) -> None:
        """The arm says what it read, and what it read is zero.

        The count it used to print was « N tolerated », held against a
        burn-down baseline. There is no baseline any more, so the number
        that means something is the CORPUS: zero class anchors over every
        rule file, passed or held. A guard reporting zero over an empty
        corpus would print the same zero, which is why the file count is
        in the same sentence.
        """
        assert guard.main([]) == 0
        line = next(text for text in capsys.readouterr().out.splitlines() if "class-anchored selection call" in text)

        assert "0 class-anchored selection call" in line
        assert f"over {len(guard.harness_files())} harness rule file(s)" in line

    def test_it_actually_found_forwarders_to_check(self) -> None:
        """A scope that empties would make « no violation » mean nothing."""
        sources = "\n".join(
            p.read_text(encoding="utf-8")
            for p in guard.SOURCES.rglob("*")
            if p.is_file() and p.suffix in {".js", ".ts", ".tsx"}
        )

        assert len(guard.FORWARDER.findall(guard.COMMENT.sub(" ", sources))) >= 5


class TestTheHardZeroFloor:
    """The FIRST class anchor is refused. There is no list to consult.

    These were the ratchet's tests: a burn-down baseline held the shipped
    debt, an occurrence it owned was tolerated and counted, and a
    regeneration refused to grow. The burn-down reached zero, and an empty
    list is a floor someone can raise again — so the file, the ratchet and
    the `--allow-additions` escape hatch went with the debt they carried.

    What the tests assert therefore inverts: not « an occurrence the
    baseline does not own is refused » but « an occurrence is refused ».
    The distinction is the whole sub-phase, and it is exactly what a
    re-added baseline entry would have hidden.
    """

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

    def _arm(self, tmp_path, monkeypatch, source):
        """Runs the anchor arm over one fixture file.

        `harness_files` and `ROOT` are patched on `markup_anchors`, the
        module whose globals the arm reads — patching the re-export on the
        entry point would rebind a name the arm never looks at.

        Args:
            tmp_path: The pytest fixture.
            monkeypatch: The pytest fixture.
            source: The fixture harness file's text.

        Returns:
            The arm's exit code.
        """
        fixture = self._fixture(tmp_path, source)
        monkeypatch.setattr(anchors, "harness_files", lambda: [fixture])
        monkeypatch.setattr(anchors, "ROOT", tmp_path)
        return guard.check_anchor_debt()

    def test_the_first_class_anchored_call_is_refused(self, tmp_path, monkeypatch, capsys) -> None:
        """One occurrence, no baseline, exit 1 — naming file, line and token."""
        assert self._arm(tmp_path, monkeypatch, "querySelector('.card')\n") == 1
        err = capsys.readouterr().err

        assert "fixture.py:1" in err and ".card" in err
        assert "1 anchor occurrence(s)" in err

    def test_the_first_held_class_anchor_is_refused(self, tmp_path, monkeypatch, capsys) -> None:
        """A selector held in a variable is refused exactly like a call's."""
        assert self._arm(tmp_path, monkeypatch, "SEL = '.probe-held .card'\n") == 1
        err = capsys.readouterr().err

        assert "held outside any selection call" in err
        assert "2 anchor occurrence(s)" in err, "two tokens in one selector are two occurrences"

    def test_a_migrated_state_assertion_is_refused(self, tmp_path, monkeypatch, capsys) -> None:
        """`classList.contains('open')` reads a class the state has left."""
        assert self._arm(tmp_path, monkeypatch, "el.classList.contains('open')\n") == 1

        assert "hasAttribute('data-open')" in capsys.readouterr().err

    def test_a_genre_name_at_an_undeclared_site_is_refused(self, tmp_path, monkeypatch, capsys) -> None:
        """The exemption is a SITE, so the name alone buys nothing.

        `h2` was a permanent exception by NAME, and `machine.py` used it to
        walk siblings looking for the next heading — structure, under a
        written reason that described a geometry rule two files over. A
        name-keyed list cannot tell the two uses apart; only the site can.
        """
        assert self._arm(tmp_path, monkeypatch, "el.classList.contains('h2')\n") == 1

        assert "GENRE_SITES" in capsys.readouterr().err

    def test_a_declared_genre_site_survives_the_floor(self, tmp_path, monkeypatch, capsys) -> None:
        """A site in the table is exempt, and is COUNTED as exempt.

        The fixture is named after a real declared site so the (file, line,
        class) key matches; what is proven is the keying, not the reason.
        """
        fixture = tmp_path / "audit.py"
        fixture.write_text("\n" * 100 + "el.classList.contains('ep')\n", encoding="utf-8")
        monkeypatch.setattr(anchors, "harness_files", lambda: [fixture])
        monkeypatch.setattr(anchors, "ROOT", tmp_path)

        assert guard.check_anchor_debt() == 0
        assert "1 genre assertion(s) exempt" in capsys.readouterr().out

    def test_every_declared_exemption_carries_a_reason(self) -> None:
        """A reason-less exemption is itself a violation (ACC-11)."""
        assert anchors.GENRE_SITES
        assert all(reason.strip() for reason in anchors.GENRE_SITES.values())
        assert len({reason for reason in anchors.GENRE_SITES.values()}) == len(anchors.GENRE_SITES), (
            "one sentence covering every site distinguishes none of them"
        )

    def test_each_declared_exemption_still_names_a_live_assertion(self) -> None:
        """A site that MOVED is an exemption nobody re-read.

        The key is `file:line`, and that is the intended cost: an
        exemption is a claim about ONE assertion.
        """
        live = {
            (path.name, line, name) for path in anchors.harness_files() for line, name in anchors.state_assertions(path)
        }

        assert set(anchors.GENRE_SITES) <= live

    def test_the_guard_takes_no_argument_any_more(self, capsys) -> None:
        """`--write-baseline` is gone, and saying so is part of the removal."""
        assert guard.main(["--write-baseline"]) == 1

        assert "the burn-down baseline" in capsys.readouterr().err

    def test_nothing_reads_a_baseline_file(self) -> None:
        """No path, no loader, no writer — and no file on disk.

        A guard that still knew where a baseline lived would be one edit
        from consulting it again.
        """
        assert not (Path(guard.ROOT) / "frontend" / "maquette" / "anchor-baseline.json").exists()
        assert not [name for name in ("BASELINE", "load_baseline", "write_baseline") if hasattr(anchors, name)]
        assert "anchor-baseline" not in SCRIPT.read_text(encoding="utf-8")

    def test_the_second_reader_finds_no_class_anchor_either(self) -> None:
        """The cross-check that `--write-baseline` used to make, kept.

        The regeneration held the guard's own extraction against the
        independent classifier's and refused to write when they disagreed.
        Deleting it would leave the floor resting on ONE reader's zero, so
        the agreement is asserted here instead: both read the real harness,
        and both must find nothing.
        """
        run = subprocess.run(
            [sys.executable, str(SCRIPT.parent / "classify-rule-anchors.py"), "--baseline"],
            capture_output=True,
            text=True,
        )

        assert run.returncode == 0, run.stderr
        assert json.loads(run.stdout) == []


class TestTheFifthSyntacticPosition:
    """A class name READ from the class attribute, outside a selector.

    THE HOLE, AND IT IS THE SAME FAMILY THE ARM WAS WRITTEN FOR. Until this
    class existed the arm knew FOUR positions a class name can occupy: the
    literal argument of a selection call, a selector-shaped held literal, a
    `classList.contains` argument, and — one attribute over — a
    `data-part` value. A rule can also read the class ATTRIBUTE itself and
    decide on a name it finds there, and that is a fifth position no reader
    opened: `className.includes('in_library')`, `className.split(' ')
    .includes('primary')`, `className.replace('ep ', '')`, a table of class
    names matched against a spread `classList`, a twelve-token regex tested
    against `className`, and a CSS rule a rule INJECTS. Six shapes, all of
    them selection work, all of them dying at the stylesheet conversion with
    no instrument able to say so.

    Each fixture below is the minimal spelling of one shape. They are
    planted, not quoted from the harness, so the arm is proven against the
    SHAPE rather than against the six sites that happened to exist.
    """

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

    def _arm(self, tmp_path, monkeypatch, source):
        """Runs the anchor arm over one fixture file.

        Args:
            tmp_path: The pytest fixture.
            monkeypatch: The pytest fixture.
            source: The fixture harness file's text.

        Returns:
            The arm's exit code.
        """
        fixture = self._fixture(tmp_path, source)
        monkeypatch.setattr(anchors, "harness_files", lambda: [fixture])
        monkeypatch.setattr(anchors, "ROOT", tmp_path)
        return guard.check_anchor_debt()

    def test_a_membership_test_on_the_class_attribute_is_refused(self, tmp_path, monkeypatch, capsys) -> None:
        """`className.includes('x')` selects by class without a selector."""
        source = 'JS = """()=>list.find(e=>e.className.includes(\'in_library\'))"""\n'
        assert self._arm(tmp_path, monkeypatch, source) == 1
        err = capsys.readouterr().err

        assert "fixture.py:1" in err and "in_library" in err

    def test_a_split_membership_test_is_refused(self, tmp_path, monkeypatch, capsys) -> None:
        """The split between `className` and `includes` hides nothing."""
        source = 'JS = """(b)=>b.className.split(\' \').includes(\'primary\')"""\n'
        assert self._arm(tmp_path, monkeypatch, source) == 1

        assert "primary" in capsys.readouterr().err

    def test_a_replace_on_the_class_attribute_is_refused(self, tmp_path, monkeypatch, capsys) -> None:
        """`className.replace('ep ', '')` names `ep` and strips it."""
        source = 'JS = """(x)=>x.className.replace(\'ep \', \'\')"""\n'
        assert self._arm(tmp_path, monkeypatch, source) == 1

        assert "'ep'" in capsys.readouterr().err

    def test_an_equality_on_the_class_attribute_is_refused(self, tmp_path, monkeypatch, capsys) -> None:
        """The same read written as a comparison."""
        source = 'JS = """(x)=>x.className === \'card\'"""\n'
        assert self._arm(tmp_path, monkeypatch, source) == 1

        assert "'card'" in capsys.readouterr().err

    def test_an_empty_comparison_names_no_class(self, tmp_path, monkeypatch) -> None:
        """`className === ''` asks whether the element is unclassed."""
        source = 'JS = """(x)=>x.className === \'\'"""\n'
        assert self._arm(tmp_path, monkeypatch, source) == 0

    def test_a_regex_of_class_names_is_refused_branch_by_branch(self, tmp_path, monkeypatch, capsys) -> None:
        """Twelve tokens in a regex literal are twelve occurrences."""
        source = 'JS = """(x)=>/burger|fab|seg\\\\b/.test(x.className)"""\n'
        assert self._arm(tmp_path, monkeypatch, source) == 1
        err = capsys.readouterr().err

        assert "'burger'" in err and "'fab'" in err and "'seg'" in err
        assert "3 anchor occurrence(s)" in err

    def test_a_class_list_read_as_a_collection_is_refused(self, tmp_path, monkeypatch, capsys) -> None:
        """A table of class names matched against a spread `classList`.

        The names are object KEYS, so there is no literal to name and the
        refusal names the SITE — which is the whole point: nothing else in
        this guard can see a class name that is never quoted.
        """
        source = 'JS = """(b)=>TONS[[...b.classList].find((c) => TONS[c])]"""\n'
        assert self._arm(tmp_path, monkeypatch, source) == 1

        assert "fixture.py:1" in capsys.readouterr().err

    def test_adding_and_removing_a_class_is_not_a_read(self, tmp_path, monkeypatch) -> None:
        """A rule that DRIVES the document writes classes; it selects none."""
        source = 'JS = """()=>document.documentElement.classList.add(\'measuring\')"""\n'
        assert self._arm(tmp_path, monkeypatch, source) == 0

    def test_an_injected_css_rule_is_refused(self, tmp_path, monkeypatch, capsys) -> None:
        """A rule a harness rule INJECTS carries a selector like any other."""
        source = 'JS = """(n)=>{st.textContent = \'.cov{-webkit-line-clamp:\' + n + \'}\';}"""\n'
        assert self._arm(tmp_path, monkeypatch, source) == 1

        assert "'cov'" in capsys.readouterr().err

    def test_reading_a_stylesheet_as_text_is_not_a_selection(self, tmp_path, monkeypatch) -> None:
        """`".splashbar {" in gate` — the subject IS the source text.

        Nothing is assigned and nothing selects: the rule asserts that a
        block of CSS reached the served document, and it keeps the class
        name the stylesheet is still written in.
        """
        source = 'check("the gate carries the style", ".splashbar {" in gate)\n'
        assert self._arm(tmp_path, monkeypatch, source) == 0

    def test_reporting_the_class_attribute_is_not_a_read(self, tmp_path, monkeypatch) -> None:
        """A rule that PRINTS an element's class names no class of its own."""
        source = 'JS = """()=>els.map(el=>el.className||el.tagName)"""\n'
        assert self._arm(tmp_path, monkeypatch, source) == 0

    def test_the_second_reader_sees_the_fifth_position_too(self, tmp_path) -> None:
        """Two readers, or one reader's zero is a claim.

        `classify-rule-anchors.py --baseline` reads the same corpus through
        its own extraction; a position only the guard knows about would
        leave the independent listing empty over a live class dependency.
        """
        self._fixture(
            tmp_path, 'JS = """()=>list.find(e=>e.className.includes(\'in_library\'))"""\nquerySelector(\'#view\')\n'
        )
        run = subprocess.run(
            [sys.executable, str(SCRIPT.parent / "classify-rule-anchors.py"), "--baseline", str(tmp_path)],
            capture_output=True,
            text=True,
        )

        assert run.returncode == 0, run.stderr
        assert [(entry["kind"], entry["token"]) for entry in json.loads(run.stdout)] == [("read", "in_library")]

    def test_the_real_harness_reads_no_class_name(self) -> None:
        """Green on this repository: the fifth position is empty too."""
        assert anchors.collect_read_findings() == []


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

        assert guard.escaped_named_selections(fixture) == [(1, f'SEL = "{self.ESCAPED}"')]

    def test_an_escaped_call_is_refused_and_read_by_nothing(self, tmp_path):
        """The measured shape: a selection call hosted in a `"…"` string.

        Both halves are asserted, because the refusal exists exactly because
        the reading fails: `named_selections` finds NOTHING here, and without
        the refusal that silence is the whole defect.
        """
        source = "await pg.evaluate(\"()=>document.querySelector('" + self.ESCAPED + "')\")\n"
        fixture = self._fixture(tmp_path, source)

        assert guard.named_selections(fixture) == []
        assert [line for line, _ in guard.escaped_named_selections(fixture)] == [1]

    def test_the_two_reading_shapes_are_not_refused(self, tmp_path):
        """A single-quoted selector inside a triple-quoted host needs no escape."""
        source = 'await pg.evaluate("""()=>document.querySelector(\'' + self.READABLE + '\')""")\n'
        fixture = self._fixture(tmp_path, source)

        assert guard.escaped_named_selections(fixture) == []
        assert guard.named_selections(fixture) == [(1, "data-part", "probe/part")]

    def test_a_comment_is_refused_by_nothing(self, tmp_path):
        """A comment quoting the escaped shape is prose, not a selection."""
        fixture = self._fixture(tmp_path, f"# once written {self.ESCAPED}\n")

        assert guard.escaped_named_selections(fixture) == []

    def test_the_arm_exits_1_and_names_the_file(self, tmp_path, monkeypatch, capsys):
        """The refusal is the ARM's, not just the helper's.

        `harness_files` is patched on the entry point, which is the module
        whose globals `check_named_values` reads.
        """
        fixture = self._fixture(tmp_path, f'SEL = "{self.ESCAPED}"\n')
        monkeypatch.setattr(guard, "harness_files", lambda: [fixture])
        monkeypatch.setattr(guard, "ROOT", tmp_path)

        assert guard.check_named_values() == 1
        assert "fixture.py:1" in capsys.readouterr().err

    def test_the_harness_carries_no_escaped_selection(self):
        """Green on this repository: every selection is in a readable shape."""
        assert [
            (path, found) for path in guard.harness_files() if (found := guard.escaped_named_selections(path))
        ] == []


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
        the call pass is blind: `named_selections` finds NOTHING here, and
        that silence was the whole defect.
        """
        fixture = self._fixture(tmp_path, f"SEL = '{self.HELD}'\n")

        assert guard.named_selections(fixture) == []
        assert guard.held_named_selections(fixture) == [(1, "data-part", "probe/held")]

    def test_the_arm_refuses_a_held_value_no_source_emits(self, tmp_path, monkeypatch, capsys) -> None:
        """The refusal is the ARM's, not just the helper's.

        `harness_files` is patched on the entry point, which is the module
        whose globals `check_named_values` reads.
        """
        fixture = self._fixture(tmp_path, f"SEL = '{self.HELD}'\n")
        monkeypatch.setattr(guard, "harness_files", lambda: [fixture])
        monkeypatch.setattr(guard, "ROOT", tmp_path)

        assert guard.check_named_values() == 1
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

        assert guard.named_selections(fixture) == [(1, "data-part", "probe/held")]
        assert guard.held_named_selections(fixture) == []

    def test_a_comment_holding_a_selection_is_read_by_nothing(self, tmp_path) -> None:
        """A comment quoting a selector is prose — in Python and in the JS."""
        # One fixture path, so the two shapes are written and read in turn.
        assert guard.held_named_selections(self._fixture(tmp_path, f"# held '{self.HELD}'\n")) == []
        embedded = f'X = """// held \'{self.HELD}\'"""\n'

        assert guard.held_named_selections(self._fixture(tmp_path, embedded)) == []

    def test_a_computed_value_is_skipped_whole(self, tmp_path) -> None:
        """`[data-part="${k}"]` names no literal, and must not be half-read."""
        assert guard.held_named_selections(self._fixture(tmp_path, "SEL = '[data-part=\"${k}\"] .port'\n")) == []

    def test_the_repository_holds_selections_the_call_pass_never_saw(self) -> None:
        """Non-vacuity: this pass reads something on the real harness.

        A pass that finds nothing everywhere is a pass proving nothing, and
        its green would be indistinguishable from an oversight.
        """
        found = {path.name for path in guard.harness_files() if guard.held_named_selections(path)}

        assert len(found) >= 4, found

    def test_the_printed_line_breaks_the_count_down(self, capsys) -> None:
        """A total nobody can break down is a total nobody can tell is short.

        Two breakdowns, because the arm now reads more than one attribute:
        how many of the selections were HELD, and how many belong to each
        naming attribute. A `data-tone` arm that silently read nothing
        would leave the total unmoved.
        """
        assert guard.check_named_values() == 0
        line = next(
            text for text in capsys.readouterr().out.splitlines() if "naming-attribute selection(s) checked" in text
        )

        assert "of them held)" in line
        for attribute in guard.NAMING_ATTRIBUTES:
            assert f"{attribute} against" in line


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
        assert guard.emitted_named_values(self._source(tmp_path, self.DATASET))["data-part"] == {"probe/imperative"}

    def test_a_set_attribute_call_emits(self, tmp_path) -> None:
        """`el.setAttribute("data-part", "…")` is the same emission, spelled out."""
        emitted = guard.emitted_named_values(self._source(tmp_path, self.SET_ATTRIBUTE))

        assert emitted["data-part"] == {"probe/imperative"}

    def test_a_computed_imperative_value_is_skipped_whole(self, tmp_path) -> None:
        """A value the script computes names no literal to compare against."""
        computed = 'el.dataset.part = kind;\nel.setAttribute("data-part", `part/${k}`);\n'

        assert guard.emitted_named_values(self._source(tmp_path, computed))["data-part"] == set()

    def test_a_comment_holding_an_assignment_emits_nothing(self, tmp_path) -> None:
        """A comment describing the assignment is prose, and emits nothing."""
        assert guard.emitted_named_values(self._source(tmp_path, "// " + self.DATASET))["data-part"] == set()

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

        assert guard.check_named_values() == 0, capsys.readouterr().err

    def test_the_repository_emits_a_part_imperatively(self) -> None:
        """Non-vacuity: this reading finds something on the real sources.

        A pass that reads nothing anywhere is a pass whose green says
        nothing, and the engine builds the episode popover in script.
        """
        engine = guard.SOURCES / "engine" / "legacy.js"

        assert "episode/popover" in guard.emitted_named_values(engine)["data-part"]


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


class TestInterpolatedAndConcatenatedSelectors:
    """The held pass's own blind spot: two shapes NEITHER reader could see.

    The held pass qualified a candidate by a SELECTOR ALPHABET, and a
    selector the harness builds at run time does not spell itself in it:

      * an f-string carries `{…}` interpolations — `f'#sheet
        [data-part="sheet/action"][data-setsort="{key}"]'` — and the braces
        are outside the alphabet, so the whole literal was dropped;
      * a selector CONCATENATED onto a variable starts with the descendant
        combinator — `querySelector(s + ' .fback')` — and the candidate
        pattern demanded `.`, `#` or `[` immediately after the quote.

    Both are live selections, and both were read by nothing: not by the
    anchor arm, not by the part arm, not by the independent classifier. A
    floor of zero over a corpus a reader cannot see is not a zero, which is
    why these are read before the floor is declared.

    THE INTERPOLATION IS AN OPAQUE TOKEN. It does not end the selector, and
    it does not contribute a name either: `.{k}card` yields NO class token,
    because the class is computed and half-reading a name is worse than not
    reading it.

    AND THE WIDENING IS A RULE, NOT A WAIVER. Two refusals keep prose and
    stylesheet text out of a pass that now tolerates braces: an
    interpolation is a BALANCED `{…}` span, and a selector's only `=` sits
    inside an attribute block.
    """

    # A class anchor inside an f-string selector.
    INTERPOLATED = "SEL = f'#view .swipe[data-index=\"{i}\"]'\n"
    # A class anchor after a leading space, concatenated onto a variable.
    CONCATENATED = "await pg.evaluate(\"(s)=>document.querySelector(s + ' .fback')\")\n"

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

    def test_an_interpolated_selector_is_read(self, tmp_path) -> None:
        """The braces are opaque, and the selector around them is read."""
        found = guard.held_occurrences(self._fixture(tmp_path, self.INTERPOLATED), {"swipe"})

        assert found == [(1, '#view .swipe[data-index="{i}"]')]
        assert guard.class_tokens(found[0][1]) == [".swipe"]

    def test_a_concatenated_selector_is_read(self, tmp_path) -> None:
        """A leading space is the descendant combinator, not a disqualifier."""
        assert guard.held_occurrences(self._fixture(tmp_path, self.CONCATENATED), {"fback"}) == [(1, ".fback")]

    def test_a_computed_class_name_yields_no_token(self, tmp_path) -> None:
        """`.{k}card` names no class at rest, and must not be half-read."""
        assert guard.class_tokens("#view .{k}card") == []

    def test_a_stylesheet_fragment_is_not_a_selector(self, tmp_path) -> None:
        """`.cov{-webkit-line-clamp:` opens a brace it never closes."""
        assert guard.held_occurrences(self._fixture(tmp_path, "CSS = '.cov{-webkit-line-clamp:'\n"), {"cov"}) == []

    def test_a_rule_opening_is_not_a_selector(self, tmp_path) -> None:
        """`.splashbar {` is a stylesheet rule opening, not a selection."""
        assert guard.held_occurrences(self._fixture(tmp_path, "CSS = '.splashbar {'\n"), {"splashbar"}) == []

    def test_a_journal_label_is_not_a_selector(self, tmp_path) -> None:
        """`#splash.hidden = {x}` balances its braces and is still prose.

        A selector's only `=` lives inside an attribute block; a bare one
        says the string is a message about an element, not a selection of
        it.
        """
        assert guard.held_occurrences(self._fixture(tmp_path, "M = '#splash.hidden = {x}'\n"), {"hidden"}) == []

    def test_the_arm_refuses_both_and_names_them(self, tmp_path, monkeypatch, capsys) -> None:
        """The refusal is the ARM's: exactly two violations, both named."""
        fixture = self._fixture(tmp_path, self.INTERPOLATED + self.CONCATENATED)
        monkeypatch.setattr(anchors, "harness_files", lambda: [fixture])
        monkeypatch.setattr(anchors, "ROOT", tmp_path)

        assert guard.check_anchor_debt() == 1
        err = capsys.readouterr().err

        assert "fixture.py:1" in err and ".swipe" in err
        assert "fixture.py:2" in err and ".fback" in err
        assert "2 anchor occurrence(s)" in err

    def test_the_classifier_reads_both_shapes_too(self, tmp_path) -> None:
        """The second reader agrees, or one of the two is wrong.

        The third line is a literal-argument call carrying no class token:
        the classifier refuses a root with no selection call at all, and
        that refusal is not what this test is about.
        """
        self._fixture(tmp_path, self.INTERPOLATED + self.CONCATENATED + "querySelector('#view')\n")
        run = subprocess.run(
            [sys.executable, str(SCRIPT.parent / "classify-rule-anchors.py"), "--baseline", str(tmp_path)],
            capture_output=True,
            text=True,
        )

        assert run.returncode == 0, run.stderr
        assert [entry["token"] for entry in json.loads(run.stdout)] == [".swipe", ".fback"]


class TestTheDerivedStateCorpus:
    """ARM 4's corpus is a QUESTION about the harness, not a tuple.

    It was seven names, and the wave that wrote it coined twelve boolean
    states. The five it did not name — `data-edited`, `data-mono`,
    `data-solid`, `data-read-only`, `data-skeleton` — were selected by
    presence from five rules and read by the arm never, and nothing could
    tell: the writes it skipped were in neither the numerator nor the
    denominator of the count it printed.
    """

    def _harness(self, tmp_path, monkeypatch, source):
        """Points the derivation at one fixture rule file.

        Args:
            tmp_path: The pytest fixture.
            monkeypatch: The pytest fixture.
            source: The fixture rule file's text.

        Returns:
            Nothing; the guard's `harness_files` is patched in place.
        """
        fixture = tmp_path / "fixture.py"
        fixture.write_text(source, encoding="utf-8")
        monkeypatch.setattr(states, "harness_files", lambda: [fixture])

    def test_a_presence_selection_declares_a_state(self, tmp_path, monkeypatch) -> None:
        """`[data-fresh]` is the whole declaration."""
        self._harness(tmp_path, monkeypatch, "S = '[data-fresh]'\n")

        assert "fresh" in states.boolean_state_attributes()

    def test_has_attribute_declares_one_too(self, tmp_path, monkeypatch) -> None:
        """The same question, asked in JavaScript."""
        self._harness(tmp_path, monkeypatch, 'J = """()=>x.hasAttribute(\'data-fresh\')"""\n')

        assert "fresh" in states.boolean_state_attributes()

    def test_an_attribute_whose_value_is_compared_is_not_a_state(self, tmp_path, monkeypatch) -> None:
        """`[data-key^="mediaSheet:"]` carries data; presence is a payload."""
        self._harness(tmp_path, monkeypatch, "S = '[data-key]'\nT = '[data-key^=\"mediaSheet:\"]'\n")

        assert "key" not in states.boolean_state_attributes()

    def test_an_attribute_whose_value_is_read_is_not_a_state(self, tmp_path, monkeypatch) -> None:
        """`badge.dataset.tone` reads a value; so does `.dataset.noPoster`."""
        self._harness(
            tmp_path,
            monkeypatch,
            'S = \'[data-tone]\'\nU = \'[data-no-poster]\'\nJ = """()=>[b.dataset.tone, b.dataset.noPoster]"""\n',
        )
        derived = states.boolean_state_attributes()

        assert "tone" not in derived and "no-poster" not in derived

    def test_the_five_the_tuple_missed_are_in_the_corpus_now(self) -> None:
        """The regression, on the real trees."""
        derived = states.boolean_state_attributes()

        assert {"edited", "mono", "solid", "read-only", "skeleton"} <= derived

    def test_an_empty_derivation_is_refused_rather_than_reported_green(self, tmp_path, monkeypatch, capsys) -> None:
        """A corpus that comes back empty is a derivation that broke."""
        self._harness(tmp_path, monkeypatch, "# nothing selects anything\n")

        assert guard.check_state_attributes() == 1
        assert "the derivation is broken" in capsys.readouterr().err

    def test_the_printed_line_names_what_it_derived(self, capsys) -> None:
        """A count nobody can break down is a count nobody reads."""
        assert guard.check_state_attributes() == 0
        line = next(text for text in capsys.readouterr().out.splitlines() if "state attribute write(s) checked" in text)

        assert "data-edited" in line and "DERIVED" in line


class TestTheNamingAttributes:
    """ARM 3 holds every attribute whose values are NAMES, not `data-part` alone.

    `data-tone` was coined by one wave, selected WITH A VALUE at ten harness
    call sites, and named in neither this arm's reader nor the French
    guard's — so a renamed tone left ten rules selecting nothing with no
    static refusal anywhere.
    """

    def test_the_list_is_declared_once_for_both_guards(self) -> None:
        """Two questions, one set — a second copy is a second thing to move."""
        values = load_values()

        assert set(guard.NAMING_ATTRIBUTES) == set(values.NAMING_ATTRIBUTES)

    def test_a_tone_selection_is_read(self, tmp_path, monkeypatch) -> None:
        """The selection side sees an attribute that is not `data-part`."""
        fixture = tmp_path / "fixture.py"
        fixture.write_text("""S = '[data-part="dialog/button"][data-tone="danger"]'\n""", encoding="utf-8")

        assert guard.held_named_selections(fixture) == [(1, "data-part", "dialog/button"), (1, "data-tone", "danger")]

    def test_the_real_harness_selects_tones_and_every_one_is_emitted(self) -> None:
        """Non-vacuity, then the contract."""
        selected = [
            entry
            for path in guard.harness_files()
            for entry in guard.named_selections(path) + guard.held_named_selections(path)
            if entry[1] == "data-tone"
        ]

        assert len(selected) >= 8, selected
        assert guard.check_named_values() == 0


class TestHarnessParses:
    r"""The precondition: a rule file Python cannot read is a violation.

    Sub-phase 4.1's hole, and it is the defect class this whole guard exists
    to end. A rewrite substituted `[data-part="suggestion/wrap"]` into
    selectors hosted in single-line DOUBLE-quoted Python strings: the raw `"`
    ended the literal, and `inter.py` and `mouse.py` STOPPED PARSING. Every
    instrument then read them and reported no violation — this guard exited
    0, the baseline regeneration (a mode since deleted) wrote happily,
    `classify-rule-anchors.py` counted.
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

        assert guard.escaped_named_selections(fixture) == []
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
        # EVERY ARM `main` CALLS, derived from `main` itself rather than listed
        # here. The list was written when there were four and stayed at four
        # when arms 5 and 6 landed, so those two ran FOR REAL inside a test that
        # believes it mocked everything — slow, and silent about whether `main`
        # reaches them at all. A hand-kept copy of a call list is the thing this
        # hold exists to check.
        source = (guard.__file__ and Path(guard.__file__).read_text(encoding="utf-8")) or ""
        body = source[source.index("\ndef main(") :]
        arms = [name for name in re.findall(r"if (check_\w+)\(\)", body) if name != "check_harness_parses"]
        assert len(arms) >= 6, f"main calls {len(arms)} arms; the guard has six"

        ran = []
        monkeypatch.setattr(guard, "check_harness_parses", lambda: 1)
        for arm in arms:
            monkeypatch.setattr(guard, arm, lambda name=arm: ran.append(name) or 0)

        assert guard.main([]) == 1
        assert ran == arms

    def test_every_harness_file_parses(self):
        """Green on this repository: every rule file is readable Python.

        THE COUNT IS NOT WRITTEN HERE. It said 52 while the tree held 72 — a
        figure typed once beside the thing it describes, which is the defect
        `check-live-relay.py`'s stale-figure arm exists for. The assertion below
        reads the tree.
        """
        assert guard.parse_failures(guard.harness_files()) == []
