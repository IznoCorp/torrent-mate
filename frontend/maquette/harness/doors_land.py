"""R502 — each door of a block lands where its cause is settled, and says it (Q7).

Q7 of 2026-10-01: « chaque carte dit sa cause, ce qui la lève et où elle se
règle (Système › Disques, « Voir le tracker », ses réglages) ». The door is the
card's foot ALONE (DECIDED 6); it is a link inside a page, so it STACKS and
Retour gives « À traiter » back (§ 16). A door that lands on a page saying
nothing of the cause is a broken promise (maquette-blocked § 1.3).

What this holds:

1. every external cause's card offers ONE foot, its door — « Voir les disques »
   for a disk, « Voir les dépendances » for a service, « Voir le tracker » for a
   tracker — and no « Abandonner »;
2. a finger on each door lands on its page — Système for a disk or a service,
   Trackers with the tracker's panel up for a tracker — the section landed on
   in the viewport and focused;
3. the landed surface says the same cause: a disk « presque plein » under
   « Disques »; the Plex row « hors ligne », « ne répond pas depuis … »; the
   tracker's panel « Ne répond pas depuis … »;
4. the landing is an arrival: Retour (twice under the tracker's panel) gives
   « À traiter » back, the card still there;
5. an account that may not open Système (`system.view`) sees the cause and the
   lift and no door (`acq-block-door-reserved`, § 17);
6. `system-dependency-plex-down`: Système's dependencies hold a Plex row, down.

Red before the lot's phase 3: the disk and service causes draw no door;
Système has no landing door, no Plex row, and no tracker says it is unreachable
(maquette-blocked DESIGN § 0.1 item 4, item 5).
"""
import asyncio
import json
import pathlib

from common import PANEL_IN, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
ACQUISITION = WORDS["screens"]["acquisition"]
SYSTEM = WORDS["screens"]["system"]
TRACKERS = WORDS["screens"]["trackers"]
STATES = WORDS["states"]
LADDER = WORDS["surfaces"]["ladder"]
ABANDON = ACQUISITION["abandonFoot"]

DISKS = ACQUISITION.get("blockDisks", "<no copy>")
DEPENDENCIES = ACQUISITION.get("blockDependencies", "<no copy>")
TRACKER = ACQUISITION["ratioReasonTracker"]
# Each external cause's state, the card it poses on, and the door it offers.
DOORS = [
    ("acq-card-deferred-space", "This City Is Ours", DISKS),
    ("acq-card-deferred-missing", "This City Is Ours", DISKS),
    ("acq-block-library-full", "President Curtis", DISKS),
    ("acq-card-deferred-ratio", "This City Is Ours", TRACKER),
    ("acq-block-tracker-unreachable", "Silo|S03", TRACKER),
    ("acq-block-provider-unreachable", "Conclave", DEPENDENCIES),
    ("acq-block-plex-unreachable", "The Alabama Solution", DEPENDENCIES),
    ("acq-block-client-unreachable", "This City Is Ours", DEPENDENCIES),
]


def opening(sentence):
    """The words a sentence opens with, before any value it names."""
    return sentence.split("{{")[0].strip()


DOWN_SINCE = opening(SYSTEM.get("downSince", "<no copy>"))
UNREACHABLE = opening(TRACKERS.get("panel", {}).get("unreachableSince", "<no copy>"))

FEET = """(key) => [...document.querySelectorAll('#view [data-part="card"]')]
  .filter(card => card.dataset.acquisition === key)
  .flatMap(card => [...card.querySelectorAll('[data-part="card/foot"]')])
  .map(foot => foot.textContent.trim())"""
CARD = """(key) => {
  const card = [...document.querySelectorAll('#view [data-part="card"]')].find(one => one.dataset.acquisition === key);
  return card ? {reason: card.querySelector('[data-part="card/reason"]')?.textContent.trim() ?? '',
    doors: card.querySelectorAll('[data-go]').length} : null}"""
# Where a landing on Système stands: the address, the section's heading in the
# viewport and focused, and the facts that follow it, up to the next heading.
SECTION = """(section) => {
  const heading = document.querySelector(`#view [data-section="${section}"]`);
  const facts = [];
  for (let node = heading?.nextElementSibling; node && !node.matches('h2'); node = node.nextElementSibling)
    facts.push(...[...node.querySelectorAll('li')].map(row => row.textContent.replace(/\\s+/g, ' ').trim()));
  const box = heading?.getBoundingClientRect();
  return {path: location.pathname, found: Boolean(heading),
    inView: Boolean(box && box.top >= 0 && box.bottom <= innerHeight),
    focused: heading !== null && document.activeElement === heading, facts};
}"""
TODO_BACK = """(key) => ({path: location.pathname,
  todo: document.querySelector('[data-acqtab="todo"]')?.getAttribute('aria-selected') === 'true',
  card: [...document.querySelectorAll('#view [data-part="card"]')].some(card => card.dataset.acquisition === key)})"""
