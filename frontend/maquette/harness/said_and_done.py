"""R171 — the verbs that SAID a sentence now send one, and move what they answer about (B-383).

THE DEFECT. Three buttons answered a canned sentence over an unchanged world:
« Re-scraper les métadonnées » on the follow panel, the SAME words on the media
sheet, and « Lancer »/« Lancer à blanc » on a maintenance command's panel. The
first two were drawn as `data-rescrape` (read by the dying engine, which showed
a message and returned) and `data-toast`; the third as `target: { toast }`. All
three are NE-DOIT-PAS-1 — a sentence that can be right about nothing.

WHAT THIS RULE READS, AND WHAT IT REFUSES TO READ. The NETWORK
(`window.__mocks.answered()` — the seam replaces `fetch`, so the browser's own
request events never fire for a mocked call) and the STATE the answer is about.
Never the message: a screen-reading hold passes over a build that draws the
right thing and sends nothing, which is precisely what these three did for a
whole wave under a green gate.

  m1. THE SHEET'S « Métadonnées rafraîchies » ROW IS A FACT NOBODY SERVED.
      Before the act it shows the constant. A finger on the sheet's own
      « Re-scraper les métadonnées » sends `rescrapeMedia` — with the 202 its
      contract declares, which is R170's repair read from the other end — the
      layer's next answer carries a `metadataRefreshedAt` that was null, and the
      row on screen has moved with it. Four holds, because a call that leaves
      and a state that moves and a surface that redraws are three different
      failures.
  m2. THE FOLLOW PANEL'S TWIN SENDS THE SAME OPERATION. Same words, another
      surface, one verb — the panel's action is taken by a finger and the call
      is read the same way.
  m3. NOTHING ANSWERS `data-rescrape` TWICE. The engine's branch is deleted and
      the registry's is the only reader left. A name answered on both sides acts
      twice, and it is a defect a rule can read rather than an arbitration
      (`lib/verbs.ts` says so in its own header).
  m4. A MAINTENANCE COMMAND RUNS, AND THE STATE MOVES. A finger on « Lancer »
      for a command that is not blank: `runMaintenanceAction` is answered, and
      the layer's pipeline state — `idle` before — is no longer idle after.
  m5. A BLANK RUN IS A CALL THAT LEAVES BESIDE A STATE THAT DOES NOT MOVE, and
      that is the whole of what « à blanc » means. The destructive command's
      panel offers « Lancer à blanc »; the finger sends, and the state is still
      `idle` afterwards. A rule holding only m4 would be green over a blank run
      that had quietly started the machine, which is the worse of the two
      defects.

HOW THE LAYER'S PIPELINE STATE IS READ, since no GET answers it. By asking for a
BLANK run and reading the `state` it answers: a dry run changes nothing by
contract, so it is a probe rather than an act. Every probe is taken after the
calls under test have been counted, so it cannot be mistaken for one of them.

WHAT IT DOES NOT READ. The sentences themselves — they are `fr.json`'s and
`check-no-french.py`'s. Nor what a real backend would do with any of the three
asks: the contract declares what the interface requires (D7), and
`rescrapeMedia` is a demand on the register rather than an operation anyone has
built.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, PANEL_IN, SETTLED, Journal, open_page

from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENGINE = ROOT / "design" / "src" / "engine" / "legacy.js"

# THE SHEET OF AN OWNED SERIES, where the re-scrape act is drawn.
SHEET_STATE = "mediasheet-series"

# THE FOLLOW LIST, whose panel carries the same words for a medium in the
# library — and the medium, named, because the verb is drawn only for a follow
# the library HOLDS and the list carries follows that it does not.
# « Dark Matter » is the ONE follow the library holds under the same title —
# measured, not chosen: `inLibrary` matches `window.LIBRARY` on an exact title,
# and of the fourteen follows it is the only one that does (B-383's own reading
# named three, which was read on another scenario). A row that stops being
# there fails this hold with `found False` rather than measuring another
# medium in silence.
FOLLOWS_STATE = "acq-follows-list"
FOLLOWED_IN_LIBRARY = "Dark Matter"

# A MAINTENANCE COMMAND'S PANEL. The first is destructive, so it is ALWAYS
# blank whatever the page's switch says; the second offers no blank run at all,
# so its button is the real one.
BLANK_COMMAND = "library-clean"
REAL_COMMAND = "library-status"

# The command the probe asks for. It is asked BLANK, so it reads the layer's
# pipeline state without moving it.
PROBE_COMMAND = REAL_COMMAND

# What the layer's pipeline reads as when nothing is running.
IDLE = "idle"

# EVERY CALL THE LAYER ANSWERED FOR ONE OPERATION, as `{status, path}` pairs.
CALLS = """(operationId) => (window.__mocks?.answered() || [])
  .filter((call) => call.operationId === operationId)
  .map((call) => ({status: call.status, path: decodeURIComponent(call.path)}))"""

# WHAT ONE `data-rescrape` ACT NAMES. Read as a VALUE and not only as a
# presence, and that is not decoration: the value IS the subject the act is
# about, and an attribute nothing ever compares is classed a boolean STATE by
# `scripts/markup_states.py` — which then refuses the markup that writes it,
# correctly, because React renders a false boolean as the string "false" and a
# presence selector would match it for ever.
RESCRAPE_SUBJECT = """(selector) => {
  const one = document.querySelector(selector);
  return one === null ? null : one.dataset.rescrape ?? null;
}"""

# THE ROW THE SHEET DRAWS THE REFRESH INSTANT IN.
REFRESHED_ROW = """() => {
  const row = document.querySelector('[data-part="media/refreshed"]');
  return row === null ? null : (row.textContent || '').trim();
}"""

# WHAT THE LAYER ANSWERS FOR ONE SHEET, asked directly: the surface shows a
# formatted date and the layer holds an instant, and a rule that read only the
# surface could not tell a moved state from a re-rendered constant.
SHEET_FIELD = """async ([provider, identifier]) => {
  const answer = await fetch(`/api/media/${provider}/${identifier}`);
  const sheet = await answer.json();
  return sheet === null ? null : sheet.metadataRefreshedAt ?? null;
}"""

# THE LAYER'S PIPELINE STATE, read through a BLANK run — which changes nothing
# by contract, and is therefore a probe and not an act.
PIPELINE_STATE = """async (command) => {
  const answer = await fetch(`/api/maintenance/actions/${command}/run`, {
    method: 'POST',
    headers: {'content-type': 'application/json'},
    body: JSON.stringify({dryRun: true}),
  });
  const outcome = await answer.json();
  return outcome === null ? null : outcome.state;
}"""

# ONE ELEMENT FOUND BY SELECTOR AND A WORD OF ITS LABEL, brought to the middle
# of the screen as a hand would, then aimed at.
AIM = """([selector, word]) => {
  const one = [...document.querySelectorAll(selector)]
    .find((element) => !word || (element.textContent || '').includes(word));
  if (!one) return {found: false};
  one.scrollIntoView({block: 'center'});
  const box = one.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, label: (one.textContent || '').trim(),
          reachable: !!hit && (hit === one || one.contains(hit)),
          covering: hit === null ? 'nothing' : hit.tagName};
}"""


async def tap(page, selector, word=""):
    """Taps what a selector finds, by a finger at its own centre.

    Args:
        page: The page.
        selector: Where to look.
        word: A word its label carries, when the selector finds several.

    Returns:
        What the aim read, with `tapped` saying whether a finger went down.
    """
    await page.evaluate(AIM, [selector, word])
    await page.wait_for_timeout(SETTLED)
    aim = await page.evaluate(AIM, [selector, word])
    aim["tapped"] = bool(aim.get("found") and aim.get("reachable"))
    if aim["tapped"]:
        await page.touchscreen.tap(aim["x"], aim["y"])
        await page.wait_for_timeout(ACTED)
    return aim


async def drive(page, state):
    """Drives one named state and lets it settle."""
    await page.evaluate("(id)=>window.__go(id)", state)
    await page.wait_for_timeout(SETTLED)


async def sheet_rescrape_sends(page, journal):
    """m1 — the sheet's own act sends, the layer moves, the row redraws."""
    await page.evaluate("() => window.__mocks.reset()")
    await drive(page, SHEET_STATE)
    before_row = await page.evaluate(REFRESHED_ROW)
    # SILO'S IDENTITY, taken from the address the state navigated to rather than
    # written down here: a rule carrying its own copy of an identifier is a rule
    # that goes on measuring the wrong medium after a fixture moves.
    address = await page.evaluate("() => window.location.pathname")
    parts = address.strip("/").split("/")
    identity = parts[-2:] if len(parts) >= 3 else ["", ""]
    before_field = await page.evaluate(SHEET_FIELD, identity)

    subject = await page.evaluate(
        RESCRAPE_SUBJECT, '[data-part="sheet/action"][data-rescrape]')
    aim = await tap(page, '[data-part="sheet/action"][data-rescrape]')
    calls = await page.evaluate(CALLS, "rescrapeMedia")
    after_field = await page.evaluate(SHEET_FIELD, identity)
    await page.wait_for_timeout(ACTED)
    after_row = await page.evaluate(REFRESHED_ROW)

    journal.check("the sheet's re-scrape is under the finger", aim["tapped"],
                  f"found {aim.get('found')}, covered by {aim.get('covering')}")
    journal.check(
        "and it NAMES the medium it is about",
        subject is not None and subject != "",
        f"data-rescrape={subject!r} — an act with no subject asks about nothing",
    )
    journal.check(
        "and it SENDS, with the 202 the contract declares",
        len(calls) == 1 and calls[0]["status"] == 202,
        f"{calls} — a verb that said a sentence and sent nothing is the defect",
    )
    journal.check(
        "the layer held no refresh instant before the act, and holds one after",
        before_field is None and after_field is not None,
        f"before {before_field!r}, after {after_field!r}",
    )
    journal.check(
        "and the sheet's row moved with it",
        before_row is not None and after_row is not None and after_row != before_row,
        f"{before_row!r} → {after_row!r}",
    )


