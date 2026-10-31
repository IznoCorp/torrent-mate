"""R515 — what is typed in a search field stays as typed: the page writes nothing into it, and it asks for a capital only where a title is typed (B-690, B-694).

« quand je tape quelque chose, la deuxième lettre est à chaque fois en majuscule »
(Laura, iPhone SE, the installed app): « star » typed in the « + » search came out
« STar ». THE MECHANISM, measured: the field was CONTROLLED by the address, which
the router answers a task after the keystroke, and React puts a controlled field
whose state did not move in its event back to the value it rendered — so every
keystroke rewrote the field to the text before it (`""` after the first letter),
then to the new one. On an iPhone the emptied field re-armed the keyboard's
capital, and the second letter came out upper case.

WHAT IS READ, for every search field of the maquette (the « + » search and its
identifier field, « Filtrer par nom » on Suivis, the Médiathèque's and the
settings' search), each reached by its named state:
  1. typing « star » with the keyboard, the page writes NOTHING into the focused
     field — every assignment to its `value` while it has the focus is counted;
  2. the field holds « star »;
  3. it asks for no correction (`autocorrect` off) in every one of them, and for
     the keyboard's first capital (`autocapitalize="sentences"`) only where a TITLE
     is typed — the « + » search, « Filtrer par nom », the Médiathèque's search
     (B-694: « la première lettre en majuscule aussi et ça c'est dommage »). The
     identifier field and the settings' search (setting keys, typed as written)
     ask for no capital at all.

WHAT NO ENGINE HERE SHOWS: the capital itself is the iPhone keyboard's; the
reporter confirms it on the device. The rewrite that arms it is what is held.
"""
import asyncio

from common import SETTLED, Journal, open_page, read_at, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

# Every assignment to an input's `value` made while that input has the focus.
#
# INSTALLED BEFORE THE APPLICATION RUNS, and it has to be: React tracks a field's
# value through the prototype's setter AS IT WAS when the field was created, so a
# spy laid on the prototype afterwards never sees React's writes. Installed later,
# this rule passed on the very code that rewrote the field on every keystroke.
SPY = """(() => {
  const own = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
  window.__fieldWrites = [];
  Object.defineProperty(HTMLInputElement.prototype, 'value', {
    configurable: true,
    get() { return own.get.call(this); },
    set(value) {
      if (this === document.activeElement) window.__fieldWrites.push(String(value));
      own.set.call(this, value);
    },
  });
})();"""

# What the field says of itself once typed in.
READ = """(selector) => {
  const field = document.querySelector(selector);
  return { value: field?.value ?? null, writes: [...window.__fieldWrites],
           capitalize: field?.getAttribute('autocapitalize') ?? null,
           correct: field?.getAttribute('autocorrect') ?? null };
}"""

# The fields, each with the named state that draws it.
FIELDS = (
    ("acq-add-empty", "#addq", "the « + » search", "sentences"),
    ("acq-add-empty", "#byidv", "the « + » identifier", "off"),
    ("acq-follows-list", "#follq", "« Filtrer par nom »", "sentences"),
    ("lib-grid", "#libq", "the Médiathèque's search", "sentences"),
    ("settings", "#qsettings", "the settings' search", "off"),
)


async def main():
    journal = Journal("R515 — what is typed stays as typed")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        await context.add_init_script(script=SPY)
        await page.reload(wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for state, selector, name, capital in FIELDS:
            await read_at(page, state, "() => null", wait=SETTLED)
            field = page.locator(selector)
            if selector == "#byidv":
                # The identifier field lives inside its disclosure, closed at rest.
                await page.click('[data-part="add/by-id"] summary')
            await field.wait_for(state="visible")
            await field.click()
            await page.evaluate("() => { window.__fieldWrites.length = 0; }")
            await field.press_sequentially("star", delay=60)
            await page.wait_for_function("() => window.__mocks.inFlight() === 0")
            read = await page.evaluate(READ, selector)
            journal.check(f"{state}, {name}: typing writes nothing into the field",
                          read["writes"] == [], str(read["writes"]))
            journal.check(f"{state}, {name}: the field holds what was typed", read["value"] == "star",
                          str(read["value"]))
            journal.check(f"{state}, {name}: capital asked as `{capital}`, no correction asked",
                          read["capitalize"] == capital and read["correct"] == "off",
                          str({"autocapitalize": read["capitalize"], "autocorrect": read["correct"]}))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
