"""R236 — a navigation badge reads an answer the frame keeps observed, from any page.

A badge is a function its row points at, reading the query cache synchronously
(`app/navigation.ts`). A synchronous read is not an observer: a query nobody
observes is not refetched when a live event invalidates it, and is dropped from
the cache five minutes after its last observer left. So a badge read from a page
that does not draw its own subject froze on whatever the boot had fetched, and a
live event that changed the subject changed nothing on the button.

Each row that carries a badge therefore DECLARES the reads its badge derives
from, and the frame observes them for the document's lifetime — one observer
per row the frame DRAWS, so a row not drawn asks for nothing.

On a cold load of the Médiathèque — a page that reads nothing of Acquisition,
nor of Système:

1. the Acquisition button carries the seeded « À traiter » count;
2. the server empties « À traiter » and says so with a live event the backend
   emits: the badge is gone — absent, never « 0 » — without the operator
   having opened Acquisition.

THE MENU BUTTON carries the badge of the rows the bar does not hold — Système's,
which counts the maintenance facts AND the machine's faults, and — since L24
(OPEN 2 = A) — a disk nearly full and an index anomaly. Its expected number
is computed HERE from the three answers the server gives (a stale lock, a sweep
that has not finished, leftover temporary entries; a service or a dependency in
alert), never read off the interface:

3. on the same cold load, the button's number is that count, and the drawer's
   Système entry draws the same number — one derivation;
4. the server's lock goes stale and a run's end says so: the number follows;
5. a service stops (the simulated fault Système draws): the number counts it;
6. nothing is left to say: the button carries no badge, and neither does the
   drawer's entry.

THE BADGES COUNT WITHOUT RIGHTS, and that is said rather than left to be found:
no right exists yet. The rights half — a row the account cannot open registers
no observer, sends no read and adds nothing to the button — is written with the
rights model, and mutated there.

R-conformity-k — ONE COUNT BADGE (`hold_one_badge`, in its own context): every
placement of the badge reads one drawing.
"""
import asyncio

from common import PHONE, PROTOTYPE, SETTLED, Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

LIBRARY = "media"
BADGE = """() => {
  const badge = document.querySelector('#nav button[data-page="acq"] [data-part="shell/tab-badge"]');
  return badge ? badge.textContent.trim() : null;
}"""
MENU = """() => {
  const read = (selector) => {
    const node = document.querySelector(selector);
    return node ? node.textContent.trim() : null;
  };
  return {
    button: read('[data-drawer] [data-part="shell/menu-badge"]'),
    entry: read('#drawer a[data-navgo="sys"] [data-part="shell/drawer-count"]'),
  };
}"""
# What Système has to say, from the server's own answers — the oracle outside
# the interface. A tone is the contract's token, not interface copy.
SERVER_COUNT = """async () => {
  const read = async (address) => (await fetch(address)).json();
  const [locks, services, dependencies, disks, index] = await Promise.all([
    read('/api/v1/maintenance/locks'), read('/api/v1/system/services'), read('/api/v1/system/dependencies'),
    read('/api/v1/maintenance/disks'), read('/api/v1/maintenance/index-health')]);
  const maintenance = (locks.pipelineLock.stale ? 1 : 0)
    + (locks.sweep.status === 'pending' ? 1 : 0)
    + (locks.sweep.status !== 'pending' && locks.sweep.orphans.length > 0 ? 1 : 0);
  const faults = [...services, ...dependencies].filter((fact) => fact.tone === 'alert').length;
  const care = [...disks, ...index].filter((fact) => fact.state === 'nearly_full' || fact.state === 'to_clean').length;
  return maintenance + faults + care;
}"""
CURRENT = "() => document.querySelector('#nav button[aria-current=\"page\"]')?.dataset.page ?? null"
RUN_ENDED = """async () => {
  window.__mocks.stream.emit("PipelineEnded", {});
  await window.__mocks.quiet();
}"""


async def settle(page):
    """Waits for the layer to be quiet and the frame to have drawn."""
    await page.evaluate("()=>window.__mocks.quiet()")
    await page.wait_for_timeout(SETTLED)
    await page.evaluate("()=>window.__mocks.quiet()")


def said(count):
    """What a badge draws for a count: its number, or nothing at all."""
    return str(count) if count else None


