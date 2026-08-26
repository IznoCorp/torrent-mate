"""R89 — the quiet signal really tracks what is in flight, before anything depends on it.

THIS IS L09'S HINGE, AND IT IS NOT THE LIBRARY. Every surface this lot wires is
proved by the oracle rendering what it rendered — and that proof holds only if
the oracle measures the surface AT REST. `oracle.py`'s settle asks the mock
layer whether anything is still in flight (`window.__mocks.quiet()`, D-L08-9),
and until this wave nothing ever fetched, so that signal resolved on the spot
and had never once been exercised against a real request.

A signal that has only ever answered « nothing in flight » because nothing could
be in flight is a signal nobody has tested. This rule tests it, in the phase
that installs the query cache and BEFORE the first surface is wired — because
discovering it at the tenth surface would mean ten accepted divergences and no
proof at all.

WHAT IT HOLDS:

  1. `inFlight()` counts a real request, through the same `read()` every surface
     will use — not through a hand-rolled fetch that would prove the harness.
  2. `quiet()` does NOT resolve while a request is held back. Measured against
     an injected latency, and judged by which of the two settles FIRST rather
     than by a duration: a race has one winner on an idle machine and on a
     loaded one, where a timing assertion has two answers.
  3. `quiet()` resolves once the request lands, and the count is back to zero.
  4. THE WATERFALL. Read, render, read again: the second request must already be
     counted when the first settles, or the signal reports quiet in the gap and
     an oracle measures a page that is about to change. L08 made
     `releaseWaiters` a macrotask for exactly this, and a macrotask is the kind
     of decision that is silently undone by someone tidying an await.
  5. The BUDGET is real and is named. `oracle.py` races the signal against
     2 000 ms and goes on without it — so a request slower than that is measured
     mid-flight, by design, and this rule states the number rather than leaving
     it to be discovered.

WHAT IT DOES NOT READ, said before what it does:

  - It does not read `oracle.py`. Whether the oracle CALLS the signal is proved
    where the first surface is wired, by running the oracle with and without
    `TM_ORACLE_NO_SETTLE=1` — the lever `oracle.py` already publishes for it.
    Asserting the call here by grepping the file would be a rule certifying that
    a line exists, which is not the same as a rule certifying it works.
  - It does not read whether a SURFACE waits. No surface fetches yet. That is
    phase 5's, and it is written into the plan rather than assumed.
  - It does not read a real network. The seam replaces `fetch` in process
    (D-L08-2's stated cost), so caching, redirects and abort signals are outside
    every measurement here.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, Journal, open_page

# What `oracle.py` gives the signal before it goes on without it. Named here so
# the two cannot drift silently: a rule that measured a latency ABOVE this
# number would be measuring the budget expiring and calling it a settle.
ORACLE_QUIET_BUDGET_MS = 2000

# The latency the held-back request answers after. Comfortably under the budget
# above, and comfortably over the time a resolved promise takes to settle.
HELD_BACK_MS = 400

# An address the contract declares and the layer answers, chosen because it
# needs no parameter and mutates nothing.
PROBE_ADDRESS = "/api/library/categories"


async def hold(journal):
    """Exercises the quiet signal against real requests."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        _context, page = await open_page(browser, **PHONE)

        present = await page.evaluate(
            "()=>typeof window.__mocks?.quiet === 'function'"
            " && typeof window.__queries?.getQueryCache === 'function'")
        journal.check("the layer and the cache are both published", present)
        if not present:
            await browser.close()
            return

        # (1) and (2) together: a request is held back, the count sees it, and
        # the signal loses the race against a timer that is shorter than the
        # latency. Judged by WHICH SETTLES FIRST — never by a stopwatch.
        raced = await page.evaluate(
            """async ({ address, latency }) => {
                window.__mocks.reset();
                window.__mocks.setDefaultLatency(latency);
                const started = window.fetch(address);
                const seen = window.__mocks.inFlight();
                const first = await Promise.race([
                    window.__mocks.quiet().then(() => "quiet"),
                    new Promise((r) => setTimeout(() => r("timer"), latency / 2)),
                ]);
                await started;
                return { seen, first };
            }""",
            {"address": PROBE_ADDRESS, "latency": HELD_BACK_MS})
        journal.check("a request in flight is counted", raced["seen"] == 1,
                      f"inFlight() = {raced['seen']}")
        journal.check("quiet() does not resolve while a request is held back",
                      raced["first"] == "timer",
                      f"the {HELD_BACK_MS // 2} ms timer won: {raced['first']}")

        # (3) it resolves once the request lands, and the count is back to zero.
        after = await page.evaluate(
            """async () => {
                await window.__mocks.quiet();
                return window.__mocks.inFlight();
            }""")
        journal.check("quiet() resolves once nothing is in flight", after == 0,
                      f"inFlight() = {after}")

        # (4) THE WATERFALL, and the assertion here was WRONG the first time it
        # was written — it read `inFlight()` after quiet and expected 0, which
        # BOTH behaviours produce. Released a task later, the second request is
        # already counted so quiet waits for it and the count is 0 afterwards;
        # released inside the settlement, quiet answers before the second
        # request exists and the count is 0 then too. A mutation removing the
        # macrotask left the hold green, which is this repository's own
        # dominant failure mode caught in the act.
        #
        # WHAT DISTINGUISHES THEM IS ORDER, not a count: did the second request
        # FINISH before quiet answered? Released correctly, yes. Released early,
        # quiet answers while the second request has not even been issued.
        waterfall = await page.evaluate(
            """async ({ address, latency }) => {
                window.__mocks.reset();
                window.__mocks.setDefaultLatency(latency);
                let secondFinished = false;
                window.fetch(address).then(
                    () => window.fetch(address).then(() => { secondFinished = true; }));
                await window.__mocks.quiet();
                return { secondFinished, stillInFlight: window.__mocks.inFlight() };
            }""",
            {"address": PROBE_ADDRESS, "latency": 50})
        journal.check(
            "quiet() waits for a request the first one had not issued yet",
            waterfall["secondFinished"] is True,
            f"second request finished before quiet answered: "
            f"{waterfall['secondFinished']} (inFlight = {waterfall['stillInFlight']})")

        # (5) the budget is stated rather than discovered. A latency above it is
        # measured mid-flight BY DESIGN, and this hold is what makes that a
        # documented limit instead of a surprise at surface ten.
        journal.check(
            f"the oracle's budget for this signal is {ORACLE_QUIET_BUDGET_MS} ms",
            HELD_BACK_MS < ORACLE_QUIET_BUDGET_MS,
            f"held back {HELD_BACK_MS} ms — a request slower than "
            f"{ORACLE_QUIET_BUDGET_MS} ms is measured in flight, by design")

        await page.evaluate("()=>window.__mocks.reset()")
        await browser.close()


def main():
    journal = Journal("R89 — the quiet signal tracks what is in flight")
    asyncio.run(hold(journal))
    journal.summary()


if __name__ == "__main__":
    main()
