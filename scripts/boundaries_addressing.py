#!/usr/bin/env python3
"""The address model's own arm of `check-frontend-boundaries.py`.

WHY IT IS A FILE. `check-frontend-boundaries.py` reached 921 non-blank lines
against a hard ceiling of 1 000, and it gains an arm in the same wave that
found the ceiling coming. The split follows a SUBJECT rather than a line
count: everything here answers one question — does the SOURCE declare the
address model D1 settled, where the path carries the identity and the query
carries the state?

That question has its own machinery and nothing else uses it: a small reader
for JavaScript object literals, so a `validateSearch` body written inline can
be read for the keys it declares, and a bracket-matcher over the dying
engine's page table. The arms that stayed behind read IMPORTS and FILE SIZES,
which share no line of this.

Imported by `check-frontend-boundaries.py` and by nothing else. It runs no
corpus of its own: the caller passes the root.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_MEMBER_NAME = re.compile(r"[A-Za-z_$][\w$]*")
# A key written in quotes, read off the SOURCE — the scanned text has had
# its strings blanked, which is exactly why this cannot be read there.
_QUOTED_KEY = re.compile(r"""['"]([A-Za-z_$][\w$]*)['"]""")


def _skip_blank(text: str, offset: int) -> int:
    """Find the first index at or after `offset` carrying no whitespace.

    Args:
        text: The source being read.
        offset: Where to start looking.

    Returns:
        The index of the first non-blank character, or the text's length.
    """
    while offset < len(text) and text[offset].isspace():
        offset += 1
    return offset


def _balanced(text: str, start: int, opener: str, closer: str) -> int:
    """Find the delimiter closing the one at `start`.

    Args:
        text: The source being read.
        start: The index of the opening delimiter.
        opener: The opening delimiter.
        closer: The closing delimiter.

    Returns:
        The closing delimiter's index, or -1 when it is never reached.
    """
    depth = 0
    for offset in range(start, len(text)):
        if text[offset] == opener:
            depth += 1
        elif text[offset] == closer:
            depth -= 1
            if depth == 0:
                return offset
    return -1


# A comment, or a string literal in any of the three quotings. Ordered so the
# first opener encountered wins: a `//` inside a block comment is comment text,
# and a quote inside a comment opens nothing.
_NOISE = re.compile(r"""//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`""", re.S)


def _strip_noise(text: str) -> str:
    """Blank every comment and string literal, leaving each offset where it was.

    The reader below walks braces and matches on names, and both are fooled by
    text that only LOOKS like code: a `// validateSearch: …` note was read AS a
    member and failed the build over a legitimate comment. Blanking in place
    keeps every offset aligned with the source, so a caller can locate a body
    here and still slice it from the text it came from.

    Args:
        text: The source being read.

    Returns:
        The same text, every comment and string blanked out with spaces.
    """
    return _NOISE.sub(lambda noise: re.sub(r"[^\n]", " ", noise.group(0)), text)


def _read_body(scan: str, cursor: int) -> tuple[int, int] | None:
    """Find the span of a function's body, from its arrow or its opening brace.

    An arrow may hand back a parenthesised object literal, so parentheses are
    stepped over after the arrow. Anything else between the head and a brace
    means the shape is one this reader does not follow — it says so, rather
    than scanning on to an unrelated brace further down the file.

    Args:
        scan: The route text, with its comments and strings blanked.
        cursor: The index of the arrow, or of the body's opening brace.

    Returns:
        The body's span, its braces excluded, or None.
    """
    if scan.startswith("=>", cursor):
        cursor += 2
        while cursor < len(scan) and (scan[cursor].isspace() or scan[cursor] == "("):
            cursor += 1
    if cursor >= len(scan) or scan[cursor] != "{":
        return None
    closing = _balanced(scan, cursor, "{", "}")
    if closing == -1:
        return None
    return cursor + 1, closing


