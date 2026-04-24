"""Tests for personalscraper.info.run — collect_info and format_info."""

from pathlib import Path
from unittest.mock import patch

from personalscraper.info.run import DiskStatus, InfoReport, collect_info, format_info

# ── Helpers ─────────────────────────────────────────────────────────────────


def _disk_usage_result(total: int, used: int, free: int):
    """Return a namedtuple-like object matching shutil.disk_usage output."""
    import collections

    Usage = collections.namedtuple("Usage", ["total", "used", "free"])
    return Usage(total=total, used=used, free=free)


# ── DiskStatus unit tests ────────────────────────────────────────────────────


def test_disk_status_not_mounted():
    """DiskStatus with mounted=False has zero byte counts."""
    ds = DiskStatus(name="DISK01", path=None, mounted=False, total_bytes=0, used_bytes=0)
    assert ds.mounted is False
    assert ds.total_bytes == 0
    assert ds.used_bytes == 0


def test_disk_status_mounted_with_data():
    """DiskStatus with mounted=True carries real byte counts."""
    ds = DiskStatus(
        name="DISK01",
        path=Path("/Volumes/DISK01"),
        mounted=True,
        total_bytes=2_000_000_000_000,
        used_bytes=1_200_000_000_000,
    )
    assert ds.mounted is True
    assert ds.total_bytes == 2_000_000_000_000


# ── collect_info unit tests ──────────────────────────────────────────────────


def test_collect_info_version(test_config):
    """collect_info returns current __version__ string."""
    import personalscraper

    with patch("shutil.disk_usage", return_value=_disk_usage_result(1_000, 500, 500)):
        report = collect_info(test_config)

    assert report.version == personalscraper.__version__


def test_collect_info_staging_path(test_config):
    """collect_info sets staging_path from config.paths.staging_dir."""
    with patch("shutil.disk_usage", return_value=_disk_usage_result(1_000, 500, 500)):
        report = collect_info(test_config)

    assert report.staging_path == test_config.paths.staging_dir


def test_collect_info_disk_not_mounted(test_config):
    """collect_info marks disk as NOT MOUNTED when path does not exist."""
    # Patch disk paths to a non-existent location
    with patch("personalscraper.info.run.Path.exists", return_value=False):
        report = collect_info(test_config)

    for disk_status in report.disks:
        assert disk_status.mounted is False
        assert disk_status.total_bytes == 0
        assert disk_status.used_bytes == 0


def test_collect_info_disk_mounted_with_data(test_config, tmp_path):
    """collect_info reads shutil.disk_usage for mounted disks."""
    # Make the disk path exist
    disk_path = tmp_path / "fake_disk"
    disk_path.mkdir()

    fake_usage = _disk_usage_result(
        total=2_000_000_000_000,
        used=1_200_000_000_000,
        free=800_000_000_000,
    )
    with (
        patch("personalscraper.info.run.Path.exists", return_value=True),
        patch("shutil.disk_usage", return_value=fake_usage),
    ):
        report = collect_info(test_config)

    for disk_status in report.disks:
        assert disk_status.mounted is True
        assert disk_status.total_bytes == 2_000_000_000_000
        assert disk_status.used_bytes == 1_200_000_000_000


def test_collect_info_disk_mounted_but_empty(test_config):
    """collect_info marks disk as empty when used bytes < 1 MB."""
    fake_usage = _disk_usage_result(
        total=10_000_000_000,
        used=512_000,  # 512 KB — filesystem headers only
        free=9_999_488_000,
    )
    with (
        patch("personalscraper.info.run.Path.exists", return_value=True),
        patch("shutil.disk_usage", return_value=fake_usage),
    ):
        report = collect_info(test_config)

    # All disks show mounted=True but used_bytes below 1 MB threshold
    for disk_status in report.disks:
        assert disk_status.mounted is True
        assert disk_status.used_bytes < 1_000_000


# ── format_info unit tests ───────────────────────────────────────────────────


def _make_report(*, mounted: bool = True, used: int = 1_200_000_000_000, total: int = 2_000_000_000_000) -> InfoReport:
    """Build a minimal InfoReport for formatting tests."""
    return InfoReport(
        version="0.2.0",
        staging_path=Path("/tmp/staging"),
        disks=[
            DiskStatus(
                name="drive_a",
                path=Path("/Volumes/DISK01") if mounted else None,
                mounted=mounted,
                total_bytes=total if mounted else 0,
                used_bytes=used if mounted else 0,
            )
        ],
    )


def test_format_info_contains_version():
    """format_info output includes 'personalscraper' and version."""
    output = format_info(_make_report())
    assert "personalscraper" in output
    assert "0.2.0" in output


def test_format_info_contains_staging():
    """format_info output includes staging: label."""
    output = format_info(_make_report())
    assert "staging:" in output


def test_format_info_not_mounted_label():
    """format_info shows NOT MOUNTED for unmounted disks."""
    output = format_info(_make_report(mounted=False))
    assert "NOT MOUNTED" in output


def test_format_info_empty_disk_label():
    """format_info shows MOUNTED BUT EMPTY for disks with < 1 MB used."""
    output = format_info(_make_report(used=512_000, total=10_000_000_000))
    assert "MOUNTED BUT EMPTY" in output


def test_format_info_disk_with_data_shows_percent():
    """format_info shows percentage for disks with real data."""
    output = format_info(_make_report(used=1_200_000_000_000, total=2_000_000_000_000))
    assert "%" in output


def test_format_info_disk_count_header(test_config):
    """format_info header shows the number of configured disks."""
    report = InfoReport(
        version="0.2.0",
        staging_path=Path("/fake/staging"),
        disks=[
            DiskStatus(name=d.id, path=d.path, mounted=False, total_bytes=0, used_bytes=0) for d in test_config.disks
        ],
    )
    output = format_info(report)
    assert f"({len(test_config.disks)} configured)" in output
