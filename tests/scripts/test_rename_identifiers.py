"""Tests for the identifier-renaming tool.

The tool's own docstring promised "every shape in ``tests/scripts/``" and no
such file existed, so nothing held it. Every test below is a defect that was
found by auditing the campaign the tool carried out, and each one fails against
the tool as it stood before this file was written.

The discipline the module docstring states, and that these tests enforce: the
tool's failure mode is SILENT CORRUPTION, so where it cannot be certain it must
refuse loudly rather than guess.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "rename-identifiers.py"

# Anything the tool parses as JavaScript goes through `scripts/source-spans.mjs`,
# which requires `frontend/node_modules/typescript`. The `test` CI job installs
# Python only — the frontend deps live in the `frontend` job — so these skip
# there rather than failing, the same way the Makefile guards `check-frontend`
# and `openapi` with `if [ -d frontend/node_modules ]`. The Python-language
# tests below carry no such guard and run everywhere, on purpose: the parser
# they exercise is Python's own tokeniser.
needs_typescript = pytest.mark.skipif(
    not (ROOT / "frontend" / "node_modules" / "typescript").is_dir(),
    reason="frontend/node_modules/typescript absent (installed by the frontend CI job)",
)


def run(tmp_path: Path, mapping: dict[str, str], *flags: str) -> subprocess.CompletedProcess[str]:
    """Runs the tool over ``tmp_path/tree`` with ``mapping``.

    Args:
        tmp_path: The pytest temporary directory holding a ``tree/`` to walk.
        mapping: The rename table.
        *flags: Extra command-line flags (``--values``, ``--whole=…``, …).

    Returns:
        The completed process, with stdout and stderr captured.
    """
    table = tmp_path / "map.json"
    table.write_text(json.dumps(mapping), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(table), f"--root={tmp_path / 'tree'}", *flags],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )


def tree(tmp_path: Path, name: str, body: str) -> Path:
    """Creates ``tmp_path/tree/name`` holding ``body`` and returns its path."""
    root = tmp_path / "tree"
    root.mkdir(exist_ok=True)
    target = root / name
    target.write_text(body, encoding="utf-8")
    return target


# --- The prose hole: the defect that shipped to production -------------------


@needs_typescript
def test_multiword_string_is_never_rewritten_word_by_word(tmp_path: Path) -> None:
    """A sentence keeps every word: only a WHOLE-body match may move.

    This is the 429-line incident. ``"rien de conforme au profil"`` became
    ``"… au profile"`` and reached production, because the id test was applied
    to each space-separated word instead of to the whole string.
    """
    source = tree(
        tmp_path,
        "copy.js",
        'const a = "rien de conforme au profil";\nconst b = "profil";\n',
    )

    result = run(tmp_path, {"profil": "profile"}, "--values")

    assert result.returncode == 0, result.stderr
    body = source.read_text(encoding="utf-8")
    assert '"rien de conforme au profil"' in body, "the sentence was rewritten"
    assert '"profile"' in body, "CONTROL: the bare value did not move — dead tool?"


@needs_typescript
def test_whole_only_value_moves_alone_but_not_inside_a_sentence(tmp_path: Path) -> None:
    """``--whole=`` was declared, documented, passed — and never read."""
    source = tree(
        tmp_path,
        "mixed.js",
        'const bare = "profil";\nconst sentence = "conforme au profil ici";\n',
    )

    result = run(tmp_path, {"profil": "profile"}, "--values", "--whole=profil")

    assert result.returncode == 0, result.stderr
    body = source.read_text(encoding="utf-8")
    assert 'const bare = "profile";' in body
    assert 'const sentence = "conforme au profil ici";' in body


@needs_typescript
def test_inner_words_is_opt_in(tmp_path: Path) -> None:
    """A class list can still be rewritten, but only when asked for by name."""
    source = tree(tmp_path, "classes.js", 'const c = "carte ouverte";\n')

    result = run(tmp_path, {"carte": "card"}, "--values", "--inner-words")

    assert result.returncode == 0, result.stderr
    assert 'const c = "card ouverte";' in source.read_text(encoding="utf-8")


@needs_typescript
def test_single_token_value_still_moves(tmp_path: Path) -> None:
    """The mode's whole reason for existing keeps working."""
    source = tree(tmp_path, "state.js", 'const s = "en_attente";\nconst k = "acq-en_attente";\n')

    result = run(tmp_path, {"en_attente": "pending"}, "--values")

    assert result.returncode == 0, result.stderr
    body = source.read_text(encoding="utf-8")
    assert '"pending"' in body
    assert '"acq-pending"' in body


