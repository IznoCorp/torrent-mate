"""Build a deterministic 1 000-item / ~1 TB virtual filesystem for performance regression tests.

File-size distribution (per DESIGN §15.6.1):
  - 5%  > 50 GB : sparse files (os.truncate)
  - 70% 1–5 GB  : sparse files (os.truncate)
  - 25% < 100 MB: real pseudo-random content (seeded RNG for determinism)

The fixture is written to ``tests/e2e/perf/.fixture/`` by default and is gitignored.
A second invocation with the same seed and the same FIXTURE_VERSION produces a byte-identical layout.

Usage::

    python -m tests.e2e.perf.build_fixture
    python tests/e2e/perf/build_fixture.py [--output-dir DIR] [--seed N]
"""

from __future__ import annotations

import argparse
import os
import random
import struct
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SEED: int = 42
ITEM_COUNT: int = 1_000

# Bucket thresholds (bytes)
LARGE_MIN: int = 50 * 1024 * 1024 * 1024  # 50 GB
MEDIUM_MIN: int = 1 * 1024 * 1024 * 1024  # 1 GB
MEDIUM_MAX: int = 5 * 1024 * 1024 * 1024  # 5 GB
SMALL_MAX: int = 100 * 1024 * 1024  # 100 MB

# Bucket probabilities: [large, medium, small]
BUCKET_WEIGHTS: list[float] = [0.05, 0.70, 0.25]

# For small files, write in chunks to avoid huge allocations.
CHUNK_SIZE: int = 64 * 1024  # 64 KiB


def _fixture_version(version_file: Path) -> int:
    """Read the fixture version integer from a FIXTURE_VERSION file.

    Args:
        version_file: Path to the FIXTURE_VERSION file (one integer line).

    Returns:
        Integer fixture version.

    Raises:
        ValueError: If the file content cannot be parsed as an integer.
        FileNotFoundError: If the version file does not exist.
    """
    return int(version_file.read_text().strip())


def _choose_sizes(rng: random.Random) -> list[int]:
    """Choose file sizes for all items according to the bucket distribution.

    Args:
        rng: A seeded :class:`random.Random` instance.

    Returns:
        A list of *ITEM_COUNT* byte sizes, one per fixture file.
    """
    buckets = rng.choices(["large", "medium", "small"], weights=BUCKET_WEIGHTS, k=ITEM_COUNT)
    sizes: list[int] = []
    for bucket in buckets:
        if bucket == "large":
            # Slightly above 50 GB; vary up to 200 GB for realism.
            size = rng.randint(LARGE_MIN + 1, 200 * 1024 * 1024 * 1024)
        elif bucket == "medium":
            size = rng.randint(MEDIUM_MIN, MEDIUM_MAX)
        else:
            # Small: up to 100 MB - 1 byte (exclusive upper bound).
            size = rng.randint(1, SMALL_MAX - 1)
        sizes.append(size)
    return sizes


def _write_sparse(path: Path, size: int) -> None:
    """Create a sparse file of the given byte length using truncate(2).

    Args:
        path: Destination file path (parent directory must exist).
        size: Target file size in bytes.
    """
    with path.open("wb") as fh:
        # open() creates the file; os.truncate extends it to *size* as a sparse hole.
        os.truncate(fh.fileno(), size)


def _write_real(path: Path, size: int, rng: random.Random) -> None:
    """Write pseudo-random bytes to a file so that OSHash output is deterministic.

    Using a seeded RNG guarantees the same byte sequence on every invocation
    with the same seed, making the fixture byte-identical across rebuilds.

    Args:
        path: Destination file path (parent directory must exist).
        size: Total bytes to write.
        rng: A seeded :class:`random.Random` instance (shared across all files
             in this build so that call order determines content).
    """
    remaining = size
    with path.open("wb") as fh:
        while remaining > 0:
            chunk = min(CHUNK_SIZE, remaining)
            # Pack random 64-bit integers into bytes for speed.
            n_words = (chunk + 7) // 8
            data = struct.pack(f"{n_words}Q", *[rng.getrandbits(64) for _ in range(n_words)])
            fh.write(data[:chunk])
            remaining -= chunk


def build_fixture(output_dir: Path, seed: int, version_file: Path) -> None:
    """Build the deterministic 1 000-item virtual filesystem fixture.

    Creates the output directory if it does not exist.  On subsequent calls
    with the same *seed* and fixture version, the resulting directory tree
    (filenames, sizes, and content for small files) is byte-identical.

    Args:
        output_dir: Root directory under which fixture files are written.
            Structured as ``output_dir/disk{01..N}/dir{A..Z}/file_{i:04d}.mkv``.
        seed: Integer seed for the :class:`random.Random` RNG.  Pin to
            ``DEFAULT_SEED`` for reproducible CI baseline.
        version_file: Path to the ``FIXTURE_VERSION`` file; its value is
            embedded in the subdirectory name so different versions never
            collide.

    Raises:
        FileNotFoundError: If *version_file* does not exist.
        ValueError: If *version_file* contains a non-integer value.
    """
    version = _fixture_version(version_file)
    rng = random.Random(seed)

    versioned_root = output_dir / f"v{version}"
    versioned_root.mkdir(parents=True, exist_ok=True)

    sizes = _choose_sizes(rng)

    # Spread files across 4 pseudo-disks and 10 sub-directories each to mimic
    # a realistic multi-disk library layout.
    n_disks = 4
    n_dirs = 10
    total = len(sizes)

    print(f"[build_fixture] version={version} seed={seed} items={total} root={versioned_root}", flush=True)

    for idx, size in enumerate(sizes):
        disk_idx = idx % n_disks
        dir_idx = (idx // n_disks) % n_dirs
        disk_dir = versioned_root / f"disk{disk_idx + 1:02d}" / f"dir{dir_idx:02d}"
        disk_dir.mkdir(parents=True, exist_ok=True)

        filename = f"file_{idx:04d}.mkv"
        file_path = disk_dir / filename

        if size < SMALL_MAX:
            # Real content: OSHash reads the first+last 64 KiB, so these bytes matter.
            _write_real(file_path, size, rng)
        else:
            # Sparse: only metadata and the first/last extents are allocated.
            _write_sparse(file_path, size)

        if (idx + 1) % 100 == 0:
            print(f"  [{idx + 1}/{total}] written", flush=True)

    print(f"[build_fixture] done — {total} files under {versioned_root}", flush=True)


def main() -> None:
    """Entry point for CLI invocation.

    Parses ``--output-dir`` and ``--seed`` overrides, then delegates to
    :func:`build_fixture`.

    Args: (parsed from sys.argv)
        --output-dir: Override the output directory (default: ``tests/e2e/perf/.fixture``
            relative to the repository root detected from this file's location).
        --seed: Override the random seed (default: ``DEFAULT_SEED = 42``).

    Raises:
        SystemExit: On argument parse error (argparse default behaviour).
    """
    # Detect repo root as two levels above this file's ``tests/e2e/perf/`` location.
    repo_root = Path(__file__).resolve().parents[3]
    default_output = repo_root / "tests" / "e2e" / "perf" / ".fixture"
    version_file = Path(__file__).resolve().parent / "FIXTURE_VERSION"

    parser = argparse.ArgumentParser(
        description="Build the deterministic perf-test fixture filesystem.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output,
        help=f"Root directory for fixture output (default: {default_output})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for deterministic layout (default: {DEFAULT_SEED})",
    )
    args = parser.parse_args()

    build_fixture(output_dir=args.output_dir, seed=args.seed, version_file=version_file)


if __name__ == "__main__":
    main()
