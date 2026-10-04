"""R428 — « Comptes »: the roster and the roles from the answer, a change that moves, and no escalation (§ 17).

DESIGN maquette-l18 § 3.9, § 5 (R-L18-s, R-L18-t, R-L18-u, R-L18-v), round 8 Q9 = B, ruling 20,
ruling 22, round 9 Q14 = A, M7, F2.

1. R-L18-s — BOTH SIDES: « Comptes » is a menu entry, MARKED for a household member and its
   page explains the right it lacks; forcing the roster answers 403.
2. R-L18-t — FROM THE ANSWER: one row per account, its role by the served name (Admin by its
   kind, gap G-10); one row per role, the five the operator seeded (O-K1-4); Admin's role panel
   offers nothing.
3. R-L18-u — A CHANGE MOVES, AND REACHES THE ACCOUNT: giving `trackers.view` to the household
   role through its panel calls updateRole, and a household member signed in afterwards has
   Trackers in its bar. Demoting the last Admin answers 409.
4. R-L18-u (M7) — NO ESCALATION: a manager who is not Admin sees no Admin account, sees the roles
   beyond its own greyed, and forcing one, or touching its own role, answers 403.
5. R-L18-v — A NEW ACCOUNT, on its own page (R525): without an e-mail it is said at the field and
   nothing is asked; created with one that is a user of the managed server, linked to Plex on the
   role its kind starts on (O-K1-4).
"""
import asyncio
import json
import pathlib

from common import SETTLED, PANEL_IN, ACTED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
SEEDS = json.loads((SOURCE / "mocks/seeds/accounts.json").read_text(encoding="utf-8"))
OWNER = json.loads((SOURCE / "mocks/seeds/account.json").read_text(encoding="utf-8"))

ROWS = """() => ({
  accounts: [...document.querySelectorAll('[data-part="accounts/account"]')].map((one) => ({
    name: one.querySelector('[data-part="flux/name"]').textContent,
    role: one.querySelector('[data-part="flux/value"]').textContent })),
  roles: [...document.querySelectorAll('[data-part="accounts/role"] [data-part="flux/name"]')].map((one) => one.textContent) })"""
ACTS = """(attribute) => [...document.querySelectorAll('#sheet [' + attribute + ']')].map((one) => ({
  value: one.getAttribute(attribute), off: one.disabled || one.hasAttribute('aria-disabled') || one.hasAttribute('data-disabled') }))"""
CALL = """async ([who, method, path, body]) => { if (who) window.__mocks.setIdentity(who);
  return (await fetch(path, { method, body: body === null ? undefined : JSON.stringify(body) })).status; }"""


