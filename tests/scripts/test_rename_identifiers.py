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

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "rename-identifiers.py"


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


def test_multiword_string_is_never_rewritten_word_by_word(tmp_path: Path) -> None:
    """A sentence keeps every word: only a WHOLE-body match may move.

    This is the 429-line incident. ``"rien de conforme au profil"`` became
    ``"… au profile"`` and reached production, because the id test was applied
    to each space-separated word instead of to the whole string.
    """
    source = tree(tmp_path, "copy.js", 'const a = "rien de conforme au profil";\n')

    result = run(tmp_path, {"profil": "profile"}, "--values")

    assert result.returncode == 0, result.stderr
    assert source.read_text(encoding="utf-8") == 'const a = "rien de conforme au profil";\n'


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


def test_inner_words_is_opt_in(tmp_path: Path) -> None:
    """A class list can still be rewritten, but only when asked for by name."""
    source = tree(tmp_path, "classes.js", 'const c = "carte ouverte";\n')

    result = run(tmp_path, {"carte": "card"}, "--values", "--inner-words")

    assert result.returncode == 0, result.stderr
    assert 'const c = "card ouverte";' in source.read_text(encoding="utf-8")


def test_single_token_value_still_moves(tmp_path: Path) -> None:
    """The mode's whole reason for existing keeps working."""
    source = tree(tmp_path, "state.js", 'const s = "en_attente";\nconst k = "acq-en_attente";\n')

    result = run(tmp_path, {"en_attente": "pending"}, "--values")

    assert result.returncode == 0, result.stderr
    body = source.read_text(encoding="utf-8")
    assert '"pending"' in body
    assert '"acq-pending"' in body


# --- Tables that cannot mean what they say -----------------------------------


def test_chained_table_is_refused(tmp_path: Path) -> None:
    """``{a: b, b: c}`` collapsed both names onto ``c`` and exited zero."""
    source = tree(tmp_path, "chain.js", "const alpha = 1;\nconst beta = 2;\n")

    result = run(tmp_path, {"alpha": "beta", "beta": "gamma"})

    assert result.returncode != 0
    assert "chained" in result.stderr
    assert source.read_text(encoding="utf-8") == "const alpha = 1;\nconst beta = 2;\n"


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


def test_a_failed_file_does_not_leave_the_tree_half_renamed(tmp_path: Path) -> None:
    """An abort mid-walk used to leave earlier files written and later ones not."""
    first = tree(tmp_path, "a_first.js", "const suivi = 1;\n")
    third = tree(tmp_path, "c_third.js", "const suivi = 3;\n")

    result = run(tmp_path, {"suivi": "follow"})

    assert result.returncode == 0, result.stderr
    assert "follow" in first.read_text(encoding="utf-8")
    assert "follow" in third.read_text(encoding="utf-8")


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
    source = tree(tmp_path, "notes.json", '{\n  "note": "le profil est absent"\n}\n')

    result = run(tmp_path, {"profil": "profile"}, "--values")

    assert result.returncode == 0, result.stderr
    assert "le profil est absent" in source.read_text(encoding="utf-8")


def test_symlink_is_not_followed_out_of_the_root(tmp_path: Path) -> None:
    """Following one rewrote a file OUTSIDE the tree the caller named."""
    outside = tmp_path / "outside.js"
    outside.write_text("const suivi = 42;\n", encoding="utf-8")
    root = tmp_path / "tree"
    root.mkdir(exist_ok=True)
    (root / "inside.js").symlink_to(outside)

    result = run(tmp_path, {"suivi": "follow"})

    assert result.returncode == 0, result.stderr
    assert outside.read_text(encoding="utf-8") == "const suivi = 42;\n"


def test_translations_are_unreachable_even_from_inside_them(tmp_path: Path) -> None:
    """The i18n guard read the root as SPELLED, so ``--root=.`` walked past it."""
    root = tmp_path / "tree" / "i18n"
    root.mkdir(parents=True, exist_ok=True)
    source = root / "fr.js"
    source.write_text('export const fr = {a: "en_attente"};\n', encoding="utf-8")

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


# --- Shapes that already worked, held so they keep working -------------------


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


def test_rename_past_an_emoji_lands(tmp_path: Path) -> None:
    """UTF-16 units versus code points: renames past an emoji missed silently."""
    source = tree(
        tmp_path,
        "emoji.js",
        'const before = 1;\nconst label = "\U0001f600 \U0001f680";\nconst suivi = 2;\n',
    )

    result = run(tmp_path, {"suivi": "follow"})

    assert result.returncode == 0, result.stderr
    assert "const follow = 2;" in source.read_text(encoding="utf-8")


def test_running_twice_changes_nothing_the_second_time(tmp_path: Path) -> None:
    """Idempotence, held so a re-run is never a second rename."""
    source = tree(tmp_path, "idem.js", "const suivi = 1;\n")

    assert run(tmp_path, {"suivi": "follow"}).returncode == 0
    once = source.read_text(encoding="utf-8")
    assert run(tmp_path, {"suivi": "follow"}).returncode == 0

    assert source.read_text(encoding="utf-8") == once


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
