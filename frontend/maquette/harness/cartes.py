"""One card, one behaviour, in every list of the interface.

R41 — a card body opens the bottom PANEL, never a screen of its own.
R42 — a card poster ALWAYS leads somewhere: to the media sheet when that
      medium has one, to the panel when it does not. It used to lead nowhere,
      and the tooltip explaining the absence is invisible on a phone.
R43 — an action offered inline on a card is ALSO in that medium's panel.
R44 — the same medium reached from a card and from a gallery opens the SAME
      panel, action for action.
R45 — a tile addresses its panel by title, never by list index.
R46 — a card that is not a medium says so, and promises neither sheet nor panel.
R47 — every list draws its cards with the same builder and the same metrics.
R48 — a reason never truncates. It wraps, and the card grows.

R47 exists because the last holdout is what a shared component is worth:
Découvrir kept its own builder and drew a poster 63 % larger than every other
list, on a page that already offers a gallery and a deck for browsing. Reading
the code had not found it; measuring the geometry of all five surfaces did, in
one pass.

R43 and R44 are the two that matter. An action reachable from a single surface
disappears the moment that surface is displayed differently — which is exactly
how the poster view of « Incomplets » ended up with no way to complete a
series: the only « Compléter » was a button drawn on a card, and the gallery
draws no cards.

R45 exists because an index belongs to the list on screen, not to the medium.
It means something different in each lens, and a numeric title (« 1917 ») read
as an index opens the panel of whatever film happens to sit at that rank.
"""
import asyncio
import sys

from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8899/wrapped.html"

# Every state that draws cards, overlays included. The list was once shorter,
# and the two screens missing from it — resolution and release choice — were
# exactly the two drawing a card that is not a medium.
AFFICHE_LISTE = 84  # two thirds of the card's floor, so a card at that floor is 2:3  # the notch of the card that explains; see refonte.html
ETATS_CARTES = [
    "acq-encours-repos",
    "acq-encours-charge",
    "acq-suivis-liste",
    "acq-suivis-groupe",
    "lib-liste",
    "lib-incomplets",
    "lib-recents",
    "arr-repos",
    "arr-charge",
    "arr-resolution",
    "ecran-releases",
    "acq-identifier",
    "acq-decouvrir",
    "acq-decouvrir-degrade",
    # Search results were absent from this list, and the surface had drifted
    # exactly as far as the absence allowed: its poster box was sized, the
    # image inside it was not, and every thumbnail showed the top-left corner
    # of a 240x360 poster clipped into 54x81.
    "acq-ajout-resultats",
]

# States drawing tiles, and how to reach the tile layout from them.
ETATS_TUILES = ["lib-grille", "lib-incomplets", "lib-recents", "acq-suivis-grille"]

# The medium the operator reported: incomplete, and reachable both ways.
COMPARAISON = ("lib-incomplets", "Compléter → Acquisitions")


async def mode(pg, lequel):
    """Forces the library list/grid switch, when the current view has one.

    `__go` does not reset the layout, so a state visited after another inherits
    its mode. Asserting on an inherited mode measures the previous state.

    Args:
        pg: the page.
        lequel: "list" or "grid".
    """
    await pg.evaluate(
        "(m)=>{const b=document.querySelector(`[data-lmode=\"${m}\"]`); if(b) b.click();}",
        lequel,
    )
    await pg.wait_for_timeout(320)


async def actions_du_panneau(pg):
    """Returns the labels of the actions in the open panel, or None.

    Returns:
        List of action labels, or None when no panel is open.
    """
    return await pg.evaluate(
        """()=>{const s=document.querySelector('#sheet');
        if(!s||!s.classList.contains('open')) return null;
        return [...s.querySelectorAll('.sact')].map(x=>x.textContent.trim());}"""
    )


async def ferme(pg):
    """Closes any open panel and waits for the animation to finish."""
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(340)


