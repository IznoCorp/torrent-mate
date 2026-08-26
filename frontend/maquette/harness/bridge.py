"""R74 — the nav cluster is wired to the router, and the seam is now an import.

The shell is the single writer of history entries; the legacy engine keeps its
navigation LOGIC (when to push, when to unwind) and loses only its history
primitives. This rule verifies that: (a) the engine's source makes no raw
history calls that bypass the seam; (b) the journey through it (results →
sheet → back) redraws and restores state correctly; (c) deep URL entry lands on
the promised state; (d) a state-only navigation (__go) does not change history
depth; (f′) the boot handshake is real — `window.__startEngine` exists AND
the startup screen comes off on its own, before this harness ever calls
`window.__loadingDone`.

WHAT « THE BRIDGE » MEANS NOW, and it is not what it meant when this rule was
written. It was three globals — `window.__bridge`, `__screens`, `__panel` —
because a classic script inside the fragment had no other way to reach a
module. The engine is a module itself since SP4-fin, and it imports those three
names from `src/seams.ts` instead: 61 call sites, and a wrong name is a failed
BUILD rather than `undefined is not a function` on a click nobody tested.

The globals did NOT disappear, and the honest reason is that this harness uses
them — `__screens` nine times, `__panel` seven, `__bridge` twice — to drive the
app the way a legacy call site would. They are the same objects the shell fills
the imports with, so the two ways cannot disagree. What they are now is a
DRIVING SURFACE for measurement, not a bridge between two worlds; the world
they used to bridge to is gone.

The boot order used to run the other way: the engine booted itself, ahead
of the bridge, through a pre-bridge that queued the engine's writes and
replayed them once the real bridge existed (hold (e), now retired along
with that pre-bridge). The shell now creates the store and the bridge
FIRST and only then calls `window.__startEngine({ store })`, so
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
from common import (DESIGN_SOURCES, PHONE, ROOT, Journal, design_source,
                    without_comments)

# The engine may hold no history primitive of its own — the bridge is the
# only way to the single writer.
#
# THE PATTERN USED TO BE `history.<primitive>` AND THAT WAS ONLY EVER TRUE
# BECAUSE THE READ WAS NARROW. `history` is a NAME, and in `app/history-bridge.ts`
# it
# names the router's own instance (`const history = createBrowserHistory()`) —
# which is the single writer this rule exists to protect, not a breach of it.
# The moment L07 widened `DESIGN_SOURCES` onto the component tree, the old
# pattern reported two violations that were the sanctioned owner doing its job.
# A rule cannot be allowed to certify the opposite of its subject, so it is
# split in two and each half says what it means:
#
#   BROWSER  — `window.history.<primitive>`, the platform object reached
#              directly. Zero, anywhere, no exception.
#   INSTANCE — a bare `history.<primitive>`, which is the router's instance.
#              Legitimate, and ONLY in the file that creates it.
BROWSER_PRIMITIVES = (
    r"window\s*\.\s*history\s*\.\s*pushState\s*\(",
    r"window\s*\.\s*history\s*\.\s*replaceState\s*\(",
    r"window\s*\.\s*history\s*\.\s*back\s*\(",
    r"window\s*\.\s*history\s*\.\s*go\s*\(",
    r"window\s*\.\s*history\s*\.\s*forward\s*\(",
)
PRIMITIVES = (
    r"history\s*\.\s*pushState\s*\(",
    r"history\s*\.\s*replaceState\s*\(",
    r"history\s*\.\s*back\s*\(",
    r"history\s*\.\s*go\s*\(",
    r"history\s*\.\s*forward\s*\(",
)

# The one file allowed to name a history primitive, because it is the one that
# CREATES the instance. Named as a path fragment so a move is a failure rather
# than a silent pass — and it HAS moved: L09 split the shell onto five subjects
# and the history instance went with the bridge that spends it. `shell.tsx`
# imports the instance now and names no primitive on it, so this constant
# following the instance is the contract's three ends moving in one step, not
# an exemption being widened.
HISTORY_OWNER = "app/history-bridge.ts"


_journal = None


def check(name, condition, detail=""):
    return _journal.check(name, condition, detail)


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


def count_browser_primitives(source):
    """Counts the calls that reach the PLATFORM's history object directly.

    Args:
        source: JavaScript, or a document containing it, as text.

    Returns:
        How many `window.history.pushState|replaceState|back|go|forward(`
        calls the code holds, comments excluded.
    """
    cleaned = without_comments(source)
    return sum(len(re.findall(pattern, cleaned)) for pattern in BROWSER_PRIMITIVES)


def stray_instance_calls():
    """Finds files naming a history primitive that are not the owner.

    Reads each source on its own rather than the concatenation, because the
    answer is WHICH FILE — a count over the joined text can say that something
    is wrong and never say where, which is the shape of a rule nobody can act
    on.

    Returns:
        A mapping of repository-relative path to the number of bare
        `history.<primitive>` calls it holds, for every file that is not
        `HISTORY_OWNER`. Empty when the contract holds.
    """
    strays = {}
    for path in DESIGN_SOURCES:
        relative = path.relative_to(ROOT.parent.parent).as_posix()
        if relative.endswith(HISTORY_OWNER):
            continue
        cleaned = without_comments(path.read_text(encoding="utf-8"))
        count = sum(len(re.findall(pattern, cleaned)) for pattern in PRIMITIVES)
        if count:
            strays[relative] = count
    return strays


async def main():
    global _journal
    _journal = Journal("R74 — the bridge wires the nav cluster to the router")

    # ─── Hold (a): nothing reaches the platform's history object ──────
    # The engine is where the primitives would be, and it is no longer in
    # the fragment — a count taken on the fragment alone is a count of
    # nothing, which is why this reads every source the design is written in.
    browser_calls = count_browser_primitives(design_source())
    check(
        "zero window.history.* call in the design's sources",
        browser_calls == 0,
        f"{browser_calls} call(s) found",
    )

    # ─── Hold (a2): the router's instance is named in ONE file ────────
    # A bare `history.<primitive>` is the router's own instance, and that is
    # the single writer rather than a breach of it — but only where the
    # instance is created. Anywhere else is a file taking the history into its
    # own hands through a name that looks innocent.
    strays = stray_instance_calls()
    check(
        f"the router's history instance is named only in {HISTORY_OWNER}",
        not strays,
        ", ".join(f"{path} ×{count}" for path, count in sorted(strays.items())),
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        ctx = await browser.new_context(**PHONE)
        pg = await ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        # ─── Hold (f′): the boot handshake exists and fired on its own ─
        # Navigated WITHOUT going through common.open_page(): that helper calls
        # window.__loadingDone itself to get past the startup screen,
        # which would force the very effect this hold exists to observe.
        # What is measured here is whether the screen came off BEFORE this
        # harness ever touched that seam — proof the real handshake ran.
        await pg.goto("http://127.0.0.1:8899/", wait_until="load")
        probe = await pg.evaluate(
            """()=>({
                starter: typeof window.__startEngine,
                splashHidden: document.querySelector('#splash')?.hidden === true
            })"""
        )
        check(
            "window.__startEngine exists",
            probe["starter"] == "function",
            f"typeof window.__startEngine = {probe['starter']}",
        )
        check(
            "the startup screen clears on its own, before any harness call",
            probe["splashHidden"],
            f"#splash.hidden = {probe['splashHidden']}",
        )

        # Same plumbing common.open_page() would run, on the same page, now
        # that the hold above has taken its measurement: idempotent (it only
        # re-sets #splash.hidden), so calling it again here is harmless.
        await pg.evaluate("()=>window.__loadingDone?.()")
        await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
        await pg.wait_for_timeout(250)

        # ─── Hold (b): R71 journey through the bridge ──────────────────
        await pg.evaluate("()=>window.__go('acq-add-results')")
        await pg.wait_for_timeout(400)

        # The add screen left `#screen` for a real route (`/add`, rendered
        # inside `#coquille`): its results live under `[data-part="screen"][data-open]` now —
        # the FICHE this journey opens next stays fully legacy, still
        # `#screen`. Not read here (nothing has opened yet), but read
        # explicitly below once the mediaSheet is expected to have closed.
        start_state = await pg.evaluate(
            """()=>({
                screen: !!document.querySelector('[data-part="screen"][data-open]'),
                key: document.querySelector('[data-part="screen"][data-open]')?.dataset.key,
                cards: document.querySelectorAll('[data-part="result/list"] [data-part="card"]').length,
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
            """()=>{document.querySelector('[data-part="screen"][data-open] [data-part="viewport"]').scrollTop = 300;}"""
        )
        await pg.evaluate("""()=>document.querySelector('[data-part="result/list"] [data-part="card/poster"]').click()""")
        await pg.wait_for_timeout(450)

        await pg.go_back()
        await pg.wait_for_timeout(500)

        # R-7: `[data-part="screen"][data-open]` alone is AMBIGUOUS once a migrated screen and
        # the legacy `#screen` can both carry `open` at once — `#coquille`
        # mounts BEFORE the legacy fragment in DOM order, so
        # `document.querySelector` always resolves the React screen first
        # and would never surface a legacy `#screen` (the mediaSheet this
        # journey opened) that failed to close. Read explicitly here.
        back_state = await pg.evaluate(
            """()=>({
                screen: !!document.querySelector('[data-part="screen"][data-open]'),
                key: document.querySelector('[data-part="screen"][data-open]')?.dataset.key,
                cards: document.querySelectorAll('[data-part="result/list"] [data-part="card"]').length,
                query: document.querySelector('#addq')?.value,
                scroll: document.querySelector('[data-part="screen"][data-open] [data-part="viewport"]')?.scrollTop,
                legacySheetStillThere: document.querySelector('#screen').hasAttribute('data-open')
            })"""
        )

        check(
            "the back redraws the results list",
            back_state["screen"]
            and (back_state["key"] or "").startswith("add:")
            and back_state["cards"] == start_state["cards"]
            and back_state["query"] == start_state["query"],
            f"{back_state['cards']} cards · query « {back_state['query']} »",
        )
        check(
            "and the legacy mediaSheet is gone",
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
            "http://127.0.0.1:8899/media?mode=list", wait_until="load"
        )
        await pg.evaluate("()=>window.__loadingDone?.()")
        await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
        await pg.wait_for_timeout(250)

        state = await pg.evaluate(
            """()=>({
                page: state.page ?? null,
                libMode: state.libMode ?? null
            })"""
        )
        check(
            "direct entry on /media?mode=list sets the promised state",
            state["page"] == "lib" and state["libMode"] == "list",
            f"page={state['page']} libMode={state['libMode']}",
        )

        # ─── Hold (d): __go() does not change history depth ────────────
        depth_before = await pg.evaluate("()=>history.length")
        await pg.evaluate("()=>window.__go('acq-discover')")
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
