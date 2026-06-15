"""Gate test: every ``kanban-*`` helper named in the rendered transitions.yml is a console script.

The hardened prompts (:mod:`kanbanmate.core.transitions_defaults`) instruct agents to call helper
binaries by name (``kanban-update-body`` / ``kanban-move`` / ``kanban-progress`` / …). If a prompt
names a helper that is NOT declared in ``pyproject.toml``'s ``[project.scripts]``, the agent gets a
"command not found" and improvises the unsanctioned raw path (the §29 root cause). This gate scans
the rendered ``transitions.yml`` for every ``kanban-<name>`` token and asserts each is installed as
a console script — so a prompt can never reference a missing helper.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from kanbanmate.core.transitions_defaults import render_transitions_yaml

# A console-script-style helper token: ``kanban`` followed by ``-word`` segments (e.g.
# ``kanban-update-body``). Excludes the bare ``kanban`` CLI (which the prompts never shell out to as
# an agent helper). Trailing punctuation is stripped by the ``\b`` word boundary on the last segment.
_HELPER_TOKEN = re.compile(r"\bkanban-[a-z]+(?:-[a-z]+)*\b")


def _project_scripts() -> set[str]:
    """Read the ``[project.scripts]`` console-script names from ``pyproject.toml``.

    Returns:
        The set of declared console-script names (e.g. ``{"kanban", "kanban-move", …}``).
    """
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    scripts = data.get("project", {}).get("scripts", {})
    return set(scripts.keys())


def test_every_helper_named_in_transitions_is_a_console_script() -> None:
    """Every ``kanban-*`` helper the rendered transitions.yml names is installed (§29.1 gate)."""
    rendered = render_transitions_yaml("owner/repo")
    named_helpers = set(_HELPER_TOKEN.findall(rendered))
    # Sanity: the prompts DO reference at least the core helpers (guards against a regex that
    # silently matches nothing — a vacuously-passing gate).
    assert "kanban-move" in named_helpers
    assert "kanban-update-body" in named_helpers

    scripts = _project_scripts()
    missing = {h for h in named_helpers if h not in scripts}
    assert not missing, (
        f"transitions.yml names helper(s) with no [project.scripts] entry: {sorted(missing)} "
        f"(declared: {sorted(scripts)})"
    )