async def follow_panel_twin_sends(page, journal):
    """m2 — the follow panel's twin calls the same operation."""
    await page.evaluate("() => window.__mocks.reset()")
    await drive(page, FOLLOWS_STATE)
    raised = await tap(page, f'[data-panel="media:{FOLLOWED_IN_LIBRARY}"]')
    await page.wait_for_timeout(PANEL_IN)
    subject = await page.evaluate(RESCRAPE_SUBJECT, "[data-rescrape]")
    aim = await tap(page, f'[data-rescrape="{FOLLOWED_IN_LIBRARY}"]')
    calls = await page.evaluate(CALLS, "rescrapeMedia")
    journal.check("a follow's panel is raised by a finger", raised["tapped"],
                  f"found {raised.get('found')}")
    journal.check("its « Re-scraper les métadonnées » is under the finger",
                  aim["tapped"], f"found {aim.get('found')}, {aim.get('label')!r}")
    journal.check(
        "and the act names the follow, not the panel it is drawn on",
        subject == FOLLOWED_IN_LIBRARY,
        f"data-rescrape={subject!r}, expected {FOLLOWED_IN_LIBRARY!r}",
    )
    journal.check(
        "and it sends the same operation the sheet's does",
        len(calls) == 1 and calls[0]["status"] == 202,
        f"{calls}",
    )


