"""R173 — one season family: every surface counts what has AIRED (B-380).

RE-AIMED: the season family is `window.__mocks.seasonFamily()` — the seed the engine's
season table was a copy of — since that table died.

« MANQUANT » IS AN EPISODE THAT HAS AIRED AND IS NOT HELD. An episode the
catalogue announces and nobody has broadcast yet cannot be held, so it is not
missing: it is drawn to say a release is coming, and it is offered no act. The
media sheet broke that in its denominator — it took the catalogue's TOTAL as
the aired count — so on Silo the sheet printed « Saison 3 · 6/10 · 4 manquants »
while the follow panel printed « 6/7 · 1 manquant » about the same season.

THE AIRED COUNT IS DERIVED, ONCE, IN THE LAYER — from the catalogue's own episode
dates against the referential's today — and every family that states a count
must agree with it. Four families state one, and they are read here:

  1. THE SEASON FAMILY (`window.__mocks.seasonFamily()`, `[number, aired, owned]`), which the
     follow panel and every rule looking for « a season with a hole » read;
  2. THE LAYER's seasons answer — the `aired` it derives and the owned numbers it
     holds — which the sheet reads. Where the sheet is OWNED, the owned count is
     the same derivation the sheet makes: the numbers at or below what aired;
  3. THE FOLLOWS' totals, which are the season family's sums;
  4. THE INCOMPLETE SHOWS' totals, which are the season family's sums too.

A number corrected in one of them and not in the others is B-088's class — two
families keyed the same way are not the same answer — and it is what the first
half of this rule refuses, over EVERY followed show the season family holds.

ONE NAMED EXCLUSION, AND IT ASSERTS. « Dexter: Resurrection » is followed under a
title no sheet carries and its follow's totals are not its seasons' sums (B-476).
It is not filtered out: the rule holds that it STILL disagrees, so the day B-476
is repaired this falls, and the exclusion has to leave with it.

THE SECOND HALF IS THE SCREEN, on the three followed seasons where the catalogue
announces more than has aired — the only seasons where the two readings of the
denominator draw different numbers, so the only ones where a sheet reverting to
the catalogue's total can be seen. The sheet and the follow panel must draw the
same fraction and the same « manquants », both equal to the season family. The
announced episodes are drawn as information beside the fraction.

AND ONE SEASON NOT YET AIRED, drawn as information with no act, beside a season
that aired in 1997 and keeps its act because everything in it is missing.

Every count below is read from the data the surface is drawn from, and every word
from `fr.json`: nothing about a fixture is typed here but the subjects' titles.

RE-AIMED, said out loud: the address and the catalogue were read from `addressIdsFor` and `sheetFor`. The engine's sheet table and
its resolvers are gone; the reads below ask `window.__addressOf` / `__sheetOf` /
`__carriedFor` — the seed the served read answers from, published by the harness
driver — and the hold count is unchanged.
"""
import asyncio
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PANEL_IN, ROOT, SETTLED, Journal, open_page

from playwright.async_api import async_playwright

# A state that re-seeds the layer; every surface is raised over it.
START_STATE = "acq-follows-list"

CONTRACT = json.loads((ROOT / "contract" / "openapi.json").read_text(encoding="utf-8"))
WORDS = json.loads((ROOT / "design" / "src" / "i18n" / "fr.json").read_text(encoding="utf-8"))
SEASON_WORD = WORDS["common"]["season"]
UPCOMING_WORD = WORDS["screens"]["media"]["seasonUpcoming"]

# The followed show whose follow totals are known to disagree, and its entry.
# french-ok: a media title, the fixture's own data
KNOWN_DISAGREEMENT = {"Dexter: Resurrection": "B-476"}

# The followed show, the key its sheet is opened under, and the season whose
# catalogue announces more than has aired.
# french-ok: media titles, the fixture's own data
SCREEN_SUBJECTS = [
    ("Silo", "Silo (2023)", 3),
    ("Furious", "Furious (2026)", 1),
    ("American Dad!", "American Dad!", 22),
]

# A season that has not aired, on a sheet the reader owns and holds nothing of
# that season; and a season that aired long ago and holds nothing. NOT « Scrubs »,
# although its second season is unaired too: its sheet is the revival's and its
# owned numbers are the original show's, so it holds episodes nobody has aired.
# french-ok: media titles, the fixture's own data
NOT_YET_AIRED = ("Reine rouge", 2)
# french-ok: a media title, the fixture's own data
AIRED_LONG_AGO = ("Les Animaniacs", 5)

