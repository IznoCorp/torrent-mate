"""R429 — the reader's corrections of L18: renaming, the swipe's rights, the season, the co-requester (§ 17).

DESIGN maquette-l18 § 3.0, § 3.4, § 3.5, § 3.9; round 8 Q11, round 9 Q13, round 9 Q14, round 10 Q6.

1. A ROLE IS RENAMED THROUGH THE INTERFACE — an ordinary role and a created one; never
   Admin (round 9 Q14: « modifiables par l'interface »).
2. THE SWIPE OBEYS THE RIGHTS: a follow's swipe acts are offered only where its panel would offer
   them; a 403 the interface still meets says its refusal, never a success first.
3. « RÉCUPÉRER LA SAISON N » only with the right, on one's own acquisition; a 403 says why.
4. A CO-REQUESTER'S GENERIC ACTS: « Retirer de la liste » removes the caller from the requesters and
   the follow stays for the others; the generic pause is not offered to a co-requester; the follow
   pauses once every requester holding the right has paused (round 10 Q6).
5. « RÉAFFECTER… » MOVES THE VISIBLE LINE: the card and its panel name the new requester.
6. « À TRAITER » FOLLOWS ITS RIGHT (round 9 Q13): without `acquisition.todo.view`, no tab and no
   count on the Acquisition badge.
7–12. The minors: the creation form greys what escalates; Admin reads « contourne tous les
   droits »; the header's avatar is the connected account's; Profil says no owner's line for another
   account and « aucun » for an empty role; Découvrir stays in the menu, marked; a guest's follow
   panel says no pause of its own.
"""
import asyncio

from common import SETTLED, PANEL_IN, ACTED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SHARED = "Kyma, l'onde mystérieuse"
OWN_SERIES = "Silo"
OTHERS_SERIES = "President Curtis"
MOVED = "President Curtis"

AS = """async (who) => { window.__mocks.setIdentity(who); await window.__queries.resetQueries(); }"""
TOAST = """() => document.querySelector('#toast')?.textContent || ''"""
ROW_ACTS = """(title) => { const row = [...document.querySelectorAll('#view [data-part="swipe"]')]
  .find((one) => one.querySelector('[data-part="card"]')?.textContent.includes(title));
  return row ? [...row.querySelectorAll('[data-part="swipe/action"]')].map((one) => one.dataset.swipeact) : null; }"""
TAP_INJECTED = """([attribute, title]) => { const button = document.createElement('button');
  button.setAttribute(attribute, title); document.querySelector('#view').append(button); button.click(); button.remove(); }"""
FOLLOW = """async (title) => (await (await fetch('/api/v1/acquisition/followed')).json()).find((one) => one.title === title) || null"""
PUT_PAUSE = """async ([who, title]) => { window.__mocks.setIdentity(who);
  return (await fetch('/api/v1/acquisition/followed/' + encodeURIComponent(title) + '/pause',
    { method: 'PUT', body: JSON.stringify({ paused: true }) })).status; }"""


