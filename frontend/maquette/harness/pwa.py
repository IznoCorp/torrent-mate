"""The design host is installable, and the shell it caches really opens offline.

R52 — every document the server hands out declares the manifest, the icons and
      the worker; the manifest satisfies the install criteria; the worker
      registers and answers a navigation with the network gone.
R108 — P9: every entry point the platform offers an installed application is
      declared, and the address each one names really behaves. Q4, answered by
      the operator on 2026-08-30: all three.
R105 — P7: the application opens and reads with the network gone. The shell is
      precached, the document is answered from the cache, and a named state
      renders — measured against a server that has actually STOPPED, for the
      reason written at the top of `offline_shell()`.

The rule exists because the prompt had never appeared on a phone, and the
reason was structural rather than a missing tag: the declarations sat on the
prototype, and the prototype is behind the session. The only document a phone
could reach before signing in was the login gate, and a browser reads the
manifest of the page in front of it — never one waiting behind a cookie.

The second half is the worker. Installability asks that a navigation still be
answered offline; a fetch handler that does nothing satisfies the letter and
fails the test.

WHAT THE WORKER NOW DOES, AND WHAT IT USED TO. It cached exactly one page — the
notice saying the prototype was not available — and never the prototype, because
a design reference that serves yesterday's copy is worse than one honestly
absent. Since L11 it precaches the SHELL, and the reason that is safe is written
in `design/sw.js`: a navigation goes to the network FIRST and falls back to the
cache, so whoever can reach the host sees today's prototype, and the update
discipline reloads once when the served build stops matching the running one.
"""
import asyncio
import json
import pathlib
import sys

from playwright.async_api import async_playwright
from server import start_server

# The built copy the harness serves, and the one R105 raises its own server on.
SERVED = pathlib.Path("/tmp/tm-refonte")

HOST = "https://tm-design.iznogoudatall.xyz"

# The icons the shipped application serves. What this host hands out is
# compared against them: an icon identical to the app's tells a home screen
# nothing, whatever the label under it says.
APPLICATION = pathlib.Path(__file__).resolve().parents[2] / "public"

# Chrome's install criteria, as facts about the manifest.
REQUIRED_SIZES = {"192x192", "512x512"}
INSTALLABLE_DISPLAYS = {"standalone", "fullscreen", "minimal-ui"}


