"""R160 — the season act on a FOLLOWED show's own sheet takes THAT follow (B-382).

RE-AIMED: the season rows are `window.__mocks.seasons()` — the served seasons read's
rows, the ones every season block now draws — since the engine's season table died.

ONE SHOW WAS TWO FOLLOWS. The media sheets are keyed by title and twenty
identities carry two keys — « Silo (2023) » and « Silo » hold the same sheet —
and the screen opened from a provider address is titled by the DATED one. The
sheet's `followed` test matches on the base title, so « Silo (2023) » is
followed by « Silo » and the sheet offers the season act. But the act was
ADDRESSED under the screen's title: the layer found no follow called « Silo
(2023) », began one, and answered « Série suivie et saison 3 demandée — aucun
épisode à récupérer. » — a follow that already existed announced as begun, a
second follow created beside it, and a count read under a key that holds none.
B-378's shape, on the sheet of a show the reader both owns and follows.

WHY THESE THREE SUBJECTS: they are the FOLLOWED shows whose sheet is keyed twice
— the dated key and the bare one resolve the same sheet, the follow is recorded
under the bare one. The first hold for each checks that premise on the
referential and on the follows, so a fixture that moves says so before a finger
does.

ONLY ONE OF THEM HAS A HOLE, AND THIS RULE WAS RE-AIMED FOR IT (B-380). Furious
and President Curtis hold every episode that has aired; their sheets offered the
act only because they divided by the catalogue's total, announced episodes
included, and « 5/8 · 3 manquants » is what made a finger reachable there. With
the denominator repaired the act is gone, which is right: what has not aired is
not missing. So the hold no longer reads « the sheet offers the act » on every
subject. It reads the season family first, and where no aired episode is missing
it holds the OPPOSITE — the sheet offers nothing. The walk under a finger stays
on Silo, the one subject with a hole.

WHAT IT READS, for each subject, on a freshly seeded layer, the sheet opened
under its DATED key and the act pressed by a finger:
  1. THE OPERATION IS CALLED once, and its address names the FOLLOW — the bare
     title — never the sheet's key.
  2. NO FOLLOW IS BEGUN: the follows hold exactly the titles they held before.
     A new title beside the old one is the phantom.
  3. THE FOLLOW THAT EXISTED AGREES WITH THE ANSWER: `acquiring` afterwards
     where the season had episodes to get (Silo), its status UNCHANGED where
     it had none (Furious, President Curtis). RE-AIMED, and said here: this
     hold read « moves to `acquiring` » on all three, so it certified a follow
     « À jour » at 5/5 moved to « En cours d'acquisition » over an answer of
     zero — a proxy (the status moved) held in place of the property (the
     follow says what was answered).
  4. THE SENTENCE is the one chosen for a follow that already existed, at the
     count the follow panel draws for that season — read from `fr.json` and from
     the seasons data the panel reads, never retyped.
  5. NO ERROR IS RAISED.

RE-AIMED, said out loud: the twins' premise read `sheetFor`, and the sheet is opened with the identity a tap carries. The engine's sheet table and
its resolvers are gone; the reads below ask `window.__addressOf` / `__sheetOf` /
`__carriedFor` — the seed the served read answers from, published by the harness
driver — and the hold count is unchanged.

RE-AIMED when the engine's `window.__referentiel` object died: the base title
is read through `window.__baseTitle`, published by `harness/publish.ts` from
`lib/titles.ts`. The holds and what they compare are unchanged.

RE-AIMED when the follows took the contract's names: a follow's title, kind and
status are read as `title`, `kind` and `status` (and `owned`), where they were
the engine's `t`, `k` and `st`. The holds and what they compare are unchanged.
"""
import asyncio
import json
import pathlib
import sys
from urllib.parse import unquote

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, ROOT, SETTLED, Journal, open_page

from playwright.async_api import async_playwright

# A state that re-seeds the layer; the sheet is opened over it.
START_STATE = "acq-follows-list"

# The followed show and the key its sheet is opened under.
# french-ok: media titles, the fixture's own data
SUBJECTS = {
    "Silo": "Silo (2023)",
    "Furious": "Furious (2026)",
    "President Curtis": "President Curtis (2026)",
}

