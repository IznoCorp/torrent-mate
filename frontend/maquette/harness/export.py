"""L'extraction CSS ne doit RIEN laisser derrière elle sans le dire.

`regions.json` porte une allowlist : `extract-maquette-css.py` n'exporte que ce
qui y figure. Une classe définie dans BLOC 2 mais absente des deux listes serait
silencieusement absente de l'app — le défaut le plus coûteux possible, parce
qu'il ne se voit qu'au moment où l'écran est déjà faux.

Ce script classe CHAQUE classe de BLOC 2 par ce qu'elle fait vraiment :

  app      — au moins un élément la porte, hors chrome du prototype
  harnais  — vue uniquement dans le harnais (panneau d'états, notes, cadre)
  posée    — jamais présente dans un état figé, mais écrite par le code
             (classes transitoires : geste armé, chargement, sélection)
  MORTE    — définie en CSS, jamais portée, jamais écrite par le code

« MORTE » est un échec : du CSS mort dans la maquette devient du CSS mort dans
l'app, et pire, laisse croire qu'une classe existe.
"""
import asyncio, json, pathlib, re, sys
from playwright.async_api import async_playwright

RACINE = pathlib.Path(__file__).resolve().parent.parent
BAR = "─" * 62

# Le harnais est physiquement identifiable dans le DOM.
CHROME_PROTO = ".hpanel,.hbtn,.note,.states"
HARNAIS_CONNUS = {"hpanel", "states", "notes", "stage", "device", "note", "hbtn"}


def classes_bloc2() -> set[str]:
    """Les classes définies par une règle CSS dans BLOC 2 — commentaires exclus."""
    h = (RACINE / "refonte.html").read_text()
    i = h.find("BLOC 2")
    if i < 0:
        sys.exit("BLOC 2 introuvable : la maquette a perdu sa séparation harnais/app.")
    # Remonter à l'OUVREUR du commentaire d'en-tête : découper sur « BLOC 2 »
    # laisse un `*/` orphelin, et le texte de l'en-tête (« app-surface.css »,
    # « .tm ») se lit alors comme des sélecteurs. Deux fausses classes mortes
    # sont nées exactement de là.
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
    # Le harnais est écrit par le code lui aussi : sans cette soustraction il
    # atterrirait dans « posées », donc dans l'allowlist d'export.
    posees = {c for c in reste - HARNAIS_CONNUS
              if re.search(r"[\"'` ]" + re.escape(c) + r"[\"'` ]", src)}
    mortes = sorted(reste - posees - HARNAIS_CONNUS)
    har |= (reste & HARNAIS_CONNUS)

    print(f"{BAR}\nClassement des {len(cl)} classes de BLOC 2\n{BAR}")
    print(f"  app       {len(app):4d}")
    print(f"  posées    {len(posees):4d}  (transitoires : {', '.join(sorted(posees)) or '—'})")
    print(f"  harnais   {len(har):4d}")
    print(f"  MORTES    {len(mortes):4d}  {', '.join(mortes) or '—'}")

    # L'allowlist doit couvrir tout ce qui part vers l'app : le rendu ET le transitoire.
    regions = json.loads((RACINE / "regions.json").read_text())
    attendu = {"." + c for c in (app | posees)}
    manquantes = sorted(attendu - set(regions["exportedSelectors"]))

    echecs = []
    if mortes:
        echecs.append(f"{len(mortes)} règle(s) CSS morte(s) : {', '.join(mortes)}")
    if manquantes:
        echecs.append(f"{len(manquantes)} classe(s) hors allowlist : {', '.join(manquantes)}")

    print()
    if echecs:
        for x in echecs:
            print("■", x)
        print(f"{BAR}\nÉCHEC — l'extraction laisserait du CSS derrière elle.")
        sys.exit(1)
    print(f"{BAR}\nOK — chaque classe de BLOC 2 est classée, et l'allowlist les couvre toutes.")

asyncio.run(main())
