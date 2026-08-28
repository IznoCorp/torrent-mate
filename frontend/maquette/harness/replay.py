"""R93 — a reconnect replays the gap, and never reloads to cover it.

WHAT THIS RULE IS ABOUT, and it is the second clause of L10's contract:
« reconnection and loss are handled visibly ». Handled means the gap is
RECOVERED, and the recovery is the honest one.

THE DEFECT IT REFUSES IS ONE LINE AND ALWAYS CORRECT. On reconnect, invalidate
everything. It heals every gap, it never misses an event, and it is
indistinguishable from a reload — it throws away exactly what L09 built, at the
moment the network is least able to pay for it. Nothing but a measurement
against the cache tells it apart from a precise replay: both leave the screen
right.

WHAT IT HOLDS:

  the cursor    a reconnect carries `?last_id=` naming the last event this
                client saw. Without it the gap is either lost or papered over.
  the gap       every event that happened while the socket was down arrives
                after it comes back, in order, and none arrives twice.
  the burst     a replay of several events is ONE synchronous burst, and every
                event in it is announced. Production dropped events buried in a
                batch in three separate hooks (FRONTEND-DATA-03) because they
                inspected only the newest. The shape cannot occur here — the
                relay announces per event as it arrives — and « cannot occur »
                is a claim, so it is measured.
  no reload     the reconnect itself invalidates NOTHING. Measured against the
                query cache: every entry's `dataUpdatedAt` and invalidation
                state, before the drop and after the recovery.
  the walk      connected -> reconnecting -> lost -> connected, driven by a
                server that is really unreachable, and `refused` reached by a
                4401 which does NOT retry.

WHAT IT DOES NOT READ, said before what it does:

  - It does not read WHAT an event refreshes. That is R91's, and this rule is
    green with an empty rule table on purpose: the two questions are « did the
    gap heal » and « did the right thing move », and a rule answering both
    answers neither clearly.
  - It does not read the DRAWN states. R92 reads those, by their text and their
    control. A condition string is not a surface.
  - It does not read a real network. The transport is a fake obeying
    `web-ui.md` § WebSocket Protocol; what a real socket does with proxies,
    sleep and captive portals is outside every measurement here.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, Journal, open_page

# Long enough for the first backoff delay (250 ms) plus the handshake, short
# enough that the rule costs nothing. Read from the relay rather than guessed
# would be better; it is stated here and the hold below asserts the RESULT
# (reconnected) rather than the duration, so a slow machine cannot fail it for
# being slow.
RECONNECT_WINDOW_MS = 900

# Past three failed attempts the relay stops saying « reconnecting ». Four
# failures is therefore the first moment `lost` is correct, and the sum of the
# first four backoff delays is 250 + 500 + 1000 + 2000.
LOST_WINDOW_MS = 4200


async def hold(journal):
    """Drives the relay through a loss and reads what came back."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser, **PHONE)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        present = await page.evaluate(
            "()=>Boolean(window.__relay && window.__mocks?.stream && window.__queries)")
        journal.check("the relay, the stream and the cache are all published", present)
        if not present:
            await browser.close()
            return

        observed = await page.evaluate(
            """async ({ reconnectWindow }) => {
                 const wait = (ms) => new Promise((r) => setTimeout(r, ms));
                 const stream = window.__mocks.stream;
                 // A CACHE WITH SOMETHING IN IT, or « nothing was invalidated »
                 // would be true of an empty cache and prove nothing.
                 await fetch("/api/library/categories");
                 await fetch("/api/system/services");
                 await window.__mocks.quiet();
                 const readCache = () => window.__queries.getQueryCache().getAll()
                   .map((entry) => ({
                     key: JSON.stringify(entry.queryKey),
                     updated: entry.state.dataUpdatedAt,
                     invalidated: entry.state.isInvalidated,
                   }));

                 stream.emit("PipelineStarted", {});
                 await window.__mocks.quiet();
                 const cacheBefore = readCache();

                 stream.drop(1006);
                 await wait(40);
                 const whileDown = window.__relay.condition().condition;
                 // The gap: three events the client cannot possibly have seen.
                 stream.emitBurst([
                   { type: "StepStarted" },
                   { type: "StepCompleted" },
                   { type: "ItemProgressed" },
                 ]);
                 await wait(reconnectWindow);
                 const afterRecovery = window.__relay.condition().condition;
                 const cacheAfter = readCache();
                 const addresses = stream.connections();
                 return {
                   whileDown, afterRecovery, addresses, cacheBefore, cacheAfter,
                   unmatched: window.__relay.unmatched(),
                 };
               }""",
            {"reconnectWindow": RECONNECT_WINDOW_MS})

        journal.check(
            "a drop is noticed, and the connection says so",
            observed["whileDown"] == "reconnecting",
            f"the condition went to {observed['whileDown']!r}")
        journal.check(
            "the connection comes back on its own",
            observed["afterRecovery"] == "connected",
            f"after {RECONNECT_WINDOW_MS} ms the condition is "
            f"{observed['afterRecovery']!r}")
        journal.check(
            "the reconnect carries the cursor of the last event seen",
            observed["addresses"][-1].endswith("last_id=1-0"),
            f"it asked for {observed['addresses'][-1]!r} — without the cursor the "
            "gap is either lost or papered over by invalidating everything")

        # THE GAP. Three events happened while the socket was down; the relay
        # counts every event it cannot map, so all three must appear there —
        # which is what says they were ANNOUNCED and not merely replayed onto a
        # socket nobody was reading.
        gap = observed["unmatched"]
        journal.check(
            "every event of the gap arrives, in order, exactly once",
            gap == ["PipelineStarted", "StepStarted", "StepCompleted", "ItemProgressed"],
            f"the relay announced {gap}")

        # NO RELOAD. The reconnect is the one moment a blanket invalidation
        # would be invisible — the screen looks right either way.
        before = {entry["key"]: entry for entry in observed["cacheBefore"]}
        after = {entry["key"]: entry for entry in observed["cacheAfter"]}
        moved = [key for key, entry in after.items()
                 if key in before and (entry["updated"] != before[key]["updated"]
                                       or entry["invalidated"] != before[key]["invalidated"])]
        journal.check(
            "the reconnect itself invalidates nothing",
            len(before) > 0 and moved == [],
            f"{len(before)} cache entr(ies) before the drop, {len(moved)} moved: {moved} "
            "— a reconnect that invalidates everything heals every gap and is "
            "indistinguishable from a reload")

        # THE WALK past « reconnecting », driven by a server that is really not
        # there: the connection never opens, which is a different path through
        # the client from a session being refused.
        walk = await page.evaluate(
            """async ({ lostWindow }) => {
                 const wait = (ms) => new Promise((r) => setTimeout(r, ms));
                 window.__mocks.stream.setUnreachable(true);
                 window.__mocks.stream.drop(1006);
                 await wait(lostWindow);
                 const lost = window.__relay.condition();
                 window.__mocks.stream.setUnreachable(false);
                 window.__relay.reconnect();
                 await wait(200);
                 const back = window.__relay.condition().condition;
                 return { lost, back };
               }""",
            {"lostWindow": LOST_WINDOW_MS})
        journal.check(
            "a connection that keeps failing becomes `lost`, not `reconnecting` forever",
            walk["lost"]["condition"] == "lost" and walk["lost"]["attempts"] > 3,
            f"after {LOST_WINDOW_MS} ms the condition is {walk['lost']['condition']!r} "
            f"at {walk['lost']['attempts']} attempt(s)")
        journal.check(
            "the manual retry reconnects at once",
            walk["back"] == "connected",
            f"after asking, the condition is {walk['back']!r}")

        # A REFUSAL IS NOT A CONNECTION PROBLEM, so it is not retried. A loop
        # that produces nothing and says nothing is the « rien ne se passe »
        # §8 of the constitution calls a lie by omission.
        refused = await page.evaluate(
            """async () => {
                 const wait = (ms) => new Promise((r) => setTimeout(r, ms));
                 window.__mocks.stream.refuse(true);
                 const before = window.__mocks.stream.connections().length;
                 window.__mocks.stream.drop(1006);
                 await wait(1200);
                 const state = window.__relay.condition();
                 const attemptsMade = window.__mocks.stream.connections().length - before;
                 window.__mocks.stream.refuse(false);
                 return { condition: state.condition, attemptsMade };
               }""")
        journal.check(
            "a 4401 becomes `refused`",
            refused["condition"] == "refused",
            f"the condition is {refused['condition']!r}")
        journal.check(
            "and a refusal is not retried",
            refused["attemptsMade"] == 1,
            f"{refused['attemptsMade']} connection(s) were made after the refusal — "
            "retrying an expired session is a loop that produces nothing")

        await page.evaluate("()=>{ window.__relay.reset(); window.__mocks.reset(); }")
        await context.close()
        await browser.close()
    journal.summary(errors)


def main():
    journal = Journal("R93 — a reconnect replays the gap, and never reloads to cover it")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
