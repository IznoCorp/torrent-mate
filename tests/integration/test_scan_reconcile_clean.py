"""Integration test: scan → reconcile finds zero drift (MUST-16 / BD-AG).

The invariant "a fully-seeded, aligned library produces zero reconcile
findings" is the baseline correctness check for the reconcile pipeline.
If this test fails, it means either:

  (a) the seeded fixture (BD-AF) contains inconsistencies, or
  (b) a change to a reconcile detector introduced a false positive.

Test plan (4 steps):

  1. **Seed** — obtain a :class:`~tests.integration.fixtures.seeded_library_fs.SeededLibrary`
     via the :func:`seeded_library_fs` fixture: FS + DB in perfect
     alignment (10 items, ~64 files, correct season counts, valid
     dispatch_path attributes, no orphan releases).

  2. **Assert fixture invariants** — sanity-check the fixture itself so
     that if the fixture is broken the failure message is immediately
     actionable (BD-AF self-check).

  3. **Run reconcile** — call :func:`~personalscraper.indexer.reconcile.reconcile`
     directly on the open connection.  No CLI invocation is required; the
     reconcile function is the same code path the ``library-reconcile``
     command delegates to.  This avoids the need to mock the config /
     CLI layer while still exercising the detector logic end-to-end.

  4. **Assert zero findings** — every sub-field of the returned
     :class:`~personalscraper.indexer.reconcile.ReconcileReport` must be
     empty / zero.  The headline assertion is ``total_findings == 0``.

MUST-16 link: this test pins the invariant described in the tech-debt
0.16.0 DESIGN §9 ("scan → reconcile = clean") so that any future change
that introduces spurious findings is caught at the test gate rather than
discovered in production.
"""

from __future__ import annotations

from personalscraper.indexer.reconcile import ReconcileReport, reconcile
from tests.integration.fixtures.seeded_library_fs import SeededLibrary

# Register the fixture module so pytest discovers seeded_library_fs without
# importing the fixture function directly (a direct import would cause ruff
# F811 "redefinition of unused name" on every test method parameter).
pytest_plugins = ["tests.integration.fixtures.seeded_library_fs"]

# ---------------------------------------------------------------------------
# MUST-16 / BD-AG — scan → reconcile = clean invariant
# ---------------------------------------------------------------------------


