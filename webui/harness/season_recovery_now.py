"""R-season-recovery-a, -e and -g (the card) — a whole season's recovery in « En cours ».

The operator, 2026-09-29 17:36: « on doit pouvoir voir qu'une récupération de saison à été lancé et est
en cours, et on doit s'assuré qu'aucun téléchargement d'épisode de la saison se lance en parallèle »;
his Q6 = A: the acquisition card of an episode of that season is ABSORBED — the season's card covers
it; his Q19: an automatic recovery is told apart, lightly (DECIDED 8 = A: « S03 · auto »).

WHAT IT HOLDS:

  R-season-recovery-a  exclusive in « En cours »: at rest (the dense world holds Silo's S03 running)
                       and after the finger's ask from `season-recovery-before-ask`, no card of
                       « En vol » names an episode of a season whose season card of the same series
                       is drawn; « En vol »'s count equals the cards drawn; before the ask the
                       S03E07 card IS drawn (the hold reads a real absorption, not an empty list),
                       and the ask moves the count by zero (one card left, one came), the season's
                       card at the top.
  R-season-recovery-e  one card per season: a second ask queues nothing more and answers `reused`;
                       « En cours » holds exactly one « Silo · S03 » — and still one once the pack
                       has arrived in the staging area (`season-card-arrived`).
  R-season-recovery-g  the card's half: on `season-card-automatic` the season card's subtitle reads
                       « S03 · auto »; on the manual subject (`season-card-requested`) no « auto »;
                       no other card of « En vol » carries it (their trigger is unknown: nothing).

The ask is a FINGER's: the follow's row raised on « Suivis », « Récupérer la saison 3 » tapped in
its panel, « En cours » read back.
"""
import asyncio
import re

from common import SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SERIES = "Silo"
SEASON_LINE = "S03"
EPISODE = "S03E07"
AUTOMATIC = "S03 · auto"
GRAB = f"{SERIES}|3"

EN_VOL = """() => {
  const body = document.querySelector('[data-region="acquisition/body"]');
  const section = body ? body.querySelector('[data-part="section"]') : null;
  const tab = document.querySelector('[data-acqtab="now"] [data-part="segment/count"]');
  const cards = section ? [...section.querySelectorAll('[data-part="card"]')].map((card) => ({
    title: card.querySelector('[data-part="card/title"]')?.textContent.trim() ?? '',
    line: card.querySelector('[data-part="card/subtitle"]')?.textContent.trim() ?? '',
  })) : [];
  return {cards, count: tab ? Number(tab.textContent.trim()) : null};
}"""

RAISE = """(title) => {
  const row = [...document.querySelectorAll('#view [data-panel]')].find(
    (one) => one.dataset.panel === title || one.dataset.panel.endsWith(':' + title));
  if (!row) return {found: false};
  row.scrollIntoView({block: 'center'});
  const box = row.getBoundingClientRect();
  const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
  const mine = !!hit && (hit === row || row.contains(hit));
  if (mine) {
    // An icon is an SVGElement and has no `click` (B-364): it is sent the event a finger would.
    if (typeof hit.click === "function") hit.click();
    else hit.dispatchEvent(new MouseEvent("click", {bubbles: true, cancelable: true, view: window}));
  }
  return {found: true, reachable: mine};
}"""

TAP_GRAB = """(value) => {
  const act = document.querySelector(`[data-grab-season="${CSS.escape(value)}"]`);
  if (!act) return false;
  act.closest('details')?.setAttribute('open', '');
  act.scrollIntoView({block: 'center'});
  act.click();
  return true;
}"""

SAID = "()=>window.__toast?.read?.()?.message?.message || ''"

ASK_AGAIN = """async () => (await (await fetch('/api/v1/acquisition/follows/Silo/seasons/3/grab',
  {method: 'POST'})).json())"""


def season_cards(cards):
    """The season cards of the subject — its title, its line the season alone or « · auto »."""
    return [card for card in cards if card["title"] == SERIES and re.match(r"^S03( ·|$)", card["line"])]


def episodes_beside_a_season(cards):
    """Every card naming an episode of a season whose season card of the same series is drawn."""
    seasons = {(card["title"], card["line"][:3]) for card in cards if re.match(r"^S\d+( ·|$)", card["line"])}
    return [card for card in cards
            if re.match(r"^S\d+E\d+", card["line"]) and (card["title"], card["line"][:3]) in seasons]


async def read_now(page):
    """Puts the page on « En cours » and reads « En vol »."""
    await page.evaluate("()=>{window.__panel?.close?.(); window.__store.write({page: 'acq', acqTab: 'now'});"
                        " window.__store.touch?.();}")
    await page.wait_for_timeout(SETTLED)
    return await page.evaluate(EN_VOL)


