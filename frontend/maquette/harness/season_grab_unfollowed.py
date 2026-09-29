"""R158 — a season with a hole is taken by someone who OWNS the show and does not follow it.

RE-AIMED: the fixture's holes and the count a season's ask answers are `window.__mocks.seasonFamily()`,
the seed the layer counts from, since the engine's season table (its copy) died.

RE-AIMED: the incomplete shows are the served answer in the query cache
(`["/api/library/incomplete"]`), since the engine's copy died.

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
other ten fall to the « no season data » note and draw no matrix and no verb
IN THE FOLLOW PANEL, which is why nobody met the defect by accident. The SHEET
draws its own catalogue, and there six of the ten DO offer the act — 21 acts,
every one answering « aucun épisode » (B-380's extent). None of the twelve is followed,
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
  3. THE WORLD MOVES, AND NO FOLLOW IS BORN: the queue holds a ONE-OFF
     acquisition of that season, asked by the account, and the medium is still
     not followed (round 10 Q2 = A). A success over an unchanged world is the
     exact defect of B-378. RE-AIMED OUT LOUD: this hold read « the medium is
     followed afterwards » — the act implied the follow until the operator
     ruled that a season of an unfollowed series is one-off, never a follow.
  4. THE SENTENCE IS THE SEASON'S OWN, with no follow in it — read from
     `fr.json`; RE-AIMED OUT LOUD from the `…NewlyFollowed` sentences, which
     retire with the follow the act no longer begins.
  5. THE SURFACE PRESSED READS DIFFERENTLY afterwards — the one the operator was
     looking at is not the only one that does not know. GIVEN BACK, said out
     loud (RULINGS 28): it was set aside for one phase while a one-off ask
     changed no fact the panel or the sheet drew; it now reads the season's row,
     which says « demandée » and offers the act no more while the one-off
     acquisition lives in the queue.
  6. (RETIRED OUT LOUD: « a second tap queues no second card » — once asked, both
     surfaces draw « Demandée » where the act was, so no finger can ask twice;
     item 5's « offers the act no more » holds it.)
  7. NO ERROR IS RAISED.

AND ONE NEGATIVE LEG, from a measurement: the sheet's season list must NOT
offer the act on a show nobody owns. `complete` is false for anything not
owned, so a gate written as `!complete` alone offered a grab on all seven
seasons of « The Venture Bros » (`mediasheet-suggestion-series`). Those rows are
CLOSED <details>: a button inside one has no box, the oracle measured no
divergence and every tier stayed green. So it is COUNTED IN THE DOCUMENT, and
beside it Silo's owned sheet is held to offer the act exactly where it prints a
shortfall, so the count of zero reads a gate and not a list that stopped
drawing.

AND A FOLLOWED SHOW THE READER HOLDS NOTHING OF, on its sheet. The same act is
offered wherever the show is looked at, so a followed show with no episode owned
is offered its seasons — and a season that has not aired yet is offered nothing,
on any show, because what has not aired is not missing. No fixture datum carries
such a follow: one added to the follows seed would redraw every state drawn over
« Suivis ». So the rule CREATES it, by a finger on « Suivre » on the show's own
sheet — the path the operator takes by hand: open a show from Découvrir, follow
it, look at its seasons. Two subjects, both suggestions nobody owns or follows,
named by no other rule and no named state:

  « Agent Elvis » — one season, aired. Once followed it is offered that season,
  the act is answered, the follow resolves a sheet (the question R156 asks), and
  the follow agrees with the answer: being acquired where the season had
  episodes to get, its status kept where it had none. RE-AIMED, and said here:
  this hold read « being acquired afterwards » whatever was answered. RE-AIMED
  AGAIN: the layer counts a season its family does not carry the way the
  season surfaces draw it, so « Agent Elvis »'s aired season has episodes to
  get and the follow is being acquired.
  « Grimsburg » — its third season airs after the page's today, read in the
  page (`window.__today()`, the clock the sheet compares with; it read the
  engine's `TODAY` through the referential until that left the engine, and was
  RE-AIMED at the clock then). Once followed its first two seasons are offered the act and the
  third is not.

WHAT IT DOES NOT READ: the QUEUED path of a one-off ask — the pipeline busy,
`seasonQueued` said.
R125 holds the queued clause on a medium already followed; this rule walks the
idle pipeline only.

THE HIT TEST IS INLINED, as it is in the other rules that tap: moving it to
`common.py` needs a rule to be pointable at a build first (B-325).

THE MESSAGE IS CLOSED, NEVER WIPED — RE-AIMED, and said here. This rule used to
empty `#toast` by hand before each walk, on the ground that no gesture dismissed
the greeting. That became false when the message took a finger (R159), and
wiping the node blinded every hold to the message on screen. Each walk now
closes it through the host's own `hide()`, waits the exit's drawn duration, and
holds it gone from paint before a finger aims at anything. The close comes
BEFORE the act; every hold on a sentence reads what the act says, after it.

RE-AIMED, said out loud: the seasons still to air and the follow's sheet were read from `sheetFor`. The engine's sheet table and
its resolvers are gone; the reads below ask `window.__addressOf` / `__sheetOf` /
`__carriedFor` — the seed the served read answers from, published by the harness
driver — and the hold count is unchanged.

RE-AIMED when the follows took the contract's names: a follow's title, kind and
status are read as `title`, `kind` and `status` (and `owned`), an incomplete
show's as `title`, where they were the engine's `t`, `k` and `st`. The holds
and what they compare are unchanged.
"""
import asyncio
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, PANEL_IN, ROOT, SETTLED, Journal, open_page, chrome_launch_args

