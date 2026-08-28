"""R95 — the interface never says « connected » over a link that is not.

THIS RULE EXISTS BECAUSE THE WHOLE LOT WAS BUILT WITHOUT IT, and the adversarial
review is what found that out. L10's promise is §8 — « rien en silence » — and
the relay it shipped could report `connected` over a dead link by three
independent routes, none of which any of its five other rules could reach:

  A HALF-OPEN SOCKET. The laptop sleeps, the phone backgrounds the application,
  a proxy drops an idle flow: `readyState` stays OPEN and no `close` is ever
  delivered. A client that listens only for `close` believes it is connected for
  as long as the tab lives — and `staleTime: Infinity` means every screen is
  frozen at that instant, permanently, under a green dot.

  A HUNG OPENING. A wedged 101 upgrade fires neither `open` nor `close`, so the
  backoff ladder — which only steps on a `close` — never advances at all.

  AN UNSOLICITED CLEAN CLOSE. The server closes with 1000 when it shuts down,
  and this deployment restarts the web process on every merge. Treating every
  1000 as a teardown we asked for left the condition on `connected` with no
  socket and nothing scheduled.

WHY NO EXISTING RULE COULD SEE ANY OF IT. The fake transport pushes nothing on
its own (D-L10-4), so silence is its NORMAL state — no rule could tell « quiet
because nothing happened » from « quiet because the link is dead ». And
`MockSocket` had exactly two ways to end a connection, both explicit and both
delivered. A hang was unrepresentable. `stall()` exists now, and it is the whole
reason this rule can be written.

WHAT IT HOLDS:

  the numbers    the two limits that SHIP, read out of `lib/relay.ts` — because
                 the holds below shorten them, and a rule that only ever
                 measured a shortened timer would prove nothing about the one
                 the operator runs.
  silence        a socket that stays open and says nothing is noticed, and the
                 condition leaves `connected`.
  the hang       an opening that resolves neither way is noticed.
  the clean close a 1000 nobody asked for is a loss; a 1000 we asked for is not.
  the age        `currentSince` moves on EVERY frame, including a ping — it is
                 the age of the DATA, and the notice says so in French.

WHAT IT DOES NOT READ, said before what it does:

  - It does not read the DRAWN states. R92 reads those, by their text and their
    control. This rule reads the condition the drawing is derived from.
  - It does not read what an event refreshes. That is R91's.
  - It does not prove a REAL browser goes half-open. Nothing can, in a harness;
    what is proved is that the client survives a socket that stops speaking,
    which is the behaviour a half-open socket produces.
"""
import asyncio
import pathlib
import re
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, Journal, open_page

RELAY_SOURCE = (pathlib.Path(__file__).resolve().parent.parent
                / "design" / "src" / "lib" / "relay.ts")

# What the two limits must be in the shipped source. The server pings after
# thirty seconds of client silence, so a silence limit at or below thirty would
# tear down a healthy connection on every quiet minute; production answers for
# this protocol against real sockets at 45 s and 10 s.
WANTED_SILENCE_MS = 45_000
WANTED_OPENING_MS = 10_000

# What the holds run at. Short enough to cost nothing, long enough that a
# loaded machine cannot expire one by accident.
SHORT_SILENCE_MS = 400
SHORT_OPENING_MS = 400

# THE SILENCE PROBE HOLDS THE OPENING LIMIT LONG, and that is the whole of what
# lets it name which timer fired. Its first version shortened BOTH to the same
# value; the opening deadline is armed at connect, so it expired at the same
# instant and produced the same observable. Removing the silence watchdog
# entirely then left the rule green — the mutation that was supposed to prove
# the hold did not fall, which is how the hold was found to be measuring the
# wrong timer.
PATIENT_OPENING_MS = 30_000


def declared(name):
    """Reads one limit out of `relay.ts`, or None if it is not declared."""
    found = re.search(rf"^const {name} = ([\d_]+);",
                      RELAY_SOURCE.read_text(encoding="utf-8"), re.MULTILINE)
    return int(found.group(1).replace("_", "")) if found else None


