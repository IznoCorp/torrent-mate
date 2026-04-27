"""Hypothesis strategies for property-based indexer tests.

Provides composable generators used by ``test_drift.py`` and other property
tests across the indexer test suite.  All strategies produce small, deterministic
values appropriate for fast CI runs.

Generators:

- :func:`valid_file` — a single fixture file descriptor.
- :func:`valid_disk_layout` — a list of fixture file descriptors with unique paths.
- :func:`mutation` — a single mutation operation on a disk layout.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from hypothesis import strategies as st
from hypothesis.strategies import SearchStrategy, composite

# ---------------------------------------------------------------------------
# Constants controlling strategy size to keep CI fast.
# ---------------------------------------------------------------------------

#: Fixed epoch used as the centre of mtime generation (2024-01-15 00:00:00 UTC).
_TEST_EPOCH_NS: int = 1_705_276_800_000_000_000

#: Mtime range: ±30 days around the test epoch.
_MTIME_DELTA_NS: int = 30 * 24 * 3600 * 1_000_000_000

#: Maximum number of files in a disk layout.
_MAX_FILES: int = 20

#: Maximum individual file content size (bytes).
_MAX_CONTENT_BYTES: int = 256

#: Maximum number of path components.
_MAX_DEPTH: int = 4

#: Maximum length of a single path component.
_MAX_PATH_COMPONENT: int = 20


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FileSpec:
    """Descriptor for a single fixture file in a generated disk layout.

    Args:
        rel_path: Relative POSIX path string from disk root, e.g. ``"movies/foo.mkv"``.
        content: Raw bytes content of the file.
        mtime_ns: Desired mtime in nanoseconds (may be clamped by the consumer).
    """

    rel_path: str
    content: bytes
    mtime_ns: int


@dataclass
class DiskLayout:
    """A collection of fixture files representing one virtual disk.

    Args:
        files: List of :class:`FileSpec` with unique ``rel_path`` values.
    """

    files: list[FileSpec]


MutationKind = Literal["add_file", "delete_file", "modify_content", "rename_file", "change_mtime"]


@dataclass
class Mutation:
    """A single mutation to apply to a :class:`DiskLayout`.

    Args:
        kind: Type of mutation.
        target_index: Index into ``DiskLayout.files`` for operations that need a
            target.  Ignored by ``add_file``; clamped to ``len(files) - 1``
            by the consumer.
        new_content: Replacement content for ``modify_content`` mutations.
        new_rel_path: Target path for ``rename_file`` mutations.
        new_mtime_ns: New mtime for ``change_mtime`` mutations.
        new_file: File to add for ``add_file`` mutations; ``None`` otherwise.
    """

    kind: MutationKind
    target_index: int
    new_content: bytes
    new_rel_path: str
    new_mtime_ns: int
    new_file: FileSpec | None


# ---------------------------------------------------------------------------
# Helper: path components strategy
# ---------------------------------------------------------------------------


def _path_component() -> SearchStrategy[str]:
    """Strategy producing a single non-empty ASCII path component.

    Returns:
        A strategy producing ASCII strings suitable for use as directory or file
        names (no slashes, no dots, no whitespace).
    """
    return st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-"),
        min_size=1,
        max_size=_MAX_PATH_COMPONENT,
    )


# ---------------------------------------------------------------------------
# valid_file
# ---------------------------------------------------------------------------


@composite
def valid_file(draw: st.DrawFn) -> FileSpec:
    """Generate a single fixture file descriptor.

    Produces a :class:`FileSpec` with:

    - A relative path of depth 1..4 using safe ASCII characters.
    - Binary content of 0..:data:`_MAX_CONTENT_BYTES` bytes.
    - An mtime within ±30 days of a fixed test epoch.

    Args:
        draw: Hypothesis draw function (injected by ``@composite``).

    Returns:
        A :class:`FileSpec` instance.
    """
    depth = draw(st.integers(min_value=1, max_value=_MAX_DEPTH))
    components = [draw(_path_component()) for _ in range(depth)]
    # Ensure the leaf looks like a video file for oshash eligibility.
    leaf = components[-1] + ".mkv"
    components[-1] = leaf
    rel_path = "/".join(components)

    content = draw(st.binary(min_size=0, max_size=_MAX_CONTENT_BYTES))
    mtime_delta = draw(st.integers(min_value=-_MTIME_DELTA_NS, max_value=_MTIME_DELTA_NS))
    mtime_ns = _TEST_EPOCH_NS + mtime_delta

    return FileSpec(rel_path=rel_path, content=content, mtime_ns=mtime_ns)


# ---------------------------------------------------------------------------
# valid_disk_layout
# ---------------------------------------------------------------------------


@composite
def valid_disk_layout(draw: st.DrawFn) -> DiskLayout:
    """Generate a disk layout with unique file paths.

    Produces a :class:`DiskLayout` with 1..:data:`_MAX_FILES` files, all having
    distinct ``rel_path`` values (duplicates are deduplicated by suffix).

    Args:
        draw: Hypothesis draw function (injected by ``@composite``).

    Returns:
        A :class:`DiskLayout` instance.
    """
    files_raw: list[FileSpec] = draw(st.lists(valid_file(), min_size=1, max_size=_MAX_FILES))

    # Deduplicate rel_path by appending a counter suffix when needed.
    seen: dict[str, int] = {}
    files: list[FileSpec] = []
    for spec in files_raw:
        base = spec.rel_path
        if base in seen:
            seen[base] += 1
            unique_path = base.replace(".mkv", f"_{seen[base]}.mkv")
        else:
            seen[base] = 0
            unique_path = base
        files.append(FileSpec(rel_path=unique_path, content=spec.content, mtime_ns=spec.mtime_ns))

    return DiskLayout(files=files)


# ---------------------------------------------------------------------------
# mutation
# ---------------------------------------------------------------------------


@composite
def mutation(draw: st.DrawFn) -> Mutation:
    """Generate a single mutation to apply to a :class:`DiskLayout`.

    One of five kinds (chosen uniformly):

    - ``add_file`` — add a new file to the layout.
    - ``delete_file`` — remove the file at ``target_index``.
    - ``modify_content`` — replace the content of the file at ``target_index``.
    - ``rename_file`` — move the file at ``target_index`` to ``new_rel_path``.
    - ``change_mtime`` — update the mtime of the file at ``target_index``.

    Args:
        draw: Hypothesis draw function (injected by ``@composite``).

    Returns:
        A :class:`Mutation` instance.
    """
    kind: MutationKind = draw(
        st.sampled_from(["add_file", "delete_file", "modify_content", "rename_file", "change_mtime"])
    )
    target_index = draw(st.integers(min_value=0, max_value=_MAX_FILES - 1))
    new_content = draw(st.binary(min_size=1, max_size=_MAX_CONTENT_BYTES))
    new_path_component = draw(_path_component())
    new_rel_path = "mutated/" + new_path_component + ".mkv"
    mtime_delta = draw(st.integers(min_value=-_MTIME_DELTA_NS, max_value=_MTIME_DELTA_NS))
    new_mtime_ns = _TEST_EPOCH_NS + mtime_delta
    new_file = draw(valid_file()) if kind == "add_file" else None

    return Mutation(
        kind=kind,
        target_index=target_index,
        new_content=new_content,
        new_rel_path=new_rel_path,
        new_mtime_ns=new_mtime_ns,
        new_file=new_file,
    )