SHEET_SCOPE = '[data-region="screen-media/body"]'
PANEL_SCOPE = "#sheetin"


def operation_path(operation_id):
    """The path the contract declares for one operation.

    Args:
        operation_id: The operation, as the contract names it.

    Returns:
        The path template.

    Raises:
        SystemExit: When the contract declares no such operation.
    """
    for path, item in CONTRACT["paths"].items():
        for operation in item.values():
            if isinstance(operation, dict) and operation.get("operationId") == operation_id:
                return path
    raise SystemExit(f"the contract declares no {operation_id}")


# EVERY FAMILY, READ THROUGH THE LAYER'S OWN ANSWERS — `fetch` is the seam, so
# this is the answer the surfaces are drawn from and not a second reading of it.
FAMILIES = """async ([followsPath, incompletePath, seasonsPath, sheetPath]) => {
  const read = async (path) => {
    const answer = await fetch(path);
    return answer.ok ? answer.json() : null;
  };
  const reference = window.__referentiel;
  const shows = [];
  for (const title of Object.keys(window.__mocks.seasonFamily())) {
    const address = window.__addressOf(title);
    let seasons = null;
    let sheet = null;
    if (address) {
      const at = (template) => template
        .replace("{provider}", encodeURIComponent(address.provider))
        .replace("{providerId}", encodeURIComponent(address.id));
      seasons = await read(at(seasonsPath));
      sheet = await read(at(sheetPath));
    }
    shows.push({title, family: window.__mocks.seasonFamily()[title], address,
                aired: seasons ? seasons.aired : null,
                owned: seasons ? seasons.owned : null,
                sheetOwned: sheet ? sheet.owned === true : false});
  }
  return {follows: await read(followsPath), incomplete: await read(incompletePath), shows};
}"""

# ONE SEASON ROW, read where a reader reads it: the summary's own text for the
# number and the fraction, and the named parts for what it says beside them.
ROW = """([scope, word, season]) => {
  const root = document.querySelector(scope);
  if (!root) return {found: false, reason: "no " + scope};
  for (const row of root.querySelectorAll('[data-part="season"]')) {
    const summary = row.querySelector("summary");
    const text = ((summary && summary.textContent) || "").replace(/\\s+/g, " ").trim();
    if (text !== `${word} ${season}` && !text.startsWith(`${word} ${season} `)) continue;
    const said = (part) => {
      const found = row.querySelector(`[data-part="${part}"]`);
      return found ? found.textContent.replace(/\\s+/g, " ").trim() : null;
    };
    return {found: true, text, missing: said("season/missing"),
            upcoming: said("season/upcoming"),
            act: !!row.querySelector('[data-part="season/grab"]')};
  }
  return {found: false, reason: "no row " + season};
}"""

# WHAT THE CATALOGUE SAYS OF ONE SEASON: how many of its episodes aired by
# today, how many are announced after it, and the first announced date as the
# interface formats it.
CATALOGUE = """([key, season]) => {
  const reference = window.__referentiel;
  const sheet = window.__sheetOf(key);
  const episodes = (sheet && sheet.episodes && sheet.episodes[String(season)]) || [];
  const total = ((sheet && sheet.seasons) || []).find((one) => one.number === season);
  const ahead = episodes.filter((one) => one.airDate && one.airDate > reference.TODAY)
    .map((one) => one.airDate).sort();
  return {total: total ? total.episodes : null,
          aired: episodes.filter((one) => one.airDate && one.airDate <= reference.TODAY).length,
          ahead: ahead.length,
          firstAhead: ahead.length ? reference.dateFR(ahead[0]) : null};
}"""


def fraction_of(row):
    """The « owned/aired » a season row's summary draws, or the word it draws instead.

    Args:
        row: The row as `ROW` read it.

    Returns:
        The fraction or word after the season number, or None.
    """
    match = re.match(rf"{re.escape(SEASON_WORD)} \d+ (\S+(?: \S+)?)", row.get("text", ""))
    if not match:
        return None
    drawn = match.group(1)
    if drawn.startswith(UPCOMING_WORD):
        return UPCOMING_WORD
    return drawn.split(" ")[0]


def count_in(said):
    """The leading count of a « N manquants » mark, or None when nothing is said.

    Args:
        said: The mark's text.

    Returns:
        The count.
    """
    match = re.match(r"(\d+)", said or "")
    return int(match.group(1)) if match else None


