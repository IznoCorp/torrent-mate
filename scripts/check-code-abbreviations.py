#!/usr/bin/env python3
"""Refuses a declared name built from a mutilated word, and freezes the debt.

THE RULE is `docs/reference/code-naming.md`: a name is written out in full.
`configuration`, not `cfg`. `message`, not `msg`. The objective is reading — a
name is read far more often than it is typed, and a mutilated word costs its
reader a translation every time.

WHY THIS FILE EXISTS AT ALL. The rule was written on 2026-08-25 with a banner
saying it was not armed, because this repository has already learned, with
French, that A NAMING RULE WITHOUT AN ARM IS A SENTENCE IN A FILE: `data-*`
names were brought under the English rule and four of them simply stayed.

ARM `names` — a declared name carrying a refused word.

WHAT IS READ. Every `.py` file under `personalscraper/`, `scripts/` and
`frontend/maquette/`, parsed rather than grepped, and every DECLARED name in
it: classes, functions, methods, parameters, locals, comprehension targets,
`except … as`, `with … as`, and import aliases. Locals are in scope on purpose
— public names alone were measured at 93 occurrences with a debt that had not
moved in a month, so a guard restricted to them would have been green from day
one and would have changed nothing about what a reader actually reads, which is
function bodies.

WHAT IS NOT READ, and each is a decision:

  `tests/` — 12 774 occurrences, a separate decision that has not been taken.
  TYPESCRIPT — `check-no-french.py`'s vocabulary arm (arm 6) already refuses a
      name built from a word absent from `scripts/code-vocabulary.txt`. Two
      guards over one corpus is two things to keep in step.
  A WORD OF ONE LETTER — `i`, `j`, `n`, `x` are SHORT names, not mutilated
      ones, and that distinction is the whole of the exemption Clean Code
      grants a brief scope: it licenses a name that is brief, never a word with
      its middle removed. 57 % of this debt sits in scopes of five lines or
      fewer, which is why the line is drawn at mutilation and not at length.
  A NAME IMPORTED FROM A LIBRARY — this reads DECLARATIONS. A third-party
      spelling is that library's, and the guard has nothing to say about it.

ARM `baseline` — the ratchet, PER FILE and never a global count.

`scripts/code-abbreviations-baseline.json` records the count each file carries
today. It may go down. It may not go up. A file that reaches zero must leave
the list, so the record cannot quietly describe a tree that has moved.

PER FILE, and the reason is a hole the global form leaves open: a pull request
that removes one `tmp` and adds another leaves a global total unchanged and
passes. The per-file form costs a few hundred entries and closes it.

REFUSED, NOT PRINTED. `check_app_interface_text` drifted by 7 inside the very
pull request that introduced it as a control, because a number nobody compares
is a number nobody reads.

ARM `lists` — the two word files are well formed.

Every refused word names the word it mutilates; every allowed word names the
reason it stays; no word sits in both files; no word is listed twice. A refusal
that cannot say what the name SHOULD be is a refusal nobody can act on, and an
exemption nobody had to justify is indistinguishable from an oversight.

Exit code: 0 when every arm run is clean, 1 otherwise.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ("personalscraper", "scripts", "frontend/maquette")
REFUSED_FILE = ROOT / "scripts" / "code-abbreviations.txt"
ALLOWED_FILE = ROOT / "scripts" / "code-abbreviations-allowed.txt"
BASELINE_FILE = ROOT / "scripts" / "code-abbreviations-baseline.json"

# A directory that holds no source of ours.
SKIPPED = {"node_modules", "__pycache__", ".venv", "dist", "__screenshots__"}

# `word = the rest of the line`. The right-hand side is prose and may hold
# anything, including the `=` of an example.
ENTRY = re.compile(r"^([A-Za-z][A-Za-z0-9]*)\s*=\s*(.*)$")

# A name is cut on its separators, then each chunk on its case boundaries.
# `HTTPTransport` yields `http` and `transport`, not `h`, `t`, `t`, `p`.
SEPARATORS = re.compile(r"[^A-Za-z0-9]+")
CASE_RUN = re.compile(r"[A-Z]+(?![a-z])|[A-Z][a-z]*|[a-z]+|\d+")


def read_word_file(path: Path) -> tuple[dict[str, str], list[str]]:
    """Read one of the two word lists.

    Args:
        path: The file to read.

    Returns:
        A (words, complaints) pair. `words` maps each word to the text after
        its `=`; `complaints` names every line that could not be read, or that
        carried a word with nothing said about it.
    """
    words: dict[str, str] = {}
    complaints: list[str] = []
    if not path.is_file():
        # `relative_to` would raise for a path outside the tree, which a test
        # legitimately hands it; the name is enough to act on either way.
        return words, [f"{path.name} is missing — the arm has no list to read"]
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entry = ENTRY.match(stripped)
        if entry is None:
            complaints.append(f"{path.name}:{number} — « {stripped} » is not `word = reason`")
            continue
        word, reason = entry.group(1).lower(), entry.group(2).strip()
        if not reason:
            complaints.append(
                f"{path.name}:{number} — « {word} » says nothing; a line with no reason is "
                f"itself a violation")
            continue
        if word in words:
            complaints.append(f"{path.name}:{number} — « {word} » is listed twice")
            continue
        words[word] = reason
    return words, complaints


def words_of(name: str) -> list[str]:
    """Cut a declared name into the words it is built from.

    Args:
        name: An identifier as written.

    Returns:
        Its words, lowercased, in order.
    """
    found: list[str] = []
    for chunk in SEPARATORS.split(name):
        found.extend(run.lower() for run in CASE_RUN.findall(chunk))
    return found


def declared_names(tree: ast.AST):
    """Yield every name a module DECLARES, with the line it is declared on.

    Args:
        tree: A parsed module.

    Yields:
        `(name, line)` pairs.
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node.lineno
        elif isinstance(node, ast.arg):
            yield node.arg, node.lineno
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            yield node.id, node.lineno
        elif isinstance(node, ast.ExceptHandler) and node.name:
            yield node.name, node.lineno
        elif isinstance(node, ast.alias):
            # `import x.y as z` declares `z`; `import x.y` declares `x`.
            yield node.asname or node.name.split(".")[0], getattr(node, "lineno", 0)


