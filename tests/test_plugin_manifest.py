"""Validate the Claude plugin manifests and /kanban skill frontmatter.

Loads three artifacts at the repo root and asserts structural correctness:

* ``.claude-plugin/marketplace.json`` — required top-level fields, a non-empty
  plugin list, and a ``kanban`` plugin entry with the expected keys.
* ``plugin/.claude-plugin/plugin.json`` — the PLUGIN manifest (distinct from the
  marketplace), with required fields and a ``version`` matching both the VERSION
  file and the marketplace entry (so all three stay in lockstep).
* ``plugin/skills/kanban/SKILL.md`` — the skill's YAML frontmatter
  (``name`` / ``description``).
"""

from __future__ import annotations

import json
import re
import yaml
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_json(path: Path) -> Any:
    """Read and parse a JSON file, returning the decoded object."""
    return json.loads(path.read_text(encoding="utf-8"))


def _read_version(path: Path) -> str:
    """Read the VERSION file, stripping whitespace."""
    return path.read_text(encoding="utf-8").strip()


def _parse_skill_frontmatter(path: Path) -> dict[str, Any]:
    """Parse the YAML frontmatter block from a SKILL.md file.

    Expects a ``---`` delimited block at the top of the file. Returns the parsed
    mapping, or an empty dict if no frontmatter is found.
    """
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if m is None:
        return {}
    return yaml.safe_load(m.group(1)) or {}


class TestMarketplaceManifest:
    """Tests for ``.claude-plugin/marketplace.json``."""

    @staticmethod
    def manifest() -> Any:
        return _read_json(REPO_ROOT / ".claude-plugin" / "marketplace.json")

    def test_top_level_name(self) -> None:
        manifest = self.manifest()
        assert manifest["name"] == "kanbanmate"

    def test_plugins_is_non_empty_list(self) -> None:
        manifest = self.manifest()
        plugins = manifest["plugins"]
        assert isinstance(plugins, list)
        assert len(plugins) > 0

    def test_kanban_plugin_exists(self) -> None:
        manifest = self.manifest()
        kanban = next((p for p in manifest["plugins"] if p.get("name") == "kanban"), None)
        assert kanban is not None, "No plugin entry with name 'kanban' found"

    def test_kanban_plugin_required_fields(self) -> None:
        manifest = self.manifest()
        kanban = next(p for p in manifest["plugins"] if p.get("name") == "kanban")
        assert "name" in kanban
        assert kanban["name"] == "kanban"
        assert "description" in kanban
        assert isinstance(kanban["description"], str)
        assert len(kanban["description"]) > 0
        assert "version" in kanban
        assert isinstance(kanban["version"], str)
        assert "source" in kanban
        assert kanban["source"] == "./plugin"

    def test_kanban_version_matches_version_file(self) -> None:
        manifest = self.manifest()
        kanban = next(p for p in manifest["plugins"] if p.get("name") == "kanban")
        expected_version = _read_version(REPO_ROOT / "VERSION")
        assert kanban["version"] == expected_version, (
            f"Plugin version {kanban['version']!r} != VERSION file {expected_version!r}"
        )


class TestPluginManifest:
    """Tests for ``plugin/.claude-plugin/plugin.json`` (the PLUGIN manifest).

    Distinct from the marketplace manifest: this is what makes the plugin itself
    independently installable / validatable (``claude plugin validate ./plugin``).
    """

    @staticmethod
    def manifest() -> Any:
        return _read_json(REPO_ROOT / "plugin" / ".claude-plugin" / "plugin.json")

    def test_name_is_kanban(self) -> None:
        manifest = self.manifest()
        assert manifest["name"] == "kanban"

    def test_required_fields(self) -> None:
        manifest = self.manifest()
        assert isinstance(manifest.get("description"), str)
        assert len(manifest["description"]) > 0
        assert isinstance(manifest.get("version"), str)
        assert "author" in manifest

    def test_version_matches_version_file(self) -> None:
        manifest = self.manifest()
        expected_version = _read_version(REPO_ROOT / "VERSION")
        assert manifest["version"] == expected_version, (
            f"plugin.json version {manifest['version']!r} != VERSION file {expected_version!r}"
        )

    def test_version_matches_marketplace_entry(self) -> None:
        manifest = self.manifest()
        marketplace = _read_json(REPO_ROOT / ".claude-plugin" / "marketplace.json")
        kanban = next(p for p in marketplace["plugins"] if p.get("name") == "kanban")
        assert manifest["version"] == kanban["version"], (
            f"plugin.json version {manifest['version']!r} != "
            f"marketplace entry {kanban['version']!r}"
        )


class TestSkillFrontmatter:
    """Tests for ``plugin/skills/kanban/SKILL.md``."""

    @staticmethod
    def frontmatter() -> dict[str, Any]:
        return _parse_skill_frontmatter(REPO_ROOT / "plugin" / "skills" / "kanban" / "SKILL.md")

    def test_frontmatter_is_non_empty(self) -> None:
        fm = self.frontmatter()
        assert fm, "SKILL.md frontmatter is empty or missing"

    def test_name_is_kanban(self) -> None:
        fm = self.frontmatter()
        assert fm.get("name") == "kanban"

    def test_description_is_non_empty(self) -> None:
        fm = self.frontmatter()
        desc = fm.get("description")
        assert isinstance(desc, str)
        assert len(desc) > 0
