"""Adversarial concurrency tests for the two-tier scoped scrape lock.

Constructs the real races between the global ``pipeline.lock`` (taken by
:func:`acquire_pipeline_lock`) and the per-staging-item scrape locks (taken by
:func:`acquire_scrape_resolve_lock`) using real lock files on disk:

* a *live* pid = the current process pid (``os.getpid()``) — ``os.kill(pid, 0)``
  succeeds, so the lock is held.
* a *dead* pid = ``999999999`` (matches the ``tests/test_lock.py`` convention) —
  ``os.kill`` raises ``ProcessLookupError``, so the lock is stale/inactive.

The mutual-exclusion invariant proven here: both sides create their claim BEFORE
checking the other, so in any interleaving at most one side passes its check; if
both race, both back off (never both proceed).
"""

import os
from pathlib import Path

import pytest

from personalscraper.lock import (
    acquire_pipeline_lock,
    acquire_scrape_resolve_lock,
    any_scrape_resolve_active,
    release_scrape_resolve_lock,
    scrape_locks_dir_for,
)

#: A pid that is guaranteed not to belong to any live process (mirrors the
#: ``tests/test_lock.py`` convention).
_DEAD_PID = "999999999"


def _scrape_dir(tmp_path: Path) -> Path:
    """Return the ``<data_dir>/locks/scrape/`` dir for *tmp_path* as data_dir."""
    return scrape_locks_dir_for(tmp_path)


# ---------------------------------------------------------------------------
# scrape_locks_dir_for
# ---------------------------------------------------------------------------


def test_scrape_locks_dir_for_computes_path(tmp_path):
    """scrape_locks_dir_for returns <data_dir>/locks/scrape/ without creating it."""
    result = scrape_locks_dir_for(tmp_path)
    assert result == tmp_path / "locks" / "scrape"
    # Path helper is pure — it must not create the directory itself.
    assert not result.exists()


# ---------------------------------------------------------------------------
# 1. Two distinct staging paths → both succeed (parallel)
# ---------------------------------------------------------------------------


def test_two_distinct_staging_paths_both_acquire(tmp_path):
    """Two acquire_scrape_resolve_lock on DISTINCT paths both succeed (parallel).

    No global pipeline.lock is held, so the fail-closed post-claim check passes
    for both — they take different sha1-named locks and run concurrently.
    """
    pipeline_lock = tmp_path / "pipeline.lock"
    scrape_dir = _scrape_dir(tmp_path)
    path_a = tmp_path / "item-a"
    path_b = tmp_path / "item-b"

    lock_a = acquire_scrape_resolve_lock(path_a, pipeline_lock, scrape_dir)
    lock_b = acquire_scrape_resolve_lock(path_b, pipeline_lock, scrape_dir)

    assert lock_a is not None
    assert lock_b is not None
    assert lock_a != lock_b
    assert lock_a.exists()
    assert lock_b.exists()


# ---------------------------------------------------------------------------
# 2. Same staging path twice → second returns None (idempotent guard)
# ---------------------------------------------------------------------------


def test_same_staging_path_twice_second_returns_none(tmp_path):
    """A second acquire on the SAME staging path returns None (idempotent guard)."""
    pipeline_lock = tmp_path / "pipeline.lock"
    scrape_dir = _scrape_dir(tmp_path)
    path = tmp_path / "item-a"

    first = acquire_scrape_resolve_lock(path, pipeline_lock, scrape_dir)
    second = acquire_scrape_resolve_lock(path, pipeline_lock, scrape_dir)

    assert first is not None
    assert second is None
    # The first lock is still intact — the refused second acquire must not have
    # removed or overwritten it.
    assert first.exists()
    assert first.read_text().strip() == str(os.getpid())


# ---------------------------------------------------------------------------
# 3. Global pipeline.lock held → resolve returns None AND leaves no item lock
# ---------------------------------------------------------------------------


def test_scrape_resolve_refuses_when_pipeline_lock_held(tmp_path):
    """acquire_scrape_resolve_lock returns None when the global lock is held.

    The item lock is registered first (claim-first), then the global lock probe
    trips → the just-created item lock must be released so it is NOT left behind
    (no leaked lock that would block future resolves forever).
    """
    pipeline_lock = tmp_path / "pipeline.lock"
    pipeline_lock.write_text(str(os.getpid()))  # live global holder
    scrape_dir = _scrape_dir(tmp_path)
    path = tmp_path / "item-a"

    result = acquire_scrape_resolve_lock(path, pipeline_lock, scrape_dir)

    assert result is None
    # Fail-closed cleanup: no item lock is left behind in the scrape dir.
    assert list(scrape_dir.glob("*.lock")) == []


