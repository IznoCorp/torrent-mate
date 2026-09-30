"""R-C1-a — the save bar is the frame's, and leaving with a change waiting asks, three ways out.

The operator, 2026-09-29 (ruling C1): « On parle de toutes les pages de réglages ?
Si oui alors oui. Si on veux quitter réglages un message de confirmation s'affiche,
avec enregistrer, abandonné les modif, ou fermer rester sur réglages »; on
Trackers: « Oui ». `docs/reference/operator-method.md` § 3, Rd Q4.

The bar (`settings-save-bar-frame`):
1. cold Réglages, nothing waiting: no bar; one edit filed: the bar, inside the
   frame, above the tab bar — on the rubric list, in a rubric, and on Trackers
   once a finger turns a tracker's switch; never over another page with the
   same edit waiting;
2. the named states `settings-save-bar-frame` and `settings-leave-confirm` exist
   and draw what they name.

Leaving (`settings-leave-confirm`), from Réglages with an edit waiting:
3. each way of leaving asks, and the page stays drawn under the confirmation —
   the bar, the menu, the account sheet's link, and Retour; the drawn Retour of a
   rubric, which stays on Réglages, does not;
4. its three choices are « Enregistrer », « Abandonner les modifications »,
   « Rester sur Réglages » — « Rester sur Trackers » on Trackers;
5. « Rester » closes it: Réglages, the edit still waiting; and Retour after it
   asks again;
6. « Abandonner les modifications » drops the edits and leaves — Retour lands
   where it would have; nothing was written;
7. « Enregistrer » writes the file, then leaves — from Réglages by the menu, and
   from Trackers by the bar.

Red on `main` (`4f6704ccd`): the two named states do not exist, and every way of
leaving leaves at once, the edit left waiting where no bar shows it.
"""
import asyncio
import json
import pathlib

from common import ACTED, PAGE_PATHS, PANEL_IN, PHONE, PROTOTYPE, SETTLED, Journal, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((ROOT / "i18n/fr.json").read_text(encoding="utf-8"))
# Read with a default, so the rule runs to its end on a build that has no such
# words — its red is then every hold, never a KeyError.
SETTINGS_WORDS = {key: WORDS["screens"]["settings"].get(key, f"<{key}>") for key in (
    "leaveHeading", "leaveSave", "leaveAbandon", "leaveStay")}
PAGE_NAMES = WORDS["navigation"]["pages"]
# The setting every walk files: a threshold of Réglages' own « acquisition » rubric.
EDITED = "thresholds:thresholds.min_free_space_staging_gb"
# A tracker the operator switched off: a finger turns it back on, as a pending edit.
OFF_BY_OPERATOR = "draupnirr.xyz"

WHERE = """() => ({
  page: window.state?.page ?? null,
  path: decodeURIComponent(location.pathname),
  waiting: window.SETTINGS_STATE?.modifs.size ?? null,
  bar: (() => {
    const bar = document.querySelector('#savebar');
    if (!bar) return null;
    const box = bar.getBoundingClientRect();
    const device = document.querySelector('#device').getBoundingClientRect();
    const tabs = document.querySelector('[data-part="shell/tab-bar"]')?.getBoundingClientRect();
    return {inside: box.bottom <= device.bottom + 1 && box.top >= device.top && box.width > 0,
            aboveTabs: tabs ? box.bottom <= tabs.top + 1 : true,
            inView: !!bar.closest('#view')};
  })(),
  dialog: (() => {
    const dialog = document.querySelector('#dlg[data-open]');
    if (!dialog) return null;
    return {heading: dialog.querySelector('h2')?.textContent.trim() ?? '',
            text: dialog.textContent,
            buttons: [...dialog.querySelectorAll('[data-part="dialog/button"]')].map(b => b.textContent.trim())};
  })(),
  written: (window.__mocks?.answered() || []).filter(call => call.operationId === 'updateConfigurationFile').length,
})"""


def stay_words(page):
    """The third choice's words, for the page being left."""
    return SETTINGS_WORDS["leaveStay"].replace("{{page}}", PAGE_NAMES[page])


def three_choices(page):
    """The three choices, in their order."""
    return [SETTINGS_WORDS["leaveSave"], SETTINGS_WORDS["leaveAbandon"], stay_words(page)]


