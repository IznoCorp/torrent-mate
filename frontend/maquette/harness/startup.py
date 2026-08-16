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
browser paints what it has parsed, so a screen declared after the artwork would
appear only once the wait it exists to cover is over.

What the cold-load checks below prove is the state of the DOCUMENT — the screen
is there, visible, from the instant it enters it, and gone once the interface
exists. Not the state of a painted frame: served locally, this document is about
a megabyte and a half and arrives in one burst, so the screen is parsed and then
taken off before the browser gets a single rendering opportunity. Its visible
window closes near 110 ms and the first paint lands near 290 ms — no frame here
carries it, and no probe can invent one. A guarantee about what reaches the
SCREEN needs a load slow enough to paint during, that is a throttled-network
profile in the driver: a separate rule, and an open decision for the operator.
"""
import asyncio
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

from common import Journal
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 8713  # never 8710 / 8711: the reverse proxy routes production and staging there

_journal = None


class SortieAnticipee(Exception):
    """Ends the gate checks when the screen they measure is not there at all."""


def verifier(nom, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(nom, condition, detail)


def extrait_prototype(marque):
    """Returns the prototype text between a pair of `login:<marque>` markers."""
    source = (ROOT / "design" / "refonte.html").read_text()
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

        global _journal
        _journal = Journal("R53 — écran de démarrage")

        # 1. Declared first, so it is painted first. Measured on the SOURCE,
        #    because that is what parse order follows; the DOM would answer the
        #    same question only by accident.
        source = (ROOT / "design" / "refonte.html").read_text()
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

        # The bar FILLS over the five seconds a cold load is budgeted, rather
        # than shuttling back and forth: a shuttle answers « how much longer »
        # with nothing, and reads the same at one second and at ten.
        remplissage = await pg.evaluate("""()=>{
          const i = document.querySelector('#splash .splashbar i');
          const cs = getComputedStyle(i);
          return {duree: cs.animationDuration, sens: cs.animationDirection,
                  fin: cs.animationFillMode, iterations: cs.animationIterationCount};}""")
        verifier("la barre se remplit sur 5 s, une seule fois",
                 remplissage["duree"] == "5s" and remplissage["iterations"] == "1",
                 str(remplissage))

        # Measured while it runs: from nothing to full, monotonically. The
        # harness freezes animations for its own measurements, so this one asks
        # for them back.
        largeurs = await pg.evaluate("""async()=>{
          document.documentElement.classList.remove('measuring');
          const i = document.querySelector('#splash .splashbar i');
          i.style.animation = 'none'; void i.offsetWidth; i.style.animation = '';
          const piste = i.parentElement.getBoundingClientRect().width;
          const prises = [];
          for (let n = 0; n < 6; n++) {
            prises.push(Math.round(i.getBoundingClientRect().width / piste * 100));
            await new Promise(r => setTimeout(r, 500));
          }
          return prises;}""")
        verifier("elle part de zéro", largeurs[0] <= 5, str(largeurs))
        verifier("et ne fait que croître",
                 all(b >= a for a, b in zip(largeurs, largeurs[1:])), str(largeurs))
        verifier("à mi-parcours elle est à mi-course",
                 40 <= largeurs[5] <= 60, f"{largeurs[5]} % à 2,5 s")
        await pg.evaluate("()=>document.documentElement.classList.add('measuring')")
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

        # 4. Once the document has loaded there is nothing left to cover, so the
        #    screen is gone. This check has been wrong in BOTH directions: it
        #    first asserted the current behaviour — a screen that flashed for one
        #    frame — and called that conformity; then it demanded a floor, which
        #    made the bar play a second time in a document that was already
        #    rendered. What it asserts now is what the screen is FOR.
        page2 = await ctx.new_page()
        await page2.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        await page2.wait_for_timeout(400)
        verifier("parti une fois le document chargé — il ne couvre plus rien",
                 await page2.evaluate(
                     "()=>getComputedStyle(document.querySelector('#splash')).display==='none'"))
        await page2.close()

        # 5. The gate the server builds shows the SAME screen, and reveals it on
        #    submit — the wait the browser spends fetching the document.
        serveur = subprocess.Popen(
            [sys.executable, str(ROOT / "serve.py"), str(PORT)],
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

        # ── THE COLD LOAD, the only one an operator ever sees ──────────────
        # The screen covers ONE wait: the gap between asking for the application
        # and having an interface. It spans two pages: the gate paints the
        # screen on submit, the new document paints it again from its own
        # markup, and the operator sees one continuous screen across a
        # navigation.
        #
        # Held on a TIMER here, the bar filled once while the document
        # downloaded and then restarted from zero in a document that was already
        # rendered. It was reported as loading twice, and it was. What is
        # asserted below is that the screen is up from the moment it enters the
        # document and comes off when the interface is there — not after a fixed
        # delay, which is what a rule of mine demanded and what put the second
        # bar on screen.
        #
        # The observation is taken from INSIDE the page, by a script injected
        # before any script of the document runs, and the clock is the
        # document's own — it starts when the navigation does. Asking from the
        # outside cannot answer this question any more: the document weighs
        # about a megabyte and a half, its artwork living in files beside it,
        # and it parses fast enough that the whole life of the screen — parsed,
        # then taken off by the line that ends the document — can be shorter
        # than any period a driver samples at, and shorter than the gap between
        # two rendering opportunities as well. A window that falls between two
        # readings looks exactly like a screen that never appeared, and that is
        # a verdict on the reading, not on the interface.
        #
        # So the record is made of the moments themselves, not of a period: the
        # instant the screen enters the document, every change of its state
        # afterwards, and one reading per animation frame on top of that. The
        # first two are what a fast document needs; the frames are what proves
        # the screen does not come back later.
        #
        # What this rule asserts is therefore the state of the DOCUMENT, and it
        # is named for that. Served locally, a megabyte and a half arrives in one
        # burst: the screen is parsed, then taken off by the closing line, before
        # the browser has had a single rendering opportunity — measured, entered
        # visible around 60 ms, off around 110 ms, first paint near 290 ms. No
        # painted frame carries it here, and no reading can invent one. Proving
        # the screen reaches the SCREEN needs a load slow enough to paint during
        # — a throttled network profile in the driver — which is a rule of its
        # own and an open decision for the operator, not something this one can
        # claim.
        froide = await ctx.new_page()
        await froide.add_init_script("""(() => {
          window.__releves = [];
          const noter = () => {
            const s = document.querySelector('#splash');
            window.__releves.push([performance.now(), s ? !s.hidden : null]);
          };
          let suivi = null;
          new MutationObserver(() => {
            const s = document.querySelector('#splash');
            if (s && s !== suivi) {
              suivi = s;
              noter();
              new MutationObserver(noter).observe(
                s, {attributes: true, attributeFilter: ['hidden']});
            }
          }).observe(document, {childList: true, subtree: true});
          const image = () => { noter(); requestAnimationFrame(image); };
          requestAnimationFrame(image);
        })()""")
        await froide.goto("http://127.0.0.1:8899/wrapped.html", wait_until="commit")
        await froide.wait_for_timeout(3000)
        releves = await froide.evaluate("()=>window.__releves")

        # The first reading on which the screen EXISTS is the first moment it
        # could have been seen: before it, the browser has not parsed it yet and
        # a reading of « absent » says nothing about it.
        premiere = next(((t, v) for t, v in releves if v is not None), None)
        verifier("l'écran de démarrage est là dès qu'il entre dans le document",
                 premiere is not None and premiere[1] and premiere[0] < 400,
                 f"présent à {round(premiere[0])}ms, visible : {premiere[1]}"
                 if premiere else f"absent des {len(releves)} lectures")
        vus = [t for t, v in releves if v]
        partis = [t for t, v in releves if v is False and vus and t > vus[0]]
        verifier("et il part dès que l'interface est là",
                 bool(partis) and partis[0] < 1500,
                 f"parti à {round(partis[0])}ms" if partis else "parti à jamais")
        revenus = [t for t, v in releves if v and partis and t > partis[0]]
        verifier("il ne revient pas une seconde fois", not revenus,
                 str([round(t) for t in revenus[:3]]))
        await froide.close()

        # ── where the wait is PLAYED, it lasts what the bar announces ───────
        # Signing in inside the prototype fetches nothing, so the wait that
        # follows has to be played out to be judged at all. Same screen, same
        # seam, a duration instead of an observation.
        joue = await ctx.new_page()
        await joue.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        await joue.evaluate("()=>window.__chargementTermine?.()")
        await joue.evaluate("()=>window.__go('connexion')")
        await joue.wait_for_timeout(350)
        await joue.evaluate("""()=>{
          document.querySelector('[name=identifiant]').value = 'izno';
          document.querySelector('[name=motdepasse]').value = 'x';
          document.querySelector('#loginform').requestSubmit();}""")
        t1 = time.monotonic()
        suite = []
        while time.monotonic() - t1 < 7:
            suite.append((round((time.monotonic() - t1) * 1000),
                          await joue.evaluate(
                              "()=>{const s=document.querySelector('#splash');"
                              "return s ? !s.hidden : null;}")))
            await joue.wait_for_timeout(120)
        montes = [t for t, v in suite if v]
        tombes = [t for t, v in suite if v is False and montes and t > montes[0]]
        verifier("une connexion dans le prototype couvre l'attente",
                 bool(montes) and montes[0] < 500, f"à {montes[0] if montes else '—'}ms")
        verifier("et elle dure ce que la barre annonce",
                 bool(tombes) and 4500 < tombes[0] < 6500,
                 f"parti à {tombes[0] if tombes else 'jamais'}ms")

        # The seam ends it early, which is the same promise resolving sooner.
        await joue.evaluate("()=>window.__go('connexion')")
        await joue.wait_for_timeout(300)
        await joue.evaluate("""()=>{
          document.querySelector('[name=identifiant]').value = 'izno';
          document.querySelector('[name=motdepasse]').value = 'x';
          document.querySelector('#loginform').requestSubmit();}""")
        await joue.wait_for_timeout(700)
        avant = await joue.evaluate("()=>!document.querySelector('#splash').hidden")
        await joue.evaluate("()=>window.__chargementTermine()")
        await joue.wait_for_timeout(300)
        apres = await joue.evaluate("()=>!document.querySelector('#splash').hidden")
        verifier("un chargement qui finit tôt fait partir l'écran tôt",
                 avant and not apres, f"à 700ms: {avant}, après résolution: {apres}")
        await joue.close()

        await b.close()

    _journal.summary(erreurs)

asyncio.run(main())
