"""Unit tests for the ``prime`` command in the acquisition runner.

(acq-states phase 6 — the amorce of a freshly followed series).

Targets the runner seams:

- ``_build_argv('prime', id)`` — yields the three-step sequence (detect →
  search → grab), each step scoped to the single follow.
- ``_read_mandatory_env`` — accepts ``PERSONALSCRAPER_ACQ_COMMAND=prime`` as a
  valid command and requires ``PERSONALSCRAPER_GRAB_FOLLOWED_ID``.
- ``main()`` — chains the steps in ONE run row / ONE ring buffer, announces
  each with a ``--- <step> ---`` separator, and stops at the first non-zero rc.
"""

from __future__ import annotations

import os
import signal
import sys
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from personalscraper.web.acquisition import runner as runner_mod
from personalscraper.web.acquisition.runner import _build_argv, _read_mandatory_env


def _clear_runner_env() -> None:
    """Remove the acquisition-runner env vars between tests."""
    for k in (
        "PERSONALSCRAPER_RUN_UID",
        "PERSONALSCRAPER_ACQ_COMMAND",
        "PERSONALSCRAPER_GRAB_FOLLOWED_ID",
    ):
        os.environ.pop(k, None)


# ---------------------------------------------------------------------------
# Tests — _build_argv for the prime command
# ---------------------------------------------------------------------------


class TestBuildArgvPrime:
    """``_build_argv('prime', id)`` yields the three-step priming sequence."""

    def test_three_step_sequence(self) -> None:
        """The prime argv is three CLIs: detect → search → grab.

        Each step targets ONLY the followed series (never a global pass).
        The steps are returned as a list of argv lists so the runner can
        iterate and stop at the first non-zero exit code.
        """
        result = _build_argv("prime", 42)

        # Must return a list of three argvs, not a flat list.
        assert isinstance(result, list), f"Expected list, got {type(result).__name__}"
        assert len(result) == 3, f"Expected 3 steps, got {len(result)}"

        argv0: list[str] = result[0]
        argv1: list[str] = result[1]
        argv2: list[str] = result[2]

        # Step 1: personalscraper follow detect --series {id}
        assert argv0[:4] == [sys.executable, "-m", "personalscraper", "follow"], (
            f"Step 1 prefix mismatch: {argv0[:4]!r}"
        )
        assert "detect" in argv0, f"Step 1 missing 'detect': {argv0}"
        assert "--series" in argv0, f"Step 1 missing '--series': {argv0}"
        assert any(str(42) in a for a in argv0), f"Step 1 missing '42': {argv0}"

        # Step 2: personalscraper search --followed-id {id}
        assert argv1[:4] == [sys.executable, "-m", "personalscraper", "search"], (
            f"Step 2 prefix mismatch: {argv1[:4]!r}"
        )
        assert "--followed-id" in argv1, f"Step 2 missing '--followed-id': {argv1}"
        assert "42" in argv1, f"Step 2 missing '42': {argv1}"

        # Step 3: personalscraper grab --followed-id {id}
        assert argv2[:4] == [sys.executable, "-m", "personalscraper", "grab"], f"Step 3 prefix mismatch: {argv2[:4]!r}"
        assert "--followed-id" in argv2, f"Step 3 missing '--followed-id': {argv2}"
        assert "42" in argv2, f"Step 3 missing '42': {argv2}"

    def test_every_step_is_scoped_to_the_single_follow(self) -> None:
        """No priming step may run a library-wide pass.

        Adding one series must never re-run the acquisition of the whole
        library (plan §6 « Périmètre du run d'amorce »): every step of the
        sequence carries the scoping flag for THIS follow.
        """
        steps = _build_argv("prime", 42)

        for argv in steps:
            assert "--series" in argv or "--followed-id" in argv, f"Unscoped priming step (global pass): {argv}"
            assert "42" in argv, f"Step not scoped to follow 42: {argv}"

    def test_grab_and_detect_still_yield_one_step(self) -> None:
        """The single-command runs keep their argv — one step, unchanged."""
        grab_steps = _build_argv("grab", 42)
        assert len(grab_steps) == 1, f"grab must be a single step, got {len(grab_steps)}"
        assert grab_steps[0] == [sys.executable, "-m", "personalscraper", "grab", "--followed-id", "42"]

        detect_steps = _build_argv("detect", None)
        assert len(detect_steps) == 1, f"detect must be a single step, got {len(detect_steps)}"
        assert detect_steps[0] == [sys.executable, "-m", "personalscraper", "follow", "detect"]