async def main():
    journal = Journal("R428 — « Comptes »")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def go(state, wait=SETTLED):
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(wait)

        await go("drawer-household")
        marked = await page.evaluate("()=>document.querySelector('[data-navgo=\"accounts\"]')?.hasAttribute('data-reserved')")
        journal.check("R-L18-s: « Comptes » is in a household member's menu, MARKED", marked is True, str(marked))
        await go("accounts-forbidden")
        right = await page.evaluate("()=>document.querySelector('[data-part=\"access/reserved\"]')?.dataset.right")
        journal.check("R-L18-s: opened, it names the right it lacks", right == "accounts.manage", str(right))
        forced = await page.evaluate(CALL, [None, "GET", "/api/v1/accounts", None])
        journal.check("R-L18-s: forcing the roster answers 403", forced == 403, str(forced))

        await go("accounts-roster")
        rows = await page.evaluate(ROWS)
        every = [OWNER] + SEEDS["accounts"]
        # A seeded role carries no name: the interface says the translation of its id.
        role_name = {role["id"]: await page.evaluate("(id)=>window.__i18n.t('roles.seed.' + id)", role["id"])
                     for role in SEEDS["roles"]}
        journal.check("R-L18-t: one row per account, in the answer's order",
                      [one["name"] for one in rows["accounts"]] == [one["name"] for one in every], str(rows["accounts"]))
        owner = next(one for one in rows["accounts"] if one["name"] == OWNER["name"])
        admin_words = await page.evaluate("()=>window.__i18n.t('roles.seed.admin')")
        journal.check("G-10: the Admin role is named by its kind, from fr.json", owner["role"] == admin_words, str(owner))
        others = [one for one in rows["accounts"] if one["name"] != OWNER["name"]]
        journal.check("R-L18-t: every other account shows its role's served name",
                      all(one["role"] in role_name.values() for one in others), str(others))
        journal.check("R-L18-t: one row per role", rows["roles"] == [role_name[role["id"]] for role in SEEDS["roles"]], str(rows["roles"]))
        await page.evaluate("()=>window.__panel.produce('role', 'admin')")
        await page.wait_for_timeout(PANEL_IN)
        journal.check("R-L18-t: the Admin role offers nothing to change",
                      not await page.evaluate(ACTS, "data-role-right"))

        await go("accounts-roles", PANEL_IN + SETTLED)
        grant = await page.evaluate("""()=>document.querySelector('#sheet [data-role-right="household|trackers.view|true"]')""")
        journal.check("R-L18-u: the household role's panel offers « Donner : voir les trackers »", grant is not None)
        await page.click('#sheet [data-role-right="household|trackers.view|true"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        called = await page.evaluate("()=>window.__mocks.answered().filter((one)=>one.operationId==='updateRole').map((one)=>one.status)")
        journal.check("R-L18-u: the tap calls updateRole", called == [200], str(called))
        await page.evaluate("""async () => { window.__mocks.setIdentity('household-member');
          await window.__queries.resetQueries({ queryKey: ['/api/v1/auth/me'] }); }""")
        await page.wait_for_timeout(SETTLED)
        bar = await page.evaluate("()=>[...document.querySelectorAll('#nav button[data-page]')].map((one)=>one.dataset.page)")
        journal.check("R-L18-u: a household member, read again, now has Trackers in its bar", "trackers" in bar, str(bar))

        await go("accounts-roster")
        last = await page.evaluate(CALL, [None, "PATCH", f"/api/v1/accounts/{OWNER['id']}", {"role": "household"}])
        journal.check("R-L18-u (F2): demoting the last Admin answers 409", last == 409, str(last))

        await go("accounts-escalation-greyed", PANEL_IN + SETTLED)
        rows = await page.evaluate(ROWS)
        journal.check("M7: a manager who is not Admin sees no Admin account",
                      OWNER["name"] not in [one["name"] for one in rows["accounts"]], str(rows["accounts"]))
        acts = await page.evaluate(ACTS, "data-account-role")
        greyed = {one["value"].split("|")[1] for one in acts if one["off"]}
        journal.check("Q14 = A: the roles beyond the manager's own are greyed, Admin's among them",
                      {"admin", "household"} <= greyed and "local-guest" not in greyed, str(sorted(greyed)))
        up = await page.evaluate(CALL, [None, "PATCH", "/api/v1/accounts/household-member", {"role": "household-sees-all"}])
        own = await page.evaluate(CALL, [None, "PATCH", "/api/v1/roles/spectator", {"rights": ["library.read"]}])
        admin = await page.evaluate(CALL, [None, "PATCH", f"/api/v1/accounts/{OWNER['id']}", {"role": "local-guest"}])
        journal.check("Q14 = A / M7: forcing a wider role, its own role or an Admin account answers 403",
                      (up, own, admin) == (403, 403, 403), str((up, own, admin)))

        await go("accounts-create-refused", SETTLED + 600)
        refusal = await page.evaluate("()=>document.querySelector('[data-field-error=\"email\"]')?.textContent")
        closed = await page.evaluate("()=>document.querySelector('[data-part=\"creation/submit\"]')?.disabled")
        created = await page.evaluate("()=>window.__mocks.answered().filter((one)=>one.operationId==='createAccount').length")
        journal.check("R-L18-v: a new account without an e-mail is said at its field, Create closed, and nothing is asked",
                      refusal and closed is True and created == 0, f"{refusal} / {closed} / {created} calls")
        forced = await page.evaluate(CALL, [None, "POST", "/api/v1/accounts", {"name": "Maya", "email": "", "role": "local-guest"}])
        journal.check("R-L18-v: forced without an e-mail, the creation answers 400", forced == 400, str(forced))
        # A REAL ARRIVAL ON « COMPTES », by the menu: the page the creation returns to is
        # under it in history — a named state writes none.
        await go("lib-grid")
        await page.click("[data-drawer]")
        await page.wait_for_timeout(PANEL_IN)
        await page.click('#drawer [data-navgo="accounts"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        await page.click('#view [data-part="accounts/account-create"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        await page.fill('[data-part="creation/form"] [name="name"]', "Maya")
        await page.fill('[data-part="creation/form"] [name="email"]', SEEDS["plexUsers"][0])
        await page.select_option('[data-part="creation/form"] [name="role"]', "local-guest")
        await page.click('[data-part="creation/submit"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        roster = await page.evaluate("async()=>(await (await fetch('/api/v1/accounts')).json()).accounts")
        newcomer = next((one for one in roster if one["name"] == "Maya"), None)
        journal.check("R-L18-v: an e-mail that is a user of the server links it, on the role its kind starts on",
                      newcomer is not None and newcomer["role"]["id"] == "plex-guest" and newcomer["signInKind"] == "plex",
                      str(newcomer))
        rows = await page.evaluate(ROWS)
        journal.check("R-L18-v: the roster draws it", "Maya" in [one["name"] for one in rows["accounts"]])

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
