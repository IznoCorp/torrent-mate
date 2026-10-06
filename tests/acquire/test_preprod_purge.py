"""Tests for the preprod purge (``acquire.preprod_purge``).

The preprod shares prod's torrent client in its own category. Each night it
deletes the torrents it owns whose seed obligation is written as met, and keeps
every other one, saying why. Fake client, real store over a temp
``acquire-staging.db``, a recording journal. ``tmp_path`` is never a mount
point, so the guard's ``is_mounted`` is patched; the Config is built before the
environment is switched to ``staging``.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from personalscraper.acquire import preprod_purge
from personalscraper.acquire.domain import SeedObligation
from personalscraper.acquire.events import PreprodPurgeCompleted
from personalscraper.acquire.preprod_purge import (
    PurgeDecision,
    PurgeVerdict,
    _purgeable_without_obligation,
    purge_preprod_downloads,
)
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api.torrent._base import TorrentItem
from personalscraper.conf import ids as CID
from personalscraper.conf import sandbox_guard
from personalscraper.conf.environment import Environment
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.conf.models.api_config import (
    TorrentClientEntry,
    TorrentConfig,
    TorrentScope,
    TrackerConfig,
    TrackerEconomyConfig,
    TrackerProviderConfig,
)
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.sandbox_guard import SandboxGuardError
from personalscraper.core.event_bus import Event, EventBus
from personalscraper.core.tags import SEED_PURE
from tests.fixtures.config import CANONICAL_STAGING_DIRS

_NOW = 1_800_000_000
_CATEGORY = "tm-preprod"
_TAGS = ["c411", "tm-preprod", SEED_PURE]
_MARKER = sandbox_guard.root_marker(Environment.STAGING)


class FakeClient:
    """A torrent client listing fixed completed torrents and recording deletions."""

    def __init__(
        self,
        items: list[TorrentItem],
        *,
        list_error: Exception | None = None,
        delete_errors: dict[str, Exception] | None = None,
    ) -> None:
        """Store the canned torrents and the errors to raise.

        Args:
            items: Completed torrents the client holds.
            list_error: When set, ``get_completed`` raises it.
            delete_errors: Per-hash errors ``delete`` raises.
        """
        self.items = items
        self.list_error = list_error
        self.delete_errors = delete_errors or {}
        self.calls: list[str] = []
        self.deleted: list[tuple[str, bool]] = []

    def get_completed(self) -> list[TorrentItem]:
        """Record the call; raise the configured error or return the torrents."""
        self.calls.append("get_completed")
        if self.list_error is not None:
            raise self.list_error
        return list(self.items)

    def delete(self, hash: str, *, delete_files: bool = False) -> None:
        """Record the call; raise the configured error for that hash."""
        self.calls.append("delete")
        if hash in self.delete_errors:
            raise self.delete_errors[hash]
        self.deleted.append((hash, delete_files))


class Roots:
    """The temp preprod roots: one storage disk, the staging dir and the download root."""

    def __init__(self, tmp_path: Path) -> None:
        """Create the three marked roots under *tmp_path*.

        Args:
            tmp_path: Per-test directory.
        """
        self.disk = self._marked(tmp_path / "disk")
        self.staging = self._marked(tmp_path / "staging")
        self.download = self._marked(tmp_path / "download")
        self.data = tmp_path / "data"
        self.data.mkdir()

    @staticmethod
    def _marked(root: Path) -> Path:
        """Create *root* with the preprod marker and return it."""
        root.mkdir()
        (root / _MARKER).write_text("", encoding="utf-8")
        return root


@pytest.fixture
def roots(tmp_path: Path) -> Roots:
    """Return the temp preprod roots."""
    return Roots(tmp_path)


@pytest.fixture
def mounted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every path reads as mounted."""
    monkeypatch.setattr(sandbox_guard, "is_mounted", lambda path: True)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real acquire store on a temp ``acquire-staging.db``, closed afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire-staging.db"))
    try:
        yield s
    finally:
        s.close()


