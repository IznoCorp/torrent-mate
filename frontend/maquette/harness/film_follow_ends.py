"""R230 — a film's follow ends alone, when Plex confirms it; a series' never does.

Ruling 3: a film's follow ends by itself when the film is CONFIRMED in the
library — its last rung, « vérifié dans Plex », done — and it leaves « Suivis »
without a trace there. A series' follow never ends by itself.

The subject is Wicker, the one followed film in a live list (« à récupérer »):
its ladder laid one event away from the last rung is a DERIVATION from that real
row, shown as one (RULINGS 14). The event is the rung's move to done, which the
layer carries on `ItemProgressed` — the engine's per-item, per-step event; the
engine's own timing (it deletes a film's follow at detection) is a demand owed
(DESIGN § 6.2), and the maquette draws the ruling.

1. while its last rung is pending, the film is in « Suivis » — not ended one
   rung early;
2. the rung done, the film has left « Suivis »;
3. a followed series whose last rung is done is still there;
4. on that state, in the light theme, the `waiting` chip's text reads the tone's
   own text token, `--color-waiting-text`, and not the tone itself.

Red before the move: a followed film stays in « Suivis » for ever.

RE-AIMED OUT LOUD: the named state
acq-follows-film-at-plex-check is back — RULINGS 16 had removed it because the
`waiting` chip it draws failed light contrast (2.98:1) and no token passed. The
tone now has its text token, and hold 4 reads that the chip uses it; the rule
walks the state again instead of laying the ladder over acq-follows-list.
"""
import asyncio
import json
import pathlib

from common import SETTLED, Journal, open_page, chrome_launch_args
from playwright.async_api import async_playwright

SEEDS = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds"
FOLLOWS = json.loads((SEEDS / "follows.json").read_text(encoding="utf-8"))
TAKEABLE = {row["title"] for row in json.loads((SEEDS / "takeable.json").read_text(encoding="utf-8"))}
FILM = next(one["title"] for one in FOLLOWS if one["kind"] == "movie" and one["title"] in TAKEABLE)
SERIES = next(one["title"] for one in FOLLOWS if one["kind"] == "show" and one.get("status") != "disabled")

TITLES = """() => [...document.querySelectorAll('#view [data-part="card/title"]')].map(one => one.textContent)"""

# The first `waiting` chip's text colour in the light theme, beside the two
# colours it could be: the tone's text token and the tone itself, each resolved
# by a probe so the comparison is between computed values.
WAITING_COLOURS = """() => {
  document.documentElement.dataset.theme = "light";
  const chip = [...document.querySelectorAll('#view [data-part="chip"]')].find((one) => one.dataset.tone === "waiting");
  if (!chip) return null;
  const probe = document.createElement("span");
  document.body.append(probe);
  probe.style.color = "var(--color-waiting-text)";
  const token = getComputedStyle(probe).color;
  probe.style.color = "var(--color-waiting)";
  const tone = getComputedStyle(probe).color;
  probe.remove();
  return { chip: getComputedStyle(chip).color, token, tone };
}"""


async def main():
    journal = Journal("R230 — a film's follow ends when Plex confirms it")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await page.evaluate(
            "()=>{try{window.__go('acq-follows-film-at-plex-check');return null}catch(error){return String(error)}}")
        journal.check("the named state acq-follows-film-at-plex-check exists", answer is None, answer or "")
        await page.wait_for_timeout(SETTLED)
        # RE-AIMED OUT LOUD: « Suivis » is re-read from the layer AFTER the
        # state laid the ladder one event from the end. Read as the reset drew
        # it, the list came from a follows answer taken before that ladder
        # existed, so a film ended one rung early still showed — the hold was
        # green over nothing.
        await page.evaluate(
            "()=>window.__queries?.refetchQueries({ queryKey: ['/api/acquisition/followed'] })")
        await page.wait_for_timeout(SETTLED)
        before = await page.evaluate(TITLES)
        journal.check(f"while its last rung is pending, « {FILM} » is in « Suivis »",
                      FILM in before and SERIES in before, str(before))

        colours = await page.evaluate(WAITING_COLOURS)
        journal.check("in the light theme, the `waiting` chip's text reads --color-waiting-text, not the tone",
                      colours is not None and colours["chip"] == colours["token"] != colours["tone"],
                      str(colours))
        await page.evaluate("()=>{delete document.documentElement.dataset.theme}")

        confirmed = await page.evaluate(
            "(title)=>typeof window.__mocks?.confirmInPlex === 'function' && window.__mocks.confirmInPlex(title)", FILM)
        await page.wait_for_timeout(SETTLED)
        after = await page.evaluate(TITLES)
        journal.check("the rung done, the film has left « Suivis »",
                      confirmed and FILM not in after and SERIES in after, f"confirmed {confirmed}, {after}")

        confirmed = await page.evaluate(
            "(title)=>typeof window.__mocks?.confirmInPlex === 'function' && window.__mocks.confirmInPlex(title)", SERIES)
        await page.wait_for_timeout(SETTLED)
        series = await page.evaluate(TITLES)
        journal.check(f"a followed series confirmed in Plex, « {SERIES} », is still there",
                      confirmed and SERIES in series, f"confirmed {confirmed}, {series}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
