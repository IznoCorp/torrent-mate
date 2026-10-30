"""Every key of the ``cli_library`` catalogue is read by a literal ``t(...)`` call or belongs to a declared code set.

An orphan key is a site that went back to a literal: the catalogue must not drift from the code.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from personalscraper.i18n import _catalogue
from tests.unit.i18n.test_catalogue import CODE_SETS

_ROOT = Path(__file__).resolve().parents[3] / "personalscraper"
_NAMESPACE = "cli_library"


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


def _code_set_keys() -> set[str]:
    """The keys of every declared ``t_code`` code set living in the ``cli_library`` namespace."""
    return {
        f"{namespace}.{member.value}"
        for namespace, members in CODE_SETS.items()
        if namespace == _NAMESPACE or namespace.startswith(f"{_NAMESPACE}.")
        for member in members
    }


def _catalogue_keys() -> set[str]:
    """The namespace's keys in either language, as ``cli_library.<path>``."""
    keys: set[str] = set()
    for language in ("fr", "en"):
        path = _ROOT / "i18n" / language / f"{_NAMESPACE}.json"
        flat = _catalogue.flatten(json.loads(path.read_text(encoding="utf-8")))
        keys |= {f"{_NAMESPACE}.{key}" for key in flat}
    return keys


def test_every_cli_library_key_is_read_by_a_literal_call_or_a_code_set() -> None:
    """A key no literal ``t("...")`` reads and no code set covers means its site went back to a literal."""
    orphans = sorted(_catalogue_keys() - _literal_keys() - _code_set_keys())
    assert not orphans, f"keys read by no literal t() call nor code set: {orphans}"


def test_layout_only_library_texts_are_not_in_the_catalogue() -> None:
    """Rows and field lines carry no words: they stay literals in code, never catalogue keys."""
    layout_only = {
        f"{_NAMESPACE}.query.search_row",
        f"{_NAMESPACE}.query.attribute_line",
        f"{_NAMESPACE}.query.item_field",
        f"{_NAMESPACE}.indexer_query.disk_row",
        f"{_NAMESPACE}.indexer_query.oldest_hours",
    }
    assert not layout_only & _catalogue_keys()
    one_sided = json.loads((_ROOT / "i18n" / "one_sided" / f"{_NAMESPACE}.json").read_text(encoding="utf-8"))
    assert not {key.removeprefix(f"{_NAMESPACE}.") for key in layout_only} & set(one_sided)
