"""R-fab — « En pause » cards spaced like the others; the last card clears the « + » at full scroll.

The operator's words (2026-10-02): the cards of « Suivis › En pause » touch each
other where every other list separates them, and the acquisition pages must
scroll far enough that, fully scrolled, no card sits under the « + » — so the
last card is always seen whole, and « Résoudre » on « À traiter » can be tapped
without hitting the « + » by mistake.

What this holds, at 390 px:

1. on « Suivis », the gap between two cards of the opened « En pause » fold is the
   gap between two cards of an ordinary section; the same for « Mis de côté »
   at the end of « À traiter » (the fold's sibling, same mechanism);
2. on every tab of the acquisition page, scrolled to the bottom, the last card's
   box does not intersect the « + »'s;
3. on « À traiter » filtered on « Résoudre » (the list then ends on a card that
   carries it), the last « Résoudre » is entirely visible, does not intersect the
   « + », and a tap at its centre lands on « Résoudre » (`elementFromPoint`).

Red on 08a2d8516: the folds' cards touch (gap 0 against 8 px), and the last card
ends 32 px above the bar while the « + » reaches 68 px above it.
"""
import asyncio

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

FOLLOWS = "acq-follows-list"
TODO = "acq-todo-every-cause"
SET_ASIDE = "acq-card-set-aside"
# A SECOND card to set aside, so the fold holds two to measure (the state sets Lucky aside itself).
ALSO_ASIDE = "Top Chef Le Concours Parallèle (2026)"
# (label, named state, what is done to it first): « open-paused » unfolds « En pause »; « resolve »
# filters « À traiter » on « Résoudre », which ends the list on a card that carries it — the operator's case.
PAGES = [
    ("Suivis", FOLLOWS, None),
    ("Suivis, « En pause » ouvert", FOLLOWS, "open-paused"),
    ("À traiter", TODO, None),
    ("À traiter, rien que « Résoudre »", TODO, "resolve"),
    ("En cours", "acq-now-loaded", None),
]

ORDINARY = """() => {
  const sections = [...document.querySelectorAll('#view [data-part="section"]')];
  for (const section of sections) {
    if (section.closest('[data-part="section/paused"]')) continue;
    const cards = [...section.querySelectorAll('[data-part="card"]')];
    if (cards.length < 2) continue;
    return Math.round((cards[1].getBoundingClientRect().top - cards[0].getBoundingClientRect().bottom) * 100) / 100;
  }
  return null;
}"""
FOLD = """(part) => {
  const fold = document.querySelector('#view [data-part="' + part + '"]');
  if (!fold) return null;
  const details = fold.querySelector('details');
  if (!details.open) details.querySelector('summary').click();
  return true;
}"""
FOLD_GAPS = """(part) => {
  const fold = document.querySelector('#view [data-part="' + part + '"]');
  const cards = [...fold.querySelectorAll('[data-part="card"]')];
  const gaps = [];
  for (let i = 1; i < cards.length; i++)
    gaps.push(Math.round((cards[i].getBoundingClientRect().top - cards[i - 1].getBoundingClientRect().bottom) * 100) / 100);
  return gaps;
}"""
# At full scroll: the last card of the page, the « + », and what a tap at the
# centre of the last « Résoudre » would hit.
BOTTOM = """() => {
  const fab = document.querySelector('#fab');
  const box = (el) => { const r = el.getBoundingClientRect(); return { top: r.top, bottom: r.bottom, left: r.left, right: r.right }; };
  // Only the cards DRAWN: a card in a closed fold is not on the page.
  const cards = [...document.querySelectorAll('#view [data-part="card"]')].filter(one => !one.closest('details:not([open])'));
  const last = cards.length ? cards[cards.length - 1] : null;
  // The last card that carries a « Résoudre », and it must be the last card the list draws.
  const resolve = [...cards].reverse().map(one => one.querySelector('[data-resolution]')).find(Boolean) || null;
  const lastResolve = !!(last && last.querySelector('[data-resolution]'));
  let tapped = null;
  if (resolve) {
    const r = resolve.getBoundingClientRect();
    const hit = document.elementFromPoint((r.left + r.right) / 2, (r.top + r.bottom) / 2);
    tapped = hit && (hit === resolve || resolve.contains(hit)) ? "resolve" : (hit && hit.closest('#fab') ? "fab" : String(hit && hit.tagName));
  }
  return { fab: fab && !fab.hidden ? box(fab) : null, last: last ? box(last) : null,
           resolve: resolve ? box(resolve) : null, tapped, lastResolve, count: cards.length, view: window.innerHeight };
}"""


