"""R-season-recovery-c — the absorbed episode's journey points to the season's card, and the pointer is followed.

The operator's Q6 = A: the absorbed episode's journey points to the season's card (constitution § 13,
« suivre le pointeur »); Q15 = A: the pointer leads to the Acquisition tab that holds the season's
card, that card visible and highlighted; Q14 = A: one journey per acquisition; Q16 = A: the season's
journey lists each episode it covers, with its state, each a path to its own journey.

WHAT IT HOLDS, by finger:

  the pointer      on `absorbed-journey-pointer` the episode's journey draws the note « couvert par la
                   récupération de la saison 3 » and its primary action « Voir la carte de la saison »;
                   a finger on it lands on « En cours », the card « Silo|S03 » inside the viewport,
                   focused and highlighted. Walked whole by finger from « Suivis », Retour then gives
                   back the episode's journey over « Suivis » — the link stacked (§ 16, Q12).
  stopped          on `absorbed-journey-pointer-blocked` the same finger lands on « À traiter », where
                   the season's card now stands — never a fixed « En cours ».
  ended            on `absorbed-journey-pointer-ended` the note says the season reached the library
                   and the primary action is « Voir la fiche »: a pointer never lands on nothing.
  the season's     on `season-card-journey` the season's journey names S03E07, « téléchargement déjà en
  journey          cours », and a finger on it opens that episode's own journey. Each journey names its
                   OWN acquisition's release — the season's pack for S03, the episode's for S03E07 —
                   and its own times, never one journey's for both; the season's download still
                   running, its journey offers no « Remettre en file ».
"""
import asyncio

from common import PANEL_IN, SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SEASON_CARD = "Silo|S03"
EPISODE = "Silo|S03E07"
COVERED = "couvert par la récupération de la saison 3"  # french-ok: the pointer's note, asserted as drawn
ENDED = "arrivée en médiathèque"  # french-ok: the ended pointer's note, asserted as drawn
SEE_CARD = "Voir la carte de la saison"  # french-ok: the pointer's action, asserted as drawn
SEE_SHEET = "Voir la fiche"  # french-ok: the ended pointer's action, asserted as drawn
RUNNING = "S03E07 — téléchargement déjà en cours"  # french-ok: the covered episode's line, asserted as drawn
REQUEUE = "Remettre en file"  # french-ok: the tunnel's requeue act, asserted absent on a running download
PACK = "Silo.S03.MULTi"
EPISODE_RELEASE = "Silo.S03E07."

SHEET = """() => {
  const sheet = document.querySelector('#sheet');
  if (!sheet || !sheet.hasAttribute('data-open')) return {open: false};
  const actions = [...sheet.querySelectorAll('[data-part="sheet/action"]')];
  return {
    open: true,
    title: (sheet.querySelector('[data-part="sheet/title"]') || {}).textContent || '',
    meta: (sheet.querySelector('[data-part="sheet/meta"]') || {}).textContent || '',
    times: [...sheet.querySelectorAll('[data-part="key-value"]')].map((one) => one.textContent.trim()),
    text: sheet.innerText,
    actions: actions.map((one) => ({text: one.textContent.trim(), tone: one.dataset.tone || '',
                                     go: one.dataset.go || '', dial: one.dataset.dial || '',
                                     journey: one.dataset.journey || ''})),
  };
}"""

TAP = """(text) => {
  const act = [...document.querySelectorAll('#sheet [data-part="sheet/action"]')]
    .find((one) => one.textContent.trim() === text);
  if (!act) return false;
  act.scrollIntoView({block: 'center'});
  act.click();
  return true;
}"""

LANDED = """(key) => {
  const card = [...document.querySelectorAll('#view [data-part="card"][data-acquisition]')]
    .find((one) => one.dataset.acquisition === key);
  const tab = document.querySelector('[data-acqtab][aria-selected="true"]');
  const state = window.__store.read().state;
  if (!card) return {card: false, tab: tab ? tab.dataset.acqtab : null, page: state.page, acqTab: state.acqTab};
  const box = card.getBoundingClientRect();
  return {card: true, page: state.page, acqTab: state.acqTab,
          inView: box.top >= 0 && box.bottom <= window.innerHeight,
          focused: document.activeElement === card, landed: card.hasAttribute('data-landed'),
          outline: getComputedStyle(card).outlineStyle};
}"""


