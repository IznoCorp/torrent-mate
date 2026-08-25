#!/usr/bin/env python3
"""The sign-in gate's own arm of `check-css-tokens.py`.

WHY IT IS A FILE. `check-css-tokens.py` reached 1 026 non-blank lines against a
hard ceiling of 1 000, and the ceiling is not a suggestion. The split follows a
SUBJECT rather than a line count: everything here answers one question — is the
page `serve.py` composes by text extraction still built from chunks that exist,
and does every `var()` inside them resolve there?

That question has its own sources (the composer, the four files it binds) and
its own failure mode: a marker that moved file, which is exactly what happened
three times during L07 as the scale, the palette, the typeface, the reset and
the sign-in screen's own style each left the prototype fragment.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Borrowed from the main script rather than restated: a second copy of a
# pattern is a second thing to keep in step, and this module is only ever
# imported by it.
from csstokens_patterns import COMMENT, DECLARATION, HTML_COMMENT, RUNTIME_PREFIX, USE

ROOT = Path(__file__).resolve().parent.parent

# The four files `serve.py` binds, resolved here rather than imported from the
# main script: this module is the one that follows those bindings, and a
# constant defined where it is READ cannot drift from a copy elsewhere.
DESIGN = ROOT / "frontend" / "maquette" / "design"
FRAGMENT = DESIGN / "refonte.html"
MARKUP = DESIGN / "index.html"
BASE_LAYER = DESIGN / "src" / "styles" / "base.css"
THEME_LAYER = DESIGN / "src" / "styles" / "theme.css"
LEGACY_LAYER = DESIGN / "src" / "styles" / "legacy.css"


# The composer itself. The sign-in page is whatever IT extracts — a chunk the
# files offer and `serve.py` never asks for is not on the page, so the arm reads
# the composition rather than the markers.
COMPOSER = ROOT / "frontend" / "maquette" / "serve.py"

# `styles_source = PROTOTYPE.read_text()`: the local name an `extract()` call
# passes, bound to the constant that names the file it was read from.
SOURCE_BINDING = re.compile(r"(\w+)\s*=\s*(\w+)\.read_text\(")

# `extract(styles_source, "scale")`. The second argument is quoted, so the
# `def extract(source: str, marker: str)` line is not a call and does not match.
EXTRACT_CALL = re.compile(r"\bextract\(\s*(\w+)\s*,\s*\"([\w-]+)\"\s*\)")

# `BASE_STYLESHEET` joined when L07 moved the base layer out of the fragment,
# taking `login:font` and `login:socle` with it. The arm caught that move on
# the first run after it — which is what it is for — and the repair is a new
# binding on both sides rather than a looser match here.
SOURCE_FILES = {
    "PROTOTYPE": FRAGMENT,
    "SHELL_DOCUMENT": MARKUP,
    "BASE_STYLESHEET": BASE_LAYER,
    "THEME_STYLESHEET": THEME_LAYER,
    "LEGACY_STYLESHEET": LEGACY_LAYER,
}


def without_python_comments(source: str) -> str:
    """Blanks out `#` comments, quotes respected.

    A commented-out `extract()` call composes nothing, and an arm that counted
    it would report a chunk the page never receives. A naive per-line split on
    `#` would also cut a line at a `#` inside a string literal, so the scan
    tracks the quote it is in.

    Args:
        source: Python source text.

    Returns:
        The same text with every comment replaced by spaces, line breaks kept
        so a reader can still map a match back to a line.
    """
    kept: list[str] = []
    quote = ""
    index = 0
    while index < len(source):
        char = source[index]
        if quote:
            kept.append(char)
            if char == "\\" and index + 1 < len(source):
                kept.append(source[index + 1])
                index += 2
                continue
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
            kept.append(char)
        elif char == "#":
            end = source.find("\n", index)
            end = len(source) if end < 0 else end
            kept.append(" " * (end - index))
            index = end
            continue
        else:
            kept.append(char)
        index += 1
    return "".join(kept)


def composed_chunks() -> dict[str, str] | None:
    """Collects the chunks `serve.py` actually composes the sign-in page from.

    The set is read from the composer rather than from the markers: a chunk the
    files offer and `serve.py` never extracts is not on the page, and holding
    the page to it would report a token the browser is in fact given. Which
    file each chunk comes from is read the same way — `serve.py` binds its two
    sources by name, and this follows the binding rather than guessing.

    Returns:
        Chunk text keyed by chunk name, or `None` when the composer cannot be
        read, names a source this arm cannot resolve, or extracts a chunk whose
        markers are missing — the same failure `extract()` itself raises on.
    """
    if not COMPOSER.exists():
        print(
            f"check-login: {COMPOSER} not found — the composition cannot be "
            "read, so a « no violation » here would mean nothing",
            file=sys.stderr,
        )
        return None
    composer = without_python_comments(COMPOSER.read_text(encoding="utf-8"))

    # `styles_source = PROTOTYPE.read_text()` and its sibling: the local name an
    # `extract()` call passes, bound to the constant that names the file.
    bound = {local: constant for local, constant in SOURCE_BINDING.findall(composer)}
    calls = EXTRACT_CALL.findall(composer)
    if not calls:
        print(
            f'check-login: no `extract(<source>, "<chunk>")` call in '
            f"{COMPOSER.name} — an arm that reads zero chunks holds nothing",
            file=sys.stderr,
        )
        return None

    texts: dict[Path, str] = {}
    chunks: dict[str, str] = {}
    for local, name in calls:
        path = SOURCE_FILES.get(bound.get(local, ""))
        if path is None:
            print(
                f"  login: {COMPOSER.name} extracts login:{name} from `{local}`, "
                "which this arm cannot resolve to a file — the composition it "
                "measures would not be the one served.",
                file=sys.stderr,
            )
            return None
        if not path.exists():
            print(
                f"check-login: {path} not found — the composed page cannot be "
                "read, so a « no violation » here would mean nothing",
                file=sys.stderr,
            )
            return None
        if name in chunks:
            continue
        text = texts.setdefault(path, path.read_text(encoding="utf-8"))
        start = text.find(f"login:{name}:start")
        end = text.find(f"login:{name}:end")
        if start < 0 or end < 0 or end < start:
            print(
                f"  login: {COMPOSER.name} extracts login:{name} from "
                f"{path.name}, which carries no such marker pair — `extract()` "
                "raises on this and serves no sign-in page at all.",
                file=sys.stderr,
            )
            return None
        # The same slicing serve.extract() uses, deliberately: an arm that read
        # one character more than the composer would hold a chunk the page
        # never receives.
        chunks[name] = text[text.index("\n", start) + 1 : text.rindex("\n", start, end) + 1]
    return chunks


def login_arm() -> int:
    """Refuses a token the composed sign-in page uses but is never given.

    Returns:
        1 when anything was found, 0 otherwise.
    """
    chunks = composed_chunks()
    if chunks is None:
        return 1

    # Both comment syntaxes: the CSS chunks live in a <style>, the markup chunks
    # in the document. A declaration commented out in either satisfied nothing.
    composed = COMMENT.sub(" ", "\n".join(chunks.values()))
    composed = HTML_COMMENT.sub(" ", composed)
    declared = set(DECLARATION.findall(composed))
    used: set[str] = set()
    missing: set[str] = set()
    for name, fallback in USE.findall(composed):
        used.add(name)
        # A runtime token carrying a usable fallback is not owed a declaration:
        # nothing declares `--tm-*` in CSS, the shell publishes it, and the
        # fallback is what the page renders with until it has.
        if name.startswith(RUNTIME_PREFIX) and fallback.strip():
            continue
        if name not in declared:
            missing.add(name)

    for name in sorted(missing):
        print(
            f"  login: {name} is used by the composed sign-in page but declared "
            "in no chunk serve.py composes — the page is not given it, and "
            "resolves it to nothing.",
            file=sys.stderr,
        )
    if missing:
        return 1

    print(f"login: {len(used)} var() use(s) in the composed chunks, all declared there.")
    return 0
