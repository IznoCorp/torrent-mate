"""The backend's translation layer: every text it shows a person exists in French and English.

``t("<namespace>.<key>", **params)`` returns the text in the current language. Catalogues are
JSON files, one per namespace and language (``fr/<namespace>.json``, ``en/<namespace>.json``),
with i18next-style ``{{name}}`` placeholders and ``_one`` / ``_other`` plural suffixes. A string
holds words and placeholders only; markup (Rich, HTML) stays in the code around the call.

A lookup never breaks a command, a web response or a message send: a missing key degrades to the
other language, then to the key itself, with one warning. Only strict mode (the test suite's)
raises, so a missing key is caught before it ships.
"""

from __future__ import annotations

import contextlib
import contextvars
import functools
import os
import threading
from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager
from enum import StrEnum
from pathlib import Path
from typing import Final, TypeAlias

from personalscraper.i18n import _catalogue
from personalscraper.logger import get_logger

log = get_logger("i18n")


class Language(StrEnum):
    """The languages every user text exists in."""

    FR = "fr"
    EN = "en"


DEFAULT_LANGUAGE: Final[Language] = Language.EN
LANGUAGE_VARIABLE: Final[str] = "PERSONALSCRAPER_LANG"
STRICT_VARIABLE: Final[str] = "PERSONALSCRAPER_I18N_STRICT"

# Locale variables read after ours, in POSIX order of precedence.
_LOCALE_VARIABLES: Final[tuple[str, ...]] = (LANGUAGE_VARIABLE, "LC_ALL", "LC_MESSAGES", "LANG")

Param: TypeAlias = str | int | float


class MissingTranslation(LookupError):
    """Strict mode only: a key in no catalogue, or a placeholder the caller did not supply."""


_override: contextvars.ContextVar[Language | None] = contextvars.ContextVar("i18n_language", default=None)

# Warn once per (event, subject) per process; the lock guards the set across threads.
_warned: set[tuple[str, ...]] = set()
_warned_lock = threading.Lock()


def _warn_once(event: str, *subject: str, **fields: str) -> None:
    """Log ``event`` once per ``subject`` for the process."""
    with _warned_lock:
        if (event, *subject) in _warned:
            return
        _warned.add((event, *subject))
    log.warning(event, **fields)


def _strict() -> bool:
    """Whether a missing key or placeholder raises instead of degrading."""
    return os.environ.get(STRICT_VARIABLE) == "1"


def _language_part(value: str) -> Language | None:
    """Return the supported language of a locale value (``fr_FR.UTF-8`` → FR), or ``None``."""
    head = value.split(".", 1)[0].split("@", 1)[0].replace("-", "_").split("_", 1)[0].lower()
    try:
        return Language(head)
    except ValueError:
        return None


def resolve_language(environ: Mapping[str, str] | None = None) -> Language:
    """Choose the language from the environment.

    The first of ``PERSONALSCRAPER_LANG``, ``LC_ALL``, ``LC_MESSAGES``, ``LANG`` that is set and
    non-empty decides, by its language part. An unsupported value (``C``, ``POSIX``, ``de_DE``)
    gives :data:`DEFAULT_LANGUAGE`; ``PERSONALSCRAPER_LANG`` naming one also logs one
    ``i18n_language_unsupported`` warning.

    Args:
        environ: The environment to read; ``None`` reads ``os.environ``.

    Returns:
        The language to use.
    """
    env = os.environ if environ is None else environ
    for variable in _LOCALE_VARIABLES:
        value = env.get(variable, "")
        if not value:
            continue
        language = _language_part(value)
        if language is not None:
            return language
        if variable == LANGUAGE_VARIABLE:
            log.warning("i18n_language_unsupported", variable=variable, value=value)
        return DEFAULT_LANGUAGE
    return DEFAULT_LANGUAGE


@functools.cache
def _process_language() -> Language:
    """The environment's language, resolved once per process."""
    return resolve_language(os.environ)


def current_language() -> Language:
    """Return the language of the running code.

    Returns:
        The :func:`use_language` override if one is active, else the environment's language,
        resolved once for the process.
    """
    return _override.get() or _process_language()


