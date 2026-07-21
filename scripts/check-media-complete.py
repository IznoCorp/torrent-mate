#!/usr/bin/env python3
"""Executable completeness gate for a scraped media item (staging).

A staging item is COMPLETE (scraped + dispatchable) when the pipeline's ``verify`` step
passes it (status ``valid``/``fixed``) — the real gate that decides dispatch. It checks
the NFO, poster/landscape naming, the movie video-rename to the canonical ``Title.<ext>``
(``Cube.mkv``, never the raw release name — enforced by the ``movie_video_renamed``
catalog check since VERIFY-MAINTENANCE-04), and (TV) the episode renaming + episode NFOs.
The web UI "Identifié / Vérification: Fait" read-model is looser and does NOT reflect this
— never trust it.

This is the executable definition of "scraped" for product-intent.md §méthode: no
"scraping/dispatch OK" claim is valid without this green on EVERY affected item — never a
single lucky case. Exit code = number of incomplete items (0 = all complete).

Usage:
    python scripts/check-media-complete.py                 # all staging movies + tvshows
    python scripts/check-media-complete.py --only "Obsession (2026)" "Ferrari*"
"""

from __future__ import annotations

import argparse
import fnmatch
import sys

from personalscraper.conf.loader import load_config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.core.media_types import FileType
from personalscraper.naming_patterns import PATTERNS
from personalscraper.verify.verifier import Verifier


def _check(only: list[str]) -> int:
    config = load_config()
    settings = Settings(_env_file=None)
    verifier = Verifier(settings=settings, patterns=PATTERNS, config=config, dry_run=True, fix=False)
    staging = config.paths.staging_dir

    movies_dir = staging / folder_name(find_by_file_type(config, FileType.MOVIE))
    tvshows_dir = staging / folder_name(find_by_file_type(config, FileType.TVSHOW))

    results = []
    if movies_dir.exists():
        results += [("movie", r) for r in verifier.verify_all_movies(movies_dir)]
    if tvshows_dir.exists():
        results += [("tv", r) for r in verifier.verify_all_tvshows(tvshows_dir)]

    incomplete = 0
    checked = 0
    for kind, r in results:
        name = r.media_path.name
        if only and not any(fnmatch.fnmatch(name, pat) or pat in name for pat in only):
            continue
        checked += 1
        gaps: list[str] = []
        if r.status not in ("valid", "fixed"):
            gaps.extend(f"verify: {e}" for e in (r.errors or []))
            if not r.errors:
                gaps.append(f"verify status={r.status}")

        if gaps:
            incomplete += 1
            print(f"❌ INCOMPLETE  [{kind}] {name}")
            for g in gaps:
                print(f"      - {g}")
        else:
            print(f"✅ COMPLETE    [{kind}] {name}")

    print(f"\n{checked} checked, {incomplete} incomplete.")
    return incomplete


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", default=[], help="Only check items whose folder name matches these globs/substrings.")
    args = parser.parse_args()
    return _check(args.only)


if __name__ == "__main__":
    sys.exit(main())
