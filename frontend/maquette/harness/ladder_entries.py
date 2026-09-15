"""R188 — a layer left for an arrival KEEPS its entry, and Back reopens it.

D-L13-1, ratified by the operator. Four things can be opened from an open follow
panel — the medium's sheet, its journey, its releases and its quality profile —
and until this rule they behaved in two different ways depending on which one
was tapped. The decision settles the shape: the panel's
entry STAYS, the arrival pushes its own on top, one Back comes back to the panel
and REOPENS it, a second Back leaves for the list.

WHY THE COUNT IS THE HOLD, and not « Back closes the screen ». Every wrong shape
this replaces passes that sentence: a sibling that pops the panel's entry first
also closes its screen on one Back — it simply lands one entry too far down, on
the list, with the panel gone. What tells the shapes apart is WHERE one lands and
WHAT is open there, read as a pair, for each opener.

THE THREE READINGS PER OPENER:

  1. the arrival pushes ONE entry — `history.length` grows by exactly one, and
     the index with it. A shape that pops first grows it by none.
  2. Back ×1 lands on the panel's entry, and the panel is OPEN there. This is
     the reading D-L13-1 changes, and the one that was red for every sibling.
  3. Back ×2 lands on the list, with no panel and no screen. Two backs leave a
     medium, whatever was opened over it — « one gesture, one entry » read from
     the other end.

AND THE ACT BESIDE THEM, as its counter-hold. « Récupérer maintenant » (`take`)
arrives nowhere: it takes the medium and says so, and the panel it was pressed in
closes by unwinding its own entry — the index one lower, the length unchanged,
and one more Back leaves the list. RE-AIMED: this rule first counted `take` among
the openers and expected it to push, which no act can do without inventing a
navigation; it holds the act's own shape instead, so an act that started to
push, or to leave its entry standing, falls here by name.

WHAT IT DOES NOT DO: it names no screen's contents. Whether the sheet drew the
right medium is the sheet's own rules' business; this one holds the LADDER.
"""
import asyncio

from common import PROTOTYPE, Journal
from playwright.async_api import async_playwright

journal = Journal("R188 — one ladder shape for what a panel opens")

# The state the panel is opened from: a follows LIST, because the panel's five
# actions are the follow panel's and a follow is what it is produced for.
STATE = "acq-follows-list"

# THE FOUR OPENERS and the one act, by the attribute each emits inside the
# panel. The value is read off the drawn action rather than typed here: a title written into this
# file would be a fixture assertion wearing a hold's clothes.
OPENERS = ["take", "mediasheet", "journey", "releases", "profile"]
# The one that arrives nowhere, read against the act's shape rather than the
# arrival's.
ACTS = {"take"}

READ = """()=>({length: history.length,
                index: (history.state || {}).__TSR_index ?? null,
                panel: !!document.querySelector('#sheet')?.hasAttribute('data-open'),
                screen: !!document.querySelector('[data-part="screen"][data-open]'),
                path: location.pathname})"""


async def open_the_panel(page, title):
    """Opens the follow panel on one medium, and waits for it to stand.

    Args:
        page: The Playwright page.
        title: The medium the panel is produced for.
    """
    await page.evaluate("(t)=>window.__panel.produce('follow', t)", title)
    await page.wait_for_timeout(420)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2, is_mobile=True, has_touch=True)
        page = await context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(PROTOTYPE, wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")

        for opener in OPENERS:
            await page.evaluate("()=>window.__reset?.()")
            await page.evaluate("(s)=>window.__go(s)", STATE)
            await page.wait_for_timeout(420)
            # THE SUBJECT IS CHOSEN FOR THE OPENER, not taken as read. The
            # panel draws what a follow's own state allows — a pending one
            # offers no take, a film no journey — so the list is walked until
            # one offers the action under test. A subject picked blind made this
            # rule report « the action is not drawn » for four of its five
            # openers, which is a fixture reading wearing a hold's clothes.
            titles = await page.evaluate(
                """()=>[...document.querySelectorAll('#view [data-part="card/title"]')]
                     .map((node) => node.textContent.trim()).filter(Boolean)""")
            action = f'#sheet [data-{opener}]'
            title = None
            for candidate in titles[:8]:
                await open_the_panel(page, candidate)
                if await page.evaluate("(s)=>!!document.querySelector(s)", action):
                    title = candidate
                    break
                await page.evaluate("()=>window.__panel.close()")
                await page.wait_for_timeout(160)
            if title is None:
                journal.check(f"a follow offering « {opener} » is drawn",
                              False, f"none of {len(titles[:8])} follows offers it")
                continue

            # THE LADDER IS PUT BACK BEFORE ANYTHING IS MEASURED, and this line
            # is the whole difference between a hold and a green accident: the
            # scan above opens and closes a panel per candidate, and each of
            # those writes history. Measured without this reset, four of the
            # five openers PASSED on a ladder the scan had left one entry deep,
            # while the same four failed on a clean one.
            await page.evaluate("()=>window.__reset?.()")
            await page.evaluate("(s)=>window.__go(s)", STATE)
            await page.wait_for_timeout(420)
            await open_the_panel(page, title)

            before = await page.evaluate(READ)
            await page.click(action)
            await page.wait_for_timeout(620)
            arrived = await page.evaluate(READ)
            if opener in ACTS:
                journal.check(
                    f"« {opener} » acts and its panel's entry unwinds",
                    arrived["length"] == before["length"]
                    and arrived["index"] == (before["index"] or 0) - 1
                    and not arrived["panel"] and not arrived["screen"],
                    f"{before['length']}/{before['index']} -> "
                    f"{arrived['length']}/{arrived['index']} panel={arrived['panel']} "
                    f"screen={arrived['screen']} at {arrived['path']}")
                await page.go_back()
                await page.wait_for_timeout(520)
                left = await page.evaluate(READ)
                journal.check(
                    f"and one Back after « {opener} » leaves the list, reopening nothing",
                    # The index is not compared with a number: below the list
                    # stands the exit guard, which pushes its own entry back.
                    left["index"] != before["index"]
                    and not left["panel"] and not left["screen"],
                    f"panel={left['panel']} screen={left['screen']} "
                    f"index={left['index']} at {left['path']}")
                continue
            journal.check(
                f"« {opener} » pushes ONE entry and leaves the panel's own below",
                arrived["length"] == before["length"] + 1
                and arrived["index"] == (before["index"] or 0) + 1,
                f"{before['length']}/{before['index']} -> "
                f"{arrived['length']}/{arrived['index']} at {arrived['path']} "
                "— a shape that pops the panel's entry first grows neither")

            await page.go_back()
            await page.wait_for_timeout(520)
            back_once = await page.evaluate(READ)
            journal.check(
                f"one Back from « {opener} » lands on the panel, open",
                back_once["panel"] and not back_once["screen"],
                f"panel={back_once['panel']} screen={back_once['screen']} "
                f"index={back_once['index']} at {back_once['path']} — D-L13-1: "
                "the entry a layer left for an arrival reopens the layer")

            await page.go_back()
            await page.wait_for_timeout(520)
            back_twice = await page.evaluate(READ)
            journal.check(
                f"and a second Back leaves « {opener} » for the list",
                not back_twice["panel"] and not back_twice["screen"],
                f"panel={back_twice['panel']} screen={back_twice['screen']} "
                f"index={back_twice['index']} at {back_twice['path']}")

        journal.check("no error was raised", not errors, " · ".join(errors[:3]))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
