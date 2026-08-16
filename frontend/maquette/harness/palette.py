"""R61 — every colour a rule names is a colour the document defines.

A `var(--name)` whose property is never defined, and which carries no fallback,
is invalid at computed-value time. It does not raise, it does not warn, and it
does not render as an obvious mistake: a `color` falls back to the inherited
one and a `background` disappears entirely. The screen keeps rendering, so it
keeps passing — it simply stops being the design.

That is how the palette was renamed to `--primary` while eleven declarations
kept the old `--accent` name. The wordmark lost its second colour, the sign-in
button lost its background, the install button lost its background, and the
startup bar's fill turned invisible. The host page hid it: it retyped
`--accent: #f5a524` into a block of its own, so the ONE place the screen was
ever looked at rendered correctly.

This script holds two things, because either one alone is escapable:

  · statically, no `var(--x)` without a fallback names a property the document
    never defines — this covers the surfaces no state ever visits;
  · on screen, the brand colour is ACTUALLY painted where the design puts it —
    a declaration can be present and still be overridden into nothing.
"""
import asyncio
import pathlib
import re

from common import Journal, open_page
from playwright.async_api import async_playwright

PROTOTYPE = pathlib.Path(__file__).resolve().parent.parent / "design" / "refonte.html"

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


def dangling(source):
    """Returns every custom property referenced without a fallback and never defined.

    Args:
        source: The prototype's full source.

    Returns:
        A dict property name → number of references lacking a fallback.
    """
    defined = set(re.findall(r"(--[\w-]+)\s*:", source))
    missing = {}
    for m in re.finditer(r"var\(\s*(--[\w-]+)\s*(,)?", source):
        name, fallback = m.group(1), m.group(2)
        # A reference carrying a fallback degrades on purpose; only a bare one
        # is a promise the document does not keep.
        if not fallback and name not in defined:
            missing[name] = missing.get(name, 0) + 1
    return missing


# Where the brand colour must actually land. Each entry names a state, a
# selector, and which painted property has to carry it.
PAINTS = [
    ("connexion", ".brandbig .mk", "color", "the brand's funnel"),
    ("connexion", ".brandbig em", "color", "the brand's second word"),
    ("connexion", ".loginsubmit", "backgroundColor", "the sign-in button"),
    ("demarrage", ".splashbar i", "backgroundColor", "the startup bar's fill"),
]


async def main():
    global _journal
    _journal = Journal("R61 — the palette keeps its promises")

    source = PROTOTYPE.read_text()
    missing = dangling(source)
    check("no colour referenced without being defined",
             not missing,
             ", ".join(f"{k} ×{v}" for k, v in sorted(missing.items())))

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(b)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.evaluate("()=>window.__measure(true)")

        brand = await pg.evaluate(
            "()=>getComputedStyle(document.documentElement).getPropertyValue('--primary').trim()")
        check("the brand colour is defined", bool(brand), brand)

        # The comparison is against the RESOLVED brand colour rather than a
        # literal, so changing the palette moves both sides together.
        reference = await pg.evaluate(
            """(c)=>{const d=document.createElement('div'); d.style.color=c;
                     document.body.appendChild(d);
                     const v=getComputedStyle(d).color; d.remove(); return v;}""",
            brand)

        for state_, selector, property_, what in PAINTS:
            await pg.evaluate("(i)=>window.__go(i)", state_)
            await pg.wait_for_timeout(400)
            painted = await pg.evaluate(
                """([s, p])=>{const e=document.querySelector(s);
                              return e ? getComputedStyle(e)[p] : null;}""",
                [selector, property_])
            check(f"{what} carries the brand colour",
                     painted == reference, f"{painted} instead of {reference}")

        # And nothing anywhere paints a background that resolved to nothing —
        # the visible symptom of a dangling property, on every named state.
        transparents = []
        for state_ in await pg.evaluate("()=>window.__states()"):
            await pg.evaluate("(i)=>window.__go(i)", state_)
            await pg.wait_for_timeout(120)
            seen = await pg.evaluate("""()=>{
              const lost = [];
              for (const e of document.querySelectorAll('.loginsubmit, .installgo, .splashbar i')) {
                const c = getComputedStyle(e);
                if (c.backgroundColor === 'rgba(0, 0, 0, 0)' && e.offsetParent !== null)
                  lost.push(e.className);
              }
              return lost;}""")
            transparents += [f"{state_}:{v}" for v in seen]
        check("no brand button renders a transparent background",
                 not transparents, str(transparents[:3]))

        check("no JS error", not errors, str(errors))
        await b.close()

    _journal.summary()

asyncio.run(main())
