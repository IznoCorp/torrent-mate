"""R129 — a paused tile SAYS it is paused (B-350).

THE OPERATOR READ IT ON HIS PHONE: a paused series in the follows grid is dimmed
and says nothing, while a paused film says « en pause ». One state, drawn twice,
announced once.

THE MECHANISM, and it is one character. The tile's caption was
`stFraction(follow) ?? (disabled ? paused : year)`, and `stFraction` answers
null for a FILM and only for a film (`legacy.js`: `if (follow.k === "movie")
return null`). Every series therefore has a fraction, the `??` never reached its
second branch for one, and the word was unreachable for exactly the media that
have episodes to count. A paused film said the word only because it had no
figure to say instead.

WHY THE DIMMING IS NOT THE ANSWER. It is real — the tile takes a muted class —
and it says « something », never what: the same grey covers a follow with no
verdict. A state the interface can act on is a state the interface names.

WHAT IT READS, and each fails differently:

  1. THE FIXTURE OFFERS BOTH KINDS PAUSED. Held first, because every hold below
     is vacuous over a grid with no paused tile in it — and until B-345's seeds
     there was none at rest at all.
  2. EVERY PAUSED TILE CARRIES THE WORD. The subject.
  3. A PAUSED SERIES KEEPS ITS FIGURE. The repair assembles the two rather than
     choosing between them; a repair that said the word INSTEAD of the fraction
     would pass hold 2 and lose what the tile is for.
  4. A TILE THAT IS NOT PAUSED DOES NOT CARRY THE WORD. Without it the rule is
     green over a build that writes « en pause » on everything, which is the
     cheapest way to satisfy hold 2 and the least true.
  5. NO ERROR IS RAISED.

IT ANCHORS ON NO CLASS. The dimmed tile is dimmed by a style class and nothing
else, and a rule may not select on one (the anchor arm's hard zero) — so which
tiles are paused is read from the LAYER, and each one is then found by the
address its own markup carries. That is also the stronger reading: it compares
the drawing against the data rather than against itself.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, open_page

from playwright.async_api import async_playwright

# WHERE THE TILES ARE. The follows tab in grid mode, which is the surface the
# operator was looking at.
GRID_STATE = "acq-follows-grid"

# THE WORD THE INTERFACE SAYS. French because it is the application's own
# rendered output — what a rule ASSERTS about the screen is the screen's
# language, and translating it here would stop measuring the thing reported.
PAUSED_WORD = "en pause"

# THE FOLLOWS THE LAYER HOLDS, with what each one is and what it counts. The
# fraction is rebuilt from the same two numbers the drawing reads, so hold 3
# compares two answers to one question rather than the drawing with itself.
FOLLOWS = """()=>(window.__followActions?.all() || []).map(
  (one) => ({t: one.t, k: one.k, st: one.st, own: one.own, aired: one.aired}))"""

# WHAT ONE TILE SAYS, found by the ADDRESS its markup carries rather than by its
# position: the grid is ordered and filtered by the layer, so an index here
# would read a different medium the day the order moves.
SUBTITLE_OF = """(title)=>{
  const tile = [...document.querySelectorAll('[data-part="tile"]')].find(
    (one) => one.dataset.mediasheet === title);
  if (!tile) return null;
  const said = tile.querySelector('[data-part="tile/subtitle"]');
  return said ? (said.textContent || '').trim() : "";}"""

TILES_DRAWN = """()=>document.querySelectorAll('[data-part="tile"]').length"""


async def main():
    journal = Journal("R129 — a paused tile says it is paused")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", GRID_STATE)
        await page.wait_for_timeout(SETTLED)

        drawn = await page.evaluate(TILES_DRAWN)
        journal.check(
            "the grid really draws tiles — a hold about what a tile says is "
            "vacuous over a grid with none",
            drawn > 0, f"{drawn} tile(s)")

        follows = await page.evaluate(FOLLOWS)
        paused = [one for one in follows if one["st"] == "disabled"]
        paused_shows = [one for one in paused if one["k"] == "show"]
        paused_movies = [one for one in paused if one["k"] == "movie"]
        journal.check(
            "the fixture offers a PAUSED series AND a paused film — the two "
            "halves the defect lived between (B-345 seeded them)",
            bool(paused_shows) and bool(paused_movies),
            f"shows={[one['t'] for one in paused_shows]} "
            f"movies={[one['t'] for one in paused_movies]}")

        said = {}
        for follow in paused:
            said[follow["t"]] = await page.evaluate(SUBTITLE_OF, follow["t"])
        journal.check(
            "every PAUSED tile carries the word — the series as much as the "
            "film (B-350)",
            bool(said) and all(
                one is not None and PAUSED_WORD in one.lower()
                for one in said.values()),
            str(said))

        # THE FIGURE SURVIVES THE WORD. A repair that said « en pause » in
        # place of « 4/9 » would pass the hold above and lose what a tile in a
        # follows grid is for.
        kept = {}
        for follow in paused_shows:
            fraction = f"{follow.get('own') or 0}/{follow.get('aired') or 0}"
            subtitle = said.get(follow["t"]) or ""
            kept[follow["t"]] = {"fraction": fraction, "said": subtitle}
        journal.check(
            "and a paused SERIES keeps its figure beside the word — the two are "
            "assembled, not chosen between",
            bool(kept) and all(
                one["fraction"] in one["said"] for one in kept.values()),
            str(kept))

        # THE NEGATIVE, without which the rule is green over a build that says
        # the word on every tile.
        others = [one for one in follows if one["st"] != "disabled"]
        spoken = {}
        for follow in others:
            subtitle = await page.evaluate(SUBTITLE_OF, follow["t"])
            if subtitle is not None:
                spoken[follow["t"]] = subtitle
        wrongly = {
            title: subtitle for title, subtitle in spoken.items()
            if PAUSED_WORD in subtitle.lower()
        }
        journal.check(
            "and a tile that is NOT paused does not carry it",
            bool(spoken) and not wrongly, f"{wrongly or 'none'} of {len(spoken)}")

        journal.check("and drawing the grid raises no error", not errors, str(errors))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