async def families_agree(page, journal):
    """Holds that every family stating a season count states the same one.

    Args:
        page: The page.
        journal: Where the holds are recorded.
    """
    await page.evaluate("(id)=>window.__go(id)", START_STATE)
    await page.wait_for_timeout(SETTLED)
    read = await page.evaluate(FAMILIES, [
        operation_path("readFollows"), operation_path("readLibraryIncomplete"),
        operation_path("readMediaSeasons"), operation_path("readMediaSheet")])
    follows = {one["title"]: one for one in read["follows"] or []}
    incomplete = {one["title"]: one for one in read["incomplete"] or []}
    journal.check("the layer answers the follows and the incomplete shows",
                  bool(follows) and bool(incomplete),
                  f"{len(follows)} follows, {len(incomplete)} incomplete")
    followed = [show for show in read["shows"] if show["title"] in follows]
    journal.check("the season family holds followed shows to read — the floor that makes "
                  "the holds below mean something",
                  len(followed) >= 5, str([show["title"] for show in followed]))
    for show in followed:
        title = show["title"]
        sums = (sum(owned for _, _, owned in show["family"]),
                sum(aired for _, aired, _ in show["family"]))
        totals = (follows[title].get("owned"), follows[title].get("aired"))
        if title in KNOWN_DISAGREEMENT:
            journal.check(f"« {title} »'s follow STILL disagrees with its seasons "
                          f"({KNOWN_DISAGREEMENT[title]}) — when this falls, the entry is "
                          "repaired and the exclusion leaves",
                          totals != sums, f"follow {totals} against seasons {sums}")
        else:
            journal.check(f"« {title} »: the follow's totals are its seasons' sums",
                          totals == sums, f"follow {totals} against seasons {sums}")
        if show["aired"] is None:
            journal.check(f"« {title} » has no sheet to derive from — only the named "
                          "exclusion may lack one",
                          title in KNOWN_DISAGREEMENT, str(show["address"]))
            continue
        aired_apart = [(number, aired, show["aired"].get(str(number)))
                       for number, aired, _ in show["family"]
                       if show["aired"].get(str(number)) != aired]
        journal.check(f"« {title} »: every season's aired count is the one the layer derives "
                      "from the catalogue's dates",
                      not aired_apart,
                      f"{len(show['family'])} season(s), apart (season, family, layer): "
                      f"{aired_apart}")
        if show["sheetOwned"]:
            owned_apart = []
            for number, aired, owned in show["family"]:
                numbers = (show["owned"] or {}).get(str(number), [])
                derived = len([one for one in numbers if one <= aired])
                if derived != owned:
                    owned_apart.append((number, owned, derived))
            journal.check(f"« {title} »: every season's owned count is the sheet's own "
                          "derivation — the numbers at or below what aired",
                          not owned_apart,
                          f"apart (season, family, derived): {owned_apart}")
    counted = [show for show in read["shows"] if show["title"] in incomplete]
    journal.check("the season family holds incomplete shows to read", bool(counted),
                  str([show["title"] for show in counted]))
    for show in counted:
        title = show["title"]
        sums = (sum(owned for _, _, owned in show["family"]),
                sum(aired for _, aired, _ in show["family"]))
        totals = (incomplete[title]["owned"], incomplete[title]["aired"])
        journal.check(f"« {title} »: the incomplete show's totals are its seasons' sums",
                      totals == sums, f"incomplete {totals} against seasons {sums}")


