"""R522 — an account signs in by its kind, and a local account's password is its own, set by an Admin (§ 17).

The operator, 2026-10-03: every login is an e-mail; a Plex identity with access to the managed
server signs in by Plex only, one without access is refused; the owner keeps a fallback password
replaced only on the server; a local account signs in by password and changes it in Profil; a
link to Plex drops its role to its Plex kind's starting one (O-K1-4); and « A » — the Admin gives a
local account a PROVISIONAL password at creation in « Comptes » and may reset it there.

1. THE PLEX WAIT: a PIN not yet claimed says so, offers to reopen Plex's page and to cancel.
2. ONE REFUSAL (O-K1-4 anti-enumeration): a Plex identity without access to the server is refused
   in the very words a failed password gets — nothing tells the two apart; an expired PIN says so.
3. PROFIL: a local account's password form, refused by code (current wrong, too short with the
   server's minimum), the two new passwords compared before anything is asked, and its success;
   a Plex-linked account draws no form.
4. « COMPTES »: every account says how it signs in, the Admin role is named by its kind, and the
   account a link demoted says so — its panel naming the role it held.
5. THE PROVISIONAL PASSWORD: a local account is created with one, and refused without it; a local
   account's panel resets it and says it is set, or refused short; the owner's panel says his is
   changed on the server only, and neither his nor a Plex-linked account's offers a reset.
"""
import asyncio
import json
import pathlib

from common import SETTLED, ACTED, PANEL_IN, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
SEEDS = json.loads((SOURCE / "mocks/seeds/accounts.json").read_text(encoding="utf-8"))
OWNER = json.loads((SOURCE / "mocks/seeds/account.json").read_text(encoding="utf-8"))

GATE = """() => {
  const seen = (part) => !!document.querySelector(`[data-part="login/${part}"]`)?.checkVisibility();
  const refusal = document.querySelector('[data-part="login/plex-refusal"]');
  const error = document.querySelector('#loginerr');
  return {
    pending: seen('plex-pending'), cancel: seen('plex-cancel'),
    reopen: document.querySelector('[data-part="login/plex-reopen"]')?.getAttribute('href') || null,
    plexRefusal: refusal?.checkVisibility() ? refusal.textContent : null,
    passwordRefusal: error?.checkVisibility() ? error.textContent : null };
}"""

PROFILE = """() => ({
  form: !!document.querySelector('[data-part="profile/password"]'),
  refusal: document.querySelector('[data-part="profile/password-refusal"]')?.textContent || null,
  changed: document.querySelector('[data-part="profile/password-changed"]')?.textContent || null })"""

ROSTER = """() => ({
  accounts: [...document.querySelectorAll('[data-part="accounts/account"]')].map((row) => ({
    name: row.querySelector('[data-part="flux/name"]')?.textContent || '',
    value: row.querySelector('[data-part="flux/value"]')?.textContent || '',
    detail: row.querySelector('[data-part="flux/detail"]')?.textContent || '' })),
  roles: [...document.querySelectorAll('[data-part="accounts/role"] [data-part="flux/name"]')].map((one) => one.textContent),
  refusal: document.querySelector('[data-part="accounts/refusal"]')?.textContent || null })"""

PANEL = """() => ({
  text: document.querySelector('#sheet')?.textContent || '',
  reset: !!document.querySelector('#sheet [data-part="accounts/password-reset"]'),
  done: document.querySelector('#sheet [data-part="accounts/password-reset-done"]')?.textContent || null,
  refusal: document.querySelector('#sheet [data-part="accounts/password-reset-refusal"]')?.textContent || null })"""


