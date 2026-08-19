#!/usr/bin/env python3
"""Forbid French in the code, and forbid interface text from living in the code.

The operator's rule (2026-08-16): **the code contains no French** — identifiers,
class names (code AND CSS), file names, tool messages — **and no interface string
lives in the code**: the French a reader of the interface sees lives in the i18n
resources. This script is the half of the rule that is enforced rather than
remembered; it runs in `make check` and in CI.

Four arms, each with its own scope, because "French" means a different thing in a
component than it does in a rule script that ASSERTS the French the app renders:

1. **Strings** — over the shell's own sources (`design/src`, minus `src/i18n`), the
   two servers and the harness's `.mjs` tools: a string literal carrying an
   accent, or two French function words, is interface text left in the code. Over
   the harness's RULE SCRIPTS, only the hold LABELS are read (`check("…")`,
   `Journal("…")`) — those are the tool's own messages. The French a hold COMPARES
   is the app's rendered output and must stay French; no arm may ask it to change.
2. **Identifiers** — declared names (Python read through `ast`, TypeScript through
   its declaration keywords) over the same sources, the harness, `scripts/`,
   `personalscraper/` and `tests/` — the whole repository, in other words. A name
   that NAMES a frozen thing (`MAQUETTE`) inherits that thing's reason, and two
   tokens are read differently depending on where they sit (`TOKENS_BY_SCOPE`).
3. **File names** — every path SEGMENT, tracked or merely present, under
   `frontend/`, `scripts/`, `personalscraper/` and `tests/`. This is the arm that
   keeps the rule alive for files created later, anywhere. `docs/` is NOT read:
   dated records keep the names they were written with, and rewriting a record
   would falsify it.
4. **Class names** — `class X` declarations, and the CSS classes the maquette
   DECLARES (`design/refonte.html`) plus the stylesheet extracted from it
   (`frontend/src/styles/ps/*.css`). A class name is one name shared by four
   worlds, which is why it gets an arm of its own.

Each arm also reports how much it READ, and an arm that read nothing is itself a
violation: a scope that silently empties — a renamed directory, a glob that stops
matching — otherwise announces « no violation » with perfect confidence while
measuring nothing.

Every exception CITES its reason. The CSS-class exceptions are read from
`frontend/maquette/regions.json`'s `$vocabulary` — the maquette's own record, so
there is no second copy of those reasons to drift — and this script refuses to run
if an entry there carries no reason. The other exceptions are the dictionaries
below, each entry a token mapped to why it stays.

A line may also carry an inline pragma for the string arm:

    print("recherches: 3")  # french-ok: the prototype's own data key

The reason after the colon is mandatory: a pragma with nothing after it is itself
a violation, because a permission nobody justified is indistinguishable from an
oversight.
"""

from __future__ import annotations

import ast
import io
import json
import re
import subprocess
import sys
import token as token_kinds
import tokenize
import unicodedata
from pathlib import Path

# The lexicon and the helpers that read it live beside this file: the arms are
# the questions, and those are the words the questions are asked in.
# The guard and its lexicon: the two files whose French is their subject.
SELF = {Path(__file__).name, "nofrench_lexicon.py"}

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nofrench_lexicon import *  # noqa: E402, F403
from nofrench_scan import (  # noqa: E402
    code_only, inside_quotes, python_declarations, python_string_literals,
    script_string_literals,
)
from nofrench_lexicon import (  # noqa: E402
    DEBT_BANNER, DEBT_FILE, DICTIONARY_EXCEPTIONS, EXTRACTED_CSS, FRAGMENT,
    FRENCH_TOKENS, FROZEN_IDENTIFIERS, FROZEN_PATH_SEGMENTS, HARNESS, MAQUETTE,
    REGIONS, ROOT, SCRIPTS, SHELL, VOCABULARY, deaccent, french_tokens_in,
    french_tokens_in_flat, has_accent, read, relative, scope_of,
    split_identifier,
)
# The words this codebase's names are built from — see its own header.
# The line in that file below which the words are French on purpose, and the
# one file allowed to need them.

# ── arm 1: strings ───────────────────────────────────────────────────────────
#
# A string is read as a STRING, never as a span between two quote characters: an
# apostrophe inside a comment (« the panel's own vocabulary ») closes nothing,
# and a scanner that thinks it does reports the comment's prose as a literal.
# Python is read through `tokenize`, which is exact; TypeScript through the small
# scanner below, which tracks comments, strings and templates.

HOLD_LABEL = re.compile(
    r"""(?:\bcheck|\bJournal|\bjournal\.check)\(\s*[frbuFRBU]{0,2}"""
    r"""(?P<q>'''|\"\"\"|'|")"""
    r"""(?P<body>(?:\\.|(?!(?P=q))[^\\])*)(?P=q)""", re.S)

# What the app RENDERS is quoted, in this repository's own convention, inside
# guillemets. A quotation is not a French name in the code — it is the code
# naming what the reader of the interface sees — so it is removed before judging.
QUOTED_UI = re.compile(r"«[^»]*»")

# The text between two tags. Interface copy in JSX carries no quotes at all, so
# a scanner that only reads string literals walks straight past the very thing
# arm 1 exists to find: `<p>Réglages du système</p>` is not a literal.
JSX_TEXT = re.compile(r">([^<>{}]+)<")


