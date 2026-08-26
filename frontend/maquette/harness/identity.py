"""R87 — the drawer names what this host is serving, or says it cannot.

THE DEFECT WAS NOT SILENCE, and that distinction is the whole rule. The drawer
stated `0.98.23` and `build 58d0d4fd · à jour` as literals while the repository
stood nineteen patch versions further on, and « à jour » asserted a freshness
nothing measured. A screen that says nothing sends its reader to look; a screen
that states a plausible answer stops them looking. So this rule holds two
things that are easy to confuse:

  when a host publishes an identity, the drawer shows THAT identity — the
  branch, the commit, and a mark when the tree is dirty;

  when no host published one, the drawer says the identity is unavailable and
  gives the reason. It does not fall back to anything. A fallback here would be
  the original defect wearing a different number.

AND IT IS COMPUTED PER REQUEST. Two requests across a change to the tree must
answer differently, from the same running process — a value cached at boot is
the same drift with a shorter half-life, and it is what production's own R27
post-check exists to catch on the other side.

WHAT THIS RULE DOES NOT READ.

It does not read `git`. It asserts that the host's answer CHANGES when the tree
changes and that the drawer shows what the host published; it never re-derives
the branch or the commit itself, because a rule that computed the same value
the same way would agree with a wrong implementation.

It does not read the design host's real password, which is nowhere in this
repository. It starts its own server with a hash it sets, on its own port.

It does not read production. `GET /api/version` and R27 are the other side of
this question and belong to the shipped application; nothing here touches them.
"""
import asyncio
import base64
import hashlib
import http.cookies
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from common import Journal, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 8716  # never 8710 / 8711 (the reverse proxy) and never 8712 (the design host)
PASSWORD = "harness-only-password"
# A LEGAL git ref that ends a script element. `git check-ref-format --branch`
# accepts it; only a space would be refused, and the payload needs none.
HOSTILE_BRANCH = "</script><img/src=x/onerror=alert(1)>"
IDENTITY = '[data-part="shell/served-identity"]'

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


def password_hash() -> str:
    """Returns a scrypt hash of this rule's own password, in the host's format."""
    salt = b"harness-salt-16b"
    derived = hashlib.scrypt(PASSWORD.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return base64.b64encode(salt).decode() + ":" + base64.b64encode(derived).decode()


def wait_for_gate() -> bool:
    """Waits for the design server to answer at all."""
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2)
            return True
        except urllib.error.HTTPError:  # 401 carries the gate, and that is an answer
            return True
        except OSError:
            time.sleep(0.1)
    return False


