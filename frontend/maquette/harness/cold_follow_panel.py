"""R176 — a follow panel opened cold on a typed address reads the medium's identity.

THE DEFECT IT HOLDS. A medium the library holds and nobody follows has its
provider identity in ONE list read — the incomplete shows — and the follow
panel answers three questions from that identity: whether a sheet stands behind
the title (« Voir la fiche »), which episodes are owned, and which poster heads
the panel. The Médiathèque asks that read for its own list. Typed onto any
other page, the panel waited for an identity nobody had asked for: no « Voir la
fiche », the owned cells drawn from a `number <= owned` threshold that puts
every hole at the end of its season, and the initials where the poster was.
The named states all start on the Médiathèque, which is why none of them saw it.

WHAT IT READS, and each reading is the ELEMENT, never a box or a count:
  - the action row's own labels, for « Voir la fiche »;
  - every episode cell's `data-ep` (title|season|episode|state), against the
    SAME panel opened by its named state on the Médiathèque, where the page
    itself loads the identity. That warm drawing must first carry an INTERNAL
    hole — a missing episode before an owned one in the same season — which a
    threshold can never draw: without it the comparison would be two
    thresholds agreeing;
  - an `<img>` inside the panel head's poster. The initials fill the same box
    at the same size, so the box says nothing.

THE WAIT HAS A DEADLINE. The identity read lands in a few hundred milliseconds;
the typed panel is read as soon as it matches, and at the latest after
IDENTITY_DEADLINE — so a build that never asks the read is a named fall, not a
rule that holds the machine's browser mutex while it waits.
"""
import asyncio
import pathlib
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, SETTLED, Journal, open_page

from playwright.async_api import async_playwright

# A medium the seeds hold as incomplete in the library and not as a follow.
TITLE = "Les aventures de Tintin"  # french-ok: a media title the seeds hold
# The named state that opens the same panel on the Médiathèque.
WARM_STATE = "followsheet-gaps"
# A page that does not ask the incomplete shows for itself.
TYPED_PATH = "acquisition?panel=" + urllib.parse.quote("follow:" + TITLE)
SHEET_ACTION = "Voir la fiche"  # french-ok: the interface text this hold asserts
IDENTITY_DEADLINE = 4000
POLL_INTERVAL = 100
MISSING_STATES = {"to_grab", "pending", "acquiring"}

PANEL = """(label)=>{
  const sheet = document.querySelector('#sheet');
  const actions = [...document.querySelectorAll('#sheet [data-part="sheet/action"]')]
    .map((action) => action.textContent.trim());
  const poster = document.querySelector('#sheet [data-part="sheet/poster"]');
  const image = poster ? poster.querySelector('img') : null;
  return {
    open: !!sheet && sheet.hasAttribute('data-open'),
    sheetAction: actions.some((action) => action.includes(label)),
    cells: [...document.querySelectorAll('#sheet [data-part="episode"]')].map((cell) => cell.dataset.ep),
    poster: !!poster,
    image: image ? (image.getAttribute('src') || '(no src)') : null,
    initials: poster && !image ? poster.textContent.trim() : null,
  };
}"""


def internal_holes(cells):
    """Lists the missing episodes that come before an owned one in their season.

    Args:
        cells: The `data-ep` values, `title|season|episode|state`.

    Returns:
        The holes, as `season|episode`.
    """
    seasons = {}
    for cell in cells:
        _, season, episode, state = cell.rsplit("|", 3)
        seasons.setdefault(season, {})[int(episode)] = state
    holes = []
    for season, episodes in seasons.items():
        owned = [number for number, state in episodes.items() if state == "in_library"]
        last_owned = max(owned, default=0)
        holes += [f"{season}|{number}" for number, state in sorted(episodes.items())
                  if state in MISSING_STATES and number < last_owned]
    return holes


async def read_until(page, done, deadline):
    """Reads the panel until a reading satisfies `done`, or the deadline passes.

    Args:
        page: The page the panel is on.
        done: The predicate a reading must satisfy.
        deadline: The longest wait, in milliseconds.

    Returns:
        The last reading, and the milliseconds it took.
    """
    waited = 0
    reading = await page.evaluate(PANEL, SHEET_ACTION)
    while not done(reading) and waited < deadline:
        await page.wait_for_timeout(POLL_INTERVAL)
        waited += POLL_INTERVAL
        reading = await page.evaluate(PANEL, SHEET_ACTION)
    return reading, waited


async def main():
    journal = Journal("R176 — a follow panel opened cold on a typed address reads the medium's identity")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")

        # WARM: the page loads the identity itself. Read once the cells stop
        # moving — the owned numbers arrive after the panel does.
        context, page = await open_page(browser)
        await page.evaluate("(id)=>window.__go(id)", WARM_STATE)
        await page.wait_for_timeout(SETTLED)
        previous = None
        warm, _ = await read_until(page, lambda reading: False, 0)
        for _ in range(IDENTITY_DEADLINE // POLL_INTERVAL):
            if warm["sheetAction"] and warm["cells"] and warm["cells"] == previous:
                break
            previous = warm["cells"]
            await page.wait_for_timeout(POLL_INTERVAL * 3)
            warm, _ = await read_until(page, lambda reading: False, 0)
        await context.close()
        holes = internal_holes(warm["cells"])
        journal.check(
            "the panel opened by its named state on the Médiathèque draws an internal "
            "hole — the served owned numbers, which no threshold can draw, so the "
            "comparison below is not two thresholds agreeing",
            warm["open"] and warm["sheetAction"] and bool(holes),
            f"{len(warm['cells'])} cell(s), holes {holes[:4]}")

        # COLD: typed onto a page that does not ask the identity read itself.
        context = await browser.new_context(**PHONE)
        page = await context.new_page()
        await page.goto(urllib.parse.urljoin(PROTOTYPE, TYPED_PATH), wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        typed, waited = await read_until(
            page,
            lambda reading: reading["sheetAction"] and reading["cells"] == warm["cells"]
            and reading["image"] is not None,
            IDENTITY_DEADLINE)
        journal.check(
            "the typed address opens the follow panel",
            typed["open"], f"/{TYPED_PATH}")
        journal.check(
            "« Voir la fiche » is offered once the identity read lands",
            typed["sheetAction"], f"after {waited} ms (deadline {IDENTITY_DEADLINE} ms)")
        only_warm = sorted(set(warm["cells"]) - set(typed["cells"]))
        journal.check(
            "the owned cells are the served numbers, the same as on the Médiathèque",
            bool(typed["cells"]) and typed["cells"] == warm["cells"],
            f"{len(typed['cells'])} cell(s); differing {only_warm[:4]}")
        journal.check(
            "the panel head draws the poster as an image, not the initials",
            typed["image"] is not None,
            f"image {typed['image']}" if typed["image"] else f"initials « {typed['initials']} »")
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
