#!/usr/bin/env python3
"""Arm 10 — a declared name built from a word French knows and English does not.

SPLIT OUT OF `check-no-french.py` for the room, and it is the arm that most
deserves its own file: it is the only one whose oracle comes from OUTSIDE this
repository. Every other arm asks a question this codebase answers itself — a
list of French tokens, a vocabulary file, a baseline — and each of those lists
was seeded from the code it judges, so each certifies some part of the status
quo. `aspell` was written by nobody here.

IT FAILS SOFT, AND IT SAYS SO. Where the dictionaries are absent the arm cannot
run, and it prints that it could not rather than reporting nothing: an absence
that reads as cleanliness is the defect every arm in this guard exists against.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nofrench_lexicon import (  # noqa: E402
    DICTIONARY_EXCEPTIONS, FROZEN_IDENTIFIERS, HARNESS, MAQUETTE, ROOT,
    SCRIPTS, SHELL, examined, maquette_servers, read, relative,
    split_identifier,
)
from nofrench_scan import (  # noqa: E402
    TS_DECLARATION, python_declarations,
)

def dictionary_suspects(words: set[str]) -> set[str]:
    """Returns the words French knows and English does not.

    AN ORACLE FROM OUTSIDE THE REPOSITORY. The other arms ask questions whose
    answers this repository writes itself — a 199-word list of French tokens, a
    vocabulary of allowed words — and a list is only ever as good as what
    somebody thought to put in it. `aspell` was not written by anyone here, so
    it does not share this codebase's blind spots.

    IT HAS ITS OWN, AND THEY ARE NAMED HERE RATHER THAN DISCOVERED LATER: a word
    that is French AND English is invisible to it. `corps`, `page`, `route`,
    `image`, `message`, `note`, `cause`, `train`, `pays`, `fin`, `son` are all
    known to English, so this arm cannot see them — `corps` is live in
    `frontend/src` today and no arm catches it. That is what the VOCABULARY arm
    is for, and why this one is added beside it rather than in place of it.

    Args:
        words: The lowercased words the declared names are built from.

    Returns:
        The suspects, exceptions already removed. Empty when aspell is absent.
    """
    if not words:
        return set()
    listed = sorted(words)
    try:
        unknown_english = set(subprocess.run(
            ["aspell", "--lang=en", "list"], input="\n".join(listed),
            capture_output=True, text=True, check=True).stdout.split())
        unknown_french = set(subprocess.run(
            ["aspell", "--lang=fr", "list"], input="\n".join(listed),
            capture_output=True, text=True, check=True).stdout.split())
    except (OSError, subprocess.CalledProcessError):
        # Fail SOFT and SAY SO: a machine without the dictionaries must not
        # report a cleanliness it never measured.
        print("check-no-french: aspell absent — the dictionary arm measured "
              "NOTHING (install aspell, aspell-en, aspell-fr)", file=sys.stderr)
        return set()
    return {w for w in listed
            if w in unknown_english and w not in unknown_french
            and w not in DICTIONARY_EXCEPTIONS}


def declared_names() -> list[tuple[str, str, int]]:
    """Every declared identifier the guard walks, as (path, name, line).

    ONE collection, shared. The identifier arm and the dictionary arm must read
    the same scope or the narrower one silently certifies the wider — which is
    the shape of every hole this file has had.

    Returns:
        (relative path, declared name, 1-based line) for each declaration.
    """
    out: list[tuple[str, str, int]] = []
    python = (maquette_servers()
              + sorted(HARNESS.glob("*.py"))
              + [p for p in sorted(SCRIPTS.rglob("*.py"))
                 if p.name != Path(__file__).name]
              + sorted((ROOT / "frontend" / "scripts").glob("*.py"))
              + sorted((ROOT / "personalscraper").rglob("*.py"))
              + sorted((ROOT / "tests").rglob("*.py")))
    for path in python:
        for name, line_no in python_declarations(read(path)):
            out.append((relative(path), name, line_no))
    web = [p for p in SHELL.rglob("*") if p.is_file() and p.suffix in {".ts", ".tsx"}]
    web += sorted(HARNESS.glob("*.mjs"))
    web += [p for p in (ROOT / "frontend" / "src").rglob("*")
            if p.is_file() and p.suffix in {".ts", ".tsx"}]
    for path in sorted(web):
        if "i18n" in path.parts:
            continue
        source = read(path)
        for match in TS_DECLARATION.finditer(source):
            out.append((relative(path), match.group("name"),
                        source.count("\n", 0, match.start()) + 1))
    return out


def check_dictionary(violations: list[str]) -> None:
    """Refuses a declared name built from a word French knows and English does not.

    Args:
        violations: The accumulator every arm appends to.
    """
    owners: dict[str, list[str]] = {}
    for path, name, line_no in declared_names():
        for word in split_identifier(name):
            if len(word) > 2 and word.isalpha():
                owners.setdefault(word.lower(), []).append(f"{path}:{line_no}: {name!r}")
    examined["name words / dictionary"] += len(owners)
    for word in sorted(dictionary_suspects(set(owners))):
        where = owners[word][0]
        violations.append(
            f"{where} is built from {word!r}, which French knows and English "
            f"does not — name it in English, or add it to DICTIONARY_EXCEPTIONS "
            f"in {relative(Path(__file__))} with the reason it is not French here")