# ---------------------------------------------------------------------------
# 4. acquire_pipeline_lock backs off (and releases global) when a resolve active
# ---------------------------------------------------------------------------


def test_pipeline_lock_backs_off_when_scrape_active(tmp_path):
    """acquire_pipeline_lock returns False + releases the global lock when a resolve is active."""
    pipeline_lock = tmp_path / "pipeline.lock"
    scrape_dir = _scrape_dir(tmp_path)
    scrape_dir.mkdir(parents=True, exist_ok=True)
    # A live resolve holds an item lock.
    (scrape_dir / "abc123.lock").write_text(str(os.getpid()))

    result = acquire_pipeline_lock(pipeline_lock, scrape_dir)

    assert result is False
    # The global lock the function transiently acquired must be released — it is
    # not leaked when the function backs off.
    assert not pipeline_lock.exists()


# ---------------------------------------------------------------------------
# 4b. acquire_pipeline_lock releases the global lock if the post-claim probe raises
# ---------------------------------------------------------------------------


def test_pipeline_lock_released_when_scrape_probe_raises(tmp_path, monkeypatch):
    """acquire_pipeline_lock releases pipeline.lock when the post-claim probe raises (SF5).

    The scrape-active probe runs AFTER the global lock is claimed. If it raises
    an unexpected exception (dir mutated mid-glob, non-OSError FS error), the
    just-claimed global lock must be released before the exception propagates —
    no exception path may leave pipeline.lock on disk.
    """
    pipeline_lock = tmp_path / "pipeline.lock"
    scrape_dir = _scrape_dir(tmp_path)

    import personalscraper.lock as lock_mod

    def _boom(_scrape_locks_dir):
        raise RuntimeError("dir mutated mid-glob")

    monkeypatch.setattr(lock_mod, "any_scrape_resolve_active", _boom)

    with pytest.raises(RuntimeError, match="dir mutated mid-glob"):
        acquire_pipeline_lock(pipeline_lock, scrape_dir)

    # Fail-safe cleanup: the transiently-claimed global lock is NOT leaked.
    assert not pipeline_lock.exists()


# ---------------------------------------------------------------------------
# 5. acquire_pipeline_lock succeeds when scrape dir empty / only stale locks
# ---------------------------------------------------------------------------


def test_pipeline_lock_succeeds_when_scrape_dir_empty(tmp_path):
    """acquire_pipeline_lock succeeds when the scrape dir does not exist yet."""
    pipeline_lock = tmp_path / "pipeline.lock"
    scrape_dir = _scrape_dir(tmp_path)  # not created

    assert acquire_pipeline_lock(pipeline_lock, scrape_dir) is True
    assert pipeline_lock.exists()
    assert pipeline_lock.read_text().strip() == str(os.getpid())


def test_pipeline_lock_succeeds_when_only_stale_scrape_locks(tmp_path):
    """acquire_pipeline_lock succeeds when the scrape dir holds only stale locks."""
    pipeline_lock = tmp_path / "pipeline.lock"
    scrape_dir = _scrape_dir(tmp_path)
    scrape_dir.mkdir(parents=True, exist_ok=True)
    # A crashed resolve left a dead-pid lock behind.
    (scrape_dir / "dead.lock").write_text(_DEAD_PID)

    assert acquire_pipeline_lock(pipeline_lock, scrape_dir) is True
    assert pipeline_lock.exists()


# ---------------------------------------------------------------------------
# 6. any_scrape_resolve_active — stale (dead-pid) locks are inactive
# ---------------------------------------------------------------------------


def test_any_scrape_resolve_active_missing_dir_is_false(tmp_path):
    """any_scrape_resolve_active returns False when the dir does not exist."""
    assert any_scrape_resolve_active(_scrape_dir(tmp_path)) is False


def test_any_scrape_resolve_active_stale_lock_is_inactive(tmp_path):
    """A dead-pid item lock is treated as inactive by any_scrape_resolve_active."""
    scrape_dir = _scrape_dir(tmp_path)
    scrape_dir.mkdir(parents=True, exist_ok=True)
    (scrape_dir / "dead.lock").write_text(_DEAD_PID)

    assert any_scrape_resolve_active(scrape_dir) is False


def test_any_scrape_resolve_active_live_lock_is_active(tmp_path):
    """A live-pid item lock is treated as active by any_scrape_resolve_active."""
    scrape_dir = _scrape_dir(tmp_path)
    scrape_dir.mkdir(parents=True, exist_ok=True)
    (scrape_dir / "live.lock").write_text(str(os.getpid()))

    assert any_scrape_resolve_active(scrape_dir) is True


