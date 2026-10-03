"""Catalogue tests: the shipped JSON files agree with each other and with the code that calls them."""

from __future__ import annotations

import ast
import json
from enum import StrEnum
from importlib import resources
from pathlib import Path

from personalscraper.app.errors import RefusalCode
from personalscraper.i18n import Language, _catalogue

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PACKAGE_ROOT = _REPO_ROOT / "personalscraper"
_FRONTEND_FR = _REPO_ROOT / "frontend" / "maquette" / "design" / "src" / "i18n" / "fr.json"

# Namespace -> the closed StrEnum whose members are looked up with ``t_code``. A phase that adds
# a coded namespace declares the pair here and ships a key per member.
CODE_SETS: dict[str, type[StrEnum]] = {"cli_refusals": RefusalCode}

_MARKUP = ("**", "<", "[/", "[bold", "[cyan", "[red", "[green", "[yellow", "[dim")


def _real_root() -> Path:
    """The shipped catalogue directory, as a real path."""
    return _PACKAGE_ROOT / "i18n"


def _read(language: str, namespace: str) -> dict:
    """The parsed shipped catalogue file of one namespace and language."""
    return json.loads((_real_root() / language / f"{namespace}.json").read_text(encoding="utf-8"))


def _namespaces(language: str) -> set[str]:
    """The namespaces shipped in ``language``."""
    return {p.stem for p in (_real_root() / language).glob("*.json")}


