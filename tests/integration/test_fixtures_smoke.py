"""Smoke test proving that integration fixtures compose correctly.

Asserts that the fixture chain evaluates without errors and that each
fixture produces the expected shape.  No production behaviour is tested here.
"""

from pathlib import Path

from personalscraper.conf.models.config import Config
from tests.integration.conftest import FakeQBitClient


def test_fixtures_compose(
    staging_tree: Path,
    fake_disks: list[Path],
    integration_config: Config,
    integration_config_path: Path,
    fake_qbit: FakeQBitClient,
) -> None:
    """Prove the integration fixture chain evaluates without errors.

    Checks:
    - staging_tree exists on disk.
    - fake_disks contains exactly 4 entries.
    - integration_config.paths.staging_dir points at staging_tree.
    - integration_config_path exists on disk.
    - fake_qbit starts with an empty torrent list.

    Args:
        staging_tree: Staging root fixture.
        fake_disks: List of fake disk root paths.
        integration_config: Composed Config wired to fixture paths.
        integration_config_path: Path to the serialised config.json5.
        fake_qbit: In-memory qBittorrent stub.
    """
    assert staging_tree.is_dir(), "staging_tree must be an existing directory"
    assert len(fake_disks) == 4, f"expected 4 fake disks, got {len(fake_disks)}"
    assert integration_config.paths.staging_dir == staging_tree, (
        "integration_config.paths.staging_dir must equal staging_tree"
    )
    assert integration_config_path.exists(), "serialised config.json5 must exist on disk"
    assert fake_qbit.get_completed_torrents() == [], "fake_qbit must start with an empty torrent list"