from playwright.async_api import async_playwright

# Where the incomplete shows are drawn, as cards a finger can reach.
LENS_STATE = "lib-incomplete"
# A series nobody owns or follows, whose sheet draws season rows from the
# catalogue — the negative leg's subject.
SUGGESTION_STATE = "mediasheet-suggestion-series"
# An owned series with a hole — the negative leg's control.
OWNED_SHEET_STATE = "mediasheet-series"
# Where the two suggestions are drawn as posters a finger opens a sheet from.
DISCOVER_STATE = "discover-posters"
# A followed show nothing is owned of: every season aired, and one not yet.
ALL_AIRED = "Agent Elvis"
ONE_NOT_AIRED = "Grimsburg"

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
SEASON_KEYS = ("seasonAsked", "seasonAskedOne", "seasonAskedNone", "seasonQueued")
# The season's own mark while its one-off acquisition lives.
ASKED_MARK = json.loads(
    (ROOT / "design" / "src" / "i18n" / "fr.json").read_text(encoding="utf-8")
)["screens"]["media"]["seasonAskedOnce"]

ANSWERED = "()=>(window.__mocks?.answered?.() || [])"

FOLLOWS = """()=>Object.fromEntries((window.__followActions?.all() || []).map(
  (one) => [one.title, one.status]))"""

# WHICH INCOMPLETE SHOWS HAVE A HOLE THE MATRIX DRAWS, and which are followed —
# from the data, before a finger moves.
THE_SUBJECTS = """()=>{
  const followed = new Set((window.__followActions?.all() || []).map((one) => one.title));
  const incomplete = (window.__queries.getQueryData(["/api/library/incomplete"]) || []).map((show) => show.title);
  return {
    incomplete: incomplete.length,
    followedAmongThem: incomplete.filter((title) => followed.has(title)),
    withAHole: incomplete.filter((title) => (window.__mocks.seasonFamily()[title] || []).some(
      ([number, aired, owned]) => (owned || 0) < (aired || 0))),
  };}"""

