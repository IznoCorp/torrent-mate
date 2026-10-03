#!/usr/bin/env python3
"""The two arms that COUNT the backend's user texts (arms 14 and 15).

The operator's rule (2026-10-04): the code and its comments are English, and the
texts a user reads — messages, notifications, CLI — are carried by a fr/en
translation layer (`personalscraper.i18n`). `personalscraper/` held about six
hundred such texts written straight into the code the day this arm was added, so
neither can be REFUSED in one day. Both are COUNTING RATCHETS in the manner of
`check_test_prose`: the figure is published every run, may go down, and is
refused going up. Baselines live in `scripts/french-exemption-baseline.json`.

* **Backend French** (`backend_french_literals`) — a string literal under
  `personalscraper/`, docstrings included, that the guard's own detector calls
  French and no `# french-ok: <reason>` pragma licenses. A pragma with no reason
  licenses nothing, so the literal stays counted.
* **Backend text sinks** (`backend_text_sinks`) — a place that shows text to a
  user: CLI output, a `help=` / `short_help=` / `prompt=` keyword, a command's
  docstring help. English inline text is invisible to the first count, so this
  is the one that makes « every user text goes through the layer » measurable.
  A sink whose text comes from a `t(...)` / `t_code(...)` call is not counted.

The measuring functions take the repository root so a fixture tree can be
measured; the arms in `check-no-french.py` pass the real one.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nofrench_lexicon import (  # noqa: E402
    ROOT, examined, exempted, offending_string, read, walk,
)
from nofrench_scan import pragma_on, python_string_literals  # noqa: E402

BASELINE = ROOT / "scripts" / "french-exemption-baseline.json"

# The callee names that show text to a user. A call counts by the LAST segment
# of its dotted name (`self.console.print`, `typer.echo`, bare `echo` after a
# `from typer import echo`), so an alias or a nesting does not hide a sink.
OUTPUT_ATTRS = {"echo", "secho", "print", "log", "rule", "prompt", "confirm"}
# `print`/`log` are only user sinks on a console: bare `print` and `logger.log`
# are developer output (OPEN-4: logs are not user text).
CONSOLE_ONLY = {"print", "log", "rule"}
BARE_OUTPUT = {"echo", "secho", "prompt", "confirm"}
# The keywords that carry a command's or an option's help text.
TEXT_KEYWORDS = {"help", "short_help", "prompt"}
# The translation lookups: a subtree headed by one of these is already carried.
TRANSLATION_CALLS = {"t", "t_code"}
COMMAND_DECORATORS = {"command", "callback"}


def _dotted(node: ast.expr) -> list[str]:
    """Returns a callee's dotted name as its segments, empty when not a name.

    A subscript with a `str` constant key contributes that key as a segment, so
    `state["console"].print` reads as `state.console.print`.

    Args:
        node: The callee expression of a call or a decorator.

    Returns:
        The segments from the root name to the last attribute, or `[]`.
    """
    parts: list[str] = []
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        if isinstance(node, ast.Attribute):
            parts.append(node.attr)
        elif isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            parts.append(node.slice.value)
        else:
            return []
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return parts[::-1]
    return []


def _is_translation(node: ast.AST) -> bool:
    """Whether a node is a `t(...)` / `t_code(...)` call.

    Args:
        node: Any AST node.

    Returns:
        True when the node calls one of `TRANSLATION_CALLS`.
    """
    if not isinstance(node, ast.Call):
        return False
    name = _dotted(node.func)
    return bool(name) and name[-1] in TRANSLATION_CALLS


def _carries_text(node: ast.AST) -> bool:
    """Whether a subtree holds literal user text, translation calls aside.

    Text is an f-string, or a `str` constant holding a space (a one-word constant
    is a key, a style or a unit, not a sentence).

    Args:
        node: The root of the subtree to inspect.

    Returns:
        True when untranslated literal text is found in the subtree.
    """
    if _is_translation(node):
        return False
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return " " in node.value.strip()
    return any(_carries_text(child) for child in ast.iter_child_nodes(node))


def _is_output_call(call: ast.Call) -> bool:
    """Whether a call writes to the user: typer output, a console, a prompt.

    Args:
        call: The call node to classify.

    Returns:
        True when the callee is a user-facing output sink.
    """
    name = _dotted(call.func)
    if not name:
        return False
    last = name[-1]
    if len(name) == 1:
        return last in BARE_OUTPUT
    if last in CONSOLE_ONLY:
        return "console" in name[-2].lower()
    return last in OUTPUT_ATTRS


def _is_command(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether a function is decorated `*.command` / `*.callback`.

    Args:
        function: The function definition to inspect.

    Returns:
        True when one of its decorators is a command or callback.
    """
    for decorator in function.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        name = _dotted(target)
        if name and name[-1] in COMMAND_DECORATORS:
            return True
    return False


