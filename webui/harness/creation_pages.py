"""R525 — a creation opens its own page with a validated form, and an unused role can be deleted (§ 17, § 16).

The operator, 2026-10-04: « Le bouton nouveau rôle dans la gestion des comptes crée directement un nouveau
rôle avec un nom par défaut ; je préférerais avoir une nouvelle page avec un formulaire de création avec
validation. Pas de nom par défaut, saisie avec champs obligatoires, et aussi possibilité de supprimer un rôle
mais seulement s'il est attribué à aucun compte. » — « Créer un nouveau compte devrait avoir sa propre page
avec formulaire et validation aussi. » His ruling A: a role a newcomer starts on (`defaultFor`) is not
deletable either, even when no account holds it; and his standing rule: the interface never OFFERS an act
the viewer cannot perform, the API refusal is for direct calls.

1. « NOUVEAU RÔLE » OPENS A PAGE AND CREATES NOTHING: the tap lands on `/accounts/roles/new`, no
   `createRole` leaves, the name field is EMPTY (no generated name) and Create is closed.
2. THE ROLE FORM VALIDATES AT THE FIELD: an emptied name is said at the name field, Create closed;
   forcing `createRole` nameless answers 400 `role.name_required`. A seeded role's words are NOT a taken
   name — a seeded role carries no `name`, and the server cannot know the interface's translation.
3. A VALID ROLE IS CREATED AND THE PAGE RETURNS: a name and a right open Create; one `createRole` 201,
   back on `/accounts`, and the roster draws the role. Reopened, the page says that name — typed in
   another case between spaces, the contract's rule — taken at the name field, Create closed.
4. « NOUVEAU COMPTE » OPENS A PAGE LIKEWISE: `/accounts/new`, nothing created, every field empty, Create
   closed; an invalid e-mail is said at its field; the roster page carries no creation form.
5. A VALID ACCOUNT IS CREATED AND THE PAGE RETURNS; a refusal lands at its field — a local account
   without its provisional password is told so under the password field, and nothing is created. The
   password policy (the operator, 2026-10-04) is said under the field before anything is typed, and a
   password breaking it is said there at once, Create closed, nothing asked.
6. DELETE IS OFFERED ONLY WHERE IT CAN BE DONE: absent on a role an account holds and on a role a
   newcomer starts on (ruling A), present on an unused one; forcing either refused answers 409
   `role.in_use` / `role.default`.
7. DELETING ASKS FIRST, THEN REMOVES: the tap opens a confirmation and no write leaves; confirming calls
   `deleteRole` and the roster no longer draws the role.
"""
import asyncio
import json
import pathlib

from common import SETTLED, PANEL_IN, ACTED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
SEEDS = json.loads((SOURCE / "mocks/seeds/accounts.json").read_text(encoding="utf-8"))

ROLE_SCREEN = '[data-part="screen"][data-open][data-key="role-create"]'
ACCOUNT_SCREEN = '[data-part="screen"][data-open][data-key="account-create"]'
CALLS = """(operation) => window.__mocks.answered().filter((one) => one.operationId === operation).map((one) => one.status)"""
ROLES = """() => [...document.querySelectorAll('#view [data-part="accounts/role"] [data-part="flux/name"]')].map((one) => one.textContent)"""
ACCOUNTS = """() => [...document.querySelectorAll('#view [data-part="accounts/account"] [data-part="flux/name"]')].map((one) => one.textContent)"""
CALL = """async ([method, path, body]) => {
  const answer = await fetch(path, { method, body: body === null ? undefined : JSON.stringify(body) });
  const read = await answer.json().catch(() => ({}));
  return { status: answer.status, code: read.code ?? null }; }"""
