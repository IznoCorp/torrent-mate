"""R79 — the library loads more, says when it cannot, and lets one try again.

The Médiathèque reads `library.db` locally, so a page of 24 more costs neither
quota nor external network: the loading regime is infinite scroll, and §8 says
the count line always tells how many are shown of how many. That leaves three
promises nothing measured until this rule existed, all of them at the END of
the list, where a long scroll is the only way in:

  · the end of the sample SAYS it is the end of the sample, and says how many
    titles the prototype really carries — otherwise the last row contradicts
    the « of 1 861 » counter above it;
  · a page that fails to load says what remains VALID, and offers to try
    again — the failure is simulated once, on purpose, because a path nobody
    can see is a path nobody can judge;
  · and « Réessayer » really loads. This is the one control on a migrated PAGE
    whose handler is the component's own rather than the document-level
    delegation's, which is exactly why it earns a hold: the delegation is
    covered elsewhere, and this is not delegated.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

from playwright.async_api import async_playwright

READ = """()=>({
  foot: (document.querySelector('#libload')||{}).textContent || '',
  retry: !!document.querySelector('#libretry'),
  rows: document.querySelectorAll('#libitems .card, #libitems .tile').length,
  count: window.__magasin.lire().etat.libCount,
  err: !!window.__magasin.lire().etat.libErr,
  total: window.__referentiel.libFiltered().length,
  carried: window.__referentiel.libraryLoaded(),
})"""


async def main():
    journal = Journal("R79 — the library's loading, and the way back from a failure")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        _, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── the failure, and the way back ──────────────────────────────────
        await page.evaluate("()=>window.__go('lib-erreur-suite')")
        await page.wait_for_timeout(700)
        failed = await page.evaluate(READ)
        journal.check(
            "a page that fails to load says so",
            failed["err"] and "charger la suite" in failed["foot"],
            failed["foot"][:110])
        journal.check(
            "and says how many are already shown, and still valid",
            str(failed["count"]) in failed["foot"]
            and "restent valides" in failed["foot"],
            f"{failed['count']} shown — {failed['foot'][:110]}")
        journal.check(
            "the rows already loaded are STILL THERE under the failure",
            failed["rows"] == failed["count"],
            f"{failed['rows']} drawn for {failed['count']} loaded")
        journal.check("and it offers to try again", failed["retry"])

        # THE ONE CONTROL A COMPONENT OWNS, so the one whose handler nothing
        # else covers. Looked up before it is tapped, like every other — and
        # measured ALONE: the sentinel that loads on scroll is neutralised
        # first, because it can produce the same outcome for a different
        # reason. Without that, a retry that does nothing at all still passes,
        # the next page arriving from the observer instead — which is precisely
        # how the defect this hold now catches survived being written.
        await page.evaluate(
            "()=>{window.__observeReel = IntersectionObserver.prototype.observe;"
            " IntersectionObserver.prototype.observe = function () {};}")
        control = page.locator("#libretry").first
        tapped = bool(await control.count())
        if tapped:
            await control.click()
            await page.wait_for_timeout(1500)
        await page.evaluate(
            "()=>{IntersectionObserver.prototype.observe = window.__observeReel;}")
        after = await page.evaluate(READ)
        journal.check(
            "trying again really loads the next page",
            tapped and not after["err"] and after["count"] > failed["count"]
            and after["rows"] == after["count"],
            f"{failed['count']} → {after['count']}, {after['rows']} drawn"
            if tapped else "no control carries #libretry")

        # ── the end of the sample says it is the end of the SAMPLE ─────────
        await page.evaluate("()=>window.__go('lib-liste')")
        await page.wait_for_timeout(600)
        await page.evaluate("""()=>{const etat = window.__magasin.lire().etat;
          window.__magasin.ecrire({libCount: window.__referentiel.libFiltered().length});
          window.__referentiel.render();}""")
        await page.wait_for_timeout(600)
        ended = await page.evaluate(READ)
        journal.check(
            "at the end, the page says it is the end of the SAMPLE",
            "Fin de l'échantillon" in ended["foot"], ended["foot"][:110])
        journal.check(
            "and says how many titles this prototype really carries",
            str(ended["carried"]) in ended["foot"],
            f"{ended['carried']} carried — {ended['foot'][:90]}")
        journal.check(
            "which is the number it really has, not the library's own total",
            ended["carried"] == ended["total"] and ended["carried"] < 1861,
            f"{ended['carried']} carried, {ended['total']} filtered")

        await browser.close()
    journal.summary(errors)


asyncio.run(main())
