"""R524 — « Comptes »: an Admin cuts an account's access, and the account is signed out at once (§ 17).

The operator, 2026-10-04: « Je dois aussi pouvoir en tant qu'admin couper l'accès à des utilisateurs, même si
c'est des utilisateurs Plex qui se connecte par SSO. Via un toggle qui par défaut est actif » — and « si on n'a
pas le droit l'interface ne devrait pas permettre de le faire ; la protection sert pour les appels API directs ».
His rulings: Q4 = A (cutting ends every session of the account, and every later sign-in is refused), Q5 = A (any
account but the owner and the acting Admin's own; Admin only).

1. THE ADMIN SEES ONE SWITCH PER ACCOUNT, ON by default; the owner's row greyed, with its reason.
2. A SECOND ADMIN sees its own row greyed with its reason, and the owner's; forcing its own answers 403.
3. A MANAGER WHO IS NOT ADMIN sees no switch at all; forcing one answers 403 — the Admin check first, before
   the account is even looked up.
4. CUTTING an account calls `setAccountAccess`, marks its row, and the account's next request lands on the
   sign-in gate; its password sign-in and its Plex sign-in are refused « access disabled ».
5. TURNING IT BACK ON lets the account sign in again.
"""
import asyncio
import json
import pathlib

from common import SETTLED, PANEL_IN, ACTED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
SEEDS = json.loads((SOURCE / "mocks/seeds/accounts.json").read_text(encoding="utf-8"))
OWNER = json.loads((SOURCE / "mocks/seeds/account.json").read_text(encoding="utf-8"))
LOCAL = next(one for one in SEEDS["accounts"] if one["id"] == "local-account")
LINKED = next(one for one in SEEDS["accounts"] if one["id"] == "household-member")

SWITCHES = """() => [...document.querySelectorAll('[data-part="accounts/account"]')].map((row) => {
  const toggle = row.querySelector('[data-part="accounts/access"]');
  return { id: row.dataset.account, access: row.dataset.access, cut: row.querySelector('[data-part="accounts/cut"]') !== null,
    toggle: toggle === null ? null : { on: toggle.getAttribute('aria-checked') === 'true', off: toggle.disabled },
    locked: row.querySelector('[data-part="accounts/access-locked"]')?.dataset.reason ?? null };
})"""
CALL = """async ([method, path, body]) => {
  const answer = await fetch(path, { method, body: body === null ? undefined : JSON.stringify(body) });
  const read = await answer.json().catch(() => ({}));
  return { status: answer.status, code: read.code ?? null }; }"""
GATE = "()=>document.querySelector('#login')?.hidden === false"


