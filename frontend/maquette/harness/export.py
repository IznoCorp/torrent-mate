"""CSS extraction must leave NOTHING behind without saying so.

`regions.json` carries an allowlist: `extract-maquette-css.py` exports only
what it lists. A class defined in BLOCK 2 but absent from both lists would be
silently missing from the app — the most expensive defect possible, because it
only becomes visible once the screen is already wrong.

This script classifies EVERY BLOCK 2 class by what it actually does:

  app      — at least one element carries it, outside the prototype chrome
  harness  — seen only in the harness (state panel, notes, phone frame)
  written  — never present in a frozen state, but written by the code
             (transient classes: armed gesture, loading, selection)
  DEAD     — defined in CSS, never carried, never written by the code

« DEAD » is a failure: dead CSS in the prototype becomes dead CSS in the app
and, worse, suggests a class exists when it does not.
"""
import asyncio, json, pathlib, re, sys
from playwright.async_api import async_playwright

RACINE = pathlib.Path(__file__).resolve().parent.parent
BAR = "─" * 62

# The harness is physically identifiable in the DOM.
CHROME_PROTO = ".hpanel,.hbtn,.note,.states"
HARNAIS_CONNUS = {"hpanel", "states", "notes", "stage", "device", "note", "hbtn"}


def classes_bloc2() -> set[str]:
    """Classes defined by a CSS rule inside BLOCK 2 — comments excluded."""
    h = (RACINE / "refonte.html").read_text()
    i = h.find("BLOCK 2")
    if i < 0:
        sys.exit("BLOCK 2 not found: the prototype lost its harness/app separation.")
    # Go back to the OPENER of the header comment: slicing on « BLOCK 2 »
    # leaves an orphan `*/`, and the header's own prose then parses as
    # selectors, producing false dead classes.
    i = h.rfind("/*", 0, i)
    css = re.sub(r"/\*.*?\*/", "", h[i : h.find("</style>", i)], flags=re.S)
    css = re.sub(r"\"[^\"]*\"|'[^']*'", '""', css)
    out = set()
    for m in re.finditer(r"([^{}]+)\{", css):
        if "@" in m.group(1) and "media" in m.group(1):
            continue
        out.update(re.findall(r"\.([a-zA-Z][\w-]*)", m.group(1)))
    return out


async def main():
    cl = sorted(classes_bloc2())
    src = (RACINE / "refonte.html").read_text()
    src = src[src.find("</style>"):]  # markup + JS, sans le CSS

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        # The startup screen covers the frame for as long as the load it stands
        # for lasts. Nothing is being fetched here, so the harness closes that
        # wait through the same seam the app uses, rather than sleeping it out.
        await pg.evaluate("()=>window.__chargementTermine?.()")
        await pg.evaluate("()=>window.__measure(true)")
        etats = await pg.evaluate("()=>window.__states()")
        app, har = set(), set()
        for e in etats:
            await pg.evaluate("(i)=>window.__go(i)", e)
            await pg.wait_for_timeout(170)
            r = await pg.evaluate("""([CL, CHROME])=>{const a=[],h=[];
              for (const c of CL) for (const el of document.getElementsByClassName(c)) {
                if (el.closest(CHROME) || el.classList.contains('stage') || el.classList.contains('device')) h.push(c);
                else a.push(c);
              }
              return {a:[...new Set(a)], h:[...new Set(h)]};}""", [cl, CHROME_PROTO])
            app |= set(r["a"]); har |= set(r["h"])
        await b.close()

    har -= app
    reste = set(cl) - app - har
    # The harness is written by the code too: without this subtraction it
    # would land in « written », hence in the export allowlist.
    posees = {c for c in reste - HARNAIS_CONNUS
              if re.search(r"[\"'` ]" + re.escape(c) + r"[\"'` ]", src)}
    mortes = sorted(reste - posees - HARNAIS_CONNUS)
    har |= (reste & HARNAIS_CONNUS)

    print(f"{BAR}\nClassement des {len(cl)} classes de BLOC 2\n{BAR}")
    print(f"  app       {len(app):4d}")
    print(f"  written   {len(posees):4d}  (transient: {', '.join(sorted(posees)) or '—'})")
    print(f"  harnais   {len(har):4d}")
    print(f"  MORTES    {len(mortes):4d}  {', '.join(mortes) or '—'}")

    # The allowlist must cover everything bound for the app: rendered AND
    # transient.
    regions = json.loads((RACINE / "regions.json").read_text())
    attendu = {"." + c for c in (app | posees)}
    manquantes = sorted(attendu - set(regions["exportedSelectors"]))

    echecs = []
    if mortes:
        echecs.append(f"{len(mortes)} dead CSS rule(s): {', '.join(mortes)}")
    if manquantes:
        echecs.append(f"{len(manquantes)} class(es) outside the allowlist: {', '.join(manquantes)}")

    print()
    if echecs:
        for x in echecs:
            print("■", x)
        print(f"{BAR}\nFAILURE - extraction would leave CSS behind.")
        sys.exit(1)
    print(f"{BAR}\nOK - every BLOCK 2 class is classified, and the allowlist covers them all.")

asyncio.run(main())
