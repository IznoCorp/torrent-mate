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

The session is v1's (`tm_v1_session`), so ending it is v1's `POST /api/v1/auth/logout`
and the host has no route of its own for it. The visible half therefore reads that the
sign-out SENT that request (the layer's record of what it answered), and the invisible
half starts the design host over a stand-in v1 and asks whether a session v1 has ended
still opens anything.
"""
import asyncio
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

from common import Journal, open_page, browser_channel, chrome_launch_args
from server import fake_v1
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 8715  # never 8710 / 8711: the reverse proxy routes production and staging there
# The session the stand-in v1 holds, and the cookie that carries it: the design host's door is v1's.
SESSION = "harness-session"

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


def v1_door_admitted_for():
    """How long the host takes a session v1 accepted as still accepted, in seconds."""
    sys.path.insert(0, str(ROOT))
    try:
        import v1_door
    finally:
        sys.path.remove(str(ROOT))
    return v1_door.ADMITTED_FOR


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
        b = await p.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
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
        #    prototype is served statically here and answers v1's sign-out from
        #    its mocks — and a sign-out that failed must not stop the screen.
        await pg.click('#sheet button[data-part="sheet/action"][data-tone="danger"]')
        await pg.wait_for_timeout(400)
        after = await pg.evaluate("""()=>({
          login: getComputedStyle(document.querySelector('#login')).display,
          sheet: document.querySelector('#sheet').hasAttribute('data-open'),
          scrim: document.querySelector('#scrim').hasAttribute('data-open')})""")
        check("it leads to the sign-in screen", after["login"] != "none", str(after))
        check("and closes the sheet", not after["sheet"] and not after["scrim"], str(after))
        check("no JS error even with no server-side route", not errors, str(errors))
        sent = await pg.evaluate("""()=>(window.__mocks?.answered() || [])
          .filter(call => call.operationId === 'signOut')
          .map(call => `${call.method} ${call.path}`)""")
        check("it sends v1's sign-out, which is what ends the session",
              sent == ["POST /api/v1/auth/logout"], str(sent))

        # The account PAGE carries the same exit as the account panel, and its
        # tap has to land on the entry screen just the same: two emitters, one
        # verb, and a rule that read only one of them would stay green over the
        # other going dead.
        account_context, account_page = await open_page(b)
        account_page.on("pageerror", lambda e: errors.append(str(e)))
        await account_page.evaluate("()=>document.querySelector('#toastx')?.click()")
        await account_page.evaluate("()=>window.__store.write({page: 'profile'})")
        await account_page.wait_for_timeout(400)
        page_exit = await account_page.query_selector('#view [data-part="card/foot"][data-signout]')
        check("the account page carries « Se déconnecter »", page_exit is not None)
        if page_exit is not None:
            await page_exit.click()
            await account_page.wait_for_timeout(400)
            landed = await account_page.evaluate(
                "()=>getComputedStyle(document.querySelector('#login')).display")
            check("and its tap leads to the sign-in screen too", landed != "none", landed)
        await account_context.close()

        await b.close()

    # 3. The half that is not visible: the server really stops accepting the
    #    session. Measured on the server, because the screen cannot show it. The
    #    design host asks v1 each time — a refusal is never remembered — so a session
    #    v1 has ended reopens nothing, and a session it still holds does.
    with fake_v1(SESSION) as v1:
        server = subprocess.Popen(
            [sys.executable, str(ROOT / "serve.py"), str(PORT)],
            env={**os.environ, "TM_DESIGN_V1_URL": v1.url},
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            check("the gate answers", bool(wait_for_gate()))
            cookie = f"tm_v1_session={SESSION}"
            # `/offline.html` and the brand assets are open to everyone; the library's artwork
            # is the cheapest gated answer, and it asks v1 without building the document.
            held, _ = request_path("/assets/x.webp", cookie=cookie)
            check("a session v1 holds is admitted past the gate", held == 404, str(held))
            v1.sessions.discard(SESSION)
            time.sleep(v1_door_admitted_for() + 0.5)
            ended, _ = request_path("/assets/x.webp", cookie=cookie)
            check("a session v1 has ended reopens nothing", ended == 401, str(ended))
            status_after, _ = request_path("/", cookie="tm_v1_session=")
            check("and neither does an empty one, which is what a cleared cookie leaves",
                  status_after == 401, str(status_after))
        finally:
            server.terminate()
            server.wait(timeout=5)

    _journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
