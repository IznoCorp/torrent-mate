"""A static server that lets deep client-side paths be requested directly.

The plain `http.server` on 8899 — the one every existing rule points at —
answers a file for a file's own path and nothing else: request `/profil/12`
against it and the answer is 404, because no such file exists on disk. The
router only ever sees a path like that from inside an already-loaded
document, never from a fresh navigation, so nothing measured through 8899
can tell a reload, a shared link, or a browser back button from a 404.

This module holds the server that closes that gap, and nothing else. Files
under its root are served as-is; any other path that does not resolve to an
existing file instead answers `wrapped.html`, exactly the way a host serving
a single-page application is expected to — EXCEPT under `PREFIXES_ASSETS`,
where a missing file stays a 404: a route-shaped address can carry dots of
its own (a release folder name, `Backrooms.2026.MULTi.2160p.WEB-DL`, is not
a file extension), so a dot in the final segment is no longer what decides
the fold. It is not a replacement for 8899: that server keeps its narrower
job, and every existing rule keeps pointing at it. This one is a second,
thread-backed server a rule can start on its own scratch port, hand a root,
and stop again without leaving a process behind.
"""

from __future__ import annotations

import contextlib
import functools
import http.server
import os
import pathlib
import threading
from collections.abc import Iterator

# Never one of these: 8710/8711/8712 are the reverse proxy's routes to prod
# and staging, and 8899 is the prototype's own host — 45 rules already point
# at it, and a second server on the same port would just race it for the
# socket.
PORTS_RESERVES = (8710, 8711, 8712, 8899)


class GestionnaireRepli(http.server.SimpleHTTPRequestHandler):
    """Serves `directory` as-is; answers `wrapped.html` for every other path.

    `translate_path` is the one seam `SimpleHTTPRequestHandler` offers for
    this: it turns a request path into a filesystem path, and the base
    implementation has already resolved the query string, percent-encoding
    and any `..` segment before this override ever sees the result —
    reimplementing any of that here would be the same bug waiting to be
    reintroduced. A path is treated as the router's when the resolved path
    is not an existing FILE and does not fall under `PREFIXES_ASSETS` — the
    directories this root actually serves real, addressable files from. A
    missing file THERE (`/vite/absent.js`) still 404s through the parent
    implementation; everywhere else, no file behind the address folds to the
    document.

    Testing for a FILE rather than mere existence is what makes the bare
    root fall back too: `self.directory` itself exists as a directory, so an
    `exists()` check alone would defer "/" to the parent's own directory
    listing instead of the document every other router-owned address
    already gets — the one entry point a single-page application is
    guaranteed to be asked for.

    A dot in the final segment is deliberately NOT what decides the fold: a
    route param can carry one of its own (a release folder name,
    `Backrooms.2026.MULTi.2160p.WEB-DL`) without being a file extension, and
    only the served directory's actual layout — not a string's shape — says
    which paths are real files.
    """

    # The only directories under a served root this handler answers a
    # missing path from with a 404 rather than the document — real,
    # addressable static files (`assets/…`, `vite/…`), never a route param
    # that merely happens to contain a dot.
    PREFIXES_ASSETS = ("/assets/", "/vite/")

    def translate_path(self, path: str) -> str:
        """Returns the filesystem path a request resolves to.

        Args:
            path: The raw request path, exactly as `http.server` passes it
                to this seam — query string and fragment included.

        Returns:
            The resolved path from the parent implementation when it names
            an existing file, or falls under `PREFIXES_ASSETS` (a missing
            asset reference stays a 404, never the document);
            `directory/wrapped.html` for every other path with no file
            behind it.
        """
        resolu = super().translate_path(path)
        if os.path.isfile(resolu):
            return resolu
        chemin = path.split("?", 1)[0]
        if chemin.startswith(self.PREFIXES_ASSETS):
            return resolu
        return os.path.join(self.directory, "wrapped.html")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — name imposed by BaseHTTPRequestHandler
        """Silences per-request logging.

        A rule driving many requests does not need a stderr line per one —
        the assertions it runs afterward ARE the record of what happened.
        """


