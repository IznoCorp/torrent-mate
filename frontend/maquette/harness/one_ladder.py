"""R207 — one ladder, from the wish to Plex, read by the card and the journey sheet.

Three lists used to answer « where is this medium »: the card's five-position
strip, the journey's five stages and the pipeline's nine steps. The ladder is
ONE list of eight rungs — demandé, cherché, attrapé, téléchargement, arrivé,
identifié, rangé, vérifié dans Plex — and the card's strip and the journey
sheet are two READERS of it (§13: one derivation per question).

What this holds, at the phone's real width:

1. THE CARD. On `acq-card-rungs` (« En vol ») and `acq-todo-loaded` (« À
   traiter »), every card on the ladder draws eight cells,
   its strip does not overflow, and line 2 names the current rung WHOLE (§12:
   nothing essential truncated) after its figure « n sur 8 », n being the
   current cell's position.
2. THE AGREEMENT. For every such card, the journey sheet opened on the same
   medium names the same current rung — the card and the sheet cannot disagree
   because they read one list. RE-AIMED OUT LOUD: the sheet is opened in the
   state that drew its card. It was opened in the LAST state for every card, so
   a card of the first state was read against the other world's journey, and
   agreed only while the reset re-read the queue under the previous state's
   scenario — an accident the frame's boot list carried, gone with it.
3. THE ORDER. The sheet draws the eight rungs in the ruled order, read from the
   i18n resources by their keys, and opens « rangé » into its three steps —
   trié, enrichi, rangé — from the same answer, right under it.
4. THE REASON. On `acq-card-blocked`, the card stopped on « identifié » is
   `blocked` there and carries its reason in full.

FIVE RUNGS, NOT EIGHT, ON THE CARDS (RULINGS 2, re-read): the cards live in
« En vol » and « À traiter », and there the real rows stand on téléchargement,
arrivé, identifié, rangé and vérifié dans Plex. RE-AIMED OUT LOUD: this hold
read six rungs on « En cours » alone, reached through the rows waiting to be
taken, found nothing and shelved today — which left « En cours ». No row is
invented to fill the picture; the eight are read whole on the sheet, where they
all exist. « vérifié dans Plex » is reached on the cards by ONE row, Star Trek's,
and that row is ruling 6's DERIVATION of its real settled row — a settled row
carrying no match to confirm joins neither list.

5. NO WISH OR SEARCH DONE WITHOUT ITS DATE (round one, A5). « demandé » and
   « cherché » are passed only on the date the row carries: on every such
   card's sheet, either one passed has a time. The later rungs' times come from
   the journey's shared template, an older defect this does not read.
6. A FOLDER DROPPED BY HAND STARTS AT « ARRIVÉ ». Nobody asked for it, searched
   it, took it or downloaded it: on its card the four rungs before « arrivé »
   are not passed.

THE CURRENT RUNG, RE-READ OUT LOUD: it was the first cell not passed. A rung
the row never lived now precedes the passed ones, so the current rung is the one
in motion, waiting or stopped, else the one after the last passed — on the card
and on the sheet alike.
"""
import asyncio
import json
import pathlib

from common import ACTED, PANEL_IN, SETTLED, Journal, open_page
from playwright.async_api import async_playwright

# The ruled order of the ladder, by the keys its names are written under.
RUNGS = ["requested", "searched", "grabbed", "downloading", "arrived",
         "identified", "shelved", "verified"]
# Where the cards on the ladder are drawn: what is in flight, and what waits for
# the operator's hand.
LADDER_STATES = ("acq-card-rungs", "acq-todo-loaded")
# The rungs the real rows stand on across those two lists. RE-AIMED OUT LOUD:
# « vérifié dans Plex » left it — only a DISAGREEING Plex match waits there, and
# no real row carries one; the eight are held whole on the journey sheet.
REACHED = {"downloading", "arrived", "identified", "shelved"}
# The three steps the sheet opens « rangé » into.
STEPS = ["sorted", "enriched", "shelved"]
# The rows the seeds say were dropped in the staging area by hand.
SEEDS = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds"
DROPPED = {row["title"] for name in ("stuck.json", "stuck-loaded.json")
           for row in json.loads((SEEDS / name).read_text(encoding="utf-8"))
           if row.get("droppedByHand")}
# The queue's rows stopped on the scrape: blocked on « identifié ».
BLOCKED_ROWS = {row["title"] for row in json.loads((SEEDS / "blocked.json").read_text(encoding="utf-8"))}
# The time a sheet draws for a rung nobody recorded one for.
NO_TIME = "—"
# The state of a rung the row has not reached, or never lived.
PENDING = "pending"


