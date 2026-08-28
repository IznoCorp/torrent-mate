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

# THE GAP IS MADE OF EVENTS NO RULE CLAIMS, and that is not a convenience. This
# rule's subject is whether the GAP HEALS and whether the reconnect ITSELF
# invalidates anything. Filling the gap with real, mapped events would make both
# measurements read the map's work instead: every one of them legitimately
# refreshes something, so « the reconnect invalidates nothing » becomes false
# for a reason that has nothing to do with reconnecting. Written with mapped
# events first, and the full suite is what caught it — the rule was green alone,
# when no feature table existed yet.
GAP_TYPES = ("GapOne", "GapTwo", "GapThree")
FIRST_TYPE = "GapZero"

# AND ONE EVENT THE MAP REALLY CLAIMS. The gap above is unmapped on purpose —
# it isolates the reconnect from the map's own work — but proving arrival only
# for events that refresh NOTHING proves it for the one category where losing
# them costs nothing. A relay that dropped every claimed event during a replay
# passed all ten holds. This one is claimed, so its key moving across the
# reconnect is what says the gap really healed.
CLAIMED_TYPE = "PipelineStarted"
CLAIMED_KEY = '["/api/pipeline/status"]'

# Past three failed attempts the relay stops saying « reconnecting ». `lost` is
# therefore correct from the FOURTH failure, which the first three delays reach:
# 250 + 500 + 1000 ≈ 1 750 ms. The window is deliberately over-generous — the
# run reports five attempts — and the comment used to say « the fourth delay »,
# which is one delay too many and would have sent a reader looking for a defect
# in the ladder rather than in the arithmetic.
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
            """async ({ reconnectWindow, first, gap }) => {
                 const wait = (ms) => new Promise((r) => setTimeout(r, ms));
                 const stream = window.__mocks.stream;
                 // A CACHE WITH SOMETHING IN IT, or « nothing was invalidated »
                 // would be true of an empty cache and prove nothing.
                 //
                 // PRIMED THROUGH THE CACHE, not through `fetch`. This block
                 // used to call `fetch("/api/library/categories")` and
                 // `fetch("/api/system/services")` and its comment claimed they
                 // established the precondition. They go through the mock seam
                 // and create NO query-cache entry at all — what satisfied
                 // `len(before) > 0` was the landing route's own mounted
                 // queries, which this rule neither names nor controls.
                 const prime = (key) =>
                   window.__queries.setQueryData(key, { primed: true });
                 prime(["/api/library/categories"]);
                 prime(["/api/system/services"]);
                 prime(["/api/pipeline/status"]);
                 await window.__mocks.quiet();
                 const readCache = () => window.__queries.getQueryCache().getAll()
                   .map((entry) => ({
                     key: JSON.stringify(entry.queryKey),
                     updated: entry.state.dataUpdatedAt,
                     invalidated: entry.state.isInvalidated,
                   }));

                 const opener = stream.emit(first, {});
                 await window.__mocks.quiet();
                 const cacheBefore = readCache();

                 const openedBefore = stream.connections().length;
                 stream.drop(1006);
                 await wait(40);
                 const whileDown = window.__relay.condition().condition;
                 // The gap: three events the client cannot possibly have seen.
                 stream.emitBurst(gap.map((type) => ({ type })));
                 await wait(reconnectWindow);
                 const afterRecovery = window.__relay.condition().condition;
                 const cacheAfter = readCache();
                 const addresses = stream.connections();
                 return {
                   whileDown, afterRecovery, addresses, cacheBefore, cacheAfter,
                   unmatched: window.__relay.unmatched(),
                   // THE CURSOR THE FIRST EVENT WAS GIVEN, rather than `1-0`
                   // written out. That literal was only ever right because
                   // `reset()` is called at the END of this rule and never at
                   // the start, so `sequence` happened to be 0 on a fresh page.
                   // Any earlier emit — a future boot-time state, another rule
                   // sharing a context — makes it `2-0` and the hold fails for a
                   // reason unrelated to the cursor.
                   opener: opener.id,
                   // AND HOW MANY SOCKETS THE WINDOW OPENED. Reading only the
                   // last address says nothing about a relay that opened five
                   // in 900 ms, which is a real transport defect nobody counted.
                   openedInWindow: stream.connections().length - openedBefore,
                 };
               }""",
            {"reconnectWindow": RECONNECT_WINDOW_MS,
             "first": FIRST_TYPE, "gap": list(GAP_TYPES),
})

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
            observed["addresses"][-1].endswith(
                f"last_id={observed['opener']}"),
            f"it asked for {observed['addresses'][-1]!r}, and the first event "
            f"was given {observed['opener']!r} — without the cursor the "
            "gap is either lost or papered over by invalidating everything")

        # THE GAP. Three events happened while the socket was down; the relay
        # counts every event it cannot map, so all three must appear there —
        # which is what says they were ANNOUNCED and not merely replayed onto a
        # socket nobody was reading.
        gap = observed["unmatched"]
        journal.check(
            "every unclaimed event of the gap arrives, in order, exactly once",
            gap == [FIRST_TYPE, *GAP_TYPES],
            f"the relay announced {gap}")
        # A SECOND WALK, because the two questions are opposites: the first
        # needs a gap that refreshes NOTHING — or « the reconnect invalidates
        # nothing » measures the map's own work — and this one needs a gap that
        # refreshes SOMETHING.
        claimed = await page.evaluate(
            """async ({ reconnectWindow, claimed, claimedKey }) => {
                 const wait = (ms) => new Promise((r) => setTimeout(r, ms));
                 const readOne = () => {
                   const entry = window.__queries.getQueryCache().getAll()
                     .find((one) => JSON.stringify(one.queryKey) === claimedKey);
                   return entry === undefined ? null
                     : `${entry.state.dataUpdatedAt}/${entry.state.isInvalidated}`;
                 };
                 const before = readOne();
                 window.__mocks.stream.drop(1006);
                 await wait(40);
                 window.__mocks.stream.emit(claimed, {});
                 await wait(reconnectWindow);
                 await window.__mocks.quiet();
                 return { before, after: readOne() };
               }""",
            {"reconnectWindow": RECONNECT_WINDOW_MS,
             "claimed": CLAIMED_TYPE, "claimedKey": CLAIMED_KEY})
        journal.check(
            "and a CLAIMED event of the gap really refreshed its key",
            claimed["before"] is not None and claimed["after"] != claimed["before"],
            f"{CLAIMED_KEY} read {claimed['before']} before the drop and "
            f"{claimed['after']} after the recovery — the unmatched "
            "list above can only ever prove arrival for events that refresh "
            "nothing, so a relay dropping every claimed event during a replay "
            "passed every hold in this file")

        # NO RELOAD. The reconnect is the one moment a blanket invalidation
        # would be invisible — the screen looks right either way.
        before = {entry["key"]: entry for entry in observed["cacheBefore"]}
        after = {entry["key"]: entry for entry in observed["cacheAfter"]}
        # `key in before` USED TO BE THE WHOLE COMPARISON, so an entry that
        # DISAPPEARED contributed nothing. `queryClient.clear()` on reconnect —
        # the most literal "reload under another name" there is, and one line to
        # write — emptied the cache and this hold reported no movement.
        # Measured: 5 entries before, 0 after, `moved == []`, PASS.
        gone = sorted(set(before) - set(after))
        moved = [key for key, entry in after.items()
                 if key in before and (entry["updated"] != before[key]["updated"]
                                       or entry["invalidated"] != before[key]["invalidated"])]
        journal.check(
            "the reconnect itself invalidates nothing, and removes nothing",
            len(before) > 0 and moved == [] and gone == []
            and observed["afterRecovery"] == "connected",
            f"{len(before)} cache entr(ies) before the drop, {len(moved)} moved "
            f"({moved}) and {len(gone)} removed ({gone}) — a reconnect that "
            "invalidates or empties the cache heals every gap and is "
            "indistinguishable from a reload. AND the reconnect must have "
            "happened: without that condition this hold passes vacuously on a "
            "loaded machine, where nothing reconnected and so nothing moved")

        journal.check(
            "and it opened ONE socket, not a storm",
            observed["openedInWindow"] == 1,
            f"{observed['openedInWindow']} socket(s) were opened in the "
            f"{RECONNECT_WINDOW_MS} ms window — reading only the last address "
            "says nothing about a relay that opened five")

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

        # THE FREEZE, AND THE THAW. A listener that throws must stop the cursor
        # — or the failed event is skipped by the next replay — and a fresh
        # connection must start it again, or the replay window grows for ever.
        # Found by mutation: removing the thaw made no rule fall.
        frozen = await page.evaluate(
            """async ({ window: reconnectWindow }) => {
                 const wait = (ms) => new Promise((r) => setTimeout(r, ms));
                 window.__relay.reset();
                 await wait(200);
                 const off = () => { throw new Error("a listener that throws"); };
                 const stop = window.__relay.subscribe(off);
                 window.__mocks.stream.emit("FreezeOne", {});
                 await window.__mocks.quiet();
                 const afterThrow = window.__relay.cursor();
                 window.__mocks.stream.emit("FreezeTwo", {});
                 await window.__mocks.quiet();
                 const stillFrozen = window.__relay.cursor();
                 stop();
                 // A fresh connection replays from the frozen id and thaws it.
                 window.__mocks.stream.drop(1006);
                 await wait(reconnectWindow);
                 window.__mocks.stream.emit("FreezeThree", {});
                 await window.__mocks.quiet();
                 return { afterThrow, stillFrozen, thawed: window.__relay.cursor() };
               }""",
            {"window": RECONNECT_WINDOW_MS})
        journal.check(
            "a listener that throws stops the cursor, and keeps it stopped",
            frozen["stillFrozen"] == frozen["afterThrow"],
            f"the cursor read {frozen['afterThrow']!r} after the throw and "
            f"{frozen['stillFrozen']!r} after the next event — a cursor that "
            "steps past a failed delivery skips it on the next replay, which is "
            "the whole reason it stops")
        journal.check(
            "and a fresh connection starts it again",
            frozen["thawed"] is not None
            and frozen["thawed"] != frozen["stillFrozen"],
            f"after the reconnect the cursor read {frozen['thawed']!r} against "
            f"{frozen['stillFrozen']!r} — without the thaw the freeze is "
            "permanent and every later reconnect re-requests the whole stream")

        await page.evaluate("()=>{ window.__relay.reset(); window.__mocks.reset(); }")
        await context.close()
        await browser.close()
    journal.summary(errors)


def main():
    journal = Journal("R93 — a reconnect replays the gap, and never reloads to cover it")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
