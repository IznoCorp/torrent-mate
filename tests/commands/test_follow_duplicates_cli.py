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


def _seed(db_path: Path, rows: list[tuple[str, str, int, str]]) -> None:
    """Migrate an acquire.db, write *rows*, then drop the migration lock's sidecars.

    Args:
        db_path: Where the store is created.
        rows: ``(media_ref_json, title, active, kind)`` per follow.
    """
    store = build_acquire_store(AcquireConfig(db_path=db_path))
    try:
        store.follow.list_all()  # creates the file and applies the migrations
    finally:
        store.close()
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT INTO followed_series (media_ref_json, title, active, added_at, kind) VALUES (?, ?, ?, 1, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    for sidecar in (Path(f"{db_path}.lock"), Path(f"{db_path}.lock.json")):
        sidecar.unlink(missing_ok=True)


def _seed_duplicates(db_path: Path) -> None:
    """Write one show twice (tvdb 81189), a film sharing its TMDB number, and a lone film.

    Args:
        db_path: Where the store is created.
    """
    _seed(
        db_path,
        [
            ('{"tvdb_id": 81189, "tmdb_id": null, "imdb_id": null}', "Breaking Bad", 1, "show"),
            ('{"tvdb_id": 81189, "tmdb_id": 1396, "imdb_id": null}', "Breaking Bad", 0, "show"),
            ('{"tvdb_id": null, "tmdb_id": 1396, "imdb_id": null}', "A Film", 0, "movie"),
            ('{"tvdb_id": null, "tmdb_id": 603, "imdb_id": null}', "The Matrix", 1, "movie"),
        ],
    )


def test_report_is_codes_and_counts(tmp_path: Path, test_config: Any) -> None:
    """The report counts the shared ids and the follows involved, names each follow by rowid, keys TMDB by kind."""
    db_path = tmp_path / "acquire.db"
    _seed_duplicates(db_path)

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "acquisition-follow-duplicates", "--db", str(db_path)])

    assert result.exit_code == 0, result.output
    assert _json_from(result) == {
        "groups": 1,
        "follows": 2,
        "duplicates": [{"provider": "tvdb", "provider_id": 81189, "kind": "show", "followed_ids": [1, 2]}],
    }


def test_report_counts_a_follow_in_two_groups_once(tmp_path: Path, test_config: Any) -> None:
    """Two rows sharing their TVDB and TMDB ids make two groups and two follows, not four."""
    db_path = tmp_path / "acquire.db"
    _seed(
        db_path,
        [
            ('{"tvdb_id": 81189, "tmdb_id": 1396, "imdb_id": null}', "Breaking Bad", 1, "show"),
            ('{"tvdb_id": 81189, "tmdb_id": 1396, "imdb_id": "tt0903747"}', "Breaking Bad", 0, "show"),
        ],
    )

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "acquisition-follow-duplicates", "--db", str(db_path)])

    assert result.exit_code == 0, result.output
    payload = _json_from(result)
    assert (payload["groups"], payload["follows"]) == (2, 2)


def test_report_writes_nothing(tmp_path: Path, test_config: Any) -> None:
    """The command leaves the database byte-identical and takes no migration lock (opened read only)."""
    db_path = tmp_path / "acquire.db"
    _seed_duplicates(db_path)
    before = db_path.read_bytes()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "acquisition-follow-duplicates", "--db", str(db_path)])

    assert result.exit_code == 0, result.output
    assert db_path.read_bytes() == before
    assert not Path(f"{db_path}.lock").exists(), "a store open takes the migration lock; a report must not"


def test_the_subcommand_config_wins_over_the_root_one(tmp_path: Path, test_config: Any) -> None:
    """``acquisition-follow-duplicates --config`` reads that configuration's store, not the root's."""
    other_config = test_config.model_copy(
        update={"acquire": test_config.acquire.model_copy(update={"db_path": tmp_path / "other.db"})}
    )
    _seed_duplicates(tmp_path / "other.db")
    chosen = tmp_path / "other-config"

    def load(path: Path | None = None) -> Any:
        return other_config if path == chosen else test_config

    with patch("personalscraper.conf.loader.load_config", side_effect=load):
        result = run_cli(["--format", "json", "acquisition-follow-duplicates", "--config", str(chosen)])

    assert result.exit_code == 0, result.output
    assert _json_from(result)["groups"] == 1


def test_a_file_that_is_no_store_is_refused(tmp_path: Path, test_config: Any) -> None:
    """A file that is not an acquire.db exits 1 with the catalogue's message, not a traceback."""
    not_a_store = tmp_path / "notes.db"
    not_a_store.write_bytes(b"not a database at all, just text" * 64)

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "acquisition-follow-duplicates", "--db", str(not_a_store)])

    assert result.exit_code == 1
    refusal = t("cli_acquisition.follow_duplicates.db_unreadable", path=str(not_a_store), error="")
    assert refusal.strip() in result.output


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