# --- Tables that cannot mean what they say -----------------------------------


@needs_typescript
def test_chained_table_is_refused(tmp_path: Path) -> None:
    """``{a: b, b: c}`` collapsed both names onto ``c`` and exited zero."""
    source = tree(tmp_path, "chain.js", "const alpha = 1;\nconst beta = 2;\n")

    result = run(tmp_path, {"alpha": "beta", "beta": "gamma"})

    assert result.returncode != 0
    assert "chained" in result.stderr
    assert source.read_text(encoding="utf-8") == "const alpha = 1;\nconst beta = 2;\n"


@needs_typescript
def test_merging_table_is_refused(tmp_path: Path) -> None:
    """Two names onto one is a lost distinction, never an intended rename."""
    tree(tmp_path, "merge.js", "const un = 1;\nconst deux = 2;\n")

    result = run(tmp_path, {"un": "one", "deux": "one"})

    assert result.returncode != 0
    assert "merging" in result.stderr


# --- The parser must match the language --------------------------------------


def test_python_comment_with_an_apostrophe_does_not_abort_the_rename(tmp_path: Path) -> None:
    """The read-back proof parsed ``.py`` with the TypeScript parser.

    TypeScript reads the apostrophe in ``# l'ajout`` as an opening quote and
    ``\"\"\"`` as an empty string, so every Python file disagreed with itself:
    52 harness files out of 52 aborted, mid-walk.
    """
    source = tree(
        tmp_path,
        "harness.py",
        '"""Un module avec l\'apostrophe."""\n# une remarque avec l\'apostrophe\nCODE = "window.suivi"\n',
    )

    result = run(tmp_path, {"suivi": "follow"})

    assert result.returncode == 0, result.stderr + result.stdout
    assert "window.follow" in source.read_text(encoding="utf-8")


@needs_typescript
def test_every_file_is_renamed_when_none_of_them_fails(tmp_path: Path) -> None:
    """The happy path across several files, in walk order."""
    first = tree(tmp_path, "a_first.js", "const suivi = 1;\n")
    third = tree(tmp_path, "c_third.js", "const suivi = 3;\n")

    result = run(tmp_path, {"suivi": "follow"})

    assert result.returncode == 0, result.stderr
    assert "follow" in first.read_text(encoding="utf-8")
    assert "follow" in third.read_text(encoding="utf-8")


@needs_typescript
def test_a_file_the_parser_refuses_does_not_leave_the_tree_half_renamed(
    tmp_path: Path,
) -> None:
    """An abort mid-walk left earlier files WRITTEN and later ones untouched.

    The test that used to carry this name built two well-formed files and
    asserted they were both renamed — it never constructed a failing file, so
    it could not see the property it was named for. It would have passed with
    the defect fully present. This one builds the failure.

    `b_broken.js` cannot be parsed, so the walk raises on it. What must NOT
    happen is `a_first.js` keeping a rename while `c_third.js` never gets one:
    a half-renamed tree is worse than an untouched one, because it looks done.
    """
    first = tree(tmp_path, "a_first.js", "const suivi = 1;\n")
    tree(tmp_path, "b_broken.js", "const = = = ;\nfunction ( { \n")
    third = tree(tmp_path, "c_third.js", "const suivi = 3;\n")

    result = run(tmp_path, {"suivi": "follow"})

    renamed = [path.name for path in (first, third) if "follow" in path.read_text(encoding="utf-8")]
    # Either every file moved or none did. One of two is the failure.
    assert renamed in ([], ["a_first.js", "c_third.js"]), (
        f"tree left half renamed: {renamed} moved, exit={result.returncode}, stderr={result.stderr}"
    )