def offending_string(body: str, quoting_allowed: bool = False) -> str:
    """Returns why a literal counts as French, or an empty string.

    Args:
        body: The literal, quotes included.
        quoting_allowed: True for a tool message, which may NAME an interface
            surface (« Médiathèque », Système, SIMULÉE) — the English sentence
            says what is being read, and the French word is the thing read. A
            capitalised accented word is such a name; a lowercase one is prose.

    Returns:
        The reason, ready to print, or "" when the literal is not French.
    """
    body = QUOTED_UI.sub(" ", body)
    if quoting_allowed:
        body = " ".join(w for w in re.split(r"(\s+)", body)
                        if not (w[:1].isupper() and has_accent(w)))
    if has_accent(body):
        accents = sorted({c for c in body if has_accent(c)})
        return f"accented characters {accents}"
    found = WORD.findall(body)
    # Lowercase in the SOURCE for the FUNCTION words only: French prose is
    # lowercase, and `LA`/`EST`/`DES` are abbreviations. An interface LABEL is
    # capitalised by nature — « Fermer » — so the label vocabulary reads every
    # case.
    words = {deaccent(word).lower() for word in found}
    lowercase = {deaccent(word).lower() for word in found if word.islower()}
    hits = sorted(lowercase & FRENCH_FUNCTION_WORDS)
    if len(hits) >= 2:
        return f"French function words {hits}"
    # A tool message may NAME the button it presses — « a Retour from the sheet
    # lands on … » — and that name is capitalised. Inside the application's own
    # code there is no such excuse, so there the label vocabulary reads every
    # case.
    labels = sorted((lowercase if quoting_allowed else words) & FRENCH_UI_WORDS)
    if labels:
        return f"French interface words {labels}"
    return ""


def pragma_on(lines: list[str], line_no: int) -> str | None:
    """Returns the reason a line's french-ok pragma cites, or None.

    Args:
        lines: The file's lines.
        line_no: The 1-based line the literal starts on.

    Returns:
        The cited reason, "" when the pragma cites nothing, or None when the
        line carries no pragma. The line ABOVE counts too: a JSX attribute has
        no room for a trailing comment.

        THE LINE BELOW DELIBERATELY DOES NOT. This docstring used to promise it
        — for the wrapped-literal case — and implementing that promise turned
        every pragma into a THREE-line grant: a brand-new French literal parked
        next to any of the twenty-one existing pragmas became invisible. A
        wrapped literal can carry its pragma on the line above like everything
        else; licensing a neighbour is a bigger hole than the one it closed.
    """
    for candidate in (line_no, line_no - 1):
        if not 1 <= candidate <= len(lines):
            continue
        line = lines[candidate - 1]
        found = PRAGMA.search(line)
        # A pragma written INSIDE a string is not a pragma. Without this, one
        # literal reading `"# french-ok: …"` licensed its neighbours.
        if found and not inside_quotes(line, found.start()):
            return found.group("reason").strip()
    return None


def remedy(path: Path) -> str:
    """Returns where this file's French is supposed to go instead.

    Args:
        path: The file the violation was found in.

    Returns:
        The sentence the violation ends with. A `scripts/` tool has no i18n
        bundle to be sent to, and telling its author to put a message in the
        front-end's resource file would be advice nobody can follow.
    """
    if scope_of(path) in {"repository tools", "harness tools", "harness"}:
        return "a developer tool speaks English"
    return "interface text belongs in design/src/i18n/fr.json"


def check_strings(violations: list[str]) -> None:
    """Runs the string arm over the shell, the servers and the hold labels."""
    strict: list[Path] = [p for p in SHELL.rglob("*") if p.is_file()
                          and p.suffix in {".ts", ".tsx"} and "i18n" not in p.parts]
    strict += [MAQUETTE / "serve.py", MAQUETTE / "resync.py"]
    strict += sorted(HARNESS.glob("*.mjs"))
    # The repository's own tools speak to a DEVELOPER, so they speak English.
    # (The `personalscraper` CLI is a different case entirely: it speaks to the
    # OPERATOR, in French, and it is interface — no arm reads it.)
    # This file is the one exception the arm makes for itself: its French IS its
    # subject — the lexicon is a list of French words, and pragmas on a word list
    # would say nothing a reader does not already see.
    # `rglob`: `scripts/ops/` holds nine more tools one level down, and a glob
    # one level deep read none of them. A scope is checked the same way a name
    # is — `scripts/` is not `scripts/ops/`.
    # This file and its lexicon are the two the arm excepts for itself: their
    # French IS their subject — a list of French words cannot be written in
    # English, and pragmas on a word list would say nothing a reader does not
    # already see.
    strict += [p for p in sorted(SCRIPTS.rglob("*.py"))
               if p.name not in SELF]
    for path in sorted(strict):
        source = read(path)
        lines = source.splitlines()
        literals = (python_string_literals(source) if path.suffix == ".py"
                    else script_string_literals(source))
        examined[f"string literals / {scope_of(path)}"] += len(literals)
        for line_no, body in literals:
            reason = offending_string(body)
            if not reason:
                continue
            cited = pragma_on(lines, line_no)
            if cited:
                continue
            if cited == "":
                violations.append(
                    f"{relative(path)}:{line_no}: a french-ok pragma citing no "
                    "reason permits nothing")
                continue
            violations.append(
                f"{relative(path)}:{line_no}: French string literal "
                f"({reason}) — {remedy(path)}: {body[:60]!r}")

        # The text BETWEEN two tags. Interface copy in JSX carries no quotes,
        # so the literal scan above walks straight past the commonest shape of
        # the very thing this arm exists to find.
        if path.suffix == ".tsx":
            for match in JSX_TEXT.finditer(source):
                text = match.group(1)
                if not text.strip():
                    continue
                examined["rendered text / shell"] += 1
                reason = offending_string(text)
                if not reason:
                    continue
                line_no = source.count("\n", 0, match.start()) + 1
                if pragma_on(lines, line_no):
                    continue
                violations.append(
                    f"{relative(path)}:{line_no}: French text rendered from the "
                    f"code ({reason}) — {remedy(path)}: {text.strip()[:60]!r}")

    for path in sorted(HARNESS.glob("*.py")):
        source = read(path)
        lines = source.splitlines()
        for match in HOLD_LABEL.finditer(source):
            examined["hold labels / harness"] += 1
            line_no = source.count("\n", 0, match.start()) + 1
            reason = offending_string(match.group("body"), quoting_allowed=True)
            if not reason:
                continue
            if pragma_on(lines, line_no):
                continue
            violations.append(
                f"{relative(path)}:{line_no}: French hold label ({reason}) — a "
                f"hold's label is the tool's own message: "
                f"{match.group('body')[:60]!r}")


