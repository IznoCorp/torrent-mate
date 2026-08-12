"""R54 — signing out ends the session and lands on the entry screen.

Two halves, and only one of them is visible.

The visible half: the button used to answer with a message saying the session
had been closed. A message is not a destination — the interface it was written
on stayed exactly where it was, signed in.

The invisible half is the one that matters: the session IS the cookie, and the
cookie belongs to the server. An interface that showed the entry form while the
cookie was still valid would be contradicted by the next reload, which would
walk straight back in. So this script does not settle for the screen changing —
it asks the server, afterwards, whether the session is still accepted.
"""
import asyncio
import http.cookies
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

from playwright.async_api import async_playwright

RACINE = pathlib.Path(__file__).resolve().parent.parent
PORT = 8715  # never 8710 / 8711: the reverse proxy routes production and staging there
BAR = "─" * 62

echecs = []
faits = 0


def verifier(nom, condition, detail=""):
    """Records one executed check and its verdict."""
    global faits
    faits += 1
    print(("  OK   " if condition else "  ECHEC") + f" {nom}" + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def attendre_portail():
    """Waits for the design server to answer, and returns its gate page."""
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2) as r:
                return r.read().decode()
        except urllib.error.HTTPError as err:  # 401 carries the gate
            return err.read().decode()
        except OSError:
            time.sleep(0.1)
    return ""


def demander(chemin, cookie=None):
    """Performs one GET without following redirects.

    Args:
        chemin: The path to request.
        cookie: A raw Cookie header value, or None.

    Returns:
        A (status, headers) pair.
    """
    class SansRedirection(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    requete = urllib.request.Request(f"http://127.0.0.1:{PORT}{chemin}")
    if cookie:
        requete.add_header("Cookie", cookie)
    ouvreur = urllib.request.build_opener(SansRedirection)
    try:
        with ouvreur.open(requete, timeout=5) as r:
            return r.status, r.headers
    except urllib.error.HTTPError as err:
        return err.code, err.headers


async def main():
    print(f"{BAR}\nR54 — déconnexion\n{BAR}")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        await pg.evaluate("()=>document.querySelector('#toastx').click()")

        # 1. The button exists where a session is ended from, and it is the only
        #    one: an exit reachable from nowhere is an exit nobody finds.
        await pg.evaluate("()=>window.__go('feuille-utilisateur')")
        await pg.wait_for_timeout(250)
        boutons = await pg.evaluate("""()=>[...document.querySelectorAll('#sheet button')]
          .filter(x=>/déconnecter/i.test(x.textContent))
          .map(x=>({texte:x.textContent.trim(), donnees:Object.keys(x.dataset),
                    haut:x.getBoundingClientRect().height}))""")
        verifier("le menu utilisateur porte « Se déconnecter »", len(boutons) == 1, str(boutons))
        verifier("et il n'y répond pas par un simple message",
                 bool(boutons) and "toast" not in boutons[0]["donnees"],
                 str(boutons[0]["donnees"]) if boutons else "")

        # 2. Pressing it lands on the entry screen, with the sheet gone. The
        #    prototype is served statically here, so the request to end the
        #    session has nowhere to land — and that must not stop the screen.
        await pg.click("#sheet button.sact.danger")
        await pg.wait_for_timeout(400)
        apres = await pg.evaluate("""()=>({
          connexion: getComputedStyle(document.querySelector('#login')).display,
          feuille: document.querySelector('#sheet').classList.contains('open'),
          voile: document.querySelector('#scrim').classList.contains('open')})""")
        verifier("mène à l'écran de connexion", apres["connexion"] != "none", str(apres))
        verifier("et referme la feuille", not apres["feuille"] and not apres["voile"], str(apres))
        verifier("sans erreur JS même sans route côté serveur", not erreurs, str(erreurs))

        await b.close()

    # 3. The half that is not visible: the server really stops accepting the
    #    session. Measured on the server, because the screen cannot show it.
    serveur = subprocess.Popen(
        [sys.executable, str(RACINE / "serve.py"), str(PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        verifier("le portail répond", bool(attendre_portail()))
        statut, entetes = demander("/deconnexion")
        biscuit = http.cookies.SimpleCookie()
        biscuit.load(entetes.get("Set-Cookie", ""))
        morceau = biscuit.get("tm_design")
        # One check, not two: everything else on this server answers an unknown
        # path with the same redirect, so a status read on its own could never
        # tell a working route from a missing one.
        verifier("« /deconnexion » périme le cookie et renvoie au portail",
                 statut == 303 and entetes.get("Location") == "/"
                 and morceau is not None and morceau.value == ""
                 and str(morceau["max-age"]) == "0",
                 f"{statut} → {entetes.get('Location')} · "
                 f"{entetes.get('Set-Cookie', 'aucun Set-Cookie')}")
        # The cookie the gate hands out is unknown here — the password is not in
        # the repository — but ANY value must be refused once expired, and an
        # empty one is exactly what the browser is left holding.
        statut_apres, _ = demander("/", cookie="tm_design=")
        verifier("un cookie périmé ne rouvre rien", statut_apres == 401, str(statut_apres))
    finally:
        serveur.terminate()
        serveur.wait(timeout=5)

    print()
    print(f"{BAR}\n{faits} règles EXÉCUTÉES — "
          + ("aucune violation" if not echecs else f"{len(echecs)} violation(s) : {', '.join(echecs)}"))
    if echecs:
        raise SystemExit(1)

asyncio.run(main())
