"""R457 (R-L23-f) — « Créer et publier un torrent » is held by its own right, on both sides.

L23 DESIGN § 0.2 (organisation ruling 21): the design fixes the LIST of rights —
`trackers.upload`, distinct from `trackers.control` — and proposes its starting
value, the same as `trackers.control`'s: held by nobody but Admin, through the
ACL bypass; who holds it afterwards is « Comptes »' configuration. L18's own
convention: « every rule proving a right names its two halves » — the act ABSENT
from the DOM for an account without the right (§ 17 point 1), the call refused
403 when forced.

1. THE LIST: `trackers.upload` is a right of the contract's closed `Right` set,
   named in the interface's words, and no shipped role carries it (Admin holds
   it by bypass).
2. ADMIN (the owner): the act is offered on a pair where nothing cross-seeds.
3. A ROLE GIVEN `trackers.control` AND NOT `trackers.upload`: the same pair
   offers « Chercher un cross-seed » and NOT « Créer et publier un torrent »;
   the upload forced by hand answers 403 — the two rights independent.
4. A ROLE GIVEN `trackers.upload` AND NOT `trackers.control`: the act is offered
   and the search is not; the upload asked answers 202.
5. A ROLE WITH NO TRACKER RIGHT (the seeded household member): no act, and the
   forced upload answers 403.
6. The torrent card's swipe drawer never carries the upload, whoever reads it.

Red before the wiring: the contract has no `trackers.upload`, and the act and its
call follow `trackers.control`.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT.parents[1] / "contract/openapi.json").read_text(encoding="utf-8"))
SEEDS = json.loads((ROOT / "design/src/mocks/seeds/accounts.json").read_text(encoding="utf-8"))
WORDS = json.loads((ROOT / "design/src/i18n/fr.json").read_text(encoding="utf-8"))["access"]
RIGHT = "trackers.upload"
UPLOADABLE = "e5c6f4e9bc5d619c15aa476ec0e278f2267bf0bb"
TRACKER = "v3x.club"
STATE = "torrents-cross-seed-upload"
# The role the invented account below is seeded with; its rights are set per check.
ROLE = "household"
MEMBER = "household-member"
BASE = next(role["rights"] for role in SEEDS["roles"] if role["id"] == ROLE)

PAIR = f"""() => {{
  const row = document.querySelector('#sheet[data-open] [data-part="torrents/cross-seed-row"][data-tracker="{TRACKER}"]');
  return row === null ? null : {{
    upload: !!row.querySelector('[data-part="torrents/cross-seed-upload"]'),
    search: !!row.querySelector('[data-part="torrents/cross-seed-search"]'),
  }};
}}"""
DRAWER = "() => document.querySelectorAll('#view [data-part=\"swipe/action\"][data-cross-seed-upload]').length"
# Signs one account in, with its role's rights set as « Comptes » would, and drops the page's reads.
AS = """async ([identity, role, rights]) => {
  if (role !== null) window.__mocks.setRoleRights(role, rights);
  window.__mocks.setIdentity(identity);
  await window.__queries.resetQueries();
}"""
FORCE = f"""async () => (await fetch(
  `/api/v1/torrents/{UPLOADABLE}/cross-seed/${{encodeURIComponent('{TRACKER}')}}/upload`, {{ method: 'POST' }})).status"""


async def as_identity(page, identity, rights=None):
    """Enters the upload's named state signed in as one account, its role holding `rights` when given."""
    await page.evaluate(f"()=>window.__go('{STATE}')")
    await page.wait_for_timeout(SETTLED)
    await page.evaluate(AS, [identity, ROLE if rights is not None else None, rights or []])
    await page.wait_for_timeout(SETTLED)


async def pair(page):
    """Opens the uploadable origin's panel and reads its pair on the tracker."""
    await page.evaluate("(entry) => window.__panel.produce('torrent', entry)", f"{UPLOADABLE}:c411")
    await page.wait_for_timeout(ACTED)
    return await page.evaluate(PAIR)


async def main():
    journal = Journal("R457 (R-L23-f) — « Créer et publier un torrent » held by `trackers.upload`, on both sides")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── 1. the list ──────────────────────────────────────────────────
        listed = CONTRACT["components"]["schemas"]["Right"]["enum"]
        journal.check("1 the contract's closed Right set names trackers.upload, beside trackers.control",
                      RIGHT in listed and "trackers.control" in listed, repr(listed))
        worded = WORDS["rights"]["trackers"].get("upload"), WORDS["holders"]["trackers"].get("upload")
        journal.check("1 the right is named in the interface's words, its default said", all(worded), repr(worded))
        carriers = [role["id"] for role in SEEDS["roles"] if RIGHT in role["rights"]]
        journal.check("1 no shipped role carries it: Admin alone, by its bypass (DESIGN § 0.2)", not carriers,
                      repr(carriers))

        # ── 2. Admin ─────────────────────────────────────────────────────
        await page.evaluate(f"()=>window.__go('{STATE}')")
        await page.wait_for_timeout(SETTLED)
        owner = await pair(page)
        journal.check("2 Admin is offered the act where nothing cross-seeds", bool(owner and owner["upload"]),
                      repr(owner))

        # ── 3. trackers.control without trackers.upload ──────────────────
        control = [*BASE, "trackers.view", "trackers.control"]
        await as_identity(page, MEMBER, control)
        drawer = await page.evaluate(DRAWER)
        controlled = await pair(page)
        journal.check("3 a role with trackers.control and not trackers.upload: the search offered, the upload ABSENT",
                      bool(controlled and controlled["search"] and not controlled["upload"]), repr(controlled))
        status = await page.evaluate(FORCE)
        journal.check("3 the same account forcing the upload is refused 403", status == 403, str(status))

        # ── 4. trackers.upload without trackers.control ──────────────────
        await as_identity(page, MEMBER, [*BASE, "trackers.view", RIGHT])
        uploader = await pair(page)
        journal.check("4 a role with trackers.upload and not trackers.control: the upload offered, the search absent",
                      bool(uploader and uploader["upload"] and not uploader["search"]), repr(uploader))
        status = await page.evaluate(FORCE)
        journal.check("4 the same account's upload is answered 202", status == 202, str(status))

        # ── 5. no tracker right ──────────────────────────────────────────
        await as_identity(page, MEMBER)
        bare = await page.evaluate(PAIR)
        journal.check("5 the seeded household member: no act anywhere", not (bare and (bare["upload"] or bare["search"])),
                      repr(bare))
        status = await page.evaluate(FORCE)
        journal.check("5 the seeded household member forcing the upload is refused 403", status == 403, str(status))

        # ── 6. the swipe drawer ──────────────────────────────────────────
        journal.check("6 the torrent card's swipe drawer carries no upload, the controlling role's included",
                      drawer == 0, str(drawer))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