@contextlib.contextmanager
def _use_language(language: Language) -> Iterator[None]:
    """Set the language override for the block and restore the previous one on exit."""
    token = _override.set(language)
    try:
        yield
    finally:
        _override.reset(token)


def use_language(language: Language) -> AbstractContextManager[None]:
    """Override the language inside a ``with`` block (per thread and per asyncio task).

    Args:
        language: The language to use inside the block.

    Returns:
        A context manager restoring the previous language on exit.
    """
    return _use_language(language)


def _coerce_language(language: Language | str | None) -> Language:
    """Return ``language`` as a :class:`Language`, or the current language when it is not one.

    Raises:
        ValueError: Only in strict mode, for a value that is not a supported language.
    """
    if language is None:
        return current_language()
    try:
        return Language(language)
    except ValueError:
        if _strict():
            raise
        _warn_once("i18n_language_unsupported", str(language), variable="language", value=str(language))
        return current_language()


def _find(key: str, language: Language, count: int | float | None) -> str | None:
    """Look ``key`` up in ``language``, then the other language; ``None`` when neither holds it."""
    namespace, _, path = key.partition(".")
    others = [other for other in Language if other is not language]
    for candidate in (language, *others):
        words = _catalogue.load_namespace(candidate.value, namespace)
        if count is not None:
            suffixed = f"{path}_{_catalogue.plural_category(candidate.value, count)}"
            if suffixed in words:
                return words[suffixed]
        if path in words:
            return words[path]
    return None


def t(key: str, /, *, language: Language | None = None, **params: Param) -> str:
    """Return the text of ``key`` (``"<namespace>.<path>"``) in ``language``.

    ``count=`` selects ``<key>_one`` or ``<key>_other`` by the language's plural rule. A key absent
    from ``language`` falls back to the other language, then to the key itself, with one
    ``i18n_key_missing`` warning per key and language. A ``{{name}}`` the caller did not supply
    stays in the text with one ``i18n_param_missing`` warning; an extra parameter is ignored.

    Args:
        key: The dotted key; its first segment is the namespace file.
        language: Overrides :func:`current_language` for this call; a ``str`` is coerced, and an
            unsupported one falls back to :func:`current_language` with one
            ``i18n_language_unsupported`` warning.
        **params: The values of the text's placeholders.

    Returns:
        The interpolated text.

    Raises:
        MissingTranslation: Only in strict mode (``PERSONALSCRAPER_I18N_STRICT=1``), for a key in
            no catalogue or a placeholder not supplied.
        ValueError: Only in strict mode, for a ``language`` that is not supported.
    """
    chosen = _coerce_language(language)
    count = params.get("count")
    text = _find(key, chosen, count if isinstance(count, (int, float)) else None)
    if text is None:
        if _strict():
            raise MissingTranslation(f"no text for {key!r} in any catalogue")
        _warn_once("i18n_key_missing", key, chosen.value, key=key, language=chosen.value)
        return key
    rendered, missing = _catalogue.interpolate(text, params)
    if missing:
        names = ", ".join(sorted(missing))
        if _strict():
            raise MissingTranslation(f"{key!r} needs {names}")
        _warn_once("i18n_param_missing", key, names, key=key, missing=names)
    return rendered


def t_code(namespace: str, code: str, /, *, language: Language | None = None, **params: Param) -> str:
    """Return ``t(f"{namespace}.{code}")`` for a member of a closed code set.

    The one sanctioned dynamic key: ``code`` is a ``StrEnum`` member and ``namespace`` is declared
    in ``CODE_SETS`` of ``tests/unit/i18n/test_catalogue.py``, which checks every member is worded.

    Args:
        namespace: The catalogue namespace of the code set.
        code: The member's value.
        language: Overrides :func:`current_language` for this call.
        **params: The values of the text's placeholders.

    Returns:
        The interpolated text.
    """
    return t(f"{namespace}.{code}", language=language, **params)


def _use_root_for_tests(root: Path | None) -> None:
    """Point the catalogues at ``root`` (``None``: the packaged ones) and clear every cache."""
    _catalogue.set_root(root)
    _reset_for_tests()


def _reset_for_tests() -> None:
    """Forget the loaded catalogues, the warnings already given and the resolved language."""
    _catalogue.load_namespace.cache_clear()
    _process_language.cache_clear()
    with _warned_lock:
        _warned.clear()
