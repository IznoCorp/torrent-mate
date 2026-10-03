"""Catalogue loading, plural rule and interpolation for the translation layer.

Pure mechanics, no policy: which language to use, what to do about a missing key and whether to
raise are decided by :mod:`personalscraper.i18n`. A catalogue is one JSON file per namespace and
language, ``<root>/<language>/<namespace>.json``, nested objects with dotted access.
"""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Mapping
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Any

from personalscraper.logger import get_logger

log = get_logger("i18n")

_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")

# The catalogue root, overridable by tests; ``None`` means the packaged one.
_root_override: Traversable | None = None


def catalogue_root() -> Traversable:
    """Return the directory holding the ``fr/``, ``en/`` and ``one_sided/`` folders.

    Returns:
        The test override when one is set, else the ``personalscraper.i18n`` package directory.
    """
    return _root_override if _root_override is not None else resources.files("personalscraper.i18n")


def set_root(root: Traversable | None) -> None:
    """Point the loader at another catalogue directory (tests), or back at the package (``None``).

    Args:
        root: The directory to read, or ``None`` for the packaged catalogues.
    """
    global _root_override
    _root_override = root
    load_namespace.cache_clear()


def flatten(tree: Mapping[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten nested objects into dotted keys, keeping string leaves only.

    Args:
        tree: A parsed catalogue file.
        prefix: The dotted path of ``tree`` itself.

    Returns:
        ``{"a.b.c": "text"}`` for every string leaf.
    """
    flat: dict[str, str] = {}
    for name, value in tree.items():
        path = f"{prefix}{name}"
        if isinstance(value, str):
            flat[path] = value
        elif isinstance(value, Mapping):
            flat.update(flatten(value, f"{path}."))
    return flat


@functools.cache
def load_namespace(language: str, namespace: str) -> Mapping[str, str]:
    """Read one namespace of one language, once per process.

    An absent or unreadable file yields an empty namespace and, for an unreadable one, one
    ``i18n_catalogue_unreadable`` error (the cache makes it once). It never raises.

    Args:
        language: The language code (``"fr"``, ``"en"``).
        namespace: The namespace, i.e. the file stem.

    Returns:
        The namespace's flattened ``{dotted key: text}``.
    """
    node = catalogue_root().joinpath(language, f"{namespace}.json")
    try:
        if not node.is_file():
            return {}
        parsed = json.loads(node.read_text(encoding="utf-8"))
        if not isinstance(parsed, Mapping):
            raise ValueError("a catalogue is a JSON object")
    except (OSError, ValueError) as exc:
        log.error("i18n_catalogue_unreadable", language=language, namespace=namespace, error=str(exc))
        return {}
    return flatten(parsed)


def plural_category(language: str, count: int | float) -> str:
    """Return the CLDR plural category (``one`` or ``other``) of ``count`` in ``language``.

    Args:
        language: The language code.
        count: The quantity.

    Returns:
        ``"one"`` for 0 and 1 in French, for 1 in English; ``"other"`` otherwise.
    """
    if language == "fr":
        return "one" if 0 <= count < 2 else "other"
    return "one" if count == 1 else "other"


def placeholders(text: str) -> set[str]:
    """Return the names of the ``{{name}}`` placeholders in ``text``."""
    return set(_PLACEHOLDER.findall(text))


def interpolate(text: str, params: Mapping[str, object]) -> tuple[str, set[str]]:
    """Replace each supplied ``{{name}}`` by ``str(value)``.

    Args:
        text: A catalogue string.
        params: The values supplied by the caller; extras are ignored.

    Returns:
        The text, and the names of the placeholders that stayed because no value was supplied.
    """
    missing: set[str] = set()

    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in params:
            return str(params[name])
        missing.add(name)
        return match.group(0)

    return _PLACEHOLDER.sub(substitute, text), missing
