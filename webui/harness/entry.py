"""R62 — the sign-in screen is ONE screen, wherever one meets it.

It is met twice. Arriving at the design host, before any session exists, it is
the whole page and the host builds it. Signing out inside the prototype, it is
a layer over the phone frame. Two documents, one screen — and nothing compared
them, so they drifted: the host retyped a palette the prototype had renamed,
and the screen inherited a type scale from whatever it was dropped into,
rendering 16px in one place and 14px in the other.

Comparing renderings, not sources, is the point. A shared source proves
nothing on its own: the host legitimately adjusts what a page needs that a
layer does not, and an adjustment is exactly where a difference hides.

What this script holds to:

  · the two renderings agree on geometry, colour and type for every part of the
    screen — the wordmark, the card, the fields, the button;
  · they say the same words;
  · the host takes its palette from the prototype rather than carrying one.

RE-AIMED, count unchanged: signing out is asked of `window.__entry.signOut()`, the entry
seam the harness publishes; the engine's global `signOut` went with its delegation branch.

RE-AIMED AGAIN, count unchanged, for L18 (round 8 Q10 = B): the prototype's gate offers Plex
FIRST and keeps the password behind « Utiliser un mot de passe », so it is read with that
disclosure OPEN, its Plex block out of the comparison — the host's password page has none, by
design (R-L18-q). Geometry is read against each part's own block (the wordmark against the
brand, a field against the form), because the Plex block legitimately moves both blocks.
"""
import asyncio
import pathlib
import re

from common import (
    PROTOTYPE,
    READ_THROUGH_LOCALHOST,
    Journal,
    browser_channel, chrome_launch_args,
    read_through_localhost,
    resolve_deployed_host_locally,
)
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOST = "https://tm-design.iznogoudatall.xyz/"

# Position is compared as a LOCAL geometry — each part against the screen's own
# box — because the host page and the phone frame are not required to sit at
# the same place in the viewport, only to draw the same screen.
READ = """() => {
  const brand = document.querySelector('[data-part="login"] [data-part="brand/large"]').getBoundingClientRect();
  const form = document.querySelector('[data-part="login"] [data-part="login/form"]').getBoundingClientRect();
  const targets = ['[data-part="brand/large"] [data-part="brand/mark"]', '[data-part="brand/large"] [data-part="brand/wordmark"]', '[data-part="brand/large"] em', '[data-part="login/form"]',
                   '[data-part="login/field"] input', '[data-part="login/submit"]'];
  const out = {};
  for (const s of targets) {
    const e = document.querySelector('[data-part="login"] ' + s);
    if (!e) { out[s] = 'ABSENT'; continue; }
    const r = e.getBoundingClientRect(), c = getComputedStyle(e);
    const own = s === '[data-part="login/form"]' ? r : s.startsWith('[data-part="brand/large"]') ? brand : form;
    out[s] = {
      w: r.width, h: r.height, dx: r.x - own.x, dy: r.y - own.y,
      color: c.color, background: c.backgroundColor,
      font: c.fontFamily.split(',')[0], size: c.fontSize,
      weight: c.fontWeight, radius: c.borderRadius,
    };
  }
  out['__words'] = ['[data-part="brand/large"]', '[data-part="login/form"]']
    .map((part) => document.querySelector('[data-part="login"] ' + part).textContent)
    .join(' ').replace(/\\s+/g, ' ').trim();
  return out;
}"""

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


async def main():
    global _journal
    _journal = Journal("R62 — one sign-in screen")

    # The host must not carry a palette of its own: a retyped value renders
    # correctly here while the reference is broken, which is how the brand
    # colour stayed lost for as long as it did.
    host_src = (ROOT / "serve.py").read_text()
    # Everything the host contributes on its own — as opposed to what it
    # extracts — is checked, not one named block: moving the copy into a
    # differently-named string would otherwise walk straight past the rule.
    own = "\n".join(m.group(1) for m in
                    re.finditer(r'= \"\"\"(.*?)\"\"\"', host_src, re.S))
    forbidden = re.findall(r"(--[\w-]+)\s*:", own)
    forbidden += re.findall(r"\b(font-family|line-height|font-size|"
                            r"-webkit-font-smoothing|font-variant-numeric)\s*:", own)
    check("the host redeclares nothing the reference owns",
          not forbidden, str(sorted(set(forbidden))))

    async with async_playwright() as p:
        b = await p.chromium.launch(channel=browser_channel(), args=chrome_launch_args(resolve_deployed_host_locally(HOST)))
        # FRENCH, PINNED: the host side is the LIVE tm-design, which serves `develop` and words its
        # page in French until the account's language is merged there; the runner's own locale
        # would otherwise decide the verdict.
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True, locale="fr-FR")
        errors = []

        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(f"host: {e}"))
        response = await pg.goto(HOST, wait_until="load")
        ok, ip_address = read_through_localhost(await response.server_addr())
        check(READ_THROUGH_LOCALHOST, ok, str(ip_address))
        await pg.wait_for_timeout(500)
        arrival = await pg.evaluate(READ)

        pg2 = await ctx.new_page()
        pg2.on("pageerror", lambda e: errors.append(f"prototype: {e}"))
        await pg2.goto(PROTOTYPE, wait_until="load")
        await pg2.evaluate("()=>document.querySelector('#toastx').click()")
        await pg2.wait_for_timeout(250)
        # THE SIGN-OUT IS STARTED, NOT AWAITED THROUGH THE BRIDGE (as `account_language.py`): what
        # is read is the gate once it is up, not a promise the page may let go of.
        await pg2.evaluate("()=>{ void window.__entry.signOut(); }")
        await pg2.wait_for_function("()=>document.querySelector('#login')?.hidden === false")
        await pg2.wait_for_timeout(700)
        await pg2.evaluate("()=>document.querySelector('[data-part=\"login/password-disclosure\"]')?.click()")
        await pg2.wait_for_timeout(250)
        signout = await pg2.evaluate(READ)
        await b.close()

    check("both renderings carry the same parts",
          sorted(arrival) == sorted(signout)
          and not [k for k in arrival if arrival[k] == "ABSENT"],
          str([k for k in arrival if arrival[k] == "ABSENT"]))

    check("and they say the same words",
          arrival["__words"] == signout["__words"],
          f"{arrival['__words'][:44]!r} vs {signout['__words'][:44]!r}")

    # Colour, type and radius are compared EXACTLY: a difference there is always a
    # decision that drifted. Geometry allows one pixel, and only one: both boxes
    # measure 390x844 to the pixel, so what is left is a flex centring landing on
    # a half pixel and rounding two ways. Real drift is never one pixel.
    GEOMETRY = {"w", "h", "dx", "dy"}
    for key in [k for k in arrival if not k.startswith("__")]:
        a, s = arrival[key], signout.get(key)
        if not (isinstance(a, dict) and isinstance(s, dict)):
            gaps = {"whole": (a, s)}
        else:
            gaps = {k: (a[k], s[k]) for k in a
                    if (abs(a[k] - s[k]) > 1 if k in GEOMETRY else a[k] != s[k])}
        check(f"« {key} » renders the same on both sides", not gaps,
              "; ".join(f"{k}: host={va} prototype={vs}"
                        for k, (va, vs) in list(gaps.items())[:3]))

    check("no JS error", not errors, str(errors))

    _journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
