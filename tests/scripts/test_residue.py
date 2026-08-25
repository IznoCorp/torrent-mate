"""Tests for R80's readers — the half of the rule that needs no browser.

`frontend/maquette/harness/residue.py` pairs each unlayered `legacy.css`
selector with the typed variant wearing its identity anchor, then compares
computed styles in the document. THE COMPARISON needs Chrome. THE PAIRING does
not: it is four pure functions over text, and they are where every defect this
rule has had so far actually lived.

Three of them were found by adversarial review, after the rule was written,
green, and merged into the contracts tier:

  the factory reader split a `cva()` call on a comma inside a COMMENT, so three
      factories came out with an empty base and took their pairs with them;
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
    """Imports the rule's module without running it."""
    sys.path.insert(0, str(HARNESS))
    spec = importlib.util.spec_from_file_location("residue", HARNESS / "residue.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rule = load()


class TestBalanced:
    """A call ends at its closing parenthesis, and never inside a string."""

    def test_a_parenthesis_inside_a_class_literal_does_not_extend_the_call(self) -> None:
        """`before:content-['(']` is ordinary Tailwind and used to swallow the file."""
        source = 'cva("pip before:content-[\'(\'] w-2", {}) ; const after = "leftover";'
        end = rule.balanced(source, source.index("("))
        assert source[end - 1] == ")"
        assert "leftover" not in source[:end]

    def test_a_closing_parenthesis_inside_a_literal_does_not_end_the_call(self) -> None:
        """The other direction: it used to truncate the call and empty the base."""
        source = "cva(\"pip before:content-[')'] w-2\", { variants: {} })"
        assert rule.balanced(source, source.index("(")) == len(source)

    def test_an_unclosed_call_stops_at_the_end_rather_than_running_away(self) -> None:
        """No exception, and no index past the text."""
        source = 'cva("pip", {'
        assert rule.balanced(source, source.index("(")) == len(source)


class TestWithoutComments:
    """A comment's comma must not end a call's first argument."""

    def test_a_comma_in_a_line_comment_is_blanked(self) -> None:
        """The defect: one comment ended the base after four characters."""
        source = 'cva(\n  // one, two, three\n  "sec flex",\n)'
        assert "one, two" not in rule.without_comments(source)
        assert '"sec flex"' in rule.without_comments(source)

    def test_a_block_comment_is_blanked_and_the_length_is_kept(self) -> None:
        """Offsets are preserved, so nothing downstream has to adjust."""
        source = 'const a = /* a, b, c */ "x";'
        blanked = rule.without_comments(source)
        assert len(blanked) == len(source)
        assert "a, b, c" not in blanked and '"x"' in blanked

    def test_a_double_slash_inside_a_class_literal_survives(self) -> None:
        """`bg-[url(//host/x)]` is a class name, not a comment."""
        source = 'cva("card bg-[url(//host/x)] p-4")'
        assert "//host/x" in rule.without_comments(source)

    def test_an_apostrophe_in_a_comment_does_not_open_a_quote_run(self) -> None:
        """The comment branch consumes it before the quote branch is reached."""
        source = '/* the engine\'s markup */\ncva("sec flex")'
        assert '"sec flex"' in rule.without_comments(source)

    def test_a_jsx_apostrophe_derails_it_and_that_is_written_down(self) -> None:
        """A KNOWN LIMIT, held so it cannot become a surprise.

        The docstring names this and the regex-literal case as untracked. The
        loud consequence — an empty base — is refused by the `unread` hold; the
        quiet one is a truncated branch table. This case exists so the limit is
        measured rather than asserted, and so the day someone closes it, a test
        turns red and asks them to update the docstring with it.
        """
        source = "const a = <p>don't</p>; // note, here\n"
        assert rule.without_comments(source) == source, "still untracked — see the docstring"


class TestFactoryReading:
    """Every `cva(` call is accounted for: read, unreadable, or a duplicate."""

    def test_the_repository_accounts_for_every_call(self) -> None:
        """The hold the rule runs, exercised without a browser."""
        factories, files_read, unread, duplicates, calls = rule.read_factories()
        assert files_read > 0 and calls > 0
        assert unread == []
        assert len(factories) + len(unread) + len(duplicates) == calls

    def test_two_factories_claiming_one_anchor_are_named_not_overwritten(self) -> None:
        """Three do today, and the last one read used to win in silence."""
        _, _, _, duplicates, _ = rule.read_factories()
        assert duplicates, "the three known collisions must be reported, never absorbed"
        assert all("claimed by" in entry for entry in duplicates)


class TestResidueReading:
    """The stylesheet is read as CSS, at-rules and all."""

    def test_a_rule_inside_an_at_rule_is_read_as_itself(self) -> None:
        """`@media (…) { .a { … } }` yields `.a`, never the media prelude."""
        text = rule.strip_comments(
            "@media (prefers-reduced-motion: no-preference) {\n  .herobg { animation: heroin 1s; }\n}"
        )
        heads = [head.strip() for head, _ in rule.RULE.findall(text)]
        assert heads == [".herobg"]

    def test_the_repository_pairs_at_or_above_its_floor(self) -> None:
        """The floor is the MEASURED count, and it is a ratchet.

        Seven was B-067's tally and it was the wrong floor the moment the rule
        found sixteen: nine pairs could have stopped being compared with the
        hold still green.
        """
        factories, _, _, _, _ = rule.read_factories()
        rules, declared = rule.read_residue()
        cases, unpaired, toggled, contextual = rule.pair_up(rules, factories)
        assert declared > 0 and rules
        assert len(cases) >= rule.PAIRS_FLOOR
        # The three buckets are printed by name every run; none may be empty of
        # meaning — `unpaired` is the engine's own markup, which is the whole
        # reason the residue exists.
        assert unpaired and isinstance(toggled, list) and isinstance(contextual, list)

    def test_the_utility_probe_never_wears_the_anchor_it_is_compared_against(self) -> None:
        """Otherwise the comparison would hold the residue against itself."""
        factories, _, _, _, _ = rule.read_factories()
        rules, _ = rule.read_residue()
        cases, _, _, _ = rule.pair_up(rules, factories)
        for case in cases:
            assert not set(case["worn"]) & set(case["utilities"]), case["selector"]
