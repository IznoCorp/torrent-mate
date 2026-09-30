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
3. a finger on a row opens its panel, a layer above the roster;
4. from « Trackers », a finger edits the floor in the setting's panel, taps
   « Valider » and shuts the panel: the save bar APPEARS on « Trackers » — the
   page never left; its « Enregistrer » writes
   through `updateConfigurationFile`, and the entry, read again, shows the value
   the layer now answers;
5. « Voir les torrents » is an ARRIVAL from the tracker's panel: it lands on
   « Torrents » filtered to that tracker, stacking one entry over the panel's,
   and Retour reopens the tracker's panel on « Trackers » (D-L13-1, 09-13); it is
   a finger's target, at least 44 px high;
6. the alert threshold's panel, raised from the entry, is titled in the
   interface's words — never the key's raw English, « alert threshold »;
7. from « Trackers », a finger sets the alert threshold above the tracker's
   ratio and saves: the entry's alert chip AND the bar's badge move in the
   render that follows — the rule refreshes nothing, the save does;
8. while the settings catalogue is being read, the policy says so — never
   « Aucune politique réglée », which is an answer, not a wait;
9. when that read failed, the policy says it failed, naming what — never
   « Aucune politique réglée » either.

RE-AIMED OUT LOUD (L16-bis, the operator's Q3 — a tracker's row opens a bottom
panel, like a torrent's card): the policy rows, the guidance, « Voir les
torrents », the wait and the failure are read in the tracker's PANEL, never in a
fold; opening it is a layer above the roster (Back closes it), no longer an
adjustment of the page. RULINGS 2's door is unchanged: a policy row raises the
setting's own panel.

RE-AIMED OUT LOUD (L16-bis, the reader's N-bis, 2026-09-30): hold 5 read
« Voir les torrents » as an ADJUSTMENT — the selector's verb, replacing the
panel's entry — and Retour then left « Trackers » for the entry page. His
D-L13-1: a layer left for an arrival keeps its entry and Retour reopens it, as
the torrent panel's « Voir la fiche » does. Hold 5 now walks it with a finger
and reads the Retour; red on `515c277bd`.

Red before the move: no entry opens. Holds 6–9 came with correction round C16,
red while the save left `/api/trackers` stale, the policy read `?? []`, the
panel fell back to the key's own words and « Voir les torrents » stood at 39 px.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, chrome_launch_args, open_page
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
ALERT = f"tracker:tracker.providers.{WITH_POLICY}.economy.alert_threshold"
# A threshold far above any seeded ratio, so the tracker can only be under it.
THRESHOLD = "9"
LABELS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["settings"]["labels"]
ALERT_LABEL = LABELS.get("alert_threshold", "<no copy>")
SURFACE_ERROR = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["surfaces"]["error"]["lead"]
FINGER = 44
BADGE = """() => document.querySelector('[data-part="shell/tab-bar"] [data-page="trackers"] [data-part="shell/tab-badge"]')
  ?.textContent.trim() ?? null"""
# THE POLICY, AS THE TRACKER'S PANEL SAYS IT: its note — the guidance, « none
# set », the wait or the failure.
POLICY = """(name) => {
  const sheet = document.querySelector('#sheet[data-open]');
  if (!sheet || sheet.querySelector('[data-part="sheet/title"]')?.textContent.trim() !== name) return null;
  const notes = [...sheet.querySelectorAll('p')].map(note => note.textContent.trim());
  return {notes, unset: notes.includes(UNSET)};
}""".replace("UNSET", json.dumps(WORDS.get("policyUnset")))
# A floor no seed carries, so what is read back can only be what was typed.
TYPED = "1.7"

OPEN = """(name) => {
  const sheet = document.querySelector('#sheet[data-open]');
  const mine = sheet && sheet.querySelector('[data-part="sheet/title"]')?.textContent.trim() === name;
  const notes = mine ? [...sheet.querySelectorAll('p')].map(note => note.textContent.trim()) : [];
  return {
    open: !!mine,
    rows: mine ? [...sheet.querySelectorAll('[data-part="sheet/action"][data-setting]')]
      .map(row => ({setting: row.dataset.setting, text: row.textContent.replace(/\\s+/g, ' ').trim()})) : [],
    guidance: notes.includes(GUIDANCE) ? GUIDANCE : null,
    unset: notes.includes(UNSET) ? UNSET : null,
    see: mine && [...sheet.querySelectorAll('[data-part="sheet/action"]')].some(action => action.textContent.trim() === SEE),
    length: history.length,
  };
}""".replace("GUIDANCE", json.dumps(WORDS.get("floorGuidance"))).replace("UNSET", json.dumps(WORDS.get("policyUnset"))).replace(
    "SEE", json.dumps(WORDS.get("seeTorrents")))
# WHERE THE WALK STANDS: the tab, the filter, the panel up and its title, the depth.
WHERE = """() => ({tab: window.state?.trackersTab, filter: window.state?.trackersFilter,
  sheet: document.querySelector('#sheet[data-open] [data-part="sheet/title"]')?.textContent.trim() ?? null,
  length: history.length, address: location.pathname + location.search})"""
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


async def close_layers(page):
    """Backs out of every panel still open, as a finger's back gesture does."""
    for _ in range(3):
        if not await page.evaluate("()=>document.querySelector('#sheet')?.hasAttribute('data-open') ?? false"):
            return
        await page.go_back()
        await page.wait_for_timeout(ACTED)


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


async def main():
    journal = Journal("R262 — a tracker's policy is set where its ratio lives")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
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
        opened_by = await tapped(page, f'#view [data-tracker-open="{WITH_POLICY}"]')
        opened = await page.evaluate(OPEN, WITH_POLICY)
        journal.check("a finger on the row opens its panel, a layer above the roster",
                      opened["open"] and not before["open"] and opened["length"] == before["length"] + 1,
                      f"tapped {opened_by}: {before['open']}/{before['length']} -> {opened['open']}/{opened['length']}")

        calls = await page.evaluate("()=>window.__mocks.answered().length")
        row = f'#sheet[data-open] [data-part="sheet/action"][data-setting="{FLOOR}"]'
        walked = {"row": await tapped(page, row)}
        walked["field"] = await tapped(page, '#sheetin [data-part="field/input"]')
        if walked["field"]:
            await page.keyboard.press("ControlOrMeta+A")
            await page.keyboard.type(TYPED)
        walked["commit"] = await tapped(page, "#sheetin [data-commitsetting]")
        # « Valider » files the edit and keeps the panel up, showing it pending;
        # the operator then shuts the panel, by the back gesture, to reach the bar.
        await page.go_back()
        await page.wait_for_timeout(ACTED)
        # BACK REOPENS the tracker's panel the setting's panel was raised from;
        # one more back closes it onto the roster, where the save bar stands.
        await close_layers(page)
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
        await page.evaluate(f"()=>window.__panel.produce('tracker', {json.dumps(WITH_POLICY)})")
        await page.wait_for_timeout(ACTED)
        reread = await page.evaluate(OPEN, WITH_POLICY)
        floor = next((row["text"] for row in reread["rows"] if row["setting"] == FLOOR), "")
        journal.check("and the entry, read again, shows the value the layer now answers",
                      answered is not None and answered["shown"] in floor, f"{floor!r} · {answered}")

        # A FINGER'S WALK, never a driven panel: the panel's entry is what Retour reopens.
        # THE TAB TAPPED, so the address says « Trackers » as a walk would have left it.
        await enter(page, "trackers-roster")
        await tapped(page, '#view [data-trackers-tab="trackers"]')
        await tapped(page, f'#view [data-tracker-open="{WITH_POLICY}"]')
        opened = await page.evaluate(WHERE)
        see = page.locator('#sheet[data-open] [data-part="sheet/action"]', has_text=WORDS.get("seeTorrents"))
        height = round((await see.first.bounding_box() or {}).get("height", 0)) if await see.count() == 1 else 0
        if await see.count() == 1:
            await see.tap()
            await page.wait_for_timeout(ACTED)
        landed = await page.evaluate(WHERE)
        journal.check("« Voir les torrents » is an arrival: « Torrents » filtered to the tracker, one entry stacked",
                      landed["tab"] == "torrents" and landed["filter"] == WITH_POLICY and landed["sheet"] is None
                      and landed["length"] == opened["length"] + 1, f"{landed} from {opened}")
        await page.go_back()
        await page.wait_for_timeout(ACTED)
        back = await page.evaluate(WHERE)
        journal.check("Retour reopens the tracker's panel on « Trackers », unfiltered",
                      back["tab"] == "trackers" and back["filter"] == "" and back["sheet"] == WITH_POLICY,
                      f"{back} from {landed}")

        journal.check(f"« Voir les torrents » is a finger's target, at least {FINGER} px high", height >= FINGER,
                      f"{height} px")

        # ── the alert threshold, set from « Trackers », moves the alert ──────
        await enter(page, "trackers-entry-open")
        walked = {"row": await tapped(page, f'#sheet[data-open] [data-part="sheet/action"][data-setting="{ALERT}"]')}
        title = await page.evaluate("()=>document.querySelector('#sheetin')?.textContent.slice(0, 160) ?? ''")
        journal.check(f"the alert threshold's panel is titled « {ALERT_LABEL} », never « alert threshold »",
                      ALERT_LABEL in title and "alert threshold" not in title.lower(), repr(title))
        walked["field"] = await tapped(page, '#sheetin [data-part="field/input"]')
        if walked["field"]:
            await page.keyboard.press("ControlOrMeta+A")
            await page.keyboard.type(THRESHOLD)
        walked["commit"] = await tapped(page, "#sheetin [data-commitsetting]")
        await page.go_back()
        await page.wait_for_timeout(ACTED)
        await close_layers(page)
        walked["save"] = await tapped(page, "#savebar [data-save]")
        await page.wait_for_timeout(SETTLED)
        chip = await page.evaluate(
            f"""()=>document.querySelector('#view [data-part="trackers/entry"][data-tracker="{WITH_POLICY}"] [data-part="trackers/alert"]')
                ?.textContent.trim() ?? null""")
        badge = await page.evaluate(BADGE)
        journal.check(f"the threshold saved at {THRESHOLD} from « Trackers » moves {WITH_POLICY}'s alert chip "
                      "and the bar's badge — the rule refreshing nothing",
                      chip is not None and badge is not None and int(badge) >= 1, f"walked {walked}: chip {chip!r} · badge {badge!r}")

        # ── the policy's own wait and failure ────────────────────────────
        for outcome, label in (("{latencyMilliseconds: 60000}", "in flight"), ("{status: 500}", "failed")):
            await enter(page, "trackers-entry-open")
            # NOT AWAITED: the held-back read answers in a minute, and the wait is what is read.
            await page.evaluate(f"""()=>{{window.__mocks.setOperationOutcome('readSettings', {outcome});
                void window.__queries?.resetQueries({{queryKey: ['/api/config/schema']}}).catch(() => null);}}""")
            await page.wait_for_timeout(SETTLED)
            # THE PANEL ASKED FOR AGAIN, as a finger on the row asks it.
            await page.evaluate(f"()=>window.__panel.produce('tracker', {json.dumps(WITH_POLICY)})")
            await page.wait_for_timeout(SETTLED)
            policy = await page.evaluate(POLICY, WITH_POLICY)
            notes = " ".join((policy or {}).get("notes", []))
            said = WORDS.get("policyLoading", "<no copy>") in notes if label == "in flight" else (
                SURFACE_ERROR.split("{{")[0].strip() in notes)
            journal.check(f"the catalogue's read {label}: the policy says so, never « {WORDS.get('policyUnset')} »",
                          policy is not None and said and not policy["unset"], str(policy))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
