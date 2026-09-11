"""R141 — the way out of the phone frame is remembered, and only a desktop reads it back.

A PREFERENCE, NOT A MOMENT. The way out of the frame was a checkbox and nothing
else, so a reload put the operator back inside the phone every time he had left
it. It is a preference now: the choice is written to `localStorage` when the
control changes and read back before any module runs, so a reload opens where
he left it — the shape the appearance already has, one inline script beside it.

WHERE THE SCRIPT LIVES IS PART OF WHAT IS HELD. It is harness chrome, so it is
an inline script in `design/index.html` beside the control — never a module of
the app, never the dying engine — and it goes when the frame goes. The key is
the harness's: it is written in that document and in no file under
`design/src/`, so nothing the app ships can read it or come to depend on it.

WHAT IT REFUSES, hold by hold:

  * a press out of the frame that does not write the choice, and a press back
    that does not take it back;
  * a reload that opens inside the frame after the operator left it, and one
    that opens out of the frame after he came back. Both are read in the FIRST
    frames: an init script, which runs before the document's own, listens for
    `document.readyState` leaving `loading` and records the checkbox's
    `checked` at that moment. `interactive` is reached once every inline script
    has run and BEFORE any deferred or module script does, so what it records
    is the document's own script and nothing else. A read after load would
    prove nothing: by then the app's modules have run, and any of them could
    have checked the box — the reading would be green over a restore that the
    harness's script never did, which is the one place this rule says it lives;
  * the remembered choice reaching a window where the frame is not drawn.
    There is nothing to leave there, and a checked box would still take
    `overflow: clip` off the device, which the frame declares outside any
    breakpoint. That reading is compared with the same page BEFORE anything was
    stored, never with a value typed here;
  * the same narrow window forgetting the choice: it is a desktop's preference,
    and a narrow window is no reason to erase it;
  * the key being written anywhere the app could read it.

WHAT IT DOES NOT READ. Whether a restored page FLASHES the frame before it
leaves it is a paint, and no assertion here can time one. What is held is the
fact a flash would be made of: the box's state when parsing ends.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, Journal, open_page
from desktop_frame import CHECKBOX, DESKTOP, DEVICE, LABEL  # noqa: E402 - the path line above must run first

# The one name the two ends share: the control's script writes it, and this
# rule reads it. Typed here because it is a contract, like the appearance's.
STORAGE_KEY = "tm-desktop-switch"
OUT_OF_THE_FRAME = "out-of-the-frame"

DOCUMENT = ROOT / "design" / "index.html"
APPLICATION_SOURCES = ROOT / "design" / "src"

# Records the box's state when parsing ends — `interactive` is reached once
# every inline script has run and before any deferred or module script does,
# so what it records is the document's own script and nothing a module did.
FIRST_FRAMES = """(checkbox)=>{
  window.__firstFrameChecked = null;
  document.addEventListener('readystatechange', () => {
    if (window.__firstFrameChecked === null && document.readyState !== 'loading') {
      const box = document.querySelector(checkbox);
      window.__firstFrameChecked = box ? box.checked : 'missing';
    }
  }, true);
}"""

READ = """([checkbox, device, key])=>{
  const element = document.querySelector(device);
  const rectangle = element.getBoundingClientRect();
  let stored = null;
  try { stored = localStorage.getItem(key); } catch (error) { stored = 'unreadable'; }
  return {
    checked: document.querySelector(checkbox).checked,
    firstFrame: window.__firstFrameChecked ?? null,
    stored,
    framed: Math.round(rectangle.width) < innerWidth,
    box: [rectangle.x, rectangle.y, rectangle.width, rectangle.height].map(Math.round),
    overflow: getComputedStyle(element).overflow,
    viewport: [innerWidth, innerHeight],
  };
}"""

AFTER_A_PRESS = 400
AFTER_A_RELOAD = 400


async def read(page):
    """What the control, the device and the storage say, right now.

    Args:
        page: The page to read.

    Returns:
        The reading, as the page script returns it.
    """
    return await page.evaluate(READ, [CHECKBOX, DEVICE, STORAGE_KEY])


async def reload(page):
    """Reloads the page and waits for the document to be read again.

    Args:
        page: The page to reload.

    Returns:
        The reading after the reload.
    """
    await page.reload(wait_until="load")
    await page.wait_for_timeout(AFTER_A_RELOAD)
    return await read(page)


async def measure_desktop(browser, journal):
    """Holds that a press is remembered across a reload, both ways.

    Args:
        browser: A launched Playwright browser.
        journal: The run's journal.
    """
    context, page = await open_page(browser, **DESKTOP)
    await context.add_init_script(script=f"({FIRST_FRAMES})({CHECKBOX!r})")
    fresh = await read(page)
    journal.check(
        "a desktop with nothing remembered opens inside the frame",
        fresh["stored"] is None and not fresh["checked"] and fresh["framed"],
        f"at {fresh['viewport']} — stored {fresh['stored']!r}, checked "
        f"{fresh['checked']}, device {fresh['box']}")

    await page.click(LABEL)
    await page.wait_for_timeout(AFTER_A_PRESS)
    pressed = await read(page)
    journal.check(
        "one press out of the frame writes the choice",
        pressed["stored"] == OUT_OF_THE_FRAME and pressed["checked"]
        and not pressed["framed"],
        f"stored {pressed['stored']!r}, checked {pressed['checked']}, device "
        f"{pressed['box']}")

    left = await reload(page)
    journal.check(
        "and a reload opens OUT of the frame, the box already checked when "
        "parsing ends and before any module runs",
        left["firstFrame"] is True and left["checked"] and not left["framed"],
        f"checked when parsing ended {left['firstFrame']!r}, after load "
        f"{left['checked']}, device {left['box']} at {left['viewport']}, "
        f"stored {left['stored']!r}")

    await context.close()

    # THE WAY BACK IS READ ON A PAGE OF ITS OWN. Driven on from the page above,
    # its premise would be that page's reload: a restore that failed would leave
    # the box unchecked, the press below would check it, and the way back would
    # fall too — one defect named twice. Here the operator leaves the frame by
    # hand and comes back, whatever the reload above did.
    context, page = await open_page(browser, **DESKTOP)
    await context.add_init_script(script=f"({FIRST_FRAMES})({CHECKBOX!r})")
    await page.click(LABEL)
    await page.wait_for_timeout(AFTER_A_PRESS)
    await page.click(LABEL)
    await page.wait_for_timeout(AFTER_A_PRESS)
    back = await read(page)
    journal.check(
        "the press back into the frame takes the choice back",
        back["stored"] is None and not back["checked"] and back["framed"],
        f"stored {back['stored']!r}, checked {back['checked']}, device "
        f"{back['box']}")

    returned = await reload(page)
    journal.check(
        "and a reload then opens INSIDE the frame",
        returned["firstFrame"] is False and not returned["checked"]
        and returned["framed"],
        f"checked when parsing ended {returned['firstFrame']!r}, after load "
        f"{returned['checked']}, device {returned['box']}, stored "
        f"{returned['stored']!r}")
    await context.close()


async def measure_phone(browser, journal):
    """Holds that a phone-sized window neither applies nor forgets the choice.

    Args:
        browser: A launched Playwright browser.
        journal: The run's journal.
    """
    context, page = await open_page(browser)
    await context.add_init_script(script=f"({FIRST_FRAMES})({CHECKBOX!r})")
    before = await read(page)
    await page.evaluate(
        "([key, value])=>localStorage.setItem(key, value)",
        [STORAGE_KEY, OUT_OF_THE_FRAME])
    remembered = await reload(page)
    journal.check(
        "a window where the frame is not drawn does not apply a desktop's "
        "remembered choice: the box stays unchecked and the device reads what "
        "it read before anything was stored",
        remembered["firstFrame"] is False and not remembered["checked"]
        and remembered["overflow"] == before["overflow"]
        and remembered["box"] == before["box"],
        f"at {remembered['viewport']} — checked when parsing ended "
        f"{remembered['firstFrame']!r}, after load {remembered['checked']}; "
        f"overflow {remembered['overflow']!r} against {before['overflow']!r} "
        f"before, device {remembered['box']} against {before['box']}")
    journal.check(
        "and it does not forget it either",
        remembered["stored"] == OUT_OF_THE_FRAME,
        f"stored {remembered['stored']!r}")
    await context.close()


def hold_the_key_is_the_harness(journal):
    """Holds that the key lives in the harness's document and nowhere the app ships.

    Args:
        journal: The run's journal.
    """
    document = DOCUMENT.read_text(encoding="utf-8")
    readers = sorted(
        str(path.relative_to(ROOT)) for path in APPLICATION_SOURCES.rglob("*")
        if path.is_file() and path.suffix in {".ts", ".tsx", ".js", ".css", ".json", ".html"}
        and STORAGE_KEY in path.read_text(encoding="utf-8", errors="replace"))
    journal.check(
        "the key is written in the harness's document, beside the control",
        STORAGE_KEY in document,
        f"« {STORAGE_KEY} » in {DOCUMENT.relative_to(ROOT)}")
    journal.check(
        "and in no file the app ships",
        not readers,
        f"found under {APPLICATION_SOURCES.relative_to(ROOT)}: {readers}")


async def hold(journal):
    """Runs the desktop and the phone readings against one browser.

    Args:
        journal: The run's journal.
    """
    hold_the_key_is_the_harness(journal)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        await measure_desktop(browser, journal)
        await measure_phone(browser, journal)
        await browser.close()
    journal.summary()


def main():
    """Runs the rule."""
    journal = Journal(
        "R141 — the way out of the phone frame is remembered, and only a desktop "
        "reads it back")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
