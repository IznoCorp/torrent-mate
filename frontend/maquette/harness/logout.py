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

from common import Journal, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 8715  # never 8710 / 8711: the reverse proxy routes production and staging there

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


def wait_for_gate():
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


def request_path(path, cookie=None):
    """Performs one GET without following redirects.

    Args:
        path: The path to request.
        cookie: A raw Cookie header value, or None.

    Returns:
        A (status, headers) pair.
    """
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}")
    if cookie:
        req.add_header("Cookie", cookie)
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=5) as r:
            return r.status, r.headers
    except urllib.error.HTTPError as err:
        return err.code, err.headers


async def main():
    global _journal
    _journal = Journal("R54 — signing out")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(b)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.evaluate("()=>document.querySelector('#toastx').click()")

        # 1. The button exists where a session is ended from, and it is the only
        #    one: an exit reachable from nowhere is an exit nobody finds.
        await pg.evaluate("()=>window.__go('sheet-user')")
        await pg.wait_for_timeout(250)
        buttons = await pg.evaluate("""()=>[...document.querySelectorAll('#sheet button')]
          .filter(x=>/déconnecter/i.test(x.textContent))
          .map(x=>({text:x.textContent.trim(), data:Object.keys(x.dataset),
                    height:x.getBoundingClientRect().height}))""")
        check("the user menu carries « Se déconnecter »", len(buttons) == 1, str(buttons))
        check("and it does not answer with a mere message",
                 bool(buttons) and "toast" not in buttons[0]["data"],
          str(buttons[0]["data"]) if buttons else "")

        # 2. Pressing it lands on the entry screen, with the sheet gone. The
        #    prototype is served statically here, so the request to end the
        #    session has nowhere to land — and that must not stop the screen.
        await pg.click("#sheet button.sact.danger")
        await pg.wait_for_timeout(400)
        after = await pg.evaluate("""()=>({
          login: getComputedStyle(document.querySelector('#login')).display,
          sheet: document.querySelector('#sheet').classList.contains('open'),
          scrim: document.querySelector('#scrim').classList.contains('open')})""")
        check("it leads to the sign-in screen", after["login"] != "none", str(after))
        check("and closes the sheet", not after["sheet"] and not after["scrim"], str(after))
        check("no JS error even with no server-side route", not errors, str(errors))

        await b.close()

    # 3. The half that is not visible: the server really stops accepting the
    #    session. Measured on the server, because the screen cannot show it.
    server = subprocess.Popen(
        [sys.executable, str(ROOT / "serve.py"), str(PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        check("the gate answers", bool(wait_for_gate()))
        status, headers = request_path("/logout")
        jar = http.cookies.SimpleCookie()
        jar.load(headers.get("Set-Cookie", ""))
        crumb = jar.get("tm_design")
        # One check, not two: everything else on this server answers an unknown
        # path with the same redirect, so a status read on its own could never
        # tell a working route from a missing one.
        check("« /logout » expires the cookie and sends back to the gate",
                 status == 303 and headers.get("Location") == "/"
                 and crumb is not None and crumb.value == ""
                 and str(crumb["max-age"]) == "0",
                 f"{status} → {headers.get('Location')} · "
                 f"{headers.get('Set-Cookie', 'no Set-Cookie')}")
        # The cookie the gate hands out is unknown here — the password is not in
        # the repository — but ANY value must be refused once expired, and an
        # empty one is exactly what the browser is left holding.
        status_after, _ = request_path("/", cookie="tm_design=")
        check("an expired cookie reopens nothing", status_after == 401, str(status_after))
    finally:
        server.terminate()
        server.wait(timeout=5)

    _journal.summary()

asyncio.run(main())
