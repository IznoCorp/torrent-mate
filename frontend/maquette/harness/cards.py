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
LIST_POSTER = 84  # two thirds of the card's floor, so a card at that floor is 2:3  # the notch of the card that explains; see refonte.html
CARD_STATES = [
    "acq-now-idle",
    "acq-now-loaded",
    "acq-follows-list",
    "acq-follows-groupe",
    "lib-list",
    "lib-incomplete",
    "lib-recent",
    "arr-idle",
    "arr-loaded",
    "arr-resolution",
    "screen-releases",
    "acq-identify",
    "acq-discover",
    "acq-discover-degraded",
    # Search results were absent from this list, and the surface had drifted
    # exactly as far as the absence allowed: its poster box was sized, the
    # image inside it was not, and every thumbnail showed the top-left corner
    # of a 240x360 poster clipped into 54x81.
    "acq-add-results",
]

# States drawing tiles, and how to reach the tile layout from them.
TILE_STATES = ["lib-grid", "lib-incomplete", "lib-recent", "acq-follows-grid"]

# The medium the operator reported: incomplete, and reachable both ways.
COMPARISON = ("lib-incomplete", "Compléter → Acquisitions")


async def mode(pg, which):
    """Forces the library list/grid switch, when the current view has one.

    `__go` does not reset the layout, so a state visited after another inherits
    its mode. Asserting on an inherited mode measures the previous state.

    Args:
        pg: the page.
        which: "list" or "grid".
    """
    await pg.evaluate(
        "(m)=>{const b=document.querySelector(`[data-lmode=\"${m}\"]`); if(b) b.click();}",
        which,
    )
    await pg.wait_for_timeout(320)


async def panel_actions(pg):
    """Returns the labels of the actions in the open panel, or None.

    Returns:
        List of action labels, or None when no panel is open.
    """
    return await pg.evaluate(
        """()=>{const s=document.querySelector('#sheet');
        if(!s||!s.hasAttribute('data-open')) return null;
        return [...s.querySelectorAll('[data-part="sheet/action"]')].map(x=>x.textContent.trim());}"""
    )


async def close_panel(pg):
    """Closes any open panel and waits for the animation to finish."""
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(340)