GRAB_OPERATION = "grabSeasonForFollow"
BEING_ACQUIRED = "acquiring"

SENTENCES = json.loads(
    (ROOT / "design" / "src" / "i18n" / "fr.json").read_text(encoding="utf-8")
)["verbs"]["media"]

ANSWERED = "()=>(window.__mocks?.answered?.() || [])"

FOLLOWS = """()=>Object.fromEntries((window.__followActions?.all() || []).map(
  (one) => [one.title, one.status]))"""

# THE PREMISE, on the referential and on the follows: both keys resolve a sheet,
# the follow is recorded under the bare one and not under the dated one.
TWINS = """([bare, dated])=>{
  const titles = (window.__followActions?.all() || []).map((one) => one.title);
  return {bareSheet: !!window.__sheetOf(bare), datedSheet: !!window.__sheetOf(dated),
          sameBase: window.__baseTitle(bare) === window.__baseTitle(dated),
          followedBare: titles.includes(bare), followedDated: titles.includes(dated)};}"""

# EVERY SEASON ROW ON THE SHEET THAT OFFERS THE ACT, with its value.
OFFERED = """()=>{
  const root = document.querySelector('[data-region="screen-media/body"]');
  return root ? [...root.querySelectorAll('[data-part="season/grab"]')]
    .map((act) => act.dataset.grabSeason || "") : [];}"""

# THE SUMMARY OF THE ROW HOLDING AN ACT — a closed row gives its button no box.
ROW_OF = """(value)=>{
  const act = document.querySelector(`[data-grab-season="${CSS.escape(value)}"]`);
  const row = act && act.closest('[data-part="season"]');
  const summary = row && row.querySelector("summary");
  if (!summary) return {found: false};
  summary.scrollIntoView({block: "center"});
  const box = summary.getBoundingClientRect();
  const x = box.left + box.width / 2, y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, open: row.open,
          reachable: !!hit && (hit === summary || summary.contains(hit))};}"""

AIM = """(value)=>{
  const target = document.querySelector(`[data-grab-season="${CSS.escape(value)}"]`);
  if (!target) return {found: false};
  target.scrollIntoView({block: "center"});
  const box = target.getBoundingClientRect();
  const x = box.left + box.width / 2, y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, reachable: !!hit && (hit === target || target.contains(hit))};}"""

# WHETHER ANY AIRED EPISODE OF THE FOLLOW IS MISSING, from the data the follow
# panel reads: a season whose owned count is below its aired count.
HAS_A_HOLE = """(title)=>(window.__mocks.seasons()[title] || []).some(
  ([, aired, owned]) => (owned || 0) < (aired || 0))"""

# WHAT THE FOLLOW PANEL DRAWS MISSING for one season, from the data it reads.
MISSING = """([title, season])=>{
  const row = (window.__mocks.seasons()[title] || []).find(([number]) => number === season);
  if (!row) return null;
  const missing = (row[1] || 0) - (row[2] || 0);
  return missing > 0 ? missing : 0;}"""

SAID = """()=>{const held = window.__toast?.read?.();
  return held && held.message ? held.message.message || '' : '';}"""


def sentence_for_an_existing_follow(season, count, title):
    """The sentence the act chooses for a follow that already existed.

    Args:
        season: The season asked for.
        count: The episodes the season is missing.
        title: The show the sentence names.

    Returns:
        The sentence, from the interface's own resource.
    """
    if count == 0:
        key = "seasonAskedNone"
    elif count == 1:
        key = "seasonAskedOne"
    else:
        key = "seasonAsked"
    return (SENTENCES[key].replace("{{season}}", str(season))
            .replace("{{count}}", str(count)).replace("{{title}}", title))