@needs_typescript
def test_an_ambiguous_shorthand_is_refused_not_guessed_at(tmp_path: Path) -> None:
    """`{ a, etat }` names the emitted key AND the binding, in three characters.

    Renaming it moves the wire contract while every `x.etat` reader stays —
    code that still parses, a read-back proof that only compares strings, and
    exit 0.

    EXPANDING IT AUTOMATICALLY WAS WORSE, and this test exists because that was
    tried: `{ etat }` and JSX's `{body}` are identical to a regex, so the
    expansion rewrote a pre-existing `{body}` expression container into
    `{corps: body}` in a file that did not contain the source name at all. Only
    a parser tells the two apart, and this pass has spans, not node kinds — so
    the unambiguous case is refused and the caller is told which mode owns it.
    """
    source = tree(
        tmp_path,
        "shorthand.js",
        "const etat = 1;\nconst bag = { a, etat };\nconsole.log(bag.etat);\n",
    )
    before = source.read_text(encoding="utf-8")

    result = run(tmp_path, {"etat": "state"})

    assert result.returncode != 0
    assert "SHORTHAND PROPERTY" in result.stderr
    assert "--properties" in result.stderr
    assert source.read_text(encoding="utf-8") == before


@needs_typescript
def test_an_object_key_is_left_alone(tmp_path: Path) -> None:
    """`{ etat: 2 }` is a contract with a reader; only --properties moves it."""
    source = tree(
        tmp_path,
        "keyed.js",
        "const etat = 1;\nconst keyed = { etat: 2 };\nconsole.log(keyed.etat);\n",
    )

    result = run(tmp_path, {"etat": "state"})

    assert result.returncode == 0, result.stderr
    body = source.read_text(encoding="utf-8")
    assert "const state = 1;" in body
    assert "{ etat: 2 }" in body
    assert "keyed.etat" in body


@needs_typescript
def test_a_jsx_expression_holding_the_TARGET_name_is_untouched(tmp_path: Path) -> None:
    """The corruption the expansion caused, pinned so it cannot come back.

    A file with no occurrence of the SOURCE name was rewritten, because the
    expansion searched for the target: `<p>{body}</p>` became `<p>{corps: body}</p>`.
    """
    source = tree(
        tmp_path,
        "view.jsx",
        "const body = 1;\nexport const C = () => <p>{body}</p>;\n",
    )
    before = source.read_text(encoding="utf-8")
    # CONTROL: this asserts a file did NOT change, which a tool writing nothing
    # satisfies perfectly. Something in the same run must move.
    control = tree(tmp_path, "control.js", "const corps = 1;\n")

    result = run(tmp_path, {"corps": "body"})

    assert result.returncode == 0, result.stderr
    assert source.read_text(encoding="utf-8") == before
    assert "const body = 1;" in control.read_text(encoding="utf-8"), (
        "CONTROL: the source name did not move anywhere — dead tool?"
    )


def test_python_prose_is_never_rewritten(tmp_path: Path) -> None:
    """The Python path substituted over the whole file, spans ignored.

    So a docstring, a comment and a sentence-shaped literal each had their
    French word replaced — « Le suivi est mis a jour ici » becoming « Le follow
    est mis a jour ici » — which is the exact corruption this tool exists to
    prevent, in the one language where nothing was watching.

    The JavaScript inside an evaluate string must still move: that is why the
    Python path renames inside strings at all.
    """
    source = tree(
        tmp_path,
        "harness.py",
        '"""Cette page affiche le suivi des choses."""\n'
        "# Le suivi est mis a jour ici.\n"
        'DRIVE = "()=>window.suivi()"\n'
        "def f():\n"
        '    """Retourne le suivi courant."""\n'
        '    return "le suivi de tout"\n',
    )

    result = run(tmp_path, {"suivi": "follow"})

    assert result.returncode == 0, result.stderr
    body = source.read_text(encoding="utf-8")
    assert "affiche le suivi des choses" in body, "module docstring rewritten"
    assert "# Le suivi est mis a jour ici." in body, "comment rewritten"
    assert "Retourne le suivi courant" in body, "function docstring rewritten"
    assert '"le suivi de tout"' in body, "a sentence-shaped literal rewritten"
    assert '"()=>window.follow()"' in body, "the evaluate string must still move"


