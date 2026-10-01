"""R503 — a block the engine lifts leaves « À traiter » on its own, and says so there (Q7).

Q7 of 2026-10-01: « le pipeline REPREND DE LUI-MÊME dès que le moteur voit la
cause levée, et la carte part ». DECIDED 5 = B: the existing message says it,
on « À traiter » only, one per lift — « This City Is Ours est reparti »,
« 3 acquisitions sont reparties ». The engine decides the lift and emits the
live event that invalidates the queue (BK2); the interface computes nothing.

What this holds:

1. from `acq-card-deferred-space`, the engine lifts the block (`liftBlock`, which
   emits the live event): with no gesture the card is gone from « À traiter »,
   the tab's count and the badge −1, and the message says it left;
2. the card stands in « En cours », the rung it stopped on running (`now`);
3. one cause lifted for many cards (qBittorrent back, `liftCause`): every card
   it held leaves at once, ONE message counts them, and the card held by
   another cause stays;
4. a lift while he is on another page says nothing there; the badge drops;
5. the journey keeps the trace: « bloqué — … » then « repris », with their times;
6. the named states `acq-block-lifted`, `acq-block-lifted-many`,
   `acq-block-lifted-journey` and `acq-resumed-message` exist and show it.

Red before the lot's phase 4: no lift exists in the mock (DESIGN § 4).
"""
import asyncio
import json
import pathlib

from common import ACTED, PANEL_IN, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
ACQUISITION = WORDS["screens"]["acquisition"]
LADDER = WORDS["surfaces"]["ladder"]
ONE = ACQUISITION.get("resumedOne", "<no copy>")
MANY = ACQUISITION.get("resumedMany_other", ACQUISITION.get("resumedMany", "<no copy>"))
BLOCKED_LINE = LADDER.get("blockedLine", "<no copy>").split("{{")[0].strip()
RESUMED_LINE = LADDER.get("resumedLine", "<no copy>")

SUBJECT = "This City Is Ours"
# The cards qBittorrent's outage holds on `acq-block-lifted-many`, and the one
# another cause holds.
HELD_BY_CLIENT = ["Silo|S03", "President Curtis", "Furious"]

TODO_KEYS = """() => [...document.querySelectorAll('#view [data-region="acquisition/body"] [data-part="card"]')]
  .map(card => card.dataset.acquisition)"""
TODO_COUNT = """() => {
  const count = document.querySelector('[data-acqtab="todo"] [data-part="segment/count"]');
  return count ? Number(count.textContent.trim()) : 0;
}"""
BADGE = """() => {
  const badge = document.querySelector('#nav button[data-page="acq"] [data-part="shell/tab-badge"]');
  return badge ? Number(badge.textContent.trim()) : 0;
}"""
MESSAGE = """() => {
  const host = document.querySelector('#toast');
  return host && host.dataset.shown !== undefined ? document.querySelector('#toastmsg').textContent.trim() : '';
}"""
RUNG = """(title) => {
  const queue = window.__queries?.getQueryData(['/api/acquisition/to-handle', 'loaded']) || {};
  const card = [...(queue.inFlight || []), ...(queue.arrivals || [])].find(one => one.title === title);
  const rung = (card?.ladder || []).find(one => one.rung === 'arrived');
  return rung ? {state: rung.state, reason: rung.reason ?? null} : null;
}"""
JOURNEY = """() => [...document.querySelectorAll('#sheet[data-open] [data-part="key-value"]')].map(row => row.textContent.replace(/\\s+/g, ' ').trim())"""


