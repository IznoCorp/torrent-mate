"""Tests for the torrent client scope: the part of a shared client one instance owns."""

from pathlib import Path

import json5
import pytest
from pydantic import ValidationError

from personalscraper.conf.models.api_config import TorrentClientEntry, TorrentConfig, TorrentScope
from personalscraper.core.tags import SEED_PURE

_EXAMPLE_TORRENT = Path(__file__).resolve().parents[2] / "config.example" / "torrent.json5"


class TestTorrentScope:
    """TorrentScope validation."""

    def test_valid_scope_keeps_its_fields(self, tmp_path: Path) -> None:
        """A category, a download root and the default tags validate."""
        scope = TorrentScope(category="tm-preprod", download_root=tmp_path)
        assert scope.category == "tm-preprod"
        assert scope.download_root == tmp_path
        assert scope.instance_tags == ("tm-preprod", SEED_PURE)

    @pytest.mark.parametrize("category", ["", " ", "\t"])
    def test_blank_category_refused(self, tmp_path: Path, category: str) -> None:
        """An empty or whitespace-only category would scope nothing: refused."""
        with pytest.raises(ValidationError, match="category"):
            TorrentScope(category=category, download_root=tmp_path)

    def test_empty_tag_refused(self, tmp_path: Path) -> None:
        """An empty instance tag would match every torrent in a tag filter: refused."""
        with pytest.raises(ValidationError, match="empty"):
            TorrentScope(category="tm-preprod", download_root=tmp_path, instance_tags=("", SEED_PURE))

    def test_seed_pure_missing_refused(self, tmp_path: Path) -> None:
        """Without seed-pure, the other instance's triage would pick this instance's torrents up: refused."""
        with pytest.raises(ValidationError, match=SEED_PURE):
            TorrentScope(category="tm-preprod", download_root=tmp_path, instance_tags=("tm-preprod",))

    def test_unknown_field_refused(self, tmp_path: Path) -> None:
        """A typo in the scope is caught, as everywhere in the config."""
        with pytest.raises(ValidationError):
            TorrentScope.model_validate({"category": "tm-preprod", "download_root": str(tmp_path), "save_path": "/x"})

    def test_scope_is_frozen(self, tmp_path: Path) -> None:
        """A scope read from the config cannot be changed in flight."""
        scope = TorrentScope(category="tm-preprod", download_root=tmp_path)
        with pytest.raises(ValidationError):
            scope.category = "other"  # type: ignore[misc]


class TestTorrentClientEntryScope:
    """TorrentClientEntry.scope, absent by default."""

    def test_scope_absent_is_none(self) -> None:
        """No scope = the whole client, today's behaviour."""
        assert TorrentClientEntry().scope is None

    def test_scope_parsed_from_config(self, tmp_path: Path) -> None:
        """A scope under a client entry is parsed into a TorrentScope."""
        cfg = TorrentConfig.model_validate(
            {
                "active": "qbittorrent",
                "clients": {
                    "qbittorrent": {
                        "scope": {
                            "category": "tm-preprod",
                            "download_root": str(tmp_path),
                            "instance_tags": ["tm-preprod", SEED_PURE],
                        }
                    }
                },
            }
        )
        scope = cfg.clients["qbittorrent"].scope
        assert isinstance(scope, TorrentScope)
        assert scope.instance_tags == ("tm-preprod", SEED_PURE)

    def test_shipped_example_sets_no_scope(self) -> None:
        """The shipped example leaves every client unscoped, so a sync adds no key to an existing config."""
        cfg = TorrentConfig.model_validate(json5.loads(_EXAMPLE_TORRENT.read_text())["torrent"])
        assert all(entry.scope is None for entry in cfg.clients.values())
