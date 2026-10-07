"""Tests for the design host's served identity when its tree carries no repository.

tm-design serves an rsync copy of the build tree, which has no `.git`, so the host
could run no `git` command and published nothing: the drawer said the identity was
unavailable (B-713). The deploy now leaves a stamp in the served tree, and the host
reads it when git cannot answer. Git stays first: a tree that IS a repository is
described by what it holds now, never by a file that may be older.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from _repo_paths import MAQUETTE

sys.path.insert(0, str(MAQUETTE))
import host_identity  # noqa: E402

STAMP = ".served-identity.json"
PUBLISHED = {"branch": "develop", "detached": False, "commit": "1470bdd71", "dirty": False}


def write_stamp(root, payload) -> None:
    """Writes the deploy's stamp into a served tree.

    Args:
        root: The served tree.
        payload: What the stamp holds; a string is written as it is.
    """
    text = payload if isinstance(payload, str) else json.dumps(payload)
    (root / STAMP).write_text(text, encoding="utf-8")


def test_a_tree_without_a_repository_is_described_by_its_stamp(tmp_path):
    write_stamp(tmp_path, PUBLISHED)
    assert host_identity.served_identity(tmp_path) == PUBLISHED


def test_the_stamp_reaches_the_document(tmp_path):
    write_stamp(tmp_path, PUBLISHED)
    page = host_identity.with_served_identity(b"<html><head></head></html>", tmp_path)
    assert b'id="served-identity">' + json.dumps(PUBLISHED).encode() in page


def test_a_tree_without_repository_nor_stamp_publishes_nothing(tmp_path):
    assert host_identity.served_identity(tmp_path) is None


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        [],
        {},
        {**PUBLISHED, "commit": ""},
        {**PUBLISHED, "dirty": "no"},
        {"branch": "develop", "detached": False, "commit": "abc"},
        {**PUBLISHED, "branch": "", "detached": False},
    ],
)
def test_an_unusable_stamp_publishes_nothing(tmp_path, payload):
    write_stamp(tmp_path, payload)
    assert host_identity.served_identity(tmp_path) is None


def test_a_detached_stamp_needs_no_branch(tmp_path):
    detached = {"branch": "", "detached": True, "commit": "abc1234", "dirty": False}
    write_stamp(tmp_path, detached)
    assert host_identity.served_identity(tmp_path) == detached


def test_a_stamp_carries_only_the_four_fields(tmp_path):
    write_stamp(tmp_path, {**PUBLISHED, "extra": "x"})
    assert host_identity.served_identity(tmp_path) == PUBLISHED


def test_a_repository_is_read_before_the_stamp(tmp_path):
    for arguments in (["init", "--initial-branch", "live-branch"],
                      ["config", "user.email", "test@example.invalid"],
                      ["config", "user.name", "test"],
                      ["commit", "--allow-empty", "-m", "seed"]):
        subprocess.run(["git", *arguments], cwd=tmp_path, capture_output=True, check=True)
    write_stamp(tmp_path, PUBLISHED)
    identity = host_identity.served_identity(tmp_path)
    assert identity is not None and identity["branch"] == "live-branch"