async def main():
    journal = Journal("R429 — the reader's corrections of L18")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def go(state, wait=SETTLED):
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(wait)

        async def sign_in(who, store=None):
            await page.evaluate(AS, who)
            if store:
                await page.evaluate("(state)=>window.__store.write(state)", store)
            await page.wait_for_timeout(SETTLED)

        async def panel(kind, subject):
            await page.evaluate("([kind, subject])=>window.__panel.produce(kind, subject)", [kind, subject])
            await page.wait_for_timeout(PANEL_IN + SETTLED)

        # 1 — RENAMING A ROLE.
        await go("accounts-roles", PANEL_IN + SETTLED)
        field = await page.query_selector('#sheet [data-part="accounts/role-name"]')
        journal.check("1: an ordinary role's panel offers its name to change", field is not None)
        if field is not None:
            await field.fill("Foyer")
            await page.click('#sheet [data-role-rename="household"]')
            await page.wait_for_timeout(ACTED + SETTLED)
        names = await page.evaluate("()=>[...document.querySelectorAll('[data-part=\"accounts/role\"] [data-part=\"flux/name\"]')].map((one)=>one.textContent)")
        journal.check("1: the renamed role reads its new name in the roster", "Foyer" in names, str(names))
        await page.evaluate("()=>window.__panel.close()")
        await page.wait_for_timeout(SETTLED)
        await page.click('[data-part="accounts/role-create"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        created = await page.evaluate("async()=>(await (await fetch('/api/v1/accounts')).json()).roles.at(-1)")
        await panel("role", created["id"])
        field = await page.query_selector('#sheet [data-part="accounts/role-name"]')
        if field is not None:
            await field.fill("Amis")
            await page.click(f'#sheet [data-role-rename="{created["id"]}"]')
            await page.wait_for_timeout(ACTED + SETTLED)
        names = await page.evaluate("()=>[...document.querySelectorAll('[data-part=\"accounts/role\"] [data-part=\"flux/name\"]')].map((one)=>one.textContent)")
        journal.check(f"1: a created role (« {created['name']} ») is renamed too", "Amis" in names, str(names))
        await panel("role", "admin")
        admin_field = await page.query_selector('#sheet [data-part="accounts/role-name"]')
        journal.check("1: Admin does not offer its name", admin_field is None)

        # 2 — THE SWIPE OBEYS THE RIGHTS.
        await go("acq-see-only")
        await page.evaluate("()=>window.__store.write({ acqTab: 'follows' })")
        await page.wait_for_timeout(SETTLED)
        offered = await page.evaluate("()=>document.querySelectorAll('#view [data-part=\"swipe/action\"]').length")
        journal.check("2: a role that only sees is offered no swipe act on any follow", offered == 0, str(offered))
        await sign_in("household-member-sees-all", {"page": "acq", "acqTab": "follows"})
        foreign = await page.evaluate(ROW_ACTS, OTHERS_SERIES)
        own = await page.evaluate(ROW_ACTS, OWN_SERIES)
        journal.check("2: another's follow offers no swipe act, one's own does",
                      foreign is not None and not foreign and own, f"{OTHERS_SERIES} {foreign}, {OWN_SERIES} {own}")
        await page.evaluate("()=>window.__mocks.setIdentity('see-only')")
        await page.evaluate(TAP_INJECTED, ["data-remove", OWN_SERIES])
        await page.wait_for_timeout(ACTED)
        said = await page.evaluate(TOAST)
        journal.check("2: a removal the server refuses says its refusal, never « retiré » first",
                      "retiré" not in said and "droit" in said, said)
        await page.wait_for_timeout(ACTED)
        said = await page.evaluate(TOAST)
        journal.check("2: … and after the answer too", "retiré" not in said and "droit" in said, said)

        # 3 — « RÉCUPÉRER LA SAISON N ».
        async def grabs(title):
            await page.evaluate("(title)=>window.__screens.mediaSheet(title, window.__carriedFor(title) ?? undefined)", title)
            await page.wait_for_timeout(PANEL_IN + SETTLED * 2)
            count = await page.evaluate("()=>document.querySelectorAll('[data-grab-season]').length")
            await page.evaluate("()=>history.back()")
            await page.wait_for_timeout(SETTLED)
            return count

        await go("acq-see-only")
        eden = await grabs(OWN_SERIES)
        journal.check("3: a role without the pilot right is offered no season to take", eden == 0, str(eden))
        await sign_in("household-member-sees-all", {"page": "acq", "acqTab": "follows"})
        others = await grabs(OTHERS_SERIES)
        mine = await grabs(OWN_SERIES)
        journal.check("3: another's follow offers no season to take, one's own does",
                      others == 0 and mine > 0, f"{OTHERS_SERIES} {others}, {OWN_SERIES} {mine}")
        await page.evaluate("(title)=>window.__screens.mediaSheet(title, window.__carriedFor(title) ?? undefined)", OWN_SERIES)
        await page.wait_for_timeout(PANEL_IN + SETTLED * 2)
        await page.evaluate("()=>window.__mocks.setIdentity('see-only')")
        await page.evaluate("()=>document.querySelector('[data-grab-season]')?.click()")
        await page.wait_for_timeout(ACTED + SETTLED)
        said = await page.evaluate(TOAST)
        journal.check("3: a refused season says the right it lacks", "droit" in said, said)
        await page.evaluate("()=>history.back()")

        # 4 — THE CO-REQUESTER.
        await go("quality-own-offered", PANEL_IN + SETTLED)
        acts = await page.evaluate("()=>[...document.querySelectorAll('#sheet [data-pause], #sheet [data-pause-own], #sheet [data-remove]')].map((one)=>[...one.attributes].map((a)=>a.name).find((n)=>['data-pause','data-pause-own','data-remove'].includes(n)))")
        journal.check("4: a co-requester is not offered the generic pause, its own pause and « Retirer » are",
                      "data-pause" not in acts and "data-pause-own" in acts and "data-remove" in acts, str(acts))
        await page.evaluate("()=>window.__panel.close()")
        await page.wait_for_timeout(SETTLED)
        swiped = await page.evaluate(ROW_ACTS, SHARED)
        journal.check("4: nor on the shared follow's swipe", swiped is not None and "pause" not in swiped, str(swiped))
        await panel("follow", SHARED)
        await page.click("#sheet [data-remove]")
        await page.wait_for_timeout(ACTED + SETTLED)
        mine = await page.evaluate(FOLLOW, SHARED)
        await page.evaluate("()=>window.__mocks.setIdentity('izno')")
        theirs = await page.evaluate(FOLLOW, SHARED)
        journal.check("4: « Retirer de la liste » takes the co-requester off, the follow stays for the others",
                      mine is None and theirs is not None
                      and "household-member" not in [one["id"] for one in theirs["requesters"]],
                      f"Léa {mine and mine['title']}, izno {theirs and [one['id'] for one in theirs['requesters']]}")
        await go("quality-own-offered", PANEL_IN + SETTLED)
        statuses = [await page.evaluate(PUT_PAUSE, [who, SHARED]) for who in ("guest-with-quality", "izno")]
        await page.evaluate("()=>window.__mocks.setIdentity('household-member')")
        paused = await page.evaluate(FOLLOW, SHARED)
        journal.check("4: once every requester holding the right has paused, the follow is paused",
                      statuses == [200, 200] and paused and paused["status"] == "disabled",
                      f"{statuses} {paused and paused['status']}")

        # 5 — THE REASSIGNED LINE.
        await go("acq-household")
        # THE TARGET IS A TEST ACCOUNT, out of the tester's default world: its roster is turned on.
        await page.evaluate("()=>window.__mocks.setTestRoster(true)")
        await sign_in("izno", {"page": "acq", "acqTab": "now", "scen": "loaded"})
        await panel("reassign", f"card|{MOVED}")
        await page.click('#sheet [data-reassign-to$="|household-member-sees-all"]')
        await page.wait_for_timeout(ACTED + SETTLED * 2)
        card = await page.evaluate("(title)=>[...document.querySelectorAll('#view [data-part=\"card\"]')].find((one)=>one.textContent.includes(title))?.textContent || ''", MOVED)
        journal.check("5: after « Réaffecter… », the card says « demandé par Sam »", "demandé par Sam" in card, card[:200])
        await panel("follow", MOVED)
        text = await page.evaluate("()=>document.querySelector('#sheet')?.textContent || ''")
        journal.check("5: … and its panel too", "demandé par Sam" in text, text[:300])

        # 6 — « À TRAITER » FOLLOWS ITS RIGHT.
        await go("acq-guest")
        places = await page.evaluate("""() => ({ tab: !!document.querySelector('[data-acqtab="todo"]'),
          marked: document.querySelector('[data-acqtab][aria-selected="true"]')?.dataset.acqtab ?? null,
          badge: Number(document.querySelector('#nav button[data-page="acq"] [data-part="shell/tab-badge"]')?.textContent || 0) })""")
        journal.check("6: a guest without the right has no « À traiter » and no count from it",
                      not places["tab"] and places["badge"] == 0, str(places))
        journal.check("6: the tab the body draws instead is the one the bar marks", places["marked"] == "follows",
                      str(places))
        await go("acq-household")
        holder = await page.evaluate("()=>!!document.querySelector('[data-acqtab=\"todo\"]')")
        journal.check("6: a household member holds it", holder)

        # 7 — THE CREATION FORM GREYS WHAT ESCALATES.
        await go("accounts-escalation-greyed", PANEL_IN + SETTLED)
        options = await page.evaluate("""() => [...document.querySelectorAll('[data-part="accounts/create"] select[name="role"] option')]
          .map((one) => [one.value, one.disabled])""")
        greyed = {value for value, off in options if off}
        journal.check("7: « Rôle de départ » greys the roles beyond the manager's rights",
                      "household" in greyed and "local-guest" not in greyed, str(options))

        # 8 — ADMIN, IN THE ACCOUNT'S ROLE CHOICE.
        await go("accounts-detail", PANEL_IN + SETTLED)
        admin = await page.evaluate("()=>document.querySelector('#sheet [data-account-role$=\"|admin\"]')?.textContent || ''")
        journal.check("8: Admin reads « contourne tous les droits », not « 0 droit »",
                      "contourne tous les droits" in admin and "0 droit" not in admin, admin)

        # 9 — THE HEADER'S AVATAR.
        avatar = """() => { const image = document.querySelector('.topbar .avatar img');
          return { src: image && getComputedStyle(image).display !== 'none' ? image.getAttribute('src') || '' : '',
            text: document.querySelector('.topbar .avatar')?.textContent.trim() || '' }; }"""
        await go("acq-household")
        owner = await page.evaluate(avatar)
        await go("bar-household")
        lea = await page.evaluate(avatar)
        await go("no-access")
        tom = await page.evaluate(avatar)
        journal.check("9: the header shows the connected account, not izno's picture for every identity",
                      "avatar" not in lea["src"] and lea["text"] == "L" and "avatar" not in tom["src"] and tom["text"] == "T",
                      f"Léa {lea}, Tom {tom}, at rest {owner}")

        # 10 — PROFIL OF ANOTHER ACCOUNT.
        await go("profile-household")
        text = await page.evaluate("()=>document.querySelector('#view')?.textContent || ''")
        chips = await page.evaluate("()=>[...document.querySelectorAll('[data-part=\"profile/right-held\"] [data-part=\"flux/value\"]')].map((one)=>one.textContent)")
        journal.check("10: no owner's line (« web.username », « jamais à la connexion ») for another account",
                      "web.username" not in text and "jamais à la connexion" not in text, text[:200])
        journal.check("10: a held right carries no empty « — » chip", not any("—" in one for one in chips), str(chips))
        await go("no-access")
        await page.evaluate("()=>window.__store.write({ page: 'profile' })")
        await page.wait_for_timeout(SETTLED)
        text = await page.evaluate("()=>document.querySelector('#view')?.textContent || ''")
        journal.check("10: a role with no right says « aucun »", "aucun" in text.lower(), text[:300])

        # 11 — DÉCOUVRIR STAYS IN THE MENU, MARKED.
        await go("drawer-household")
        await sign_in("see-only")
        discover = await page.evaluate("()=>{ const one = document.querySelector('[data-navgo=\"discover\"]'); return one ? one.hasAttribute('data-reserved') : null; }")
        journal.check("11: Découvrir is in the menu of an account without its right, marked « Réservé »",
                      discover is True, str(discover))

        # 12 — A GUEST'S FOLLOW PANEL.
        await go("quality-own-absent", PANEL_IN + SETTLED)
        text = await page.evaluate("()=>document.querySelector('#sheet')?.textContent || ''")
        journal.check("12: a guest without the pause right reads no « Votre pause est notée »",
                      "Votre pause est notée" not in text, text[:300])

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
