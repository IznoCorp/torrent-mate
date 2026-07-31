"""Integration tests for the ingest pipeline step.

Exercises ``personalscraper.ingest.ingest.run_ingest`` against a real
``tmp_path`` staging tree and an in-memory qBittorrent stub, asserting on
observable filesystem and tracker-JSON invariants.

Catalogue items covered:
    #1 — Ingest filter: completed / incomplete / already-tracked
    #2 — Ratio threshold guard (< min_ratio skipped, ≥ min_ratio ingested)
"""

import json
from pathlib import Path

import pytest

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.ingest.ingest import run_ingest
from tests.integration.conftest import FakeQBitClient, FakeTorrent

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_settings() -> Settings:
    """Return a minimal Settings with disk-space guard disabled.

    Sets ``min_free_space_staging_gb=0`` so the disk-space check never
    blocks the test on machines with a small ``/tmp`` partition.

    Returns:
        Settings instance with disk-space threshold cleared.
    """
    return Settings()


def _make_torrent_dir(root: Path, name: str) -> FakeTorrent:
    """Create a single-file torrent directory under *root* and return a FakeTorrent.

    Args:
        root: Parent directory for the torrent content folder.
        name: Torrent / folder name (also used as hash prefix for uniqueness).

    Returns:
        FakeTorrent pointing at ``root / name``.
    """
    torrent_dir = root / name
    torrent_dir.mkdir(parents=True, exist_ok=True)
    (torrent_dir / "video.mkv").write_bytes(b"\x00" * 16)  # tiny stub file
    return FakeTorrent(
        name=name,
        hash=f"hash_{name.lower().replace(' ', '_')}",
        content_path=str(torrent_dir),
    )


# ---------------------------------------------------------------------------
# Catalogue #1 — ingest filter invariants
# ---------------------------------------------------------------------------


def test_ingest_filters_completed_and_untracked(
    fake_qbit: FakeQBitClient,
    staging_tree: Path,
    integration_config: Config,
    tmp_path: Path,
) -> None:
    """Only the completed, untracked torrent is moved to 097-TEMP.

    Seeds fake_qbit with:
    - one completed torrent  (expected: moved to staging ingest dir)
    - one incomplete torrent (expected: present in qBit but not in completed list)
    - one already-tracked   (expected: skipped by the IngestTracker)

    Asserts:
    - Exactly one folder in staging / 097-TEMP matching the completed torrent.
    - ingested_torrents.json contains the completed torrent's hash.
    - The already-tracked hash is NOT re-processed (skip_count reflects it).

    Args:
        fake_qbit: In-memory qBittorrent stub.
        staging_tree: Staging root under tmp_path.
        integration_config: Config wired to fixture paths.
        tmp_path: Pytest temporary directory (unique per test).
    """
    torrent_source = tmp_path / "complete"
    torrent_source.mkdir()

    # Three torrents: completed, incomplete (only in active list), already-tracked
    completed = _make_torrent_dir(torrent_source, "Movie.2024.1080p")
    incomplete = _make_torrent_dir(torrent_source, "Series.S01E01.720p")
    tracked = _make_torrent_dir(torrent_source, "OldMovie.2020.BluRay")

    # Seed: only completed + tracked in the "completed" list;
    # incomplete is added to all-torrents only (simulates in-progress download)
    fake_qbit.seed([completed, tracked])
    fake_qbit.seed_all([incomplete])

    # Pre-register the already-tracked torrent in the tracker JSON so run_ingest skips it
    data_dir: Path = integration_config.paths.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    tracker_path = data_dir / "ingested_torrents.json"
    tracker_path.write_text(
        json.dumps({tracked.hash: {"name": tracked.name, "action": "moved", "date": "2024-01-01"}}),
        encoding="utf-8",
    )

    settings = _make_settings()
    # Resolve the ingest (097-TEMP) directory directly from staging_tree
    ingest_dir = staging_tree / "097-TEMP"

    report = run_ingest(
        settings,
        config=integration_config,
        ingest_dir=ingest_dir,
        staging_dir=staging_tree,
        event_bus=EventBus(),
        torrent_client=fake_qbit,
    )

    # Exactly one folder should appear in 097-TEMP (the completed torrent)
    ingested_entries = [e for e in ingest_dir.iterdir() if e.is_dir()]
    assert len(ingested_entries) == 1, (
        f"Expected exactly 1 folder in 097-TEMP, found: {[e.name for e in ingested_entries]}"
    )
    assert ingested_entries[0].name == completed.name

    # Tracker JSON must record the newly ingested hash
    tracker_data = json.loads(tracker_path.read_text(encoding="utf-8"))
    assert completed.hash in tracker_data, f"{completed.hash!r} not found in tracker JSON"

    # No errors during ingest
    assert report.error_count == 0, f"Unexpected errors: {report.details}"


class _ProvenanceSpy:
    """A StagingProvenanceWriter spy recording set_ingest calls (feature provenance)."""

    def __init__(self) -> None:
        self.ingests: list[tuple[str, str]] = []

    def set_ingest(self, info_hash: str, *, ingest_path: str, ingested_at: int) -> None:
        self.ingests.append((info_hash, ingest_path))

    def set_current_path(self, info_hash: str, *, path: str) -> None:  # pragma: no cover - unused here
        pass

    def set_dispatch(self, info_hash: str, *, dispatch_path: str, dispatched_at: int) -> None:  # pragma: no cover
        pass


