"""R-L16bis-g, -h, -c, -i — each tracker has its switch, says why it failed, and the page is the design system's.

The operator, 2026-09-29 16:58: « un toggle d'activation par tracker […] Si un
tracker fonctionne plus le toggle passe en désactivé et affiche un message avec
l'erreur si j'essaye de le réactiver » — and the list grows (v3x.club,
draupnirr.xyz, digitalcore.club). His Q3: a tracker's row opens a bottom panel,
the switch stays on the row. His Q6: a tracker off by failure counts one in the
badge. His 16:48: the page brought back to the design system.

R-L16bis-g — the switch, one write two doors:
1. `tracker-active`: the row ends on a switch (`role="switch"`), on;
2. a finger on an off tracker's switch turns it on as a PENDING edit: the save bar
   rises, nothing is written yet;
3. Réglages' own row for the same setting draws that pending value — one table;
4. « Enregistrer » writes the setting's own key through `updateConfigurationFile`;
   the roster, read again, says the tracker on, and Réglages' setting says so too;
5. the other door: an edit filed from Réglages' panel moves the roster's switch in
   the next render.

R-L16bis-h — a failing tracker says why:
6. `tracker-off-by-failure` (lacale): its switch off, « Désactivé » in the danger
   tone, and why — « Injoignable depuis le … »; `tracker-off-by-operator`
   (draupnirr.xyz) says « Désactivé » in the neutral tone, and no failure;
7. a finger turns digitalcore.club back on and saves: the engine REFUSES (422),
   the switch stays off, the served tracker stays off, and the engine's words are
   drawn under the row — still there seconds later, never in a toast;
8. the Trackers badge counts one per tracker a failure switched off, none for one
   the operator switched off (the served components summed).

R-L16bis-c — the legend, on « Trackers »:
9. on `trackers-roster` and `trackers-legend`, every chip tone a row draws has
   its legend entry, above the roster, and no entry is idle.

R-L16bis-i — the design system is reused:
10. `features/trackers` declares no variant of its own (no `cva(`), so no title, no
    filter and no removal is redrawn there; the page's parts are the design
    system's: its tab strip the one `Tabs`, a torrent the card in its swipe row,
    the switch the one switch, the legend the one legend.

RE-AIMED OUT LOUD: `trackers_roster.py`'s « two entries » is six now; the refused
identifier of R-L16-d (`trackers_alert.py`) is read on `disabled.reason`, folded.

Red before the move: no row carries a switch, the roster holds two trackers, and
the feature draws with its own variants.
"""
import asyncio
import json
import pathlib
import re