def named(rung):
    """The rung's name as a card draws it, bare or waiting on his answer.

    Args:
        rung: The name the card drew.

    Returns:
        The rung's own name: ruling 30 draws a rung waiting on the operator's
        answer as « <rung> — à confirmer », and that is still that rung.
    """
    template = LADDER.get("toConfirm", "")
    head, _, tail = template.partition("{{rung}}")
    if rung and template and rung.startswith(head) and rung.endswith(tail):
        return rung[len(head):len(rung) - len(tail)]
    return rung


def current_of(states):
    """The index of the rung a ladder stands on.

    Args:
        states: The rungs' states, in order.

    Returns:
        The rung in motion, waiting or stopped; else the one after the last
        passed; the last when every one is passed.
    """
    active = next((index for index, state in enumerate(states)
                   if state not in ("done", PENDING)), None)
    if active is not None:
        return active
    passed = max((index for index, state in enumerate(states) if state == "done"), default=-1)
    return min(passed + 1, len(states) - 1)

WORDS = json.loads((pathlib.Path(__file__).resolve().parents[1]
                    / "design/src/i18n/fr.json").read_text(encoding="utf-8"))
LADDER = WORDS["surfaces"].get("ladder", {"rungs": {}, "steps": {}, "step": "", "figure": ""})

CARDS = """() => [...document.querySelectorAll('#view [data-part="card"]')]
  .filter(card => card.querySelector('[data-part="card/strip"]'))
  .map(card => {
    const strip = card.querySelector('[data-part="card/strip"]');
    const cells = [...strip.querySelectorAll('[data-part="card/step"]')];
    const rung = card.querySelector('[data-part="card/meta"] [data-part="chip"]');
    const figure = card.querySelector('[data-part="card/meta"] > span:first-child');
    return {
      title: card.querySelector('[data-part="card/title"]').textContent,
      cells: cells.length,
      states: cells.map(cell => cell.dataset.state),
      overflow: strip.scrollWidth > strip.clientWidth + 1,
      rung: rung ? rung.textContent : null,
      rungWhole: rung ? rung.scrollWidth <= rung.clientWidth + 1 : false,
      figure: figure ? figure.textContent : null,
      reason: (card.querySelector('[data-part="card/reason"]') || {}).textContent || null,
    };
  })"""

SHEET = """() => [...document.querySelectorAll('#sheet[data-open] [data-part="key-value"]')]
  .map(row => ({
    name: row.firstElementChild.textContent,
    value: row.lastElementChild.textContent.trim(),
    tone: row.querySelector('[data-part="status-dot"]')?.dataset.tone ?? null,
    done: !!row.querySelector('[data-part="status-dot"][data-tone="success"]'),
  }))"""


