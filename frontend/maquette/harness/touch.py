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
APPUI_MS = 480

# The phone's OWN long press — select, copy, save — cannot be outrun by a
# listener, and no synthetic input raises it. It is therefore asserted on the
# DECLARATION, exactly like the `touch-action` axis claim.
GARDE_APPUI = """(selecteurs) => {
  const manquants = [];
  for (const sel of selecteurs) {
    const el = document.querySelector(sel);
    if (!el) { manquants.push(sel + ' (absent de cet état)'); continue; }
    const cs = getComputedStyle(el);
    if ((cs.webkitUserSelect || cs.userSelect) !== 'none')
      manquants.push(sel + ' sélectionnable');
    if (cs.webkitTouchCallout && cs.webkitTouchCallout !== 'none')
      manquants.push(sel + ' callout=' + cs.webkitTouchCallout);
  }
  return manquants;
}"""

_journal = None


def verifier(nom, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(nom, condition, detail)


async def glisser(cdp, x0, y0, pas, dx, dy):
    """Drags one real finger across the page.

    Args:
        cdp: An open CDP session.
        x0: Starting x, in CSS pixels.
        y0: Starting y, in CSS pixels.
        pas: Number of intermediate moves.
        dx: Horizontal travel per move.
        dy: Vertical travel per move.
    """
    await cdp.send("Input.dispatchTouchEvent",
                   {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0, "id": 1}]})
    for i in range(1, pas + 1):
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
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        cdp = await ctx.new_cdp_session(pg)
        await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        # The startup screen covers the frame for as long as the load it stands
        # for lasts. Nothing is being fetched here, so the harness closes that
        # wait through the same seam the app uses, rather than sleeping it out.
        await pg.evaluate("()=>window.__chargementTermine?.()")
        await pg.evaluate("()=>document.querySelector('#toastx').click()")

        global _journal
        _journal = Journal("R55 — les gestes sous un vrai doigt")

        async def rect(selecteur):
            return await pg.evaluate(
                "(s)=>{const e=document.querySelector(s);"
                "return e ? e.getBoundingClientRect().toJSON() : null;}", selecteur)

        # 1. Pull to refresh — on every scrolling surface, not the convenient
        #    one. The indicator has to ARM and then show its spinner; a pull
        #    that travels a few pixels and stops has no loader to show.
        surfaces = ["acq-encours-repos", "acq-suivis-liste", "acq-decouvrir",
                    "lib-grille", "lib-liste", "arr-repos", "systeme"]
        sans_charge = []
        for etat in surfaces:
            await pg.evaluate("(s)=>window.__go(s)", etat)
            await pg.wait_for_timeout(250)
            await pg.evaluate("""()=>{window.__h=0;window.__t=setInterval(()=>{
                const p=document.querySelector('#ptr');
                window.__h=Math.max(window.__h,p.getBoundingClientRect().height);},16);}""")
            r = await rect("#port")
            await glisser(cdp, r["x"] + r["width"] / 2, r["y"] + 60, 10, 0, 18)
            await pg.wait_for_timeout(250)
            out = await pg.evaluate("""()=>{clearInterval(window.__t);
                return {h:window.__h, cls:document.querySelector('#ptr').className};}""")
            # 44px is the arming threshold the gesture itself uses.
            if out["h"] < 44 or "loading" not in out["cls"]:
                sans_charge.append(f"{etat} (h={out['h']:.0f}, {out['cls']})")
            await pg.evaluate("()=>window.__reposPTR()")
        verifier(f"le tirer-pour-recharger arme et tourne sur les {len(surfaces)} surfaces",
                 not sans_charge, " · ".join(sans_charge))

        # 2. And the scrollport has NO horizontal gesture of its own. It used
        #    to change tab or lens, and it fired by accident constantly: every
        #    horizontal component of a vertical scroll, every aborted row
        #    swipe. Its absence is now the contract — a gesture that triggers
        #    what nobody asked for costs more than the taps it saves.
        for etat, attendu in (("acq-encours-repos", "En cours"), ("lib-grille", "Médias")):
            await pg.evaluate("(s)=>window.__go(s)", etat)
            await pg.wait_for_timeout(250)
            r = await rect("#port")
            for direction in (-20, 20):
                await glisser(cdp, r["x"] + r["width"] / 2, r["y"] + 200, 10, direction, 0)
                await pg.wait_for_timeout(300)
            reste = await pg.evaluate(
                "()=>(document.querySelector('.seg [aria-selected=\"true\"]')||{}).textContent")
            verifier(f"aucun glissé ne change de vue ({etat})",
                     (reste or "").startswith(attendu), str(reste))

        # 3. A vertical drag further down the surface must still SCROLL. The
        #    cure for one gesture must not swallow the browser's own.
        await pg.evaluate("()=>window.__go('lib-grille')")
        await pg.wait_for_timeout(250)
        r = await rect("#port")
        await glisser(cdp, r["x"] + r["width"] / 2, r["y"] + r["height"] - 120, 10, 0, -22)
        await pg.wait_for_timeout(350)
        defile = await pg.evaluate("()=>document.querySelector('#port').scrollTop")
        verifier("la surface défile toujours normalement", defile > 40, f"scrollTop={defile}")

        # 4. The gestures that claim their axis keep the pointer path, and the
        #    claim is what makes them survive. Measured, not assumed.
        await pg.evaluate("()=>window.__go('acq-suivis-liste')")
        await pg.wait_for_timeout(300)
        r = await rect("#view .swipe")
        await glisser(cdp, r["x"] + r["width"] / 2, r["y"] + r["height"] / 2, 12, -20, 0)
        await pg.wait_for_timeout(300)
        transforme = await pg.evaluate(
            "()=>getComputedStyle(document.querySelector('#view .swipe .card')).transform")
        verifier("une rangée s'écarte encore", transforme not in ("none", "matrix(1, 0, 0, 1, 0, 0)"),
                 transforme)

        await pg.evaluate("()=>window.__go('acq-decouvrir-deck')")
        await pg.wait_for_timeout(350)
        avant = await pg.evaluate("()=>document.querySelectorAll('.sugwrap, .dcard').length")
        r = await rect(".deck .dcard[data-depth='0']")
        await glisser(cdp, r["x"] + r["width"] / 2, r["y"] + r["height"] / 2, 12, 22, 0)
        await pg.wait_for_timeout(450)
        bouge = await pg.evaluate("""()=>{const c=document.querySelector(".deck .dcard[data-depth='0']");
            return c ? c.textContent.replace(/\\s+/g,' ').trim().slice(0,40) : null;}""")
        verifier("le deck avance encore d'une carte", bool(bouge) and avant > 0, str(bouge))

        # 5. THE LONG PRESS, on every surface where a tap is already spoken
        #    for. Three things a thumb taught that a mouse never does: it is
        #    never still, its pointer stream is cancelled by the compositor,
        #    and the phone offers its own select/copy menu instead.
        async def presser(x, y, ms=700):
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
            # A real thumb drifts several pixels over half a second. Below one,
            # Chrome delivers no `touchmove` at all — and a drift the browser
            # suppresses cannot test the tolerance that exists for it.
            for i in range(int(ms / 60)):
                ecart = 5 if i % 2 else -5
                await cdp.send("Input.dispatchTouchEvent",
                               {"type": "touchMove",
                                "touchPoints": [{"x": x + ecart, "y": y + ecart, "id": 1}]})
                await asyncio.sleep(0.06)
            await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})

        surfaces_appui = [
            ("galerie des suivis", "acq-suivis-grille", ".tile"),
            ("galerie de la médiathèque", "lib-grille", ".tile"),
            ("affiche d'une carte", "acq-suivis-liste", "#view .card .poster"),
            ("corps d'une carte", "acq-suivis-liste", "#view .card .cbody"),
            ("carte du deck", "acq-decouvrir-deck", ".deck .dcard[data-depth='0']"),
        ]
        sans_panneau, avec_selection, agis = [], [], []
        for nom, etat, sel in surfaces_appui:
            await pg.evaluate("(s)=>window.__go(s)", etat)
            await pg.wait_for_timeout(420)
            await pg.evaluate("()=>{window.__actes=[];"
                              "document.addEventListener('click', e=>window.__actes.push("
                              "(e.target.tagName||'')+'.'+(e.target.className||'')), false);}")
            r = await rect(sel)
            if r is None:
                sans_panneau.append(f"{nom} (cible absente)")
                continue
            await presser(r["x"] + r["width"] / 2, r["y"] + r["height"] / 2)
            await pg.wait_for_timeout(400)
            out = await pg.evaluate("""()=>({
              panneau: document.querySelector('#sheet').classList.contains('open'),
              selection: String(window.getSelection() || '').length,
              actes: window.__actes})""")
            if not out["panneau"]:
                sans_panneau.append(nom)
            if out["selection"] > 0:
                avec_selection.append(nom)
            # The panel opens UNDER the finger: the lift must not activate its
            # primary action. That is what a long press on a follow was doing.
            if any(".sact" in acte for acte in out["actes"]):
                agis.append(f"{nom} → {out['actes']}")
            await pg.evaluate("()=>window.__close && window.__close('sheet')")
            await pg.wait_for_timeout(150)
        verifier(f"l'appui long ouvre le panneau sur les {len(surfaces_appui)} surfaces",
                 not sans_panneau, " · ".join(sans_panneau))
        verifier("et ne sélectionne jamais rien", not avec_selection, " · ".join(avec_selection))
        verifier("le relâchement n'actionne pas le panneau qui vient d'apparaître",
                 not agis, " · ".join(agis))

        # The phone's OWN long press — select, copy, save — cannot be outrun by
        # a listener, and no synthetic input raises it, so it is asserted on the
        # declaration itself. Exactly like the `touch-action` axis claim.
        # Each surface is checked in a state that DRAWS it: the deck state has
        # no list poster, and a rule that skips what is absent proves nothing.
        for etat, selecteurs in (("acq-suivis-liste", [".poster"]),
                                 ("lib-grille", [".tile"]),
                                 ("acq-decouvrir-deck", [".dcard"]),
                                 ("feuille-suivi-complet", [".sheetposter"])):
            await pg.evaluate("(s)=>window.__go(s)", etat)
            await pg.wait_for_timeout(320)
            refus = await pg.evaluate(GARDE_APPUI, selecteurs)
            if refus:
                break
        verifier("les surfaces pressables refusent le menu du téléphone",
                 not refus, " · ".join(refus))


        # ── the browser's own menu is refused where we answer ─────────────
        # `user-select` stops a selection and `-webkit-touch-callout` answers
        # iOS; neither touches the menu Android raises from `contextmenu`. The
        # observable fact is that the event is prevented — a native menu itself
        # is not observable from here, so asserting its absence would be a rule
        # that can never fail.
        refus = await pg.evaluate("""()=>{
          const cible = document.querySelector('#view .poster') ||
                        document.querySelector('#view .card');
          const e = new MouseEvent('contextmenu', {bubbles:true, cancelable:true});
          cible.dispatchEvent(e);
          return {sur: cible.className, refuse: e.defaultPrevented};}""")
        verifier("le menu du navigateur est refusé sur une affiche",
                 refus["refuse"], refus["sur"])

        # But never inside a text field: pasting has no other route there, and
        # the interface offers nothing of its own.
        champ = await pg.evaluate("""()=>{
          const c = document.querySelector('#device input[type="search"], #device input');
          if (!c) return null;
          const e = new MouseEvent('contextmenu', {bubbles:true, cancelable:true});
          c.dispatchEvent(e);
          return e.defaultPrevented;}""")
        verifier("mais gardé dans un champ de saisie", champ is False, str(champ))

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
        couche = await pg.evaluate("""()=>{
          const port = document.querySelector('#port');
          const c = [...document.querySelectorAll('.card')]
            .find(e => e.getBoundingClientRect().width > 0 && !port.contains(e));
          if (!c) return null;
          const e = new MouseEvent('contextmenu', {bubbles:true, cancelable:true});
          c.dispatchEvent(e);
          return {dansEcran: !!document.querySelector('.screen.open')?.contains(c),
                  refuse: e.defaultPrevented};}""")
        verifier("une carte est dessinée au-dessus du défilement",
                 couche is not None and couche["dansEcran"], str(couche))
        verifier("et le menu du navigateur y est refusé aussi",
                 bool(couche and couche["refuse"]), str(couche))

        # And a press there must ARM. Four states draw a poster above the
        # scrollport — a poster is not a card body, so nothing refuses it a
        # timer — and with the listeners bound to the scrollport the press never
        # reached it at all. The panel is read WHILE THE FINGER IS DOWN: on that
        # surface a tap opens it too, so anything measured after the lift cannot
        # tell a press from a tap.
        await pg.evaluate("()=>closeSheet()")
        await pg.wait_for_timeout(340)
        verifier("le panneau part fermé", not await pg.evaluate(
            "()=>document.querySelector('#sheet').classList.contains('open')"))
        cible = await pg.evaluate("""()=>{
          const port = document.querySelector('#port');
          const a = [...document.querySelectorAll('.poster')]
            .find(e => e.getBoundingClientRect().width > 0 && !port.contains(e));
          if (!a) return null;
          const r = a.getBoundingClientRect();
          const x = r.x + r.width / 2, y = r.y + r.height / 2;
          return port.contains(document.elementFromPoint(x, y)) ? null : {x, y};}""")
        verifier("une affiche est dessinée au-dessus du défilement", cible is not None)
        if cible:
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchStart",
                            "touchPoints": [{"x": cible["x"], "y": cible["y"], "id": 1}]})
            await pg.wait_for_timeout(APPUI_MS + 240)
            pendant = await pg.evaluate(
                "()=>document.querySelector('#sheet').classList.contains('open')")
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchEnd", "touchPoints": []})
            await pg.wait_for_timeout(320)
            verifier("et un appui long y ouvre le panneau, doigt encore posé", pendant)
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
        verifier("une feuille est ouverte", await pg.evaluate(
            "()=>document.querySelector('#sheet').classList.contains('open')"))

        async def glisserPoignee(depuis, jusqua, pas=12):
            """Drags one finger down the handle, in steps a thumb really makes."""
            r = await pg.evaluate(
                "()=>{const b=document.querySelector('#sheetgrab').getBoundingClientRect();"
                "return {x:b.x+b.width/2, y:b.y+b.height/2};}")
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchStart",
                            "touchPoints": [{"x": r["x"], "y": r["y"] + depuis, "id": 1}]})
            for dy in range(pas, jusqua + 1, pas):
                await cdp.send("Input.dispatchTouchEvent",
                               {"type": "touchMove",
                                "touchPoints": [{"x": r["x"], "y": r["y"] + dy, "id": 1}]})
                await asyncio.sleep(0.016)
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchEnd", "touchPoints": []})
            await pg.wait_for_timeout(420)

        await glisserPoignee(0, 150)
        verifier("un glissé de 150px ferme la feuille", not await pg.evaluate(
            "()=>document.querySelector('#sheet').classList.contains('open')"))

        # A short drag is not a dismissal: it must spring back, and it must not
        # leave the sheet displaced.
        await pg.evaluate("()=>openFollowSheet('Silo')")
        await pg.wait_for_timeout(450)
        await glisserPoignee(0, 24)
        etat = await pg.evaluate("""()=>({
          ouverte: document.querySelector('#sheet').classList.contains('open'),
          deplacee: document.querySelector('#sheet').style.transform || ''})""")
        verifier("un glissé trop court la laisse ouverte", etat["ouverte"], str(etat))
        verifier("et remise en place", not etat["deplacee"], etat["deplacee"])
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
        verifier("à la souris aussi, un glissé de 150px ferme", not await pg.evaluate(
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
        annule = await pg.evaluate("""()=>{
          const s = document.querySelector('#sheet');
          return {ouverte: s.classList.contains('open'), deplacee: s.style.transform || ''};}""")
        verifier("une annulation ne ferme pas la feuille", annule["ouverte"], str(annule))
        verifier("et la remet en place", not annule["deplacee"], annule["deplacee"])
        await pg.evaluate("()=>closeSheet()")
        await pg.wait_for_timeout(320)

        verifier("aucune erreur JS", not erreurs, str(erreurs))
        await b.close()

    _journal.summary()

asyncio.run(main())