def _read_callable(scan: str, offset: int) -> tuple[tuple[int, int], str, str] | None:
    """Read one function's body span, declared return type and parameter list.

    A return type may be written INLINE — `(raw): { page?: string } => …` — and
    its brace sits exactly where a braced body's does. It is read as the TYPE,
    the arrow behind it opening the body; the reader that took the first brace
    it found measured the type, reported a body, and matched none of its keys.

    Args:
        scan: The route text, with its comments and strings blanked.
        offset: The index of the `function` keyword, or of the parameter list.

    Returns:
        The body's span, the declared return type as written, and the SPAN of
        the parameter list — or None when the shape is not one this reader
        follows. The parameter list is handed back as a span and not as text
        because a key there may be QUOTED, and quotes are blanked in `scan`:
        only the caller, which holds the source, can read one.
    """
    if scan.startswith("function", offset):
        cursor = _skip_blank(scan, offset + len("function"))
        named = _MEMBER_NAME.match(scan, cursor)
        offset = _skip_blank(scan, named.end()) if named else cursor
    if offset >= len(scan) or scan[offset] != "(":
        return None
    closing = _balanced(scan, offset, "(", ")")
    if closing == -1:
        return None
    parameters = (offset + 1, closing)
    cursor = _skip_blank(scan, closing + 1)
    returned = ""
    if cursor < len(scan) and scan[cursor] == ":":
        head = _skip_blank(scan, cursor + 1)
        if scan[head:head + 1] == "{":
            end = _balanced(scan, head, "{", "}")
            if end == -1:
                return None
            returned = scan[head + 1:end]
            cursor = _skip_blank(scan, end + 1)
        else:
            ends = [p for p in (scan.find("=>", cursor), scan.find("{", cursor)) if p != -1]
            if not ends:
                return None
            returned = scan[cursor + 1:min(ends)].strip()
            cursor = min(ends)
    body = _read_body(scan, cursor)
    return None if body is None else (body, returned, parameters)


def _declaration_of(scan: str, name: str) -> int | None:
    """Find where this file declares `name`, if it declares it at all.

    Args:
        scan: The route text, with its comments and strings blanked.
        name: The referenced name.

    Returns:
        The offset a callable reader starts from, or None when this file
        declares no such name.
    """
    escaped = re.escape(name)
    declared = re.search(rf"\bfunction\s+{escaped}\s*\(", scan)
    if declared:
        return declared.start()
    bound = re.search(rf"\b(?:const|let|var)\s+{escaped}\s*(?::[^=\n]*)?=\s*", scan)
    return _skip_blank(scan, bound.end()) if bound else None


def literal_keys(body: str, source: str | None = None) -> set[str]:
    """Read the keys of every object literal in a function body.

    A key sits in exactly one place: straight after the `{` that opens its
    literal, or after a `,` at that same brace depth. The reader this replaces
    took every `identifier :` in the text, so `const cfg: string` and the `acq`
    of `raw.x ? acq : sys` were collected as page keys — and this arm is in
    `make check` and in CI, so an invented key fails the build over a body that
    reads nothing at all. The body is scanned as a literal itself: an arrow
    handing back `({ … })` gives its object over with the braces stripped.

    A KEY MAY BE QUOTED — `({ "page": … })` is the same declaration as
    `({ page: … })` — and a quote is blanked out of the scanned text, so the
    source is read alongside it. `_strip_noise` blanks IN PLACE, which is what
    makes the two line up offset for offset.

    Args:
        body: The function body, without its own braces, comments and strings
            blanked.
        source: The same body unblanked, of the same length. Omitted, a quoted
            key simply is not read.

    Returns:
        Every key name the body's object literals declare.
    """
    keys: set[str] = set()
    scan = "{" + body + "}"
    written = "{" + source + "}" if source is not None else None
    depth: list[str] = []
    expecting = False
    index = 0
    while index < len(scan):
        character = scan[index]
        if character in "{[(":
            depth.append(character)
            expecting = character == "{"
        elif character in "}])":
            if depth:
                depth.pop()
            expecting = False
        elif character == ",":
            expecting = bool(depth) and depth[-1] == "{"
        elif not character.isspace():
            named = _MEMBER_NAME.match(scan, index)
            if named is not None:
                if expecting and scan[_skip_blank(scan, named.end()):][:1] == ":":
                    keys.add(named.group(0))
                expecting = False
                index = named.end()
                continue
            expecting = False
        elif written is not None and expecting and written[index] in "\"'":
            quoted = _QUOTED_KEY.match(written, index)
            if quoted is not None and scan[_skip_blank(scan, quoted.end()):][:1] == ":":
                keys.add(quoted.group(1))
                expecting = False
                index = quoted.end()
                continue
        index += 1
    return keys


