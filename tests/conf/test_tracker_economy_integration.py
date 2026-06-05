"""Config-load integration for the tracker economy block — tracker-economy §Components.5.

A tracker.json5 ``economy`` block parses into the typed model through the real
``load_config_dir`` path, with humanized durations converted to integer seconds;
an invalid policy (target_ratio < min_ratio) or a malformed duration is rejected
at config-load time as a ``ConfigValidationError``.
"""

from __future__ import annotations

import pathlib

import pytest

from personalscraper.conf.loader import ConfigValidationError, load_config_dir

_PATTERNS = (
    '{"staging_dirs":[{"id":1,"name":"movies","file_type":"movie"},'
    '{"id":2,"name":"tvshows","file_type":"tvshow"},'
    '{"id":97,"name":"temp","file_type":null,"role":"ingest"},'
    '{"id":98,"name":"autres","file_type":"other"}]}'
)


def _write_config(config_dir: pathlib.Path, c411_body: str) -> pathlib.Path:
    """Write a minimal split-config dir whose tracker.json5 carries ``c411_body``.

    Args:
        config_dir: Directory to populate (created if absent).
        c411_body: JSON5 fragment for the ``c411`` provider (e.g. with an economy block).

    Returns:
        The populated config directory.
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    base = config_dir.parent
    (config_dir / "config.json5").write_text(
        '{"config_version":1,"overlays":["paths.json5","disks.json5","patterns.json5","tracker.json5"],'
        f'"paths":{{"torrent_complete_dir":"{base}/c","staging_dir":"{base}/s","data_dir":"{base}/dt"}}}}'
    )
    (config_dir / "paths.json5").write_text("{}")
    (config_dir / "disks.json5").write_text(f'{{"disks":[{{"id":"a","path":"{base}/disk","categories":["movies"]}}]}}')
    (config_dir / "patterns.json5").write_text(_PATTERNS)
    (config_dir / "tracker.json5").write_text(
        '{"tracker":{"providers":{"c411":{' + c411_body + "}},"
        '"priority":["c411"],"max_total_results":50,"max_per_tracker":30,"timeout_per_tracker":15}}'
    )
    return config_dir


def test_economy_block_loads_with_seconds(tmp_path: pathlib.Path) -> None:
    """A tracker.json5 economy block parses; humanized durations become seconds."""
    cfg = load_config_dir(
        _write_config(
            tmp_path / "ok",
            '"enabled":false,"economy":{"target_ratio":2.0,"min_ratio":1.0,"min_seed_time":"72h","hit_and_run_grace":"0h"}',
        )
    )
    eco = cfg.tracker.providers["c411"].economy
    assert eco is not None
    assert eco.target_ratio == 2.0
    assert eco.min_ratio == 1.0
    assert eco.min_seed_time == 259_200
    assert eco.hit_and_run_grace == 0


def test_target_ratio_below_min_rejected_at_load(tmp_path: pathlib.Path) -> None:
    """target_ratio < min_ratio raises ConfigValidationError at config-load."""
    with pytest.raises(ConfigValidationError, match="target_ratio"):
        load_config_dir(
            _write_config(
                tmp_path / "bad",
                '"enabled":false,"economy":{"target_ratio":0.5,"min_ratio":1.0,"min_seed_time":"72h"}',
            )
        )


def test_economy_none_when_absent(tmp_path: pathlib.Path) -> None:
    """A provider without an economy block loads with economy=None (activation-only)."""
    cfg = load_config_dir(_write_config(tmp_path / "noeco", '"enabled":false'))
    assert cfg.tracker.providers["c411"].economy is None


def test_malformed_duration_rejected_at_load(tmp_path: pathlib.Path) -> None:
    """A malformed duration string raises ConfigValidationError at config-load."""
    with pytest.raises(ConfigValidationError):
        load_config_dir(
            _write_config(
                tmp_path / "baddur",
                '"enabled":false,"economy":{"target_ratio":2.0,"min_seed_time":"bad"}',
            )
        )