def _one_sided(namespace: str) -> set[str]:
    """The keys ``one_sided/<namespace>.json`` declares as translated in one language only."""
    path = _real_root() / "one_sided" / f"{namespace}.json"
    return set(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else set()


def _plural_groups(keys: set[str]) -> set[str]:
    """Base keys that have a ``_one`` or ``_other`` member."""
    return {k.rsplit("_", 1)[0] for k in keys if k.endswith(("_one", "_other"))}


def _all_namespaces() -> list[str]:
    """Every namespace shipped in either language, sorted."""
    return sorted(_namespaces("fr") | _namespaces("en"))


def test_ships_as_package_data() -> None:
    """The catalogues are reachable through ``importlib.resources`` (and so ship in the wheel)."""
    root = resources.files("personalscraper.i18n")
    assert root.joinpath("fr", "units.json").is_file()
    assert root.joinpath("en", "units.json").is_file()
    assert root.joinpath("one_sided", "units.json").is_file()


def test_pyproject_declares_the_package_data() -> None:
    """``pyproject.toml`` lists the three catalogue folders for the wheel."""
    text = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"personalscraper.i18n" = ["fr/*.json", "en/*.json", "one_sided/*.json"]' in text


def _drift(namespace: str, fr: set[str], en: set[str], declared: set[str]) -> list[str]:
    """Problems of one namespace: one-sided keys not declared, and declared keys translated in both."""
    actual = fr ^ en
    problems = [f"{namespace}.{key}: one-sided but not declared" for key in sorted(actual - declared)]
    problems += [f"{namespace}.{key}: declared one-sided but translated in both" for key in sorted(declared - actual)]
    return problems


def test_every_namespace_in_both_languages_and_keys_match_but_declared_one_sided() -> None:
    """Completeness: key sets agree across languages except for the declared one-sided keys, both ways."""
    assert _namespaces("fr") == _namespaces("en"), "a namespace file exists in one language only"
    problems: list[str] = []
    for namespace in _all_namespaces():
        fr = set(_catalogue.flatten(_read("fr", namespace)))
        en = set(_catalogue.flatten(_read("en", namespace)))
        problems += _drift(namespace, fr, en, _one_sided(namespace))
    assert not problems, "\n".join(problems)


def test_one_sided_list_detects_drift() -> None:
    """Control: the comparison used above flags an undeclared and a stale declaration, and passes a consistent one."""
    assert _drift("demo", {"a"}, {"a", "b"}, set()) == ["demo.b: one-sided but not declared"]
    assert _drift("demo", {"a"}, {"a"}, {"a"}) == ["demo.a: declared one-sided but translated in both"]
    assert _drift("demo", {"a"}, {"a", "b"}, {"b"}) == []


def test_placeholders_and_plural_groups_agree_across_languages() -> None:
    """A translation never drops a value; plural groups are complete in both languages."""
    for namespace in _all_namespaces():
        fr = _catalogue.flatten(_read("fr", namespace))
        en = _catalogue.flatten(_read("en", namespace))
        for key in set(fr) & set(en):
            assert _catalogue.placeholders(fr[key]) == _catalogue.placeholders(en[key]), f"{namespace}.{key}"
        for catalogue in (fr, en):
            for base in _plural_groups(set(catalogue)):
                assert f"{base}_one" in catalogue and f"{base}_other" in catalogue, f"{namespace}.{base}"


def _t_calls(tree: ast.AST) -> list[ast.Call]:
    """Every ``t("<literal>", …)`` call in a tree."""
    calls = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "t"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            calls.append(node)
    return calls


def _check_calls(source: str, catalogue: dict[str, dict[str, str]]) -> list[str]:
    """Problems of the literal ``t()`` calls in ``source`` against ``catalogue`` (namespace -> flat keys)."""
    problems = []
    for call in _t_calls(ast.parse(source)):
        key = call.args[0].value  # type: ignore[attr-defined]
        namespace, _, path = key.partition(".")
        flat = catalogue.get(namespace, {})
        passed = {kw.arg for kw in call.keywords if kw.arg}
        unpacked = any(kw.arg is None for kw in call.keywords)  # ``**values``: what it carries is unknowable
        if path in flat:
            wanted = _catalogue.placeholders(flat[path])
            if "count" in passed:
                problems.append(f"{key}: count= passed but the key is not a plural group")
        elif f"{path}_one" in flat and f"{path}_other" in flat:
            wanted = _catalogue.placeholders(flat[f"{path}_one"]) | _catalogue.placeholders(flat[f"{path}_other"])
            wanted.discard("count")  # the plural selector, passed (or flagged) separately
            if "count" not in passed:
                problems.append(f"{key}: plural group called without count=")
        else:
            problems.append(f"{key}: no such key")
            continue
        missing = wanted - passed
        if missing and not unpacked:
            problems.append(f"{key}: placeholders not passed: {sorted(missing)}")
    return problems


def _union_catalogue() -> dict[str, dict[str, str]]:
    """Namespace -> flat keys, French over English, for the literal-call scan."""
    merged: dict[str, dict[str, str]] = {}
    for namespace in _all_namespaces():
        merged[namespace] = {
            **_catalogue.flatten(_read("en", namespace)),
            **_catalogue.flatten(_read("fr", namespace)),
        }
    return merged


def test_every_literal_key_called_exists_with_its_placeholders() -> None:
    """Every literal ``t("…")`` under ``personalscraper/`` names a real key and passes what it needs."""
    catalogue = _union_catalogue()
    problems: list[str] = []
    for path in sorted(_PACKAGE_ROOT.rglob("*.py")):
        rel = path.relative_to(_REPO_ROOT).as_posix()
        problems.extend(f"{rel}: {p}" for p in _check_calls(path.read_text(encoding="utf-8"), catalogue))
    assert not problems, "\n".join(problems)


def test_the_call_checker_catches_a_missing_key_and_a_missing_kwarg() -> None:
    """Control: a fixture module proves each failure mode is detected (the real scan is not vacuous)."""
    catalogue = {"demo": {"hello": "Hello {{name}}", "files_one": "{{count}} file", "files_other": "{{count}} files"}}
    assert _check_calls('t("demo.hello", name="x")\nt("demo.files", count=2)\n', catalogue) == []
    assert _check_calls('t("demo.absent")', catalogue) == ["demo.absent: no such key"]
    assert _check_calls('t("demo.hello")', catalogue) == ["demo.hello: placeholders not passed: ['name']"]
    assert _check_calls('t("demo.files")', catalogue) == ["demo.files: plural group called without count="]
    assert _check_calls('t("demo.hello", **values)', catalogue) == []  # ** is unverifiable for placeholders
    assert _check_calls('t("demo.absent", **values)', catalogue) == ["demo.absent: no such key"]  # the key still is
    assert _check_calls('t("demo.hello", name="x", count=1)', catalogue) == [
        "demo.hello: count= passed but the key is not a plural group"
    ]


def test_every_code_set_is_worded() -> None:
    """Every member of every declared code set has a key in both languages."""
    for namespace, codes in CODE_SETS.items():
        for language in Language:
            keys = set(_catalogue.flatten(_read(language.value, namespace)))
            for member in codes:
                assert member.value in keys, f"{namespace}.{member.value} missing in {language.value}"


def test_every_t_code_namespace_is_declared() -> None:
    """Every literal namespace passed to ``t_code`` is declared in ``CODE_SETS``."""
    undeclared = []
    for path in sorted(_PACKAGE_ROOT.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "t_code"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value not in CODE_SETS
            ):
                undeclared.append(f"{path.relative_to(_REPO_ROOT)}:{node.lineno}")
    assert not undeclared, undeclared


def test_namespaces_do_not_collide_with_the_interface() -> None:
    """The backend's namespaces share no top-level key with the frontend catalogue (``refusals`` is not shipped yet)."""
    frontend = set(json.loads(_FRONTEND_FR.read_text(encoding="utf-8")))
    assert set(_all_namespaces()) & frontend == set()


def test_no_markup_in_the_words() -> None:
    """Markup belongs to the code: no Markdown, HTML or Rich tag in any string."""
    for language in ("fr", "en"):
        for namespace in _namespaces(language):
            for key, text in _catalogue.flatten(_read(language, namespace)).items():
                assert not any(marker in text for marker in _MARKUP), f"{language}/{namespace}.{key}: {text!r}"