# ── arm 2: identifiers ───────────────────────────────────────────────────────

TS_DECLARATION = re.compile(
    r"\b(?:const|let|var|function|class|interface|type|enum)\s+"
    r"(?P<name>[A-Za-z_$][\w$À-ɏ]*)")


def check_identifiers(violations: list[str]) -> None:
    """Runs the identifier arm over the shell, the servers, the harness, the tools."""
    python = ([MAQUETTE / "serve.py", MAQUETTE / "resync.py"]
              + sorted(HARNESS.glob("*.py"))
              + [p for p in sorted(SCRIPTS.rglob("*.py"))
                 if p.name not in SELF]
              # `frontend/scripts/` is not `scripts/`, and that one letter of
              # scope left an entire tool — 18 French names, `SORTIE`, `JAUNE`,
              # `anneau_depuis_staging` — outside every arm while the gate
              # reported no violation.
              + sorted((ROOT / "frontend" / "scripts").glob("*.py"))
              + sorted((ROOT / "personalscraper").rglob("*.py"))
              + sorted((ROOT / "tests").rglob("*.py")))
    for path in python:
        source = read(path)
        declarations = python_declarations(source)
        examined[f"declared identifiers / {scope_of(path)}"] += len(declarations)
        for name, line_no in declarations:
            if name in FROZEN_IDENTIFIERS:
                continue
            hits = french_tokens_in(name, relative(path))
            if hits or has_accent(name):
                violations.append(
                    f"{relative(path)}:{line_no}: French identifier {name!r} "
                    f"({', '.join(hits) or 'accented'})")

    web = [p for p in SHELL.rglob("*") if p.is_file() and p.suffix in {".ts", ".tsx"}]
    web += sorted(HARNESS.glob("*.mjs"))
    web += [p for p in (ROOT / "frontend" / "src").rglob("*")
            if p.is_file() and p.suffix in {".ts", ".tsx"}]
    for path in sorted(web):
        if "i18n" in path.parts:
            continue
        source = read(path)
        for match in TS_DECLARATION.finditer(source):
            examined[f"declared identifiers / {scope_of(path)}"] += 1
            name = match.group("name")
            if name in FROZEN_IDENTIFIERS:
                continue
            hits = french_tokens_in(name, relative(path))
            if hits or has_accent(name):
                line_no = source.count("\n", 0, match.start()) + 1
                violations.append(
                    f"{relative(path)}:{line_no}: French identifier {name!r} "
                    f"({', '.join(hits) or 'accented'})")


# ── arm 3: file names ────────────────────────────────────────────────────────

# `docs/` is the ONE tree this arm does not walk: dated records keep the names
# they were written with, and rewriting a record would falsify it.
UNWATCHED_ROOTS = ("docs/",)


