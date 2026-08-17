"""R55 — every gesture answers a REAL finger, not only a synthetic one.

Synthetic `PointerEvent`s are dispatched straight at an element and are never
cancelled by anything. Real touch input goes through hit-testing and the
compositor, and the compositor takes gestures away: the moment it decides a
drag is a scroll it fires `pointercancel` and stops delivering `pointermove`
for that pointer. A pointer-only handler living inside a scrollport therefore
passes every synthetic test and does nothing at all under a thumb.

That is not hypothetical. Two gestures on the scrollport — the pull to refresh
and the swipe between views — were lost exactly that way when the gesture layer
moved from touch events to pointer events, and no script noticed, because every
script drove them synthetically.

So this one drives them through `Input.dispatchTouchEvent`, which is real
browser input, and measures the outcome rather than the wiring. The gestures
that CAN claim their axis in `touch-action` — a swipeable row, a deck card —
are measured the same way, because that claim is what makes them survive and
nothing else here proves it still holds.
"""
import asyncio

from common import Journal
from playwright.async_api import async_playwright

# The prototype's own long-press delay; a probe shorter than it proves nothing.
PRESS_MS = 480

# The phone's OWN long press — select, copy, save — cannot be outrun by a
# listener, and no synthetic input raises it. It is therefore asserted on the
# DECLARATION, exactly like the `touch-action` axis claim.
PRESS_GUARD = """(selectors) => {
  const missing = [];
  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (!el) { missing.push(sel + ' (absent from this state)'); continue; }
    const cs = getComputedStyle(el);
    if ((cs.webkitUserSelect || cs.userSelect) !== 'none')
      missing.push(sel + ' selectable');
    if (cs.webkitTouchCallout && cs.webkitTouchCallout !== 'none')
      missing.push(sel + ' callout=' + cs.webkitTouchCallout);
  }
  return missing;
}"""

_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


