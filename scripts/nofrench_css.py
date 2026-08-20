#!/usr/bin/env python3
"""The arms and helpers that read a STYLESHEET.

SPLIT OUT OF `check-no-french.py`, which arm 14 pushed past the 1 000-line
block for the second time in two days. The seam is the source being read: a
class name and a custom-property name are both names in CSS, they share the
maquette's `$vocabulary` for their frozen exceptions, and neither is found by
reading Python or TypeScript.

`check_class_names` stays next door — it also reads Python `class X`
declarations, so it is not purely a stylesheet arm — and imports the allowlist
machinery from here.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nofrench_lexicon import (  # noqa: E402
    EXTRACTED_CSS, FRAGMENT, FROZEN_IDENTIFIERS, REGIONS, ROOT, examined,
    french_tokens_in, has_accent, read, relative, split_identifier, vocabulary,
)


CSS_SELECTOR = re.compile(  # french-ok: a Latin-1 letter RANGE, not a word
    r"\.(?P<name>-?[A-Za-z_À-ɏ][\wÀ-ɏ-]*)")


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

    # `record`, not `vocabulary`: a local of that name shadowed the imported
    # `vocabulary()` for the whole function, which arm 14 below calls.
    record = find(data)
    if not isinstance(record, dict):
        raise ValueError(f"no $vocabulary record in {relative(REGIONS)}")
    allowed: dict[str, str] = {}
    frozen = record.get("frenchTokensFrozen", {})
    reason = frozen.get("$comment", "").strip()
    if not reason:
        raise ValueError("frenchTokensFrozen carries no reason")
    for token in frozen.get("tokens", []):
        allowed[token] = reason
    for token, why in record.get("abbreviationsKept", {}).items():
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



# ── arm 14: custom-property names ────────────────────────────────────────────
#
# A `--token` NAME is a name someone chose, so `CLAUDE.md` §Language covers it
# word for word — « identifiers, function/type/class names (code AND CSS) ».
# Arm 4 reads CSS CLASS names and stops there, so seven French tokens sat under
# a green gate in BOTH trees: `--danger-texte`, `--info-texte`,
# `--primary-texte`, `--success-texte`, `--warning-texte`, `--mq-scrim-doux`,
# `--mq-shadow-carte`. This is the third time a rule in that section had no arm
# — `data-*` names, `frontend/scripts/`, and now these — and each time the gap
# was found by a person reading, not by the gate.
#
# The VALUE is not read. `--waiting: oklch(…)` is data, and the token that
# carries a French word in its value would be arm 1's business, not this one's.

# A `<custom-property-name>` is `--` followed by a CSS identifier: letters of any
# script, digits, `_` and `-`. The first version of this read
# `[a-zA-Z][a-zA-Z0-9_-]*` and anchored to the start of a line, which made FIVE
# valid forms invisible — and the worst of them was the accented one, so
# `has_accent()` below was unreachable and `--café` passed the arm written to
# catch exactly that. `\w` is Unicode-aware for `str` patterns in Python 3, so it
# covers the accents this arm exists for; the prefix accepts a declaration after
# `{`, `;` or `,` as well as at the start of a line, and the optional quotes
# are for the TypeScript form — `sonner.tsx` declares three tokens as
# `"--normal-bg": …` inside a style object, which is a DECLARATION whatever
# the file extension says.
CUSTOM_PROPERTY = re.compile(r"""(?:^|[{;,])\s*["']?(--[\w-]+)["']?\s*:""", re.M)

# Token names whose French-looking word is a CSS KEYWORD, each with its reason.
# `sans` is the one real case: `--font-sans` names the `sans-serif` family, and
# it is also the French preposition. Adding `sans` to the vocabulary instead
# would licence it in every identifier in the repository, which is the opposite
# of what the vocabulary is for — so the exception is pinned to the whole NAME.
CSS_KEYWORD_TOKENS = {
    "--font-sans": "the CSS `sans-serif` family, not the French preposition",
    # Named by the `sonner` toast library, which READS these three off the
    # element. They are its API, not names anyone here chose, so renaming them
    # would simply stop the theming working.
    "--normal-bg": "the sonner library's own API",
    "--normal-text": "the sonner library's own API",
    "--normal-border": "the sonner library's own API",
}


def check_custom_properties(violations: list[str]) -> None:
    """Refuses a CSS custom-property name built from a word we do not use.

    Args:
        violations: The accumulator every arm appends to.
    """
    known = vocabulary()
    # EVERY place a custom property can be DECLARED, not just the two obvious
    # ones. The first scope read `refonte.html` + `src/styles/**` and stopped
    # there, which left four tracked component stylesheets and the shell's own
    # document outside — narrower than arm 7, which already walks all of
    # `frontend/src`. A scope that is narrower than its sibling's is a hole
    # nobody chose.
    sheets = [p for p in (FRAGMENT, ROOT / "frontend" / "maquette" / "design" / "index.html")
              if p.exists()]
    sheets += sorted((ROOT / "frontend" / "src").rglob("*.css"))
    sheets += sorted((ROOT / "frontend" / "src").rglob("*.tsx"))
    sheets += [p for p in (ROOT / "frontend" / "maquette" / "design" / "src").rglob("*.tsx")]
    for path in sheets:
        source = read(path)
        for match in CUSTOM_PROPERTY.finditer(source):
            name = match.group(1)
            examined["custom-property names / css"] += 1
            if name in CSS_KEYWORD_TOKENS:
                continue
            words = [w for w in split_identifier(name.lstrip("-")) if w]
            hits = french_tokens_in(name.lstrip("-"), relative(path))
            unknown = [w for w in words
                       if w.lower() not in known and not w.isdigit()]
            if hits or has_accent(name) or unknown:
                why = (", ".join(hits) if hits
                       else "accented" if has_accent(name)
                       else f"built from {unknown!r}, which this codebase does not use")
                line_no = source.count("\n", 0, match.start()) + 1
                violations.append(
                    f"{relative(path)}:{line_no}: French or unknown custom-property "
                    f"name {name!r} ({why}) — a token name is a name someone chose "
                    "(CLAUDE.md §Language), so it is English like any other")


