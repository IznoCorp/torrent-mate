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
    print(f"{BAR}\nRevue adversariale — second tour, {len(etats)} états\n{BAR}")

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

    # R13 — uniformité des fiches : même ordre de sections partout
    ordres=await pg.evaluate("""async ()=>{
      const out={};
      for (const [id,] of [['fiche-serie'],['fiche-film'],['fiche-sans-trailer'],['fiche-suggestion-serie'],['fiche-suggestion-film']]) {
        window.__go(id); await new Promise(r=>setTimeout(r,240));
        out[id]=[...document.querySelectorAll('#screen .h2')].map(x=>x.textContent);
      }
      return out;}""")
    print("\nOrdre des sections de fiche :")
    for k,v in ordres.items(): print(f"   {k:26} {' → '.join(v)}")
    ref=[s for s in ordres["fiche-serie"] if s!="Épisodes — saison 3"]
    for k,v in ordres.items():
        base=[s for s in v if not s.startswith("Épisodes")]
        attendu=[s.replace("Création","X").replace("Réalisation","X") for s in ref]
        got=[s.replace("Création","X").replace("Réalisation","X") for s in base]
        if got!=attendu: note("R13 ordre de sections divergent", f"{k} : {base}")

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

    # R15 — les trois modes de Suivis montrent le MÊME nombre d'items
    n=await pg.evaluate("""async ()=>{const o={};
      for (const m of ['acq-suivis-liste','acq-suivis-groupe','acq-suivis-grille']) {
        window.__go(m); await new Promise(r=>setTimeout(r,240));
        o[m]=document.querySelectorAll('#view .card, #view .tile').length;}
      return o;}""")
    print("\nItems par mode de Suivis :", n)
    if len(set(n.values()))>1: note("R15 modes de Suivis incohérents", json.dumps(n))

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

    # R26 — le fond d'affiche fondu est un trait de TOUTES les fiches, pas de
    # celles que j'ai regardées. La règle est conditionnelle et le dit : un
    # média SANS affiche dégrade en fond plat (différence justifiée par son
    # contexte propre, cf. README). Un média AVEC affiche qui n'a pas son fond
    # signale un second chemin de rendu non converti — le défaut de fond de la
    # refonte précédente.
    fonds=await pg.evaluate("""async ()=>{const out=[];
      for (const s of window.__states()) {
        window.__go(s); await new Promise(r=>setTimeout(r,180));
        const racine=document.querySelector('#screen.open, #sheet.open');
        const hero=racine && racine.querySelector('.hero');
        if (!hero) continue;
        const wrap=hero.closest('.herowrap');
        if (!wrap) { out.push(`${s} : fiche sans .herowrap`); continue; }
        const bg=wrap.querySelector('.herobg');
        const aAffiche=!!hero.querySelector('.sheetposter img');
        if (aAffiche && !bg) out.push(`${s} : affiche présente mais aucun fond`);
        if (bg && getComputedStyle(bg).backgroundImage==='none')
          out.push(`${s} : fond déclaré mais vide`);
        // Le texte ne doit JAMAIS reposer sur l'image : le dégradé de
        // fermeture est ce qui rend la règle vraie, pas la bonne volonté.
        if (bg && !getComputedStyle(bg,'::after').backgroundImage.includes('gradient'))
          out.push(`${s} : fond sans dégradé de lisibilité`);
      } return out;}""")
    for x in fonds: note("R26 fond d'affiche non généralisé", x)

    print()
    if not viol: print("Aucune violation sur ce second tour.")
    for r,l in sorted(viol.items()):
        print(f"■ {r} — {len(l)}")
        for x in l[:5]: print("   ",x)
    print(f"\nerreurs JS : {errs or 'aucune'}")
    print(f"{BAR}\nTOTAL second tour : {sum(len(v) for v in viol.values())} violations")
    await b.close()
asyncio.run(main())
