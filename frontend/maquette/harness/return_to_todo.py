"""R205 — the candidates screen returns to « À traiter », and offers no « Suivant ».

After an exit from the candidates screen the operator is back on « À traiter »,
the tab open, whichever way the screen was reached. Opened from the list, the
exit is a POP: the list's own entry, which carries its tab in the address, comes
back. Opened cold from a link, the entry beneath the screen is the page it
belongs to, laid by the boot — and it holds « À traiter » whatever tab the
device remembers, because the list the screen answers is that one.

« Suivant » is gone, and so is the progression « n sur m en attente » that
existed to serve it: « À traiter »'s tab count carries the number.

WHAT IT HOLDS, each in a fresh context:

  from the list  « À traiter » opened at its address, Lucky's « Résoudre »
                 tapped, then each exit — a candidate picked, « Laisser tel
                 quel » — lands on `/acquisition?tab=todo` with « À traiter »
                 selected, and `history.length` is the one the screen stood at:
                 the exit popped, it did not push.
  cold           `/resolution/Lucky` opened from nothing, with « En cours »
                 remembered on the device; the pick lands on « À traiter », and
                 `history.length` did not grow.
  the absence    on the tie, where several folders wait: no `[data-next]` and
                 no « en attente » anywhere on the screen.

WHAT IT DOES NOT READ: the exit's effect on the queue (R57's), the toast and its
undo, or an exit reached from Arrivées' « Ça coince ».
"""
import asyncio
import json
import pathlib
from urllib.parse import quote

from common import ACTED, PAGE_PATHS, PHONE, PROTOTYPE, SETTLED, Journal
from playwright.async_api import async_playwright

ROOT = PROTOTYPE.rstrip("/")
LIST = ROOT + PAGE_PATHS["acq"] + "?tab=todo"
# The blocked card the detour starts from, read off its own seed so the rule
# follows the fixture; its folder is the one its pending decision names.
BLOCKED_SEED = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds/blocked.json"
FOLDER = json.loads(BLOCKED_SEED.read_text(encoding="utf-8"))[0]["title"]
COLD = ROOT + "/resolution/" + quote(FOLDER)
# The tab the device remembers on the cold walk: anything but « À traiter », so
# a floor that merely opened the remembered tab cannot pass.
REMEMBERED = "now"
KEY = "acquisition-tab"

SCREEN = '[data-part="screen"][data-open][data-key^="resolution:"]'
EXITS = (("a candidate picked", "[data-resolve]"), ("« Laisser tel quel »", "[data-leave]"))

WHERE = """() => ({
  address: decodeURIComponent(location.pathname + location.search),
  selected: document.querySelector('[data-acqtab][aria-selected="true"]')?.dataset.acqtab ?? null,
  screen: !!document.querySelector('""" + SCREEN + """'),
  depth: history.length,
})"""


async def fresh(browser, script=None):
    """A fresh context and page, its storage prepared before any document loads."""
    context = await browser.new_context(**PHONE)
    if script:
        await context.add_init_script(script)
    page = await context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    return context, page, errors


async def settle(page, address):
    """Opens an address and waits for the page to settle."""
    await page.goto(address, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.evaluate("()=>window.__mocks?.quiet?.()")
    await page.wait_for_timeout(SETTLED)


async def leave_by(page, selector):
    """Takes one exit off the screen, and reads where it landed."""
    present = await page.evaluate("(s)=>document.querySelector(s)!==null", selector)
    if present:
        await page.evaluate("(s)=>document.querySelector(s).click()", selector)
        await page.wait_for_timeout(ACTED + SETTLED)
    return present, await page.evaluate(WHERE)


def landed(journal, label, present, on_screen, after):
    """Holds one exit's landing: « À traiter », at its address, by a pop."""
    wanted = PAGE_PATHS["acq"] + "?tab=todo"
    journal.check(f"{label}: the exit exists on the screen", present and on_screen["screen"],
                  f"exit present {present}, screen open {on_screen['screen']}")
    journal.check(f"{label}: it lands on « À traiter », its tab in the address",
                  after["address"] == wanted and after["selected"] == "todo" and not after["screen"],
                  f"{after['address']!r}, selected {after['selected']!r} — wanted {wanted!r} and 'todo'")
    journal.check(f"{label}: the exit popped — history.length did not grow",
                  after["depth"] == on_screen["depth"],
                  f"{on_screen['depth']} on the screen → {after['depth']} after the exit")


async def main():
    """Runs the rule."""
    journal = Journal("R205 — the candidates screen returns to « À traiter », no « Suivant »")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")

        for label, selector in EXITS:
            context, page, errors = await fresh(browser)
            await settle(page, LIST)
            await page.evaluate(
                "(folder)=>document.querySelector(`[data-resolution=\"${CSS.escape(folder)}\"]`)?.click()",
                FOLDER)
            await page.wait_for_timeout(ACTED + SETTLED)
            on_screen = await page.evaluate(WHERE)
            present, after = await leave_by(page, selector)
            landed(journal, f"from the list, {label}", present, on_screen, after)
            journal.check(f"no JS error (from the list, {label})", not errors, str(errors))
            await context.close()

        script = f"try {{ localStorage.setItem({json.dumps(KEY)}, {json.dumps(REMEMBERED)}); }} catch (error) {{}}"
        context, page, errors = await fresh(browser, script)
        await settle(page, COLD)
        on_screen = await page.evaluate(WHERE)
        present, after = await leave_by(page, EXITS[0][1])
        landed(journal, "cold, a candidate picked", present, on_screen, after)
        journal.check("no JS error (cold)", not errors, str(errors))
        await context.close()

        context, page, errors = await fresh(browser)
        await settle(page, ROOT)
        await page.evaluate("()=>window.__go('acq-resolution-tie')")
        await page.wait_for_timeout(SETTLED)
        read = await page.evaluate("""(s) => {
          const screen = document.querySelector(s);
          return { screen: !!screen, next: !!document.querySelector('[data-next]'),
                   text: screen ? screen.innerText : '' };
        }""", SCREEN)
        journal.check("the tie draws the screen", read["screen"], str(read["screen"]))
        journal.check("no « Suivant » on the screen", not read["next"], "a [data-next] is drawn")
        journal.check("no progression « n sur m en attente » on the screen",
                      "en attente" not in read["text"],  # french-ok: the progression's own words, asserted absent
                      read["text"][:200])
        journal.check("no JS error (the tie)", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
