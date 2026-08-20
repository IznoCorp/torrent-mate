#!/usr/bin/env python3
r"""Does a migrated PAGE draw what the legacy drew, byte for byte?

A tool, not a rule — it is run BY HAND while a page is being converted, and it
stops being runnable the moment the legacy renderer it compares against is
deleted. That order is the point: prove first, delete after.

    python3 frontend/maquette/fidelity.py viewSystemLegacy systeme systeme-panne

It needs the legacy renderer reachable from `window.__referentiel` under a name
of its own (`viewSystemLegacy: viewSystem`), added for the proof and removed
with the renderer.

TWO WAYS TO NAME THE LEGACY SIDE, and the second exists because of a page
whose markup is not what its renderer returns. `viewArrivals()` returned the
whole page, so the comparison could call it and diff the string. `viewLibrary()`
returns a SKELETON — an empty `#libitems`, an empty `#libcount` — which the
fragment fills afterwards, and diffing against that string would report every
row as a divergence. So the legacy side can also be RECORDED: drive the states
while the fragment still owns the page, save what `#view` actually held, then
flip ownership and compare the component against the recording.

    fidelity.py --record /tmp/lib.json lib-list lib-grid …   (before)
    fidelity.py --against /tmp/lib.json lib-list lib-grid …  (after)

The recording is the same normalised text the live comparison uses, so the two
paths differ only in where the legacy side comes from.

WHICH HOST IT READS, AND WHY THAT IS NOT A DETAIL
-------------------------------------------------
`#view` by default, because a PAGE draws there — but a page may have a SECOND
host, and one already does: the settings page portals its save bar into
`#device`. A comparison run against `#view` alone says nothing about that bar,
and saying nothing is not the same as saying « identical »: the bar shipped
with its legacy emitter deleted and no byte-for-byte proof, and it had lost a
whitespace text node and gained a file-name mapping the legacy did not apply.
Both were found by reading, which is the expensive way. Pass the host as the
last argument (`--host '#device'`) and compare each one.

A RECORDING AGES, AND TWO THINGS IN IT AGE FASTER THAN THE REST
---------------------------------------------------------------
`--against` compares today's page with a file written earlier, so anything the
page derives from something OUTSIDE its own code will differ for reasons that
have nothing to do with the conversion being measured. Two are known, and both
have cost a diagnosis:

- **The wall clock.** « Prochaine recherche à 3 h 20 » is
  `nextSearchFR(CADENCE_CRON, new Date())`. A recording taken at 03:00
  and replayed at 15:00 differs on that line in every state that draws it.
- **The embedded data.** `resync.py` rewrites the follow counters and the
  drawer's deployed version from the live system, and the drawer is on screen
  in every state — so one data commit makes a whole recording stale.

Neither is a divergence to debug. Re-record, and take the comparison that
matters BEFORE committing anything that moves data; if a recording must be
compared across such a change, classify every differing token rather than
reading the count — 35 of 82 states differed once, and all of it was those two.

WHAT IT NORMALISES, AND WHY EACH ONE IS NOT A DIFFERENCE
--------------------------------------------------------
Three classes of difference cost a full measuring cycle each before they were
understood. All three are the WRITER, not the markup, and an oracle
that reports them measures the writer:

1. **Inline styles.** React serialises a style OBJECT: `margin-top:0` comes back
   as `margin-top: 0px;`, `flex:1` as `flex: 1 1 0%`. Both sides are re-written
   through the CSSOM, so the comparison is about the declarations.
2. **Attribute order.** It is the order of INSERTION, and the DOM has none —
   React sets `type` after `placeholder`, a template writes it before. Both
   sides are re-sorted.
3. **Whitespace runs.** HTML collapses them at render time, so `\\n        ` and
   ` ` are the same thing on screen. Collapsed on both sides, and whitespace
   BETWEEN TAGS is dropped entirely.

What it does NOT normalise, deliberately: a whitespace text node between TEXT
and a tag. `<span>Label <span class="rf">` and `<span>Label<span class="rf">`
render differently in an inline container, and restoring those nodes is the trap
this conversion has already paid three times («&nbsp;Saison 33/13&nbsp;»).
"""
import asyncio
import difflib
import json
import pathlib
import re
import sys

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

PROTOTYPE = "http://127.0.0.1:8899/wrapped.html"

# One serialiser for both sides. Everything a browser considers equal is made
# textually equal here, and nothing else.
NORMALIZE = """()=>{
  window.__normaliser = (html) => {
    const holder = document.createElement('div');
    holder.innerHTML = html;
    for (const element of holder.querySelectorAll('[style]'))
      element.setAttribute('style', element.style.cssText);
    for (const element of holder.querySelectorAll('*')) {
      const pairs = [...element.attributes]
        .map((attribute) => [attribute.name, attribute.value])
        .sort((left, right) => (left[0] < right[0] ? -1 : 1));
      for (const [name] of pairs) element.removeAttribute(name);
      for (const [name, value] of pairs) element.setAttribute(name, value);
    }
    return holder.innerHTML;
  };}"""

