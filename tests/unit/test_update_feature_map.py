"""Unit tests for ``scripts/update_feature_map.py``.

Cover marker extraction (``Design:``/``Contract:`` parsing on function and
async function docstrings, with class/module docstrings ignored), codename
resolution against the override table, ``--check`` behavior, drift detection,
and codename collision reporting.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from update_feature_map import (
    build_maps,
    collect_markers,
    diff_maps,
    main,
    write_maps,
)


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Build a minimal repo skeleton with tests/ and tests/feature_map/."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "feature_map").mkdir()
    return tmp_path


def _write_test_file(repo: Path, rel: str, source: str) -> Path:
    """Write a test source file under ``repo/<rel>`` and return the absolute path."""
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


class TestCollectMarkers:
    """Marker extraction from docstrings."""

    def test_design_and_contract_present_function(self, fake_repo: Path) -> None:
        """Function with both Design: and Contract: produces one entry."""
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_x.py",
            '''
def test_circuit_breaker_opens():
    """Circuit breaker opens after 3 failures.

    Design: docs/features/api-unify/DESIGN.md#circuit-breaker-opens
    Contract: After 3 consecutive failures the breaker opens.
    """
''',
        )
        entries, warnings, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        assert warnings == []
        assert len(entries) == 1
        assert entries[0].design_path == "docs/features/api-unify/DESIGN.md"
        assert entries[0].anchor == "circuit-breaker-opens"
        assert entries[0].test_id.endswith("::test_circuit_breaker_opens")

    def test_design_and_contract_present_async_function(self, fake_repo: Path) -> None:
        """Async function with both markers produces one entry."""
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_async.py",
            '''
async def test_async_handler():
    """Async path.

    Design: docs/features/api-unify/DESIGN.md#async-handler
    Contract: yields async result.
    """
''',
        )
        entries, _, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        assert len(entries) == 1
        assert entries[0].anchor == "async-handler"

    def test_only_design_no_contract_skipped(self, fake_repo: Path) -> None:
        """Design: line without Contract: skips the test with a warning."""
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_y.py",
            '''
def test_legacy():
    """Legacy test.

    Design: docs/features/api-unify/DESIGN.md#legacy
    """
''',
        )
        entries, warnings, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        assert entries == []
        assert len(warnings) == 1
        assert warnings[0].endswith("::test_legacy")

    def test_only_contract_no_design_ignored(self, fake_repo: Path) -> None:
        """Contract: alone is silently ignored — not a coverage candidate."""
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_z.py",
            '''
def test_no_design():
    """Some test.

    Contract: does a thing.
    """
''',
        )
        entries, warnings, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        assert entries == []
        assert warnings == []

    def test_multiple_design_lines_in_one_docstring(self, fake_repo: Path) -> None:
        """Two Design: lines in one docstring produce two entries (cross-cutting)."""
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_multi.py",
            '''
def test_cross_cutting():
    """Touches two sections.

    Design: docs/features/api-unify/DESIGN.md#section-a
    Design: docs/features/api-unify/DESIGN.md#section-b
    Contract: covers a and b.
    """
''',
        )
        entries, _, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        assert {e.anchor for e in entries} == {"section-a", "section-b"}

    def test_module_and_class_docstrings_ignored(self, fake_repo: Path) -> None:
        """Module-level and class-level docstrings must not produce markers."""
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_doc_levels.py",
            '''"""Module-level docstring with stray markers.

