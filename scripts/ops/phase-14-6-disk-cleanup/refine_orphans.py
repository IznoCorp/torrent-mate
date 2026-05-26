"""Re-classify DELETE_NO_VIDEO_SIBLING entries with subdir awareness.

A NFO classified DELETE_NO_VIDEO_SIBLING might still be a tvshow-root NFO
if the parent dir contains Saison NN/ subdirs with videos. Plex may have
indexed it as the show's metadata — deletion would lose metadata.

Refined classes:
  - SAFE_TORRENT_LEFTOVER: NFO in a nested subdir with no videos anywhere
  - REVIEW_SHOW_ROOT: NFO at show root, parent has subdirs with videos (Plex risk)
  - REVIEW_NO_SIBLING_NO_SUBDIR: NFO in a dir with no videos AND no subdirs (rare, manual)
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".flv", ".webm"}


def has_video_in_subdirs(directory: Path, max_depth: int = 3) -> int:
    """Count videos in immediate child SUBDIRS of `directory` (not in directory itself)."""
    if not directory.is_dir():
        return 0
    count = 0
    try:
        for child in directory.iterdir():
            if not child.is_dir():
                continue
            try:
                for descendant in child.rglob("*"):
                    if descendant.is_file() and descendant.suffix.lower() in VIDEO_EXTS:
                        count += 1
                        if count > 0:
                            return count
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError):
        pass
    return count


def refine_delete_entries(csv_path: Path) -> dict[str, list[Path]]:
    """Read CSV, re-classify DELETE_NO_VIDEO_SIBLING rows."""
    classes: dict[str, list[Path]] = {}
    with csv_path.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row["classification"] != "DELETE_NO_VIDEO_SIBLING":
                continue
            nfo = Path(row["path"])
            if not nfo.exists():
                classes.setdefault("MISSING_AT_REFINE_TIME", []).append(nfo)
                continue
            parent = nfo.parent
            subdir_videos = has_video_in_subdirs(parent)
            if subdir_videos > 0:
                # Parent has subdirs containing videos (e.g., Saison NN/ with .mkv)
                # → this NFO is likely show-root legacy metadata
                classes.setdefault("REVIEW_SHOW_ROOT", []).append(nfo)
            else:
                # No videos in subdirs either → safe torrent leftover
                classes.setdefault("SAFE_TORRENT_LEFTOVER", []).append(nfo)
    return classes


def main() -> int:
    csv_path = Path("/tmp/nfo_audit_v3.csv")
    refined = refine_delete_entries(csv_path)
    print("=== Refined DELETE_NO_VIDEO_SIBLING ===")
    for cls, items in sorted(refined.items()):
        print(f"\n{cls}: {len(items)}")
        for item in items[:5]:
            print(f"  {item}")
        if len(items) > 5:
            print(f"  ... and {len(items) - 5} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
