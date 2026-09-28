"""R250 — the oracle reads a frame the harness's welcome hint cannot reach (B-558).

THE DEFECT, MEASURED BEFORE IT WAS NAMED. The named state `pwa-ios` did not
render the same twice: read by the oracle at load, 3 readings in 10 carried a
visible toast and a hidden floating action button, 2 more caught the toast
mid-fade; read alone, none. The only message raised was the harness's own
welcome hint (`design/src/harness/panel.ts`), a timer of 900 ms from the boot
that stays silent in measuring mode. The oracle never entered measuring mode:
it dismissed the toast by a click (`neutralise`) and raced the timer instead.
Alone, `pwa-ios` is read before the timer is due; at load it is read after it,
and a hint landing between the last dismissal and the measurement is recorded
as the state's own rendering.

WHAT IT HOLDS, through the oracle's OWN functions — `open_frame`,
`measure_state`, the recipe and the region table — never through a copy of
them, so the frame read here is the frame the oracle reads:

  1. `pwa-ios`, driven in the oracle's order (the states before it first),
     is read with the message host OUT OF THE FRAME — `display: none`, what
     measuring mode makes of it, so no message can be read there, whole or
     mid-fade — and the floating action button drawn: the two regions that
     diverged.
  2. Once the hint's timer is due, no message is on screen. A dismissal by
     click wins only when it comes AFTER the timer; this hold waits the timer
     out and asks the message host whether anything is showing. It reads the
     application's state rather than a rectangle, so it still bites where the
     host is hidden: a hint raised in the state takes the action button off
     screen whatever the stylesheet draws.

The measuring mode itself is not read here: it is a style class on the root,
and a rule anchored on a style class dies with it. What the mode is FOR — the
hint staying silent — is what hold 2 reads.

READ `READINGS` TIMES, each on a fresh frame, because the symptom is a race:
a single reading proves nothing about a defect that showed 3 times in 10.

WHAT IT DOES NOT READ: whether the hint itself works for the operator. That is
the harness's own chrome, no part of the interface, and nothing here asks it to
appear.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from common import Journal  # noqa: E402 — the path above is what makes it importable

import oracle  # noqa: E402 — the path above is what makes it importable

# The state that diverged, and the two regions it diverged on.
STATE = "pwa-ios"
MESSAGE_REGION = "shell/toast"
ACTION_REGION = "shell/action-button"

# Fresh frames read per run. The divergence was measured at 3 in 10 at load;
# ten readings make a run that misses it by chance unlikely rather than
# impossible, which is why hold 2 exists beside the symptom.
READINGS = 10

# The instant, in milliseconds since the frame's navigation began, by which the
# hint's timer is certainly due: it is armed at the boot with 900 ms, and the
# boot was measured raising it 674-835 ms after the frame opened. The wait is
# not a settle — it is a timer queued AFTER the hint's, and timers run in the
# order they fall due, so the hint has had its turn when this one resolves.
HINT_DUE_BY_MS = 3000
WAIT_PAST_THE_HINT = """(dueBy)=>new Promise((resolve)=>
  setTimeout(resolve, Math.max(0, dueBy - performance.now())))"""


def out_of_frame(reading):
    """Says whether a region reading is a host present but taken out of the frame.

    Args:
        reading: The oracle's measurement of the region, or `None`.

    Returns:
        True when the region exists and is `display: none`. An absent region is
        not accepted: a selector that stopped matching reads nothing, which is
        not the same as a message nobody can see.
    """
    if reading is None:
        return False
    return reading["style"].get("display") == "none"


def drawn(reading):
    """Says whether a region reading is a control on screen.

    Args:
        reading: The oracle's measurement of the region, or `None`.

    Returns:
        True when the region exists and is not `display: none`.
    """
    if reading is None:
        return False
    return reading["style"].get("display") != "none"


async def read_once(browser, recipe, regions, journal, index, errors):
    """Opens one frame the way the oracle does and reads `pwa-ios` in it.

    Args:
        browser: A launched Playwright browser.
        recipe: The oracle's `probe` block.
        regions: The oracle's region table.
        journal: The rule's journal.
        index: Which reading this is, for the detail lines.
        errors: Where uncaught page errors are collected.
    """
    context, page = await oracle.open_frame(browser, recipe)
    page.on("pageerror", lambda error: errors.append(str(error)))
    states = await page.evaluate("()=>window.__states()")
    if STATE not in states:
        journal.check(f"reading {index}: `{STATE}` is a named state", False,
                      f"__states() has {len(states)} ids, none of them `{STATE}`")
        await context.close()
        return
    reading = None
    for state in states[:states.index(STATE) + 1]:
        reading = await oracle.measure_state(page, state, regions, recipe)
    message, action = reading.get(MESSAGE_REGION), reading.get(ACTION_REGION)
    journal.check(f"reading {index}: `{STATE}` is read with the message host out of the frame",
                  out_of_frame(message), f"{MESSAGE_REGION} = {message}")
    journal.check(f"reading {index}: `{STATE}` is read with the action button drawn",
                  drawn(action), f"{ACTION_REGION} = {action}")

    await page.evaluate(WAIT_PAST_THE_HINT, HINT_DUE_BY_MS)
    on_screen = await page.evaluate("()=>window.__toast?.read() ?? null")
    shown = bool(on_screen and on_screen.get("shown"))
    journal.check(f"reading {index}: no message is raised once the hint's timer is due",
                  not shown, f"__toast.read() = {on_screen}")
    await context.close()


async def main():
    """Reads `pwa-ios` through the oracle `READINGS` times."""
    journal = Journal("R250 — the oracle's reading of pwa-ios carries no harness hint")
    recipe = oracle.load_recipe()
    regions = oracle.load_regions()
    errors = []
    async with oracle.browser_driver()() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        for index in range(1, READINGS + 1):
            await read_once(browser, recipe, regions, journal, index, errors)
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