def tracked_paths() -> list[str]:
    """Returns every path in the repository this arm watches.

    The WHOLE repository, minus `docs/` — four named roots used to be the scope,
    which left `hooks/`, `config.example/`, `.github/` and the root itself
    unwatched while the docstring said « anywhere ».

    Untracked-but-not-ignored files are listed too (`--others
    --exclude-standard`): a file created five minutes ago is exactly the one
    this arm exists to catch, and it is not tracked until it is added — a gate
    that only reads the index says nothing until after the commit it should
    have blocked.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True)
    return sorted({p for p in listed.stdout.split("\0")
                   if p and not p.startswith(UNWATCHED_ROOTS)})


def check_file_names(violations: list[str]) -> None:
    """Runs the file-name arm over every tracked path segment."""
    seen: set[tuple[str, str]] = set()
    for path in tracked_paths():
        for segment in path.split("/"):
            examined["path segments / repository"] += 1
            stem = segment.rsplit(".", 1)[0] if "." in segment else segment
            # Frozen TOKENS, not frozen segments: `maquette` stays wherever it
            # appears — the directory, `extract-maquette-css.py`, the extracted
            # stylesheets — and each of those would otherwise need its own
            # entry, which is how an allowlist grows without anyone deciding.
            hits = [h for h in french_tokens_in(stem, path)
                    if h not in FROZEN_PATH_SEGMENTS]
            if not (hits or has_accent(segment)):
                continue
            key = (segment, ", ".join(hits))
            if key in seen:
                continue
            seen.add(key)
            violations.append(
                f"{path}: French path segment {segment!r} "
                f"({', '.join(hits) or 'accented'})")


# ── arm 4: class names ───────────────────────────────────────────────────────

CSS_SELECTOR = re.compile(r"\.(?P<name>-?[A-Za-z_À-ɏ][\wÀ-ɏ-]*)")


def css_allowlist() -> dict[str, str]:
    """Returns the frozen CSS class names, each mapped to its recorded reason.

    Read from `regions.json`'s `$vocabulary` — the maquette's own record — so the
    reasons have exactly one home. An entry with no reason is itself a
    violation: a permission nobody justified is indistinguishable from an
    oversight.

    Raises:
        ValueError: When the record is missing or an entry carries no reason.
    """
    data = json.loads(REGIONS.read_text(encoding="utf-8"))

    def find(node: object) -> dict | None:
        if isinstance(node, dict):
            if "$vocabulary" in node:
                return node["$vocabulary"]
            for value in node.values():
                got = find(value)
                if got is not None:
                    return got
        return None

    vocabulary = find(data)
    if not isinstance(vocabulary, dict):
        raise ValueError(f"no $vocabulary record in {relative(REGIONS)}")
    allowed: dict[str, str] = {}
    frozen = vocabulary.get("frenchTokensFrozen", {})
    reason = frozen.get("$comment", "").strip()
    if not reason:
        raise ValueError("frenchTokensFrozen carries no reason")
    for token in frozen.get("tokens", []):
        allowed[token] = reason
    for token, why in vocabulary.get("abbreviationsKept", {}).items():
        if token.startswith("$"):
            continue
        if not str(why).strip():
            raise ValueError(f"abbreviationsKept[{token!r}] carries no reason")
        allowed[token] = str(why)
    return allowed


def allowed_class(name: str, allowed: dict[str, str]) -> bool:
    """Returns True when a class name is covered by a cited exception."""
    if name in allowed:
        return True
    return any(key.endswith("*") and name.startswith(key[:-1])
               for key in allowed)


def declared_css_classes(source: str) -> dict[str, int]:
    """Returns the class names a stylesheet DECLARES, with their first line."""
    found: dict[str, int] = {}
    for block in re.finditer(r"(?P<selectors>[^{}]+)\{[^{}]*\}", source):
        selectors = block.group("selectors")
        # A selector list only: anything after an `@media`/`@supports` prelude,
        # or a property line, carries no leading-dot class.
        for match in CSS_SELECTOR.finditer(selectors):
            name = match.group("name")
            line_no = source.count("\n", 0, block.start() + match.start()) + 1
            found.setdefault(name, line_no)
    return found


def check_class_names(violations: list[str]) -> None:
    """Runs the class-name arm over code classes and declared CSS classes."""
    allowed = css_allowlist()

    for path in ([MAQUETTE / "serve.py", MAQUETTE / "resync.py"]
                 + sorted(HARNESS.glob("*.py"))):
        tree = ast.parse(read(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                examined["class names / python"] += 1
                hits = french_tokens_in(node.name, relative(path))
                if hits or has_accent(node.name):
                    violations.append(
                        f"{relative(path)}:{node.lineno}: French class name "
                        f"{node.name!r} ({', '.join(hits) or 'accented'})")

    code_class = re.compile(r"\bclass\s+(?P<name>[A-Za-z_$][\w$À-ɏ]*)")
    typescript = [p for p in SHELL.rglob("*")
                  if p.is_file() and p.suffix in {".ts", ".tsx"}]
    typescript += [p for p in (ROOT / "frontend" / "src").rglob("*")
                   if p.is_file() and p.suffix in {".ts", ".tsx"}]
    for path in sorted(typescript):
        source = read(path)
        for match in code_class.finditer(source):
            examined["class names / typescript"] += 1
            name = match.group("name")
            hits = french_tokens_in(name, relative(path))
            if hits or has_accent(name):
                line_no = source.count("\n", 0, match.start()) + 1
                violations.append(
                    f"{relative(path)}:{line_no}: French class name {name!r} "
                    f"({', '.join(hits) or 'accented'})")

    # `rglob`, and the whole styles tree: `ps/tokens/` holds six real
    # stylesheets and `globals.css` sits beside `ps/`, all of them unread while
    # the arm globbed one directory one level deep.
    # Every stylesheet under `frontend/src`, not only those under `styles/`:
    # four sit beside the component they dress (`ds/LogLine.css`,
    # `ds/StatPanel.css`, `ds/StatusDot.css`, `pipeline/PipelineStepper.css`)
    # and declared 49 class names no arm read.
    sheets = [FRAGMENT] + sorted((ROOT / "frontend" / "src").rglob("*.css"))
    for path in sheets:
        if not path.is_file():
            continue
        source = read(path)
        if path is FRAGMENT:
            # The fragment is one document: only its <style> blocks declare CSS.
            source = "\n".join(
                m.group(1) for m in re.finditer(
                    r"<style[^>]*>(.*?)</style>", source, re.S))
        declared = declared_css_classes(source)
        examined["declared CSS classes / "
                 + ("fragment" if path == FRAGMENT else "extracted")] += len(declared)
        for name, line_no in declared.items():
            if allowed_class(name, allowed):
                continue
            hits = french_tokens_in_flat(name)
            if hits or has_accent(name):
                violations.append(
                    f"{relative(path)}:{line_no}: French CSS class {name!r} "
                    f"({', '.join(hits) or 'accented'}) — a class name is one "
                    "name shared by four worlds")


def vocabulary(debt_only: bool = False) -> set[str]:
    """Returns the words this codebase's names are built from.

    Args:
        debt_only: When true, returns only the words below the debt banner —
            French on purpose, and owed by one file.

    Returns:
        The set of words, lower-cased.
    """
    words, below = set(), False
    for line in VOCABULARY.read_text(encoding="utf-8").splitlines():
        if line.startswith(DEBT_BANNER):
            below = True
        if not line.strip() or line.startswith("#"):
            continue
        # Without the flag this is the WHOLE vocabulary, debt included: the
        # engine's names must still pass the arm that reads them. What the
        # flag isolates is who may BORROW those words, which is one file.
        if not debt_only or below:
            words.add(line.strip().lower())
    return words


def check_french_debt(violations: list[str]) -> None:
    """Refuses a debt word anywhere but the one file that owes it.

    The vocabulary was seeded FROM the codebase, so every French name still
    standing quietly contributed its own word and the arm reading that file
    certified them. Naming the debt is only half of it — the other half is
    that it must not grow: a new name built from `apparence` or `tris`
    outside the dying engine would inherit an exemption nobody granted it.

    Args:
        violations: The accumulator every arm appends to.
    """
    owed = vocabulary(debt_only=True)
    if not owed:
        # Deleting the BANNER alone would fold every French word back into the
        # general vocabulary and silence this arm without removing a thing —
        # the section and the file it exists for go together, or neither does.
        if (ROOT / DEBT_FILE).exists() and DEBT_BANNER not in VOCABULARY.read_text(
                encoding="utf-8"):
            violations.append(
                f"{relative(VOCABULARY)}: the debt banner is gone while "
                f"{DEBT_FILE} is still here — either the words below it moved "
                "back in unmarked, or the section was removed before the file "
                "it was written for")
        return
    examined["french debt words / vocabulary"] += len(owed)
    # The app is read too: a debt word borrowed in `frontend/src` would be no
    # less an exemption nobody granted, and it is not the engine's file.
    # EVERY scope the guard reads, not two frontend trees. The banner claims
    # these words are « needed by exactly ONE file » and that this arm « refuses
    # them anywhere else » — and it read no `.py` at all, so thirteen of the
    # twenty-four passed silently as Python identifiers, and `panne` was live in
    # `harness/machine.py` under a green gate. A bound that covers a quarter of
    # the codebase is not a bound.
    sources = [p for p in SHELL.rglob("*")
               if p.is_file() and p.suffix in {".ts", ".tsx", ".js"}
               and "i18n" not in p.parts and relative(p) != DEBT_FILE]
    sources += [p for p in (ROOT / "frontend" / "src").rglob("*")
                if p.is_file() and p.suffix in {".ts", ".tsx"}]
    sources += [MAQUETTE / "serve.py", MAQUETTE / "resync.py"]
    sources += sorted(HARNESS.glob("*.py"))
    sources += [p for p in sorted(SCRIPTS.rglob("*.py")) if p.name not in SELF]
    sources += sorted((ROOT / "personalscraper").rglob("*.py"))
    sources += sorted((ROOT / "tests").rglob("*.py"))
    for path in sorted(sources):
        raw = read(path)
        lines = raw.splitlines()
        # A JavaScript declaration regex over a `.py` file matches nothing, so
        # merely ADDING Python to the scope changed nothing: `panne` stayed
        # green in `harness/machine.py`. Python is read by Python's own reader.
        if path.suffix == ".py":
            found = [(name, line_no) for name, line_no in python_declarations(raw)]
        else:
            source = code_only(raw)
            found = [(m.group(1), source.count("\n", 0, m.start()) + 1)
                     for m in re.finditer(
                         r"(?:function|const|let|var|class|type|interface)\s+"
                         r"([A-Za-z_$][\w$]*)", source)]
        for name, line_no in found:
            # Same as the vocabulary arm: an empty reason grants nothing.
            if pragma_on(lines, line_no):
                continue
            # A word DECLARED as an English abbreviation is not borrowed
            # French, wherever it appears. `sel` is a selector, `maint`
            # maintenance, `repos` git repositories — each already carries
            # its reason in DICTIONARY_EXCEPTIONS, and one declaration
            # should answer for both arms rather than each keeping a list.
            borrowed = [w for w in split_identifier(name)
                        if w.lower() in owed and w.lower() not in DICTIONARY_EXCEPTIONS]
            if borrowed:
                violations.append(
                    f"{relative(path)}:{line_no}: {name!r} borrows "
                    f"{', '.join(repr(w) for w in borrowed)} from the French "
                    f"words {DEBT_FILE} still owes — that exemption is the "
                    "engine's alone, and it dies with it")


def check_vocabulary(violations: list[str]) -> None:
    """Refuses a declared name built from a word this codebase does not use.

    THE OTHER ARMS ASK « IS THIS FRENCH? », and that question is only ever as
    good as the list of French words behind it. That list had holes — `suivante`,
    `trier`, `fermer`, `afficher`, `chargement`, `compte`, `monde` were all
    invisible to it — so « no violation » quietly meant « none among the words we
    thought of », and a hundred and forty French names sat under it unremarked.

    This arm asks the opposite: « is this word one we use? ». The vocabulary is
    a file in the repository, so it has no holes by construction — a name built
    from a word nobody wrote down is refused, whatever language it came from.

    It reads `.js` as well as `.ts`/`.tsx`, which is what finally puts the
    legacy engine under a guard: its identifiers are English now, so the words
    they are made of are simply in the list.

    Args:
        violations: The accumulator every arm appends to.
    """
    words = vocabulary()
    if not words:
        violations.append(f"{relative(VOCABULARY)} is empty — the arm reading it "
                          "would accept every name ever written")
        return
    sources = [p for p in SHELL.rglob("*")
               if p.is_file() and p.suffix in {".ts", ".tsx", ".js"}
               and "i18n" not in p.parts]
    for path in sorted(sources):
        raw = read(path)
        lines = raw.splitlines()
        # Comments and strings are blanked first: a name extractor that reads
        # prose invents declarations — « the type this module exports » yields
        # `this` — and eighty of those buried the four real findings.
        source = code_only(raw)
        for match in re.finditer(
                r"(?:function|const|let|var|class|type|interface)\s+"
                r"([A-Za-z_$][\w$]*)", source):
            name = match.group(1)
            if name in FROZEN_IDENTIFIERS:
                continue
            line_no = source[: match.start()].count("\n") + 1
            # A pragma citing NOTHING is not a grant (module docstring):
            # `is not None` accepted a bare `french-ok:` and silenced the arm.
            if pragma_on(lines, line_no):
                continue
            examined["name words / shell"] += 1
            unknown = [w for w in split_identifier(name)
                       if len(w) > 1 and w.lower() not in words]
            if unknown:
                violations.append(
                    f"{relative(path)}:{line_no}: {name!r} is built from "
                    f"{', '.join(repr(w) for w in unknown)}, which "
                    f"{'is' if len(unknown) == 1 else 'are'} not in "
                    f"{relative(VOCABULARY)} — rename it in English, or add the "
                    "word there if the codebase really speaks it")


def check_data_attributes(violations: list[str]) -> None:
    """Refuses a `data-*` attribute NAME built from a word this codebase lacks.

    CLAUDE.md brings these names under the rule — a `data-*` name is a name
    someone chose — and until now nothing read them. Nineteen were renamed by
    hand in the same wave that wrote the rule, and four were missed:
    `data-prendre`, `data-maintrub`, `data-qreg` and `data-apparence` stayed,
    green, because no arm looked. A rule with no arm is a sentence in a file.

    The VALUES are not read, and must not be: `data-go="profil"` names a page,
    and a page id is an address.

    It asks the vocabulary's question rather than « is this word French? »,
    because the names here are abbreviations — `rub` for « rubrique » is
    invisible to any list of French words, and `maintopic` is not.

    Args:
        violations: The accumulator every arm appends to.
    """
    words = vocabulary()
    sources = [p for p in SHELL.rglob("*")
               if p.is_file() and p.suffix in {".ts", ".tsx", ".js"}]
    # `design/index.html` is the application shell's markup since SP4-fin wave
    # 2, and it was read by no arm: `id="coquille"` — the React mount point —
    # sat there in French while every gate was green.
    # And `frontend/index.html` beside it: the maquette's twin was added when
    # `id="coquille"` was found in it, and the PRODUCTION app's own shell markup
    # — the one actually served — was left unread by the same arm.
    sources += [FRAGMENT, MAQUETTE / "design" / "index.html",
                ROOT / "frontend" / "index.html"]
    sources += [p for p in (ROOT / "frontend" / "src").rglob("*")
                if p.is_file() and p.suffix in {".ts", ".tsx", ".css"}]
    for path in sorted(sources):
        source = read(path)
        for match in re.finditer(
                r"\bdata-([a-zA-Z][\w-]*)"
                r"|\bid=\"([A-Za-z][\w-]*)\""
                # `id='coquille'` and `id={'coquille'}` name the same element as
                # `id="coquille"`; only the double-quoted spelling was read.
                r"|\bid='([A-Za-z][\w-]*)'"
                r"|\bid=\{\s*['\"]([A-Za-z][\w-]*)['\"]\s*\}", source):
            name = (match.group(1) or match.group(2)
                    or match.group(3) or match.group(4))
            examined["data-* names / markup"] += 1
            line_no = source.count("\n", 0, match.start()) + 1
            unknown = [w for w in split_identifier(name)
                       if len(w) > 1 and w.lower() not in words]
            if unknown:
                violations.append(
                    f"{relative(path)}:{line_no}: the markup name "
                    f"{name!r} is built from "
                    f"{', '.join(repr(w) for w in unknown)}, which "
                    f"{'is' if len(unknown) == 1 else 'are'} not in "
                    f"{relative(VOCABULARY)} — name it in English, or add the "
                    "word there if the codebase really speaks it")


SHELL_BY_NAME = {"Makefile"}


def first_line(path: Path) -> str:
    """The file's first line, or "" when it cannot be read as text."""
    try:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            return handle.readline()
    except OSError:
        return ""


