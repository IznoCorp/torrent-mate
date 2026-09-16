"""R197 — a spent panel action is drawn as disabled (B-339).

WHAT THE OPERATOR SAW. On the add screen, a result already added: its panel's
primary action read « ✓ Ajouté » in full primary yellow, and a tap did nothing.
The act was spent and the drawing did not say so.

WHAT IT READS, on the real panels of two results of the same answer — one added
by a finger, one not — so the two buttons are the same variant, the same tone,
in the same document, and differ only by being spent:

  s1. THE SPENT ACTION IS DISABLED, AND A TAP ON IT ADDS NOTHING. Already true
      when the defect was reported; held so a drawing repair cannot buy itself
      by making the button live again.
  s2. ITS DRAWING DIFFERS FROM THE AVAILABLE ONE, read on the computed
      properties a disabled half can move — opacity, background, text and
      border colour. The detail names every property that differs, so a fall
      says which one stopped differing.
  s3. AND IT STILL DIFFERS in the light theme and with reduced motion, each in
      a context of its own.
  s4. AND IT DOES NOT WEAR THE « + » the available act wears: a check mark
      beside a plus is an act offered and an act done in one button.

THE OPACITY HALF WAS ALREADY THERE when this rule was written: `disabled:
opacity-50` on the action variant's base, so s1–s3 read green before any move
and s4 was the only red. The mutation removing that half is what proves s2 and
s3 read it.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, PANEL_IN, PANEL_OUT, SETTLED, Journal, open_page

from playwright.async_api import async_playwright

RESULTS_STATE = "acq-add-results"

# THE PROPERTIES A DISABLED HALF CAN MOVE.
DRAWN = ("opacity", "backgroundColor", "color", "borderTopColor")

# TWO RESULTS THE LIBRARY DOES NOT OWN, so the act adds directly with no dialog.
UNOWNED = """()=>(window.__searchResults?.().results || [])
  .map((result, position) => ({position, owned: result.owned}))
  .filter((one) => !one.owned).map((one) => one.position)"""

# THE OPEN PANEL'S ADD ACTION, as drawn.
ACTION = """(position)=>{
  const act = document.querySelector(`#sheet[data-open] [data-add="${position}"]`);
  if (!act) return null;
  const style = getComputedStyle(act);
  return {
    disabled: act.disabled,
    icon: act.querySelector('svg')?.innerHTML ?? null,
    text: act.textContent.trim(),
    theme: document.documentElement.dataset.theme || null,
    drawn: {opacity: style.opacity, backgroundColor: style.backgroundColor,
            color: style.color, borderTopColor: style.borderTopColor},
  };
}"""


async def tap(page, selector):
    """Taps the first element a selector finds, by a finger at its own centre."""
    await page.evaluate("""(selector)=>document.querySelector(selector)
      ?.scrollIntoView({block: 'center'})""", selector)
    await page.wait_for_timeout(SETTLED)
    aim = await page.evaluate("""(selector) => {
      const one = document.querySelector(selector);
      if (!one) return {found: false};
      const box = one.getBoundingClientRect();
      const x = box.left + box.width / 2;
      const y = box.top + box.height / 2;
      const hit = document.elementFromPoint(x, y);
      return {found: true, x, y,
              reachable: !!hit && (hit === one || one.contains(hit)),
              covering: hit === null ? 'nothing' : hit.tagName};
    }""", selector)
    aim["tapped"] = bool(aim.get("found") and aim.get("reachable"))
    if aim["tapped"]:
        await page.touchscreen.tap(aim["x"], aim["y"])
        await page.wait_for_timeout(ACTED)
    return aim


async def open_result_panel(page, position):
    """Opens one result's panel from its row."""
    await page.evaluate("()=>window.__panel?.close?.()")
    await page.wait_for_timeout(PANEL_OUT)
    await tap(page, f'[data-part="screen"][data-open] [data-panel="add:{position}"]')
    await page.wait_for_timeout(PANEL_IN)
    return await page.evaluate(ACTION, position)


async def read_both(browser, **context_options):
    """Adds one result by a finger, then reads its spent act and another's available one."""
    context, page = await open_page(browser, **context_options)
    await page.evaluate("(id)=>window.__go(id)", RESULTS_STATE)
    await page.wait_for_timeout(SETTLED + ACTED)
    unowned = await page.evaluate(UNOWNED)
    if len(unowned) < 2:
        await context.close()
        return {"unowned": unowned}
    spent_position, available_position = unowned[0], unowned[1]
    await open_result_panel(page, spent_position)
    await tap(page, f'#sheet [data-add="{spent_position}"]')
    spent = await open_result_panel(page, spent_position)
    added_before = await page.evaluate("()=>window.__addedPositions()")
    retap = await tap(page, f'#sheet [data-add="{spent_position}"]')
    added_after = await page.evaluate("()=>window.__addedPositions()")
    available = await open_result_panel(page, available_position)
    await context.close()
    return {"unowned": unowned, "spent": spent, "available": available, "retap": retap,
            "added_before": added_before, "added_after": added_after}


def differing(reading):
    """Names the drawn properties on which the spent act differs from the available one."""
    if not reading.get("spent") or not reading.get("available"):
        return []
    return [name for name in DRAWN
            if reading["spent"]["drawn"][name] != reading["available"]["drawn"][name]]


async def main():
    """Reads the spent act against the available one, in three contexts."""
    journal = Journal("R197 — a spent panel action is drawn as disabled")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        dark = await read_both(browser)
        journal.check("the spent action is disabled, and a tap on it adds nothing",
                      bool(dark.get("spent")) and dark["spent"]["disabled"]
                      and dark.get("available") is not None and not dark["available"]["disabled"]
                      and dark["added_before"] == dark["added_after"],
                      str(dark))
        journal.check("it does not wear the « + » the available act wears",
                      bool(dark.get("spent")) and bool(dark.get("available"))
                      and dark["available"]["icon"] is not None
                      and dark["spent"]["icon"] != dark["available"]["icon"],
                      f"spent icon {(dark.get('spent') or {}).get('icon')!r:.80}, "
                      f"available icon {(dark.get('available') or {}).get('icon')!r:.80}")
        journal.check("its drawing differs from the available one",
                      bool(differing(dark)),
                      f"differs on {differing(dark)}; spent {dark.get('spent')}, "
                      f"available {dark.get('available')}")
        for name, options in (("in the light theme", {"color_scheme": "light"}),
                              ("with reduced motion", {"reduced_motion": "reduce"})):
            reading = await read_both(browser, **options)
            journal.check(f"and it still differs {name}",
                          bool(differing(reading)),
                          f"differs on {differing(reading)}; spent {reading.get('spent')}, "
                          f"available {reading.get('available')}")
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