async def main():
    journal = Journal("R236 — a navigation badge reads an answer the frame keeps observed")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context = await browser.new_context(**PHONE)
        page = await context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(PROTOTYPE + LIBRARY, wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        await page.evaluate("()=>document.querySelector('#toastx')?.click()")
        await settle(page)

        current = await page.evaluate(CURRENT)
        journal.check("the cold load lands on the Médiathèque, not on Acquisition", current == "lib", str(current))
        seeded = await page.evaluate(BADGE)
        journal.check("on a cold load of another page, Acquisition's button carries the seeded count",
                      seeded is not None and seeded.isdigit() and int(seeded) > 0, str(seeded))

        expected = await page.evaluate(SERVER_COUNT)
        menu = await page.evaluate(MENU)
        journal.check("on the same cold load, the menu button carries what Système has to say",
                      expected > 0 and menu["button"] == said(expected), f"server {expected}, button {menu['button']}")
        journal.check("and the drawer's Système entry draws the same number — one derivation",
                      menu["entry"] == menu["button"], f"entry {menu['entry']}, button {menu['button']}")

        await page.evaluate("()=>window.__mocks.setLockStale(true)")
        await page.evaluate(RUN_ENDED)
        await settle(page)
        stale = await page.evaluate(SERVER_COUNT)
        menu = await page.evaluate(MENU)
        journal.check("a lock gone stale, announced by a run's end, moves the menu button's number",
                      stale == expected + 1 and menu["button"] == said(stale),
                      f"server {stale}, button {menu['button']}")

        await page.evaluate("()=>window.__store.write({ fault: true })")
        await settle(page)
        menu = await page.evaluate(MENU)
        journal.check("a service stopped counts too — the machine's faults, not maintenance alone",
                      menu["button"] == said(stale + 1) and menu["entry"] == menu["button"],
                      f"expected {stale + 1}, button {menu['button']}, entry {menu['entry']}")

        await page.evaluate("()=>window.__store.write({ fault: false })")
        # RE-AIMED OUT LOUD (L24): nothing to say now also POSES a healthy machine —
        # the seed at rest is the operator's, a disk nearly full among it.
        await page.evaluate("()=>{ window.__mocks.setLockStale(false); window.__mocks.setTmpOrphans(false);"
                            " window.__mocks.setMachineHealthy(true);"
                            " window.__queries.invalidateQueries({ queryKey: ['/api/v1/maintenance/disks'] });"
                            " window.__queries.invalidateQueries({ queryKey: ['/api/v1/maintenance/index-health'] }); }")
        await page.evaluate(RUN_ENDED)
        await settle(page)
        quiet = await page.evaluate(SERVER_COUNT)
        menu = await page.evaluate(MENU)
        journal.check("with nothing to say, the menu button and the drawer's entry carry no badge — not « 0 »",
                      quiet == 0 and menu["button"] is None and menu["entry"] is None,
                      f"server {quiet}, button {menu['button']}, entry {menu['entry']}")

        await page.evaluate("""async () => {
          window.__mocks.clearBlocked();
          window.__mocks.stream.emit("WantedAbandoned", {});
          await window.__mocks.quiet();
        }""")
        await settle(page)
        after = await page.evaluate(BADGE)
        journal.check("after a live event empties « À traiter », the badge is gone from the other page",
                      after is None, f"still reads {after}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await hold_one_badge(browser, journal)
        await browser.close()
    journal.summary()


BADGE_STATES = ("menu-system-badge", "drawer-navigation", "acq-todo-loaded")
BADGE_PARTS = ("shell/tab-badge", "shell/menu-badge", "shell/drawer-count", "segment/count")
BADGE_DRAWINGS = """(parts)=>parts.flatMap((part) => [...document.querySelectorAll(`[data-part="${part}"]`)]
  .filter((badge) => badge.getBoundingClientRect().height > 0)
  .map((badge) => {
    const style = getComputedStyle(badge);
    return {part, drawing: [Math.round(badge.getBoundingClientRect().height), style.backgroundColor, style.color,
                            style.fontSize, style.fontWeight].join(' ')};
  }))"""


async def hold_one_badge(browser, journal):
    """R-conformity-k — one count badge, wherever a count is drawn.

    The bar's tab, the menu button, the drawer's entry and a tab bar's count
    each read, on the states that draw them, one height, fill, ink and type.

    Args:
        browser: The launched browser; the holds read a context of their own.
        journal: The rule's journal.
    """
    seen = {}
    context, page = await open_page(browser)
    for state in BADGE_STATES:
        for badge in await read_at(page, state, BADGE_DRAWINGS, list(BADGE_PARTS)):
            seen.setdefault(badge["part"], set()).add(badge["drawing"])
    await context.close()
    journal.check("every placement of the badge is drawn somewhere", set(seen) == set(BADGE_PARTS),
                  f"drawn: {sorted(seen)}")
    drawings = set().union(*seen.values()) if seen else set()
    journal.check("and every one reads one height, fill, ink and type", len(drawings) == 1,
                  f"{ {part: sorted(values) for part, values in seen.items()} }")


if __name__ == "__main__":
    asyncio.run(main())