async def main():
    """Runs R41–R45 and reports how many rules actually executed.

    Returns:
        0 when every rule passed, 1 otherwise.
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
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.goto(URL, wait_until="load")
        await pg.evaluate("()=>window.__measure(true)")
        # A closed screen keeps its markup in the DOM. Cards left behind there
        # are unreachable, so measuring them measures nothing the operator can
        # touch — and it charges one screen's cards to every later state.
        await pg.evaluate(
            "()=>{window.visible = (el)=>el.getClientRects().length > 0;}"
        )

        # ---- R41 / R42 -------------------------------------------------
        for state_ in CARD_STATES:
            await pg.evaluate("(i)=>window.__go(i)", state_)
            await pg.wait_for_timeout(360)
            if state_.startswith("lib-"):
                await mode(pg, "list")
            seen = await pg.evaluate(
                """()=>[...document.querySelectorAll('[data-part="card"]')].filter(visible).map(c=>{
                    const b=c.querySelector('[data-part="card/body"]');
                    const p=c.querySelector('[data-part="card/poster"]');
                    return {title:c.querySelector('[data-part="card/title"]')?.textContent||'',
                            nonMedia:c.dataset.nonmedia||null,
                            panel:b?b.dataset.panel||null:null,
                            directSheet:b?b.dataset.sheet||null:null,
                            posterIsButton:p?p.tagName==='BUTTON':false,
                            posterToSheet:p?p.dataset.mediasheet||null:null,
                            posterToPanel:p?p.dataset.panel||null:null,
                            posterUnknown:p?(p.querySelector('[data-part="card/poster-fallback"] b')||{}).textContent==='?':false};})"""
            )
            if not seen:
                failures.append(f"R41 {state_}: no card at all — the state draws nothing")
                continue
            executed += 3
            for c in seen:
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
                    if c["posterIsButton"]:
                        failures.append(f"R46 {state_} « {c['title']} »: a {c['nonMedia']} offers a media sheet")
                    if c["nonMedia"] == "dossier":
                        if not c["panel"]:
                            failures.append(f"R46 {state_} « {c['title']} »: a folder addresses no panel")
                        elif c["panel"].startswith("media:"):
                            failures.append(f"R46 {state_} « {c['title']} »: a folder addresses a MEDIA panel")
                    elif c["panel"]:
                        failures.append(f"R46 {state_} « {c['title']} »: a {c['nonMedia']} addresses a media panel")
                    continue
                if not c["panel"]:
                    failures.append(f"R41 {state_} « {c['title']} »: the body addresses no panel")
                if c["directSheet"]:
                    failures.append(f"R41 {state_} « {c['title']} »: the body still opens a sheet directly")
                # A poster leads to the SHEET when the medium has one, and to
                # the PANEL when it does not — never nowhere. An unidentified
                # folder still has actions, and « Résoudre → » is what one is
                # after; a dead zone on the page where things are stuck is the
                # worst possible place for one.
                if c["posterIsButton"] and not (c["posterToSheet"] or c["posterToPanel"]):
                    failures.append(f"R42 {state_} « {c['title']} »: the poster is a button leading nowhere")
                if not c["posterIsButton"]:
                    failures.append(f"R42 {state_} « {c['title']} »: the poster is not a control at all")
                # Two DIFFERENT absences, never merged: « ? » says there is no
                # MEDIUM, initials say there is no artwork. A card whose medium
                # is known keeps its sheet even when nothing illustrates it.
                if c["posterUnknown"] and c["posterToSheet"]:
                    failures.append(f"R42 {state_} « {c['title']} »: « ? » over a medium that has a sheet")
                if not c["posterUnknown"] and c["posterToPanel"]:
                    failures.append(f"R42 {state_} « {c['title']} »: an identified poster leading to the panel")
            non_media_count = sum(1 for c in seen if c["nonMedia"])
            print(f"  R41/R42 {state_:22} {len(seen):3} cards"
                  + (f" ({non_media_count} non-media)" if non_media_count else ""))

        # ---- R43 -------------------------------------------------------
        for state_ in CARD_STATES:
            await pg.evaluate("(i)=>window.__go(i)", state_)
            await pg.wait_for_timeout(360)
            if state_.startswith("lib-"):
                await mode(pg, "list")
            inlines = await pg.evaluate(
                """()=>[...document.querySelectorAll('[data-part="card"]')].filter(visible)
                    .filter(c=>c.querySelector('[data-part="card/foot"]') && !c.dataset.nonmedia)
                    .map(c=>({title:c.querySelector('[data-part="card/title"]')?.textContent||'',
                              action:c.querySelector('[data-part="card/foot"]').textContent.trim(),
                              panel:c.querySelector('[data-part="card/body"]')?.dataset.panel||null}))"""
            )
            for item in inlines:
                executed += 1
                if not item["panel"]:
                    # R41 already reports this card; going on would only crash
                    # the run and bury both findings under a stack trace.
                    failures.append(f"R43 {state_} « {item['title']} »: no panel to compare against")
                    continue
                await pg.evaluate(
                    """(s)=>document.querySelector(`[data-part="card/body"][data-panel="${s.replace(/"/g,'')}"]`)?.click()""",
                    item["panel"],
                )
                await pg.wait_for_timeout(420)
                actions = await panel_actions(pg)
                await close_panel(pg)
                if actions is None:
                    failures.append(f"R43 {state_} « {item['title']} »: the body opened no panel")
                    continue
                # Compared on the first word: the inline button is terser than
                # the panel entry by design (« Résoudre → » against « Résoudre
                # le dossier »), and comparing whole labels would forbid that.
                verb = item["action"].split()[0].rstrip("→").strip()
                if not any(a.startswith(verb) for a in actions):
                    failures.append(
                        f"R43 {state_} « {item['title']} »: inline « {item['action']} » "
                        f"is offered by no panel action ({actions})"
                    )

        # ---- R45 -------------------------------------------------------
        for state_ in TILE_STATES:
            await pg.evaluate("(i)=>window.__go(i)", state_)
            await pg.wait_for_timeout(360)
            await mode(pg, "grid")
            refs = await pg.evaluate(
                """()=>[...document.querySelectorAll('[data-part="tile"][data-panel]')].map(t=>({
                    panel:t.dataset.panel, name:t.querySelector('[data-part="tile/title"]')?.textContent||'',
                    subLine:t.querySelector('[data-part="tile/subtitle"]')?.textContent||''}))"""
            )
            if not refs:
                failures.append(f"R45 {state_}: no tile declares a panel")
                continue
            executed += 1
            for t in refs:
                ref = t["panel"].split(":", 1)[1] if ":" in t["panel"] else ""
                if ref.isdigit() and not t["name"].strip().isdigit():
                    failures.append(f"R45 {state_} « {t['name']} »: panel addressed by index ({t['panel']})")
                # A sub-line reading « undefined » is what a tile shows when a
                # caller passes the wrong argument — visible, and easy to miss.
                if t["subLine"].strip() in ("undefined", "null", "NaN"):
                    failures.append(f"R45 {state_} « {t['name']} »: sub-line reads « {t['subLine']} »")
            print(f"  R45     {state_:22} {len(refs):3} tiles")

        # ---- R50 -------------------------------------------------------
        # Every gallery draws its tiles with the same builder and the same
        # metrics, and its column count follows the CONTAINER's width. A media
        # query would read the window instead, and a 390px frame on a 1280px
        # desktop would be told it has room for six columns it does not have.
        geometries = {}
        for state_ in TILE_STATES + ["acq-discover-posters"]:
            await pg.evaluate("(i)=>window.__go(i)", state_)
            await pg.wait_for_timeout(400)
            await mode(pg, "grid")
            g = await pg.evaluate(
                """()=>{const t=document.querySelector('[data-part="tile"]'); if(!t) return null;
                const grid=t.parentElement, r=t.getBoundingClientRect();
                return {columns:getComputedStyle(grid).gridTemplateColumns.split(' ').length,
                        gap:getComputedStyle(grid).gap,
                        tile:[Math.round(r.width),Math.round(r.height)],
                        name:getComputedStyle(t.querySelector('[data-part="tile/title"]')).fontSize,
                        subLine:getComputedStyle(t.querySelector('[data-part="tile/subtitle"]')).fontSize};}"""
            )
            if g is None:
                failures.append(f"R50 {state_}: no tile at all")
                continue
            geometries[state_] = g
        if len(geometries) < 2:
            failures.append("R50: fewer than two galleries to compare")
        else:
            executed += 1
            reference = next(iter(geometries.items()))
            for state_, g in geometries.items():
                if g != reference[1]:
                    gaps = {k: (reference[1][k], v) for k, v in g.items() if v != reference[1][k]}
                    failures.append(f"R50 {state_} draws a tile unlike {reference[0]}: {gaps}")
            print(f"  R50     {len(geometries)} galleries, "
                  f"{'one' if all(g == reference[1] for g in geometries.values()) else 'SEVERAL'} metric(s)")

        # The ladder answers the container. Widening the frame must add
        # columns without the window moving at all.
        await pg.evaluate("(i)=>window.__go(i)", "lib-grid")
        await pg.wait_for_timeout(400)
        await mode(pg, "grid")
        ladder = await pg.evaluate(
            """async ()=>{const d=document.querySelector('#device'), out=[];
            const before=d.style.width;
            for (const w of [390, 500, 700, 900]) {
                d.style.width = w+'px'; d.style.maxWidth = w+'px';
                await new Promise(r=>setTimeout(r,180));
                out.push([Math.round(document.querySelector('#port').getBoundingClientRect().width),
                          getComputedStyle(document.querySelector('[data-part="grid"]')).gridTemplateColumns.split(' ').length]);
            }
            d.style.width = before; d.style.maxWidth = '';
            return out;}"""
        )
        executed += 1
        columns = [n for _, n in ladder]
        if columns != sorted(columns) or len(set(columns)) < 2:
            failures.append(f"R50 the column ladder does not answer the container: {ladder}")
        else:
            print(f"  R50     container ladder {ladder}")

        # ---- R47 / R48 -------------------------------------------------
        metrics = {}
        truncated = []
        for state_ in CARD_STATES:
            await pg.evaluate("(i)=>window.__go(i)", state_)
            await pg.wait_for_timeout(360)
            if state_.startswith("lib-"):
                await mode(pg, "list")
            m = await pg.evaluate(
                """()=>{const c=document.querySelector('[data-part="card"]:not([data-nonmedia])');
                if(!c) return null;
                const p=c.querySelector('[data-part="card/poster"]'), t=c.querySelector('[data-part="card/title"]');
                const rp=p.getBoundingClientRect(), cs=getComputedStyle(c);
                return {poster:Math.round(rp.width),
                        padding:cs.padding, radius:cs.borderRadius,
                        title:getComputedStyle(t).fontSize,
                        gap:getComputedStyle(c.querySelector('[data-part="card/top"]')).gap};}"""
            )
            if m:
                metrics[state_] = m
            truncated += await pg.evaluate(
                """()=>[...document.querySelectorAll('[data-part="card/reason"]')]
                    .filter(e=>e.scrollHeight>e.clientHeight+1)
                    .map(e=>e.textContent.slice(0,60))"""
            )
        if len(metrics) < 2:
            failures.append("R47: fewer than two surfaces to compare")
        else:
            executed += 1
            reference = next(iter(metrics.items()))
            for state_, m in metrics.items():
                if m != reference[1]:
                    gaps = {k: (reference[1][k], v) for k, v in m.items() if v != reference[1][k]}
                    failures.append(f"R47 {state_} draws a card unlike {reference[0]}: {gaps}")
            print(f"  R47     {len(metrics)} list surfaces, "
                  f"{'one' if all(m == reference[1] for m in metrics.values()) else 'SEVERAL'} metric(s)")
        # R47 also PINS the size. Checking only that every surface agrees leaves
        # the poster free to be any size at all, as long as it is wrong
        # everywhere — which is how it stayed at 42px, then 49px, while the rule
        # reported conformity. The value is the anatomy notch of the card that
        # EXPLAINS (title, sub-line, reason): 87px of text column, two thirds of
        # it, 58px. Shrinking it back now fails here.
        executed += 1
        widths = {m["poster"] for m in metrics.values()}
        if widths != {LIST_POSTER}:
            failures.append(f"R47 the list poster is not {LIST_POSTER}px: {sorted(widths)}")
        else:
            print(f"  R47     the list poster is {LIST_POSTER}px, the notch of the "
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
        executed += 4
        ratios, flush, margins, overlaps = set(), [], [], []
        for state_ in await pg.evaluate("()=>window.__states()"):
            await pg.evaluate("(i)=>window.__go(i)", state_)
            await pg.wait_for_timeout(110)
            seen_state = await pg.evaluate("""()=>{
              const out = {ratios: [], flush: [], margins: [], overlap: []};
              for (const c of document.querySelectorAll('[data-part="card"]')) {
                const p = c.querySelector('[data-part="card/poster"]');
                if (!p || !p.getBoundingClientRect().width) continue;
                const rp = p.getBoundingClientRect(), rc = c.getBoundingClientRect();
                const title = (c.querySelector('[data-part="card/title"]')||{}).textContent || '?';
                out.ratios.push(Math.round(rp.height / rp.width * 100) / 100);
                for (const [edge, gap] of [['top', rp.top - rc.top],
                                           ['left', rp.left - rc.left],
                                           ['bottom', rc.bottom - rp.bottom]])
                  if (Math.abs(gap) > 1.5)
                    out.flush.push(`${title} — ${edge} at ${gap.toFixed(1)}px`);
                const t = c.querySelector('[data-part="card/title"]');
                if (t) {
                  const rt = t.getBoundingClientRect();
                  if (rt.left < rp.right - 0.5) out.overlap.push(title);
                  else if (rt.left - rp.right < 6) out.margins.push(title);
                }
              }
              return out;}""")
            ratios |= set(seen_state["ratios"])
            flush += [f"{state_}: {x}" for x in seen_state["flush"]]
            margins += [f"{state_}: {x}" for x in seen_state["margins"]]
            overlaps += [f"{state_}: {x}" for x in seen_state["overlap"]]
        if any(r < 1.45 for r in ratios):
            failures.append(f"R47 a poster is squatter than 2:3: {sorted(ratios)}")
        else:
            print(f"  R47     no poster is squatter than 2:3 "
                  f"({min(ratios)} to {max(ratios)})")

        # Cropping is BOUNDED, not forbidden. Forbidding it means the poster
        # stops before the card's bottom, which is the defect that was reported;
        # allowing it unbounded turns a busy card's artwork into a strip. The
        # bound is stated here, so a card that grows past it fails instead of
        # quietly shaving the picture. Measured against each image's own natural
        # size, never against the stylesheet.
        executed += 1
        cropped = []
        for state_ in await pg.evaluate("()=>window.__states()"):
            await pg.evaluate("(i)=>window.__go(i)", state_)
            await pg.wait_for_timeout(100)
            cropped += await pg.evaluate("""()=>{
              const out = [];
              for (const img of document.querySelectorAll('[data-part="card"] [data-part="card/poster"] img')) {
                const b = img.getBoundingClientRect();
                if (!b.width || !img.naturalWidth) continue;
                const rs = img.naturalHeight / img.naturalWidth, rb = b.height / b.width;
                const loss = rs > rb ? 1 - rb / rs : 1 - rs / rb;
                if (loss > 0.02)
                  out.push([(img.closest('[data-part="card"]').querySelector('[data-part="card/title"]')||{})
                              .textContent.slice(0, 24), Math.round(loss * 100)]);
              }
              return out;}""")
        too_much = [x for x in cropped if x[1] > 40]
        if too_much:
            failures.append(f"R47 a poster loses more than 40% of its artwork: {too_much[:3]}")
        else:
            worst = max((x[1] for x in cropped), default=0)
            print(f"  R47     {len({x[0] for x in cropped})} poster(s) cropped, "
                  f"worst {worst}% — bounded, never stretched")
        if flush:
            failures.append(f"R47 a poster does not reach the card's edges: {flush[:3]}")
        else:
            print("  R47     and reaches the card's top, left and bottom edge")
        if overlaps:
            failures.append(f"R47 a poster runs over the title: {overlaps[:3]}")
        else:
            print("  R47     without ever running over the title")
        if margins:
            failures.append(f"R47 the text column lost its margin: {margins[:3]}")
        else:
            print("  R47     and the text beside it keeps its margin")

        executed += 1
        for text in truncated:
            failures.append(f"R48 a reason is truncated: « {text}… »")

        # ---- R44 -------------------------------------------------------
        state_, expected = COMPARISON
        await pg.evaluate("(i)=>window.__go(i)", state_)
        await pg.wait_for_timeout(360)
        await mode(pg, "grid")
        box = await pg.evaluate(
            """()=>{const t=document.querySelector('[data-part="tile"][data-panel]');
            if(!t) return null; const r=t.getBoundingClientRect();
            return {x:r.x+r.width/2, y:r.y+r.height/2, title:t.querySelector('[data-part="tile/title"]')?.textContent||''};}"""
        )
        if box is None:
            failures.append(f"R44 {state_}: no tile to press")
        else:
            executed += 1
            await pg.mouse.move(box["x"], box["y"])
            await pg.mouse.down()
            await pg.wait_for_timeout(660)
            await pg.mouse.up()
            await pg.wait_for_timeout(430)
            from_tile = await panel_actions(pg)
            await close_panel(pg)

            await mode(pg, "list")
            await pg.evaluate(
                """(t)=>[...document.querySelectorAll('[data-part="card"]')].find(c=>c.querySelector('[data-part="card/title"]')?.textContent===t)?.querySelector('[data-part="card/body"]')?.click()""",
                box["title"],
            )
            await pg.wait_for_timeout(430)
            from_card = await panel_actions(pg)
            await close_panel(pg)

            if from_tile is None or from_card is None:
                failures.append(f"R44 « {box['title']} »: one of the two paths opened no panel")
            elif from_tile != from_card:
                failures.append(
                    f"R44 « {box['title']} »: the two paths differ\n"
                    f"       gallery: {from_tile}\n"
                    f"       card   : {from_card}"
                )
            elif expected not in from_tile:
                failures.append(
                    f"R44 « {box['title']} »: panel lacks « {expected} » ({from_tile})"
                )
            else:
                print(f"  R44     « {box['title']} » identical from both paths, "
                      f"{len(from_tile)} actions")

        # ── ONE ELEMENT, ONE DESTINATION, ACROSS EVERY PAGE ────────────────
        # A poster used to lead to the media sheet on four pages and to the
        # bottom PANEL on Arrivées, where a stuck folder has no sheet to lead
        # to. Same object, same look, two meanings — and a reader cannot learn a
        # rule that holds four times out of five. A folder is not a medium: it
        # wears a FOLDER, which promises the panel and nothing else.
        #
        # Read over every named state, because the divergence lived on one page
        # and a rule reading a single screen would have agreed with it.
        confusions, folders = [], 0
        for state_ in await pg.evaluate("()=>window.__states()"):
            try:
                await pg.evaluate("(i)=>window.__go(i)", state_)
            except Exception as err:  # noqa: BLE001 — the state itself is the finding
                failures.append(f"R46: state « {state_} » cannot be played — {err}")
                continue
            await pg.wait_for_timeout(110)
            seen_state = await pg.evaluate("""()=>{
              const out = {offending: [], folders: 0};
              // Only a poster one can PRESS makes a promise. A candidate's
              // poster is a picture — a span — and promises nothing at all.
              for (const a of document.querySelectorAll('button[data-part="card/poster"]')) {
                if (!a.getBoundingClientRect().width) continue;
                if (!a.hasAttribute('data-mediasheet'))
                  out.offending.push('pressable poster with no data-mediasheet: ' + a.className);
              }
              for (const d of document.querySelectorAll('[data-part="card/folder"]')) {
                if (!d.getBoundingClientRect().width) continue;
                out.folders++;
                if (!d.hasAttribute('data-panel') || d.hasAttribute('data-mediasheet') ||
                    d.closest('[data-nonmedia="dossier"]') === null)
                  out.offending.push('folder badly marked: ' + d.className);
              }
              return out;}""")
            folders += seen_state["folders"]
            confusions += [f"{state_}: {x}" for x in seen_state["offending"]]
        executed += 2
        if confusions:
            failures.append("R46 poster/folder: " + "; ".join(confusions[:3]))
        else:
            print("  R46     a poster leads to the sheet and nowhere else, "
                  "on every state")
        if folders == 0:
            failures.append("R46: no folder drawn anywhere — the rule above is vacuous")
        else:
            print(f"  R46     {folders} folder(s) drawn, marked non-media, "
                  "promising the panel")

        if errors:
            failures.append(f"JS errors: {errors}")
        await b.close()

    print(f"\n{executed} rule checks EXECUTED · {len(failures)} failures")
    for e in failures:
        print(f"  FAIL {e}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
