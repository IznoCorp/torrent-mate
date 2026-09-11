"""R159 — a message said while a layer is open is SEEN, and it takes a finger (B-381).

WHAT NOBODY COULD SEE. A verb pressed inside the bottom sheet speaks through the
message layer, and the frame ranked the message at z-49 under the sheet at z-52
(`ui/variants/frame.ts`). The sentence was in the document, visible, at full
opacity — and painted under the sheet's own content: « Série suivie et saison 3
demandée — 6 épisodes à récupérer. » held by the toast seam for three seconds
while the operator saw nothing.

AND A SECOND HALF UNDER THE FIRST. While any layer is open, `app/focus.ts` marks
every child of the shell except that layer `inert` — and the message was one of
them. `inert` changes nothing about painting and removes an element from
hit-testing, so a message raised above the sheet would have been SEEN with a
close and an « Annuler » that no finger could reach.

Every instrument was green over both. R125 and R158 read `window.__toast.read()`,
which answers what the layer HOLDS, not what is painted. R101's hold (d) shows
the message with no layer open. The oracle measures no paint order.

TWO QUESTIONS, READ SEPARATELY, because each half can be broken alone:

  PAINT — `elementFromPoint` at the centre of the element carrying the message's
  text, with `inert` LIFTED from the message host for the reading and put back
  at once. The lift is what lets a hit test answer « what is painted here »
  rather than « what takes a finger here »; R101 lifts `inert` from the tab bar
  for the same reason.
    1. Over an open bottom sheet (`sheet-user`), a message is painted on top.
    2. On the follow panel, after the panel's own verb — « Récupérer la saison »
       on the one follow with a hole — the sentence the verb chose is on top.
    3. On the media screen (`mediasheet-series`), a message is painted on top.
       THIS LEG WAS NEVER RED FOR PAINT. The first version of this rule read the
       screen as covering the message; it was reading `inert`. It stays as the
       witness that the screen, ranked 45, never covered it.

  TOUCH — nothing lifted, a real finger.
    4. Over an open bottom sheet, a finger on the message's close takes the
       message off screen.

WHAT IT DOES NOT READ: whether the message covers something it should not —
R101 holds the message against the tab bar.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, PANEL_IN, SETTLED, Journal, open_page

from playwright.async_api import async_playwright

SHEET_STATE = "sheet-user"
FOLLOWS_STATE = "acq-follows-list"
SCREEN_STATE = "mediasheet-series"
PROBE = "probe message for R159"

# THE MESSAGE ON SCREEN IS TAKEN OFF FIRST. The design note's greeting occupies
# the host after boot, and a probe shown over it was never carried: an earlier
# version of this rule read the greeting's text and failed for a reason that
# was not the stacking.
HIDE = "()=>window.__toast.hide()"
SHOW = "(text)=>window.__toast.show({message: text})"
SHOWN = "()=>window.__toast.read().shown"

# WHAT IS PAINTED AT THE MESSAGE'S OWN TEXT — the deepest element under the
# message host whose text holds the words, hit-tested with `inert` lifted from
# the host and its ancestors for the reading only.
PAINTED_ON_TOP = """(words)=>{
  const host = document.querySelector('#toast');
  if (!host) return {host: false};
  const holders = [...host.querySelectorAll('*')].filter((one) =>
    (one.textContent || '').includes(words)
    && ![...one.children].some((child) => (child.textContent || '').includes(words)));
  const carrier = holders[0] || ((host.textContent || '').includes(words) ? host : null);
  if (!carrier) return {host: true, carried: false, text: (host.textContent || '').trim()};
  const lifted = [];
  for (let node = host; node; node = node.parentElement)
    if (node.hasAttribute('inert')) { lifted.push(node); node.removeAttribute('inert'); }
  const box = carrier.getBoundingClientRect();
  const x = box.left + box.width / 2, y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  lifted.forEach((node) => node.setAttribute('inert', ''));
  return {host: true, carried: true, at: [Math.round(x), Math.round(y)], lifted: lifted.length,
          onTop: !!hit && host.contains(hit),
          hit: hit ? hit.tagName + '.' + String(hit.className || '').split(' ')[0]
                     + (hit.dataset && hit.dataset.part ? '[' + hit.dataset.part + ']' : '') : null};}"""

# WHERE A FINGER ON THE MESSAGE'S CLOSE WOULD LAND — nothing lifted.
AIM_AT_THE_CLOSE = """()=>{
  const close = document.querySelector('#toastx');
  if (!close) return {found: false};
  const box = close.getBoundingClientRect();
  const x = box.left + box.width / 2, y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, reachable: !!hit && (hit === close || close.contains(hit)),
          hit: hit ? hit.tagName + '.' + String(hit.className || '').split(' ')[0] : null,
          inert: !!close.closest('[inert]')};}"""

# The one follow with a hole, drawn on the follows list.
THE_FOLLOW_WITH_A_HOLE = """()=>{
  const drawn = [...document.querySelectorAll('[data-panel]')].map((one) => one.dataset.panel);
  for (const follow of (window.__followActions?.all() || [])) {
    if (!drawn.some((seen) => seen === follow.t || seen.endsWith(':' + follow.t))) continue;
    if ((window.SEASONS[follow.t] || []).some(([n, aired, owned]) => (owned || 0) < (aired || 0)))
      return follow.t;
  }
  return null;}"""

AIM = """([selector, predicate])=>{
  const target = [...document.querySelectorAll(selector)].find((one) =>
    predicate === null || one.dataset.panel === predicate || (one.dataset.panel || '').endsWith(':' + predicate));
  if (!target) return {found: false};
  target.scrollIntoView({block: 'center'});
  const box = target.getBoundingClientRect();
  const x = box.left + box.width / 2, y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, reachable: !!hit && (hit === target || target.contains(hit))};}"""

SAID = """()=>{const held = window.__toast?.read?.();
  return held && held.message ? held.message.message || '' : '';}"""


async def show_over(page, state, wait):
    """Drives a state, clears the message on screen and shows the probe.

    Args:
        page: The page.
        state: The named state to drive.
        wait: How long the state takes to settle.
    """
    await page.evaluate("(id)=>window.__go(id)", state)
    await page.wait_for_timeout(wait)
    await page.evaluate(HIDE)
    await page.wait_for_timeout(SETTLED)
    await page.evaluate(SHOW, PROBE)
    await page.wait_for_timeout(SETTLED)


async def main():
    journal = Journal("R159 — a message said while a layer is open is seen and takes a finger")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)

        # ── PAINT ────────────────────────────────────────────────────────────
        # 1. Over an open bottom sheet.
        await show_over(page, SHEET_STATE, SETTLED)
        over_sheet = await page.evaluate(PAINTED_ON_TOP, PROBE)
        journal.check("with a bottom sheet open, a message is painted on top at its own text",
                      over_sheet.get("onTop") is True, str(over_sheet))

        # 2. On the follow panel, after the panel's own verb.
        await page.evaluate("(id)=>window.__go(id)", FOLLOWS_STATE)
        await page.wait_for_timeout(SETTLED)
        title = await page.evaluate(THE_FOLLOW_WITH_A_HOLE)
        journal.check("the fixture holds a follow with a hole, drawn on the follows list",
                      bool(title), str(title))
        if title:
            await page.evaluate(HIDE)
            row = await page.evaluate(AIM, ["[data-panel]", title])
            if row.get("found") and row.get("reachable"):
                await page.touchscreen.tap(row["x"], row["y"])
                await page.wait_for_timeout(PANEL_IN)
            act = await page.evaluate(AIM, ['#sheetin [data-part="season/grab"]', None])
            journal.check(f"« {title} »'s panel offers its season verb to a finger",
                          act.get("found") and act.get("reachable"), str(act))
            if act.get("found") and act.get("reachable"):
                await page.touchscreen.tap(act["x"], act["y"])
                await page.wait_for_timeout(ACTED)
                said = await page.evaluate(SAID)
                seen = await page.evaluate(PAINTED_ON_TOP, said[:24]) if said else {"carried": False}
                journal.check("and the sentence the verb chose is painted on top, over the panel it was pressed in",
                              bool(said) and seen.get("onTop") is True, f"{said!r} {seen}")

        # 3. On the media screen — the witness.
        await page.evaluate("()=>window.__panel?.close?.()")
        await show_over(page, SCREEN_STATE, SETTLED * 3)
        over_screen = await page.evaluate(PAINTED_ON_TOP, PROBE)
        journal.check("on the media screen, a message is painted on top at its own text — the "
                      "screen never covered it",
                      over_screen.get("onTop") is True, str(over_screen))

        # ── TOUCH ────────────────────────────────────────────────────────────
        # 4. Over an open bottom sheet, nothing lifted, a real finger.
        await show_over(page, SHEET_STATE, SETTLED)
        close = await page.evaluate(AIM_AT_THE_CLOSE)
        journal.check("with a bottom sheet open, the message's close takes a finger — nothing lifted",
                      close.get("found") and close.get("reachable"), str(close))
        if close.get("found") and close.get("reachable"):
            await page.touchscreen.tap(close["x"], close["y"])
            await page.wait_for_timeout(SETTLED)
        journal.check("and the finger takes the message off screen",
                      await page.evaluate(SHOWN) is False)

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())