async def go(page, journal, state):
    """Asks for a named state and holds that it exists."""
    answer = await page.evaluate(
        "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
    await page.wait_for_timeout(SETTLED)
    journal.check(f"the named state {state} exists", answer is None, answer or "")


async def on_todo(page):
    """A finger on « À traiter »'s tab, its message closed."""
    await page.locator("[data-acqtab=todo]").first.tap()
    await page.wait_for_timeout(ACTED)
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(SETTLED)


async def lift(page, script):
    """The engine lifts — no gesture: the mock's lift, and its live event drained."""
    await page.evaluate(f"async ()=>{{ {script}; await window.__mocks.quiet(); }}")
    await page.wait_for_timeout(ACTED)


async def main():
    journal = Journal("R503 — a block the engine lifts leaves « À traiter » on its own")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── 1–2. one lift, on « À traiter » ────────────────────────────────
        await go(page, journal, "acq-card-deferred-space")
        await on_todo(page)
        before = {"keys": await page.evaluate(TODO_KEYS), "tab": await page.evaluate(TODO_COUNT),
                  "badge": await page.evaluate(BADGE)}
        await lift(page, f"window.__mocks.liftBlock({json.dumps(SUBJECT)})")
        after = {"keys": await page.evaluate(TODO_KEYS), "tab": await page.evaluate(TODO_COUNT),
                 "badge": await page.evaluate(BADGE), "message": await page.evaluate(MESSAGE)}
        journal.check("lifted by the engine, the card leaves « À traiter » with no gesture; the count and the badge −1",
                      SUBJECT in before["keys"] and SUBJECT not in after["keys"]
                      and after["tab"] == before["tab"] - 1 and after["badge"] == before["badge"] - 1,
                      f"before {before} · after {after}")
        said = ONE.replace("{{title}}", SUBJECT)
        journal.check(f"the message says it — « {said} »", after["message"] == said, repr(after["message"]))
        await page.locator("[data-acqtab=now]").first.tap()
        await page.wait_for_timeout(ACTED)
        drawn = await page.evaluate(TODO_KEYS)
        rung = await page.evaluate(RUNG, SUBJECT)
        journal.check("it stands in « En cours » again, the rung it stopped on running, no cause left",
                      SUBJECT in drawn and rung == {"state": "now", "reason": None}, f"{drawn} · {rung}")

        # ── 3. one cause, many cards ───────────────────────────────────────
        await go(page, journal, "acq-block-client-unreachable")
        await page.evaluate("()=>window.__mocks.poseBlock('This City Is Ours','insufficient_space')")
        await page.evaluate("()=>window.__queries.invalidateQueries({queryKey:['/api/acquisition/to-handle']})")
        await on_todo(page)
        held = await page.evaluate(TODO_KEYS)
        await lift(page, "window.__mocks.liftCause('client_unreachable')")
        left = await page.evaluate(TODO_KEYS)
        message = await page.evaluate(MESSAGE)
        gone = [key for key in HELD_BY_CLIENT if key in held and key not in left]
        journal.check("qBittorrent back: every card it held leaves at once; the one under another cause stays",
                      gone == HELD_BY_CLIENT and SUBJECT in left, f"held {held} · left {left}")
        said = MANY.replace("{{count}}", str(len(HELD_BY_CLIENT)))
        journal.check(f"ONE message counts them — « {said} »", message == said, repr(message))

        # ── 4. nothing said elsewhere ──────────────────────────────────────
        await go(page, journal, "acq-card-deferred-space")
        await page.locator('#nav button[data-page="lib"]').first.tap()
        await page.wait_for_timeout(ACTED)
        await page.evaluate("()=>document.querySelector('#toastx')?.click()")
        await page.wait_for_timeout(SETTLED)
        badge = await page.evaluate(BADGE)
        await lift(page, f"window.__mocks.liftBlock({json.dumps(SUBJECT)})")
        message, dropped = await page.evaluate(MESSAGE), await page.evaluate(BADGE)
        journal.check("lifted while he reads the Médiathèque: nothing is said there, the badge drops",
                      message == "" and dropped == badge - 1, f"message {message!r} · badge {badge} → {dropped}")

        # ── 5. the journey keeps the trace ─────────────────────────────────
        await go(page, journal, "acq-block-lifted-journey")
        await page.wait_for_timeout(PANEL_IN)
        lines = await page.evaluate(JOURNEY)
        blocked = next((index for index, line in enumerate(lines) if BLOCKED_LINE in line), -1)
        resumed = next((index for index, line in enumerate(lines) if line.startswith(RESUMED_LINE)), -1)
        journal.check(f"the journey says « {BLOCKED_LINE} … » then « {RESUMED_LINE} », each with its time",
                      0 <= blocked < resumed and any(ch.isdigit() for ch in lines[blocked])
                      and any(ch.isdigit() for ch in lines[resumed]), str(lines))

        # ── 6. the named states ────────────────────────────────────────────
        await go(page, journal, "acq-block-lifted")
        keys = await page.evaluate(TODO_KEYS)
        journal.check("acq-block-lifted: « En cours » holds the card again", SUBJECT in keys, str(keys))
        await go(page, journal, "acq-block-lifted-many")
        keys = await page.evaluate(TODO_KEYS)
        journal.check("acq-block-lifted-many: « À traiter » keeps only the card another cause holds",
                      SUBJECT in keys and not any(key in keys for key in HELD_BY_CLIENT), str(keys))
        await go(page, journal, "acq-resumed-message")
        await page.wait_for_timeout(ACTED)
        message = await page.evaluate(MESSAGE)
        journal.check("acq-resumed-message: the message is said on « À traiter »",
                      message == ONE.replace("{{title}}", SUBJECT), repr(message))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
