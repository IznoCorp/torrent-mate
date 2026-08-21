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
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-markup-contracts.py"


def load():
    """Imports the guard, despite its hyphenated filename."""
    spec = importlib.util.spec_from_file_location("check_markup_contracts", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load()


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
        monkeypatch.setattr(guard, "BASELINE", baseline)
        # The success message renders the baseline path relative to ROOT;
        # the real baseline lives under it, the test's temp one does not.
        monkeypatch.setattr(guard, "ROOT", tmp_path)
        done = subprocess.CompletedProcess([], 0, json.dumps(fresh), "")
        monkeypatch.setattr(guard.subprocess, "run", lambda *a, **k: done)
        findings = [
            (guard.entry_identity(e), e.get("selector", e.get("class")), f"{e['file']}:{e['line']}") for e in fresh
        ]
        monkeypatch.setattr(guard, "collect_anchor_findings", lambda: findings)
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
