"""R425 — the instance's forbidden writes: a named list, subtracted from every role, said once (§ 17; ruling 23).

DESIGN maquette-l18 § 3.7, § 5 (R-L18-o, R-L18-b's source holds).

1. SOURCE — THE FLAG IS DEAD: no product source reads a settings-local `readOnly`, and none
   guesses the ceiling from an address or a port: the list comes with the account.
2. R-L18-o — EVERY WRITE ABSENT, ADMIN INCLUDED: on today's read-only instance the owner has no
   « ＋ », no lever in Système, no selection in the Médiathèque, no switch on Trackers, no field
   in Réglages; forcing a run answers 403; the page says « lecture seule » once.
3. PREPROD — ONLY WHAT THE LIST NAMES: with `library.delete` alone forbidden, the media sheet
   keeps « Re-scraper » and loses « Supprimer », forcing the delete answers 403 and the rescrape
   does not, and the notice names the forbidden right rather than saying « lecture seule ».
"""
import asyncio
import pathlib
import re

from common import SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
FLAG = re.compile(r"SETTINGS_STATE\.readOnly|^\s*readOnly: (boolean|false)[,;]")
GUESS = re.compile(r"8711|location\.port|import\.meta\.env\.\w*(STAGING|PREPROD)")

QUIET = """async () => { for (let i = 0; i < 40 && document.querySelector('#toast[data-shown]'); i += 1) {
  document.querySelector('#toastx')?.click(); await new Promise((settle) => setTimeout(settle, 250)); } }"""
NOTICE = "() => document.querySelector('[data-part=\"access/ceiling\"]')?.textContent || null"
PRESENT = "(selector) => !!document.querySelector(selector)"


def product_sources():
    """Every product source under `design/src`, the harness and the mock aside."""
    for path in sorted(SOURCE.rglob("*.ts*")):
        relative = path.relative_to(SOURCE).as_posix()
        if relative.startswith(("mocks/", "harness/", "contract/")) or ".test." in relative:
            continue
        yield relative, path.read_text(encoding="utf-8")


async def main():
    journal = Journal("R425 — the forbidden writes, named, subtracted from every role")
    sources = list(product_sources())
    flags = [f"{name}:{n}" for name, text in sources for n, line in enumerate(text.splitlines(), 1)
             if FLAG.search(line) and "variants" not in name]
    journal.check("the settings-local read-only flag is gone", not flags, str(flags))
    guesses = [f"{name}:{n}" for name, text in sources for n, line in enumerate(text.splitlines(), 1)
               if GUESS.search(line)]
    journal.check("R-L18-b: no source guesses the ceiling from an address", not guesses, str(guesses))

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def go(state, patch=None):
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            if patch:
                await page.evaluate("(patch)=>{window.__store.write(patch)}", patch)
                await page.wait_for_timeout(SETTLED)
            await page.evaluate(QUIET)

        await go("ceiling-operator")
        fab = await page.evaluate("()=>!document.querySelector('#fab')?.hidden")
        journal.check("R-L18-o: the owner has no « ＋ » under the ceiling", not fab)
        notice = await page.evaluate(NOTICE)
        journal.check("R-L18-o: the page says « lecture seule » once", notice and "lecture seule" in notice
                      and await page.evaluate("()=>document.querySelectorAll('[data-part=\"access/ceiling\"]').length")
                      == 1, str(notice))
        places = {"sys": '[data-pipeline-pause], [data-pipeline-resume], [data-watcher]',
                  "lib": "[data-selmode]", "trackers": "[data-tracker-switch]"}
        for where, selector in places.items():
            patch = {"page": where}
            if where == "trackers":
                patch["trackersTab"] = "trackers"
            await page.evaluate("(patch)=>{window.__store.write(patch)}", patch)
            await page.wait_for_timeout(SETTLED)
            journal.check(f"R-L18-o: no write offered on {where} under the ceiling",
                          not await page.evaluate(PRESENT, selector), selector)
        forced = await page.evaluate("async()=>(await fetch('/api/pipeline/run',{method:'POST',body:'{}'})).status")
        journal.check("R-L18-o: forcing a run as the owner answers 403", forced == 403, str(forced))

        await go("settings-read-only")
        await page.evaluate("()=>window.__panel.produce('setting', 'paths.torrent_complete_dir')")
        await page.wait_for_timeout(SETTLED)
        journal.check("R-L18-o: a setting offers no field on the read-only instance",
                      not await page.evaluate(PRESENT, '#sheet [data-part="field"]:not([data-read-only])'))

        await go("ceiling-preprod")
        sheet = await page.evaluate("""() => ({ rescrape: !!document.querySelector('[data-rescrape]'),
          remove: !!document.querySelector('[data-part="sheet/action"][data-del]') })""")
        journal.check("preprod: the sheet keeps « Re-scraper » and loses « Supprimer »",
                      sheet["rescrape"] and not sheet["remove"], str(sheet))
        notice = await page.evaluate(NOTICE)
        journal.check("preprod: the notice names the forbidden right, not « lecture seule »",
                      notice and "supprimer de la médiathèque" in notice and "lecture seule" not in notice, str(notice))
        statuses = await page.evaluate("""async () => ({
          remove: (await fetch('/api/library/items', { method: 'DELETE', body: JSON.stringify({ titles: [] }) })).status,
          rescrape: (await fetch('/api/media/tmdb/1/rescrape', { method: 'POST', body: '{}' })).status })""")
        journal.check("preprod: forcing the delete answers 403, the rescrape does not",
                      statuses["remove"] == 403 and statuses["rescrape"] != 403, str(statuses))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
