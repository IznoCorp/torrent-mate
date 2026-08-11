"""Second tour adversarial — uniformité, cohérence, honnêteté du texte.
On cherche à faire tomber la maquette sur ce qu'une capture ne montre pas."""
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

    # Même exigence qu'au premier tour : on compte les règles EXÉCUTÉES, pour
    # qu'un audit devenu muet ne se lise plus comme un audit vert.
    evaluees=set()
    def evalue(*r): evaluees.update(r)
    REGLES_ATTENDUES=11
    print(f"{BAR}\nRevue adversariale — second tour, {len(etats)} états\n{BAR}")

    evalue('R11')
    # R11 — jargon, valeurs techniques et anglais machine dans le texte rendu
    for e in etats:
        await pg.evaluate("(i)=>window.__go(i)",e); await pg.wait_for_timeout(240)
        bad=await pg.evaluate("""()=>{
          const r=document.querySelector('#dlg').classList.contains('open')?'#dlg'
                 :document.querySelector('#screen').classList.contains('open')?'#screen'
                 :document.querySelector('#sheet').classList.contains('open')?'#sheet':'#view';
          const t=document.querySelector(r).innerText;
          const motifs=[[/\\bundefined\\b/,'undefined'],[/\\bNaN\\b/,'NaN'],[/\\bnull\\b/,'null'],
            [/\\[object /,'[object'],[/\\b0\\/0\\b/,'0/0'],[/\\*\\s\\*\\s\\*/,'expression cron'],
            [/\\bError\\b/,'Error'],[/\\bTrue\\b|\\bFalse\\b/,'booléen brut']];
          return motifs.filter(([re])=>re.test(t)).map(([,n])=>n);}""")
        for x in bad: note("R11 jargon ou valeur technique visible", f"{e} : {x}")

    evalue('R12')
    # R12 — uniformité des boutons d'action principaux
    geo=await pg.evaluate("""async ()=>{
      const out={};
      const mesure=(sel,nom)=>{const el=document.querySelector(sel); if(!el) return;
        const s=getComputedStyle(el); const b=el.getBoundingClientRect();
        out[nom]={h:Math.round(b.height),poids:s.fontWeight,taille:s.fontSize,centre:s.justifyContent,
                  radius:s.borderRadius,icone:!!el.querySelector(':scope > svg')};};
      window.__go('acq-encours-charge'); await new Promise(r=>setTimeout(r,220));
      mesure('.cfoot.solid','pied de carte (primaire)');
      window.__go('feuille-suivi-trous'); await new Promise(r=>setTimeout(r,240));
      mesure('.sact.primary','feuille (primaire)');
      window.__go('fiche-suggestion-film'); await new Promise(r=>setTimeout(r,240));
      mesure('.ficheadd','fiche (ajouter)');
      window.__go('acq-ajout-resultats'); await new Promise(r=>setTimeout(r,240));
      mesure('.resbtn','résultat de recherche');
      window.__go('lib-suppression'); await new Promise(r=>setTimeout(r,240));
      mesure('.dlgbtn.danger','dialogue (danger)');
      return out;}""")
    print("Géométrie des boutons principaux :")
    for k,v in geo.items(): print(f"   {k:26} {v}")
    hs=[v["h"] for v in geo.values()]
    if max(hs)-min(hs) > 2: note("R12 hauteurs de boutons hétérogènes", f"{min(hs)}–{max(hs)} px : {json.dumps(geo,ensure_ascii=False)}")
    for k,v in geo.items():
        # « normal » N'EST PAS centré : c'est la mollesse de règle qui avait
        # laissé passer la violation que l'opérateur a trouvée au doigt.
        # Arbitrage 2026-08-11 : icône → aligné à gauche ; sans icône → centré.
        attendu = "flex-start" if v.get("icone") else "center"
        if v["centre"] != attendu:
            note("R12 alignement non conforme", f"{k} : {v['centre']} au lieu de {attendu} (icône: {v.get('icone')})")
        if v["radius"] != "8px": note("R12 radius hétérogène", f"{k} : {v['radius']}")
        if v["taille"] != "13.5px": note("R12 taille de texte hétérogène", f"{k} : {v['taille']}")

    evalue('R13')
    # R13 — uniformité des fiches : MÊME BASE pour toutes.
    #
    # L'ancienne version échantillonnait 5 états figés, dont aucun média
    # INCOMPLET — et c'est exactement par là qu'une divergence est passée sans
    # être vue. On tire désormais l'échantillon de la DONNÉE : complète,
    # incomplète, sans visuel, suggestion, film et série.
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
    print(f"\nBase des fiches, sur {len(ordres)} médias tirés de la donnée :")
    # Les sections FACULTATIVES par nature (bande-annonce absente, catalogue
    # inconnu) ne comptent pas comme divergence ; l'ossature, si.
    OPT = {"trailer", "nofiche", "rulenote"}
    def ossature(l):
        return [s.replace("Création", "X").replace("Réalisation", "X") for s in l if s not in OPT]
    formes = {}
    for k, v in ordres.items():
        formes.setdefault(tuple(ossature(v)), []).append(k)
    for f, l in formes.items():
        print(f"   {len(l):2d} médias · {' → '.join(f)}")
    if len(formes) > 1:
        ref = max(formes.items(), key=lambda kv: len(kv[1]))[0]
        for f, l in formes.items():
            if f != ref:
                note("R13 fiche qui ne suit pas la base commune",
                     f"{', '.join(l[:3])} : {' → '.join(f)} au lieu de {' → '.join(ref)}")

    evalue('R14')
    # R14 — chaque couche se ferme par le scrim ET par Retour
    for id_,sel in [("feuille-suivi-trous","#sheet"),("lib-suppression","#dlg"),("fiche-serie","#screen"),("acq-ajout-resultats","#screen")]:
        await pg.evaluate("(i)=>window.__go(i)",id_); await pg.wait_for_timeout(300)
        ouvert=await pg.evaluate("(s)=>document.querySelector(s).classList.contains('open')",sel)
        if sel!="#screen":
            await pg.evaluate("()=>document.querySelector('#scrim').click()"); await pg.wait_for_timeout(300)
            if await pg.evaluate("(s)=>document.querySelector(s).classList.contains('open')",sel):
                note("R14 couche non fermable par le scrim", f"{id_}")
        else:
            await pg.evaluate("()=>document.querySelector('#screen .fback').click()"); await pg.wait_for_timeout(350)
            if await pg.evaluate("()=>document.querySelector('#screen').classList.contains('open')"):
                note("R14 écran non fermable par Retour", f"{id_}")
        if not ouvert: note("R14 couche qui ne s'ouvre pas", id_)

    evalue('R15')
    # R15 — les trois modes de Suivis montrent le MÊME nombre d'items
    n=await pg.evaluate("""async ()=>{const o={};
      for (const m of ['acq-suivis-liste','acq-suivis-groupe','acq-suivis-grille']) {
        window.__go(m); await new Promise(r=>setTimeout(r,240));
        o[m]=document.querySelectorAll('#view .card, #view .tile').length;}
      return o;}""")
    print("\nItems par mode de Suivis :", n)
    if len(set(n.values()))>1: note("R15 modes de Suivis incohérents", json.dumps(n))

    evalue('R16')
    # R16 — le badge est la somme qu'il prétend être
    bad=await pg.evaluate("""async ()=>{const out=[];
      for (const s of ['reel','charge']) { S.scen=s; window.__go('acq-encours-'+(s==='reel'?'repos':'charge'));
        await new Promise(r=>setTimeout(r,240));
        const badge=document.querySelector('[data-page=acq] .navbadge');
        const attendu=D.takeable().length+D.blocked().length;
        const lu=badge?Number(badge.textContent):0;
        if (lu!==attendu) out.push(`${s} : badge ${lu} ≠ à récupérer+à traiter ${attendu}`);
        const onglet=document.querySelector('.seg .n');
        const lu2=onglet?Number(onglet.textContent):0;
        if (lu2!==attendu) out.push(`${s} : badge d'onglet ${lu2} ≠ ${attendu}`);
      } return out;}""")
    for x in bad: note("R16 badge non dérivé", x)

    evalue('R17')
    # R17 — toute mutation destructive est confirmée ou réversible
    rev=await pg.evaluate("""async ()=>{const out=[];
      window.__go('acq-suivis-liste'); await new Promise(r=>setTimeout(r,240));
      document.querySelector('#view .swipe .act.remove').click(); await new Promise(r=>setTimeout(r,320));
      if (!document.querySelector('#toastundo')) out.push('retirer un suivi : aucun Annuler');
      window.__go('lib-liste'); await new Promise(r=>setTimeout(r,260));
      const av=W.lib.length;
      document.querySelector('#libitems .swipe .act.remove').click(); await new Promise(r=>setTimeout(r,320));
      if (!document.querySelector('#dlg').classList.contains('open')) out.push('supprimer un média : aucune confirmation');
      if (W.lib.length!==av) out.push('supprimer un média : mutation AVANT confirmation');
      return out;}""")
    for x in rev: note("R17 destruction sans garde-fou", x)

    evalue('R26')
    # R26 — le fond d'affiche fondu est un trait de TOUTES les fiches, pas de
    # celles que j'ai regardées. La règle est conditionnelle et le dit : un
    # média SANS affiche dégrade en fond plat (différence justifiée par son
    # contexte propre, cf. README). Un média AVEC affiche qui n'a pas son fond
    # signale un second chemin de rendu non converti — le défaut de fond de la
    # refonte précédente.
    fonds=await pg.evaluate("""async ()=>{const out=[];
      const racineDoc=document.documentElement;
      // LES DEUX THÈMES. Un sélecteur orphelin laissé par une suppression avait
      // donné position:absolute au bandeau en clair seulement : la fiche était
      // sens dessus dessous, et la règle ne regardait que le sombre.
      for (const theme of [null,'light']) {
        theme ? racineDoc.setAttribute('data-theme',theme) : racineDoc.removeAttribute('data-theme');
        for (const s of window.__states()) {
          window.__go(s); await new Promise(r=>setTimeout(r,150));
          const racine=document.querySelector('#screen.open, #sheet.open');
          const hero=racine && racine.querySelector('.hero');
          if (!hero) continue;
          const nom=`${s}/${theme||'sombre'}`;
          const wrap=hero.closest('.herowrap');
          if (!wrap) { out.push(`${nom} : fiche sans .herowrap`); continue; }
          const bg=wrap.querySelector('.herobg');
          if (!bg) { out.push(`${nom} : fiche sans bandeau`); continue; }
          const sb=getComputedStyle(bg), rb=bg.getBoundingClientRect(), rh=hero.getBoundingClientRect();
          // Le bandeau OCCUPE le haut : il pousse le contenu, il ne flotte pas.
          if (sb.position!=='relative') out.push(`${nom} : bandeau en ${sb.position}`);
          const aVisuelIci=!wrap.classList.contains('noaffiche');
          // Sans visuel, le champ est volontairement court : il tient la place,
          // il ne prétend rien. Le seuil ne s'applique qu'à une vraie image.
          const seuil = aVisuelIci ? 240 : 48;
          if (rb.height < seuil)
            out.push(`${nom} : bandeau haut de ${Math.round(rb.height)}px (< ${seuil})`);
          // Le titre vient SOUS l'image, en la chevauchant par le bas.
          if (rh.top <= rb.top) out.push(`${nom} : titre au-dessus du bandeau`);
          if (rh.top >= rb.bottom) out.push(`${nom} : titre décollé du bandeau`);
          // Le texte ne repose JAMAIS sur l'image nue : le dégradé de
          // fermeture est ce qui rend la règle vraie, pas la bonne volonté.
          if (!getComputedStyle(bg,'::after').backgroundImage.includes('gradient'))
            out.push(`${nom} : bandeau sans dégradé de lisibilité`);
          const aVisuel=!wrap.classList.contains('noaffiche');
          if (aVisuel && sb.backgroundImage==='none') out.push(`${nom} : bandeau déclaré mais vide`);
        }
      }
      racineDoc.removeAttribute('data-theme');
      return out;}""")
    for x in fonds: note("R26 fond d'affiche non généralisé", x)

    evalue('R27')
    # R27 — ARBITRAGE OPÉRATEUR du 11 août : la bande-annonce s'ouvre TOUJOURS
    # dans YouTube, jamais dans l'application, et la fiche la propose quel que
    # soit l'endroit d'où l'on vient — médiathèque, acquisitions ou Découvrir.
    # La règle porte l'arbitrage : une fiche qui promettrait une lecture interne
    # serait fausse même si elle était jolie.
    bandes=await pg.evaluate("""async ()=>{const out=[];
      for (const s of window.__states()) {
        window.__go(s); await new Promise(r=>setTimeout(r,150));
        const racine=document.querySelector('#screen.open, #sheet.open');
        if (!racine || !racine.querySelector('.hero')) continue;
        const el=racine.querySelector('.trailer');
        if (!el) continue;                       // absence assumée : dit ailleurs
        if (el.tagName!=='A') { out.push(`${s} : bande-annonce en <${el.tagName}>, pas un lien`); continue; }
        const href=el.getAttribute('href')||'';
        if (!/^https:\\/\\/www\\.youtube\\.com\\/watch\\?v=[\\w-]{6,}$/.test(href))
          out.push(`${s} : href non conforme « ${href.slice(0,48)} »`);
        if (el.getAttribute('target')!=='_blank') out.push(`${s} : le lien ne quitte pas l'app`);
        if (!(el.getAttribute('rel')||'').includes('noopener')) out.push(`${s} : lien sortant sans noopener`);
        if (/lecture ici|plein écran|dans l.app/i.test(el.textContent+(el.dataset.toast||'')))
          out.push(`${s} : promet une lecture interne`);
      } return out;}""")
    for x in bandes: note("R27 bande-annonce non conforme à l'arbitrage", x)

    evalue('R28')
    # R28 — EXIGENCE OPÉRATEUR du 11 août : « il ne devrait y avoir qu'UN design
    # de retour compatible avec toutes les pages ». Une barre flottante blanche
    # par-dessus l'image avait créé un second design qui, sur les écrans sans
    # image, RECOUVRAIT le titre au lieu de le pousser. La règle mesure les deux
    # choses : une seule signature, et jamais de contenu collé ni recouvert.
    retours=await pg.evaluate("""async ()=>{const sig={}, colles=[];
      for (const s of window.__states()) {
        window.__go(s); await new Promise(r=>setTimeout(r,150));
        const bar=document.querySelector('#screen.open .fichebar');
        if (!bar) continue;
        const btn=bar.querySelector('.fback');
        if (!btn) { colles.push(`${s} : barre sans retour`); continue; }
        const sb=getComputedStyle(bar), sx=getComputedStyle(btn), rb=bar.getBoundingClientRect();
        // Une barre hors flux ne pousse rien : elle finit par recouvrir.
        if (sb.position!=='static' && sb.position!=='relative')
          colles.push(`${s} : barre en ${sb.position} — elle ne pousse pas le contenu`);
        const k=[sb.position, sb.backgroundColor, sx.color, Math.round(rb.height)].join('|');
        (sig[k] ||= []).push(s);
        // On mesure le premier PIXEL DE TEXTE, pas la première boîte : un
        // conteneur peut toucher la barre par son padding sans que rien ne
        // soit collé. C'est du texte collé que l'opérateur a signalé.
        const port=document.querySelector('#screen .port');
        const texte=port && [...port.querySelectorAll('h1,h2,h3,p,span,button,a,label')]
          .find(e=>{const r=e.getBoundingClientRect();
                    return r.height>0 && (e.textContent||'').trim().length>1 && !e.closest('.note');});
        if (texte) {
          const ecart=texte.getBoundingClientRect().top-rb.bottom;
          if (ecart < 8) colles.push(`${s} : texte à ${Math.round(ecart)}px de la barre`);
        }
      }
      return {sig, colles};}""")
    if len(retours["sig"]) > 1:
        for k, l in retours["sig"].items():
            note("R28 plusieurs designs de retour", f"{k} → {', '.join(l[:4])}")
    for x in retours["colles"]: note("R28 retour mal posé", x)
    print(f"\nDesigns de retour distincts : {len(retours['sig'])} sur "
          f"{sum(len(v) for v in retours['sig'].values())} écrans")

    evalue('R29')
    # R29 — la présence d'un épisode se lit dans la LISTE des numéros possédés,
    # jamais au seuil « numéro <= nombre possédés ». Ce seuil suppose le trou en
    # fin de saison : faux pour 35 séries de cette médiathèque. La règle vérifie
    # l'accord entre ce qui est AFFICHÉ et la donnée, sur des séries à trou
    # INTERNE — là où les deux méthodes divergent.
    ep=await pg.evaluate("""async ()=>{const out=[];
      // TOUTES les séries à trou INTERNE, pas un échantillon : c'est là que le
      // seuil et la liste divergent, donc là que la règle a une chance de mordre.
      const atrous=Object.entries(POSSEDES).filter(([t,s])=>
        Object.values(s).some(l=>l.length && l.some((n,i)=>n!==i+1))).map(([t])=>t);
      if (!atrous.length) return ['aucune série à trou interne — la règle serait vacante'];
      let inspectes=0;
      for (const titre of atrous) {
        window.__reset(); set({page:'lib', phase:'prete'}); openFiche(titre);
        await new Promise(r=>setTimeout(r,160));
        for (const det of document.querySelectorAll('#screen details.season')) {
          const num=Number((det.querySelector('summary')?.textContent||'').match(/Saison\\s+(\\d+)/)?.[1]);
          const detenus=possedesDe(titre, num);
          if (!detenus) continue;
          // Les DEUX rendus : lignes à titres ET matrice de numéros.
          const cases=[...det.querySelectorAll('.eprow')].map(r=>[
              Number((r.querySelector('.en')?.textContent||'').replace(/\\D/g,'')), r])
            .concat([...det.querySelectorAll('.eps .ep')].map(c=>[Number(c.textContent), c]));
          for (const [n, el] of cases) {
            if (!n || el.classList.contains('annonce')) continue;
            inspectes++;
            const affiche=el.classList.contains('en_mediatheque');
            if (affiche !== detenus.has(n))
              out.push(`${titre} S${num}E${n} : affiché ${affiche?'présent':'manquant'}, réellement ${detenus.has(n)?'présent':'manquant'}`);
          }
        }
      }
      if (!inspectes) out.push('aucun épisode inspecté — la règle ne prouve rien');
      return out.slice(0, 12);}""")
    for x in ep: note("R29 présence d'épisode non conforme à la donnée", x)

    print()
    if not viol: print("Aucune violation sur ce second tour.")
    for r,l in sorted(viol.items()):
        print(f"■ {r} — {len(l)}")
        for x in l[:5]: print("   ",x)
    print(f"\nerreurs JS : {errs or 'aucune'}")
    print(f"{BAR}\nTOTAL second tour : {sum(len(v) for v in viol.values())} violations "
          f"· {len(evaluees)}/{REGLES_ATTENDUES} règles exécutées")
    if len(evaluees) != REGLES_ATTENDUES:
        print(f"⚠ {REGLES_ATTENDUES - len(evaluees)} règle(s) jamais exécutée(s) : "
              "un audit muet n'est pas un audit vert.")
    await b.close()
asyncio.run(main())
