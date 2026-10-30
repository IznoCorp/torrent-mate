"""R426 — Profil is the connected account: its role, what it can do, and why not the rest (§ 17; ruling 14).

DESIGN maquette-l18 § 3.8, § 5 (R-L18-p, R-L18-z).

1. R-L18-p — THE ROLE IS READ, NEVER PRINTED: signed in as a household member and as a guest,
   Profil and the account menu each show the role the server answered — two identities, two
   names — and Profil draws no place for the other accounts.
2. R-L18-z — THE LIST IS THE MODEL'S: the rights listed as held are exactly the role's; every
   right lacking is listed with who holds it by default, never a role compared.
3. THE CEILING, ON PROFIL: under preprod's list the deletion is lacking « on this instance »,
   named, and the rest is held.
"""
import asyncio
import json
import pathlib

from common import SETTLED, PANEL_IN, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
SEEDS = json.loads((SOURCE / "mocks/seeds/accounts.json").read_text(encoding="utf-8"))
# The test roster (roles a manager might have created) joins the seeded one for the states
# that sign a test account in.
ROLE_OF = {one["id"]: next(role for role in SEEDS["roles"] + SEEDS["testRoles"] if role["id"] == one["role"])
           for one in SEEDS["accounts"] + SEEDS["testAccounts"]}
STATES = {"profile-household": "household-member", "profile-guest": "guest"}

READ = """() => ({
  role: document.querySelector('[data-part="profile/role"] [data-part="flux/value"]')?.textContent || null,
  held: [...document.querySelectorAll('[data-part="profile/right-held"] [data-part="flux/name"]')].map((one) => one.textContent),
  lacking: [...document.querySelectorAll('[data-part="profile/right-lacking"]')].map((one) => ({
    name: one.querySelector('[data-part="flux/name"]').textContent,
    why: one.querySelector('[data-part="flux/detail"]')?.textContent || '' })),
  text: document.querySelector('#view').textContent })"""


async def main():
    journal = Journal("R426 — Profil is the connected account")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        label = lambda right: page.evaluate("(k)=>window.__i18n.t(k)", f"access.rights.{right}")  # noqa: E731

        names = []
        for state, identity in STATES.items():
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            read = await page.evaluate(READ)
            role = ROLE_OF[identity]
            names.append(read["role"])
            # A seeded role carries no name: the interface says the translation of its id.
            said = role.get("name") or await page.evaluate("(id)=>window.__i18n.t('roles.seed.' + id)", role["id"])
            journal.check(f"R-L18-p: {state} shows the role the server answered", read["role"] == said,
                          f"{read['role']} / {said}")
            wanted = sorted([await label(right) for right in role["rights"]])
            journal.check(f"R-L18-z: {state} lists as held exactly its role's rights", sorted(read["held"]) == wanted,
                          f"{len(read['held'])} held, {len(wanted)} carried")
            unexplained = [one["name"] for one in read["lacking"] if not one["why"]]
            journal.check(f"R-L18-z: {state} says who holds every right it lacks", read["lacking"] and not unexplained,
                          str(unexplained))
            journal.check(f"R-L18-p: {state} draws no place for the other accounts",
                          "autres comptes" not in read["text"].lower())
            await page.evaluate("()=>window.__panel.produce('account')")
            await page.wait_for_timeout(PANEL_IN)
            menu = await page.evaluate("()=>document.querySelector('#sheet')?.textContent || ''")
            journal.check(f"R-L18-p: {state}'s account menu names its role", said in menu, menu[:80])
        journal.check("R-L18-p: two identities, two role names — nothing printed as a constant",
                      len(set(names)) == 2, str(names))

        await page.evaluate("()=>window.__go('profile-preprod')")
        await page.wait_for_timeout(SETTLED)
        read = await page.evaluate(READ)
        removal = await label("library.delete")
        lacking = {one["name"]: one["why"] for one in read["lacking"]}
        journal.check("preprod: deleting from the library is lacking, on this instance, for everyone",
                      "instance" in lacking.get(removal, ""), str(lacking))
        journal.check("preprod: every other right is held", len(read["held"]) == len(SEEDS["roles"][0]["rights"]) or
                      len(read["lacking"]) == 1, f"{len(read['held'])} held, {len(read['lacking'])} lacking")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
