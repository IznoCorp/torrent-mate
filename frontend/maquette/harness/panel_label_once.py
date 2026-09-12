"""R139 — a panel never offers the same label twice.

B-313: the follow sheet drew « Voir le parcours » TWICE — once as the primary
act, once in the secondary row — for any medium whose primary act falls through
to the journey. The operator reported it from Arrivées with a screenshot.

**THE RULE THAT WOULD HAVE CAUGHT IT DID NOT EXIST**, and the register said so
in the same breath as the defect: nothing counted a panel's actions by label.
So this rule is not written around the one producer that was wrong. It raises
every panel a finger can reach on the surfaces below and refuses a repeated
label in any of them — the defect's FAMILY, not its instance.

WHY A LABEL AND NOT A DESTINATION. Two buttons leading to different places may
legitimately sit side by side; two buttons a reader cannot tell apart cannot.
What the operator saw was two identical words, and the label is the only thing
he had to choose between them. A rule reading destinations would have been
green over the exact screenshot that opened the bug — both buttons carried the
same one.

RAISED BY A FINGER, never through a producer. The row is scrolled to, its own
centre is hit-tested, and the click is dispatched AT THAT POINT by the mouse —
so a row something covers fails here instead of being clicked through. A rule
that calls the producer measures the drawing and not the path to it, and the
panel this bug lives in is reached by a tap on a card.

WHAT IT READS, and each fails differently:

  1. THE SWEEP RAISED PANELS AT ALL. Written FIRST and before anything counts
     labels, because a walk that opens nothing has no duplicate to find and the
     rule below it would be green for ever over an empty list. It is the same
     vacuity that made a sibling rule's « nothing was refused » meaningless
     until it read the layer's own record.
  2. THE SUBJECT FAMILY IS STILL DRAWN — at least one panel whose PRIMARY act
     leads to the journey, which is exactly the branch B-313 lives in. Read by
     the action's own destination (`data-journey`), never by its text: a rule
     anchored on French would stop measuring the day the copy is retouched, and
     would say « no violation » while doing it.
  3. NO PANEL OFFERS THE SAME LABEL TWICE. Every offender is named with the
     panel it was drawn in and the word it repeated.

THE SURFACES ARE A LIST, deliberately. Widening the sweep is editing it, and
the selector is generic: any element addressing a panel, on whatever surface.
The two here were chosen because one CONTAINS the subject and the other is the
broadest catalogue of follow panels the prototype draws — films and series,
watched and not, in the library and not.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, PANEL_IN, SETTLED, open_page

from playwright.async_api import async_playwright

# WHERE THE PANELS ARE RAISED FROM. `arr-queued` carries the subject — a medium
# with no sheet that nothing is chasing, whose primary act falls through to the
# journey. `acq-follows-list` is the breadth.
SURFACES = ["arr-queued", "acq-follows-list"]

# THE DISTINCT PANELS A SURFACE ADDRESSES. A card offers the same panel from
# its folder button and from its body; both are the same descriptor, so the
# walk raises each address once and the second entry point costs nothing.
ADDRESSES = """()=>{
  const seen = [];
  for (const one of document.querySelectorAll('[data-panel]'))
    if (!seen.includes(one.dataset.panel)) seen.push(one.dataset.panel);
  return seen;}"""

# AIMING AT ONE ADDRESS, the way a thumb does: bring the row into view, take
# its own centre, and ask the document what is actually AT that point. The
# click is dispatched by the mouse at the returned coordinates rather than on
# the node, so a row under a scrim fails instead of being reached through it.
AIM = """(address)=>{
  const row = [...document.querySelectorAll('[data-panel]')].find(
    (one) => one.dataset.panel === address);
  if (!row) return {found: false};
  row.scrollIntoView({block: "center"});
  const box = row.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y,
          reachable: !!hit && (hit === row || row.contains(hit)),
          covering: hit ? (hit.dataset.part
                           || hit.getAttribute("class")
                           || hit.tagName) : null};}"""

# WHAT THE RAISED PANEL OFFERS. The labels in the order a reader meets them,
# and — separately — whether the FIRST act of the FIRST block leads to the
# journey, which is the branch the defect lived in. The blocks are told apart
# by `data-part`, never by their class.
OFFERED = """()=>{
  const sheet = document.querySelector('[data-part="sheet"]');
  const blocks = [...document.querySelectorAll('[data-part="sheet/actions"]')];
  const lead = blocks.length
    ? blocks[0].querySelector('[data-part="sheet/action"]') : null;
  return {
    open: !!window.__panel?.isOpen?.(),
    title: (document.querySelector('[data-part="sheet/title"]')
              ?.textContent || "").trim(),
    labels: [...document.querySelectorAll('[data-part="sheet/action"]')]
              .map((one) => (one.textContent || "").trim()),
    leadsToJourney: !!lead && lead.dataset.journey !== undefined,
    sheet: !!sheet};}"""

CLOSE = """()=>window.__panel?.close?.()"""


def repeated(labels):
    """Names the labels a panel offers more than once.

    Args:
        labels: The panel's action labels, in the order they are drawn.

    Returns:
        The repeated ones, sorted, each named once however often it recurs.
    """
    return sorted({one for one in labels if labels.count(one) > 1})


async def main():
    journal = Journal("R139 — a panel never offers the same label twice")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        raised: list[dict] = []
        unreachable: list[str] = []
        for surface in SURFACES:
            await page.evaluate("(id)=>window.__go(id)", surface)
            await page.wait_for_timeout(SETTLED)
            for address in await page.evaluate(ADDRESSES):
                aim = await page.evaluate(AIM, address)
                if not aim.get("reachable"):
                    unreachable.append(f"{surface} · {address} "
                                       f"({aim.get('covering')})")
                    continue
                await page.mouse.click(aim["x"], aim["y"])
                await page.wait_for_timeout(PANEL_IN)
                seen = await page.evaluate(OFFERED)
                if seen["open"]:
                    raised.append({**seen, "surface": surface,
                                   "address": address})
                await page.evaluate(CLOSE)
                await page.wait_for_timeout(SETTLED)

        # ── THE WALK HAPPENED, and it is said before anything is counted ────
        journal.check(
            "the walk really RAISED panels — written before the count below, "
            "because a sweep that opened none would leave that count green "
            "over an empty list for ever",
            len(raised) >= len(SURFACES) and not unreachable,
            f"{len(raised)} panel(s) over {len(SURFACES)} surface(s)"
            + (f"; unreachable: {unreachable}" if unreachable else ""))

        # ── AND IT REACHED THE BRANCH THE DEFECT LIVED IN ──────────────────
        subjects = [one for one in raised if one["leadsToJourney"]]
        journal.check(
            "and it reached a panel whose PRIMARY act leads to the journey — "
            "B-313's own branch, a medium with no sheet that nothing is "
            "chasing. Held by the destination and never by the word, so "
            "retouching the copy cannot silently empty this walk",
            bool(subjects),
            f"{len(subjects)} such panel(s): "
            + ", ".join(one["address"] for one in subjects))

        # ── THE RULE ITSELF ────────────────────────────────────────────────
        offenders = [
            f"{one['surface']} · « {one['title']} » offers "
            + ", ".join(f"« {word} »" for word in repeated(one["labels"]))
            + f" twice — {one['labels']}"
            for one in raised if repeated(one["labels"])]
        journal.check(
            "no panel offers the same label twice — two buttons a reader "
            "cannot tell apart are a choice he cannot make (B-313)",
            not offenders,
            f"{len(raised)} panel(s) read; "
            + ("no repetition" if not offenders else "; ".join(offenders)))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
