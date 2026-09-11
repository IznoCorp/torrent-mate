"""R158 — a season with a hole is taken by someone who OWNS the show and does not follow it.

THE PREMISE THIS RULE REFUSES was written in the code as a comment: « the panel
is only ever drawn for [a follow] ». It was false. A card in the library's
« Incomplets » lens carries `data-panel="media:<title>"`, the engine's
delegation discards the genre and produces the FOLLOW panel for any title, and
`followFacts` synthesises a record for an incomplete show. So the follow panel's
season grab was reachable, with one tap, for a medium nobody follows — and its
mock answered a success over a world in which nothing had changed (B-378). The
operator ruled « offer it — the backend follows »: the act is legitimate, and it
implies the follow.

WHY THESE TWO SUBJECTS, and the rule derives them rather than trusting this
sentence: « Les Animaniacs » and « Les aventures de Tintin » are the only
incomplete shows the fixture holds that carry SEASONS data with a hole. The
other ten fall to the « no season data » note and draw no matrix and no verb,
which is why nobody met the defect by accident. None of the twelve is followed,
so every card in the lens reaches the non-follow path. If the fixture moves, the
first hold says so before a finger does.

WHAT IT READS, on BOTH surfaces that draw the same hole — the follow panel
raised from the lens card's body, and the media sheet opened from its poster —
each walked on a freshly seeded layer, for each subject:

  1. A FINGER REACHES the card and then the season's button — hit-tested at the
     element's own centre, never clicked through a selector.
  2. THE OPERATION IS CALLED once, for the season the finger was on, answered
     as a success — read on what the LAYER answered, because the mock layer replaces
     `fetch` and no browser request event ever fires for it.
  3. THE WORLD MOVES: the medium is followed afterwards, when it was not before.
     A success over an unchanged world is the exact defect of B-378.
  4. THE SENTENCE IS CHOSEN for a follow begun by the act — one of the
     `…NewlyFollowed` sentences, read from `fr.json` rather than retyped. That
     is the only reading of the answer's `newlyFollowed` a rule can take: the
     layer records a call's status and path, not its body.
  5. THE SURFACE PRESSED READS DIFFERENTLY afterwards — the one the operator was
     looking at is not the only one that does not know.
  6. NO ERROR IS RAISED.

AND ONE NEGATIVE LEG, from a measurement: the sheet's season list must NOT
offer the act on a show nobody owns. `complete` is false for anything not
owned, so a gate written as `!complete` alone offered a grab on all seven
seasons of « The Venture Bros » (`mediasheet-suggestion-series`). Those rows are
CLOSED <details>: a button inside one has no box, the oracle measured no
divergence and every tier stayed green. So it is COUNTED IN THE DOCUMENT, and
beside it Silo's owned sheet is held to offer the act exactly where it prints a
shortfall, so the count of zero reads a gate and not a list that stopped
drawing.

WHAT IT DOES NOT READ: the QUEUED path of a follow begun by the act — the
pipeline busy, `seasonQueuedNewlyFollowed` said, the follow created `pending`.
R125 holds the queued clause on a medium already followed; this rule walks the
idle pipeline only.

THE HIT TEST IS INLINED, as it is in the other rules that tap: moving it to
`common.py` needs a rule to be pointable at a build first (B-325).
"""
import asyncio
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, PANEL_IN, ROOT, SETTLED, Journal, open_page

from playwright.async_api import async_playwright

# Where the incomplete shows are drawn, as cards a finger can reach.
LENS_STATE = "lib-incomplete"
# A series nobody owns or follows, whose sheet draws season rows from the
# catalogue — the negative leg's subject.
SUGGESTION_STATE = "mediasheet-suggestion-series"
# An owned series with a hole — the negative leg's control.
OWNED_SHEET_STATE = "mediasheet-series"

# The operation, as the contract names it, read by operationId.
GRAB_OPERATION = "grabSeasonForFollow"

