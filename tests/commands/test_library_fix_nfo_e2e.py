"""E2E tests for ``personalscraper library-fix-nfo`` — CLI-level harness.

Covers smoke, dry-run preview, apply mode, idempotence, safety gate,
error handling, output schema, and BDD closure-of-loop.
"""

from __future__ import annotations

import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from tests.commands._e2e_helpers import (
    make_synthetic_db,
    run_cli,
)


def _json_from_result(result: Any) -> dict[str, Any]:
    """Extract the JSON dict from CliRunner output.

    The command emits structlog lines (Python repr) before the final
    ``typer.echo(json.dumps(...))``.  Find the *last* JSON object so the
    structlog ``{...}`` reprs don't confuse the parser.
    """
    raw: str = result.output.strip()
    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    start = clean.rfind("{")
    if start == -1:
        raise ValueError(f"No JSON object found in output: {raw!r}")
    return json.loads(clean[start:])  # type: ignore[no-any-return]


def _insert_media_item(
    conn: sqlite3.Connection,
    title: str = "Test Show",
    kind: str = "show",
    category_id: str = "tv_shows",
) -> int:
    """Insert a minimal media_item row and return its id."""
    now = 1700000000
    cursor = conn.execute(
        """
        INSERT INTO media_item (kind, title, title_sort, category_id, date_created, date_modified)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (kind, title, title, category_id, now, now),
    )
    conn.commit()
    rowid = cursor.lastrowid
    assert rowid is not None
    return rowid


def _set_dispatch_path(conn: sqlite3.Connection, item_id: int, path: str) -> None:
    """Set the dispatch_path attribute on a media_item."""
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
        (item_id, path),
    )
    conn.commit()


def _run_fix_nfo(args: list[str], db_path: Path) -> "Any":  # noqa: F821
    """Run library-fix-nfo with --db pointing at the synthetic DB."""
    return run_cli(["library-fix-nfo", "--db", str(db_path), *args])


def _well_formed_tvshow_nfo(title: str = "My Show") -> str:
    """Return a well-formed tvshow.nfo XML string."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<tvshow>\n"
        f"  <title>{title}</title>\n"
        '  <uniqueid type="tvdb" default="true">12345</uniqueid>\n'
        "</tvshow>\n"
    )


def _trailing_url_tvshow_nfo(title: str = "Show With Trailing URL") -> str:
    """Return a tvshow.nfo with a trailing TVDB URL after the root close tag."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<tvshow>\n"
        f"  <title>{title}</title>\n"
        "</tvshow>\n"
        "https://thetvdb.com/series/12345\n"
    )


def _trailing_url_movie_nfo(title: str = "Movie With Trailing URL") -> str:
    """Return a movie.nfo with a trailing TMDB URL after the root close tag."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<movie>\n"
        f"  <title>{title}</title>\n"
        "</movie>\n"
        "https://www.themoviedb.org/movie/12345\n"
    )


def _trailing_arbitrary_tvshow_nfo(title: str = "Show With Unsafe Trailing") -> str:
    """Return a tvshow.nfo with arbitrary XML after the root close tag."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<tvshow>\n"
        f"  <title>{title}</title>\n"
        "</tvshow>\n"
        "<comment>arbitrary XML fragment</comment>\n"
    )


def _malformed_body_tvshow_nfo(title: str = "Broken Show") -> str:
    """Return a tvshow.nfo whose body is malformed + trailing URL."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<tvshow>\n"
        f"  <title>{title}</title>\n"
        "  <unclosed>\n"
        "</tvshow>\n"
        "https://thetvdb.com/series/99999\n"
    )


def _no_root_close_tvshow_nfo(title: str = "Incomplete Show") -> str:
    """Return a tvshow.nfo with NO root close tag."""
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<tvshow>\n  <title>{title}</title>\n'


# ── 1. Smoke ─────────────────────────────────────────────────────────────────────


def test_fix_nfo_help_exits_zero() -> None:
    """``library-fix-nfo --help`` exits 0."""
    result = run_cli(["library-fix-nfo", "--help"])
    assert result.exit_code == 0


# ── 2. Realistic dry-run preview ─────────────────────────────────────────────────


