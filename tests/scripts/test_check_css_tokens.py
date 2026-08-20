"""Tests for the shipped-stylesheet token guard.

IT SHIPPED WITH NO TEST, and an adversarial review defeated it five ways within
the hour: a declaration inside a comment satisfied a use, `var(/*c*/--x)` was
invisible, `var(--tm-h,)` counted as carrying a fallback, a declaration written
`.tm{--x:red}` on one line was not seen at all, and — the one that matters — a
token declared ONLY under a theme attribute counted as declared everywhere.

That last one is the guard's own subject one level down: a `var()` that resolves
under one condition and to nothing under every other is precisely the defect it
exists to refuse. Each case below is one of those five.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-css-tokens.py"


def load():
    """Imports the guard, despite its hyphenated filename."""
    spec = importlib.util.spec_from_file_location("check_css_tokens", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load()


def verdict(css: str) -> tuple[list[str], list[str], list[str]]:
    """Runs the guard's decider over one snippet."""
    return guard.unresolved(css)


class TestWhatResolves:
    """The ordinary cases, so a tightening cannot quietly refuse valid CSS."""

    def test_a_declared_token_resolves(self) -> None:
        """The baseline."""
        assert verdict(".tm{--x:red}\n.tm .a{color:var(--x)}") == ([], [], [])

    def test_a_declaration_on_one_line_counts(self) -> None:
        """`.tm{--x:red}` is valid CSS; anchoring to line starts refused it."""
        undefined, _, _ = verdict(".tm{--x:red}\n.tm .a{color:var(--x)}")

        assert undefined == []

    def test_a_theme_OVERRIDE_is_not_a_conditional_declaration(self) -> None:
        """Declared in the base scope AND under a theme is simply declared.

        This is what a theme IS, and refusing it would make the rule unusable
        the moment the light palette landed.
        """
        css = '.tm{--x:blue}\n:root[data-theme="light"] .tm{--x:red}\n.tm .a{color:var(--x)}'

        assert verdict(css) == ([], [], [])

    def test_a_runtime_token_with_a_real_fallback_resolves(self) -> None:
        """`--tm-*` is published by script; the fallback is what makes it safe."""
        assert verdict(".tm .a{height:var(--tm-h, 0px)}") == ([], [], [])


class TestWhatIsRefused:
    """The five defeats, each pinned so it cannot come back."""

    def test_an_undeclared_token_is_refused(self) -> None:
        """The state the whole wave existed to end."""
        undefined, _, _ = verdict(".tm .a{color:var(--nope)}")

        assert undefined == ["--nope"]

    def test_a_declaration_inside_a_COMMENT_grants_nothing(self) -> None:
        """Commented-out CSS is not CSS."""
        undefined, _, _ = verdict("/*\n--x: red;\n*/\n.tm .a{color:var(--x)}")

        assert undefined == ["--x"]

    def test_a_comment_inside_var_does_not_hide_the_use(self) -> None:
        """`var(/*c*/--nope)` is a use, and it used to be invisible."""
        undefined, _, _ = verdict(".tm .a{color:var(/*c*/--nope)}")

        assert undefined == ["--nope"]

    def test_a_token_declared_ONLY_under_a_condition_is_refused(self) -> None:
        """The guard's own subject, one level down.

        Under every other theme it resolves to nothing — a broken surface that
        renders correctly in exactly the one state someone happened to test.
        """
        css = ':root[data-theme="light"] .tm{--x:red}\n.tm .a{color:var(--x)}'
        undefined, conditional, _ = verdict(css)

        assert conditional == ["--x"]
        assert undefined == []

    def test_an_EMPTY_fallback_is_not_a_fallback(self) -> None:
        """`var(--tm-h,)` resolves to exactly as much as `var(--tm-h)`."""
        _, _, bare = verdict(".tm .a{height:var(--tm-h,)}")

        assert bare == ["--tm-h"]

    def test_a_runtime_token_with_no_fallback_is_refused(self) -> None:
        """It resolves to nothing until the script that sets it has run."""
        _, _, bare = verdict(".tm .a{height:var(--tm-h)}")

        assert bare == ["--tm-h"]


class TestTheSheetItself:
    """The guard is only real if its scope is."""

    def test_the_shipped_sheet_resolves_everything(self) -> None:
        """Green on this repository; red here means a real unresolved token."""
        assert verdict(guard.SHEET.read_text(encoding="utf-8")) == ([], [], [])

    def test_the_sheet_actually_uses_tokens(self) -> None:
        """A scope that empties would make « no violation » mean nothing."""
        css = guard.COMMENT.sub(" ", guard.SHEET.read_text(encoding="utf-8"))

        assert len(guard.USE.findall(css)) > 100
