"""Wiring test: the sort step seeds provenance with the MEDIA FOLDER (#30).

Unit-testing ``media_root_for`` proves the rule; this proves the rule is
actually applied. Without the wiring the helper is dead code and the identity
seed keeps landing on the file — the exact silent failure that sent « The
Odyssey » (2026) to a free title match on 2026-08-06 despite its TMDB id being
known since the grab.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.sorter.run import run_sort


class _CapturingProvenance:
    """A StagingProvenanceWriter recording every ``move_path`` it receives."""

    def __init__(self) -> None:
        self.moves: list[tuple[str, str]] = []

    def set_ingest(self, info_hash: str, *, ingest_path: str, ingested_at: int, run_uid: str | None = None) -> None:
        """Unused on the sort path."""

    def move_path(self, old_path: str, new_path: str) -> None:
        """Record the move the sort step reports."""
        self.moves.append((old_path, new_path))

    def set_scrape_run(self, staging_path: str, *, run_uid: str | None, scraped_at: int) -> None:
        """Unused on the sort path."""

    def record_dispatch_by_path(
        self, staging_path: str, *, dispatch_path: str, dispatched_at: int, run_uid: str | None = None
    ) -> None:
        """Unused on the sort path."""


def test_sort_seeds_provenance_with_the_movie_folder_not_the_file(
    integration_config: Config,
    staging_tree: Path,
) -> None:
    """A single-file movie must seed the FOLDER the scrape will look up.

    Reproduces the incident shape: a bare ``.mp4`` arrives in the ingest dir and
    the sorter files it under ``001-MOVIES/<Title (Year)>/``. The provenance seed
    must name that folder — not the file inside it.
    """
    from personalscraper.conf.staging import find_ingest_dir, staging_path

    ingest_dir = staging_path(integration_config, find_ingest_dir(integration_config))
    ingest_dir.mkdir(parents=True, exist_ok=True)

    source = ingest_dir / "The.Odyssey.2026.VO.720p.AVC.AAC.2.0-ONYXA.mp4"
    source.write_bytes(b"x" * 4096)

    provenance = _CapturingProvenance()
    run_sort(
        Settings(),
        staging_tree,
        integration_config,
        dry_run=False,
        event_bus=EventBus(),
        provenance=provenance,
    )

    assert provenance.moves, "sort must report the move to provenance"
    _old, new = provenance.moves[0]
    new_path = Path(new)

    assert new_path.is_dir(), f"the seeded path must be the media FOLDER, got {new_path}"
    assert new_path.suffix == "", f"the seeded path must not be a file, got {new_path}"
    # And it is the folder that actually holds the sorted file.
    assert any(child.name == source.name for child in new_path.iterdir()), (
        f"{new_path} should contain the sorted release"
    )