def _config(roots: Roots, scope: TorrentScope | None | str = "default") -> Config:
    """Build the preprod Config over *roots* (built in prod, before the env switch).

    Args:
        roots: The temp roots.
        scope: The client scope; ``"default"`` builds the preprod scope over the download root.

    Returns:
        The Config, with a ``c411`` tracker holding an economy block and a ``tr4ker`` one without.
    """
    if scope == "default":
        scope = TorrentScope(category=_CATEGORY, download_root=roots.download)
    economy = TrackerEconomyConfig(target_ratio=1.0, min_seed_time=259_200)
    return Config(
        paths=PathConfig(torrent_complete_dir=roots.download, staging_dir=roots.staging, data_dir=roots.data),
        disks=[DiskConfig(id="disk_a", path=roots.disk, categories=list(CID.BUILTIN_CATEGORY_IDS))],
        staging_dirs=CANONICAL_STAGING_DIRS,
        torrent=TorrentConfig(active="qbittorrent", clients={"qbittorrent": TorrentClientEntry(scope=scope)}),  # type: ignore[arg-type]
        tracker=TrackerConfig(
            providers={
                "c411": TrackerProviderConfig(enabled=True, economy=economy),
                "tr4ker": TrackerProviderConfig(enabled=True),
            }
        ),
    )