# ---------------------------------------------------------------------------
# Tests — env contract for the prime command
# ---------------------------------------------------------------------------


class TestEnvContractPrime:
    """The env contract accepts ``prime`` as a valid command."""

    def test_prime_is_valid_command(self) -> None:
        """_read_mandatory_env accepts PERSONALSCRAPER_ACQ_COMMAND=prime."""
        _clear_runner_env()
        os.environ["PERSONALSCRAPER_RUN_UID"] = "test-uid-prime-1"
        os.environ["PERSONALSCRAPER_ACQ_COMMAND"] = "prime"
        os.environ["PERSONALSCRAPER_GRAB_FOLLOWED_ID"] = "42"
        try:
            run_uid, command, followed_id = _read_mandatory_env()
            assert run_uid == "test-uid-prime-1"
            assert command == "prime", f"Expected 'prime', got {command!r}"
            assert followed_id == 42, f"Expected 42, got {followed_id!r}"
        finally:
            _clear_runner_env()

    def test_unknown_command_still_exits_2(self) -> None:
        """An unknown PERSONALSCRAPER_ACQ_COMMAND is still rejected (exit 2)."""
        _clear_runner_env()
        os.environ["PERSONALSCRAPER_RUN_UID"] = "test-uid-prime-2"
        os.environ["PERSONALSCRAPER_ACQ_COMMAND"] = "primer"
        os.environ["PERSONALSCRAPER_GRAB_FOLLOWED_ID"] = "42"
        try:
            with pytest.raises(SystemExit) as exc_info:
                _read_mandatory_env()
            assert exc_info.value.code == 2, "An unknown acquisition command must exit 2"
        finally:
            _clear_runner_env()

    def test_prime_requires_followed_id(self) -> None:
        """A prime run without PERSONALSCRAPER_GRAB_FOLLOWED_ID exits 2.

        The followed_id is mandatory for prime (same as grab): three CLIs
        all need it. This test will fail UNTIL the env contract is updated
        in 6.2 to check for 'prime' alongside 'grab'.
        """
        _clear_runner_env()
        os.environ["PERSONALSCRAPER_RUN_UID"] = "test-uid-prime-3"
        os.environ["PERSONALSCRAPER_ACQ_COMMAND"] = "prime"
        # Deliberately omit PERSONALSCRAPER_GRAB_FOLLOWED_ID.
        try:
            with pytest.raises(SystemExit) as exc_info:
                _read_mandatory_env()
            assert exc_info.value.code == 2, (
                "Missing PERSONALSCRAPER_GRAB_FOLLOWED_ID must exit 2 for the prime command"
            )
        finally:
            _clear_runner_env()


# ---------------------------------------------------------------------------
# Tests — main() chains the three steps in ONE run row
# ---------------------------------------------------------------------------


class _FakeProc:
    """Minimal ``Popen`` stand-in: an iterable stdout + a fixed return code."""

    def __init__(self, lines: list[str], rc: int) -> None:
        """Store the canned output and exit code.

        Args:
            lines: The lines the fake process writes to stdout.
            rc: The exit code :meth:`wait` returns.
        """
        self.stdout: Iterator[str] = iter(lines)
        self._rc = rc

    def wait(self) -> int:
        """Return the canned exit code."""
        return self._rc


class _FakeWriter:
    """Recording stand-in for :class:`PipelineRunWriter`."""

    calls: list[tuple[str, Any]] = []

    def __init__(self, db_path: Path) -> None:
        """Record nothing but the path (the fake writes no DB).

        Args:
            db_path: The library.db path the runner passed.
        """
        self.db_path = db_path

    def insert(self, run_uid: str, **kwargs: Any) -> None:
        """Record the row reservation."""
        _FakeWriter.calls.append(("insert", {"run_uid": run_uid, **kwargs}))

    def update_pid(self, run_uid: str, pid: int) -> None:
        """Record the pid claim."""
        _FakeWriter.calls.append(("update_pid", pid))

    def finalize(self, run_uid: str, outcome: str, **kwargs: Any) -> None:
        """Record the finalization."""
        _FakeWriter.calls.append(("finalize", {"outcome": outcome, **kwargs}))


