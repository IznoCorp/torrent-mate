"""R96 — the add screen's footer announces, is legible, and can be dismissed.

B-139, reported by the operator on 2026-08-28 from a photograph: a WHITE
RECTANGLE at the bottom of a dark screen. `addFooterAction` was declared in
`features/acquisition/variants.ts` and called by nobody, so the button carried
no class at all and the browser painted it with its own defaults — light
ground, dark text. The bar is `sticky`, it covers a card, and its only exit was
that button. An exit nobody can see is not an exit, which is why the operator
read it as a notification stuck on the screen.

WHY THE ORACLE CANNOT HOLD THIS, and it is a STATE gap rather than a coverage
one. The bar paints only when `added.size > 0`. The add screen's two named
states are `acq-add-empty` and `acq-add-results`; the second searches « star
wars » and adds nothing. **No measured state has ever painted this bar**, so no
reference of the recorded oracle contains a single pixel of it. Widening
`engine/states.js` was the other route and it was refused for a written reason:
that file is the dying engine's scenario table, which L13 removes, and a repair
that grows what must die is a repair that has to be made twice.

So this rule walks the journey the operator walks — open the add screen, search,
open a result, add it — which is the register's own rule 4: *the rule must cover
the path the operator actually walks*.

WHAT IT HOLDS:

  the announcement    adding a medium raises the bar, which was absent before.
  the legibility      the action's colour is the `primary` token and its ground
                      is transparent. Measured against a PROBE carrying
                      `color: var(--color-primary)` rather than against a
                      literal: the token resolves through the theme, and a rule
                      that had to know what oklch it lands on would be a table
                      someone maintains by hand.
  the border          the variant writes `[border:0]`. A bare `<button>` has a
                      platform border, and « no border » is half of what made
                      the rectangle read as a rectangle.
  the dismissal       the operator arbitrated the bar on 2026-08-29: « elle
                      passe par-dessus, c'est une notification comme une autre,
                      elle est fermable ». So it overlays — nothing reserves its
                      space — and it closes. Its touch box is held at 44 px,
                      which is a target and not a spacing step.
  the re-announcement adding a SECOND medium raises it again. What is remembered
                      is the count it was dismissed at, never a boolean: a
                      boolean would swallow the next announcement, and a
                      notification that can be permanently silenced by dismissing
                      an earlier one is a different defect wearing this fix.

WHAT IT DOES NOT READ, said before what it does:

  - IT IS NOT THE ORACLE AND DOES NOT BECOME ONE. It reads four computed
    properties of two elements. That the bar is well drawn — its spacing, its
    ground, its separator — is measured by nothing, and saying so is the cost of
    the route taken. The gain is that no line of `engine/states.js` was written
    to obtain it.
  - IT DOES NOT READ A REAL FINGER. The clicks here are synthetic, and a
    synthetic pointer is never cancelled by the compositor. That limit belongs
    to the gesture rules, not to this one: nothing here is a drag.
  - IT SAYS NOTHING ABOUT THE COLOUR BEING RIGHT. It holds that the button wears
    the token the variant names. Whether `primary` is the correct token for this
    action is a drawing decision, and the maquette is where that is decided.
  - IT DOES NOT READ WHICH ROUTE ADDED WHAT. Both routes into `added` are
    walked — the direct add and the « replace » dialog's confirmation, which
    reach the same Set through different handlers — and each is NAMED in the
    detail line. What is not held is that a given result takes a given route:
    that is the fixture's business, and pinning it here would make this rule
    fail the day a seed changes what the library already owns.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

# The bar and its two controls, by the anchors the markup emits. `data-part` is
# the naming attribute `check-markup-contracts.py` holds both ends of, so a
# rename that moved only one end falls there before it falls here.
FOOTER = '[data-part="add/foot"]'
DISMISS = '[data-part="add/foot-dismiss"]'

# The action carries no `data-part` of its own: it is the bar's only other
# button, and giving it an anchor purely to be selected here would be a contract
# invented by its instrument. Selected by position inside the bar instead.
ACTION = f'{FOOTER} button:not({DISMISS})'

# WHICH RESULTS, and the two are chosen to take DIFFERENT routes. The seed
# `mocks/seeds/search-results.json` marks its first three `owned: true` and its
# last three `owned: false`, so one of each walks the « replace » confirmation
# and the direct add. Held rather than assumed: each route is named in its
# check's detail line, so a seed that stops distinguishing them says so on the
# run instead of quietly halving what this rule covers.
OWNED_RESULT = 0
UNOWNED_RESULT = 3

# A touch target, not a spacing step. The scale stops at 24 px, which is why the
# variant writes `size-[44px]` as an arbitrary value and says so by its shape.
TOUCH_TARGET = 44


async def open_add_screen_with_results(page):
    """Opens `/add` on a real search, the way the named state does.

    The same seam `engine/states.js` drives for `acq-add-results`, so this rule
    and that state reach the screen by one route rather than two spellings of
    it.
    """
    await page.evaluate("()=>window.__screens.add('star wars')")
    await page.wait_for_selector('[data-part="result/list"]')
    await page.wait_for_timeout(400)


async def add_one_result(page, position):
    """Walks one result all the way into `added`, through its panel.

    THE ADD ACTION IS NOT ON THE CARD. A result card opens a panel, and the
    panel carries `data-act="add:N"`. A rule that clicked the card and asserted
    the bar would fail for a reason that is not the defect, and a rule that
    wrote into the store directly would prove the bar renders and nothing about
    whether the operator can reach it.

    AND THERE ARE TWO ROUTES, which is not a detail this rule may caveat away.
    A result already in the library opens a « replace » dialog first, and its
    confirmation reaches the same `added` Set through a different handler
    (`data-confirmadd`). The first version of this rule walked one route, and the
    journey it happened to pick took the other — the bar never appeared and the
    rule failed for a reason that was not the defect. Both are walked, and which
    one a given result takes is REPORTED, because a rule that silently walks
    whichever route it meets cannot say it has held both.

    Args:
        page: The Playwright page, on the add screen with results.
        position: Which result card to open, zero-based.

    Returns:
        `"direct"` or `"replace"`, naming the route this result took.
    """
    cards = page.locator('[data-part="result/list"] [data-panel^="add:"]')
    card = cards.nth(position)
    # THE ACT IS SELECTED BY ITS OWN INDEX, never by `.first`. A panel from a
    # previous result can still be in the document, and `.first` then clicks the
    # act of a result nobody opened — which made a probe of this journey report
    # that every one of five results took the « replace » route while three of
    # them are seeded `owned: false`. A rule that picks whichever element it
    # meets first measures whichever element it meets first.
    panel = await card.get_attribute("data-panel")
    await card.click()
    act = f'[data-act="{panel}"]'
    await page.wait_for_selector(act)
    await page.locator(act).click()
    await page.wait_for_timeout(400)
    # VISIBLE, not merely present. The dialog of an earlier add stays in the
    # document once closed, so a bare `count()` finds it and this helper waits
    # to click a node nothing can click — the same defect as `.first` above,
    # one node further on: a rule that asks « is it there? » about a layer is
    # asking the wrong question, because a closed layer is still there.
    confirm = page.locator("[data-confirmadd]:visible")
    if await confirm.count():
        await confirm.first.click()
        await page.wait_for_timeout(500)
        return "replace"
    return "direct"


async def measure(page):
    """Reads what the bar and its two controls compute to.

    The action's colour is compared against a PROBE given
    `color: var(--color-primary)` and mounted in the same document, never
    against a literal. The token resolves through the theme and through the
    reader's colour scheme; a rule holding a literal would hold one theme and
    report about both.

    Returns:
        A dictionary of what was measured, or `None` where the bar is absent.
    """
    return await page.evaluate(
        """({ footer, action, dismiss }) => {
             const bar = document.querySelector(footer);
             if (!bar) return null;
             const act = document.querySelector(action);
             const shut = document.querySelector(dismiss);
             const probe = document.createElement("span");
             probe.style.color = "var(--color-primary)";
             bar.appendChild(probe);
             const wanted = getComputedStyle(probe).color;
             probe.remove();
             const actStyle = act ? getComputedStyle(act) : null;
             const shutBox = shut ? shut.getBoundingClientRect() : null;
             return {
               present: true,
               hasAction: Boolean(act),
               hasDismiss: Boolean(shut),
               color: actStyle ? actStyle.color : null,
               wanted,
               background: actStyle ? actStyle.backgroundColor : null,
               borderStyle: actStyle ? actStyle.borderTopStyle : null,
               position: getComputedStyle(bar).position,
               dismissWidth: shutBox ? Math.round(shutBox.width) : 0,
               dismissHeight: shutBox ? Math.round(shutBox.height) : 0,
             };
           }""",
        {"footer": FOOTER, "action": ACTION, "dismiss": DISMISS})


def transparent(value):
    """Says whether a computed background is genuinely no background.

    Chrome writes an unpainted background two ways depending on how it was
    asked for, and a rule that knew only one of them would go green over the
    other.

    Args:
        value: A computed `background-color`.

    Returns:
        True when nothing is painted.
    """
    return value in ("rgba(0, 0, 0, 0)", "transparent")


async def hold(journal):
    """Walks the journey and records every verdict."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))

        await open_add_screen_with_results(page)

        before = await measure(page)
        journal.check(
            "nothing is announced before anything is added",
            before is None,
            "the bar is absent on a search that added nothing — which is why "
            "no named state has ever painted it")

        first_route = await add_one_result(page, OWNED_RESULT)
        after = await measure(page)
        journal.check(
            "adding a medium announces it",
            after is not None and after["hasAction"],
            f"the bar and its action are present, reached by the "
            f"« {first_route} » route")

        if after:
            journal.check(
                "the action is painted in the primary token, not by the browser",
                after["color"] == after["wanted"],
                f"the action computes {after['color']} and "
                f"`var(--color-primary)` computes {after['wanted']} in the same "
                "document — B-139 is these two disagreeing, and the operator "
                "photographed the disagreement")
            journal.check(
                "the action has no ground of its own",
                transparent(after["background"]),
                f"its background computes {after['background']}: a bare button "
                "carries the platform's own light ground, which on a dark "
                "screen is the white rectangle")
            journal.check(
                "the action has no platform border",
                after["borderStyle"] == "none",
                f"its border-style computes {after['borderStyle']}")
            journal.check(
                "the bar overlays rather than reserving space",
                after["position"] == "sticky",
                f"it computes position: {after['position']} — arbitrated by the "
                "operator on 2026-08-29, « elle passe par-dessus, c'est une "
                "notification comme une autre »")
            journal.check(
                "the notification can be dismissed",
                after["hasDismiss"],
                "the bar carries a dismissal — the other half of the same "
                "arbitration, and what makes an overlaying bar acceptable")
            journal.check(
                "the dismissal is a touch target",
                after["dismissWidth"] >= TOUCH_TARGET
                and after["dismissHeight"] >= TOUCH_TARGET,
                f"it measures {after['dismissWidth']}x{after['dismissHeight']} "
                f"against a floor of {TOUCH_TARGET}")

            await page.locator(DISMISS).click()
            await page.wait_for_timeout(300)
            dismissed = await measure(page)
            journal.check(
                "dismissing it takes it off the screen",
                dismissed is None,
                "the bar is gone after one tap on its dismissal")

            second_route = await add_one_result(page, UNOWNED_RESULT)
            again = await measure(page)
            journal.check(
                f"a further medium is announced again (« {second_route} » route)",
                again is not None,
                "adding a second medium raises the bar the first dismissal "
                "took away — what is remembered is the COUNT it was dismissed "
                "at, never a boolean, because a boolean would swallow every "
                "announcement after the first")

            # WHERE THE ACTION LANDS, held last because it navigates away, and
            # held at all because it MOVED. `toFollows()` went to `/` with
            # `search: { page: "acq", tab: "now" }` — the page's identity in the
            # query, which D1 forbids, and to an address that is not the
            # acquisition page: `/` is the root, which the boot SETTLES onto
            # `/acquisition`. The destination was right only by way of a
            # redirect (B-051).
            if again is not None:
                await page.locator(ACTION).click()
                await page.wait_for_timeout(700)
                landed = await page.evaluate(
                    "()=>location.pathname + location.search")
                journal.check(
                    "the action lands on the page's own address, state in the query",
                    landed.startswith("/acquisition") and "tab=now" in landed
                    and "page=" not in landed,
                    f"it landed on {landed!r} — identity in the PATH, state in "
                    "the QUERY, and no redirect standing in for either")

        await context.close()
        await browser.close()
    journal.summary(errors)


def main():
    journal = Journal(
        "R96 — the add screen's footer announces, is legible, and is dismissed")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
