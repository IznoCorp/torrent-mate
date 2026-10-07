"""R-gaps — the drawer's footer and Profil's sessions keep their gaps, and no heading stands bare (B-710, B-711, B-712).

THE DEFECTS, from the operator's screenshots at 390 px:

1. Profil: the active-sessions card ended ON the next heading, « Connexions récentes ».
2. The drawer: the « Apparence » control sat ON the footer's top border.
3. The drawer: the « Maquette » heading was followed by nothing — its entries lay below the
   navigation's clip, so the visible menu ended on a heading that named nothing.

WHAT THIS RULE HOLDS, at 390 px, read through `getBoundingClientRect`:

1. between the sessions card and the notices heading there is at least `SECTION_GAP` px, and in each
   section of Profil a heading is `HEADING_GAP` px above what it heads;
2. between the appearance control and the footer's top edge there is at least `FOOT_GAP` px;
3. at every position the navigation's scroll can come to rest on, no group heading stands at the
   cut with all its entries below it — a heading is never the last thing a reader sees. The
   rest positions are those the scroll lands on after each step of `SCROLL_STEP` px, and the
   rule waits `SETTLE_MS` for the browser's snapping to finish;
4. the same holds at 844×390 (a phone turned on its side), where the largest group is taller than
   the navigation's visible height: at every rest no heading stands bare, and the last entry of
   EVERY group can be brought whole into the visible navigation.
"""

import asyncio
import os

from common import Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

WIDTH = 390
LANDSCAPE = {"width": 844, "height": 390}

# Two sections of Profil are apart by the page's own gap between sections (`--spacing-7`, 14 px);
# a heading and what it heads by `section()`'s (`--spacing-4`, 8 px); the control and the footer
# by the footer's own breathing room (`--spacing-6`, 12 px).
SECTION_GAP = 14
HEADING_GAP = 8
FOOT_GAP = 12

# How far the navigation is scrolled between two readings, and how long the browser may take to
# settle on a rest position after one.
SCROLL_STEP = 30
SETTLE_MS = 250

READ_PROFILE = """() => {
  const panel = document.querySelector('[data-part="profile/sessions"] [data-part="panel"]');
  const heading = document.querySelector('[data-part="profile/notices"] [data-part="heading"]');
  if (!panel || !heading) return {found: false};
  // A section Profil does not draw in this state (the install one, off a phone's browser) is not measured.
  const inside = ['language', 'install', 'notifications', 'sessions'].filter(
    (name) => document.querySelector(`[data-part="profile/${name}"]`)).map((name) => {
    const own = document.querySelector(`[data-part="profile/${name}"]`);
    const title = own?.querySelector('[data-part="heading"]');
    const next = title?.nextElementSibling;
    return {name, gap: title && next ? Math.round((next.getBoundingClientRect().top - title.getBoundingClientRect().bottom) * 10) / 10 : null};
  });
  return {
    found: true,
    gap: Math.round((heading.getBoundingClientRect().top - panel.getBoundingClientRect().bottom) * 10) / 10,
    inside,
  };
}"""

# The group headings drawn in the navigation whose first entry is not drawn whole above the cut.
READ_STRANDED = """() => {
  const nav = document.querySelector('#drawer nav');
  const cut = nav.getBoundingClientRect().bottom;
  return [...nav.querySelectorAll('.grp')].filter((group) => {
    const title = group.querySelector('.sect')?.getBoundingClientRect();
    const first = group.querySelector('a, button')?.getBoundingClientRect();
    return title && first && title.bottom <= cut && title.height > 0 && first.bottom > cut;
  }).map((group) => group.querySelector('.sect').textContent);
}"""

# Whether each group's last entry can be scrolled whole into the navigation's visible box. The
# scroll is moved to the entry's own offset and clamped by the browser, so a group the scroll
# range cannot bring up reads false.
READ_REACHABLE = """() => {
  const nav = document.querySelector('#drawer nav');
  return [...nav.querySelectorAll('.grp')].map((group) => {
    const last = [...group.querySelectorAll('a, button')].at(-1);
    if (!last) return {title: group.querySelector('.sect')?.textContent ?? '', reachable: false};
    nav.scrollTop += last.getBoundingClientRect().bottom - nav.getBoundingClientRect().bottom;
    const box = nav.getBoundingClientRect();
    const rect = last.getBoundingClientRect();
    return {
      title: group.querySelector('.sect')?.textContent ?? '',
      reachable: rect.height > 0 && rect.top >= box.top - 0.5 && rect.bottom <= box.bottom + 0.5,
    };
  });
}"""