def test_any_scrape_resolve_active_mixed_live_and_stale_is_active(tmp_path):
    """One live lock among stale ones still makes the dir active."""
    scrape_dir = _scrape_dir(tmp_path)
    scrape_dir.mkdir(parents=True, exist_ok=True)
    (scrape_dir / "dead.lock").write_text(_DEAD_PID)
    (scrape_dir / "live.lock").write_text(str(os.getpid()))

    assert any_scrape_resolve_active(scrape_dir) is True


# ---------------------------------------------------------------------------
# release_scrape_resolve_lock
# ---------------------------------------------------------------------------


def test_release_scrape_resolve_lock_removes_item_lock(tmp_path):
    """release_scrape_resolve_lock removes the item lock so the item can re-resolve."""
    pipeline_lock = tmp_path / "pipeline.lock"
    scrape_dir = _scrape_dir(tmp_path)
    path = tmp_path / "item-a"

    lock = acquire_scrape_resolve_lock(path, pipeline_lock, scrape_dir)
    assert lock is not None
    release_scrape_resolve_lock(lock)
    assert not lock.exists()

    # After release the SAME item can be resolved again (the idempotent guard
    # only blocks while the prior resolve is in flight).
    again = acquire_scrape_resolve_lock(path, pipeline_lock, scrape_dir)
    assert again is not None
    assert again == lock


# ---------------------------------------------------------------------------
# Cross-side interleaving — after a resolve wins, the pipeline backs off
# ---------------------------------------------------------------------------


def test_resolve_then_pipeline_mutual_exclusion_end_to_end(tmp_path):
    """A resolve that wins its lock makes a subsequent acquire_pipeline_lock back off.

    This is the fail-closed guarantee end-to-end across both helpers: the resolve
    claims first with no global holder (succeeds), then a pipeline holder trying
    to start sees the active item lock and backs off (releasing its transient
    global lock).
    """
    pipeline_lock = tmp_path / "pipeline.lock"
    scrape_dir = _scrape_dir(tmp_path)
    path = tmp_path / "item-a"

    item_lock = acquire_scrape_resolve_lock(path, pipeline_lock, scrape_dir)
    assert item_lock is not None

    # Now a full pipeline run tries to start — it must back off.
    assert acquire_pipeline_lock(pipeline_lock, scrape_dir) is False
    assert not pipeline_lock.exists()

    # Once the resolve releases, the pipeline can proceed.
    release_scrape_resolve_lock(item_lock)
    assert acquire_pipeline_lock(pipeline_lock, scrape_dir) is True


# ---------------------------------------------------------------------------
# Order-inversion race guards — prove CLAIM-FIRST-THEN-VERIFY is required
#
# These simulate the interleaving where the OPPOSING claim lands in the window
# between our claim and our check.  Only the claim-first-then-verify ordering
# survives: if the code inverted to check-then-claim, it would have already
# passed its (then-clear) check and would wrongly proceed.  Injecting the
# opposing claim as a side effect of OUR claim reproduces that exact window.
# ---------------------------------------------------------------------------


def test_scrape_resolve_backs_off_when_pipeline_appears_during_claim(tmp_path, monkeypatch):
    """A pipeline holder appearing WHILE the resolve claims its item lock → back off.

    Reproduces the race an inverted (check-then-claim) resolve would miss: the
    global pipeline.lock is grabbed in the window between the resolve's check and
    its claim.  We inject it as a side effect of the item-lock ``acquire_lock``
    call, so a correct claim-first-then-verify resolve re-checks the pipeline
    lock AFTER claiming and backs off; an inverted resolve (which checked before
    claiming, when the lock was still clear) would wrongly return the item lock.
    """
    pipeline_lock = tmp_path / "pipeline.lock"
    scrape_dir = _scrape_dir(tmp_path)
    path = tmp_path / "item-a"

    import personalscraper.lock as lock_mod

    real_acquire = lock_mod.acquire_lock

    def _acquire_and_race(lock_file, *args, **kwargs):
        result = real_acquire(lock_file, *args, **kwargs)
        # After the ITEM lock is claimed, a concurrent pipeline run grabs the
        # global lock — exactly the window a check-then-claim ordering misses.
        if result and lock_file != pipeline_lock and not pipeline_lock.exists():
            pipeline_lock.write_text(str(os.getpid()))
        return result

    monkeypatch.setattr(lock_mod, "acquire_lock", _acquire_and_race)

    result = acquire_scrape_resolve_lock(path, pipeline_lock, scrape_dir)

    # Claim-first-then-verify: the resolve re-checks the pipeline lock after
    # claiming, sees the racing holder, and backs off (no leaked item lock).
    assert result is None
    assert list(scrape_dir.glob("*.lock")) == []


