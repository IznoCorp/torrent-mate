"""Rescrape by medium: one medium, named by a provider id, launched through the maintenance path."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from personalscraper.app.errors import (
    AppInternalError,
    AppNotFound,
    AppPreconditionRequired,
    RefusalCode,
)
from personalscraper.app.library.identity import Provider
from personalscraper.app.library.service import RescrapeAccepted
from personalscraper.app.maintenance import service as maintenance_service
from personalscraper.app.maintenance.registry import REGISTRY, canonical_options_json
from personalscraper.core.identity import MediaRef
from tests.unit.app.library.world import World

_RUNNER_PID = 4242


@pytest.fixture
def spawned(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str, bool]]:
    """Replace the runner spawn: no process starts, every launch is recorded.

    Args:
        monkeypatch: Pytest's monkeypatch.

    Returns:
        The ``(run_uid, action_id, options_json, dry_run)`` of every spawn, in order.
    """
    calls: list[tuple[str, str, str, bool]] = []

    def fake_spawn(run_uid: str, action_id: str, options_json: str, dry_run: bool) -> int:
        """Record the launch and answer a fixed pid."""
        calls.append((run_uid, action_id, options_json, dry_run))
        return _RUNNER_PID

    monkeypatch.setattr(maintenance_service, "_spawn_runner", fake_spawn)
    return calls


def _runs(index_path: Path) -> list[tuple[str, str, str, int, int]]:
    """Read the reserved maintenance runs.

    Args:
        index_path: ``library.db``.

    Returns:
        ``(run_uid, command, options_json, dry_run, pid)`` per row, by insertion.
    """
    with sqlite3.connect(index_path) as conn:
        return conn.execute(
            "SELECT run_uid, command, options_json, dry_run, pid FROM pipeline_run WHERE kind='maintenance' ORDER BY id"
        ).fetchall()


def test_a_held_movie_is_rescraped_without_a_dry_run(world: World, spawned: list[tuple[str, str, str, bool]]) -> None:
    """A live apply of the per-medium action needs no prior dry-run; the run row is reserved and claimed."""
    movie = world.index.item("Heat", tmdb="949", imdb="tt0113277")
    world.index.movie_file(movie, "films/Heat")

    accepted = world.service.request_rescrape(world.actor, MediaRef(tmdb_id=949))

    assert (accepted.provider, accepted.provider_id, accepted.queued) == (Provider.TMDB, "949", False)
    assert accepted.run_uid is not None
    options = canonical_options_json({"item_id": movie})
    assert spawned == [(accepted.run_uid, "library-rescrape-item", options, False)]
    assert _runs(world.index.path) == [(accepted.run_uid, "library-rescrape-item", options, 0, _RUNNER_PID)]


def test_a_show_is_rescraped_by_its_tvdb_id(world: World, spawned: list[tuple[str, str, str, bool]]) -> None:
    """A show is addressed by its TVDB id and answered under it."""
    show = world.index.item("Holes", kind="show", tvdb="81189", tmdb="1396")
    world.index.episodes(show, 1, [1, 2])

    accepted = world.service.request_rescrape(world.actor, MediaRef(tvdb_id=81189))

    assert (accepted.provider, accepted.provider_id) == (Provider.TVDB, "81189")
    assert [json.loads(call[2]) for call in spawned] == [{"item_id": show}]


def test_an_unknown_id_is_not_found_and_nothing_launches(
    world: World, spawned: list[tuple[str, str, str, bool]]
) -> None:
    """No row holds the id: 404 ``media.not_found``, no run reserved, no spawn."""
    with pytest.raises(AppNotFound) as refused:
        world.service.request_rescrape(world.actor, MediaRef(tmdb_id=1))

    assert refused.value.code is RefusalCode.MEDIA_NOT_FOUND
    assert spawned == []
    assert _runs(world.index.path) == []


def test_holders_without_live_files_are_not_found(world: World, spawned: list[tuple[str, str, str, bool]]) -> None:
    """Rows hold the id but none has a live file (a tombstone, a 0-file phantom): 404, no launch."""
    gone = world.index.item("Gone", tmdb="7")
    world.index.movie_file(gone, "films/Gone", deleted=True)
    world.index.item("Gone", tmdb="7", year=2021)

    with pytest.raises(AppNotFound) as refused:
        world.service.request_rescrape(world.actor, MediaRef(tmdb_id=7))

    assert refused.value.code is RefusalCode.MEDIA_NOT_FOUND
    assert spawned == []


def test_a_held_lock_queues_the_run(world: World, spawned: list[tuple[str, str, str, bool]]) -> None:
    """A live pipeline.lock never refuses: the run is launched and answered as queued."""
    movie = world.index.item("Heat", tmdb="949")
    world.index.movie_file(movie, "films/Heat")
    (world.data_dir / "pipeline.lock").write_text(str(os.getpid()))

    accepted = world.service.request_rescrape(world.actor, MediaRef(tmdb_id=949))

    assert accepted.queued is True
    assert len(spawned) == 1


def test_of_two_rows_only_the_one_with_live_files_is_rescraped(
    world: World, spawned: list[tuple[str, str, str, bool]]
) -> None:
    """A duplicate whose second row is a 0-file phantom rescrapes the row holding the files."""
    world.index.item("Friends", kind="show", tvdb="79168", year=1994)
    held = world.index.item("Friends [UNCUT]", kind="show", tvdb="79168", year=1994)
    world.index.episodes(held, 1, [1])

    accepted = world.service.request_rescrape(world.actor, MediaRef(tvdb_id=79168))

    assert [json.loads(call[2]) for call in spawned] == [{"item_id": held}]
    assert accepted.run_uid == spawned[0][0]


def test_two_rows_with_live_files_are_both_rescraped(world: World, spawned: list[tuple[str, str, str, bool]]) -> None:
    """Both rows hold files: one launch each; the answer names the lowest row's run."""
    first = world.index.item("Friends", kind="show", tvdb="79168", year=1994)
    world.index.episodes(first, 1, [1], folder="series/Friends/Saison 01")
    second = world.index.item("Friends [UNCUT]", kind="show", tvdb="79168", year=1994)
    world.index.episodes(second, 1, [1], folder="series/Friends UNCUT/Saison 01")

    accepted = world.service.request_rescrape(world.actor, MediaRef(tvdb_id=79168))

    assert [json.loads(call[2]) for call in spawned] == [{"item_id": first}, {"item_id": second}]
    assert accepted.run_uid == spawned[0][0]
    assert len({run[0] for run in _runs(world.index.path)}) == 2