def test_python_prose_survives_the_bracket_pass(tmp_path: Path) -> None:
    """Order is load-bearing, and getting it wrong DESTROYED the prose.

    The bracket pass rewrites the text through `re.sub`, while the spans were
    measured on the original source. Holding prose after it sliced at stale
    offsets and cut the sentences out of the file entirely. A selector and a
    guillemets quote in the same file is the shape that exposed it.
    """
    source = tree(
        tmp_path,
        "ordered.py",
        '# Une remarque avec « Récupérer maintenant » dedans.\nSEL = "[data-go=suivi]"\nDRIVE = "()=>window.suivi()"\n',
    )

    result = run(tmp_path, {"suivi": "follow"})

    assert result.returncode == 0, result.stderr
    body = source.read_text(encoding="utf-8")
    assert chr(0) not in body, "a placeholder was left in the file"
    assert "« Récupérer maintenant »" in body, "prose was cut out by stale offsets"
    assert '"[data-go=suivi]"' in body, "a bracketed selector is data and stays"
    # CONTROL: the evaluate string in the same file must have moved, or a tool
    # that writes nothing would satisfy every assertion above.
    assert '"()=>window.follow()"' in body, "CONTROL: the drive string did not move — dead tool?"


# --- Scopes the walker claimed to cover --------------------------------------


def test_values_mode_reaches_json(tmp_path: Path) -> None:
    """``.css``/``.json``/``.html`` were a guaranteed no-op reported as success.

    The whole file was handed over as ONE string span, which then failed the id
    test on its first brace — so the three file types the mode was extended to
    cover could never be modified, and the tool said nothing.
    """
    source = tree(tmp_path, "regions.json", '{\n  "state": "en_attente"\n}\n')

    result = run(tmp_path, {"en_attente": "pending"}, "--values")

    assert result.returncode == 0, result.stderr
    assert '"pending"' in source.read_text(encoding="utf-8")


def test_values_mode_leaves_json_prose_alone(tmp_path: Path) -> None:
    """Reaching JSON must not mean rewriting the sentences inside it."""
    source = tree(
        tmp_path,
        "notes.json",
        '{\n  "note": "le profil est absent",\n  "state": "profil"\n}\n',
    )

    result = run(tmp_path, {"profil": "profile"}, "--values")

    assert result.returncode == 0, result.stderr
    body = source.read_text(encoding="utf-8")
    assert "le profil est absent" in body, "the sentence was rewritten"
    assert '"profile"' in body, "CONTROL: the bare value did not move — dead tool?"


@needs_typescript
def test_symlink_is_not_followed_out_of_the_root(tmp_path: Path) -> None:
    """Following one rewrote a file OUTSIDE the tree the caller named."""
    outside = tmp_path / "outside.js"
    outside.write_text("const suivi = 42;\n", encoding="utf-8")
    root = tmp_path / "tree"
    root.mkdir(exist_ok=True)
    (root / "inside.js").symlink_to(outside)

    control = tree(tmp_path, "inside_real.js", "const suivi = 1;\n")

    result = run(tmp_path, {"suivi": "follow"})

    assert result.returncode == 0, result.stderr
    assert outside.read_text(encoding="utf-8") == "const suivi = 42;\n"
    assert "follow" in control.read_text(encoding="utf-8"), "CONTROL: a real file in the root did not move — dead tool?"


@needs_typescript
def test_translations_are_unreachable_even_from_inside_them(tmp_path: Path) -> None:
    """The i18n guard read the root as SPELLED, so ``--root=.`` walked past it."""
    root = tmp_path / "tree" / "i18n"
    root.mkdir(parents=True, exist_ok=True)
    source = root / "fr.js"
    source.write_text('export const fr = {a: "en_attente"};\n', encoding="utf-8")
    # A POSITIVE CONTROL, OUTSIDE `i18n/` — a control inside it would be
    # excluded too, which is exactly the behaviour under test. This test
    # asserts a file was NOT touched, and a tool writing nothing satisfies that
    # perfectly, so the control is what tells the two apart.
    control = tmp_path / "tree" / "sibling.js"
    control.write_text('const s = "en_attente";\n', encoding="utf-8")

    table = tmp_path / "map.json"
    table.write_text(json.dumps({"en_attente": "pending"}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(table), "--root=.", "--values"],
        capture_output=True,
        text=True,
        check=False,
        cwd=root,
    )

    assert result.returncode == 0, result.stderr
    assert '"en_attente"' in source.read_text(encoding="utf-8")

    # Second run, from the PARENT: the tool reaches the control and still
    # refuses the translations.
    second = subprocess.run(
        [sys.executable, str(SCRIPT), str(table), "--root=.", "--values"],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path / "tree",
    )

    assert second.returncode == 0, second.stderr
    assert '"en_attente"' in source.read_text(encoding="utf-8"), "i18n was reached"
    assert '"pending"' in control.read_text(encoding="utf-8"), "CONTROL: a file outside i18n/ did not move — dead tool?"


