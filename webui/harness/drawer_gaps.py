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
3. every group heading of the open menu has, at the end of the navigation's scroll, an entry below
   it that is inside the navigation's visible box — a heading is never the last thing a reader sees.
"""
import asyncio
import os

from common import Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

WIDTH = 390

# Two sections of Profil are apart by the page's own gap between sections (`--spacing-7`, 14 px);
# a heading and what it heads by `section()`'s (`--spacing-4`, 8 px); the control and the footer
# by the footer's own breathing room (`--spacing-6`, 12 px).
SECTION_GAP = 14
HEADING_GAP = 8
FOOT_GAP = 12

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
            browser, viewport={"width": WIDTH, "height": 844}, is_mobile=True, has_touch=True)
        page.on("pageerror", lambda error: errors.append(str(error)))

        profile = await read_at(page, "profile-sessions", READ_PROFILE)
        await page.evaluate("()=>document.querySelector('[data-part=\"profile/notices\"]').scrollIntoView({block:'center'})")
        await shoot(page, "1-profil-sessions")
        journal.check("the sessions card and the notices heading are apart",
                      profile["found"] and profile["gap"] >= SECTION_GAP, str(profile))
        bare_headings = [one["name"] for one in profile.get("inside", []) if one["gap"] is None or one["gap"] < HEADING_GAP]
        journal.check("every account section keeps its heading apart from what it heads",
                      profile["found"] and not bare_headings, str(profile.get("inside")))

        drawer = await read_at(page, "drawer-navigation", READ_DRAWER)
        journal.check("the appearance control and the footer are apart",
                      drawer["found"] and drawer["gap"] >= FOOT_GAP, str(drawer))
        await shoot(page, "2-drawer-appearance-footer")
        bare = [g["title"] for g in drawer.get("groups", []) if not g["visible"]]
        journal.check("no group heading ends the visible menu without its entries",
                      drawer["found"] and not bare, str(drawer.get("groups")))
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
