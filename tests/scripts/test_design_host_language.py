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
from html.parser import HTMLParser
from types import ModuleType

import pytest
from _repo_paths import MAQUETTE

DESIGN = MAQUETTE / "design"
CATALOGUES = {
    language: json.loads((DESIGN / "src" / "i18n" / f"{language}.json").read_text(encoding="utf-8"))
    for language in ("fr", "en")
}


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


# THE BRAND IS NO LANGUAGE's: the wordmark's two halves are drawn as they are.
BRAND_WORDS = frozenset({"Torrent", "Mate"})


def _leaves(node: object) -> list[str]:
    """Every string of a catalogue, at any depth.

    Args:
        node: A catalogue, or one of its branches or leaves.

    Returns:
        The strings it holds.
    """
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [leaf for child in node.values() for leaf in _leaves(child)]
    if isinstance(node, list):
        return [leaf for child in node for leaf in _leaves(child)]
    return []


class _Words(HTMLParser):
    """Collects what a visitor reads of a page: its text nodes and its accessible names."""

    def __init__(self) -> None:
        """Starts with nothing read, outside any script or style."""
        super().__init__()
        self.words: list[str] = []
        self._skipped = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Reads an element's accessible name, and enters a script or a style.

        Args:
            tag: The element's name.
            attrs: Its attributes.
        """
        if tag in ("script", "style", "title"):
            self._skipped += 1
        self.words.extend(value for name, value in attrs if name == "aria-label" and value)

    def handle_endtag(self, tag: str) -> None:
        """Leaves a script or a style.

        Args:
            tag: The element's name.
        """
        if tag in ("script", "style", "title"):
            self._skipped -= 1

    def handle_data(self, data: str) -> None:
        """Reads a text node outside a script or a style.

        Args:
            data: The text.
        """
        text = " ".join(data.split())
        if text and not self._skipped:
            self.words.append(text)


def test_the_english_page_keeps_none_of_the_french_fallback() -> None:
    """Every word an English visitor reads — text and accessible names, the splash's too — is English.

    Read against the whole page rather than a list of keys: a French fallback nobody keyed (the
    startup screen the page appends) is no English catalogue's word, and fails here.
    """
    page = SERVE.login_page(False, language="en").decode()
    english = {" ".join(leaf.split()) for leaf in _leaves(CATALOGUES["en"])}
    reader = _Words()
    reader.feed(page)
    foreign = [word for word in reader.words if word not in english and word not in BRAND_WORDS]
    assert foreign == []


def test_the_reason_is_said_in_the_language() -> None:
    """A session ended is said in the visitor's language, under the English subtitle."""
    page = SERVE.login_page(False, "reasonExpired", language="en").decode()
    assert CATALOGUES["en"]["server"]["login"]["reasonExpired"] in page


# ELEMENTS THAT NEVER CLOSE: the reader must not wait for their end tag.
VOID_ELEMENTS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"})
# WORDED ELSEWHERE, OR NOBODY'S: the sign-in field's label is replaced by the e-mail's words at boot
# (`app/gate.ts`) and on the design host (`v1_door.as_v1_form`); the frame switch is the design
# review's own control, outside the interface.
WORDED_ELSEWHERE = frozenset({"Identifiant"})
OUTSIDE_THE_INTERFACE = "harness/"


def _word(key: str) -> str:
    """The French catalogue's word at a dotted key.

    Args:
        key: The key, as the markup names it.

    Returns:
        The word, its white space folded.
    """
    node: object = CATALOGUES["fr"]
    for part in key.split("."):
        assert isinstance(node, dict), key
        node = node[part]
    assert isinstance(node, str), key
    return " ".join(node.split())


class _Fallbacks(HTMLParser):
    """Collects every word of the shell document's body with the key it is worded by, if any."""

    def __init__(self) -> None:
        """Starts outside the body, with no element open."""
        super().__init__()
        self.found: list[tuple[str, str | None]] = []
        self._open: list[tuple[str, str | None, bool]] = []
        self._in_body = False

    def _skipped(self) -> bool:
        """Whether the reader stands in a script, a style or a region outside the interface.

        Returns:
            True when what it reads now is no word of the interface.
        """
        return any(tag in ("script", "style") or outside for tag, _, outside in self._open)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Reads an element's accessible name and opens it.

        Args:
            tag: The element's name.
            attrs: Its attributes.
        """
        if tag == "body":
            self._in_body = True
            return
        named = dict(attrs)
        outside = (named.get("data-part") or "").startswith(OUTSIDE_THE_INTERFACE)
        if self._in_body and not self._skipped() and not outside and named.get("aria-label"):
            self.found.append((str(named["aria-label"]), named.get("data-words-label")))
        if tag not in VOID_ELEMENTS:
            self._open.append((tag, named.get("data-words"), outside))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Reads a self-closed element's accessible name; nothing is opened.

        Args:
            tag: The element's name.
            attrs: Its attributes.
        """
        named = dict(attrs)
        if self._in_body and not self._skipped() and named.get("aria-label"):
            self.found.append((str(named["aria-label"]), named.get("data-words-label")))

    def handle_endtag(self, tag: str) -> None:
        """Closes the element.

        Args:
            tag: The element's name.
        """
        if tag in VOID_ELEMENTS:
            return
        while self._open:
            if self._open.pop()[0] == tag:
                break

    def handle_data(self, data: str) -> None:
        """Reads a text node with the key of the element that holds it.

        Args:
            data: The text.
        """
        text = " ".join(data.split())
        if text and self._in_body and not self._skipped():
            self.found.append((text, self._open[-1][1] if self._open else None))


def test_every_word_of_the_shell_is_keyed_and_its_french_is_the_catalogues() -> None:
    """The markup no component draws — the splash, the install bar, the top bar — is worded by key.

    A word with no key stays French for an English account: the boot rewords only what names its
    key (`src/i18n/index.ts` `wordMarkup`). And each fallback IS the French catalogue's word, so
    the page without script reads what the boot would say, extracted rather than retyped.
    """
    reader = _Fallbacks()
    reader.feed(SERVE.SHELL_DOCUMENT.read_text(encoding="utf-8"))
    unkeyed = [word for word, key in reader.found if key is None and word not in BRAND_WORDS | WORDED_ELSEWHERE]
    assert unkeyed == []
    retyped = [(word, key) for word, key in reader.found if key is not None and _word(key) != word]
    assert retyped == []


def test_the_french_splash_is_served_as_the_prototype_writes_it() -> None:
    """Worded in French, the startup screen the host serves IS the prototype's, byte for byte.

    Its fallback words are the French catalogue's, so wording them in French must change nothing:
    an escape the markup does not write (an apostrophe turned ``&#x27;``) makes the served screen a
    retyping of the prototype's, which the harness's « extracted from the prototype, never
    retyped » (``webui/harness/startup.py``) refuses.
    """
    splash = SERVE.extract(SERVE.SHELL_DOCUMENT.read_text(encoding="utf-8"), "splash")
    assert "'" in splash, "the splash holds no apostrophe: this test would distinguish nothing"
    assert SERVE.v1_door.worded(splash, CATALOGUES["fr"]) == splash
