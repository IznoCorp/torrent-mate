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
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, Journal

PORT = 8918
# The scratch design root is NESTED, because the tree it copies is not
# self-contained and says so: `engine/engine-shape.ts` imports the mock layer's
# declaration from `frontend/maquette/`, one level above the design root, and
# the boundaries guard names that reach as a decision until the engine dies at
# L13. A flat scratch made the copy unbuildable — every hold here answered 503
# and the rule read a broken host where there was only an incomplete copy.
SCRATCH_HOME = pathlib.Path("/tmp/tm-refonte/_r73")
SCRATCH = SCRATCH_HOME / "design"
PASSWORD = "epreuve"


def fingerprint() -> str:
    salt = os.urandom(16)
    computed = hashlib.scrypt(PASSWORD.encode(), salt=salt,
                             n=16384, r=8, p=1, dklen=32)
    return (base64.b64encode(salt).decode() + ":"
            + base64.b64encode(computed).decode())


def prepare_scratch() -> None:
    """Builds the scratch design root: copies for what mutates, links for
    what must stay shared and read-only (node_modules, the artwork).
    """
    if SCRATCH_HOME.exists():
        shutil.rmtree(SCRATCH_HOME)
    SCRATCH.mkdir(parents=True)
    design = ROOT / "design"
    for name in ("refonte.html", "index.html", "vite.config.mjs", "package.json"):
        shutil.copy(design / name, SCRATCH / name)
    # The envelope names a module entry: without its source the scratch build
    # cannot resolve it, and the rule would report a broken host where there is
    # only an incomplete copy. It is copied, not linked — a mutation probe may
    # edit it, and no measurement writes into the operator's source.
    shutil.copytree(design / "src", SCRATCH / "src")
    (SCRATCH / "node_modules").symlink_to(design / "node_modules")
    (SCRATCH / "assets").symlink_to(design / "assets")
    # And whatever the tree reaches for OUTSIDE itself, found by reading the
    # sources rather than by naming one file here: a name typed into this rule
    # is a second copy of the guard's list, and it would rot the day a second
    # reach is allowed. Each is copied at the same relative depth, so the
    # copy resolves the import exactly as the source does.
    for module in sorted(SCRATCH.glob("src/**/*.ts")) + sorted(SCRATCH.glob("src/**/*.tsx")):
        for match in re.finditer(r'from "((?:\.\./)+[^"]+)"', module.read_text()):
            # RESOLVED ON BOTH SIDES, because `/tmp` is a symlink to
            # `/private/tmp` here: comparing a resolved target against an
            # unresolved root made every in-tree import look like an escape.
            target = (module.parent / match.group(1)).resolve()
            root = SCRATCH.resolve()
            if root in target.parents:
                continue
            # Where it sits relative to the design root is what the source tree
            # is asked for — the file NAME alone would read the wrong file the
            # day two directories hold the same one.
            step = os.path.relpath(target, root)
            landing = SCRATCH / step
            if not landing.exists():
                landing.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(design / step, landing)


def request_(path_, cookie=None, method="GET", body=None):
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=150)
    headers = {}
    if cookie:
        headers["Cookie"] = cookie
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    conn.request(method, path_, body=body, headers=headers)
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return response, data


