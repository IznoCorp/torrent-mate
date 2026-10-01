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
2. a finger on each door kind — the disks for a staging disk without room, an
   unreadable download volume and a full library; the dependencies for TMDB /
   TVDB, Plex and qBittorrent; the tracker — lands on its page: Système, the
   section landed on in the viewport and focused, or Trackers with the
   tracker's panel up;
3. the landed surface says the SAME cause, by a fact ABSENT AT REST (r1 of the
   lot's reading: Disk2 « bientôt plein » at rest let the disks door pass with
   no block posed): the « Staging » disk « bientôt plein »; the volume
   qBittorrent downloaded to « hors ligne »; every library disk « bientôt
   plein » and none with room — Disk1's « 1,8 To libres » would contradict
   « aucun disque n'a la place »; the service's row « hors ligne », « ne
   répond pas depuis … »; the tracker's panel « Ne répond pas depuis … »;
4. the landing is an arrival: `history.length` grows by one per entry it
   stacks (the page, then the tracker's panel), and Retour, as many times,
   gives « À traiter » back, the card still there, its scroll kept (§ 1.3);
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

# The rows the disks door lands on, by the cause posed — absent from the machine at rest.
DISKS_BLOCKED = json.loads((SOURCE / "mocks/seeds/disks-blocked.json").read_text(encoding="utf-8"))
# Each walk to Système: the state, the card, the section, the fact the landing must hold.
SYSTEM_WALKS = [
    ("acq-card-deferred-space", "This City Is Ours", "disks",
     [DISKS_BLOCKED["insufficient_space"]["label"], STATES["nearly_full"]]),
    ("acq-card-deferred-missing", "This City Is Ours", "disks",
     [DISKS_BLOCKED["content_missing"]["label"], STATES["offline"]]),
    ("acq-block-provider-unreachable", "Conclave", "dependencies", ["TMDB / TVDB", STATES["offline"], DOWN_SINCE]),
    ("acq-block-plex-unreachable", "The Alabama Solution", "dependencies", ["Plex", STATES["offline"], DOWN_SINCE]),
    ("acq-block-client-unreachable", "This City Is Ours", "dependencies",
     ["qBittorrent", STATES["offline"], DOWN_SINCE]),
]
ENTRIES = "()=>history.length"
# Where each section of Système is read from, and its facts as a row says them: label, state's word, line.
REST_READS = {"disks": "/api/maintenance/disks", "dependencies": "/api/system/dependencies"}
AT_REST = """async ([address, states]) => (await (await fetch(address)).json())
  .map((fact) => `${fact.label}${fact.state ? states[fact.state] : (fact.value ?? '')}${fact.secondaryLine ?? ''}`)"""
PORT = "()=>document.querySelector('#port')?.scrollTop ?? null"
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


async def facts_at_rest(page, section):
    """The facts one section of Système holds on the machine at rest, no block posed, as its rows say them."""
    await page.evaluate("()=>window.__go('acq-todo-loaded')")
    await page.wait_for_timeout(SETTLED)
    return await page.evaluate(AT_REST, [REST_READS[section], STATES])


def saying(facts, says):
    """The facts that hold every part of what the landing must say."""
    return [fact for fact in facts if all(part in fact for part in says)]


async def system_door(browser, journal, state, key, section, says):
    """A finger on a door to Système, on a page of its own: one entry, the section saying the cause.

    The page is its own so its history starts there. The section must say the
    cause by a fact absent at rest.
    """
    context, page = await open_page(browser)
    what = f"{state} · « {DISKS if section == 'disks' else DEPENDENCIES} »"
    rest = await facts_at_rest(page, section)
    await go(page, journal, state)
    await page.locator("[data-acqtab=todo]").first.tap()
    await page.wait_for_timeout(SETTLED)
    entries = await page.evaluate(ENTRIES)
    await tap_door(page, key, DISKS if section == "disks" else DEPENDENCIES)
    # The landing keeps its section centred while the page's reads answer.
    await page.wait_for_timeout(SETTLED)
    landed = await page.evaluate(SECTION, section)
    journal.check(f"{what}: lands on Système, « {section} » in view and focused, one entry stacked",
                  landed["path"].endswith("/system") and landed["found"] and landed["inView"] and landed["focused"]
                  and await page.evaluate(ENTRIES) == entries + 1,
                  str({k: v for k, v in landed.items() if k != "facts"}))
    journal.check(f"{what}: the section says the cause — {says} — a fact absent at rest",
                  bool(saying(landed["facts"], says)) and not saying(rest, says),
                  f"landed {landed['facts']} · at rest {rest}")
    await back_to_todo(page, journal, key, 1, what)
    await context.close()


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
        for state, key, section, says in SYSTEM_WALKS:
            await system_door(browser, journal, state, key, section, says)

        # A FULL LIBRARY: every library disk short of room, none saying room.
        rest = await facts_at_rest(page, "disks")
        await go(page, journal, "acq-block-library-full")
        await tap_door(page, "President Curtis", DISKS)
        await page.wait_for_timeout(SETTLED)
        landed = (await page.evaluate(SECTION, "disks"))["facts"]
        library = [fact for fact in landed if fact.startswith("Disk")]
        journal.check(f"acq-block-library-full: every library disk « {STATES['nearly_full']} », none « {STATES['room']} » "
                      "— Disk1's free space no longer contradicts the cause",
                      bool(library) and all(STATES["nearly_full"] in fact and STATES["room"] not in fact
                                            for fact in library)
                      and any(STATES["room"] in fact for fact in rest), f"landed {landed} · at rest {rest}")
        await back_to_todo(page, journal, "President Curtis", 1, f"acq-block-library-full · « {DISKS} »")

        # THE TRACKER: the page and its panel, two entries; at rest it answers.
        context_tracker, tracker_page = await open_page(browser)
        await go(tracker_page, journal, "acq-block-tracker-unreachable")
        await tracker_page.locator("[data-acqtab=todo]").first.tap()
        await tracker_page.wait_for_timeout(SETTLED)
        entries = await tracker_page.evaluate(ENTRIES)
        await tap_door(tracker_page, "Silo|S03", TRACKER)
        landed = await tracker_page.evaluate(PANEL)
        journal.check(f"« {TRACKER} » on an unreachable tracker lands on Trackers, c411's panel up, two entries stacked",
                      landed["path"].endswith("/trackers") and landed["title"] == "c411"
                      and await tracker_page.evaluate(ENTRIES) == entries + 2,
                      f"{landed['path']} · {landed['title']!r}")
        journal.check(f"the tracker's panel says it does not answer — « {UNREACHABLE} … »",
                      UNREACHABLE in landed["text"], landed["text"][:300])
        await back_to_todo(tracker_page, journal, "Silo|S03", 2, f"« {TRACKER} »")
        await tracker_page.evaluate("()=>window.__go('acq-todo-loaded')")
        await tracker_page.wait_for_timeout(SETTLED)
        await tracker_page.evaluate("()=>window.__panel.produce('tracker', 'c411')")
        await tracker_page.wait_for_timeout(PANEL_IN + SETTLED)
        rest = await tracker_page.evaluate(PANEL)
        journal.check(f"at rest, c411's panel does not say « {UNREACHABLE} »", bool(rest["text"])
                      and UNREACHABLE not in rest["text"], rest["text"][:200])
        await context_tracker.close()

        # THE SCROLL KEPT: the list whole, scrolled to its door, Retour.
        await go(page, journal, "acq-todo-every-cause")
        door = page.locator('#view [data-part="card"][data-acquisition="This City Is Ours"] [data-part="card/foot"]',
                            has_text=DISKS)
        # THE FINGER WHERE THE DOOR STANDS, the list scrolled by hand first: a
        # locator's tap scrolls again before it touches, and the offset read
        # before it would not be the one left.
        await door.first.evaluate("(node) => node.scrollIntoView({block: 'center'})")
        await page.wait_for_timeout(SETTLED)
        scrolled = await page.evaluate(PORT)
        box = await door.first.bounding_box()
        await page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        await page.go_back()
        await page.wait_for_timeout(PANEL_IN + SETTLED * 2)
        kept = await page.evaluate(PORT)
        journal.check("Retour from Système gives « À traiter » back at the scroll it was left at",
                      scrolled is not None and scrolled > 0 and kept is not None and abs(kept - scrolled) <= 2,
                      f"left at {scrolled}, back at {kept}")

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