def check_shell_scripts(violations: list[str]) -> None:
    """Refuses French in a `.sh` — every line of one is the tool speaking.

    NO ARM READ `.sh` AT ALL, and three of this repository's nine shell scripts
    were written in French throughout — the two deploy scripts and the poller,
    which between them are the only sanctioned way to put anything in front of
    the operator. The rule has always covered them: a message a tool prints is
    English. Nothing had ever looked.

    A shell script has no i18n bundle and renders nothing to a reader of the
    interface, so the distinction the other arms draw — code here, copy there —
    does not exist in one. Every line is read, comment and message alike.

    Args:
        violations: The accumulator every arm appends to.
    """
    for relative_path in tracked_paths():
        path = ROOT / relative_path
        if not path.is_file():
            continue
        # A SCRIPT IS A SCRIPT WHETHER OR NOT ITS NAME ENDS IN `.sh`. Matching
        # the extension alone left every git hook out — `hooks/pre-commit`,
        # `hooks/pre-push`, `hooks/commit-msg`, `scripts/pre-push` — plus the
        # Makefile and a PM2 `.cjs` declaration, all of which print to the
        # operator and none of which any arm read. Three all-French `.sh` files
        # were once found this way; these are the same class, one naming
        # convention over.
        # `.py` carries a shebang too and is already read, line by line, by the
        # string and identifier arms; pulling it in here would double every
        # finding and trip on the accent RANGES in this file's own regexes.
        if path.suffix == ".py":
            continue
        if not (relative_path.endswith((".sh", ".cjs", ".mjs"))
                or path.name in SHELL_BY_NAME
                or first_line(path).startswith("#!")):
            continue
        lines = read(path).splitlines()
        for line_no, line in enumerate(lines, start=1):
            examined["lines / shell scripts"] += 1
            reason = offending_string(line)
            if not reason:
                continue
            if pragma_on(lines, line_no):
                continue
            violations.append(
                f"{relative_path}:{line_no}: French in a shell script "
                f"({reason}) — a developer tool speaks English: {line.strip()[:60]!r}")


