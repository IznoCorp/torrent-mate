"""R229 — « Suivre » is proposed on a series that arrived, and never done unasked.

Ruling 1: an arrival creates a PUNCTUAL acquisition, never a follow. On the card
of an arrival that is an IDENTIFIED SERIES nobody follows, the interface
PROPOSES the follow — a foot on the card and the same action in its panel (one
card, one behaviour) — and nothing is followed until it is tapped. No offer on a
film, on a card without identity (nothing to follow yet), or on a series
already followed. And a card born of an arrival is never drawn in « Suivis »,
even the episode of a followed series (OPEN 3, ruled A): « Suivis » lists
follows only.

Every subject is read off the seeds the layer answers from: a series is what
carries a TVDB identifier (the series provider), a follow is matched by any
shared provider identifier — never by a title written here.

1. the arrivals changed the follows list by NOTHING;
2. the unfollowed arrived series (« Les Zinzins de l'Espace ») carries the
   offer, and its panel offers « Suivre »;
3. no film, no card without identity, no followed series carries it;
4. a tap changes the follows list by exactly ONE, and the offer goes;
5. « Suivis » draws no card born of an arrival: no requester line, no ladder;
6. a ONE-OFF season (round 10 Q2: a season asked of a series nobody follows,
   `Requester.via` = `request`) is offered « Suivre » the same way — its card
   in « En vol » and its panel (RULINGS 28). The subject is the first
   incomplete show of the seeds that is a series nobody follows with a hole
   the seasons data holds, asked through the season's own operation.

Red before the move: an arrival card carries no offer.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page, chrome_launch_args
from playwright.async_api import async_playwright

SEEDS = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds"
FOLLOWS = json.loads((SEEDS / "follows.json").read_text(encoding="utf-8"))
MOVING = json.loads((SEEDS / "moving.json").read_text(encoding="utf-8"))
INCOMPLETE = json.loads((SEEDS / "incomplete-shows.json").read_text(encoding="utf-8"))


def followed(ids):
    """Whether a follow shares one provider identifier with these."""
    ids = ids or {}
    return any(str(ids.get(key)) == str(value)
               for follow in FOLLOWS for key, value in (follow.get("ids") or {}).items()
               if value is not None and ids.get(key) is not None)


SERIES = [row["title"] for row in MOVING if (row.get("ids") or {}).get("tvdb") and not followed(row.get("ids"))]
FILMS = [row["title"] for row in MOVING if row.get("ids") and not row["ids"].get("tvdb")]
FOLLOWED = [row["title"] for row in MOVING if followed(row.get("ids"))]
OFFERED = SERIES[0] if SERIES else None

CARDS = """() => [...document.querySelectorAll('#view [data-part="card"]')].map(card => ({
  title: card.querySelector('[data-part="card/title"]').textContent,
  offer: [...card.querySelectorAll('[data-part="card/foot"]')]
    .some(foot => foot.getAttribute('data-follow') === card.querySelector('[data-part="card/title"]').textContent),
}))"""
COUNT = "() => (window.__followActions?.all() || []).length"

# A season with a hole, of the first unfollowed incomplete series that has one.
ONE_OFF_SUBJECT = """(titles)=>{
  for (const title of titles) {
    const hole = (window.__mocks.seasonFamily()[title] || []).find(
      ([number, aired, owned]) => (owned || 0) < (aired || 0));
    if (hole) return {title, season: hole[0]};
  }
  return null;}"""
ASK_ONCE = """async ({title, season})=>{
  const answer = await fetch(`/api/acquisition/follows/${encodeURIComponent(title)}/seasons/${season}/grab`,
    {method: 'POST'});
  await window.__queries.invalidateQueries({queryKey: ['/api/acquisition/to-handle']});
  return answer.status;}"""
PANEL_ACTIONS = """()=>{const sheet=document.querySelector('#sheet');
    if(!sheet||!sheet.hasAttribute('data-open')) return null;
    return [...sheet.querySelectorAll('[data-part="sheet/action"]')]
      .map(one=>({text: one.textContent.trim(), follow: (one.getAttribute('data-follow') || '') !== ''}));}"""


async def main():
    journal = Journal("R229 — « Suivre » proposed on an arrived series, never done unasked")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        journal.check("the seeds hold an unfollowed arrived series, a film and a followed series",
                      OFFERED is not None and FILMS and FOLLOWED, f"{SERIES} / {FILMS} / {FOLLOWED}")
        answer = await page.evaluate(
            "()=>{try{window.__go('acq-now-loaded');return null}catch(error){return String(error)}}")
        journal.check("the named state acq-now-loaded exists", answer is None, answer or "")
        await page.wait_for_timeout(SETTLED)
        before = await page.evaluate(COUNT)
        journal.check("the arrivals changed the follows list by nothing",
                      before == len(FOLLOWS), f"{before} follows, {len(FOLLOWS)} seeded")

        cards = {card["title"]: card["offer"] for card in await page.evaluate(CARDS)}
        journal.check(f"« {OFFERED} » carries the offer", cards.get(OFFERED) is True, str(cards))
        wrongly = [title for title in FILMS + FOLLOWED if cards.get(title)]
        journal.check("no film and no followed series carries it",
                      all(title in cards for title in FILMS + FOLLOWED) and not wrongly,
                      f"offered on {wrongly}, drawn {sorted(cards)}")
        without_identity = await page.evaluate("""()=>[...document.querySelectorAll('#view [data-part="card"][data-nonmedia]')]
            .filter(card => [...card.querySelectorAll('[data-part="card/foot"]')]
              .some(foot => (foot.getAttribute('data-follow') || '') !== '')).length""")
        journal.check("no card without identity carries it", without_identity == 0, str(without_identity))

        # ── its panel offers « Suivre » ────────────────────────────────────
        await page.evaluate("""(title)=>[...document.querySelectorAll('#view [data-part="card"]')]
            .find(card => card.querySelector('[data-part="card/title"]').textContent === title)
            ?.querySelector('[data-part="card/body"]')?.click()""", OFFERED)
        await page.wait_for_timeout(ACTED)
        panel = await page.evaluate("""()=>{const sheet=document.querySelector('#sheet');
            if(!sheet||!sheet.hasAttribute('data-open')) return null;
            return [...sheet.querySelectorAll('[data-part="sheet/action"]')]
              .map(one=>({text: one.textContent.trim(), follow: (one.getAttribute('data-follow') || '') !== ''}));}""")
        journal.check("its panel offers « Suivre »",
                      panel is not None and any(one["follow"] and "Suivre" in one["text"] for one in panel), str(panel))
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(ACTED)

        # ── a tap follows it, once ─────────────────────────────────────────
        tapped = await page.evaluate("""(title)=>{const foot=[...document.querySelectorAll('#view [data-part="card/foot"]')]
            .find(one => one.getAttribute('data-follow') === title); if(!foot) return false; foot.click(); return true;}""", OFFERED)
        await page.wait_for_timeout(SETTLED)
        after = await page.evaluate(COUNT)
        still = {card["title"]: card["offer"] for card in await page.evaluate(CARDS)}
        journal.check("a tap changes the follows list by exactly one, and the offer goes",
                      tapped and after == before + 1 and still.get(OFFERED) is False,
                      f"tapped {tapped}, {before} → {after}, offer {still.get(OFFERED)}")

        # ── « Suivis » lists follows only ──────────────────────────────────
        await page.evaluate("()=>document.querySelector('[data-acqtab=\"follows\"]')?.click()")
        await page.wait_for_timeout(SETTLED)
        arrivals = await page.evaluate("""()=>({
            requester: document.querySelectorAll('#view [data-part="card/requester"]').length,
            ladder: document.querySelectorAll('#view [data-part="card/step"]').length,
            rows: document.querySelectorAll('#view [data-part="card/title"]').length})""")
        journal.check("« Suivis » draws no card born of an arrival",
                      arrivals["rows"] > 0 and arrivals["requester"] == 0 and arrivals["ladder"] == 0, str(arrivals))

        # ── a one-off season is offered « Suivre » too ─────────────────────
        await page.evaluate("()=>window.__go('acq-now-loaded')")
        await page.wait_for_timeout(SETTLED)
        unfollowed = [row["title"] for row in INCOMPLETE
                      if (row.get("ids") or {}).get("tvdb") and not followed(row.get("ids"))]
        subject = await page.evaluate(ONE_OFF_SUBJECT, unfollowed)
        journal.check("the seeds hold an unfollowed incomplete series with a hole", subject is not None,
                      str(unfollowed))
        if subject is not None:
            status = await page.evaluate(ASK_ONCE, subject)
            await page.wait_for_timeout(SETTLED)
            title = subject["title"]
            cards = {card["title"]: card["offer"] for card in await page.evaluate(CARDS)}
            journal.check(f"the one-off season's card (« {title} ») carries the offer",
                          cards.get(title) is True, f"asked {status}; {cards}")
            await page.evaluate("""(title)=>[...document.querySelectorAll('#view [data-part="card"]')]
                .find(card => card.querySelector('[data-part="card/title"]').textContent === title)
                ?.querySelector('[data-part="card/body"]')?.click()""", title)
            await page.wait_for_timeout(ACTED)
            panel = await page.evaluate(PANEL_ACTIONS)
            journal.check("and its panel offers « Suivre »",
                          panel is not None and any(one["follow"] and "Suivre" in one["text"] for one in panel),
                          str(panel))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
