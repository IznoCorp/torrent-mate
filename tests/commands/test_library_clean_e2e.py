"""E2E tests for ``personalscraper library-clean`` — CLI-level harness.

Validates dry-run-by-default invariant: the default invocation must NEVER
delete anything from the filesystem.  Covers .actors/ removal, empty dirs,
junk files, --only / --disk filters, and mutual-exclusion of --apply/--dry-run.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from unittest.mock import patch

from tests.commands._e2e_helpers import (
    assert_no_python_traceback,
    capture_event_bus,
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


def _ansi_clean(output: str) -> str:
    """Strip Rich ANSI escape codes for plain-text assertions."""
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def _setup_movie_with_actors(tmp_path, test_config):
    """Create drive_a/cat_movies/TestMovie/.actors/dummy.txt and return the actors path."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    drive_a = tmp_path / "drive_a"
    movie_dir = drive_a / "cat_movies" / "TestMovie (2020)"
    actors_dir = movie_dir / ".actors"
    actors_dir.mkdir(parents=True)
    (actors_dir / "dummy.txt").write_text("actor thumb content")
    (movie_dir / "test.mkv").write_bytes(b"fake video content")

    return cfg, actors_dir, db_path


# ── 1. Smoke ─────────────────────────────────────────────────────────────────────


def test_clean_help_exits_zero(test_config) -> None:
    """``library-clean --help`` exits 0."""
    result = run_cli(["library-clean", "--help"])
    assert result.exit_code == 0, result.output
    assert "library-clean" in result.output


# ── 2. Empty storage ────────────────────────────────────────────────────────────


def test_clean_empty_storage_zero_actions(tmp_path, test_config) -> None:
    """No media directories exist → zero deletions reported."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    # Drive directories exist but category subdirs do not.
    (tmp_path / "drive_a").mkdir(exist_ok=True)
    (tmp_path / "drive_b").mkdir(exist_ok=True)
    (tmp_path / "drive_c").mkdir(exist_ok=True)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean"])

    assert result.exit_code == 0, result.output
    clean = _ansi_clean(result.output)
    assert "Would delete 0 items" in clean, f"Expected 0 items deleted, got: {clean}"


# ── 3. Dry-run safety (CRITICAL) ────────────────────────────────────────────────


def test_clean_dry_run_no_writes_actors_dir(tmp_path, test_config) -> None:
    """Default invocation (no ``--apply``) MUST NOT delete the .actors/ directory."""
    cfg, actors_dir, _ = _setup_movie_with_actors(tmp_path, test_config)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean"])

    assert result.exit_code == 0, result.output
    clean = _ansi_clean(result.output)
    assert "DRY-RUN" in clean, f"Expected DRY-RUN marker, got: {clean}"
    assert "Would delete" in clean, f"Expected 'Would delete', got: {clean}"

    # The .actors/ dir MUST still exist.
    assert actors_dir.exists(), f"DRY-RUN leaked deletion: {actors_dir} no longer exists"
    assert (actors_dir / "dummy.txt").exists(), "DRY-RUN leaked deletion of file inside .actors/"


# ── 4. Apply mode ───────────────────────────────────────────────────────────────


def test_clean_apply_removes_actors_dir(tmp_path, test_config, monkeypatch) -> None:
    """``--apply`` deletes the .actors/ directory."""
    cfg, actors_dir, _ = _setup_movie_with_actors(tmp_path, test_config)

    # Pin contract: clean is a filesystem-only operation that does NOT emit
    # its own domain events.  However, the command now uses per_step_boundary
    # to build the fail-open delete authority (DESIGN §7.4), which constructs
    # the ProviderRegistry and emits exactly one RegistryBootValidated event.
    # This is a boundary event — not a cleanup event.
    captured = capture_event_bus(monkeypatch)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean", "--apply"])

    assert result.exit_code == 0, result.output
    clean = _ansi_clean(result.output)
    assert "Deleted:" in clean, result.output

    # The .actors/ dir MUST be gone.
    assert not actors_dir.exists(), f"--apply did not delete .actors/: still exists at {actors_dir}"

    assert len(captured) == 1, f"Expected 1 boundary event, got {len(captured)}: {[type(e).__name__ for e in captured]}"
    assert captured[0].__class__.__name__ == "RegistryBootValidated", (
        f"Expected RegistryBootValidated, got {captured[0].__class__.__name__}"
    )


# ── 5. --only filter ────────────────────────────────────────────────────────────


def test_clean_only_filter_restricts_scope(tmp_path, test_config) -> None:
    """``--only actors`` removes .actors/ but NOT empty dirs or junk files."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    drive_a = tmp_path / "drive_a"
    movie_dir = drive_a / "cat_movies" / "TestMovie (2020)"
    actors_dir = movie_dir / ".actors"
    actors_dir.mkdir(parents=True)
    (actors_dir / "thumb.jpg").write_text("thumb")
    (movie_dir / "test.mkv").write_bytes(b"fake video")

    # Also create an empty dir and a junk file in the same movie dir.
    empty_subdir = movie_dir / "empty_subdir"
    empty_subdir.mkdir()
    junk_file = movie_dir / ".DS_Store"
    junk_file.write_text("junk")

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean", "--apply", "--only", "actors"])

    assert result.exit_code == 0, result.output

    # .actors/ removed.
    assert not actors_dir.exists(), f".actors/ should be removed, but exists at {actors_dir}"

    # Empty dir NOT removed.
    assert empty_subdir.exists(), f"--only actors leaked to empty dirs: {empty_subdir} was removed"

    # Junk file NOT removed.
    assert junk_file.exists(), f"--only actors leaked to junk files: {junk_file} was removed"


