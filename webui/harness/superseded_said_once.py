"""R505 — a release chosen earlier and arrived later is not filed, its torrent seeds, and it is said once (Q9).

Q9 of 2026-10-01: « au rangement, le DERNIER CHOISI gagne […] une release
choisie plus tôt qui arrive après n'est PAS rangée, son torrent continue de
semer, son tunnel se ferme avec la raison « remplacé par un choix plus récent »,
dite une fois dans « À traiter », écartée par « × » » — for every medium,
films included. DECIDED 2: « Marquer comme vu » in the card's panel, no « × ».
A pack that superseded one episode only goes to its end; the episode kept is
named in its journey, and no card is drawn (maquette-blocked § 1.6).

What this holds:

1. `acq-superseded-episode` (Silo · S03E07, chosen before the season's pack,
   arrived after it) and `acq-superseded-film` (Conclave's 2160p, chosen
   before the 1080p in place): the card says « Remplacé par un choix plus
   récent : <winner> est en place. » with the winner's release line, then
   « Son torrent continue de semer. »; chip « clos » neutral; foot « Voir la
   fiche » alone, no « × »;
2. its torrent is a SEEDING row of Trackers › « Torrents », under its own
   release name;
3. BY FINGER on the film: the card's panel offers « Marquer comme vu »; a tap
   on it removes the card, the badge −1;
4. `acq-superseded-seen`: the episode's card gone, the badge −1;
5. `acq-superseded-pack-keeps-newer`: no card for the pack nor the episode, and
   the pack's journey says « S03E07 — gardé : choisi plus récemment ».

Red before the lot's phase 5: no superseded card exists (DESIGN § 4).
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
KEPT = JOURNEY.get("keptNewer", "<no copy>")
SEEDING = WORDS["screens"]["torrents"]["states"]["seeding"]
SUPERSEDED = CLOSURE.get("superseded", "<no copy>")
STILL_SEEDING = CLOSURE.get("seeding", "<no copy>")

# Each superseded release: its state, the card's key, the release in place, and its own torrent.
EPISODE = ("acq-superseded-episode", "Silo|S03E07", "Silo.S03.MULTi.1080p.WEB-DL.DDP5.1.H264-FRATERNITY",
           "Silo.S03E07.MULTi.1080p.WEB-DL.DDP5.1.H264-FRATERNITY")
FILM = ("acq-superseded-film", "Conclave", "Conclave.2024.MULTi.1080p.WEB-DL.H264-FW",
        "Conclave.2024.MULTi.2160p.WEB-DL.DV.HDR.H265-FW")
PACK = "Silo|S03"
KEPT_EPISODE = "S03E07"

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
BADGE = """() => {
  const badge = document.querySelector('#nav button[data-page="acq"] [data-part="shell/tab-badge"]');
  return badge ? Number(badge.textContent.trim()) : 0;
}"""
ACTIONS = """() => [...document.querySelectorAll('#sheet[data-open] [data-part="sheet/action"]')]
  .map(action => action.textContent.trim())"""
JOURNEY_LINES = """() => [...document.querySelectorAll('#sheet[data-open] [data-part="key-value"]')]
  .map(row => row.textContent.replace(/\\s+/g, ' ').trim())"""
# The Torrents tab, asked for as a page's dials are: the downloads read again.
TO_TORRENTS = """() => {
  window.__queries?.removeQueries({queryKey: ['/api/v1/acquisition/downloads']});
  window.applyState({page: 'trackers', trackersTab: 'torrents', phase: 'ready'});
}"""
TORRENT = """(name) => {
  const row = [...document.querySelectorAll('#view [data-part="torrents/row"]')]
    .find(one => one.querySelector('[data-part="card/title"]')?.textContent.trim() === name);
  return row ? row.querySelector('[data-part="chip"]')?.textContent.trim() ?? '' : null;
}"""
CARD_BUTTONS = {"card/poster", "card/folder", "card/body", "card/foot"}


async def go(page, journal, state):
    """Asks for a named state and holds that it exists."""
    answer = await page.evaluate(
        "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
    await page.wait_for_timeout(SETTLED)
    journal.check(f"the named state {state} exists", answer is None, answer or "")


def said(card, winner):
    """Whether a superseded card says the winner in place, the torrent seeding, « clos » and « Voir la fiche » alone."""
    sentence = SUPERSEDED.replace("{{winner}}", winner)
    return (card is not None and sentence in card["reason"] and STILL_SEEDING in card["reason"]
            and card["chip"] == CLOSED and card["tone"] == "neutral" and card["feet"] == [SEE_SHEET]
            and set(card["buttons"]) <= CARD_BUTTONS)


async def main():
    journal = Journal("R505 — a superseded release is said once, its torrent still seeding")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── 1–2. the card says it; its torrent seeds ───────────────────────
        badges = {}
        for state, key, winner, own in (EPISODE, FILM):
            await go(page, journal, state)
            card = await page.evaluate(CARD, key)
            badges[state] = await page.evaluate(BADGE)
            journal.check(f"{state}: « {key} » says it was replaced by « {winner} », its torrent still seeding; "
                          f"chip « {CLOSED} », foot « {SEE_SHEET} » alone, no « × »", said(card, winner), str(card))
            await page.evaluate(TO_TORRENTS)
            await page.wait_for_timeout(ACTED)
            chip = await page.evaluate(TORRENT, own)
            journal.check(f"{state}: its torrent « {own} » is a row of « Torrents », « {SEEDING} »",
                          chip == SEEDING, repr(chip))

        # ── 3. dismissed by finger: the film ───────────────────────────────
        await go(page, journal, FILM[0])
        body = page.locator(f'#view [data-part="card"][data-acquisition="{FILM[1]}"] [data-part="card/body"]')
        if await body.count():
            await body.first.tap()
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        actions = await page.evaluate(ACTIONS)
        journal.check(f"a finger on the film's card opens its panel, « {MARK_SEEN} » among its actions",
                      MARK_SEEN in actions, str(actions))
        mark = page.locator('#sheet[data-open] [data-part="sheet/action"]', has_text=MARK_SEEN)
        if await mark.count():
            await mark.first.tap()
        await page.wait_for_timeout(ACTED)
        keys, badge = await page.evaluate(KEYS), await page.evaluate(BADGE)
        journal.check(f"a finger on « {MARK_SEEN} » removes the film's card, the badge −1",
                      FILM[1] not in keys and badge == badges[FILM[0]] - 1, f"{keys} · badge {badge}")

        # ── 4. the episode, seen ───────────────────────────────────────────
        await go(page, journal, "acq-superseded-seen")
        await page.wait_for_timeout(PANEL_IN + ACTED + SETTLED)
        keys, badge = await page.evaluate(KEYS), await page.evaluate(BADGE)
        journal.check("acq-superseded-seen: the episode's card is gone, the badge −1",
                      EPISODE[1] not in keys and badge == badges[EPISODE[0]] - 1, f"{keys} · badge {badge}")

        # ── 5. the pack that kept a newer episode: no card, a journey line ─
        await go(page, journal, "acq-superseded-pack-keeps-newer")
        await page.wait_for_timeout(PANEL_IN)
        keys = await page.evaluate(KEYS)
        lines = await page.evaluate(JOURNEY_LINES)
        kept = KEPT.replace("{{episode}}", KEPT_EPISODE)
        journal.check("acq-superseded-pack-keeps-newer: no closure card for the pack nor the episode",
                      PACK not in keys and EPISODE[1] not in keys, str(keys))
        journal.check(f"the pack's journey says « {kept} »", any(line.startswith(kept) for line in lines), str(lines))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