# The two subjects the fixture holds, named so the derivation below is checked
# against a sentence a reader can see. french-ok: media titles, the fixture's own data
EXPECTED_SUBJECTS = {"Les Animaniacs", "Les aventures de Tintin"}

# The surfaces, and how a finger reaches each from a lens card.
PANEL = "panel"
SHEET = "sheet"
REACHED_BY = {
    PANEL: ("card/body", "data-panel", "media:{title}", "#sheetin"),
    SHEET: ("card/poster", "data-mediasheet", "{title}", '[data-region="screen-media/body"]'),
}

# THE SENTENCES, read from the resource the interface reads. A retyped sentence
# renders correctly in a rule while the reference is broken.
SENTENCES = json.loads(
    (ROOT / "design" / "src" / "i18n" / "fr.json").read_text(encoding="utf-8")
)["verbs"]["media"]
NEWLY_FOLLOWED_KEYS = (
    "seasonAskedNewlyFollowed",
    "seasonAskedOneNewlyFollowed",
    "seasonAskedNoneNewlyFollowed",
)

ANSWERED = "()=>(window.__mocks?.answered?.() || [])"

FOLLOWS = """()=>Object.fromEntries((window.__followActions?.all() || []).map(
  (one) => [one.t, one.st]))"""

# WHICH INCOMPLETE SHOWS HAVE A HOLE THE MATRIX DRAWS, and which are followed —
# from the data, before a finger moves.
THE_SUBJECTS = """()=>{
  const followed = new Set((window.__followActions?.all() || []).map((one) => one.t));
  const incomplete = (window.__referentiel?.INCOMPLETE || []).map((show) => show.t);
  return {
    incomplete: incomplete.length,
    followedAmongThem: incomplete.filter((title) => followed.has(title)),
    withAHole: incomplete.filter((title) => (window.SEASONS[title] || []).some(
      ([number, aired, owned]) => (owned || 0) < (aired || 0))),
  };}"""

# The greeting toast sits over the surface (B-317) and no gesture dismisses it,
# so it is emptied: this walk does not prove the toast can be dismissed, only
# that what is under it is reachable once it is gone.
EMPTY_THE_TOAST = """()=>{const one = document.querySelector('#toast');
  if (!one) return false;
  one.textContent = "";
  one.className = "";
  one.removeAttribute("data-open");
  return true;}"""

# WHAT A TAP AT THE ELEMENT'S CENTRE WOULD HIT, after bringing it into view.
AIM = """([part, attribute, value])=>{
  const target = [...document.querySelectorAll(`[data-part="${part}"]`)].find(
    (one) => one.getAttribute(attribute) === value);
  if (!target) return {found: false};
  target.scrollIntoView({block: "center"});
  const box = target.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y,
          reachable: !!hit && (hit === target || target.contains(hit)),
          covering: hit === null ? "nothing" :
            (hit.tagName + (hit.className ? "." + String(hit.className).split(" ")[0] : ""))};}"""

# THE FIRST SEASON IN THE SURFACE THAT PRINTS A SHORTFALL, and the act on it.
SEASON_ON_OFFER = """(scope)=>{
  const root = document.querySelector(scope);
  if (!root) return {scope: false};
  for (const season of root.querySelectorAll('[data-part="season"]')) {
    if (!season.querySelector('[data-part="season/missing"]')) continue;
    const act = season.querySelector('[data-part="season/grab"]');
    return {scope: true,
            label: ((season.querySelector("summary") || {}).textContent || "").trim(),
            offered: !!act, value: act ? act.dataset.grabSeason || "" : ""};
  }
  return {scope: true, label: "", offered: false, value: ""};}"""