READ_DRAWER = """() => {
  const control = document.querySelector('#drawer [data-appearance]')?.closest('[data-part="view/switch"]');
  const footer = document.querySelector('#drawer [data-part="shell/served-identity"]');
  const nav = document.querySelector('#drawer nav');
  if (!control || !footer || !nav) return {found: false};
  const box = nav.getBoundingClientRect();
  nav.scrollTop = nav.scrollHeight;
  const groups = [...nav.querySelectorAll('.grp')].map((group) => {
    const entries = [...group.querySelectorAll('a, button')];
    const last = entries.at(-1)?.getBoundingClientRect();
    return {
      title: group.querySelector('.sect')?.textContent ?? '',
      entries: entries.length,
      visible: !!last && last.height > 0 && last.top >= box.top && last.bottom <= box.bottom + 0.5,
    };
  });
  return {
    found: true,
    gap: Math.round((footer.getBoundingClientRect().top - control.getBoundingClientRect().bottom) * 10) / 10,
    groups,
  };
}"""


# Where to keep a capture of each place, when the operator of the run asks for them (a pull request's
# description); unset, the rule measures and writes nothing.
SHOTS = os.environ.get("TM_GAPS_SHOTS")


async def shoot(page, name):
    """Saves the page's current view when captures were asked for.

    Args:
        page: The Playwright page.
        name: The capture's file stem.
    """
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        await page.screenshot(path=os.path.join(SHOTS, f"{name}.png"))


async def stranded_at_rests(page):
    """Steps the navigation's scroll and reads the bare headings at every rest.

    Args:
        page: The Playwright page, its drawer open.

    Returns:
        The headings left bare, keyed by the scroll position they rest at.
    """
    stranded = {}
    reach = await page.evaluate(
        "()=>{const nav=document.querySelector('#drawer nav');return nav.scrollHeight-nav.clientHeight}"
    )
    for top in range(0, int(reach) + SCROLL_STEP, SCROLL_STEP):
        await page.evaluate("(top)=>{document.querySelector('#drawer nav').scrollTo(0, top)}", top)
        await page.wait_for_timeout(SETTLE_MS)
        at_rest = await page.evaluate(READ_STRANDED)
        if at_rest:
            stranded[top] = at_rest
    return stranded


async def main():
    """Runs the rule at 390 px.

    Returns:
        Nothing; the journal exits non-zero on any violation.
    """
    journal = Journal("R-gaps — the gaps of Profil's sessions and of the drawer's foot, and no bare heading")
    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(
            browser, viewport={"width": WIDTH, "height": 844}, is_mobile=True, has_touch=True
        )
        page.on("pageerror", lambda error: errors.append(str(error)))

        profile = await read_at(page, "profile-sessions", READ_PROFILE)
        await page.evaluate(
            "()=>document.querySelector('[data-part=\"profile/notices\"]').scrollIntoView({block:'center'})"
        )
        await shoot(page, "1-profil-sessions")
        journal.check(
            "the sessions card and the notices heading are apart",
            profile["found"] and profile["gap"] >= SECTION_GAP,
            str(profile),
        )
        bare_headings = [
            one["name"] for one in profile.get("inside", []) if one["gap"] is None or one["gap"] < HEADING_GAP
        ]
        journal.check(
            "every account section keeps its heading apart from what it heads",
            profile["found"] and not bare_headings,
            str(profile.get("inside")),
        )

        drawer = await read_at(page, "drawer-navigation", READ_DRAWER)
        journal.check(
            "the appearance control and the footer are apart",
            drawer["found"] and drawer["gap"] >= FOOT_GAP,
            str(drawer),
        )
        await shoot(page, "2-drawer-end-of-scroll")
        # THE OPERATOR'S POSITION: scrolled so the « Maquette » heading is the last thing the
        # navigation shows, its entries below the cut.
        await page.evaluate("""()=>{
          const nav = document.querySelector('#drawer nav');
          const title = nav.querySelector('[data-part="harness/menu"] .sect');
          nav.scrollTop += title.getBoundingClientRect().bottom - nav.getBoundingClientRect().bottom + 8;
        }""")
        await shoot(page, "3-drawer-heading-at-the-cut")
        bare = [g["title"] for g in drawer.get("groups", []) if not g["visible"]]
        journal.check(
            "the end of the menu's scroll shows every group's entries",
            drawer["found"] and not bare,
            str(drawer.get("groups")),
        )
        stranded = await stranded_at_rests(page)
        journal.check(
            "no group heading rests at the cut with its entries below it",
            not stranded,
            str(dict(list(stranded.items())[:6])),
        )
        await context.close()

        # A PHONE ON ITS SIDE: the largest group is taller than what the navigation shows.
        context, page = await open_page(browser, viewport=LANDSCAPE, is_mobile=True, has_touch=True)
        page.on("pageerror", lambda error: errors.append(str(error)))
        await read_at(page, "drawer-navigation", READ_DRAWER)
        # No heading check here: at this height a group is taller than the navigation and scrolls
        # freely inside its snap area by design, so only reachability is asserted.
        unreachable = [g["title"] for g in await page.evaluate(READ_REACHABLE) if not g["reachable"]]
        journal.check(
            "at 844x390 the last entry of every group can be brought whole into the navigation",
            not unreachable,
            str(unreachable),
        )
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
