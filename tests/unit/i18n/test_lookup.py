"""Lookup tests for the backend translation layer: language choice, fallback, strict mode, plurals."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog.testing

from personalscraper import i18n
from personalscraper.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_VARIABLE,
    STRICT_VARIABLE,
    Language,
    MissingTranslation,
    current_language,
    resolve_language,
    t,
    use_language,
)


def _write(root: Path, language: str, namespace: str, content: object) -> None:
    """Write one namespace catalogue under ``root`` (a raw string is written verbatim)."""
    folder = root / language
    folder.mkdir(parents=True, exist_ok=True)
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    (folder / f"{namespace}.json").write_text(text, encoding="utf-8")


@pytest.fixture
def fixture_root(tmp_path: Path) -> Iterator[Path]:
    """Point the catalogue loader at an empty fixture directory for the test."""
    i18n._use_root_for_tests(tmp_path)
    yield tmp_path
    i18n._use_root_for_tests(None)


@pytest.fixture
def lenient(monkeypatch: pytest.MonkeyPatch) -> None:
    """Leave strict mode (the suite default) for a test that exercises the degradations."""
    monkeypatch.delenv(STRICT_VARIABLE, raising=False)


def test_reads_the_requested_language() -> None:
    """The real ``units`` namespace answers in the requested language."""
    assert t("units.yes", language=Language.FR) == "oui"
    assert t("units.yes", language=Language.EN) == "yes"


def test_a_plain_string_language_is_read_like_the_enum() -> None:
    """``language="fr"`` (a ``str``, not a ``Language``) reads the French text."""
    assert t("units.yes", language="fr") == "oui"  # type: ignore[arg-type]
    assert i18n.t_code("units", "yes", language="en") == "yes"  # type: ignore[arg-type]


def test_an_unsupported_language_warns_once_and_falls_back(lenient: None) -> None:
    """An unsupported ``language`` uses the current language, with one warning however often it repeats."""
    with structlog.testing.capture_logs() as logs:
        assert t("units.yes", language="de") == "yes"  # type: ignore[arg-type]
        assert t("units.yes", language="de") == "yes"  # type: ignore[arg-type]
    assert [e["event"] for e in logs] == ["i18n_language_unsupported"]


def test_an_unsupported_language_raises_in_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strict mode turns an unsupported ``language`` into a ``ValueError``."""
    monkeypatch.setenv(STRICT_VARIABLE, "1")
    with pytest.raises(ValueError):
        t("units.yes", language="de")  # type: ignore[arg-type]


def test_a_nested_namespace_is_read_through_dotted_keys(fixture_root: Path) -> None:
    """A nested catalogue answers ``t("ns.group.key")`` in both languages, plural groups included."""
    _write(
        fixture_root,
        "en",
        "demo",
        {"group": {"key": "Deep", "files_one": "{{count}} file", "files_other": "{{count}} files"}},
    )
    _write(
        fixture_root,
        "fr",
        "demo",
        {"group": {"key": "Profond", "files_one": "{{count}} fichier", "files_other": "{{count}} fichiers"}},
    )
    assert t("demo.group.key", language=Language.EN) == "Deep"
    assert t("demo.group.key", language=Language.FR) == "Profond"
    assert t("demo.group.files", language=Language.EN, count=2) == "2 files"
    assert t("demo.group.files", language=Language.FR, count=1) == "1 fichier"


def test_falls_back_to_the_other_language(fixture_root: Path) -> None:
    """A key present in one language only is returned from that one."""
    _write(fixture_root, "en", "demo", {"only_english": "English only"})
    _write(fixture_root, "fr", "demo", {})
    assert t("demo.only_english", language=Language.FR) == "English only"


def test_missing_key_returns_the_key_and_warns_once(fixture_root: Path, lenient: None) -> None:
    """A key in no catalogue is returned as is, with one warning per key and language."""
    with structlog.testing.capture_logs() as logs:
        assert t("units.absent", language=Language.EN) == "units.absent"
        assert t("units.absent", language=Language.EN) == "units.absent"
    missing = [e for e in logs if e["event"] == "i18n_key_missing"]
    assert len(missing) == 1
    assert missing[0]["key"] == "units.absent"


def test_missing_key_raises_in_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strict mode turns a missing key into an error."""
    monkeypatch.setenv(STRICT_VARIABLE, "1")
    with pytest.raises(MissingTranslation):
        t("units.absent")


def test_unsupplied_placeholder_stays_and_warns(fixture_root: Path, lenient: None) -> None:
    """A placeholder the caller did not supply stays in the text, with one warning."""
    _write(fixture_root, "en", "demo", {"hello": "Hello {{name}}"})
    with structlog.testing.capture_logs() as logs:
        assert t("demo.hello", language=Language.EN) == "Hello {{name}}"
        assert t("demo.hello", language=Language.EN) == "Hello {{name}}"
    assert len([e for e in logs if e["event"] == "i18n_param_missing"]) == 1


def test_unsupplied_placeholder_raises_in_strict(fixture_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Strict mode turns an unsupplied placeholder into an error."""
    _write(fixture_root, "en", "demo", {"hello": "Hello {{name}}"})
    monkeypatch.setenv(STRICT_VARIABLE, "1")
    with pytest.raises(MissingTranslation):
        t("demo.hello", language=Language.EN)


