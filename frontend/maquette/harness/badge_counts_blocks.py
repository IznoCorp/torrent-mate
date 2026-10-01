"""R506 — the Acquisition badge counts the whole « À traiter » list (Q7).

Q7: « le badge d'Acquisition compte toute la liste » — every block, the external
ones included, « Mis de côté » excluded (ruling 16). The badge is `todoCards`'
count; moving the deferred card into the list moves the badge with it.

The expected number is computed HERE from the server's answer — the queue's
lists, one card per acquisition, a card counted when a rung of its ladder is
stopped for his hand (`blocked`) or classified by the engine as a block it
lifts (`resumes` set), or when it carries a closure; never one set aside
(`aside`) — and never read off the interface. It is read from the Médiathèque,
a page that draws nothing of Acquisition (R236's walk).

1. on each moved deferral, on the list whole (`acq-todo-every-cause`), on
   qBittorrent's outage holding every card in flight
   (`acq-block-client-unreachable`), on a closure and on a superseded release,
   the badge read from the Médiathèque equals that count (r2 of the lot's
   reading: the three moved reports alone left a badge blind to the five new
   causes);
2. and « À traiter »'s own tab count says the same number.

Red before the move: the badge reads 3 on `acq-card-deferred-*` while 4 blocks
exist (maquette-blocked DESIGN § 0.1 item 2).
"""
import asyncio

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

STATES = ("acq-card-deferred-ratio", "acq-card-deferred-space", "acq-card-deferred-missing",
          "acq-todo-every-cause", "acq-block-client-unreachable", "acq-closure-torrent-removed",
          "acq-superseded-episode")
SERVER_COUNT = """async () => {
  const queue = await (await fetch('/api/acquisition/to-handle?scenario=loaded')).json();
  const titles = new Set();
  for (const card of [...queue.blocked, ...queue.arrivals, ...queue.inFlight]) {
    const ladder = card.ladder || [];
    if (ladder.some((rung) => rung.state === 'aside')) continue;
    const stopped = card.closure != null || ladder.some((rung) => rung.state === 'blocked'
      || rung.resumes != null);
    if (stopped) titles.add(card.title + '|' + (card.season ?? '') + '|' + (card.episode ?? ''));
  }
  return titles.size;
}"""
BADGE = """() => {
  const badge = document.querySelector('#nav button[data-page="acq"] [data-part="shell/tab-badge"]');
  return badge ? Number(badge.textContent.trim()) : 0;
}"""
TODO_COUNT = """() => {
  const count = document.querySelector('[data-acqtab="todo"] [data-part="segment/count"]');
  return count ? Number(count.textContent.trim()) : 0;
}"""


async def main():
    journal = Journal("R506 — the Acquisition badge counts the whole « À traiter » list")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for state in STATES:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            await page.evaluate("()=>document.querySelector('[data-acqtab=\"todo\"]')?.click()")
            await page.wait_for_timeout(ACTED)
            tab = await page.evaluate(TODO_COUNT)
            expected = await page.evaluate(SERVER_COUNT)
            await page.evaluate("()=>document.querySelector('#nav button[data-page=\"lib\"]')?.click()")
            await page.wait_for_timeout(ACTED)
            await page.evaluate("()=>window.__mocks.quiet()")
            badge = await page.evaluate(BADGE)
            journal.check(f"{state}: read from the Médiathèque, the badge counts every block the server holds",
                          expected > 0 and badge == expected, f"server {expected}, badge {badge}")
            journal.check(f"{state}: and « À traiter »'s tab says the same number",
                          tab == expected, f"tab {tab}, server {expected}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
