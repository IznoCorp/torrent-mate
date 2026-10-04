"""Read-model game filter — a game in a non-terminal category is not surfaced.

``scan_staging_media`` must skip a game release (disc image + game signal) even
when the sorter parked it in the non-terminal ``other`` category (098-AUTRES),
while still surfacing genuine unrecognized media there for triage. The skip is
logged (``staging_game_hidden``) — never a silent disappearance (§méthode).
"""

from pathlib import Path

import structlog

from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.staging import staging_path
from personalscraper.web.staging.read_model import scan_staging_media
from tests.fixtures.config import CANONICAL_STAGING_DIRS


def make_config(tmp_path: Path) -> Config:
    """Build a minimal Config whose staging tree lives under ``tmp_path``.

    Uses the canonical staging_dirs (so the non-terminal ``other`` category
    exists) with a single trivial disk/category — enough to drive
    ``scan_staging_media`` over the ``other`` folder.
    """
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[DiskConfig(id="disk_0", path=tmp_path / "disk", categories=["movies"])],
        categories={"movies": CategoryConfig(folder_name="001-MOVIES")},
        staging_dirs=CANONICAL_STAGING_DIRS,
    )


def _mkitem(parent: Path, folder: str, files: list[str]) -> None:
    """Create ``folder`` under ``parent`` holding empty ``files``."""
    d = parent / folder
    d.mkdir(parents=True)
    for name in files:
        (d / name).write_bytes(b"")


def _other_dir(config) -> Path:
    """Return the on-disk path of the non-terminal ``other`` staging category."""
    entry = next(e for e in config.staging_dirs if e.file_type == "other")
    return staging_path(config, entry)


class TestReadModelGameFilter:
    """scan_staging_media hides games, keeps other media visible."""

    def test_game_in_other_is_hidden_media_stays_visible(self, tmp_path: Path):
        """ACC-03: the game folder is filtered out, the non-game folder remains."""
        config = make_config(tmp_path)
        other = _other_dir(config)
        _mkitem(
            other,
            "Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto",
            ["Marvels.Spider-Man.2-Mephisto.iso", "msm2.nfo"],
        )
        _mkitem(other, "Some Unknown Release (2024)", ["readme.txt"])

        items = scan_staging_media(config, tmp_path / "absent.db")
        folders = {it.folder for it in items}

        assert "Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto" not in folders
        assert "Some Unknown Release (2024)" in folders

    def test_game_skip_is_logged(self, tmp_path: Path):
        """The skip emits ``staging_game_hidden`` — no silent disappearance."""
        config = make_config(tmp_path)
        other = _other_dir(config)
        _mkitem(
            other,
            "Cyberpunk.2077.v2.1.0-RUNE",
            ["cp2077.iso"],
        )

        with structlog.testing.capture_logs() as logs:
            scan_staging_media(config, tmp_path / "absent.db")

        events = [entry.get("event") for entry in logs]
        assert "staging_game_hidden" in events
