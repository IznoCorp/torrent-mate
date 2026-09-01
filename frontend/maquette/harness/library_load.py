"""R79 — the library loads more, says when it cannot, and lets one try again.

The Médiathèque reads `library.db` locally, so a page of 24 more costs neither
quota nor external network: the loading regime is infinite scroll, and §8 says
the count line always tells how many are shown of how many. That leaves three
promises nothing measured until this rule existed, all of them at the END of
the list, where a long scroll is the only way in:

  · the end of the sample SAYS it is the end of the sample, and says how many
    titles the prototype really carries — otherwise the last row contradicts
    the « of 1 861 » counter above it. Since L09 those are two fields of one
    answer rather than two functions of the engine: `loaded` is what the source
    holds and `total` is what the library claims, and the hold reads both;
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

# READ WHERE THE LIBRARY READS, since L09. The count, the failure and the two
# totals were four values in the interface's own store and in the engine's
# fixture; they are the query's now — `libCount`, `libErr`, `libLoading` and
# `libFailedOnce` no longer exist, and `libFiltered()` / `libraryLoaded()` went
# with the fixture they read. What the rule HOLDS is untouched: how many are
# shown, whether the failure says so, and whether the end mark names the sample
# rather than the library.
READ = """()=>{
  const listing = window.__queries.getQueryCache().getAll()
    .find((query) => query.queryKey[0] === '/api/library/items');
  const pages = listing?.state.data?.pages ?? [];
  return {
    foot: (document.querySelector('#libload')||{}).textContent || '',
    retry: !!document.querySelector('#libretry'),
    // WHAT THE LIST HOLDS, NOT WHAT IT DRAWS — since L12 they are different.
    // The list is WINDOWED (P24): it renders a window and stands spacers in for
    // the rest, so counting rendered nodes answers « how many fit on screen »
    // and no longer « how many have loaded ». Every hold below is about
    // LOADING, so it reads the count the surface declares.
    // Rendered nodes are kept beside it, because « the window is not empty » is
    // still worth knowing and a windowed list drawing NOTHING would otherwise
    // pass every hold here.
    rows: Number((document.querySelector('#libitems')||{}).dataset?.virtualised) || 0,
    drawn: document.querySelectorAll('#libitems [data-part="card"], #libitems [data-part="tile"]').length,
    // THE WINDOW'S OWN GEOMETRY, which nothing below derives from the cache.
    // `rows` is the count the surface declares and it is computed from the very
    // pages the hold sums into `count`: comparing them is data against itself,
    // and it passed by construction. What the spacers SPAN is produced by the
    // virtualiser and by nothing else, so it is evidence.
    lanes: Number((document.querySelector('#libitems')||{}).dataset?.lanes) || 1,
    spanned: (document.querySelector('#libitems')||{getBoundingClientRect:()=>({height:0})})
      .getBoundingClientRect().height,
    lineHeight: (() => {
      const first = document.querySelector('#libitems [data-part="card"], #libitems [data-part="tile"]');
      return first ? first.getBoundingClientRect().height : 0;
    })(),
    count: pages.reduce((held, page) => held + page.items.length, 0),
    err: listing?.state.status === 'error'
         || listing?.state.fetchStatus === 'idle' && !!listing?.state.error,
    total: pages[0]?.total ?? 0,
    carried: pages[0]?.loaded ?? 0,
  };
}"""


async def main():
    journal = Journal("R79 — the library's loading, and the way back from a failure")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        _, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── the failure, and the way back ──────────────────────────────────
        await page.evaluate("()=>window.__go('lib-error-more')")
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
        # MEASURED, NOT RE-DERIVED. « rows == count » was two expressions over
        # ONE array — `data-virtualised` is the prop the page computes from the
        # same pages this hold sums — so it could only fail by the attribute
        # being absent. What the window SPANS is the virtualiser's own output:
        # its spacers stand in for the rows it is not drawing, so a window that
        # forgot the loaded rows is short by their height.
        lines = -(-failed["count"] // max(failed["lanes"], 1))
        expected = (lines - 1) * failed["lineHeight"]
        journal.check(
            "the rows already loaded are STILL THERE under the failure",
            failed["drawn"] > 0 and failed["lineHeight"] > 0
            and failed["spanned"] >= expected,
            f"{failed['drawn']} drawn and the window spans "
            f"{failed['spanned']:.0f}px for {failed['count']} loaded row(s) over "
            f"{failed['lanes']} lane(s) — {lines} line(s) of "
            f"{failed['lineHeight']:.0f}px need at least {expected:.0f}px, so "
            "the window has dropped what was already loaded")
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
            and after["rows"] == after["count"] and after["drawn"] > 0,
            f"{failed['count']} → {after['count']}, {after['rows']} held, "
            f"{after['drawn']} drawn"
            if tapped else "no control carries #libretry")

        # ── the end of the sample says it is the end of the SAMPLE ─────────
        await page.evaluate("()=>window.__go('lib-list')")
        await page.wait_for_timeout(600)
        # ASK FOR EVERY PAGE, through the door the list publishes. Writing a
        # count into the store used to be enough because the store WAS the
        # paging; the cache holds the pages now, so reaching the end means
        # asking for them. Bounded, and it stops when nothing more arrives —
        # a loop that trusted a count would spin on a list that stopped growing.
        await page.evaluate("""async ()=>{
          const held = () => {
            const listing = window.__queries.getQueryCache().getAll()
              .find((query) => query.queryKey[0] === '/api/library/items');
            return (listing?.state.data?.pages ?? [])
              .reduce((count, page) => count + page.items.length, 0);
          };
          for (let asked = 0; asked < 40; asked += 1) {
            const before = held();
            window.__libraryNextPage?.();
            await new Promise((settle) => setTimeout(settle, 30));
            if (held() === before) break;
          }
        }""")
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
            ended["carried"] == ended["rows"] and ended["carried"] < ended["total"]
            and ended["drawn"] > 0,
            f"{ended['carried']} carried, {ended['rows']} held, "
            f"{ended['drawn']} drawn, "
            f"{ended['total']} claimed by the library")

        await browser.close()
    journal.summary(errors)


asyncio.run(main())
