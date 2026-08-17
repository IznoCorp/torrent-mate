#!/usr/bin/env python3
"""Does a migrated PAGE draw what the legacy drew, byte for byte?

A tool, not a rule — it is run BY HAND while a page is being converted, and it
stops being runnable the moment the legacy renderer it compares against is
deleted. That order is the point: prove first, delete after.

    python3 frontend/maquette/fidelity.py viewSystemLegacy systeme systeme-panne

It needs the legacy renderer reachable from `window.__referentiel` under a name
of its own (`viewSystemLegacy: viewSystem`), added for the proof and removed
with the renderer.

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
import re
import sys

from playwright.async_api import async_playwright

PROTOTYPE = "http://127.0.0.1:8899/wrapped.html"

# One serialiser for both sides. Everything a browser considers equal is made
# textually equal here, and nothing else.
NORMALISER = """()=>{
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


async def main(legacy_name: str, states: list[str], host: str = "#view") -> int:
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
        await page.evaluate("()=>window.__chargementTermine?.()")
        await page.evaluate("()=>document.querySelector('#toastx')?.click()")
        await page.evaluate(NORMALISER)

        for state in states:
            await page.evaluate(f"()=>window.__go({state!r})")
            await page.wait_for_timeout(420)
            measured = await page.evaluate(READ, host)
            legacy = await page.evaluate(
                f"()=>window.__normaliser(window.__referentiel[{legacy_name!r}]())")
            drawn = measured["drawn"] or ""
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
    print(f"\nJS errors: {errors or 'none'}")
    print(f"divergences: {divergences}/{len(states)}")
    return 1 if divergences or errors else 0


if __name__ == "__main__":
    arguments = sys.argv[1:]
    host = "#view"
    if "--host" in arguments:
        index = arguments.index("--host")
        host = arguments[index + 1]
        arguments = arguments[:index] + arguments[index + 2:]
    if len(arguments) < 2:
        raise SystemExit(
            "usage: fidelity.py <legacyRendererName> <state> [state…] "
            "[--host <selector>]\n"
            "  the renderer must be reachable as window.__referentiel[<name>]\n"
            "  --host names the container to compare, `#view` by default —\n"
            "  a page with a second host (the save bar's `#device`) needs one\n"
            "  run per host, or half of it ships unproven")
    raise SystemExit(asyncio.run(main(arguments[0], arguments[1:], host)))
