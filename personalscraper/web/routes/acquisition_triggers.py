"""Acquisition trigger routes — manual detect + per-series grab (OBJ3 / §5).

Extracted from ``web/routes/acquisition.py`` to keep that module under the
1000-LOC ceiling (same precedent as ``web/acquisition/_helpers.py``). Both
routers share the ``/api/acquisition`` prefix and are registered side by side
under the single ``guarded_api`` perimeter in ``app.py``.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import uuid
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Request

from personalscraper.acquire.store import build_acquire_store
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.web.acquisition.runner import grab_options_json, hash_options_json, prime_options_json
from personalscraper.web.deps import require_x_requested_with
from personalscraper.web.models.acquisition import GrabTriggerResponse

router = APIRouter(prefix="/api/acquisition", tags=["acquisition"])
logger = get_logger(__name__)

#: What :func:`enqueue_prime_run` did — the seam the card status reads: a
#: priming run in flight (spawned / already running) is « vérification en
#: cours », a failed enqueue leaves the card on its derived (honest) state.
PrimeOutcome = Literal["spawned", "already_running", "failed"]


@dataclass(frozen=True)
class PrimeResult:
    """Outcome of an amorce enqueue, WITH the run it points at.

    The outcome alone cannot satisfy §5 (« le déclenchement manuel montre le
    run »): a caller that only learns « something started » has nothing to poll.
    Carrying the uid lets every manual entry point follow its run to the real,
    numbered result — or to the real error.

    Attributes:
        outcome: What the enqueue did (``spawned`` / ``already_running`` /
            ``failed``).
        run_uid: The run to follow — freshly spawned, or the in-flight one this
            call joined. ``None`` only when nothing runs (``failed``).
    """

    outcome: PrimeOutcome
    run_uid: str | None

    @property
    def started(self) -> bool:
        """Whether a run is actually in flight for this call."""
        return self.outcome in ("spawned", "already_running")


# ── POST /api/acquisition/followed/{id}/search — per-series manual grab (OBJ3) ──


def pid_is_alive(pid: int | None) -> bool:
    """Report whether *pid* names a live process — the ONE liveness authority.

    An un-ended ``pipeline_run`` row proves nothing on its own: a runner that
    crashed (or was SIGKILLed) never gets to write ``ended_at``, so the row
    stays open forever. Liveness is what separates « still running » from
    « stale row », and it must be decided in exactly ONE place: a reader that
    skips this check pins a card on « vérification en cours » for a process
    that died days ago, while the 409 guard on the same row lets the action
    through — two answers to the same question.

    Args:
        pid: The ``pipeline_run.pid`` column value. ``None`` for a row whose
            runner never claimed a pid; the column is untyped at the SQLite
            level, so a corrupt row can also deliver a non-integral value —
            handled rather than crashing a read.

    Returns:
        ``True`` when the pid names a live process. A ``PermissionError``
        counts as ALIVE (the process exists but is owned by another user);
        ``None``, a dead pid and an unusable value all count as stale.
    """
    if pid is None:
        return False  # never claimed → stale row
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False  # dead pid → stale row
    except PermissionError:
        return True  # alive, owned by another user
    except (TypeError, ValueError, OSError):
        return False  # unusable pid value → treat as stale
    return True


def _live_run_uid(db_path: Path, command: str, options_json: str) -> str | None:
    """Return the uid of an in-flight acquisition run with the same scope, if any.

    Scans ``pipeline_run`` for an un-ended row of the given *command* whose
    ``options_json`` matches (same followed series / same detect scope) and
    whose pid is still alive per :func:`pid_is_alive`. A dead/NULL pid is a
    stale row (crashed runner) and is ignored. Single authority for « is this
    action already running? » — both the 409 guard and the amorce idempotence
    read it.

    Args:
        db_path: Absolute path to ``library.db``.
        command: The run command to match (``'grab'`` / ``'follow-detect'`` /
            ``'prime'``).
        options_json: The canonical options string for the run scope.

    Returns:
        The live run's ``run_uid``, or ``None`` when none matches (also on a
        missing DB or an unreadable ``pipeline_run`` — the guard fails open
        rather than blocking a legitimate action).

        The uid, not a bool: §5 requires the manual trigger to SHOW the run, and
        an operator who joins a run already in flight must be able to follow THAT
        run to its numbered result. A boolean cannot be polled.
    """
    if not db_path.exists():
        return None
    try:
        with closing(sqlite3.connect(str(db_path))) as conn:
            apply_pragmas(conn)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT run_uid, pid FROM pipeline_run WHERE command = ? AND ended_at IS NULL AND options_json = ?",
                (command, options_json),
            ).fetchall()
    except sqlite3.Error:
        logger.warning("grab_guard_query_failed", command=command, exc_info=True)
        return None
    for row in rows:
        if pid_is_alive(row["pid"]):
            return str(row["run_uid"])
    return None


def _guard_no_running_grab(db_path: Path, options_json: str, command: str = "grab") -> None:
    """Raise 409 when a live acquisition run with the same scope is in flight.

    Args:
        db_path: Absolute path to ``library.db``.
        options_json: The canonical options string for the run scope.
        command: The run command to match (``'grab'`` / ``'follow-detect'``).

    Raises:
        HTTPException: 409 when a live matching run is already running.
    """
    if _live_run_uid(db_path, command, options_json) is not None:
        raise HTTPException(status_code=409, detail="A matching acquisition run is already in flight")


def _spawn_grab_runner(run_uid: str, followed_id: int) -> int:
    """Spawn the grab runner as a detached subprocess.

    Args:
        run_uid: The reserved run's unique identifier.
        followed_id: The followed series to scope the grab to.

    Returns:
        The pid of the spawned runner process.
    """
    env = {
        **os.environ,
        "PERSONALSCRAPER_RUN_UID": run_uid,
        "PERSONALSCRAPER_GRAB_FOLLOWED_ID": str(followed_id),
    }
    logger.info("grab_trigger_spawned", run_uid=run_uid, followed_id=followed_id)
    proc = subprocess.Popen(
        [sys.executable, "-m", "personalscraper.web.acquisition.runner"],
        start_new_session=True,
        env=env,
    )
    return proc.pid


def _spawn_prime_runner(run_uid: str, followed_id: int) -> int:
    """Spawn the priming runner as a detached subprocess.

    Mirrors :func:`_spawn_grab_runner` — same runner, same env contract, the
    ``prime`` command only chaining three CLI steps instead of one.

    Args:
        run_uid: The reserved run's unique identifier.
        followed_id: The followed series to prime.

    Returns:
        The pid of the spawned runner process.
    """
    env = {
        **os.environ,
        "PERSONALSCRAPER_RUN_UID": run_uid,
        "PERSONALSCRAPER_ACQ_COMMAND": "prime",
        "PERSONALSCRAPER_GRAB_FOLLOWED_ID": str(followed_id),
    }
    logger.info("prime_trigger_spawned", run_uid=run_uid, followed_id=followed_id)
    proc = subprocess.Popen(
        [sys.executable, "-m", "personalscraper.web.acquisition.runner"],
        start_new_session=True,
        env=env,
    )
    return proc.pid


def enqueue_prime_run(db_path: Path | None, followed_id: int) -> PrimeResult:
    """Enqueue the amorce of a freshly followed (or reactivated) series.

    Reserves a ``pipeline_run`` row (``kind='maintenance'``, ``command='prime'``)
    through the SAME run authority as the manual grab/detect triggers — never a
    parallel mechanism (NE-DOIT-PAS-7) — then spawns the runner. The run is
    fire-and-forget from the request's viewpoint: every failure is logged and
    swallowed so the follow is still created (the card then simply reads
    ``unverified``, never an optimistic « À jour »).

    Idempotence: a prime already in flight for this follow is NOT duplicated —
    §6 allows exactly one refusal, the duplicate of the same action.

    Args:
        db_path: Absolute path to ``library.db`` (``None`` when the indexer is
            not configured — the amorce is then impossible and reported failed).
        followed_id: Rowid of the ``followed_series`` row to prime.

    Returns:
        A :class:`PrimeResult` carrying what happened AND the run to follow:
        ``spawned`` with the fresh uid, ``already_running`` with the in-flight
        run's uid (the caller joins it, §6), or ``failed`` with ``None``.
    """
    if db_path is None:
        logger.warning("prime_enqueue_no_db_path", followed_id=followed_id)
        return PrimeResult(outcome="failed", run_uid=None)

    options_json = prime_options_json(followed_id)
    live_uid = _live_run_uid(db_path, "prime", options_json)
    if live_uid is not None:
        logger.info("prime_already_running", followed_id=followed_id, run_uid=live_uid)
        # §6: not a refusal — the operator joins the run already doing the work,
        # and gets ITS uid so the UI can follow it to its numbered result (§5).
        return PrimeResult(outcome="already_running", run_uid=live_uid)

    run_uid = uuid.uuid4().hex
    writer = PipelineRunWriter(db_path)
    try:
        writer.insert(
            run_uid,
            trigger="web",
            dry_run=False,
            pid=os.getpid(),
            kind="maintenance",
            command="prime",
            options_json=options_json,
            if_absent=True,
        )
    except sqlite3.Error as exc:
        # The reservation itself failed (locked / unreadable library.db). The
        # function's whole contract is « never break the 201 »: letting this
        # propagate would 500 a create whose follow row is already committed,
        # and the operator would see an error for a follow that DOES exist.
        # Report it like every other amorce failure — with the follow it
        # concerns and the reason.
        logger.warning("prime_reserve_failed", run_uid=run_uid, followed_id=followed_id, error=str(exc))
        return PrimeResult(outcome="failed", run_uid=None)
    try:
        pid = _spawn_prime_runner(run_uid, followed_id)
    except Exception as exc:  # noqa: BLE001 — the 201 must never depend on the amorce
        # Finalize the reserved row: a failed amorce is a visible error run,
        # never a row stuck at 'running' and never a silent nothing.
        try:
            writer.finalize(run_uid, "error", error=f"Runner spawn failed: {exc}")
        except sqlite3.Error:
            logger.warning("prime_finalize_failed", run_uid=run_uid, followed_id=followed_id)
        logger.warning("prime_spawn_failed", run_uid=run_uid, followed_id=followed_id, error=str(exc))
        return PrimeResult(outcome="failed", run_uid=None)

    try:
        writer.update_pid(run_uid, pid)
    except sqlite3.Error:
        # The runner IS live; only its pid bookkeeping failed. Say so — the
        # liveness guard reads that pid, so a row stuck on the web process's
        # pid is a fact the operator may need.
        logger.warning("prime_update_pid_failed", run_uid=run_uid, followed_id=followed_id, pid=pid)
    return PrimeResult(outcome="spawned", run_uid=run_uid)


@router.post(
    "/detect",
    status_code=202,
    response_model=GrabTriggerResponse,
    dependencies=[Depends(require_x_requested_with)],
)
def trigger_detect(request: Request) -> GrabTriggerResponse:
    """Launch the aired-episode / film discovery on demand (§5 manual watcher).

    The detect pass (the 03:00 cron's job) polls the provider catalog for every
    active follow, enqueues the missing episodes / films as wanted rows, and —
    for movie follows already in the library — performs the §5 acquired-film
    closure. This endpoint runs it NOW: it reserves a ``pipeline_run`` row
    (``command='follow-detect'``, ``trigger='web'``), spawns the acquisition
    runner in detect mode, and returns ``202`` with the ``run_uid`` so the UI
    tracks the run to its numeric result — never a blind success toast.

    Args:
        request: The incoming FastAPI request.

    Returns:
        ``202`` with :class:`GrabTriggerResponse` (``{"run_uid": "..."}``).

    Raises:
        409: A detect run is already in flight.
        500: The runner subprocess failed to spawn.
    """
    config = request.app.state.config
    db_path = cast(Path, config.indexer.db_path)

    # Reject a duplicate concurrent detect (pid-alive guard on the same options).
    _guard_no_running_grab(db_path, "{}", command="follow-detect")

    run_uid = uuid.uuid4().hex
    writer = PipelineRunWriter(db_path)
    writer.insert(
        run_uid,
        trigger="web",
        dry_run=False,
        pid=os.getpid(),
        kind="maintenance",
        command="follow-detect",
        options_json="{}",
        if_absent=True,
    )
    try:
        env = {
            **os.environ,
            "PERSONALSCRAPER_RUN_UID": run_uid,
            "PERSONALSCRAPER_ACQ_COMMAND": "detect",
        }
        logger.info("detect_trigger_spawned", run_uid=run_uid)
        subprocess.Popen(
            [sys.executable, "-m", "personalscraper.web.acquisition.runner"],
            start_new_session=True,
            env=env,
        )
    except (OSError, ValueError) as exc:
        writer.finalize(run_uid, "error", error=f"Runner spawn failed: {exc}")
        logger.error("detect_trigger_spawn_failed", run_uid=run_uid, error=str(exc))
        raise HTTPException(status_code=500, detail="Could not launch the detect runner") from exc
    return GrabTriggerResponse(run_uid=run_uid)


#: The two per-follow manual actions, each with the ``pipeline_run.command`` it
#: reserves and the canonical scope string its idempotence guard matches. They
#: are DISTINCT actions on purpose (acq-states phase 8): « Rechercher » primes
#: the whole chain (detect → search → grab) while « Récupérer maintenant » only
#: claims what is already known to be takeable. A live one therefore never
#: refuses the other — §6 allows exactly one refusal, the duplicate of the SAME
#: action. The spawners are NOT held here: they are looked up by name at call
#: time so a test (or a future decorator) monkeypatching the module attribute
#: is actually honoured.
_FOLLOWED_ACTIONS: dict[str, tuple[str, Callable[[int], str]]] = {
    "prime": ("prime", prime_options_json),
    "grab": ("grab", grab_options_json),
}


def _launch_followed_action(request: Request, followed_id: int, action: str) -> GrabTriggerResponse:
    """Reserve + spawn one of the per-follow manual actions.

    Shared body of the two trigger routes so they can never drift apart on the
    404 order, the idempotence guard, the pid bookkeeping or the fail-soft
    finalize. Only the reserved command, the scope string and the spawner
    differ — all three read from :data:`_FOLLOWED_ACTIONS`.

    Args:
        request: The incoming FastAPI request.
        followed_id: Rowid of the ``followed_series`` row.
        action: ``"prime"`` or ``"grab"`` — the key in :data:`_FOLLOWED_ACTIONS`.

    Returns:
        :class:`GrabTriggerResponse` carrying the launched ``run_uid``.

    Raises:
        HTTPException: 404 (unknown follow), 409 (the SAME action is already in
            flight for this follow), 500 (the runner failed to spawn).
    """
    command, options_of = _FOLLOWED_ACTIONS[action]
    config = request.app.state.config
    db_path = cast(Path, config.indexer.db_path)

    # 1. Verify the series exists (404 before any run reservation).
    store = build_acquire_store(config.acquire)
    try:
        existing = store.follow.get(followed_id)
    finally:
        store.close()
    if existing is None:
        raise HTTPException(status_code=404, detail="Followed series not found")

    options_json = options_of(followed_id)

    # 2. Reject the duplicate of the SAME action on the same follow (409) — and
    #    ONLY that: a running grab must never refuse a prime, nor the reverse.
    _guard_no_running_grab(db_path, options_json, command=command)

    # 3. Reserve the pipeline_run row with the web process pid (guaranteed alive
    #    until the runner claims its own pid), then spawn the runner.
    run_uid = uuid.uuid4().hex
    writer = PipelineRunWriter(db_path)
    writer.insert(
        run_uid,
        trigger="web",
        dry_run=False,
        pid=os.getpid(),
        kind="maintenance",
        command=command,
        options_json=options_json,
        if_absent=True,
    )

    try:
        # Resolved at CALL time (never captured in the table above), so the
        # spawner a test patches on this module is the one that runs.
        spawn = _spawn_prime_runner if action == "prime" else _spawn_grab_runner
        pid = spawn(run_uid, followed_id)
    except (OSError, ValueError) as exc:
        # Never leave the reserved row 'running' on a spawn failure (fail-soft).
        try:
            writer.finalize(run_uid, "error", error=str(exc))
        except sqlite3.Error:
            logger.warning("followed_trigger_finalize_failed", run_uid=run_uid, command=command)
        logger.error(
            "followed_trigger_spawn_failed",
            run_uid=run_uid,
            command=command,
            followed_id=followed_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=f"Failed to spawn {command} runner") from exc

    if isinstance(pid, int):
        try:
            writer.update_pid(run_uid, pid)
        except sqlite3.Error:
            logger.warning("followed_trigger_update_pid_failed", run_uid=run_uid, command=command)

    return GrabTriggerResponse(run_uid=run_uid)


@router.post(
    "/followed/{followed_id}/search",
    status_code=202,
    response_model=GrabTriggerResponse,
    dependencies=[Depends(require_x_requested_with)],
)
def trigger_followed_search(request: Request, followed_id: int) -> GrabTriggerResponse:
    """Launch the FULL search chain for one followed series (« Rechercher »).

    Spawns the ``prime`` runner — ``follow detect --series N`` →
    ``search --followed-id N`` → ``grab --followed-id N`` — and returns ``202``
    with the ``run_uid`` so the UI tracks the run to its numeric result.

    It used to spawn a bare ``grab``, which was the right runner while a single
    pass did everything. Since the five-state split, ``grab`` only claims items
    already marked takeable: pressing « Rechercher » on a follow whose episodes
    read ``pending`` or ``unverified`` would have done strictly nothing and
    reported success — a silent no-op (NE-DOIT-PAS-1). Priming re-polls the
    catalog, re-searches the trackers and grabs what it finds, which is what the
    button has always claimed to do (§5 watcher semantics, on demand).

    Args:
        request: The incoming FastAPI request.
        followed_id: Rowid of the ``followed_series`` row.

    Returns:
        ``202`` with :class:`GrabTriggerResponse` (``{"run_uid": "..."}``).

    Raises:
        404: The followed series does not exist.
        409: A priming run for this series is already in flight (the only
            permitted refusal — a running grab does NOT block it).
        500: The runner subprocess failed to spawn.
    """
    return _launch_followed_action(request, followed_id, "prime")


@router.post(
    "/followed/{followed_id}/grab",
    status_code=202,
    response_model=GrabTriggerResponse,
    dependencies=[Depends(require_x_requested_with)],
)
def trigger_followed_grab(request: Request, followed_id: int) -> GrabTriggerResponse:
    """Claim NOW what is already takeable for one follow (« Récupérer maintenant »).

    The counterpart of :func:`trigger_followed_search`: it spawns the ``grab``
    runner alone (``grab --followed-id N``), which takes the items the last
    search already marked ``available`` — no catalog poll, no tracker search.
    That is exactly the action an operator wants on an « À récupérer » item:
    the work is known, only the claiming is pending, and waiting for the 03:20
    cron is the wait §6 forbids.

    Args:
        request: The incoming FastAPI request.
        followed_id: Rowid of the ``followed_series`` row.

    Returns:
        ``202`` with :class:`GrabTriggerResponse` (``{"run_uid": "..."}``).

    Raises:
        404: The followed series does not exist.
        409: A grab for this series is already running (the only permitted
            refusal — a running prime does NOT block it).
        500: The runner subprocess failed to spawn.
    """
    return _launch_followed_action(request, followed_id, "grab")


# ── Spine-driven per-item actions (feature spine-actions, F4) ────────────────────

#: Maps the F4 action to its ``pipeline_run.command`` (and the CLI it runs).
_HASH_ACTIONS = {"rescrape": "acquisition-rescrape", "requeue": "acquisition-requeue"}


def _spawn_hash_runner(run_uid: str, action: str, info_hash: str) -> int:
    """Spawn the acquisition runner scoped to one grab info-hash (F4).

    Args:
        run_uid: The reserved run's unique identifier.
        action: ``"rescrape"`` or ``"requeue"`` (the ``PERSONALSCRAPER_ACQ_COMMAND`` value).
        info_hash: The grab info-hash to scope the action to.

    Returns:
        The pid of the spawned runner process.
    """
    env = {
        **os.environ,
        "PERSONALSCRAPER_RUN_UID": run_uid,
        "PERSONALSCRAPER_ACQ_COMMAND": action,
        "PERSONALSCRAPER_ACQ_INFO_HASH": info_hash,
    }
    logger.info("hash_trigger_spawned", run_uid=run_uid, action=action, info_hash=info_hash)
    proc = subprocess.Popen(
        [sys.executable, "-m", "personalscraper.web.acquisition.runner"],
        start_new_session=True,
        env=env,
    )
    return proc.pid


def _launch_hash_action(request: Request, info_hash: str, action: str) -> GrabTriggerResponse:
    """Reserve + spawn a spine-driven per-item action (rescrape / requeue).

    Mirrors :func:`_launch_followed_action` for an info-hash scope: 404 when the grab is
    not tracked, 409 when the SAME action is already in flight for this item, fail-soft
    finalize on a spawn error.

    Raises:
        HTTPException: 404 (untracked grab), 409 (same action in flight), 500 (spawn failed).
    """
    row_command = _HASH_ACTIONS[action]
    # Canonicalise to the stored lowercase form (the spine lowercases info-hashes) so the
    # 409 idempotence guard and the spawned scope can never diverge by URL casing.
    info_hash = info_hash.lower()
    config = request.app.state.config
    db_path = cast(Path, config.indexer.db_path)

    # 1. Verify the grab is tracked on the spine (404 before any reservation). A manual/
    #    direct item has no row → nothing to act on.
    store = build_acquire_store(config.acquire)
    try:
        row = store.provenance.by_hash(info_hash)
    finally:
        store.close()
    if row is None:
        raise HTTPException(status_code=404, detail="No tracked acquisition for this info-hash")

    options_json = hash_options_json(info_hash)
    # 2. Reject the duplicate of the SAME action on the same item (409).
    _guard_no_running_grab(db_path, options_json, command=row_command)

    # 3. Reserve the run row with the web pid, then spawn the runner.
    run_uid = uuid.uuid4().hex
    writer = PipelineRunWriter(db_path)
    writer.insert(
        run_uid,
        trigger="web",
        dry_run=False,
        pid=os.getpid(),
        kind="maintenance",
        command=row_command,
        options_json=options_json,
        if_absent=True,
    )
    try:
        pid = _spawn_hash_runner(run_uid, action, info_hash)
    except (OSError, ValueError) as exc:
        try:
            writer.finalize(run_uid, "error", error=str(exc))
        except sqlite3.Error:
            logger.warning("hash_trigger_finalize_failed", run_uid=run_uid, command=row_command)
        logger.error("hash_trigger_spawn_failed", run_uid=run_uid, command=row_command, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to spawn {row_command} runner") from exc
    if isinstance(pid, int):
        try:
            writer.update_pid(run_uid, pid)
        except sqlite3.Error:
            logger.warning("hash_trigger_update_pid_failed", run_uid=run_uid, command=row_command)
    return GrabTriggerResponse(run_uid=run_uid)


@router.post(
    "/journeys/{info_hash}/rescrape",
    status_code=202,
    response_model=GrabTriggerResponse,
    dependencies=[Depends(require_x_requested_with)],
)
def trigger_journey_rescrape(request: Request, info_hash: str) -> GrabTriggerResponse:
    """Re-scrape one tracked staging item, seeded from its grab identity (F4, « Re-scraper »).

    Returns 202 with the run_uid. 404 when untracked, 409 when a re-scrape for this item is
    already in flight, 500 on spawn failure.
    """
    return _launch_hash_action(request, info_hash, "rescrape")


@router.post(
    "/journeys/{info_hash}/requeue",
    status_code=202,
    response_model=GrabTriggerResponse,
    dependencies=[Depends(require_x_requested_with)],
)
def trigger_journey_requeue(request: Request, info_hash: str) -> GrabTriggerResponse:
    """Requeue one item's wanted row back to pending (F4, « Requeue »).

    Returns 202 with the run_uid. 404 when untracked, 409 when a requeue for this item is
    already in flight, 500 on spawn failure.
    """
    return _launch_hash_action(request, info_hash, "requeue")
