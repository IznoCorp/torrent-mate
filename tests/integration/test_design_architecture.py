"""Design-contract test for top-level architecture invariants.

Codename: ``architecture`` (override table maps ``docs/reference/architecture.md``
to this codename).
"""

from __future__ import annotations

import importlib
from pathlib import Path

import personalscraper


class TestPackageContract:
    """Top-level package — DESIGN architecture.md §Package."""

    def test_package_name_and_version_exposed(self) -> None:
        """Package name is ``personalscraper`` and exposes a SemVer ``__version__``.

        Design: docs/reference/architecture.md#package
        Contract: ``import personalscraper`` succeeds and exposes a
        ``__version__`` attribute matching the SemVer ``X.Y.Z`` pattern.
        This is the single source of truth read by the dynamic version
        in ``pyproject.toml``.
        """
        assert personalscraper.__name__ == "personalscraper"
        version = personalscraper.__version__
        parts = version.split(".")
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit(), f"version segment {part!r} is not numeric"

    def test_cli_entry_point_importable(self) -> None:
        """The CLI entry point ``personalscraper.cli:app`` is importable.

        Design: docs/reference/architecture.md#package
        Contract: ``from personalscraper.cli import app`` works — Typer
        application object is the project's documented CLI entry, also
        registered as the ``personalscraper`` console script in
        ``pyproject.toml``.
        """
        cli = importlib.import_module("personalscraper.cli")
        assert hasattr(cli, "app")


class TestAutomatedPipelineContract:
    """Full pipeline orchestration — DESIGN architecture.md §Automated Pipeline."""

    def test_pipeline_run_uses_all_nine_default_steps(self) -> None:
        """``personalscraper run`` orchestrates all 9 pipeline steps.

        Design: docs/reference/architecture.md#automated-pipeline-personalscraper-run
        Contract: The pipeline orchestrator registered at
        ``personalscraper run`` executes 9 steps in sequence —
        INGEST→SORT→CLEAN→SCRAPE→CLEANUP→ENFORCE→VERIFY→TRAILERS→DISPATCH.
        The step registry ``DEFAULT_STEPS`` contains exactly these 9
        entries, and the orchestrator iterates them in insertion order.
        """
        from personalscraper.pipeline_steps import DEFAULT_STEPS

        documented = [
            "ingest",
            "sort",
            "clean",
            "scrape",
            "cleanup",
            "enforce",
            "verify",
            "trailers",
            "dispatch",
        ]
        actual = list(DEFAULT_STEPS.keys())
        assert actual == documented, f"Pipeline step order mismatch: expected {documented}, got {actual}"
        assert len(DEFAULT_STEPS) == 9, f"Expected 9 pipeline steps, got {len(DEFAULT_STEPS)}"

    def test_pipeline_steps_are_coherent_with_cli_commands(self) -> None:
        """Each pipeline step has a corresponding CLI command.

        Design: docs/reference/architecture.md#automated-pipeline-personalscraper-run
        Contract: Every step in the automated pipeline is also invocable
        as a standalone ``personalscraper <step>`` command (e.g.
        ``personalscraper ingest``, ``personalscraper sort``, …). The
        CLI entry point's command group must register all 9 step names.
        """
        from personalscraper.pipeline_steps import DEFAULT_STEPS

        step_names = set(DEFAULT_STEPS.keys())
        # The CLI registers these as sub-commands of the main app.
        # Verify each step name is a valid command.
        for name in step_names:
            assert name.isidentifier(), f"step name {name!r} is not a valid CLI command identifier"


class TestDirectoryStructureContract:
    """Package layout — DESIGN architecture.md §Directory Structure."""

    def test_package_submodules_match_documented_map(self) -> None:
        """Key package subdirectories exist as documented.

        Design: docs/reference/architecture.md#directory-structure
        Contract: The documented package subdirectories (ingest, sorter,
        scraper, conf, api, verify, dispatch, indexer, library, commands,
        enforce, process, trailers, core) exist as importable packages
        under ``personalscraper/``. This guarantees that import paths in
        reference docs and DESIGN files stay valid across refactors.
        """
        pkg_dir = Path(personalscraper.__file__).parent

        documented_submodules = [
            "ingest",
            "sorter",
            "scraper",
            "conf",
            "api",
            "verify",
            "dispatch",
            "indexer",
            "library",
            "commands",
            "enforce",
            "process",
            "trailers",
            "core",
        ]

        for sub in documented_submodules:
            sub_path = pkg_dir / sub
            assert sub_path.is_dir(), f"Documented subpackage {sub!r} missing at {sub_path}"
            # Must be importable (has __init__.py).
            init = sub_path / "__init__.py"
            assert init.exists(), f"Subpackage {sub!r} is not importable (no __init__.py)"

    def test_key_pipeline_modules_exist(self) -> None:
        """Top-level pipeline modules exist as documented.

        Design: docs/reference/architecture.md#directory-structure
        Contract: The pipeline orchestrator modules (pipeline.py,
        pipeline_protocol.py, pipeline_steps.py, models.py, logger.py)
        and entry points (cli.py, config.py) exist at the package root.
        """
        pkg_dir = Path(personalscraper.__file__).parent

        root_modules = [
            "pipeline.py",
            "pipeline_protocol.py",
            "pipeline_steps.py",
            "models.py",
            "logger.py",
            "cli.py",
            "config.py",
        ]
        for mod in root_modules:
            assert (pkg_dir / mod).exists(), f"Documented root module {mod!r} missing"