@pytest.fixture
def primed_runner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[list[list[str]]]:
    """Neutralize the runner's I/O and yield the list of spawned argvs.

    Patches config loading, the run-row writer and Redis so ``main()`` can be
    exercised in-process; each test then installs its own ``subprocess.Popen``
    fake through :func:`_install_procs`.
    """
    _FakeWriter.calls = []
    spawned: list[list[str]] = []
    config = SimpleNamespace(
        indexer=SimpleNamespace(db_path=tmp_path / "library.db"),
        web=SimpleNamespace(enabled=False, stream_key="tm:test", stream_maxlen=100),
    )
    monkeypatch.setattr(runner_mod, "load_config", lambda: config)
    monkeypatch.setattr(runner_mod, "PipelineRunWriter", _FakeWriter)
    monkeypatch.setattr(runner_mod, "_get_redis", lambda _cfg: None)

    original_sigterm = signal.getsignal(signal.SIGTERM)
    _clear_runner_env()
    try:
        yield spawned
    finally:
        _clear_runner_env()
        signal.signal(signal.SIGTERM, original_sigterm)


def _install_procs(monkeypatch: pytest.MonkeyPatch, spawned: list[list[str]], rcs: list[int]) -> None:
    """Make ``Popen`` return one :class:`_FakeProc` per *rcs* entry, in order.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        spawned: List the fake records each spawned argv into.
        rcs: The exit code of each successive step.
    """
    queue = list(rcs)

    def _fake_popen(argv: list[str], **_kwargs: Any) -> _FakeProc:
        spawned.append(argv)
        rc = queue.pop(0) if queue else 0
        return _FakeProc([f"line from {argv[3]}\n"], rc)

    monkeypatch.setattr(runner_mod.subprocess, "Popen", _fake_popen)


class TestPrimeChaining:
    """``main()`` runs the three prime steps in ONE run row / ring buffer."""

    def test_three_steps_run_in_one_row_with_separators(
        self, monkeypatch: pytest.MonkeyPatch, primed_runner: list[list[str]]
    ) -> None:
        """All three steps run, each announced by its separator line."""
        _install_procs(monkeypatch, primed_runner, [0, 0, 0])
        os.environ["PERSONALSCRAPER_RUN_UID"] = "uid-chain-ok"
        os.environ["PERSONALSCRAPER_ACQ_COMMAND"] = "prime"
        os.environ["PERSONALSCRAPER_GRAB_FOLLOWED_ID"] = "42"

        with pytest.raises(SystemExit) as exc_info:
            runner_mod.main()

        assert exc_info.value.code == 0
        assert len(primed_runner) == 3, f"Expected 3 spawned steps, got {primed_runner}"

        # ONE row: a single insert (command='prime') and a single finalize.
        inserts = [c for c in _FakeWriter.calls if c[0] == "insert"]
        finals = [c for c in _FakeWriter.calls if c[0] == "finalize"]
        assert len(inserts) == 1, f"Expected 1 run row, got {len(inserts)}"
        assert inserts[0][1]["command"] == "prime"
        assert inserts[0][1]["options_json"] == '{"followed_id": 42}'
        assert len(finals) == 1, f"Expected 1 finalize, got {len(finals)}"
        assert finals[0][1]["outcome"] == "success"

        # ONE buffer: the three steps + their separators are all in the tail.
        tail: str = finals[0][1]["output_tail"]
        assert "--- follow detect --series 42 ---" in tail, tail
        assert "--- search --followed-id 42 ---" in tail, tail
        assert "--- grab --followed-id 42 ---" in tail, tail

    def test_chain_stops_at_the_first_failing_step(
        self, monkeypatch: pytest.MonkeyPatch, primed_runner: list[list[str]]
    ) -> None:
        """A non-zero rc stops the chain — outcome error, partial output kept."""
        _install_procs(monkeypatch, primed_runner, [0, 3, 0])
        os.environ["PERSONALSCRAPER_RUN_UID"] = "uid-chain-fail"
        os.environ["PERSONALSCRAPER_ACQ_COMMAND"] = "prime"
        os.environ["PERSONALSCRAPER_GRAB_FOLLOWED_ID"] = "7"

        with pytest.raises(SystemExit) as exc_info:
            runner_mod.main()

        assert exc_info.value.code == 3
        assert len(primed_runner) == 2, f"The grab step must NOT run after a failure: {primed_runner}"

        finals = [c for c in _FakeWriter.calls if c[0] == "finalize"]
        assert len(finals) == 1
        assert finals[0][1]["outcome"] == "error"
        # The partial output shows WHERE it stopped (the search separator is
        # the last one, the grab separator never emitted).
        tail: str = finals[0][1]["output_tail"]
        assert "--- search --followed-id 7 ---" in tail, tail
        assert "--- grab --followed-id 7 ---" not in tail, tail

    def test_single_step_grab_has_no_separator(
        self, monkeypatch: pytest.MonkeyPatch, primed_runner: list[list[str]]
    ) -> None:
        """A one-step run keeps its plain output — no separator noise."""
        _install_procs(monkeypatch, primed_runner, [0])
        os.environ["PERSONALSCRAPER_RUN_UID"] = "uid-single"
        os.environ["PERSONALSCRAPER_ACQ_COMMAND"] = "grab"
        os.environ["PERSONALSCRAPER_GRAB_FOLLOWED_ID"] = "5"

        with pytest.raises(SystemExit) as exc_info:
            runner_mod.main()

        assert exc_info.value.code == 0
        assert len(primed_runner) == 1
        finals = [c for c in _FakeWriter.calls if c[0] == "finalize"]
        assert "---" not in finals[0][1]["output_tail"]