async def go(page, journal, state):
    """Asks for a named state, and holds that it exists rather than crashing."""
    answer = await page.evaluate(
        "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
    journal.check(f"the named state {state} exists", answer is None, answer or "")


def rung_name(key):
    """The name a rung is drawn under."""
    return LADDER["rungs"].get(key, key)


def step_name(key):
    """The name a step of « rangé » is drawn under, as its line spells it."""
    return LADDER["step"].replace("{{name}}", LADDER["steps"].get(key, key))


async def main():
    journal = Journal("R207 — one ladder, read by the card and the journey sheet")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        cards = []
        for state in LADDER_STATES:
            await go(page, journal, state)
            await page.wait_for_timeout(SETTLED)
            cards += [{**card, "state": state} for card in await page.evaluate(CARDS)]
        journal.check("cards on the ladder are drawn", len(cards) >= 6, str(len(cards)))
        for card in cards:
            journal.check(
                f"« {card['title']} » draws eight cells, no overflow",
                card["cells"] == len(RUNGS) and not card["overflow"],
                f"{card['cells']} cells, overflow={card['overflow']}")
            card["current"] = current_of(card["states"])
            position = card["current"]
            expected_figure = LADDER["figure"].replace(
                "{{position}}", str(position + 1)).replace("{{count}}", str(len(RUNGS)))
            journal.check(
                f"« {card['title']} » names its current rung whole, after its figure",
                named(card["rung"]) == rung_name(RUNGS[position]) and card["rungWhole"]
                and card["figure"] == expected_figure,
                f"figure={card['figure']!r} rung={card['rung']!r} whole={card['rungWhole']}")
        reached = {RUNGS[card["current"]] for card in cards}
        journal.check("the real rows reach the rungs they stand on across « En vol » and « À traiter » (RULINGS 2)",
                      REACHED <= reached, f"{sorted(reached, key=RUNGS.index)} — wanted at least {sorted(REACHED, key=RUNGS.index)}")

        # THE AGREEMENT: the sheet opened on each card's medium names its rung,
        # in the state that drew the card.
        drawn_in = LADDER_STATES[-1]
        for card in cards:
            if card["state"] != drawn_in:
                drawn_in = card["state"]
                await go(page, journal, drawn_in)
                await page.wait_for_timeout(SETTLED)
            await page.evaluate(f"()=>window.__panel.produce('journey', {json.dumps(card['title'])})")
            await page.wait_for_timeout(PANEL_IN)
            rows = await page.evaluate(SHEET)
            ladder_rows = [row for row in rows if row["name"] in
                           {rung_name(key) for key in RUNGS}]
            # The sheet's pips: passed, not reached (neutral), or where it stands.
            sheet_states = ["done" if row["done"] else PENDING if row["tone"] == "neutral" else "now"
                            for row in ladder_rows]
            current = ladder_rows[current_of(sheet_states)]["name"] if ladder_rows else None
            journal.check(
                f"« {card['title']} »: the sheet's current rung is the card's",
                current is not None and current == named(card["rung"]),
                f"sheet={current!r} card={card['rung']!r}")
            # ONE SOURCE FOR THE STEPS TOO: past « rangé », its three steps are
            # passed — read from the answer, never from a list of the sheet's own.
            asked = [row for row in ladder_rows if row["name"] in (rung_name("requested"), rung_name("searched"))]
            journal.check(
                f"« {card['title']} »: « demandé » and « cherché », passed, carry their time",
                len(asked) == 2 and all(row["value"] != NO_TIME for row in asked if row["done"]),
                str([row["name"] for row in asked if row["done"] and row["value"] == NO_TIME]))
            if card["current"] > RUNGS.index("shelved") or all(state == "done" for state in card["states"]):
                steps = [row for row in rows if row["name"] in {step_name(key) for key in STEPS}]
                journal.check(
                    f"« {card['title']} »: past « rangé », the sheet's three steps are passed",
                    len(steps) == len(STEPS) and all(row["done"] for row in steps), str(steps))
            await page.evaluate("()=>window.__panel.close()")
            await page.wait_for_timeout(ACTED)

        # A FOLDER DROPPED BY HAND starts at « arrivé », in both worlds.
        await go(page, journal, "acq-card-requester")
        await page.wait_for_timeout(SETTLED)
        dropped = [card for card in cards + await page.evaluate(CARDS) if card["title"] in DROPPED]
        journal.check(
            "a folder dropped by hand passed no rung before « arrivé »",
            bool(DROPPED) and len({card["title"] for card in dropped}) >= 2
            and all(not any(state == "done" for state in card["states"][:RUNGS.index("arrived")])
                    for card in dropped),
            str([(card["title"], card["states"][:RUNGS.index("arrived")]) for card in dropped]))

        # THE ORDER, and « rangé » opened from the same answer.
        await page.evaluate("()=>window.__go('sheet-journey')")
        await page.wait_for_timeout(PANEL_IN)
        rows = [row["name"] for row in await page.evaluate(SHEET)]
        wanted = []
        for key in RUNGS:
            wanted.append(rung_name(key))
            if key == "shelved":
                wanted.extend(step_name(step) for step in STEPS)
        journal.check("the sheet draws the eight rungs in the ruled order, « rangé » "
                      "opened into its three steps right under it",
                      rows[:len(wanted)] == wanted, str(rows))

        # THE REASON, in full, under a blocked rung.
        await go(page, journal, "acq-card-blocked")
        await page.wait_for_timeout(SETTLED)
        # RE-AIMED OUT LOUD: « À traiter » also holds a card blocked on its LAST
        # rung (a Plex match to confirm); this hold reads the cards stopped on
        # « identifié ». A POSITIVE SUBJECT (round one, A12): it filtered the
        # cards blocked there and then asserted they were — true of any list.
        # It reads the rows the queue's seed says are stopped on the scrape.
        stopped = await page.evaluate(CARDS)
        blocked = [card for card in stopped if card["title"] in BLOCKED_ROWS]
        journal.check(
            "a card stopped on « identifié » is blocked there, with its reason in full",
            len(blocked) == len(BLOCKED_ROWS) and bool(blocked) and all(
                len(card["states"]) == len(RUNGS)
                and card["states"][RUNGS.index("identified")] == "blocked"
                and card["rung"] == rung_name("identified")
                and card["reason"] for card in blocked),
            str([(card["title"], card["rung"], bool(card["reason"])) for card in blocked]))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
