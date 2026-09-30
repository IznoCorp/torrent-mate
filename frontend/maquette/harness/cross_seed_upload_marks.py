"""R455, R456 — a tracker says whether it accepts uploads, and a published torrent says it is yours.

Round 11 OPEN 2 = B: « un interrupteur "accepte les uploads" par tracker,
distinct de l'interrupteur cross-seed, dans Réglages et sur l'entrée du
tracker » — one write, two doors, as the cross-seed switch (L17 OPEN 2 = A).
OPEN 5 = B: « une troisième valeur de marque d'origine », « publié par vous »,
beside « téléchargé ici » and « cross-seed »; the ratio is computed like any
torrent's. L23 DESIGN § 3 states 6 and OPEN 5.

R455 — the « accepte les uploads » switch:
1. `tracker-upload-disabled`: v3x.club's panel says it does not accept uploads,
   its cross-seed switch still on beside it;
2. a finger on it: no confirmation, ONE `updateConfigurationFile`; in the render
   that follows the panel, the summary's `acceptsUploads` and Réglages' own
   setting all read on; a finger again: off, the same way, and nothing published
   is withdrawn;
3. the other door: Réglages' write turns it off, and the panel reads off.

R456 — the third origin mark:
4. `torrents-cross-seed-published`: the published copy's card wears « Publié par
   vous » in its own colour, the origin and a found cross-seed theirs; the legend
   says the word; its panel says the same provenance, and its ratio is its own.

Red before the move: no tracker panel carries the switch, no card the third mark.
"""
import asyncio

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

ORIGIN = "66e23ab395c438b7db4f7c855bd451d8bb1f0046"
COPY = "7c1e0b2f95c438b7db4f7c855bd451d8bb1f0046"
KEY = "tracker.providers.v3x.club.accepts_uploads"
SWITCH = '#sheet[data-open] [data-uploads-switch="v3x.club"]'

READ = """(key) => ({
  row: document.querySelector('#sheet[data-open] [data-part="tracker/uploads"]')?.dataset.on ?? null,
  state: document.querySelector('#sheet[data-open] [data-part="tracker/uploads-state"]')?.textContent.trim() ?? null,
  crossSeed: document.querySelector('#sheet[data-open] [data-part="tracker/cross-seed-state"]')?.dataset.on ?? null,
  summary: (window.__queries?.getQueryData(['/api/trackers']) || []).find(one => one.name === 'v3x.club')
    ?.crossSeed.acceptsUploads ?? null,
  setting: (window.__queries?.getQueryData(['/api/config/schema']) || []).flatMap(t => t.settings)
    .find(s => s.key === key)?.raw ?? null,
  dialog: !!document.querySelector('[data-part="dialog"][data-open]'),
})"""
WRITES = """() => (window.__mocks?.answered() || []).filter(call => call.operationId === 'updateConfigurationFile').length"""
# Réglages' own write: the same file, the same key — the other door.
SETTINGS_WRITE = """async (key) => {
  await fetch('/api/config/files/tracker', { method: 'PUT', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ [`tracker:${key}`]: false }) });
  await window.__queries?.invalidateQueries();
}"""
MARKS = """() => Object.fromEntries([...document.querySelectorAll('#view [data-part="torrents/row"]')].map(row => {
  const dot = row.querySelector('[data-part="torrents/origin"]');
  return [`${row.dataset.entry}:${row.querySelector('[data-part="torrents/tracker"]')?.textContent.trim()}`,
          { origin: dot?.dataset.origin, tone: dot?.dataset.tone, word: dot?.getAttribute('aria-label') }];
}))"""
LEGEND = """() => document.querySelector('#view [data-part="legend"]')?.textContent ?? ''"""
FACTS = """() => document.querySelector('#sheet[data-open]')?.textContent ?? ''"""


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


async def main():
    journal = Journal("R455, R456 — « accepte les uploads », one write two doors; « Publié par vous », a third mark")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── R455: the switch ─────────────────────────────────────────────
        answer = await enter(page, "tracker-upload-disabled")
        start = await page.evaluate(READ, KEY)
        journal.check("R455 tracker-upload-disabled: v3x.club does not accept uploads, its cross-seed switch still on",
                      answer is None and start["row"] == "false" and start["state"] == "N'accepte pas les uploads"
                      and start["crossSeed"] == "true" and start["summary"] is False, repr(answer or start))
        before = await page.evaluate(WRITES)
        await page.locator(SWITCH).first.tap()
        await page.wait_for_timeout(ACTED)
        on = await page.evaluate(READ, KEY)
        journal.check("R455 a finger turns it on: no confirmation, ONE write; panel, summary and Réglages read on",
                      not on["dialog"] and await page.evaluate(WRITES) - before == 1 and on["row"] == "true"
                      and on["summary"] is True and on["setting"] is True, repr(on))
        await page.locator(SWITCH).first.tap()
        await page.wait_for_timeout(ACTED)
        off = await page.evaluate(READ, KEY)
        journal.check("R455 again: off, no confirmation, ONE write; the cross-seed switch untouched",
                      not off["dialog"] and await page.evaluate(WRITES) - before == 2 and off["row"] == "false"
                      and off["summary"] is False and off["setting"] is False and off["crossSeed"] == "true",
                      repr(off))

        await enter(page, "tracker-cross-seed-switch-off")
        await page.evaluate("() => window.__panel.produce('tracker', 'v3x.club')")
        await page.wait_for_timeout(ACTED)
        live = await page.evaluate(READ, KEY)
        await page.evaluate(SETTINGS_WRITE, KEY)
        await page.wait_for_timeout(ACTED)
        other = await page.evaluate(READ, KEY)
        journal.check("R455 the other door: Réglages' write turns it off, and the tracker's panel reads off",
                      live["row"] == "true" and other["row"] == "false" and other["summary"] is False,
                      f"{live} → {other}")

        # ── R456: the third origin mark ──────────────────────────────────
        await enter(page, "torrents-cross-seed")
        await page.evaluate("() => window.__panel.close?.()")
        await page.wait_for_timeout(ACTED)
        crosses = [mark for mark in (await page.evaluate(MARKS)).values() if mark.get("origin") == "cross"]
        answer = await enter(page, "torrents-cross-seed-published")
        facts = await page.evaluate(FACTS)
        await page.evaluate("() => window.__panel.close?.()")
        await page.wait_for_timeout(ACTED)
        marks = await page.evaluate(MARKS)
        copy, origin = marks.get(f"{COPY}:tr4ker", {}), marks.get(f"{ORIGIN}:c411", {})
        journal.check("R456 the published copy's card wears « Publié par vous », in a colour of its own",
                      answer is None and copy.get("origin") == "published" and copy.get("word") == "Publié par vous"
                      and origin.get("origin") == "origin" and copy.get("tone") not in (None, origin.get("tone")),
                      repr(answer or marks))
        journal.check("R456 a found cross-seed keeps its own mark, a colour neither of the other two",
                      bool(crosses) and all(mark["tone"] not in (copy.get("tone"), origin.get("tone")) for mark in crosses),
                      repr(crosses))
        legend = await page.evaluate(LEGEND)
        journal.check("R456 the legend says « Publié par vous »", "Publié par vous" in legend, repr(legend))
        journal.check("R456 its panel says the same provenance", "Publié par vous" in facts, repr(facts[:300]))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
