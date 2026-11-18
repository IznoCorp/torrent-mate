"""Tests for the i18n placeholder guard's reading of a `t()` call's arguments.

B-154: the shorthand reader (`{ start, end }`) only saw a name followed by nothing but
commas, braces and blanks up to the end of the LINE, so a call written on one line yielded
only its last name and the guard reported every other placeholder as unsupplied.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
SCRIPT = SCRIPTS / "check-i18n-placeholders.py"


def load():
    """Imports the guard, despite its hyphenated filename."""
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("check_i18n_placeholders", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


guard = load()


def supplied(call: str) -> set[str]:
    """Returns the names the guard reads from one `t()` call's source text."""
    match = guard.CALL.search(call)
    assert match is not None, "the call was not recognised"
    return guard.supplied_names(match.group("args"))


@pytest.mark.parametrize(
    ("call", "names"),
    [
        pytest.param('t("k", { start, end })', {"start", "end"}, id="shorthand-on-one-line"),
        pytest.param('t("k", { start, middle, end })', {"start", "middle", "end"}, id="three-shorthands-on-one-line"),
        pytest.param('t("k", {\n  start,\n  end,\n})', {"start", "end"}, id="shorthand-on-several-lines"),
        pytest.param('t("k", { from: a, to: b })', {"from", "to"}, id="named-on-one-line"),
        pytest.param('t("k", { start, end: stop })', {"start", "end"}, id="shorthand-then-named"),
        pytest.param('t("k", { count: items.length, label })', {"count", "label"}, id="expression-value"),
        pytest.param('t("k", {\n  // french-ok: a note\n  start, end\n})', {"start", "end"}, id="comment-before"),
    ],
)
def test_every_name_a_call_passes_is_read(call: str, names: set[str]) -> None:
    """Each name the call passes is read, whatever the layout."""
    assert supplied(call) == names


def test_a_value_is_not_taken_for_a_name() -> None:
    """`{ a: foo, b: bar }` supplies `a` and `b`, never the identifiers `foo` and `bar`."""
    assert supplied('t("k", { a: foo, b: bar })') == {"a", "b"}
