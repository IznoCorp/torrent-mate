"""Tests for the maquette CSS extractor's selector scoping.

THE EXTRACTOR HAD NO TEST. It rewrites every selector of the application
stylesheet, its `--check` mode is a gate in `make check` and in CI, and a
mistake in that rewrite is invisible to `--check` by construction: the guard
compares the generated text against what the extractor emits, so an extractor
that emits the wrong thing agrees with itself perfectly.

The defect that prompted these: `:root[data-theme="light"]` was rewritten to
`.tm`, dropping the attribute. Both theme blocks would have collapsed onto one
selector of equal specificity and the later one would have won unconditionally
— the theme switch dead, the text exactly as expected, and no named state
driving the light theme for the parity probe to notice.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "extract-maquette-css.py"


def load():
    """Imports the extractor, despite its hyphenated filename."""
    spec = importlib.util.spec_from_file_location("extract_maquette_css", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extractor = load()


class TestApplyScope:
    """`apply_scope` — the one rewrite every extracted selector goes through."""

    def test_bare_root_becomes_the_scope(self) -> None:
        """Custom properties on `:root` must land on the app's root.

        Scoped as a DESCENDANT they would sit below it, and every `var()`
        under the root would resolve to nothing.
        """
        assert extractor.apply_scope(":root") == extractor.SCOPE

    def test_a_qualified_root_keeps_its_qualifier_AND_its_position(self) -> None:
        """Two mistakes were made here in one day; the parity probe caught both.

        Dropping the attribute made `:root[data-theme="light"]` a second,
        unconditional `:root`: the two theme blocks collapsed to equal
        specificity, source order decided, and the theme switch died silently.

        Welding the qualifier to the scope — `.tm[data-theme="light"]` — was no
        better and looked correct: the attribute sits on `<html>` and the scope
        class on `<body>`, so it asks ONE element for both and matches nothing.
        7 300 divergences, the whole light theme falling back to dark.

        The qualified root stays where it is and the scope follows it.
        """
        scoped = extractor.apply_scope(':root[data-theme="light"]')

        assert scoped == f"{extractor.SCOPE}".join([':root[data-theme="light"] ', ""])

    def test_a_qualified_html_or_body_is_treated_the_same_way(self) -> None:
        """The same rule, and it was missed on the first pass at this branch."""
        assert extractor.apply_scope("html.selecting") == f"html.selecting {extractor.SCOPE}"
        assert extractor.apply_scope("body.locked") == f"body.locked {extractor.SCOPE}"

    def test_a_qualified_root_with_a_descendant_keeps_both(self) -> None:
        """A document-rooted selector keeps its head and gains the scope after it."""
        scoped = extractor.apply_scope(':root[data-theme="light"] body')

        assert '[data-theme="light"]' in scoped

    def test_a_document_rooted_selector_keeps_its_head(self) -> None:
        """`.tm html…` would ask for a `.tm` ancestor ABOVE `<html>`: matches nothing."""
        assert extractor.apply_scope("html.selecting .bottombar").startswith("html.selecting")

    def test_an_ordinary_selector_is_nested_under_the_scope(self) -> None:
        """The common case, unchanged."""
        assert extractor.apply_scope(".card") == f"{extractor.SCOPE} .card"

    def test_a_selector_list_is_scoped_part_by_part(self) -> None:
        """Each comma-separated part decides on its own."""
        scoped = extractor.apply_scope(':root[data-theme="light"], .card')

        assert scoped == f':root[data-theme="light"] {extractor.SCOPE}, {extractor.SCOPE} .card'
