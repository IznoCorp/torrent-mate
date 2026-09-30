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
   card of « En vol » names a deferral;
5. the ratio cause offers « Voir le tracker » on its card, and neither other
   cause does;
6. a finger on it lands on the Trackers tab with that tracker's entry open —
   `/trackers?tracker=<name>` read on the address, the « Trackers » tab being the
   page's default and so never written (`list=` names only « Torrents ») — as an
   arrival (the history grows by one);
7. a ratio deferral on a tracker with NO threshold of its own says it has none —
   never an invented « seuil de 0 ».

RE-AIMED OUT LOUD (correction round C16): hold 1 found the threshold's digits
anywhere in the reason — « 1 » is already in « c411 », so a wrong threshold
stayed green; it now reads the whole sentence, the tracker and ITS threshold in
their places. Hold 7 is new, red while a tracker with no `min_ratio` read « 0 ».

The deferrals are DERIVATIONS, POSED and shown as such (`poseDeferral`): no card
of the real data is deferred.

Red before the move: no card names any of the three causes.
"""
import asyncio
import json
import pathlib

from common import SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
LADDER = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["surfaces"]["ladder"]
REASONS = LADDER["reasons"]
# The tracker with no threshold of its own: its policy is unset in the seeds.
UNSET = "tr4ker"
# The reads a card's ladder is drawn from, as the posed states drop them.
QUEUE = "['/api/acquisition/to-handle']"
STAGED = "['/api/staging/media']"
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

WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["acquisition"]
PATH_WORDS = WORDS.get("ratioReasonTracker", "<no copy>")
PATH = """(title) => [...document.querySelectorAll('#view [data-part="card"]')]
  .filter(card => card.querySelector('[data-part="card/title"]')?.textContent.trim() === title)
  .flatMap(card => [...card.querySelectorAll('[data-part="card/foot"]')])
  .filter(foot => foot.textContent.trim() === %s).length""" % json.dumps(PATH_WORDS, ensure_ascii=False)
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
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
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
                sentence = REASONS[token].replace("{{tracker}}", TRACKER).replace("{{minimum}}", written(OWN))
                journal.check(f"it names {TRACKER} and its own threshold {written(OWN)}, never the global {written(GLOBAL)}"
                              f" — « {sentence} »", sentence in card["reason"], repr(card["reason"]))
            ladder = await page.evaluate(
                """(title)=>{const queue=window.__queries?.getQueryData(['/api/acquisition/to-handle','loaded'])||{};
                  const card=[...(queue.inFlight||[]),...(queue.arrivals||[])].find(one=>one.title===title);
                  return ((card&&card.ladder)||[]).map(rung=>rung.reason).filter(Boolean);}""", title)
            offered = await page.evaluate(PATH, title)
            journal.check(f"{state}: « {PATH_WORDS} » is offered {'on the ratio cause' if token == 'ratio_below_threshold' else 'on no other cause'}",
                          offered == (1 if token == "ratio_below_threshold" else 0), str(offered))
            others = [one["title"] for one in cards if one["title"] != title
                      and any(cause in one["reason"] for cause in causes)]
            journal.check(f"{state}: the cause drawn is the one the ladder carries, and no other card names a deferral",
                          token in ladder and not others, f"ladder {ladder} · others {others}")

        # ── a finger on « Voir le tracker » ───────────────────────────────
        await page.evaluate("()=>window.__go('acq-card-deferred-ratio')")
        await page.wait_for_timeout(SETTLED)
        before = await page.evaluate("()=>history.length")
        foot = page.locator('#view [data-part="card/foot"]', has_text=PATH_WORDS)
        if await foot.count():
            await foot.first.tap()
            await page.wait_for_timeout(SETTLED)
        where = await page.evaluate("""()=>({path: location.pathname, search: location.search, length: history.length,
            tab: document.querySelector('[data-trackers-tab="trackers"]')?.getAttribute('aria-selected'),
            open: document.querySelector(`#view [data-part="trackers/entry"][data-tracker="c411"] details[open]`) !== null})""")
        journal.check(f"a finger on « {PATH_WORDS} » lands on the Trackers tab, {TRACKER}'s entry open, as an arrival",
                      where["path"].endswith("/trackers") and where["tab"] == "true"
                      and "list=torrents" not in where["search"] and f"tracker={TRACKER}" in where["search"] and where["open"] and where["length"] == before + 1,
                      f"{where} · history.length {before}")

        # ── a tracker with no threshold of its own ─────────────────────────
        await page.evaluate("()=>window.__go('acq-card-deferred-ratio')")
        await page.wait_for_timeout(SETTLED)
        await page.evaluate(f"""async ()=>{{window.__mocks?.poseDeferral('{SUBJECT}', 'ratio_below_threshold', '{UNSET}');
            await window.__queries?.invalidateQueries({{queryKey: {QUEUE}}});
            await window.__queries?.invalidateQueries({{queryKey: {STAGED}}});}}""")
        await page.wait_for_timeout(SETTLED)
        card = next((one for one in await page.evaluate(CARDS) if one["title"] == SUBJECT), {"reason": ""})
        sentence = LADDER.get("ratioWithoutThreshold", "<no copy>").replace("{{tracker}}", UNSET)
        journal.check(f"deferred on {UNSET}, which has no threshold, the card says so — « {sentence} », never « seuil de 0 »",
                      sentence in card["reason"] and "seuil de 0" not in card["reason"], repr(card["reason"]))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
