"""Sorter package — media file type detection, name cleaning, and sorting.

Handles the V2 pipeline step: detect file types, clean filenames via guessit,
and sort items from the staging root into categorized subdirectories
(001-MOVIES, 002-TVSHOWS, 004-AUDIO, etc.).
"""

from personalscraper.sorter.file_type import FileType, detect_dir_type, detect_file_type

__all__ = [
    "FileType",
    "detect_dir_type",
    "detect_file_type",
]
