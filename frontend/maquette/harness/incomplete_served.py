"""R193 — « this series is incomplete » is the SERVED list's answer, wherever it is asked.

A follow panel about a series the library holds with holes offers to complete
it — « Compléter » is its primary act — and the removal dialog counts that
series' files from the same fact. Until this rule both read the dying engine's
own copy of the incomplete shows, a list the served layer never writes, so what
the library page drew from `/api/library/incomplete` and what the panel said
about the same series were two answers that could part company.

WHAT IS READ, in two halves:

  1. THE PANEL FOLLOWS THE ANSWER. On the library's « incomplete » lens, the
     served answer is read, then held again WITHOUT one series; the panel about
     that series, opened afterwards, no longer offers to complete it — and the
     panel about a series still in the answer still does. A panel reading any
     other copy keeps offering it.
  2. AND THE FACT IS NOT REACHABLE WITHOUT A READ OF ITS OWN. From the
     acquisition page, on a cache a named state has just cleared — where no
     surface has asked for the incomplete shows — the panel about an incomplete
     series still offers to complete it: it asked.

WHAT IT DOES NOT HOLD: the lens's own drawing, which is the library's rules'.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, Journal, open_page  # noqa: E402

from playwright.async_api import async_playwright  # noqa: E402

journal = Journal("R193 — the incomplete shows are the served list")

SEEDS = ROOT / "design" / "src" / "mocks" / "seeds"
KEY = '["/api/library/incomplete"]'

PANEL = """async (title)=>{
  window.__panel.produce('follow', title);
  await new Promise((done) => setTimeout(done, 900));
  const sheet = document.querySelector('#sheet');
  const offered = !!sheet?.querySelector('[data-complete]');
  window.__panel.close();
  await new Promise((done) => setTimeout(done, 300));
  return {open: !!sheet, offered};
}"""


async def main():
    shows = [one["title"] for one in json.loads((SEEDS / "incomplete-shows.json").read_text())]
    removed, kept = shows[0], shows[1]

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # 1 — the panel follows the answer the cache holds.
        await page.evaluate("()=>{window.__reset?.(); window.__go('followsheet-gaps');}")
        await page.wait_for_timeout(900)
        await page.evaluate("()=>window.__panel.close()")
        await page.wait_for_timeout(300)
        held = await page.evaluate(
            f"""(title)=>{{
              const answer = window.__queries.getQueryData({KEY});
              if (!Array.isArray(answer)) return null;
              window.__queries.setQueryData({KEY},
                answer.filter((show) => (show.t ?? show.title) !== title));
              return answer.length;
            }}""", removed)
        journal.check("the library's lens has read the served incomplete shows",
                      held == len(shows), f"held {held} of {len(shows)}")
        without = await page.evaluate(PANEL, removed)
        journal.check(
            f"with « {removed} » gone from the answer, its panel no longer offers to complete it",
            without["open"] and not without["offered"],
            f"{without} — the panel read another copy than the served list")
        still = await page.evaluate(PANEL, kept)
        journal.check(
            f"and the panel about « {kept} », still in the answer, still does",
            still["open"] and still["offered"], f"{still}")

        # 2 — reachable without a surface having asked first.
        await page.evaluate("()=>{window.__reset?.(); window.__go('acq-follows-list');}")
        await page.wait_for_timeout(600)
        cold = await page.evaluate(f"()=>window.__queries.getQueryData({KEY}) === undefined")
        answer = await page.evaluate(PANEL, kept)
        journal.check(
            f"on a cache where nothing asked for them, the panel about « {kept} » asks and offers to complete it",
            answer["open"] and answer["offered"],
            f"{answer} (cache cold before: {cold})")

        journal.check("no error was raised", not errors, " · ".join(errors[:3]))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
