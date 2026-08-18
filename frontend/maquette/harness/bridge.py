"""R74 — the nav cluster is wired to the router, and the seam is now an import.

The shell is the single writer of history entries; the legacy engine keeps its
navigation LOGIC (when to push, when to unwind) and loses only its history
primitives. This rule verifies that: (a) the engine's source makes no raw
history calls that bypass the seam; (b) the journey through it (results →
sheet → back) redraws and restores state correctly; (c) deep URL entry lands on
the promised state; (d) a state-only navigation (__go) does not change history
depth; (f′) the boot handshake is real — `window.__demarrerMoteur` exists AND
the startup screen comes off on its own, before this harness ever calls
`window.__chargementTermine`.

WHAT « THE BRIDGE » MEANS NOW, and it is not what it meant when this rule was
written. It was three globals — `window.__pont`, `__ecrans`, `__panneau` —
because a classic script inside the fragment had no other way to reach a
module. The engine is a module itself since SP4-fin, and it imports those three
names from `src/seams.ts` instead: 61 call sites, and a wrong name is a failed
BUILD rather than `undefined is not a function` on a click nobody tested.

The globals did NOT disappear, and the honest reason is that this harness uses
them — `__ecrans` nine times, `__panneau` seven, `__pont` twice — to drive the
app the way a legacy call site would. They are the same objects the shell fills
the imports with, so the two ways cannot disagree. What they are now is a
DRIVING SURFACE for measurement, not a bridge between two worlds; the world
they used to bridge to is gone.

The boot order used to run the other way: the engine booted itself, ahead
of the bridge, through a pre-bridge that queued the engine's writes and
replayed them once the real bridge existed (hold (e), now retired along
with that pre-bridge). The shell now creates the store and the bridge
FIRST and only then calls `window.__demarrerMoteur({ magasin })`, so
nothing is queued and nothing is replayed — a module that never evaluates
simply never makes that call, and the startup screen stays up: a visible,
truthful failure rather than an app with mute verbs.

Nothing here mutates anything. The measured copy is shared by every rule
of the harness, so a rule that severed it would, on any interruption,
fail the next rule for a reason having nothing to do with what that rule
holds. Hold (e′) — that severing the copy's module entry leaves the
startup screen up, because the fail-silent path is dead — is proven by a
mutation applied by hand to the copy, outside any rule, and its outcome
is recorded in regions.json.
"""
import asyncio
import pathlib
import re
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, ROOT, Journal, design_source

# The engine may hold no history primitive of its own — the bridge is the
# only way to the single writer.
PRIMITIVES = (
    r"history\s*\.\s*pushState\s*\(",
    r"history\s*\.\s*replaceState\s*\(",
    r"history\s*\.\s*back\s*\(",
    r"history\s*\.\s*go\s*\(",
    r"history\s*\.\s*forward\s*\(",
)

# A slash opens a regular expression rather than a division when the last
# significant character before it cannot end an expression.
BEFORE_REGEX = set("(,=:[!&|?{};+-*%^~<>")
WORDS_BEFORE_REGEX = ("return", "typeof", "case", "in", "of", "new", "delete",
                    "do", "else", "void", "instanceof", "yield", "await")

_journal = None


def check(name, condition, detail=""):
    return _journal.check(name, condition, detail)