async def main():
    journal = Journal("R524 — « Comptes »: an Admin cuts an account's access")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        words = lambda key: page.evaluate("(k)=>window.__i18n.t(k)", key)  # noqa: E731

        async def go(state, wait=SETTLED):
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(wait)

        def row(rows, account):
            return next((one for one in rows if one["id"] == account), None)

        def greyed(one, reason):
            return one is not None and one["toggle"] is not None and one["toggle"]["off"] and one["locked"] == reason

        # 1. The Admin's view.
        await go("accounts-roster")
        rows = await page.evaluate(SWITCHES)
        journal.check("1: the Admin sees one switch per account",
                      rows and all(one["toggle"] is not None for one in rows), str(rows))
        journal.check("1: every switch is ON by default (sign-in allowed)",
                      rows and all(one["toggle"] and one["toggle"]["on"] for one in rows), str(rows))
        owner = row(rows, OWNER["id"])
        journal.check("1: the owner's switch is greyed, with its reason",
                      greyed(owner, "owner"), str(owner))
        others = [one for one in rows if one["id"] != OWNER["id"]]
        journal.check("1: every other account's switch may be pressed",
                      others and all(one["toggle"] is not None and not one["toggle"]["off"] and not one["locked"] for one in others), str(others))
        forced = await page.evaluate(CALL, ["PUT", f"/api/v1/accounts/{OWNER['id']}/access", {"signInAllowed": False}])
        journal.check("1: forcing the owner's cut answers 403 account.owner_access",
                      forced == {"status": 403, "code": "account.owner_access"}, str(forced))

        # 2. A second Admin's view: its own row.
        await go("accounts-access-own")
        rows = await page.evaluate(SWITCHES)
        own = row(rows, LOCAL["id"])
        journal.check("2: a second Admin's own switch is greyed, with its reason",
                      greyed(own, "own"), str(own))
        owner = row(rows, OWNER["id"])
        journal.check("2: and the owner's, with the owner's reason",
                      greyed(owner, "owner"), str(owner))
        forced = await page.evaluate(CALL, ["PUT", f"/api/v1/accounts/{LOCAL['id']}/access", {"signInAllowed": False}])
        journal.check("2: forcing its own cut answers 403 account.own_access",
                      forced == {"status": 403, "code": "account.own_access"}, str(forced))

        # 3. A manager who is not Admin.
        await go("accounts-escalation-greyed", PANEL_IN + SETTLED)
        rows = await page.evaluate(SWITCHES)
        journal.check("3: a manager who is not Admin sees the roster, and no switch at all",
                      rows and all(one["toggle"] is None and one["locked"] is None for one in rows), str(rows))
        forced = await page.evaluate(CALL, ["PUT", f"/api/v1/accounts/{LINKED['id']}/access", {"signInAllowed": False}])
        unknown = await page.evaluate(CALL, ["PUT", "/api/v1/accounts/nobody/access", {"signInAllowed": False}])
        journal.check("3: forcing a cut answers 403 account.access_admin_only — on an unknown account too",
                      forced == unknown == {"status": 403, "code": "account.access_admin_only"}, f"{forced} {unknown}")

        # 4. Cutting.
        await go("accounts-roster")
        await page.click(f'[data-part="accounts/account"][data-account="{LOCAL["id"]}"] [data-part="accounts/access"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        called = await page.evaluate(
            "()=>window.__mocks.answered().filter((one)=>one.operationId==='setAccountAccess').map((one)=>one.status)")
        journal.check("4: the tap calls setAccountAccess", called == [200], str(called))
        cut = row(await page.evaluate(SWITCHES), LOCAL["id"])
        journal.check("4: the cut account's row is marked, its switch OFF",
                      cut is not None and cut["access"] == "off" and cut["cut"] and cut["toggle"] is not None and not cut["toggle"]["on"], str(cut))
        cut_plex = await page.evaluate(CALL, ["PUT", f"/api/v1/accounts/{LINKED['id']}/access", {"signInAllowed": False}])
        journal.check("4: a Plex-linked account is cut as well", cut_plex["status"] == 200, str(cut_plex))
        # THE CUT ACCOUNT'S OWN BROWSER: its next request.
        await page.evaluate("""async (id) => { window.__mocks.setIdentity(id);
          await window.__queries.resetQueries({ queryKey: ['/api/v1/auth/me'] }); }""", LOCAL["id"])
        await page.wait_for_timeout(SETTLED)
        statuses = await page.evaluate(
            "()=>window.__mocks.answered().filter((one)=>one.operationId==='readAccount').map((one)=>one.status)")
        journal.check("4: the cut account's next request answers 401", 401 in statuses, str(statuses))
        journal.check("4: and lands on the sign-in gate", await page.evaluate(GATE))
        disabled = await words("refusals.auth.access_disabled")
        await page.evaluate("()=>document.querySelector('[data-part=\"login/password-disclosure\"]')?.click()")
        await page.fill('#loginform input[name="username"]', LOCAL["email"])
        await page.fill('#loginform input[name="password"]', "a password")
        await page.click('#loginform [type="submit"]')
        await page.wait_for_timeout(ACTED)
        said = await page.evaluate("()=>document.querySelector('#loginerr')?.textContent")
        journal.check("4: its password sign-in is refused « access disabled »", said == disabled, f"{said} / {disabled}")
        await page.evaluate("(id)=>window.__mocks.setIdentity(id)", LINKED["id"])
        await page.click('[data-part="login/plex-submit"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        said = await page.evaluate("()=>document.querySelector('[data-part=\"login/plex-refusal\"]')?.textContent")
        journal.check("4: a cut Plex account's Plex sign-in is refused « access disabled »",
                      said == disabled, f"{said} / {disabled}")

        # 5. Back on.
        await page.evaluate("(id)=>window.__mocks.setIdentity(id)", OWNER["id"])
        back = await page.evaluate(CALL, ["PUT", f"/api/v1/accounts/{LOCAL['id']}/access", {"signInAllowed": True}])
        journal.check("5: the Admin turns the access back on", back["status"] == 200, str(back))
        await page.evaluate("(id)=>window.__mocks.setIdentity(id)", LOCAL["id"])
        await page.click('#loginform [type="submit"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        me = await page.evaluate("async()=>{ const a = await fetch('/api/v1/auth/me'); return [a.status, (await a.json()).id]; }")
        journal.check("5: the account signs in again", me == [200, LOCAL["id"]] and not await page.evaluate(GATE), str(me))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