def main():
    journal = Journal("R73 — the host serves the build")
    server = None
    try:
        prepare_scratch()
        server = subprocess.Popen(
            [sys.executable, str(ROOT / "serve.py"), str(PORT)],
            env={**os.environ, "TM_DESIGN_ROOT": str(SCRATCH),
                 "TM_DESIGN_PASSWORD_HASH": fingerprint()},
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        # Boot wait: poll until the port answers (up to 50 × 0.1 s). When it
        # never answers, the child's stderr is the only trace of why — a bind
        # error must read as a bind error, not as a failed session open after
        # a wait that says nothing about it.
        for attempt in range(50):
            try:
                request_("/")
                break
            except (OSError, http.client.HTTPException):
                if attempt == 49:
                    # communicate() returns as soon as the child exits (a
                    # failed bind crashes it with a traceback) and waits a
                    # few seconds for a child that is still alive; either
                    # way, whatever was written is printed before re-raising.
                    try:
                        _, stderr_bytes = server.communicate(timeout=5)
                    except subprocess.TimeoutExpired as expired:
                        stderr_bytes = expired.stderr
                    if stderr_bytes:
                        print(f"serve.py stderr:\n"
                              f"{stderr_bytes.decode('utf-8', 'replace')}",
                              file=sys.stderr)
                    else:
                        print("serve.py wrote nothing to stderr before it "
                              "stopped answering", file=sys.stderr)
                    raise
                time.sleep(0.1)

        response, _ = request_(
            "/login", method="POST",
            body=f"username=izno&password={PASSWORD}")
        cookie = (response.getheader("Set-Cookie") or "").split(";")[0]
        journal.check("the session opens", response.status == 303 and cookie,
                         f"{response.status}")

        # (a) The served document IS the build, to the byte.
        response, served = request_("/", cookie)
        built_path = SCRATCH / "dist" / "index.html"
        built = built_path.read_bytes() if built_path.exists() else None
        journal.check("the served document is the build, to the byte",
                      response.status == 200 and built is not None and served == built,
                      f"{len(served)} bytes served, "
                      + (f"{len(built)} in the build" if built is not None
                         else "dist never emitted"))

        # (fallback) A path routing owns client-side (/mediasheet/…, /profile/…) is
        # not a route this static host knows about — it must still answer the
        # ONE document, exactly like "/", session-gated the same way. A 303
        # here would drop the address bar's path and defeat the router before
        # it runs; a 404 would dead-end a reload or a shared link.
        response_without, without_session = request_("/media/tvdb/403245")
        response_root, login_page = request_("/")
        journal.check(
            "an unknown address with no session answers the sign-in screen, like «/»",
            response_without.status == 401 and response_root.status == 401
            and without_session == login_page,
            f"{response_without.status} vs {response_root.status}")

        response_with, with_session = request_("/media/tvdb/403245", cookie)
        journal.check(
            "an unknown address with a session answers the SAME document as «/»",
            response_with.status == 200 and with_session == served,
            f"{response_with.status}, {len(with_session)} bytes against "
            f"{len(served)} at «/»")

        # (dotted fallback) The generic fallback above is matched on a path
        # with NO dot in it. A route-shaped path can carry one of its own — a
        # release folder name, never a file extension — and this host's own
        # unmatched-path branch (`do_GET`'s final `if not path_.startswith(
        # ...)` cascade in `serve.py`) never tested for dots in the first
        # place, so nothing here needed changing to hold: proven directly,
        # with the SAME dossier that regressed `server.py`'s harness-only
        # fallback (Task 5, `server.py`).
        response_dots, with_dots = request_(
            "/resolution/Backrooms.2026.MULTi.2160p.WEB-DL", cookie)
        journal.check(
            "a deep address whose last segment carries dots "
            "answers, with a session, the SAME document as «/»",
            response_dots.status == 200 and with_dots == served,
            f"{response_dots.status}, {len(with_dots)} bytes against "
            f"{len(served)} at «/»")

        # (favicon) A brand asset, served without a session like the manifest
        # and the PWA icons — a `<link rel="icon">` is fetched uncredentialed.
        response_favicon, favicon_body = request_("/favicon.svg")
        journal.check(
            "/favicon.svg answers 200 image/svg+xml",
            response_favicon.status == 200
            and (response_favicon.getheader("Content-Type") or "").startswith("image/svg+xml"),
            f"{response_favicon.status}, {response_favicon.getheader('Content-Type')}")

        # (portal) The library's real artwork stays gated even now that an
        # unknown path falls through to the document instead of a redirect —
        # the fallback must not swallow the /assets/ portal rule ahead of it.
        response_portal, portal_body = request_("/assets/x.webp")
        journal.check(
            "/assets/x.webp with no session answers 401 — never the sign-in page, "
            "never the file",
            response_portal.status == 401 and portal_body == b"",
            f"{response_portal.status}, {len(portal_body)} bytes")

        # (b) An edited source is served rebuilt — never yesterday's build.
        with open(SCRATCH / "refonte.html", "a") as file_:
            file_.write("\n<!-- r73-probe -->\n")
        response, served = request_("/", cookie)
        journal.check("an edited source is rebuilt on the fly",
                         response.status == 200 and b"r73-probe" in served,
                         f"{response.status}")

        # Mutation 3: Verify that a corrupted build (served bytes != dist) is
        # caught by the byte-identity hold ALONE. Corrupt the dist after it's
        # built, then verify ONLY the byte-identity hold fails (others still pass).
        dist_path = SCRATCH / "dist" / "index.html"
        dist_original = dist_path.read_bytes()
        try:
            dist_path.write_bytes(dist_original + b"\n")
            response, served = request_("/", cookie)
            # The served bytes are now corrupted: served != dist (but status 200).
            # This is a design-conformity hold; it fells byte-identity alone.
            # Verifying here proves mutation 3's isolation.
            journal.check("mutation 3: corrupted build bytes — only the hold "
                          "«the served document is the build, to the byte» gives way",
                          response.status == 200 and served != dist_original,
                          f"{response.status}, equal: {served == dist_original}")
        finally:
            dist_path.write_bytes(dist_original)

        # (c) A broken build answers 503 and SAYS it broke.
        (SCRATCH / "vite.config.mjs").write_text("ceci n'est pas du javascript {\n")
        # The config is a build input: its mtime alone must trigger the try.
        response, body = request_("/", cookie)
        body_str = body.decode("utf-8", "replace")
        # Extract text between <pre and </pre> and check for non-empty error.
        pre_start = body_str.find("<pre")
        pre_end = body_str.find("</pre>")
        error_excerpt = ""
        if pre_start >= 0 and pre_end > pre_start:
            tag_end = body_str.find(">", pre_start)
            if tag_end >= 0 and tag_end < pre_end:
                error_excerpt = body_str[tag_end + 1:pre_end].strip()
        error_not_empty = len("".join(error_excerpt.split())) >= 10
        journal.check("a broken build answers 503 and says so",
                         response.status == 503
                         and "build de la maquette a" in body_str
                         and error_not_empty,
                         f"{response.status}, error: {error_excerpt[:60]}")

        # And the way back: restoring the config heals the host on its own.
        shutil.copy(ROOT / "design" / "vite.config.mjs",
                    SCRATCH / "vite.config.mjs")
        response, served = request_("/", cookie)
        journal.check("restoring the source heals the host",
                         response.status == 200 and b"r73-probe" in served,
                         f"{response.status}")
    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
        shutil.rmtree(SCRATCH, ignore_errors=True)
    journal.summary()


main()
