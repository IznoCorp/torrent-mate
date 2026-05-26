"""Audit NFO orphans on production disks.

Classifies each *.nfo file into one of:
  - KEEP_TVSHOW_ROOT: `tvshow.nfo` at a show root (even if all seasons empty)
  - KEEP_HAS_SIBLING: NFO with at least one matching video sibling
  - KEEP_SEASON_HAS_VIDEOS: `season.nfo` in a season dir that contains videos
  - DELETE_NO_VIDEO_SIBLING: standalone NFO whose paired media is missing
  - DELETE_DEAD_SEASON: `season.nfo` in season dir with zero videos
  - REVIEW: cannot classify confidently (manual review)

CSV output: path,classification,parent_dir_kind,sibling_video_count,size_bytes
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

VIDEO_EXTS = {
    ".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".flv", ".webm",
    ".ts", ".mpg", ".mpeg", ".m2ts", ".mts",
    ".iso", ".vob", ".divx", ".ogv", ".ogm", ".mxf", ".rm", ".rmvb",
    ".3gp", ".asf", ".dv", ".f4v",
}
DISKS = [
    Path("/Volumes/Disk1/medias"),
    Path("/Volumes/Disk2/medias"),
    Path("/Volumes/Disk3/medias"),
    Path("/Volumes/Disk4/medias"),
]


def is_real_video(path: Path) -> bool:
    """True only for real video files. Excludes AppleDouble ._* sidecars."""
    if not path.is_file():
        return False
    if path.name.startswith("._"):
        return False
    return path.suffix.lower() in VIDEO_EXTS


def has_video_in(directory: Path, recursive: bool = False) -> int:
    if not directory.is_dir():
        return 0
    try:
        if recursive:
            return sum(1 for p in directory.rglob("*") if is_real_video(p))
        return sum(1 for p in directory.iterdir() if is_real_video(p))
    except (OSError, PermissionError):
        return 0


def classify_nfo(nfo: Path) -> tuple[str, str, int]:
    """Return (classification, parent_kind, sibling_video_count)."""
    parent = nfo.parent
    name = nfo.name.lower()
    stem = nfo.stem  # filename without .nfo

    # 0. AppleDouble (._*) files — macOS resource forks, never real NFOs
    if name.startswith("._"):
        return ("DELETE_APPLEDOUBLE", "appledouble", 0)

    # 1. tvshow.nfo at show root → always KEEP
    if name == "tvshow.nfo":
        return ("KEEP_TVSHOW_ROOT", "show", has_video_in(parent, recursive=True))

    # 2. season.nfo → check whether the season has any videos
    if name == "season.nfo":
        video_count = has_video_in(parent, recursive=False)
        if video_count > 0:
            return ("KEEP_SEASON_HAS_VIDEOS", "season", video_count)
        return ("DELETE_DEAD_SEASON", "season", 0)

    # 3. Generic NFO: look for a video sibling with the same stem
    video_count = has_video_in(parent, recursive=False)

    # Try exact stem match first — but reject ._* AppleDouble pseudo-videos
    for ext in VIDEO_EXTS:
        candidate = parent / (stem + ext)
        if is_real_video(candidate):
            return ("KEEP_HAS_SIBLING", "media", video_count)
        candidate = parent / (stem + ext.upper())
        if is_real_video(candidate):
            return ("KEEP_HAS_SIBLING", "media", video_count)

    # If parent dir has zero videos at all → standalone orphan
    if video_count == 0:
        return ("DELETE_NO_VIDEO_SIBLING", "empty", 0)

    # Parent has videos but none matches this NFO's stem → REVIEW
    return ("REVIEW", "ambiguous", video_count)


def main() -> int:
    writer = csv.writer(sys.stdout)
    writer.writerow(["path", "classification", "parent_kind", "sibling_video_count", "size_bytes"])

    counts: dict[str, int] = {}
    total = 0

    def iter_nfos(root: Path):
        """Walk dirs manually, swallowing transient FileNotFoundError."""
        stack = [root]
        while stack:
            current = stack.pop()
            try:
                entries = list(current.iterdir())
            except (OSError, PermissionError) as exc:
                print(f"# scan error {current}: {exc}", file=sys.stderr)
                continue
            for entry in entries:
                try:
                    if entry.is_dir():
                        stack.append(entry)
                    elif entry.is_file() and entry.suffix.lower() == ".nfo":
                        yield entry
                except (OSError, PermissionError) as exc:
                    print(f"# stat error {entry}: {exc}", file=sys.stderr)

    for disk in DISKS:
        if not disk.is_dir():
            print(f"# skip {disk} (not mounted)", file=sys.stderr)
            continue
        for nfo in iter_nfos(disk):
            try:
                classification, parent_kind, sibling_count = classify_nfo(nfo)
                size = nfo.stat().st_size
            except (OSError, PermissionError) as exc:
                print(f"# error {nfo}: {exc}", file=sys.stderr)
                continue
            writer.writerow([str(nfo), classification, parent_kind, sibling_count, size])
            counts[classification] = counts.get(classification, 0) + 1
            total += 1

    print(f"# total NFOs scanned: {total}", file=sys.stderr)
    for cls, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"# {cls}: {count}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
