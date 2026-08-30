#!/usr/bin/env python3
"""The two properties an installed application has and a tab does not.

R109 — P27: under `display-mode: standalone` the application shows nothing that
      exists only because a browser is around it. There is exactly one such
      thing in this tree and it is the install proposal: an application already
      on the home screen asking to be put on the home screen is the clearest
      possible sign that nobody checked.

R110 — P30: the back-forward cache is not evicted. Walking out of the
      application and back must restore the page rather than rebuild it —
      `pageshow.persisted` is what says which happened.

WHY THIS FILE IS NOT CALLED `platform.py`, and it is worth a paragraph because it
cost a full `make check`. It was, for about an hour. A rule is run as
`python3 <harness>/<rule>.py`, which puts the harness directory at `sys.path[0]`,
and `tests/scripts/` puts it on the path too — so a module named after a
STANDARD LIBRARY module shadows it for everything downstream. `attr/_compat.py`
does `import platform` and asks it for `python_implementation`; it got this file
instead, and four subprocess smoke tests failed with an `AttributeError` naming
a module none of them mentions. The lesson generalises past this name: a
directory that lands on `sys.path` may not hold a file named after anything in
the standard library.

WHY R110 IS A RATCHET AND NOT A REPAIR. Nothing in the tree registers
`beforeunload` or `unload` today (`grep -rn "beforeunload\\|'unload'"
design/src` → 0), which are the two handlers that make a browser refuse to keep
a page. So this rule is expected GREEN on the day it is written, and that is the
point: it falls on the day someone adds the handler that evicts, which is a line
that looks harmless in every review. A rule that only ever confirms good news is
still the rule that catches the regression.
"""
import asyncio
import sys

from common import Journal
from playwright.async_api import async_playwright
from server import start_server

import pathlib

SERVED = pathlib.Path("/tmp/tm-refonte")
PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2,
         "is_mobile": True, "has_touch": True}


# The one platform that offers the banner with no event at all. Android needs a
# `beforeinstallprompt`, which no headless run ever fires — which is why the
# control below is an iPhone and not a desktop.
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


