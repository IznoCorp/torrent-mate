"""Tests for pre-scrape release preparation (DEV #1 — sample/RAR).

Covers :mod:`personalscraper.process.extract`:

- :func:`strip_sample_artifacts` removes ``Sample/`` dirs and ``*-sample.*``
  clips, preserves real videos AND archives, and honours ``--dry-run``.
- :func:`extract_release_archives` extracts multi-part RAR sets (REAL extraction
  via the ``rar``/``unrar`` toolchain when present, skipped otherwise), removes
  consumed archive parts on success, is idempotent, fails soft on a corrupt
  archive, and honours ``--dry-run``.

The real-extraction tests reproduce the reported production bug: a "Rafa"-style
scene release whose real video is locked in a multi-part RAR next to a
``Sample/`` preview clip — before the fix the scraper matched the sample clip as
the episode and the real video was never extracted.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from personalscraper.process.extract import (
    _find_rar_entrypoints,
    _is_first_volume,
    extract_release_archives,
    strip_sample_artifacts,
)

_RAR = shutil.which("rar")
_UNRAR = shutil.which("unrar")
_needs_rar_toolchain = pytest.mark.skipif(
    not (_RAR and _UNRAR), reason="requires the rar (creator) and unrar (extractor) binaries"
)


def _write(path: Path, data: bytes) -> Path:
    """Write ``data`` to ``path`` (creating parent dirs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _make_rar(
    release_dir: Path,
    video_name: str,
    *,
    video_bytes: bytes,
    volume_kb: int | None = None,
    arc_name: str = "release.rar",
) -> None:
    """Create a real RAR set in ``release_dir`` from a fake video file.

    The source video is written, archived with the ``rar`` binary (store mode
    for speed), then deleted so only the archive parts remain — mirroring a
    freshly-downloaded scene release.

    Args:
        release_dir: Directory to hold the archive parts.
        video_name: Filename of the video stored inside the archive.
        video_bytes: Payload of the fake video (size drives multi-part split).
        volume_kb: If set, split into volumes of this many KiB (multi-part).
        arc_name: Archive base name (for building independent sets in one dir).
    """
    release_dir.mkdir(parents=True, exist_ok=True)
    src = release_dir / video_name
    src.write_bytes(video_bytes)
    cmd = [str(_RAR), "a", "-ep", "-m0"]
    if volume_kb is not None:
        cmd.append(f"-v{volume_kb}k")
    cmd += [arc_name, video_name]
    subprocess.run(cmd, cwd=release_dir, check=True, capture_output=True)
    src.unlink()


class TestIsFirstVolume:
    """``_is_first_volume`` selects only the entry volume of a RAR set."""

    def test_plain_rar_is_first(self) -> None:
        """Old-style ``name.rar`` is the entry volume."""
        assert _is_first_volume("release.rar") is True

    def test_part01_is_first(self) -> None:
        """New-style ``part01``/``part1`` is the entry volume."""
        assert _is_first_volume("release.part01.rar") is True
        assert _is_first_volume("release.part1.rar") is True

    def test_part02_is_not_first(self) -> None:
        """Continuation parts (``part02``/``part2``) are not entry volumes."""
        assert _is_first_volume("release.part02.rar") is False
        assert _is_first_volume("release.part2.rar") is False


class TestStripSampleArtifacts:
    """``strip_sample_artifacts`` removes samples, preserves real + archives."""

    def test_removes_sample_dir(self, tmp_path: Path) -> None:
        """A ``Sample/`` subdir with a clip is removed entirely."""
        rel = tmp_path / "Show" / "Show.S01E01-GRP"
        _write(rel / "Sample" / "show.s01e01-grp-sample.mkv", b"\0" * 1024)
        _write(rel / "show.s01e01-grp.mkv", b"\0" * 4096)  # real video stays

        report = strip_sample_artifacts(tmp_path, dry_run=False)

        assert not (rel / "Sample").exists()
        assert (rel / "show.s01e01-grp.mkv").exists()
        assert report.success_count == 1

    def test_removes_loose_sample_file(self, tmp_path: Path) -> None:
        """A flat ``*-sample.*`` file (no Sample/ dir) is removed."""
        rel = tmp_path / "Movie (2026)"
        _write(rel / "movie.2026-sample.mkv", b"\0" * 1024)
        _write(rel / "movie.2026.mkv", b"\0" * 4096)

        report = strip_sample_artifacts(tmp_path, dry_run=False)

        assert not (rel / "movie.2026-sample.mkv").exists()
        assert (rel / "movie.2026.mkv").exists()
        assert report.success_count == 1

    def test_preserves_archives(self, tmp_path: Path) -> None:
        """Archive parts are NOT stripped (only successful extraction removes them)."""
        rel = tmp_path / "Show" / "Show.S01E01-GRP"
        _write(rel / "Sample" / "x-sample.mkv", b"\0" * 1024)
        _write(rel / "release.rar", b"RARARCHIVE")
        _write(rel / "release.r00", b"RARVOLUME")

        strip_sample_artifacts(tmp_path, dry_run=False)

        assert (rel / "release.rar").exists()
        assert (rel / "release.r00").exists()
        assert not (rel / "Sample").exists()

    def test_dry_run_changes_nothing(self, tmp_path: Path) -> None:
        """Dry-run reports would-strip count without deleting."""
        rel = tmp_path / "Show" / "Show.S01E01-GRP"
        _write(rel / "Sample" / "x-sample.mkv", b"\0" * 1024)

        report = strip_sample_artifacts(tmp_path, dry_run=True)

        assert (rel / "Sample").exists()
        assert report.success_count == 1


class TestExtractFailSoftAndDryRun:
    """Orchestration tests that run everywhere (no rar/unrar required)."""

    def test_failsoft_on_corrupt_archive(self, tmp_path: Path) -> None:
        """A bogus .rar fails soft: archive retained, error counted, no crash."""
        rel = tmp_path / "Show" / "Show.S01E01-GRP"
        _write(rel / "release.rar", b"not a real rar file")

        report = extract_release_archives(tmp_path, dry_run=False)

        assert (rel / "release.rar").exists()  # preserved for manual recovery
        assert report.error_count == 1
        assert report.success_count == 0

    def test_dry_run_does_not_extract(self, tmp_path: Path) -> None:
        """Dry-run reports the would-extract count without touching the archive."""
        rel = tmp_path / "Show" / "Show.S01E01-GRP"
        _write(rel / "release.rar", b"anything")

        report = extract_release_archives(tmp_path, dry_run=True)

        assert (rel / "release.rar").exists()
        assert report.success_count == 1

    def test_extracted_dir_is_noop(self, tmp_path: Path) -> None:
        """A finished release (video present, archives already removed) is a no-op.

        Idempotence is structural: with no entry-volume archive there is nothing
        to extract, so a re-run does no work and reports nothing.
        """
        rel = tmp_path / "Show" / "Show.S01E01-GRP"
        _write(rel / "show.s01e01.mkv", b"\0" * 4096)  # already extracted, no archives

        report = extract_release_archives(tmp_path, dry_run=False)

        assert report.success_count == 0
        assert report.error_count == 0
        assert report.skip_count == 0
        assert (rel / "show.s01e01.mkv").exists()


@_needs_rar_toolchain
class TestExtractRealRar:
    """Real end-to-end extraction via the rar/unrar toolchain (non-vacuous)."""

    def test_single_volume_extraction_removes_archive(self, tmp_path: Path) -> None:
        """A real single-volume RAR is extracted and the archive removed."""
        rel = tmp_path / "Movie (2026)"
        payload = b"FAKEVIDEO" * 2048
        _make_rar(rel, "movie.2026.mkv", video_bytes=payload)
        assert (rel / "release.rar").exists()

        report = extract_release_archives(tmp_path, dry_run=False)

        extracted = rel / "movie.2026.mkv"
        assert extracted.exists()
        assert extracted.read_bytes() == payload
        assert not (rel / "release.rar").exists()  # consumed
        assert report.success_count == 1

    def test_multipart_extraction_reproduces_rafa(self, tmp_path: Path) -> None:
        """A multi-part RAR next to a Sample/ clip — the production scenario.

        After CLEAN (extract + strip), the real episode video must exist and the
        sample clip must be gone, so scrape can never match the sample.
        """
        rel = tmp_path / "Rafa" / "Rafa.S01E01.DOC-Penrose"
        payload = b"REALEPISODE" * 30_000  # ~330 KB → forces multiple volumes
        _make_rar(rel, "rafa.s01e01.mkv", video_bytes=payload, volume_kb=100)
        _write(rel / "Sample" / "rafa.s01e01-penrose-sample.mkv", b"\0" * 4096)
        # sanity: more than one archive volume was produced
        assert len(list(rel.glob("release.*"))) >= 2

        extract_report = extract_release_archives(tmp_path, dry_run=False)
        strip_report = strip_sample_artifacts(tmp_path, dry_run=False)

        assert (rel / "rafa.s01e01.mkv").read_bytes() == payload
        assert not (rel / "Sample").exists()
        assert not list(rel.glob("release.*"))  # all volumes consumed
        assert extract_report.success_count == 1
        assert strip_report.success_count == 1


class TestFindRarEntrypoints:
    """``_find_rar_entrypoints`` returns only entry volumes, skips samples."""

    def test_skips_continuation_and_sample(self, tmp_path: Path) -> None:
        """Only the entry ``.rar`` is returned; continuations and samples skipped."""
        rel = tmp_path / "Show" / "Show.S01E01-GRP"
        _write(rel / "release.rar", b"x")
        _write(rel / "release.r00", b"x")  # continuation (.r00 is not *.rar)
        _write(rel / "release.part02.rar", b"x")  # continuation
        _write(rel / "Sample" / "x-sample.rar", b"x")  # sample dir — ignored

        entries = _find_rar_entrypoints(tmp_path)

        names = [e.name for e in entries]
        assert names == ["release.rar"]


@_needs_rar_toolchain
class TestExtractMultiSetAndPartial:
    """Review-hardened real-RAR cases: multiple sets per dir, partial sets."""

    def test_two_independent_sets_both_survive(self, tmp_path: Path) -> None:
        """Two independent RAR sets in ONE dir: both videos extracted (BUG-1).

        Before the set-scoped-removal fix, extracting the first set deleted the
        second set's archives (directory-scoped removal) → silent data loss.
        """
        rel = tmp_path / "Movie (2026)"
        a = b"AAAA" * 4096
        b = b"BBBB" * 4096
        _make_rar(rel, "cd1.mkv", video_bytes=a, arc_name="cd1.rar")
        _make_rar(rel, "cd2.mkv", video_bytes=b, arc_name="cd2.rar")

        report = extract_release_archives(tmp_path, dry_run=False)

        assert (rel / "cd1.mkv").read_bytes() == a
        assert (rel / "cd2.mkv").read_bytes() == b  # would be GONE before the fix
        assert not list(rel.glob("*.rar"))
        assert report.success_count == 2
        assert report.error_count == 0

    def test_partial_multipart_fails_soft_and_retains_archives(self, tmp_path: Path) -> None:
        """A multi-part set missing a volume fails soft; archives are retained.

        The error is surfaced (no silent success), and because the archives stay
        the no_archive_files verify check still blocks the item from dispatch.
        """
        rel = tmp_path / "Rafa" / "Rafa.S01E01-EDITH"
        _make_rar(rel, "rafa.s01e01.mkv", video_bytes=b"REAL" * 30_000, volume_kb=100)
        volumes = sorted(rel.glob("release.*"))
        assert len(volumes) >= 2
        volumes[-1].unlink()  # drop a continuation volume → incomplete set

        report = extract_release_archives(tmp_path, dry_run=False)

        assert report.error_count >= 1
        assert report.success_count == 0
        assert list(rel.glob("release.*"))  # surviving archive volumes retained


class TestExtractSymlinkRejection:
    """A RAR carrying a symlink member is rejected (filesystem-escape guard)."""

    def test_symlink_member_is_rejected(self, tmp_path: Path, monkeypatch) -> None:
        """Extractall must NOT run for an archive with a symlink member."""
        import rarfile

        rel = tmp_path / "Movie (2026)"
        _write(rel / "release.rar", b"data")

        class _Info:
            def is_symlink(self) -> bool:
                return True

        class _FakeRar:
            def __init__(self, *a: object, **k: object) -> None:
                pass

            def __enter__(self) -> "_FakeRar":
                return self

            def __exit__(self, *a: object) -> bool:
                return False

            def infolist(self) -> list[_Info]:
                return [_Info()]

            def volumelist(self) -> list[str]:
                return ["release.rar"]

            def extractall(self, path: str | None = None) -> None:
                # Must never run for a symlink-bearing archive.
                (Path(path) / "evil.mkv").write_bytes(b"escaped")

        monkeypatch.setattr(rarfile, "RarFile", _FakeRar)

        report = extract_release_archives(tmp_path, dry_run=False)

        assert report.error_count == 1
        assert (rel / "release.rar").exists()  # archive retained
        assert not (rel / "evil.mkv").exists()  # extractall never executed


_EXTRACTOR = shutil.which("unrar") or shutil.which("unar") or shutil.which("bsdtar")
_GOLDEN_RAR = Path(__file__).parent / "fixtures" / "golden_single.rar"


@pytest.mark.skipif(not _EXTRACTOR, reason="requires a RAR extractor backend (unrar/unar/bsdtar)")
class TestExtractGoldenFixture:
    """Real extraction from a committed golden RAR (review COV-4).

    Runs wherever an extractor backend exists (including CI with unar/unrar
    installed), so the happy success path is asserted even without the `rar`
    creator binary.
    """

    def test_golden_single_volume_extracts_and_removes_archive(self, tmp_path: Path) -> None:
        """The committed golden RAR extracts its video and the archive is removed."""
        rel = tmp_path / "Movie (2020)"
        rel.mkdir(parents=True)
        shutil.copy(_GOLDEN_RAR, rel / "golden_single.rar")

        report = extract_release_archives(tmp_path, dry_run=False)

        assert (rel / "movie.2020.mkv").exists()
        assert not (rel / "golden_single.rar").exists()
        assert report.success_count == 1
        assert report.error_count == 0
