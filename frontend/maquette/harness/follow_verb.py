"""R130 — « Ajouter » really follows, from both places that offer it.

THE ACT AND ITS TWO EMITTERS. A suggestion's panel offers « Ajouter » / « Suivre
la série » and carries `data-follow` with the suggestion's POSITION beside it; a
medium's own sheet offers the same act and carries `data-follow` with its KIND
beside it instead. Both are React already. What is not is the READER: one branch
of the dying engine's document delegation answers both, and moving the act means
moving that reader and deleting the branch.

TWO EMITTERS IS THE WHOLE REASON THIS RULE READS BOTH. A move that satisfied the
panel and left the sheet's `data-fkind` path unanswered would draw a follow
button that does nothing, on the screen where a reader is most likely to press
it — and no hold reading only the panel could tell. `data-take` cost this
repository exactly that shape, in the other direction: two branches for one name,
the first swallowing the second.

WHAT IT READS, and each fails differently:

  1. THE FIXTURE OFFERS A SUGGESTION THAT IS NOT ALREADY FOLLOWED. Held first,
     because the act's own body returns early on a title already followed — so
     every hold below would pass over a walk that did nothing at all.
  2. THE ACTION IS ON A BUTTON A FINGER REACHES, hit-tested at its own centre.
     « Is the node in the tree » is a different question from « would a tap
     there land on it ».
  3. THE FOLLOW ARRIVES AT THE HEAD OF « Suivis », MARKED NEW. Read on the
     LAYER's own answer, never on the screen: a message is a message and can be
     right about nothing. The head and the mark are both read, because a follow
     appended at the tail is a follow the reader has to go looking for, which is
     what « il apparaît en tête, marqué Nouveau » exists to prevent.
  4. THE SUGGESTION LEAVES THE DECK. Following something is answering the
     question the deck asked, so the card is spent — and it is read where the
     deck reads it, on the layer, not by counting what happens to be drawn.
  5. THE SHEET'S OWN BUTTON ADDS TOO, on a medium whose sheet offers it. The
     second emitter, the one a partial move would break in silence.
  6. NO ERROR IS RAISED anywhere in the walk.

HOW THE PANEL IS OPENED, and the split is deliberate. The panel is raised
through the seam and the ACTION is tapped by a finger. Which GESTURE opens a
suggestion's panel is a live question of its own — a tap on a deck card reaches
the media sheet through a child that covers the whole card — and it belongs to
the entry that owns it, with its own rule. Mixing the two would leave this rule
red for a reason that is not this act's, which is the state a rule cannot be
read in.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, SETTLED, open_page

from playwright.async_api import async_playwright

# WHERE THE SUGGESTIONS ARE, and where a sheet offers the same act.
DECK_STATE = "acq-discover"
SHEET_STATE = "mediasheet-suggestion-series"

# THE RESERVE THE DECK IS DRAWN FROM, and the follows the layer holds. Both are
# read as the surfaces read them, so a hold compares two answers to one question
# rather than the drawing with itself.
RESERVE = "()=>(window.__suggestions?.() || []).map((one) => ({t: one.t, k: one.k}))"
FOLLOWS = """()=>(window.__followActions?.all() || []).map(
  (one) => ({t: one.t, k: one.k, st: one.st, fresh: !!one.fresh}))"""

# WHAT THE DECK CONSIDERS SPENT. `sugGone` is a Set of POSITIONS in the reserve,
# mutated in place, and it is what keeps a card from coming back on the next
# render — so a card removed from the document and absent here is a card that
# returns.
SPENT = """()=>[...(window.__store?.read().state.sugGone || [])]"""

# THE ACTIONS THE PANEL OFFERS, by LABEL, read off the panel rather than off the
# producer's source.
ACTIONS = """()=>[...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
  .map((one) => (one.textContent || '').trim())"""


async def tap_action(page, word):
    """Taps the panel action whose label carries a word, by a real finger.

    Args:
        page: The page.
        word: A word the action's label carries, lower-cased.

    Returns:
        What the aim read, with `tapped` saying whether a finger went down.
    """
    aim = await page.evaluate("""(word)=>{
        const act = [...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
          .find((one) => (one.textContent || '').toLowerCase().includes(word));
        if (!act) return {found: false};
        const box = act.getBoundingClientRect();
        const x = box.left + box.width / 2;
        const y = box.top + box.height / 2;
        const hit = document.elementFromPoint(x, y);
        return {found: true, x, y, label: (act.textContent || '').trim(),
                reachable: !!hit && (hit === act || act.contains(hit)),
                covering: hit === null ? "nothing" : hit.tagName};}""", word)
    if aim.get("found") and aim.get("reachable"):
        await page.touchscreen.tap(aim["x"], aim["y"])
        aim["tapped"] = True
    else:
        aim["tapped"] = False
    return aim


async def tap_part(page, part):
    """Taps the element carrying one `data-part`, hit-tested at its centre.

    IT SCROLLS FIRST, and that is not a convenience. The sheet's own follow
    button sits far below the fold — measured at y=1661 on an 844-tall frame —
    and `elementFromPoint` there answers null, so a hit test taken without
    scrolling reports « covered by nothing » and reads as a defect. A hand
    scrolls; the rule does what the hand does, and then asks what is under the
    finger.
    """
    await page.evaluate("""(part)=>{
        document.querySelector('[data-part="' + part + '"]')
          ?.scrollIntoView({block: "center"});}""", part)
    # THE SCROLL IS LET SETTLE BEFORE THE BOX IS READ, and the first version of
    # this helper did not: measuring the rectangle in the same turn as the
    # scroll answered a point where `elementFromPoint` returned the ROOT
    # element — a reading that looks exactly like a covered button and is only
    # a stale rectangle.
    await page.wait_for_timeout(SETTLED)
    aim = await page.evaluate("""(part)=>{
        const one = document.querySelector('[data-part="' + part + '"]');
        if (!one) return {found: false};
        const box = one.getBoundingClientRect();
        const x = box.left + box.width / 2;
        const y = box.top + box.height / 2;
        const hit = document.elementFromPoint(x, y);
        return {found: true, x, y,
                reachable: !!hit && (hit === one || one.contains(hit)),
                covering: hit === null ? "nothing" :
                  (hit.tagName + (hit.className ? "." + String(hit.className).split(" ")[0] : ""))};}""",
        part)
    if aim.get("found") and aim.get("reachable"):
        await page.touchscreen.tap(aim["x"], aim["y"])
        aim["tapped"] = True
    else:
        aim["tapped"] = False
    return aim


async def main():
    journal = Journal("R130 — « Ajouter » follows, from the panel and from the sheet")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", DECK_STATE)
        await page.wait_for_timeout(SETTLED)

        reserve = await page.evaluate(RESERVE)
        followed_before = await page.evaluate(FOLLOWS)
        held = {one["t"] for one in followed_before}
        # THE SUBJECT IS CHOSEN FROM THE DATA BEFORE A FINGER MOVES, so a
        # failure is about the interface and never about the walk. A title
        # already followed would take the act's own early return.
        subject = next(
            ((position, one) for position, one in enumerate(reserve)
             if one["t"] not in held), (None, None))
        position, suggestion = subject
        journal.check(
            "the reserve offers a suggestion that is NOT already followed — "
            "without one, every hold below passes over a walk that did nothing",
            suggestion is not None,
            f"{len(reserve)} in the reserve, {len(held)} already followed")
        if suggestion is None:
            journal.summary()
            await context.close()
            await browser.close()
            return

        await page.evaluate("(at)=>window.__panel.produce('suggestion', String(at))",
                            position)
        await page.wait_for_timeout(PANEL_IN)
        offered = await page.evaluate(ACTIONS)
        journal.check(
            "the suggestion's panel offers the act",
            any("ajout" in one.lower() or "suivre" in one.lower() for one in offered),
            str(offered))

        spent_before = await page.evaluate(SPENT)
        aim = await tap_action(page, "ajout" if suggestion["k"] == "Film" else "suivre")
        journal.check(
            "and it is on a button a finger reaches, hit-tested at its centre",
            aim["tapped"], str(aim))
        await page.wait_for_timeout(ACTED)

        followed_after = await page.evaluate(FOLLOWS)
        head = followed_after[0] if followed_after else None
        journal.check(
            "the follow arrives at the HEAD of « Suivis », marked new — read on "
            "the layer, because a message can be right about nothing",
            head is not None and head["t"] == suggestion["t"] and head["fresh"],
            f"head={head} subject={suggestion}")

        spent_after = await page.evaluate(SPENT)
        journal.check(
            "and the suggestion leaves the deck — read where the deck reads it, "
            "so a card removed from the document but not from `sugGone` is a "
            "card that comes back",
            position in spent_after and position not in spent_before,
            f"{spent_before} → {spent_after}, position {position}")

        journal.check("and the act raises no error", not errors, str(errors))

        # ── THE SECOND EMITTER ─────────────────────────────────────────────
        #
        # The sheet's own button, which carries the KIND rather than a position.
        # A move that answered the panel and left this one unanswered would draw
        # a button that does nothing on the screen where it is most pressed.
        errors.clear()
        await page.evaluate("(id)=>window.__go(id)", SHEET_STATE)
        await page.wait_for_timeout(SETTLED)
        sheet_before = await page.evaluate(FOLLOWS)
        sheet_subject = await page.evaluate(
            """()=>{const one = document.querySelector('[data-part="media/add"]');
                    return one ? {title: one.dataset.follow, kind: one.dataset.fkind} : null;}""")
        journal.check(
            "the sheet of a medium that is not followed offers the act, with "
            "the KIND beside it — the emitter a partial move breaks in silence",
            sheet_subject is not None and bool(sheet_subject.get("title"))
            and bool(sheet_subject.get("kind")),
            str(sheet_subject))
        sheet_aim = await tap_part(page, "media/add")
        journal.check(
            "and that button takes a finger too",
            sheet_aim["tapped"], str(sheet_aim))
        await page.wait_for_timeout(ACTED)
        sheet_after = await page.evaluate(FOLLOWS)
        journal.check(
            "and the medium is followed after it",
            sheet_subject is not None
            and any(one["t"] == sheet_subject["title"] for one in sheet_after)
            and not any(one["t"] == sheet_subject["title"] for one in sheet_before),
            f"{len(sheet_before)} → {len(sheet_after)} follows, "
            f"subject={sheet_subject}")
        journal.check("and the sheet's act raises no error either",
                      not errors, str(errors))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
