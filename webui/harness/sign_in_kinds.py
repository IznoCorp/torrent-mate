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
6. ADMIN ONLY (the operator, 2026-10-03: « Admin pour n'importe quel compte à mot de passe via
   "comptes", l'utilisateur d'un compte à mot de passe peut changer son mot de passe via son
   profil »): a manager who is not Admin is offered no reset, even of an account whose role its
   own covers, and is told why; forced, the reset answers 403 `password.reset_admin_only`, its own
   account's too.
7. THE PASSWORD POLICY (the operator, 2026-10-04: twelve characters, an uppercase letter, a digit,
   a special character): Profil and a local account's reset say the rule under the field, and a
   password breaking it is said before anything is asked.
8. AN ADMIN NEVER RESETS ITS OWN (the operator, 2026-10-04: « un Admin change son propre mot de
   passe seulement via changeOwnPassword, mot de passe actuel requis »): a second Admin's own panel
   offers no reset and says why; forced, it answers 403 `password.reset_own`.
9. WHY THE SESSION ENDED (the operator, 2026-10-04): the gate says it, from the server's code, in the
   interface's words — « session expirée » for `auth.required`, « accès désactivé par un
   administrateur » for `auth.access_disabled` — and says nothing on a plain visit.
10. THE PROFIL BUTTON, one button in three faces: « Installer l'app » (a browser that offers the
    install), the way to do it by hand on iOS Safari, and « Mettre à jour » for an installed app with a
    newer version waiting — and none at all when there is nothing to do.
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
  rule: document.querySelector('[data-part="profile/password-rule"]')?.textContent || null,
  refusal: document.querySelector('[data-part="profile/password-refusal"]')?.textContent || null,
  changed: document.querySelector('[data-part="profile/password-changed"]')?.textContent || null })"""

ROSTER = """() => ({
  accounts: [...document.querySelectorAll('[data-part="accounts/account"]')].map((row) => ({
    name: row.querySelector('[data-part="flux/name"]')?.textContent || '',
    value: row.querySelector('[data-part="flux/value"]')?.textContent || '',
    detail: row.querySelector('[data-part="flux/detail"]')?.textContent || '' })),
  roles: [...document.querySelectorAll('[data-part="accounts/role"] [data-part="flux/name"]')].map((one) => one.textContent),
  refusal: document.querySelector('[data-field-error]')?.textContent || null })"""

FORCE = """async ([account]) => {
  const answer = await fetch(`/api/v1/accounts/${account}/password`, { method: 'POST', body: JSON.stringify({ password: 'Correct-horse battery 9' }) });
  return [answer.status, (await answer.json()).code ?? null]; }"""

REASON = """() => {
  const line = document.querySelector('[data-part="login/reason"]');
  return { reason: line?.checkVisibility() ? line.textContent : null };
}"""

INSTALL = """() => {
  const section = document.querySelector('[data-part="profile/install"]');
  const action = section?.querySelector('[data-part="profile/install-action"]');
  return {
    face: section?.getAttribute('data-face') || null,
    action: action?.textContent || null,
    steps: [...(section?.querySelectorAll('[data-part="profile/install-steps"] li') || [])].map((one) => one.textContent),
  };
}"""

PANEL = """() => ({
  text: document.querySelector('#sheet')?.textContent || '',
  rule: document.querySelector('#sheet [data-part="accounts/password-rule"]')?.textContent || null,
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
                      await say("roles.seed.admin") in roster["roles"], str(roster["roles"]))
        demoted = next(one for one in SEEDS["accounts"] if one.get("demotedFrom"))
        before = await say(f"roles.seed.{demoted['demotedFrom']}")
        panel = await page.evaluate(PANEL)
        journal.check("Comptes: the account a link demoted says so on its row, and its panel names the role it held",
                      await say("screens.accounts.demotedShort") in rows[demoted["name"]]["detail"]
                      and await say("screens.accounts.demoted", role=before) in panel["text"],
                      f"{rows[demoted['name']]['detail']!r} / {panel['text'][:120]!r}")

        # 5. The provisional password.
        # READ ON THE ROSTER SERVED: a named state writes no history, so the page its
        # creation page returns to is not « Comptes » (R525 walks that return).
        await at("accounts-create-provisional", "() => null", ACTED + SETTLED)
        served = await page.evaluate("async()=>(await (await fetch('/api/v1/accounts')).json()).accounts")
        nina = next((one for one in served if one["name"] == "Nina"), None)
        journal.check("a local account is created with its provisional password",
                      await answered("createAccount") == [201] and nina is not None
                      and nina["signInKind"] == "local", str(nina))
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

        # 6. Admin only.
        manager = await at("accounts-reset-not-admin", PANEL, PANEL_IN + SETTLED)
        journal.check("Admin only: a manager who is not Admin is offered no reset, even within its role's reach, and is told why",
                      not manager["reset"] and await say("screens.accounts.reset.adminOnly") in manager["text"],
                      manager["text"][:160])
        forced = [await page.evaluate(FORCE, [one]) for one in ("local-guest", "local-account")]
        journal.check("Admin only: forced, a reset answers 403 password.reset_admin_only, its own account's too",
                      forced == [[403, "password.reset_admin_only"]] * 2, str(forced))

        # 7. The password policy.
        rule = await say("common.passwordRule", minimum=SEEDS["passwordMinimum"])
        weak_words = await say("refusals.password.too_weak", minimum=SEEDS["passwordMinimum"])
        journal.check("policy: Profil says the rule under the new password", local["rule"] == rule, str(local["rule"]))
        journal.check("policy: a local account's reset says the rule under the field", offered["rule"] == rule,
                      str(offered["rule"]))
        weak = await at("profile-password-too-weak", PROFILE, ACTED + SETTLED)
        journal.check("policy: Profil says a new password breaking the rule before anything is asked",
                      weak["refusal"] == weak_words and not await answered("changeOwnPassword"), str(weak["refusal"]))
        weak_reset = await at("accounts-reset-too-weak", PANEL, PANEL_IN + ACTED + SETTLED)
        journal.check("policy: a provisional password breaking the rule is said before anything is asked",
                      weak_reset["refusal"] == weak_words and not await answered("resetAccountPassword"),
                      str(weak_reset["refusal"]))

        # 8. An Admin's own password.
        own = await at("accounts-reset-own", PANEL, PANEL_IN + SETTLED)
        journal.check("own: a second Admin's own panel offers no reset, and says it changes in Profil",
                      not own["reset"] and await say("screens.accounts.reset.own") in own["text"], own["text"][:160])
        forced = await page.evaluate(FORCE, ["local-account"])
        journal.check("own: forced, its own reset answers 403 password.reset_own",
                      forced == [403, "password.reset_own"], str(forced))

        # 9. Why the session ended.
        expired = await at("signin-expired", REASON, ACTED + SETTLED)
        journal.check("the gate says the session expired, in the interface's words",
                      expired["reason"] == await say("screens.gate.reasonExpired"), str(expired))
        cut = await at("signin-access-disabled", REASON, ACTED + SETTLED)
        journal.check("and that an administrator disabled the access, for the other code",
                      cut["reason"] == await say("screens.gate.reasonDisabled")
                      and cut["reason"] != expired["reason"], str(cut))
        plain = await at("signin", REASON, ACTED + SETTLED)
        journal.check("a plain visit says nothing", plain["reason"] is None, str(plain))
        again = await at("signin-expired", REASON, ACTED + SETTLED)
        left = await at("signin", REASON, ACTED + SETTLED)
        journal.check("a reason does not outlive the state that showed it",
                      again["reason"] is not None and left["reason"] is None, f"{again} / {left}")

        # 10. The Profil button.
        offer = await at("profile-install", INSTALL, SETTLED)
        journal.check("Profil: a browser that offers the install gets « Installer l'app »",
                      offer["face"] == "install"
                      and offer["action"] == await say("screens.accountPage.install.install.action"), str(offer))
        by_hand = await at("profile-install-ios", INSTALL, SETTLED)
        journal.check("Profil: on iOS Safari it is the same words, and the way is not shown until asked",
                      by_hand["face"] == "ios" and by_hand["steps"] == [], str(by_hand))
        await page.click('[data-part="profile/install-action"]')
        await page.wait_for_timeout(ACTED)
        shown = await page.evaluate(INSTALL)
        journal.check("and pressing it shows the way, in the interface's three steps",
                      shown["steps"] == [await say(f"screens.accountPage.install.steps.{step}")
                                         for step in ("share", "addToHome", "confirm")], str(shown))
        update = await at("profile-update", INSTALL, SETTLED)
        journal.check("Profil: an installed app with a newer version waiting is offered « Mettre à jour »",
                      update["face"] == "update"
                      and update["action"] == await say("screens.accountPage.install.update.action"), str(update))
        quiet = await at("profile-local", INSTALL, SETTLED)
        journal.check("Profil: where there is nothing to install or update, there is no button",
                      quiet["face"] is None, str(quiet))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