def sources() -> list[Path]:
    """Collect the corpus, sorted for a stable report."""
    found: list[Path] = []
    for entry in CORPUS:
        base = ROOT / entry
        if not base.is_dir():
            continue
        found.extend(path for path in base.rglob("*.py") if not SKIPPED & set(path.parts))
    return sorted(found)


def scan(refused: dict[str, str]) -> tuple[dict[str, list[str]], int, int]:
    """Find every declared name built from a refused word.

    Args:
        refused: The blacklist, word to the word it mutilates.

    Returns:
        A `(findings, files_read, names_read)` triple. `findings` maps a
        repository-relative path to its findings, one line each.
    """
    findings: dict[str, list[str]] = {}
    files_read = names_read = 0
    for path in sources():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as broken:
            findings.setdefault(path.relative_to(ROOT).as_posix(), []).append(
                f"cannot be parsed ({broken.msg}), so this file is not measured")
            continue
        files_read += 1
        for name, line in declared_names(tree):
            names_read += 1
            for word in words_of(name):
                if len(word) < 2 or word not in refused:
                    continue
                findings.setdefault(path.relative_to(ROOT).as_posix(), []).append(
                    f"{line}: `{name}` — « {word} » is `{refused[word]}` with its middle removed")
    return findings, files_read, names_read


def arm_lists(refused: dict[str, str], allowed: dict[str, str],
              complaints: list[str]) -> int:
    """Refuse a malformed word file, and a word claimed by both of them.

    Args:
        refused: The blacklist.
        allowed: The kept words.
        complaints: What reading the two files already found.

    Returns:
        The number of violations.
    """
    both = sorted(set(refused) & set(allowed))
    for word in both:
        complaints.append(
            f"« {word} » is refused AND kept — one file would quietly win, and which one "
            f"depends on the order they happen to be read in")
    print(f"  lists: {len(refused)} refused word(s), {len(allowed)} kept, "
          f"{len(complaints)} complaint(s)")
    for entry in complaints:
        print("    " + entry, file=sys.stderr)
    return len(complaints)


