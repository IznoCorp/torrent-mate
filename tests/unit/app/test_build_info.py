"""The build identity v1 serves: the package version and the commit the process booted with."""

from __future__ import annotations

from pathlib import Path

import personalscraper
from personalscraper.app.build_info import BUILD_INFO, BuildInfo, read_build_commit


def test_reads_the_stripped_commit(tmp_path: Path) -> None:
    """A present ``BUILD_COMMIT`` is answered without its surrounding whitespace."""
    (tmp_path / "BUILD_COMMIT").write_text("abc1234\n", encoding="utf-8")

    assert read_build_commit(tmp_path) == "abc1234"


def test_absent_commit_is_dev(tmp_path: Path) -> None:
    """No ``BUILD_COMMIT`` (a development checkout) is answered as ``dev``."""
    assert read_build_commit(tmp_path) == "dev"


def test_unreadable_commit_is_dev(tmp_path: Path) -> None:
    """A ``BUILD_COMMIT`` that cannot be read as a file is answered as ``dev``, never raised."""
    (tmp_path / "BUILD_COMMIT").mkdir()

    assert read_build_commit(tmp_path) == "dev"


def test_undecodable_commit_is_dev(tmp_path: Path) -> None:
    """A ``BUILD_COMMIT`` that is not UTF-8 is answered as ``dev``: the import never raises, the process starts."""
    (tmp_path / "BUILD_COMMIT").write_bytes(b"\xff\xfe")

    assert read_build_commit(tmp_path) == "dev"


def test_boot_value_carries_the_package_version() -> None:
    """The value read at import names this package's version."""
    assert isinstance(BUILD_INFO, BuildInfo)
    assert BUILD_INFO.version == personalscraper.__version__
    assert BUILD_INFO.commit
