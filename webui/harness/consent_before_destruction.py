"""R412 — no destruction without consent (L24, NE-DOIT-PAS-6).

One hold read the library's single delete; what no rule read was the clause
over EVERY destructive verb. Each verb below destroys or gives something up on
the engine's side:

  - `journey-abandon` — abandon a medium's acquisition (« À traiter »);
  - `staging-delete` — delete a staged folder;
  - `del` — delete a medium from the library;
  - `removesecret` — remove a provider's key;
  - `torrent-remove` — remove a torrent from qBittorrent (Trackers).

Maintenance's destructive commands are held by R67 (a real run only after a
blank one); the bulk delete's dialog naming the ticked media by `selection.py`.

WHAT IS READ, for each verb tapped (the verb's own attribute, on a button, the
way a card or a panel carries it), read on what the LAYER answered:

  1. the dialog opens, and NO write has left — not one non-GET call;
  2. its way out (`data-dialog-dismiss`) closes it, and still no write has left.
"""
import asyncio

from common import ACTED, SETTLED, Journal, open_page, read_at, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

# A LIBRARY REMOVAL IS TAPPED AS ITS ROW CARRIES IT: the title and the row's identity
# (`data-del-ref`), because a title alone removes nothing — two media may share one.
TAP = """([attribute, value]) => {
  const before = window.__mocks.answered().length;
  const button = document.createElement('button');
  button.setAttribute(attribute, value);
  if (attribute === 'data-del')
    button.setAttribute('data-del-ref', [...window.__librarySelection([value]).keys()][0] ?? '');
  document.body.append(button);
  button.click();
  button.remove();
  return before;
}"""

READ = """(before) => ({
  open: !!document.querySelector('#dlg[data-open]'),
  writes: window.__mocks.answered().slice(before).filter((call) => call.method !== 'GET')
    .map((call) => call.operationId)})"""

DISMISS = """() => document.querySelector('#dlg[data-open] [data-dialog-dismiss]')?.click()"""

TORRENT = """async () => {
  const downloads = await (await fetch('/api/v1/acquisition/downloads')).json();
  const one = (downloads.downloads ?? []).find((entry) => entry.infoHash && entry.tracker);
  return one ? `${one.infoHash}:${one.tracker}` : null;
}"""
SECRET = """async () => ((await (await fetch('/api/v1/config/secrets')).json())[0] ?? {}).key ?? null"""


async def main():
    journal = Journal("R412 — no destruction without consent")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await read_at(page, "trackers-page", "() => true")
        torrent = await page.evaluate(TORRENT)
        secret = await page.evaluate(SECRET)
        cases = (
            ("journey-abandon", "acq-card-blocked", "data-journey-abandon", "Lucky"),
            ("staging-delete", "acq-card-blocked", "data-staging-delete", "Lucky"),
            ("del", "lib-grid", "data-del", "Silo (2023)"),
            ("removesecret", "settings", "data-removesecret", secret),
            ("torrent-remove", "trackers-page", "data-torrent-remove", torrent),
        )
        for verb, state, attribute, value in cases:
            if not journal.check(f"{verb}: a subject to tap it on", bool(value), str(value)):
                continue
            await read_at(page, state, "() => true")
            before = await page.evaluate(TAP, [attribute, value])
            await page.wait_for_timeout(ACTED)
            asked = await page.evaluate(READ, before)
            journal.check(f"{verb}: the dialog opens before anything is written",
                          asked["open"] and asked["writes"] == [], str(asked))
            await page.evaluate(DISMISS)
            await page.wait_for_timeout(ACTED + SETTLED)
            left = await page.evaluate(READ, before)
            journal.check(f"{verb}: its way out closes it, and nothing has been written",
                          not left["open"] and left["writes"] == [], str(left))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
