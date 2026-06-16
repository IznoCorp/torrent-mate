"""Hexagonal layering guard (DESIGN §3.2 downward-only import rule).

This test statically enforces that import direction stays downward only. For
each source layer under ``src/kanbanmate/<layer>/`` it parses every ``.py``
file with :mod:`ast`, collects the dotted targets of every ``import`` and
``from ... import`` statement, and asserts that none of them reach into a
forbidden upper layer.

The check is purely static (no module import / execution), so it works even
while upper layers are empty stubs. Layers with no source beyond ``__init__``
— or whose modules declare no imports — trivially pass.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Repository-relative anchor: tests/ -> repo root -> src/kanbanmate.
PACKAGE_ROOT: Path = Path(__file__).resolve().parent.parent / "src" / "kanbanmate"

# Downward-only import contract (DESIGN §3.2). Each key is a layer; the value
# lists the layer names that layer may NOT import from. A layer absent from
# this table (``daemon``, ``cli``, ``bin``) is a top entrypoint with no upward
# constraint. Forbidden targets are matched against the dotted module path
# ``kanbanmate.<layer>...``.
FORBIDDEN: dict[str, list[str]] = {
    # core is pure: it may import nothing from any other kanbanmate layer.
    "core": ["ports", "adapters", "app", "daemon", "cli", "bin"],
    # ports are Protocols: they may reference core but nothing below them.
    # ports are Protocols: they may reference core AND name adapter VALUE objects
    # (e.g. ``CommentRef``) so a port method can be typed in terms of the records its
    # adapters already produce — only ``core`` may not (DESIGN §8.1.b). They must not
    # reach orchestration (app/daemon/cli) or the entrypoints (bin).
    "ports": ["app", "daemon", "cli", "bin"],
    # adapters implement ports against core; they must not reach orchestration.
    "adapters": ["app", "daemon", "cli"],
    # app is the composition root; it must not import the entrypoints.
    "app": ["cli", "daemon"],
    # http is the webhook-receiver entrypoint (ingress-multiproject §4.1). Like cli/daemon it sits
    # at the TOP of the hierarchy and may import app/adapters/core, plus the registry loader in
    # ``cli.init`` (``_load_registry`` / ``_projects_path`` — EXACTLY as the ``daemon`` entrypoint
    # already does; the registry-FILE reader lives in cli and is a shared concern). It must NOT
    # reach the ``daemon``/``bin`` sibling entrypoints, so the receiver stays a thin standalone
    # front-door and ``core`` stays pure.
    "http": ["daemon", "bin"],
}


def _iter_layer_files(layer: str) -> list[Path]:
    """Return every ``.py`` file belonging to a layer.

    Args:
        layer: The layer directory name under ``src/kanbanmate/``.

    Returns:
        A sorted list of ``Path`` objects for each ``.py`` file in the layer
        (including ``__init__.py`` and any nested sub-packages). Empty when the
        layer directory does not exist yet.
    """
    layer_dir = PACKAGE_ROOT / layer
    if not layer_dir.is_dir():
        return []
    return sorted(layer_dir.rglob("*.py"))


def _imported_modules(source: str, filename: str) -> set[str]:
    """Collect the dotted module targets of every import in ``source``.

    Both ``import a.b.c`` and ``from a.b import c`` contribute their fully
    dotted module path (the ``from`` clause for the latter). Relative imports
    (``from . import x``) are resolved to a ``kanbanmate``-rooted path so that
    intra-package shortcuts are still subject to the layering contract.

    Args:
        source: The Python source text to parse.
        filename: The file path, used only for AST error messages.

    Returns:
        The set of dotted module paths referenced by import statements.
    """
    tree = ast.parse(source, filename=filename)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # ``node.module`` is None for ``from . import x``; ``node.level``
            # is the number of leading dots in a relative import. We only need
            # the module portion to evaluate the layering contract.
            if node.level == 0 and node.module is not None:
                modules.add(node.module)
            elif node.level > 0:
                # Resolve a relative import to its kanbanmate-rooted path. A
                # file at ``kanbanmate.<layer>...`` importing ``from ..app``
                # must still be caught, so we normalise to an absolute target.
                modules.add(_resolve_relative(filename, node.level, node.module))
    return modules


def _resolve_relative(filename: str, level: int, module: str | None) -> str:
    """Resolve a relative import target to an absolute dotted path.

    Args:
        filename: The importing file's path on disk.
        level: The relative-import level (number of leading dots).
        module: The module portion after the dots, or ``None``.

    Returns:
        The absolute dotted module path rooted at ``kanbanmate`` (best effort).
    """
    # Package of the importing file: parts from ``kanbanmate`` onward, dropping
    # the file stem. ``level`` dots climb that many package levels up.
    rel_path = Path(filename).resolve()
    parts = list(rel_path.with_suffix("").parts)
    if "kanbanmate" in parts:
        parts = parts[parts.index("kanbanmate") :]
    # Drop the module's own name, then climb ``level - 1`` additional packages.
    package_parts = parts[:-1]
    if level > 1:
        package_parts = package_parts[: -(level - 1)] if level - 1 < len(package_parts) else []
    if module:
        package_parts = [*package_parts, *module.split(".")]
    return ".".join(package_parts)


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_has_no_upward_imports(layer: str) -> None:
    """Assert a layer imports nothing from a forbidden upper layer.

    For the given ``layer``, walk every ``.py`` file, collect import targets,
    and fail if any target resolves to a forbidden ``kanbanmate.<upper>`` path.
    Empty layers (no source files, or sources with no imports) pass trivially.

    Args:
        layer: The layer name under test, drawn from :data:`FORBIDDEN`.
    """
    forbidden_layers = FORBIDDEN[layer]
    forbidden_prefixes = tuple(f"kanbanmate.{upper}" for upper in forbidden_layers)

    files = _iter_layer_files(layer)
    if not files:
        pytest.skip(f"layer '{layer}' has no source files yet")

    violations: list[str] = []
    for path in files:
        modules = _imported_modules(path.read_text(encoding="utf-8"), str(path))
        for module in sorted(modules):
            if module == "kanbanmate":
                # The bare package import exposes no specific upper layer.
                continue
            for prefix in forbidden_prefixes:
                # Match either the exact module or a dotted sub-module of it
                # (``kanbanmate.app`` and ``kanbanmate.app.tick`` both count).
                if module == prefix or module.startswith(f"{prefix}."):
                    rel = path.relative_to(PACKAGE_ROOT.parent.parent)
                    violations.append(f"{rel}: imports '{module}' (forbidden for layer '{layer}')")

    assert not violations, "Upward import(s) violating DESIGN §3.2 layering:\n" + "\n".join(
        violations
    )
