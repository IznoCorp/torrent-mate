"""R405 — one completeness: a followed series' season figures come from the engine's answer (L24, NE-DOIT-PAS-1, § 13).

The engine answers « what has aired against what the library holds, season by
season » for a follow — `GET /api/v1/acquisition/followed/{id}/completeness`, one
matrix read from the cache so that « this panel and the followed card read the
same facts through the same derivation and can never disagree ». The maquette
never called it: both sheets crossed a seasons read of their own.

WHAT IS READ:

  1. the follow sheet of a followed series (`followsheet-complete`, and
     « Silo »): `readFollowCompleteness` answered 200, and every season's
     « owned/aired » is the operation's `owned/total` for that season;
  2. the Médiathèque sheet of the same followed series (`mediasheet-series`,
     « Silo (2023) », followed as « Silo »): the operation answered, and its
     season figures are the follow sheet's, word for word;
  3. a series nobody follows (`followsheet-gaps`, « Les aventures de Tintin »):
     the operation is not asked — there is no follow to ask it of — and the
     sheet keeps its own figures.
"""
import asyncio
import re

from common import PANEL_IN, SETTLED, Journal, open_page, read_at, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

READ = """(args) => {
  const [scope, follow] = args;
  const root = scope === 'sheet' ? document.querySelector('#sheet[data-open]')
                                 : document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]');
  const seasons = [...(root?.querySelectorAll('[data-part="season"] summary') ?? [])]
    .map((summary) => summary.textContent.replace(/\\s+/g, ' ').trim());
  const answer = follow ? window.__queries.getQueryData(['/api/v1/acquisition/followed', follow, 'completeness']) : null;
  const calls = window.__mocks.answered().filter((call) => call.operationId === 'readFollowCompleteness')
    .map((call) => call.path + ' ' + call.status);
  return {seasons, answer, calls};
}"""

FIGURE = re.compile(r"(\d+)\s+(\d+)/(\d+)")


def figures(summaries):
    """The « season → owned/aired » a list of season summaries draws.

    Args:
        summaries: Each season's summary text.

    Returns:
        A dict keyed by season number.
    """
    found = {}
    for text in summaries:
        match = FIGURE.search(text)
        if match:
            found[int(match.group(1))] = f"{match.group(2)}/{match.group(3)}"
    return found


def answered(answer):
    """The « season → owned/total » the completeness operation answered.

    Args:
        answer: The operation's answer from the query cache.

    Returns:
        A dict keyed by season number, empty when nothing was answered.
    """
    return {season["season"]: f"{min(season['owned'], season['total'])}/{season['total']}"
            for season in (answer or {}).get("seasons", []) if season["total"] > 0}


async def open_follow(page, title):
    """Opens the follow sheet of one title, from a reset layer.

    Args:
        page: The Playwright page.
        title: The follow.
    """
    await page.evaluate("(title) => { window.__mocks.reset(); window.__panel.produce('follow', title); }", title)
    await page.wait_for_timeout(PANEL_IN + SETTLED + SETTLED)


async def main():
    journal = Journal("R405 — one completeness")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        complete = await read_at(page, "followsheet-complete", READ, ["sheet", "American Dad!"],
                                 wait=PANEL_IN + SETTLED + SETTLED)
        journal.check("followsheet-complete: readFollowCompleteness answered 200",
                      any(call.endswith(" 200") for call in complete["calls"]), str(complete["calls"]))
        drawn, wanted = figures(complete["seasons"]), answered(complete["answer"])
        journal.check("followsheet-complete: every season's figure is the operation's",
                      bool(wanted) and drawn == wanted, str({"drawn": drawn, "answered": wanted}))

        await open_follow(page, "Silo")
        follow = await page.evaluate(READ, ["sheet", "Silo"])
        journal.check("« Silo », follow sheet: readFollowCompleteness answered 200",
                      any(call.endswith(" 200") for call in follow["calls"]), str(follow["calls"]))
        drawn, wanted = figures(follow["seasons"]), answered(follow["answer"])
        journal.check("« Silo », follow sheet: every season's figure is the operation's",
                      bool(wanted) and drawn == wanted, str({"drawn": drawn, "answered": wanted}))

        media = await read_at(page, "mediasheet-series", READ, ["screen", "Silo"], wait=PANEL_IN + SETTLED + SETTLED)
        journal.check("« Silo (2023) », Médiathèque sheet: readFollowCompleteness answered 200",
                      any(call.endswith(" 200") for call in media["calls"]), str(media["calls"]))
        journal.check("« Silo (2023) », Médiathèque sheet: the same season figures as the follow sheet",
                      bool(figures(media["seasons"])) and figures(media["seasons"]) == figures(follow["seasons"]),
                      str({"media": figures(media["seasons"]), "follow": figures(follow["seasons"])}))

        gaps = await read_at(page, "followsheet-gaps", READ, ["sheet", None], wait=PANEL_IN + SETTLED + SETTLED)
        journal.check("followsheet-gaps: a series nobody follows asks no completeness",
                      not any("aventures" in call for call in gaps["calls"]), str(gaps["calls"]))
        journal.check("followsheet-gaps: and keeps its own season figures", bool(figures(gaps["seasons"])),
                      str(gaps["seasons"][:3]))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