async def follow(page, journal, state, where, tab):
    """Opens a covered episode's journey, taps its pointer, and reads where it landed."""
    await page.evaluate("(id)=>window.__go(id)", state)
    await page.wait_for_timeout(PANEL_IN + SETTLED)
    sheet = await page.evaluate(SHEET)
    journal.check(f"{where}: the episode's journey draws the note « {COVERED} »",
                  sheet["open"] and COVERED in sheet.get("text", ""), sheet.get("text", "")[:200])
    primary = [one for one in sheet.get("actions", []) if one["tone"] == "primary"]
    journal.check(f"{where}: its primary action is « {SEE_CARD} », the landing naming the season's card",
                  bool(primary) and primary[0]["text"] == SEE_CARD
                  and primary[0]["dial"] == f"{tab}:{SEASON_CARD}", str(primary))
    journal.check(f"{where}: the episode is not relaunched alone from its journey (no « Remettre en file »)",
                  not any("Remettre en file" in one["text"] for one in sheet.get("actions", [])),  # french-ok: an action asserted absent
                  str([one["text"] for one in sheet.get("actions", [])]))
    tapped = await page.evaluate(TAP, SEE_CARD)
    await page.wait_for_timeout(SETTLED * 3)
    landed = await page.evaluate(LANDED, SEASON_CARD)
    journal.check(f"{where}: the finger lands on the tab holding the season's card ({tab})",
                  tapped and landed["page"] == "acq" and landed["acqTab"] == tab, str(landed))
    journal.check(f"{where}: that card is in the viewport, focused and highlighted",
                  landed.get("card") and landed.get("inView") and landed.get("focused") and landed.get("landed")
                  and landed.get("outline") == "solid", str(landed))
    return landed


async def main():
    """Runs the rule."""
    journal = Journal("R-season-recovery-c — the absorbed episode's journey points to the season's card")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await follow(page, journal, "absorbed-journey-pointer", "live", "now")

        # ── THE WHOLE WALK, BY FINGER, so Retour reads the history a hand writes ──
        await page.evaluate("()=>window.__go('acq-now-loaded')")
        await page.wait_for_timeout(SETTLED)
        await page.tap('[data-acqtab="follows"]')
        await page.wait_for_timeout(SETTLED)
        await page.locator('#view [data-panel$=":Silo"], #view [data-panel="Silo"]').first.tap()
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        await page.locator('#sheet [data-journey]').first.tap()
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        await page.locator(f'#sheet [data-journey="{EPISODE}"]').tap()
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        await page.locator(f'#sheet [data-dial="now:{SEASON_CARD}"]').tap()
        await page.wait_for_timeout(SETTLED * 3)
        landed = await page.evaluate(LANDED, SEASON_CARD)
        journal.check("by finger: « Suivis » → Silo → « Voir le parcours » → S03E07 → « Voir la carte de la saison » "
                      "lands on « En cours », the card highlighted",
                      landed.get("acqTab") == "now" and landed.get("landed"), str(landed))
        await page.go_back()
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        back = await page.evaluate("""() => ({tab: window.__store.read().state.acqTab,
          title: document.querySelector('#sheet[data-open] [data-part="sheet/title"]')?.textContent || ''})""")
        journal.check("Retour gives back the episode's journey, over the page it was opened on, « Suivis »",
                      back == {"tab": "follows", "title": "Silo · S03E07"}, str(back))

        await follow(page, journal, "absorbed-journey-pointer-blocked", "stopped", "todo")

        await page.evaluate("()=>window.__go('absorbed-journey-pointer-ended')")
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        sheet = await page.evaluate(SHEET)
        primary = [one for one in sheet.get("actions", []) if one["tone"] == "primary"]
        journal.check("ended: the note says the season reached the library",
                      sheet["open"] and ENDED in sheet.get("text", ""), sheet.get("text", "")[:200])
        journal.check("ended: the primary action is « Voir la fiche », and no « Voir la carte de la saison »",
                      bool(primary) and primary[0]["text"] == SEE_SHEET
                      and not any(one["text"] == SEE_CARD for one in sheet.get("actions", [])), str(primary))

        await page.evaluate("()=>window.__go('season-card-journey')")
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        sheet = await page.evaluate(SHEET)
        season_sheet = sheet
        journal.check("the season's journey names the season's pack, its own release",
                      PACK in sheet.get("meta", ""), sheet.get("meta", ""))
        journal.check("the season's download still running, its journey offers no « Remettre en file »",
                      not any(one["text"] == REQUEUE for one in sheet.get("actions", [])),
                      str([one["text"] for one in sheet.get("actions", [])]))
        covered = [one for one in sheet.get("actions", []) if one["text"] == RUNNING]
        journal.check("the season's journey names S03E07, « téléchargement déjà en cours », a path to its journey",
                      len(covered) == 1 and covered[0]["journey"] == EPISODE,
                      str([one["text"] for one in sheet.get("actions", [])]))
        await page.evaluate(TAP, RUNNING)
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        sheet = await page.evaluate(SHEET)
        journal.check("a finger on it opens that episode's own journey — its pointer drawn",
                      sheet["open"] and COVERED in sheet.get("text", ""), sheet.get("title", ""))
        journal.check("the episode's journey names the episode's own release, and its own times — not the season's",
                      EPISODE_RELEASE in sheet.get("meta", "") and PACK not in sheet.get("meta", "")
                      and sheet.get("times") and sheet.get("times") != season_sheet.get("times"),
                      f"{sheet.get('meta')!r} {sheet.get('times')} vs {season_sheet.get('times')}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
