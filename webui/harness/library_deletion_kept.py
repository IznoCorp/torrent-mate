"""R526 — a deletion answers medium by medium, and a kept medium is said kept, with its reason (operator ruling R2).

The operator, 2026-10-05 (R2, « Raison par médias »): `deleteLibraryItems` answers, per medium,
`deleted` or `kept` with its reason — a seeding still owed (with the date it is owed until when
the store knows it), a disk unplugged, a folder that would not go — and the interface shows the
reason in place of removing the row. Constitution § 8, « Rien en silence ».

1. THE WIRE: a kept medium answers `kept`, its reason and, for a seeding owed, its date; it is
   still held. In a request of several, the others go and answer `deleted`, reason and date null.
2. THE THREE KEPT STATES (`lib-delete-kept-seed`, `-disk`, `-failed`): once the removal is
   confirmed, the dialog drawn after it names the medium with its reason in `fr.json`'s words
   (the date included for the seeding), no toast says it was deleted, and its row is still drawn.
3. THE PARTLY DELETED STATE (`lib-delete-partly`): the dialog counts what went against what was
   asked and names only the medium kept; the two that went are no longer drawn, the kept one is.
4. THE YEAR-LESS INCOMPLETE SHOW (`lib-incomplete-yearless`, N1): a show served `year: null`
   reads what it is missing and nothing else — never « null · ».
"""
import asyncio

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

ASK = """async ([method, path, body]) => {
  const answer = await fetch(path, body === null ? { method } : { method, body: JSON.stringify(body) });
  return { status: answer.status, body: await answer.json().catch(() => null) };
}"""

MEMBERSHIP = "/api/v1/library/membership?provider={provider}&providerId={providerId}"

# The seed's media the states name, each by the identity its row carries.
ANIMANIACS = {"provider": "tvdb", "providerId": "72879"}
ANIMANIACS_TITLE = "Les Animaniacs"
PARTLY = ["Les Animaniacs", "La cour de récré", "Earl"]
PARTLY_KEPT = "La cour de récré"
# The kept states' date: 12 October 2026, 20:00 UTC (the state's own constant).
OWED_UNTIL = 1791835200

# What the dialog drawn after the confirmation says, and what the screen still draws.
DRAWN = """() => {
  const dialog = document.querySelector('#dlg[data-open]');
  return {
    heading: dialog?.querySelector('h2, [data-part="dialog/heading"]')?.textContent?.trim() ?? null,
    text: dialog?.textContent ?? '',
    buttons: dialog ? [...dialog.querySelectorAll('[data-part="dialog/button"]')].map((b) => b.textContent.trim()) : [],
    toast: document.querySelector('#toastmsg')?.textContent ?? '',
    rows: [...document.querySelectorAll('[data-del]')].map((one) => one.dataset.del),
  };
}"""

# The seeding's date in the interface's words: its day, then its time of day, as the dialog composes them.
OWED_WORDS = """(epoch) => {
  const until = new Date(epoch * 1000);
  const day = new Intl.DateTimeFormat(window.__i18n.language, { day: 'numeric', month: 'long' }).format(until);
  const two = (value) => String(value).padStart(2, '0');
  const time = window.__i18n.t('surfaces.clock.timeOfDay', { hour: two(until.getHours()), minute: two(until.getMinutes()) });
  return window.__i18n.t('verbs.library.delete.keptSeedOwed', { day, time });
}"""