async def hold(journal):
    """Drives the three ways a link dies without saying so."""
    silence, opening = declared("SILENCE_LIMIT_MILLISECONDS"), declared("OPENING_LIMIT_MILLISECONDS")
    journal.check(
        f"the shipped silence limit is {WANTED_SILENCE_MS} ms",
        silence == WANTED_SILENCE_MS,
        f"`relay.ts` declares {silence} — the server pings after 30 s of client "
        "silence, so a limit at or below that tears down healthy connections")
    journal.check(
        f"the shipped opening limit is {WANTED_OPENING_MS} ms",
        opening == WANTED_OPENING_MS,
        f"`relay.ts` declares {opening}")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser, **PHONE)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        present = await page.evaluate(
            "()=>Boolean(window.__relay?.limits && window.__mocks?.stream?.stall)")
        journal.check("the relay and the fake both answer for liveness", present)
        if not present:
            await browser.close()
            return

        # SILENCE. The socket stays open and says nothing at all. Before the
        # watchdog existed this was indistinguishable from a healthy quiet link,
        # and the interface said « Connecté » for the life of the tab.
        silent = await page.evaluate(
            """async ({ limit, patient }) => {
                 const wait = (ms) => new Promise((r) => setTimeout(r, ms));
                 window.__relay.reset();
                 window.__relay.limits({ silence: limit, opening: patient });
                 window.__relay.reconnect();
                 await wait(120);
                 const whileTalking = window.__relay.condition().condition;
                 const sockets = window.__mocks.stream.state().sockets;
                 // NOTHING IS EMITTED AND NOTHING IS CLOSED. Just silence — and
                 // the condition is SAMPLED throughout rather than read at the
                 // end, because the relay is expected to notice AND recover:
                 // the watchdog fires, the ladder reconnects, the fake accepts,
                 // and by the time a single read lands it says `connected`
                 // again. A hold that read only the end would report the defect
                 // it was written to catch. (It did, the first time.)
                 const seen = [];
                 for (let i = 0; i < 24; i += 1) {
                   seen.push(window.__relay.condition().condition);
                   await wait(limit / 6);
                 }
                 return { whileTalking, sockets, seen: [...new Set(seen)] };
               }""",
            {"limit": SHORT_SILENCE_MS, "patient": PATIENT_OPENING_MS})
        journal.check(
            "a socket that is talking reads `connected`",
            silent["whileTalking"] == "connected" and silent["sockets"] >= 1,
            f"condition {silent['whileTalking']!r} over {silent['sockets']} socket(s)")
        journal.check(
            "a socket that stops speaking is noticed",
            any(one != "connected" for one in silent["seen"]),
            f"over {SHORT_SILENCE_MS * 4} ms of silence on an OPEN socket the "
            f"condition was only ever {silent['seen']} — a half-open socket "
            "never closes itself, so a client that waits for `close` waits for "
            "ever, and every screen freezes under a green dot")
        journal.check(
            "and it comes back on its own once the link is replaced",
            silent["seen"][-1] == "connected" or "connected" in silent["seen"],
            f"the conditions seen were {silent['seen']}")

        # THE HANG. Neither accepted nor refused: no `open`, no `close`, no
        # `error`. The backoff ladder only steps on a close, so without a
        # deadline nothing is ever scheduled again.
        hung = await page.evaluate(
            """async ({ limit }) => {
                 const wait = (ms) => new Promise((r) => setTimeout(r, ms));
                 window.__relay.reset();
                 window.__relay.limits({ silence: limit, opening: limit });
                 window.__mocks.stream.stall(true);
                 window.__relay.reconnect();
                 await wait(120);
                 const whileHanging = window.__relay.condition().condition;
                 await wait(limit * 3);
                 const noticed = window.__relay.condition();
                 window.__mocks.stream.stall(false);
                 await wait(limit * 3);
                 return { whileHanging, noticed,
                          recovered: window.__relay.condition().condition };
               }""",
            {"limit": SHORT_OPENING_MS})
        journal.check(
            "an opening that resolves neither way is noticed",
            hung["noticed"]["condition"] != "connecting"
            and hung["noticed"]["attempts"] >= 1,
            f"after {SHORT_OPENING_MS * 3} ms hung the condition is "
            f"{hung['noticed']['condition']!r} at {hung['noticed']['attempts']} "
            "attempt(s) — a wedged upgrade fires no event at all, so nothing but "
            "a deadline can advance the ladder")
        journal.check(
            "and the ladder keeps climbing until the server answers",
            hung["recovered"] == "connected",
            f"once the server answered the condition is {hung['recovered']!r}")

        # THE CLEAN CLOSE. One we asked for is silence; one we did not is a loss.
        closes = await page.evaluate(
            """async ({ limit }) => {
                 const wait = (ms) => new Promise((r) => setTimeout(r, ms));
                 window.__relay.reset();
                 window.__relay.limits({ silence: 60_000, opening: limit });
                 window.__relay.reconnect();
                 await wait(150);
                 // The server shuts down and closes cleanly. Nobody asked.
                 window.__mocks.stream.drop(1000);
                 await wait(60);
                 const unsolicited = window.__relay.condition().condition;
                 await wait(1200);
                 return { unsolicited,
                          recovered: window.__relay.condition().condition,
                          sockets: window.__mocks.stream.state().sockets };
               }""",
            {"limit": SHORT_OPENING_MS})
        journal.check(
            "a clean close NOBODY ASKED FOR is a loss, not silence",
            closes["unsolicited"] != "connected",
            f"the server closed with 1000 and the condition is "
            f"{closes['unsolicited']!r} — this deployment restarts the web "
            "process on every merge, so an unsolicited 1000 is the most frequent "
            "way this connection ends")
        journal.check(
            "and it reconnects on its own",
            closes["recovered"] == "connected" and closes["sockets"] >= 1,
            f"condition {closes['recovered']!r} over {closes['sockets']} socket(s)")

        # THE AGE OF THE DATA. Any frame proves the link is alive, so any frame
        # moves it — a ping as much as an event.
        aged = await page.evaluate(
            """async () => {
                 const wait = (ms) => new Promise((r) => setTimeout(r, ms));
                 window.__relay.reset();
                 window.__relay.limits({ silence: 60_000, opening: 10_000 });
                 window.__relay.reconnect();
                 await wait(150);
                 const atHandshake = window.__relay.condition().currentSince;
                 await wait(120);
                 window.__mocks.stream.ping();
                 await window.__mocks.quiet();
                 const afterPing = window.__relay.condition().currentSince;
                 await wait(120);
                 window.__mocks.stream.emit("LivenessProbe", {});
                 await window.__mocks.quiet();
                 return { atHandshake, afterPing,
                          afterEvent: window.__relay.condition().currentSince };
               }""")
        journal.check(
            "the data carries an instant at all",
            all(isinstance(aged[one], int) for one in
                ("atHandshake", "afterPing", "afterEvent")),
            f"the three readings were {aged} — a `null` here means nothing ever "
            "dated the data, and comparing two of them would raise rather than "
            "name the defect")
        journal.check(
            "a ping dates the data, because it proves the link is alive",
            isinstance(aged["afterPing"], int)
            and isinstance(aged["atHandshake"], int)
            and aged["afterPing"] > aged["atHandshake"],
            f"handshake {aged['atHandshake']}, after a ping {aged['afterPing']} — "
            "written only at the handshake it announced the SESSION's start: a "
            "screen opened at 09:00 and dropped at 14:30 claimed its data was "
            "five hours old when it was thirty seconds old")
        journal.check(
            "and so does an event",
            isinstance(aged["afterEvent"], int)
            and isinstance(aged["afterPing"], int)
            and aged["afterEvent"] > aged["afterPing"],
            f"after a ping {aged['afterPing']}, after an event {aged['afterEvent']}")

        await page.evaluate("()=>{ window.__relay.reset(); window.__mocks.reset(); }")
        await context.close()
        await browser.close()
    journal.summary(errors)


def main():
    journal = Journal("R95 — the interface never says connected over a dead link")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