def _destructured_keys(parameters: str) -> set[str]:
    """Read the query keys a destructured parameter list binds.

    `({ page, ...rest }) => …` reads the query as surely as `raw.page` does, and
    the reader that never looked at the parameter list saw neither.

    A bound key may be QUOTED — `({ "page": asked }) => …` binds the query's
    `page` under another name — so the parameter list is read from the SOURCE
    and both spellings are collected.

    Args:
        parameters: The parameter list, without its parentheses, as written.

    Returns:
        Every name bound at a property's position.
    """
    keys: set[str] = set()
    for pattern in re.findall(r"\{([^{}]*)\}", parameters):
        for entry in pattern.split(","):
            named = re.match(r"""\s*(?:['"]([A-Za-z_$][\w$]*)['"]|([A-Za-z_$][\w$]*))""",
                             entry)
            if named:
                keys.add(named.group(1) or named.group(2))
    return keys


def validate_search_bodies(text: str) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Read every `validateSearch` member of a route file, bounded to the member.

    The file is stripped of its comments and its string literals first — a
    comment naming the member was read AS the member — and every offset below is
    taken from that stripped text, while the body is sliced from the source, so
    a `raw["page"]` still reads as the key it is.

    The search is anchored on the member and follows only what may legally sit
    there: `: (…) =>`, `: function`, the method shorthand `(…) {`, or a bare
    NAME — a reference to a function declared in the same file. The unbounded
    reader this replaces took the next `=>` ANYWHERE below the member, so a
    reference read an unrelated block. A name followed by `(` is a CALL, not a
    reference: what it hands back is decided at runtime, so the reader says it
    cannot read that member rather than measuring the callee's own body and
    counting it as this one's.

    A member that resolves to nothing is not silence: the reader says it cannot
    read it, because a body nobody read is a body nobody holds — and it says
    WHICH way it failed, a name this file declares nowhere being a different
    defect from a name declared in a shape the reader does not follow.

    Args:
        text: The route file's source.

    Returns:
        A pair — one (body, declared return type, parameter list) per member
        read, and one sentence per member whose body could not be reached.
    """
    readings: list[tuple[str, str, str]] = []
    unreadable: list[str] = []
    scan = _strip_noise(text)
    for member in re.finditer(r"\bvalidateSearch\s*[:(]", scan):
        cursor = member.end() - 1
        if scan[cursor] == "(":
            reading = _read_callable(scan, cursor)
        else:
            cursor = _skip_blank(scan, cursor + 1)
            if scan.startswith("function", cursor) or scan[cursor:cursor + 1] == "(":
                reading = _read_callable(scan, cursor)
            else:
                named = _MEMBER_NAME.match(scan, cursor)
                after = _skip_blank(scan, named.end()) if named else cursor
                if named is None:
                    reading = None
                elif scan.startswith("=>", after):
                    # A single parameter needs no parentheses: `raw => ({ … })`.
                    span = _read_body(scan, after)
                    reading = None if span is None else (span, "", named.span())
                elif scan[after:after + 1] == "(":
                    reading = None
                else:
                    declared = _declaration_of(scan, named.group(0))
                    if declared is None:
                        unreadable.append(
                            f"its validateSearch names « {named.group(0)} », which this file "
                            f"declares nowhere — the reader cannot read that body, and a body "
                            f"nobody read is a body nobody holds")
                        continue
                    reading = _read_callable(scan, declared)
        if reading is None:
            unreadable.append(
                "its validateSearch is written in a shape this reader does not follow — "
                "it cannot read that body, and a body nobody read is a body nobody holds")
            continue
        (start, end), returned, (opened, closed) = reading
        readings.append((text[start:end], returned, text[opened:closed]))
    return readings, unreadable


def navigation_page_ids(root: Path) -> list[str]:
    """Read the page ids the navigation table declares.

    IT USED TO READ THE ENGINE. `PAGES_OF()` in `engine/legacy.js` was one of
    four copies of the page list, and this reader held it against the address
    model. L15 left one table — `app/navigation.ts` — so the subject moved with
    it, and the hold is the same hold: an address with no page is an address
    leading nowhere, a page with no address is a surface nobody can link to.

    The array is extracted by counting brackets before its entries are read:
    a bare `id: "…"` pattern over the whole module would collect every other
    identifier in it, and a line-anchored one would depend on an indentation
    the formatter owns.

    Args:
        root: The directory to read.

    Returns:
        The ids, in declaration order; an empty list when the table or the
        declaration is absent.
    """
    table = root / "app" / "navigation.ts"
    if not table.is_file():
        return []
    text = table.read_text(encoding="utf-8")
    declaration = text.find("export const NAVIGATION")
    if declaration == -1:
        return []
    # THE ARRAY'S OWN BRACKET, and it is not the first one after the name. The
    # declaration is typed — `export const NAVIGATION: readonly NavigationRow[]
    # = [` — so a plain search for "[" finds the type's empty pair, balances it
    # on the very next character and reads an empty array. The reader then
    # answers « no pages » about a table that has eight, which the caller
    # reports as « reads to nothing »: loud, and it was, but only because that
    # branch exists at all.
    assigned = re.search(r"=\s*\[", text[declaration:])
    if assigned is None:
        return []
    opening = declaration + assigned.end() - 1
    depth = 0
    for offset, character in enumerate(text[opening:], opening):
        if character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
            if depth == 0:
                return re.findall(r'id:\s*"([^"]+)"', text[opening:offset])
    return []


def balanced_object(source: str, opened: int) -> str | None:
    """Returns the `{ … }` starting at `opened`, braces balanced.

    Args:
        source: The whole file's text, already stripped of comments and strings.
        opened: The offset of the opening brace.

    Returns:
        The literal including both braces, or None when it never closes — which
        the caller skips rather than handing to a walker that would raise.
    """
    depth = 0
    for at in range(opened, len(source)):
        if source[at] == "{":
            depth += 1
        elif source[at] == "}":
            depth -= 1
            if depth == 0:
                return source[opened:at + 1]
    return None


def arm_addressing(root: Path) -> int:
    """Refuse a page identity in a query, a dial in a path, an undeclared screen, or a page table nothing serves.

    Invariant 1 says the URL and the interface never contradict each other, and
    D1 says which half carries what: the PATH carries the identity — which thing
    is being looked at — and the QUERY carries the state — how it is being
    looked at. `/library/breaking-bad?sort=recent`, never `?page=lib` and never
    `/library/sort/recent`.

    R69 checks this at runtime, in a browser, over the states it drives. This
    checks it offline, over the SOURCE, on every `make check`. The two do not
    overlap: a rule reads what the interface DID, this reads what it is allowed
    to declare, and the cheaper of the two to act on is this one.

    It is an ARM of `check-frontend-boundaries.py`, not a second script, and
    that is L02's lesson paid for once already — a guard nobody runs proves
    nothing. It lives in its own FILE because of a ceiling, and the distinction
    matters: one entry point, one exit code, one thing to remember to run.

    It also holds the SCREEN paths, and that is a contract with three ends: the
    `SCREEN_PARENTS` table declares them, the route files serve them, and this
    reads both and refuses a difference. A screen is a layer over a page rather
    than a page of its own, so a route the table does not carry resolves to the
    not-found page underneath the screen — invisible until the screen closes,
    which is why an offline reader is what catches it. The table's VALUES are
    held too: the page a screen belongs to has to be a page `PAGE_PATHS`
    carries, or the screen closes onto a surface nothing can draw.

    And the PAGES, against the engine that draws them: `PAGE_PATHS` says which
    path names a page, `PAGES_OF()` says which pages exist, and a page in one
    and not the other is either an address leading nowhere or a surface nobody
    can link to. The not-found page is the engine's alone — it names a surface
    rather than a place, and composes the address it was asked for.

    Args:
        root: The directory to read.

    Returns:
        The number of violations.
    """
    violations = []
    model = root / "lib" / "addresses.ts"
    declaration = model.read_text(encoding="utf-8") if model.is_file() else ""
    # The dial names come from the model itself, never from a list written
    # here: a second list is how the two drift, and this one would drift
    # silently because nothing renders it.
    dials = set(re.findall(r'parameter:\s*"([^"]+)"', declaration))
    dials.update(re.findall(r'PANEL_PARAMETER = "([^"]+)"', declaration))
    pages = set(re.findall(r'^\s{2}(\w+):\s*"/', declaration, re.M))
    # The same reading, one level over: the page table's VALUES are the paths a
    # page claims, and the screen table's entries are the paths a screen does.
    page_paths = set(re.findall(r'^\s{2}\w+:\s*"(/[^"]*)"', declaration, re.M))
    # The screen table is read as PAIRS — the path a screen answers and the
    # page it belongs to. The parent is half the declaration: a screen resolves
    # to it, and a page nobody serves put underneath one is the not-found
    # surface again, only spelled differently.
    screen_parents = dict(re.findall(r'^\s{2}"(/[^"]*)":\s*"(\w+)"', declaration, re.M))
    screen_paths = set(screen_parents)
    # The page table read as PAIRS as well: a path the table promises and no
    # route file answers is an address that reaches the not-found page, and
    # only the pair can name the page it was promised for.
    page_addresses = dict(re.findall(r'^\s{2}(\w+):\s*"(/[^"]*)"', declaration, re.M))

    # The model is the whole of what this arm reads, so a tree without it — or
    # a model that reads to nothing — must not read clean: a reader that stays
    # green over a tree it cannot read is the failure `check-frontend-boundaries.py`'s `arm_cycles` names. The
    # route scan below still runs, so the summary always describes what was
    # actually read.
    if not model.is_file():
        violations.append(
            "lib/addresses.ts: the address model is missing — the arm has nothing "
            "to read, and a reader that stays green over a tree it cannot read is "
            "the failure `check-frontend-boundaries.py`'s `arm_cycles` names")
    elif not pages or not dials:
        violations.append(
            f"lib/addresses.ts: the address model reads {len(pages)} page(s) and "
            f"{len(dials)} dial(s) — a gutted model is the same blindness as a "
            f"missing one")

    routes = root / "routes"
    files = sorted(routes.glob("*.tsx")) + sorted(routes.glob("*.ts")) if routes.is_dir() else []
    served = set()
    bodies_read = 0
    for file in files:
        module = file.relative_to(root).as_posix()
        text = file.read_text(encoding="utf-8")
        for path in re.findall(r'^\s*path:\s*"([^"]+)"', text, re.M):
            served.add(path)
            # A dial promoted into the path — the shape D1 names and forbids.
            for segment in [s for s in path.split("/") if s and not s.startswith("$")]:
                if segment in dials:
                    violations.append(
                        f'{module}: "{path}" puts the dial « {segment} » in the PATH — '
                        f"a dial is state, and state travels in the query")
        # A page identity declared as a search parameter — the shape D1
        # replaced. `page` by name, and any id the page table carries.
        #
        # Read out of the `SearchParams` BODY rather than line by line: these
        # types are written on ONE line as often as on several, and a
        # line-anchored pattern saw only the first key. It was written that way
        # first, and the mutation that puts `page` back went straight past it —
        # a guard that reads half of what it claims to read is the shape this
        # whole file exists to refuse.
        declared = set()
        for body in re.findall(r"type\s+\w*SearchParams\w*\s*=\s*\{([^}]*)\}", text, re.S):
            declared.update(re.findall(r"(\w+)\s*\??\s*:", body))
        for name in re.findall(r'for \(const name of \[([^\]]*)\]', text):
            declared.update(re.findall(r'"(\w+)"', name))
        for name in sorted(declared & (pages | {"page"})):
            violations.append(
                f"{module}: declares « {name} » as a search parameter — "
                f"a page is an identity, and identity travels in the path")

        # The same declaration written INLINE in `validateSearch`, with no
        # named type to read: `validateSearch: (raw) => ({ page: … })`. The
        # named-type reader above saw only declared types, so a route reading a
        # page id straight out of the raw query escaped it entirely. The body is
        # read BOUNDED to its own member, and then everything it reads, returns,
        # names as its return type or binds in its parameters is collected. A
        # member whose body cannot be reached is a violation in its own right,
        # because a reader silent over what it could not read is the blindness
        # this file exists to refuse.
        inline = set()
        readings, unreadable = validate_search_bodies(text)
        bodies_read += len(readings)
        for sentence in unreadable:
            violations.append(f"{module}: {sentence}")
        for body, returned, parameters in readings:
            # The body is the SOURCE slice, so a quoted key still reads as one;
            # everything that scans for CODE reads it with its noise blanked.
            code = _strip_noise(body)
            inline.update(re.findall(r"""raw\s*(?:\?\.)?\[\s*['"](\w+)['"]\s*\]""", body))
            inline.update(re.findall(r"raw\s*\??\.\s*(\w+)", code))
            inline.update(re.findall(r"read\.(\w+)\s*=", code))
            inline.update(literal_keys(code, body))
            inline.update(_destructured_keys(parameters))
            # A return type written INLINE declares its keys right here rather
            # than under a name — and a name carries no colon, so one read
            # serves both shapes.
            inline.update(re.findall(r"(\w+)\s*\??\s*:", returned))
            for named in re.findall(r"\w+", returned):
                for shape in re.findall(
                        rf"type\s+{re.escape(named)}\s*=\s*\{{([^{{}}]*)\}}", text, re.S):
                    inline.update(re.findall(r"(\w+)\s*\??\s*:", shape))
        for name in sorted(inline & (pages | {"page"})):
            violations.append(
                f"{module}: reads « {name} » inline in its validateSearch — "
                f"a page is an identity, and identity travels in the path")

    # AND THE NAVIGATIONS THEMSELVES, wherever they are written. Everything
    # above reads `routes/`, which is where an address is DECLARED — and D1 is
    # broken just as easily where one is CONSTRUCTED. `toFollows()` in
    # `features/acquisition/add-screen.tsx` navigated with
    # `search: { page: "acq", tab: "now" }`, carrying the page's identity in the
    # query, inside a feature file no reader here reached: the rule was
    # enforced by a human diff and by nothing else (B-051).
    #
    # WHAT IS READ: the `search:` object of any `go(…)` or `navigate(…)` call,
    # anywhere under the tree except `routes/` (already covered above) and the
    # dying engine (which has no router). The object is bounded to its own
    # braces, so a key three properties later in an unrelated literal is not
    # read as a search parameter.
    #
    # WHAT IS NOT READ: a search object built elsewhere and passed in by name.
    # Following that needs the scopes, not the text, and the shape met in the
    # field is the literal — which is also the shape somebody writes without
    # thinking about D1.
    # THE TEXT IS STRIPPED FIRST, and the KEYS ARE READ BY THE BRACE WALKER —
    # both tools this module already owned, and the first version of this reader
    # used neither.
    #
    # Unstripped, `go(` matched NINE COMMENT LINES out of twenty-two, so the
    # printed count was 2.2x the truth while the register cited it as the
    # coverage proof; and the mirror defect was live — a doc comment mentioning
    # `go()` within four hundred characters of an ordinary
    # `fetchThings({ search: { page: 2 } })` turned pagination into a D1 breach.
    #
    # `[^{}]*` was worse: the comment claimed the object was « bounded to its own
    # braces » and the class refuses ANY brace, so a NESTED value made the whole
    # match fail and the navigation was skipped in silence —
    # `search: { filters: { kind }, page: "acq" }` read clean.
    #
    # `routes/` is read here TOO. The first version skipped it saying « already
    # covered above », and the routes half reads `path:` declarations and
    # `validateSearch` bodies — never a `go()` call. A route file is exactly
    # where someone composing an address is most likely to write one.
    navigation_calls = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
            continue
        relative = path.relative_to(root)
        if relative.parts[0] == "engine":
            continue
        body = _strip_noise(path.read_text(encoding="utf-8"))
        for call in re.finditer(r"\b(?:go|navigate)\s*\(", body):
            navigation_calls += 1
            window = body[call.end():call.end() + 400]
            searched = re.search(r"search\s*:\s*(\{)", window)
            if not searched:
                continue
            # THE OBJECT IS TAKEN WHOLE, from the full body and not from the
            # window. `literal_keys` walks braces and raises on a literal that
            # never closes, which is what a 400-character slice hands it.
            literal = balanced_object(body, call.end() + searched.start(1))
            if literal is None:
                continue
            # WITHOUT ITS OWN BRACES, and with no second argument: the body is
            # already stripped, and `source` must be the SAME text at the SAME
            # length — a file name there is an IndexError, which is how this
            # call announced itself.
            keys = literal_keys(literal[1:-1])
            for name in sorted(keys & (pages | {"page"})):
                line = body.count("\n", 0, call.start()) + 1
                violations.append(
                    f"{relative}:{line}: navigates with « {name} » in its "
                    "search object — a page is an identity, and identity "
                    "travels in the PATH (D1). The address model already "
                    "declares the page's own path; use it, and leave the query "
                    "for how the page is being looked at.")

    # A route that is neither a page's path nor the root is a SCREEN, and the
    # model has to say so — the two ends are compared, never merged.
    screen_routes = {path for path in served if path not in page_paths and path != "/"}
    for path in sorted(screen_routes - screen_paths):
        violations.append(
            f'lib/addresses.ts: "{path}" is served by a route and declared by no SCREEN_PARENTS '
            f"entry — it would resolve to the not-found page underneath its screen")
    for path in sorted(screen_paths - screen_routes):
        violations.append(
            f'lib/addresses.ts: SCREEN_PARENTS declares "{path}", which no route serves — '
            f"a declaration outliving its route is how the table stops describing the tree")
    for path, parent in sorted(screen_parents.items()):
        if parent not in pages:
            violations.append(
                f'lib/addresses.ts: SCREEN_PARENTS puts « {parent} » under "{path}", and '
                f"PAGE_PATHS carries no such page — the screen would close onto a page "
                f"nothing can draw or address")
    for page, path in sorted(page_addresses.items()):
        if path not in served:
            violations.append(
                f'lib/addresses.ts: PAGE_PATHS gives the page « {page} » the address "{path}", '
                f"which no route file serves — the address the table promises reaches the "
                f"not-found page instead")

    # And the PAGES themselves, against the table that declares them. The
    # address model says which path names a page; `app/navigation.ts` says
    # which pages exist. A page in one and not the other is an address leading
    # nowhere or a surface nobody can link to — invisible either way until
    # someone types the address, which is the case an offline reader is for.
    # The not-found page is the one id that is the table's alone: it names a
    # surface rather than a place, so it has no path by design — it composes
    # the address it was asked for.
    declared_not_found = set(re.findall(r'NOT_FOUND_PAGE = "([^"]+)"', declaration))
    table_pages = set(navigation_page_ids(root))
    if table_pages:
        for page in sorted(table_pages - pages - declared_not_found):
            violations.append(
                f'app/navigation.ts: the table declares the page « {page} », which '
                f"PAGE_PATHS gives no address — a surface nobody can link to")
        for page in sorted(pages - table_pages):
            violations.append(
                f'lib/addresses.ts: PAGE_PATHS declares an address for « {page} », which '
                f"the navigation table does not carry — an address leading nowhere")
    elif (root / "app" / "navigation.ts").is_file():
        violations.append(
            "app/navigation.ts: the table reads to nothing — the page list cannot be "
            "held against the address model, and a reader that stays green over a "
            "declaration it cannot read is the failure `check-frontend-boundaries.py`'s "
            "`arm_cycles` names")

    print(f"  addressing: {len(files)} route file(s), {len(dials)} dial(s), "
          f"{len(pages)} page(s) against {len(table_pages)} the table declares, "
          f"{len(screen_paths)} screen(s), {bodies_read} validateSearch body(ies) read, "
          f"{navigation_calls} navigation call site(s) read, "
          f"{len(violations)} violation(s)")
    for entry in violations:
        print("    " + entry, file=sys.stderr)
    return len(violations)