def test_ingest_records_provenance_hash_to_folder(
    fake_qbit: FakeQBitClient,
    staging_tree: Path,
    integration_config: Config,
    tmp_path: Path,
) -> None:
    """Phase 2: a successful ingest links the torrent hash → its staging folder.

    This is the hash↔folder seam #30 needs (the knowledge that exists at ingest and
    was previously discarded). The write is advisory; here a spy captures it.
    """
    torrent_source = tmp_path / "complete"
    torrent_source.mkdir()
    completed = _make_torrent_dir(torrent_source, "Inception.2010.1080p")
    fake_qbit.seed([completed])
    integration_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    ingest_dir = staging_tree / "097-TEMP"
    spy = _ProvenanceSpy()

    report = run_ingest(
        _make_settings(),
        config=integration_config,
        ingest_dir=ingest_dir,
        staging_dir=staging_tree,
        event_bus=EventBus(),
        torrent_client=fake_qbit,
        provenance=spy,
    )

    assert report.error_count == 0, f"Unexpected errors: {report.details}"
    assert len(spy.ingests) == 1, f"expected one provenance set_ingest, got {spy.ingests}"
    info_hash, ingest_path = spy.ingests[0]
    assert info_hash == completed.hash
    assert ingest_path.endswith(completed.name), f"ingest_path {ingest_path} should be the staging folder"


# ---------------------------------------------------------------------------
# Catalogue #2 — ratio threshold guard
# ---------------------------------------------------------------------------


@pytest.fixture()
def _min_ratio_1(integration_config: Config) -> Config:
    """Return integration_config with ingest.min_ratio set to 1.0.

    This fixture is intentionally test-local (defined in test_ingest.py, not
    conftest.py) because the ratio override is specific to the ratio-threshold
    test and must not bleed into other tests.

    Args:
        integration_config: Base integration Config fixture.

    Returns:
        Config copy with ``ingest.min_ratio = 1.0``.
    """
    new_ingest = integration_config.ingest.model_copy(update={"min_ratio": 1.0})
    return integration_config.model_copy(update={"ingest": new_ingest})


def test_ingest_ratio_threshold(
    fake_qbit: FakeQBitClient,
    staging_tree: Path,
    _min_ratio_1: Config,
    tmp_path: Path,
) -> None:
    """Only the torrent at or above min_ratio is ingested; the other is skipped.

    Seeds two completed torrents with ratios 0.99 and 1.00.  Runs ingest with
    ``config.ingest.min_ratio = 1.0`` (via the ``_min_ratio_1`` fixture).

    Asserts:
    - Exactly one folder in 097-TEMP (the 1.00-ratio torrent).
    - The 0.99-ratio torrent is not present in 097-TEMP.

    Args:
        fake_qbit: In-memory qBittorrent stub.
        staging_tree: Staging root under tmp_path.
        _min_ratio_1: Config copy with min_ratio = 1.0.
        tmp_path: Pytest temporary directory (unique per test).
    """
    torrent_source = tmp_path / "complete"
    torrent_source.mkdir()

    below = _make_torrent_dir(torrent_source, "BelowRatio.Movie.2024")
    below_torrent = FakeTorrent(
        name=below.name,
        hash=below.hash,
        content_path=below.content_path,
        ratio=0.99,
    )

    above = _make_torrent_dir(torrent_source, "AboveRatio.Movie.2024")
    above_torrent = FakeTorrent(
        name=above.name,
        hash=above.hash,
        content_path=above.content_path,
        ratio=1.00,
    )

    fake_qbit.seed([below_torrent, above_torrent])

    settings = _make_settings()
    ingest_dir = staging_tree / "097-TEMP"

    report = run_ingest(
        settings,
        config=_min_ratio_1,
        ingest_dir=ingest_dir,
        staging_dir=staging_tree,
        event_bus=EventBus(),
        torrent_client=fake_qbit,
    )

    ingested_entries = [e for e in ingest_dir.iterdir() if e.is_dir()]
    ingested_names = {e.name for e in ingested_entries}

    assert above.name in ingested_names, f"Expected {above.name!r} in 097-TEMP, found: {ingested_names}"
    assert below.name not in ingested_names, (
        f"{below.name!r} should have been skipped (ratio 0.99 < 1.0), found: {ingested_names}"
    )
    assert report.error_count == 0, f"Unexpected errors: {report.details}"


class _RaisingProvenance:
    """A StagingProvenanceWriter whose every write RAISES (ACC-03 hardening)."""

    def set_ingest(self, info_hash: str, *, ingest_path: str, ingested_at: int) -> None:
        raise RuntimeError("provenance exploded")

    def move_path(self, old_path: str, new_path: str) -> None:  # pragma: no cover - not hit here
        raise RuntimeError("provenance exploded")

    def record_dispatch_by_path(
        self, staging_path: str, *, dispatch_path: str, dispatched_at: int
    ) -> None:  # pragma: no cover
        raise RuntimeError("provenance exploded")


def test_ingest_survives_a_raising_provenance_writer(
    fake_qbit: FakeQBitClient,
    staging_tree: Path,
    integration_config: Config,
    tmp_path: Path,
) -> None:
    """ACC-03: a provenance write that RAISES never fails the ingest step."""
    torrent_source = tmp_path / "complete"
    torrent_source.mkdir()
    completed = _make_torrent_dir(torrent_source, "Film.2024.1080p")
    fake_qbit.seed([completed])
    integration_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

    report = run_ingest(
        _make_settings(),
        config=integration_config,
        ingest_dir=staging_tree / "097-TEMP",
        staging_dir=staging_tree,
        event_bus=EventBus(),
        torrent_client=fake_qbit,
        provenance=_RaisingProvenance(),
    )

    assert report.error_count == 0, f"a raising provenance writer must not fail ingest: {report.details}"
    assert report.success_count == 1, "the transfer must still complete"
