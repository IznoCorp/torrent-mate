"""R504 — a tunnel whose medium vanished is closed, said once, and « Marquer comme vu » dismisses it (Q8).

Q8 of 2026-10-01: « un tunnel dont le média a disparu (torrent retiré, fichiers
absents) se ferme avec sa raison ; la carte le dit une fois dans « À traiter »,
écartée par « × » (= vu) ; rangé à la main ailleurs, il part simplement ; un
média qui revient plus tard ouvre un nouveau tunnel. » DECIDED 2 (his word, C):
no « × » on the card — a tap opens its bottom panel, and « Marquer comme vu »
is one of its actions. The seen mark is the engine's (BK5).

What this holds:

1. `acq-closure-torrent-removed` and `acq-closure-files-absent`: the closure
   card stands in « À traiter », its chip « clos » in the neutral tone, its
   reason line saying why it closed and that a return opens a new tunnel, its
   foot « Voir la fiche » alone — no « × », no other button;
2. BY FINGER: a tap on the card opens its panel, « Marquer comme vu » among
   its actions; a tap on it removes the card, the tab's count and the
   Acquisition badge −1;
3. the queue read again from the layer does not bring it back (the seen mark
   is the engine's, not the cache's);
4. the named states `acq-closure-panel` and `acq-closure-seen` show the panel
   and the card gone;
5. `acq-closure-dismiss-failed`: the write refused, the card is back and the
   error is said;
6. `acq-closure-filed-by-hand`: no card, in « À traiter » nor in « En cours »;
7. `acq-closure-medium-back`: a new card in « En cours », the old closure
   still in « À traiter », unseen;
8. `acq-closure-two-one-title`: two closures of ONE title (Silo · S03 and Silo
   · S03E07) each stand as a card; « Marquer comme vu » from the episode's
   card removes that card and leaves the season's — the panel acts on the
   TOUCHED card's acquisition, never on the first closure of its title (M1 of
   the lot's reading).

WHAT IT DOES NOT READ: a reload of the DOCUMENT — the mock's world resets with
the document (`rights_frame.py`'s note), so a posed closure cannot outlive one.
Hold 3 reads what a reload does to the data: the queue asked again.

Red before the lot's phase 5: no closure exists; the mock re-opens a vanished
row (DESIGN § 4).
"""
import asyncio
import json
import pathlib

from common import ACTED, PANEL_IN, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
CLOSURE = WORDS["surfaces"]["card"].get("closure", {})
CLOSED = WORDS["surfaces"]["ladder"].get("closed", "<no copy>")
JOURNEY = WORDS["panels"]["journey"]
MARK_SEEN = JOURNEY.get("markSeen", "<no copy>")
SEE_SHEET = JOURNEY["seeSheet"]
REFUSED = WORDS["verbs"]["acquisition"].get("closureSeenRefused", "<no copy>")


def opening(sentence):
    """The words a sentence opens with, before any value it names."""
    return sentence.split("{{")[0].strip()


SUBJECT = "This City Is Ours"
# Two closures of one title: the season's pack and an episode of it.
SEASON_CLOSED = "Silo|S03"
EPISODE_CLOSED = "Silo|S03E07"
# Each closure of a vanished medium, the card it is posed on, and its reason.
CLOSURES = [
    ("acq-closure-torrent-removed", SUBJECT, "torrent_removed"),
    ("acq-closure-files-absent", "President Curtis", "files_absent"),
]

CARD = """(key) => {
  const card = [...document.querySelectorAll('#view [data-region="acquisition/body"] [data-part="card"]')]
    .find(one => one.dataset.acquisition === key);
  if (!card) return null;
  const chip = card.querySelector('[data-part="card/meta"] [data-part="chip"]');
  return {reason: card.querySelector('[data-part="card/reason"]')?.textContent.trim() ?? '',
    chip: chip?.textContent.trim() ?? '', tone: chip?.dataset.tone ?? '',
    feet: [...card.querySelectorAll('[data-part="card/foot"]')].map(foot => foot.textContent.trim()),
    buttons: [...card.querySelectorAll('button')].map(button => button.dataset.part)};
}"""
KEYS = """() => [...document.querySelectorAll('#view [data-region="acquisition/body"] [data-part="card"]')]
  .map(card => card.dataset.acquisition)"""