def check_unread_javascript(violations: list[str]) -> None:
    """Refuses a `.js` under the shell that no arm reads, except the engine.

    Every arm above globs `.ts`/`.tsx`, so a JavaScript file under
    `design/src/` is examined by none of them. That is correct for exactly one
    file — the legacy engine, moved there byte for byte, whose French
    identifiers predate the rule and would be rewritten by a conversion, not by
    a rename. It is wrong for anything else: a NEW `.js` would be new code, in
    the one scope where nobody is looking.

    An implicit exclusion is what this file exists to distrust — it reports
    « no violation » about a scope it never opened. So the exclusion is written
    down, and it is a list of one.

    Args:
        violations: The accumulator every arm appends to.
    """
    # Each entry is here because it was MOVED, not written: its French
    # identifiers predate the rule and only a conversion — not a rename — will
    # reach them. `legacy.js` is the engine; `states.js` is the scenario table
    # lifted out of it, whose entries call the engine's own French names.
    allowed = {SHELL / "engine" / "legacy.js", SHELL / "states.js"}
    unread = {path for path in SHELL.rglob("*.js") if path.is_file()}
    for path in sorted(unread - allowed):
        violations.append(
            f"{relative(path)} is JavaScript under the shell, which no arm "
            "reads — write it in TypeScript, or name it here with the reason "
            "it is exempt")
    for path in sorted(allowed - unread):
        violations.append(
            f"{relative(path)} is named as exempt but does not exist — the "
            "exemption outlived its subject")
    examined["unread javascript / shell"] += len(unread)


