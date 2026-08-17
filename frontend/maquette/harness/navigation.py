"""R76 — the shell owns navigation through one door, and every call through
it is its own history entry.

`go()` is the ONLY function in `design/src/` allowed to call
`routeur.navigate()` (Task 9's comment states the law: the router library
batches its commits into a microtask, so two writes issued in the same task
would merge into one entry unless something flushes between them — and the
legacy unwinding logic COUNTS entries). A second call site calling
`navigate()` on its own, without the same immediate `historique.flush()`,
would silently start losing history depth under exactly the condition that
matters most: two navigations decided in the same synchronous handler.

What this holds to:

1. `navigate(` appears in `design/src/` exactly once, comments blanked, and
   that one call sits inside `go()`'s own body — a source-level count,
   the same discipline R74 already holds the legacy engine's raw
   `history.*` calls to.
2. A round trip through the single door — `__ecrans.profil(t)` (the bridge
   a legacy call site uses) onto the screen, then a navigation back to `/`
   — writes ONE entry per call and back walks them in reverse. `go()`
   itself is not exposed to `window` (by design — it is a module export,
   not a debugging hook), so the return leg is driven on `window.__routeur`
   directly: the SAME router instance `go()` closes over, given the
   SAME two-line body (`navigate()` then `history.flush()`) it runs.
   Walking back is judged by the screen's OWN observed state at each stop,
   never by `history.length` — a count that would still look right even if
   two pushes had merged into one and a third, unrelated entry happened to
   sit underneath.
3. Two `__ecrans.profil(...)` calls issued in the SAME task — no `await`
   between them — still produce TWO separate entries, walked back one at a
   time and judged the same way: by which title's screen the walk reveals,
   not by a length that a merge would not visibly change.
"""
import asyncio
import json
import pathlib
import re
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, Journal, open_page

DESIGN_SRC = ROOT / "design" / "src"

TITLE = "Silo"
OTHER_TITLE = "House of the Dragon"

SCREEN_STATE = """() => {
  const screen = document.querySelector('.screen.open');
  return {
    open: !!screen,
    key: screen?.dataset.cle ?? null,
    pathname: location.pathname,
  };
}"""


def without_line_comments(source):
    """Blanks `//` line comments in hand-written TypeScript source.

    `design/src/` is authored directly — no minifier, no dense regular
    expressions squeezed onto one line — so a per-line, quote-tracking scan
    telling a `//` that opens a comment from one sitting inside a string or
    template literal is enough here; R74's fuller lexer answers a question
    this smaller, human-written source never asks (a multi-line template
    literal spanning a `//` is not a shape any file below has today, and
    this function does not claim to survive one).

    Args:
        source: TypeScript, as text.

    Returns:
        The same text with every `//…` line-comment tail blanked.
    """
    lines = []
    for line in source.splitlines():
        quote = None
        i = 0
        while i < len(line):
            c = line[i]
            if quote:
                if c == "\\" and i + 1 < len(line):
                    i += 2
                    continue
                if c == quote:
                    quote = None
                i += 1
                continue
            if c in "\"'`":
                quote = c
                i += 1
                continue
            if line[i : i + 2] == "//":
                line = line[:i]
                break
            i += 1
        lines.append(line)
    return "\n".join(lines)


def count_navigate_outside_go(design_src):
    """Counts `navigate(` calls under `design/src/`, and how many sit
    outside `go()`'s own body in `shell.tsx`.

    Args:
        design_src: The `design/src/` directory.

    Returns:
        `(total, outside_go)` — the total call count after comments are
        blanked, and how many of those are NOT inside `export function
        go(`'s body.
    """
    total = 0
    outside_go = 0
    files = sorted(design_src.rglob("*.ts")) + sorted(design_src.rglob("*.tsx"))
    for file in files:
        cleaned = without_line_comments(file.read_text(encoding="utf-8"))
        positions = [m.start() for m in re.finditer(r"\bnavigate\(", cleaned)]
        total += len(positions)
        if file.name != "shell.tsx":
            outside_go += len(positions)
            continue
        start, end = go_body_bounds(cleaned)
        outside_go += sum(1 for pos in positions if not (start >= 0 and start <= pos <= end))
    return total, outside_go


