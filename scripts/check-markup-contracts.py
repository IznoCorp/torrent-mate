#!/usr/bin/env python3
"""Refuses a `data-*` value the markup emits and no reader understands.

THE DEFECT CLASS, and it cost eight contracts in one day. The prototype drives
itself by delegation: markup carries `data-X="value"`, a click handler writes
that value VERBATIM into a store field, and components compare the field
against the values they know.

    <button data-phase="ready">                     the markup emits
    store.write({ phase: closest.dataset.phase })   the handler writes, verbatim
    state.phase === "ready"                          the reader compares

Three ends, and nothing tied them together. So a rename that moved two of them
left the third behind, every time, and the control simply stopped working while
every gate stayed green:

  * `data-phase="prete"` on the « Réessayer » button of every error surface.
    No reader knows `prete`, so the retry wrote a phase nothing renders and the
    error screen never cleared.
  * `data-hscen="reel"` / `"charge"` on the harness's data-scenario dial, whose
    readers compare `real` / `loaded`. Clicking « État réel » landed on the
    loaded branch and both buttons showed unpressed.

Neither was found by reading the diff, by the 50-rule suite, or by a sweep for
French strings — they are not French-vs-English, they are markup-vs-reader.
This rule asks the only question that catches them: **does anything understand
what this button writes?**

WHAT IT READS. Handlers of the shape `store.write({ field: …dataset.name })`
give the `data-name` → `field` map. Every `data-name="value"` in the maquette's
sources is then checked against the values any reader compares that field
against — `field === "v"`, `.field === "v"`, `field: "v"`, `["field"] == "v"`.

WHAT IT DOES NOT READ. A handler that TRANSLATES rather than forwards
(`dataset.x === "a" ? "b" : "c"`) is out of scope: the emitted value is then an
input to a decision, not a stored value, and holding it here would report a
defect that is not one.

Usage:
    python3 scripts/check-markup-contracts.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "frontend" / "maquette" / "design" / "src"

# `store.write({ pipe: closest.dataset.pipe })` — the handler that FORWARDS a
# markup value into a store field. The two names differ often enough
# (`data-hphase` → `phase`) that both are captured.
FORWARDER = re.compile(
    r"store\.write\(\{\s*(?P<field>\w+)\s*:\s*\w+\.dataset\.(?P<attr>\w+)\s*,?\s*\}\)")

# `data-name="value"` in emitted markup or JSX. A value carrying `${` is
# computed, and this rule cannot know what it evaluates to.
EMITTED = re.compile(r"""data-(?P<attr>[a-z][\w-]*)=["'](?P<value>[^"'${]+)["']""")

# Comments are stripped before anything is read. `library.tsx` carries a comment
# describing a REJECTED first version — « gated it on `phase === "prete"` » —
# and reading it as code made this rule believe `prete` was a value some reader
# understood, so it walked past the dead retry button it was written to catch.
# Reading CSS as text cost the token guard the same way, one file over.
COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)


def readers_of(field: str, sources: str) -> set[str]:
    """Returns every literal value some reader compares `field` against.

    Args:
        field: The store field's name.
        sources: All maquette source text, concatenated.

    Returns:
        The set of literal values, including the ones written as defaults.
    """
    patterns = [
        rf"""\b{field}\s*===?\s*["']([^"']+)["']""",
        rf"""\.{field}\s*===?\s*["']([^"']+)["']""",
        rf"""\[["']{field}["']\]\s*===?\s*["']([^"']+)["']""",
        rf"""\b{field}\s*:\s*["']([^"']+)["']""",
    ]
    found: set[str] = set()
    for pattern in patterns:
        found |= set(re.findall(pattern, sources))
    return found


def main() -> int:
    """Checks every forwarded `data-*` value against the readers of its field.

    Returns:
        1 when anything was found, 0 otherwise.
    """
    files = [p for p in sorted(SOURCES.rglob("*"))
             if p.is_file() and p.suffix in {".js", ".ts", ".tsx"}]
    if not files:
        print(f"check-markup-contracts: no sources under {SOURCES} — the scope "
              "is empty, so « no violation » would mean nothing", file=sys.stderr)
        return 1
    text = {p: p.read_text(encoding="utf-8") for p in files}
    # Comments describe what was TRIED; only code says what is understood.
    joined = COMMENT.sub(" ", "\n".join(text.values()))

    forwarded = {m.group("attr"): m.group("field")
                 for m in FORWARDER.finditer(joined)}
    if not forwarded:
        print("check-markup-contracts: no `store.write({f: …dataset.x})` handler "
              "found — either the delegation changed shape or this rule is "
              "reading the wrong tree", file=sys.stderr)
        return 1

    violations = 0
    checked = 0
    for path, source in text.items():
        for match in EMITTED.finditer(source):
            attr, value = match.group("attr"), match.group("value").strip()
            field = forwarded.get(attr)
            if field is None:
                continue                      # not forwarded: not this rule's business
            checked += 1
            known = readers_of(field, joined)
            if value not in known:
                line = source.count("\n", 0, match.start()) + 1
                rel = path.relative_to(ROOT)
                print(f"  {rel}:{line}: `data-{attr}=\"{value}\"` is written "
                      f"verbatim into `{field}`, and no reader compares "
                      f"`{field}` against {value!r}. The control is dead: it "
                      f"writes a value nothing renders. Known: "
                      f"{sorted(known) or '(none)'}", file=sys.stderr)
                violations += 1

    if violations:
        print(f"\ncheck-markup-contracts: {violations} dead control(s). A "
              "`data-*` value, the handler that forwards it and the readers "
              "that compare it are ONE contract — they move together or the "
              "button stops working in silence.", file=sys.stderr)
        return 1

    print(f"check-markup-contracts: {len(forwarded)} forwarded attribute(s), "
          f"{checked} emitted value(s), every one understood by a reader.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
