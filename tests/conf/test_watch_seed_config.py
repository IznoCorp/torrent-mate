"""Tests for watch-seed configuration models and overlay wiring.

Covers ACC-4 (cross_seed defaults to False) and anti-drift checks
between config/ and config.example/.
"""

from pathlib import Path

import json5
import pytest
from pydantic import ValidationError

from personalscraper.conf.models.api_config import TrackerProviderConfig
from personalscraper.conf.models.watch_seed import CrossSeedConfig, WatchConfig

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_EXAMPLE_DIR = _REPO_ROOT / "config.example"
_LOCAL_DIR = _REPO_ROOT / "config"


# ---------------------------------------------------------------------------
# TrackerProviderConfig
# ---------------------------------------------------------------------------


class TestTrackerProviderCrossSeed:
    """Tests for the cross_seed field on TrackerProviderConfig (ACC-4)."""

    def test_tracker_provider_cross_seed_defaults_false(self):
        """TrackerProviderConfig().cross_seed must default to False (ACC-4).

        Design: docs/features/watch-seed/DESIGN.md §D9
        Contract: ACC-4 — cross_seed opt-in gate.
        """
        cfg = TrackerProviderConfig()
        assert cfg.cross_seed is False, "ACC-4: cross_seed must default to False (opt-in gate per D9)"


# ---------------------------------------------------------------------------
# CrossSeedConfig defaults
# ---------------------------------------------------------------------------


class TestCrossSeedConfig:
    """Tests for CrossSeedConfig model defaults and validation."""

    def test_cross_seed_config_defaults(self):
        """CrossSeedConfig() must have correct default values.

        Design: docs/features/watch-seed/DESIGN.md §Config
        Contract: cross_seed block in config.example/watch_seed.json5.
        """
        cfg = CrossSeedConfig()
        assert cfg.enabled is False
        assert cfg.max_searches_per_day == 250
        assert cfg.min_delay_between_searches_s == 30
        assert cfg.exclude_recent_search_days == 3
        assert cfg.verify_timeout_s == 900

    def test_max_searches_invalid_rejected(self):
        """CrossSeedConfig(max_searches_per_day=0) must raise ValidationError.

        max_searches_per_day has ge=1 constraint.
        """
        with pytest.raises(ValidationError):
            CrossSeedConfig(max_searches_per_day=0)


# ---------------------------------------------------------------------------
# WatchConfig defaults
# ---------------------------------------------------------------------------


class TestWatchConfig:
    """Tests for WatchConfig model defaults and validation."""

    def test_watch_config_defaults(self):
        """WatchConfig() must have correct default values.

        Design: docs/features/watch-seed/DESIGN.md §Config
        Contract: watch block in config.example/watch_seed.json5.
        """
        cfg = WatchConfig()
        assert cfg.enabled is False
        assert cfg.poll_interval_s == 60
        assert cfg.debounce_s == 900
        assert cfg.safety_net_hours == 24

    def test_poll_interval_below_min_rejected(self):
        """WatchConfig(poll_interval_s=5) must raise ValidationError.

        poll_interval_s has ge=10 constraint.
        """
        with pytest.raises(ValidationError):
            WatchConfig(poll_interval_s=5)


# ---------------------------------------------------------------------------
# Anti-drift: config.example/ ↔ config/ overlay wiring
# ---------------------------------------------------------------------------


def _read_json5(path: Path) -> dict:
    """Read and parse a JSON5 file.

    Args:
        path: Path to the JSON5 file.

    Returns:
        Parsed dict.
    """
    with open(path, encoding="utf-8") as fh:
        return json5.load(fh)


class TestConfigJson5CrossSeedBlocks:
    """Anti-drift checks for config.example/ overlay wiring."""

    def test_config_json5_has_cross_seed_blocks(self):
        """Verify config.example/watch_seed.json5 wiring and overlay reference.

        config.example/watch_seed.json5 must exist with cross_seed + watch keys,
        and config.example/config.json5 overlays must reference watch_seed.json5.

        Design: docs/features/watch-seed/DESIGN.md §Config
        Contract: anti-drift rule — both config/ and config.example/ must be wired.
        """
        # 1. Watch-seed overlay file must exist
        ws_path = _EXAMPLE_DIR / "watch_seed.json5"
        assert ws_path.is_file(), f"config.example/watch_seed.json5 missing at {ws_path}"

        ws = _read_json5(ws_path)

        # 2. Must contain both top-level blocks
        assert "cross_seed" in ws, "config.example/watch_seed.json5 must have 'cross_seed' top-level key"
        assert "watch" in ws, "config.example/watch_seed.json5 must have 'watch' top-level key"

        # 2b. cross_seed block must contain verify_timeout_s key (anti-drift).
        # The key is commented-out in JSON5, so check the raw file text.
        raw_text = ws_path.read_text(encoding="utf-8")
        assert "verify_timeout_s" in raw_text, (
            "config.example/watch_seed.json5 must contain 'verify_timeout_s' key (commented)"
        )

        # 3. config.example/config.json5 overlays array must reference watch_seed.json5
        master_path = _EXAMPLE_DIR / "config.json5"
        assert master_path.is_file(), f"config.example/config.json5 missing at {master_path}"

        master = _read_json5(master_path)
        overlays = master.get("overlays", [])

        assert "watch_seed.json5" in overlays, (
            "config.example/config.json5 overlays array must include 'watch_seed.json5'"
        )

    @pytest.mark.skipif(
        not (_LOCAL_DIR / "config.json5").is_file(),
        reason="Local config/ dir not present (CI-safe skip)",
    )
    def test_local_config_has_cross_seed_blocks(self):
        """If config/ exists locally, it must also have watch_seed overlay wired.

        This test is CI-safe: it is skipped when config/ does not exist
        (which is the case in CI, where no local config/ is provisioned).

        Design: docs/features/watch-seed/DESIGN.md §Config
        Contract: anti-drift — local config must mirror config.example/.
        """
        # Local watch_seed overlay
        ws_path = _LOCAL_DIR / "watch_seed.json5"
        assert ws_path.is_file(), f"config/watch_seed.json5 missing at {ws_path}"

        ws = _read_json5(ws_path)

        assert "cross_seed" in ws, "config/watch_seed.json5 must have 'cross_seed' top-level key"
        assert "watch" in ws, "config/watch_seed.json5 must have 'watch' top-level key"

        # cross_seed block must contain verify_timeout_s key (anti-drift).
        # The key is commented-out in JSON5, so check the raw file text.
        raw_text = ws_path.read_text(encoding="utf-8")
        assert "verify_timeout_s" in raw_text, (
            "config/watch_seed.json5 must contain 'verify_timeout_s' key (commented)"
        )

        # Local master overlays reference
        master_path = _LOCAL_DIR / "config.json5"
        master = _read_json5(master_path)
        overlays = master.get("overlays", [])

        assert "watch_seed.json5" in overlays, "config/config.json5 overlays array must include 'watch_seed.json5'"
