"""One card, one behaviour, in every list of the interface.

R41 — a card body opens the bottom PANEL, never a screen of its own.
R42 — a card poster opens the media SHEET, whenever that medium has one.
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

        # ---- R41 / R42 -------------------------------------------------
        for etat in ETATS_CARTES:
            await pg.evaluate("(i)=>window.__go(i)", etat)
            await pg.wait_for_timeout(360)
            if etat.startswith("lib-"):
                await mode(pg, "list")
            releve = await pg.evaluate(
                """()=>[...document.querySelectorAll('.card')].map(c=>{
                    const b=c.querySelector('.cbody');
                    const p=c.querySelector('.poster');
                    return {titre:c.querySelector('.ctitle')?.textContent||'',
                            nonMedia:c.dataset.nonmedia||null,
                            panneau:b?b.dataset.panel||null:null,
                            feuilleDirecte:b?b.dataset.sheet||null:null,
                            posterEstBouton:p?p.tagName==='BUTTON':false,
                            posterVersFiche:p?p.dataset.fiche||null:null,
                            posterInerte:p?p.querySelector('.pfall')!==null:false};})"""
            )
            if not releve:
                echecs.append(f"R41 {etat}: no card at all — the state draws nothing")
                continue
            executees += 3
            for c in releve:
                # R46 — a card that is not a medium says so, and promises
                # neither a sheet nor a panel. A release is one candidate among
                # several for a medium already named on the screen; it has no
                # sheet of its own, and offering one would be a dead promise.
                if c["nonMedia"]:
                    if c["panneau"]:
                        echecs.append(f"R46 {etat} « {c['titre']} »: a {c['nonMedia']} addresses a media panel")
                    if c["posterEstBouton"]:
                        echecs.append(f"R46 {etat} « {c['titre']} »: a {c['nonMedia']} offers a media sheet")
                    continue
                if not c["panneau"]:
                    echecs.append(f"R41 {etat} « {c['titre']} »: the body addresses no panel")
                if c["feuilleDirecte"]:
                    echecs.append(f"R41 {etat} « {c['titre']} »: the body still opens a sheet directly")
                # A poster with no sheet renders as an inert placeholder, not a
                # button — an unidentified medium must not promise a sheet.
                if c["posterEstBouton"] and not c["posterVersFiche"]:
                    echecs.append(f"R42 {etat} « {c['titre']} »: the poster is a button leading nowhere")
                if not c["posterEstBouton"] and not c["posterInerte"]:
                    echecs.append(f"R42 {etat} « {c['titre']} »: no poster at all")
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
                """()=>[...document.querySelectorAll('.card')]
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
                return {affiche:[Math.round(rp.width),Math.round(rp.height)],
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

        if erreurs:
            echecs.append(f"JS errors: {erreurs}")
        await b.close()

    print(f"\n{executees} rule checks EXECUTED · {len(echecs)} failures")
    for e in echecs:
        print(f"  FAIL {e}")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
