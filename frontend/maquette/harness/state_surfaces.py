"""R90 — the error surfaces are one component, and the oracle can see them at all.

WHAT THIS RULE EXISTS FOR, and it is the second half rather than the first. Six
surfaces drew « could not load » by asking the dying engine for a string and
handing it to `dangerouslySetInnerHTML`. They are one component now
(`ui/state-surfaces.tsx`), which the oracle proves moved nothing. What the
oracle cannot prove is that the component is REACHED — a page that stopped
drawing an error surface at all renders less, and « renders less » is a
divergence only where a region measures it.

AND THE REASON THIS RULE IS WORTH ITS BROWSER is B-108. The oracle's own
`neutralise` used to tear `.note` nodes out of React's tree before measuring;
React then threw `NotFoundError` on the next reconciliation, the subtree died,
and four states were RECORDED AS BLANK — `acq-now-error`, `acq-now-loading`,
`arr-error`, `arr-loading`, every one of them a loading or an error surface. The
instrument was blind exactly here. So this rule reads the surfaces DIRECTLY,
by their own text and their own control, and it does not depend on a rectangle.

WHAT IT DOES NOT READ, said before what it does:

  - It does not read whether the copy is RIGHT. That is the i18n resource's, and
    the string was extracted from `legacy.js` rather than retyped precisely so
    that no reader has to judge it.
  - It does not read the LOADING surfaces. Their placeholders carry no text and
    no control; the oracle measures them, and now it measures them non-blank.
  - It does not read whether a retry re-asks anything REAL. No surface is wired
    to the query cache yet — that is L09's later phases, and asserting it now
    would be a rule certifying the fixture.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, Journal, open_page

# Every named state that draws an error surface, and what the surface is about.
# READ OFF `states.js`, never guessed: a first version of this list invented
# `sys-error` and `maint-error`, which do not exist, and the rule crashed on the
# third state rather than quietly measuring three of five.
# <sub>`grep -B3 'phase: "error"' design/src/engine/states.js`</sub>
ERROR_STATES = {
    "arr-error": "ce qui arrive",                  # french-ok: the app's rendered output
    "acq-now-error": "ce qui vous attend",         # french-ok: the app's rendered output
    "acq-follows-error": "vos suivis",             # french-ok: the app's rendered output
    "lib-error": "votre médiathèque",              # french-ok: the app's rendered output
    "system-error": None,
}

# What every one of them says, whatever its subject. Extracted from the engine
# into `i18n/fr.json`; quoted here because it is the app's rendered output, and
# a rule that asserted a KEY would pass over a resource serving nothing.
SHARED_BODY = "Le serveur n'a pas répondu"    # french-ok: the app's rendered output


async def hold(journal):
    """Drives every error state and reads the surface it draws."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        _context, page = await open_page(browser, **PHONE)
        # EVERY PAGE ERROR THE WALK RAISES, collected from the page itself.
        # This rule was written for B-108 — twenty-two React `NotFoundError`s
        # over 83 states, which nothing read — and it carried a comment saying
        # so at the end of the walk with no listener anywhere in the file.
        raised: list[str] = []
        page.on("pageerror", lambda error: raised.append(str(error)))
        # UNDER THE MEASURING CLASS, deliberately: this is the document the
        # oracle judges, and B-108 is what happens when the two differ.
        await page.evaluate("()=>document.documentElement.classList.add('measuring')")

        seen = 0
        for state, subject in sorted(ERROR_STATES.items()):
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(120)
            read = await page.evaluate(
                """() => {
                    const surface = document.querySelector('[data-part="surface-error"]');
                    if (!surface) return { drawn: false };
                    return {
                        drawn: true,
                        role: surface.getAttribute("role"),
                        text: surface.textContent,
                        height: surface.getBoundingClientRect().height,
                        retry: !!surface.querySelector('[data-part="surface-error/retry"]'),
                    };
                }""")
            if not journal.check(f"{state} draws an error surface", read["drawn"]):
                continue
            seen += 1
            journal.check(f"{state} announces itself", read["role"] == "alert",
                          f'role={read["role"]!r}')
            journal.check(f"{state} says what went wrong",
                          SHARED_BODY in read["text"],
                          f'{len(read["text"])} characters')
            if subject:
                journal.check(f"{state} names its own subject",
                              subject in read["text"], f"looked for « {subject} »")
            journal.check(f"{state} offers a way out", read["retry"])
            # THE HEIGHT IS READ HERE TOO, and not because this rule measures
            # geometry. A surface whose subtree died renders at the container's
            # own padding — 28 px, measured — while a drawn one is over a
            # hundred. That is B-108's signature, and a rule that watched only
            # for the TEXT would have passed over a blank the oracle recorded.
            journal.check(f"{state} is really drawn, not a collapsed container",
                          read["height"] > 100, f'{read["height"]} px')

        journal.check("every declared error state was reached",
                      seen == len(ERROR_STATES),
                      f"{seen}/{len(ERROR_STATES)} — a corpus smaller than the "
                      f"declaration is a rule reading less than it says")

        # No React error anywhere in the walk. B-108 was 22 of them over 83
        # states, and nothing read them.
        journal.check("no error was raised walking the error states",
                      not raised, "; ".join(raised[:3]) or "none")

        await browser.close()


def main():
    journal = Journal("R90 — the error surfaces are drawn, and drawn once")
    asyncio.run(hold(journal))
    journal.summary()


if __name__ == "__main__":
    main()
