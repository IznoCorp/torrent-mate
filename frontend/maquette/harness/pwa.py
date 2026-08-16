"""The design host is installable, from the FIRST document a phone reaches.

R52 — every document the server hands out declares the manifest, the icons and
      the worker; the manifest satisfies the install criteria; the worker
      registers and answers a navigation with the network gone.

The rule exists because the prompt had never appeared on a phone, and the
reason was structural rather than a missing tag: the declarations sat on the
prototype, and the prototype is behind the session. The only document a phone
could reach before signing in was the login gate, and a browser reads the
manifest of the page in front of it — never one waiting behind a cookie.

The second half is the worker. Installability asks that a navigation still be
answered offline; a fetch handler that does nothing satisfies the letter and
fails the test. The worker here is network-first and caches ONE page, the one
that says the prototype is not available — never the prototype itself, because
a design reference that serves yesterday's copy is worse than one that is
honestly absent.
"""
import asyncio
import json
import pathlib
import sys

from playwright.async_api import async_playwright

HOST = "https://tm-design.iznogoudatall.xyz"

# The icons the shipped application serves. What this host hands out is
# compared against them: an icon identical to the app's tells a home screen
# nothing, whatever the label under it says.
APPLICATION = pathlib.Path(__file__).resolve().parents[2] / "public"

# Chrome's install criteria, as facts about the manifest.
REQUIRED_SIZES = {"192x192", "512x512"}
INSTALLABLE_DISPLAYS = {"standalone", "fullscreen", "minimal-ui"}