def test_params_are_interpolated_and_extras_ignored(fixture_root: Path) -> None:
    """``{{name}}`` becomes ``str(value)``; an extra parameter is ignored."""
    _write(fixture_root, "en", "demo", {"hello": "Hello {{name}} ({{n}})"})
    assert t("demo.hello", language=Language.EN, name="Ada", n=3, extra="x") == "Hello Ada (3)"


def test_plural_by_language(fixture_root: Path) -> None:
    """French counts 0 and 1 as ``one``; English counts only 1."""
    plural = {"files_one": "{{count}} file", "files_other": "{{count}} files"}
    _write(fixture_root, "en", "demo", plural)
    _write(fixture_root, "fr", "demo", {"files_one": "{{count}} fichier", "files_other": "{{count}} fichiers"})
    assert t("demo.files", language=Language.FR, count=0) == "0 fichier"
    assert t("demo.files", language=Language.EN, count=0) == "0 files"
    assert t("demo.files", language=Language.FR, count=1) == "1 fichier"
    assert t("demo.files", language=Language.EN, count=1) == "1 file"
    assert t("demo.files", language=Language.FR, count=2) == "2 fichiers"
    assert t("demo.files", language=Language.EN, count=2) == "2 files"


def test_resolve_language_precedence() -> None:
    """Each variable wins over the next; unsupported or empty values fall to the default."""
    chain = {"PERSONALSCRAPER_LANG": "en", "LC_ALL": "fr", "LC_MESSAGES": "fr", "LANG": "fr"}
    assert resolve_language(chain) is Language.EN
    assert resolve_language({"LC_ALL": "en_US.UTF-8", "LC_MESSAGES": "fr", "LANG": "fr"}) is Language.EN
    assert resolve_language({"LC_MESSAGES": "en", "LANG": "fr"}) is Language.EN
    assert resolve_language({"LANG": "fr_FR.UTF-8"}) is Language.FR
    for value in ("C", "POSIX", "de_DE.UTF-8", ""):
        assert resolve_language({"LANG": value}) is DEFAULT_LANGUAGE
    assert resolve_language({}) is DEFAULT_LANGUAGE
    # An empty variable is skipped, not read as « unsupported ».
    assert resolve_language({"PERSONALSCRAPER_LANG": "", "LANG": "en"}) is Language.EN


def test_english_when_no_language_is_named() -> None:
    """No locale, a ``C`` locale or an unsupported one resolves to English, the default."""
    assert resolve_language({}) is Language.EN
    assert resolve_language({"LANG": "C"}) is Language.EN
    assert resolve_language({"LANG": "de_DE.UTF-8"}) is Language.EN


def test_unsupported_personalscraper_lang_warns() -> None:
    """A PERSONALSCRAPER_LANG naming an unsupported language yields the default and one warning."""
    with structlog.testing.capture_logs() as logs:
        assert resolve_language({LANGUAGE_VARIABLE: "de"}) is DEFAULT_LANGUAGE
    assert [e["event"] for e in logs] == ["i18n_language_unsupported"]


def test_current_language_follows_the_environment_and_the_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """``current_language`` reads the environment (suite pinned to en); ``use_language`` overrides a block."""
    assert current_language() is Language.EN
    with use_language(Language.FR):
        assert current_language() is Language.FR
        assert t("units.yes") == "oui"
    assert current_language() is Language.EN


def test_use_language_is_isolated_per_thread() -> None:
    """Two threads under two languages each read their own."""
    seen: dict[str, str] = {}
    barrier = threading.Barrier(2)

    def worker(name: str, language: Language) -> None:
        """Read ``units.yes`` under ``language``, in step with the other thread."""
        with use_language(language):
            barrier.wait(timeout=5)
            seen[name] = t("units.yes")
            barrier.wait(timeout=5)

    threads = [
        threading.Thread(target=worker, args=("fr", Language.FR)),
        threading.Thread(target=worker, args=("en", Language.EN)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert seen == {"fr": "oui", "en": "yes"}


def test_unreadable_catalogue_degrades(fixture_root: Path, lenient: None) -> None:
    """Invalid JSON: ``t`` returns the key, logs one error, never raises."""
    _write(fixture_root, "en", "broken", "{ not json")
    _write(fixture_root, "fr", "broken", "{ not json")
    with structlog.testing.capture_logs() as logs:
        assert t("broken.x", language=Language.EN) == "broken.x"
        assert t("broken.y", language=Language.EN) == "broken.y"
    errors = [e for e in logs if e["event"] == "i18n_catalogue_unreadable"]
    assert len(errors) == 2  # one per language file, once each
    assert {e["language"] for e in errors} == {"en", "fr"}


def test_t_code_is_t_of_the_joined_key() -> None:
    """``t_code`` looks up ``<namespace>.<code>``."""
    assert i18n.t_code("units", "yes", language=Language.FR) == "oui"