# THE SEASON ROWS AND THE ACTS ON THEM, COUNTED IN THE DOCUMENT — open or not.
# A closed <details> gives a button no box, so only the tree can say it is there.
COUNT_ON_THE_SHEET = """()=>{
  const root = document.querySelector('[data-region="screen-media/body"]');
  const rows = root ? [...root.querySelectorAll('[data-part="season"]')] : [];
  return {
    rows: rows.length,
    grabs: rows.filter((row) => row.querySelector('[data-part="season/grab"]')).length,
    shortfalls: rows.filter((row) => row.querySelector('[data-part="season/missing"]')).length,
    labels: rows.filter((row) => row.querySelector('[data-part="season/grab"]'))
      .map((row) => ((row.querySelector("summary") || {}).textContent || "").trim()),
  };}"""

SAID = """()=>{
  const held = window.__toast?.read?.();
  return held && held.message ? held.message.message || '' : '';}"""

SURFACE_TEXT = "(scope)=>(document.querySelector(scope)?.textContent || '')"


def chosen_for_a_follow_begun(said, season):
    """Says whether a message is one of the sentences chosen for a follow begun.

    Args:
        said: What the interface said.
        season: The season the act was for.

    Returns:
        The matching key, or an empty string.
    """
    for key in NEWLY_FOLLOWED_KEYS:
        pieces = re.split(r"(\{\{season\}\}|\{\{count\}\})", SENTENCES[key])
        pattern = "".join(
            re.escape(str(season)) if piece == "{{season}}"
            else r"\d+" if piece == "{{count}}"
            else re.escape(piece)
            for piece in pieces)
        if re.fullmatch(pattern, said):
            return key
    return ""


async def take_a_season(page, journal, errors, title, surface):
    """Walks one subject to one surface from the lens, and takes a season there.

    Args:
        page: The page.
        journal: Where the holds are recorded.
        errors: The page errors collected so far, cleared before the act.
        title: The incomplete show.
        surface: `PANEL` or `SHEET`.
    """
    part, attribute, value, scope = REACHED_BY[surface]
    where = f"« {title} » on the {surface}"
    # A FRESH LAYER FOR EVERY WALK: `__go` re-seeds the mocks, so a follow begun
    # by the previous walk cannot make this one's subject « already followed ».
    await page.evaluate("(id)=>window.__go(id)", LENS_STATE)
    await page.wait_for_timeout(SETTLED)
    # THE LENS IN LIST MODE, where a card's body raises the panel and its poster
    # opens the sheet. A tile carries both on one node and a tap opens the sheet
    # (B-316), so the grid cannot reach the panel by finger at all.
    await page.evaluate("""()=>window.__store.write({libMode: "list"})""")
    await page.wait_for_timeout(SETTLED)
    await page.evaluate(EMPTY_THE_TOAST)
    before = await page.evaluate(FOLLOWS)
    journal.check(f"{where}: nobody follows it before the act", title not in before,
                  f"status before: {before.get(title)!r}")
    aim = await page.evaluate(AIM, [part, attribute, value.format(title=title)])
    journal.check(f"{where}: a finger reaches its card's {part}",
                  aim["found"] and aim["reachable"],
                  f"found={aim['found']} hits {aim.get('covering')}")
    if not (aim["found"] and aim["reachable"]):
        return
    await page.touchscreen.tap(aim["x"], aim["y"])
    await page.wait_for_timeout(PANEL_IN if surface == PANEL else SETTLED * 2)
    season = await page.evaluate(SEASON_ON_OFFER, scope)
    journal.check(f"{where}: it prints a season with a shortfall and OFFERS to take it",
                  season["scope"] and season["offered"],
                  f"scope={season['scope']} {season.get('label')!r} "
                  f"value={season.get('value')!r}")
    if not season["offered"]:
        return
    act = await page.evaluate(AIM, ["season/grab", "data-grab-season", season["value"]])
    journal.check(f"{where}: and a finger reaches that button",
                  act["found"] and act["reachable"], f"hits {act.get('covering')}")
    if not (act["found"] and act["reachable"]):
        return
    number = season["value"].split("|")[-1]
    looked_at = await page.evaluate(SURFACE_TEXT, scope)
    mark = len(await page.evaluate(ANSWERED))
    errors.clear()
    await page.touchscreen.tap(act["x"], act["y"])
    await page.wait_for_timeout(ACTED)
    grabs = [call for call in (await page.evaluate(ANSWERED))[mark:]
             if call["operationId"] == GRAB_OPERATION]
    # ANSWERED AS A SUCCESS, not « answered 201 ». The contract declares 201 and
    # the layer answers 200 — measured on every walk of this rule — so a hold on
    # the literal code would be red for a reason that is not this act.
    journal.check(
        f"{where}: the season grab is called ONCE, for season {number}, answered "
        "as a success",
        len(grabs) == 1 and grabs[0]["path"].endswith(f"/seasons/{number}/grab")
        and 200 <= grabs[0]["status"] < 300,
        str([(call["path"], call["status"]) for call in grabs]))
    after = await page.evaluate(FOLLOWS)
    journal.check(f"{where}: and the medium IS FOLLOWED afterwards — the act moved the "
                  "world, it did not answer a success over an unchanged one (B-378)",
                  title in after, f"status after: {after.get(title)!r}")
    said = await page.evaluate(SAID)
    journal.check(f"{where}: the sentence is the one CHOSEN for a follow begun by the act",
                  bool(chosen_for_a_follow_begun(said, number)), repr(said))
    journal.check(f"{where}: the surface pressed reads differently afterwards",
                  await page.evaluate(SURFACE_TEXT, scope) != looked_at)
    journal.check(f"{where}: tapping raises no error", not errors, str(errors))