TODO_COUNT = """() => {
  const count = document.querySelector('[data-acqtab="todo"] [data-part="segment/count"]');
  return count ? Number(count.textContent.trim()) : 0;
}"""
BADGE = """() => {
  const badge = document.querySelector('#nav button[data-page="acq"] [data-part="shell/tab-badge"]');
  return badge ? Number(badge.textContent.trim()) : 0;
}"""
ACTIONS = """() => [...document.querySelectorAll('#sheet[data-open] [data-part="sheet/action"]')]
  .map(action => action.textContent.trim())"""
MESSAGE = """() => {
  const host = document.querySelector('#toast');
  return host && host.dataset.shown !== undefined ? document.querySelector('#toastmsg').textContent.trim() : '';
}"""
# The buttons a card of the one markup draws: its poster or folder, its body, its feet.
CARD_BUTTONS = {"card/poster", "card/folder", "card/body", "card/foot"}


async def go(page, journal, state):
    """Asks for a named state and holds that it exists."""
    answer = await page.evaluate(
        "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
    await page.wait_for_timeout(SETTLED)
    journal.check(f"the named state {state} exists", answer is None, answer or "")


async def tab(page, name):
    """A finger on one of Acquisition's tabs."""
    await page.locator(f"[data-acqtab={name}]").first.tap()
    await page.wait_for_timeout(SETTLED)


async def tap_card(page, key):
    """A finger on a card's body: its bottom panel rises."""
    body = page.locator(f'#view [data-part="card"][data-acquisition="{key}"] [data-part="card/body"]')
    if await body.count():
        await body.first.tap()
    await page.wait_for_timeout(PANEL_IN + SETTLED)


async def tap_action(page, label):
    """A finger on one action of the open panel."""
    action = page.locator('#sheet[data-open] [data-part="sheet/action"]', has_text=label)
    if await action.count():
        await action.first.tap()
    await page.wait_for_timeout(ACTED)


def said(card, reason):
    """Whether a closure card says its reason, the reopening, « clos » neutral, and « Voir la fiche » alone."""
    return (card is not None and opening(CLOSURE.get(reason, "<no copy>")) in card["reason"]
            and CLOSURE.get("reopens", "<no copy>") in card["reason"]
            and card["chip"] == CLOSED and card["tone"] == "neutral" and card["feet"] == [SEE_SHEET]
            and set(card["buttons"]) <= CARD_BUTTONS)


async def main():
    journal = Journal("R504 — a vanished medium is said once, « Marquer comme vu » dismisses it")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── 1. the closure card says it ────────────────────────────────────
        for state, key, reason in CLOSURES:
            await go(page, journal, state)
            card = await page.evaluate(CARD, key)
            journal.check(f"{state}: « {key} » says « {opening(CLOSURE.get(reason, '<no copy>'))} … » and the "
                          f"reopening, chip « {CLOSED} » neutral, foot « {SEE_SHEET} » alone, no « × »",
                          said(card, reason), str(card))

        # ── 2–3. dismissed by finger, for good ─────────────────────────────
        await go(page, journal, "acq-closure-torrent-removed")
        before = {"count": await page.evaluate(TODO_COUNT), "badge": await page.evaluate(BADGE)}
        await tap_card(page, SUBJECT)
        actions = await page.evaluate(ACTIONS)
        journal.check(f"a finger on the card opens its panel, « {MARK_SEEN} » among its actions",
                      MARK_SEEN in actions, str(actions))
        await tap_action(page, MARK_SEEN)
        after = {"keys": await page.evaluate(KEYS), "count": await page.evaluate(TODO_COUNT),
                 "badge": await page.evaluate(BADGE)}
        journal.check(f"a finger on « {MARK_SEEN} » removes the card; the count and the badge −1",
                      SUBJECT not in after["keys"] and after["count"] == before["count"] - 1
                      and after["badge"] == before["badge"] - 1, f"before {before} · after {after}")
        await page.evaluate("()=>window.__queries.removeQueries({queryKey:['/api/v1/acquisition/to-handle']})")
        await tab(page, "now")
        await tab(page, "todo")
        again = await page.evaluate(KEYS)
        journal.check("the queue asked again from the layer does not bring it back (the seen mark is the engine's)",
                      SUBJECT not in again and await page.evaluate(BADGE) == after["badge"], str(again))

        # ── 4. the panel and the seen, as named states ─────────────────────
        await go(page, journal, "acq-closure-panel")
        await page.wait_for_timeout(PANEL_IN + ACTED)
        actions = await page.evaluate(ACTIONS)
        journal.check(f"acq-closure-panel: the card's panel is up, « {MARK_SEEN} » among its actions",
                      MARK_SEEN in actions, str(actions))
        await go(page, journal, "acq-closure-seen")
        await page.wait_for_timeout(PANEL_IN + ACTED + SETTLED)
        keys, badge = await page.evaluate(KEYS), await page.evaluate(BADGE)
        journal.check("acq-closure-seen: the card is gone, the badge −1",
                      SUBJECT not in keys and badge == before["badge"] - 1, f"{keys} · badge {badge}")

        # ── 5. the write refused ───────────────────────────────────────────
        await go(page, journal, "acq-closure-dismiss-failed")
        await page.wait_for_timeout(PANEL_IN + ACTED + SETTLED)
        card, message = await page.evaluate(CARD, SUBJECT), await page.evaluate(MESSAGE)
        journal.check(f"acq-closure-dismiss-failed: the card is back and the error said — « {opening(REFUSED)} … »",
                      said(card, "torrent_removed") and opening(REFUSED) in message and await page.evaluate(BADGE)
                      == before["badge"], f"{card} · {message!r}")

        # ── 6. filed by hand: no card at all ───────────────────────────────
        await go(page, journal, "acq-closure-filed-by-hand")
        todo = await page.evaluate(KEYS)
        await tab(page, "now")
        now = await page.evaluate(KEYS)
        journal.check("acq-closure-filed-by-hand: no card for it, in « À traiter » nor in « En cours »",
                      SUBJECT not in todo and SUBJECT not in now and len(todo) == before["count"] - 1,
                      f"todo {todo} · now {now}")

        # ── 7. the medium back: a new tunnel ───────────────────────────────
        await go(page, journal, "acq-closure-medium-back")
        card = await page.evaluate(CARD, SUBJECT)
        await tab(page, "now")
        fresh = await page.evaluate(CARD, SUBJECT)
        journal.check("acq-closure-medium-back: a new card in « En cours », the old closure still unseen in « À traiter »",
                      said(card, "torrent_removed") and fresh is not None and fresh["chip"] != CLOSED,
                      f"todo {card} · now {fresh}")

        # ── 8. two closures, one title: the touched one is seen ───────────
        await go(page, journal, "acq-closure-two-one-title")
        posed = await page.evaluate(KEYS)
        both = [await page.evaluate(CARD, key) for key in (SEASON_CLOSED, EPISODE_CLOSED)]
        await tap_card(page, EPISODE_CLOSED)
        await tap_action(page, MARK_SEEN)
        left = await page.evaluate(KEYS)
        journal.check(f"acq-closure-two-one-title: « {MARK_SEEN} » on « {EPISODE_CLOSED} » removes that card and "
                      f"keeps « {SEASON_CLOSED} »",
                      None not in both and EPISODE_CLOSED not in left and SEASON_CLOSED in left, f"posed {posed} · left {left}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
