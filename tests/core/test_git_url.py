"""Tests for core/git_url (bosun sub-phase 4.1)."""

from __future__ import annotations

import pytest
from kanbanmate.core.git_url import validate_git_url


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/LounisBou/KanbanMate",
        "https://github.com/LounisBou/KanbanMate.git",
    ],
)
def test_https_github_accepted(url: str) -> None:
    assert validate_git_url(url) is None


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ssh://git@github.com/o/r.git",
        "git://github.com/o/r.git",
        "git@github.com:o/r.git",  # scp-style — no scheme separator
        "https://evil.example.com/o/r.git",  # host not allowlisted
        "https://github.com/onlyowner",  # missing repo segment
        "https://github.com/owner/..",  # traversal repo name → clone dir escapes the base
        "https://github.com/../repo",  # traversal owner segment
        "https://github.com/owner/.",  # current-dir repo name
        "https://github.com/owner/.git",  # strips to an empty repo name → target == base dir
        "https://user:pass@github.com/owner/repo",  # embedded credentials → leak to .git/config + ps
        "https://token@github.com/owner/repo.git",  # username-only credential
        "",
    ],
)
def test_disallowed_rejected(url: str) -> None:
    assert validate_git_url(url) is not None
