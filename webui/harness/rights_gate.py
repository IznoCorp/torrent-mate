"""R427 — the gate offers Plex first, the password behind a disclosure, and the account's kind decides who a password admits (§ 17).

DESIGN maquette-l18 § 3.1, § 5 (R-L18-q, R-L18-r), round 8 Q10 = B, F47.

1. R-L18-q — THE HOST'S PAGE IS UNCHANGED: `index.html`'s `login:markup` region is byte for
   byte the base branch's (`develop`, `main` before the git flow's cut-over), and nothing of the
   Plex block is in it — the design host extracts it. Two things are set aside before comparing,
   on both sides: every `data-words*` attribute — the key of an element's words, which the boot or
   the host uses to word the page in the reader's language (FG-1 B) — and the region's one
   comment, the one that opens « The unauthenticated entry screen. » and explains them, matched
   exactly once on each side; the markers stay, and any other comment is compared like markup (an
   abrupt-closing `<!-->` closes at once: what follows it is live). Any other change to the region
   is still one.
2. R-L18-q — PLEX FIRST: the gate draws « Se connecter avec Plex » and keeps the password form
   CLOSED behind « Utiliser un mot de passe »; tapped, the disclosure opens the form.
3. R-L18-r — PLEX UNREACHABLE opens the disclosure by itself and says why.
4. R-L18-r — A PASSWORD FOR A PLEX-LINKED ACCOUNT is refused with the one refusal every failed
   attempt gets (401 `auth.refused`, O-K1-4 anti-enumeration); the owner's fallback walks through.
5. R-L18-r — A Plex account on the Invité Plex role (O-K1-4) is admitted, read-only: it lands on the Médiathèque,
   with no bar.
6. A landing whose account read is CANCELLED — the cache cleared under it — lands nowhere and
   raises nothing.
"""
import asyncio
import json
import pathlib
import re
import subprocess

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
OWNER_EMAIL = json.loads((ROOT / "design/src/mocks/seeds/account.json").read_text(encoding="utf-8"))["email"]
REGION = re.compile(r"<!-- login:markup:start -->.*?<!-- login:markup:end -->", re.S)
# What `comparable` sets aside: the key of an element's words, and the region's ONE known comment.
# An attribute goes with ONE of the blanks around it — the one after it when there is one — so
# the line breaks and indents that stay are the base branch's own.
WORDS_KEY = re.compile(r'(\s+)data-words(?:-[\w-]+)?="[^"]*"(\s*)')
# THAT COMMENT, BY ITS OPENING, not any comment: a comment planted in the region — and `<!-->`,
# which the parser closes at once, leaving the markup after it live — is compared like markup.
COMMENT = re.compile(r"<!-- The unauthenticated entry screen\.(?:(?!-->).)*-->", re.S)


def comparable(region):
    """The region as R-L18-q compares it: its `data-words*` attributes and its one comment set aside.

    Args:
        region: The `login:markup` region, markers included.

    Returns:
        The same text, byte for byte, without them.

    Raises:
        ValueError: When the region does not hold its one comment exactly once.
    """
    unkeyed = WORDS_KEY.sub(lambda found: found.group(1) if found.group(2) else "", region)
    stripped, found = COMMENT.subn("", unkeyed)
    if found != 1:
        raise ValueError(f"R-L18-q: the login:markup region holds its one comment {found} times, not once")
    return stripped

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
        root: The `webui` directory of the checkout to read.

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
        # A base cut before the prototype left `frontend/maquette/` holds the
        # envelope at its old place; the region is the same file either way.
        try:
            envelope = git("show", f"{ref}:webui/design/index.html")
        except subprocess.CalledProcessError:
            envelope = git("show", f"{ref}:frontend/maquette/design/index.html")
        return REGION.search(envelope).group(0)


async def main():
    journal = Journal("R427 — Plex first, the password behind a disclosure")
    here = REGION.search((ROOT / "design/index.html").read_text(encoding="utf-8")).group(0)
    journal.check(
        "R-L18-q: the host's password region is byte for byte the base branch's, its words' keys and comment aside",
        comparable(here) == comparable(base_region()),
    )
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
        words = await page.evaluate("()=>window.__i18n.t('refusals.auth.refused')")
        statuses = await page.evaluate("()=>window.__mocks.answered().filter((one)=>one.operationId==='signIn').map((one)=>one.status)")
        journal.check("R-L18-r: a Plex-linked account's password is refused like any failed attempt", refused["shown"]
                      and refused["refusal"] == words and 401 in statuses, f"{refused['refusal']} {statuses}")

        await at("signin-password-open")
        await page.fill('#loginform input[name="username"]', OWNER_EMAIL)
        await page.fill('#loginform input[name="password"]', "secret")
        await page.click('[data-part="login/submit"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        owner = await page.evaluate(GATE)
        journal.check("R-L18-r: the owner's fallback password walks through", not owner["shown"], str(owner))

        bare = await at("signin-plex-bare", ACTED + SETTLED)
        journal.check("R-L18-r: a Plex account on the Invité Plex role lands on the Médiathèque, with no bar",
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
            if (String(asked[0]?.url ?? asked[0]).includes('/api/v1/auth/me'))
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
