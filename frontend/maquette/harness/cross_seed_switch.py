"""R-L17-e — a tracker's cross-seed switch, in two halves, where the tracker is.

§ 19: « un interrupteur par tracker »; OPEN 2 = A: on the Trackers page AND in
Réglages, one write, two doors; round 9 Q5: the switch cuts NEW cross-seeds only,
its confirmation offering — UNCHECKED — to cut the running ones too; M4: the
confirmation names each running obligation that would end; M6: the engine's own
switch cuts nothing running and hides nothing. L17 DESIGN § 3.2 (S2), re-homed
into the tracker's panel (L16-bis § 1.7).

1. a finger opens tr4ker's panel: its cross-seed switch reads on;
2. a finger on it opens a confirmation naming the tracker and President Curtis's
   running obligation there, its « running ones too » box UNCHECKED;
3. confirmed as is: ONE `updateConfigurationFile` answered, without the option;
   in the render that follows, the panel's switch, the roster's line, the
   summary's `enabled` and Réglages' setting all read off — and the pair running
   on tr4ker still runs, its obligation still open;
4. again with the box checked: ONE write carrying the option and no other call;
   the pair reads « stoppé » by the switch, its entry is gone, its obligation
   closed « libérée »;
5. a finger turns it back on: no confirmation, one write, on;
6. `tracker-cross-seed-switch-off`: the panel says « coupé », the running pair runs;
7. the engine off: the panel says so ABOVE the tracker's own switch, which stays,
   and the tracker's line says the tracker on and the engine off — never that the
   engine searches there;
8. each write is confirmed by a status message, as the cut, the search and the
   exclusion are; after a cut that took the running ones, the panel says they
   were cut, never that they continue;
9. Réglages names every row keyed by a tracker by that tracker, its domain ONE
   subject (`v3x.club`, never « v3x · club »).

Red before the move: no tracker panel carries a cross-seed switch.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1] / "design/src"
SWITCH = json.loads((ROOT / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["crossSeed"]["switch"]
ORIGIN = "66e23ab395c438b7db4f7c855bd451d8bb1f0046"
COPY = "7c1e0b2f95c438b7db4f7c855bd451d8bb1f0046"
KEY = "tracker.providers.tr4ker.cross_seed"
DONE = json.loads((ROOT / "i18n/fr.json").read_text(encoding="utf-8"))["verbs"]["crossSeed"]

READ = """([origin, copy, key]) => {
  const downloads = window.__queries?.getQueryData(['/api/acquisition/downloads'])?.downloads || [];
  const obligation = (window.__queries?.getQueryData(['/api/acquisition/obligations'])?.items || [])
    .find(one => one.infoHash === copy);
  const toggle = document.querySelector('#sheet[data-open] [data-part="tracker/cross-seed-switch"]');
  return {
    panel: toggle ? toggle.getAttribute('aria-checked') === 'true' : null,
    nextPass: !!document.querySelector('#sheet[data-open] [data-part="tracker/cross-seed-next-pass"]'),
    line: document.querySelector('#view [data-tracker="tr4ker"] [data-part="trackers/cross-seed"]')?.textContent.trim() ?? null,
    summary: (window.__queries?.getQueryData(['/api/trackers']) || []).find(t => t.name === 'tr4ker')?.crossSeed?.enabled,
    setting: (window.__queries?.getQueryData(['/api/config/schema']) || []).flatMap(t => t.settings).find(s => s.key === key)?.raw,
    pair: downloads.find(entry => entry.infoHash === origin)?.crossSeed?.pairs.find(p => p.tracker === 'tr4ker') ?? null,
    copy: downloads.some(entry => entry.infoHash === copy),
    released: obligation ? obligation.releasedAt : 'absent',
    engineNote: !!document.querySelector('#sheet[data-open] [data-part="tracker/cross-seed-engine-off"]'),
    state: document.querySelector('#sheet[data-open] [data-part="tracker/cross-seed-state"]')?.textContent.trim() ?? null,
    detail: document.querySelector('#sheet[data-open] [data-part="tracker/cross-seed-state"]')
      ?.nextElementSibling?.textContent.trim() ?? null,
    toast: document.getElementById('toast')?.textContent.trim() ?? '',
  };
}"""
DIALOG = """() => {
  const box = document.querySelector('[data-part="dialog"][data-open]');
  return box ? {text: box.textContent, checked: box.querySelector('[data-part="dialog/check"]')?.getAttribute('aria-checked')} : null;
}"""
SUBJECTS = """() => {
  const names = (window.__queries?.getQueryData(['/api/trackers']) || []).map(one => one.name);
  return (window.__queries?.getQueryData(['/api/config/schema']) || []).flatMap(topic => topic.settings)
    .filter(one => one.key.startsWith('tracker.providers.'))
    .map(one => ({key: one.key, label: window.__settingLabels.label(one),
                  tracker: names.find(name => one.key.startsWith(`tracker.providers.${name}.`)) ?? null}));
}"""
WRITES = """() => (window.__mocks?.answered() || []).map(call => ({op: call.operationId, path: decodeURIComponent(call.path)}))"""
CONFIRM = '[data-part="dialog"][data-open] [data-part="dialog/button"][data-tone="danger"]'


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


async def tap(page, selector):
    """A finger on the first element a selector names; True when there was one."""
    target = page.locator(selector)
    if not await target.count():
        return False
    await target.first.tap()
    await page.wait_for_timeout(ACTED)
    return True


async def open_tr4ker(page):
    """The roster, then a finger on tr4ker's row: its panel."""
    await enter(page, "trackers-cross-seed")
    await tap(page, '#view [data-tracker-open="tr4ker"]')