PANEL = """() => ({path: location.pathname,
  title: document.querySelector('#sheet[data-open] [data-part="sheet/title"]')?.textContent.trim() ?? '',
  text: document.querySelector('#sheet[data-open]')?.textContent.replace(/\\s+/g, ' ') ?? ''})"""


async def go(page, journal, state):
    """Asks for a named state and holds that it exists."""
    answer = await page.evaluate(
        "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
    await page.wait_for_timeout(SETTLED)
    journal.check(f"the named state {state} exists", answer is None, answer or "")


async def tap_door(page, key, label):
    """A finger on « À traiter »'s tab, then on a card's door."""
    await page.locator("[data-acqtab=todo]").first.tap()
    await page.wait_for_timeout(SETTLED)
    door = page.locator(f'#view [data-part="card"][data-acquisition="{key}"] [data-part="card/foot"]', has_text=label)
    if await door.count():
        await door.first.tap()
    await page.wait_for_timeout(PANEL_IN + SETTLED)


async def back_to_todo(page, journal, key, steps, what):
    """Retour, as many times as the landing stacked; « À traiter » is back with its card."""
    for _ in range(steps):
        await page.go_back()
        await page.wait_for_timeout(PANEL_IN + SETTLED)
    where = await page.evaluate(TODO_BACK, key)
    journal.check(f"{what}: Retour gives « À traiter » back, « {key} » still there",
                  where["todo"] and where["card"], str(where))


async def system_door(page, journal, state, key, section, says, what):
    """A finger on a door to Système: lands on the section, which says the cause."""
    await go(page, journal, state)
    await tap_door(page, key, DISKS if section == "disks" else DEPENDENCIES)
    # The landing keeps its section centred while the page's reads answer.
    await page.wait_for_timeout(SETTLED)
    landed = await page.evaluate(SECTION, section)
    journal.check(f"{what}: lands on Système, « {section} » in view and focused",
                  landed["path"].endswith("/system") and landed["found"] and landed["inView"] and landed["focused"],
                  str({k: v for k, v in landed.items() if k != "facts"}))
    journal.check(f"{what}: the section says the cause — {says}",
                  any(all(part in fact for part in says) for fact in landed["facts"]), str(landed["facts"]))
    await back_to_todo(page, journal, key, 1, what)


async def main():
    journal = Journal("R502 — each door of a block lands where its cause is settled, and says it")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── 1. every external cause offers its door, alone ─────────────────
        for state, key, label in DOORS:
            await go(page, journal, state)
            feet = await page.evaluate(FEET, key)
            journal.check(f"{state}: « {key} » offers its door « {label} » alone, no « {ABANDON} »",
                          feet == [label], str(feet))

        # ── 2–4. a finger on each door kind, the landing, and Retour ───────
        await system_door(page, journal, "acq-card-deferred-space", "This City Is Ours", "disks",
                          [STATES["nearly_full"]], f"« {DISKS} »")
        await system_door(page, journal, "acq-block-plex-unreachable", "The Alabama Solution", "dependencies",
                          ["Plex", STATES["offline"], DOWN_SINCE], f"« {DEPENDENCIES} »")

        await go(page, journal, "acq-block-tracker-unreachable")
        await tap_door(page, "Silo|S03", TRACKER)
        landed = await page.evaluate(PANEL)
        journal.check(f"« {TRACKER} » on an unreachable tracker lands on Trackers, c411's panel up",
                      landed["path"].endswith("/trackers") and landed["title"] == "c411",
                      f"{landed['path']} · {landed['title']!r}")
        journal.check(f"the tracker's panel says it does not answer — « {UNREACHABLE} … »",
                      UNREACHABLE in landed["text"], landed["text"][:300])
        await back_to_todo(page, journal, "Silo|S03", 2, f"« {TRACKER} »")

        # ── 5. no door where the page is not his ───────────────────────────
        await go(page, journal, "acq-block-door-reserved")
        card = await page.evaluate(CARD, "This City Is Ours")
        cause = opening(LADDER["reasons"]["insufficient_space"])
        lift = opening(LADDER.get("lifts", {}).get("insufficient_space", "<no copy>"))
        journal.check("acq-block-door-reserved: without system.view the cause and the lift are drawn, no door",
                      card is not None and cause in card["reason"] and lift in card["reason"] and card["doors"] == 0,
                      str(card))

        # ── 6. Plex among the dependencies, down ───────────────────────────
        await go(page, journal, "system-dependency-plex-down")
        landed = await page.evaluate(SECTION, "dependencies")
        journal.check("system-dependency-plex-down: the dependencies hold Plex, down, « ne répond pas depuis … »",
                      any("Plex" in fact and STATES["offline"] in fact and DOWN_SINCE in fact
                          for fact in landed["facts"]), str(landed["facts"]))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
