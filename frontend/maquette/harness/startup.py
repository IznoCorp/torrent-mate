"""R53 — the startup screen, and the wait it covers.

Signing in navigates to a document of several megabytes. Two waits follow one
another and both used to be blank:

  1. between the tap on « Se connecter » and the new document's first frame,
     during which the browser still shows the gate;
  2. between that first frame and the interface being rendered.

The first belongs to the gate the server builds, the second to the document
itself. This script proves both are covered by the SAME screen — extracted from
the prototype, never retyped, the rule the login gate already obeys — and that
the screen is gone the moment there is an interface behind it.

Position in source order is a correctness property here, not a detail: a
browser paints what it has parsed, so a screen declared after the artwork would
appear only once the wait it exists to cover is over.

What the cold-load checks below prove is the state of the DOCUMENT — the screen
is there, visible, from the instant it enters it, and gone once the interface
exists. Not the state of a painted frame: served locally, this document is about
a megabyte and a half and arrives in one burst, so the screen is parsed and then
taken off before the browser gets a single rendering opportunity. Its visible
window closes near 110 ms and the first paint lands near 290 ms — no frame here
carries it, and no probe can invent one. A guarantee about what reaches the
SCREEN needs a load slow enough to paint during, that is a throttled-network
profile in the driver: a separate rule, and an open decision for the operator.
"""
import asyncio
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

from common import Journal
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 8713  # never 8710 / 8711: the reverse proxy routes production and staging there

_journal = None


class EarlyExit(Exception):
    """Ends the gate checks when the screen they measure is not there at all."""


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


def prototype_excerpt(marker):
    """Returns the prototype text between a pair of `login:<marker>` markers."""
    # THE SHELL DOCUMENT, not the fragment: the startup screen is application
    # SHELL markup, and it moved to `index.html` when the fragment stopped
    # carrying a program. The fragment still holds the STYLE the screen wears,
    # which is a different question and a different marker.
    source = (ROOT / "design" / "index.html").read_text()
    start = source.find(f"login:{marker}:start")
    end = source.find(f"login:{marker}:end")
    if start < 0 or end < 0:
        sys.exit(f"login:{marker} markers absent from the prototype")
    return source[source.index("\n", start) + 1 : source.rindex("\n", start, end) + 1]


