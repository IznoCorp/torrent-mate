"""Regression: no inline ``QBitClient()`` construction in ingest or pipeline.

DESIGN D3 promotes the torrent client into :class:`AppContext` (boot-wired by
``_build_app_context``). Pipeline steps and CLI commands MUST read
``ctx.torrent_client`` instead of lazily constructing a ``QBitClient`` inline.
These AST-based tests guard against a regression that re-introduces an inline
fallback in either site.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Resolve module paths relative to the repository root so the test is
# independent of the pytest invocation directory.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_INGEST_PATH = _REPO_ROOT / "personalscraper" / "ingest" / "ingest.py"
_PIPELINE_PATH = _REPO_ROOT / "personalscraper" / "commands" / "pipeline.py"


def _has_inline_qbit(path: Path) -> bool:
    """Return ``True`` when the module constructs ``QBitClient`` inline.

    Walks the module AST looking for any call whose callee resolves to the
    name ``QBitClient`` — covering both a bare ``QBitClient(...)`` call and an
    attribute access such as ``module.QBitClient(...)``.

    Args:
        path: Absolute path to the Python module to inspect.

    Returns:
        ``True`` if at least one inline ``QBitClient`` construction is found.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name == "QBitClient":
                return True
    return False


def test_ingest_no_inline_qbit() -> None:
    """``ingest.py`` must not construct ``QBitClient`` inline (DESIGN D3)."""
    assert not _has_inline_qbit(_INGEST_PATH), (
        "ingest.py still builds QBitClient inline — read ctx.torrent_client instead"
    )


def test_pipeline_no_inline_qbit() -> None:
    """``pipeline.py`` must not construct ``QBitClient`` inline (DESIGN D3)."""
    assert not _has_inline_qbit(_PIPELINE_PATH), (
        "pipeline.py still builds QBitClient inline — read ctx.torrent_client instead"
    )
