"""Every key of the ``cli_acquisition`` catalogue is read by a literal ``t(...)`` call: an orphan is a reverted site."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from personalscraper.i18n import _catalogue

_ROOT = Path(__file__).resolve().parents[3] / "personalscraper"
_NAMESPACE = "cli_acquisition"


def _literal_keys() -> set[str]:
    """Every literal first argument of a ``t(...)`` call under ``personalscraper/``."""
    keys: set[str] = set()
    for path in _ROOT.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "t"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                keys.add(node.args[0].value)
    return keys


def _catalogue_keys() -> set[str]:
    """The namespace's keys in either language, as ``cli_acquisition.<path>``."""
    keys: set[str] = set()
    for language in ("fr", "en"):
        path = _ROOT / "i18n" / language / f"{_NAMESPACE}.json"
        flat = _catalogue.flatten(json.loads(path.read_text(encoding="utf-8")))
        keys |= {f"{_NAMESPACE}.{key}" for key in flat}
    return keys


def test_every_cli_acquisition_key_is_read_by_a_literal_call() -> None:
    """A key no ``t("...")`` reads means its site went back to a literal; the catalogue must not drift from the code."""
    orphans = sorted(_catalogue_keys() - _literal_keys())
    assert not orphans, f"keys read by no literal t() call: {orphans}"


def test_follow_backfill_labels_are_all_keyed() -> None:
    """The four backfill field labels are shown to the user: a label back to a literal leaves its key orphaned."""
    for field in ("title", "poster", "overview", "year"):
        assert f"{_NAMESPACE}.follow.backfill.field_{field}" in _catalogue_keys() & _literal_keys()