class TestOptionsJsonSingleAuthority:
    """Each ``options_json`` byte format has exactly ONE construction site (m22).

    The 409 guard, the card reader and the runner all compare the scope string
    by EXACT EQUALITY, so a second site typing the same literal is a latent
    « the guard silently never matches » bug. Both formats now live in
    ``web/acquisition/runner.py`` and every other module imports them.
    """

    def test_runner_options_json_delegates_to_the_shared_builders(self) -> None:
        """``_options_json`` re-types neither format — it calls the builders."""
        assert runner_mod._options_json("prime", 7) == runner_mod.prime_options_json(7)
        assert runner_mod._options_json("grab", 7) == runner_mod.grab_options_json(7)
        assert runner_mod._options_json("detect", None) == "{}"

    def test_trigger_route_uses_the_shared_grab_builder(self) -> None:
        """The per-follow action table points at the shared builder object itself."""
        from personalscraper.web.routes import acquisition_triggers

        assert acquisition_triggers._FOLLOWED_ACTIONS["grab"][1] is runner_mod.grab_options_json
        assert acquisition_triggers._FOLLOWED_ACTIONS["prime"][1] is runner_mod.prime_options_json

    def test_the_two_formats_stay_distinct_scopes(self) -> None:
        """Prime and grab are deliberately DIFFERENT strings — distinct actions.

        A running grab must never refuse a prime, nor the reverse; the guard
        tells them apart by ``command`` AND by these bytes. Pinned because the
        already-deployed rows carry exactly these.
        """
        assert runner_mod.prime_options_json(42) == '{"followed_id": 42}'
        assert runner_mod.grab_options_json(42) == '{"followed_id":42}'

    def test_only_one_construction_site_per_format(self) -> None:
        """Grep-proof: no module re-types an ``options_json`` literal.

        Scans the whole package rather than trusting review discipline — this
        is exactly the drift that produced two hand-typed copies of the grab
        format in the first place.
        """
        from pathlib import Path as _Path

        runner_path = _Path(runner_mod.__file__).resolve()
        package_root = runner_path.parents[2]
        offenders = sorted(
            str(py)
            for py in package_root.rglob("*.py")
            if py.resolve() != runner_path and 'json.dumps({"followed_id"' in py.read_text(encoding="utf-8")
        )
        assert offenders == [], f"options_json must be built in runner.py alone; also built in {offenders}"
