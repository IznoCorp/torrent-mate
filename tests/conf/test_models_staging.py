"""Tests for StagingDirConfig model validation."""

import pytest
from pydantic import ValidationError

from personalscraper.conf.models import Config, StagingDirConfig

# ---------------------------------------------------------------------------
# StagingDirConfig unit tests
# ---------------------------------------------------------------------------


def _make_entry(**kwargs) -> dict:
    """Return a minimal valid StagingDirConfig dict, overridable via kwargs."""
    base = {"id": 1, "name": "movies", "file_type": "movie"}
    base.update(kwargs)
    return base


class TestStagingDirConfigValid:
    """Valid configurations must parse without error."""

    def test_minimal_entry(self):
        """Minimal valid entry parses all fields correctly."""
        entry = StagingDirConfig(**_make_entry())
        assert entry.id == 1
        assert entry.name == "movies"
        assert entry.file_type == "movie"
        assert entry.role is None

    def test_with_role_ingest(self):
        """Entry with role='ingest' parses without error."""
        entry = StagingDirConfig(**_make_entry(id=97, name="temp", file_type=None, role="ingest"))
        assert entry.role == "ingest"

    def test_name_kebab_case(self):
        """Kebab-case names with hyphens are accepted."""
        entry = StagingDirConfig(**_make_entry(name="tv-shows"))
        assert entry.name == "tv-shows"

    def test_id_boundary_zero(self):
        """Id=0 is a valid lower boundary."""
        StagingDirConfig(**_make_entry(id=0))

    def test_id_boundary_999(self):
        """Id=999 is a valid upper boundary."""
        StagingDirConfig(**_make_entry(id=999))

    def test_no_file_type(self):
        """file_type is optional."""
        entry = StagingDirConfig(**_make_entry(file_type=None))
        assert entry.file_type is None


class TestStagingDirConfigInvalid:
    """Invalid configurations must raise ValidationError."""

    def test_id_below_zero(self):
        """Id below 0 raises ValidationError."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            StagingDirConfig(**_make_entry(id=-1))

    def test_id_above_999(self):
        """Id above 999 raises ValidationError."""
        with pytest.raises(ValidationError, match="less than or equal to 999"):
            StagingDirConfig(**_make_entry(id=1000))

    def test_name_uppercase(self):
        """Uppercase names violate the kebab-case pattern."""
        with pytest.raises(ValidationError):
            StagingDirConfig(**_make_entry(name="MOVIES"))

    def test_name_with_underscore(self):
        """Underscores in names violate the kebab-case pattern."""
        with pytest.raises(ValidationError):
            StagingDirConfig(**_make_entry(name="tv_shows"))

    def test_name_with_special_char(self):
        """Spaces in names violate the kebab-case pattern."""
        with pytest.raises(ValidationError):
            StagingDirConfig(**_make_entry(name="tv shows"))

    def test_invalid_file_type(self):
        """Unknown file_type strings raise ValidationError."""
        with pytest.raises(ValidationError, match="file_type"):
            StagingDirConfig(**_make_entry(file_type="bogus"))


# ---------------------------------------------------------------------------
# Config-level validators (require a full Config — use a minimal fixture)
# ---------------------------------------------------------------------------


def _minimal_config_dict(staging_dirs: list[dict]) -> dict:
    """Build a minimal Config dict with the given staging_dirs."""
    return {
        "paths": {
            "torrent_complete_dir": "/tmp/torrents",
            "staging_dir": "/tmp/staging",
            "data_dir": "/tmp/.data",
        },
        "disks": [{"id": "disk_a", "path": "/tmp/disk_a", "categories": ["movies"]}],
        "staging_dirs": staging_dirs,
    }


class TestConfigStagingDirsValidators:
    """Root-level Config validators for staging_dirs."""

    def test_valid_staging_dirs(self):
        """A complete valid staging_dirs list passes root-level validation."""
        Config.model_validate(
            _minimal_config_dict(
                [
                    {"id": 1, "name": "movies", "file_type": "movie"},
                    {"id": 97, "name": "temp", "file_type": None, "role": "ingest"},
                ]
            )
        )

    def test_duplicate_id_fails(self):
        """Two entries with the same id raise ValidationError."""
        with pytest.raises(ValidationError, match="[Dd]uplicate"):
            Config.model_validate(
                _minimal_config_dict(
                    [
                        {"id": 1, "name": "movies", "file_type": "movie"},
                        {"id": 1, "name": "tvshows", "file_type": "tvshow"},
                    ]
                )
            )

    def test_zero_ingest_role_fails(self):
        """Missing ingest role raises ValidationError."""
        with pytest.raises(ValidationError, match="[Ii]ngest"):
            Config.model_validate(
                _minimal_config_dict(
                    [
                        {"id": 1, "name": "movies", "file_type": "movie"},
                    ]
                )
            )

    def test_two_ingest_roles_fail(self):
        """Two entries with role='ingest' raise ValidationError."""
        with pytest.raises(ValidationError, match="[Ii]ngest"):
            Config.model_validate(
                _minimal_config_dict(
                    [
                        {"id": 97, "name": "temp", "file_type": None, "role": "ingest"},
                        {"id": 98, "name": "autres", "file_type": None, "role": "ingest"},
                    ]
                )
            )

    def test_config_without_staging_dirs_raises_friendly_error(self):
        """staging_dirs is required in Phase 2 — missing key must emit friendly message."""
        cfg = _minimal_config_dict([])
        del cfg["staging_dirs"]
        with pytest.raises(ValidationError, match="MANUAL.md"):
            Config.model_validate(cfg)