async def take_a_season(page, journal, errors, bare, dated):
    """Opens a followed show's sheet under its dated key and takes a season by finger.

    Args:
        page: The page.
        journal: Where the holds are recorded.
        errors: The page errors collected so far, cleared before the act.
        bare: The title the follow is recorded under.
        dated: The key the sheet is opened under.
    """
    where = f"« {dated} », followed as « {bare} »"
    await page.evaluate("(id)=>window.__go(id)", START_STATE)
    await page.wait_for_timeout(SETTLED)
    twins = await page.evaluate(TWINS, [bare, dated])
    journal.check(f"{where}: both keys resolve one sheet and the follow is the bare one",
                  twins["bareSheet"] and twins["datedSheet"] and twins["sameBase"]
                  and twins["followedBare"] and not twins["followedDated"], str(twins))
    await page.evaluate("(title)=>window.__screens.mediaSheet(title, window.__carriedFor(title) ?? undefined)", dated)
    await page.wait_for_timeout(SETTLED * 3)
    await page.evaluate("()=>window.__toast?.hide?.()")
    offered = await page.evaluate(OFFERED)
    if not await page.evaluate(HAS_A_HOLE, bare):
        journal.check(f"{where}: nothing that aired is missing, so the sheet offers no season act",
                      not offered, str(offered))
        return
    journal.check(f"{where}: the sheet offers the season act", bool(offered), str(offered))
    if not offered:
        return
    value = offered[0]
    season = int(value.split("|")[-1])
    row = await page.evaluate(ROW_OF, value)
    if row.get("found") and row.get("reachable") and not row.get("open"):
        await page.touchscreen.tap(row["x"], row["y"])
        await page.wait_for_timeout(SETTLED)
    act = await page.evaluate(AIM, value)
    journal.check(f"{where}: a finger reaches « season {season} »'s act",
                  act.get("found") and act.get("reachable"), str(act))
    if not (act.get("found") and act.get("reachable")):
        return
    before = await page.evaluate(FOLLOWS)
    count = await page.evaluate(MISSING, [bare, season])
    mark = len(await page.evaluate(ANSWERED))
    errors.clear()
    await page.touchscreen.tap(act["x"], act["y"])
    await page.wait_for_timeout(ACTED)

    grabs = [call for call in (await page.evaluate(ANSWERED))[mark:]
             if call["operationId"] == GRAB_OPERATION]
    paths = [unquote(call["path"]) for call in grabs]
    journal.check(f"{where}: the act is called once, addressed to the FOLLOW « {bare} »",
                  len(paths) == 1 and paths[0].endswith(f"/follows/{bare}/seasons/{season}/grab"),
                  str(paths))
    after = await page.evaluate(FOLLOWS)
    phantoms = sorted(set(after) - set(before))
    journal.check(f"{where}: no follow is begun — the follows hold the same titles",
                  not phantoms and len(after) == len(before),
                  f"{len(before)} → {len(after)}, new: {phantoms}")
    # THE FOLLOW AGREES WITH WHAT WAS ANSWERED: it moves to being acquired only
    # when the season had something to get, and keeps its status over an answer
    # of nothing — never « En cours d'acquisition » beside « 5/5 · À jour ».
    if count:
        journal.check(f"{where}: the follow that existed moves to « {BEING_ACQUIRED} » — "
                      f"the season had {count} episode(s) to get",
                      after.get(bare) == BEING_ACQUIRED,
                      f"{before.get(bare)!r} → {after.get(bare)!r}")
    else:
        journal.check(f"{where}: the follow that existed KEEPS its status — the answer had "
                      "nothing to get, so nothing is being acquired",
                      count is not None and after.get(bare) == before.get(bare),
                      f"count {count!r}, {before.get(bare)!r} → {after.get(bare)!r}")
    said = await page.evaluate(SAID)
    expected = sentence_for_an_existing_follow(season, count, bare) if count is not None else None
    journal.check(f"{where}: the sentence is the one for a follow that existed, at the panel's count",
                  expected is not None and said == expected, f"{said!r} against {expected!r}")
    journal.check(f"{where}: pressing raises no error", not errors, str(errors))


async def main():
    journal = Journal("R160 — the season act on a followed show's sheet takes that follow")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        for bare, dated in SUBJECTS.items():
            await take_a_season(page, journal, errors, bare, dated)
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