def test_fix_nfo_dry_run_preview_counts(tmp_path: Path, test_config) -> None:
    """Dry-run reports correct counters without mutating files."""
    db_path = make_synthetic_db(tmp_path)

    # Show A: well-formed.
    show_a = tmp_path / "ShowA"
    show_a.mkdir()
    (show_a / "tvshow.nfo").write_text(_well_formed_tvshow_nfo("Show A"))

    # Show B: trailing TVDB URL (would fix).
    show_b = tmp_path / "ShowB"
    show_b.mkdir()
    (show_b / "tvshow.nfo").write_text(_trailing_url_tvshow_nfo("Show B"))

    # Show C: trailing arbitrary text (unsafe).
    show_c = tmp_path / "ShowC"
    show_c.mkdir()
    (show_c / "tvshow.nfo").write_text(_trailing_arbitrary_tvshow_nfo("Show C"))

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    for title, d in [("Show A", show_a), ("Show B", show_b), ("Show C", show_c)]:
        item_id = _insert_media_item(conn, title=title)
        _set_dispatch_path(conn, item_id, str(d))
    conn.close()

    result = _run_fix_nfo([], db_path)
    assert result.exit_code == 0, result.output

    data = _json_from_result(result)
    assert data["apply"] is False
    assert data["items_scanned"] == 3
    assert data["nfo_resolved"] == 3
    assert data["nfo_missing"] == 0
    assert data["already_ok"] == 1
    assert data["unsafe_trailing"] == 1
    assert data["would_fix"] == 1
    assert "fixed" not in data

    # No .nfo.bak files created in dry-run.
    assert not list(tmp_path.rglob("*.nfo.bak"))

    # NFO file contents unchanged.
    assert "https://thetvdb.com/series/12345" in (show_b / "tvshow.nfo").read_text()
    assert "<comment>arbitrary XML fragment</comment>" in (show_c / "tvshow.nfo").read_text()


# ── 3. Apply mode ────────────────────────────────────────────────────────────────


def test_fix_nfo_apply_fixes_trailing_url(tmp_path: Path, test_config) -> None:
    """--apply truncates trailing URL and creates .bak backup."""
    db_path = make_synthetic_db(tmp_path)

    show_dir = tmp_path / "ShowB"
    show_dir.mkdir()
    original = _trailing_url_tvshow_nfo("Show B")
    (show_dir / "tvshow.nfo").write_text(original)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    item_id = _insert_media_item(conn, title="Show B")
    _set_dispatch_path(conn, item_id, str(show_dir))
    conn.close()

    result = _run_fix_nfo(["--apply"], db_path)
    assert result.exit_code == 0, result.output

    data = _json_from_result(result)
    assert data["apply"] is True
    assert data["fixed"] == 1

    # .bak file exists with original content.
    bak_path = show_dir / "tvshow.nfo.bak"
    assert bak_path.exists()
    assert bak_path.read_text() == original

    # Fixed NFO no longer has trailing URL and parses OK.
    fixed_content = (show_dir / "tvshow.nfo").read_bytes()
    assert b"https://thetvdb.com" not in fixed_content
    ET.parse(str(show_dir / "tvshow.nfo"))  # does not raise


def test_fix_nfo_apply_fixes_trailing_url_movie(tmp_path: Path, test_config) -> None:
    """--apply truncates trailing TMDB URL on a movie NFO."""
    db_path = make_synthetic_db(tmp_path)

    movie_dir = tmp_path / "MovieTest"
    movie_dir.mkdir()
    original = _trailing_url_movie_nfo("Movie Test")
    (movie_dir / "movie.nfo").write_text(original)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    item_id = _insert_media_item(conn, title="Movie Test", kind="movie", category_id="movies")
    _set_dispatch_path(conn, item_id, str(movie_dir))
    conn.close()

    result = _run_fix_nfo(["--apply"], db_path)
    assert result.exit_code == 0, result.output

    data = _json_from_result(result)
    assert data["fixed"] == 1

    fixed_content = (movie_dir / "movie.nfo").read_bytes()
    assert b"themoviedb.org" not in fixed_content
    ET.parse(str(movie_dir / "movie.nfo"))  # does not raise


# ── 4. Idempotence ───────────────────────────────────────────────────────────────