# THE MESSAGE ON SCREEN IS CLOSED THE WAY THE INTERFACE CLOSES IT — the host's
# own `hide()` — and read gone from PAINT, not wiped from the document.
CLOSE_THE_MESSAGE = "()=>window.__toast?.hide?.()"
MESSAGE_GONE = """()=>{
  const host = document.querySelector('#toast');
  if (!host) return {gone: true};
  const style = getComputedStyle(host);
  const held = window.__toast?.read?.();
  return {gone: !(held && held.shown)
            && (style.visibility === 'hidden' || Number(style.opacity) === 0),
          shown: !!(held && held.shown), visibility: style.visibility,
          opacity: style.opacity};}"""
# The exit's drawn duration — the fade and the visibility step behind it,
# 400 ms — and a frame.
MESSAGE_EXIT = 450


async def close_the_message(page, journal, where):
    """Closes the message on screen through its host, and holds it gone from paint.

    Args:
        page: The page.
        journal: Where the holds are recorded.
        where: The walk, for the hold's own text.
    """
    await page.evaluate(CLOSE_THE_MESSAGE)
    await page.wait_for_timeout(MESSAGE_EXIT)
    gone = await page.evaluate(MESSAGE_GONE)
    journal.check(f"{where}: the message on screen is closed by its host and gone from paint "
                  "before a finger aims at anything",
                  gone["gone"], str(gone))

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

