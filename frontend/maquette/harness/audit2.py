"""Second adversarial pass — uniformity, consistency, honesty of the text.
Aimed at what a screenshot does not show.
"""
import asyncio, json
from playwright.async_api import async_playwright
BAR="─"*62

async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>window.__measure(true)")
    etats=await pg.evaluate("()=>window.__states()")
    viol={}
    def note(r,d): viol.setdefault(r,[]).append(d)

    # Same requirement as the first pass: count the rules EXECUTED, so an
    # audit that has gone mute no longer reads as a green audit.
    evaluees=set()
    def evalue(*r): evaluees.update(r)
    REGLES_ATTENDUES=13
    print(f"{BAR}\nAdversarial review, second pass — {len(etats)} states\n{BAR}")

    evalue('R11')
    # R11 — jargon, technical values and machine English in rendered text
    for e in etats:
        await pg.evaluate("(i)=>window.__go(i)",e); await pg.wait_for_timeout(240)
        bad=await pg.evaluate("""()=>{
          const r=document.querySelector('#dlg').classList.contains('open')?'#dlg'
                 :document.querySelector('#screen').classList.contains('open')?'#screen'
                 :document.querySelector('#sheet').classList.contains('open')?'#sheet':'#view';
          const t=document.querySelector(r).innerText;
          const motifs=[[/\\bundefined\\b/,'undefined'],[/\\bNaN\\b/,'NaN'],[/\\bnull\\b/,'null'],
            [/\\[object /,'[object'],[/\\b0\\/0\\b/,'0/0'],[/\\*\\s\\*\\s\\*/,'expression cron'],
            [/\\bError\\b/,'Error'],[/\\bTrue\\b|\\bFalse\\b/,'raw boolean']];
          return motifs.filter(([re])=>re.test(t)).map(([,n])=>n);}""")
        for x in bad: note("R11 visible jargon or technical value", f"{e} : {x}")

    evalue('R12')
    # R12 — uniformity of the primary action buttons
    geo=await pg.evaluate("""async ()=>{
      const out={};
      const mesure=(sel,nom)=>{const el=document.querySelector(sel); if(!el) return;
        const s=getComputedStyle(el); const b=el.getBoundingClientRect();
        out[nom]={h:Math.round(b.height),poids:s.fontWeight,taille:s.fontSize,centre:s.justifyContent,
                  radius:s.borderRadius,icone:!!el.querySelector(':scope > svg')};};
      window.__go('acq-encours-charge'); await new Promise(r=>setTimeout(r,220));
      mesure('.cfoot.solid','card footer (primary)');
      window.__go('feuille-suivi-trous'); await new Promise(r=>setTimeout(r,240));
      mesure('.sact.primary','sheet (primary)');
      window.__go('fiche-suggestion-film'); await new Promise(r=>setTimeout(r,240));
      mesure('.ficheadd','media sheet (add)');
      window.__go('acq-ajout-resultats'); await new Promise(r=>setTimeout(r,240));
      mesure('.resbtn','search result');
      window.__go('lib-suppression'); await new Promise(r=>setTimeout(r,240));
      mesure('.dlgbtn.danger','dialog (danger)');
      return out;}""")
    print("Primary button geometry:")
    for k,v in geo.items(): print(f"   {k:26} {v}")
    hs=[v["h"] for v in geo.values()]
    if max(hs)-min(hs) > 2: note("R12 inconsistent button heights", f"{min(hs)}–{max(hs)} px : {json.dumps(geo,ensure_ascii=False)}")
    for k,v in geo.items():
        # « normal » is NOT centred: rule slackness of that kind let a real
        # misalignment through. Rule: with an icon → left-aligned; without →
        # centred.
        attendu = "flex-start" if v.get("icone") else "center"
        if v["centre"] != attendu:
            note("R12 non-conformant alignment", f"{k}: {v['centre']} instead of {attendu} (icon: {v.get('icone')})")
        if v["radius"] != "8px": note("R12 inconsistent radius", f"{k} : {v['radius']}")
        if v["taille"] != "13.5px": note("R12 inconsistent text size", f"{k} : {v['taille']}")

    evalue('R13')
    # R13 — sheet uniformity: the SAME BASE for all of them.
    #
    # Sampling a handful of fixed states, none of them an INCOMPLETE medium,
    # is exactly how a divergence slips through unseen. The sample is
    # therefore drawn from the DATA: complete, incomplete, without visual,
    # suggestion, film and series.
    ordres=await pg.evaluate("""async ()=>{
      const out={}, choix=[];
      const titres=Object.keys(FICHES_RAW ?? {});
      const prend=(pred, n)=>titres.filter(pred).slice(0, n);
      const incomplet=(t)=>{const s=POSSEDES[t]??POSSEDES[baseTitle(t)];
        if(!s) return false; const f=fiche(t); if(!f?.saisons) return false;
        return f.saisons.some(x=>x.ep && (s[String(x.n)]??[]).length < x.ep);};
      choix.push(...prend(t=>fiche(t)?.k==='movie', 2));
      choix.push(...prend(t=>fiche(t)?.k==='show' && !incomplet(t), 2));
      choix.push(...prend(incomplet, 4));
      choix.push(...prend(t=>!(HEROS[t]??HEROS[baseTitle(t)]), 2));
      for (const t of [...new Set(choix)]) {
        window.__reset(); set({page:'lib', phase:'prete'}); openFiche(t);
        await new Promise(r=>setTimeout(r,200));
        const b=document.querySelector('#screen .body');
        if (!b) { out[t]=['FICHE VIDE']; continue; }
        out[t]=[...b.children]
          .filter(x=>x.getBoundingClientRect().height>0 && !x.classList.contains('note'))
          .map(x=>{const hh=x.querySelector('.h2');
            return hh ? hh.textContent.trim() : (x.className||x.tagName).toString().split(' ')[0];});
      }
      return out;}""")
    print(f"\nMedia-sheet base, over {len(ordres)} media drawn from the data:")
    # Sections that are OPTIONAL by nature (no trailer, unknown catalogue) do
    # not count as divergence; the skeleton does.
    OPT = {"trailer", "nofiche", "rulenote"}
    def ossature(l):
        return [s.replace("Création", "X").replace("Réalisation", "X") for s in l if s not in OPT]
    formes = {}
    for k, v in ordres.items():
        formes.setdefault(tuple(ossature(v)), []).append(k)
    for f, l in formes.items():
        print(f"   {len(l):2d} media · {' → '.join(f)}")
    if len(formes) > 1:
        ref = max(formes.items(), key=lambda kv: len(kv[1]))[0]
        for f, l in formes.items():
            if f != ref:
                note("R13 sheet not following the common base",
                     f"{', '.join(l[:3])} : {' → '.join(f)} au lieu de {' → '.join(ref)}")

    evalue('R14')
    # R14 — every layer closes via the scrim AND via Back
    for id_,sel in [("feuille-suivi-trous","#sheet"),("lib-suppression","#dlg"),("fiche-serie","#screen"),("acq-ajout-resultats","#screen")]:
        await pg.evaluate("(i)=>window.__go(i)",id_); await pg.wait_for_timeout(300)
        ouvert=await pg.evaluate("(s)=>document.querySelector(s).classList.contains('open')",sel)
        if sel!="#screen":
            await pg.evaluate("()=>document.querySelector('#scrim').click()"); await pg.wait_for_timeout(300)
            if await pg.evaluate("(s)=>document.querySelector(s).classList.contains('open')",sel):
                note("R14 layer not closable via the scrim", f"{id_}")
        else:
            await pg.evaluate("()=>document.querySelector('#screen .fback').click()"); await pg.wait_for_timeout(350)
            if await pg.evaluate("()=>document.querySelector('#screen').classList.contains('open')"):
                note("R14 screen not closable via Back", f"{id_}")
        if not ouvert: note("R14 layer that does not open", id_)

    evalue('R15')
    # R15 — the three Suivis modes show the SAME number of items
    n=await pg.evaluate("""async ()=>{const o={};
      for (const m of ['acq-suivis-liste','acq-suivis-groupe','acq-suivis-grille']) {
        window.__go(m); await new Promise(r=>setTimeout(r,240));
        o[m]=document.querySelectorAll('#view .card, #view .tile').length;}
      return o;}""")
    print("\nItems per Suivis mode:", n)
    if len(set(n.values()))>1: note("R15 inconsistent Suivis modes", json.dumps(n))

    evalue('R16')
    # R16 — the badge is the sum it claims to be
    bad=await pg.evaluate("""async ()=>{const out=[];
      for (const s of ['reel','charge']) { S.scen=s; window.__go('acq-encours-'+(s==='reel'?'repos':'charge'));
        await new Promise(r=>setTimeout(r,240));
        const badge=document.querySelector('[data-page=acq] .navbadge');
        const attendu=D.takeable().length+D.blocked().length;
        const lu=badge?Number(badge.textContent):0;
        if (lu!==attendu) out.push(`${s}: badge ${lu} != to-grab+to-resolve ${attendu}`);
        const onglet=document.querySelector('.seg .n');
        const lu2=onglet?Number(onglet.textContent):0;
        if (lu2!==attendu) out.push(`${s}: tab badge ${lu2} != ${attendu}`);
      } return out;}""")
    for x in bad: note("R16 badge not derived", x)

    evalue('R17')
    # R17 — every destructive mutation is confirmed or reversible
    rev=await pg.evaluate("""async ()=>{const out=[];
      window.__go('acq-suivis-liste'); await new Promise(r=>setTimeout(r,240));
      document.querySelector('#view .swipe .act.remove').click(); await new Promise(r=>setTimeout(r,320));
      if (!document.querySelector('#toastundo')) out.push('removing a follow: no undo');
      window.__go('lib-liste'); await new Promise(r=>setTimeout(r,260));
      const av=W.lib.length;
      document.querySelector('#libitems .swipe .act.remove').click(); await new Promise(r=>setTimeout(r,320));
      if (!document.querySelector('#dlg').classList.contains('open')) out.push('deleting a medium: no confirmation');
      if (W.lib.length!==av) out.push('deleting a medium: mutation BEFORE confirmation');
      return out;}""")
    for x in rev: note("R17 destruction without a guard", x)

    evalue('R26')
    # R26 — the melting visual header is a trait of ALL media sheets, not only
    # the ones that were looked at. The rule is conditional and says so: a
    # medium WITHOUT a visual degrades to a flat field (a difference justified
    # by its own context). A medium WITH a visual that has no header signals a
    # second rendering path that was never converted.
    fonds=await pg.evaluate("""async ()=>{const out=[];
      const racineDoc=document.documentElement;
      // BOTH THEMES. An orphan selector left by a deletion gave the header
      // position:absolute in the light theme only: the sheet was upside down,
      // and the rule looked at the dark theme alone.
      for (const theme of [null,'light']) {
        theme ? racineDoc.setAttribute('data-theme',theme) : racineDoc.removeAttribute('data-theme');
        for (const s of window.__states()) {
          window.__go(s); await new Promise(r=>setTimeout(r,300));
          const racine=document.querySelector('#screen.open, #sheet.open');
          const hero=racine && racine.querySelector('.hero');
          if (!hero) continue;
          const nom=`${s}/${theme||'sombre'}`;
          const wrap=hero.closest('.herowrap');
          if (!wrap) { out.push(`${nom}: sheet without .herowrap`); continue; }
          const bg=wrap.querySelector('.herobg');
          if (!bg) { out.push(`${nom}: sheet without a header`); continue; }
          const sb=getComputedStyle(bg), rb=bg.getBoundingClientRect(), rh=hero.getBoundingClientRect();
          // The header OCCUPIES the top: it pushes content, it does not float.
          if (sb.position!=='relative') out.push(`${nom}: header in ${sb.position}`);
          const aVisuelIci=!wrap.classList.contains('noaffiche');
          // With no visual the field is deliberately short: it holds the place
          // and claims nothing. The threshold applies only to a real image.
          const seuil = aVisuelIci ? 240 : 48;
          if (rb.height < seuil)
            out.push(`${nom} : bandeau haut de ${Math.round(rb.height)}px (< ${seuil})`);
          // The title sits UNDER the image, overlapping its lower edge.
          if (rh.top <= rb.top) out.push(`${nom}: title above the header`);
          if (rh.top >= rb.bottom) out.push(`${nom}: title detached from the header`);
          // Text NEVER rests on the bare image: the closing gradient is what
          // makes the rule true, not good intentions.
          if (!getComputedStyle(bg,'::after').backgroundImage.includes('gradient'))
            out.push(`${nom}: header without a legibility gradient`);
          const aVisuel=!wrap.classList.contains('noaffiche');
          if (aVisuel && sb.backgroundImage==='none') out.push(`${nom}: header declared but empty`);
        }
      }
      racineDoc.removeAttribute('data-theme');
      return out;}""")
    for x in fonds: note("R26 visual header not generalised", x)

    evalue('R27')
    # R27 — a trailer ALWAYS opens in YouTube, never inside the application,
    # and the sheet offers it wherever one arrives from: library, acquisitions
    # or Découvrir. The rule carries that decision: a sheet promising in-app
    # playback would be wrong even if it were pretty.
    bandes=await pg.evaluate("""async ()=>{const out=[];
      for (const s of window.__states()) {
        window.__go(s); await new Promise(r=>setTimeout(r,300));
        const racine=document.querySelector('#screen.open, #sheet.open');
        if (!racine || !racine.querySelector('.hero')) continue;
        const el=racine.querySelector('.trailer');
        if (!el) continue;                       // declared absence: stated elsewhere
        if (el.tagName!=='A') { out.push(`${s}: trailer as <${el.tagName}>, not a link`); continue; }
        const href=el.getAttribute('href')||'';
        if (!/^https:\\/\\/www\\.youtube\\.com\\/watch\\?v=[\\w-]{6,}$/.test(href))
          out.push(`${s}: non-conformant href « ${href.slice(0,48)} »`);
        if (el.getAttribute('target')!=='_blank') out.push(`${s}: the link does not leave the app`);
        if (!(el.getAttribute('rel')||'').includes('noopener')) out.push(`${s}: outbound link without noopener`);
        if (/lecture ici|plein écran|dans l.app/i.test(el.textContent+(el.dataset.toast||'')))
          out.push(`${s}: promises in-app playback`);
      } return out;}""")
    for x in bandes: note("R27 trailer not conformant", x)

    evalue('R28')
    # R28 — there must be exactly ONE back-control design, compatible with
    # every page. A floating white bar over the image created a second design
    # which, on screens without an image, COVERED the title instead of pushing
    # it. The rule measures both things: a single signature, and never content
    # glued or covered.
    retours=await pg.evaluate("""async ()=>{const sig={}, colles=[];
      for (const s of window.__states()) {
        window.__go(s); await new Promise(r=>setTimeout(r,300));
        const bar=document.querySelector('#screen.open .fichebar');
        if (!bar) continue;
        const btn=bar.querySelector('.fback');
        if (!btn) { colles.push(`${s}: bar without a back control`); continue; }
        const sb=getComputedStyle(bar), sx=getComputedStyle(btn), rb=bar.getBoundingClientRect();
        // A bar outside the flow pushes nothing: it ends up covering.
        if (sb.position!=='static' && sb.position!=='relative')
          colles.push(`${s}: bar in ${sb.position} — it does not push content`);
        const k=[sb.position, sb.backgroundColor, sx.color, Math.round(rb.height)].join('|');
        (sig[k] ||= []).push(s);
        // Measure the first PIXEL OF TEXT, not the first box: a container can
        // touch the bar through its padding without anything being glued.
        const port=document.querySelector('#screen .port');
        const texte=port && [...port.querySelectorAll('h1,h2,h3,p,span,button,a,label')]
          .find(e=>{const r=e.getBoundingClientRect();
                    return r.height>0 && (e.textContent||'').trim().length>1 && !e.closest('.note');});
        if (texte) {
          const ecart=texte.getBoundingClientRect().top-rb.bottom;
          if (ecart < 8) colles.push(`${s}: text ${Math.round(ecart)}px from the bar`);
        }
      }
      return {sig, colles};}""")
    if len(retours["sig"]) > 1:
        for k, l in retours["sig"].items():
            note("R28 several back-control designs", f"{k} → {', '.join(l[:4])}")
    for x in retours["colles"]: note("R28 back control badly placed", x)
    print(f"\nDistinct back-control designs: {len(retours['sig'])} across "
          f"{sum(len(v) for v in retours['sig'].values())} screens")

    evalue('R29')
    # R29 — episode presence is read from the LIST of owned numbers, never
    # from a « number <= owned count » threshold. That threshold assumes the
    # hole is at the end of the season: false for 35 series in this library.
    # The rule checks agreement between what is DISPLAYED and the data, on
    # series with an INTERNAL hole — where the two methods diverge.
    ep=await pg.evaluate("""async ()=>{const out=[];
      // ALL series with an INTERNAL hole, not a sample: that is where the
      // threshold and the list diverge, so that is where the rule has a chance
      // to bite.
      const atrous=Object.entries(POSSEDES).filter(([t,s])=>
        Object.values(s).some(l=>l.length && l.some((n,i)=>n!==i+1))).map(([t])=>t);
      if (!atrous.length) return ['no series with an internal hole — the rule would be vacuous'];
      let inspectes=0;
      for (const titre of atrous) {
        window.__reset(); set({page:'lib', phase:'prete'}); openFiche(titre);
        await new Promise(r=>setTimeout(r,160));
        for (const det of document.querySelectorAll('#screen details.season')) {
          const num=Number((det.querySelector('summary')?.textContent||'').match(/Saison\\s+(\\d+)/)?.[1]);
          const detenus=possedesDe(titre, num);
          if (!detenus) continue;
          // BOTH renderings: titled rows AND the numbered matrix.
          const cases=[...det.querySelectorAll('.eprow')].map(r=>[
              Number((r.querySelector('.en')?.textContent||'').replace(/\\D/g,'')), r])
            .concat([...det.querySelectorAll('.eps .ep')].map(c=>[Number(c.textContent), c]));
          for (const [n, el] of cases) {
            if (!n || el.classList.contains('annonce')) continue;
            inspectes++;
            const affiche=el.classList.contains('en_mediatheque');
            if (affiche !== detenus.has(n))
              out.push(`${titre} S${num}E${n}: shown ${affiche?'present':'missing'}, actually ${detenus.has(n)?'present':'missing'}`);
          }
        }
      }
      if (!inspectes) out.push('no episode inspected — the rule proves nothing');
      return out.slice(0, 12);}""")
    for x in ep: note("R29 episode presence not matching the data", x)

    evalue('R30')
    # R30 — ONE season rendering. Two existed: a titled list (29 series) and a
    # numbered matrix (177), and twelve sheets contained both at once. A sheet
    # must not have two faces depending on the data it happens to have.
    rendus=await pg.evaluate("""async ()=>{const c={lignes:[], matrice:[], mixte:[]};
      const series=Object.keys(FICHES_RAW).filter(t=>fiche(t)?.k!=='movie');
      for (const t of series) {
        window.__reset(); set({page:'lib',phase:'prete'}); openFiche(t);
        await new Promise(r=>setTimeout(r,35));
        const dets=[...document.querySelectorAll('#screen details.season')];
        if (!dets.length) continue;
        const formes=new Set(dets.map(d=>
          d.querySelector('.eprow') ? 'lignes' : d.querySelector('.eps .ep') ? 'matrice' : 'vide'));
        formes.delete('vide');
        if (formes.size>1) c.mixte.push(t);
        else if (formes.has('lignes')) c.lignes.push(t);
        else if (formes.has('matrice')) c.matrice.push(t);
      }
      return c;}""")
    print(f"\nSeason rendering — list: {len(rendus['lignes'])} · "
          f"matrice : {len(rendus['matrice'])} · MIXED: {len(rendus['mixte'])}")
    for t in rendus["mixte"][:6]:
        note("R30 two season renderings within ONE sheet", t)
    if rendus["lignes"] and rendus["matrice"]:
        note("R30 two season renderings across sheets",
             f"{len(rendus['lignes'])} en liste (ex. {rendus['lignes'][0]}) contre "
             f"{len(rendus['matrice'])} en matrice (ex. {rendus['matrice'][0]})")

    evalue('R31')
    # R31 — from the LIBRARY, a card opens the media sheet, never the
    # acquisition sheet. Opening « Récupérer maintenant / Mettre en pause »
    # from the library created a second sheet design, whose content also
    # varied depending on whether the title was followed.
    dest=await pg.evaluate("""async ()=>{const out=[];
      for (const etat of ['lib-incomplets','lib-liste','lib-recents']) {
        for (let i=0; i<6; i++) {
          window.__go(etat); await new Promise(r=>setTimeout(r,300));
          const cartes=[...document.querySelectorAll('#view .card .cbody')];
          if (i>=cartes.length) break;
          const titre=cartes[i].querySelector('.ctitle')?.textContent?.slice(0,26) ?? '?';
          cartes[i].click(); await new Promise(r=>setTimeout(r,260));
          if (document.querySelector('#sheet').classList.contains('open'))
            out.push(`${etat} · « ${titre} » opens the acquisition sheet`);
          else if (!document.querySelector('#screen').classList.contains('open'))
            out.push(`${etat} · « ${titre} » opens nothing`);
        }
      } return out;}""")
    for x in dest: note("R31 library card with the wrong destination", x)

    print()
    if not viol: print("No violations on this second pass.")
    for r,l in sorted(viol.items()):
        print(f"■ {r} — {len(l)}")
        for x in l[:5]: print("   ",x)
    print(f"\nJS errors: {errs or 'none'}")
    print(f"{BAR}\nTOTAL, second pass: {sum(len(v) for v in viol.values())} violations "
          f"· {len(evaluees)}/{REGLES_ATTENDUES} rules executed")
    if len(evaluees) != REGLES_ATTENDUES:
        print(f"⚠ {REGLES_ATTENDUES - len(evaluees)} rule(s) never executed: "
              "a mute audit is not a green audit.")
    await b.close()
asyncio.run(main())
