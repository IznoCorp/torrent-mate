"""Tests for Pydantic API config models."""

import pytest

from personalscraper.api.tracker._ranking import RankingBonuses, RankingConfig, ThresholdEntry
from personalscraper.conf.models.api_config import (
    MetadataConfig,
    NotifyConfig,
    TorrentClientEntry,
    TorrentConfig,
    TrackerConfig,
)


class TestThresholdEntry:
    """ThresholdEntry ByteSize-aware parsing."""

    def test_string_size_parsed(self) -> None:
        """at='1GB' is parsed to 1_000_000_000."""
        entry = ThresholdEntry(at="1GB", score=10)  # type: ignore[arg-type]
        assert entry.at == 1_000_000_000

    def test_string_binary_parsed(self) -> None:
        """at='500MiB' is parsed to 524_288_000."""
        entry = ThresholdEntry(at="500MiB", score=5)  # type: ignore[arg-type]
        assert entry.at == 524_288_000

    def test_int_passthrough(self) -> None:
        """at=100 passes through as 100."""
        entry = ThresholdEntry(at=100, score=5)
        assert entry.at == 100


class TestRankingConfig:
    """RankingConfig round-trip."""

    def test_default_construction(self) -> None:
        """Default RankingConfig has empty criteria."""
        cfg = RankingConfig()
        assert cfg.criteria == []
        assert cfg.bonuses == RankingBonuses()
        assert cfg.min_seeders == 1

    def test_roundtrip_defaults(self) -> None:
        """Round-trip from dict with defaults."""
        data = {
            "criteria": [],
            "bonuses": {"freeleech": 10, "silverleech": 5},
            "min_seeders": 1,
        }
        cfg = RankingConfig.model_validate(data)
        assert cfg.min_seeders == 1
        assert cfg.bonuses.freeleech == 10

    def test_threshold_with_string_size(self) -> None:
        """Threshold with string size parses correctly."""
        data = {
            "criteria": [
                {
                    "field": "size",
                    "weight": 1,
                    "prefer": "higher",
                    "thresholds": [
                        {"at": 0, "score": 0},
                        {"at": "1GB", "score": 5},
                        {"at": "5GB", "score": 10},
                    ],
                }
            ],
        }
        cfg = RankingConfig.model_validate(data)
        thresholds = cfg.criteria[0].thresholds
        assert thresholds is not None
        assert thresholds[1].at == 1_000_000_000
        assert thresholds[2].at == 5_000_000_000


class TestMetadataConfig:
    """MetadataConfig model tests."""

    def test_defaults(self) -> None:
        """Default MetadataConfig has expected language defaults."""
        cfg = MetadataConfig()
        assert cfg.defaults.language == "fr-FR"
        assert cfg.defaults.fallback_language == "en-US"

    def test_providers_parsed(self) -> None:
        """Providers dict is parsed correctly."""
        data = {"providers": {"tmdb": {"enabled": True}, "tvdb": {"enabled": False}}}
        cfg = MetadataConfig.model_validate(data)
        assert cfg.providers["tmdb"].enabled is True
        assert cfg.providers["tvdb"].enabled is False


class TestTorrentConfig:
    """TorrentConfig model tests."""

    def test_defaults(self) -> None:
        """Default TorrentConfig has empty active client."""
        cfg = TorrentConfig()
        assert cfg.active == ""

    def test_clients_parsed(self) -> None:
        """Clients dict is parsed correctly."""
        data = {
            "active": "qbittorrent",
            "clients": {"qbittorrent": {"enabled": True, "host": "192.168.1.1", "port": 9090}},
        }
        cfg = TorrentConfig.model_validate(data)
        assert cfg.active == "qbittorrent"
        assert cfg.clients["qbittorrent"].host == "192.168.1.1"


class TestSandboxCategories:
    """``sandbox_categories``: how an unscoped instance learns which categories belong to the sandboxes."""

    def test_default_is_empty(self) -> None:
        """No key, no sandbox category: prod behaves as before."""
        assert TorrentClientEntry().sandbox_categories == ()
        assert TorrentConfig().active_sandbox_categories() == ()

    def test_active_client_categories_are_returned(self) -> None:
        """The active client's list is what the instance keeps out of."""
        cfg = TorrentConfig.model_validate(
            {"active": "qbit", "clients": {"qbit": {"sandbox_categories": ["tm-preprod", "tm-dev"]}}}
        )
        assert cfg.active_sandbox_categories() == ("tm-preprod", "tm-dev")

    def test_scoped_instance_refuses_the_key(self) -> None:
        """A sandbox is itself scoped: the key belongs to the unscoped instance only."""
        with pytest.raises(ValueError, match="sandbox_categories"):
            TorrentClientEntry.model_validate(
                {"scope": {"category": "tm-dev", "download_root": "/srv/dev"}, "sandbox_categories": ["tm-preprod"]}
            )

    @pytest.mark.parametrize("bad", [[""], ["  "]])
    def test_blank_category_is_refused(self, bad: list[str]) -> None:
        """A blank category would match nothing, or everything uncategorised: refused."""
        with pytest.raises(ValueError, match="sandbox_categories"):
            TorrentClientEntry.model_validate({"sandbox_categories": bad})


class TestTrackerConfig:
    """TrackerConfig model tests."""

    def test_defaults(self) -> None:
        """Default TrackerConfig has expected caps."""
        cfg = TrackerConfig()
        assert cfg.max_total_results == 50
        assert cfg.timeout_per_tracker == 15

    def test_priority_list(self) -> None:
        """Priority list is ordered."""
        data = {"priority": ["tr4ker", "c411"]}
        cfg = TrackerConfig.model_validate(data)
        assert cfg.priority == ["tr4ker", "c411"]


class TestNotifyConfig:
    """NotifyConfig model tests."""

    def test_defaults(self) -> None:
        """Default NotifyConfig has both providers disabled and acquire muted."""
        cfg = NotifyConfig()
        assert cfg.telegram.enabled is False
        assert cfg.healthchecks.enabled is False
        assert cfg.acquire_notify_enabled is False
