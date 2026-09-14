"""Tests for the `cva()` factory reader — pure functions over text, no browser.

`frontend/maquette/harness/factories.py` reads every typed variant's anchor,
base and branches; `resolution_card.py` reads a factory's declaration through
it. It was R80's reading half, and every defect that rule had lived here.

Three of them were found by adversarial review, after the rule was written,
green, and merged into the contracts tier:

  the factory reader split a `cva()` call on a comma inside a COMMENT, so three
      factories came out with an empty base;
  `balanced()` counted parentheses inside STRING LITERALS while
      `split_top_level()` three functions below tracked quotes, so an ordinary
      `before:content-['(']` ran the reader to the end of the file;
  the `FACTORY` pattern wanted `export const NAME =` exactly, so four ordinary
      spellings matched nothing and vanished with no complaint.

None had failing output. All three exited 0. That is B-041's shape — the newest
guard being the one with nothing to re-run — so these exist.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[2] / "frontend" / "maquette" / "harness"


def load():
    """Imports the reader's module."""
    sys.path.insert(0, str(HARNESS))
    spec = importlib.util.spec_from_file_location("factories", HARNESS / "factories.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reader = load()


class TestBalanced:
    """A call ends at its closing parenthesis, and never inside a string."""

    def test_a_parenthesis_inside_a_class_literal_does_not_extend_the_call(self) -> None:
        """`before:content-['(']` is ordinary Tailwind and used to swallow the file."""
        source = 'cva("pip before:content-[\'(\'] w-2", {}) ; const after = "leftover";'
        end = reader.balanced(source, source.index("("))
        assert source[end - 1] == ")"
        assert "leftover" not in source[:end]

    def test_a_closing_parenthesis_inside_a_literal_does_not_end_the_call(self) -> None:
        """The other direction: it used to truncate the call and empty the base."""
        source = "cva(\"pip before:content-[')'] w-2\", { variants: {} })"
        assert reader.balanced(source, source.index("(")) == len(source)

    def test_an_unclosed_call_stops_at_the_end_rather_than_running_away(self) -> None:
        """No exception, and no index past the text."""
        source = 'cva("pip", {'
        assert reader.balanced(source, source.index("(")) == len(source)


class TestWithoutComments:
    """A comment's comma must not end a call's first argument."""

    def test_a_comma_in_a_line_comment_is_blanked(self) -> None:
        """The defect: one comment ended the base after four characters."""
        source = 'cva(\n  // one, two, three\n  "sec flex",\n)'
        assert "one, two" not in reader.without_comments(source)
        assert '"sec flex"' in reader.without_comments(source)

    def test_a_block_comment_is_blanked_and_the_length_is_kept(self) -> None:
        """Offsets are preserved, so nothing downstream has to adjust."""
        source = 'const a = /* a, b, c */ "x";'
        blanked = reader.without_comments(source)
        assert len(blanked) == len(source)
        assert "a, b, c" not in blanked and '"x"' in blanked

    def test_a_double_slash_inside_a_class_literal_survives(self) -> None:
        """`bg-[url(//host/x)]` is a class name, not a comment."""
        source = 'cva("card bg-[url(//host/x)] p-4")'
        assert "//host/x" in reader.without_comments(source)

    def test_an_apostrophe_in_a_comment_does_not_open_a_quote_run(self) -> None:
        """The comment branch consumes it before the quote branch is reached."""
        source = '/* the engine\'s markup */\ncva("sec flex")'
        assert '"sec flex"' in reader.without_comments(source)

    def test_a_jsx_apostrophe_derails_it_and_that_is_written_down(self) -> None:
        """A KNOWN LIMIT, held so it cannot become a surprise.

        The docstring names this and the regex-literal case as untracked. The
        loud consequence — an empty base — is refused by the `unread` hold; the
        quiet one is a truncated branch table. This case exists so the limit is
        measured rather than asserted, and so the day someone closes it, a test
        turns red and asks them to update the docstring with it.
        """
        source = "const a = <p>don't</p>; // note, here\n"
        assert reader.without_comments(source) == source, "still untracked — see the docstring"


class TestFactoryReading:
    """Every `cva(` call is accounted for: read, unreadable, or a duplicate."""

    def test_the_repository_accounts_for_every_call(self) -> None:
        """The hold `resolution_card.py` relies on, exercised without a browser."""
        factories, files_read, unread, duplicates, calls = reader.read_factories()
        assert files_read > 0 and calls > 0
        assert unread == []
        assert len(factories) + len(unread) + len(duplicates) == calls

    def test_two_factories_claiming_one_anchor_are_named_not_overwritten(self) -> None:
        """Three do today, and the last one read used to win in silence."""
        _, _, _, duplicates, _ = reader.read_factories()
        assert duplicates, "the three known collisions must be reported, never absorbed"
        assert all("claimed by" in entry for entry in duplicates)