# Words `aspell` reports as French-and-not-English that are NOT French names
# here. Each is a real word of this codebase's trade, and each is written down
# because an exemption nobody can read is indistinguishable from an oversight.
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
    python = ([MAQUETTE / "serve.py", MAQUETTE / "resync.py"]
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


# JSX text for the EXEMPTION COUNT. Deliberately a distinct name from arm 1's
# `JSX_TEXT` above: defining a second `JSX_TEXT` here shadowed it and quietly
# dropped that arm's coverage from 124 rendered strings to 59.
JSX_TEXT_NODE = re.compile(r">([^<>{}]*[A-Za-zÀ-ÿ][^<>{}]*)<")


def jsx_text(source: str) -> list[str]:
    """Returns the text nodes of a JSX source.

    Interface copy in JSX carries no quotes, so a scanner reading only string
    literals walks past the very thing it is looking for.

    Args:
        source: The `.tsx` source.

    Returns:
        Each text node, whitespace-trimmed, long enough to be a sentence.
    """
    return [body.strip() for body in JSX_TEXT_NODE.findall(source)
            if len(body.strip().split()) >= 3]


def check_app_interface_text(violations: list[str]) -> None:
    """Measures the French interface text `frontend/src` carries, and says so.

    THIS ARM DOES NOT REFUSE. `frontend/src` is the React application the
    maquette shell is being built to replace, and it has no i18n layer at all —
    no `i18n/` directory, no `useTranslation`. Its French is written straight
    into the components. The operator ruled that this is an ACCEPTED state
    rather than a defect: moving that copy into resources would be work thrown
    away with the app that holds it. §Language names two i18n surfaces — the
    maquette shell and `serve.py`'s pages — and this is deliberately neither.

    So why an arm at all? Because the string arm walks the shell, the servers,
    the harness tools and the repository tools, and NOT this tree — and an
    unread scope reports « no violation » about a place it never opened. That
    is how 842 French strings sat under a green gate, and how `id="coquille"`
    and three all-French shell scripts sat under it before them. An exemption
    nobody counts is indistinguishable from an oversight.

    The count is therefore published in the ledger beside every other scope. It
    reads the whole tree, so it drops to zero only if the tree empties — and
    the ledger already refuses a scope that examined NOTHING.

    Args:
        violations: The accumulator every arm appends to. Nothing is added:
            this arm measures, and the measurement is its whole output.
    """
    app = ROOT / "frontend" / "src"
    production = tests = 0
    for path in sorted(app.rglob("*")):
        if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
            continue
        source = read(path)
        literals = script_string_literals(source)
        examined["interface text / app (exempt)"] += len(literals)
        # JSX TEXT CARRIES NO QUOTES, which is the very shape arm 1 exists to
        # find — and this arm walked straight past it, so the published number
        # was short by ~9% and could not move when French JSX copy was added.
        found = sum(1 for _, body in literals if offending_string(body))
        found += sum(1 for body in jsx_text(source) if offending_string(body))
        if path.name.endswith((".test.ts", ".test.tsx")) or "__tests__" in path.parts:
            tests += found
        else:
            production += found
    # SPLIT, because they are not the same thing. French a test ASSERTS is the
    # app's rendered output — CLAUDE.md already rules it legitimate — and it was
    # 72% of the headline figure, masking the number that matters.
    exempted["french interface strings / app (production)"] = production
    exempted["french interface strings / app (asserted by tests)"] = tests

    # A RATCHET, not a print. The count drifted +7 inside the very PR that
    # introduced it as a control, and nothing noticed: a number nobody compares
    # is a number nobody reads. Only the PRODUCTION figure is pinned — lowering
    # it is the only thing that lowers the baseline.
    baseline_path = ROOT / "scripts" / "french-exemption-baseline.json"
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))["production"]
    except (OSError, ValueError, KeyError):
        violations.append(
            f"{relative(baseline_path)} is missing or unreadable — the exemption "
            "has no baseline, so nothing would notice it growing")
        return
    if production > baseline:
        violations.append(
            f"the accepted French in `frontend/src` GREW: {production} production "
            f"strings against a baseline of {baseline}. The exemption covers what "
            "is already there, never more — move the new copy out, or lower the "
            f"baseline in {relative(baseline_path)} deliberately.")


