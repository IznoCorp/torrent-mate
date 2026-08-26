#!/usr/bin/env python3
"""Forbid French in the code, and forbid interface text from living in the code.

The operator's rule (2026-08-16): **the code contains no French** — identifiers,
class names (code AND CSS), file names, tool messages — **and no interface string
lives in the code**: the French a reader of the interface sees lives in the i18n
resources. This script is the half of the rule that is enforced rather than
remembered; it runs in `make check` and in CI.

Fourteen arms, each with its own scope, because "French" means a different thing
in a component than it does in a rule script that ASSERTS the French the app
renders. `ARMS` is the list `main` walks; arm 13 holds this enumeration against
it, so an arm added without a heading here fails the gate:

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
   DECLARES (`design/refonte.html`) plus the app's own stylesheets
   (`frontend/src/styles/ps/*.css`) — which are no longer extracted from it:
   that machinery went on 2026-08-20, the maquette REPLACES the app. A class name is one name shared by four
   worlds, which is why it gets an arm of its own.
5. **Unread JavaScript** — a `.js` under the shell that every other arm's globs
   walk past. One file is allowed to be there (the legacy engine); a second one
   turning up would be a scope silently emptying.
6. **Vocabulary** — the question turned around. Not « is this word French? »,
   whose answer is only ever as good as the list of French words behind it, but
   « is this word one we use? », read from `scripts/code-vocabulary.txt`.
7. **`data-*` names** — an attribute name is a name someone chose, so it obeys
   the rule. The VALUES of the NAMING attributes (`data-part`, `data-region`,
   `data-tone`, `data-action`, `data-side`) do too: such a value is a
   structural name someone chose, so its words are read against the
   vocabulary — body in `nofrench_values.py`. The ADDRESS attributes' values
   (`data-go`, `data-key`, `data-panel`, `data-page`, `data-mediasheet`,
   `data-resolve`, `data-follow`, `data-toast`, and anything whose value is a
   route, a title, a folder or a store datum) stay unread, because a page id
   is an address, not a name.
8. **The engine's declared debt** — the French words the legacy engine still
   needs, listed below a banner in the vocabulary and refused to every other
   file, so a vocabulary seeded from the code cannot licence the debt it exists
   to catch.
9. **Shell scripts** — every line a `.sh` prints is the tool speaking, and no
   arm read one at all until three all-French scripts turned up. Body in
   `nofrench_shell.py`, whose corpus no other arm reads.
10. **Dictionary** — a declared name built from a word French knows and English
   does not. Fail-soft when `aspell` is absent, and it SAYS so: absence must
   never read as cleanliness. Body in `nofrench_dictionary.py` — it is the one
   arm whose oracle comes from outside this repository.
11. **App interface text** — `frontend/src` is exempt by the operator's ruling,
   and the exemption is a RATCHET: the French there is counted and refused to
   grow. Body in `nofrench_ratchets.py`.
12. **Test prose** — the French in `tests/`, counted and held to a baseline.
   The French a harness ASSERTS is the app's rendered output and stays; a
   docstring or a tool message is English. Body in `nofrench_ratchets.py`.
13. **Custom-property names** — a `--token` name is a name someone chose, and
   arm 4 stopped at CSS *class* names, so seven French tokens sat under a green
   gate in both trees. Values are not read: those are data.
14. **The self-description** — the arm that counts the arms. Three files
   carried three different counts and none of them was right; this one reads
   `main`, this docstring and `CLAUDE.md`, and refuses a description that has
   drifted away from the arms that actually run.

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
#
# ONLY the two files whose French IS their subject. This set does not mean « part
# of the guard » — it means « unreadable by the guard », and a file in it is not
# examined by arms 1, 2 or 6 ever again. `nofrench_ratchets.py` was put here for
# ONE accented literal and that cost it three arms of coverage; it carries a
# `french-ok:` pragma instead, which is what the pragma is for. Adding a file
# here is emptying a scope by hand, and it needs a better reason than convenience.
SELF = {Path(__file__).name, "nofrench_lexicon.py"}

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nofrench_lexicon import *  # noqa: E402, F403
from nofrench_scan import (  # noqa: E402
    TS_DECLARATION, code_only, inside_quotes, pragma_on, python_declarations,
    python_string_literals, script_string_literals,
)
# Arms 11 and 12 — the two that COUNT rather than refuse. They stay in `ARMS`;
# only their bodies live next door, where that module's header says why.
from nofrench_ratchets import (  # noqa: E402
    check_app_interface_text, check_test_prose, jsx_text,
)
# Arm 14 and the stylesheet machinery arm 4 borrows — see that module's header.
from nofrench_css import (  # noqa: E402
    CSS_SELECTOR, allowed_class, check_custom_properties, css_allowlist,
    declared_css_classes,
)
# The VALUE half of arm 7 — see that module's header for the seam, the five
# spellings a value takes and why the attribute list is shared with the markup
# guard rather than copied.
from nofrench_values import (  # noqa: E402
    check_data_attributes, check_named_values,
)
# Arm 10 — the one oracle from outside this repository. See its header.
from nofrench_dictionary import check_dictionary  # noqa: E402
# Arm 9 — the only arm whose corpus is the shell. See its header.
from nofrench_shell import check_shell_scripts  # noqa: E402
from nofrench_lexicon import (  # noqa: E402
    DEBT_BANNER, vocabulary, DEBT_FILE, DICTIONARY_EXCEPTIONS, EXTRACTED_CSS, FRAGMENT,
    FRENCH_TOKENS, FROZEN_IDENTIFIERS, FROZEN_PATH_SEGMENTS, HARNESS, MAQUETTE,
    REGIONS, ROOT, SCRIPTS, SHELL, VOCABULARY, deaccent, french_tokens_in,
    french_tokens_in_flat, has_accent, read, relative, scope_of,
    split_identifier, tracked_paths,
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

# The text between two tags. Interface copy in JSX carries no quotes at all, so
# a scanner that only reads string literals walks straight past the very thing
# arm 1 exists to find: `<p>Réglages du système</p>` is not a literal.
JSX_TEXT = re.compile(r">([^<>{}]+)<")


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
    # `rglob`, not `glob`: a scope is checked the same way a name is. A glob one
    # level deep once read none of the nine tools that sat in `scripts/ops/`
    # (deleted 2026-08-20 — a dated one-shot from May), and reported no
    # violation about a directory it had never opened.
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
    # THE MAQUETTE'S STYLESHEETS, ALL OF THEM. This read `refonte.html` alone,
    # which was the whole of the prototype's CSS until L07 converted it — the
    # fragment holds no rule now, and the classes that remain declared live in
    # the residue and in the harness sheet. The arm went vacuous on the day the
    # last rule left, and refused itself: « its scope is empty, so its `no
    # violation` means nothing » is this guard working, not failing.
    maquette_styles = sorted(
        (ROOT / "frontend" / "maquette" / "design" / "src" / "styles").glob("*.css"))
    sheets = ([FRAGMENT] + maquette_styles
              + sorted((ROOT / "frontend" / "src").rglob("*.css")))
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
        # THE FRAGMENT IS PART OF THE MAQUETTE SCOPE, not a scope of its own.
        # It held the prototype's whole stylesheet and now holds none of it,
        # and a scope that can legitimately reach zero cannot also be the thing
        # the vacuity check watches. Folding it in keeps ONE counter over the
        # maquette's declared classes — which is what must never reach zero,
        # and which the guard can therefore refuse when it does.
        scope = "maquette" if path == FRAGMENT or path in maquette_styles else "app"
        # REGISTERED UNCONDITIONALLY. Guarding this with `if declared:` is what
        # a scope needs in order to disappear quietly, and a scope that
        # disappears is exactly what the vacuity check exists to catch: move
        # `src/styles/` one directory down and the glob stops matching, the
        # counter stays at zero, and the arm reports « no violation » over a
        # tree it never opened.
        examined["declared CSS classes / " + scope] += len(declared)
        for name, line_no in declared.items():
            if allowed_class(name, allowed):
                continue
            hits = french_tokens_in_flat(name)
            if hits or has_accent(name):
                violations.append(
                    f"{relative(path)}:{line_no}: French CSS class {name!r} "
                    f"({', '.join(hits) or 'accented'}) — a class name is one "
                    "name shared by four worlds")


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
    # A GENERATED file's names are the generator's, not a choice anyone made,
    # so this arm — and only this arm — steps over them. The count is PRINTED
    # rather than merely applied: an exemption nobody counts is
    # indistinguishable from an oversight, and a stale entry, one naming a file
    # that is not there, is a violation of its own.
    generated = {SHELL / name for name in GENERATED_SOURCES}
    for name in sorted(GENERATED_SOURCES):
        if not (SHELL / name).is_file():
            violations.append(
                f"{relative(SHELL / name)}: recorded as generated and is not in the "
                "tree — the exemption has stopped describing anything")
    sources = [p for p in sources if p not in generated]
    examined.setdefault("generated sources stepped over / shell", 0)
    examined["generated sources stepped over / shell"] += len(generated)
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
    allowed = {SHELL / "engine" / "legacy.js", SHELL / "engine" / "states.js"}
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
# ── arm 13: the self-description ─────────────────────────────────────────────
#
# THREE FILES CARRIED THREE COUNTS AND NOT ONE WAS RIGHT. This docstring said
# « Four arms », `main` said « the four arms », the success line enumerated nine
# of them, and `CLAUDE.md` said « eleven » — while `main` was calling twelve.
# Every one of those numbers had been typed by hand, so every one drifted on its
# own schedule, and a reader who believed « four » stopped looking for the other
# eight. A count nobody compares is a count nobody reads.
#
# So the count is DERIVED now: `ARMS` is the one list, `main` walks it, and the
# success line prints its length — none of those three can drift again, because
# none of them is typed. What prose still owns is the ENUMERATION (one numbered
# heading per arm, up in the module docstring) and the sentence in `CLAUDE.md`,
# which lives in another file entirely and so needs a reader HERE. This is an
# arm rather than an assertion because a false description of the rule is a
# violation of the same kind as a French name: both let a reader believe a scope
# is covered when it is not.

CLAUDE_MD = ROOT / "CLAUDE.md"

# `CLAUDE.md` §Language, the sentence naming this script and its arm count.
CLAUDE_MD_ARMS = re.compile(r"`scripts/check-no-french\.py`\s*\((?P<word>[a-z]+) arms")

NUMBER_WORDS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
    7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
    13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen",
    17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
}


def arms_bypassing_the_list() -> list[str]:
    """Returns any call in `main` that reaches this module's own functions.

    `main` walks `ARMS`, so the count cannot drift by construction — but a later
    hand could still run something beside the loop. The first version of this
    only looked for a bare `check_*(…)`, and an adversarial review defeated it
    in one line: a helper named anything else (`def extra_pass(v): …`) called
    from `main` ran completely uncounted while this reported nothing. So the
    question is no longer « is it named like an arm? » but « does `main` call
    into this file at all outside the loop? », which has no such hole. `print`
    and the built-ins are not ours and are left alone.

    Returns:
        The names `main` calls directly that are defined in this module. Empty
        is healthy.
    """
    tree = ast.parse(read(Path(__file__)))
    ours = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    body = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "main")
    return [node.value.func.id for node in ast.walk(body)
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id in ours]


def unregistered_arms() -> list[str]:
    """Returns `check_*` functions this module defines but `ARMS` does not carry.

    The other direction of the same question: an arm written and never
    registered does not run, and nothing else in the file would say so.

    Returns:
        The unregistered `check_*` names. Empty is healthy.
    """
    tree = ast.parse(read(Path(__file__)))
    defined = {node.name for node in tree.body
               if isinstance(node, ast.FunctionDef) and node.name.startswith("check_")}
    return sorted(defined - {arm.__name__ for arm, _ in ARMS})


def check_arm_count(violations: list[str]) -> None:
    """Refuses a self-description that disagrees with the arms that run.

    Holds three things against `ARMS`: that nothing is called around it, that
    the module docstring carries a numbered heading for each arm, and that the
    sentence in `CLAUDE.md` names the same count.

    Args:
        violations: The accumulator every arm appends to.
    """
    examined["arms / self-description"] += len(ARMS)
    bypassing = arms_bypassing_the_list()
    if bypassing:
        violations.append(
            f"`main` calls {bypassing} outside the `ARMS` loop — whatever runs "
            "there is documented by nothing and counted by nothing, which is "
            "the state this arm exists to end")
    stranded = unregistered_arms()
    if stranded:
        violations.append(
            f"{stranded} is defined as an arm and absent from `ARMS`, so it "
            "never runs — a scope that reports « no violation » because nobody "
            "called it")

    doc = __doc__ or ""
    word = NUMBER_WORDS.get(len(ARMS), str(len(ARMS)))
    # The COUNT WORD in the first paragraph, which is the one that read « Four »
    # for a whole wave. The headings below it were held from the start and this
    # was not: an adversarial review set it back to « Four arms » and the gate
    # stayed green, so the very defect this arm is named for survived it.
    heading = re.search(r"^(?P<word>[A-Z][a-z]+) arms, each with its own scope",
                        doc, re.M)
    if heading is None:
        violations.append(
            "the module docstring no longer opens with « <N> arms, each with "
            "its own scope » — that sentence is what names the count in prose, "
            "and this arm has nothing to hold once it is gone")
    elif heading.group("word").lower() != word:
        violations.append(
            f"the module docstring says « {heading.group('word')} arms » and "
            f"there are {len(ARMS)} — write « {word.capitalize()} ». This is the "
            "exact word that said « Four » while twelve arms ran.")
    for position, (_, label) in enumerate(ARMS, start=1):
        if f"{position}. **{label}**" not in doc:
            violations.append(
                f"the module docstring carries no « {position}. **{label}** » "
                "heading — an arm nobody documented is an arm nobody knows to "
                "look for, which is how three of these went unnamed for a wave")

    try:
        claimed = CLAUDE_MD_ARMS.search(read(CLAUDE_MD))
    except OSError:
        claimed = None
    if claimed is None:
        violations.append(
            f"{CLAUDE_MD.name} no longer carries the sentence naming this "
            "script's arm count — the cross-file reader that catches its drift "
            "has nothing left to read, so restore it or retire this hold")
    elif claimed.group("word") != word:
        violations.append(
            f"{CLAUDE_MD.name} says « {claimed.group('word')} arms » and there "
            f"are {len(ARMS)} — write « {word} ». That sentence was wrong for a "
            "whole wave, for the single reason that nothing read it.")


# THE ONE LIST. Every count in this file is `len(ARMS)` or derived from it, and
# the label beside each arm is the heading its docstring entry must carry.
ARMS: tuple[tuple[object, str], ...] = (
    (check_strings, "Strings"),
    (check_identifiers, "Identifiers"),
    (check_file_names, "File names"),
    (check_class_names, "Class names"),
    (check_unread_javascript, "Unread JavaScript"),
    (check_vocabulary, "Vocabulary"),
    (check_data_attributes, "`data-*` names"),
    (check_french_debt, "The engine's declared debt"),
    (check_shell_scripts, "Shell scripts"),
    (check_dictionary, "Dictionary"),
    (check_app_interface_text, "App interface text"),
    (check_test_prose, "Test prose"),
    (check_custom_properties, "Custom-property names"),
    (check_arm_count, "The self-description"),
)


def main(argv: list[str] | None = None) -> int:
    """Runs every arm in `ARMS` and reports every violation.

    The arms are WALKED rather than listed again here: a hand-written second
    list is a count that drifts, and this one drifted three times (see arm 13).

    Args:
        argv: The command line, defaulting to `sys.argv[1:]`. With `--counts`
            the examined ledger is printed one line per counter instead of the
            success line — ACC-12 greps that output for the naming-value
            count, because a gate proves what it READS, not what it exits.

    Returns:
        1 when anything was found, 0 otherwise.
    """
    counts_only = "--counts" in (sys.argv[1:] if argv is None else argv)
    violations: list[str] = []
    for arm, _ in ARMS:
        arm(violations)
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
    if counts_only:
        for what, count in examined.items():
            print(f"{count} {what}")
        return 0
    print(f"no-French guardrail: {len(ARMS)} arms ("
          + ", ".join(label for _, label in ARMS)
          + "), no violation — read "
          + ", ".join(f"{count} {what}" for what, count in examined.items()))
    # Named out loud, every run. The operator ACCEPTED this French; what must
    # never happen again is it being invisible.
    for what, count in exempted.items():
        print(f"  exempt, counted, not refused: {count} {what}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