FORM = """([screen, fields]) => {
  const root = document.querySelector(screen);
  if (!root) return null;
  const value = (name) => root.querySelector('[name="' + name + '"]')?.value ?? null;
  const error = (name) => root.querySelector('[data-field-error="' + name + '"]')?.textContent ?? null;
  return { path: location.pathname, values: Object.fromEntries(fields.map((name) => [name, value(name)])),
    errors: Object.fromEntries(fields.map((name) => [name, error(name)])),
    submit: root.querySelector('[data-part="creation/submit"]')?.disabled ?? null,
    required: [...root.querySelectorAll('[aria-required="true"]')].map((one) => one.getAttribute('name')) }; }"""
ROLE_FIELDS = ["name"]
ACCOUNT_FIELDS = ["name", "email", "role", "password"]


async def main():
    journal = Journal("R525 — a creation opens its own page with a validated form")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        words = lambda key, **values: page.evaluate("([k, v])=>window.__i18n.t(k, v)", [key, values])  # noqa: E731

        async def go(state, wait=SETTLED):
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(wait)

        async def form(screen, fields):
            return await page.evaluate(FORM, [screen, fields])

        async def to_accounts():
            """Arrives on « Comptes » by the menu, from the library.

            A real arrival, so the page a creation returns to is under it in history — a
            named state writes none.
            """
            await go("lib-grid")
            await page.click("[data-drawer]")
            await page.wait_for_timeout(PANEL_IN)
            await page.click('#drawer [data-navgo="accounts"]')
            await page.wait_for_timeout(ACTED + SETTLED)

        # 1. « Nouveau rôle » opens a page, and creates nothing.
        await go("accounts-roster")
        await page.click('#view [data-part="accounts/role-create"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        opened = await form(ROLE_SCREEN, ROLE_FIELDS)
        journal.check("1: « Nouveau rôle » opens the role's creation page at /accounts/roles/new",
                      opened is not None and opened["path"].endswith("/accounts/roles/new"), str(opened))
        journal.check("1: and the tap alone creates nothing", await page.evaluate(CALLS, "createRole") == [],
                      str(await page.evaluate(CALLS, "createRole")))
        journal.check("1: the name field is EMPTY — no generated name — and marked required, Create closed",
                      opened is not None and opened["values"]["name"] == "" and "name" in opened["required"]
                      and opened["submit"] is True, str(opened))

        # 2. The role form validates at the field.
        if opened is not None:
            await page.fill(f'{ROLE_SCREEN} [name="name"]', "x")
            await page.fill(f'{ROLE_SCREEN} [name="name"]', "")
            await page.wait_for_timeout(SETTLED)
        emptied = await form(ROLE_SCREEN, ROLE_FIELDS)
        journal.check("2: an emptied name is said at its field, Create closed",
                      emptied is not None and emptied["errors"]["name"] == await words("refusals.role.name_required")
                      and emptied["submit"] is True, str(emptied))
        seeded_words = await page.evaluate("()=>window.__i18n.t('roles.seed.household')")
        if opened is not None:
            await page.fill(f'{ROLE_SCREEN} [name="name"]', seeded_words)
            await page.wait_for_timeout(SETTLED)
        seeded = await form(ROLE_SCREEN, ROLE_FIELDS)
        journal.check(f"2: a seeded role's words (« {seeded_words} ») are no taken name — it carries no `name`",
                      seeded is not None and seeded["errors"]["name"] is None and seeded["submit"] is False, str(seeded))
        forced = await page.evaluate(CALL, ["POST", "/api/v1/roles", {"name": "  ", "rights": []}])
        journal.check("2: forced nameless, createRole answers 400 role.name_required",
                      forced == {"status": 400, "code": "role.name_required"}, str(forced))

        # 3. A valid role is created, and the page returns to the roster.
        await to_accounts()
        await page.click('#view [data-part="accounts/role-create"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        if await page.query_selector(ROLE_SCREEN) is not None:
            await page.fill(f'{ROLE_SCREEN} [name="name"]', "Amis")
            await page.click(f'{ROLE_SCREEN} [data-role-create-right="library.read"]')
            await page.wait_for_timeout(SETTLED)
        valid = await form(ROLE_SCREEN, ROLE_FIELDS)
        journal.check("3: a name and a right open Create, no error said",
                      valid is not None and valid["submit"] is False and valid["errors"]["name"] is None, str(valid))
        if valid is not None and valid["submit"] is False:
            await page.click(f'{ROLE_SCREEN} [data-part="creation/submit"]')
            await page.wait_for_timeout(ACTED + SETTLED)
        journal.check("3: Create calls createRole once, answered 201",
                      await page.evaluate(CALLS, "createRole") == [201], str(await page.evaluate(CALLS, "createRole")))
        path = await page.evaluate("()=>location.pathname")
        roles = await page.evaluate(ROLES)
        journal.check("3: the page returns to the roster, which draws the new role",
                      path.endswith("/accounts") and await page.query_selector(ROLE_SCREEN) is None and "Amis" in roles,
                      f"{path} / {roles}")
        await page.click('#view [data-part="accounts/role-create"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        if await page.query_selector(ROLE_SCREEN) is not None:
            await page.fill(f'{ROLE_SCREEN} [name="name"]', "  AMIS ")
            await page.wait_for_timeout(SETTLED)
        taken = await form(ROLE_SCREEN, ROLE_FIELDS)
        journal.check("3: reopened, the name a role now carries (« Amis », typed «  AMIS  ») is said taken at its field, "
                      "Create closed",
                      taken is not None and taken["errors"]["name"] == await words("refusals.role.name_taken")
                      and taken["submit"] is True, str(taken))

        # 4. « Nouveau compte » opens a page likewise.
        await to_accounts()
        journal.check("4: the roster page carries no creation form",
                      await page.query_selector('#view form') is None)
        await page.click('#view [data-part="accounts/account-create"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        empty = await form(ACCOUNT_SCREEN, ACCOUNT_FIELDS)
        journal.check("4: « Nouveau compte » opens the account's creation page at /accounts/new",
                      empty is not None and empty["path"].endswith("/accounts/new"), str(empty))
        journal.check("4: and the tap alone creates nothing", await page.evaluate(CALLS, "createAccount") == [])
        journal.check("4: every field is empty — no role chosen for the reader — the required ones marked, Create closed",
                      empty is not None and all(value == "" for value in empty["values"].values())
                      and {"name", "email", "role"} <= set(empty["required"]) and empty["submit"] is True, str(empty))
        if empty is not None:
            await page.fill(f'{ACCOUNT_SCREEN} [name="email"]', "nina")
            await page.fill(f'{ACCOUNT_SCREEN} [name="name"]', "Nina")
            await page.wait_for_timeout(SETTLED)
        invalid = await form(ACCOUNT_SCREEN, ACCOUNT_FIELDS)
        journal.check("4: an invalid e-mail is said at its field, Create closed",
                      invalid is not None and invalid["errors"]["email"] == await words("refusals.account.email_invalid")
                      and invalid["submit"] is True, str(invalid))

        # 5. A refusal lands at its field; a valid account is created and the page returns.
        if invalid is not None:
            await page.fill(f'{ACCOUNT_SCREEN} [name="email"]', "nina@example.invalid")
            await page.select_option(f'{ACCOUNT_SCREEN} [name="role"]', "local-guest")
            await page.wait_for_timeout(SETTLED)
            await page.click(f'{ACCOUNT_SCREEN} [data-part="creation/submit"]')
            await page.wait_for_timeout(ACTED + SETTLED)
        refused = await form(ACCOUNT_SCREEN, ACCOUNT_FIELDS)
        journal.check("5: a local account without its provisional password is told so under the password field",
                      refused is not None and refused["errors"]["password"] == await words("refusals.password.required"),
                      str(refused))
        journal.check("5: and nothing is created", await page.evaluate(CALLS, "createAccount") == [400],
                      str(await page.evaluate(CALLS, "createAccount")))
        rule = await words("common.passwordRule", minimum=SEEDS["passwordMinimum"])
        hint = await page.evaluate(
            "(s)=>document.querySelector(s + ' [data-field=\"password\"]')?.textContent || ''", ACCOUNT_SCREEN)
        journal.check("5: the password policy is said under the field before anything is typed", rule in hint, hint)
        if refused is not None:
            await page.fill(f'{ACCOUNT_SCREEN} [name="password"]', "correcthorsebattery")
            await page.wait_for_timeout(SETTLED)
        weak = await form(ACCOUNT_SCREEN, ACCOUNT_FIELDS)
        journal.check("5: a password breaking the policy is said at its field, Create closed, nothing asked",
                      weak is not None
                      and weak["errors"]["password"] == await words("refusals.password.too_weak",
                                                                    minimum=SEEDS["passwordMinimum"])
                      and weak["submit"] is True and await page.evaluate(CALLS, "createAccount") == [400], str(weak))
        if refused is not None:
            await page.fill(f'{ACCOUNT_SCREEN} [name="password"]', "Correct-horse battery 9")
            await page.wait_for_timeout(SETTLED)
            await page.click(f'{ACCOUNT_SCREEN} [data-part="creation/submit"]')
            await page.wait_for_timeout(ACTED + SETTLED)
        path = await page.evaluate("()=>location.pathname")
        accounts = await page.evaluate(ACCOUNTS)
        journal.check("5: the valid account is created, and the page returns to the roster, which draws it",
                      await page.evaluate(CALLS, "createAccount") == [400, 201] and path.endswith("/accounts")
                      and "Nina" in accounts, f"{path} / {accounts}")

        # 6. Delete is offered only where it can be done.
        async def offered(state):
            await go(state, PANEL_IN + SETTLED)
            return await page.query_selector('#sheet [data-role-delete]') is not None

        journal.check("6: a role an account holds offers no Delete", not await offered("accounts-roles"))
        journal.check("6: a role a newcomer starts on, held by nobody, offers no Delete (ruling A)",
                      not await offered("accounts-role-default-unheld"))
        held = await page.evaluate(CALL, ["DELETE", "/api/v1/roles/requester", None])
        default = await page.evaluate(CALL, ["DELETE", "/api/v1/roles/local-guest", None])
        journal.check("6: forced, they answer 409 role.in_use and 409 role.default",
                      (held, default) == ({"status": 409, "code": "role.in_use"}, {"status": 409, "code": "role.default"}),
                      str((held, default)))
        journal.check("6: a role no account holds and no newcomer starts on offers Delete",
                      await offered("accounts-role-unused"))

        # 7. Deleting asks first, then removes.
        unused = await page.evaluate("()=>document.querySelector('#sheet [data-role-delete]')?.dataset.roleDelete ?? null")
        before = await page.evaluate("()=>window.__mocks.answered().length")
        if unused is not None:
            await page.click('#sheet [data-role-delete]')
            await page.wait_for_timeout(ACTED)
        asked = await page.evaluate("""(before) => ({ open: !!document.querySelector('#dlg[data-open]'),
          writes: window.__mocks.answered().slice(before).filter((one) => one.method !== 'GET').length })""", before)
        journal.check("7: Delete opens a confirmation, and no write leaves", asked == {"open": True, "writes": 0}, str(asked))
        if asked["open"]:
            await page.click('#dlg[data-open] [data-confirm-role-delete]')
            await page.wait_for_timeout(ACTED + SETTLED)
        roles = await page.evaluate("async()=>(await (await fetch('/api/v1/accounts')).json()).roles.map((one)=>one.id)")
        journal.check("7: confirming calls deleteRole, and the role is gone",
                      await page.evaluate(CALLS, "deleteRole") == [200] and unused is not None and unused not in roles,
                      f"{await page.evaluate(CALLS, 'deleteRole')} / {unused} in {roles}")
        drawn = await page.evaluate(ROLES)
        journal.check("7: the roster no longer draws it", "Amis" not in drawn, str(drawn))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