async def one_reading(browser, journal, errors, *, standalone):
    """Reads whether the install proposal is offered, under one display mode.

    THE MEDIA IS OVERRIDDEN IN THE PAGE, and this is stated rather than hidden
    because it decides what the reading is worth. `Emulation.setEmulatedMedia`
    does NOT carry `display-mode` in the Chrome this harness runs — measured,
    all three payload shapes, with `matchMedia("(display-mode: browser)")`
    staying true throughout. So the query is answered in the page instead.

    WHAT THAT PROVES AND WHAT IT DOES NOT. It proves the APPLICATION's own
    branch: the code deciding whether to offer an install reads this query, and
    under standalone it must not offer. It does not prove Chrome reports
    standalone correctly when really installed — Chrome's job, not this
    prototype's, and only a home screen settles it.

    Args:
        browser: A launched Playwright browser.
        journal: Where the verdicts go.
        errors: Where page errors are collected.
        standalone: Whether the application is to believe it is installed.
    """
    context = await browser.new_context(**PHONE, user_agent=IPHONE)
    page = await context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    if standalone:
        await context.add_init_script("""
            const real = window.matchMedia.bind(window);
            window.matchMedia = (query) =>
              query.includes("display-mode: standalone")
                ? {matches: true, media: query, onchange: null,
                   addEventListener(){}, removeEventListener(){},
                   addListener(){}, removeListener(){},
                   dispatchEvent(){ return false; }}
                : real(query);
        """)
    with start_server(SERVED) as port:
        await page.goto(f"http://127.0.0.1:{port}/", wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        await page.evaluate("()=>document.querySelector('#toastx')?.click()")

        # THE BANNER IS WAITED FOR AS A CONDITION, never slept on. The first
        # version used a fixed 700 ms and the control failed — not because the
        # application was wrong but because the banner had not arrived yet, and
        # a rule whose verdict depends on how fast the machine is has no verdict.
        # The two readings wait the SAME way and for the same bound, so the one
        # that expects nothing gives the banner exactly the opportunity the one
        # that expects it does.
        appeared = True
        try:
            await page.wait_for_function(
                """()=>{const bar=document.querySelector("#installbar");
                     return bar && !bar.hidden
                         && bar.getBoundingClientRect().height > 0;}""",
                timeout=6000)
        except Exception:
            appeared = False

        journal.check(
            f"the display mode really took (standalone={standalone})",
            await page.evaluate(
                """()=>matchMedia("(display-mode: standalone)").matches""") is standalone,
            "a rule under no media proves nothing")

        journal.check("the proposal exists in the document at all",
                      await page.evaluate(
                          """()=>document.querySelector("#installbar") !== null"""),
                      "#installbar")

        offered = appeared and await page.evaluate(
            """()=>{const bar=document.querySelector("#installbar");
                 if(!bar) return false;
                 const box=bar.getBoundingClientRect();
                 return !bar.hidden && box.height > 0;}""")
        if standalone:
            # THE `display-mode` BRANCH SPECIFICALLY. `install.py` already holds
            # the other one — `navigator.standalone`, which is how iOS says it —
            # so what is added here is the branch an Android or desktop install
            # takes, and which nothing read.
            journal.check(
                "an installed application is not asked to install itself",
                offered is False, f"offered={offered}")
        else:
            journal.check(
                "and a browser that is NOT installed IS asked — the control",
                offered is True,
                f"offered={offered} — without this the hold above is vacuous")
    await context.close()


async def main():
    """Runs R109 and R110.

    Returns:
        0 when both hold, 1 otherwise.
    """
    journal = Journal("R109 / R110 — standalone, and the back-forward cache")
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")

        # --- R109 (P27) — standalone hides what only a browser justifies -----
        #
        # IT IS A CONTROLLED PAIR, and it has to be. The first version asserted
        # only that the proposal was absent under standalone, and it passed with
        # the check DELETED from the application: in a plain desktop context the
        # banner never appears anyway, because Android needs a
        # `beforeinstallprompt` that never fires here. « Not offered » was
        # « never offered », and the rule was measuring nothing.
        #
        # The pair is an iPhone user agent, which is the one platform that
        # offers the banner with no event at all: WITHOUT standalone it must be
        # on screen, WITH it, gone. Only the second reading is the property; the
        # first is what makes the second mean something.
        for standalone in (False, True):
            await one_reading(browser, journal, errors, standalone=standalone)

        # --- R110 (P30) — nothing in the tree evicts the page ----------------
        #
        # WHY THIS IS A STATIC READ AND NOT A NAVIGATION, and it is a limit worth
        # stating rather than working around. Chrome refuses to keep a page in
        # the back-forward cache whenever a DevTools client is attached, and
        # Playwright is always one — measured: `pageshow.persisted` came back
        # `undefined` on a real walk out and back, with and without
        # `--enable-features=BackForwardCache`. A rule that cannot distinguish
        # « the page was rebuilt » from « this browser never keeps pages » is a
        # rule about the harness.
        #
        # So what runs here is the RATCHET, and it is the half that catches the
        # regression: the two handlers that make a browser refuse to keep a page
        # are `beforeunload` and `unload`, and the tree registers neither. That
        # is a line which looks harmless in every review, and this is what goes
        # red the day it is written. The runtime half is device-only, exercised
        # and dated like the oracle's certification — MODEL § 3.1's precedent
        # for the interaction budget, and for the same reason.
        design = pathlib.Path(__file__).resolve().parents[1] / "design" / "src"
        evictors = []
        for source in design.rglob("*"):
            if source.suffix not in (".ts", ".tsx", ".js") or not source.is_file():
                continue
            text = source.read_text(errors="ignore")
            for handler in ("beforeunload", '"unload"', "'unload'", "onunload"):
                if handler in text:
                    evictors.append(f"{source.relative_to(design)} → {handler}")
        journal.check(
            "nothing registers a handler that evicts the back-forward cache",
            not evictors, ", ".join(evictors) or "no beforeunload, no unload")

        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