READ = """(selector)=>{
  const host = document.querySelector(selector);
  return {
    drawn: host ? window.__normaliser(host.innerHTML) : null,
    children: host ? host.children.length : -1,
    elements: host ? host.querySelectorAll('*').length : -1,
  };}"""


def tidy(html: str) -> str:
    """Returns the markup with every difference a browser ignores removed."""
    return re.sub(r">\s+<", "><", re.sub(r"\s+", " ", html)).strip()


async def main(legacy_name: str, states: list[str], host: str = "#view",
               record: str | None = None, against: str | None = None) -> int:
    """Compares a migrated page against the legacy side, state by state.

    Args:
        legacy_name: The legacy renderer's own name on `window.__referentiel`.
        states: The state ids to drive.
        host: The element the page draws into — a page may have a SECOND host.
        record: Path to write the legacy side to, for a later comparison.
        against: Path to compare today's page with, instead of a live renderer.

    Returns:
        A process exit code: 0 when every state matched.
    """
    divergences = 0
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context = await browser.new_context(
            viewport={"width": 390, "height": 844}, device_scale_factor=2,
            is_mobile=True, has_touch=True)
        page = await context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(PROTOTYPE, wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        # THE BOOT HINT IS DISMISSED ONCE IT EXISTS, not before. It is raised
        # about 770 ms after load and hides itself about five seconds later —
        # so a click issued here, immediately, lands before there is anything
        # to click, and the toast then rides the walk as a floating overlay
        # that expires partway through it. Whichever state happens to be
        # sampled at the boundary is recorded WITH `.show` and compared
        # WITHOUT it, and the oracle reports a divergence about a timer.
        # Measured: identical clock on both sides of a move (raised 770 ms,
        # hidden 5775 ms), one state apart in the walk — a real difference
        # would not care where in the sequence it was read.
        try:
            await page.wait_for_selector("#toast.show", timeout=4000,
                                         state="attached")
        except PlaywrightTimeoutError:
            # Said plainly rather than as a traceback: the toast may one
            # day stop being raised, and that is not this tool breaking.
            print("  (no boot toast to dismiss — measuring as-is)")
        await page.evaluate("()=>document.querySelector('#toastx')?.click()")
        await page.evaluate(NORMALIZE)

        saved = json.loads(pathlib.Path(against).read_text(encoding="utf-8")) if against else {}
        recorded: dict[str, str] = {}
        for state in states:
            await page.evaluate(f"()=>window.__go({state!r})")
            await page.wait_for_timeout(420)
            measured = await page.evaluate(READ, host)
            drawn = measured["drawn"] or ""
            if record:
                recorded[state] = drawn
                print(f"  RECORD {state:<24} elements={measured['elements']} "
                      f"collapsed {len(tidy(drawn))}")
                continue
            legacy = (saved.get(state, "") if against else await page.evaluate(
                f"()=>window.__normaliser(window.__referentiel[{legacy_name!r}]())"))
            if against and state not in saved:
                print(f"  MISSING {state} — the recording does not carry it")
                divergences += 1
                continue
            same = tidy(drawn) == tidy(legacy)
            divergences += 0 if same else 1
            print(f"  {'SAME  ' if same else 'DIFFER'} {state:<24} "
                  f"elements={measured['elements']:<5} "
                  f"children={measured['children']} "
                  f"collapsed {len(tidy(drawn))} vs {len(tidy(legacy))}")
            if not same:
                diff = difflib.unified_diff(
                    re.split(r"(?<=>)", tidy(legacy)),
                    re.split(r"(?<=>)", tidy(drawn)),
                    "legacy", "shell", lineterm="", n=1)
                for line in list(diff)[:40]:
                    print("      " + line[:200])
        await browser.close()
    if record:
        pathlib.Path(record).write_text(
            json.dumps(recorded, ensure_ascii=False), encoding="utf-8")
        print(f"\nrecorded {len(recorded)} state(s) into {record}")
        return 1 if errors else 0
    print(f"\nJS errors: {errors or 'none'}")
    print(f"divergences: {divergences}/{len(states)}")
    return 1 if divergences or errors else 0


if __name__ == "__main__":
    arguments = sys.argv[1:]
    host = "#view"
    record = against = None
    for flag in ("--host", "--record", "--against"):
        if flag in arguments:
            index = arguments.index(flag)
            value = arguments[index + 1]
            arguments = arguments[:index] + arguments[index + 2:]
            if flag == "--host":
                host = value
            elif flag == "--record":
                record = value
            else:
                against = value
    if record or against:
        arguments = ["-"] + arguments
    if len(arguments) < 2:
        raise SystemExit(
            "usage: fidelity.py <legacyRendererName> <state> [state…] "
            "[--host <selector>]\n"
            "       fidelity.py --record <file> <state> [state…]   (before)\n"
            "       fidelity.py --against <file> <state> [state…]  (after)\n"
            "  the renderer must be reachable as window.__referentiel[<name>]\n"
            "  --host names the container to compare, `#view` by default —\n"
            "  a page with a second host (the save bar's `#device`) needs one\n"
            "  run per host, or half of it ships unproven")
    raise SystemExit(asyncio.run(
        main(arguments[0], arguments[1:], host, record, against)))