async def drag(cdp, x0, y0, steps, dx, dy):
    """Drags one real finger across the page.

    Args:
        cdp: An open CDP session.
        x0: Starting x, in CSS pixels.
        y0: Starting y, in CSS pixels.
        steps: Number of intermediate moves.
        dx: Horizontal travel per move.
        dy: Vertical travel per move.
    """
    await cdp.send("Input.dispatchTouchEvent",
                   {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0, "id": 1}]})
    for i in range(1, steps + 1):
        await cdp.send("Input.dispatchTouchEvent",
                       {"type": "touchMove",
                        "touchPoints": [{"x": x0 + i * dx, "y": y0 + i * dy, "id": 1}]})
        await asyncio.sleep(0.02)
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        cdp = await ctx.new_cdp_session(pg)
        await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        # The startup screen covers the frame for as long as the load it stands
        # for lasts. Nothing is being fetched here, so the harness closes that
        # wait through the same seam the app uses, rather than sleeping it out.
        await pg.evaluate("()=>window.__chargementTermine?.()")
        await pg.evaluate("()=>document.querySelector('#toastx').click()")

        global _journal
        _journal = Journal("R55 — the gestures under a real finger")

        async def rect(selector):
            return await pg.evaluate(
                "(s)=>{const e=document.querySelector(s);"
                "return e ? e.getBoundingClientRect().toJSON() : null;}", selector)

        # 1. Pull to refresh — on every scrolling surface, not the convenient
        #    one. The indicator has to ARM and then show its spinner; a pull
        #    that travels a few pixels and stops has no loader to show.
        surfaces = ["acq-encours-repos", "acq-suivis-liste", "acq-decouvrir",
                    "lib-grille", "lib-liste", "arr-repos", "systeme"]
        without_loading = []
        for state_ in surfaces:
            await pg.evaluate("(s)=>window.__go(s)", state_)
            await pg.wait_for_timeout(250)
            await pg.evaluate("""()=>{window.__h=0;window.__t=setInterval(()=>{
                const p=document.querySelector('#ptr');
                window.__h=Math.max(window.__h,p.getBoundingClientRect().height);},16);}""")
            r = await rect("#port")
            await drag(cdp, r["x"] + r["width"] / 2, r["y"] + 60, 10, 0, 18)
            await pg.wait_for_timeout(250)
            out = await pg.evaluate("""()=>{clearInterval(window.__t);
                return {h:window.__h, cls:document.querySelector('#ptr').className};}""")
            # 44px is the arming threshold the gesture itself uses.
            if out["h"] < 44 or "loading" not in out["cls"]:
                without_loading.append(f"{state_} (h={out['h']:.0f}, {out['cls']})")
            await pg.evaluate("()=>window.__reposPTR()")
        check(f"the pull-to-refresh arms and spins on the {len(surfaces)} surfaces",
                 not without_loading, " · ".join(without_loading))

        # 2. And the scrollport has NO horizontal gesture of its own. It used
        #    to change tab or lens, and it fired by accident constantly: every
        #    horizontal component of a vertical scroll, every aborted row
        #    swipe. Its absence is now the contract — a gesture that triggers
        #    what nobody asked for costs more than the taps it saves.
        for state_, expected in (("acq-encours-repos", "En cours"), ("lib-grille", "Médias")):
            await pg.evaluate("(s)=>window.__go(s)", state_)
            await pg.wait_for_timeout(250)
            r = await rect("#port")
            for direction in (-20, 20):
                await drag(cdp, r["x"] + r["width"] / 2, r["y"] + 200, 10, direction, 0)
                await pg.wait_for_timeout(300)
            left = await pg.evaluate(
                "()=>(document.querySelector('.seg [aria-selected=\"true\"]')||{}).textContent")
            check(f"no drag changes the view ({state_})",
                     (left or "").startswith(expected), str(left))

        # 3. A vertical drag further down the surface must still SCROLL. The
        #    cure for one gesture must not swallow the browser's own.
        await pg.evaluate("()=>window.__go('lib-grille')")
        await pg.wait_for_timeout(250)
        r = await rect("#port")
        await drag(cdp, r["x"] + r["width"] / 2, r["y"] + r["height"] - 120, 10, 0, -22)
        await pg.wait_for_timeout(350)
        scrolled = await pg.evaluate("()=>document.querySelector('#port').scrollTop")
        check("the surface still scrolls normally", scrolled > 40, f"scrollTop={scrolled}")

        # 4. The gestures that claim their axis keep the pointer path, and the
        #    claim is what makes them survive. Measured, not assumed.
        await pg.evaluate("()=>window.__go('acq-suivis-liste')")
        await pg.wait_for_timeout(300)
        r = await rect("#view .swipe")
        await drag(cdp, r["x"] + r["width"] / 2, r["y"] + r["height"] / 2, 12, -20, 0)
        await pg.wait_for_timeout(300)
        transformed = await pg.evaluate(
            "()=>getComputedStyle(document.querySelector('#view .swipe .card')).transform")
        check("a row still opens", transformed not in ("none", "matrix(1, 0, 0, 1, 0, 0)"),
                 transformed)

        await pg.evaluate("()=>window.__go('acq-decouvrir-deck')")
        await pg.wait_for_timeout(350)
        before = await pg.evaluate("()=>document.querySelectorAll('.sugwrap, .dcard').length")
        r = await rect(".deck .dcard[data-depth='0']")
        await drag(cdp, r["x"] + r["width"] / 2, r["y"] + r["height"] / 2, 12, 22, 0)
        await pg.wait_for_timeout(450)
        moved = await pg.evaluate("""()=>{const c=document.querySelector(".deck .dcard[data-depth='0']");
            return c ? c.textContent.replace(/\\s+/g,' ').trim().slice(0,40) : null;}""")
        check("the deck still moves on by one card", bool(moved) and before > 0, str(moved))

        # 5. THE LONG PRESS, on every surface where a tap is already spoken
        #    for. Three things a thumb taught that a mouse never does: it is
        #    never still, its pointer stream is cancelled by the compositor,
        #    and the phone offers its own select/copy menu instead.
        async def press(x, y, ms=700):
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
            # A real thumb drifts several pixels over half a second. Below one,
            # Chrome delivers no `touchmove` at all — and a drift the browser
            # suppresses cannot test the tolerance that exists for it.
            for i in range(int(ms / 60)):
                drift = 5 if i % 2 else -5
                await cdp.send("Input.dispatchTouchEvent",
                               {"type": "touchMove",
                                "touchPoints": [{"x": x + drift, "y": y + drift, "id": 1}]})
                await asyncio.sleep(0.06)
            await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})

        press_surfaces = [
            ("follows gallery", "acq-suivis-grille", ".tile"),
            ("library gallery", "lib-grille", ".tile"),
            ("a card's poster", "acq-suivis-liste", "#view .card .poster"),
            ("a card's body", "acq-suivis-liste", "#view .card .cbody"),
            ("deck card", "acq-decouvrir-deck", ".deck .dcard[data-depth='0']"),
        ]
        without_panel, with_selection, fired = [], [], []
        for name, state_, sel in press_surfaces:
            await pg.evaluate("(s)=>window.__go(s)", state_)
            await pg.wait_for_timeout(420)
            await pg.evaluate("()=>{window.__acts=[];"
                              "document.addEventListener('click', e=>window.__acts.push("
                              "(e.target.tagName||'')+'.'+(e.target.className||'')), false);}")
            r = await rect(sel)
            if r is None:
                without_panel.append(f"{name} (target absent)")
                continue
            await press(r["x"] + r["width"] / 2, r["y"] + r["height"] / 2)
            await pg.wait_for_timeout(400)
            out = await pg.evaluate("""()=>({
              panel: document.querySelector('#sheet').classList.contains('open'),
              selection: String(window.getSelection() || '').length,
              acts: window.__acts})""")
            if not out["panel"]:
                without_panel.append(name)
            if out["selection"] > 0:
                with_selection.append(name)
            # The panel opens UNDER the finger: the lift must not activate its
            # primary action. That is what a long press on a follow was doing.
            if any(".sact" in act for act in out["acts"]):
                fired.append(f"{name} → {out['acts']}")
            await pg.evaluate("()=>window.__close && window.__close('sheet')")
            await pg.wait_for_timeout(150)
        check(f"the long press opens the panel on the {len(press_surfaces)} surfaces",
                 not without_panel, " · ".join(without_panel))
        check("and never selects anything", not with_selection, " · ".join(with_selection))
        check("the lift does not fire the panel that has just appeared",
                 not fired, " · ".join(fired))

        # The phone's OWN long press — select, copy, save — cannot be outrun by
        # a listener, and no synthetic input raises it, so it is asserted on the
        # declaration itself. Exactly like the `touch-action` axis claim.
        # Each surface is checked in a state that DRAWS it: the deck state has
        # no list poster, and a rule that skips what is absent proves nothing.
        for state_, selectors in (("acq-suivis-liste", [".poster"]),
                                 ("lib-grille", [".tile"]),
                                 ("acq-decouvrir-deck", [".dcard"]),
                                 ("feuille-suivi-complet", [".sheetposter"])):
            await pg.evaluate("(s)=>window.__go(s)", state_)
            await pg.wait_for_timeout(320)
            refusal = await pg.evaluate(PRESS_GUARD, selectors)
            if refusal:
                break
        check("the pressable surfaces refuse the phone's own menu",
                 not refusal, " · ".join(refusal))


        # ── the browser's own menu is refused where we answer ─────────────
        # `user-select` stops a selection and `-webkit-touch-callout` answers
        # iOS; neither touches the menu Android raises from `contextmenu`. The
        # observable fact is that the event is prevented — a native menu itself
        # is not observable from here, so asserting its absence would be a rule
        # that can never fail.
        refusal = await pg.evaluate("""()=>{
          const target = document.querySelector('#view .poster') ||
                         document.querySelector('#view .card');
          const e = new MouseEvent('contextmenu', {bubbles:true, cancelable:true});
          target.dispatchEvent(e);
          return {on: target.className, refused: e.defaultPrevented};}""")
        check("the browser's menu is refused on a poster",
                 refusal["refused"], refusal["on"])

        # But never inside a text field: pasting has no other route there, and
        # the interface offers nothing of its own.
        field = await pg.evaluate("""()=>{
          const c = document.querySelector('#device input[type="search"], #device input');
          if (!c) return null;
          const e = new MouseEvent('contextmenu', {bubbles:true, cancelable:true});
          c.dispatchEvent(e);
          return e.defaultPrevented;}""")
        check("but kept inside a text field", field is False, str(field))

        # ── and the press answers ABOVE the scrollport too ─────────────────
        # The listeners lived on the scrollport, which holds the pages and
        # nothing else: every layer above it — sheet, screen, drawer, dialog —
        # sits outside it, so eight states drew a card no press could reach.
        # What is checked is the panel OPENING there, not which element the
        # listeners happen to be bound to — that would be checking a choice
        # against itself, and no such rule can ever fall.
        # The layers above the scrollport — sheet, screen, drawer, dialog — sit
        # OUTSIDE it, so a refusal bound to the scrollport leaves every card and
        # poster drawn in one of them offering the browser's menu. Eight named
        # states draw one.
        #
        # The long press is NOT checked here, and deliberately: on those cards
        # the body opens the panel on a plain tap, so `armerAppui` refuses to arm
        # a timer that would open it twice. A rule asserting a press there would
        # be asserting a behaviour the design does not want.
        await pg.evaluate("()=>window.__go('acq-identifier')")
        await pg.wait_for_timeout(450)
        # `acq-identifier` opens the add screen — a real route now
        # (`/ajout`, rendered inside `#coquille`), not `#screen`: the card
        # this hold reaches is drawn there, above the scrollport just the
        # same.
        layer = await pg.evaluate("""()=>{
          const port = document.querySelector('#port');
          const c = [...document.querySelectorAll('.card')]
            .find(e => e.getBoundingClientRect().width > 0 && !port.contains(e));
          if (!c) return null;
          const e = new MouseEvent('contextmenu', {bubbles:true, cancelable:true});
          c.dispatchEvent(e);
          return {inScreen: !!document.querySelector('.screen.open')?.contains(c),
                  refused: e.defaultPrevented};}""")
        check("a card is drawn above the scrollport",
                 layer is not None and layer["inScreen"], str(layer))
        check("and the browser's menu is refused there too",
                 bool(layer and layer["refused"]), str(layer))

        # And a press there must ARM. Four states draw a poster above the
        # scrollport — a poster is not a card body, so nothing refuses it a
        # timer — and with the listeners bound to the scrollport the press never
        # reached it at all. The panel is read WHILE THE FINGER IS DOWN: on that
        # surface a tap opens it too, so anything measured after the lift cannot
        # tell a press from a tap.
        await pg.evaluate("()=>closeSheet()")
        await pg.wait_for_timeout(340)
        check("the panel starts closed", not await pg.evaluate(
            "()=>document.querySelector('#sheet').classList.contains('open')"))
        target = await pg.evaluate("""()=>{
          const port = document.querySelector('#port');
          const a = [...document.querySelectorAll('.poster')]
            .find(e => e.getBoundingClientRect().width > 0 && !port.contains(e));
          if (!a) return null;
          const r = a.getBoundingClientRect();
          const x = r.x + r.width / 2, y = r.y + r.height / 2;
          return port.contains(document.elementFromPoint(x, y)) ? null : {x, y};}""")
        check("a poster is drawn above the scrollport", target is not None)
        if target:
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchStart",
                            "touchPoints": [{"x": target["x"], "y": target["y"], "id": 1}]})
            await pg.wait_for_timeout(PRESS_MS + 240)
            during = await pg.evaluate(
                "()=>document.querySelector('#sheet').classList.contains('open')")
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchEnd", "touchPoints": []})
            await pg.wait_for_timeout(320)
            check("and a long press there opens the panel, finger still down", during)
            await pg.evaluate("()=>closeSheet()")
            await pg.wait_for_timeout(300)

        # ── 6. THE SHEET HANDLE, dragged down by a real finger ────────────
        # It read the pointer stream with neither capture nor a claimed axis, so
        # a 150px drag delivered pointerdown, TWO pointermoves, then
        # pointercancel — and never the pointerup its closing hangs off. The
        # sheet stayed open. Same mechanism as the pull-to-refresh and the view
        # swipe, on a third gesture no rule had looked at.
        await pg.evaluate("()=>{closeSheet(); openFollowSheet('Silo');}")
        await pg.wait_for_timeout(450)
        check("a sheet is open", await pg.evaluate(
            "()=>document.querySelector('#sheet').classList.contains('open')"))

        async def drag_handle(from_, to, steps=12):
            """Drags one finger down the handle, in steps a thumb really makes."""
            r = await pg.evaluate(
                "()=>{const b=document.querySelector('#sheetgrab').getBoundingClientRect();"
                "return {x:b.x+b.width/2, y:b.y+b.height/2};}")
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchStart",
                            "touchPoints": [{"x": r["x"], "y": r["y"] + from_, "id": 1}]})
            for dy in range(steps, to + 1, steps):
                await cdp.send("Input.dispatchTouchEvent",
                               {"type": "touchMove",
                                "touchPoints": [{"x": r["x"], "y": r["y"] + dy, "id": 1}]})
                await asyncio.sleep(0.016)
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchEnd", "touchPoints": []})
            await pg.wait_for_timeout(420)

        await drag_handle(0, 150)
        check("a 150px drag closes the sheet", not await pg.evaluate(
            "()=>document.querySelector('#sheet').classList.contains('open')"))

        # A short drag is not a dismissal: it must spring back, and it must not
        # leave the sheet displaced.
        await pg.evaluate("()=>openFollowSheet('Silo')")
        await pg.wait_for_timeout(450)
        await drag_handle(0, 24)
        sheet_state = await pg.evaluate("""()=>({
          open: document.querySelector('#sheet').classList.contains('open'),
          moved: document.querySelector('#sheet').style.transform || ''})""")
        check("a drag too short leaves it open", sheet_state["open"], str(sheet_state))
        check("and put back in place", not sheet_state["moved"], sheet_state["moved"])
        # A MOUSE drag must close it too — the interface is used from a desktop
        # browser. Touch gets implicit pointer capture for free; a mouse does
        # not, so without an explicit capture the events stop the moment the
        # cursor leaves a 22px strip, which is the first centimetre of a 70px
        # gesture.
        await pg.evaluate("()=>openFollowSheet('Silo')")
        await pg.wait_for_timeout(450)
        r = await pg.evaluate(
            "()=>{const b=document.querySelector('#sheetgrab').getBoundingClientRect();"
            "return {x:b.x+b.width/2, y:b.y+b.height/2};}")
        await pg.mouse.move(r["x"], r["y"])
        await pg.mouse.down()
        for dy in range(12, 151, 12):
            await pg.mouse.move(r["x"], r["y"] + dy)
            await asyncio.sleep(0.016)
        await pg.mouse.up()
        await pg.wait_for_timeout(420)
        check("with a mouse too, a 150px drag closes it", not await pg.evaluate(
            "()=>document.querySelector('#sheet').classList.contains('open')"))

        # A cancel is not a lift. The compositor can still take the gesture — a
        # second finger, a system edge swipe — and the sheet must go back where
        # it was rather than close on something the operator did not finish.
        await pg.evaluate("()=>openFollowSheet('Silo')")
        await pg.wait_for_timeout(450)
        # Driven as a REAL cancelled touch, not as synthetic events: a
        # hand-built PointerEvent carries an id no pointer owns, so the capture
        # the handler takes throws and the probe measures its own artefact.
        r = await pg.evaluate(
            "()=>{const b=document.querySelector('#sheetgrab').getBoundingClientRect();"
            "return {x:b.x+b.width/2, y:b.y+b.height/2};}")
        await cdp.send("Input.dispatchTouchEvent",
                       {"type": "touchStart",
                        "touchPoints": [{"x": r["x"], "y": r["y"], "id": 1}]})
        for dy in (40, 80, 120):
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchMove",
                            "touchPoints": [{"x": r["x"], "y": r["y"] + dy, "id": 1}]})
            await asyncio.sleep(0.016)
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchCancel", "touchPoints": []})
        await pg.wait_for_timeout(420)
        cancelled = await pg.evaluate("""()=>{
          const s = document.querySelector('#sheet');
          return {open: s.classList.contains('open'), moved: s.style.transform || ''};}""")
        check("a cancel does not close the sheet", cancelled["open"], str(cancelled))
        check("and puts it back in place", not cancelled["moved"], cancelled["moved"])
        await pg.evaluate("()=>closeSheet()")
        await pg.wait_for_timeout(320)

        check("no JS error", not errors, str(errors))
        await b.close()

    _journal.summary()

asyncio.run(main())
