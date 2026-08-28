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
  5. THE STREAM. A delivery goes nowhere near `fetch`, so the request counter
     cannot see one — and between a frame arriving and the refetch it provokes
     being issued, that counter reads zero over a world that is about to
     change. It is hold 4's gap, entered from the other side, and L10 is the
     first lot where it can happen at all: until the relay existed, nothing
     could arrive while a measurement was being taken. Held three ways — a
     delivery is counted, `quiet()` loses the race against a timer while one is
     dispatched, and a burst of N leaves the counter at zero rather than at
     N - 1 or -1.
  6. The BUDGET is real and is named. `oracle.py` races the signal against
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
  - It does not read what a delivery INVALIDATES. That is R91's, measured
    against the query cache itself; this rule reads only whether the signal
    knows a delivery is in flight. A rule holding both would answer two
    questions and answer neither clearly.
  - It does not read a real network. The seam replaces `fetch` in process
    (D-L08-2's stated cost), so caching, redirects and abort signals are outside
    every measurement here.
"""
import asyncio
import pathlib
import re
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, Journal, open_page

# What `oracle.py` gives the signal before it goes on without it. Named here so
# the two cannot drift silently: a rule that measured a latency ABOVE this
# number would be measuring the budget expiring and calling it a settle.
# THE ORACLE'S OWN NUMBER, READ FROM THE ORACLE. It was written here as `2000`
# beside a comment saying « named here so the two cannot drift silently », and
# nothing read the other side: the hold below compared two constants declared
# in this same file, so it held under any value either of them took. The number
# this whole rule rests on was the one thing it did not measure.
ORACLE_SOURCE = (pathlib.Path(__file__).resolve().parent.parent / "oracle.py")
_budget = re.search(r"^NETWORK_QUIET_BUDGET_MS\s*=\s*(\d+)",
                    ORACLE_SOURCE.read_text(encoding="utf-8"), re.MULTILINE)
if _budget is None:
    raise SystemExit("R89: `NETWORK_QUIET_BUDGET_MS` is not declared in oracle.py — "
                     "this rule cannot hold a budget it cannot read.")
ORACLE_QUIET_BUDGET_MS = int(_budget.group(1))

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
        # R93 collects these and this rule did not. An uncaught exception
        # thrown inside the delivery path is reported to the page and was
        # swallowed here — and the delivery path is exactly where the counters
        # can desynchronise.
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

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

        # (5) THE STREAM. Judged the same way hold 2 is — by WHICH SETTLES
        # FIRST — and not by a stopwatch, because a race has one winner on an
        # idle machine and on a loaded one.
        #
        # THE TIMER IT RACES IS A MICROTASK CHAIN, not a `setTimeout`. The
        # delivery is released one MACROTASK after the frames go out, so a
        # `setTimeout(…, 0)` would be queued behind it and lose for a reason
        # that has nothing to do with the signal. A chain of resolved promises
        # drains entirely before any macrotask runs, which is exactly the
        # window a wrong implementation would answer inside.
        stream = await page.evaluate(
            """async () => {
                window.__mocks.reset();
                // A DELIVERY IS COUNTED WHETHER OR NOT ANYONE IS LISTENING:
                // `deliver()` wraps the push, and `push()` iterates a possibly
                // empty list of sockets. So these holds passed with ZERO
                // sockets open — with `installRelay()` deleted from the boot
                // entirely — while the one named « resolves once the FAN-OUT has
                // been issued » reported success over a fan-out that could not
                // exist. What is asserted first is that there is a client.
                const listening = window.__mocks.stream.state().sockets;
                const claimedBefore = window.__relay.unmatchedCount();
                const before = window.__mocks.inFlight();
                window.__mocks.stream.emit("SettleProbe", {});
                const during = window.__mocks.inFlight();
                let drained = 0;
                const microtasks = (async () => {
                    for (let i = 0; i < 50; i += 1) { drained += 1; await null; }
                    return "microtasks";
                })();
                const first = await Promise.race([
                    window.__mocks.quiet().then(() => "quiet"),
                    microtasks,
                ]);
                await window.__mocks.quiet();
                const after = window.__mocks.inFlight();
                return { before, during, first, after, drained, listening,
                         arrived: window.__relay.unmatchedCount() - claimedBefore };
            }""")
        journal.check(
            "there is a socket to deliver to, and the frame arrived at it",
            stream["listening"] >= 1 and stream["arrived"] == 1,
            f"{stream['listening']} socket(s) open and {stream['arrived']} frame(s) "
            "reached the relay — the counter answers for the DRIVER having been "
            "called, so without this every hold below passes over a page where "
            "nothing is delivered at all")
        journal.check("a delivery is counted while it is in flight",
                      stream["before"] == 0 and stream["during"] == 1,
                      f"inFlight() was {stream['before']} before the emit and "
                      f"{stream['during']} during it")
        journal.check(
            "quiet() does not resolve inside the delivery's own microtask window",
            stream["first"] == "microtasks",
            f"the microtask chain won: {stream['first']} "
            f"(drained {stream['drained']} turns)")
        journal.check("quiet() resolves once the fan-out has been issued",
                      stream["after"] == 0, f"inFlight() = {stream['after']}")

        # A BURST IS THE ARITHMETIC HOLD. A counter incremented once per emit
        # and released once per macrotask is right; one released per SOCKET, or
        # once for the whole burst, is off by N and the error only shows at
        # N > 1. Zero afterwards is the only answer both mistakes fail.
        burst = await page.evaluate(
            """async () => {
                window.__mocks.reset();
                const listening = window.__mocks.stream.state().sockets;
                const claimedBefore = window.__relay.unmatchedCount();
                // EVENTS NO RULE CLAIMS. The counter answers for deliveries
                // AND for requests in flight, so a mapped event adds its own
                // refetch to the number and the arithmetic this hold is about
                // stops being visible. Written with mapped events first, and
                // the full suite caught it: it read 4 for a burst of 3.
                window.__mocks.stream.emitBurst([
                    { type: "BurstOne" },
                    { type: "BurstTwo" },
                    { type: "BurstThree" },
                ]);
                const during = window.__mocks.inFlight();
                await window.__mocks.quiet();
                return { during, after: window.__mocks.inFlight(), listening,
                         arrived: window.__relay.unmatchedCount() - claimedBefore };
            }""")
        journal.check("a burst of three counts three, and settles at zero",
                      burst["during"] == 3 and burst["after"] == 0
                      and burst["listening"] >= 1 and burst["arrived"] == 3,
                      f"counted {burst['during']} during the burst and "
                      f"{burst['after']} after, over {burst['listening']} "
                      f"socket(s), with {burst['arrived']} frame(s) arriving")

        # THE COMPOSITE THE MACROTASK EXISTS FOR. Both stream holds above use
        # UNMAPPED types, for a stated reason — the arithmetic stays visible —
        # and the consequence is that the chain the macrotask protects (frame
        # arrives -> rule invalidates -> refetch is issued -> the counter sees
        # it before waiters are released) is exercised by no hold in this file.
        # It holds today by a property of the cache library's internals that
        # nothing here asserts: `invalidateQueries` -> `refetchQueries` ->
        # `fetch` is synchronous. Anything that moves the refetch onto the
        # observer-notification path — a batching wrapper, a `refetchType`
        # change, a library upgrade — lands it AFTER the release, and `quiet()`
        # resolves over a page about to change.
        mapped = await page.evaluate(
            """async () => {
                window.__mocks.reset();
                // THE DELIVERY'S OWN COST, MEASURED FIRST. `> 1` could not tell
                // one delivery plus one refetch from a delivery counted twice —
                // the burst hold pins that elsewhere, in another evaluation,
                // and nothing stated the dependency. An unmapped event gives
                // the baseline in the same breath.
                window.__mocks.stream.emit("SettleBaseline", {});
                const deliveryAlone = window.__mocks.inFlight();
                await window.__mocks.quiet();
                const base = window.__mocks.inFlight();
                window.__mocks.stream.emit("ItemDispatched", { action: "replaced" });
                const straightAway = window.__mocks.inFlight();
                await window.__mocks.quiet();
                return { base, deliveryAlone, straightAway,
                         after: window.__mocks.inFlight() };
            }""")
        journal.check(
            "a MAPPED event's refetch is counted before the delivery is released",
            mapped["base"] == 0 and mapped["after"] == 0
            and mapped["straightAway"] > mapped["deliveryAlone"],
            f"an unmapped emit costs {mapped['deliveryAlone']}; a mapped one "
            f"reads {mapped['straightAway']} immediately, {mapped['after']} once "
            "quiet — the DIFFERENCE is the refetch, counted synchronously. Equal, "
            "the refetch had not been issued yet and every measurement of a live "
            "surface would be taken mid-flight")

        # (6) the budget is stated rather than discovered. A latency above it is
        # measured mid-flight BY DESIGN, and this hold is what makes that a
        # documented limit instead of a surprise at surface ten.
        # THE BUDGET, MEASURED RATHER THAN COMPARED. This hold used to be
        # `HELD_BACK_MS < ORACLE_QUIET_BUDGET_MS` — two numbers declared in this
        # file, touching nothing running. A `quiet()` that became slower than
        # the oracle's budget would leave every hold here green while the oracle
        # timed out on all 2 871 of its measurements and took each one
        # mid-flight, which is the exact condition this rule exists to prevent.
        settled = await page.evaluate(
            """async ({ address, latency }) => {
                window.__mocks.reset();
                window.__mocks.setDefaultLatency(latency);
                const started = performance.now();
                window.fetch(address);
                await window.__mocks.quiet();
                return performance.now() - started;
            }""",
            {"address": PROBE_ADDRESS, "latency": HELD_BACK_MS})
        journal.check(
            f"the signal settles inside the oracle's {ORACLE_QUIET_BUDGET_MS} ms budget",
            settled < ORACLE_QUIET_BUDGET_MS,
            f"a request held back {HELD_BACK_MS} ms settled in {settled:.0f} ms "
            f"against a budget of {ORACLE_QUIET_BUDGET_MS} ms — past it, "
            "`oracle.py` stops waiting and measures the page in flight, on every "
            "one of its states, with nothing red anywhere")

        await page.evaluate("()=>window.__mocks.reset()")
        await browser.close()
    return errors


def main():
    journal = Journal("R89 — the quiet signal tracks what is in flight")
    errors = asyncio.run(hold(journal))
    journal.summary(errors or ())


if __name__ == "__main__":
    main()
