"""The design host's sign-in page speaks the visitor's browser language (OPEN-2 B).

WHAT IT PAYS FOR. Before anyone is signed in, the interface speaks the browser's language when
it is French or English, and English otherwise (the operator, 2026-10-04: OPEN-2 B). On tm-design
the sign-in page is not the prototype's: ``serve.py`` builds it by extracting the prototype's
markup, and no script of the application runs there — so the host has to word it itself, from
the same keys the prototype's boot reads (``data-words``, ``data-words-label``) and the same rule
for picking the language (the first tag the interface speaks).

WHAT MAKES IT NON-VACUOUS. The page is built by ``login_page`` itself and read as the visitor gets
it: its ``lang``, its title, every keyed word and the e-mail label, each compared with the
catalogue's value for that language — and the French fallback words of the markup are held
absent from the English page, so a page that kept them would fail.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from types import ModuleType

import pytest
from _repo_paths import MAQUETTE

DESIGN = MAQUETTE / "design"
CATALOGUES = {language: json.loads((DESIGN / "src" / "i18n" / f"{language}.json").read_text(encoding="utf-8"))
              for language in ("fr", "en")}


def _serve() -> ModuleType:
    """Loads ``serve.py`` by its location, as ``scripts/csstokens_login.py`` does.

    Returns:
        The module.
    """
    sys.path.insert(0, str(MAQUETTE))
    spec = importlib.util.spec_from_file_location("design_host_serve", MAQUETTE / "serve.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SERVE = _serve()


@pytest.mark.parametrize(
    ("header", "language"),
    [
        ("fr-FR,fr;q=0.9,en;q=0.8", "fr"),
        ("en-US,en;q=0.9", "en"),
        ("de-DE,de;q=0.9,fr;q=0.8", "fr"),
        ("de-DE,es;q=0.5", "en"),
        ("en;q=0.2, fr;q=0.9", "fr"),
        ("fr;q=0", "en"),
        ("", "en"),
        (None, "en"),
    ],
)
def test_the_language_is_the_first_tag_the_interface_speaks(header: str | None, language: str) -> None:
    """``Accept-Language`` read by preference: the first French or English tag, else English."""
    assert SERVE.request_language(header) == language


@pytest.mark.parametrize("language", ["fr", "en"])
def test_the_sign_in_page_is_worded_in_the_language(language: str) -> None:
    """Every keyed word, the accessible name, the e-mail label, the title and ``lang`` follow it."""
    page = SERVE.login_page(False, language=language).decode()
    gate = CATALOGUES[language]["screens"]["gate"]
    assert f'<html lang="{language}">' in page
    assert f"<title>{CATALOGUES[language]['server']['login']['title']}</title>" in page
    for key in ("title", "subtitle", "password", "invalid", "submit"):
        assert re.search(rf'data-words="screens\.gate\.{key}"[^>]*>{re.escape(gate[key])}<', page), key
    assert f'aria-label="{gate["title"]}"' in page
    assert f"<span>{gate['email']}</span>" in page


def test_the_english_page_keeps_none_of_the_french_fallback() -> None:
    """The markup's French — the page-without-script fallback — never reaches an English visitor."""
    page = SERVE.login_page(False, language="en").decode()
    french = CATALOGUES["fr"]["screens"]["gate"]
    for key in ("subtitle", "password", "invalid", "submit", "email"):
        assert french[key] not in page, key


def test_the_reason_is_said_in_the_language() -> None:
    """A session ended is said in the visitor's language, under the English subtitle."""
    page = SERVE.login_page(False, "reasonExpired", language="en").decode()
    assert CATALOGUES["en"]["server"]["login"]["reasonExpired"] in page
