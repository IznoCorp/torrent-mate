"""R53 — the startup screen, and the wait it covers.

Signing in navigates to a document of several megabytes. Two waits follow one
another and both used to be blank:

  1. between the tap on « Se connecter » and the new document's first frame,
     during which the browser still shows the gate;
  2. between that first frame and the interface being rendered.

The first belongs to the gate the server builds, the second to the document
itself. This script proves both are covered by the SAME screen — extracted from
the prototype, never retyped, the rule the login gate already obeys — and that
the screen is gone the moment there is an interface behind it.

Position in source order is a correctness property here, not a detail: a
browser paints what it has parsed, so a screen declared after the embedded
artwork would appear only once the wait it exists to cover is over.
"""
import asyncio
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

from playwright.async_api import async_playwright

RACINE = pathlib.Path(__file__).resolve().parent.parent
PORT = 8713  # never 8710 / 8711: the reverse proxy routes production and staging there
BAR = "─" * 62

echecs = []
faits = 0


class SortieAnticipee(Exception):
    """Ends the gate checks when the screen they measure is not there at all."""


def verifier(nom, condition, detail=""):
    """Records one executed check and its verdict."""
    global faits
    faits += 1
    print(("  OK   " if condition else "  ECHEC") + f" {nom}" + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def extrait_prototype(marque):
    """Returns the prototype text between a pair of `login:<marque>` markers."""
    source = (RACINE / "refonte.html").read_text()
    debut = source.find(f"login:{marque}:start")
    fin = source.find(f"login:{marque}:end")
    if debut < 0 or fin < 0:
        sys.exit(f"marqueurs login:{marque} absents du prototype")
    return source[source.index("\n", debut) + 1 : source.rindex("\n", debut, fin) + 1]


def normaliser(texte):
    """Collapses whitespace so two renderings of the same markup compare equal."""
    return re.sub(r"\s+", " ", texte).strip()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        await pg.evaluate("()=>document.querySelector('#toastx').click()")

        print(f"{BAR}\nR53 — écran de démarrage\n{BAR}")

        # 1. Declared first, so it is painted first. Measured on the SOURCE,
        #    because that is what parse order follows; the DOM would answer the
        #    same question only by accident.
        source = (RACINE / "refonte.html").read_text()
        corps = source[source.find('<div class="device"'):]
        rang_splash = corps.find('id="splash"')
        premier_autre = min(
            x for x in (corps.find("<header"), corps.find('id="port"'), corps.find('id="login"'))
            if x > 0
        )
        verifier("déclaré avant tout le reste du cadre", 0 < rang_splash < premier_autre,
                 f"splash à {rang_splash}, premier autre élément à {premier_autre}")

        # 2. It covers the frame, and it says what is happening.
        await pg.evaluate("()=>window.__go('demarrage')")
        await pg.wait_for_timeout(250)
        mesure = await pg.evaluate("""()=>{
          const s=document.querySelector('#splash'), d=document.querySelector('#device');
          const rs=s.getBoundingClientRect(), rd=d.getBoundingClientRect();
          const cs=getComputedStyle(s);
          const dessous=document.elementFromPoint(rd.x+rd.width/2, rd.y+rd.height/2);
          return {couvre: Math.abs(rs.width-rd.width)<1 && Math.abs(rs.height-rd.height)<1,
                  visible: cs.display!=='none' && cs.opacity!=='0',
                  marque: !!s.querySelector('.brandbig'),
                  progression: !!s.querySelector('[role=progressbar]'),
                  anime: getComputedStyle(s.querySelector('.splashbar i')).animationName,
                  texte: (s.textContent||'').replace(/\\s+/g,' ').trim(),
                  aucunControle: s.querySelectorAll('button,a,input').length,
                  devant: !!(dessous && dessous.closest('#splash'))};}""")
        verifier("couvre tout le cadre", mesure["couvre"] and mesure["visible"], str(mesure["couvre"]))
        verifier("rien de l'interface ne passe devant", mesure["devant"])
        verifier("porte la marque", mesure["marque"])
        verifier("porte une progression animée",
                 mesure["progression"] and mesure["anime"] not in ("none", ""), mesure["anime"])
        verifier("dit ce qui se passe", len(mesure["texte"]) > 20, mesure["texte"][:60])
        verifier("n'offre aucun contrôle", mesure["aucunControle"] == 0,
                 f"{mesure['aucunControle']} contrôle(s)")

        # 3. Gone everywhere else. A cover left behind is the one failure this
        #    screen can cause on its own.
        etats = await pg.evaluate("()=>window.__states()")
        restants = []
        for etat in etats:
            if etat == "demarrage":
                continue
            await pg.evaluate("(i)=>window.__go(i)", etat)
            await pg.wait_for_timeout(60)
            if await pg.evaluate("()=>getComputedStyle(document.querySelector('#splash')).display!=='none'"):
                restants.append(etat)
        verifier(f"absent des {len(etats) - 1} autres états", not restants, ", ".join(restants))

        # 4. It also comes off on its own, without the harness driving it: the
        #    document opens ON the startup screen and the first render drops it.
        page2 = await ctx.new_page()
        await page2.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        verifier("retiré par le premier rendu, sans le harnais",
                 await page2.evaluate(
                     "()=>getComputedStyle(document.querySelector('#splash')).display==='none'"))
        await page2.close()

        # 5. The gate the server builds shows the SAME screen, and reveals it on
        #    submit — the wait the browser spends fetching the document.
        serveur = subprocess.Popen(
            [sys.executable, str(RACINE / "serve.py"), str(PORT)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            portail = ""
            for _ in range(50):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2) as r:
                        portail = r.read().decode()
                    break
                except urllib.error.HTTPError as err:  # 401 carries the gate
                    portail = err.read().decode()
                    break
                except OSError:
                    time.sleep(0.1)
            verifier("le portail répond", bool(portail))
            verifier("le portail porte l'écran de démarrage", 'id="splash"' in portail)
            verifier("il y arrive caché", 'id="splash" hidden' in portail)
            attendu = normaliser(extrait_prototype("splash").replace(
                ' id="splash"', ' id="splash" hidden', 1))
            verifier("extrait du prototype, non recopié", attendu and attendu in normaliser(portail))
            verifier("le portail porte le style de l'écran", ".splashbar" in portail)

            page3 = await ctx.new_page()
            await page3.goto(f"http://127.0.0.1:{PORT}/", wait_until="load")
            # Without the screen there is nothing to measure, and measuring
            # anyway raises instead of naming the defect. A crash is a failure
            # nobody can read.
            if not await page3.evaluate("()=>!!document.querySelector('#splash')"):
                verifier("caché tant qu'on n'a pas soumis", False, "aucun écran dans le portail")
                verifier("apparaît à la soumission", False, "aucun écran dans le portail")
                verifier("et remplace le formulaire", False, "aucun écran dans le portail")
                await page3.close()
                raise SortieAnticipee
            avant = await page3.evaluate(
                "()=>getComputedStyle(document.querySelector('#splash')).display")
            verifier("caché tant qu'on n'a pas soumis", avant == "none", avant)
            # Submitting navigates away, so the state to measure is the one at
            # the instant of the submit, not afterwards. A second listener
            # registered after the gate's own runs after it, and sessionStorage
            # carries what it saw across the navigation.
            await page3.evaluate("""()=>document.querySelector('#loginform')
              .addEventListener('submit', () => sessionStorage.setItem('__demarrage',
                JSON.stringify({
                  splash: getComputedStyle(document.querySelector('#splash')).display,
                  login: getComputedStyle(document.querySelector('#login')).display})))""")
            await page3.fill('input[name="identifiant"]', "quelqu-un")
            await page3.fill('input[name="motdepasse"]', "quelque-chose")
            await page3.click(".loginsubmit")
            await page3.wait_for_timeout(500)
            apres = await page3.evaluate(
                "()=>JSON.parse(sessionStorage.getItem('__demarrage') || 'null')") or {}
            verifier("apparaît à la soumission", apres.get("splash", "none") != "none", str(apres))
            verifier("et remplace le formulaire", apres.get("login") == "none", str(apres))
            await page3.close()
        except SortieAnticipee:
            pass
        finally:
            serveur.terminate()
            serveur.wait(timeout=5)

        await b.close()

    print()
    print(f"{BAR}\n{faits} règles EXÉCUTÉES — "
          + ("aucune violation" if not echecs else f"{len(echecs)} violation(s) : {', '.join(echecs)}"))
    if erreurs:
        print("erreurs JS :", erreurs)
    if echecs or erreurs:
        raise SystemExit(1)

asyncio.run(main())
