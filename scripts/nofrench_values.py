#!/usr/bin/env python3
"""Arm 7 — a `data-*` NAME, and the VALUE of one whose values are names.

SPLIT OUT OF `check-no-french.py`, which stood at 985 non-blank lines against
a 1 000-line hard ceiling: the arms this sub-phase owed it are what would have
broken the gate. The seam is the same one `nofrench_ratchets.py` was cut on —
one arm, one file. It asks two questions of the same markup: whether an
attribute's NAME is a word this codebase speaks, and whether what a NAMING
attribute SAYS is.

WHICH ATTRIBUTES, AND WHY THE LIST IS NOT HERE. `markup_text.NAMING_ATTRIBUTES`
holds it, and the markup guard reads the same constant to hold a different
question — every value a rule SELECTS must be emitted somewhere. `data-tone`
was coined by one wave and was in neither list, so a French tone value passed
this gate while ten harness rules selected `danger` with nothing to refuse a
rename. A contract with two copies of its list is a contract that drifts, so
there is one copy and both guards read it.

A NAMING value is a structural name — `library/body`, `card/overview`,
`primary`, `danger` — and it obeys the rule a name obeys: split on `/` and `-`,
checked word by word against the vocabulary. An ADDRESS value is not a name:
`data-go="profil"` names a page, and a page id, a route, a title, a folder or a
datum the app stores is an address. An attribute in NEITHER list is unread
here, and the name half still reads every NAME.

AND IT READS THE IMPERATIVE SHAPES. A node the engine BUILDS carries no
`data-part="…"` text anywhere: it is created, given its attributes by
assignment, then appended. The markup guard was taught those two shapes
deliberately, in the same commit as the anchor they carry; this arm was not,
and three values — `selection/bar`, `harness/panel`, `episode/popover` — were
read by nothing. The count said 463 and a literal count over the same corpus
said 443 literal plus 3 imperative, so the shortfall was visible only to
someone who went looking for it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from markup_text import NAMING_ATTRIBUTES  # noqa: E402
from nofrench_lexicon import (  # noqa: E402
    FRAGMENT, MAQUETTE, ROOT, SHELL, VOCABULARY, examined, read, relative,
    split_identifier, vocabulary,
)

# The ADDRESS attributes, named here so that adding an attribute forces the
# choice of which list it joins. An address is a datum: a page id, a route, a
# title, a folder, something the app stores or displays. No arm may ask one of
# them to be English.
ADDRESS_ATTRIBUTES = frozenset({
    "data-go", "data-key", "data-panel", "data-page", "data-mediasheet",
    "data-resolve", "data-follow", "data-toast",
})

# A naming attribute's literal value, in the three DECLARATIVE spellings:
# double-quoted, single-quoted, and the JSX braced-string form.
NAMED_VALUE = re.compile(
    r"\b(?P<attr>" + "|".join(sorted(NAMING_ATTRIBUTES)) + r")"
    r"""(?:="(?P<dq>[^"]*)"|='(?P<sq>[^']*)'|=\{\s*['"](?P<brace>[^'"]*)['"]\s*\})""")

# And the two IMPERATIVE spellings, on an element the script builds:
# `bar.dataset.part = "selection/bar"` and
# `el.setAttribute("data-part", "harness/panel")`. `dataset` spells a
# `data-two-word` attribute `twoWord`, so the property name is put back into
# its attribute spelling before the lookup.
IMPERATIVE_DATASET = re.compile(
    r"""\.dataset\.(?P<attr>[a-z][A-Za-z0-9]*)\s*=\s*['"](?P<value>[^'"]*)['"]""")
IMPERATIVE_SET_ATTRIBUTE = re.compile(
    r"""\.setAttribute\(\s*['"](?P<attr>data-[a-z][\w-]*)['"]\s*,\s*"""
    r"""['"](?P<value>[^'"]*)['"]\s*\)""")

# The lexicon's ledger is the canonical table of every counter; this key is
# declared HERE so the arm and its count live in one file. The zero-count hold
# in `main` still refuses it when it stays empty. It is named after `data-part`
# and stays so whatever else joins the list: ACC-12 greps this line's wording.
examined.setdefault("data-part values / markup", 0)


def attribute_of(dataset_name: str) -> str:
    """Returns the attribute spelling of a `dataset` property name.

    Args:
        dataset_name: The property name as written after `.dataset.`.

    Returns:
        The full attribute name — `noPoster` becomes `data-no-poster`.
    """
    return "data-" + re.sub(r"([A-Z])",
                            lambda m: "-" + m.group(1).lower(), dataset_name)


def named_values(source: str) -> list[tuple[int, str, str]]:
    """Returns every naming-attribute value one source spells out.

    Five shapes: the three declarative ones and the two imperative ones. A
    COMPUTED value names no literal — `data-tone="${TONS[row.tone]}"` is a
    table lookup at run time, and reading its text as a name would refuse
    the interpolation itself as a foreign word — so it is skipped whole,
    exactly as the markup guard skips a computed emission.

    Args:
        source: One file's text.

    Returns:
        `(offset, attribute, value)` tuples, in reading order.
    """
    found: list[tuple[int, str, str]] = []
    for match in NAMED_VALUE.finditer(source):
        value = (match.group("dq") or match.group("sq")
                 or match.group("brace"))
        found.append((match.start(), match.group("attr"), value))
    for match in IMPERATIVE_DATASET.finditer(source):
        attribute = attribute_of(match.group("attr"))
        if attribute in NAMING_ATTRIBUTES:
            found.append((match.start(), attribute, match.group("value")))
    for match in IMPERATIVE_SET_ATTRIBUTE.finditer(source):
        if match.group("attr") in NAMING_ATTRIBUTES:
            found.append((match.start(), match.group("attr"),
                          match.group("value")))
    return [entry for entry in sorted(found) if "${" not in entry[2]]


def check_named_values(path: Path, source: str, violations: list[str]) -> None:
    """Refuses a naming-attribute value built from a word this codebase lacks.

    Args:
        path: The file being read, for the message.
        source: Its text.
        violations: The accumulator every arm appends to.
    """
    words = vocabulary()
    for offset, attribute, value in named_values(source):
        examined["data-part values / markup"] += 1
        line_no = source.count("\n", 0, offset) + 1
        unknown = [w for w in re.split(r"[/-]", value)
                   if len(w) > 1 and w.lower() not in words]
        if unknown:
            violations.append(
                f"{relative(path)}:{line_no}: the markup value {value!r} "
                f"of {attribute!r} is built from "
                f"{', '.join(repr(w) for w in unknown)}, which "
                f"{'is' if len(unknown) == 1 else 'are'} not in "
                f"{relative(VOCABULARY)} — name it in English, or add the "
                "word there if the codebase really speaks it")


def check_data_attributes(violations: list[str]) -> None:
    """Refuses a `data-*` attribute NAME built from a word this codebase lacks.

    CLAUDE.md brings these names under the rule — a `data-*` name is a name
    someone chose — and until now nothing read them. Nineteen were renamed by
    hand in the same wave that wrote the rule, and four were missed:
    `data-prendre`, `data-maintrub`, `data-qreg` and `data-apparence` stayed,
    green, because no arm looked. A rule with no arm is a sentence in a file.

    The VALUES of the NAMING attributes are read too, and of nothing else.
    That half lives in `nofrench_values.py`, beside this file: the list of
    attributes, the five spellings a value takes, and why an ADDRESS value
    is not a name. It moved out at 985 non-blank lines against a 1 000-line
    hard ceiling — the arm this sub-phase owed the file was the arm that
    would have broken the gate.

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
        check_named_values(path, source, violations)


__all__ = ["ADDRESS_ATTRIBUTES", "NAMING_ATTRIBUTES", "check_data_attributes",
           "check_named_values", "named_values"]