async def open_at(browser, page_id):
    """A fresh phone context, cold at a page's address, past the startup screen."""
    context = await browser.new_context(**PHONE)
    page = await context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    await page.goto(PROTOTYPE + PAGE_PATHS[page_id].lstrip("/"), wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(SETTLED)
    return context, page, errors


async def file_an_edit(page):
    """Files one pending edit of Réglages, as its field would."""
    await page.evaluate("""(identifier)=>{
      const setting = window.__queries.getQueryData(['/api/config/schema']).flatMap(t => t.settings)
        .find(s => window.settingId(s) === identifier);
      window.__changeSetting(identifier, Number(setting.raw) + 7);}""", EDITED)
    await page.wait_for_timeout(ACTED)


async def tap(page, selector, wait=ACTED):
    """A finger on the first element a selector names; False when there is none."""
    target = page.locator(selector)
    if not await target.count():
        return False
    await target.first.tap()
    await page.wait_for_timeout(wait)
    return True


async def choose(page, words):
    """A finger on the confirmation's choice that says `words` — none when it is not up."""
    choice = page.locator('#dlg[data-open] [data-part="dialog/button"]', has_text=words)
    if not await choice.count():
        return
    await choice.first.tap()
    await page.wait_for_timeout(ACTED * 2)


async def where(page):
    """Where the interface is, and what it shows."""
    return await page.evaluate(WHERE)


def asked(seen, page_id):
    """Whether the confirmation is up over `page_id`, with its three choices."""
    return (seen["dialog"] is not None and seen["page"] == page_id
            and seen["dialog"]["heading"] == SETTINGS_WORDS["leaveHeading"]
            and seen["dialog"]["buttons"] == three_choices(page_id))


async def hold_the_bar(browser, journal):
    """Holds 1–2: the bar is the frame's, on the pages that hold edits only."""
    context, page, errors = await open_at(browser, "cfg")
    at_rest = await where(page)
    await file_an_edit(page)
    listed = await where(page)
    entered = await tap(page, '#view [data-topic="acquisition"]')
    rubric = await where(page)
    journal.check("R-C1-a 1: cold Réglages, nothing waiting — no bar",
                  at_rest["page"] == "cfg" and at_rest["bar"] is None, repr(at_rest))
    journal.check("R-C1-a 1: one edit filed — the bar, inside the frame, above the tab bar, on the rubric list",
                  listed["bar"] is not None and listed["bar"]["inside"] and listed["bar"]["aboveTabs"]
                  and not listed["bar"]["inView"], repr(listed))
    journal.check("R-C1-a 1: and in a rubric, entered by a finger",
                  entered and rubric["bar"] is not None and rubric["waiting"] == 1, f"{entered} {rubric!r}")
    for other in ("lib", "acq", "sys"):
        await page.evaluate("(p)=>{window.__store.write({page: p}); window.__store.touch();}", other)
        await page.wait_for_timeout(ACTED)
        away = await where(page)
        journal.check(f"R-C1-a 1: never over « {PAGE_NAMES[other]} », the edit still waiting",
                      away["page"] == other and away["bar"] is None and away["waiting"] == 1, repr(away))
    journal.check("R-C1-a 1: no JS error on the bar's walk", not errors, str(errors))
    await context.close()

    context, page, errors = await open_at(browser, "trackers")
    await tap(page, '[data-trackers-tab="trackers"]')
    switched = await tap(page, f'#view [data-tracker-switch="{OFF_BY_OPERATOR}"]')
    trackers = await where(page)
    journal.check("R-C1-a 1: on Trackers, a finger on a tracker's switch raises the frame's bar",
                  switched and trackers["page"] == "trackers" and trackers["bar"] is not None
                  and not trackers["bar"]["inView"], f"{switched} {trackers!r}")
    await context.close()

    context, page, errors = await open_at(browser, "cfg")
    for state in ("settings-save-bar-frame", "settings-leave-confirm"):
        answer = await page.evaluate(
            "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
        await page.wait_for_timeout(PANEL_IN)
        seen = await where(page)
        if state == "settings-save-bar-frame":
            journal.check(f"R-C1-a 2: `{state}` draws the frame's bar over Réglages",
                          answer is None and seen["bar"] is not None and seen["dialog"] is None, answer or repr(seen))
        else:
            journal.check(f"R-C1-a 2: `{state}` draws the three-choice confirmation over Réglages",
                          answer is None and asked(seen, "cfg"), answer or repr(seen))
    await context.close()


async def hold_each_way_asks(browser, journal):
    """Holds 3–6: every way of leaving Réglages asks; « Rester » and « Abandonner » do what they say."""
    context, page, errors = await open_at(browser, "cfg")
    await file_an_edit(page)
    ways = (
        ("the bar", ['[data-part="shell/tab-bar"] [data-page="lib"]']),
        ("the menu", ['[data-part="shell/header"] [data-drawer]', '#drawer [data-navgo="sys"]']),
        ("the account sheet's link", ['[data-account]', '#sheet [data-go="profile"]']),
    )
    for name, taps in ways:
        walked = [await tap(page, selector, PANEL_IN) for selector in taps]
        seen = await where(page)
        journal.check(f"R-C1-a 3: leaving Réglages by {name} asks, Réglages still drawn",
                      all(walked) and asked(seen, "cfg"), f"taps {walked} · {seen!r}")
        if seen["dialog"] is not None:
            await choose(page, stay_words("cfg"))
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(ACTED)
        stayed = await where(page)
        journal.check(f"R-C1-a 5: « {stay_words('cfg')} » after {name}: Réglages, the edit still waiting",
                      stayed["page"] == "cfg" and stayed["dialog"] is None and stayed["waiting"] == 1
                      and stayed["bar"] is not None, repr(stayed))

    await page.go_back()
    await page.wait_for_timeout(ACTED)
    back = await where(page)
    journal.check("R-C1-a 3: Retour from Réglages asks, Réglages still drawn at its address",
                  asked(back, "cfg") and back["path"] == PAGE_PATHS["cfg"], repr(back))
    if back["dialog"] is not None:
        await choose(page, stay_words("cfg"))
    stayed = await where(page)
    await page.go_back()
    await page.wait_for_timeout(ACTED)
    again = await where(page)
    journal.check("R-C1-a 5: Retour after « Rester » still works — it asks again",
                  stayed["page"] == "cfg" and stayed["dialog"] is None and asked(again, "cfg"),
                  f"{stayed!r} → {again!r}")
    if again["dialog"] is not None:
        await choose(page, SETTINGS_WORDS["leaveAbandon"])
    dropped = await where(page)
    journal.check("R-C1-a 6: « Abandonner les modifications » on Retour: the edits dropped, nothing written, "
                  "and the Retour lands on Acquisition",
                  dropped["page"] == "acq" and dropped["path"] == PAGE_PATHS["acq"] and dropped["waiting"] == 0
                  and dropped["written"] == 0 and dropped["dialog"] is None, repr(dropped))
    journal.check("R-C1-a: no JS error on Réglages' walk", not errors, str(errors))
    await context.close()

    # THE DRAWN RETOUR OF A RUBRIC stays on Réglages: it is no leave, and does not ask.
    context, page, errors = await open_at(browser, "cfg")
    await file_an_edit(page)
    await tap(page, '#view [data-topic="acquisition"]')
    drawn = await tap(page, '#view [data-part="screen/back"]')
    seen = await where(page)
    journal.check("R-C1-a 3: the drawn Retour of a rubric gives back the rubric list and does not ask",
                  drawn and seen["page"] == "cfg" and seen["dialog"] is None and seen["waiting"] == 1, repr(seen))
    await context.close()

    # « ABANDONNER » BY THE BAR lands where the tap led.
    context, page, errors = await open_at(browser, "cfg")
    await file_an_edit(page)
    await tap(page, '[data-part="shell/tab-bar"] [data-page="lib"]')
    await choose(page, SETTINGS_WORDS["leaveAbandon"])
    left = await where(page)
    journal.check("R-C1-a 6: « Abandonner les modifications » by the bar lands on Médiathèque, nothing written",
                  left["page"] == "lib" and left["waiting"] == 0 and left["written"] == 0
                  and left["bar"] is None and left["dialog"] is None, repr(left))
    await context.close()


async def hold_save(browser, journal):
    """Hold 7: « Enregistrer » writes, then leaves — Réglages by the menu, Trackers by the bar."""
    context, page, errors = await open_at(browser, "cfg")
    await file_an_edit(page)
    await tap(page, '[data-part="shell/header"] [data-drawer]', PANEL_IN)
    await tap(page, '#drawer [data-navgo="sys"]', PANEL_IN)
    await choose(page, SETTINGS_WORDS["leaveSave"])
    saved = await where(page)
    journal.check("R-C1-a 7: « Enregistrer » by the menu writes the file, then lands on Système",
                  saved["page"] == "sys" and saved["written"] == 1 and saved["waiting"] == 0
                  and saved["dialog"] is None, repr(saved))
    await page.go_back()
    await page.wait_for_timeout(ACTED)
    back = await where(page)
    journal.check("R-C1-a 7: and Retour from Système gives Réglages back, nothing left to ask",
                  back["page"] == "cfg" and back["dialog"] is None, repr(back))
    journal.check("R-C1-a: no JS error on the save by the menu", not errors, str(errors))
    await context.close()

    context, page, errors = await open_at(browser, "trackers")
    await tap(page, '[data-trackers-tab="trackers"]')
    await tap(page, f'#view [data-tracker-switch="{OFF_BY_OPERATOR}"]')
    await tap(page, '[data-part="shell/tab-bar"] [data-page="acq"]')
    seen = await where(page)
    journal.check("R-C1-a 4: leaving Trackers by the bar asks, its third choice « Rester sur Trackers »",
                  asked(seen, "trackers"), repr(seen))
    if seen["dialog"] is not None:
        await choose(page, SETTINGS_WORDS["leaveSave"])
    saved = await where(page)
    journal.check("R-C1-a 7: « Enregistrer » on Trackers writes the tracker's file, then lands on Acquisition",
                  saved["page"] == "acq" and saved["written"] == 1 and saved["waiting"] == 0, repr(saved))
    journal.check("R-C1-a: no JS error on Trackers' walk", not errors, str(errors))
    await context.close()


async def main():
    journal = Journal("R-C1-a — the frame's save bar, and the three-choice confirmation before leaving")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        await hold_the_bar(browser, journal)
        await hold_each_way_asks(browser, journal)
        await hold_save(browser, journal)
        await browser.close()
    journal.summary([])


if __name__ == "__main__":
    asyncio.run(main())
