"""Sorter package — media file type detection, name cleaning, and sorting.

Detects file types, cleans filenames via guessit, and sorts items from
the staging root into categorized subdirectories
({movies_dir}, {tvshows_dir}, {audio_dir}, etc.).
"""

from personalscraper.sorter.file_type import FileType, detect_dir_type, detect_file_type
from personalscraper.sorter.matcher import find_matching_directory

__all__ = [
    "FileType",
    "detect_dir_type",
    "detect_file_type",
    "find_matching_directory",
]