async def main():
    """Runs R52 and reports how many checks actually executed.

    Returns:
        0 when the host is installable, 1 otherwise.
    """
    failures = []
    executed = 0
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx = await b.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        pg = await ctx.new_page()

        # --- the gate, which is all a phone sees before signing in ----------
        await pg.goto(HOST, wait_until="load")
        declare = await pg.evaluate(
            """()=>({
              manifest: document.querySelector('link[rel="manifest"]')?.href||null,
              iosCapable: document.querySelector('meta[name="apple-mobile-web-app-capable"]')?.content||null,
              iosTitle: document.querySelector('meta[name="apple-mobile-web-app-title"]')?.content||null,
              iosIcon: document.querySelector('link[rel="apple-touch-icon"]')?.href||null,
              themeColor: document.querySelector('meta[name="theme-color"]')?.content||null})"""
        )
        for key, value in declare.items():
            executed += 1
            if not value:
                failures.append(f"R52 the login gate declares no {key}")

        # --- the manifest itself --------------------------------------------
        response = await pg.request.get(f"{HOST}/manifest.webmanifest")
        executed += 1
        if response.status != 200:
            failures.append(f"R52 the manifest answers {response.status}")
        else:
            m = json.loads(await response.text())
            sizes = {i.get("sizes") for i in m.get("icons", [])}
            checks = {
                "name": bool(m.get("name")),
                "short_name": bool(m.get("short_name")),
                "start_url": bool(m.get("start_url")),
                "display installable": m.get("display") in INSTALLABLE_DISPLAYS,
                "icons 192 and 512": REQUIRED_SIZES <= sizes,
                "a maskable icon": any(
                    "maskable" in (i.get("purpose") or "") for i in m["icons"]
                ),
            }
            for what, ok in checks.items():
                executed += 1
                if not ok:
                    failures.append(f"R52 the manifest fails: {what}")
            # Every icon must actually load — a declared icon that 404s costs
            # the prompt as surely as a missing one — and it must be THIS
            # host's icon. A name distinguishes two entries in a list; on a
            # home screen what is seen first is the picture, and two identical
            # pictures under different labels are still two identical
            # pictures. Compared byte for byte against what the app serves.
            for icon in m.get("icons", []):
                executed += 1
                r = await pg.request.get(f"{HOST}{icon['src']}")
                if r.status != 200:
                    failures.append(f"R52 icon {icon['src']} answers {r.status}")
                    continue
                executed += 1
                served = await r.body()
                expected = APPLICATION / icon["src"].lstrip("/")
                if expected.is_file() and served == expected.read_bytes():
                    failures.append(
                        f"R52 icon {icon['src']} is the app's own — nothing tells them apart"
                    )
            executed += 1
            apple = declare.get("iosIcon")
            if apple:
                r = await pg.request.get(apple)
                file = APPLICATION / apple.rsplit("/", 1)[-1]
                if r.status != 200:
                    failures.append(f"R52 the iOS icon answers {r.status}")
                elif file.is_file() and await r.body() == file.read_bytes():
                    failures.append("R52 the iOS icon is the app's own — the home screen shows no difference")

        # --- and it installs as a DIFFERENT application ----------------------
        #
        # The shipped app installs as « TorrentMate ». A prototype that installs
        # under the same name, or under an abbreviation of it, puts two entries
        # on one home screen that nobody can tell apart — and the one that gets
        # opened is whichever was tapped last. The name has to be distinct
        # everywhere the system reads one: the manifest's `name`, its
        # `short_name` (the home-screen label on Android), and the iOS meta
        # (the label there, because Safari reads neither manifest field).
        #
        # `id` is checked as well. Left out, the identity defaults to
        # `start_url` — « / » on both — so nothing but the origin separates
        # them, and an origin is not something a home screen shows.
        APP_NAME = "TorrentMate"
        if response.status == 200:
            identity = {
                "manifest name": m.get("name"),
                "manifest short_name": m.get("short_name"),
                "iOS title": declare.get("iosTitle"),
            }
            for what, value in identity.items():
                executed += 1
                if value == APP_NAME or value is None:
                    failures.append(
                        f"R52 the {what} does not tell this apart from the app: {value!r}"
                    )
                elif "design" not in (value or "").lower():
                    failures.append(f"R52 the {what} does not say it is the design: {value!r}")
            executed += 1
            if not m.get("id"):
                failures.append("R52 the manifest declares no id — identity falls back to start_url")

        # --- the worker registers and takes control --------------------------
        # Bounded on purpose. `serviceWorker.ready` never rejects — a document
        # that registers no worker leaves it pending forever, so an unbounded
        # await turns the absence of a worker into a hang instead of a finding.
        ready = await pg.evaluate(
            """async()=>Promise.race([
                 navigator.serviceWorker.ready.then(()=>true),
                 new Promise(r=>setTimeout(()=>r(false), 8000))])"""
        )
        executed += 1
        if not ready:
            failures.append("R52 the service worker never became ready")

        # A worker does not control the document that registered it. Without
        # this reload the next navigation goes straight to the network, and
        # measuring it measures the network rather than the worker.
        await pg.reload(wait_until="load")
        controlling = await pg.evaluate("()=>navigator.serviceWorker.controller!==null")
        executed += 1
        if not controlling:
            failures.append("R52 the worker does not control the page after a reload")

        # --- and the fallback a navigation would get is really there ---------
        #
        # Measured through the CACHE rather than by cutting the network:
        # `set_offline` does not reach requests a service worker makes in
        # Chromium, so navigating with it on measures the network coming back,
        # not the worker. What can be established here is the substantive
        # fact — the worker installed, and the page it would answer with is in
        # its cache and reads correctly. Whether Chrome then offers to install
        # is Chrome's judgement, and only a real phone settles it.
        fallback = await pg.evaluate(
            """async()=>{const c=await caches.open("tm-design-offline");
                 const r=await c.match("/hors-ligne.html");
                 return r ? (r.ok ? await r.text() : `status ${r.status}`)
                          : "absent from the cache";}"""
        )
        executed += 1
        if "Hors ligne" not in fallback:
            failures.append(f"R52 the offline fallback is not usable: {fallback[:90]}")
        await b.close()

    for line in failures:
        print(f"  FAIL {line}")
    print(f"\n{executed} checks EXECUTED · {len(failures)} failures")
    print(
        "VERDICT:",
        "installable from the first document"
        if not failures
        else "the phone has nothing to install",
    )
    return 1 if failures else 0


sys.exit(asyncio.run(main()))
