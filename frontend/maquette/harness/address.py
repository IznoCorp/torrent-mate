"""R68 — an unknown address breaks nothing, and an absent account is not invented.

Two surfaces production serves that the prototype did not draw, and they share
one discipline: answer honestly what you do not have.

· **A wrong address.** It is the one input an interface never controls — a
  stale bookmark, a shared link, a renamed route. The prototype answered it by
  looking up a page table that did not carry the id and calling `.render()` on
  nothing: a TypeError, and the whole frame stopped. That is the worst possible
  answer to a bookmark. It now renders, names what was asked for, and offers a
  way out (DOIT-7 — never a dead end).

· **The account surface.** There is ONE account on this server. Drawing a list
  of colleagues to fill the screen is what §13 forbids: an interface showing
  data the system does not hold teaches its operator to distrust the rest of
  it. The place of the others is marked and EMPTY, and says why.

Everything the account surface claims about the session is compared against
`web.json5` — the real file, not a number written beside it.
"""
import asyncio
import os
import pathlib
import re

from common import Journal, open_page
from playwright.async_api import async_playwright

WEB = pathlib.Path(os.path.expanduser("~/.torrentmate/config/web.json5"))

READ = """() => ({
  overflow: document.querySelector('#port').scrollWidth - document.querySelector('#port').clientWidth,
  page: state.page,
  text: document.querySelector('#view').textContent.replace(/\\s+/g, ' ').trim(),
  empty: (document.querySelector('#view [data-part="empty-state"] b') || {}).textContent || '',
  exits: [...document.querySelectorAll('#view button')].map((b) => ({
    text: b.textContent.trim(),
    target: Object.keys(b.dataset).join(','),
    inert: b.disabled,
  })),
  facts: [...document.querySelectorAll('#view [data-part="flux"] [data-part="flux/row"]')].map((x) => ({
    l: x.querySelector('[data-part="flux/name"]').textContent.trim(),
    v: x.querySelector('[data-part="flux/value"]').textContent.trim(),
    k: (x.querySelector('[data-part="flux/key"]') || {}).textContent || '',
  })),
})"""


def web_config():
    """What `web.json5` really holds, or None when it is not on this machine."""
    if not WEB.is_file():
        return None
    raw = WEB.read_text()
    # JSON5 with comments — the two values this rule compares are read by name
    # rather than by parsing a dialect no standard library knows.
    def field(name):
        m = re.search(rf'\b{name}\s*:\s*"?([^",\n]+)"?', raw)
        return m.group(1).strip() if m else None
    return {"username": field("username"), "ttl": field("session_ttl_hours")}


async def main():
    journal = Journal("R68 — an unknown address, and an account that is not invented")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(b)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        # ── a wrong address ────────────────────────────────────────────────
        # Driving to it and reading the frame are guarded SEPARATELY: when the
        # interface throws, the drive throws with it and the probe dies on a
        # traceback — a crash is a failure nobody can read, and the mutation
        # that restores this very defect proved it by reporting nothing at all.
        try:
            await pg.evaluate(
                "()=>applyState({page: 'cette-page-n-existe-pas', phase: 'ready'})")
        except Exception as trouble:  # noqa: BLE001 — the throw IS the finding
            errors.append(str(trouble))
        await pg.wait_for_timeout(350)
        try:
            lost = await pg.evaluate(READ)
        except Exception as trouble:  # noqa: BLE001
            errors.append(str(trouble))
            lost = {"overflow": 0, "page": None, "text": "", "empty": "",
                    "exits": [], "facts": []}
        journal.check("an unknown address does not bring the interface down",
                      not errors and len(lost["text"]) > 40,
                      f"{len(lost['text'])} characters · errors {errors}")
        # Everything after this measures the surface, so what the drive raised
        # is not carried into those verdicts as well.
        errors.clear()
        journal.check("it lands on a surface made for it",
                      lost["page"] == "404", lost["page"])
        journal.check("it NAMES the address that was asked for",
                      "cette-page-n-existe-pas" in lost["text"],
                      lost["text"][:90])
        journal.check("it says nothing is broken",
                      "cassé" in lost["text"], lost["text"][:90])
        exits = [s for s in lost["exits"] if s["target"] and not s["inert"]]
        journal.check("it offers at least one way out, and none is inert",
                      len(exits) >= 2 and len(exits) == len(lost["exits"]),
                      str([s["text"] for s in lost["exits"]]))
        journal.check("nothing spills past the frame", lost["overflow"] <= 0,
                      f"{lost['overflow']}px")

        # ── the account surface, reached the way one reaches it ────────────
        await pg.evaluate("()=>applyState({page: 'acq', phase: 'ready'})")
        await pg.wait_for_timeout(250)
        await pg.tap('[data-sheet="utilisateur"]')
        await pg.wait_for_timeout(420)
        menu = await pg.evaluate(
            """()=>[...document.querySelectorAll('[data-part="sheet/actions"] [data-part="sheet/action"]')].map((b) => ({
                 text: b.textContent.trim(), inert: b.disabled,
                 target: Object.entries(b.dataset).map(([k, v]) => k + '=' + v).join(',')}))""")
        profile = [m for m in menu if "Profil" in m["text"]]
        journal.check("the user menu carries the profile entry",
                      bool(profile), str([m["text"] for m in menu]))
        journal.check("and it leads somewhere",
                      profile and not profile[0]["inert"] and profile[0]["target"],
                      str(profile))

        await pg.tap('[data-part="sheet/actions"] [data-part="sheet/action"]:has-text("Profil")')
        await pg.wait_for_timeout(420)
        account = await pg.evaluate(READ)
        journal.check("the menu entry does open the account surface",
                      account["page"] == "profile", account["page"])
        journal.check("the place of the other accounts is marked AND EMPTY",
                      "pas encore" in account["empty"].lower(), account["empty"])
        journal.check("nothing spills past the account's frame",
                      account["overflow"] <= 0, f"{account['overflow']}px")

        # ── what it claims is what `web.json5` holds ───────────────────────
        real = web_config()
        if real is None:
            journal.check("what the account states comes from web.json5", False,
                          "web.json5 absent — the comparison could not be made")
        else:
            usernames = [f["v"] for f in account["facts"] if f["k"] == "web.username"]
            journal.check("the username shown is the one in the configuration",
                          usernames == [real["username"]],
                          f"{usernames} vs {real['username']}")
            durations = [f for f in account["facts"] if f["k"] == "web.session_ttl_hours"]
            journal.check("the session duration shown is the one in the configuration",
                          durations and real["ttl"] in " ".join(
                              f"{d['v']} {d.get('s', '')}" for d in durations)
                          or (durations and real["ttl"] == "720" and "30 jours" in durations[0]["v"]),
                          f"{[d['v'] for d in durations]} vs {real['ttl']} hours")

        # No colleague is invented. What identifies an account here is an
        # address, so every address on the surface must be the real one — a
        # capitalised-words regex reads two adjacent headings as a person and
        # would have failed on « Vous Identifiant », which names nobody.
        addresses = set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", account["text"]))
        real_one = await pg.evaluate("()=>ACCOUNT.mail")
        journal.check("no other account is invented to fill the screen",
                      addresses <= {real_one},
                      f"{len(addresses)} address(es): {', '.join(sorted(addresses)) or 'none'}")

        journal.check("no JS error", not errors, str(errors))
        await ctx.close()
        await b.close()

    journal.summary()


asyncio.run(main())