async def share_target_lands(browser):
    """R108's other half — the address `share_target` names really pre-fills.

    A DECLARATION AND A BEHAVIOUR ARE TWO THINGS. The manifest saying a share
    lands on `/add?q=` is checked against the manifest; whether `/add?q=` then
    puts the shared text in front of the operator is checked here, and nothing
    else in this file would notice if it stopped.

    It runs against the served copy rather than the live host, because that is
    where every other behavioural rule runs and because the design host would
    need a session for it.

    Args:
        browser: A launched Playwright browser.

    Returns:
        The `(executed, failures)` pair.
    """
    executed = 0
    failures = []
    context = await browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True)
    page = await context.new_page()
    shared = "Silo"
    with start_server(SERVED) as port:
        await page.goto(f"http://127.0.0.1:{port}/add?q={shared}", wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        await page.evaluate("()=>document.querySelector('#toastx')?.click()")
        await page.wait_for_timeout(600)
        executed += 1
        # THE FIELD, not the address. An address carrying `?q=` proves only that
        # the browser kept the query string; what a share is FOR is the text
        # being in front of the operator when the screen opens.
        filled = await page.evaluate(
            """()=>{const fields=[...document.querySelectorAll("input")];
                 return fields.map((field)=>field.value).filter(Boolean);}""")
        if shared not in filled:
            failures.append(
                f"R108 a share lands on /add without pre-filling it: {filled[:4]}")
    await context.close()
    return executed, failures


async def offline_shell(browser):
    """P7 — the application opens and reads with the network gone.

    WHY IT RAISES ITS OWN SERVER AND THEN KILLS IT, rather than using
    `context.set_offline(True)` as the property was first written. Chromium's
    offline emulation does not reach the requests a SERVICE WORKER makes: with
    it on, the worker's own network-first `fetch` still succeeds, the navigation
    is answered by the server, and the rule passes without the cache ever being
    touched. It would be green for the wrong reason, which is the one outcome
    an instrument must not have. The same paragraph is already written at R52's
    last hold, where it was learned.

    Stopping a real server is the only reading with nothing behind it. It is a
    SCRATCH server on a port the kernel picks, never the shared host on 8899:
    the suite runs eight rules at a time and killing what the others are reading
    would fail seven rules for a reason having nothing to do with any of them.

    Args:
        browser: A launched Playwright browser.

    Returns:
        The `(executed, failures)` pair, folded into R52's own totals.
    """
    executed = 0
    failures = []
    context = await browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True)
    page = await context.new_page()

    # THE BROWSER'S OWN HTTP CACHE IS TURNED OFF, and this is the hold's whole
    # validity. Found by mutation: with the document deliberately left OUT of
    # the worker's precache, this rule reported no violation — the page had
    # been loaded twice, so Chrome's disk cache answered the reload after the
    # server was gone, and « the shell opened offline » was true of the wrong
    # cache. An instrument that cannot tell which cache answered is measuring
    # the browser, not the worker.
    session = await context.new_cdp_session(page)
    await session.send("Network.setCacheDisabled", {"cacheDisabled": True})

    with start_server(SERVED) as port:
        origin = f"http://127.0.0.1:{port}"
        await page.goto(f"{origin}/", wait_until="load")
        # Bounded, for the reason R52 states: `serviceWorker.ready` never
        # rejects, so an unbounded await turns « no worker » into a hang.
        ready = await page.evaluate(
            """async()=>Promise.race([
                 navigator.serviceWorker.ready.then(()=>true),
                 new Promise(r=>setTimeout(()=>r(false), 8000))])""")
        executed += 1
        if not ready:
            failures.append("R105 no worker installed on the served copy")
            await context.close()
            return executed, failures
        # A worker does not control the document that registered it.
        await page.reload(wait_until="load")
        executed += 1
        if not await page.evaluate("()=>navigator.serviceWorker.controller!==null"):
            failures.append("R105 the worker does not control the page after a reload")
            await context.close()
            return executed, failures

        # THE SHELL IS COMPLETED, AND THE COMPLETION IS AWAITED — never slept
        # on. The application asks for this at boot too; asking again here is
        # idempotent (`cache.add` over an entry that is already there is the
        # same entry) and it is what makes the moment the shell became whole a
        # fact this rule OBSERVED rather than one it hoped had happened by now.
        report = await page.evaluate(
            """async()=>new Promise((resolve)=>{
                 const channel = new MessageChannel();
                 channel.port1.onmessage = (event)=>resolve(event.data);
                 navigator.serviceWorker.controller.postMessage(
                   "cache-shell", [channel.port2]);
                 setTimeout(()=>resolve({missing:["the worker never answered"]}), 8000);
               })""")
        executed += 1
        if report["missing"]:
            failures.append(
                f"R105 the shell could not be completed: {report['missing'][:4]}")
            await context.close()
            return executed, failures

        executed += 1
        held = await page.evaluate(
            """async()=>{const names=await caches.keys();
                 const shell=names.find(n=>n.startsWith("tm-shell-"));
                 if(!shell) return [];
                 const c=await caches.open(shell);
                 return (await c.keys()).map(r=>new URL(r.url).pathname);}""")
        if not any(path.startswith("/vite/") for path in held):
            failures.append(f"R105 the shell holds no bundle: {held[:6]}")
            await context.close()
            return executed, failures

        executed += 1
        # THE DOCUMENT, HELD UNDER ITS OWN KEY, and held DIRECTLY rather than
        # inferred from the reload below succeeding. Found by mutation: with the
        # document deliberately dropped from the precache, the page still opened
        # offline and this rule still passed — because on the harness host
        # `/offline.html` has no file behind it and the fallback handler folds
        # it onto the document, so the worker's LAST-RESORT entry is a full copy
        # of the prototype. The consequence held while the mechanism was gone,
        # which is the difference between a rule and a coincidence.
        if "/" not in held:
            failures.append(f"R105 the shell holds no document: {held[:6]}")
            await context.close()
            return executed, failures

    # THE SERVER IS GONE from here. Any answer the page now gets came from the
    # worker's cache and from nowhere else.
    executed += 1
    # THROUGH PLAYWRIGHT'S OWN REQUEST CONTEXT, never `fetch` from inside the
    # page. The mock layer has replaced the page's `fetch` and ANSWERS every
    # same-origin path — 404 « no mock route » for one it does not know — so an
    # in-page probe would come back with a Response instead of throwing, and
    # this hold would read « the host is still answering » forever. Measured:
    # that is exactly what it did on the first run.
    try:
        await page.request.get(f"{origin}/build.json")
        still_up = True
    except Exception:
        still_up = False
    if still_up:
        failures.append(
            "R105 the host is still answering — this reading would prove nothing")
        await context.close()
        return executed, failures

    executed += 1
    # A FAILED NAVIGATION IS A FINDING, NOT A CRASH. Found by mutation: with the
    # cache fallback removed from the worker, `page.reload` raised
    # `net::ERR_FAILED` and this rule died with a traceback. The suite counts
    # that as a failure either way, but a rule that cannot say WHICH defect it
    # found sends its reader to a stack trace instead of to the worker.
    try:
        await page.reload(wait_until="load")
    except Exception as refused:
        failures.append(
            f"R105 the shell did not open offline — the navigation failed: "
            f"{str(refused).splitlines()[0][:80]}")
        await context.close()
        return executed, failures

    executed += 1
    # AND IT WAS THE WORKER THAT ANSWERED IT. `workerStart` is set only when a
    # service worker intercepted the navigation, so this separates « something
    # answered » from « the thing this lot built answered » — the second reader
    # the mutation above proved was needed.
    from_worker = await page.evaluate(
        """()=>{const n=performance.getEntriesByType("navigation")[0];
             return n ? n.workerStart > 0 : false;}""")
    if not from_worker:
        failures.append(
            "R105 the document offline came from something other than the worker")
        await context.close()
        return executed, failures

    executed += 1
    # THE DOCUMENT CAME BACK AT ALL. A failed navigation leaves the browser's
    # own error page, which has no `#view` and no state driver.
    driver = await page.evaluate("()=>typeof window.__go==='function'")
    if not driver:
        failures.append("R105 the shell did not open offline — no state driver")
        await context.close()
        return executed, failures

    executed += 1
    # AND IT READS. « Opens » is not the property: a shell that renders an empty
    # frame is a shell nobody can use. A named state is driven and the view must
    # carry text, exactly as `states.py` reads it.
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    # A state on a PAGE the shell owns, and one whose data comes from the mock
    # layer — so what is being read is the shell rendering, never a cached
    # response standing in for it.
    await page.evaluate("(id)=>window.__go(id)", "lib-grid")
    await page.wait_for_timeout(400)
    rendered = await page.evaluate(
        """()=>{const v=document.querySelector('#view');
             return v ? (v.innerText||'').trim().length : 0;}""")
    if rendered < 20:
        failures.append(
            f"R105 a named state renders nothing offline — {rendered} characters")

    executed += 1
    # AND THE MOCKED CONTRACT STILL ANSWERS, which is what makes the shell
    # READABLE rather than merely present: the layer replaces `fetch` in the
    # page, so the data a surface draws never depended on the network at all.
    # This hold is what separates « the document loaded » from « the application
    # works », and it is the half a document-only reading would miss.
    answered = await page.evaluate(
        """async()=>{const r=await fetch("/api/library/items");
             return r.status;}""")
    if answered != 200:
        failures.append(f"R105 the contract does not answer offline — {answered}")

    await context.close()
    return executed, failures


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

            # --- R108 (P9) — the entry points, and what each one promises ----
            #
            # NO RULE CAN MAKE AN OPERATING SYSTEM SHARE INTO AN APPLICATION,
            # and this does not pretend to. What is proved is the PAIR: the
            # manifest declares it, and the address it names behaves. The half
            # that needs a device is exercised on a device and written down with
            # its date, like the oracle's certification.
            share = m.get("share_target") or {}
            executed += 1
            if share.get("action") != "/add":
                failures.append(
                    f"R108 share_target lands nowhere useful: {share.get('action')!r}")
            executed += 1
            # ALL THREE PARAMETERS ONTO ONE NAME. A share arrives as a title
            # from one application, as text from another and as a URL from a
            # third; mapping only one of them makes the entry point work for
            # whichever application the author happened to test with.
            parameters = share.get("params") or {}
            mapped = {parameters.get(name) for name in ("title", "text", "url")}
            if mapped != {"q"}:
                failures.append(
                    f"R108 share_target does not carry every shape onto q: {parameters!r}")
            executed += 1
            if (m.get("launch_handler") or {}).get("client_mode") != "navigate-existing":
                failures.append(
                    "R108 launch_handler would open a second window rather than reuse one")
            executed += 1
            if m.get("handle_links") != "preferred":
                failures.append(
                    f"R108 handle_links is not declared: {m.get('handle_links')!r}")
            executed += 1
            # DECLINED IN WRITING, AND STILL DECLINED. A permission prompt with
            # nothing to send trains the operator to refuse it, and a browser
            # remembers that refusal far longer than a wave. The consumer is
            # §18's ratio alert (L16), and this hold is what keeps the decision
            # from being reversed by accident rather than on purpose.
            if "gcm_sender_id" in m or "push" in json.dumps(m).lower():
                failures.append(
                    "R108 the manifest declares push, which L11 declined in writing")

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

        # --- and the shell a navigation would fall back to is really there ---
        #
        # Measured through the CACHE and not by cutting the network, on THIS
        # host: `set_offline` does not reach the requests a service worker makes
        # in Chromium, so navigating with it on measures the network coming
        # back rather than the worker. R105 below settles the substantive
        # question the honest way — against a server that has stopped — and what
        # is established here is that the LIVE design host's own worker holds
        # the shell. Whether Chrome then offers to install is Chrome's
        # judgement, and only a real phone settles that.
        cached = await pg.evaluate(
            """async()=>{const names=await caches.keys();
                 const shell=names.find(n=>n.startsWith("tm-shell-"));
                 if(!shell) return {cache:null, held:[]};
                 const c=await caches.open(shell);
                 return {cache:shell,
                         held:(await c.keys()).map(r=>new URL(r.url).pathname)};}"""
        )
        executed += 1
        if not cached["cache"]:
            failures.append("R52 no shell cache exists — the worker precached nothing")
        else:
            # WHAT THE GATE CAN HONESTLY PROMISE, and it is not the document.
            # This runs unauthenticated, against the SIGN-IN GATE — the only
            # document a phone reaches before signing in, and therefore the only
            # one a worker can install from. There, `/` and `/vite/*` both
            # answer 401: the prototype is what the password protects. So the
            # gate's shell cache holds the manifest, the icons and the offline
            # notice, and nothing else CAN be in it.
            #
            # The document and the bundles are R105's, where the application is
            # actually running and everything is reachable. Holding them here
            # would be holding the host to something its own auth model forbids.
            executed += 1
            # The notice is what an unsigned visitor gets with the network gone,
            # and it is the one page this half of the worker exists to keep.
            if "/offline.html" not in cached["held"]:
                failures.append(
                    f"R52 the gate cached no offline notice: {cached['held'][:6]}")
            executed += 1
            # NOTHING UNDER `/api/`, ever. A worker answering the contract from
            # disk would make the interface say what the operator's machine had
            # stopped saying — §8 read from the wrong end.
            api = [p for p in cached["held"] if p.startswith("/api/")]
            if api:
                failures.append(f"R52 the shell cache holds server state: {api[:4]}")

        # --- R108 (P9) — and the address a share names really behaves --------
        share_executed, share_failures = await share_target_lands(b)
        executed += share_executed
        failures.extend(share_failures)

        # --- R105 (P7) — and it really opens with the network gone -----------
        offline_executed, offline_failures = await offline_shell(b)
        executed += offline_executed
        failures.extend(offline_failures)
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


# UNDER A GUARD so the holds above can be exercised one at a time while they are
# being written. Importing this file used to run the whole rule and then exit
# the interpreter, which meant the only way to try a single hold was to run all
# thirty-four against the live design host.
if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