async def main():
    journal = Journal("R158 — a season is taken from « Incomplets » by someone who does not follow the show")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", LENS_STATE)
        await page.wait_for_timeout(SETTLED)
        subjects = await page.evaluate(THE_SUBJECTS)
        journal.check(
            "the fixture holds exactly the two subjects this rule names — the only "
            "incomplete shows with a hole in their seasons data",
            set(subjects["withAHole"]) == EXPECTED_SUBJECTS,
            f"{subjects['withAHole']} of {subjects['incomplete']} incomplete shows")
        journal.check(
            "and none of the incomplete shows is followed, so every card in the lens "
            "reaches the non-follow path",
            subjects["incomplete"] > 0 and not subjects["followedAmongThem"],
            str(subjects["followedAmongThem"]))

        for title in sorted(EXPECTED_SUBJECTS):
            for surface in (PANEL, SHEET):
                await take_a_season(page, journal, errors, title, surface)

        # ── NOT ON A SHOW NOBODY OWNS ────────────────────────────────────────
        await page.evaluate("(id)=>window.__go(id)", SUGGESTION_STATE)
        await page.wait_for_timeout(SETTLED * 3)
        suggestion = await page.evaluate(COUNT_ON_THE_SHEET)
        journal.check(
            "the unowned suggestion's sheet draws season rows, so the count below "
            "reads a list and not an absence",
            suggestion["rows"] > 0, f"{suggestion['rows']} row(s)")
        journal.check(
            "and offers NO season grab on a show nobody owns — counted in the "
            "document, because its rows are closed <details> and no measurement of "
            "geometry can see a button inside one",
            suggestion["grabs"] == 0,
            f"{suggestion['grabs']} grab(s) over {suggestion['rows']} row(s): "
            f"{suggestion['labels'][:3]}")

        await page.evaluate("(id)=>window.__go(id)", OWNED_SHEET_STATE)
        await page.wait_for_timeout(SETTLED * 3)
        owned = await page.evaluate(COUNT_ON_THE_SHEET)
        journal.check(
            "while an owned show's sheet offers the act on exactly the seasons "
            "that print a shortfall",
            owned["shortfalls"] > 0 and owned["grabs"] == owned["shortfalls"],
            f"{owned['grabs']} grab(s), {owned['shortfalls']} shortfall(s) over "
            f"{owned['rows']} row(s)")

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
