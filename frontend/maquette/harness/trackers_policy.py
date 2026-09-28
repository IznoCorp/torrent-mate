"""R262 — a tracker's policy is set where its ratio lives, through the settings' own write.

DOIT-3 — act where one observes. A tracker's entry opens onto its floor
(`min_ratio`), its seed time (`min_seed_time`) and its alert threshold, each the
SAME setting the settings page draws (§ 13, one write, two doors): a tap raises
that setting's own panel, « Valider » files the edit, and the save bar the
settings page draws is drawn on the « Trackers » page too, so the edit is never
left waiting where the operator cannot see it (NE-DOIT-PAS-2).

1. `trackers-entry-open` opens the first tracker's entry: its three rows name
   their settings, `<file>:<key>`, and show the values the catalogue answers; a
   guidance line says what the floor is; « Voir les torrents » is offered;
2. `trackers-policy-unset` opens a tracker with no policy, which says so;
3. a finger opening an entry ADJUSTS: `history.length` unchanged;
4. from « Trackers », a finger edits the floor in the setting's panel, taps
   « Valider » and shuts the panel: the save bar APPEARS on « Trackers » — the
   page never left; its « Enregistrer » writes
   through `updateConfigurationFile`, and the entry, read again, shows the value
   the layer now answers;
5. « Voir les torrents » lands on « Torrents » filtered to that tracker, as an
   adjustment.

Red before the move: no entry opens.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
TRACKERS = json.loads((SOURCE / "mocks/seeds/trackers.json").read_text(encoding="utf-8"))
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["trackers"]
# The tracker whose policy is set, and the one that has none, read off the seeds.
WITH_POLICY = TRACKERS[0]["name"]
WITHOUT_POLICY = TRACKERS[1]["name"]
FIELDS = ("min_ratio", "min_seed_time", "alert_threshold")
FLOOR = f"tracker:tracker.providers.{WITH_POLICY}.economy.min_ratio"
# A floor no seed carries, so what is read back can only be what was typed.
TYPED = "1.7"

OPEN = """(name) => {
  const entry = document.querySelector(`#view [data-part="trackers/entry"][data-tracker="${name}"]`);
  const fold = entry?.querySelector('details');
  return {
    open: !!fold?.open,
    rows: [...(entry?.querySelectorAll('[data-part="trackers/policy"] [data-setting]') ?? [])]
      .map(row => ({setting: row.dataset.setting, text: row.textContent.replace(/\\s+/g, ' ').trim()})),
    guidance: entry?.querySelector('[data-part="trackers/policy-guidance"]')?.textContent.trim() ?? null,
    unset: entry?.querySelector('[data-part="trackers/policy-unset"]')?.textContent.trim() ?? null,
    see: !!entry?.querySelector('[data-part="trackers/see-torrents"]'),
    length: history.length,
  };
}"""
CATALOGUE = """(id) => {
  const topics = window.__queries?.getQueryData(['/api/config/schema']) || [];
  const one = topics.flatMap((topic) => topic.settings).find((s) => (s.file + ':' + s.key) === id);
  return one ? {raw: one.raw, shown: String(one.displayedValue)} : null;
}"""


async def tapped(page, selector):
    """A finger's tap on the one element the selector names; False when it cannot land."""
    target = page.locator(selector)
    if await target.count() != 1:
        return False
    try:
        await target.tap(timeout=5000)
    except PlaywrightTimeoutError:
        return False
    await page.wait_for_timeout(ACTED)
    return True


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


