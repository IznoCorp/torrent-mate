"""Tests for the single pipeline-run trigger authority (spawn_pipeline_run).

Guards the invariant that ``pipeline.lock`` is the sole gate: a run is spawned only
when the lock is free, and a held lock defers (no second trigger mechanism). Backs
the §4 continuation (the decisions runner reuses this exact authority after a
scrape-resolve so the media finishes its pipeline through to dispatch).
"""

from pathlib import Path
from unittest.mock import patch

from personalscraper.web.pipeline_trigger import spawn_pipeline_run


def test_spawn_when_lock_free_returns_run_uid(tmp_path: Path) -> None:
    """A free lock spawns ``personalscraper run`` and returns its run_uid."""
    with (
        patch("personalscraper.web.pipeline_trigger.is_lock_held", return_value=False),
        patch("personalscraper.web.pipeline_trigger.subprocess.Popen") as popen,
    ):
        run_uid = spawn_pipeline_run(tmp_path, trigger_reason="scrape-resolve")

    assert run_uid is not None
    popen.assert_called_once()
    argv = popen.call_args.args[0]
    assert argv[1:] == [
        "-m",
        "personalscraper",
        "run",
        "--no-console",
        "--trigger-reason=scrape-resolve",
    ]
    # The run_uid is propagated to the child so it adopts the reserved run row.
    assert popen.call_args.kwargs["env"]["PERSONALSCRAPER_RUN_UID"] == run_uid


def test_no_spawn_when_lock_held_returns_none(tmp_path: Path) -> None:
    """A held lock defers: no run spawned, ``None`` returned (single authority)."""
    with (
        patch("personalscraper.web.pipeline_trigger.is_lock_held", return_value=True),
        patch("personalscraper.web.pipeline_trigger.subprocess.Popen") as popen,
    ):
        run_uid = spawn_pipeline_run(tmp_path, trigger_reason="scrape-resolve")

    assert run_uid is None
    popen.assert_not_called()


def test_dry_run_appends_flag(tmp_path: Path) -> None:
    """``dry_run=True`` appends ``--dry-run`` to the spawned argv."""
    with (
        patch("personalscraper.web.pipeline_trigger.is_lock_held", return_value=False),
        patch("personalscraper.web.pipeline_trigger.subprocess.Popen") as popen,
    ):
        spawn_pipeline_run(tmp_path, trigger_reason="web", dry_run=True)

    assert "--dry-run" in popen.call_args.args[0]


def test_continuation_trigger_reason_is_a_valid_run_trigger() -> None:
    """The §4 continuation trigger MUST be accepted by ``run --trigger-reason``.

    Guard-test #3 (product-intent §méthode): the other tests here mock ``Popen``,
    so they assert the argv is *built* with ``scrape-resolve`` but never that the
    spawned ``run`` would *accept* it. It does not: before the fix,
    ``--trigger-reason=scrape-resolve`` failed argv validation, the continuation
    run crashed, and the resolved media stayed in staging — never dispatched (the
    §4 dénaturation, caught only by a real prod resolve). This wires both ends of
    the contract so they cannot drift again.
    """
    from personalscraper.commands.pipeline import _validate_trigger_reason
    from personalscraper.web.pipeline_trigger import RESOLVE_CONTINUATION_TRIGGER

    assert _validate_trigger_reason(RESOLVE_CONTINUATION_TRIGGER) == RESOLVE_CONTINUATION_TRIGGER