class TestScanReconcileClean:
    """Pinned invariant: a fully-aligned seeded library has zero reconcile findings."""

    def test_reconcile_on_aligned_library_is_clean(self, seeded_library_fs: SeededLibrary) -> None:
        """reconcile() on a perfectly-seeded library must return total_findings==0.

        Steps:
          1. Verify fixture invariants (BD-AF self-check).
          2. Run reconcile(conn) with all detectors (default scopes).
          3. Assert every finding bucket is empty / zero.
          4. Assert the headline total is zero.

        If this test fails with a count > 0 on any bucket, the fixture or
        a reconcile detector has regressed.

        Args:
            seeded_library_fs: Aligned FS + seeded DB fixture (BD-AF).
        """
        lib = seeded_library_fs

        # ---- Step 1: fixture self-check (BD-AF) ----
        assert lib.n_items == 10, (
            f"BD-AF fixture must insert exactly 10 media_item rows, got {lib.n_items}. "
            "Check the seeded_library_fs fixture."
        )
        assert lib.n_files > 0, "BD-AF fixture must insert at least 1 media_file row."
        # 8 movies × 5 files = 40, 2 shows × 2 seasons × 6 episodes = 24 → total 64
        assert lib.n_files == 64, (
            f"BD-AF fixture must insert exactly 64 media_file rows "
            f"(8 movies×5 + 2 shows×2 seasons×6 eps), got {lib.n_files}."
        )
        assert lib.disk_root.exists(), "Disk root directory must exist on the filesystem."

        # ---- Step 2: run all reconcile detectors ----
        report: ReconcileReport = reconcile(lib.conn, scopes=None, enqueue_repairs=False)

        # ---- Step 3: assert per-bucket findings are empty ----
        assert report.merkle_drift == [], (
            f"merkle_drift must be [] on a freshly-seeded DB with merkle_root=NULL "
            f"(NULL disks are excluded from the drift detector). "
            f"Got: {report.merkle_drift}"
        )
        assert report.dispatch_path_missing == [], (
            f"dispatch_path_missing must be [] — all item dispatch_path attributes "
            f"point to directories created by the fixture. "
            f"Got: {report.dispatch_path_missing}"
        )
        assert report.enrich_stale == 0, (
            f"enrich_stale must be 0 — all files have enriched_at=NULL which is "
            f"excluded by the stale detector (condition: enriched_at IS NOT NULL). "
            f"Got: {report.enrich_stale}"
        )
        assert report.release_orphans == [], (
            f"release_orphans must be [] — every media_release has at least one "
            f"surviving (non-deleted) media_file pointing to it. "
            f"Got: {report.release_orphans}"
        )
        assert report.files_without_release == 0, (
            f"files_without_release must be 0 — all media_file rows have a non-NULL "
            f"release_id (enriched_at=NULL so the second condition is also excluded). "
            f"Got: {report.files_without_release}"
        )
        assert report.season_count_drift == [], (
            f"season_count_drift must be [] — season.episode_count was set to exactly "
            f"the number of episode rows inserted for each season (6 each). "
            f"Got: {report.season_count_drift}"
        )
        assert report.items_without_files == [], (
            f"items_without_files must be [] — every media_item has at least one "
            f"surviving media_file linked via media_release. "
            f"Got: {report.items_without_files}"
        )

        # ---- Step 4: headline assertion (MUST-16) ----
        assert report.total_findings == 0, (
            f"total_findings must be 0 on a perfectly-seeded aligned library. "
            f"This pins MUST-16: scan → reconcile = clean. "
            f"Got total_findings={report.total_findings}. "
            f"Breakdown — "
            f"merkle_drift={report.merkle_drift}, "
            f"dispatch_path_missing={report.dispatch_path_missing}, "
            f"enrich_stale={report.enrich_stale}, "
            f"release_orphans={report.release_orphans}, "
            f"files_without_release={report.files_without_release}, "
            f"season_count_drift={report.season_count_drift}, "
            f"items_without_files={report.items_without_files}"
        )

    def test_fixture_creates_expected_db_rows(self, seeded_library_fs: SeededLibrary) -> None:
        """DB row counts match the fixture contract (BD-AF structural check).

        Queries the DB directly to verify row counts match the fixture's
        claimed totals.  This catches any drift between the fixture code
        and the :class:`SeededLibrary` metadata fields without relying on
        the reconcile detector paths.

        Args:
            seeded_library_fs: Aligned FS + seeded DB fixture (BD-AF).
        """
        lib = seeded_library_fs
        conn = lib.conn

        # media_item count
        item_count = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
        assert item_count == lib.n_items, (
            f"media_item count mismatch: DB has {item_count}, fixture reports {lib.n_items}"
        )

        # media_file count
        file_count = conn.execute("SELECT COUNT(*) FROM media_file WHERE deleted_at IS NULL").fetchone()[0]
        assert file_count == lib.n_files, (
            f"media_file count mismatch: DB has {file_count}, fixture reports {lib.n_files}"
        )

        # Every media_item has a dispatch_path attribute
        items_with_dispatch = conn.execute(
            "SELECT COUNT(DISTINCT item_id) FROM item_attribute WHERE key = 'dispatch_path'"
        ).fetchone()[0]
        assert items_with_dispatch == lib.n_items, (
            f"Not all items have a dispatch_path attribute: {items_with_dispatch}/{lib.n_items} do"
        )

        # Every media_release has at least one surviving media_file
        orphan_releases = conn.execute(
            """
            SELECT COUNT(*)
              FROM media_release mr
             WHERE NOT EXISTS (
                 SELECT 1 FROM media_file mf
                  WHERE mf.release_id = mr.id
                    AND mf.deleted_at IS NULL
             )
            """
        ).fetchone()[0]
        assert orphan_releases == 0, f"Fixture produced {orphan_releases} orphan media_release rows"

        # Season episode_count matches actual episode rows
        drifted_seasons = conn.execute(
            """
            SELECT COUNT(*)
              FROM season s
              LEFT JOIN (
                  SELECT season_id, COUNT(*) AS cnt FROM episode GROUP BY season_id
              ) e ON e.season_id = s.id
             WHERE s.episode_count != COALESCE(e.cnt, 0)
            """
        ).fetchone()[0]
        assert drifted_seasons == 0, f"Fixture produced {drifted_seasons} seasons with drifted episode_count"

    def test_dispatch_paths_exist_on_fs(self, seeded_library_fs: SeededLibrary) -> None:
        """All dispatch_path attribute values exist as real directories on disk.

        This directly validates the FS side of the fixture — the reconcile
        detect_dispatch_path_missing detector walks these paths, so they
        must genuinely exist.

        Args:
            seeded_library_fs: Aligned FS + seeded DB fixture (BD-AF).
        """
        from pathlib import Path

        lib = seeded_library_fs
        conn = lib.conn

        rows = conn.execute("SELECT item_id, value FROM item_attribute WHERE key = 'dispatch_path'").fetchall()

        assert len(rows) == lib.n_items, f"Expected {lib.n_items} dispatch_path attributes, found {len(rows)}"

        missing: list[str] = []
        for item_id, value in rows:
            if not Path(value).exists():
                missing.append(f"item_id={item_id} → {value!r}")

        assert not missing, "The following dispatch_path directories do not exist on disk:\n" + "\n".join(
            f"  {m}" for m in missing
        )
