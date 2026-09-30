"""R427 — the gate offers Plex first, the password behind a disclosure, and `auth.password` decides who a password admits (§ 17).

DESIGN maquette-l18 § 3.1, § 5 (R-L18-q, R-L18-r), round 8 Q10 = B, F47.

1. R-L18-q — THE HOST'S PAGE IS UNCHANGED: `index.html`'s `login:markup` region is byte for
   byte `main`'s, and nothing of the Plex block is in it — the design host extracts it.
2. R-L18-q — PLEX FIRST: the gate draws « Se connecter avec Plex » and keeps the password form
   CLOSED behind « Utiliser un mot de passe »; tapped, the disclosure opens the form.
3. R-L18-r — PLEX UNREACHABLE opens the disclosure by itself and says why.
4. R-L18-r — A PASSWORD FOR AN ACCOUNT WITHOUT `auth.password` is refused with its reason (403);
   the owner's password (Admin holds the right) walks through.
5. R-L18-r — A Default-only Plex account is admitted, read-only: it lands on the Médiathèque,
   with no bar.
"""
import asyncio
import pathlib
import re
import subprocess

from common import SETTLED, ACTED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGION = re.compile(r"<!-- login:markup:start -->.*?<!-- login:markup:end -->", re.S)

GATE = """() => ({
  shown: !document.querySelector('#login').hidden,
  plex: !!document.querySelector('[data-part="login/plex-submit"]')?.checkVisibility(),
  form: !!document.querySelector('#loginform')?.checkVisibility(),
  unreachable: !!document.querySelector('[data-part="login/plex-unreachable"]')?.checkVisibility(),
  refusal: document.querySelector('#loginerr')?.checkVisibility() ? document.querySelector('#loginerr').textContent : null,
  page: window.__store.read().state.page,
  bar: document.querySelector('#nav')?.checkVisibility() || false })"""


def main_region():
    """The `login:markup` region as `main` holds it."""
    shown = subprocess.run(["git", "show", "origin/main:frontend/maquette/design/index.html"],
                           capture_output=True, text=True, cwd=ROOT, check=True).stdout
    return REGION.search(shown).group(0)


async def main():
    journal = Journal("R427 — Plex first, the password behind a disclosure")
    here = REGION.search((ROOT / "design/index.html").read_text(encoding="utf-8")).group(0)
    journal.check("R-L18-q: the host's password region is byte for byte main's", here == main_region())
    journal.check("R-L18-q: nothing of Plex is in the region the host extracts", "plex" not in here.lower())

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def at(state, wait=SETTLED):
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(wait)
            return await page.evaluate(GATE)

        rest = await at("signin")
        journal.check("R-L18-q: the gate offers Plex, the password closed", rest["plex"] and not rest["form"], str(rest))
        await page.click('[data-part="login/password-disclosure"]')
        await page.wait_for_timeout(SETTLED)
        opened = await page.evaluate(GATE)
        journal.check("R-L18-q: « Utiliser un mot de passe » opens the form", opened["form"], str(opened))

        down = await at("signin-plex-unreachable-open", ACTED)
        journal.check("R-L18-r: Plex unreachable opens the password by itself, and says why",
                      down["form"] and down["unreachable"], str(down))

        refused = await at("signin-password-refused", ACTED)
        words = await page.evaluate("()=>window.__i18n.t('screens.gate.passwordRefused')")
        statuses = await page.evaluate("()=>window.__mocks.answered().filter((one)=>one.operationId==='signIn').map((one)=>one.status)")
        journal.check("R-L18-r: a guest's password is refused with its reason", refused["shown"]
                      and refused["refusal"] == words and 403 in statuses, f"{refused['refusal']} {statuses}")

        await at("signin-password-open")
        await page.fill('#loginform input[name="username"]', "izno")
        await page.fill('#loginform input[name="password"]', "secret")
        await page.click('[data-part="login/submit"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        owner = await page.evaluate(GATE)
        journal.check("R-L18-r: the owner's password walks through (Admin holds the right)", not owner["shown"], str(owner))

        bare = await at("signin-plex-bare", ACTED + SETTLED)
        journal.check("R-L18-r: a Default-only Plex account lands on the Médiathèque, with no bar",
                      not bare["shown"] and bare["page"] == "lib" and not bare["bar"], str(bare))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