async def main():
    journal = Journal("R522 — an account signs in by its kind; a local account's password is set by an Admin")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def at(state, read, wait=SETTLED):
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(wait)
            return await page.evaluate(read)

        async def say(key, **params):
            return await page.evaluate("([k, p])=>window.__i18n.t(k, p)", [key, params])

        async def answered(operation):
            return await page.evaluate(
                "(id)=>window.__mocks.answered().filter((one)=>one.operationId===id).map((one)=>one.status)", operation)

        # 1–2. The gate.
        pending = await at("signin-plex-pending", GATE, ACTED + SETTLED)
        journal.check("the Plex wait: a PIN not yet claimed says so, offers to reopen Plex and to cancel",
                      pending["pending"] and pending["cancel"] and pending["reopen"] == SEEDS["plexSignInUrl"],
                      str(pending))
        refused = await at("signin-plex-refused", GATE, ACTED + SETTLED)
        password = await at("signin-password-refused", GATE, ACTED + SETTLED)
        words = await say("refusals.auth.refused")
        journal.check("one refusal: a Plex identity without access is refused in a failed password's very words",
                      refused["plexRefusal"] == words == password["passwordRefusal"],
                      f"{refused['plexRefusal']!r} / {password['passwordRefusal']!r}")
        expired = await at("signin-plex-expired", GATE, ACTED + SETTLED)
        journal.check("an expired PIN says so", expired["plexRefusal"] == await say("refusals.plex.pin_expired"),
                      str(expired["plexRefusal"]))

        # 3. Profil.
        local = await at("profile-local", PROFILE)
        linked = await at("profile-plex-linked", PROFILE)
        journal.check("Profil: a local account draws its password form, a Plex-linked one none",
                      local["form"] and not linked["form"], f"{local['form']} / {linked['form']}")
        wrong = await at("profile-password-current-wrong", PROFILE, ACTED + SETTLED)
        journal.check("Profil: a wrong current password is refused by its code",
                      wrong["refusal"] == await say("refusals.password.current_wrong"), str(wrong["refusal"]))
        short = await at("profile-password-too-short", PROFILE, ACTED + SETTLED)
        minimum = await say("refusals.password.too_short", minimum=SEEDS["passwordMinimum"])
        journal.check("Profil: a short new password is refused with the server's minimum",
                      short["refusal"] == minimum, str(short["refusal"]))
        mismatch = await at("profile-password-mismatch", PROFILE, ACTED + SETTLED)
        journal.check("Profil: two different new passwords are said before anything is asked",
                      mismatch["refusal"] == await say("screens.accountPage.password.mismatch")
                      and not await answered("changeOwnPassword"), str(mismatch["refusal"]))
        changed = await at("profile-password-changed", PROFILE, ACTED + SETTLED)
        journal.check("Profil: the password is changed, and said so",
                      changed["changed"] == await say("screens.accountPage.password.changed")
                      and await answered("changeOwnPassword") == [200], str(changed))

        # 4. « Comptes ».
        roster = await at("accounts-linked-demoted", ROSTER, PANEL_IN + SETTLED)
        kinds = {one["id"]: one["signInKind"] for one in [OWNER, *SEEDS["accounts"]]}
        names = {one["id"]: one["name"] for one in SEEDS["accounts"]}
        rows = {one["name"]: one for one in roster["accounts"]}
        unsaid = []
        for account, kind in kinds.items():
            row = rows.get(names.get(account, OWNER["name"]))
            if row is None or await say(f"screens.accounts.signInKind.{kind}") not in row["detail"]:
                unsaid.append(account)
        journal.check("Comptes: every account says how it signs in", not unsaid, str(unsaid))
        journal.check("Comptes: the Admin role is named by its kind",
                      await say("access.roleKinds.admin") in roster["roles"], str(roster["roles"]))
        demoted = next(one for one in SEEDS["accounts"] if one.get("demotedFrom"))
        before = next(role["name"] for role in SEEDS["roles"] if role["id"] == demoted["demotedFrom"])
        panel = await page.evaluate(PANEL)
        journal.check("Comptes: the account a link demoted says so on its row, and its panel names the role it held",
                      await say("screens.accounts.demotedShort") in rows[demoted["name"]]["detail"]
                      and await say("screens.accounts.demoted", role=before) in panel["text"],
                      f"{rows[demoted['name']]['detail']!r} / {panel['text'][:120]!r}")

        # 5. The provisional password.
        created = await at("accounts-create-provisional", ROSTER, ACTED + SETTLED)
        nina = next((one for one in created["accounts"] if one["name"] == "Nina"), None)
        journal.check("a local account is created with its provisional password",
                      await answered("createAccount") == [201] and nina is not None
                      and await say("screens.accounts.signInKind.local") in nina["detail"], str(nina))
        missing = await at("accounts-create-password-missing", ROSTER, ACTED + SETTLED)
        journal.check("a local account without a provisional password is refused, by its code",
                      missing["refusal"] == await say("refusals.password.required"), str(missing["refusal"]))
        offered = await at("accounts-reset-local", PANEL, PANEL_IN + SETTLED)
        journal.check("a local account's panel offers to reset its password", offered["reset"], offered["text"][:120])
        done = await at("accounts-reset-done", PANEL, PANEL_IN + ACTED + SETTLED)
        holder = next(one["name"] for one in SEEDS["accounts"] if one["id"] == "local-account")
        journal.check("the reset is set, and said with the holder's name",
                      done["done"] == await say("screens.accounts.reset.done", name=holder)
                      and await answered("resetAccountPassword") == [200], str(done["done"]))
        too_short = await at("accounts-reset-too-short", PANEL, PANEL_IN + ACTED + SETTLED)
        journal.check("a short provisional password is refused with the server's minimum",
                      too_short["refusal"] == minimum, str(too_short["refusal"]))
        owner = await at("accounts-owner-password", PANEL, PANEL_IN + SETTLED)
        journal.check("the owner's panel says his password changes on the server only, and offers no reset",
                      not owner["reset"] and await say("refusals.password.held_by_cli") in owner["text"],
                      owner["text"][:160])
        plex = await at("accounts-plex-no-password", PANEL, PANEL_IN + SETTLED)
        journal.check("a Plex-linked account's panel offers no reset", not plex["reset"] and plex["text"],
                      plex["text"][:120])

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
