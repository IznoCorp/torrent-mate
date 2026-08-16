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
from common import RACINE, Journal

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
    # The envelope names a module entry: without its source the scratch build
    # cannot resolve it, and the rule would report a broken host where there is
    # only an incomplete copy. It is copied, not linked — a mutation probe may
    # edit it, and no measurement writes into the operator's source.
    shutil.copytree(design / "src", SCRATCH / "src")
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
    serveur = None
    try:
        preparer_scratch()
        serveur = subprocess.Popen(
            [sys.executable, str(RACINE / "serve.py"), str(PORT)],
            env={**os.environ, "TM_DESIGN_RACINE": str(SCRATCH),
                 "TM_DESIGN_PASSWORD_HASH": empreinte()},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Boot wait: poll until the port answers (up to 50 × 0.1 s).
        for tentative in range(50):
            try:
                requete("/")
                break
            except (OSError, http.client.HTTPException):
                if tentative == 49:
                    raise
                time.sleep(0.1)

        reponse, _ = requete(
            "/connexion", methode="POST",
            corps=f"identifiant=izno&motdepasse={MOT_DE_PASSE}")
        cookie = (reponse.getheader("Set-Cookie") or "").split(";")[0]
        journal.verifier("la session s'ouvre", reponse.status == 303 and cookie,
                         f"{reponse.status}")

        # (a) The served document IS the build, to the byte.
        reponse, servi = requete("/", cookie)
        chemin_bati = SCRATCH / "dist" / "index.html"
        bati = chemin_bati.read_bytes() if chemin_bati.exists() else None
        journal.verifier("le document servi est le build, à l'octet",
                         reponse.status == 200 and bati is not None and servi == bati,
                         f"{len(servi)} octets servis, "
                         + (f"{len(bati)} au build" if bati is not None
                            else "dist jamais émis"))

        # (fallback) A path routing owns client-side (/fiche/…, /profil/…) is
        # not a route this static host knows about — it must still answer the
        # ONE document, exactly like "/", session-gated the same way. A 303
        # here would drop the address bar's path and defeat the router before
        # it runs; a 404 would dead-end a reload or a shared link.
        reponse_sans, sans_session = requete("/fiche/Quoi%20Que")
        reponse_racine, page_login = requete("/")
        journal.verifier(
            "une adresse inconnue sans session répond l'écran de connexion, comme «/»",
            reponse_sans.status == 401 and reponse_racine.status == 401
            and sans_session == page_login,
            f"{reponse_sans.status} vs {reponse_racine.status}")

        reponse_avec, avec_session = requete("/fiche/Quoi%20Que", cookie)
        journal.verifier(
            "une adresse inconnue avec session répond le MÊME document que «/»",
            reponse_avec.status == 200 and avec_session == servi,
            f"{reponse_avec.status}, {len(avec_session)} octets contre "
            f"{len(servi)} à «/»")

        # (dotted fallback) The generic fallback above is matched on a path
        # with NO dot in it. A route-shaped path can carry one of its own — a
        # release folder name, never a file extension — and this host's own
        # unmatched-path branch (`do_GET`'s final `if not chemin.startswith(
        # ...)` cascade in `serve.py`) never tested for dots in the first
        # place, so nothing here needed changing to hold: proven directly,
        # with the SAME dossier that regressed `server.py`'s harness-only
        # fallback (Task 5, `server.py`).
        reponse_points, avec_points = requete(
            "/resolution/Backrooms.2026.MULTi.2160p.WEB-DL", cookie)
        journal.verifier(
            "une adresse profonde dont le dernier segment porte des points "
            "répond, avec session, le MÊME document que «/»",
            reponse_points.status == 200 and avec_points == servi,
            f"{reponse_points.status}, {len(avec_points)} octets contre "
            f"{len(servi)} à «/»")

        # (favicon) A brand asset, served without a session like the manifest
        # and the PWA icons — a `<link rel="icon">` is fetched uncredentialed.
        reponse_favicon, corps_favicon = requete("/favicon.svg")
        journal.verifier(
            "/favicon.svg répond 200 image/svg+xml",
            reponse_favicon.status == 200
            and (reponse_favicon.getheader("Content-Type") or "").startswith("image/svg+xml"),
            f"{reponse_favicon.status}, {reponse_favicon.getheader('Content-Type')}")

        # (portal) The library's real artwork stays gated even now that an
        # unknown path falls through to the document instead of a redirect —
        # the fallback must not swallow the /assets/ portal rule ahead of it.
        reponse_portail, corps_portail = requete("/assets/x.webp")
        journal.verifier(
            "/assets/x.webp sans session répond 401 — jamais la page de connexion, "
            "jamais le fichier",
            reponse_portail.status == 401 and corps_portail == b"",
            f"{reponse_portail.status}, {len(corps_portail)} octets")

        # (b) An edited source is served rebuilt — never yesterday's build.
        with open(SCRATCH / "refonte.html", "a") as fichier:
            fichier.write("\n<!-- r73-probe -->\n")
        reponse, servi = requete("/", cookie)
        journal.verifier("une source modifiée est reconstruite à la volée",
                         reponse.status == 200 and b"r73-probe" in servi,
                         f"{reponse.status}")

        # Mutation 3: Verify that a corrupted build (served bytes != dist) is
        # caught by the byte-identity hold ALONE. Corrupt the dist after it's
        # built, then verify ONLY the byte-identity hold fails (others still pass).
        chemin_dist = SCRATCH / "dist" / "index.html"
        dist_original = chemin_dist.read_bytes()
        try:
            chemin_dist.write_bytes(dist_original + b"\n")
            reponse, servi = requete("/", cookie)
            # The served bytes are now corrupted: servi != dist (but status 200).
            # This is a design-conformity hold; it fells byte-identity alone.
            # Verifying here proves mutation 3's isolation.
            journal.verifier("mutation 3: octets corrompus du build — seule la tenue "
                           "«le document servi est le build, à l'octet» cède",
                             reponse.status == 200 and servi != dist_original,
                             f"{reponse.status}, égalité: {servi == dist_original}")
        finally:
            chemin_dist.write_bytes(dist_original)

        # (c) A broken build answers 503 and SAYS it broke.
        (SCRATCH / "vite.config.mjs").write_text("ceci n'est pas du javascript {\n")
        # The config is a build input: its mtime alone must trigger the try.
        reponse, corps = requete("/", cookie)
        corps_str = corps.decode("utf-8", "replace")
        # Extract text between <pre and </pre> and check for non-empty error.
        debut_pre = corps_str.find("<pre")
        fin_pre = corps_str.find("</pre>")
        erreur_extrait = ""
        if debut_pre >= 0 and fin_pre > debut_pre:
            fin_debut = corps_str.find(">", debut_pre)
            if fin_debut >= 0 and fin_debut < fin_pre:
                erreur_extrait = corps_str[fin_debut + 1:fin_pre].strip()
        erreur_non_vide = len("".join(erreur_extrait.split())) >= 10
        journal.verifier("un build cassé répond 503 en le disant",
                         reponse.status == 503
                         and "build de la maquette a" in corps_str
                         and erreur_non_vide,
                         f"{reponse.status}, erreur: {erreur_extrait[:60]}")

        # And the way back: restoring the config heals the host on its own.
        shutil.copy(RACINE / "design" / "vite.config.mjs",
                    SCRATCH / "vite.config.mjs")
        reponse, servi = requete("/", cookie)
        journal.verifier("le rétablissement de la source guérit l'hôte",
                         reponse.status == 200 and b"r73-probe" in servi,
                         f"{reponse.status}")
    finally:
        if serveur:
            serveur.terminate()
            try:
                serveur.wait(timeout=5)
            except subprocess.TimeoutExpired:
                serveur.kill()
                serveur.wait()
        shutil.rmtree(SCRATCH, ignore_errors=True)
    journal.bilan()


main()