@pytest.fixture
def staging(monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    """Return the switch that puts the process in ``staging`` (called once the Config is built)."""
    return lambda: monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")


def _item(
    roots: Roots,
    info_hash: str,
    *,
    category: str = _CATEGORY,
    tags: list[str] | None = None,
    save_path: str | None = None,
    content_path: Path | None | str = "default",
) -> TorrentItem:
    """Build a completed torrent saved under the download root by default."""
    if content_path == "default":
        content_path = roots.download / f"Release.{info_hash}"
    return TorrentItem(
        hash=info_hash,
        name=f"Release.{info_hash}",
        size_bytes=1024,
        progress=1.0,
        state="uploading",
        content_path=content_path,  # type: ignore[arg-type]
        category=category,
        tags=list(_TAGS) if tags is None else tags,
        save_path=str(roots.download) if save_path is None else save_path,
    )


def _oblige(store: ConcreteAcquireStore, info_hash: str, *, met: bool) -> int:
    """Insert a C411 obligation, met or not, and return its id."""
    return store.seed.add(
        SeedObligation(
            info_hash=info_hash,
            source_tracker="c411",
            min_seed_time_s=259_200,
            min_ratio=1.0,
            added_at=_NOW - 400_000,
            satisfied_at=_NOW - 10 if met else None,
        )
    )


def _released_at(store: ConcreteAcquireStore, obligation_id: int) -> int | None:
    """Read one obligation's ``released_at`` back."""
    conn = sqlite3.connect(store._db_path)
    try:
        return conn.execute("SELECT released_at FROM seed_obligation WHERE id = ?", (obligation_id,)).fetchone()[0]  # type: ignore[no-any-return]
    finally:
        conn.close()


class Run:
    """One purge run's inputs and what it did."""

    def __init__(self) -> None:
        """Start with an empty journal and no event."""
        self.journal: list[Path] = []
        self.events: list[Event] = []
        self.bus = EventBus()
        self.bus.subscribe(PreprodPurgeCompleted, self.events.append)

    def __call__(
        self,
        store: ConcreteAcquireStore,
        client: FakeClient,
        config: Config,
        *,
        dry_run: bool = False,
        max_purged: int = 20,
    ) -> list[PurgeDecision]:
        """Run one purge with the recording journal and bus."""
        return purge_preprod_downloads(
            store,  # type: ignore[arg-type]
            client,  # type: ignore[arg-type]
            config,
            now=_NOW,
            dry_run=dry_run,
            max_purged=max_purged,
            event_bus=self.bus,
            journal=self.journal.append,
        )


@pytest.fixture
def run() -> Run:
    """Return a fresh purge runner."""
    return Run()


def _verdicts(decisions: list[PurgeDecision]) -> dict[str, PurgeVerdict]:
    """Map each decision's hash to its verdict."""
    return {d.info_hash: d.verdict for d in decisions}


# -- purged ----------------------------------------------------------------------------------------


def test_met_obligation_is_purged_released_and_journaled(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """A met obligation: the client deletes the torrent and its files, the row is released, one journal entry."""
    config = _config(roots)
    oid = _oblige(store, "aaaa", met=True)
    item = _item(roots, "aaaa")
    client = FakeClient([item])
    staging()
    decisions = run(store, client, config)
    assert decisions == [PurgeDecision("aaaa", item.name, PurgeVerdict.PURGED, oid)]
    assert client.deleted == [("aaaa", True)]
    assert _released_at(store, oid) == _NOW
    assert run.journal == [item.content_path]


def test_summary_event_counts_purged_and_kept(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """One ``PreprodPurgeCompleted`` per run carries the purged and kept counts."""
    config = _config(roots)
    _oblige(store, "aaaa", met=True)
    _oblige(store, "bbbb", met=False)
    staging()
    run(store, FakeClient([_item(roots, "aaaa"), _item(roots, "bbbb"), _item(roots, "cccc")]), config)
    assert len(run.events) == 1
    event = run.events[0]
    assert isinstance(event, PreprodPurgeCompleted)
    assert (event.purged, event.kept, event.dry_run) == (1, 2, False)


# -- kept: the obligation --------------------------------------------------------------------------


def test_unmet_obligation_is_kept(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """An obligation not yet met keeps its torrent; nothing is released or journaled."""
    config = _config(roots)
    oid = _oblige(store, "aaaa", met=False)
    client = FakeClient([_item(roots, "aaaa")])
    staging()
    decisions = run(store, client, config)
    assert decisions[0].verdict is PurgeVerdict.KEPT_UNMET
    assert decisions[0].obligation_id == oid
    assert client.deleted == []
    assert _released_at(store, oid) is None
    assert run.journal == []


def test_torrent_without_obligation_is_kept_unknown(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """No obligation row keeps the torrent, even from a tracker with no economy block (O-3 B)."""
    config = _config(roots)
    tr4ker_tags = ["tr4ker", "tm-preprod", SEED_PURE]
    client = FakeClient([_item(roots, "aaaa"), _item(roots, "bbbb", tags=tr4ker_tags)])
    staging()
    decisions = run(store, client, config)
    assert _verdicts(decisions) == {"aaaa": PurgeVerdict.KEPT_UNKNOWN, "bbbb": PurgeVerdict.KEPT_UNKNOWN}
    assert all(d.obligation_id is None for d in decisions)
    assert client.deleted == []
    assert run.journal == []


def test_a_tracker_without_economy_is_not_purgeable_without_obligation() -> None:
    """The one predicate reads O-3 B: no tracker, with or without an economy block, waives the obligation."""
    economy = TrackerEconomyConfig(target_ratio=1.0, min_seed_time=259_200)
    assert _purgeable_without_obligation(None) is False
    assert _purgeable_without_obligation(TrackerProviderConfig(enabled=True)) is False
    assert _purgeable_without_obligation(TrackerProviderConfig(enabled=True, economy=economy)) is False


def test_the_predicate_is_the_one_switch_for_a_torrent_without_obligation(
    roots: Roots,
    mounted: None,
    staging: Callable[[], None],
    store: ConcreteAcquireStore,
    run: Run,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Were the predicate to read O-3 A, a completed tr4ker torrent would be purged with no row to release."""
    config = _config(roots)
    monkeypatch.setattr(
        preprod_purge, "_purgeable_without_obligation", lambda cfg: cfg is not None and cfg.economy is None
    )
    item = _item(roots, "aaaa", tags=["tr4ker", "tm-preprod", SEED_PURE])
    client = FakeClient([item, _item(roots, "bbbb")])
    staging()
    decisions = run(store, client, config)
    assert _verdicts(decisions) == {"aaaa": PurgeVerdict.PURGED, "bbbb": PurgeVerdict.KEPT_UNKNOWN}
    assert client.deleted == [("aaaa", True)]
    assert run.journal == [item.content_path]


def test_unreadable_store_keeps_the_torrent(
    roots: Roots,
    mounted: None,
    staging: Callable[[], None],
    store: ConcreteAcquireStore,
    run: Run,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A store that cannot answer keeps the torrent as unknown and says why."""
    config = _config(roots)
    _oblige(store, "aaaa", met=True)

    def _locked(info_hash: str) -> SeedObligation | None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(store.seed, "find_active_by_hash", _locked)
    client = FakeClient([_item(roots, "aaaa")])
    staging()
    with caplog.at_level(logging.WARNING):
        decisions = run(store, client, config)
    assert decisions[0].verdict is PurgeVerdict.KEPT_UNKNOWN
    assert client.deleted == []
    assert "acquire.preprod_purge.store_unreadable" in caplog.text


# -- kept: the scope -------------------------------------------------------------------------------


def test_another_category_is_never_seen(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """A torrent of another category (prod's) is in no decision and is never deleted, even with a met row."""
    config = _config(roots)
    _oblige(store, "aaaa", met=True)
    client = FakeClient([_item(roots, "aaaa", category="movies")])
    staging()
    assert run(store, client, config) == []
    assert client.deleted == []


def test_missing_instance_tag_is_out_of_scope(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """A torrent in the category but without every instance tag is kept as out of scope."""
    config = _config(roots)
    _oblige(store, "aaaa", met=True)
    _oblige(store, "bbbb", met=True)
    client = FakeClient([_item(roots, "aaaa", tags=["c411", "tm-preprod"]), _item(roots, "bbbb", tags=[])])
    staging()
    decisions = run(store, client, config)
    assert _verdicts(decisions) == {
        "aaaa": PurgeVerdict.KEPT_OUT_OF_SCOPE,
        "bbbb": PurgeVerdict.KEPT_OUT_OF_SCOPE,
    }
    assert client.deleted == []


@pytest.mark.parametrize("where", ["elsewhere", "", "sibling"])
def test_save_path_outside_the_download_root_is_out_of_scope(
    roots: Roots,
    mounted: None,
    staging: Callable[[], None],
    store: ConcreteAcquireStore,
    run: Run,
    tmp_path: Path,
    where: str,
) -> None:
    """A save path outside the download root (or none, or a prefix-sharing sibling) is out of scope."""
    config = _config(roots)
    _oblige(store, "aaaa", met=True)
    save_path = {"elsewhere": str(tmp_path / "elsewhere"), "": "", "sibling": str(roots.download) + "-prod"}[where]
    client = FakeClient([_item(roots, "aaaa", save_path=save_path)])
    staging()
    assert run(store, client, config)[0].verdict is PurgeVerdict.KEPT_OUT_OF_SCOPE
    assert client.deleted == []


def test_a_hash_the_client_lists_in_upper_case_finds_its_lower_case_obligation(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """The store keeps hashes lower-case: an upper-case client hash still finds its met obligation."""
    config = _config(roots)
    oid = _oblige(store, "abcdef", met=True)
    client = FakeClient([_item(roots, "ABCDEF")])
    staging()
    decisions = run(store, client, config)
    assert decisions[0].verdict is PurgeVerdict.PURGED
    assert decisions[0].obligation_id == oid
    assert client.deleted == [("ABCDEF", True)]


def test_an_empty_save_path_is_out_of_scope_even_when_the_working_directory_is_in_the_root(
    roots: Roots,
    mounted: None,
    staging: Callable[[], None],
    store: ConcreteAcquireStore,
    run: Run,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty save path resolves to the working directory: it must be refused, not read as that directory."""
    config = _config(roots)
    _oblige(store, "aaaa", met=True)
    client = FakeClient([_item(roots, "aaaa", save_path="")])
    monkeypatch.chdir(roots.download)
    staging()
    assert run(store, client, config)[0].verdict is PurgeVerdict.KEPT_OUT_OF_SCOPE
    assert client.deleted == []


# -- kept: the roots -------------------------------------------------------------------------------


def test_content_path_outside_the_roots_is_kept_and_the_guard_logged(
    roots: Roots,
    mounted: None,
    staging: Callable[[], None],
    store: ConcreteAcquireStore,
    run: Run,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A content path the guard refuses keeps the torrent; the refusal is logged."""
    config = _config(roots)
    oid = _oblige(store, "aaaa", met=True)
    client = FakeClient([_item(roots, "aaaa", content_path=tmp_path / "medias" / "Film")])
    staging()
    with caplog.at_level(logging.WARNING):
        decisions = run(store, client, config)
    assert decisions[0].verdict is PurgeVerdict.KEPT_OUTSIDE_ROOT
    assert client.deleted == []
    assert _released_at(store, oid) is None
    assert "acquire.preprod_purge.guard_refused" in caplog.text


def test_content_path_under_another_preprod_root_than_the_download_root_is_kept(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """The save path is in the download root but the content path is in the staging root: kept, never deleted."""
    config = _config(roots)
    oid = _oblige(store, "aaaa", met=True)
    client = FakeClient([_item(roots, "aaaa", content_path=roots.staging / "Release.aaaa")])
    staging()
    decisions = run(store, client, config)
    assert decisions[0].verdict is PurgeVerdict.KEPT_OUTSIDE_ROOT
    assert client.deleted == []
    assert _released_at(store, oid) is None
    assert run.journal == []


def test_content_path_escaping_by_symlink_is_kept(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run, tmp_path: Path
) -> None:
    """A content path inside the download root that is a symlink out of every root is kept."""
    config = _config(roots)
    _oblige(store, "aaaa", met=True)
    outside = tmp_path / "medias"
    outside.mkdir()
    link = roots.download / "Release.aaaa"
    link.symlink_to(outside)
    client = FakeClient([_item(roots, "aaaa", content_path=link)])
    staging()
    assert run(store, client, config)[0].verdict is PurgeVerdict.KEPT_OUTSIDE_ROOT
    assert client.deleted == []


def test_unmarked_root_keeps_the_torrent(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """A download root that lost its marker (a dropped disk) keeps everything under it."""
    config = _config(roots)
    _oblige(store, "aaaa", met=True)
    (roots.download / _MARKER).unlink()
    client = FakeClient([_item(roots, "aaaa")])
    staging()
    assert run(store, client, config)[0].verdict is PurgeVerdict.KEPT_OUTSIDE_ROOT
    assert client.deleted == []


def test_content_path_that_is_a_root_itself_is_kept(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """A torrent whose content path is the download root itself is kept: the purge never aims at a whole root."""
    config = _config(roots)
    _oblige(store, "aaaa", met=True)
    client = FakeClient([_item(roots, "aaaa", content_path=roots.download)])
    staging()
    assert run(store, client, config)[0].verdict is PurgeVerdict.KEPT_OUTSIDE_ROOT
    assert client.deleted == []


def test_missing_content_path_is_kept(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """A torrent the client gives no content path for is kept outside the roots."""
    config = _config(roots)
    _oblige(store, "aaaa", met=True)
    client = FakeClient([_item(roots, "aaaa", content_path=None)])
    staging()
    assert run(store, client, config)[0].verdict is PurgeVerdict.KEPT_OUTSIDE_ROOT
    assert client.deleted == []


# -- dry run, cap, client errors -------------------------------------------------------------------


def test_dry_run_deletes_marks_and_journals_nothing(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """``dry_run`` reports what would go and writes nothing anywhere."""
    config = _config(roots)
    oid = _oblige(store, "aaaa", met=True)
    client = FakeClient([_item(roots, "aaaa")])
    staging()
    decisions = run(store, client, config, dry_run=True)
    assert decisions[0].verdict is PurgeVerdict.PURGED
    assert client.deleted == []
    assert "delete" not in client.calls
    assert _released_at(store, oid) is None
    assert run.journal == []
    assert isinstance(run.events[0], PreprodPurgeCompleted)
    assert run.events[0].dry_run is True


def test_cap_purges_at_most_max(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """With N+1 met torrents and a cap of N, N are purged and the last one is kept at the cap."""
    config = _config(roots)
    hashes = ["aaaa", "bbbb", "cccc"]
    ids = {h: _oblige(store, h, met=True) for h in hashes}
    client = FakeClient([_item(roots, h) for h in hashes])
    staging()
    decisions = run(store, client, config, max_purged=2)
    assert _verdicts(decisions) == {
        "aaaa": PurgeVerdict.PURGED,
        "bbbb": PurgeVerdict.PURGED,
        "cccc": PurgeVerdict.KEPT_CAP,
    }
    assert [h for h, _ in client.deleted] == ["aaaa", "bbbb"]
    assert _released_at(store, ids["cccc"]) is None
    assert len(run.journal) == 2


def test_failed_delete_is_kept_and_the_run_continues(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """A delete the client refuses keeps the torrent unmarked and unjournaled; the next one is still purged."""
    config = _config(roots)
    first, second = _oblige(store, "aaaa", met=True), _oblige(store, "bbbb", met=True)
    client = FakeClient([_item(roots, "aaaa"), _item(roots, "bbbb")], delete_errors={"aaaa": RuntimeError("503")})
    staging()
    decisions = run(store, client, config)
    assert _verdicts(decisions) == {"aaaa": PurgeVerdict.KEPT_CLIENT_ERROR, "bbbb": PurgeVerdict.PURGED}
    assert _released_at(store, first) is None
    assert _released_at(store, second) == _NOW
    assert run.journal == [roots.download / "Release.bbbb"]


def test_listing_failure_raises_before_any_delete(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run
) -> None:
    """A client that cannot list raises; nothing is deleted, marked or announced."""
    config = _config(roots)
    oid = _oblige(store, "aaaa", met=True)
    client = FakeClient([_item(roots, "aaaa")], list_error=RuntimeError("unreachable"))
    staging()
    with pytest.raises(RuntimeError, match="unreachable"):
        run(store, client, config)
    assert client.deleted == []
    assert _released_at(store, oid) is None
    assert run.events == []


# -- refused before any client call ----------------------------------------------------------------


@pytest.mark.parametrize("env", ["prod", "dev"])
def test_refused_outside_staging_before_any_client_call(
    roots: Roots,
    mounted: None,
    store: ConcreteAcquireStore,
    run: Run,
    monkeypatch: pytest.MonkeyPatch,
    env: str | None,
) -> None:
    """Outside ``staging`` (prod, dev) the purge refuses before it touches the client."""
    config = _config(roots)
    _oblige(store, "aaaa", met=True)
    monkeypatch.setenv("PERSONALSCRAPER_ENV", env)
    client = FakeClient([_item(roots, "aaaa")])
    with pytest.raises(SandboxGuardError, match="staging"):
        run(store, client, config)
    assert client.calls == []
    assert run.events == []


@pytest.mark.parametrize("scope", ["none", "blank_category", "no_tags", "blank_tag"])
def test_empty_scope_is_refused_before_any_client_call(
    roots: Roots, mounted: None, staging: Callable[[], None], store: ConcreteAcquireStore, run: Run, scope: str
) -> None:
    """No scope, a blank category or an empty tag set or tag refuses the purge before any listing."""
    built = {
        "none": None,
        "blank_category": TorrentScope.model_construct(category=" ", download_root=roots.download),
        "no_tags": TorrentScope.model_construct(category=_CATEGORY, download_root=roots.download, instance_tags=()),
        "blank_tag": TorrentScope.model_construct(
            category=_CATEGORY, download_root=roots.download, instance_tags=("", SEED_PURE)
        ),
    }[scope]
    config = _config(roots, scope=built)
    client = FakeClient([_item(roots, "aaaa")])
    staging()
    with pytest.raises(SandboxGuardError, match="scope"):
        run(store, client, config)
    assert client.calls == []
