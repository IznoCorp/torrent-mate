"""R163 — the harness's own chrome never covers the product's answer (B-394).

WHAT WENT WRONG. A message said while a layer is open is drawn at the TOP of the
frame, and the harness's two floating buttons — the design note and the states
list — sit exactly there. They declared `z-index: 70`, the splash's rank, so the
sentence answering a verb pressed inside a sheet was painted under chrome that
is in NO production build. The operator read it on a journey sheet.

WHY IT HIT-TESTS RATHER THAN READING TWO NUMBERS, the reason R101 already gives:
two `z-index` values say nothing unless the elements share a stacking context,
and everything here turns on that. `elementFromPoint` asks the browser what is
in front, which is the question an eye asks.

AND WHY IT LIFTS `inert` FIRST, which is the trap this rule was WRITTEN INTO and
measured its way out of. While a layer is open the harness bar carries `inert`,
and `inert` takes an element out of hit-testing WITHOUT changing what is
painted — B-381's own lesson, in this file's own subject. Measured on the head
that declares `z-index: 70`: as drawn, the hit test answers the message on both
buttons and the rule would have passed over the defect; with the bar's inertness
lifted, the same point answers the BUTTON on both, in two states. So the rule
lifts the attribute, asks what is in front, and puts it back — it measures
PAINT, which is what the operator read, and never reachability, which is a
different question with a different answer.

WHAT IT READS, and each hold fails differently:

  k0. THE TWO BOXES ACTUALLY OVERLAP. Held first and read as a rectangle: the
      message is full width at the top and the buttons are inset from the right,
      so they meet — but a layout change could part them, and a hit test taken
      where nothing overlaps proves nothing at all.
  k1. WHERE THEY MEET, THE MESSAGE IS ON TOP — measured with the bar's inertness
      lifted, so what is read is paint and not reach. The hit test lands on the
      message or on something inside it, never on a harness button. This is the
      ruling.
  k2. THE OPENED PANEL STAYS ABOVE THE MESSAGE. The states list is the
      instrument the prototype is driven with; a message painted over it would
      hide the control one is reaching for. Read the same way, inside the panel.

WHAT IT DOES NOT READ. Whether the buttons are reachable when no message is
shown: that is the harness's own business and no product property, and this rule
would report it without being able to say what it means. Nor does it read the
ranked list in `ui/variants/frame.ts` — a list is prose, and prose is not what
paints.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, PANEL_IN, SETTLED, open_page

from playwright.async_api import async_playwright

# A STATE THAT OPENS A LAYER, because the message only moves to the top while one
# is open — which is the placement this rule is about.
LAYERED_STATE = "sheet-user"

# The message's own text. A token rather than a sentence: what is measured is
# where it is painted, and an interface sentence written here would be one the
# interface never says.
MESSAGE = "R163"

# WHERE THE MESSAGE AND THE HARNESS CHROME MEET, and what is painted there. The
# overlap is computed from both boxes and the hit test is taken at its centre —
# never at the message's own centre, which the buttons never reach.
OVERLAP = """() => {
  const message = document.querySelector('#toast');
  const bar = document.querySelector('[data-part="harness/bar"]');
  const buttons = bar ? [...bar.querySelectorAll('button')] : [];
  if (!message || buttons.length === 0) return {found: false, buttons: buttons.length};
  // INERTNESS LIFTED FOR THE READING, AND PUT BACK. `inert` removes an element
  // from hit-testing and changes nothing about what is painted, so a hit test
  // taken over an inert bar answers what is BEHIND it — which is how this very
  // rule first passed over the defect it exists for.
  const inerted = [];
  for (let node = bar; node; node = node.parentElement) {
    if (node.hasAttribute && node.hasAttribute('inert')) {
      node.removeAttribute('inert');
      inerted.push(node);
    }
  }
  const said = message.getBoundingClientRect();
  const meetings = buttons.map((button) => {
    const box = button.getBoundingClientRect();
    const left = Math.max(said.left, box.left);
    const right = Math.min(said.right, box.right);
    const top = Math.max(said.top, box.top);
    const bottom = Math.min(said.bottom, box.bottom);
    if (right <= left || bottom <= top) return {label: button.id, overlaps: false};
    const x = (left + right) / 2;
    const y = (top + bottom) / 2;
    const hit = document.elementFromPoint(x, y);
    // NAMED BY THE CONTROL, never by the drawing inside it: a verdict reading
    // « path » says nothing about what covers the sentence.
    const covering = hit === null ? null : hit.closest('button, [data-part]');
    return {label: button.id, overlaps: true, width: right - left, height: bottom - top,
            onTop: hit === null ? 'nothing'
              : (message.contains(hit) ? 'the message'
                 : covering === null ? hit.tagName
                 : (covering.id || covering.dataset.part || covering.tagName)),
            covered: !!hit && button.contains(hit)};
  });
  for (const node of inerted) node.setAttribute('inert', '');
  return {found: true, shown: !!window.__toast?.read().shown,
          lifted: inerted.length, meetings};
}"""

# THE OPENED PANEL, read where it covers the message: it fills the frame, so its
# own centre is a point the message would be drawn at.
PANEL = """() => {
  const panel = document.querySelector('[data-part="harness/panel"]');
  const message = document.querySelector('#toast');
  if (!panel || !message) return {found: false};
  const inerted = [];
  for (let node = panel; node; node = node.parentElement) {
    if (node.hasAttribute && node.hasAttribute('inert')) {
      node.removeAttribute('inert');
      inerted.push(node);
    }
  }
  const said = message.getBoundingClientRect();
  const x = said.left + said.width / 2;
  const y = said.top + said.height / 2;
  const hit = document.elementFromPoint(x, y);
  for (const node of inerted) node.setAttribute('inert', '');
  return {found: true,
          onTop: hit === null ? 'nothing'
            : (panel.contains(hit) ? 'the panel'
               : message.contains(hit) ? 'the message' : hit.tagName)};
}"""


async def show_message(page):
    """Says a message through the host's own seam and waits for it to be shown."""
    await page.evaluate("(text)=>window.__toast?.show({message: text})", MESSAGE)
    await page.wait_for_timeout(SETTLED)


async def main():
    """Runs the three holds with a layer open, then with the panel opened."""
    journal = Journal("R163 — the harness's chrome never covers the message")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", LAYERED_STATE)
        await page.wait_for_timeout(PANEL_IN)
        await show_message(page)
        reading = await page.evaluate(OVERLAP)
        meetings = reading.get("meetings") or []
        met = [meeting for meeting in meetings if meeting.get("overlaps")]

        journal.check("the message and the harness's buttons meet at the top of the frame",
                      reading.get("found") and reading.get("shown") and len(met) == len(meetings)
                      and len(met) >= 2,
                      f"{len(met)} of {len(meetings)} button(s) overlap: "
                      + str([(m['label'], round(m.get('width', 0)), round(m.get('height', 0)))
                             for m in met]))
        journal.check("where they meet, the message is what is PAINTED",
                      bool(met) and all(meeting["onTop"] == "the message" for meeting in met),
                      f"inertness lifted on {reading.get('lifted')} element(s); "
                      + str([(meeting["label"], meeting["onTop"]) for meeting in met]))

        # ── the instrument, which must stay above the answer ──────────────
        await page.evaluate("()=>document.querySelector('#scenBtn')?.click()")
        await page.wait_for_timeout(SETTLED)
        await show_message(page)
        panel = await page.evaluate(PANEL)
        journal.check("the opened states panel stays above the message",
                      panel.get("found") and panel["onTop"] == "the panel", str(panel))

        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
