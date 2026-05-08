"""Design-contract test for top-level architecture invariants.

Codename: ``architecture`` (override table maps ``docs/reference/architecture.md``
to this codename).
"""

from __future__ import annotations

import importlib

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
