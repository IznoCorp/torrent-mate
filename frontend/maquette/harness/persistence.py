"""R100 — the chrome persists: one document, the same nodes, and focus survives.

THREE PROPERTIES OF `MODEL.md` § 3, AND ONE DEFECT UNDER ALL THREE.

  P1  ONE DOCUMENT. No full navigation between any two named states. It was
      true by construction and measured by nothing, which is a different thing
      from true: a single `<a href>` without a router, or one `location.assign`
      in a producer, turns a mobile application back into a website and no
      existing rule would say so.
  P2  A PERSISTENT CHROME. The tab bar's button nodes keep their identity
      across a page switch and a store bump. This was FALSE — B-231: the engine
      called `renderNav()` unconditionally from `render()`, so the bar's
      buttons were new nodes on every navigation and every simulated mutation.
  P28 FOCUS SURVIVES A REDRAW. `document.activeElement` is the same node across
      the same two events. It was false for the same reason and by the same
      mechanism: a focused button replaced by an equal one leaves focus on the
      document body, so a keyboard reader loses their place whenever a counter
      moves.

WHY P2 AND P28 ARE ONE RULE AND NOT TWO. They have one cause and one repair,
and holding them apart would let a repair satisfy one while the other stayed
broken in a way nobody was measuring. The interesting case is precisely the one
where the node LOOKS the same: an `innerHTML` rewrite produces buttons that are
identical in every respect a screenshot, a rectangle or a text assertion can
read. `isSameNode` is the only question that separates them.

WHAT IT DOES NOT READ, said before what it does:

  - It does not hold the bar's CONTENTS. Which pages sit in it, in what order,
    with which badge, is the navigation table's, and `page_host.py` holds the
    table against the address model. This rule would pass over a bar that kept
    four wrong buttons perfectly.
  - P1's walk drives the named states through `window.__go`, which is a seam
    and not a finger. A full navigation caused by a real tap on a control this
    walk never touches is outside it. What the walk DOES cover is every state
    the interface declares it can be in, which is the corpus every other rule
    here is measured over.
  - The store bump is `window.__store.touch()` — the same call every engine
    action ends in. A bump made another way is not a different case; that is
    the one door.
"""
import asyncio
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

from playwright.async_api import async_playwright

# The identity of every button in the bar, as a list of node handles held on
# the page. `isSameNode` is asked on the page rather than in Python, because a
# Playwright element handle survives a re-render and would compare equal to a
# replacement by its selector.
CAPTURE = """() => {
  window.__persistenceProbe = [...document.querySelectorAll('#nav button')];
  return window.__persistenceProbe.length;
}"""

SAME = """() => {
  const before = window.__persistenceProbe || [];
  const now = [...document.querySelectorAll('#nav button')];
  return {
    before: before.length,
    now: now.length,
    same: before.length > 0 && before.length === now.length
      && before.every((node, at) => node.isSameNode(now[at])),
  };
}"""


async def main():
    journal = Journal("R100 — the chrome persists, and focus with it")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # (a) ONE DOCUMENT, across every state the interface declares.
        states = await page.evaluate("()=>window.__states()")
        journal.check(
            "the interface declares the states this walk covers",
            len(states) > 50,
            f"{len(states)} named state(s)")
        entries = []
        for state in states:
            await page.evaluate("(id)=>window.__go(id)", state)
            entries.append(await page.evaluate(
                "()=>performance.getEntriesByType('navigation').length"))
        journal.check(
            "no full navigation between any two named states — one document",
            entries and max(entries) == 1 and min(entries) == 1,
            f"navigation entries over {len(entries)} state(s): "
            f"min {min(entries) if entries else 'none'}, "
            f"max {max(entries) if entries else 'none'}")

        # (b) THE BAR'S BUTTONS KEEP THEIR IDENTITY across a page switch.
        await page.evaluate("()=>window.__go('acq-now-idle')")
        await page.wait_for_timeout(200)
        captured = await page.evaluate(CAPTURE)
        journal.check(
            "the bar draws its buttons at all — the identity hold has a subject",
            captured == 4,
            f"{captured} button(s) in #nav")
        await page.evaluate("()=>window.__store.write({page: 'lib'})")
        await page.wait_for_timeout(200)
        switched = await page.evaluate(SAME)
        journal.check(
            "a page switch keeps the tab bar's button nodes (P2, B-231)",
            switched["same"],
            f"{switched['before']} before, {switched['now']} after, "
            f"same nodes: {switched['same']}")

        # (c) AND A STORE BUMP, which is what every engine action ends in.
        await page.evaluate("()=>window.__store.touch()")
        await page.wait_for_timeout(200)
        bumped = await page.evaluate(SAME)
        journal.check(
            "a store bump keeps them too (P2, B-231)",
            bumped["same"],
            f"same nodes after a bump: {bumped['same']}")

        # (d) FOCUS SURVIVES BOTH. Focused on the bar, not merely present: the
        # node that holds focus is the node whose replacement loses it.
        await page.evaluate("()=>document.querySelector('#nav button').focus()")
        focused = await page.evaluate(
            "()=>document.activeElement?.dataset?.page ?? null")
        journal.check(
            "focus can be placed on a tab — the hold below has a subject",
            focused is not None,
            f"focus on data-page={focused!r}")
        await page.evaluate("()=>window.__store.write({page: 'arr'})")
        await page.evaluate("()=>window.__store.touch()")
        await page.wait_for_timeout(200)
        kept = await page.evaluate("""()=>{
          const active = document.activeElement;
          return {
            page: active && active.dataset ? active.dataset.page ?? null : null,
            inBar: !!(active && active.closest && active.closest('#nav')),
            body: active === document.body,
          };}""")
        journal.check(
            "focus survives a page switch and a store bump (P28, B-231)",
            kept["inBar"] and kept["page"] == focused and not kept["body"],
            f"active element: {kept}")

        await context.close()
        await browser.close()
    journal.summary(errors)


asyncio.run(main())