def without_comments(source):
    """Blanks out the JavaScript comments of a document, and only those.

    A stripper that knows about `//` and `/* */` alone is fail-open on this
    document, and measurably so: the engine carries URLs inside string
    literals (`"https://…"`, whose `//` would blank the rest of the line) and
    quotes inside regular-expression literals (`/[&<>"]/g`, whose `"` would
    open a string state that runs on until the file's next quote). Either
    mistake swallows the real calls that follow, so a rule counting them
    would pass by having lost its evidence rather than by finding none.

    The source is therefore walked as JavaScript: code, line comment, block
    comment, the three string kinds with their escapes, template
    substitutions (`${…}`, whose contents are code again) and regular
    expressions, told apart from division by the last significant character.

    Args:
        source: JavaScript, or a document containing it, as text.

    Returns:
        The same text with every comment character replaced by a space,
        newlines preserved so lines still line up with the original.
    """
    out = []
    i, n = 0, len(source)
    # `previous` is the last significant character of the CODE regions; it is
    # what tells a regular expression from a division.
    previous = ""
    # Brace depth inside the current code region, and the stack of depths
    # suspended by the enclosing `${` substitutions.
    depth, templates = 0, []

    def word_before(position):
        """True when a keyword ends right before `position` (regex context)."""
        prefix = source[:position].rstrip()
        return any(prefix.endswith(word)
                   and (len(prefix) == len(word)
                        or not (prefix[-len(word) - 1].isalnum()
                                or prefix[-len(word) - 1] in "_$"))
                   for word in WORDS_BEFORE_REGEX)

    while i < n:
        c = source[i]
        pair = source[i:i + 2]

        if pair == "//":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue

        if pair == "/*":
            while i < n and source[i:i + 2] != "*/":
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append("  ")
                i += 2
            continue

        if c in "\"'":
            # A single- or double-quoted string: escapes only, no nesting.
            out.append(c)
            i += 1
            while i < n and source[i] != c:
                if source[i] == "\\" and i + 1 < n:
                    out.append(source[i:i + 2])
                    i += 2
                    continue
                if source[i] == "\n":  # unterminated: do not eat the file
                    break
                out.append(source[i])
                i += 1
            if i < n and source[i] == c:
                out.append(c)
                i += 1
            previous = c
            continue

        if c == "`":
            # A template literal: runs to its closing backtick, except that
            # every `${…}` inside it is code, and is lexed as such.
            out.append(c)
            i += 1
            while i < n:
                if source[i] == "\\" and i + 1 < n:
                    out.append(source[i:i + 2])
                    i += 2
                    continue
                if source[i] == "`":
                    out.append("`")
                    i += 1
                    previous = "`"
                    break
                if source[i:i + 2] == "${":
                    out.append("${")
                    i += 2
                    templates.append(depth)
                    depth = 0
                    previous = "{"
                    break
                out.append(source[i])
                i += 1
            continue

        if c == "}" and depth == 0 and templates:
            # Closes a `${…}`: back inside the template literal that opened it.
            out.append("}")
            i += 1
            depth = templates.pop()
            while i < n:
                if source[i] == "\\" and i + 1 < n:
                    out.append(source[i:i + 2])
                    i += 2
                    continue
                if source[i] == "`":
                    out.append("`")
                    i += 1
                    previous = "`"
                    break
                if source[i:i + 2] == "${":
                    out.append("${")
                    i += 2
                    templates.append(depth)
                    depth = 0
                    previous = "{"
                    break
                out.append(source[i])
                i += 1
            continue

        if c == "/" and (previous == "" or previous in BEFORE_REGEX
                         or word_before(i)):
            # A regular expression literal: its `/` delimiters, its character
            # classes (where a `/` is literal) and its escapes.
            out.append(c)
            i += 1
            in_class = False
            while i < n and source[i] != "\n":
                if source[i] == "\\" and i + 1 < n:
                    out.append(source[i:i + 2])
                    i += 2
                    continue
                if source[i] == "[":
                    in_class = True
                elif source[i] == "]":
                    in_class = False
                elif source[i] == "/" and not in_class:
                    out.append("/")
                    i += 1
                    break
                out.append(source[i])
                i += 1
            previous = "/"
            continue

        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(0, depth - 1)
        out.append(c)
        if not c.isspace():
            previous = c
        i += 1

    return "".join(out)


def count_history_primitives(source):
    """Counts the direct history primitives left in a document's code.

    Args:
        source: JavaScript, or a document containing it, as text.

    Returns:
        How many `history.pushState|replaceState|back|go|forward(` calls the
        code holds, comments excluded and string/regex contents left alone.
    """
    cleaned = without_comments(source)
    return sum(len(re.findall(pattern, cleaned)) for pattern in PRIMITIVES)


