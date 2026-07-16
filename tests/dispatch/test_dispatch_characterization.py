"""Characterization pins for the dispatch template entry points (P0.4).

These tests freeze the CURRENT, pre-refactor behaviour of the two dispatch
entry points before any code moves in the ``solidify`` feature:

- :func:`personalscraper.dispatch._movie.dispatch_movie` — *replace* semantics.
- :func:`personalscraper.dispatch._tv.dispatch_tvshow` — *merge* semantics.

They are behavioural goldens, not aspirational specs: whatever the code does
today is what they assert. Three observable surfaces are pinned per entry point
where applicable:

1. **Destination path computation** — disk choice (most-free for new media,
   same-disk for existing), the category sub-folder, and the canonical folder
   name.
2. **``existing_action`` reporting** — ``"moved"`` (new), ``"replaced"``
   (movie), ``"merged"`` (TV) exactly as emitted on ``DispatchResult.action``.
3. **Journal side-effect PARITY (F1)** — a movie *replace* AND a TV
   *merge-overwrite* each write a destructive-journal ``overwrite`` row. The two
   TV pins encode the POST-F1 expectation and are ``xfail(strict=True)`` until
   the P2.2/P2.3 dispatch template routes both destruction paths through the
   shared journal call (DESIGN §6/§7 F1, plan phase-02); they flip loudly then.
   An *add-only* merge (no episode overwritten) stays non-journaled — the trace
   is for destructions only — so that case is deliberately not pinned here.
4. **Orphan / tmp hygiene** — no ``_tmp_dispatch_*`` / ``.new.tmp`` /
   ``.old.tmp`` / ``.merge_backup`` residue survives a successful dispatch, and
   the staging source folder is consumed.

The dispatch entry points are exercised DIRECTLY (a real :class:`Dispatcher`
over a real :class:`EventBus`), mirroring the fixture patterns of
``tests/integration/test_dispatch_{new,replace,merge}.py`` and the unit setup in
``tests/dispatch/test_dispatcher.py`` — tmp_path-simulated staging + storage
disks, a DB-backed :class:`MediaIndex`, and real rsync transfers of tiny files.

Non-deterministic fields (absolute tmp_path prefixes, journal timestamps) are
normalized before comparison so the goldens are stable (complete-golden rule).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch._movie import dispatch_movie
from personalscraper.dispatch._tv import dispatch_tvshow
from personalscraper.dispatch._types import DispatchResult
from personalscraper.dispatch.dispatcher import Dispatcher
from personalscraper.dispatch.media_index import IndexEntry, MediaIndex
from personalscraper.indexer.destructive_journal import list_recent

_GB = 1024**3


# ---------------------------------------------------------------------------
# Infrastructure fixtures (mirror tests/integration/conftest.py, kept local so
# the file is self-contained in the tests/dispatch/ tier).
# ---------------------------------------------------------------------------


@pytest.fixture()
def _rsync_available() -> None:
    """Skip when rsync is absent — the Dispatcher requires it at construction.

    Mirrors ``tests/integration/conftest.py::rsync_available``. The dispatch
    transfer primitives (``_move_new`` / ``replace`` / ``merge``) shell out to
    real rsync, so a missing binary makes these characterization pins
    unexercisable rather than failing.
    """
    if shutil.which("rsync") is None:
        pytest.skip("rsync not available on this system")


@pytest.fixture()
def char_disks(tmp_path: Path) -> list[Path]:
    """Build four fake disk roots (``Disk1``…``Disk4``) under tmp_path.

    Args:
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        List of four existing directory paths used as storage disk roots.
    """
    disks: list[Path] = []
    for i in range(1, 5):
        d = tmp_path / f"Disk{i}"
        d.mkdir(parents=True, exist_ok=True)
        disks.append(d)
    return disks


@pytest.fixture()
def char_config(test_config: Config, char_disks: list[Path]) -> Config:
    """Compose a validated Config wired to the fixture disks for dispatch.

    Derived from the shared ``test_config`` (11-category base). MOVIES is
    accepted on disk1/disk2/disk3 so the new-media disk-choice among multiple
    eligible disks is exercisable; TV_SHOWS stays on disk1. ``indexer.db_path``
    is pinned under ``paths.data_dir`` so the dispatcher, the destructive
    journal, and the assertions share one tmp_path-scoped SQLite file. Disk
    thresholds are zeroed so tiny fixture items are never gated on free space.

    Args:
        test_config: Synthetic Config fixture (tests/fixtures/config.py).
        char_disks: Four fake disk root paths.

    Returns:
        Validated Config with disks pointing at ``char_disks`` and a pinned
        indexer DB path.
    """
    new_disks = [
        DiskConfig(id="disk1", path=char_disks[0], categories=[CID.MOVIES, CID.TV_SHOWS]),
        DiskConfig(id="disk2", path=char_disks[1], categories=[CID.MOVIES, CID.ANIME, CID.MOVIES_ANIMATION]),
        DiskConfig(
            id="disk3",
            path=char_disks[2],
            categories=[CID.MOVIES, CID.MOVIES_DOCUMENTARY, CID.TV_SHOWS_ANIMATION],
        ),
        DiskConfig(
            id="disk4",
            path=char_disks[3],
            categories=[CID.TV_SHOWS_DOCUMENTARY, CID.AUDIOBOOKS, CID.STANDUP, CID.THEATER, CID.TV_PROGRAMS],
        ),
    ]
    new_indexer = test_config.indexer.model_copy(update={"db_path": test_config.paths.data_dir / "library.db"})
    new_thresholds = test_config.thresholds.model_copy(
        update={"min_free_space_staging_gb": 0, "min_free_space_disk_gb": 0.0}
    )
    config = test_config.model_copy(update={"disks": new_disks, "indexer": new_indexer, "thresholds": new_thresholds})
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture()
def char_db_path(char_config: Config) -> Path:
    """Return the resolved (non-None) indexer DB path pinned by ``char_config``.

    Narrows the ``Path | None`` model field to ``Path`` for the index/journal
    call sites — ``char_config`` always pins it under ``paths.data_dir``.

    Args:
        char_config: Dispatch-wired Config fixture.

    Returns:
        The tmp_path-scoped ``library.db`` path shared by the dispatcher, the
        destructive journal, and the assertions.
    """
    db_path = char_config.indexer.db_path
    assert db_path is not None, "char_config must pin indexer.db_path"
    return db_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_media_dir(parent: Path, name: str, files: dict[str, bytes]) -> Path:
    """Create ``parent/name`` and populate it with ``files`` (relative → bytes).

    Args:
        parent: Directory under which the media folder is created.
        name: Media folder basename (e.g. ``"Oppenheimer (2023)"``).
        files: Mapping of POSIX-relative file paths to their byte contents;
            intermediate directories are created as needed.

    Returns:
        Path to the created media directory.
    """
    media_dir = parent / name
    media_dir.mkdir(parents=True, exist_ok=True)
    for rel, data in files.items():
        target = media_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return media_dir


def _seed_index(db_path: Path, entry: IndexEntry) -> None:
    """Seed the DB-backed MediaIndex with a single existing-media entry.

    Args:
        db_path: Path to the tmp_path-scoped library SQLite file.
        entry: The IndexEntry to persist so ``_resolve_existing_on_filesystem``
            finds the on-disk copy and routes to replace/merge instead of new.
    """
    index = MediaIndex(db_path, event_bus=EventBus())
    try:
        index.add(entry)
    finally:
        index.close()


def _snapshot(result: DispatchResult, tmp_root: Path) -> dict[str, Any]:
    """Return a tmp_path-normalized golden view of a DispatchResult.

    The absolute tmp_path prefix (non-deterministic across runs) is stripped so
    the destination becomes a stable POSIX-relative string; ``action``,
    ``disk``, and ``reason`` are pinned verbatim.

    Args:
        result: The DispatchResult returned by an entry point.
        tmp_root: The test's ``tmp_path`` root to relativize the destination.

    Returns:
        A JSON-like dict with the deterministic, comparable fields.
    """
    destination = result.destination.relative_to(tmp_root).as_posix() if result.destination is not None else None
    return {
        "action": result.action,
        "disk": result.disk,
        "destination": destination,
        "reason": result.reason,
    }


def _patch_disk_usage(monkeypatch: pytest.MonkeyPatch, free_by_path: dict[str, int]) -> None:
    """Monkeypatch ``shutil.disk_usage`` at the disk_scanner call-site.

    Fake disks share one real filesystem, so their true free space is identical
    and ``max()`` tie-breaking would be non-deterministic. This forces distinct
    per-disk free-space values so the most-free-disk selection is deterministic
    and load-bearing (mirrors ``tests/integration/test_dispatch_new.py``).

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        free_by_path: Mapping of disk-root path string → synthetic free bytes.
            Any path not under a listed root falls through to the real call.
    """
    real_disk_usage = shutil.disk_usage

    def _fake(path: Any) -> Any:
        path_str = str(path)
        for disk_path, free_bytes in free_by_path.items():
            if path_str == disk_path or path_str.startswith(disk_path + "/"):

                class _Usage:
                    total = 1000 * _GB
                    free = free_bytes
                    used = total - free

                return _Usage()
        return real_disk_usage(path)

    monkeypatch.setattr("personalscraper.dispatch.disk_scanner.shutil.disk_usage", _fake)


def _residue(disk_root: Path) -> list[Path]:
    """Return any leftover dispatch temp/backup artifacts under ``disk_root``.

    Args:
        disk_root: A storage disk root to scan recursively.

    Returns:
        Paths of ``_tmp_dispatch_*``, ``*.new.tmp``, ``*.old.tmp`` and
        ``.merge_backup`` residue; empty when the disk is clean.
    """
    return [
        *disk_root.rglob("_tmp_dispatch_*"),
        *disk_root.rglob("*.new.tmp"),
        *disk_root.rglob("*.old.tmp"),
        *disk_root.rglob(".merge_backup"),
    ]


# ---------------------------------------------------------------------------
# dispatch_movie — new-media placement (most-free disk)
# ---------------------------------------------------------------------------


def test_dispatch_movie_new_media_pins_most_free_disk(
    char_config: Config,
    char_db_path: Path,
    char_disks: list[Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _rsync_available: None,
) -> None:
    """New movie routes to the most-free eligible disk; destination pinned.

    Disk free space is forced to disk1=100 GB, disk2=500 GB, disk3=200 GB,
    disk4=50 GB; all of disk1/2/3 accept MOVIES, so disk2 (most free) must win.
    Pins the full normalized result (action ``"moved"``, disk ``"disk2"``,
    ``<Disk2>/cat_movies/<name>`` destination), source consumption, and clean
    temp hygiene on the winning disk.

    Args:
        char_config: Dispatch-wired Config fixture.
        char_db_path: Resolved indexer DB path shared with the dispatcher.
        char_disks: Four fake disk roots.
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture.
        _rsync_available: Skips when rsync is missing.
    """
    _patch_disk_usage(
        monkeypatch,
        {
            str(char_disks[0]): 100 * _GB,
            str(char_disks[1]): 500 * _GB,
            str(char_disks[2]): 200 * _GB,
            str(char_disks[3]): 50 * _GB,
        },
    )

    name = "Oppenheimer (2023)"
    source = _make_media_dir(tmp_path / "staging_src", name, {"Oppenheimer.mkv": b"\x00" * 4096})

    index = MediaIndex(char_db_path, event_bus=EventBus())
    dispatcher = Dispatcher(char_config, Settings(), index, event_bus=EventBus())
    try:
        result = dispatch_movie(dispatcher, source, CID.MOVIES)
    finally:
        index.close()

    movies_folder = char_config.category(CID.MOVIES).folder_name
    assert _snapshot(result, tmp_path) == {
        "action": "moved",
        "disk": "disk2",
        "destination": f"Disk2/{movies_folder}/{name}",
        "reason": None,
    }
    # Destination materialized on the winning disk; staging source consumed.
    assert (char_disks[1] / movies_folder / name / "Oppenheimer.mkv").exists()
    assert not source.exists()
    # No temp residue anywhere on the winning disk.
    assert _residue(char_disks[1]) == []


# ---------------------------------------------------------------------------
# dispatch_movie — replace existing (same disk) + destructive journal
# ---------------------------------------------------------------------------


def test_dispatch_movie_replace_pins_destination_action_and_journal(
    char_config: Config,
    char_db_path: Path,
    char_disks: list[Path],
    tmp_path: Path,
    _rsync_available: None,
) -> None:
    """Existing movie is replaced in place; a journal ``overwrite`` row lands.

    An on-disk copy of ``Dune (2021)`` pre-exists on disk1 and is seeded into
    the index, so ``dispatch_movie`` routes to replace (not new). Neither folder
    carries an NFO, so the §7 identity guard fails open and the replace
    proceeds. Pins: destination = the existing on-disk path (same disk), action
    ``"replaced"``, the old file removed / new file present, clean temp hygiene,
    and — critically — the destructive journal records exactly one ``overwrite``
    row by actor ``dispatch`` for the destination.

    Args:
        char_config: Dispatch-wired Config fixture.
        char_db_path: Resolved indexer DB path shared with the dispatcher.
        char_disks: Four fake disk roots.
        tmp_path: Pytest temporary directory.
        _rsync_available: Skips when rsync is missing.
    """
    name = "Dune (2021)"
    movies_folder = char_config.category(CID.MOVIES).folder_name

    existing = _make_media_dir(char_disks[0] / movies_folder, name, {"old_version.mkv": b"x" * 16})
    _seed_index(
        char_db_path,
        IndexEntry(name=name, disk="disk1", category=CID.MOVIES, path=str(existing), media_type="movie"),
    )

    source = _make_media_dir(tmp_path / "staging_src", name, {"new_version.mkv": b"y" * 4096})

    index = MediaIndex(char_db_path, event_bus=EventBus())
    dispatcher = Dispatcher(char_config, Settings(), index, event_bus=EventBus())
    try:
        result = dispatch_movie(dispatcher, source, CID.MOVIES)
    finally:
        index.close()

    dest_rel = f"Disk1/{movies_folder}/{name}"
    assert _snapshot(result, tmp_path) == {
        "action": "replaced",
        "disk": "disk1",
        "destination": dest_rel,
        "reason": None,
    }
    # Old content gone, new content present on the SAME disk it existed on.
    assert not (existing / "old_version.mkv").exists()
    assert (existing / "new_version.mkv").exists()
    assert not source.exists()
    assert _residue(char_disks[0]) == []

    # Journal side-effect: a movie replace records ONE destructive overwrite row.
    rows = list_recent(char_db_path)
    overwrite_rows = [r for r in rows if r["op"] == "overwrite" and str(r["path"]) == str(existing)]
    assert len(overwrite_rows) == 1, f"movie replace must journal exactly one overwrite; got {rows}"
    assert overwrite_rows[0]["actor"] == "dispatch"


# ---------------------------------------------------------------------------
# dispatch_tvshow — merge-OVERWRITE existing (same disk); journals overwrite (F1)
#
# Pre-F1 the TV merge path did not journal at all (movie replace did — the
# asymmetry the P0 pin used to freeze). DESIGN §6/§7 F1 routes BOTH destruction
# paths (movie replace + TV merge-overwrite) through the shared destructive
# journal in the P2.2/P2.3 template. The two tests below encode that POST-F1
# expectation and are xfail(strict=True) until the template lands — so the
# intermediate gates stay green now, and the xfail flips loudly (xpass under
# strict = failure) the moment P2.3 wires the journal call. Two distinct
# destruction sub-paths are covered: a same-filename rsync overwrite and a
# re-scrape rename purge (different filename, same season/episode key).
# ---------------------------------------------------------------------------

_F1_XFAIL_REASON = "F1: TV merge journal lands with the P2.2/P2.3 template (DESIGN §6/§7 F1, plan phase-02)"


@pytest.mark.xfail(strict=True, reason=_F1_XFAIL_REASON)
def test_dispatch_tvshow_merge_overwrite_pins_destination_action_and_journal(
    char_config: Config,
    char_db_path: Path,
    char_disks: list[Path],
    tmp_path: Path,
    _rsync_available: None,
) -> None:
    """Existing episode is OVERWRITTEN in a merge; one journal ``overwrite`` row lands.

    Rewritten from the pre-F1 no-journal pin (which merged an *add-only* episode
    and therefore destroyed nothing). Here an on-disk ``Fallout (2024)`` with
    ``Saison 01/episode1.mkv`` pre-exists on disk1 and is seeded into the index,
    so ``dispatch_tvshow`` routes to merge (not new). The staging copy carries a
    ``Saison 01/episode1.mkv`` under the SAME filename with new bytes, so the
    rsync merge OVERWRITES the on-disk episode — a genuine destruction of the
    previous content. Pins: destination = the existing on-disk path (same disk),
    action ``"merged"``, the episode's bytes replaced, clean temp/backup
    hygiene, and — at parity with the movie replace above (F1) — exactly one
    destructive ``overwrite`` row by actor ``dispatch`` for the show folder.

    Args:
        char_config: Dispatch-wired Config fixture.
        char_db_path: Resolved indexer DB path shared with the dispatcher.
        char_disks: Four fake disk roots.
        tmp_path: Pytest temporary directory.
        _rsync_available: Skips when rsync is missing.
    """
    name = "Fallout (2024)"
    tv_folder = char_config.category(CID.TV_SHOWS).folder_name

    existing = _make_media_dir(char_disks[0] / tv_folder, name, {"Saison 01/episode1.mkv": b"x" * 16})
    _seed_index(
        char_db_path,
        IndexEntry(name=name, disk="disk1", category=CID.TV_SHOWS, path=str(existing), media_type="tvshow"),
    )

    # Same episode filename with new bytes → the rsync merge overwrites the
    # on-disk copy, destroying the previous version (which F1 must journal).
    source = _make_media_dir(tmp_path / "staging_src", name, {"Saison 01/episode1.mkv": b"y" * 4096})

    index = MediaIndex(char_db_path, event_bus=EventBus())
    dispatcher = Dispatcher(char_config, Settings(), index, event_bus=EventBus())
    try:
        result = dispatch_tvshow(dispatcher, source, CID.TV_SHOWS)
    finally:
        index.close()

    assert _snapshot(result, tmp_path) == {
        "action": "merged",
        "disk": "disk1",
        "destination": f"Disk1/{tv_folder}/{name}",
        "reason": None,
    }
    # The on-disk episode now carries the new bytes (old version destroyed);
    # source consumed; no temp/backup residue survives.
    assert (existing / "Saison 01" / "episode1.mkv").read_bytes() == b"y" * 4096
    assert not source.exists()
    assert _residue(char_disks[0]) == []

    # F1 (flipped from the pre-F1 no-journal pin): a TV merge that OVERWRITES an
    # existing episode records exactly one destructive ``overwrite`` row by actor
    # ``dispatch`` for the show folder — parity with the movie replace above
    # (DESIGN §6/§7 F1). Fails today (the TV path never journals); the P2.2/P2.3
    # template makes it pass, at which point the strict xfail flips.
    rows = list_recent(char_db_path)
    overwrite_rows = [r for r in rows if r["op"] == "overwrite" and str(r["path"]) == str(existing)]
    assert len(overwrite_rows) == 1, f"F1: TV merge-overwrite must journal exactly one overwrite; got {rows}"
    assert overwrite_rows[0]["actor"] == "dispatch"


@pytest.mark.xfail(strict=True, reason=_F1_XFAIL_REASON)
def test_dispatch_tvshow_merge_overwrite_rescrape_rename_journals(
    char_config: Config,
    char_db_path: Path,
    char_disks: list[Path],
    tmp_path: Path,
    _rsync_available: None,
) -> None:
    """Re-scrape rename overwrite (same S/E key, new filename) journals one row.

    New F1 regression covering the subtler destruction path: the merge's
    ``purge_episode_conflicts`` step deletes an on-disk episode whose
    ``(season, episode)`` key matches a source episode under a DIFFERENT
    filename (a re-scrape swapping the localised title segment — EN ``S04E06 -
    YOU LOOK HORRIBLE`` vs FR ``S04E06 - T'AS UNE SALE GUEULE``). The old file is
    destroyed and replaced by the source version, so exactly one destructive
    ``overwrite`` row must be journaled (F1) — just like the same-filename
    overwrite above and the movie replace.

    Args:
        char_config: Dispatch-wired Config fixture.
        char_db_path: Resolved indexer DB path shared with the dispatcher.
        char_disks: Four fake disk roots.
        tmp_path: Pytest temporary directory.
        _rsync_available: Skips when rsync is missing.
    """
    name = "Fallout (2024)"
    tv_folder = char_config.category(CID.TV_SHOWS).folder_name

    old_ep = "Saison 01/S04E06 - YOU LOOK HORRIBLE.mkv"
    new_ep = "Saison 01/S04E06 - T'AS UNE SALE GUEULE.mkv"
    existing = _make_media_dir(char_disks[0] / tv_folder, name, {old_ep: b"x" * 16})
    _seed_index(
        char_db_path,
        IndexEntry(name=name, disk="disk1", category=CID.TV_SHOWS, path=str(existing), media_type="tvshow"),
    )

    source = _make_media_dir(tmp_path / "staging_src", name, {new_ep: b"y" * 4096})

    index = MediaIndex(char_db_path, event_bus=EventBus())
    dispatcher = Dispatcher(char_config, Settings(), index, event_bus=EventBus())
    try:
        result = dispatch_tvshow(dispatcher, source, CID.TV_SHOWS)
    finally:
        index.close()

    assert _snapshot(result, tmp_path) == {
        "action": "merged",
        "disk": "disk1",
        "destination": f"Disk1/{tv_folder}/{name}",
        "reason": None,
    }
    # The old-titled episode is gone (destroyed by the conflict purge); the
    # re-scraped filename is the sole S04E06 on disk; source consumed; clean.
    assert not (existing / "Saison 01" / "S04E06 - YOU LOOK HORRIBLE.mkv").exists()
    assert (existing / "Saison 01" / "S04E06 - T'AS UNE SALE GUEULE.mkv").exists()
    assert not source.exists()
    assert _residue(char_disks[0]) == []

    # F1: the destroyed on-disk episode is journaled as exactly one ``overwrite``
    # row by actor ``dispatch`` for the show folder. Fails today; the P2.2/P2.3
    # template lands the journal call (DESIGN §6/§7 F1), flipping the strict xfail.
    rows = list_recent(char_db_path)
    overwrite_rows = [r for r in rows if r["op"] == "overwrite" and str(r["path"]) == str(existing)]
    assert len(overwrite_rows) == 1, f"F1: re-scrape rename overwrite must journal exactly one overwrite; got {rows}"
    assert overwrite_rows[0]["actor"] == "dispatch"