# --- Shapes that already worked, held so they keep working -------------------


@needs_typescript
def test_identifiers_move_but_strings_do_not(tmp_path: Path) -> None:
    """The tool's founding boundary rule."""
    source = tree(
        tmp_path,
        "shell.ts",
        'const suivi = 1;\nconst label = "un suivi lisible";\n',
    )

    result = run(tmp_path, {"suivi": "follow"})

    assert result.returncode == 0, result.stderr
    body = source.read_text(encoding="utf-8")
    assert "const follow = 1;" in body
    assert '"un suivi lisible"' in body


@needs_typescript
def test_a_value_past_an_emoji_still_moves(tmp_path: Path) -> None:
    """UTF-16 units versus code points, exercised where the drift actually bites.

    The test that used to carry this ground renamed an IDENTIFIER after an
    emoji and could not fail: the emoji sits inside a string span, and the code
    span after it still holds the name whether the offsets drifted or not. It
    certified a fix it never exercised — neutering `utf16_offsets` left it
    green.

    The real symptom was a string literal CUT IN HALF: JavaScript counts an
    emoji as two units and Python as one, so every span past it landed short
    and `"en_attente"` arrived as `"en_` in one chunk and `attente"` in the
    next, matching neither. That needs `--values`, which renames INSIDE string
    literals — which is where the offsets have to be right.

    Neutering `utf16_offsets` turns this red: 1 rename becomes 0.
    """
    source = tree(
        tmp_path,
        "emoji.js",
        'const label = "\U0001f600 \U0001f680 \U0001f4a9 \U0001f44d";\nconst state = "en_attente";\n',
    )

    result = run(tmp_path, {"en_attente": "pending"}, "--values")

    assert result.returncode == 0, result.stderr
    body = source.read_text(encoding="utf-8")
    assert '"pending"' in body, "the value past four emoji was not renamed"
    assert "\U0001f600" in body, "the emoji themselves must be untouched"


@needs_typescript
def test_running_twice_changes_nothing_the_second_time(tmp_path: Path) -> None:
    """Idempotence, held so a re-run is never a second rename."""
    source = tree(tmp_path, "idem.js", "const suivi = 1;\n")

    assert run(tmp_path, {"suivi": "follow"}).returncode == 0
    once = source.read_text(encoding="utf-8")
    # CONTROL: idempotence is trivially true of a tool that never writes. The
    # first run has to have done something for the second to mean anything.
    assert "follow" in once, "CONTROL: the first run renamed nothing — dead tool?"
    assert run(tmp_path, {"suivi": "follow"}).returncode == 0

    assert source.read_text(encoding="utf-8") == once


@needs_typescript
def test_build_outputs_are_never_walked(tmp_path: Path) -> None:
    """A value pass reached a MINIFIED bundle and rewrote it.

    ``personalscraper/web/static/`` is the mirror of ``frontend/dist``. It is
    gitignored, so nothing tracked the damage and ``git checkout`` could not
    undo it: ``unicode-range`` became ``unicode-filed`` and an
    ``<input type="range">`` became ``type="filed"`` in the served bundle.
    ``node_modules`` and ``dist`` had been named one at a time; asking git what
    it ignores covers every generated tree, including the ones not yet created.
    """
    root = tmp_path / "tree"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("tree/built/\n", encoding="utf-8")
    built = root / "built"
    built.mkdir()
    bundle = built / "bundle.js"
    bundle.write_text('const t = "en_attente";\n', encoding="utf-8")
    source = root / "app.js"
    source.write_text('const t = "en_attente";\n', encoding="utf-8")

    result = run(tmp_path, {"en_attente": "pending"}, "--values")

    assert result.returncode == 0, result.stderr
    assert '"pending"' in source.read_text(encoding="utf-8")
    assert '"en_attente"' in bundle.read_text(encoding="utf-8")


