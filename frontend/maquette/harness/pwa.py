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

HOTE = "https://tm-design.iznogoudatall.xyz"

# The icons the shipped application serves. What this host hands out is
# compared against them: an icon identical to the app's tells a home screen
# nothing, whatever the label under it says.
APPLICATION = pathlib.Path(__file__).resolve().parents[2] / "public"

# Chrome's install criteria, as facts about the manifest.
TAILLES_REQUISES = {"192x192", "512x512"}
AFFICHAGES_INSTALLABLES = {"standalone", "fullscreen", "minimal-ui"}


async def main():
    """Runs R52 and reports how many checks actually executed.

    Returns:
        0 when the host is installable, 1 otherwise.
    """
    echecs = []
    executees = 0
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
        await pg.goto(HOTE, wait_until="load")
        declare = await pg.evaluate(
            """()=>({
              manifeste: document.querySelector('link[rel="manifest"]')?.href||null,
              iosCapable: document.querySelector('meta[name="apple-mobile-web-app-capable"]')?.content||null,
              iosTitre: document.querySelector('meta[name="apple-mobile-web-app-title"]')?.content||null,
              iconeIos: document.querySelector('link[rel="apple-touch-icon"]')?.href||null,
              couleur: document.querySelector('meta[name="theme-color"]')?.content||null})"""
        )
        for cle, valeur in declare.items():
            executees += 1
            if not valeur:
                echecs.append(f"R52 the login gate declares no {cle}")

        # --- the manifest itself --------------------------------------------
        reponse = await pg.request.get(f"{HOTE}/manifest.webmanifest")
        executees += 1
        if reponse.status != 200:
            echecs.append(f"R52 the manifest answers {reponse.status}")
        else:
            m = json.loads(await reponse.text())
            tailles = {i.get("sizes") for i in m.get("icons", [])}
            controles = {
                "name": bool(m.get("name")),
                "short_name": bool(m.get("short_name")),
                "start_url": bool(m.get("start_url")),
                "display installable": m.get("display") in AFFICHAGES_INSTALLABLES,
                "icons 192 and 512": TAILLES_REQUISES <= tailles,
                "a maskable icon": any(
                    "maskable" in (i.get("purpose") or "") for i in m["icons"]
                ),
            }
            for quoi, bon in controles.items():
                executees += 1
                if not bon:
                    echecs.append(f"R52 the manifest fails: {quoi}")
            # Every icon must actually load — a declared icon that 404s costs
            # the prompt as surely as a missing one — and it must be THIS
            # host's icon. A name distinguishes two entries in a list; on a
            # home screen what is seen first is the picture, and two identical
            # pictures under different labels are still two identical
            # pictures. Compared byte for byte against what the app serves.
            for icone in m.get("icons", []):
                executees += 1
                r = await pg.request.get(f"{HOTE}{icone['src']}")
                if r.status != 200:
                    echecs.append(f"R52 icon {icone['src']} answers {r.status}")
                    continue
                executees += 1
                servi = await r.body()
                attendu = APPLICATION / icone["src"].lstrip("/")
                if attendu.is_file() and servi == attendu.read_bytes():
                    echecs.append(
                        f"R52 icon {icone['src']} is the app's own — nothing tells them apart"
                    )
            executees += 1
            apple = declare.get("iconeIos")
            if apple:
                r = await pg.request.get(apple)
                fichier = APPLICATION / apple.rsplit("/", 1)[-1]
                if r.status != 200:
                    echecs.append(f"R52 the iOS icon answers {r.status}")
                elif fichier.is_file() and await r.body() == fichier.read_bytes():
                    echecs.append("R52 the iOS icon is the app's own — the home screen shows no difference")

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
        NOM_APP = "TorrentMate"
        if reponse.status == 200:
            identite = {
                "manifest name": m.get("name"),
                "manifest short_name": m.get("short_name"),
                "iOS title": declare.get("iosTitre"),
            }
            for quoi, valeur in identite.items():
                executees += 1
                if valeur == NOM_APP or valeur is None:
                    echecs.append(
                        f"R52 the {quoi} does not tell this apart from the app: {valeur!r}"
                    )
                elif "design" not in (valeur or "").lower():
                    echecs.append(f"R52 the {quoi} does not say it is the design: {valeur!r}")
            executees += 1
            if not m.get("id"):
                echecs.append("R52 the manifest declares no id — identity falls back to start_url")

        # --- the worker registers and takes control --------------------------
        # Bounded on purpose. `serviceWorker.ready` never rejects — a document
        # that registers no worker leaves it pending forever, so an unbounded
        # await turns the absence of a worker into a hang instead of a finding.
        pris = await pg.evaluate(
            """async()=>Promise.race([
                 navigator.serviceWorker.ready.then(()=>true),
                 new Promise(r=>setTimeout(()=>r(false), 8000))])"""
        )
        executees += 1
        if not pris:
            echecs.append("R52 the service worker never became ready")

        # A worker does not control the document that registered it. Without
        # this reload the next navigation goes straight to the network, and
        # measuring it measures the network rather than the worker.
        await pg.reload(wait_until="load")
        controle = await pg.evaluate("()=>navigator.serviceWorker.controller!==null")
        executees += 1
        if not controle:
            echecs.append("R52 the worker does not control the page after a reload")

        # --- and the fallback a navigation would get is really there ---------
        #
        # Measured through the CACHE rather than by cutting the network:
        # `set_offline` does not reach requests a service worker makes in
        # Chromium, so navigating with it on measures the network coming back,
        # not the worker. What can be established here is the substantive
        # fact — the worker installed, and the page it would answer with is in
        # its cache and reads correctly. Whether Chrome then offers to install
        # is Chrome's judgement, and only a real phone settles it.
        replie = await pg.evaluate(
            """async()=>{const c=await caches.open("tm-design-offline");
                 const r=await c.match("/hors-ligne.html");
                 return r ? (r.ok ? await r.text() : `status ${r.status}`)
                          : "absent from the cache";}"""
        )
        executees += 1
        if "Hors ligne" not in replie:
            echecs.append(f"R52 the offline fallback is not usable: {replie[:90]}")
        await b.close()

    for ligne in echecs:
        print(f"  FAIL {ligne}")
    print(f"\n{executees} checks EXECUTED · {len(echecs)} failures")
    print(
        "VERDICT:",
        "installable from the first document"
        if not echecs
        else "the phone has nothing to install",
    )
    return 1 if echecs else 0


sys.exit(asyncio.run(main()))
