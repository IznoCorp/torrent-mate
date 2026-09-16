"""R201 — a refused follow is said refused, and the sheet's act carries an identity.

WHAT THIS EXISTS FOR, and it is the other half of R200. R200 asks the LAYER a
question and reads the layer's answer: four requests and no interface at all. So
the refusal it brought into being — a create the layer cannot identify is a 400
— had no reader anywhere. Walked by a finger, that refusal was answered with the
sentence of a success: « … ajouté à vos suivis », the row wearing « ✓ Suivi »,
the local list rolling back three seconds later with nothing said. §2 and §13 —
the interface says what is really true of the machine — and §7/§8 — nothing is
destroyed in silence.

AND THE ACT THAT REACHES THE REFUSAL FIRST IS THE SHEET'S. A search result and a
suggestion both carry their medium's identifiers; the media sheet's own
« Suivre » carried the title and the KIND and nothing else, so its create was
recorded only because the layer joins by title. The join is a FALLBACK, not an
identity: the day it misses — a real server, a wider seed — the sheet's act is
the one the layer cannot identify.

  h1. THE SUBJECT IS ONE THE LAYER CANNOT JOIN, proved by a create carrying its
      title alone: without that, everything below passes over the join.
  h2. THE SHEET'S ACT CARRIES THE MEDIUM'S IDENTITY: the layer records the
      follow, with identifiers, although no list it serves carries the title.
  h3. A REFUSED CREATE IS SAID REFUSED: the message is the refusal's own, and
      never the one a success says.
  h4. AND NO ROW WEARS THE DONE WORD after it.
  h5. AND THE TWO ENDS AGREE: the local list holds what the layer holds.

WHAT IT DOES NOT READ. The HELD outcome — a mutation the outbox keeps because
nothing answered — is NOT a refusal, and this rule never drives it: R107 holds
that path, and a held act keeps the message it has always said. Nothing here
reads a network trace either: the mock layer intercepts `fetch` INSIDE the page,
so a Playwright response listener sees nothing at all on these addresses, and
what left is read in the layer's own register.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, ROOT, SETTLED, Journal, open_page

from playwright.async_api import async_playwright

# A state that re-seeds the layer, driven before anything is armed: a named
# state RESETS the scenario, so an outcome set before one is an outcome nothing
# applies.
START_STATE = "acq-follows-list"

# THE SUBJECT OF THE SHEET'S ACT, chosen for what the layer CANNOT do with it:
# `mocks/seeds/media-sheets.json` holds it, unowned and identified, and neither
# `search-results.json` nor `suggestions.json` carries the title — so the create's
# title-join finds nothing and the only identity that can reach the layer is the
# one the act sends. french-ok: a media title, which is data.
SHEET_SUBJECT = "Conclave"
SHEET_IDENTITY = {"tmdb": 974576, "imdb": "tt20215234"}

# The query the add screen is opened on, and the kind word the seed gives the
# row acted on there. french-ok: a query and a data value the seeds carry.
QUERY = "star wars"
SERIES_WORD = "Série"

SENTENCES = json.loads(
    (ROOT / "design" / "src" / "i18n" / "fr.json").read_text(encoding="utf-8")
)["verbs"]["follows"]

# THE REFUSAL'S OWN SENTENCE, or None while the resource has none — read
# rather than spelled here, and absent is a FAILURE with a name rather than a
# rule that cannot run.
REFUSED = SENTENCES.get("refused")

# What a SUCCESS says, in the words that make it recognisable: the verb a film
# takes and the verb a series takes, each read from the resource.
SUCCESS_WORDS = [SENTENCES["added"].split(" » ")[-1].split(" —")[0],
                 SENTENCES["followed"].split(" » ")[-1].split(" —")[0]]

CREATE = """async(body)=>{
  const answer = await fetch("/api/acquisition/followed", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)});
  let payload = null;
  try { payload = await answer.json(); } catch (nothing) { payload = null; }
  return {status: answer.status, payload};
}"""

FOLLOWS = """async()=>{
  const answer = await fetch("/api/acquisition/followed");
  const body = await answer.json();
  const rows = Array.isArray(body) ? body : (body.items ?? body.follows ?? []);
  return rows.map((row) => ({title: row.title, ids: row.ids}));
}"""

SAID = """()=>{const held = window.__toast?.read?.();
  return held && held.message ? (held.message.message || "") : "";}"""

LOCAL = "()=>(window.__followActions?.all() || []).map((one) => one.title)"

# The rows of the add screen's listing, each with the done chip it wears and the
# kind its own subtitle says — the reading `add_footer.py` takes of the same
# cards, asked of every row at once.
ROWS = """()=>[...document.querySelectorAll(
    '[data-part="result/list"] [data-part="card/body"][data-panel^="add:"]')]
  .map((body) => ({
    panel: body.dataset.panel,
    title: (body.querySelector('[data-part="card/title"]') || {}).title || null,
    kind: ((body.querySelector('[data-part="card/subtitle"]') || {}).textContent || "")
      .split(" · ").find((word) => word === "Film" || word === "Série") || null,
    chip: body.querySelector('[data-part="chip"]')
      ? body.querySelector('[data-part="chip"]').textContent.trim() : null,
  }))"""


async def tap_part(page, part):
    """Scrolls a `data-part` into view, hit-tests its centre and taps it.

    The sheet's follow button sits far below the fold, and a hit test taken
    without scrolling answers null — which reads exactly like a covered button
    and is only a rectangle nobody brought on screen. `follow_verb.py` pays the
    same price for the same element and says so there.

    Args:
        page: The page.
        part: The `data-part` value.

    Returns:
        What was aimed at, and whether the tap happened.
    """
    await page.evaluate("""(part)=>{
        document.querySelector('[data-part="' + part + '"]')
          ?.scrollIntoView({block: "center"});}""", part)
    await page.wait_for_timeout(SETTLED)
    aim = await page.evaluate("""(part)=>{
        const one = document.querySelector('[data-part="' + part + '"]');
        if (!one) return {found: false};
        const box = one.getBoundingClientRect();
        const x = box.left + box.width / 2;
        const y = box.top + box.height / 2;
        const hit = document.elementFromPoint(x, y);
        return {found: true, x, y,
                reachable: !!hit && (hit === one || one.contains(hit))};}""", part)
    if aim.get("found") and aim.get("reachable"):
        await page.touchscreen.tap(aim["x"], aim["y"])
        aim["tapped"] = True
    else:
        aim["tapped"] = False
    return aim


async def the_sheet_carries_an_identity(page, journal):
    """Follows an unjoinable medium from its own sheet and reads the register.

    Args:
        page: The page, on a state that has re-seeded the layer.
        journal: Where the holds are recorded.
    """
    alone = await page.evaluate(CREATE, {"title": SHEET_SUBJECT, "kind": "movie"})
    journal.check(
        "the subject's title is one the layer cannot join — without it, the "
        "hold below passes over the join instead of over the act",
        alone["status"] == 400,
        f"a create carrying the title alone answered {alone['status']}")

    before = await page.evaluate(FOLLOWS)
    await page.evaluate(
        "(subject)=>window.__screens.mediaSheet(subject.title, subject.carried)",
        {"title": SHEET_SUBJECT,
         # THE ENTRY'S CARRIED IDENTITY IS THE ADDRESS AND NOTHING ELSE: the
         # sheet is addressed by provider id, and no landed list holds this
         # title, so the walk supplies what a tap would have supplied. What the
         # BUTTON sends is the sheet's own read, which is what is held here.
         "carried": {"title": SHEET_SUBJECT, "poster": None, "ids": SHEET_IDENTITY}})
    await page.wait_for_timeout(SETTLED * 3)
    aim = await tap_part(page, "media/add")
    journal.check("the unowned medium's sheet offers the act, on a button a "
                  "finger reaches", aim.get("tapped"), str(aim))
    await page.wait_for_timeout(ACTED)

    after = await page.evaluate(FOLLOWS)
    recorded = next((row for row in after if row["title"] == SHEET_SUBJECT), None)
    journal.check(
        "and the sheet's act carries the medium's identity — the layer records "
        "the follow although it can join the title to nothing",
        recorded is not None and bool(recorded["ids"]),
        f"{len(before)} → {len(after)} follow(s); recorded {recorded}")


async def a_refusal_is_drawn(page, journal):
    """Takes a refused act by finger on the add screen and reads what is said.

    Args:
        page: The page.
        journal: Where the holds are recorded.
    """
    await page.evaluate("()=>window.__mocks.reset()")
    await page.evaluate("(query)=>window.__screens.add(query)", QUERY)
    await page.wait_for_selector('[data-part="result/list"]')
    await page.wait_for_timeout(ACTED)
    await page.evaluate("()=>window.__toast?.hide?.()")

    # ARMED HERE AND NOWHERE EARLIER, and proved armed: `window.__go` re-seeds
    # the scenario, so an outcome set before a named state is an outcome that
    # was thrown away — the trap this lot paid twice.
    await page.evaluate(
        """()=>window.__mocks.setOperationOutcome("createFollow", {status: 400})""")
    probe = await page.evaluate(
        CREATE, {"title": "probe", "kind": "movie", "provider": "tmdb", "providerId": 1})
    journal.check("the refusal is armed — a probe create is answered with it",
                  probe["status"] == 400, f"answered {probe['status']}")

    rows = await page.evaluate(ROWS)
    free = next((row for row in rows
                 if row["chip"] is None and row["kind"] == SERIES_WORD), None)
    journal.check(
        "the listing offers a series nothing has acted on — the subject of the "
        "three holds below",
        free is not None, f"{len(rows)} row(s): {rows}")
    if free is None:
        return

    served_before = await page.evaluate(FOLLOWS)
    await page.click(f'[data-part="result/list"] [data-panel="{free["panel"]}"]')
    await page.wait_for_timeout(SETTLED)
    # THE ACT'S POSITION IS READ OUT FIRST, never composed inside the selector:
    # a placeholder carrying a dotted call reads to `check-markup-contracts.py`
    # as a class token in a selector held in a variable, which is the one thing
    # that arm refuses.
    position = free["panel"].removeprefix("add:")
    act = f'[data-add="{position}"]'
    await page.wait_for_selector(act)
    await page.locator(act).click()
    # THE ANSWER IS WAITED FOR, and then the rollback behind it: the local list
    # is written before the request leaves, and what this rule reads is the
    # state the operator is left in, not the one he sees for a frame.
    await page.wait_for_timeout(ACTED + SETTLED)

    said = await page.evaluate(SAID)
    expected = None if REFUSED is None else REFUSED.replace("{{title}}", free["title"])
    journal.check(
        "a refused create is SAID refused — the message is the refusal's own, "
        "from the interface's resource",
        expected is not None and said == expected,
        f"said {said!r}, expected {expected!r}")
    journal.check(
        "and it is never the sentence a success says",
        all(words not in said for words in SUCCESS_WORDS),
        f"said {said!r}, a success would have said {SUCCESS_WORDS}")

    after_rows = await page.evaluate(ROWS)
    wearing = [row for row in after_rows if row["chip"]]
    journal.check(
        "and no row wears the done word over an act the layer refused",
        not any(row["panel"] == free["panel"] for row in wearing),
        f"{[(row['panel'], row['chip']) for row in after_rows]}")

    local = await page.evaluate(LOCAL)
    served_after = await page.evaluate(FOLLOWS)
    journal.check(
        "and the two ends agree — the local list holds what the layer holds",
        sorted(local) == sorted(row["title"] for row in served_after),
        f"{len(served_before)} served before, {len(served_after)} after; "
        f"{len(local)} held locally")


async def main():
    """Walks the sheet's act, then a refused act, and reads what is drawn."""
    journal = Journal("R201 — a refused follow is said refused, and the sheet's "
                      "act carries an identity")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", START_STATE)
        await page.wait_for_timeout(SETTLED)
        await the_sheet_carries_an_identity(page, journal)
        await a_refusal_is_drawn(page, journal)

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