def meets(a, b):
    """Whether two boxes share any area."""
    return a["left"] < b["right"] and b["left"] < a["right"] and a["top"] < b["bottom"] and b["top"] < a["bottom"]


async def fresh(browser, errors):
    """A page of its own: a message left by the previous state would hide the « + »."""
    context, page = await open_page(browser)
    page.on("pageerror", lambda error: errors.append(str(error)))
    return context, page


SCROLL = """() => { const port = document.querySelector('#port'); port.scrollTop = port.scrollHeight; return port.scrollTop; }"""


async def to_the_bottom(page):
    """Scrolls #port until it stops moving: a list that grows as it is reached is followed to its end."""
    seen = -1
    for _ in range(12):
        top = await page.evaluate(SCROLL)
        await page.wait_for_timeout(ACTED)
        if top == seen:
            break
        seen = top


async def go(page, state):
    answer = await page.evaluate(
        "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
    await page.wait_for_timeout(SETTLED)
    # The boot hint comes back with the state and hides the « + » while it is up.
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(ACTED)
    return answer


async def main():
    journal = Journal("R-fab — « En pause » spaced like the others, the last card clears the « + »")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        errors = []
        contexts = []

        for label, state, part in (("« En pause »", FOLLOWS, "section/paused"),
                                   ("« Mis de côté »", SET_ASIDE, "section/set-aside")):
            context, page = await fresh(browser, errors)
            contexts.append(context)
            answer = await go(page, state)
            journal.check(f"the named state {state} exists", answer is None, answer or "")
            if state == SET_ASIDE:
                # The layer is reset by every named state, so the second card is set aside after it.
                await page.evaluate("""(title)=>{window.__mocks?.setAside(title);
                    window.__queries?.removeQueries({ queryKey: ["/api/acquisition/to-handle"] });}""", ALSO_ASIDE)
                await page.wait_for_timeout(SETTLED)
            await page.evaluate(FOLD, part)
            await page.wait_for_timeout(ACTED)
            gaps = await page.evaluate(FOLD_GAPS, part)
            journal.check(f"{label} holds at least two cards to measure", len(gaps) >= 1, str(gaps))
            if state == FOLLOWS:
                ordinary = await page.evaluate(ORDINARY)
                journal.check("an ordinary section's two cards are measured", ordinary is not None and ordinary > 0, str(ordinary))
            journal.check(f"{label}: the gap between two cards is the ordinary section's ({ordinary}px)",
                          bool(gaps) and all(gap == ordinary for gap in gaps), str(gaps))

        ended_on_resolve = False
        for label, state, sort in PAGES:
            context, page = await fresh(browser, errors)
            contexts.append(context)
            answer = await go(page, state)
            journal.check(f"the named state {state} exists", answer is None, answer or "")
            try:
                await page.wait_for_function("()=>document.querySelector('#fab') && !document.querySelector('#fab').hidden", timeout=3000)
            except Exception:  # the check below says it, with the reading
                pass
            if sort == "open-paused":
                await page.evaluate(FOLD, "section/paused")
                await page.wait_for_timeout(ACTED)
            elif sort is not None:
                await page.evaluate("(filter)=>window.__store.write({ todoFilter: filter })", sort)
                await page.wait_for_timeout(SETTLED)
            await to_the_bottom(page)
            reading = await page.evaluate(BOTTOM)
            journal.check(f"« {label} »: the « + » is drawn and the page holds cards",
                          reading["fab"] is not None and reading["last"] is not None, str(reading))
            if reading["fab"] is None or reading["last"] is None:
                continue
            journal.check(f"« {label} »: at full scroll the last card does not touch the « + »",
                          not meets(reading["last"], reading["fab"]) and reading["last"]["bottom"] <= reading["fab"]["top"] + 0.5
                          or reading["last"]["right"] <= reading["fab"]["left"],
                          f"card bottom {reading['last']['bottom']}, « + » top {reading['fab']['top']}")
            if state == TODO and reading["lastResolve"]:
                ended_on_resolve = True
                journal.check("« À traiter »: the last « Résoudre » is whole in the window, off the « + », and a tap lands on it",
                              reading["resolve"] is not None
                              and reading["resolve"]["top"] >= 0 and reading["resolve"]["bottom"] <= reading["view"]
                              and not meets(reading["resolve"], reading["fab"]) and reading["tapped"] == "resolve",
                              f"{reading['resolve']}, tap → {reading['tapped']}")

        journal.check("« À traiter » filtered on « Résoudre » ends the list on a card that carries « Résoudre »", ended_on_resolve)
        journal.check("no JS error", not errors, str(errors))
        for context in contexts:
            await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
