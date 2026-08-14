"""R73 — the host serves the build, and a failed build says so.

Since the switch, the document the operator judges is the Vite build. Three
things must therefore hold, and each has its own way of rotting silently:
the served bytes could drift from `dist/index.html` (a re-grown synthesis),
an edit could serve yesterday's build (a stale reference wearing today's
date), and a broken build could hide behind the previous output. The rule
boots the real `serve.py` on a scratch COPY of the design root — a
measurement must never write into the operator's source — and holds all
three over plain HTTP.
"""
import base64
import hashlib
import http.client
import os
import pathlib
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from commun import RACINE, Journal

PORT = 8918
SCRATCH = pathlib.Path("/tmp/tm-refonte/_r73")
MOT_DE_PASSE = "epreuve"


def empreinte() -> str:
    sel = os.urandom(16)
    calcule = hashlib.scrypt(MOT_DE_PASSE.encode(), salt=sel,
                             n=16384, r=8, p=1, dklen=32)
    return (base64.b64encode(sel).decode() + ":"
            + base64.b64encode(calcule).decode())


def preparer_scratch() -> None:
    """Builds the scratch design root: copies for what mutates, links for
    what must stay shared and read-only (node_modules, the artwork).
    """
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    design = RACINE / "design"
    for nom in ("refonte.html", "index.html", "vite.config.mjs", "package.json"):
        shutil.copy(design / nom, SCRATCH / nom)
    (SCRATCH / "node_modules").symlink_to(design / "node_modules")
    (SCRATCH / "assets").symlink_to(design / "assets")


def requete(chemin, cookie=None, methode="GET", corps=None):
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=150)
    entetes = {}
    if cookie:
        entetes["Cookie"] = cookie
    if corps is not None:
        entetes["Content-Type"] = "application/x-www-form-urlencoded"
    conn.request(methode, chemin, body=corps, headers=entetes)
    reponse = conn.getresponse()
    donnees = reponse.read()
    conn.close()
    return reponse, donnees


def main():
    journal = Journal("R73 — l'hôte sert le build")
    preparer_scratch()
    serveur = subprocess.Popen(
        [sys.executable, str(RACINE / "serve.py"), str(PORT)],
        env={**os.environ, "TM_DESIGN_RACINE": str(SCRATCH),
             "TM_DESIGN_PASSWORD_HASH": empreinte()},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1)
        reponse, _ = requete(
            "/connexion", methode="POST",
            corps=f"identifiant=izno&motdepasse={MOT_DE_PASSE}")
        cookie = (reponse.getheader("Set-Cookie") or "").split(";")[0]
        journal.verifier("la session s'ouvre", reponse.status == 303 and cookie,
                         f"{reponse.status}")

        # (a) The served document IS the build, to the byte.
        reponse, servi = requete("/", cookie)
        bati = (SCRATCH / "dist" / "index.html").read_bytes()
        journal.verifier("le document servi est le build, à l'octet",
                         reponse.status == 200 and servi == bati,
                         f"{len(servi)} octets servis, {len(bati)} au build")

        # (b) An edited source is served rebuilt — never yesterday's build.
        with open(SCRATCH / "refonte.html", "a") as fichier:
            fichier.write("\n<!-- r73-probe -->\n")
        reponse, servi = requete("/", cookie)
        journal.verifier("une source modifiée est reconstruite à la volée",
                         reponse.status == 200 and b"r73-probe" in servi,
                         f"{reponse.status}")

        # (c) A broken build answers 503 and SAYS it broke.
        (SCRATCH / "vite.config.mjs").write_text("ceci n'est pas du javascript {\n")
        # The config is a build input: its mtime alone must trigger the try.
        reponse, corps = requete("/", cookie)
        journal.verifier("un build cassé répond 503 en le disant",
                         reponse.status == 503
                         and "build de la maquette a" in corps.decode("utf-8", "replace"),
                         f"{reponse.status}")

        # And the way back: restoring the config heals the host on its own.
        shutil.copy(RACINE / "design" / "vite.config.mjs",
                    SCRATCH / "vite.config.mjs")
        reponse, servi = requete("/", cookie)
        journal.verifier("le rétablissement de la source guérit l'hôte",
                         reponse.status == 200 and b"r73-probe" in servi,
                         f"{reponse.status}")
    finally:
        serveur.terminate()
        serveur.wait(timeout=5)
        shutil.rmtree(SCRATCH, ignore_errors=True)
    journal.bilan()


main()