def test_a_tmdb_id_held_by_a_film_and_a_show_rescrapes_the_film(
    world: World, spawned: list[tuple[str, str, str, bool]]
) -> None:
    """TMDB's movie and TV id spaces are distinct: a TMDB id names its movie holders first."""
    film = world.index.item("Film", tmdb="500")
    world.index.movie_file(film, "films/Film")
    show = world.index.item("Show", kind="show", tmdb="500")
    world.index.episodes(show, 1, [1])

    world.service.request_rescrape(world.actor, MediaRef(tmdb_id=500))

    assert [json.loads(call[2]) for call in spawned] == [{"item_id": film}]


def test_the_per_medium_action_is_a_write_without_dry_run() -> None:
    """The action the service launches: a live write, one required integer item id."""
    (action,) = [a for a in REGISTRY if a.id == "library-rescrape-item"]

    assert (action.risk, action.dry_run, action.category) == ("write", "unsupported", "analyze")
    assert [(o.name, o.type, o.required) for o in action.options] == [("item_id", "int", True)]


def test_the_per_medium_action_is_reserved_without_a_dry_run(world: World) -> None:
    """The reservation takes no 428 path for the per-medium action."""
    (action,) = [a for a in REGISTRY if a.id == "library-rescrape-item"]

    maintenance_service._reserve_run_row(
        world.index.path,
        run_uid="a" * 32,
        action=action,
        command=action.id,
        options_json=canonical_options_json({"item_id": 1}),
        dry_run=False,
    )

    assert [run[1] for run in _runs(world.index.path)] == ["library-rescrape-item"]


def test_the_library_wide_rescrape_still_demands_a_dry_run(world: World) -> None:
    """The old ``library-rescrape`` is destructive: its live apply still needs a fresh dry-run (428)."""
    (action,) = [a for a in REGISTRY if a.id == "library-rescrape"]

    with pytest.raises(AppPreconditionRequired):
        maintenance_service._reserve_run_row(
            world.index.path,
            run_uid="b" * 32,
            action=action,
            command=action.id,
            options_json=canonical_options_json({"item-id": 1}),
            dry_run=False,
        )

    assert _runs(world.index.path) == []


