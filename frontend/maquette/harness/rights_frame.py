"""R421 — the frame is composed by rights: the bar, the menu's badge, the drawer, a place not held (§ 17).

DESIGN maquette-l18 § 3.2, § 3.3, § 5 (R-L18-d, R-L18-e, R-L18-f, R-L18-y), ruling 22's precision.

1. R-L18-d — THE BAR DRAWS EXACTLY THE PAGES THE ACCOUNT OPENS, in the table's order:
   four for the owner, three for a household member and a Plex guest (Acquisition,
   Médiathèque, Découvrir), and NO bar at all for a Default-only account — one page is no
   bar. A page the account does not open is ABSENT from the bar's DOM, never disabled.
2. R-L18-e — THE BADGES COUNT BY RIGHTS: the same seeded Système fault gives the owner a
   badge on the menu button and a household member none; in the drawer every entry is
   drawn, and a MARKED one carries no count.
3. R-L18-f / R-L18-y — A PLACE NOT HELD EXPLAINS ITSELF: tapped from the drawer, Système and
   Maintenance render the reserved form — the right that is missing, who holds it by
   default — and never the page.
4. Ruling 22 — A ROLE THAT OPENS NO PAGE lands on its own page: sign-out only, no bar, no
   menu button.

WHAT IT DOES NOT READ: the refusal side (R280); a cold address typed as another identity,
which the mock cannot hold across a reload (its dials reset with the document).
"""
import asyncio
import pathlib
import re

from common import SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
TABLE = (SOURCE / "app/navigation.ts").read_text(encoding="utf-8")
IN_BAR = [identifier for identifier, flag
          in re.findall(r'\bid: "([^"]+)",.*?\binBar: (true|false)', TABLE, re.S) if flag == "true"]
ACQUISITION_SIDE = ["acq", "lib", "discover"]
RESERVED = ["trackers", "sys", "maint", "cfg", "accounts"]

BAR = """() => {
  const bar = document.querySelector('#nav');
  return { shown: !!bar && bar.checkVisibility(),
           pages: [...document.querySelectorAll('#nav button[data-page]')].map((one) => one.dataset.page) };
}"""
MENU_BADGE = "() => document.querySelector('[data-part=\"shell/menu-badge\"]')?.textContent || null"
DRAWER = """() => [...document.querySelectorAll('[data-navgo]')].map((entry) => ({
  page: entry.dataset.navgo, reserved: entry.hasAttribute('data-reserved'),
  count: entry.querySelector('[data-part="shell/drawer-count"]')?.textContent || null }))"""
RESERVED_FORM = """() => {
  const form = document.querySelector('#view [data-part="access/reserved"]');
  return { right: form?.dataset.right || null, text: form?.textContent || '',
           page: document.querySelector('#view [data-region]')?.textContent.length || 0 };
}"""


async def main():
    journal = Journal("R421 — the frame is composed by rights")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def go(state):
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)

        await go("drawer-navigation")
        owner = await page.evaluate(BAR)
        journal.check("R-L18-d: the owner's bar draws every bar page, in the table's order",
                      owner["pages"] == IN_BAR, str(owner))
        for state in ("bar-household", "bar-guest"):
            await go(state)
            bar = await page.evaluate(BAR)
            journal.check(f"R-L18-d: {state} draws Acquisition, Médiathèque, Découvrir — Trackers absent",
                          bar["shown"] and bar["pages"] == ACQUISITION_SIDE, str(bar))
        await go("bar-rightless")
        bare = await page.evaluate(BAR)
        journal.check("R-L18-d: a Default-only account draws no bar at all — one page is no bar",
                      not bare["shown"] and not bare["pages"], str(bare))

        await go("menu-system-badge")
        owner_badge = await page.evaluate(MENU_BADGE)
        await page.evaluate("""async () => { window.__mocks.setIdentity('household-member');
          await window.__queries.invalidateQueries({ queryKey: ['/api/auth/me'] }); }""")
        await page.wait_for_timeout(SETTLED)
        member_badge = await page.evaluate(MENU_BADGE)
        journal.check("R-L18-e: one Système fault badges the owner's menu and not a household member's",
                      owner_badge and not member_badge, f"owner {owner_badge}, member {member_badge}")

        await go("drawer-household")
        entries = await page.evaluate(DRAWER)
        marked = sorted(one["page"] for one in entries if one["reserved"])
        journal.check("R-L18-f: the drawer draws Trackers, Système, Maintenance, Réglages, Comptes MARKED",
                      marked == sorted(RESERVED), str(marked))
        counted = [one["page"] for one in entries if one["reserved"] and one["count"]]
        journal.check("R-L18-e: a marked entry carries no count", not counted, str(counted))
        journal.check("R-L18-d: the drawer holds no page the account lacks and hiding cannot mislead about",
                      not [one for one in entries if one["page"] not in ACQUISITION_SIDE + RESERVED], str(entries))

        await page.click('[data-navgo="maint"]')
        await page.wait_for_timeout(SETTLED)
        opened = await page.evaluate(RESERVED_FORM)
        journal.check("R-L18-y: Maintenance, tapped from the drawer, draws the reserved form, not the page",
                      opened["right"] == "system.view", str(opened))
        await go("place-reserved")
        reserved = await page.evaluate(RESERVED_FORM)
        words = await page.evaluate("(key)=>window.__i18n?.t(key) ?? null", "access.rights.system.view")
        journal.check("R-L18-f: Système names the right it lacks and who holds it by default",
                      reserved["right"] == "system.view" and words and words in reserved["text"]
                      and "Admin" in reserved["text"], reserved["text"][:160])

        await go("no-access")
        lone = await page.evaluate("""() => ({
          bar: document.querySelector('#nav')?.checkVisibility() || false,
          menu: document.querySelector('[data-part="shell/header"] [data-drawer]')?.checkVisibility() || false,
          signOut: !!document.querySelector('#view [data-signout]'),
          acts: document.querySelectorAll('#view button').length })""")
        journal.check("ruling 22: a role that opens no page draws its own page — sign-out only, no bar, no menu",
                      not lone["bar"] and not lone["menu"] and lone["signOut"] and lone["acts"] == 1, str(lone))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
