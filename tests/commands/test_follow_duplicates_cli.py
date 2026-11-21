"""``acquisition-follow-duplicates``: read-only report of the provider ids two or more follows hold.

The output is codes and counts (no sentence); ``acquire.db`` is opened read only, so the
report can run against a copy of production's file.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

from personalscraper.acquire.store import build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.i18n import t
from tests.commands._e2e_helpers import run_cli


def _json_from(result: Any) -> dict[str, Any]:
    """Extract the last JSON object from CLI output (strips ANSI codes).

    Args:
        result: CliRunner result.

    Returns:
        The decoded payload.
    """
    raw = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    return json.loads(raw[raw.find("{") :])


def _seed_duplicates(db_path: Path) -> None:
    """Migrate an acquire.db and write one show twice (tvdb 81189) beside a lone film.

    Args:
        db_path: Where the store is created.
    """
    store = build_acquire_store(AcquireConfig(db_path=db_path))
    try:
        store.follow.list_all()  # creates the file and applies the migrations
    finally:
        store.close()
    conn = sqlite3.connect(db_path)
    rows = [
        ('{"tvdb_id": 81189, "tmdb_id": null, "imdb_id": null}', "Breaking Bad", 1),
        ('{"tvdb_id": 81189, "tmdb_id": 1396, "imdb_id": null}', "Breaking Bad", 0),
        ('{"tvdb_id": null, "tmdb_id": 603, "imdb_id": null}', "The Matrix", 1),
    ]
    conn.executemany(
        "INSERT INTO followed_series (media_ref_json, title, active, added_at) VALUES (?, ?, ?, 1)",
        rows,
    )
    conn.commit()
    conn.close()


def test_report_is_codes_and_counts(tmp_path: Path, test_config: Any) -> None:
    """The report counts the shared ids and the follows involved, and names each follow by rowid."""
    db_path = tmp_path / "acquire.db"
    _seed_duplicates(db_path)

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "acquisition-follow-duplicates", "--db", str(db_path)])

    assert result.exit_code == 0, result.output
    assert _json_from(result) == {
        "groups": 1,
        "follows": 2,
        "duplicates": [{"provider": "tvdb", "provider_id": 81189, "followed_ids": [1, 2]}],
    }


def test_report_writes_nothing(tmp_path: Path, test_config: Any) -> None:
    """The command leaves the database byte-identical (opened read only, never migrated)."""
    db_path = tmp_path / "acquire.db"
    _seed_duplicates(db_path)
    before = db_path.read_bytes()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "acquisition-follow-duplicates", "--db", str(db_path)])

    assert result.exit_code == 0, result.output
    assert db_path.read_bytes() == before


def test_report_reads_the_configured_store(test_config: Any) -> None:
    """Without ``--db`` the command reads ``acquire.db_path`` from the configuration."""
    db_path = Path(test_config.acquire.db_path)
    _seed_duplicates(db_path)

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "acquisition-follow-duplicates"])

    assert result.exit_code == 0, result.output
    assert _json_from(result)["groups"] == 1


def test_a_missing_database_is_refused_and_never_created(tmp_path: Path, test_config: Any) -> None:
    """An absent file exits 1 with the catalogue's message, and no empty store is left behind."""
    missing = tmp_path / "absent.db"

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "acquisition-follow-duplicates", "--db", str(missing)])

    assert result.exit_code == 1
    assert t("cli_acquisition.follow_duplicates.db_not_found", path=str(missing)) in result.output
    assert not missing.exists()
