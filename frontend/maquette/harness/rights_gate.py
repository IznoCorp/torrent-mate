"""R427 — the gate offers Plex first, the password behind a disclosure, and `auth.password` decides who a password admits (§ 17).

DESIGN maquette-l18 § 3.1, § 5 (R-L18-q, R-L18-r), round 8 Q10 = B, F47.

1. R-L18-q — THE HOST'S PAGE IS UNCHANGED: `index.html`'s `login:markup` region is byte for
   byte the base branch's (`develop`, `main` before the git flow's cut-over), and nothing of the
   Plex block is in it — the design host extracts it.
2. R-L18-q — PLEX FIRST: the gate draws « Se connecter avec Plex » and keeps the password form
   CLOSED behind « Utiliser un mot de passe »; tapped, the disclosure opens the form.
3. R-L18-r — PLEX UNREACHABLE opens the disclosure by itself and says why.
4. R-L18-r — A PASSWORD FOR AN ACCOUNT WITHOUT `auth.password` is refused with its reason (403);
   the owner's password (Admin holds the right) walks through.
5. R-L18-r — A Default-only Plex account is admitted, read-only: it lands on the Médiathèque,
   with no bar.
6. A landing whose account read is CANCELLED — the cache cleared under it — lands nowhere and
   raises nothing.
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


# After the git flow's cut-over the checkout serving tm-design stands on `develop`
# (docs/features/git-flow/DESIGN.md § 3.6); before it, `develop` does not exist.
BASES = ("develop", "main")


def base_region(root=ROOT):
    """The `login:markup` region as the base branch holds it: `develop`, else `main`.

    A CI checkout is one commit deep and carries neither remote branch: each is
    fetched, one commit deep, when it is absent — never compared against
    nothing.

    Args:
        root: The `frontend/maquette` directory of the checkout to read.

    Returns:
        The region, markers included.

    Raises:
        subprocess.CalledProcessError: When neither branch can be read or fetched.
    """
    def git(*arguments):
        return subprocess.run(["git", *arguments], capture_output=True, text=True, cwd=root, check=True).stdout

    def known(ref):
        return subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref],
                              capture_output=True, cwd=root).returncode == 0

    for branch in BASES:
        ref = f"origin/{branch}"
        if not known(ref):
            fetched = subprocess.run(["git", "fetch", "--depth=1", "origin", f"{branch}:refs/remotes/{ref}"],
                                     capture_output=True, cwd=root).returncode == 0
            if not fetched and branch != BASES[-1]:
                continue
        return REGION.search(git("show", f"{ref}:frontend/maquette/design/index.html")).group(0)


async def main():
    journal = Journal("R427 — Plex first, the password behind a disclosure")
    here = REGION.search((ROOT / "design/index.html").read_text(encoding="utf-8")).group(0)
    journal.check("R-L18-q: the host's password region is byte for byte the base branch's", here == base_region())
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

        # A LANDING WHOSE ACCOUNT READ IS CANCELLED — the cache cleared under it,
        # as every driven state's reset does — lands nowhere and raises nothing.
        # The account read is held back so the clears fall inside it: on a slow
        # runner the persistence walk's zero-wait drive did exactly that, and
        # the page threw « CancelledError » twice.
        await page.evaluate("""()=>{
          const ask = window.fetch;
          window.__heldFetch = ask;
          window.fetch = async (...asked) => {
            if (String(asked[0]?.url ?? asked[0]).includes('/api/auth/me'))
              await new Promise((done) => setTimeout(done, 800));
            return ask(...asked);
          };}""")
        before = len(errors)
        await page.evaluate("(id)=>window.__go(id)", "signin-plex-bare")
        for _ in range(12):
            await page.wait_for_timeout(150)
            await page.evaluate("()=>window.__queries.clear()")
        await page.wait_for_timeout(ACTED)
        await page.evaluate("()=>{window.fetch = window.__heldFetch;}")
        journal.check("R-L18-r: a landing whose account read is cancelled raises nothing",
                      len(errors) == before, str(errors[before:]))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