def check_test_prose(violations: list[str]) -> None:
    """Reads the French in `tests/`, counts it, and refuses it growing.

    UNREAD AND UNCOUNTED, which is the worst of the two states. CLAUDE.md is
    unambiguous that docstrings are English and that a tool's messages are
    English — and no arm opened `tests/` for strings at all, so 413 French
    literals sat there while the gate reported no violation and no counter
    named the scope. `personalscraper/`'s French has a documented carve-out
    (the CLI speaks to the operator, in French); `tests/` has none.

    Translating them is a separate piece of work — 159 docstrings and 110
    assertion messages, each of which has to be read to be moved. What must not
    wait is the invisibility: an unread scope reports « no violation » about a
    place it never opened, and that is how every hole this file has had began.

    So the scope is read, published, and RATCHETED: it may shrink, never grow.
    A new French docstring in a test is refused today; the existing ones are a
    declared debt with a number attached.

    Args:
        violations: The accumulator every arm appends to.
    """
    french = 0
    for path in sorted((ROOT / "tests").rglob("*.py")):
        source = read(path)
        literals = python_string_literals(source)
        examined["string literals / tests"] += len(literals)
        french += sum(1 for _, body in literals if offending_string(body))
    exempted["french strings / tests"] = french

    baseline_path = ROOT / "scripts" / "french-exemption-baseline.json"
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))["tests"]
    except (OSError, ValueError, KeyError):
        violations.append(
            f"{relative(baseline_path)} has no `tests` baseline — the scope "
            "would be read and counted, and still free to grow")
        return
    if french > baseline:
        violations.append(
            f"the French in `tests/` GREW: {french} strings against a baseline "
            f"of {baseline}. Docstrings and tool messages are English "
            f"(CLAUDE.md §Language) — write the new one in English, or lower "
            f"the baseline in {relative(baseline_path)} deliberately.")


def main() -> int:
    """Runs the four arms and reports every violation.

    Returns:
        1 when anything was found, 0 otherwise.
    """
    violations: list[str] = []
    check_strings(violations)
    check_identifiers(violations)
    check_file_names(violations)
    check_class_names(violations)
    check_unread_javascript(violations)
    check_vocabulary(violations)
    check_data_attributes(violations)
    check_french_debt(violations)
    check_shell_scripts(violations)
    check_dictionary(violations)
    check_app_interface_text(violations)
    check_test_prose(violations)
    for what, count in examined.items():
        if count == 0:
            violations.append(
                f"the arm reading {what} examined NOTHING — its scope is empty, "
                "so its « no violation » means nothing")
    if violations:
        print("no-French guardrail violations:", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        print(f"\n{len(violations)} violation(s). The rule: the code is English "
              "(identifiers, class names, file names, tool messages); the French "
              "a reader of the interface sees lives in the i18n resources.",
              file=sys.stderr)
        return 1
    print("no-French guardrail: 4 arms + the vocabulary + the markup names + "
          "the engine's declared debt + the shell scripts + the "
          "unread-JavaScript ledger, no violation — read "
          + ", ".join(f"{count} {what}" for what, count in examined.items()))
    # Named out loud, every run. The operator ACCEPTED this French; what must
    # never happen again is it being invisible.
    for what, count in exempted.items():
        print(f"  exempt, counted, not refused: {count} {what}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
