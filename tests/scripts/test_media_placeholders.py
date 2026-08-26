"""Tests for the test suite's own media placeholder — B-099's regression cover.

WHY A TEST FOR A TEST HELPER. The defect was not a wrong value; it was a cost.
Thirty-eight fixture sites wrote two hundred megabytes of REAL zeroes each, one
`make test` pass left 13 GB across 47 049 files, pytest kept the last three
passes, and the machine's boot volume filled up until no command could run. A
value defect announces itself; this one only announced itself as a dead machine.

So the two properties are held here rather than remembered: the placeholder
REPORTS the size a check will read, and it does not OCCUPY it.
"""

from __future__ import annotations

import os
from pathlib import Path

from tests._media_files import write_placeholder_media

# The size the library checks compare against — a real video is over it, a
# sample is under it. The figure is the fixtures' own.
PLACEHOLDER_SIZE = 200 * 1024 * 1024


def test_it_reports_the_size_a_check_will_read(tmp_path: Path) -> None:
    """`stat().st_size` answers in full, which is what every consumer reads."""
    written = write_placeholder_media(tmp_path / "Movie.mkv", PLACEHOLDER_SIZE)
    assert written.stat().st_size == PLACEHOLDER_SIZE


def test_it_does_not_occupy_the_size_it_reports(tmp_path: Path) -> None:
    """The blocks on disk are a rounding error against the size claimed.

    THE UNIT IS BLOCKS, NOT `st_size`, and that is the whole point: the two
    disagree by design here, and a test written against `st_size` alone would
    pass on the dense version this replaces.
    """
    written = write_placeholder_media(tmp_path / "Movie.mkv", PLACEHOLDER_SIZE)
    occupied = written.stat().st_blocks * 512
    assert occupied < PLACEHOLDER_SIZE // 100, (
        f"{occupied} bytes on disk for a {PLACEHOLDER_SIZE}-byte placeholder — "
        "the file is dense, and a full test pass will write gigabytes again")


def test_reading_it_back_returns_what_a_dense_file_would(tmp_path: Path) -> None:
    """A sparse read yields the same zeroes, so no consumer can tell.

    Held over a small size: the property is the file system's, and asserting it
    over two hundred megabytes would read two hundred megabytes to prove that
    nothing was written.
    """
    written = write_placeholder_media(tmp_path / "Small.mkv", 4096)
    assert written.read_bytes() == b"\x00" * 4096


def test_it_replaces_whatever_was_there(tmp_path: Path) -> None:
    """Like `write_bytes`, which it replaced: an existing file is truncated."""
    target = tmp_path / "Movie.mkv"
    target.write_bytes(b"stale content that must not survive")
    write_placeholder_media(target, 1024)
    assert target.stat().st_size == 1024
    assert target.read_bytes() == b"\x00" * 1024


def test_every_fixture_site_goes_through_it() -> None:
    r"""No test writes a large dense placeholder by hand any more.

    THE RATCHET, and it is what stops the 13 GB coming back one fixture at a
    time. A site added tomorrow with `write_bytes(b"\\x00" * N)` for a large N
    fails here, on the day it is typed rather than on the day a disk fills.
    """
    root = Path(__file__).resolve().parents[1]
    dense: list[str] = []
    for source in sorted(root.rglob("*.py")):
        # This file and the helper both QUOTE the pattern in prose. A ratchet
        # that reads its own explanation is a ratchet that can never be green.
        if source.name in ("test_media_placeholders.py", "_media_files.py"):
            continue
        for number, line in enumerate(source.read_text(encoding="utf-8").split("\n"), 1):
            if 'write_bytes(b"\\x00"' not in line:
                continue
            # Only the large ones: a kilobyte costs nothing and rewriting it
            # would be churn with no defect behind it.
            for size in _sizes_in(line):
                if size >= 1_000_000:
                    dense.append(f"{source.relative_to(root)}:{number}")
    assert not dense, (
        "large dense placeholder(s) — use `write_placeholder_media`: " + ", ".join(dense))


def _sizes_in(line: str) -> list[int]:
    """Returns the byte sizes a `write_bytes` line multiplies out to."""
    import re
    found = re.search(r'write_bytes\(b"\\x00" \* \(?([0-9_]+)((?: \* 1024)*)\)?\)', line)
    if not found:
        return []
    value = int(found.group(1).replace("_", ""))
    for _ in range(found.group(2).count("* 1024")):
        value *= 1024
    return [value]


def test_the_retention_policy_is_declared() -> None:
    """A green pass leaves nothing behind, whatever a future fixture writes.

    The sparse placeholder is the first half; this is the second, and it is the
    half that holds for fixtures nobody has written yet. Read from the file
    rather than from `request.config`, so the test says which SETTING is
    required rather than what this run happened to be given.
    """
    settings = (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8")
    assert 'tmp_path_retention_policy = "failed"' in settings
    # The option landed in pytest 7.3; below it the key is unknown, warned about
    # once, and then ignored — the guard would silently do nothing.
    assert '"pytest>=7.3' in settings


def test_the_environment_really_honours_it(request) -> None:
    """And the running configuration agrees, so the declaration is not decorative."""
    assert request.config.getini("tmp_path_retention_policy") == "failed"
    assert os.path.basename(str(request.config.inipath)) == "pyproject.toml"