def test_fix_nfo_idempotent_after_fix(tmp_path: Path, test_config) -> None:
    """Re-running --apply on an already-fixed item reports already_ok."""
    db_path = make_synthetic_db(tmp_path)

    show_dir = tmp_path / "ShowB"
    show_dir.mkdir()
    (show_dir / "tvshow.nfo").write_text(_trailing_url_tvshow_nfo("Show B"))

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    item_id = _insert_media_item(conn, title="Show B")
    _set_dispatch_path(conn, item_id, str(show_dir))
    conn.close()

    # First run: fix.
    result1 = _run_fix_nfo(["--apply"], db_path)
    assert result1.exit_code == 0
    data1 = _json_from_result(result1)
    assert data1["fixed"] == 1

    # Second run: already ok.
    result2 = _run_fix_nfo(["--apply"], db_path)
    assert result2.exit_code == 0
    data2 = _json_from_result(result2)
    assert data2["fixed"] == 0
    assert data2["already_ok"] == 1


# ── 5. Safety gate — unsafe trailing skipped ─────────────────────────────────────


def test_fix_nfo_unsafe_trailing_skipped(tmp_path: Path, test_config) -> None:
    """Trailing XML comments (not whitelisted URLs) are NOT truncated."""
    db_path = make_synthetic_db(tmp_path)

    show_dir = tmp_path / "ShowC"
    show_dir.mkdir()
    original = _trailing_arbitrary_tvshow_nfo("Show C")
    (show_dir / "tvshow.nfo").write_text(original)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    item_id = _insert_media_item(conn, title="Show C")
    _set_dispatch_path(conn, item_id, str(show_dir))
    conn.close()

    result = _run_fix_nfo(["--apply"], db_path)
    assert result.exit_code == 0, result.output

    data = _json_from_result(result)
    assert data["unsafe_trailing"] == 1
    assert data["fixed"] == 0

    # Original NFO unchanged.
    assert (show_dir / "tvshow.nfo").read_text() == original

    # No .bak written.
    assert not (show_dir / "tvshow.nfo.bak").exists()


# ── 6. Errors ────────────────────────────────────────────────────────────────────


def test_fix_nfo_nfo_missing_file_not_on_disk(tmp_path: Path, test_config) -> None:
    """Item with dispatch_path but no NFO file on disk → nfo_missing."""
    db_path = make_synthetic_db(tmp_path)

    show_dir = tmp_path / "MissingNfo"
    show_dir.mkdir()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    item_id = _insert_media_item(conn, title="Missing NFO")
    _set_dispatch_path(conn, item_id, str(show_dir))
    conn.close()

    result = _run_fix_nfo([], db_path)
    assert result.exit_code == 0, result.output

    data = _json_from_result(result)
    assert data["items_scanned"] == 1
    assert data["nfo_missing"] == 1
    assert data["nfo_resolved"] == 0


def test_fix_nfo_still_malformed_counted(tmp_path: Path, test_config) -> None:
    """Trailing URL is safe but NFO body is itself broken → still_malformed."""
    db_path = make_synthetic_db(tmp_path)

    show_dir = tmp_path / "BrokenShow"
    show_dir.mkdir()
    original = _malformed_body_tvshow_nfo("Broken Show")
    (show_dir / "tvshow.nfo").write_text(original)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    item_id = _insert_media_item(conn, title="Broken Show")
    _set_dispatch_path(conn, item_id, str(show_dir))
    conn.close()

    result = _run_fix_nfo(["--apply"], db_path)
    assert result.exit_code == 0, result.output

    data = _json_from_result(result)
    assert data["still_malformed"] == 1
    assert data["fixed"] == 0


def test_fix_nfo_no_root_close_counted(tmp_path: Path, test_config) -> None:
    """NFO with no root close tag → no_root_close."""
    db_path = make_synthetic_db(tmp_path)

    show_dir = tmp_path / "IncompleteShow"
    show_dir.mkdir()
    original = _no_root_close_tvshow_nfo("Incomplete Show")
    (show_dir / "tvshow.nfo").write_text(original)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    item_id = _insert_media_item(conn, title="Incomplete Show")
    _set_dispatch_path(conn, item_id, str(show_dir))
    conn.close()

    result = _run_fix_nfo([], db_path)
    assert result.exit_code == 0, result.output

    data = _json_from_result(result)
    assert data["no_root_close"] == 1
    assert data["would_fix"] == 0


