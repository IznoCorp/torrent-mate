"""Tests for the torrent client scope: the part of a shared client one instance owns."""

from pathlib import Path

import json5
import pytest
from pydantic import ValidationError

from personalscraper.conf.models.api_config import TorrentClientEntry, TorrentConfig, TorrentScope
from personalscraper.core.tags import SEED_ONLY, SEED_PURE

_EXAMPLE_TORRENT = Path(__file__).resolve().parents[2] / "config.example" / "torrent.json5"


class TestTorrentScope:
    """TorrentScope validation."""

    def test_valid_scope_keeps_its_fields(self, tmp_path: Path) -> None:
        """A category, a download root and the default tags validate."""
        scope = TorrentScope(category="tm-preprod", download_root=tmp_path)
        assert scope.category == "tm-preprod"
        assert scope.download_root == tmp_path
        assert scope.instance_tags == ("tm-preprod",)
        assert scope.v0_seed_pure is True

    @pytest.mark.parametrize("category", ["", " ", "\t"])
    def test_blank_category_refused(self, tmp_path: Path, category: str) -> None:
        """An empty or whitespace-only category would scope nothing: refused."""
        with pytest.raises(ValidationError, match="category"):
            TorrentScope(category=category, download_root=tmp_path)

    def test_relative_download_root_refused(self) -> None:
        """A relative root would resolve against each process's working directory: refused."""
        with pytest.raises(ValidationError, match="absolute"):
            TorrentScope(category="tm-preprod", download_root=Path("downloads/preprod"))

    def test_absolute_download_root_accepted(self, tmp_path: Path) -> None:
        """An absolute root validates unchanged."""
        assert tmp_path.is_absolute()
        assert TorrentScope(category="tm-preprod", download_root=tmp_path).download_root == tmp_path

    @pytest.mark.parametrize("tag", ["", " ", "\t"])
    def test_blank_tag_refused(self, tmp_path: Path, tag: str) -> None:
        """An empty or whitespace-only instance tag would match every torrent in a tag filter: refused."""
        with pytest.raises(ValidationError, match="empty"):
            TorrentScope(category="tm-preprod", download_root=tmp_path, instance_tags=(tag,))

    def test_instance_tag_alone_accepted(self, tmp_path: Path) -> None:
        """The instance tag alone names the instance: seed-pure is no longer required among the tags."""
        scope = TorrentScope(category="tm-preprod", download_root=tmp_path, instance_tags=("tm-dev",))
        assert scope.instance_tags == ("tm-dev",)

    def test_no_instance_tag_refused(self, tmp_path: Path) -> None:
        """Without an instance tag a scoped reader could own no torrent: refused."""
        with pytest.raises(ValidationError, match="instance tag"):
            TorrentScope(category="tm-preprod", download_root=tmp_path, instance_tags=())

    @pytest.mark.parametrize("tag", [SEED_PURE, SEED_ONLY])
    def test_triage_tag_among_instance_tags_refused(self, tmp_path: Path, tag: str) -> None:
        """A triage tag is not an instance tag: with one among them no grab of the instance would be triaged."""
        with pytest.raises(ValidationError, match=tag):
            TorrentScope(category="tm-preprod", download_root=tmp_path, instance_tags=("tm-preprod", tag))

    def test_grab_tags_carry_seed_pure_while_v0_flag_on(self, tmp_path: Path) -> None:
        """With the v0 flag on (default) a grab carries the instance tags and seed-pure, so v0 prod skips it."""
        scope = TorrentScope(category="tm-preprod", download_root=tmp_path)
        assert scope.grab_tags == ("tm-preprod", SEED_PURE)

    def test_grab_tags_without_v0_flag(self, tmp_path: Path) -> None:
        """With the v0 flag off a grab carries the instance tags alone."""
        scope = TorrentScope(category="tm-preprod", download_root=tmp_path, v0_seed_pure=False)
        assert scope.grab_tags == ("tm-preprod",)

    def test_cross_seed_tags_carry_seed_only(self, tmp_path: Path) -> None:
        """A cross-seed carries the instance tags, seed-only, and seed-pure while the v0 flag is on."""
        on = TorrentScope(category="tm-preprod", download_root=tmp_path)
        off = TorrentScope(category="tm-preprod", download_root=tmp_path, v0_seed_pure=False)
        assert on.cross_seed_tags == ("tm-preprod", SEED_ONLY, SEED_PURE)
        assert off.cross_seed_tags == ("tm-preprod", SEED_ONLY)

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
                            "instance_tags": ["tm-preprod"],
                        }
                    }
                },
            }
        )
        scope = cfg.clients["qbittorrent"].scope
        assert isinstance(scope, TorrentScope)
        assert scope.instance_tags == ("tm-preprod",)

    def test_shipped_example_sets_no_scope(self) -> None:
        """The shipped example leaves every client unscoped, so a sync adds no key to an existing config."""
        cfg = TorrentConfig.model_validate(json5.loads(_EXAMPLE_TORRENT.read_text())["torrent"])
        assert all(entry.scope is None for entry in cfg.clients.values())