async def main():
    journal = Journal("R-L17-e — a tracker's cross-seed switch, in two halves, where the tracker is")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        argument = [ORIGIN, COPY, KEY]

        await open_tr4ker(page)
        before = await page.evaluate(READ, argument)
        journal.check("a finger opens tr4ker's panel: its cross-seed switch reads on",
                      before["panel"] is True and before["pair"] and before["pair"]["state"] == "active", repr(before))
        await tap(page, '#sheet[data-open] [data-cross-seed-switch="tr4ker"]')
        dialog = await page.evaluate(DIALOG)
        journal.check("a finger on it asks first: the tracker and its running obligation named, the box unchecked",
                      dialog is not None and "tr4ker" in dialog["text"] and "President Curtis S01E10" in dialog["text"]
                      and dialog["checked"] == "false", repr(dialog))
        calls = len(await page.evaluate(WRITES))
        await tap(page, CONFIRM)
        writes = (await page.evaluate(WRITES))[calls:]
        after = await page.evaluate(READ, argument)
        # THE LAYER'S RECORD CARRIES NO QUERY: whether the option travelled is read by what moved, below.
        journal.check("confirmed as is: one config write, and nothing else",
                      [w["op"] for w in writes if not w["op"].startswith("read")] == ["updateConfigurationFile"], repr(writes))
        journal.check("the panel's switch, the roster's line, the summary and Réglages' setting all read off, at once",
                      after["panel"] is False and after["summary"] is False and after["setting"] is False
                      and after["line"] is not None and "coupé sur ce tracker" in after["line"] and after["nextPass"],
                      repr({k: after[k] for k in ("panel", "summary", "setting", "line", "nextPass")}))
        journal.check("the pair running on tr4ker still runs, its obligation still open (M6: new ones only)",
                      after["pair"]["state"] == "active" and after["copy"] and after["released"] is None, repr(after["pair"]))
        journal.check("the write confirms: « coupé », the running ones continuing",
                      bool(DONE.get("switchOffDone")) and after["toast"].startswith(
                          DONE.get("switchOffDone", "∅").replace("{{tracker}}", "tr4ker")), repr(after["toast"]))

        await open_tr4ker(page)
        await tap(page, '#sheet[data-open] [data-cross-seed-switch="tr4ker"]')
        await tap(page, '[data-part="dialog"][data-open] [data-part="dialog/check"]')
        calls = len(await page.evaluate(WRITES))
        await tap(page, CONFIRM)
        writes = [w for w in (await page.evaluate(WRITES))[calls:] if not w["op"].startswith("read")]
        after = await page.evaluate(READ, argument)
        journal.check("with the box checked: still one write, no second call (the option rides it)",
                      [w["op"] for w in writes] == ["updateConfigurationFile"], repr(writes))
        journal.check("the running pair reads « stoppé » by the switch, its entry gone, its obligation closed « libérée »",
                      after["pair"]["state"] == "stopped" and after["pair"]["stopCause"] == "switch"
                      and after["pair"]["stoppedAt"] and not after["copy"] and isinstance(after["released"], (int, float)),
                      repr((after["pair"], after["copy"], after["released"])))
        journal.check("the write confirms the running ones cut, and the panel says so — never « ceux en cours continuent »",
                      bool(DONE.get("switchOffStoppedDone")) and after["toast"].startswith(
                          DONE.get("switchOffStoppedDone", "∅").replace("{{tracker}}", "tr4ker"))
                      and SWITCH.get("offStoppedDetail") is not None and after["detail"] == SWITCH["offStoppedDetail"],
                      repr((after["toast"], after["detail"])))

        calls = len(await page.evaluate(WRITES))
        await tap(page, '#sheet[data-open] [data-cross-seed-switch="tr4ker"]')
        writes = [w for w in (await page.evaluate(WRITES))[calls:] if not w["op"].startswith("read")]
        after = await page.evaluate(READ, argument)
        journal.check("a finger turns it back on: no confirmation, one write, on",
                      await page.evaluate(DIALOG) is None and [w["op"] for w in writes] == ["updateConfigurationFile"]
                      and after["panel"] is True and after["summary"] is True, repr((writes, after["panel"])))
        journal.check("turned back on, the write confirms it",
                      bool(DONE.get("switchOnDone")) and after["toast"].startswith(
                          DONE.get("switchOnDone", "∅").replace("{{tracker}}", "tr4ker")), repr(after["toast"]))

        await enter(page, "tracker-cross-seed-switch-off")
        await page.wait_for_timeout(ACTED)
        off = await page.evaluate(READ, argument)
        journal.check("tracker-cross-seed-switch-off: the panel says « coupé », the running pair runs",
                      off["panel"] is False and off["state"] == SWITCH["off"] and off["pair"]["state"] == "active", repr(off))

        await enter(page, "trackers-cross-seed-engine-off")
        await tap(page, '#view [data-tracker-open="tr4ker"]')
        engine = await page.evaluate(READ, argument)
        journal.check("the engine off: said above the tracker's own switch, which stays drawn and on",
                      engine["engineNote"] and engine["panel"] is True and engine["pair"]["state"] == "active", repr(engine))
        journal.check("the engine off: the tracker's line says the tracker on and the engine off, never that it searches",
                      SWITCH.get("onEngineOffDetail") is not None and engine["detail"] == SWITCH["onEngineOffDetail"],
                      repr((engine["state"], engine["detail"])))

        subjects = await page.evaluate(SUBJECTS)
        wrong = [row for row in subjects
                 if row["tracker"] is None or row["label"].split(" — ")[0].split(" · ")[0].lower() != row["tracker"].lower()]
        journal.check("Réglages names every tracker-keyed row by its tracker, a domain ONE subject",
                      any("." in (row["tracker"] or "") for row in subjects) and not wrong,
                      repr(wrong[:4] or [row["label"] for row in subjects][:4]))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