async def main():
    """Runs R41–R45 and reports how many rules actually executed.

    Returns:
        0 when every rule passed, 1 otherwise.
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
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        await pg.goto(URL, wait_until="load")
        await pg.evaluate("()=>window.__measure(true)")
        # A closed screen keeps its markup in the DOM. Cards left behind there
        # are unreachable, so measuring them measures nothing the operator can
        # touch — and it charges one screen's cards to every later state.
        await pg.evaluate(
            "()=>{window.visible = (el)=>el.getClientRects().length > 0;}"
        )

        # ---- R41 / R42 -------------------------------------------------
        for etat in ETATS_CARTES:
            await pg.evaluate("(i)=>window.__go(i)", etat)
            await pg.wait_for_timeout(360)
            if etat.startswith("lib-"):
                await mode(pg, "list")
            releve = await pg.evaluate(
                """()=>[...document.querySelectorAll('.card')].filter(visible).map(c=>{
                    const b=c.querySelector('.cbody');
                    const p=c.querySelector('.poster');
                    return {titre:c.querySelector('.ctitle')?.textContent||'',
                            nonMedia:c.dataset.nonmedia||null,
                            panneau:b?b.dataset.panel||null:null,
                            feuilleDirecte:b?b.dataset.sheet||null:null,
                            posterEstBouton:p?p.tagName==='BUTTON':false,
                            posterVersFiche:p?p.dataset.fiche||null:null,
                            posterVersPanneau:p?p.dataset.panel||null:null,
                            posterInconnu:p?(p.querySelector('.pfall b')||{}).textContent==='?':false};})"""
            )
            if not releve:
                echecs.append(f"R41 {etat}: no card at all — the state draws nothing")
                continue
            executees += 3
            for c in releve:
                # R46 — a card that is not a medium says so, and never offers a
                # media sheet. What it may offer beyond that depends on WHICH
                # kind of non-medium it is, and merging the two was a defect:
                #
                #   · a RELEASE is one candidate among several for a medium
                #     already named on the screen. It has nothing of its own, so
                #     it promises neither sheet nor panel.
                #   · a DOSSIER is a folder the scrape could not name. It has no
                #     medium behind it, but it has its own actions — « Résoudre »
                #     is exactly what one came for — so it MUST address a panel,
                #     and that panel is its own, not a medium's.
                if c["nonMedia"]:
                    if c["posterEstBouton"]:
                        echecs.append(f"R46 {etat} « {c['titre']} »: a {c['nonMedia']} offers a media sheet")
                    if c["nonMedia"] == "dossier":
                        if not c["panneau"]:
                            echecs.append(f"R46 {etat} « {c['titre']} »: a folder addresses no panel")
                        elif c["panneau"].startswith("media:"):
                            echecs.append(f"R46 {etat} « {c['titre']} »: a folder addresses a MEDIA panel")
                    elif c["panneau"]:
                        echecs.append(f"R46 {etat} « {c['titre']} »: a {c['nonMedia']} addresses a media panel")
                    continue
                if not c["panneau"]:
                    echecs.append(f"R41 {etat} « {c['titre']} »: the body addresses no panel")
                if c["feuilleDirecte"]:
                    echecs.append(f"R41 {etat} « {c['titre']} »: the body still opens a sheet directly")
                # A poster leads to the SHEET when the medium has one, and to
                # the PANEL when it does not — never nowhere. An unidentified
                # folder still has actions, and « Résoudre → » is what one is
                # after; a dead zone on the page where things are stuck is the
                # worst possible place for one.
                if c["posterEstBouton"] and not (c["posterVersFiche"] or c["posterVersPanneau"]):
                    echecs.append(f"R42 {etat} « {c['titre']} »: the poster is a button leading nowhere")
                if not c["posterEstBouton"]:
                    echecs.append(f"R42 {etat} « {c['titre']} »: the poster is not a control at all")
                # Two DIFFERENT absences, never merged: « ? » says there is no
                # MEDIUM, initials say there is no artwork. A card whose medium
                # is known keeps its sheet even when nothing illustrates it.
                if c["posterInconnu"] and c["posterVersFiche"]:
                    echecs.append(f"R42 {etat} « {c['titre']} »: « ? » over a medium that has a sheet")
                if not c["posterInconnu"] and c["posterVersPanneau"]:
                    echecs.append(f"R42 {etat} « {c['titre']} »: an identified poster leading to the panel")
            horsMedia = sum(1 for c in releve if c["nonMedia"])
            print(f"  R41/R42 {etat:22} {len(releve):3} cards"
                  + (f" ({horsMedia} non-media)" if horsMedia else ""))

        # ---- R43 -------------------------------------------------------
        for etat in ETATS_CARTES:
            await pg.evaluate("(i)=>window.__go(i)", etat)
            await pg.wait_for_timeout(360)
            if etat.startswith("lib-"):
                await mode(pg, "list")
            inlines = await pg.evaluate(
                """()=>[...document.querySelectorAll('.card')].filter(visible)
                    .filter(c=>c.querySelector('.cfoot') && !c.dataset.nonmedia)
                    .map(c=>({titre:c.querySelector('.ctitle')?.textContent||'',
                              action:c.querySelector('.cfoot').textContent.trim(),
                              panneau:c.querySelector('.cbody')?.dataset.panel||null}))"""
            )
            for item in inlines:
                executees += 1
                if not item["panneau"]:
                    # R41 already reports this card; going on would only crash
                    # the run and bury both findings under a stack trace.
                    echecs.append(f"R43 {etat} « {item['titre']} »: no panel to compare against")
                    continue
                await pg.evaluate(
                    "(s)=>document.querySelector(`.cbody[data-panel=\"${s.replace(/\"/g,'')}\"]`)?.click()",
                    item["panneau"],
                )
                await pg.wait_for_timeout(420)
                actions = await actions_du_panneau(pg)
                await ferme(pg)
                if actions is None:
                    echecs.append(f"R43 {etat} « {item['titre']} »: the body opened no panel")
                    continue
                # Compared on the first word: the inline button is terser than
                # the panel entry by design (« Résoudre → » against « Résoudre
                # le dossier »), and comparing whole labels would forbid that.
                verbe = item["action"].split()[0].rstrip("→").strip()
                if not any(a.startswith(verbe) for a in actions):
                    echecs.append(
                        f"R43 {etat} « {item['titre']} »: inline « {item['action']} » "
                        f"is offered by no panel action ({actions})"
                    )

        # ---- R45 -------------------------------------------------------
        for etat in ETATS_TUILES:
            await pg.evaluate("(i)=>window.__go(i)", etat)
            await pg.wait_for_timeout(360)
            await mode(pg, "grid")
            refs = await pg.evaluate(
                """()=>[...document.querySelectorAll('.tile[data-panel]')].map(t=>({
                    panneau:t.dataset.panel, nom:t.querySelector('.nm')?.textContent||'',
                    sousLigne:t.querySelector('.fr')?.textContent||''}))"""
            )
            if not refs:
                echecs.append(f"R45 {etat}: no tile declares a panel")
                continue
            executees += 1
            for t in refs:
                ref = t["panneau"].split(":", 1)[1] if ":" in t["panneau"] else ""
                if ref.isdigit() and not t["nom"].strip().isdigit():
                    echecs.append(f"R45 {etat} « {t['nom']} »: panel addressed by index ({t['panneau']})")
                # A sub-line reading « undefined » is what a tile shows when a
                # caller passes the wrong argument — visible, and easy to miss.
                if t["sousLigne"].strip() in ("undefined", "null", "NaN"):
                    echecs.append(f"R45 {etat} « {t['nom']} »: sub-line reads « {t['sousLigne']} »")
            print(f"  R45     {etat:22} {len(refs):3} tiles")

        # ---- R50 -------------------------------------------------------
        # Every gallery draws its tiles with the same builder and the same
        # metrics, and its column count follows the CONTAINER's width. A media
        # query would read the window instead, and a 390px frame on a 1280px
        # desktop would be told it has room for six columns it does not have.
        geometries = {}
        for etat in ETATS_TUILES + ["acq-decouvrir-affiches"]:
            await pg.evaluate("(i)=>window.__go(i)", etat)
            await pg.wait_for_timeout(400)
            await mode(pg, "grid")
            g = await pg.evaluate(
                """()=>{const t=document.querySelector('.tile'); if(!t) return null;
                const grille=t.parentElement, r=t.getBoundingClientRect();
                return {colonnes:getComputedStyle(grille).gridTemplateColumns.split(' ').length,
                        gap:getComputedStyle(grille).gap,
                        tuile:[Math.round(r.width),Math.round(r.height)],
                        nom:getComputedStyle(t.querySelector('.nm')).fontSize,
                        sousLigne:getComputedStyle(t.querySelector('.fr')).fontSize};}"""
            )
            if g is None:
                echecs.append(f"R50 {etat}: no tile at all")
                continue
            geometries[etat] = g
        if len(geometries) < 2:
            echecs.append("R50: fewer than two galleries to compare")
        else:
            executees += 1
            reference = next(iter(geometries.items()))
            for etat, g in geometries.items():
                if g != reference[1]:
                    ecarts = {k: (reference[1][k], v) for k, v in g.items() if v != reference[1][k]}
                    echecs.append(f"R50 {etat} draws a tile unlike {reference[0]}: {ecarts}")
            print(f"  R50     {len(geometries)} galleries, "
                  f"{'one' if all(g == reference[1] for g in geometries.values()) else 'SEVERAL'} metric(s)")

        # The ladder answers the container. Widening the frame must add
        # columns without the window moving at all.
        await pg.evaluate("(i)=>window.__go(i)", "lib-grille")
        await pg.wait_for_timeout(400)
        await mode(pg, "grid")
        echelle = await pg.evaluate(
            """async ()=>{const d=document.querySelector('#device'), out=[];
            const avant=d.style.width;
            for (const w of [390, 500, 700, 900]) {
                d.style.width = w+'px'; d.style.maxWidth = w+'px';
                await new Promise(r=>setTimeout(r,180));
                out.push([Math.round(document.querySelector('#port').getBoundingClientRect().width),
                          getComputedStyle(document.querySelector('.grid')).gridTemplateColumns.split(' ').length]);
            }
            d.style.width = avant; d.style.maxWidth = '';
            return out;}"""
        )
        executees += 1
        colonnes = [n for _, n in echelle]
        if colonnes != sorted(colonnes) or len(set(colonnes)) < 2:
            echecs.append(f"R50 the column ladder does not answer the container: {echelle}")
        else:
            print(f"  R50     container ladder {echelle}")

        # ---- R47 / R48 -------------------------------------------------
        metriques = {}
        tronquees = []
        for etat in ETATS_CARTES:
            await pg.evaluate("(i)=>window.__go(i)", etat)
            await pg.wait_for_timeout(360)
            if etat.startswith("lib-"):
                await mode(pg, "list")
            m = await pg.evaluate(
                """()=>{const c=document.querySelector('.card:not([data-nonmedia])');
                if(!c) return null;
                const p=c.querySelector('.poster'), t=c.querySelector('.ctitle');
                const rp=p.getBoundingClientRect(), cs=getComputedStyle(c);
                return {affiche:Math.round(rp.width),
                        padding:cs.padding, rayon:cs.borderRadius,
                        titre:getComputedStyle(t).fontSize,
                        gap:getComputedStyle(c.querySelector('.ctop')).gap};}"""
            )
            if m:
                metriques[etat] = m
            tronquees += await pg.evaluate(
                """()=>[...document.querySelectorAll('.creason')]
                    .filter(e=>e.scrollHeight>e.clientHeight+1)
                    .map(e=>e.textContent.slice(0,60))"""
            )
        if len(metriques) < 2:
            echecs.append("R47: fewer than two surfaces to compare")
        else:
            executees += 1
            reference = next(iter(metriques.items()))
            for etat, m in metriques.items():
                if m != reference[1]:
                    ecarts = {k: (reference[1][k], v) for k, v in m.items() if v != reference[1][k]}
                    echecs.append(f"R47 {etat} draws a card unlike {reference[0]}: {ecarts}")
            print(f"  R47     {len(metriques)} list surfaces, "
                  f"{'one' if all(m == reference[1] for m in metriques.values()) else 'SEVERAL'} metric(s)")
        # R47 also PINS the size. Checking only that every surface agrees leaves
        # the poster free to be any size at all, as long as it is wrong
        # everywhere — which is how it stayed at 42px, then 49px, while the rule
        # reported conformity. The value is the anatomy notch of the card that
        # EXPLAINS (title, sub-line, reason): 87px of text column, two thirds of
        # it, 58px. Shrinking it back now fails here.
        executees += 1
        largeurs = {m["affiche"] for m in metriques.values()}
        if largeurs != {AFFICHE_LISTE}:
            echecs.append(f"R47 the list poster is not {AFFICHE_LISTE}px: {sorted(largeurs)}")
        else:
            print(f"  R47     the list poster is {AFFICHE_LISTE}px, the notch of the "
                  "card that explains")

        # The poster keeps a poster's RATIO and reaches the card's top and left.
        # Deriving its width from the card's height — which is what a full-height
        # 2:3 poster means — was tried and does not survive contact: a grid sizes
        # an `auto` column before the row's final height is known, so on a 219px
        # card the poster computed 146px against a column of 89 and ran over the
        # text, on 17 states. The sound direction is the other one: the poster's
        # own height is the card's FLOOR, so a card at that floor is bled on
        # three edges and a taller card on two — with the ratio intact
        # everywhere, which is what makes a poster a poster.
        executees += 4
        ratios, colles, marges, chevauche = set(), [], [], []
        for etat in await pg.evaluate("()=>window.__states()"):
            await pg.evaluate("(i)=>window.__go(i)", etat)
            await pg.wait_for_timeout(110)
            vu = await pg.evaluate("""()=>{
              const out = {ratios: [], colles: [], marges: [], chev: []};
              for (const c of document.querySelectorAll('.card')) {
                const p = c.querySelector('.poster');
                if (!p || !p.getBoundingClientRect().width) continue;
                const rp = p.getBoundingClientRect(), rc = c.getBoundingClientRect();
                const titre = (c.querySelector('.ctitle')||{}).textContent || '?';
                out.ratios.push(Math.round(rp.height / rp.width * 100) / 100);
                for (const [bord, ecart] of [['haut', rp.top - rc.top],
                                             ['gauche', rp.left - rc.left],
                                             ['bas', rc.bottom - rp.bottom]])
                  if (Math.abs(ecart) > 1.5)
                    out.colles.push(`${titre} — ${bord} à ${ecart.toFixed(1)}px`);
                const t = c.querySelector('.ctitle');
                if (t) {
                  const rt = t.getBoundingClientRect();
                  if (rt.left < rp.right - 0.5) out.chev.push(titre);
                  else if (rt.left - rp.right < 6) out.marges.push(titre);
                }
              }
              return out;}""")
            ratios |= set(vu["ratios"])
            colles += [f"{etat}: {x}" for x in vu["colles"]]
            marges += [f"{etat}: {x}" for x in vu["marges"]]
            chevauche += [f"{etat}: {x}" for x in vu["chev"]]
        if any(r < 1.45 for r in ratios):
            echecs.append(f"R47 a poster is squatter than 2:3: {sorted(ratios)}")
        else:
            print(f"  R47     no poster is squatter than 2:3 "
                  f"({min(ratios)} to {max(ratios)})")

        # Cropping is BOUNDED, not forbidden. Forbidding it means the poster
        # stops before the card's bottom, which is the defect that was reported;
        # allowing it unbounded turns a busy card's artwork into a strip. The
        # bound is stated here, so a card that grows past it fails instead of
        # quietly shaving the picture. Measured against each image's own natural
        # size, never against the stylesheet.
        executees += 1
        rognees = []
        for etat in await pg.evaluate("()=>window.__states()"):
            await pg.evaluate("(i)=>window.__go(i)", etat)
            await pg.wait_for_timeout(100)
            rognees += await pg.evaluate("""()=>{
              const out = [];
              for (const img of document.querySelectorAll('.card .poster img')) {
                const b = img.getBoundingClientRect();
                if (!b.width || !img.naturalWidth) continue;
                const rs = img.naturalHeight / img.naturalWidth, rb = b.height / b.width;
                const perte = rs > rb ? 1 - rb / rs : 1 - rs / rb;
                if (perte > 0.02)
                  out.push([(img.closest('.card').querySelector('.ctitle')||{})
                              .textContent.slice(0, 24), Math.round(perte * 100)]);
              }
              return out;}""")
        trop = [x for x in rognees if x[1] > 40]
        if trop:
            echecs.append(f"R47 a poster loses more than 40% of its artwork: {trop[:3]}")
        else:
            pire = max((x[1] for x in rognees), default=0)
            print(f"  R47     {len({x[0] for x in rognees})} poster(s) cropped, "
                  f"worst {pire}% — bounded, never stretched")
        if colles:
            echecs.append(f"R47 a poster does not reach the card's edges: {colles[:3]}")
        else:
            print("  R47     and reaches the card's top, left and bottom edge")
        if chevauche:
            echecs.append(f"R47 a poster runs over the title: {chevauche[:3]}")
        else:
            print("  R47     without ever running over the title")
        if marges:
            echecs.append(f"R47 the text column lost its margin: {marges[:3]}")
        else:
            print("  R47     and the text beside it keeps its margin")

        executees += 1
        for texte in tronquees:
            echecs.append(f"R48 a reason is truncated: « {texte}… »")

        # ---- R44 -------------------------------------------------------
        etat, attendue = COMPARAISON
        await pg.evaluate("(i)=>window.__go(i)", etat)
        await pg.wait_for_timeout(360)
        await mode(pg, "grid")
        boite = await pg.evaluate(
            """()=>{const t=document.querySelector('.tile[data-panel]');
            if(!t) return null; const r=t.getBoundingClientRect();
            return {x:r.x+r.width/2, y:r.y+r.height/2, titre:t.querySelector('.nm')?.textContent||''};}"""
        )
        if boite is None:
            echecs.append(f"R44 {etat}: no tile to press")
        else:
            executees += 1
            await pg.mouse.move(boite["x"], boite["y"])
            await pg.mouse.down()
            await pg.wait_for_timeout(660)
            await pg.mouse.up()
            await pg.wait_for_timeout(430)
            depuis_tuile = await actions_du_panneau(pg)
            await ferme(pg)

            await mode(pg, "list")
            await pg.evaluate(
                "(t)=>[...document.querySelectorAll('.card')].find(c=>c.querySelector('.ctitle')?.textContent===t)?.querySelector('.cbody')?.click()",
                boite["titre"],
            )
            await pg.wait_for_timeout(430)
            depuis_carte = await actions_du_panneau(pg)
            await ferme(pg)

            if depuis_tuile is None or depuis_carte is None:
                echecs.append(f"R44 « {boite['titre']} »: one of the two paths opened no panel")
            elif depuis_tuile != depuis_carte:
                echecs.append(
                    f"R44 « {boite['titre']} »: the two paths differ\n"
                    f"       gallery: {depuis_tuile}\n"
                    f"       card   : {depuis_carte}"
                )
            elif attendue not in depuis_tuile:
                echecs.append(
                    f"R44 « {boite['titre']} »: panel lacks « {attendue} » ({depuis_tuile})"
                )
            else:
                print(f"  R44     « {boite['titre']} » identical from both paths, "
                      f"{len(depuis_tuile)} actions")

        # ── ONE ELEMENT, ONE DESTINATION, ACROSS EVERY PAGE ────────────────
        # A poster used to lead to the media sheet on four pages and to the
        # bottom PANEL on Arrivées, where a stuck folder has no sheet to lead
        # to. Same object, same look, two meanings — and a reader cannot learn a
        # rule that holds four times out of five. A folder is not a medium: it
        # wears a FOLDER, which promises the panel and nothing else.
        #
        # Read over every named state, because the divergence lived on one page
        # and a rule reading a single screen would have agreed with it.
        confusions, dossiers = [], 0
        for etat in await pg.evaluate("()=>window.__states()"):
            try:
                await pg.evaluate("(i)=>window.__go(i)", etat)
            except Exception as err:  # noqa: BLE001 — the state itself is the finding
                echecs.append(f"R46: l'état « {etat} » ne se joue pas — {err}")
                continue
            await pg.wait_for_timeout(110)
            vu = await pg.evaluate("""()=>{
              const out = {fautives: [], dossiers: 0};
              // Only a poster one can PRESS makes a promise. A candidate's
              // poster is a picture — a span — and promises nothing at all.
              for (const a of document.querySelectorAll('button.poster')) {
                if (!a.getBoundingClientRect().width) continue;
                if (!a.hasAttribute('data-fiche'))
                  out.fautives.push('affiche pressable sans data-fiche: ' + a.className);
              }
              for (const d of document.querySelectorAll('.folder')) {
                if (!d.getBoundingClientRect().width) continue;
                out.dossiers++;
                if (!d.hasAttribute('data-panel') || d.hasAttribute('data-fiche') ||
                    d.closest('[data-nonmedia="dossier"]') === null)
                  out.fautives.push('dossier mal marqué: ' + d.className);
              }
              return out;}""")
            dossiers += vu["dossiers"]
            confusions += [f"{etat}: {x}" for x in vu["fautives"]]
        executees += 2
        if confusions:
            echecs.append("R46 poster/folder: " + "; ".join(confusions[:3]))
        else:
            print("  R46     a poster leads to the sheet and nowhere else, "
                  "on every state")
        if dossiers == 0:
            echecs.append("R46: no folder drawn anywhere — the rule above is vacuous")
        else:
            print(f"  R46     {dossiers} folder(s) drawn, marked non-media, "
                  "promising the panel")

        if erreurs:
            echecs.append(f"JS errors: {erreurs}")
        await b.close()

    print(f"\n{executees} rule checks EXECUTED · {len(echecs)} failures")
    for e in echecs:
        print(f"  FAIL {e}")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