async def one_season_on_both_surfaces(page, journal, errors, bare, key, season):
    """Holds that the sheet and the follow panel draw one season identically.

    Args:
        page: The page.
        journal: Where the holds are recorded.
        errors: The page errors collected so far.
        bare: The title the follow is recorded under.
        key: The key the sheet is opened under.
        season: The season read.
    """
    where = f"« {bare} » season {season}"
    await page.evaluate("(id)=>window.__go(id)", START_STATE)
    await page.wait_for_timeout(SETTLED)
    family = await page.evaluate(
        "([title, season])=>(window.__mocks.seasonFamily()[title] || []).find(([n]) => n === season) || null",
        [bare, season])
    catalogue = await page.evaluate(CATALOGUE, [key, season])
    journal.check(f"{where}: the catalogue announces more than has aired — the case where "
                  "the two denominators draw apart",
                  family is not None and catalogue["total"] is not None
                  and catalogue["total"] > family[1],
                  f"family {family}, catalogue {catalogue}")
    if family is None:
        return
    _, aired, owned = family
    expected = f"{owned}/{aired}"
    missing = aired - owned

    errors.clear()
    await page.evaluate("(title)=>window.__screens.mediaSheet(title, window.__carriedFor(title) ?? undefined)", key)
    await page.wait_for_timeout(SETTLED * 3)
    sheet = await page.evaluate(ROW, [SHEET_SCOPE, SEASON_WORD, season])
    await page.evaluate("(id)=>window.__go(id)", START_STATE)
    await page.wait_for_timeout(SETTLED)
    await page.evaluate("(title)=>window.__panel.produce('follow', title)", bare)
    await page.wait_for_timeout(PANEL_IN + SETTLED)
    panel = await page.evaluate(ROW, [PANEL_SCOPE, SEASON_WORD, season])

    journal.check(f"{where}: the SHEET draws owned over AIRED — « {expected} »",
                  sheet.get("found") and fraction_of(sheet) == expected,
                  f"{sheet.get('text') or sheet.get('reason')!r}")
    journal.check(f"{where}: the FOLLOW PANEL draws the same « {expected} »",
                  panel.get("found") and fraction_of(panel) == expected,
                  f"{panel.get('text') or panel.get('reason')!r}")
    journal.check(f"{where}: both say the same « manquants », aired and not held — {missing}",
                  count_in(sheet.get("missing")) == (missing or None)
                  and count_in(panel.get("missing")) == (missing or None),
                  f"sheet {sheet.get('missing')!r}, panel {panel.get('missing')!r}")
    journal.check(f"{where}: the sheet says the {catalogue['ahead']} announced episode(s) are "
                  f"coming, from {catalogue['firstAhead']}",
                  catalogue["ahead"] > 0 and sheet.get("upcoming") is not None
                  and str(catalogue["ahead"]) in sheet["upcoming"]
                  and catalogue["firstAhead"] in sheet["upcoming"],
                  f"{sheet.get('upcoming')!r}")
    journal.check(f"{where}: raising both surfaces raises no error", not errors, str(errors))


async def a_season_not_yet_aired(page, journal):
    """Holds the information drawn for an unaired season, and the act kept by an aired one.

    Args:
        page: The page.
        journal: Where the holds are recorded.
    """
    title, season = NOT_YET_AIRED
    await page.evaluate("(id)=>window.__go(id)", START_STATE)
    await page.wait_for_timeout(SETTLED)
    catalogue = await page.evaluate(CATALOGUE, [title, season])
    journal.check(f"« {title} » season {season} has not aired: nothing of it before today, "
                  "and a date after it",
                  catalogue["aired"] == 0 and catalogue["firstAhead"] is not None, str(catalogue))
    await page.evaluate("(title)=>window.__screens.mediaSheet(title, window.__carriedFor(title) ?? undefined)", title)
    await page.wait_for_timeout(SETTLED * 3)
    row = await page.evaluate(ROW, [SHEET_SCOPE, SEASON_WORD, season])
    journal.check(f"« {title} » season {season}: drawn « {UPCOMING_WORD} », with its date",
                  row.get("found") and fraction_of(row) == UPCOMING_WORD
                  and row.get("upcoming") is not None
                  and str(catalogue["firstAhead"]) in row["upcoming"],
                  f"{row.get('text') or row.get('reason')!r}, beside it {row.get('upcoming')!r}")
    journal.check(f"« {title} » season {season}: offered no act, and says nothing is missing",
                  row.get("found") and not row.get("act") and row.get("missing") is None,
                  str(row))

    title, season = AIRED_LONG_AGO
    catalogue = await page.evaluate(CATALOGUE, [title, season])
    await page.evaluate("(id)=>window.__go(id)", START_STATE)
    await page.wait_for_timeout(SETTLED)
    await page.evaluate("(title)=>window.__screens.mediaSheet(title, window.__carriedFor(title) ?? undefined)", title)
    await page.wait_for_timeout(SETTLED * 3)
    row = await page.evaluate(ROW, [SHEET_SCOPE, SEASON_WORD, season])
    journal.check(f"« {title} » season {season} aired entire and nothing of it is held: it "
                  f"keeps its act, and all {catalogue['aired']} are missing",
                  row.get("found") and row.get("act") and catalogue["aired"] > 0
                  and catalogue["ahead"] == 0
                  and count_in(row.get("missing")) == catalogue["aired"],
                  f"{row.get('text') or row.get('reason')!r}, catalogue {catalogue}")


async def main():
    """Reads the four families, then the two surfaces."""
    journal = Journal("R173 — one season family: every surface counts what has aired")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await families_agree(page, journal)
        for bare, key, season in SCREEN_SUBJECTS:
            await one_season_on_both_surfaces(page, journal, errors, bare, key, season)
        await a_season_not_yet_aired(page, journal)
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
