"""The `cva()` factory reader — every typed variant's anchor, base and branches, read as text.

NOT A RULE: plumbing a rule may borrow, like `common.py`. NO RULE BORROWS IT
TODAY: `resolution_card.py` read `iconButton`'s base through it to hold the
candidate card's check mark to the icon size, and B-500 retired that mark for a
pill held to a finger's height.

It was the reading half of R80, which compared the engine's residue stylesheet
with the variants that stylesheet shadowed. R80 died with the stylesheet; this
half had a reader of its own and moved here unchanged. It needs no browser,
and `tests/scripts/test_factories.py` exercises it.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

# WHERE A FACTORY MAY BE DECLARED: anywhere in the component tree. Named by
# SHAPE and not by file, for the reason `common.py` gives about the design's
# sources — a tuple of paths misses the factory written tomorrow. A first
# version of this read `ui/variants*.ts` and `features/*/variants.ts` and found
# 44 factories while missing the three files that hold the shared vocabulary,
# so it paired ONE anchor of the seven B-067 named and reported no
# divergence. The engine is excluded: it draws its markup by hand and owns no
# variant.
_COMPONENTS = ROOT / "design" / "src"
VARIANT_SOURCES = sorted(
    path for extension in ("*.ts", "*.tsx")
    for path in _COMPONENTS.rglob(extension)
    if "engine" not in path.relative_to(_COMPONENTS).parts
)

# `export const NAME = cva(` — the factory, wherever it is declared.
FACTORY = re.compile(r"export const ([A-Za-z_$][\w$]*)\s*=\s*cva\s*\(")

# ANY call to the factory helper, however it is written. This is the counter
# that makes `FACTORY` honest: the pattern above wants `export const NAME =`
# and nothing else, so `cva<Props>(…)`, `const x: F = cva(…)`, a factory
# exported on a later line, or one wrapped in `memo(…)` matches NOTHING and
# vanishes with no complaint — and losing `statusDot()` alone would have taken
# six of sixteen pairs out of the comparison while the run stayed green. Every
# call must be accounted for: read, or named as unread.
CVA_CALL = re.compile(r"(?<![\w$])cva\s*\(")

# A double-quoted class-list literal. The sources write every one of them with
# double quotes; a single-quoted one would be missed, so the count of factories
# read is printed and held above zero.
LITERAL = re.compile(r'"((?:\\.|[^"\\])*)"')


def balanced(text, start):
    """Returns the index just past the `(` opened at `start`.

    QUOTES ARE TRACKED, and they were not. `split_top_level()` three functions
    below has always tracked them and this one did not, inside the same file —
    so a class literal carrying an unbalanced parenthesis, which is ordinary
    Tailwind (`before:content-['(']`, and `endMark()` already ships
    `before:content-['']`), ran the scan to the end of the file. The factory
    then read every literal after it as one of its own branches, and no hold
    said a word: the anchor was still right, so nothing looked wrong.

    Args:
        text: The source.
        start: The index OF the opening parenthesis.

    Returns:
        The index one past the matching `)`, or the end of the text when the
        call never closes.
    """
    depth = 0
    index = start
    quote = None
    while index < len(text):
        character = text[index]
        if quote:
            if character == "\\":
                index += 2
                continue
            if character == quote:
                quote = None
        elif character in "\"'`":
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return len(text)


def split_top_level(text):
    """Splits a call's arguments on TOP-LEVEL commas.

    Args:
        text: The text between a call's parentheses.

    Returns:
        The arguments, as written.
    """
    parts, current, depth, quote = [], [], 0, None
    for index, character in enumerate(text):
        if quote:
            current.append(character)
            if character == quote and text[index - 1] != "\\":
                quote = None
            continue
        if character in "\"'`":
            quote = character
        elif character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(character)
    parts.append("".join(current))
    return parts


def without_comments(text):
    """Blank out a TypeScript source's comments, keeping every offset.

    THIS IS NOT TIDINESS, IT IS THE READER'S CORRECTNESS. A `cva()` call's
    first argument is separated from the rest by a TOP-LEVEL COMMA, and this
    repository's comments are full of commas. One comment's comma ended the
    first argument after four characters, so a factory's base came out EMPTY,
    its anchor vanished from the table, and its pair simply stopped being
    compared. Nothing failed — the rule printed one pair fewer.

    Quotes and templates are tracked, so a `//` inside a class-name literal is
    not mistaken for a comment. Lengths are preserved so nothing downstream has
    to care that anything was removed.

    WHAT IT DOES NOT TRACK, and both are ordinary TypeScript: an APOSTROPHE in
    JSX text (`<p>don't</p>`) and a QUOTE inside a regex literal
    (`/["']/g`). Either opens a quote run that swallows text to the next quote
    character in the file, and a comment inside that run survives. The loud
    outcome — a base blanked to nothing — is refused by the `unread` hold; the
    quiet one is a truncated branch table. Written down rather than discovered,
    and the reason there is a test for each.

    Args:
        text: A TypeScript source.

    Returns:
        The same text with every comment replaced by spaces of equal length.
    """
    out = list(text)
    index, quote, length = 0, None, len(text)
    while index < length:
        character = text[index]
        if quote:
            if character == "\\":
                index += 2
                continue
            if character == quote:
                quote = None
            index += 1
            continue
        if character in "\"'`":
            quote = character
            index += 1
            continue
        if character == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] != "\n":
                out[index] = " "
                index += 1
            continue
        if character == "/" and index + 1 < length and text[index + 1] == "*":
            end = text.find("*/", index + 2)
            end = length if end == -1 else end + 2
            for blank in range(index, end):
                if out[blank] != "\n":
                    out[blank] = " "
            index = end
            continue
        index += 1
    return "".join(out)


def read_factories():
    """Reads every `cva()` factory into its anchor, its base and its branches.

    THE ANCHOR IS THE FIRST TOKEN of the base string, and that is not a guess:
    `ui/variants.ts` states the convention in its own header — « the original
    class name is kept at the front of every string, emptied of style » — and
    D4 wants an anchor to be exactly that.

    Returns:
        A `(factories, files_read, unread, duplicates, calls)` tuple.
        `factories` maps an anchor class to a dict carrying the factory's name,
        its base class list, and its branches keyed by the branch's own leading
        token. `unread` names every factory whose base came out EMPTY — a
        factory the reader could not read is a pair that silently stops being
        compared, so it is a violation and never a skip. `duplicates` names two
        factories claiming one anchor, which used to be a silent overwrite.
        `calls` is how many `cva(` calls the sources hold at all, so the reader
        can be held against the corpus instead of against itself.
    """
    factories = {}
    unread = []
    duplicates = []
    calls = 0
    for path in VARIANT_SOURCES:
        text = without_comments(path.read_text(encoding="utf-8"))
        calls += len(CVA_CALL.findall(text))
        for found in FACTORY.finditer(text):
            opening = text.index("(", found.end() - 1)
            call = text[opening + 1:balanced(text, opening) - 1]
            arguments = split_top_level(call)
            base = " ".join(
                piece for literal in LITERAL.finditer(arguments[0])
                for piece in [literal.group(1)]
            ).split()
            if not base:
                unread.append(f"{found.group(1)}() in {path.name}")
                continue
            branches = {}
            for argument in arguments[1:]:
                for literal in LITERAL.finditer(argument):
                    tokens = literal.group(1).split()
                    if tokens:
                        branches.setdefault(tokens[0], tokens)
            if base[0] in factories:
                # TWO FACTORIES CLAIMING ONE ANCHOR. The convention this reader
                # leans on — « the original class name is kept at the front » —
                # is not universal: three factories lead with a UTILITY
                # (`ml-auto`, `flex-none`, `text-foreground`) rather than an
                # identity anchor. The last one read used to win in silence.
                duplicates.append(
                    f"« {base[0]} » claimed by {factories[base[0]]['name']}() and "
                    f"{found.group(1)}()")
                continue
            factories[base[0]] = {
                "name": found.group(1),
                "file": path.name,
                "base": base,
                "branches": branches,
            }
    return factories, len(VARIANT_SOURCES), unread, duplicates, calls
