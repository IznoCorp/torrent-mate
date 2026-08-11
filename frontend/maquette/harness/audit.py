"""Revue adversariale — chaque retour de l'opérateur devient une RÈGLE
vérifiée sur TOUS les états, pas un correctif sur le cas signalé.

Le parti pris est de chercher à faire ÉCHOUER la maquette, pas à la confirmer.
"""
import asyncio, json
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
    await pg.evaluate("()=>window.__measure(true)")
    etats = await pg.evaluate("()=>window.__states()")
    viol = {}
    def note(regle, detail):
        viol.setdefault(regle, []).append(detail)

    print(f"{BAR}\nRevue adversariale — {len(etats)} états\n{BAR}")

    for e in etats:
        await pg.evaluate("(i)=>window.__go(i)", e); await pg.wait_for_timeout(280)
        r = await pg.evaluate("""(etat)=>{
          const R = {};
          const vis = (el)=>el.offsetParent!==null || el.getClientRects().length>0;
          const racine = document.querySelector('#dlg').classList.contains('open') ? document.querySelector('#dlg')
                       : document.querySelector('#screen').classList.contains('open') ? document.querySelector('#screen')
                       : document.querySelector('#sheet').classList.contains('open') ? document.querySelector('#sheet')
                       : document.querySelector('#view');

          // R1 — toute affiche cliquable mène à une fiche RENSEIGNÉE
          R.fichesCreuses = [...racine.querySelectorAll('[data-fiche]')].map(el=>el.dataset.fiche)
            .filter(t=>{const f=fiche(t); return !f || !f.ov || !f.g || !(f.cast||[]).length;});

          // R2 — DURCIE : un bouton doit avoir une DESTINATION déclarée, pas
          // seulement une classe connue. La version par classe blanchissait
          // tout `.sact`, donc « Profil de qualité » menait nulle part sans
          // que la règle bronche — trouvé au doigt par l'opérateur.
          R.boutonsMorts = [...racine.querySelectorAll('button, a')]
            .filter(el=>el.getBoundingClientRect().height>0 && !el.disabled
                    && !el.closest('.hbtn') && !el.closest('.hpanel')
                    && !el.closest('details:not([open])'))
            .filter(el=>Object.keys(el.dataset).length===0 && !el.id && !el.onclick
                    && !/searchclear|burger|avatar|fback|more\b|fab|sel\b|vsw|seg\b|pill|tile|ep\b/.test(el.className))
            .map(el=>'« '+el.textContent.trim().slice(0,28)+' »');

          // R3 — cibles tactiles : toute commande fait au moins 40 px dans un sens
          R.ciblesTropPetites = [...racine.querySelectorAll('button,a')].filter(el=>{
            if (!vis(el) || el.closest('.hbtn') || el.closest('.hpanel')) return false;
            const b=el.getBoundingClientRect();
            // EXCEPTION DÉCLARÉE : la cellule d'épisode fait 31 × 27 dans le
            // composant LIVRÉ. À 13 cellules par ligne, 44 px demanderait
            // 572 px de large : la contrainte est géométrique, pas un oubli.
            // La règle porte son exception plutôt que de la taire.
            if (el.classList.contains('ep')) return false;
            return b.width>0 && b.height>0 && b.height<32 && b.width<32;
          }).map(el=>(el.className||el.tagName)+' '+Math.round(el.getBoundingClientRect().height)+'px');

          // R4 — débordement horizontal hors défileurs DÉCLARÉS
          const SCROLLERS = '.pillscroll,.cast,.eps,.hpanel';
          R.debordements = [...racine.querySelectorAll('*')].filter(el=>{
            const bb=el.getBoundingClientRect();
            return bb.right>390.5 && bb.width>0 && !el.closest(SCROLLERS);
          }).map(el=>(el.className||el.tagName)+' →'+Math.round(el.getBoundingClientRect().right));

          // R5 — un défileur horizontal ne doit JAMAIS bloquer le pan vertical
          R.scrollersBloquants = [...racine.querySelectorAll('*')].filter(el=>{
            const s=getComputedStyle(el);
            return s.overflowX==='auto'||s.overflowX==='scroll';
          }).filter(el=>{const ta=getComputedStyle(el).touchAction; return ta==='pan-x';})
            .map(el=>el.className+' touch-action:'+getComputedStyle(el).touchAction);

          // R6 — un titre essentiel n'est jamais tronqué au point d'être une devinette
          R.titresTronques = [...racine.querySelectorAll('.ht,.sheettitle,.dlg h3')].filter(el=>
            el.scrollWidth>el.clientWidth+1).map(el=>el.textContent.trim().slice(0,30));

          // R7 — aucune section ne rend le vide en silence
          R.panneauxVides = [...racine.querySelectorAll('.panel')].filter(el=>
            el.children.length===0).length;

          // R23 — dans un groupe d'options, toutes les rangées ont la même
          // taille, et la FORME distingue choix unique (cercle) et choix
          // multiple (carré). Des pastilles identiques ne disaient pas la règle.
          R.optionsIrregulieres = [];
          for (const grp of racine.querySelectorAll('.optlist')) {
            const opts = [...grp.querySelectorAll('.opt')];
            const t = opts.map(e=>{const b=e.getBoundingClientRect();
              return Math.round(b.width)+'×'+Math.round(b.height);});
            if (new Set(t).size > 1) R.optionsIrregulieres.push('tailles '+[...new Set(t)].join(' / '));
            const formes = new Set(opts.map(e=>e.classList.contains('radio')?'radio':'check'));
            if (formes.size > 1) R.optionsIrregulieres.push('groupe mixte radio/case');
            const roles = new Set(opts.map(e=>e.getAttribute('role')));
            if (roles.size > 1) R.optionsIrregulieres.push('rôles mélangés');
          }

          // R22 — tout interrupteur a EXACTEMENT les mêmes dimensions, quelle
          // que soit la longueur du libellé à côté. Un chip « Oui/Non » dans
          // une rangée flex prenait la hauteur du texte.
          R.switchsIrreguliers = [];
          const sw = [...racine.querySelectorAll('.switch')];
          if (sw.length > 1) {
            const tailles = sw.map(e=>{const b=e.getBoundingClientRect();
              return Math.round(b.width)+'×'+Math.round(b.height);});
            if (new Set(tailles).size > 1) R.switchsIrreguliers = tailles;
          }

          // R20 — la médiathèque n'a qu'UNE grammaire de sous-ligne :
          // « année · type ». Deux grammaires rendent les rangées
          // incomparables entre elles.
          R.sousLignes = [];
          if (etat.startsWith('lib-') && !etat.includes('incomplets')) {
            const attendu = /^(\d{4}|année inconnue) · (Film|Série)$/;
            R.sousLignes = [...racine.querySelectorAll('#libitems .csub, #libitems .fr')]
              .map(e=>e.textContent.trim()).filter(t=>t && !attendu.test(t)).slice(0,5);
          }

          // R8 — TOUTE couche réserve la hauteur de la barre d'onglets, qui
          // passe au-dessus d'elle : écran, feuille et dialogue. La règle ne
          // couvrait que l'écran, et le défaut est réapparu sur la feuille.
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
            // Et le dernier bouton doit être ATTEIGNABLE au défilement max.
            port.scrollTop = port.scrollHeight;
            // Un <details> replié laisse une boîte de mise en page à ses
            // enfants : filtrer sur la VISIBILITÉ, pas sur l'ordre du DOM.
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
                for x in v: note("R23 groupe d'options incohérent", f"{e} : {x}")
            elif k == "switchsIrreguliers":
                if v: note("R22 interrupteurs de tailles différentes", f"{e} : {v}")
            elif k == "sousLignes":
                for x in v: note("R20 grammaire de sous-ligne divergente", f"{e} : « {x} »")
            elif k == "reserveEcran":
                if v: note("R8 réserve d'écran insuffisante", f"{e} : {v}")
            elif k == "sousLignes":
                for x in v: note("R20 grammaire de sous-ligne divergente", f"{e} : « {x} »")
            elif k == "panneauxVides":
                if v: note("R7 panneau vide", f"{e} : {v}")
            elif v:
                cle = {"fichesCreuses":"R1 fiche creuse derrière une affiche",
                       "boutonsMorts":"R2 bouton sans effet",
                       "ciblesTropPetites":"R3 cible tactile < 32 px",
                       "debordements":"R4 débordement horizontal",
                       "scrollersBloquants":"R5 défileur qui bloque le pan vertical",
                       "titresTronques":"R6 titre tronqué"}[k]
                for x in (v if isinstance(v, list) else [v]):
                    note(cle, f"{e} : {x}")

    # ── R9 : vocabulaire film/série, sur TOUTES les surfaces ──────────────
    voc = await pg.evaluate("""()=>{
      const out=[];
      const attendu={movie:{ajout:'Ajouter',pause:'Ne plus chercher',retrait:'Retirer de la liste'},
                     show:{ajout:'Suivre',pause:'Mettre en pause',retrait:'Retirer le suivi'}};
      for (const f of W.follows) {
        const lab = stLabel(f);
        if (f.k==='movie' && /jour|Terminé/.test(lab)) out.push(`film « ${f.t} » porte « ${lab} » (vocabulaire série)`);
      }
      return out;}""")
    for x in voc: note("R9 vocabulaire film/série", x)

    # ── R10 : toute action ouvre une couche, navigue, ou mute — jamais rien ─
    inertes = await pg.evaluate("""async ()=>{
      const out=[]; const snap=()=>JSON.stringify({t:W.takeable.length,i:W.inflight.length,s:W.stuck.length,
        m:W.moving.length,f:W.follows.length,l:W.lib.length,p:S.page,tab:S.acqTab,lens:S.libLens});
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
    for x in inertes: note("R10 action sans effet", x)

    print()
    if not viol and not errs:
        print("Aucune violation. (Ce qui, pour une revue adversariale, mérite méfiance.)")
    for regle, lst in sorted(viol.items()):
        print(f"■ {regle} — {len(lst)}")
        for x in lst[:6]: print("   ", x)
        if len(lst) > 6: print(f"    … et {len(lst)-6} autres")
    print(f"\nerreurs JS : {errs or 'aucune'}")
    print(f"{BAR}\nTOTAL : {sum(len(v) for v in viol.values())} violations sur {len(viol)} règles")
    json.dump({k:v for k,v in viol.items()}, open("violations.json","w"), ensure_ascii=False, indent=1)
    await b.close()
asyncio.run(main())