def _has_help_keyword(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether a command's decorator already gives `help=` (the docstring stays).

    Args:
        function: The command's function definition.

    Returns:
        True when a decorator call passes `help=` or `short_help=`.
    """
    return any(isinstance(decorator, ast.Call)
               and any(keyword.arg in {"help", "short_help"} for keyword in decorator.keywords)
               for decorator in function.decorator_list)


def backend_french_literals(root: Path) -> list[tuple[Path, int]]:
    """Returns the French string literals `personalscraper/` carries, unlicensed.

    Uses the guard's own scanner and detector, so the count is what an arm
    refusing French would see. A `# french-ok: <reason>` pragma licenses its
    line; a pragma citing nothing licenses nothing.

    Args:
        root: The repository root.

    Returns:
        One (file, line) per counted literal, docstrings included.
    """
    found: list[tuple[Path, int]] = []
    for path in sorted(walk(root / "personalscraper", "*.py")):
        source = read(path)
        lines = source.splitlines()
        literals = python_string_literals(source)
        examined["string literals / backend"] += len(literals)
        for line_no, body in literals:
            if offending_string(body) and not pragma_on(lines, line_no):
                found.append((path, line_no))
    return found


def backend_text_sinks(root: Path) -> list[tuple[Path, int, str]]:
    """Returns the places `personalscraper/` shows literal text to a user.

    Args:
        root: The repository root.

    Returns:
        One (file, line, kind) per counted sink; kind is `output` (echo, console
        print/log/rule, prompt, confirm), `keyword` (`help=`, `short_help=`,
        `prompt=`) or `docstring` (a command's docstring serving as its help).
        A sink whose text is a `t(...)` / `t_code(...)` call is not counted.
    """
    found: list[tuple[Path, int, str]] = []
    for path in sorted(walk(root / "personalscraper", "*.py")):
        try:
            tree = ast.parse(read(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                examined["sink candidates / backend"] += 1
                if _is_output_call(node):
                    arguments = [*node.args, *(k.value for k in node.keywords)]
                    if any(_carries_text(argument) for argument in arguments):
                        found.append((path, node.lineno, "output"))
                for keyword in node.keywords:
                    if keyword.arg in TEXT_KEYWORDS and _carries_text(keyword.value):
                        found.append((path, keyword.value.lineno, "keyword"))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _is_command(node) and not _has_help_keyword(node) and ast.get_docstring(node):
                    found.append((path, node.body[0].lineno, "docstring"))
    return sorted(found, key=lambda site: (str(site[0]), site[1], site[2]))


def _shown(path: Path) -> str:
    """Returns a path relative to the repository when it is under it.

    Args:
        path: The path to display.

    Returns:
        The POSIX path relative to `ROOT`, or the path as is when outside it.
    """
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _ratchet(violations: list[str], key: str, count: int, what: str, remedy: str,
             baseline_path: Path) -> None:
    """Holds a count to its baseline: published always, refused only when it grows.

    Args:
        violations: The accumulator every arm appends to.
        key: The baseline's key in the JSON file.
        count: The measured figure.
        what: The ledger label.
        remedy: What to do instead of growing the count.
        baseline_path: The baseline file.
    """
    exempted[what] = count
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))[key]
    except (OSError, ValueError, KeyError):
        violations.append(
            f"{_shown(baseline_path)} has no `{key}` baseline — the scope would "
            "be read and counted, and still free to grow")
        return
    if count > baseline:
        violations.append(
            f"{what} GREW: {count} against a baseline of {baseline}. {remedy} "
            f"Or lower the baseline in {_shown(baseline_path)} deliberately.")


def check_backend_french(violations: list[str], root: Path = ROOT,
                         baseline_path: Path = BASELINE) -> None:
    """Counts the French literals in `personalscraper/` and refuses them growing.

    Args:
        violations: The accumulator every arm appends to.
        root: The repository root (a fixture tree in tests).
        baseline_path: The ratchet file.
    """
    _ratchet(violations, "backend", len(backend_french_literals(root)),
             "french strings / backend",
             "Code is English and user text lives in the translation layer "
             "(`personalscraper.i18n`); a literal that must stay French carries "
             "`# french-ok: <reason>`.", baseline_path)


def check_backend_sinks(violations: list[str], root: Path = ROOT,
                        baseline_path: Path = BASELINE) -> None:
    """Counts the user-text sinks not fed by `t()` and refuses them growing.

    Args:
        violations: The accumulator every arm appends to.
        root: The repository root (a fixture tree in tests).
        baseline_path: The ratchet file.
    """
    _ratchet(violations, "backend_sinks", len(backend_text_sinks(root)),
             "text sinks not through t() / backend",
             "Route the text through `t(...)` / `t_code(...)`.", baseline_path)
