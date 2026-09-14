"""R189 — a redraw REPLACES the panel's entry; it never stacks another.

D-L13-1's second half, and B-397's subject. A panel that re-produces itself —
because what it shows changed — is the SAME panel, still standing on the same
entry. Writing a new entry for each redraw makes leaving it cost as many Backs
as the reader made edits, and nothing on screen says so: the panel looks
identical after the first redraw and after the fourth.

WHAT IS READ, and why it is the history and not the screen. `history.length`
before the first edit and after the third, then ONE Back and the panel must be
gone. A rule that only checked « one Back closes it » would pass on a panel that
stacked three entries and happened to be closed by the first Back's own redraw;
a rule that only counted entries would pass on a panel that writes none and
cannot be reopened. The two together are the shape.

THE EDIT IS MADE THE WAY A READER MAKES IT — into the field, committed by the
panel's own button — and not through `window.__changeSetting`. That seam was
tried first and this rule passed on it: it files a pending edit without
re-producing the panel, so it measures the one path that cannot stack an entry.
A hold must drive what the defect travels through.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, Journal  # noqa: E402

from playwright.async_api import async_playwright  # noqa: E402

journal = Journal("R189 — a redraw replaces its entry")

# The settings page itself. The RUBRIC is not named here and the row is not
# either: they are found the way `settings_editing.py` finds them — by the TYPE
# the panel can answer — because a literal id written into a rule falls the day
# a fixture is reworded, for a reason that is not a defect.
ADDRESS = "settings"

READ = """()=>({length: history.length,
                index: (history.state || {}).__TSR_index ?? null,
                panel: !!document.querySelector('#sheet')?.hasAttribute('data-open')})"""


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        context = await browser.new_context(**PHONE)
        page = await context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(PROTOTYPE + ADDRESS, wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        await page.wait_for_timeout(420)

        rubrics = await page.evaluate(
            """()=>[...document.querySelectorAll('[data-topic]')]
                 .map((one) => one.dataset.topic).filter((one) => one !== 'secrets')""")
        row = None
        for rubric in rubrics:
            await page.click(f'[data-topic="{rubric}"]')
            await page.wait_for_timeout(420)
            typed = await page.evaluate(
                """()=>{const topics = window.__queries
                    ?.getQueryData(['/api/config/schema']) || [];
                  const text = topics.flatMap((one) => one.r)
                    .find((one) => one.type === 'path' || one.type === 'text');
                  return text ? (text.f + ':' + text.c) : null;}""")
            if typed and await page.query_selector(f'[data-setting="{typed}"]'):
                row = typed
                break
            await page.evaluate("()=>history.back()")
            await page.wait_for_timeout(420)
        if not row:
            journal.check("a rubric holding a setting one can type into is drawn",
                          False, f"none among {rubrics}")
            journal.summary()
            return

        await page.click(f'[data-setting="{row}"]')
        await page.wait_for_timeout(420)
        opened = await page.evaluate(READ)
        journal.check("the row opens its setting panel", opened["panel"],
                      f"{opened}")

        # THREE EDITS MADE THE WAY A READER MAKES THEM: into the panel's own
        # field, committed by its own button. `window.__changeSetting` was used
        # first and the rule went GREEN — the seam writes the pending edit
        # without re-producing the panel, so it measured a path that cannot
        # stack an entry at all. The commit button is what re-produces, and the
        # re-production is the subject.
        for attempt in range(3):
            await page.fill('#sheetin [data-part="field/input"]', f"/tmp/r189-{attempt}")
            await page.click(f'#sheetin [data-commitsetting="{row}"]')
            await page.wait_for_timeout(320)
            if not await page.query_selector('#sheetin [data-part="field/input"]'):
                # The panel closed on a commit, which is a different behaviour
                # from the one under test — said rather than worked around.
                journal.check(f"the panel stands through edit {attempt + 1}",
                              False, "it closed on the commit")
                break
        edited = await page.evaluate(READ)
        journal.check(
            "three edits write NO new entry",
            edited["length"] == opened["length"]
            and edited["index"] == opened["index"],
            f"{opened['length']}/{opened['index']} -> "
            f"{edited['length']}/{edited['index']} — a redraw that pushes makes "
            "leaving the panel cost one Back per edit, and the panel looks the "
            "same after every one of them")

        await page.go_back()
        await page.wait_for_timeout(520)
        after = await page.evaluate(READ)
        journal.check(
            "and ONE Back closes the panel, whatever was edited in it",
            not after["panel"],
            f"the panel still stands at index {after['index']} after one Back")

        journal.check("no error was raised", not errors, " · ".join(errors[:3]))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