Design: docs/features/api-unify/DESIGN.md#module-marker
Contract: ignored at module level.
"""

class TestSuite:
    """Class-level docstring with stray markers.

    Design: docs/features/api-unify/DESIGN.md#class-marker
    Contract: ignored at class level.
    """

    def test_method(self):
        """Real method.

        Design: docs/features/api-unify/DESIGN.md#method-marker
        Contract: counted.
        """
''',
        )
        entries, _, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        assert {e.anchor for e in entries} == {"method-marker"}
        assert entries[0].test_id.endswith("test_design_doc_levels.py::TestSuite::test_method")

    def test_feature_map_directory_skipped(self, fake_repo: Path) -> None:
        """Files under tests/feature_map/ must not be scanned."""
        _write_test_file(
            fake_repo,
            "tests/feature_map/should_be_ignored.py",
            '''
def test_in_feature_map():
    """Stray.

    Design: docs/features/api-unify/DESIGN.md#stray
    Contract: should not appear.
    """
''',
        )
        entries, _, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        assert entries == []


class TestBuildMaps:
    """Codename grouping + collision detection."""

    def test_default_features_path(self, fake_repo: Path) -> None:
        """``docs/features/<codename>/DESIGN.md`` resolves via the segment rule."""
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_a.py",
            '''
def test_a():
    """A.

    Design: docs/features/test-coverage/DESIGN.md#alpha
    Contract: alpha clause.
    """
''',
        )
        entries, _, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        maps, collisions = build_maps(entries)
        assert collisions == []
        assert "test-coverage" in maps
        assert maps["test-coverage"]["sections"] == {"alpha": {"tests": ["tests/integration/test_design_a.py::test_a"]}}

    @pytest.mark.parametrize(
        ("design_path", "expected_codename"),
        [
            ("docs/reference/scraping.md", "scraper"),
            ("docs/reference/storage.md", "dispatch"),
            ("docs/reference/pipeline-internals.md", "pipeline"),
            ("docs/reference/trailers.md", "trailers"),
            ("docs/reference/indexer.md", "indexer"),
            ("docs/reference/indexer-json-shapes.md", "indexer-json-shapes"),
            ("docs/reference/architecture.md", "architecture"),
        ],
    )
    def test_override_table(self, fake_repo: Path, design_path: str, expected_codename: str) -> None:
        """Each reference doc resolves to its overridden codename."""
        source = f'''
def test_x():
    """X.

    Design: {design_path}#anchor
    Contract: clause.
    """
'''
        _write_test_file(fake_repo, "tests/integration/test_design_override.py", source)
        entries, _, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        maps, _ = build_maps(entries)
        assert expected_codename in maps

    def test_codename_collision_detected(self, fake_repo: Path) -> None:
        """Two distinct design paths resolving to the same codename collide."""
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_collision.py",
            '''
def test_x():
    """First.

    Design: docs/features/scraper/DESIGN.md#alpha
    Contract: clause.
    """

def test_y():
    """Second.

    Design: docs/reference/scraping.md#beta
    Contract: clause.
    """
''',
        )
        entries, _, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        _, collisions = build_maps(entries)
        assert len(collisions) == 1
        codename, first, second = collisions[0]
        assert codename == "scraper"
        assert {first, second} == {
            "docs/features/scraper/DESIGN.md",
            "docs/reference/scraping.md",
        }

    def test_test_ids_deduplicated_and_sorted(self, fake_repo: Path) -> None:
        """Same test repeated produces a single entry; section tests are sorted."""
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_dup.py",
            '''
def test_b_first():
    """B first.

    Design: docs/features/api-unify/DESIGN.md#shared
    Contract: clause.
    """

def test_a_second():
    """A second.

    Design: docs/features/api-unify/DESIGN.md#shared
    Contract: clause.
    """
''',
        )
        entries, _, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        maps, _ = build_maps(entries)
        tests = maps["api-unify"]["sections"]["shared"]["tests"]
        assert tests == sorted(tests)
        assert len(set(tests)) == len(tests)


class TestCheckMode:
    """``--check`` mode behavior."""

    def test_check_clean_when_committed_matches(self, fake_repo: Path) -> None:
        """When map files match what would be generated, --check exits 0."""
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_clean.py",
            '''
def test_x():
    """X.

    Design: docs/features/api-unify/DESIGN.md#x
    Contract: clause.
    """
''',
        )
        entries, _, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        maps, _ = build_maps(entries)
        write_maps(maps, fake_repo / "tests" / "feature_map")
        drifts = diff_maps(maps, fake_repo / "tests" / "feature_map")
        assert drifts == []

    def test_check_drift_when_marker_missing_from_committed_file(self, fake_repo: Path) -> None:
        """Adding a marker without rerunning the script produces drift."""
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_drift.py",
            '''
def test_x():
    """X.

    Design: docs/features/api-unify/DESIGN.md#x
    Contract: clause.
    """
''',
        )
        entries, _, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        maps, _ = build_maps(entries)
        write_maps(maps, fake_repo / "tests" / "feature_map")

        # Add a new marker without regenerating.
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_drift_more.py",
            '''
def test_y():
    """Y.

    Design: docs/features/api-unify/DESIGN.md#y
    Contract: clause.
    """
''',
        )
        entries2, _, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        maps2, _ = build_maps(entries2)
        drifts = diff_maps(maps2, fake_repo / "tests" / "feature_map")
        assert len(drifts) == 1

    def test_check_drift_when_orphan_map_file_exists(self, fake_repo: Path) -> None:
        """Map file with no corresponding markers is reported as drift."""
        orphan = fake_repo / "tests" / "feature_map" / "ghost.json"
        orphan.write_text(
            json.dumps({"feature": "ghost", "design": "x", "sections": {}, "skip_audit": []}),
            encoding="utf-8",
        )
        drifts = diff_maps({}, fake_repo / "tests" / "feature_map")
        assert orphan in drifts

    def test_skip_audit_preserved_across_runs(self, fake_repo: Path) -> None:
        """Skip-audit entries already on disk survive regeneration."""
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_skip.py",
            '''
def test_x():
    """X.

    Design: docs/features/api-unify/DESIGN.md#x
    Contract: clause.
    """
''',
        )
        entries, _, _parse_errors = collect_markers(fake_repo / "tests", fake_repo)
        maps, _ = build_maps(entries)
        map_dir = fake_repo / "tests" / "feature_map"
        write_maps(maps, map_dir)

        path = map_dir / "api-unify.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["skip_audit"] = [
            {"anchor": "purpose", "reason": "intent", "expires": "2027-05-08"},
        ]
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        write_maps(maps, map_dir)
        data2 = json.loads(path.read_text(encoding="utf-8"))
        assert data2["skip_audit"] == [
            {"anchor": "purpose", "reason": "intent", "expires": "2027-05-08"},
        ]


class TestMainEntryPoint:
    """End-to-end behavior of ``main()``."""

    def test_main_check_returns_1_on_collision(self, fake_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Codename collisions cause main() to exit 1 even in --check mode."""
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_collide.py",
            '''
def test_a():
    """A.

    Design: docs/features/scraper/DESIGN.md#a
    Contract: clause.
    """

def test_b():
    """B.

    Design: docs/reference/scraping.md#b
    Contract: clause.
    """
''',
        )
        rc = main(["--check", "--repo-root", str(fake_repo)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "codename collisions" in captured.err

    def test_main_writes_files(self, fake_repo: Path) -> None:
        """Default mode writes the expected map file."""
        _write_test_file(
            fake_repo,
            "tests/integration/test_design_write.py",
            '''
def test_x():
    """X.

    Design: docs/features/api-unify/DESIGN.md#x
    Contract: clause.
    """
''',
        )
        rc = main(["--repo-root", str(fake_repo)])
        assert rc == 0
        path = fake_repo / "tests" / "feature_map" / "api-unify.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["feature"] == "api-unify"
        assert "x" in data["sections"]


@pytest.fixture(autouse=True)
def _ensure_scripts_on_path() -> None:
    """Pyproject already adds ``scripts`` to pythonpath; this is belt-and-braces."""
    scripts_dir = str(Path(__file__).resolve().parents[2] / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