def normalize(text):
    """Collapses whitespace so two renderings of the same markup compare equal."""
    return re.sub(r"\s+", " ", text).strip()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        await pg.evaluate("()=>document.querySelector('#toastx').click()")

        global _journal
        _journal = Journal("R53 — the startup screen")

        # 1. Declared first, so it is painted first. Measured on the SOURCE,
        #    because that is what parse order follows; the DOM would answer the
        #    same question only by accident.
        source = (ROOT / "design" / "index.html").read_text()
        body = source[source.find('<div class="device"'):]
        splash_rank = body.find('id="splash"')
        # Each landmark is looked up BY NAME and the misses are named: a
        # `find()` that returns -1 for all three used to reach `min()` over an
        # empty generator and raise, which reports « the harness is broken »
        # about a document that simply moved. The markup left the fragment
        # once; it can leave this file too.
        landmarks = {"<header": body.find("<header"),
                     'id="port"': body.find('id="port"'),
                     'id="login"': body.find('id="login"')}
        absent = sorted(name for name, at in landmarks.items() if at <= 0)
        check("the frame's landmarks are all in the document read",
              not absent and splash_rank > 0,
              f"absent: {absent}" if absent else f"splash at {splash_rank}")
        first_other = min([at for at in landmarks.values() if at > 0], default=-1)
        check("declared before everything else in the frame", 0 < splash_rank < first_other,
                 f"splash at {splash_rank}, first other element at {first_other}")

        # 2. It covers the frame, and it says what is happening.
        await pg.evaluate("()=>window.__go('demarrage')")
        await pg.wait_for_timeout(250)
        measure = await pg.evaluate("""()=>{
          const s=document.querySelector('#splash'), d=document.querySelector('#device');
          const rs=s.getBoundingClientRect(), rd=d.getBoundingClientRect();
          const cs=getComputedStyle(s);
          const underneath=document.elementFromPoint(rd.x+rd.width/2, rd.y+rd.height/2);
          return {covers: Math.abs(rs.width-rd.width)<1 && Math.abs(rs.height-rd.height)<1,
                  visible: cs.display!=='none' && cs.opacity!=='0',
                  brand: !!s.querySelector('.brandbig'),
                  progress: !!s.querySelector('[role=progressbar]'),
                  animation: getComputedStyle(s.querySelector('.splashbar i')).animationName,
                  text: (s.textContent||'').replace(/\\s+/g,' ').trim(),
                  noControl: s.querySelectorAll('button,a,input').length,
                  inFront: !!(underneath && underneath.closest('#splash'))};}""")
        check("covers the whole frame", measure["covers"] and measure["visible"], str(measure["covers"]))
        check("nothing of the interface comes in front", measure["inFront"])
        check("carries the brand", measure["brand"])
        check("carries an animated progress",
                 measure["progress"] and measure["animation"] not in ("none", ""), measure["animation"])

        # The bar FILLS over the five seconds a cold load is budgeted, rather
        # than shuttling back and forth: a shuttle answers « how much longer »
        # with nothing, and reads the same at one second and at ten.
        fill = await pg.evaluate("""()=>{
          const i = document.querySelector('#splash .splashbar i');
          const cs = getComputedStyle(i);
          return {duration: cs.animationDuration, direction: cs.animationDirection,
                  fill: cs.animationFillMode, iterations: cs.animationIterationCount};}""")
        check("the bar fills over 5 s, exactly once",
                 fill["duration"] == "5s" and fill["iterations"] == "1",
              str(fill))

        # Measured while it runs: from nothing to full, monotonically. The
        # harness freezes animations for its own measurements, so this one asks
        # for them back.
        widths = await pg.evaluate("""async()=>{
          document.documentElement.classList.remove('measuring');
          const i = document.querySelector('#splash .splashbar i');
          i.style.animation = 'none'; void i.offsetWidth; i.style.animation = '';
          const track = i.parentElement.getBoundingClientRect().width;
          const samples = [];
          for (let n = 0; n < 6; n++) {
            samples.push(Math.round(i.getBoundingClientRect().width / track * 100));
            await new Promise(r => setTimeout(r, 500));
          }
          return samples;}""")
        check("it starts from zero", widths[0] <= 5, str(widths))
        check("and only ever grows",
                 all(b >= a for a, b in zip(widths, widths[1:])), str(widths))
        check("halfway through it is halfway along",
                 40 <= widths[5] <= 60, f"{widths[5]} % at 2.5 s")
        await pg.evaluate("()=>document.documentElement.classList.add('measuring')")
        check("says what is happening", len(measure["text"]) > 20, measure["text"][:60])
        check("offers no control", measure["noControl"] == 0,
                 f"{measure['noControl']} control(s)")

        # 3. Gone everywhere else. A cover left behind is the one failure this
        #    screen can cause on its own.
        states = await pg.evaluate("()=>window.__states()")
        remaining = []
        for state_ in states:
            if state_ == "demarrage":
                continue
            await pg.evaluate("(i)=>window.__go(i)", state_)
            await pg.wait_for_timeout(60)
            if await pg.evaluate("()=>getComputedStyle(document.querySelector('#splash')).display!=='none'"):
                remaining.append(state_)
        check(f"absent from the {len(states) - 1} other states", not remaining, ", ".join(remaining))

        # 4. Once the document has loaded there is nothing left to cover, so the
        #    screen is gone. This check has been wrong in BOTH directions: it
        #    first asserted the current behaviour — a screen that flashed for one
        #    frame — and called that conformity; then it demanded a floor, which
        #    made the bar play a second time in a document that was already
        #    rendered. What it asserts now is what the screen is FOR.
        page2 = await ctx.new_page()
        await page2.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        await page2.wait_for_timeout(400)
        check("gone once the document has loaded — it covers nothing any more",
                 await page2.evaluate(
                     "()=>getComputedStyle(document.querySelector('#splash')).display==='none'"))
        await page2.close()

        # 5. The gate the server builds shows the SAME screen, and reveals it on
        #    submit — the wait the browser spends fetching the document.
        server = subprocess.Popen(
            [sys.executable, str(ROOT / "serve.py"), str(PORT)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            gate = ""
            for _ in range(50):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2) as r:
                        gate = r.read().decode()
                    break
                except urllib.error.HTTPError as err:  # 401 carries the gate
                    gate = err.read().decode()
                    break
                except OSError:
                    time.sleep(0.1)
            check("the gate answers", bool(gate))
            check("the gate carries the startup screen", 'id="splash"' in gate)
            check("it arrives there hidden", 'id="splash" hidden' in gate)
            expected = normalize(prototype_excerpt("splash").replace(
                ' id="splash"', ' id="splash" hidden', 1))
            check("extracted from the prototype, never retyped", expected and expected in normalize(gate))
            check("the gate carries the screen's style", ".splashbar" in gate)

            page3 = await ctx.new_page()
            await page3.goto(f"http://127.0.0.1:{PORT}/", wait_until="load")
            # Without the screen there is nothing to measure, and measuring
            # anyway raises instead of naming the defect. A crash is a failure
            # nobody can read.
            if not await page3.evaluate("()=>!!document.querySelector('#splash')"):
                check("hidden until the form is submitted", False, "no screen in the gate")
                check("appears on submit", False, "no screen in the gate")
                check("and replaces the form", False, "no screen in the gate")
                await page3.close()
                raise EarlyExit
            before = await page3.evaluate(
                "()=>getComputedStyle(document.querySelector('#splash')).display")
            check("hidden until the form is submitted", before == "none", before)
            # Submitting navigates away, so the state to measure is the one at
            # the instant of the submit, not afterwards. A second listener
            # registered after the gate's own runs after it, and sessionStorage
            # carries what it saw across the navigation.
            await page3.evaluate("""()=>document.querySelector('#loginform')
              .addEventListener('submit', () => sessionStorage.setItem('__startup',
                JSON.stringify({
                  splash: getComputedStyle(document.querySelector('#splash')).display,
                  login: getComputedStyle(document.querySelector('#login')).display})))""")
            await page3.fill('input[name="username"]', "quelqu-un")
            await page3.fill('input[name="password"]', "quelque-chose")
            await page3.click(".loginsubmit")
            await page3.wait_for_timeout(500)
            after = await page3.evaluate(
                "()=>JSON.parse(sessionStorage.getItem('__startup') || 'null')") or {}
            check("appears on submit", after.get("splash", "none") != "none", str(after))
            check("and replaces the form", after.get("login") == "none", str(after))
            await page3.close()
        except EarlyExit:
            pass
        finally:
            server.terminate()
            server.wait(timeout=5)

        # ── THE COLD LOAD, the only one an operator ever sees ──────────────
        # The screen covers ONE wait: the gap between asking for the application
        # and having an interface. It spans two pages: the gate paints the
        # screen on submit, the new document paints it again from its own
        # markup, and the operator sees one continuous screen across a
        # navigation.
        #
        # Held on a TIMER here, the bar filled once while the document
        # downloaded and then restarted from zero in a document that was already
        # rendered. It was reported as loading twice, and it was. What is
        # asserted below is that the screen is up from the moment it enters the
        # document and comes off when the interface is there — not after a fixed
        # delay, which is what a rule of mine demanded and what put the second
        # bar on screen.
        #
        # The observation is taken from INSIDE the page, by a script injected
        # before any script of the document runs, and the clock is the
        # document's own — it starts when the navigation does. Asking from the
        # outside cannot answer this question any more: the document weighs
        # about a megabyte and a half, its artwork living in files beside it,
        # and it parses fast enough that the whole life of the screen — parsed,
        # then taken off by the line that ends the document — can be shorter
        # than any period a driver samples at, and shorter than the gap between
        # two rendering opportunities as well. A window that falls between two
        # readings looks exactly like a screen that never appeared, and that is
        # a verdict on the reading, not on the interface.
        #
        # So the record is made of the moments themselves, not of a period: the
        # instant the screen enters the document, every change of its state
        # afterwards, and one reading per animation frame on top of that. The
        # first two are what a fast document needs; the frames are what proves
        # the screen does not come back later.
        #
        # What this rule asserts is therefore the state of the DOCUMENT, and it
        # is named for that. Served locally, a megabyte and a half arrives in one
        # burst: the screen is parsed, then taken off by the closing line, before
        # the browser has had a single rendering opportunity — measured, entered
        # visible around 60 ms, off around 110 ms, first paint near 290 ms. No
        # painted frame carries it here, and no reading can invent one. Proving
        # the screen reaches the SCREEN needs a load slow enough to paint during
        # — a throttled network profile in the driver — which is a rule of its
        # own and an open decision for the operator, not something this one can
        # claim.
        cold = await ctx.new_page()
        await cold.add_init_script("""(() => {
          window.__samples = [];
          const record = () => {
            const s = document.querySelector('#splash');
            window.__samples.push([performance.now(), s ? !s.hidden : null]);
          };
          let tracked = null;
          new MutationObserver(() => {
            const s = document.querySelector('#splash');
            if (s && s !== tracked) {
              tracked = s;
              record();
              new MutationObserver(record).observe(
                s, {attributes: true, attributeFilter: ['hidden']});
            }
          }).observe(document, {childList: true, subtree: true});
          const frame = () => { record(); requestAnimationFrame(frame); };
          requestAnimationFrame(frame);
        })()""")
        await cold.goto("http://127.0.0.1:8899/wrapped.html", wait_until="commit")
        await cold.wait_for_timeout(3000)
        samples = await cold.evaluate("()=>window.__samples")

        # The first reading on which the screen EXISTS is the first moment it
        # could have been seen: before it, the browser has not parsed it yet and
        # a reading of « absent » says nothing about it.
        first = next(((t, v) for t, v in samples if v is not None), None)
        check("the startup screen is there as soon as it enters the document",
                 first is not None and first[1] and first[0] < 400,
                 f"present at {round(first[0])}ms, visible: {first[1]}"
                 if first else f"absent from the {len(samples)} readings")
        seen = [t for t, v in samples if v]
        gone = [t for t, v in samples if v is False and seen and t > seen[0]]
        check("and it leaves as soon as the interface is there",
                 bool(gone) and gone[0] < 1500,
                 f"gone at {round(gone[0])}ms" if gone else "gone for ever")
        back = [t for t, v in samples if v and gone and t > gone[0]]
        check("it does not come back a second time", not back,
                 str([round(t) for t in back[:3]]))
        await cold.close()

        # ── where the wait is PLAYED, it lasts what the bar announces ───────
        # Signing in inside the prototype fetches nothing, so the wait that
        # follows has to be played out to be judged at all. Same screen, same
        # seam, a duration instead of an observation.
        played = await ctx.new_page()
        await played.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        await played.evaluate("()=>window.__loadingDone?.()")
        await played.evaluate("()=>window.__go('connexion')")
        await played.wait_for_timeout(350)
        await played.evaluate("""()=>{
          document.querySelector('[name=username]').value = 'izno';
          document.querySelector('[name=password]').value = 'x';
          document.querySelector('#loginform').requestSubmit();}""")
        t1 = time.monotonic()
        series = []
        while time.monotonic() - t1 < 7:
            series.append((round((time.monotonic() - t1) * 1000),
                          await played.evaluate(
                              "()=>{const s=document.querySelector('#splash');"
                              "return s ? !s.hidden : null;}")))
            await played.wait_for_timeout(120)
        up = [t for t, v in series if v]
        down = [t for t, v in series if v is False and up and t > up[0]]
        check("a sign-in inside the prototype covers the wait",
                 bool(up) and up[0] < 500, f"at {up[0] if up else '—'}ms")
        check("and it lasts what the bar announces",
                 bool(down) and 4500 < down[0] < 6500,
                 f"gone at {down[0] if down else 'never'}ms")

        # The seam ends it early, which is the same promise resolving sooner.
        await played.evaluate("()=>window.__go('connexion')")
        await played.wait_for_timeout(300)
        await played.evaluate("""()=>{
          document.querySelector('[name=username]').value = 'izno';
          document.querySelector('[name=password]').value = 'x';
          document.querySelector('#loginform').requestSubmit();}""")
        await played.wait_for_timeout(700)
        before = await played.evaluate("()=>!document.querySelector('#splash').hidden")
        await played.evaluate("()=>window.__loadingDone()")
        await played.wait_for_timeout(300)
        after = await played.evaluate("()=>!document.querySelector('#splash').hidden")
        check("a load that finishes early takes the screen off early",
                 before and not after, f"at 700ms: {before}, after resolution: {after}")
        await played.close()

        await b.close()

    _journal.summary(errors)

asyncio.run(main())