# ANY ELEMENT CARRYING AN ATTRIBUTE WITH A VALUE, aimed at like `AIM`.
AIM_BY_ATTRIBUTE = """([attribute, value])=>{
  const target = [...document.querySelectorAll(`[${attribute}]`)].find(
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

# EVERY SEASON ROW ON THE SHEET: its number (the summary's first figure), and
# whether it offers the act.
ROWS_ON_THE_SHEET = """()=>{
  const root = document.querySelector('[data-region="screen-media/body"]');
  return root ? [...root.querySelectorAll('[data-part="season"]')].map((row) => {
    const figure = ((row.querySelector("summary") || {}).textContent || "").match(/\\d+/);
    const act = row.querySelector('[data-part="season/grab"]');
    return {season: figure ? Number(figure[0]) : null, offered: !!act,
            value: act ? act.dataset.grabSeason || "" : ""};
  }) : [];}"""

# THE SUMMARY OF THE ROW WHOSE ACT CARRIES A VALUE — a row of a show the reader
# does not own is drawn CLOSED, and a button inside a closed row has no box, so
# the finger opens the row first, the way the operator does.
AIM_AT_THE_ROW_OF = """(value)=>{
  const act = document.querySelector(`[data-grab-season="${CSS.escape(value)}"]`);
  const row = act && act.closest('[data-part="season"]');
  const summary = row && row.querySelector("summary");
  if (!summary) return {found: false};
  summary.scrollIntoView({block: "center"});
  const box = summary.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, open: row.open,
          reachable: !!hit && (hit === summary || summary.contains(hit))};}"""

# WHICH OF THE SHOW'S SEASONS AIR AFTER TODAY, from the clock the sheet reads.
NOT_YET_AIRED = """(title)=>{
  const sheet = window.__sheetOf(title);
  const today = window.__today ? window.__today() : null;
  return {today: today || null, resolved: !!sheet,
          later: ((sheet && sheet.seasons) || []).filter(
            (season) => today && season.airDate && season.airDate > today).map((season) => season.number)};}"""

# HOW MANY EPISODES A SEASON HAS TO GET — the count the layer answers from: the
# season family's row, and for a season that family does not carry, the row as
# the season surfaces draw it (aired, less held). RE-AIMED OUT LOUD: a season
# the family did not carry used to count nothing, so « Agent Elvis », followed
# with nothing held, was answered « aucun épisode » over ten aired ones.
MISSING_IN_SEASON = """([title, season])=>{
  const counted = (window.__mocks.seasonFamily()[title] || []).find(([number]) => number === season);
  const drawn = (window.__mocks.seasons()[title] || []).find(([number]) => number === season);
  const row = counted || drawn;
  return row ? Math.max(0, (row[1] || 0) - (row[2] || 0)) : 0;}"""

SAID = """()=>{
  const held = window.__toast?.read?.();
  return held && held.message ? held.message.message || '' : '';}"""

# A one-off acquisition of one season, in the queue as the layer answers it.
ONE_OFF = """async ({ title, season }) => {
  const worlds = await Promise.all(['', '?scenario=loaded'].map(async (query) =>
    (await fetch('/api/acquisition/to-handle' + query)).json()));
  const episode = 'S' + String(season).padStart(2, '0');
  return worlds.some((answer) => Object.values(answer).flat().some((card) => card && card.title === title
    && card.requester?.via === 'request' && card.secondaryLine.startsWith(episode)));
}"""

SURFACE_TEXT = "(scope)=>(document.querySelector(scope)?.textContent || '')"

# THE SHORTFALL THE SEASON'S ROW DRAWS before the ask — « n manquants » — the
# count the answer's sentence must agree with.
ROW_MISSING = """([scope, key])=>{
  const act = document.querySelector(scope)?.querySelector(`[data-grab-season="${CSS.escape(key)}"]`);
  const shortfall = act?.closest('[data-part="season"]')?.querySelector('[data-part="season/missing"]');
  return shortfall ? parseInt(shortfall.textContent, 10) : null;}"""


def said_count(said, key):
    """Reads the episode count a season's sentence states.

    Args:
        said: The sentence.
        key: Its key, as `the_seasons_own` matched it.

    Returns:
        The count, 0 for « aucun », 1 for the singular sentence.
    """
    if key == "seasonAskedNone":
        return 0
    if key == "seasonAskedOne":
        return 1
    found = re.search(r"(\d+) épisodes", said)  # french-ok: the sentence the interface renders
    return int(found.group(1)) if found else None

# THE SEASON'S ROW after the ask: its mark, and whether it still offers the act.
SEASON_ROW = """([scope, key])=>{
  const surface = document.querySelector(scope);
  const mark = surface?.querySelector(`[data-asked-season="${CSS.escape(key)}"]`);
  return {mark: mark ? mark.textContent.trim() : null,
          act: !!surface?.querySelector(`[data-grab-season="${CSS.escape(key)}"]`)};}"""


def the_seasons_own(said, season, title):
    """Says whether a message is one of the season's own sentences.

    Args:
        said: What the interface said.
        season: The season the act was for.
        title: The show the sentence names.

    Returns:
        The matching key, or an empty string.
    """
    for key in SEASON_KEYS:
        pieces = re.split(r"(\{\{season\}\}|\{\{count\}\}|\{\{title\}\})", SENTENCES[key])
        pattern = "".join(
            re.escape(str(season)) if piece == "{{season}}"
            else r"\d+" if piece == "{{count}}"
            else re.escape(title) if piece == "{{title}}"
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
    await close_the_message(page, journal, where)
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
    row_missing = await page.evaluate(ROW_MISSING, [scope, season["value"]])
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
    one_off = await page.evaluate(ONE_OFF, {"title": title, "season": int(number)})
    journal.check(f"{where}: the act moved the world — a one-off acquisition of that season is "
                  "queued, asked by the account (B-378)", one_off, f"queued: {one_off}")
    journal.check(f"{where}: and NO follow is born of it (round 10 Q2)",
                  title not in after, f"status after: {after.get(title)!r}")
    said = await page.evaluate(SAID)
    journal.check(f"{where}: the sentence is the season's own, with no follow in it",
                  bool(the_seasons_own(said, number, title)), repr(said))
    journal.check(f"{where}: its count is the shortfall the season's row drew",
                  row_missing is not None and said_count(said, the_seasons_own(said, number, title)) == row_missing,
                  f"row « {row_missing} manquants », said {said!r}")
    journal.check(f"{where}: the surface pressed reads differently afterwards",
                  await page.evaluate(SURFACE_TEXT, scope) != looked_at)
    row = await page.evaluate(SEASON_ROW, [scope, season["value"]])
    journal.check(f"{where}: the season's row says « {ASKED_MARK} » and offers the act no more",
                  row["mark"] == ASKED_MARK and not row["act"], str(row))
    # RETIRED OUT LOUD: « a second tap queues no second card ». Once the season
    # is asked, BOTH surfaces draw « Demandée » in the act's place (the hold
    # above reads it here; the other surface derives the same mark from the
    # same queue), so a second tap lands on the mark and no finger can ask
    # twice. The hold read nothing any more: the layer's own dedupe is not
    # reachable by a hand, and « offers the act no more » is what holds it.
    journal.check(f"{where}: tapping raises no error", not errors, str(errors))


async def follow_from_its_sheet(page, journal, errors, title):
    """Opens a suggestion's sheet from Découvrir and follows it by finger.

    Args:
        page: The page.
        journal: Where the holds are recorded.
        errors: The page errors collected so far.
        title: The suggestion.

    Returns:
        Whether the show is followed and its sheet is open.
    """
    await page.evaluate("(id)=>window.__go(id)", DISCOVER_STATE)
    await page.wait_for_timeout(SETTLED)
    await close_the_message(page, journal, f"« {title} »")
    before = await page.evaluate(FOLLOWS)
    journal.check(f"« {title} »: nobody follows it before the finger does", title not in before,
                  f"status before: {before.get(title)!r}")
    poster = await page.evaluate(AIM_BY_ATTRIBUTE, ["data-mediasheet", title])
    journal.check(f"« {title} »: a finger reaches its poster on Découvrir",
                  poster["found"] and poster["reachable"], str(poster))
    if not (poster["found"] and poster["reachable"]):
        return False
    await page.touchscreen.tap(poster["x"], poster["y"])
    await page.wait_for_timeout(SETTLED * 3)
    follow = await page.evaluate(AIM_BY_ATTRIBUTE, ["data-follow", title])
    journal.check(f"« {title} »: its sheet offers « Suivre » to a finger",
                  follow["found"] and follow["reachable"], str(follow))
    if not (follow["found"] and follow["reachable"]):
        return False
    errors.clear()
    await page.touchscreen.tap(follow["x"], follow["y"])
    await page.wait_for_timeout(ACTED)
    after = await page.evaluate(FOLLOWS)
    resolved = await page.evaluate("(t)=>window.__sheetOf(t) != null", title)
    journal.check(f"« {title} »: followed afterwards, and the follow resolves a sheet — "
                  "never a sheetless follow (R156's question)",
                  title in after and resolved, f"status {after.get(title)!r}, sheet {resolved}")
    return title in after


async def main():
    journal = Journal("R158 — a season is taken from « Incomplets » by someone who does not follow the show")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
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

        # ── A FOLLOWED SHOW THE READER HOLDS NOTHING OF ──────────────────────
        if await follow_from_its_sheet(page, journal, errors, ALL_AIRED):
            rows = await page.evaluate(ROWS_ON_THE_SHEET)
            offered = [row for row in rows if row["offered"]]
            journal.check(f"« {ALL_AIRED} », followed and not owned, is offered its aired seasons",
                          bool(rows) and len(offered) == len(rows), str(rows))
            if offered:
                value = offered[0]["value"]
                number = value.split("|")[-1]
                row = await page.evaluate(AIM_AT_THE_ROW_OF, value)
                if row.get("found") and row.get("reachable") and not row.get("open"):
                    await page.touchscreen.tap(row["x"], row["y"])
                    await page.wait_for_timeout(SETTLED)
                act = await page.evaluate(AIM, ["season/grab", "data-grab-season", value])
                journal.check(f"« {ALL_AIRED} »: a finger opens season {number}'s row and reaches its act",
                              act["found"] and act["reachable"], f"row {row} act {act}")
                missing = await page.evaluate(MISSING_IN_SEASON, [ALL_AIRED, int(number)])
                # THE STATUS BEFORE IS THE LAYER'S, re-read rather than taken from the
                # cache « Suivre » just wrote into: that cache holds the follow as
                # the interface drew it at the press, and the refetch the act causes
                # would read as the act having moved it.
                await page.evaluate("""()=>window.__queries.refetchQueries(
                  {queryKey: ["/api/acquisition/followed"]})""")
                await page.wait_for_timeout(SETTLED)
                status_before = (await page.evaluate(FOLLOWS)).get(ALL_AIRED)
                mark = len(await page.evaluate(ANSWERED))
                errors.clear()
                if act["found"] and act["reachable"]:
                    await page.touchscreen.tap(act["x"], act["y"])
                    await page.wait_for_timeout(ACTED)
                grabs = [call for call in (await page.evaluate(ANSWERED))[mark:]
                         if call["operationId"] == GRAB_OPERATION]
                journal.check(f"« {ALL_AIRED} »: a finger takes season {number} and the season grab "
                              "is called once for it, answered as a success",
                              len(grabs) == 1 and grabs[0]["path"].endswith(f"/seasons/{number}/grab")
                              and 200 <= grabs[0]["status"] < 300,
                              str([(call["path"], call["status"]) for call in grabs]))
                status = (await page.evaluate(FOLLOWS)).get(ALL_AIRED)
                # THE FOLLOW AGREES WITH WHAT WAS ANSWERED: being acquired only when
                # the season had something to get, its status kept over an answer of
                # nothing. RE-AIMED with R160's hold 3, said in the docstring.
                if missing:
                    journal.check(f"« {ALL_AIRED} »: and it is being acquired afterwards — the season "
                                  f"had {missing} episode(s) to get — with no error",
                                  status == "acquiring" and not errors, f"{status!r} {errors}")
                else:
                    journal.check(f"« {ALL_AIRED} »: and it KEEPS its status — the answer had nothing "
                                  "to get — with no error",
                                  status == status_before and not errors,
                                  f"{status_before!r} → {status!r} {errors}")
                # AND THE SENTENCE ANSWERED: the follow existed before the act (a
                # finger on « Suivre »), so it is the plain asked sentence, named,
                # at the count the seasons data holds — never « Série … suivie ».
                said = await page.evaluate(SAID)
                key = ("seasonAskedNone" if missing == 0
                       else "seasonAskedOne" if missing == 1 else "seasonAsked")
                expected = (SENTENCES[key].replace("{{season}}", number)
                            .replace("{{count}}", str(missing)).replace("{{title}}", ALL_AIRED))
                journal.check(f"« {ALL_AIRED} »: the sentence answered is `{key}`, naming the show",
                              said == expected, f"{said!r} against {expected!r}")

        if await follow_from_its_sheet(page, journal, errors, ONE_NOT_AIRED):
            later = await page.evaluate(NOT_YET_AIRED, ONE_NOT_AIRED)
            journal.check(f"« {ONE_NOT_AIRED} » has a season that airs after the page's "
                          "today, read in the page, so the leg below reads a clause",
                          bool(later["later"]), str(later))
            rows = await page.evaluate(ROWS_ON_THE_SHEET)
            unaired = [row for row in rows if row["season"] in later["later"]]
            aired = [row for row in rows if row["season"] not in later["later"]]
            journal.check(f"« {ONE_NOT_AIRED} »: a season not yet aired is offered NO act — what has "
                          "not aired is not missing",
                          bool(unaired) and not any(row["offered"] for row in unaired), str(unaired))
            journal.check(f"« {ONE_NOT_AIRED} »: while its aired seasons are offered it",
                          bool(aired) and all(row["offered"] for row in aired), str(aired))

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


if __name__ == "__main__":
    asyncio.run(main())