def arm_names(refused: dict[str, str], listing: bool) -> int:
    """Report the debt, or regenerate the baseline.

    Args:
        refused: The blacklist.
        listing: When true, print the baseline as it would be regenerated and
            refuse nothing — the record is derived, never typed out.

    Returns:
        The number of files whose count is above the baseline.
    """
    findings, files_read, names_read = scan(refused)
    counts = {path: len(entries) for path, entries in findings.items()}
    if listing:
        print(json.dumps({
            "what": (
                "Occurrences of a refused word in a DECLARED name, per file. The rule is "
                "`docs/reference/code-naming.md`; the guard is "
                "`scripts/check-code-abbreviations.py`. A count may go DOWN and never up, and "
                "a file that reaches zero leaves this record. Per file and never a global "
                "total: a change that removes one `tmp` and adds another leaves a total "
                "unchanged and passes."
            ),
            "total": sum(counts.values()),
            "files": dict(sorted(counts.items())),
        }, indent=2, ensure_ascii=False))
        return 0

    if not BASELINE_FILE.is_file():
        print(f"check-code-abbreviations: {BASELINE_FILE.relative_to(ROOT)} is missing — "
              f"regenerate it with --list-baseline", file=sys.stderr)
        return 1
    recorded = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))["files"]

    # A FLOOR. A corpus that read to nothing would report « no file over its
    # baseline » and mean « I measured nothing », which is the reading this
    # repository keeps paying for from the other end.
    if files_read == 0 or names_read == 0:
        print(f"check-code-abbreviations: {files_read} file(s) and {names_read} declared "
              f"name(s) read — the corpus is empty, so « nothing grew » is a sentence about "
              f"nothing", file=sys.stderr)
        return 1

    over = sorted(path for path, count in counts.items() if count > recorded.get(path, 0))
    stale = sorted(path for path, count in recorded.items() if counts.get(path, 0) == 0)
    total = sum(counts.values())
    frozen = sum(recorded.values())
    print(f"  names: {total} occurrence(s) in {len(counts)} file(s), against {frozen} frozen "
          f"in {len(recorded)} — read {names_read} declared name(s) over {files_read} file(s)")
    for path in over:
        was = recorded.get(path, 0)
        print(f"    {path}: {counts[path]} occurrence(s), {was} recorded", file=sys.stderr)
        for entry in findings[path][:6]:
            print(f"      {entry}", file=sys.stderr)
        if len(findings[path]) > 6:
            print(f"      … and {len(findings[path]) - 6} more", file=sys.stderr)
    for path in stale:
        print(f"    {path}: recorded as carrying {recorded[path]} and now carries none — "
              f"a file that reaches zero leaves the record", file=sys.stderr)
    return len(over) + len(stale)


def main() -> int:
    """Run the arms over the three roots."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("lists", "names"),
                        help="run one arm instead of both")
    parser.add_argument("--list-baseline", action="store_true",
                        help="print the per-file record as it would be regenerated")
    arguments = parser.parse_args()

    refused, refused_complaints = read_word_file(REFUSED_FILE)
    allowed, allowed_complaints = read_word_file(ALLOWED_FILE)
    complaints = refused_complaints + allowed_complaints

    if arguments.list_baseline:
        return arm_names(refused, listing=True)

    print("check-code-abbreviations: " + ", ".join(CORPUS))
    violations = 0
    if arguments.arm in (None, "lists"):
        violations += arm_lists(refused, allowed, complaints)
    if arguments.arm in (None, "names"):
        violations += arm_names(refused, listing=False)
    if violations:
        print(f"check-code-abbreviations: {violations} violation(s)", file=sys.stderr)
        return 1
    print("check-code-abbreviations: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