async def main():
    """Runs the rule."""
    journal = Journal("R-season-recovery-a, -e, -g — a whole season's recovery in « En cours »")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── R-a at rest: the dense world holds the recovery running ────────────────
        await page.evaluate("()=>window.__go('acq-now-loaded')")
        await page.wait_for_timeout(SETTLED)
        rest = await page.evaluate(EN_VOL)
        journal.check("R-a, at rest: « Silo · S03 » is drawn in « En vol »",
                      len(season_cards(rest["cards"])) == 1, str(season_cards(rest["cards"])))
        journal.check("R-a, at rest: no card names an episode of a season whose season card is drawn",
                      not episodes_beside_a_season(rest["cards"]), str(episodes_beside_a_season(rest["cards"])))
        journal.check("R-a, at rest: « En vol »'s count equals the cards drawn",
                      rest["count"] == len(rest["cards"]), f"count {rest['count']}, cards {len(rest['cards'])}")

        # ── R-a after the finger's ask ────────────────────────────────────────────
        await page.evaluate("()=>window.__go('season-recovery-before-ask')")
        await page.wait_for_timeout(SETTLED)
        before = await page.evaluate(EN_VOL)
        journal.check("R-a, before the ask: the S03E07 card is drawn and no season card",
                      any(card["title"] == SERIES and card["line"].startswith(EPISODE) for card in before["cards"])
                      and not season_cards(before["cards"]), str(before["cards"][:3]))
        await page.evaluate("()=>{window.__store.write({page: 'acq', acqTab: 'follows', followMode: 'list',"
                            " pill: 'tout', filter: ''}); window.__store.touch?.();}")
        await page.wait_for_timeout(SETTLED)
        raised = await page.evaluate(RAISE, SERIES)
        journal.check("the finger raises Silo's follow panel from « Suivis »", raised.get("reachable"), str(raised))
        await page.wait_for_timeout(SETTLED)
        tapped = await page.evaluate(TAP_GRAB, GRAB)
        journal.check("the finger taps « Récupérer la saison 3 » in the panel", tapped, "")
        await page.wait_for_timeout(SETTLED)
        said = await page.evaluate(SAID)
        journal.check("the toast says the answer: the season asked, one episode to get",
                      "Silo" in said and "1 épisode" in said, repr(said))
        after = await read_now(page)
        journal.check("R-a, after the ask: the S03E07 card is gone",
                      not any(card["title"] == SERIES and card["line"].startswith(EPISODE) for card in after["cards"]),
                      str(after["cards"][:3]))
        journal.check("R-a, after the ask: « Silo · S03 » stands at the top of « En vol »",
                      bool(after["cards"]) and season_cards(after["cards"][:1]) != [], str(after["cards"][:2]))
        journal.check("R-a, after the ask: « En vol »'s count moved by zero and equals the cards drawn",
                      after["count"] == before["count"] == len(after["cards"]),
                      f"before {before['count']}, after {after['count']}, drawn {len(after['cards'])}")

        # ── R-e: one card per season ────────────────────────────────────────────
        again = await page.evaluate(ASK_AGAIN)
        journal.check("R-e: a second ask queues nothing more and answers `reused`",
                      again.get("reused") is True, str(again))
        await page.evaluate("()=>window.__queries.invalidateQueries({queryKey: ['/api/v1/acquisition/to-handle']})")
        twice = await read_now(page)
        journal.check("R-e: after two asks « En cours » holds exactly one « Silo · S03 »",
                      len(season_cards(twice["cards"])) == 1, str(season_cards(twice["cards"])))
        await page.evaluate("()=>window.__go('season-card-arrived')")
        await page.wait_for_timeout(SETTLED)
        arrived = await page.evaluate(EN_VOL)
        journal.check("R-e: once the pack has arrived, still exactly one « Silo · S03 »",
                      len(season_cards(arrived["cards"])) == 1, str(season_cards(arrived["cards"])))

        # ── R-g, the card's half ────────────────────────────────────────────────
        await page.evaluate("()=>window.__go('season-card-automatic')")
        await page.wait_for_timeout(SETTLED)
        automatic = await page.evaluate(EN_VOL)
        lines = [card["line"] for card in season_cards(automatic["cards"])]
        journal.check("R-g: an automatic recovery's card reads « S03 · auto » in its subtitle",
                      lines == [AUTOMATIC], str(lines))
        others = [card for card in automatic["cards"] if "auto" in card["line"] and card not in season_cards(
            automatic["cards"])]
        journal.check("R-g: no other card carries « auto » (its trigger is unknown)", not others, str(others))
        await page.evaluate("()=>window.__go('season-card-requested')")
        await page.wait_for_timeout(SETTLED)
        manual = await page.evaluate(EN_VOL)
        lines = [card["line"] for card in season_cards(manual["cards"])]
        journal.check("R-g: a manual recovery's card reads « S03 » and no « auto »",
                      lines == [SEASON_LINE], str(lines))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