def test_a_failed_spawn_is_an_internal_refusal_and_finalises_the_row(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner cannot start: 500, and the reserved row never stays ``running``."""
    movie = world.index.item("Heat", tmdb="949")
    world.index.movie_file(movie, "films/Heat")

    def broken_spawn(run_uid: str, action_id: str, options_json: str, dry_run: bool) -> int:
        """Fail as a missing interpreter would."""
        raise OSError("no interpreter")

    monkeypatch.setattr(maintenance_service, "_spawn_runner", broken_spawn)

    with pytest.raises(AppInternalError):
        world.service.request_rescrape(world.actor, MediaRef(tmdb_id=949))

    with sqlite3.connect(world.index.path) as conn:
        assert conn.execute("SELECT outcome FROM pipeline_run").fetchall() == [("error",)]


def _seed_running(index_path: Path, item_id: int) -> None:
    """Reserve a live ``library-rescrape-item`` run for one row, as a runner already started would hold it.

    Args:
        index_path: ``library.db``.
        item_id: The row the running rescrape holds.
    """
    (action,) = [a for a in REGISTRY if a.id == "library-rescrape-item"]
    maintenance_service._reserve_run_row(
        index_path,
        run_uid=f"{item_id:032d}",
        action=action,
        command=action.id,
        options_json=canonical_options_json({"item_id": item_id}),
        dry_run=False,
    )


def test_a_rescrape_already_running_is_accepted_with_its_run_and_nothing_spawns(
    world: World, spawned: list[tuple[str, str, str, bool]]
) -> None:
    """The one holder's rescrape is already running: accepted on that run, no spawn, no second row."""
    movie = world.index.item("Heat", tmdb="949")
    world.index.movie_file(movie, "films/Heat")
    _seed_running(world.index.path, movie)

    accepted = world.service.request_rescrape(world.actor, MediaRef(tmdb_id=949))

    assert accepted == RescrapeAccepted(
        provider=Provider.TMDB, provider_id="949", queued=False, run_uid=f"{movie:032d}"
    )
    assert spawned == []
    assert len(_runs(world.index.path)) == 1


def test_a_running_holder_is_skipped_and_the_other_launched(
    world: World, spawned: list[tuple[str, str, str, bool]]
) -> None:
    """Two live holders, the first already running: the second is launched and its run answered."""
    first = world.index.item("Friends", kind="show", tvdb="79168", year=1994)
    world.index.episodes(first, 1, [1], folder="series/Friends/Saison 01")
    second = world.index.item("Friends [UNCUT]", kind="show", tvdb="79168", year=1994)
    world.index.episodes(second, 1, [1], folder="series/Friends UNCUT/Saison 01")
    _seed_running(world.index.path, first)

    accepted = world.service.request_rescrape(world.actor, MediaRef(tvdb_id=79168))

    assert [json.loads(call[2]) for call in spawned] == [{"item_id": second}]
    assert accepted.run_uid == spawned[0][0]


def test_every_holder_already_running_is_accepted_on_the_lowest_run(
    world: World, spawned: list[tuple[str, str, str, bool]]
) -> None:
    """Both live holders are already running: accepted on the lowest row's run, nothing spawns."""
    first = world.index.item("Friends", kind="show", tvdb="79168", year=1994)
    world.index.episodes(first, 1, [1], folder="series/Friends/Saison 01")
    second = world.index.item("Friends [UNCUT]", kind="show", tvdb="79168", year=1994)
    world.index.episodes(second, 1, [1], folder="series/Friends UNCUT/Saison 01")
    _seed_running(world.index.path, first)
    _seed_running(world.index.path, second)

    accepted = world.service.request_rescrape(world.actor, MediaRef(tvdb_id=79168))

    assert accepted.queued is False
    assert accepted.run_uid == f"{min(first, second):032d}"
    assert spawned == []


def test_a_second_spawn_failing_is_internal_and_the_first_run_stays(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second holder's runner cannot start: 500, the first holder's run stays recorded and live."""
    first = world.index.item("Friends", kind="show", tvdb="79168", year=1994)
    world.index.episodes(first, 1, [1], folder="series/Friends/Saison 01")
    second = world.index.item("Friends [UNCUT]", kind="show", tvdb="79168", year=1994)
    world.index.episodes(second, 1, [1], folder="series/Friends UNCUT/Saison 01")
    spawns: list[str] = []

    def second_fails(run_uid: str, action_id: str, options_json: str, dry_run: bool) -> int:
        """Start the first runner, fail the second as a missing interpreter would."""
        spawns.append(options_json)
        if len(spawns) == 2:
            raise OSError("no interpreter")
        return _RUNNER_PID

    monkeypatch.setattr(maintenance_service, "_spawn_runner", second_fails)

    with pytest.raises(AppInternalError):
        world.service.request_rescrape(world.actor, MediaRef(tvdb_id=79168))

    with sqlite3.connect(world.index.path) as conn:
        rows = conn.execute("SELECT options_json, outcome, pid FROM pipeline_run ORDER BY id").fetchall()
    assert rows == [
        (canonical_options_json({"item_id": first}), "running", _RUNNER_PID),
        (canonical_options_json({"item_id": second}), "error", rows[1][2]),
    ]