@contextlib.contextmanager
def demarrer_serveur(port: int, racine: pathlib.Path) -> Iterator[None]:
    """Serves `racine` on `port` for the lifetime of the `with` block.

    Files under `racine` are served as-is; any path with no file behind it
    instead answers `racine/wrapped.html` — the fallback that lets a deep
    client-side address (`/profil/…`, `/ajout`, `/resolution/<dossier
    portant des points>`) be requested directly rather than only reached by
    navigating there inside an already-loaded document — EXCEPT under
    `GestionnaireRepli.PREFIXES_ASSETS`, where a missing file still 404s.

    Args:
        port: The loopback port to bind. Must not be one of
            `PORTS_RESERVES`.
        racine: The directory to serve. Must contain `wrapped.html`.

    Yields:
        Nothing — the server runs on a daemon thread for the block's
        duration and is reachable at `http://127.0.0.1:{port}/` as soon as
        the `with` statement is entered.

    Raises:
        ValueError: When `port` is one of `PORTS_RESERVES`.
    """
    if port in PORTS_RESERVES:
        raise ValueError(f"port réservé : {port}")
    gestionnaire = functools.partial(GestionnaireRepli, directory=str(racine))
    # ThreadingHTTPServer's constructor binds and listens before returning
    # (bind_and_activate defaults to True) — by the time this line completes,
    # a connection from another thread queues rather than being refused.
    # Nothing below is timing-sensitive: the serving thread only pulls
    # requests off a queue that already exists, so no sleep is needed
    # between starting it and treating the server as ready.
    serveur = http.server.ThreadingHTTPServer(("127.0.0.1", port), gestionnaire)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    try:
        yield
    finally:
        serveur.shutdown()
        serveur.server_close()
        fil.join(timeout=5)


if __name__ == "__main__":
    import sys
    import urllib.error
    import urllib.request

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from commun import Journal

    PORT_PREUVE = 8917
    RACINE_PREUVE = pathlib.Path("/tmp/tm-refonte")

    journal = Journal("serveur.py — le repli répond aux adresses profondes")

    attendu = (RACINE_PREUVE / "wrapped.html").read_bytes()
    bundles = sorted((RACINE_PREUVE / "vite").glob("*.js"))
    if not journal.verifier("un bundle existe sous vite/ pour la preuve",
                            bool(bundles), f"{len(bundles)} trouvé(s)"):
        journal.bilan()
    bundle = bundles[0]

    with demarrer_serveur(PORT_PREUVE, RACINE_PREUVE):
        base = f"http://127.0.0.1:{PORT_PREUVE}"

        with urllib.request.urlopen(f"{base}/profil/X%20Y", timeout=5) as reponse:
            statut_profil, corps_profil = reponse.status, reponse.read()
        journal.verifier(
            "une adresse profonde répond 200 + le document",
            statut_profil == 200 and corps_profil == attendu,
            f"statut {statut_profil}, {len(corps_profil)} octets")

        with urllib.request.urlopen(f"{base}/vite/{bundle.name}", timeout=5) as reponse:
            statut_bundle, corps_bundle = reponse.status, reponse.read()
        journal.verifier(
            "le bundle réel est servi tel quel",
            statut_bundle == 200 and corps_bundle == bundle.read_bytes(),
            f"statut {statut_bundle}, {bundle.name}")

        try:
            urllib.request.urlopen(f"{base}/assets/inexistant.png", timeout=5)
            statut_absent = 200
        except urllib.error.HTTPError as erreur:
            statut_absent = erreur.code
        journal.verifier(
            "un asset absent SOUS UN DOSSIER SERVI 404 plutôt que de tomber dans le repli",
            statut_absent == 404, f"statut {statut_absent}")

        # The regression this fold exists to close: a route-shaped address
        # whose deepest segment carries dots of its own — a release folder
        # name, never a file extension outside PREFIXES_ASSETS — must fold
        # to the document exactly like the bare, extension-less case above.
        with urllib.request.urlopen(
            f"{base}/resolution/Backrooms.2026.MULTi.2160p.WEB-DL", timeout=5
        ) as reponse:
            statut_dossier, corps_dossier = reponse.status, reponse.read()
        journal.verifier(
            "une adresse profonde dont le dernier segment porte des points "
            "répond quand même le document",
            statut_dossier == 200 and corps_dossier == attendu,
            f"statut {statut_dossier}, {len(corps_dossier)} octets")

    journal.bilan()