@needs_typescript
def test_an_identity_entry_is_accepted(tmp_path: Path) -> None:
    """`{"scrape": "scrape"}` is a no-op, not a chain.

    It is the natural way to write a vocabulary whose members mostly move and
    one deliberately does not — exactly the `stage` table, where `scrape` stays
    because it is already English AND is the name of a pipeline step. The chain
    check refused it, so the caller had to remember to leave the unchanged
    member out. An identity cannot collapse two names onto one, which is the
    whole reason chains are refused.
    """
    source = tree(tmp_path, "stage.js", 'const a = "pris";\nconst b = "scrape";\n')

    result = run(tmp_path, {"pris": "taken", "scrape": "scrape"}, "--values")

    assert result.returncode == 0, result.stderr
    body = source.read_text(encoding="utf-8")
    assert '"taken"' in body
    assert '"scrape"' in body


@needs_typescript
def test_an_identity_entry_does_not_mask_a_real_chain(tmp_path: Path) -> None:
    """Accepting identities must not blunt the check that matters."""
    tree(tmp_path, "chain.js", "const alpha = 1;\n")

    result = run(tmp_path, {"scrape": "scrape", "alpha": "beta", "beta": "gamma"})

    assert result.returncode != 0
    assert "chained" in result.stderr


@needs_typescript
def test_an_apostrophe_in_html_is_text_not_a_quote(tmp_path: Path) -> None:
    """HTML gets double quotes only — an apostrophe there is ordinary text.

    Reading one as an opening quote swallowed everything up to the next
    apostrophe: on `refonte.html` that produced a single 93 000-character
    « string » covering 47% of the file, and the attribute values inside it
    were silently skipped. The mode reported success having changed nothing —
    the no-op-reported-as-success that `quoted_spans` was written to end.

    This interface is written in French, so its markup is full of apostrophes.
    """
    source = tree(
        tmp_path,
        "page.html",
        "<p>L'ajout</p><div data-s=\"en_attente\">C'est</div>\n",
    )

    result = run(tmp_path, {"en_attente": "pending"}, "--values")

    assert result.returncode == 0, result.stderr
    body = source.read_text(encoding="utf-8")
    assert 'data-s="pending"' in body, "the attribute past an apostrophe was skipped"
    assert "L'ajout" in body and "C'est" in body, "the prose was rewritten"


# ─── The custom-property mode ────────────────────────────────────────────
#
# A CSS custom property is not an identifier any parser here sees, and the
# word-boundary rule cannot reach one: `\b` before `--card` needs a word
# character to its left and `-` is not one. Asked to move `--card`, the tool
# renamed ZERO files and said so as « 0 file(s) touched » — a silent no-op
# wearing the shape of success. These hold the mode that closes it, and its
# boundary rule is the FORM rather than the word.


