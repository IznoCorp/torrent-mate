"""R501 — each card of « À traiter » says its cause, and what lifts it (Q7).

Q7 of 2026-10-01: « chaque carte dit sa cause, ce qui la lève et où elle se
règle ». The cause and the lift share the card's reason line (maquette-blocked
§ 1.2); a block for his judgement keeps its acts and gains one obligation, a
cause line, always — a step that failed with no sentence says which step
(B-671: Furious stood under « Une étape ne passe pas » with no reason at all).

What this holds:

1. on every state of « À traiter » the lot draws, every card has a reason line,
   none empty;
2. on each external cause's state, the subject card's reason line holds the
   cause's sentence AND its lift's — read from `fr.json`, never retyped here;
3. on `acq-card-follow-error`, the tunnel error says which step failed.

Red before the lot: the five new causes have no state; Furious' card has no
reason line (maquette-blocked DESIGN § 0.1 item 6).
"""
import asyncio
import json
import pathlib

from common import SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
LADDER = WORDS["surfaces"]["ladder"]
STEP = WORDS["surfaces"]["card"].get("failedStep", "<no copy>")
STEP_NAMES = WORDS["screens"]["run"]["step"]

# Each external cause's state, the acquisition it poses on, and its token.
EXTERNAL = [
    ("acq-card-deferred-ratio", "This City Is Ours", "ratio_below_threshold"),
    ("acq-card-deferred-space", "This City Is Ours", "insufficient_space"),
    ("acq-card-deferred-missing", "This City Is Ours", "content_missing"),
    ("acq-block-library-full", "President Curtis", "library_full"),
    ("acq-block-tracker-unreachable", "Silo|S03", "tracker_unreachable"),
    ("acq-block-provider-unreachable", "Conclave", "provider_unreachable"),
    ("acq-block-plex-unreachable", "The Alabama Solution", "plex_unreachable"),
    ("acq-block-client-unreachable", "This City Is Ours", "client_unreachable"),
    ("acq-block-film", "Conclave", "library_full"),
]
# Every other state of « À traiter » whose cards are read for a reason line.
OTHERS = ("acq-todo-loaded", "acq-todo-dense", "acq-card-plex-disagrees", "acq-card-follow-error",
          "acq-todo-every-cause", "acq-block-ratio-no-threshold")
CARDS = """() => [...document.querySelectorAll('#view [data-region="acquisition/body"] [data-part="card"]')]
  .map(card => ({
    key: card.dataset.acquisition ?? '',
    title: card.querySelector('[data-part="card/title"]')?.textContent.trim() ?? '',
    reason: card.querySelector('[data-part="card/reason"]')?.textContent.trim() ?? '',
  }))"""


def opening(sentence):
    """The words a sentence opens with, before any value it names."""
    return sentence.split("{{")[0].strip()


def closing(sentence):
    """The words a sentence ends with, after the last value it names."""
    return sentence.split("}}")[-1].strip()


async def cards_at(page, journal, state):
    """Asks for a named state, holds that it exists, and reads its cards."""
    answer = await page.evaluate(
        "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
    await page.wait_for_timeout(SETTLED)
    journal.check(f"the named state {state} exists", answer is None, answer or "")
    return await page.evaluate(CARDS)


async def main():
    journal = Journal("R501 — each card of « À traiter » says its cause, and what lifts it")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for state, key, token in EXTERNAL:
            cards = await cards_at(page, journal, state)
            silent = [card["title"] for card in cards if not card["reason"]]
            journal.check(f"{state}: every card says its cause", bool(cards) and not silent, str(silent))
            card = next((one for one in cards if one["key"] == key), {"reason": ""})
            cause, lift = LADDER["reasons"].get(token, "<no copy>"), LADDER.get("lifts", {}).get(token, "<no copy>")
            journal.check(f"{state}: « {key} » says its cause « {opening(cause)} … » and its lift « {opening(lift)} … »",
                          opening(cause) in card["reason"] and opening(lift) in card["reason"]
                          and closing(lift) in card["reason"], repr(card["reason"]))

        for state in OTHERS:
            cards = await cards_at(page, journal, state)
            silent = [card["title"] for card in cards if not card["reason"]]
            journal.check(f"{state}: every card says its cause", bool(cards) and not silent, str(silent))
            if state == "acq-card-follow-error":
                furious = next((one for one in cards if one["title"] == "Furious"), {"reason": ""})
                said = STEP.replace("{{step}}", STEP_NAMES["scrape"])
                journal.check(f"{state}: the tunnel error says which step failed — « {said} »",
                              said in furious["reason"], repr(furious["reason"]))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