# ── 6. --disk filter ────────────────────────────────────────────────────────────


def test_clean_disk_filter_restricts_scope(tmp_path, test_config) -> None:
    """``--disk drive_a`` only cleans drive_a, NOT drive_b."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    # drive_a: .actors/ dir
    drive_a = tmp_path / "drive_a"
    actors_a = drive_a / "cat_movies" / "MovieA (2020)" / ".actors"
    actors_a.mkdir(parents=True)
    (actors_a / "dummy.txt").write_text("actor")

    # drive_b: .actors/ dir
    drive_b = tmp_path / "drive_b"
    actors_b = drive_b / "cat_movies_animation" / "MovieB (2020)" / ".actors"
    actors_b.mkdir(parents=True)
    (actors_b / "dummy.txt").write_text("actor")

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean", "--apply", "--disk", "drive_a"])

    assert result.exit_code == 0, result.output

    # drive_a actors removed.
    assert not actors_a.exists(), f"drive_a .actors/ should be removed, but exists at {actors_a}"

    # drive_b actors NOT removed.
    assert actors_b.exists(), f"--disk drive_a leaked to drive_b: {actors_b} was removed"


# ── 7. Mutual exclusion ─────────────────────────────────────────────────────────


def test_clean_apply_mutually_exclusive_with_dry_run(tmp_path, test_config) -> None:
    """Passing both ``--apply`` and ``--dry-run`` exits non-zero."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean", "--apply", "--dry-run"])

    assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}: {result.output}"
    assert "mutually exclusive" in result.output.lower(), result.output


# ── 3. Errors ──