def sign_in() -> str | None:
    """Signs in and returns the raw session cookie, or None."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    body = urllib.parse.urlencode({"username": os.environ.get("TM_DESIGN_USER", "izno"),
                                   "password": PASSWORD}).encode()
    request = urllib.request.Request(f"http://127.0.0.1:{PORT}/login", data=body)
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=5) as answer:
            headers = answer.headers
    except urllib.error.HTTPError as refused:
        headers = refused.headers
    jar = http.cookies.SimpleCookie()
    jar.load(headers.get("Set-Cookie", ""))
    crumb = jar.get("tm_design")
    if crumb is None or not crumb.value:
        return None
    return f"tm_design={crumb.value}"


def document(cookie: str) -> str:
    """Fetches the served document with a session."""
    request = urllib.request.Request(f"http://127.0.0.1:{PORT}/")
    request.add_header("Cookie", cookie)
    with urllib.request.urlopen(request, timeout=180) as answer:
        return answer.read().decode("utf-8", "replace")


def published(page_text: str) -> str | None:
    """Returns the identity payload the document publishes, as raw text."""
    marker = "window.__servedIdentity="
    if marker not in page_text:
        return None
    return page_text.split(marker, 1)[1].split(";</script>", 1)[0]


async def read_drawer():
    """Opens the prototype on the STATIC host and reads the identity block."""
    async with async_playwright() as driver:
        browser = await driver.chromium.launch(channel="chrome")
        _, page = await open_page(browser)
        await page.evaluate("()=>window.__go('drawer-navigation')")
        await page.wait_for_timeout(400)
        unpublished = await page.evaluate(
            "(selector)=>{const block=document.querySelector(selector);"
            "return block ? {known: block.hasAttribute('data-known'),"
            " lines: [...block.children].map(line=>line.textContent)} : null;}", IDENTITY)
        # The published case is driven here rather than measured against the
        # design host, so that the DRAWER's two states are read the same way.
        # That the host really publishes this shape is the server half below.
        await page.evaluate("""()=>{window.__servedIdentity =
            {branch:'branch-under-test', detached:false,
             commit:'0badc0de', dirty:true};}""")
        await page.evaluate("()=>window.__go('acq-now-idle')")
        await page.wait_for_timeout(200)
        await page.evaluate("()=>window.__go('drawer-navigation')")
        await page.wait_for_timeout(400)
        dirty = await page.evaluate(
            "(selector)=>{const block=document.querySelector(selector);"
            "return {known: block.hasAttribute('data-known'),"
            " lines: [...block.children].map(line=>line.textContent)};}", IDENTITY)
        await page.evaluate("()=>{window.__servedIdentity.dirty = false;}")
        await page.evaluate("()=>window.__go('acq-now-idle')")
        await page.wait_for_timeout(200)
        await page.evaluate("()=>window.__go('drawer-navigation')")
        await page.wait_for_timeout(400)
        clean = await page.evaluate(
            "(selector)=>[...document.querySelector(selector).children]"
            ".map(line=>line.textContent)", IDENTITY)

        # A DETACHED HEAD IS NOT A BRANCH CALLED « HEAD », and this is the hold
        # that says so. `rev-parse --abbrev-ref HEAD` answers the literal string
        # `HEAD` there, exit 0, so a reader that trusted it would render `HEAD`
        # where it renders a branch — plausible, wrong, and unreadable as an
        # anomaly. The incident that opened this defect WAS a detached checkout
        # two commits behind, read as a branch.
        await page.evaluate("""()=>{window.__servedIdentity =
            {branch:'', detached:true, commit:'0badc0de', dirty:false};}""")
        await page.evaluate("()=>window.__go('acq-now-idle')")
        await page.wait_for_timeout(200)
        await page.evaluate("()=>window.__go('drawer-navigation')")
        await page.wait_for_timeout(400)
        detached = await page.evaluate(
            "(selector)=>{const block=document.querySelector(selector);"
            "return {known: block.hasAttribute('data-known'),"
            " lines: [...block.children].map(line=>line.textContent)};}", IDENTITY)

        # AND A MISSING RESOURCE SHOWS ITS KEY, never the word « undefined ».
        # `i18next.t(key, {returnObjects: true})` answers the KEY AS A STRING
        # when the key is absent, so an unchecked cast yields `undefined` for
        # every field — and `undefined` on screen reads as a value, which is the
        # defect this whole block repairs, one layer down.
        removed = await page.evaluate("""()=>{
            // The engine draws the drawer from the module's own reader, so the
            // resource has to be emptied where the reader looks: i18next's
            // store. If the bundle does not expose it, say so rather than let
            // the hold below pass over a substitution that never happened.
            const store = window.__i18n?.store?.data?.fr?.translation?.common;
            if (!store || !store.servedIdentity) return false;
            delete store.servedIdentity;
            return true;
        }""")
        await page.evaluate("()=>window.__go('acq-now-idle')")
        await page.wait_for_timeout(200)
        await page.evaluate("()=>window.__go('drawer-navigation')")
        await page.wait_for_timeout(400)
        missing = await page.evaluate(
            "(selector)=>[...document.querySelector(selector).children]"
            ".map(line=>line.textContent)", IDENTITY)
        await browser.close()
    return unpublished, dirty, clean, detached, missing, removed


def main() -> None:
    global _journal
    _journal = Journal("R87 — the drawer names what the host is serving")

    unpublished, dirty, clean, detached, missing, removed = asyncio.run(read_drawer())

    # 1. THE HONEST ABSENCE. The rule suite reads a static copy, which publishes
    #    nothing — so this is the state the harness itself is always in, and it
    #    must never be a plausible number.
    check("with no host identity, the block exists at all", unpublished is not None,
          str(unpublished))
    lines = (unpublished or {}).get("lines", [])
    check("and says the identity is unavailable, with the reason",
          unpublished is not None and not unpublished["known"] and len(lines) == 3
          and lines[1] and lines[2] and lines[1] != lines[2], str(lines))
    # The defect, named as a hold: the two literals the drawer used to state.
    check("and states no version and no build sha of its own",
          not any(part in " ".join(lines) for part in ("0.98.", "build ", "à jour")),
          str(lines))

    # 2. THE PUBLISHED IDENTITY IS THE ONE SHOWN, both halves of it.
    check("a published identity is shown, branch and commit",
          dirty["known"] and dirty["lines"][1] == "branch-under-test"
          and dirty["lines"][2].startswith("0badc0de"), str(dirty["lines"]))
    check("and a dirty tree is marked",
          dirty["lines"][2] != clean[2] and len(dirty["lines"][2]) > len(clean[2]),
          f"dirty {dirty['lines'][2]!r} · clean {clean[2]!r}")
    check("while a clean one is not", clean[2] == "0badc0de", str(clean))
    check("a detached head is named as one, not shown as a branch called « HEAD »",
          detached["known"] and detached["lines"][1] not in ("HEAD", "", "0badc0de")
          and detached["lines"][1] != "branch-under-test", str(detached["lines"]))
    check("and it still names the commit", detached["lines"][2] == "0badc0de",
          str(detached["lines"]))
    check("the resource could really be emptied, so the hold below means something",
          removed, str(removed))
    check("with its words gone the block shows their KEYS, never « undefined »",
          removed and all("undefined" not in line for line in missing)
          and any("servedIdentity" in line for line in missing), str(missing))
    check("and no line of the block ever renders « undefined »",
          not any("undefined" in line for line in
                  lines + dirty["lines"] + clean + detached["lines"] + missing),
          str(missing))

    # 3. THE SERVER HALF: the served document really carries it.
    environment = {**os.environ, "TM_DESIGN_PASSWORD_HASH": password_hash()}
    server = subprocess.Popen([sys.executable, str(ROOT / "serve.py"), str(PORT)],
                              env=environment, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
    try:
        check("the design host answers", wait_for_gate())
        cookie = sign_in()
        check("and a session can be opened on it", cookie is not None)
        if cookie:
            payload = published(document(cookie))
            check("the served document publishes an identity", payload is not None,
                  str(payload))
            check("and it names a branch, a commit and the tree's state",
                  payload is not None and all(field in payload
                                              for field in ('"branch"', '"commit"', '"dirty"')),
                  str(payload))
    finally:
        server.terminate()
        server.wait(timeout=10)

    # 4. PER CALL, NOT PER BOOT — and this is where that is really proved.
    #
    #    THE FIRST VERSION OF THIS HOLD WAS VACUOUS, and it is recorded here
    #    rather than quietly repaired. It made the served tree dirty between two
    #    requests and compared the answers; run on a tree that was ALREADY dirty
    #    — which is every tree a wave is written on — both answers read
    #    `dirty: true` and the hold passed having distinguished nothing. A hold
    #    whose discriminating power depends on the environment it happens to run
    #    in is the shape this repository has now counted seventeen times.
    #
    #    So the states are CONSTRUCTED instead of borrowed: a scratch repository
    #    with a branch name and a commit this rule chose, read twice from one
    #    process with a change in between. `host_identity.served_identity()` takes the tree as an
    #    argument, which is what makes that reachable at all.
    with tempfile.TemporaryDirectory() as scratch:
        root = pathlib.Path(scratch)
        for arguments in (["init", "--initial-branch", "a-branch-this-rule-chose"],
                          ["config", "user.email", "harness@example.invalid"],
                          ["config", "user.name", "harness"]):
            subprocess.run(["git", *arguments], cwd=root, capture_output=True, check=True)
        (root / "seed.txt").write_text("seed\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "seed"], cwd=root,
                       capture_output=True, check=True)

        reader = (
            "import json, os, pathlib, sys;"
            "sys.path.insert(0, os.environ['HARNESS_SERVER_DIR']);"
            "import host_identity;"
            "root = pathlib.Path(os.environ['TM_DESIGN_ROOT']);"
            "first = host_identity.served_identity(root);"
            "pathlib.Path(os.environ['TM_DESIGN_ROOT'], 'appeared.txt')"
            ".write_text('a change the first read did not carry');"
            "second = host_identity.served_identity(root);"
            "print(json.dumps([first, second]))"
        )
        answer = subprocess.run(
            [sys.executable, "-c", reader],
            env={**os.environ, "TM_DESIGN_ROOT": str(root),
                 "HARNESS_SERVER_DIR": str(ROOT)},
            capture_output=True, text=True, timeout=60)
        check("the host can be read against a tree this rule controls",
              answer.returncode == 0, (answer.stderr or "").strip()[-200:])
        reads = json.loads(answer.stdout) if answer.returncode == 0 else [None, None]
        before, after = reads[0], reads[1]
        check("it names the branch that is checked out",
              before is not None and before["branch"] == "a-branch-this-rule-chose",
              str(before))
        check("and the commit, abbreviated",
              before is not None and 0 < len(before["commit"]) < 40
              and all(digit in "0123456789abcdef" for digit in before["commit"]),
              str(before))
        check("a clean tree is not called dirty",
              before is not None and before["dirty"] is False, str(before))
        check("and the SAME process answers dirty once the tree is",
              after is not None and after["dirty"] is True, str(after))
        check("so the two reads differ across the change — nothing was cached",
              before != after, f"{before} vs {after}")

        # A BRANCH NAME MAY LEGALLY END THE SCRIPT ELEMENT, and until this hold
        # existed nothing said so. `json.dumps` escapes `"` and the backslash and
        # nothing else that matters inside a script body; a git ref may contain
        # `<`, `>` and `/`, so a branch named to close the element left
        # `window.__servedIdentity=` as a syntax error — the drawer then said
        # « unavailable » on exactly the branch that broke it — and turned the
        # rest into live markup on the design host's own origin.
        #
        # HELD ON THE SCRIPT BODY, NOT ON THE JSON, and that distinction IS the
        # finding: the corrupted payload parses as valid JSON, because JSON
        # permits `<` and `/` inside a string. A `json.loads` here would pass.
        subprocess.run(["git", "checkout", "-q", "-b", HOSTILE_BRANCH],
                       cwd=root, capture_output=True, check=True)
        emitter = (
            "import os, pathlib, sys;"
            "sys.path.insert(0, os.environ['HARNESS_SERVER_DIR']);"
            "import host_identity;"
            "root = pathlib.Path(os.environ['TM_DESIGN_ROOT']);"
            "page = b'<html><head><title>t</title></head><body></body></html>';"
            "sys.stdout.write(host_identity.with_served_identity(page, root).decode())"
        )
        answer = subprocess.run(
            [sys.executable, "-c", emitter],
            env={**os.environ, "TM_DESIGN_ROOT": str(root),
                 "HARNESS_SERVER_DIR": str(ROOT)},
            capture_output=True, text=True, timeout=60)
        served = answer.stdout
        check("a branch name that ends a script element is escaped, not emitted",
              answer.returncode == 0 and served.lower().count("</script") == 1,
              f"{served.lower().count('</script')} script close(s) — "
              f"{served.strip()[:150]}")
        check("and its markup does not become markup",
              "<img" not in served, served.strip()[:150])
        carried = ""
        if "window.__servedIdentity=" in served:
            carried = json.loads(served.split("window.__servedIdentity=", 1)[1]
                                 .split(";</script>", 1)[0]).get("branch", "")
        check("while the escaped value still round-trips to the branch it names",
              carried == HOSTILE_BRANCH, repr(carried)[:150])

        # AND THE DETACHED CASE, ON THE HOST rather than in the drawer. The
        # drawer hold above injects `detached: true` and proves the WORDING; it
        # says nothing about whether the host can tell a detached checkout from
        # a branch. It cannot, if it asks `rev-parse --abbrev-ref HEAD`: that
        # answers the literal string `HEAD`, exit 0. Only `symbolic-ref` fails
        # on a detached head, which is what makes the two distinguishable — and
        # a detached checkout is the state the incident behind this defect was.
        subprocess.run(["git", "checkout", "-q", "--detach"],
                       cwd=root, capture_output=True, check=True)
        answer = subprocess.run(
            [sys.executable, "-c", reader],
            env={**os.environ, "TM_DESIGN_ROOT": str(root),
                 "HARNESS_SERVER_DIR": str(ROOT)},
            capture_output=True, text=True, timeout=60)
        loose = json.loads(answer.stdout)[0] if answer.returncode == 0 else None
        check("a detached checkout is reported as detached, not as a branch",
              loose is not None and loose["detached"] is True
              and loose["branch"] == "",
              str(loose))

    # 5. AND WHERE THERE IS NO REPOSITORY, IT NAMES NOTHING. This is the case
    #    the drawer's « unavailable » exists for; a value invented here would be
    #    the original defect, one layer down.
    with tempfile.TemporaryDirectory() as bare:
        reader = ("import json, os, pathlib, sys;"
                  "sys.path.insert(0, os.environ['HARNESS_SERVER_DIR']);"
                  "import host_identity;"
                  "print(json.dumps(host_identity.served_identity("
                  "pathlib.Path(os.environ['TM_DESIGN_ROOT']))))")
        answer = subprocess.run(
            [sys.executable, "-c", reader],
            env={**os.environ, "TM_DESIGN_ROOT": bare, "HARNESS_SERVER_DIR": str(ROOT)},
            capture_output=True, text=True, timeout=60)
        check("outside a repository it names nothing, rather than guessing",
              answer.returncode == 0 and json.loads(answer.stdout or "0") is None,
              (answer.stdout or answer.stderr).strip()[-200:])

    _journal.summary()


main()