def test_fix_nfo_apple_double_counter_present(tmp_path: Path, test_config) -> None:
    """skipped_apple_double counter is present in output (belt-and-suspenders guard)."""
    db_path = make_synthetic_db(tmp_path)

    show_dir = tmp_path / "ShowA"
    show_dir.mkdir()
    (show_dir / "tvshow.nfo").write_text(_well_formed_tvshow_nfo("Show A"))

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    item_id = _insert_media_item(conn, title="Show A")
    _set_dispatch_path(conn, item_id, str(show_dir))
    conn.close()

    result = _run_fix_nfo(["--apply"], db_path)
    assert result.exit_code == 0, result.output

    data = _json_from_result(result)
    assert "skipped_apple_double" in data
    assert data["skipped_apple_double"] == 0


# ── 7. Output schema ─────────────────────────────────────────────────────────────


def test_fix_nfo_output_schema_all_keys_present(tmp_path: Path, test_config) -> None:
    """JSON output contains all expected keys with correct types."""
    db_path = make_synthetic_db(tmp_path)

    show_ok = tmp_path / "ShowOK"
    show_ok.mkdir()
    (show_ok / "tvshow.nfo").write_text(_well_formed_tvshow_nfo("OK"))

    show_url = tmp_path / "ShowURL"
    show_url.mkdir()
    (show_url / "tvshow.nfo").write_text(_trailing_url_tvshow_nfo("URL"))

    show_unsafe = tmp_path / "ShowUnsafe"
    show_unsafe.mkdir()
    (show_unsafe / "tvshow.nfo").write_text(_trailing_arbitrary_tvshow_nfo("Unsafe"))

    show_missing = tmp_path / "ShowMissing"
    show_missing.mkdir()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    for title, d in [
        ("OK", show_ok),
        ("URL", show_url),
        ("Unsafe", show_unsafe),
        ("Missing", show_missing),
    ]:
        item_id = _insert_media_item(conn, title=title)
        _set_dispatch_path(conn, item_id, str(d))
    conn.close()

    result = _run_fix_nfo(["--apply"], db_path)
    assert result.exit_code == 0, result.output

    data = _json_from_result(result)
    required_keys = [
        "apply",
        "items_scanned",
        "nfo_resolved",
        "nfo_missing",
        "already_ok",
        "no_root_close",
        "unsafe_trailing",
        "still_malformed",
        "fixed",
        "skipped_apple_double",
    ]
    for key in required_keys:
        assert key in data, f"Missing key: {key}"
        assert isinstance(data[key], int) or isinstance(data[key], bool), (
            f"Key {key} has unexpected type: {type(data[key])}"
        )

    assert data["items_scanned"] == 4
    assert data["nfo_resolved"] == 3
    assert data["nfo_missing"] == 1
    assert data["already_ok"] == 1
    assert data["fixed"] == 1
    assert data["unsafe_trailing"] == 1


# ── 8. Closure-of-loop — BDD unchanged ───────────────────────────────────────────


def test_fix_nfo_does_not_mutate_db(tmp_path: Path, test_config) -> None:
    """The fix command does not touch the indexer DB."""
    db_path = make_synthetic_db(tmp_path)

    show_dir = tmp_path / "ShowB"
    show_dir.mkdir()
    (show_dir / "tvshow.nfo").write_text(_trailing_url_tvshow_nfo("Show B"))

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    item_id = _insert_media_item(conn, title="Show B")
    _set_dispatch_path(conn, item_id, str(show_dir))
    conn.close()

    before_hash = _db_sha256(db_path)

    result = _run_fix_nfo(["--apply"], db_path)
    assert result.exit_code == 0, result.output

    after_hash = _db_sha256(db_path)
    assert before_hash == after_hash, "DB was mutated by library-fix-nfo"


def _db_sha256(db_path: Path) -> str:
    """Return SHA-256 hex digest of the DB file."""
    import hashlib

    return hashlib.sha256(db_path.read_bytes()).hexdigest()
