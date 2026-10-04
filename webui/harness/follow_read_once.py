"""R512 — a medium's follow is read one way: the sheet and its delete dialog agree (B-676).

B-676, the TM Bugs report of 2026-10-02: « Quand je clique sur « supprimer, garder
le suivi », il me propose malgré mon choix de suivre la série à nouveau. La
conservation du suivi n'a pas l'air de fonctionner ». « Earl » is in Médiathèque ›
Incomplets and followed by nobody. The delete dialog counted an incomplete show
as followed (`features/library/delete-dialog.ts`, transplanted from the engine):
it said « « Earl » est suivi », offered « Supprimer, garder le suivi », and its
receipt said « Le suivi aurait été conservé » — while the sheet, which reads the
follows, said Suivi « inactif » and offered « Suivre ». The simulation touched
nothing; the dialog asserted a follow that never existed.

The sheet itself read the follow twice: its header by the base title (« Silo »
follows « Silo (2023) ») and its « Informations » row by the exact title. One
reading is left, `followsTitle` (`lib/titles.ts`), and every surface here asks it.

What this holds, by finger, on each case's sheet:

1. the sheet's « Suivi » row reads the follow the seeds hold, and no « Suivre »
   is offered under a row that says « actif »;
2. its « Supprimer de la médiathèque » opens a dialog that says « est suivi »
   and offers « garder le suivi » exactly when the sheet says « actif »;
3. « Earl » (incomplete, not followed) reads not followed everywhere, and
   « Furious (2026) » (followed as « Furious ») reads followed everywhere.

Red before the repair: « Earl »'s dialog says it is followed; « Furious
(2026) »'s « Informations » row says « inactif » under a header that says it is
followed, and its dialog does not warn.
"""
import asyncio
import json
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, PROTOTYPE, Journal, browser_channel, chrome_launch_args, open_page, settle

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
FOLLOW_LABEL = WORDS["screens"]["media"]["follow"]
ACTIVE = WORDS["states"]["active"]
DELETE = WORDS["verbs"]["library"]["delete"]
# « « {{title}} » est suivi. » — what follows the title, the words the warning says.
FOLLOWED_WORDS = DELETE["followedOne"].split("}}")[-1].strip(" »")
KEEP = DELETE["deleteAndKeep"]

# The sheet, the title, and what the seeds make of it.
CASES = [
    ("media/tvdb/75397", "Earl", False),
    ("media/tvdb/468000", "Furious (2026)", True),
]

READ_SHEET = """(label) => {
  const rows = [...document.querySelectorAll('section[data-part="screen"] [data-part="key-value"]')];
  const row = rows.find((one) => one.firstElementChild?.textContent.trim() === label);
  return { follow: row ? row.lastElementChild.textContent.trim() : null,
           offered: !!document.querySelector('section[data-part="screen"] [data-follow]'),
           del: !!document.querySelector('section[data-part="screen"] [data-del]') };
}"""

READ_DIALOG = """() => {
  const dialog = document.querySelector('#dlg[data-open]');
  if (!dialog) return null;
  return { text: dialog.textContent,
           actions: [...dialog.querySelectorAll('button')].map((one) => one.textContent.trim()) };
}"""


async def hold(journal):
    """Opens each case's sheet, reads its follow, then its delete dialog."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))

        for address, title, followed in CASES:
            await page.goto(PROTOTYPE + address, wait_until="load")
            await page.evaluate("()=>window.__loadingDone?.()")
            await settle(page)
            await page.wait_for_timeout(ACTED)
            sheet = await page.evaluate(READ_SHEET, FOLLOW_LABEL)
            if not journal.check(f"{title}: the sheet has its « Suivi » row and its delete",
                                 sheet["follow"] is not None and sheet["del"], str(sheet)):
                continue
            active = sheet["follow"] == ACTIVE
            journal.check(f"{title}: the sheet reads the follow the seeds hold",
                          active == followed,
                          f"« Suivi » reads {sheet['follow']!r}, the seeds say followed={followed}")
            # AN OWNED MEDIUM OFFERS NO « SUIVRE » — its actions are « Re-scraper » and
            # « Supprimer » — so the offer can only contradict a row that says « actif ».
            journal.check(f"{title}: no « Suivre » is offered under a « Suivi » that says « {ACTIVE} »",
                          not (active and sheet["offered"]),
                          f"« Suivi » {sheet['follow']!r} with « Suivre » offered={sheet['offered']}")

            await page.tap('section[data-part="screen"] [data-del]')
            await page.wait_for_timeout(ACTED)
            dialog = await page.evaluate(READ_DIALOG)
            if not journal.check(f"{title}: « Supprimer » opens its dialog", dialog is not None, "no open dialog"):
                continue
            says = FOLLOWED_WORDS in dialog["text"]
            keeps = KEEP in dialog["actions"]
            journal.check(f"{title}: the dialog says « {FOLLOWED_WORDS} » exactly when the sheet says « {ACTIVE} »",
                          says == active,
                          f"dialog followed={says}, sheet « Suivi » {sheet['follow']!r} — two readings of one follow")
            journal.check(f"{title}: « {KEEP} » is offered exactly for a followed medium",
                          keeps == followed, f"actions {dialog['actions']}")
            await page.evaluate("()=>document.querySelector('#dlg[data-open] [data-dialog-dismiss]')?.click()")
            await page.wait_for_timeout(ACTED)

        await context.close()
        await browser.close()
    journal.summary(errors)


def main():
    journal = Journal("R512 — a medium's follow is read one way: the sheet and its delete dialog agree (B-676)")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