def test_clean_invalid_arg_exits_nonzero() -> None:
    """Unknown flag → non-zero exit, no Python traceback."""
    result = run_cli(["library-clean", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_clean_db_path_none_handled_gracefully(test_config) -> None:
    """Unconfigured ``indexer.db_path`` → clean does not validate at startup.

    ``clean_library`` walks config.disks and only accesses ``db_path`` when it
    actually deletes something (to publish an outbox event).  With no media
    directories on the test disks, it never reaches that code path, so exit 0
    is correct — no crash, no traceback.
    """
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean"])
    # Clean does not open the DB at startup — exit 0 is OK when nothing to clean.
    assert_no_python_traceback(result)


def test_clean_corrupt_db_handled_gracefully(tmp_path, test_config) -> None:
    """Corrupt DB → clean does not open it at startup, no traceback."""
    db_path = tmp_path / "corrupt.db"
    db_path.write_text("this is not a sqlite database")
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean"])
    # Clean does not open the DB at startup — exit 0 is OK.
    assert_no_python_traceback(result)


# ── 6. Output ──


def test_clean_text_output_well_formed(tmp_path, test_config) -> None:
    """Default invocation produces readable text with dry-run marker and counts."""
    cfg, _, _ = _setup_movie_with_actors(tmp_path, test_config)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean"])
    assert result.exit_code == 0, result.output
    clean = _ansi_clean(result.output)
    assert "DRY-RUN" in clean, f"DRY-RUN marker missing: {clean}"
    assert "Would delete" in clean, f"delete count missing: {clean}"
    assert "Cleaning library" in clean, f"header missing: {clean}"


def test_clean_error_exits_nonzero() -> None:
    """Invalid flag → non-zero exit code."""
    result = run_cli(["library-clean", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0


# ── 7. Events ──

# N/A: ``library-clean`` does not publish domain events — it operates
# exclusively on the filesystem (pathlib / shutil) and never opens the
# indexer DB with an EventBus.  The contract is verified in
# ``test_clean_apply_removes_actors_dir`` via ``capture_event_bus``
# + ``assert len(captured) == 0``.  If an event is wired later, the
# assertion will flag it.


# ── 8. Idempotence ──


def test_clean_idempotent_second_run_noop(tmp_path, test_config) -> None:
    """Running ``--apply`` twice: second run finds nothing to clean."""
    cfg, actors_dir, _ = _setup_movie_with_actors(tmp_path, test_config)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r1 = run_cli(["library-clean", "--apply"])
    assert r1.exit_code == 0, r1.output
    assert not actors_dir.exists(), f".actors/ should be deleted after first run: {actors_dir}"

    # Second run: nothing left to clean.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r2 = run_cli(["library-clean", "--apply"])
    assert r2.exit_code == 0, r2.output
    clean = _ansi_clean(r2.output)
    assert "0 items" in clean.lower(), f"Second run should find 0 items, got: {clean}"


# ── 9. Closure-of-loop ──

# N/A: ``library-clean`` is a filesystem-only operation (actors dirs, empty dirs,
# junk files).  It does not touch the indexer DB — no ``open_db`` call, no BDD
# reads or writes.  Closure-of-loop is a BDD ↔ FS coherence pattern; with no
# BDD interaction there is no loop to close.  The dry-run safety test already
# proves the command observes and respects the filesystem state.


# ── 10. C2 regression — acquire store stays OPEN across clean_library ──


def _seed_unmet_obligation(acquire_db_path: Path, dispatched_path: Path) -> None:
    """Insert one active, unmet seed obligation for *dispatched_path*.

    Uses the REAL acquire store on *acquire_db_path* (the same DB the live
    ``DeleteAuthority`` reads through ``per_step_boundary``). The obligation has
    a huge ``min_seed_time_s`` and ``added_at == now`` so its seed time is never
    met → ``may_delete`` returns VETO → the deleter must hard-skip it.

    Args:
        acquire_db_path: Resolved ``config.acquire.db_path``.
        dispatched_path: Absolute path the obligation protects (the dir whose
            descendants library-clean would otherwise delete).
    """
    from personalscraper.acquire.domain import SeedObligation
    from personalscraper.acquire.store import build_acquire_store
    from personalscraper.conf.models.acquire import AcquireConfig

    store = build_acquire_store(AcquireConfig(db_path=acquire_db_path))
    try:
        store.seed.add(
            SeedObligation(
                info_hash="c2deadbeef0001",
                source_tracker="lacale",
                min_seed_time_s=999_999_999,  # never elapses → obligation unmet
                min_ratio=1.0,
                added_at=int(time.time()),
                dispatched_path=str(dispatched_path),
            )
        )
    finally:
        store.close()


def test_clean_apply_respects_live_obligation_store_stays_open(tmp_path, test_config) -> None:
    """C2: a live seed obligation under a cleaned dir → deletion HARD-SKIPPED.

    Reproduces the C2 bug: ``library_clean`` derived the permit inside a
    ``with per_step_boundary(...)`` block, then ran ``clean_library`` AFTER the
    block had already closed ``app_context.acquire`` → ``may_delete`` hit
    "AcquireStore is closed" → fail-open swallowed it to ALLOW → the hard-skip
    never fired and the VETOed ``.actors/`` dir was deleted.

    The fix runs ``clean_library`` INSIDE the boundary so the store is alive for
    every ``may_delete`` consult.  Asserting ``skipped_by_obligation >= 1`` (via
    the CLI's "Skipped by seed obligation" line) + the dir still on disk proves
    the store stayed open. This test FAILS on the pre-fix code.
    """
    cfg, actors_dir, _ = _setup_movie_with_actors(tmp_path, test_config)

    # The live DeleteAuthority reads config.acquire.db_path; the .actors/ dir is
    # what --only actors would delete, so protect it with an unmet obligation.
    assert cfg.acquire.db_path is not None
    _seed_unmet_obligation(cfg.acquire.db_path, actors_dir)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-clean", "--apply", "--only", "actors"])

    assert result.exit_code == 0, result.output
    clean = _ansi_clean(result.output)
    # The hard-skip line must appear (store was open → may_delete saw the VETO).
    assert "Skipped by seed obligation" in clean, f"Expected obligation skip, got: {clean}"
    # And the protected dir + its content must survive.
    assert actors_dir.exists(), f"VETOed .actors/ MUST NOT be deleted (store closed too early?): {actors_dir}"
    assert (actors_dir / "dummy.txt").exists(), "VETOed .actors/ content was deleted"


def test_clean_library_error_propagates_not_swallowed_by_fail_open(tmp_path, test_config) -> None:
    """C2: ``clean_library`` exceptions must propagate, not be swallowed by the fail-open handler.

    The ``cleaned`` flag flips ``True`` just before ``_run_and_report`` is called.
    If ``clean_library`` raises inside ``_run_and_report``, the outer ``except``
    must re-raise — NOT fall through to the fail-open ``AllowAllPermit`` path.
    This proves ``clean_library``'s own errors are not caught by the authority
    fail-open handler (DESIGN §9).

    Pre-fix behaviour: the exception was swallowed → exit 0, misleading the
    operator into thinking cleanup succeeded when it actually crashed.
    """
    cfg, _, _ = _setup_movie_with_actors(tmp_path, test_config)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        with patch(
            "personalscraper.maintenance.disk_cleaner.clean_library",
            side_effect=RuntimeError("boom"),
        ):
            result = run_cli(["library-clean"])

    assert result.exit_code != 0, f"Expected non-zero exit (error propagation), got {result.exit_code}: {result.output}"
    assert isinstance(result.exception, RuntimeError), (
        f"Expected RuntimeError in result.exception, got {type(result.exception).__name__}: {result.exception}"
    )
    assert "boom" in str(result.exception), f"Expected 'boom' in exception message, got: {result.exception}"