def go_body_bounds(cleaned):
    """Finds `go()`'s own body span, braces balanced.

    The parameter list is itself an object type literal (`vers: {…}`) — its
    braces close and reopen before the function body's own `{` is reached,
    so the boundary cannot be the first `\n}` after the signature; that
    matches the PARAMETER type's closing brace, not the body's. This walks
    parens first to find where the parameter list ends, then walks braces
    from the function body's own opening brace to find where it ends.

    Args:
        cleaned: Comment-blanked TypeScript source.

    Returns:
        `(start, end)` character offsets spanning `go()`'s body
        (inclusive of both braces), or `(-1, -1)` if not found.
    """
    start = cleaned.find("export function go(")
    if start < 0:
        return -1, -1
    depth, i = 0, cleaned.index("(", start)
    while i < len(cleaned):
        if cleaned[i] == "(":
            depth += 1
        elif cleaned[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    body_start = cleaned.index("{", i)
    depth, j = 0, body_start
    while j < len(cleaned):
        if cleaned[j] == "{":
            depth += 1
        elif cleaned[j] == "}":
            depth -= 1
            if depth == 0:
                return body_start, j
        j += 1
    return body_start, len(cleaned)


async def main():
    journal = Journal("R76 — navigation through one door")

    # ─── Hold 1: one door, source-checked ──────────────────────────────
    total, outside_go = count_navigate_outside_go(DESIGN_SRC)
    journal.check(
        "navigate( appears only inside go()'s body",
        total == 1 and outside_go == 0,
        f"{total} call(s) in total, {outside_go} outside go()")

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")

        # ─── Hold 2: one entry per call, walked back in reverse ────────
        ctx, pg = await open_page(browser)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        start_point = await pg.evaluate(SCREEN_STATE)
        journal.check("the starting point has no screen open",
                      not start_point["open"], start_point["pathname"])

        await pg.evaluate(f"()=>window.__ecrans.profil({json.dumps(TITLE)})")
        await pg.wait_for_timeout(300)
        on_profile = await pg.evaluate(SCREEN_STATE)
        journal.check("__ecrans.profil() opens the screen through the single door",
                         on_profile["open"] and on_profile["key"] == f"profil:{TITLE}",
                         on_profile["pathname"])

        # go() itself is not on window — its own two-line body (navigate,
        # then the SAME immediate flush) is run here on window.__routeur,
        # the instance go() closes over.
        await pg.evaluate(
            "()=>{ window.__routeur.navigate({ to: '/' }); "
            "window.__routeur.history.flush(); }")
        await pg.wait_for_timeout(300)
        back_home = await pg.evaluate(SCREEN_STATE)
        journal.check("a go() to « / » closes the screen and writes the address",
                         not back_home["open"] and back_home["pathname"] == "/",
                         back_home["pathname"])

        await pg.go_back()
        await pg.wait_for_timeout(300)
        first_back = await pg.evaluate(SCREEN_STATE)
        journal.check(
            "the first back finds the profile screen again (counted by observed state)",
            first_back["open"] and first_back["key"] == f"profil:{TITLE}",
            first_back["pathname"])

        await pg.go_back()
        await pg.wait_for_timeout(300)
        second_back = await pg.evaluate(SCREEN_STATE)
        journal.check("the second back leaves the screen",
                      not second_back["open"], second_back["pathname"])
        journal.check("no JS error during the journey", not errors, str(errors))
        await ctx.close()

        # ─── Hold 3: two go() calls in the SAME task, two entries ───
        ctx, pg = await open_page(browser)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        # No await between the two calls: exactly the same-task condition
        # the microtask-batching risk described above concerns.
        await pg.evaluate(
            f"()=>{{ window.__ecrans.profil({json.dumps(TITLE)}); "
            f"window.__ecrans.profil({json.dumps(OTHER_TITLE)}); }}")
        await pg.wait_for_timeout(300)
        double = await pg.evaluate(SCREEN_STATE)
        journal.check(
            "two calls in the same task keep the second one",
            double["open"] and double["key"] == f"profil:{OTHER_TITLE}",
            double["pathname"])

        await pg.go_back()
        await pg.wait_for_timeout(300)
        one_back = await pg.evaluate(SCREEN_STATE)
        journal.check(
            "a first back reveals the FIRST title's entry — two entries, not one",
            one_back["open"] and one_back["key"] == f"profil:{TITLE}",
            one_back["pathname"])

        await pg.go_back()
        await pg.wait_for_timeout(300)
        two_backs = await pg.evaluate(SCREEN_STATE)
        journal.check("a second back leaves the screen",
                      not two_backs["open"], two_backs["pathname"])
        journal.check("no JS error during the two calls", not errors, str(errors))
        await ctx.close()

        await browser.close()

    journal.summary()


asyncio.run(main())
