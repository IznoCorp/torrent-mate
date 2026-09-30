"""R411 — the ladder's words, and « enrichi » unfolded (L24, DOIT-1, OPEN 5 = B).

The operator, 2026-09-29, « B »: on the journey sheet « enrichi » unfolds into
what the enrichment fetched — the metadata, the posters, the trailer — each with
its own state; the card's ladder keeps its eight rungs (round 5 Q4).

WHAT IS READ:

  1. `sheet-journey-enriched-unfolded`: right under « · enrichi » stand its
     three parts, in the seed's order, each spelled from the ladder's one
     vocabulary (`surfaces.ladder`), each with the state the medium's own
     journey read holds for it;
  2. every line of that sheet is a word of that vocabulary — a rung, a step or
     a part — never one typed elsewhere;
  3. on « En cours » (`acq-card-rungs`), every card's fraction counts the
     eight rungs and its chip names a rung — the unfold is the sheet's alone.
"""
import asyncio
import json
import pathlib

from common import PANEL_IN, SETTLED, Journal, open_page, read_at, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
LADDER = WORDS["surfaces"]["ladder"]
# The decision block shares the sheet; its rows are R401's to read.
BLOCK_ROWS = {WORDS["surfaces"]["decision"][key] for key in ("chosen", "among", "by", "when", "state")}
SUBJECT = "President Curtis"
PIP = {"done": "success", "now": "info", "waiting": "waiting", "blocked": "danger",
       "aside": "neutral", "skipped": "neutral", "pending": "neutral"}
RUNG_COUNT = len(LADDER["rungs"])


def step_word(token):
    """A step's line, as the vocabulary spells it."""
    return LADDER["step"].replace("{{name}}", LADDER["steps"][token])


def part_word(token):
    """A part of « enrichi »'s line, as the vocabulary spells it."""
    return LADDER["subStep"].replace("{{name}}", LADDER["steps"][token])


VOCABULARY = ({*LADDER["rungs"].values()} | {step_word(token) for token in LADDER["steps"]}
              | {part_word(token) for token in LADDER["steps"]})

SHEET = """(subject) => ({
  rows: [...document.querySelectorAll('#sheet[data-open] [data-part="key-value"]')].map((row) => ({
    name: row.querySelector(':scope > span')?.textContent.trim(),
    tone: row.querySelector('[data-part="status-dot"]')?.dataset.tone ?? null})),
  stages: window.__queries.getQueryData(['/api/acquisition/journeys', subject]) ?? []})"""

CARDS = """() => [...document.querySelectorAll('#view [data-part="card"]')].map((card) => ({
  text: card.textContent.replace(/\\s+/g, ' '),
  chips: [...card.querySelectorAll('[data-part="chip"]')].map((chip) => chip.textContent.trim())}))"""


async def main():
    journal = Journal("R411 — the ladder's words, and « enrichi » unfolded")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        seen = await read_at(page, "sheet-journey-enriched-unfolded", SHEET, SUBJECT, wait=PANEL_IN + SETTLED)
        shelved = next((stage for stage in seen["stages"] if stage["rung"] == "shelved"), {})
        enriched = next((step for step in shelved.get("steps", []) if step["rung"] == "enriched"), {})
        parts = enriched.get("steps", [])
        journal.check("the journey read holds « enrichi »'s three parts", len(parts) == 3, str(parts))
        names = [row["name"] for row in seen["rows"]]
        at = names.index(step_word("enriched")) if step_word("enriched") in names else -1
        drawn = seen["rows"][at + 1:at + 1 + len(parts)] if at >= 0 else []
        journal.check("right under « enrichi », its parts, each spelled from the one vocabulary",
                      [row["name"] for row in drawn] == [part_word(part["rung"]) for part in parts],
                      str([row["name"] for row in drawn]))
        journal.check("each part with the state its journey holds",
                      len(drawn) == len(parts) and all(row["tone"] == PIP[part["state"]] for row, part in zip(drawn, parts)),
                      str([(row["tone"], part["state"]) for row, part in zip(drawn, parts)]))
        journal.check("the parts are not all at one state — each says its own",
                      len({part["state"] for part in parts}) > 1, str([part["state"] for part in parts]))
        stray = [name for name in names if name not in VOCABULARY]
        stray = [name for name in stray if name not in BLOCK_ROWS]
        journal.check("every ladder line of the sheet is a word of the one vocabulary", stray == [], str(stray))

        cards = await read_at(page, "acq-card-rungs", CARDS)
        counted = LADDER["figure"].split("{{position}}")[1].replace("{{count}}", str(RUNG_COUNT))
        fractions = [card for card in cards if counted not in card["text"]]
        journal.check(f"every card on « En cours » counts the {RUNG_COUNT} rungs, never the parts",
                      cards and fractions == [], str([card["text"][:60] for card in fractions]))
        rungs = set(LADDER["rungs"].values())
        journal.check("every card names a rung, never a step nor a part",
                      all(any(chip in rungs for chip in card["chips"]) for card in cards),
                      str([card["chips"] for card in cards]))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