async def main():
    journal = Journal("R526 — a deletion answers medium by medium, and a kept medium is said kept")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def ask(method, path, body=None):
            return await page.evaluate(ASK, [method, path, body])

        async def say(key, **params):
            return await page.evaluate("([k, p])=>window.__i18n.t(k, p)", [key, params])

        async def held(ref):
            return (await ask("GET", MEMBERSHIP.format(**ref)))["body"]["inLibrary"]

        # ── 1. the wire ─────────────────────────────────────────────────────
        await page.evaluate("()=>window.__mocks.reset()")
        await page.evaluate("([ref, until])=>window.__mocks.setDeletionKept(ref, 'seed_owed', until)",
                            [ANIMANIACS, OWED_UNTIL])
        answered = await ask("DELETE", "/api/v1/library/items", {"media": [ANIMANIACS]})
        journal.check("a medium still owed its seeding answers kept, its reason and its date",
                      answered["status"] == 200
                      and answered["body"] == {"media": [{"ref": ANIMANIACS, "outcome": "kept",
                                                          "reason": "seed_owed", "owedUntil": OWED_UNTIL}]},
                      str(answered))
        journal.check("and it is still held", await held(ANIMANIACS) is True)
        await page.evaluate("()=>window.__mocks.reset()")
        await page.evaluate("(ref)=>window.__mocks.setDeletionKept(ref, 'disk_unreachable')", ANIMANIACS)
        film = {"provider": "tmdb", "providerId": "98566"}
        both = await ask("DELETE", "/api/v1/library/items", {"media": [film, ANIMANIACS]})
        outcomes = [(one["outcome"], one["reason"], one["owedUntil"]) for one in (both["body"] or {}).get("media", [])]
        journal.check("in a request of two, the other goes and answers deleted, reason and date null",
                      both["status"] == 200 and outcomes == [("deleted", None, None), ("kept", "disk_unreachable", None)],
                      str(both))

        # ── 2. the three kept states ────────────────────────────────────────
        for state, reason_key in (("lib-delete-kept-seed", None),
                                  ("lib-delete-kept-disk", "verbs.library.delete.keptDiskUnreachable"),
                                  ("lib-delete-kept-failed", "verbs.library.delete.keptFailed")):
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED + ACTED + SETTLED)
            drawn = await page.evaluate(DRAWN)
            reason = (await page.evaluate(OWED_WORDS, OWED_UNTIL)) if reason_key is None else await say(reason_key)
            heading = await say("verbs.library.delete.keptHeadingOne", title=ANIMANIACS_TITLE)
            done = await say("verbs.library.delete.done", title=ANIMANIACS_TITLE)
            journal.check(f"{state}: the dialog after the confirmation names « {ANIMANIACS_TITLE} » kept, with « {reason} »",
                          heading in drawn["text"] and reason in drawn["text"], str(drawn)[:400])
            journal.check(f"{state}: and offers nothing but to close",
                          drawn["buttons"] == [await say("verbs.library.delete.close")], str(drawn["buttons"]))
            journal.check(f"{state}: no toast says it was deleted", done not in drawn["toast"], repr(drawn["toast"]))
            journal.check(f"{state}: and its row is still drawn", ANIMANIACS_TITLE in drawn["rows"],
                          str(drawn["rows"][:12]))

        # ── 3. the partly deleted state ─────────────────────────────────────
        await page.evaluate("(id)=>window.__go(id)", "lib-delete-partly")
        await page.wait_for_timeout(SETTLED + ACTED + SETTLED)
        drawn = await page.evaluate(DRAWN)
        heading = await say("verbs.library.delete.partlyHeading", deleted=2, asked=3)
        reason = await page.evaluate(OWED_WORDS, OWED_UNTIL)
        gone = [title for title in PARTLY if title != PARTLY_KEPT]
        journal.check("lib-delete-partly: the dialog counts two gone of three asked, and names the one kept",
                      heading in drawn["text"] and f"{PARTLY_KEPT}{reason}" in drawn["text"]
                      and not any(title in drawn["text"] for title in gone),
                      str(drawn)[:400])
        still = {title: await held(ref) for title, ref in (await page.evaluate(
            "(titles)=>[...window.__librarySelection(titles).values()].map((one)=>[one.title, one.ref])", PARTLY))}
        journal.check("lib-delete-partly: the two that went are no longer held, the kept one is",
                      still == {title: title == PARTLY_KEPT for title in PARTLY}, str(still))

        # ── 4. the year-less incomplete show ────────────────────────────────
        await page.evaluate("(id)=>window.__go(id)", "lib-incomplete-yearless")
        await page.wait_for_timeout(SETTLED + ACTED)
        served = await ask("GET", "/api/v1/library/incomplete")
        show = next((one for one in served["body"] if one["title"] == ANIMANIACS_TITLE), None)
        journal.check(f"« {ANIMANIACS_TITLE} » is served without a year", show is not None and show["year"] is None,
                      str(show))
        wanted = await say("screens.library.incompleteSubNoYearMany", count=show["aired"] - show["owned"]) if show else ""
        line = await page.evaluate("""(title) => {
          const card = [...document.querySelectorAll('[data-part="card"]')]
            .find((one) => one.querySelector('[data-part="card/title"]')?.textContent === title);
          return card?.querySelector('[data-part="card/subtitle"]')?.textContent ?? null; }""", ANIMANIACS_TITLE)
        journal.check("and its line says what it is missing and nothing else", line == wanted and "null" not in (line or ""),
                      f"{line!r} vs {wanted!r}")

        journal.check("no error was raised", not errors, " · ".join(errors[:3]))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