async def main():
    journal = Journal("R262 — a tracker's policy is set where its ratio lives")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await enter(page, "trackers-entry-open")
        journal.check("the named state trackers-entry-open exists", answer is None, answer or "")
        seen = await page.evaluate(OPEN, WITH_POLICY)
        wanted = [f"tracker:tracker.providers.{WITH_POLICY}.economy.{field}" for field in FIELDS]
        journal.check(f"{WITH_POLICY}'s entry is open, its three rows naming their settings",
                      seen["open"] and [row["setting"] for row in seen["rows"]] == wanted, str(seen))
        for row in seen["rows"]:
            answered = await page.evaluate(CATALOGUE, row["setting"])
            journal.check(f"{row['setting']} shows the value the catalogue answers",
                          answered is not None and answered["shown"] in row["text"], f"{row} · {answered}")
        journal.check("a guidance line says what the floor is, and « Voir les torrents » is offered",
                      seen["guidance"] == WORDS.get("floorGuidance") and seen["see"], str(seen))

        answer = await enter(page, "trackers-policy-unset")
        journal.check("the named state trackers-policy-unset exists", answer is None, answer or "")
        unset = await page.evaluate(OPEN, WITHOUT_POLICY)
        journal.check(f"{WITHOUT_POLICY}, with no policy, says so and draws no row",
                      unset["open"] and unset["rows"] == [] and unset["unset"] == WORDS.get("policyUnset"),
                      str(unset))

        await enter(page, "trackers-roster")
        before = await page.evaluate(OPEN, WITH_POLICY)
        summary = f'#view [data-part="trackers/entry"][data-tracker="{WITH_POLICY}"] summary'
        folded = await tapped(page, summary)
        opened = await page.evaluate(OPEN, WITH_POLICY)
        journal.check("a finger opening the entry ADJUSTS: history.length unchanged",
                      opened["open"] and not before["open"] and opened["length"] == before["length"],
                      f"tapped {folded}: {before['open']}/{before['length']} -> {opened['open']}/{opened['length']}")

        calls = await page.evaluate("()=>window.__mocks.answered().length")
        row = f'#view [data-part="trackers/policy"] [data-setting="{FLOOR}"]'
        walked = {"row": await tapped(page, row)}
        walked["field"] = await tapped(page, '#sheetin [data-part="field/input"]')
        if walked["field"]:
            await page.keyboard.press("Meta+A")
            await page.keyboard.type(TYPED)
        walked["commit"] = await tapped(page, "#sheetin [data-commitsetting]")
        # « Valider » files the edit and keeps the panel up, showing it pending;
        # the operator then shuts the panel, by the back gesture, to reach the bar.
        await page.go_back()
        await page.wait_for_timeout(ACTED)
        bar = await page.evaluate(
            "()=>({page: window.state?.page, bar: !!document.querySelector('#savebar [data-save]'),"
            " sheet: document.querySelector('#sheetin')?.textContent.slice(0, 120) ?? null})")
        journal.check("« Valider » makes the save bar appear on « Trackers » itself",
                      bar["page"] == "trackers" and bar["bar"], f"{bar} · walked {walked}")
        saved = await tapped(page, "#savebar [data-save]")
        if saved:
            await page.wait_for_timeout(ACTED)
        written = await page.evaluate(
            """(n)=>window.__mocks.answered().slice(n)
                 .filter((one) => one.operationId === 'updateConfigurationFile').length""", calls)
        answered = await page.evaluate(CATALOGUE, FLOOR)
        journal.check("« Enregistrer » writes through updateConfigurationFile, and the layer answers the value",
                      written > 0 and answered is not None and str(answered["raw"]) == TYPED,
                      f"save tapped {saved}: {written} write(s) · {answered}")
        reread = await page.evaluate(OPEN, WITH_POLICY)
        floor = next((row["text"] for row in reread["rows"] if row["setting"] == FLOOR), "")
        journal.check("and the entry, read again, shows the value the layer now answers",
                      answered is not None and answered["shown"] in floor, f"{floor!r} · {answered}")

        await enter(page, "trackers-entry-open")
        start = await page.evaluate("()=>history.length")
        see = f'#view [data-part="trackers/entry"][data-tracker="{WITH_POLICY}"] [data-part="trackers/see-torrents"]'
        await tapped(page, see)
        landed = await page.evaluate(
            "()=>({tab: window.state?.trackersTab, filter: window.state?.trackersFilter, length: history.length})")
        journal.check("« Voir les torrents » lands on « Torrents » filtered to the tracker, as an adjustment",
                      landed["tab"] == "torrents" and landed["filter"] == WITH_POLICY and landed["length"] == start,
                      f"{landed} from {start}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
