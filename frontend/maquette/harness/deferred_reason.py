"""R265 — a medium deferred says why, on its card, for each of DOIT-2's three causes.

DOIT-2: a medium that waits says WHY it waits. A completed torrent the engine
does not take in is deferred for one of three causes, each a token of its own
— its ratio under the threshold, too little space, content still missing — and
the card in « En vol » says the cause its ladder carries, never a sentence
composed from another rollup. For the ratio cause it names the tracker and THAT
tracker's own threshold — never the global legacy one, which the next version
of the engine no longer reads.

1. `acq-card-deferred-ratio` — the card says its ratio on its tracker is under
   that tracker's own threshold, naming both;
2. `acq-card-deferred-space` — the card says there is too little space;
3. `acq-card-deferred-missing` — the card says content is still missing;
4. on each, the cause drawn is the one the served ladder carries, and no other
   card of « En vol » names a deferral.

The deferrals are DERIVATIONS, POSED and shown as such (`poseDeferral`): no card
of the real data is deferred.

Red before the move: no card names any of the three causes.
"""
import asyncio
import json
import pathlib

from common import SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
REASONS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["surfaces"]["ladder"]["reasons"]
SETTINGS = json.loads((SOURCE / "mocks/seeds/settings.json").read_text(encoding="utf-8"))

# Each posed state, the card it poses on, and the cause's token. A deferral
# happens BEFORE « arrivé » — a finished torrent the engine did not take in — so
# the subject is the one card of « En vol » that has not arrived yet.
SUBJECT = "This City Is Ours"
CASES = [
    ("acq-card-deferred-ratio", SUBJECT, "ratio_below_threshold"),
    ("acq-card-deferred-space", SUBJECT, "insufficient_space"),
    ("acq-card-deferred-missing", SUBJECT, "content_missing"),
]
# The ratio cause's tracker, and its own threshold against the global one.
TRACKER = "c411"


def setting(key):
    """A setting's raw value in the seeds, or None."""
    return next((row.get("raw") for topic in SETTINGS for row in topic["settings"] if row["key"] == key), None)


OWN = setting(f"tracker.providers.{TRACKER}.economy.min_ratio")
GLOBAL = setting("ingest.min_ratio")

CARDS = """() => [...document.querySelectorAll('#view [data-part="card"]')].map(card => ({
  title: card.querySelector('[data-part="card/title"]')?.textContent.trim() ?? '',
  reason: card.querySelector('[data-part="card/reason"]')?.textContent.trim() ?? '',
}))"""


def opening(token):
    """The words a cause's sentence opens with, before any value it names."""
    return REASONS.get(token, "<no copy>").split("{{")[0].strip()


def written(number):
    """A threshold as the interface writes it: a decimal comma, no trailing zero."""
    return f"{number:g}".replace(".", ",")


async def main():
    journal = Journal("R265 — a deferred medium says why, for each of DOIT-2's three causes")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        journal.check("the tracker's own threshold and the global one differ in the seeds",
                      OWN is not None and OWN != GLOBAL, f"own {OWN} · global {GLOBAL}")
        causes = [opening(token) for _, _, token in CASES]
        for state, title, token in CASES:
            answer = await page.evaluate(
                f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
            await page.wait_for_timeout(SETTLED)
            journal.check(f"the named state {state} exists", answer is None, answer or "")
            cards = await page.evaluate(CARDS)
            card = next((one for one in cards if one["title"] == title), {"reason": ""})
            journal.check(f"« {title} » says it is deferred, « {opening(token)} … »",
                          opening(token) in card["reason"], repr(card["reason"]))
            if token == "ratio_below_threshold":
                journal.check(f"it names {TRACKER} and its own threshold {written(OWN)}, never the global {written(GLOBAL)}",
                              TRACKER in card["reason"] and written(OWN) in card["reason"]
                              and f" {written(GLOBAL)}" not in card["reason"].replace(written(OWN), ""),
                              repr(card["reason"]))
            ladder = await page.evaluate(
                """(title)=>{const queue=window.__queries?.getQueryData(['/api/acquisition/to-handle','loaded'])||{};
                  const card=[...(queue.inFlight||[]),...(queue.arrivals||[])].find(one=>one.title===title);
                  return ((card&&card.ladder)||[]).map(rung=>rung.reason).filter(Boolean);}""", title)
            others = [one["title"] for one in cards if one["title"] != title
                      and any(cause in one["reason"] for cause in causes)]
            journal.check(f"{state}: the cause drawn is the one the ladder carries, and no other card names a deferral",
                          token in ladder and not others, f"ladder {ladder} · others {others}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