def _run_custom_properties(tmp_path, files, mapping):
    """Runs the tool in custom-property mode over a scratch tree.

    Args:
        tmp_path: The scratch directory.
        files: Relative path → contents.
        mapping: Old property name → new one.

    Returns:
        The tree's contents afterwards, keyed the same way.
    """
    for name, body in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    table = tmp_path / "map.json"
    table.write_text(json.dumps(mapping), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(SCRIPT), str(table), f"--root={tmp_path}", "--custom-properties"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {name: (tmp_path / name).read_text(encoding="utf-8") for name in files}


def test_custom_property_moves_its_declaration_and_its_uses(tmp_path):
    """The two CSS forms move: the declaration, and every `var()` that reads it."""
    after = _run_custom_properties(
        tmp_path,
        {"a.css": ":root { --card: red; }\n.x { background: var(--card); }\n.y { color: var( --card , #fff); }\n"},
        {"--card": "--color-card"},
    )
    assert "--color-card: red" in after["a.css"]
    assert "var(--color-card)" in after["a.css"]
    assert "var( --color-card , #fff)" in after["a.css"]
    assert "--card:" not in after["a.css"]


def test_custom_property_never_matches_a_longer_name(tmp_path):
    """`--card` must not reach inside `--card-x`, which is a different token."""
    after = _run_custom_properties(
        tmp_path,
        {"a.css": ":root { --card: red; --card-x: blue; }\n.x { border-color: var(--card-x); }\n"},
        {"--card": "--color-card"},
    )
    assert "--card-x: blue" in after["a.css"]
    assert "var(--card-x)" in after["a.css"]
    # CONTROL: the two asserts above are satisfied by a mode that moves NOTHING,
    # which is the exact defect this mode was written to close. The rename has
    # to have happened for the boundary to be worth measuring.
    assert "--color-card: red" in after["a.css"], "CONTROL: nothing was renamed at all"


# A `.ts` file in the scratch tree, so the tool reaches for the TypeScript
# parser: this case belongs with the eighteen that say so.
@needs_typescript
def test_custom_property_leaves_prose_alone(tmp_path):
    """A name inside a comment or a sentence is prose, and prose does not move.

    This is the guarantee the identifier mode buys with a parser and this mode
    buys with the form: a property moves only where it is BEING a property.
    """
    after = _run_custom_properties(
        tmp_path,
        {
            "a.css": "/* the --card token is described here */\n:root { --card: red; }\n",
            "b.ts": 'const label = "the --card is red";\n// --card in a comment\n',
        },
        {"--card": "--color-card"},
    )
    assert "/* the --card token is described here */" in after["a.css"]
    assert "--color-card: red" in after["a.css"]
    assert '"the --card is red"' in after["b.ts"]
    assert "// --card in a comment" in after["b.ts"]


# A `.ts` file in the scratch tree, so the tool reaches for the TypeScript
# parser: this case belongs with the eighteen that say so.
@needs_typescript
def test_custom_property_moves_a_whole_quoted_name(tmp_path):
    """`setProperty("--x")` and `getPropertyValue("--x")` are how code reaches one."""
    after = _run_custom_properties(
        tmp_path,
        {"b.ts": "el.style.setProperty(\"--card\", v);\nconst read = s.getPropertyValue('--card');\n"},
        {"--card": "--color-card"},
    )
    assert 'setProperty("--color-card", v)' in after["b.ts"]
    assert "getPropertyValue('--color-card')" in after["b.ts"]


def test_custom_property_does_not_rewrite_its_own_mapping_file(tmp_path):
    """The table's keys are whole quoted strings equal to the names it moves.

    Left unguarded, the tool rewrites the instruction it is executing — and a
    second run of the same command is then a no-op that looks like success.
    """
    files = {"a.css": ":root { --card: red; }\n"}
    _run_custom_properties(tmp_path, files, {"--card": "--color-card"})
    assert json.loads((tmp_path / "map.json").read_text(encoding="utf-8")) == {"--card": "--color-card"}


# --- A no-op is not a result --------------------------------------------------


def test_a_mapping_that_matches_nothing_is_refused(tmp_path):
    """« 0 file(s) touched » was the success line of a tool that could not match.

    A word boundary cannot precede `--`, so every custom-property rename was a
    silent no-op wearing the shape of a result — believed twice before anyone
    read the diff. The mode that closed it did not close this: a typo in a
    source name produces the same line. The subject being absent from the tree
    is now a refusal.
    """
    tree(tmp_path, "a.css", ":root { --card: red; }\n")
    result = run(tmp_path, {"--kard": "--color-card"}, "--custom-properties")

    assert result.returncode == 1, result.stdout + result.stderr
    message = result.stdout + result.stderr
    assert "--kard" in message, "the refusal must name what it looked for"
    assert "1 file(s) read" in message, "and say how much it read before saying so"


def test_a_rename_already_landed_is_not_refused(tmp_path):
    """Idempotence survives the refusal above, and that is the line it walks.

    Re-running a completed rename touches nothing, and the tool is held to
    that being harmless. What separates it from the case above is the TARGET
    name being present: the subject is in the tree, it has simply already
    moved.
    """
    tree(tmp_path, "a.css", ":root { --color-card: red; }\n.x { color: var(--color-card); }\n")
    result = run(tmp_path, {"--card": "--color-card"}, "--custom-properties")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 file(s) touched" in result.stdout


def test_a_corpus_that_was_entirely_excluded_says_so(tmp_path):
    """Reading nothing is reported as reading nothing, not as a clean rename.

    A `--root` pointing at a tree the exclusions swallow whole is the other way
    to touch no file, and it is neither a refusal nor a success — it is a
    measurement of zero, and it says so in its own words.
    """
    root = tmp_path / "tree" / "i18n"
    root.mkdir(parents=True, exist_ok=True)
    (root / "fr.js").write_text('export const fr = {a: "waiting"};\n', encoding="utf-8")
    table = tmp_path / "map.json"
    table.write_text(json.dumps({"waiting": "pending"}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(table), f"--root={root}", "--values"],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 file(s) read" in result.stdout