from common import ACTED, SETTLED, Journal, chrome_launch_args, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1] / "design/src"
FEATURE = ROOT / "features/trackers"
WORDS = json.loads((ROOT / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["trackers"]
TRACKERS = {tracker["name"]: tracker for tracker in json.loads((ROOT / "mocks/seeds/trackers.json").read_text(encoding="utf-8"))}
OFF_BY_OPERATOR = "draupnirr.xyz"
OFF_BY_FAILURE = "lacale"
REFUSING = "digitalcore.club"
# How long a refusal must stay drawn to be more than a toast.
STAYS = 3000


def setting(tracker):
    """The identity of a tracker's activation setting."""
    return f"tracker:tracker.providers.{tracker}.enabled"


ROW = """(name) => {
  const row = document.querySelector(`#view [data-part="trackers/entry"][data-tracker="${name}"]`);
  if (!row) return null;
  const toggle = row.querySelector('[role="switch"]');
  const disabled = row.querySelector('[data-part="trackers/disabled"]');
  return {
    switch: toggle ? toggle.getAttribute('aria-checked') === 'true' : null,
    switchPart: toggle?.dataset.part ?? null,
    disabled: disabled ? {text: disabled.textContent.trim(), tone: disabled.dataset.tone} : null,
    failure: row.querySelector('[data-part="trackers/failure"]')?.textContent.trim() ?? null,
    refusal: row.querySelector('[data-part="trackers/refusal"]')?.textContent.trim() ?? null,
    served: row.dataset.enabled === 'true',
  };
}"""
SAVE_BAR = """() => document.querySelector('#savebar')?.textContent ?? null"""
WRITES = """() => (window.__mocks?.answered() || []).filter(call => call.operationId === 'updateConfigurationFile')
  .map(call => ({status: call.status, path: decodeURIComponent(call.path)}))"""
CATALOGUE = """(key) => (window.__queries?.getQueryData(['/api/config/schema']) || [])
  .flatMap(topic => topic.settings).find(one => one.key === key)?.raw"""
BADGE = """() => document.querySelector('[data-part="shell/tab-bar"] [data-page="trackers"] [data-part="shell/tab-badge"]')
  ?.textContent.trim() ?? ''"""
SERVED = """() => (window.__queries?.getQueryData(['/api/trackers']) || []).map(t => ({name: t.name, by: t.disabled?.by ?? null}))"""
TOASTS = """() => { window.__seen = []; const toast = document.getElementById('toast');
  if (toast) new MutationObserver(() => window.__seen.push(toast.textContent.trim()))
    .observe(toast, {childList: true, subtree: true, characterData: true}); }"""
LEGEND = """() => {
  const drawn = [...document.querySelectorAll('#view [data-part="trackers/entry"] [data-tone]')].map(node => node.dataset.tone);
  const legend = [...document.querySelectorAll('#view [data-part="legend"] [data-tone]')].map(node => node.dataset.tone);
  const box = document.querySelector('#view [data-part="legend"]')?.getBoundingClientRect();
  const roster = document.querySelector('#view [data-part="trackers/roster"]')?.getBoundingClientRect();
  return {drawn, legend, above: box && roster ? box.bottom <= roster.top : null};
}"""
PARTS = """() => ({
  tablist: [...document.querySelectorAll('#view [role="tablist"]')].map(list => list.className.split(' ')[0]),
  cards: [...document.querySelectorAll('#view [data-part="torrents/row"]')].map(row =>
    !!row.querySelector('[data-part="swipe"] > [data-part="card"]')),
})"""


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


async def main():
    journal = Journal("R-L16bis-g/h/c/i — each tracker has its switch, says why it failed, from the design system")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── g: the switch ────────────────────────────────────────────────────
        answer = await enter(page, "tracker-active")
        row = await page.evaluate(ROW, "c411")
        journal.check("tracker-active: the row ends on its switch, on",
                      answer is None and row is not None and row["switch"] is True and row["switchPart"] == "trackers/switch",
                      answer or repr(row))
        await enter(page, "trackers-roster")
        await tap(page, f'#view [data-tracker-switch="{OFF_BY_OPERATOR}"]')
        row = await page.evaluate(ROW, OFF_BY_OPERATOR)
        bar = await page.evaluate(SAVE_BAR)
        journal.check(f"a finger turns {OFF_BY_OPERATOR} on as a pending edit: the save bar rises, nothing is written",
                      row is not None and row["switch"] is True and not row["served"] and bar is not None
                      and "tracker.json5" in bar and not await page.evaluate(WRITES), f"{row!r} · bar {bar!r}")
        await page.evaluate(f"()=>window.__panel.produce('setting', {json.dumps(setting(OFF_BY_OPERATOR))})")
        await page.wait_for_timeout(ACTED)
        field = await page.evaluate("""()=>document.querySelector('#sheet[data-open] [role="switch"]')?.getAttribute('aria-checked')""")
        journal.check("Réglages' own row for the same setting draws that pending value — one table",
                      field == "true", repr(field))
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(ACTED)
        await tap(page, "[data-save]")
        await page.wait_for_timeout(SETTLED)
        writes = await page.evaluate(WRITES)
        row = await page.evaluate(ROW, OFF_BY_OPERATOR)
        raw = await page.evaluate(CATALOGUE, f"tracker.providers.{OFF_BY_OPERATOR}.enabled")
        journal.check("« Enregistrer » writes the tracker file, and the roster and Réglages both read it on",
                      any(write["path"].endswith("/tracker") and write["status"] == 200 for write in writes)
                      and row is not None and row["served"] and row["switch"] and row["disabled"] is None and raw is True,
                      f"writes {writes} · {row!r} · Réglages {raw!r}")
        await enter(page, "trackers-roster")
        await page.evaluate(f"()=>window.__panel.produce('setting', {json.dumps(setting('c411'))})")
        await page.wait_for_timeout(ACTED)
        await tap(page, '#sheet[data-open] [role="switch"]')
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(ACTED)
        row = await page.evaluate(ROW, "c411")
        journal.check("the other door: an edit filed from Réglages' panel moves the roster's switch",
                      row is not None and row["switch"] is False and row["served"], repr(row))

        # ── h: a failing tracker says why ────────────────────────────────────
        answer = await enter(page, "tracker-off-by-failure")
        row = await page.evaluate(ROW, OFF_BY_FAILURE)
        reason = WORDS.get("failureReasons", {}).get("unreachable", "<no copy>")
        journal.check(f"{OFF_BY_FAILURE}, off by failure: its switch off, « Désactivé » in danger, and why",
                      answer is None and row is not None and row["switch"] is False and row["disabled"] is not None
                      and row["disabled"]["tone"] == "danger" and (row["failure"] or "").startswith(reason),
                      answer or repr(row))
        answer = await enter(page, "tracker-off-by-operator")
        row = await page.evaluate(ROW, OFF_BY_OPERATOR)
        journal.check(f"{OFF_BY_OPERATOR}, off by the operator: « Désactivé » in the neutral tone, no failure said",
                      answer is None and row is not None and row["switch"] is False and row["disabled"] is not None
                      and row["disabled"]["tone"] == "neutral" and row["failure"] is None, answer or repr(row))

        await enter(page, "trackers-roster")
        await page.evaluate(TOASTS)
        await tap(page, f'#view [data-tracker-switch="{REFUSING}"]')
        await tap(page, "[data-save]")
        await page.wait_for_timeout(SETTLED)
        words = TRACKERS[REFUSING]["disabled"]["message"]
        row = await page.evaluate(ROW, REFUSING)
        writes = await page.evaluate(WRITES)
        journal.check(f"{REFUSING} turned back on and saved: the engine refuses, 422, the switch and the tracker stay off",
                      any(write["status"] == 422 for write in writes) and row is not None
                      and row["switch"] is False and not row["served"], f"writes {writes} · {row!r}")
        await page.wait_for_timeout(STAYS)
        row = await page.evaluate(ROW, REFUSING)
        seen = await page.evaluate("()=>(window.__seen || []).join(' | ')")
        journal.check("the engine's words are drawn under the row, still there seconds later, never in a toast",
                      row is not None and words in (row["refusal"] or "") and words not in seen,
                      f"{row and row['refusal']!r} · toasts {seen!r}")

        await enter(page, "trackers-roster")
        await page.wait_for_timeout(ACTED)
        served = await page.evaluate(SERVED)
        badge = await page.evaluate(BADGE)
        failed = [one["name"] for one in served if one["by"] == "failure"]
        journal.check(f"the badge counts one per tracker a failure switched off ({', '.join(failed)}), none for the operator's",
                      len(failed) == 2 and badge == str(len(failed)), f"badge {badge!r} · served {served}")

        # ── c: the legend on « Trackers » ────────────────────────────────────
        for state in ("trackers-roster", "trackers-legend"):
            answer = await enter(page, state)
            legend = await page.evaluate(LEGEND)
            journal.check(f"{state}: every chip tone a row draws has its entry, above the roster, none idle",
                          answer is None and bool(legend["drawn"]) and set(legend["drawn"]) == set(legend["legend"])
                          and legend["above"] is True, answer or repr(legend))

        # ── i: the design system is reused ───────────────────────────────────
        own = sorted(path.name for path in FEATURE.glob("*.ts*")
                     if re.search(r"\bcva\(", path.read_text(encoding="utf-8")))
        journal.check("features/trackers declares no variant of its own — nothing redrawn there",
                      not own and not (FEATURE / "variants.ts").exists(), str(own))
        await enter(page, "torrents-list")
        parts = await page.evaluate(PARTS)
        journal.check("the tab strip is the one Tabs, and every torrent is the card in its swipe row",
                      parts["tablist"] and all(bool(cards) for cards in parts["cards"]) and len(parts["cards"]) > 0,
                      repr(parts))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
