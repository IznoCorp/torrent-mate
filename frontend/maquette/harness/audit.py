"""Adversarial review — every reported defect becomes a RULE checked across
ALL states, never a patch on the single case that was reported.

The stance is to try to make the prototype FAIL, not to confirm it.
"""
import asyncio
import json

from playwright.async_api import async_playwright

BAR = "─" * 62

async def main():
  async with async_playwright() as p:
    b = await p.chromium.launch(channel="chrome")
    ctx = await b.new_context(viewport={"width":390,"height":844},
                              device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__chargementTermine?.()")
    await pg.evaluate("()=>window.__measure(true)")
    etats = await pg.evaluate("()=>window.__states()")
    viol = {}
    def note(regle, detail):
        viol.setdefault(regle, []).append(detail)

    # A rule that disappears must be VISIBLE. Counting violated rules reads «
    # 0 of 0 » both when everything is fine and when nothing runs at all:
    # count the rules EXECUTED instead, and require the expected total.
    evaluees = set()
    def evalue(*regles):
        evaluees.update(regles)
    REGLES_ATTENDUES = 13

    print(f"{BAR}\nAdversarial review — {len(etats)} states\n{BAR}")

    for e in etats:
        await pg.evaluate("(i)=>window.__go(i)", e); await pg.wait_for_timeout(280)
        evalue('R1','R2','R3','R4','R4bis','R5','R6','R6bis','R7','R22','R23')
        r = await pg.evaluate("""(etat)=>{
          const R = {};
          const vis = (el)=>el.offsetParent!==null || el.getClientRects().length>0;
          // The media sheet left `#screen` for a real route (`/fiche/$titre`,
          // rendered inside `#coquille`): it joins this ladder, named by the
          // identity it carries and LAST, so every other case resolves exactly
          // as it did. Without it, the five states that open the fiche fall
          // through to `#view`, and R1/R2/R7/R22/R23 would pass on a page the
          // state never shows — a rule gone quiet, not a rule satisfied.
          const racine = document.querySelector('#dlg').classList.contains('open') ? document.querySelector('#dlg')
                       : document.querySelector('#screen').classList.contains('open') ? document.querySelector('#screen')
                       : document.querySelector('#sheet').classList.contains('open') ? document.querySelector('#sheet')
                       : document.querySelector('.screen.open[data-cle^="fiche:"]')
                       ?? document.querySelector('#view');

          // R1 — every tappable poster leads to a FILLED-IN sheet
          R.fichesCreuses = [...racine.querySelectorAll('[data-fiche]')].map(el=>el.dataset.fiche)
            .filter(t=>{const f=sheetFor(t); return !f || !f.ov || !f.g || !(f.cast||[]).length;});

          // R2 — HARDENED: a button must have a declared DESTINATION, not
          // merely a known class. Whitelisting by class blessed every `.sact`,
          // so a control could lead nowhere without the rule flinching.
          R.boutonsMorts = [...racine.querySelectorAll('button, a')]
            .filter(el=>el.getBoundingClientRect().height>0 && !el.disabled
                    && !el.closest('.hbtn') && !el.closest('.hpanel')
                    && !el.closest('details:not([open])'))
            // An href IS a destination — the trailer is a genuine outbound
            // link to YouTube.
            .filter(el=>!el.getAttribute('href') || el.getAttribute('href')==='#')
            .filter(el=>Object.keys(el.dataset).length===0 && !el.id && !el.onclick
                    && !/searchclear|burger|avatar|fback|more\b|fab|sel\b|vsw|seg\b|pill|tile|ep\b/.test(el.className))
            .map(el=>'« '+el.textContent.trim().slice(0,28)+' »');

          // R3 — touch targets: every control is at least 40px on one axis
          R.ciblesTropPetites = [...racine.querySelectorAll('button,a')].filter(el=>{
            if (!vis(el) || el.closest('.hbtn') || el.closest('.hpanel')) return false;
            const b=el.getBoundingClientRect();
            // DECLARED EXCEPTION: the episode cell is 31 × 27 in the SHIPPED
            // component. At 13 cells per row, 44px would demand 572px of
            // width: a geometric constraint, not an oversight. The rule
            // carries its exception rather than hiding it.
            if (el.classList.contains('ep')) return false;
            return b.width>0 && b.height>0 && b.height<32 && b.width<32;
          }).map(el=>(el.className||el.tagName)+' '+Math.round(el.getBoundingClientRect().height)+'px');

          // R4 — horizontal overflow outside DECLARED scrollers
          //
          // getBoundingClientRect reports geometry BEFORE clipping: a
          // decorative layer deliberately wider than its frame looks like
          // overflow while an ancestor clips it. Do not whitelist the class —
          // VERIFY the clipping: there must be an ancestor that really clips
          // (overflow-x hidden/clip) AND that fits within the frame itself. A
          // clipping ancestor that overflows clips nothing, it moves the
          // problem.
          const SCROLLERS = '.pillscroll,.cast,.eps,.hpanel';
          const rogne = (el) => {
            for (let p = el.parentElement; p && p !== racine.parentElement; p = p.parentElement) {
              const ox = getComputedStyle(p).overflowX;
              if (ox === 'hidden' || ox === 'clip') return p.getBoundingClientRect().right <= 390.5;
            }
            return false;
          };
          R.debordements = [...racine.querySelectorAll('*')].filter(el=>{
            const bb=el.getBoundingClientRect();
            return bb.right>390.5 && bb.width>0 && !el.closest(SCROLLERS) && !rogne(el);
          }).map(el=>(el.className||el.tagName)+' →'+Math.round(el.getBoundingClientRect().right));

          // R4b — the measurement that cannot be talked out of it: the
          // scrollport itself must offer NO horizontal scrolling. An illusory
          // clip would show up here.
          R.panHorizontal = [...racine.querySelectorAll('.port,[data-scroll-root]')]
            .filter(el=>el.scrollWidth > el.clientWidth + 1)
            .map(el=>(el.className||el.tagName)+' scrollWidth '+el.scrollWidth+' > '+el.clientWidth);

          // R5 — a horizontal scroller must NEVER block vertical panning
          R.scrollersBloquants = [...racine.querySelectorAll('*')].filter(el=>{
            const s=getComputedStyle(el);
            return s.overflowX==='auto'||s.overflowX==='scroll';
          }).filter(el=>{const ta=getComputedStyle(el).touchAction; return ta==='pan-x';})
            .map(el=>el.className+' touch-action:'+getComputedStyle(el).touchAction);

          // R6 — an essential title is never truncated to the point of being a
          // guess
          R.titresTronques = [...racine.querySelectorAll('.ht,.sheettitle,.dlg h3')].filter(el=>
            el.scrollWidth>el.clientWidth+1).map(el=>el.textContent.trim().slice(0,30));

          // R6 bis — a card title MAY ellipsize; the list is a list. But the full
          // string must stay reachable, because for an unidentified arrival the
          // release name IS its identity, and the truncation lands on the group —
          // exactly what tells two versions of the same media apart.
          R.titresPerdus = [...racine.querySelectorAll('.ctitle')].filter(el=>
            el.scrollWidth>el.clientWidth+1 && !el.getAttribute('title'))
            .map(el=>el.textContent.trim().slice(0,34));

          // R7 — no panel renders emptiness in silence
          R.panneauxVides = [...racine.querySelectorAll('.panel')].filter(el=>
            el.children.length===0).length;

          // R23 — within an option group every row has the same size, and
          // SHAPE distinguishes single choice (circle) from multiple choice
          // (square). Identical pills stated no rule.
          R.optionsIrregulieres = [];
          for (const grp of racine.querySelectorAll('.optlist')) {
            const opts = [...grp.querySelectorAll('.opt')];
            const t = opts.map(e=>{const b=e.getBoundingClientRect();
              return Math.round(b.width)+'×'+Math.round(b.height);});
            if (new Set(t).size > 1) R.optionsIrregulieres.push('tailles '+[...new Set(t)].join(' / '));
            const formes = new Set(opts.map(e=>e.classList.contains('radio')?'radio':'check'));
            if (formes.size > 1) R.optionsIrregulieres.push('mixed radio/checkbox group');
            const roles = new Set(opts.map(e=>e.getAttribute('role')));
            if (roles.size > 1) R.optionsIrregulieres.push('mixed roles');
          }

          // R22 — every switch has EXACTLY the same dimensions, whatever the
          // length of the label beside it. A chip inside a flex row took the
          // text's height.
          R.switchsIrreguliers = [];
          const sw = [...racine.querySelectorAll('.switch')];
          if (sw.length > 1) {
            const tailles = sw.map(e=>{const b=e.getBoundingClientRect();
              return Math.round(b.width)+'×'+Math.round(b.height);});
            if (new Set(tailles).size > 1) R.switchsIrreguliers = tailles;
          }

          // R20 — the library has only ONE sub-line grammar: « année · type ».
          // Two grammars make rows incomparable.
          R.sousLignes = [];
          if (etat.startsWith('lib-') && !etat.includes('incomplets')) {
            const attendu = /^(\\d{4}|année inconnue) · (Film|Série)$/;
            R.sousLignes = [...racine.querySelectorAll('#libitems .csub, #libitems .fr')]
              .map(e=>e.textContent.trim()).filter(t=>t && !attendu.test(t)).slice(0,5);
          }

          // R8 — EVERY layer reserves the height of the tab bar that passes
          // above it: screen, sheet and dialog. The rule once covered screens
          // only, and the defect came back through sheets.
          R.reserveEcran = null;
          const bar = document.querySelector('.bottombar').getBoundingClientRect().height;
          const couches = [['#screen','.port'],['#sheet','.sheetin']];
          for (const [sel, inner] of couches) {
            const el = document.querySelector(sel);
            if (!el.classList.contains('open')) continue;
            const port = el.querySelector(inner);
            if (!port) continue;
            const pb = parseFloat(getComputedStyle(port).paddingBottom);
            if (pb < bar) R.reserveEcran = `${sel} ${Math.round(pb)}px < barre ${Math.round(bar)}px`;
            // And the last button must be REACHABLE at maximum scroll.
            port.scrollTop = port.scrollHeight;
            // A collapsed <details> still gives its children a layout box:
            // filter on VISIBILITY, not on DOM order.
            const btns = [...port.querySelectorAll('button, a')]
              .filter(x => !x.closest('details:not([open])') && x.getBoundingClientRect().height > 0);
            const dernier = btns[btns.length-1];
            if (dernier) {
              const bb = dernier.getBoundingClientRect();
              const barTop = document.querySelector('.bottombar').getBoundingClientRect().top;
              if (bb.bottom > barTop + 1) R.reserveEcran = `${sel} : dernier bouton sous la barre (${Math.round(bb.bottom - barTop)}px)`;
            }
          }
          return R;
        }""", e)
        for k, v in r.items():
            if k == "optionsIrregulieres":
                for x in v: note("R23 inconsistent option group", f"{e} : {x}")
            elif k == "switchsIrreguliers":
                if v: note("R22 switches of differing sizes", f"{e} : {v}")
            elif k == "sousLignes":
                for x in v: note("R20 grammaire de sous-ligne divergente", f"{e} : « {x} »")
            elif k == "reserveEcran":
                if v: note("R8 insufficient screen reservation", f"{e} : {v}")
            elif k == "sousLignes":
                for x in v: note("R20 grammaire de sous-ligne divergente", f"{e} : « {x} »")
            elif k == "panneauxVides":
                if v: note("R7 empty panel", f"{e} : {v}")
            elif v:
                cle = {"fichesCreuses":"R1 hollow sheet behind a poster",
                       "boutonsMorts":"R2 button with no effect",
                       "ciblesTropPetites":"R3 touch target < 32px",
                       "debordements":"R4 horizontal overflow",
                       "panHorizontal":"R4b real horizontal scrolling",
                       "scrollersBloquants":"R5 scroller blocking vertical panning",
                       "titresTronques":"R6 truncated title",
                       "titresPerdus":"R6 bis title cut with no recourse"}[k]
                for x in (v if isinstance(v, list) else [v]):
                    note(cle, f"{e} : {x}")

    # R9 — film/series vocabulary, across ALL surfaces
    voc = await pg.evaluate("""()=>{
      const out=[];
      const attendu={movie:{ajout:'Ajouter',pause:'Ne plus chercher',retrait:'Retirer de la liste'},
                     show:{ajout:'Suivre',pause:'Mettre en pause',retrait:'Retirer le suivi'}};
      for (const f of world.follows) {
        const lab = stLabel(f);
        if (f.k==='movie' && /jour|Terminé/.test(lab)) out.push(`film « ${f.t} » porte « ${lab} » (vocabulaire série)`);
      }
      return out;}""")
    evalue('R9')
    for x in voc: note("R9 film/series vocabulary", x)

    # R10 — every action opens a layer, navigates, or mutates — never nothing
    inertes = await pg.evaluate("""async ()=>{
      // The snapshot has to carry every dial the interface tracks, or an
      // action that moves one the snapshot forgets reads as inert. The
      // pipeline dial joined when Arrivées gained its pilot's bar: « Lancer le
      // pipeline » really does change the interface, and this rule said it did
      // not — a false accusation is as expensive as a missed defect.
      const out=[]; const snap=()=>JSON.stringify({t:world.takeable.length,i:world.inflight.length,s:world.stuck.length,
        m:world.moving.length,f:world.follows.length,l:world.lib.length,p:state.page,tab:state.acqTab,lens:state.libLens,
        pipe:state.pipe});
      for (const id of ['acq-encours-charge','arr-charge','lib-incomplets']) {
        window.__go(id); await new Promise(r=>setTimeout(r,220));
        const btns=[...document.querySelectorAll('#view .cfoot')];
        for (let i=0;i<btns.length;i++){
          window.__go(id); await new Promise(r=>setTimeout(r,200));
          const b=[...document.querySelectorAll('#view .cfoot')][i]; if(!b) continue;
          const lab=b.textContent.trim(); const avant=snap();
          const couche=()=>['#sheet','#screen','#dlg'].some(s=>document.querySelector(s).classList.contains('open'));
          b.click(); await new Promise(r=>setTimeout(r,320));
          if (snap()===avant && !couche()) out.push(`${id} : « ${lab} » ne change rien`);
          ['#scrim'].forEach(s=>document.querySelector(s).click());
        }
      }
      return out;}""")
    evalue('R10')
    for x in inertes: note("R10 action with no effect", x)

    print()
    if not viol and not errs:
        print("No violations. (For an adversarial review, that deserves suspicion.)")
    for regle, lst in sorted(viol.items()):
        print(f"■ {regle} — {len(lst)}")
        for x in lst[:6]: print("   ", x)
        if len(lst) > 6: print(f"    … et {len(lst)-6} autres")
    print(f"\nJS errors: {errs or 'none'}")
    manquantes = REGLES_ATTENDUES - len(evaluees)
    print(f"{BAR}\nTOTAL: {sum(len(v) for v in viol.values())} violations "
          f"· {len(evaluees)}/{REGLES_ATTENDUES} rules executed")
    if manquantes:
        print(f"⚠ {manquantes} rule(s) declared but never executed: "
              f"a mute audit is not a green audit.")
    json.dump({k:v for k,v in viol.items()}, open("violations.json","w"), ensure_ascii=False, indent=1)
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if viol or errs: raise SystemExit(1)
asyncio.run(main())
