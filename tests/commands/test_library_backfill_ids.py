"""Regression tests for ``personalscraper library-backfill-ids`` CLI command (sub-phase 2.6).

Verifies:
- ``library-backfill-ids --help`` exits 0 (smoke test, existence proof).
- ``library-backfill-ids`` dispatches to ``run_backfill_ids()`` (spy).
- ``library-backfill-ids --dry-run`` does NOT open/write the DB and returns
  dry_run: true in JSON output.
- ``--show``, ``--ids-only``, ``--ratings-only`` are forwarded to the driver.
- Missing ``indexer.db_path`` exits non-zero with a clear error.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.indexer.scanner._modes.backfill_ids import BackfillStats

runner = CliRunner()

# ── patch targets ─────────────────────────────────────────────────────────────

_OPEN_DB = "personalscraper.indexer.db.open_db"
_APPLY_MIGRATIONS = "personalscraper.indexer.db.apply_migrations"
_RUN_BACKFILL = "personalscraper.indexer.scanner._modes.backfill_ids.run_backfill_ids"


def _empty_stats(**overrides: object) -> BackfillStats:
    """Build a zeroed BackfillStats, optionally overriding fields.

    Args:
        **overrides: Field name → value overrides applied to the default
            zero-valued :class:`BackfillStats`.

    Returns:
        A :class:`BackfillStats` instance suitable for mock return values.
    """
    s = BackfillStats()
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def _conn_mock() -> MagicMock:
    """Return a minimal sqlite3.Connection stub.

    Returns:
        MagicMock satisfying the open_db / apply_migrations / commit / close contract.
    """
    m = MagicMock()
    m.execute.return_value.fetchone.return_value = [0]
    m.execute.return_value.fetchall.return_value = []
    return m


# ── 1. Smoke / existence ──────────────────────────────────────────────────────


class TestLibraryBackfillIdsHelp:
    """``library-backfill-ids --help`` must exist and exit 0."""

    def test_help_exits_zero(self) -> None:
        """``library-backfill-ids --help`` exits 0 — proves the command is registered."""
        result = runner.invoke(app, ["library-backfill-ids", "--help"])
        assert result.exit_code == 0, result.output

    def test_help_mentions_dry_run(self) -> None:
        """``--dry-run`` is documented in the help text."""
        result = runner.invoke(app, ["library-backfill-ids", "--help"])
        assert "--dry-run" in result.output

    def test_help_mentions_show_flag(self) -> None:
        """``--show`` is documented in the help text."""
        result = runner.invoke(app, ["library-backfill-ids", "--help"])
        assert "--show" in result.output

    def test_help_mentions_ids_only(self) -> None:
        """``--ids-only`` is documented in the help text."""
        result = runner.invoke(app, ["library-backfill-ids", "--help"])
        assert "--ids-only" in result.output

    def test_help_mentions_ratings_only(self) -> None:
        """``--ratings-only`` is documented in the help text."""
        result = runner.invoke(app, ["library-backfill-ids", "--help"])
        assert "--ratings-only" in result.output


# ── 2. Dispatch to run_backfill_ids ──────────────────────────────────────────


class TestLibraryBackfillIdsDispatch:
    """``library-backfill-ids`` calls ``run_backfill_ids`` with the right arguments."""

    def test_dispatches_to_run_backfill_ids(self, test_config) -> None:
        """The command invokes ``run_backfill_ids`` exactly once."""
        conn_mock = _conn_mock()
        calls: list[dict] = []

        def _spy(**kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return _empty_stats()

        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
            patch(_RUN_BACKFILL, side_effect=lambda conn, **kw: _spy(**kw) or _empty_stats()),
        ):
            result = runner.invoke(app, ["library-backfill-ids"])

        assert result.exit_code == 0, result.output
        assert len(calls) == 1

    def test_show_filter_forwarded(self, test_config) -> None:
        """``--show 'Breaking Bad'`` is forwarded as ``show_filter`` to the driver."""
        conn_mock = _conn_mock()
        calls: list[dict] = []

        def _capturing_backfill(conn, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return _empty_stats()

        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
            patch(_RUN_BACKFILL, side_effect=_capturing_backfill),
        ):
            result = runner.invoke(app, ["library-backfill-ids", "--show", "Breaking Bad"])

        assert result.exit_code == 0, result.output
        assert calls[0]["show_filter"] == "Breaking Bad"

    def test_ids_only_forwarded(self, test_config) -> None:
        """``--ids-only`` is forwarded as ``ids_only=True`` to the driver."""
        conn_mock = _conn_mock()
        calls: list[dict] = []

        def _capturing_backfill(conn, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return _empty_stats()

        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
            patch(_RUN_BACKFILL, side_effect=_capturing_backfill),
        ):
            result = runner.invoke(app, ["library-backfill-ids", "--ids-only"])

        assert result.exit_code == 0, result.output
        assert calls[0]["ids_only"] is True

    def test_ratings_only_forwarded(self, test_config) -> None:
        """``--ratings-only`` is forwarded as ``ratings_only=True`` to the driver."""
        conn_mock = _conn_mock()
        calls: list[dict] = []

        def _capturing_backfill(conn, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return _empty_stats()

        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
            patch(_RUN_BACKFILL, side_effect=_capturing_backfill),
        ):
            result = runner.invoke(app, ["library-backfill-ids", "--ratings-only"])

        assert result.exit_code == 0, result.output
        assert calls[0]["ratings_only"] is True

    def test_commit_called_on_success(self, test_config) -> None:
        """``conn.commit()`` is called after a successful (non-dry-run) pass."""
        conn_mock = _conn_mock()

        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
            patch(_RUN_BACKFILL, return_value=_empty_stats()),
        ):
            result = runner.invoke(app, ["library-backfill-ids"])

        assert result.exit_code == 0, result.output
        conn_mock.commit.assert_called_once()

    def test_close_called_on_success(self, test_config) -> None:
        """``conn.close()`` is called in the finally block after a successful pass."""
        conn_mock = _conn_mock()

        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
            patch(_RUN_BACKFILL, return_value=_empty_stats()),
        ):
            result = runner.invoke(app, ["library-backfill-ids"])

        assert result.exit_code == 0, result.output
        conn_mock.close.assert_called_once()

    def test_output_json_contains_stats(self, test_config) -> None:
        """The CLI prints a JSON summary containing the BackfillStats fields."""
        conn_mock = _conn_mock()
        fake_stats = _empty_stats(items_scanned=5, items_updated=3, ids_added_count=6)

        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
            patch(_RUN_BACKFILL, return_value=fake_stats),
        ):
            result = runner.invoke(app, ["library-backfill-ids"])

        assert result.exit_code == 0, result.output
        raw = result.output.strip()
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        assert json_line is not None, f"No JSON line in output: {raw!r}"
        data = json.loads(json_line)
        assert data["items_scanned"] == 5
        assert data["items_updated"] == 3
        assert data["ids_added_count"] == 6
        assert data["dry_run"] is False


# ── 3. --dry-run ──────────────────────────────────────────────────────────────


class TestLibraryBackfillIdsDryRun:
    """``library-backfill-ids --dry-run`` runs the driver with dry_run=True."""

    def test_dry_run_forwarded_to_driver(self, test_config) -> None:
        """``--dry-run`` passes ``dry_run=True`` to ``run_backfill_ids``."""
        conn_mock = _conn_mock()
        calls: list[dict] = []

        def _capturing_backfill(conn, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return _empty_stats()

        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
            patch(_RUN_BACKFILL, side_effect=_capturing_backfill),
        ):
            result = runner.invoke(app, ["library-backfill-ids", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert calls[0]["dry_run"] is True

    def test_dry_run_does_not_commit(self, test_config) -> None:
        """``--dry-run`` must NOT call ``conn.commit()`` — no DB writes."""
        conn_mock = _conn_mock()

        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
            patch(_RUN_BACKFILL, return_value=_empty_stats()),
        ):
            result = runner.invoke(app, ["library-backfill-ids", "--dry-run"])

        assert result.exit_code == 0, result.output
        conn_mock.commit.assert_not_called()

    def test_dry_run_outputs_dry_run_true(self, test_config) -> None:
        """``--dry-run`` sets ``dry_run: true`` in the JSON output."""
        conn_mock = _conn_mock()

        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
            patch(_RUN_BACKFILL, return_value=_empty_stats()),
        ):
            result = runner.invoke(app, ["library-backfill-ids", "--dry-run"])

        assert result.exit_code == 0, result.output
        raw = result.output.strip()
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        assert json_line is not None
        data = json.loads(json_line)
        assert data["dry_run"] is True

    def test_dry_run_skips_client_construction(self, test_config) -> None:
        """``--dry-run`` skips building TMDB/TVDB/IMDb/RT clients (no API keys needed)."""
        conn_mock = _conn_mock()
        calls: list[dict] = []

        def _capturing_backfill(conn, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return _empty_stats()

        # No API keys in env — clients should remain None in dry-run mode.
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
            patch(_RUN_BACKFILL, side_effect=_capturing_backfill),
            patch.dict("os.environ", {}, clear=False),
        ):
            result = runner.invoke(app, ["library-backfill-ids", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert calls[0]["tmdb_client"] is None
        assert calls[0]["tvdb_client"] is None
        assert calls[0]["imdb_client"] is None
        assert calls[0]["rt_client"] is None


# ── 4. Missing db_path guard ──────────────────────────────────────────────────


class TestLibraryBackfillIdsMissingDbPath:
    """``library-backfill-ids`` exits non-zero when ``indexer.db_path`` is None."""

    def test_missing_db_path_exits_nonzero(self, test_config) -> None:
        """When ``cfg.indexer.db_path`` is None the command exits with code 1."""
        # Patch the db_path on the indexer config to None.
        cfg_no_db = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})

        with patch("personalscraper.conf.loader.load_config", return_value=cfg_no_db):
            result = runner.invoke(app, ["library-backfill-ids"])

        assert result.exit_code != 0