def test_pipeline_backs_off_when_resolve_appears_during_claim(tmp_path, monkeypatch):
    """A resolve item lock appearing WHILE the pipeline claims the global lock → back off.

    Mirror of the resolve-side race for :func:`acquire_pipeline_lock`: the item
    lock is registered in the window between the pipeline's check and its claim.
    We inject it as a side effect of the global-lock ``acquire_lock`` call, so a
    correct claim-first-then-verify pipeline re-checks the scrape dir AFTER
    claiming and backs off; an inverted pipeline would wrongly proceed.
    """
    pipeline_lock = tmp_path / "pipeline.lock"
    scrape_dir = _scrape_dir(tmp_path)
    scrape_dir.mkdir(parents=True, exist_ok=True)

    import personalscraper.lock as lock_mod

    real_acquire = lock_mod.acquire_lock

    def _acquire_and_race(lock_file, *args, **kwargs):
        result = real_acquire(lock_file, *args, **kwargs)
        # After the GLOBAL lock is claimed, a concurrent resolve registers its
        # item lock — exactly the window a check-then-claim ordering misses.
        if result and lock_file == pipeline_lock:
            (scrape_dir / "racing.lock").write_text(str(os.getpid()))
        return result

    monkeypatch.setattr(lock_mod, "acquire_lock", _acquire_and_race)

    result = acquire_pipeline_lock(pipeline_lock, scrape_dir)

    # Claim-first-then-verify: the pipeline re-checks the scrape dir after
    # claiming, sees the racing resolve, and backs off (releases the global lock).
    assert result is False
    assert not pipeline_lock.exists()


# ---------------------------------------------------------------------------
# Symmetric race — BOTH sides claim into the other's verify window → BOTH refuse
#
# The two order-inversion tests above each prove ONE direction backs off. Neither
# proves the JOINT invariant "if both race, BOTH back off (never both proceed)".
# Here we drive BOTH acquisitions under a single side-effect that plants the
# OPPOSING claim during each claim, so each verify window observes the other's
# LIVE claim → both must return refusal.
# ---------------------------------------------------------------------------


def test_symmetric_race_both_sides_back_off(tmp_path, monkeypatch):
    """Both sides claim into the other's window → BOTH return refusal (joint proof).

    A single ``acquire_lock`` side-effect reproduces the symmetric interleaving:

    * when the RESOLVE claims its item lock, a racing pipeline holder appears
      (``pipeline.lock`` written with a live pid);
    * when the PIPELINE claims the global lock, a racing resolve appears (an item
      ``racing.lock`` written with a live pid).

    Driving both acquisitions proves the joint invariant that neither wins:

    * the resolve's post-claim verify sees the racing ``pipeline.lock`` → returns
      ``None`` and releases its item lock (no leaked item lock);
    * the pipeline then cannot even claim ``pipeline.lock`` (the racing holder
      still owns it) → returns ``False``.

    Both refuse — never both proceed — which the two one-directional tests do not
    jointly establish.
    """
    pipeline_lock = tmp_path / "pipeline.lock"
    scrape_dir = _scrape_dir(tmp_path)
    scrape_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "item-a"

    import personalscraper.lock as lock_mod

    real_acquire = lock_mod.acquire_lock

    def _acquire_and_race(lock_file, *args, **kwargs):
        result = real_acquire(lock_file, *args, **kwargs)
        if not result:
            return result
        if lock_file == pipeline_lock:
            # The pipeline just claimed the global lock — a resolve races in with
            # its item lock, in the pipeline's verify window.
            (scrape_dir / "racing.lock").write_text(str(os.getpid()))
        else:
            # A resolve just claimed its item lock — a pipeline races in with the
            # global lock, in the resolve's verify window.
            if not pipeline_lock.exists():
                pipeline_lock.write_text(str(os.getpid()))
        return result

    monkeypatch.setattr(lock_mod, "acquire_lock", _acquire_and_race)

    # Side 1 — the resolve claims first; its verify sees the racing pipeline
    # holder and backs off (no leaked item lock).
    resolve_result = acquire_scrape_resolve_lock(path, pipeline_lock, scrape_dir)
    assert resolve_result is None
    assert list(scrape_dir.glob("*.lock")) == []

    # Side 2 — the pipeline now tries: the racing pipeline.lock (live pid) still
    # owns the global lock, so it cannot even claim it and backs off too.
    pipeline_result = acquire_pipeline_lock(pipeline_lock, scrape_dir)
    assert pipeline_result is False

    # Joint invariant proven: neither side proceeded.
    assert resolve_result is None and pipeline_result is False