async def main():
    global _journal
    _journal = Journal("R74 — the bridge wires the nav cluster to the router")

    # ─── Hold (a): the engine holds no primitive of its own ───────────
    # The engine is where the primitives would be, and it is no longer in
    # the fragment — a count taken on the fragment alone is a count of
    # nothing.
    calls = count_history_primitives(design_source())
    check(
        "zero direct history.* call in the design's sources",
        calls == 0,
        f"{calls} call(s) found",
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        ctx = await browser.new_context(**PHONE)
        pg = await ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        # ─── Hold (f′): the boot handshake exists and fired on its own ─
        # Navigated WITHOUT going through common.open_page(): that helper calls
        # window.__chargementTermine itself to get past the startup screen,
        # which would force the very effect this hold exists to observe.
        # What is measured here is whether the screen came off BEFORE this
        # harness ever touched that seam — proof the real handshake ran.
        await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        probe = await pg.evaluate(
            """()=>({
                starter: typeof window.__demarrerMoteur,
                splashHidden: document.querySelector('#splash')?.hidden === true
            })"""
        )
        check(
            "window.__demarrerMoteur exists",
            probe["starter"] == "function",
            f"typeof window.__demarrerMoteur = {probe['starter']}",
        )
        check(
            "the startup screen clears on its own, before any harness call",
            probe["splashHidden"],
            f"#splash.hidden = {probe['splashHidden']}",
        )

        # Same plumbing common.open_page() would run, on the same page, now
        # that the hold above has taken its measurement: idempotent (it only
        # re-sets #splash.hidden), so calling it again here is harmless.
        await pg.evaluate("()=>window.__chargementTermine?.()")
        await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
        await pg.wait_for_timeout(250)

        # ─── Hold (b): R71 journey through the bridge ──────────────────
        await pg.evaluate("()=>window.__go('acq-ajout-resultats')")
        await pg.wait_for_timeout(400)

        # The add screen left `#screen` for a real route (`/ajout`, rendered
        # inside `#coquille`): its results live under `.screen.open` now —
        # the FICHE this journey opens next stays fully legacy, still
        # `#screen`. Not read here (nothing has opened yet), but read
        # explicitly below once the fiche is expected to have closed.
        start_state = await pg.evaluate(
            """()=>({
                screen: !!document.querySelector('.screen.open'),
                key: document.querySelector('.screen.open')?.dataset.cle,
                cards: document.querySelectorAll('.reslist .card').length,
                query: document.querySelector('#addq')?.value
            })"""
        )
        check(
            "the results screen is there",
            start_state["screen"] and start_state["cards"] >= 2,
            f"{start_state['cards']} cards",
        )

        # Scrolled away from the top before leaving, so the return has a
        # position to restore and not merely a list to redraw.
        await pg.evaluate(
            "()=>{document.querySelector('.screen.open .port').scrollTop = 300;}"
        )
        await pg.evaluate("()=>document.querySelector('.reslist .poster').click()")
        await pg.wait_for_timeout(450)

        await pg.go_back()
        await pg.wait_for_timeout(500)

        # R-7: `.screen.open` alone is AMBIGUOUS once a migrated screen and
        # the legacy `#screen` can both carry `open` at once — `#coquille`
        # mounts BEFORE the legacy fragment in DOM order, so
        # `document.querySelector` always resolves the React screen first
        # and would never surface a legacy `#screen` (the fiche this
        # journey opened) that failed to close. Read explicitly here.
        back_state = await pg.evaluate(
            """()=>({
                screen: !!document.querySelector('.screen.open'),
                key: document.querySelector('.screen.open')?.dataset.cle,
                cards: document.querySelectorAll('.reslist .card').length,
                query: document.querySelector('#addq')?.value,
                scroll: document.querySelector('.screen.open .port')?.scrollTop,
                legacySheetStillThere: document.querySelector('#screen').classList.contains('open')
            })"""
        )

        check(
            "the back redraws the results list",
            back_state["screen"]
            and (back_state["key"] or "").startswith("ajout:")
            and back_state["cards"] == start_state["cards"]
            and back_state["query"] == start_state["query"],
            f"{back_state['cards']} cards · query « {back_state['query']} »",
        )
        check(
            "and the legacy fiche is gone",
            not back_state["legacySheetStillThere"],
            f"#screen open={back_state['legacySheetStillThere']}",
        )
        # The restored position is asserted, not merely collected: the record
        # says the journey holds the scroll, and a collected number nobody
        # judges is the one thing this harness exists to prevent. Same
        # tolerance as R71, which holds the same journey off the bridge.
        check(
            "with its scroll position",
            abs(back_state["scroll"] - 300) <= 40,
            f"{back_state['scroll']}px",
        )

        await browser.close()

    # ─── Hold (c): deep-URL entry ─────────────────────────────────────
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        ctx = await browser.new_context(**PHONE)
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.goto(
            "http://127.0.0.1:8899/wrapped.html?page=lib&mode=list", wait_until="load"
        )
        await pg.evaluate("()=>window.__chargementTermine?.()")
        await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
        await pg.wait_for_timeout(250)

        state = await pg.evaluate(
            """()=>({
                page: state.page ?? null,
                libMode: state.libMode ?? null
            })"""
        )
        check(
            "direct entry on ?page=lib&mode=list sets the promised state",
            state["page"] == "lib" and state["libMode"] == "list",
            f"page={state['page']} libMode={state['libMode']}",
        )

        # ─── Hold (d): __go() does not change history depth ────────────
        depth_before = await pg.evaluate("()=>history.length")
        await pg.evaluate("()=>window.__go('acq-decouvrir')")
        await pg.wait_for_timeout(400)
        depth_after = await pg.evaluate("()=>history.length")

        check(
            "window.__go() does not change the history depth",
            depth_after == depth_before,
            f"before={depth_before} after={depth_after}",
        )

        await browser.close()

    _journal.summary(errors)


asyncio.run(main())
