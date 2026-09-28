"""R233 — paused follows fold at the end of « Suivis », outside its count.

A paused follow is not gone: it is waiting for him to start it again. It no
longer sits among the follows that are being looked for, and no filter is
needed to find it: it is in a FOLDED section at the end of « Suivis », of the
same form as « Mis de côté » at the end of « À traiter » — unfolded to see them
and start them again.

On the list of follows:

1. no paused follow is drawn among the follows above the fold;
2. the fold is the list's last section, closed by default, and its count is the
   number of paused follows;
3. opened, it holds every paused follow;
4. there is no « En pause » filter any more, and « Tout » counts the follows
   being looked for — the paused ones are outside it;
5. started again from the fold, a follow leaves it for the list.

Red before the move: paused follows sit in the list, and the filter exists.
"""
import asyncio

from common import ACTED, SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SECTION = '[data-part="section/paused"]'

READING = f"""() => {{
  const follows = window.__queries?.getQueryData(["/api/acquisition/followed"]) || [];
  const paused = follows.filter(one => one.status === "disabled").map(one => one.title);
  const fold = document.querySelector('#view {SECTION}');
  const titles = (root) => [...root.querySelectorAll('[data-part="card/title"]')].map(one => one.textContent);
  const listed = [...document.querySelectorAll('#view [data-part="card/title"]')]
    .filter(one => !one.closest('{SECTION}')).map(one => one.textContent);
  const sections = [...document.querySelectorAll('#view [data-part^="section"]')].filter(one => one.matches('section'));
  const pills = [...document.querySelectorAll('#view [data-part="pill"]')];
  const all = pills.find(one => one.dataset.pill === "tout");
  const count = fold ? fold.querySelector('summary [data-part="section/count"]') : null;
  return {{
    total: follows.length,
    paused,
    listed,
    folded: fold ? !fold.querySelector('details')?.open : null,
    last: fold !== null && sections[sections.length - 1] === fold,
    count: count ? Number(count.textContent) : null,
    inFold: fold ? titles(fold) : null,
    pills: pills.map(one => one.dataset.pill),
    all: all ? Number(all.querySelector('span')?.textContent) : null,
  }};
}}"""
OPEN = f"""() => {{ const summary = document.querySelector('#view {SECTION} summary');
  if (!summary) return false; summary.click(); return true; }}"""
RESUME = f"""(title) => {{
  const button = [...document.querySelectorAll('#view {SECTION} [data-pause]')]
    .find(one => one.getAttribute('data-pause') === title);
  if (!button) return false; button.click(); return true; }}"""


async def main():
    journal = Journal("R233 — paused follows fold at the end of « Suivis »")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await page.evaluate(
            "()=>{try{window.__go('acq-follows-list');return null}catch(error){return String(error)}}")
        journal.check("the named state acq-follows-list exists", answer is None, answer or "")
        await page.wait_for_timeout(SETTLED)
        before = await page.evaluate(READING)
        paused = before["paused"]
        journal.check("the follows carry paused ones", bool(paused), str(paused))
        journal.check("no paused follow is drawn among the follows above the fold",
                      not any(title in before["listed"] for title in paused), str(before["listed"]))
        journal.check("the fold is the list's last section, closed, counting the paused follows",
                      before["last"] and before["folded"] is True and before["count"] == len(paused),
                      f"last {before['last']}, folded {before['folded']}, count {before['count']} of {len(paused)}")
        journal.check("there is no « En pause » filter any more", "pause" not in before["pills"], str(before["pills"]))
        journal.check("« Tout » counts the follows being looked for, the paused ones outside it",
                      before["all"] == before["total"] - len(paused),
                      f"« Tout » {before['all']}, {before['total']} follows, {len(paused)} paused")

        opened = await page.evaluate(OPEN)
        await page.wait_for_timeout(ACTED)
        unfolded = await page.evaluate(READING)
        journal.check("opened, the fold holds every paused follow",
                      opened and sorted(unfolded["inFold"] or []) == sorted(paused), str(unfolded["inFold"]))

        started = paused[0] if paused else None
        resumed = started is not None and await page.evaluate(RESUME, started)
        await page.wait_for_timeout(SETTLED)
        after = await page.evaluate(READING)
        journal.check("started again from the fold, the follow leaves it for the list",
                      resumed and started not in (after["inFold"] or []) and started not in after["paused"]
                      and after["count"] == len(paused) - 1,
                      f"resumed {resumed}, fold {after['inFold']}, count {after['count']}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
