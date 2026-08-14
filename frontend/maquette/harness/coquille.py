"""R72 — the Vite shell changes nothing the prototype renders.

`design/` carries a Vite project whose one job is to emit the prototype
verbatim inside a real envelope. A shell that transformed anything — a
minified inline script, a re-written attribute, an asset URL that stopped
resolving — would make every later conversion step start from a lie. So the
rule builds the shell, serves the output, drives the SOURCE and the BUILD to
the same named states in the same browser, and requires the rendered DOM and
the geometry of the exported regions to be identical. Rendered truth, never
screenshots: two captures of one file diverge, measured twice on this
project. R72_SANS_BUILD=1 skips the build gate so a mutation applied to dist/
survives the run — mutation runs only, never a way to pass the build check.
"""
import asyncio
import json
import os
import pathlib
import subprocess
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from commun import RACINE, TELEPHONE, Journal

DESIGN = RACINE / "design"
PORT = 8917
SOURCE = "http://127.0.0.1:8899/wrapped.html"
BATI = f"http://127.0.0.1:{PORT}/index.html"
ETATS = ["acq-ajout-resultats", "lib-grille", "fiche-film", "systeme"]

# The serialization compares what layout READS: tag, id, classes and the
# hidden attribute, in document order, for the three surfaces a state draws.
SERIALISER = """(sel) => {
  const racine = document.querySelector(sel);
  if (!racine) return null;
  const sortie = [];
  const marche = (n) => {
    if (n.nodeType !== 1) return;
    sortie.push(n.tagName + (n.id ? "#" + n.id : "")
      + (n.className && typeof n.className === "string"
         ? "." + n.className.trim().split(/\\s+/).sort().join(".") : "")
      + (n.hidden ? "[hidden]" : ""));
    for (const e of n.children) marche(e);
  };
  marche(racine);
  return sortie.join("\\n");
}"""

RECTS = """(sels) => {
  const sortie = {};
  for (const sel of sels) {
    const e = document.querySelector(sel);
    if (!e) continue;
    const r = e.getBoundingClientRect();
    sortie[sel] = [r.x, r.y, r.width, r.height].map((v) => Math.round(v));
  }
  return sortie;
}"""

# The HOST's half of the PWA contract: serve.py synthesizes these routes
# (and the browser asks for favicon.ico uninvited). A static server serving
# the same document legitimately lacks them, and R52 (pwa.py) already holds
# them against the live host — excluding them here keeps this guard sharp
# for every URL the prototype itself references, the assets above all.
ROUTES_HOTE = ("/favicon.ico", "/favicon.svg", "/sw.js", "/manifest.webmanifest")


def construire(journal):
    """Runs the build, installing first only when node_modules is absent."""
    if os.environ.get("R72_SANS_BUILD") == "1":
        journal.verifier("le build de la coquille aboutit", True,
                         "sauté (R72_SANS_BUILD=1 — mutation en cours)")
        return True
    if not (DESIGN / "node_modules").exists():
        print("  npm ci (première fois — long)")
        subprocess.run(["npm", "ci"], cwd=DESIGN, check=True,
                       capture_output=True, text=True)
    fait = subprocess.run(["npm", "run", "build"], cwd=DESIGN,
                          capture_output=True, text=True)
    journal.verifier("le build de la coquille aboutit", fait.returncode == 0,
                     (fait.stderr or fait.stdout).strip().splitlines()[-1]
                     if fait.returncode else "vite build")
    if fait.returncode != 0:
        return False
    # Verify the fragment is emitted byte-for-byte (not minified, not extracted).
    enveloppe = (DESIGN / "index.html").read_text(encoding="utf-8")
    fragment = (DESIGN / "refonte.html").read_text(encoding="utf-8")
    emis = (DESIGN / "dist" / "index.html").read_text(encoding="utf-8")
    journal.verifier(
        "le fragment est émis verbatim, à l'octet",
        emis == enveloppe.replace("<!-- maquette -->", fragment),
        f"{len(emis)} chars émis")
    return True


async def ouvrir_page(navigateur, url, erreurs):
    ctx = await navigateur.new_context(**TELEPHONE)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: erreurs.append(f"{url}: {e}")
          if not any(route in str(e) for route in ROUTES_HOTE) else None)
    # The error guard listens to RESPONSES, not console prose: a console line
    # does not carry the URL, and the browser requests /favicon.ico uninvited
    # on both servers — neither declares one, so that miss is the harness's
    # environment, never the prototype's. Every URL the prototype itself
    # requests (the assets above all) stays guarded.
    pg.on("response", lambda r: erreurs.append(f"{url}: {r.status} {r.url}")
          if r.status >= 400 and not r.url.endswith(ROUTES_HOTE) else None)
    await pg.goto(url, wait_until="load")
    await pg.evaluate("()=>window.__chargementTermine?.()")
    await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
    await pg.wait_for_timeout(250)
    return pg


async def comparer(journal, src, bat, selecteurs, etat):
    """Compare source and built pages on the same driven state.

    Checks DOM serialization of three surfaces and region geometry,
    named by the state label (e.g. 'acq-ajout-resultats' or 'arrivée').
    """
    for pg in (src, bat):
        if etat != "arrivée":
            await pg.evaluate("(e)=>window.__go(e)", etat)
            await pg.wait_for_timeout(450)
    for surface in ("#view", "#screen", "#sheet"):
        a = await src.evaluate(SERIALISER, surface)
        b = await bat.evaluate(SERIALISER, surface)
        detail = ""
        if a != b and a and b:
            la, lb = a.split("\n"), b.split("\n")
            i = next((k for k in range(min(len(la), len(lb)))
                      if la[k] != lb[k]), min(len(la), len(lb)))
            detail = f"premier écart au nœud {i}: {la[i:i+1]} ≠ {lb[i:i+1]}"
        journal.verifier(f"{etat} · {surface} identique", a == b,
                         detail or f"{(a or '').count(chr(10))+1} nœuds")
    ra = await src.evaluate(RECTS, selecteurs)
    rb = await bat.evaluate(RECTS, selecteurs)
    ecarts = [s for s in ra
              if s in rb and any(abs(x - y) > 1
                                 for x, y in zip(ra[s], rb[s]))]
    journal.verifier(f"{etat} · géométrie des régions identique",
                     set(ra) == set(rb) and not ecarts,
                     f"{len(ra)} régions"
                     + (f" · écarts: {ecarts[:2]}" if ecarts else ""))


async def main():
    journal = Journal("R72 — la coquille ne change rien au rendu")
    if not construire(journal):
        journal.bilan()

    serveur = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=DESIGN / "dist",
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    erreurs = []
    try:
        async with async_playwright() as p:
            navigateur = await p.chromium.launch(channel="chrome")
            src = await ouvrir_page(navigateur, SOURCE, erreurs)
            bat = await ouvrir_page(navigateur, BATI, erreurs)

            connus = await src.evaluate("()=>window.__states()")
            journal.verifier("les états conduits existent",
                             all(e in connus for e in ETATS), " · ".join(ETATS))

            regions = json.loads((RACINE / "regions.json").read_text())
            selecteurs = regions["harnessSelectors"]

            # Compare the arrival state (before any driving)
            await comparer(journal, src, bat, selecteurs, "arrivée")

            # Compare the driven states
            for etat in ETATS:
                await comparer(journal, src, bat, selecteurs, etat)

            await navigateur.close()
    finally:
        serveur.terminate()
        serveur.wait(timeout=5)
    journal.bilan(erreurs)


asyncio.run(main())
