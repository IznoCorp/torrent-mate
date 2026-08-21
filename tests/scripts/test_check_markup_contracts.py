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

    def test_main_does_not_read_sys_argv_when_given_an_argv(
            self, monkeypatch) -> None:
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