def engine_answers_rescrape():
    """Whether the dying engine still has a branch for `data-rescrape`."""
    return "dataset.rescrape" in ENGINE.read_text(encoding="utf-8")


async def one_reader_only(page, journal):
    """m3 — the registry answers `data-rescrape`, and the engine no longer does."""
    registered = await page.evaluate("() => window.__verbNames?.() || []")
    journal.check(
        "the verb registry answers `rescrape`",
        "rescrape" in registered,
        f"registered: {sorted(registered)}",
    )
    journal.check(
        "and the dying engine no longer does — a name answered twice acts twice",
        not engine_answers_rescrape(),
        f"`dataset.rescrape` in legacy.js: {engine_answers_rescrape()}",
    )


async def maintenance_run_moves_the_state(page, journal):
    """m4 — a real run sends, and the layer's pipeline is no longer idle."""
    await page.evaluate("() => window.__mocks.reset()")
    await drive(page, "maintenance")
    await page.evaluate('(id)=>window.__panel.produce("action", id)', REAL_COMMAND)
    await page.wait_for_timeout(PANEL_IN)
    before = await page.evaluate(PIPELINE_STATE, PROBE_COMMAND)
    taken = len(await page.evaluate(CALLS, "runMaintenanceAction"))

    aim = await tap(page, "[data-maintenance-run]")
    calls = await page.evaluate(CALLS, "runMaintenanceAction")
    after = await page.evaluate(PIPELINE_STATE, PROBE_COMMAND)

    journal.check("the command's « Lancer » is under the finger", aim["tapped"],
                  f"found {aim.get('found')}, {aim.get('label')!r}")
    journal.check(
        "and it SENDS",
        len(calls) == taken + 1,
        f"{taken} call(s) before the finger, {len(calls)} after",
    )
    journal.check(
        "the layer's pipeline was idle before and is not after",
        before == IDLE and after != IDLE,
        f"{before!r} → {after!r}",
    )


async def blank_run_moves_nothing(page, journal):
    """m5 — a blank run sends, and leaves the machine exactly as it was."""
    await page.evaluate("() => window.__mocks.reset()")
    await drive(page, "maintenance")
    await page.evaluate('(id)=>window.__panel.produce("action", id)', BLANK_COMMAND)
    await page.wait_for_timeout(PANEL_IN)
    before = await page.evaluate(PIPELINE_STATE, PROBE_COMMAND)
    taken = len(await page.evaluate(CALLS, "runMaintenanceAction"))

    aim = await tap(page, "[data-maintenance-run]")
    calls = await page.evaluate(CALLS, "runMaintenanceAction")
    after = await page.evaluate(PIPELINE_STATE, PROBE_COMMAND)

    journal.check("the destructive command's « Lancer à blanc » is under the finger",
                  aim["tapped"], f"found {aim.get('found')}, {aim.get('label')!r}")
    journal.check(
        "and it SENDS — a blank run is an act, not a mime",
        len(calls) == taken + 1,
        f"{taken} call(s) before the finger, {len(calls)} after",
    )
    journal.check(
        "while the machine stays exactly where it was",
        before == IDLE and after == IDLE,
        f"{before!r} → {after!r} — « à blanc » means the state does not move",
    )


async def main():
    """Runs the five journeys, each from a named state of its own."""
    journal = Journal("R171 — the verbs that said a sentence now send one")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await sheet_rescrape_sends(page, journal)
        await follow_panel_twin_sends(page, journal)
        await one_reader_only(page, journal)
        await maintenance_run_moves_the_state(page, journal)
        await blank_run_moves_nothing(page, journal)
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
