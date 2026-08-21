"""Second adversarial pass — uniformity, consistency, honesty of the text.
Aimed at what a screenshot does not show.
"""
import asyncio
import json

from playwright.async_api import async_playwright

BAR="─"*62

async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>window.__measure(true)")
    states=await pg.evaluate("()=>window.__states()")
    violations={}
    def note(r,d): violations.setdefault(r,[]).append(d)

    # Same requirement as the first pass: count the rules EXECUTED, so an
    # audit that has gone mute no longer reads as a green audit.
    executed=set()
    def ran(*r): executed.update(r)
    EXPECTED_RULES=13
    print(f"{BAR}\nAdversarial review, second pass — {len(states)} states\n{BAR}")

    ran('R11')
    # R11 — jargon, technical values and machine English in rendered text
    for e in states:
        await pg.evaluate("(i)=>window.__go(i)",e); await pg.wait_for_timeout(240)
        # Every screen migrated off `#screen` onto a real route — the mediaSheet,
        # the add screen, the arbitration screen, the release picker, the
        # quality profile — answers to ONE generic rung: any OPEN screen
        # carries a `data-key`, so its presence is enough, its identity never
        # read here. It sits LAST in the ladder — the same order `audit.py`,
        # `dest.py` and `states.py` use — so every pre-existing case resolves
        # exactly as before and a layer opened OVER a route is still what gets
        # read. A state opening a route this rung does not cover would
        # otherwise fall through to `#view` and this rule would read a page
        # the state does not show.
        bad=await pg.evaluate("""()=>{
          const r=document.querySelector('#dlg').hasAttribute('data-open')?'#dlg'
                 :document.querySelector('#screen').hasAttribute('data-open')?'#screen'
                 :document.querySelector('#sheet').hasAttribute('data-open')?'#sheet'
                 :document.querySelector('[data-part="screen"][data-open][data-key]')?'[data-part="screen"][data-open][data-key]'
                 :'#view';
          const t=document.querySelector(r).innerText;
          const patterns=[[/\\bundefined\\b/,'undefined'],[/\\bNaN\\b/,'NaN'],[/\\bnull\\b/,'null'],
            [/\\[object /,'[object'],[/\\b0\\/0\\b/,'0/0'],[/\\*\\s\\*\\s\\*/,'cron expression'],
            [/\\bError\\b/,'Error'],[/\\bTrue\\b|\\bFalse\\b/,'raw boolean']];
          return patterns.filter(([re])=>re.test(t)).map(([,n])=>n);}""")
        for x in bad: note("R11 visible jargon or technical value", f"{e} : {x}")

    ran('R12')
    # R12 — uniformity of the primary action buttons
    geo=await pg.evaluate("""async ()=>{
      const out={};
      const measure=(sel,name)=>{const el=document.querySelector(sel); if(!el) return;
        const s=getComputedStyle(el); const b=el.getBoundingClientRect();
        out[name]={h:Math.round(b.height),weight:s.fontWeight,size:s.fontSize,justify:s.justifyContent,
                   radius:s.borderRadius,icon:!!el.querySelector(':scope > svg')};};
      window.__go('acq-now-loaded'); await new Promise(r=>setTimeout(r,220));
      measure('[data-part="card/foot"].solid','card footer (primary)');
      window.__go('followsheet-gaps'); await new Promise(r=>setTimeout(r,240));
      measure('.sact.primary','sheet (primary)');
      window.__go('mediasheet-suggestion-movie'); await new Promise(r=>setTimeout(r,240));
      measure('.mediaadd','media sheet (add)');
      window.__go('acq-add-results'); await new Promise(r=>setTimeout(r,240));
      measure('.resbtn','search result');
      window.__go('lib-delete'); await new Promise(r=>setTimeout(r,240));
      measure('.dlgbtn.danger','dialog (danger)');
      return out;}""")
    print("Primary button geometry:")
    for k,v in geo.items(): print(f"   {k:26} {v}")
    hs=[v["h"] for v in geo.values()]
    if max(hs)-min(hs) > 2: note("R12 inconsistent button heights", f"{min(hs)}–{max(hs)} px : {json.dumps(geo,ensure_ascii=False)}")
    for k,v in geo.items():
        # « normal » is NOT centred: rule slackness of that kind let a real
        # misalignment through. Rule: with an icon → left-aligned; without →
        # centred.
        expected = "flex-start" if v.get("icon") else "center"
        if v["justify"] != expected:
            note("R12 non-conformant alignment", f"{k}: {v['justify']} instead of {expected} (icon: {v.get('icon')})")
        if v["radius"] != "8px": note("R12 inconsistent radius", f"{k} : {v['radius']}")
        if v["size"] != "13.5px": note("R12 inconsistent text size", f"{k} : {v['size']}")

    ran('R13')
    # R13 — sheet uniformity: the SAME BASE for all of them.
    #
    # Sampling a handful of fixed states, none of them an INCOMPLETE medium,
    # is exactly how a divergence slips through unseen. The sample is
    # therefore drawn from the DATA: complete, incomplete, without visual,
    # suggestion, film and series.
    orders=await pg.evaluate("""async ()=>{
      const out={}, picks=[];
      const titles=Object.keys(SHEETS_RAW ?? {});
      const take=(pred, n)=>titles.filter(pred).slice(0, n);
      const incomplete=(t)=>{const s=OWNED[t]??OWNED[baseTitle(t)];
        if(!s) return false; const f=sheetFor(t); if(!f?.seasons) return false;
        return f.seasons.some(x=>x.ep && (s[String(x.n)]??[]).length < x.ep);};
      picks.push(...take(t=>sheetFor(t)?.k==='movie', 2));
      picks.push(...take(t=>sheetFor(t)?.k==='show' && !incomplete(t), 2));
      picks.push(...take(incomplete, 4));
      picks.push(...take(t=>!(HERO_IMAGES[t]??HERO_IMAGES[baseTitle(t)]), 2));
      for (const t of [...new Set(picks)]) {
        window.__reset(); applyState({page:'lib', phase:'ready'});
        window.__screens.mediaSheet(t);
        await new Promise(r=>setTimeout(r,240));
        const b=document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"] .body');
        if (!b) { out[t]=['EMPTY SHEET']; continue; }
        out[t]=[...b.children]
          .filter(x=>x.getBoundingClientRect().height>0 && !x.classList.contains('note'))
          .map(x=>{const hh=x.querySelector('.h2');
            return hh ? hh.textContent.trim() : (x.className||x.tagName).toString().split(' ')[0];});
      }
      return out;}""")
    print(f"\nMedia-sheet base, over {len(orders)} media drawn from the data:")
    # Sections that are OPTIONAL by nature (no trailer, unknown catalogue) do
    # not count as divergence; the skeleton does.
    OPT = {"trailer", "noinfo", "rulenote"}
    def skeleton(l):
        return [s.replace("Création", "X").replace("Réalisation", "X") for s in l if s not in OPT]
    shapes = {}
    for k, v in orders.items():
        shapes.setdefault(tuple(skeleton(v)), []).append(k)
    for f, l in shapes.items():
        print(f"   {len(l):2d} media · {' → '.join(f)}")
    if len(shapes) > 1:
        ref = max(shapes.items(), key=lambda kv: len(kv[1]))[0]
        for f, l in shapes.items():
            if f != ref:
                note("R13 sheet not following the common base",
                     f"{', '.join(l[:3])} : {' → '.join(f)} instead of {' → '.join(ref)}")

    ran('R14')
    # R14 — every layer closes via the scrim AND via Back
    #
    # `acq-ajout-resultats` and `fiche-serie` both left `#screen` for real
    # routes rendered inside `#coquille`: their open/close check is the screen
    # itself, not the legacy layer id. The mediaSheet is named by the identity it
    # carries (`data-key="mediaSheet:…"`) rather than by a bare `[data-part="screen"][data-open]`,
    # which two stacked screens would both answer to. Every case closes the
    # same way from the operator's point of view (the screen's own « Retour »,
    # the scrim for a layer), so only the selector differs.
    R14_CASES = [
        ("followsheet-gaps", "#sheet", "scrim"),
        ("lib-delete", "#dlg", "scrim"),
        ("mediasheet-series", '[data-part="screen"][data-open][data-key^="mediaSheet:"]', "back"),
        ("acq-add-results", '[data-part="screen"][data-open]', "back"),
    ]
    for id_, sel, closing in R14_CASES:
        await pg.evaluate("(i)=>window.__go(i)", id_); await pg.wait_for_timeout(300)
        opened = await pg.evaluate("(s)=>!!document.querySelector(s)?.hasAttribute('data-open')", sel)
        if closing == "scrim":
            await pg.evaluate("()=>document.querySelector('#scrim').click()"); await pg.wait_for_timeout(300)
            if await pg.evaluate("(s)=>!!document.querySelector(s)?.hasAttribute('data-open')", sel):
                note("R14 layer not closable via the scrim", f"{id_}")
        else:
            await pg.evaluate("(s)=>document.querySelector(s+' .fback').click()", sel); await pg.wait_for_timeout(350)
            if await pg.evaluate("(s)=>!!document.querySelector(s)?.hasAttribute('data-open')", sel):
                note("R14 screen not closable via Back", f"{id_}")
        if not opened: note("R14 layer that does not open", id_)

    ran('R15')
    # R15 — the three Suivis modes show the SAME number of items
    n=await pg.evaluate("""async ()=>{const o={};
      for (const m of ['acq-follows-list','acq-follows-groupe','acq-follows-grid']) {
        window.__go(m); await new Promise(r=>setTimeout(r,240));
        o[m]=document.querySelectorAll('#view [data-part="card"], #view .tile').length;}
      return o;}""")
    print("\nItems per Suivis mode:", n)
    if len(set(n.values()))>1: note("R15 inconsistent Suivis modes", json.dumps(n))

    ran('R16')
    # R16 — the badge is the sum it claims to be
    bad=await pg.evaluate("""async ()=>{const out=[];
      for (const s of ['real','loaded']) { window.__store.write({scen: s}); window.__go('acq-now-'+(s==='real'?'idle':'loaded'));
        await new Promise(r=>setTimeout(r,240));
        const badge=document.querySelector('[data-page=acq] .navbadge');
        const expected=derived.takeable().length+derived.blocked().length;
        const read=badge?Number(badge.textContent):0;
        if (read!==expected) out.push(`${s}: badge ${read} != to-grab+to-resolve ${expected}`);
        const tab=document.querySelector('[data-part="segment"] .n');
        const read2=tab?Number(tab.textContent):0;
        if (read2!==expected) out.push(`${s}: tab badge ${read2} != ${expected}`);
      } return out;}""")
    for x in bad: note("R16 badge not derived", x)

    ran('R17')
    # R17 — every destructive mutation is confirmed or reversible
    rev=await pg.evaluate("""async ()=>{const out=[];
      window.__go('acq-follows-list'); await new Promise(r=>setTimeout(r,240));
      document.querySelector('#view .swipe .act.remove').click(); await new Promise(r=>setTimeout(r,320));
      if (!document.querySelector('#toastundo')) out.push('removing a follow: no undo');
      window.__go('lib-list'); await new Promise(r=>setTimeout(r,260));
      const before=world.lib.length;
      document.querySelector('#libitems .swipe .act.remove').click(); await new Promise(r=>setTimeout(r,320));
      if (!document.querySelector('#dlg').hasAttribute('data-open')) out.push('deleting a medium: no confirmation');
      if (world.lib.length!==before) out.push('deleting a medium: mutation BEFORE confirmation');
      return out;}""")
    for x in rev: note("R17 destruction without a guard", x)

    ran('R26')
    # R26 — the melting visual header is a trait of ALL media sheets, not only
    # the ones that were looked at. The rule is conditional and says so: a
    # medium WITHOUT a visual degrades to a flat field (a difference justified
    # by its own context). A medium WITH a visual that has no header signals a
    # second rendering path that was never converted.
    heroes=await pg.evaluate("""async ()=>{const out=[];
      const docRoot=document.documentElement;
      // BOTH THEMES. An orphan selector left by a deletion gave the header
      // position:absolute in the light theme only: the sheet was upside down,
      // and the rule looked at the dark theme alone.
      for (const theme of [null,'light']) {
        theme ? docRoot.setAttribute('data-theme',theme) : docRoot.removeAttribute('data-theme');
        for (const s of window.__states()) {
          window.__go(s); await new Promise(r=>setTimeout(r,300));
          // The media sheet left `#screen` for a real route; it is added here
          // by the identity it carries, or this rule about ALL media sheets
          // would stop seeing the very screen it is named after.
          const root=document.querySelector('#screen[data-open], #sheet[data-open]')
                  || document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]');
          const hero=root && root.querySelector('.hero');
          if (!hero) continue;
          const name=`${s}/${theme||'dark'}`;
          const wrap=hero.closest('.herowrap');
          if (!wrap) { out.push(`${name}: sheet without .herowrap`); continue; }
          const bg=wrap.querySelector('.herobg');
          if (!bg) { out.push(`${name}: sheet without a header`); continue; }
          const sb=getComputedStyle(bg), rb=bg.getBoundingClientRect(), rh=hero.getBoundingClientRect();
          // The header OCCUPIES the top: it pushes content, it does not float.
          if (sb.position!=='relative') out.push(`${name}: header in ${sb.position}`);
          const hasVisualHere=!wrap.hasAttribute('data-no-poster');
          // With no visual the field is deliberately short: it holds the place
          // and claims nothing. The threshold applies only to a real image.
          const threshold = hasVisualHere ? 240 : 48;
          if (rb.height < threshold)
            out.push(`${name}: top band of ${Math.round(rb.height)}px (< ${threshold})`);
          // The title sits UNDER the image, overlapping its lower edge.
          if (rh.top <= rb.top) out.push(`${name}: title above the header`);
          if (rh.top >= rb.bottom) out.push(`${name}: title detached from the header`);
          // Text NEVER rests on the bare image: the closing gradient is what
          // makes the rule true, not good intentions.
          if (!getComputedStyle(bg,'::after').backgroundImage.includes('gradient'))
            out.push(`${name}: header without a legibility gradient`);
          const hasVisual=!wrap.hasAttribute('data-no-poster');
          if (hasVisual && sb.backgroundImage==='none') out.push(`${name}: header declared but empty`);
        }
      }
      docRoot.removeAttribute('data-theme');
      return out;}""")
    for x in heroes: note("R26 visual header not generalised", x)

    ran('R27')
    # R27 — a trailer ALWAYS opens in YouTube, never inside the application,
    # and the sheet offers it wherever one arrives from: library, acquisitions
    # or Découvrir. The rule carries that decision: a sheet promising in-app
    # playback would be wrong even if it were pretty.
    trailers=await pg.evaluate("""async ()=>{const out=[];
      for (const s of window.__states()) {
        window.__go(s); await new Promise(r=>setTimeout(r,300));
        // Same reason as R26 above: the sheet is a route now, and it is where
        // the trailer lives — read it by its key or this rule goes quiet.
        const root=document.querySelector('#screen[data-open], #sheet[data-open]')
                || document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]');
        if (!root || !root.querySelector('.hero')) continue;
        const el=root.querySelector('.trailer');
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
    for x in trailers: note("R27 trailer not conformant", x)

    ran('R28')
    # R28 — there must be exactly ONE back-control design, compatible with
    # every page. A floating white bar over the image created a second design
    # which, on screens without an image, COVERED the title instead of pushing
    # it. The rule measures both things: a single signature, and never content
    # glued or covered.
    backs=await pg.evaluate("""async ()=>{const sig={}, glued=[];
      for (const s of window.__states()) {
        window.__go(s); await new Promise(r=>setTimeout(r,300));
        // The screen carrying the bar is the legacy layer when it is up, and
        // otherwise the migrated mediaSheet, named by its own key: leaving the
        // mediaSheet out would silently drop five states from this sweep, and a
        // rule that has gone quiet is not a rule that passes.
        const screen=document.querySelector('#screen[data-open]')
                  || document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]');
        const bar=screen?.querySelector('.screenbar');
        if (!bar) continue;
        const btn=bar.querySelector('.fback');
        if (!btn) { glued.push(`${s}: bar without a back control`); continue; }
        const sb=getComputedStyle(bar), sx=getComputedStyle(btn), rb=bar.getBoundingClientRect();
        // A bar outside the flow pushes nothing: it ends up covering.
        if (sb.position!=='static' && sb.position!=='relative')
          glued.push(`${s}: bar in ${sb.position} — it does not push content`);
        const k=[sb.position, sb.backgroundColor, sx.color, Math.round(rb.height)].join('|');
        (sig[k] ||= []).push(s);
        // Measure the first PIXEL OF TEXT, not the first box: a container can
        // touch the bar through its padding without anything being glued.
        const port=screen.querySelector('[data-part="viewport"]');
        const text=port && [...port.querySelectorAll('h1,h2,h3,p,span,button,a,label')]
          .find(e=>{const r=e.getBoundingClientRect();
                    return r.height>0 && (e.textContent||'').trim().length>1 && !e.closest('.note');});
        if (text) {
          const gap=text.getBoundingClientRect().top-rb.bottom;
          if (gap < 8) glued.push(`${s}: text ${Math.round(gap)}px from the bar`);
        }
      }
      return {sig, glued};}""")
    if len(backs["sig"]) > 1:
        for k, l in backs["sig"].items():
            note("R28 several back-control designs", f"{k} → {', '.join(l[:4])}")
    for x in backs["glued"]: note("R28 back control badly placed", x)
    print(f"\nDistinct back-control designs: {len(backs['sig'])} across "
          f"{sum(len(v) for v in backs['sig'].values())} screens")

    ran('R29')
    # R29 — episode presence is read from the LIST of owned numbers, never
    # from a « number <= owned count » threshold. That threshold assumes the
    # hole is at the end of the season: false for 35 series in this library.
    # The rule checks agreement between what is DISPLAYED and the data, on
    # series with an INTERNAL hole — where the two methods diverge.
    ep=await pg.evaluate("""async ()=>{const out=[];
      // ALL series with an INTERNAL hole, not a sample: that is where the
      // threshold and the list diverge, so that is where the rule has a chance
      // to bite.
      const withHoles=Object.entries(OWNED).filter(([t,s])=>
        Object.values(s).some(l=>l.length && l.some((n,i)=>n!==i+1))).map(([t])=>t);
      if (!withHoles.length) return ['no series with an internal hole — the rule would be vacuous'];
      let inspected=0;
      for (const title of withHoles) {
        window.__reset(); applyState({page:'lib', phase:'ready'});
        window.__screens.mediaSheet(title);
        await new Promise(r=>setTimeout(r,240));
        for (const det of document.querySelectorAll('[data-part="screen"][data-open][data-key^="mediaSheet:"] details[data-part="season"]')) {
          const num=Number((det.querySelector('summary')?.textContent||'').match(/Saison\\s+(\\d+)/)?.[1]);
          const owned=ownedFor(title, num);
          if (!owned) continue;
          // BOTH renderings: titled rows AND the numbered matrix.
          const cells=[...det.querySelectorAll('[data-part="episode/row"]')].map(r=>[
              Number((r.querySelector('.en')?.textContent||'').replace(/\\D/g,'')), r])
            .concat([...det.querySelectorAll('[data-part="episode/set"] [data-part="episode"]')].map(c=>[Number(c.textContent), c]));
          for (const [n, el] of cells) {
            if (!n || el.classList.contains('announced')) continue;
            inspected++;
            const shown=el.classList.contains('in_library');
            if (shown !== owned.has(n))
              out.push(`${title} S${num}E${n}: shown ${shown?'present':'missing'}, actually ${owned.has(n)?'present':'missing'}`);
          }
        }
      }
      if (!inspected) out.push('no episode inspected — the rule proves nothing');
      return out.slice(0, 12);}""")
    for x in ep: note("R29 episode presence not matching the data", x)

    ran('R30')
    # R30 — ONE season rendering. Two existed: a titled list (29 series) and a
    # numbered matrix (177), and twelve sheets contained both at once. A sheet
    # must not have two faces depending on the data it happens to have.
    renders=await pg.evaluate("""async ()=>{
      const c={rows:[], matrix:[], mixed:[], neverOpened:[], noSeason:[]};
      const series=Object.keys(SHEETS_RAW).filter(t=>sheetFor(t)?.k!=='movie');
      // The sheet is a ROUTE now: it commits a frame later than an `innerHTML`
      // assignment did. A FIXED wait makes this rule's coverage depend on how
      // loaded the host is — one too short and every sheet reads « no season »,
      // every series is skipped, and the rule reports nothing behind a green
      // exit code. Waiting for THE SCREEN ONE ASKED FOR — its own key — removes
      // the guess, and a timeout is reported instead of silently skipped.
      const waitFor=async(t)=>{
        const key='mediaSheet:'+t.normalize('NFC');
        for (let i=0;i<40;i++) {
          const el=document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]');
          if (el && el.dataset.key===key) return el;
          await new Promise(r=>setTimeout(r,25));
        }
        return null;
      };
      for (const t of series) {
        window.__reset(); applyState({page:'lib',phase:'ready'});
        window.__screens.mediaSheet(t);
        const s=await waitFor(t);
        if (!s) { c.neverOpened.push(t); continue; }
        const dets=[...s.querySelectorAll('details[data-part="season"]')];
        // A series whose provider declares no season draws none: a stated
        // absence, counted APART from a sheet that never opened.
        if (!dets.length) { c.noSeason.push(t); continue; }
        const shapes=new Set(dets.map(d=>
          d.querySelector('[data-part="episode/row"]') ? 'rows' : d.querySelector('[data-part="episode/set"] [data-part="episode"]') ? 'matrix' : 'empty'));
        shapes.delete('empty');
        if (shapes.size>1) c.mixed.push(t);
        else if (shapes.has('rows')) c.rows.push(t);
        else if (shapes.has('matrix')) c.matrix.push(t);
      }
      return c;}""")
    inspected = len(renders["rows"]) + len(renders["matrix"]) + len(renders["mixed"])
    print(f"\nSeason rendering — list: {len(renders['rows'])} · "
          f"matrix: {len(renders['matrix'])} · MIXED: {len(renders['mixed'])} "
          f"· no season: {len(renders['noSeason'])} "
          f"· inspected: {inspected}/{inspected + len(renders['noSeason']) + len(renders['neverOpened'])}")
    # A sheet that never opened is a MEASUREMENT failure, never a series to
    # skip: silence would let a slow host empty this rule and still exit green.
    for t in renders["neverOpened"][:6]:
        note("R30 sheet never opened — nothing was measured on it", t)
    if not inspected:
        note("R30 no season inspected — the rule proves nothing",
             f"{len(renders['noSeason'])} without a season, "
             f"{len(renders['neverOpened'])} never opened")
    for t in renders["mixed"][:6]:
        note("R30 two season renderings within ONE sheet", t)
    if renders["rows"] and renders["matrix"]:
        note("R30 two season renderings across sheets",
             f"{len(renders['rows'])} as a list (e.g. {renders['rows'][0]}) against "
             f"{len(renders['matrix'])} as a matrix (e.g. {renders['matrix'][0]})")

    ran('R31')
    # R31 — a card body opens the panel, and that panel offers follow actions
    # ONLY for a medium that is actually followed.
    #
    # What this guards has not changed, only where it is enforced. Offering
    # « Mettre en pause » or « Retirer le suivi » from the library produced a
    # panel whose content varied with something the screen never showed —
    # whether the title happened to be followed. The panel is now built from
    # what is true about the medium, so the rule checks that derivation instead
    # of forbidding a destination.
    dest=await pg.evaluate("""async ()=>{const out=[];
      const followed=new Set(world.follows.map(x=>x.t));
      for (const state_ of ['lib-incomplete','lib-list','lib-recent']) {
        for (let i=0; i<6; i++) {
          window.__go(state_); await new Promise(r=>setTimeout(r,300));
          const toggle=document.querySelector('[data-lmode="list"]');
          if (toggle) { toggle.click(); await new Promise(r=>setTimeout(r,260)); }
          const cards=[...document.querySelectorAll('#view [data-part="card"] [data-part="card/body"]')];
          if (i>=cards.length) break;
          const full=cards[i].querySelector('[data-part="card/title"]')?.textContent ?? '?';
          const title=full.slice(0,26);
          cards[i].click(); await new Promise(r=>setTimeout(r,300));
          const sheet=document.querySelector('#sheet');
          if (!sheet.hasAttribute('data-open')) { out.push(`${state_} · « ${title} » opens nothing`); continue; }
          const actions=[...sheet.querySelectorAll('.sact')].map(x=>x.textContent.trim());
          if (!followed.has(full)) {
            for (const a of actions)
              if (/^(Mettre en pause|Ne plus chercher|Retirer)/.test(a))
                out.push(`${state_} · « ${title} » is not followed yet offers « ${a} »`);
          }
          document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
          await new Promise(r=>setTimeout(r,260));
        }
      } return out;}""")
    for x in dest: note("R31 panel offering an action the medium does not support", x)

    print()
    if not violations: print("No violations on this second pass.")
    for r,l in sorted(violations.items()):
        print(f"■ {r} — {len(l)}")
        for x in l[:5]: print("   ",x)
    print(f"\nJS errors: {errs or 'none'}")
    print(f"{BAR}\nTOTAL, second pass: {sum(len(v) for v in violations.values())} violations "
          f"· {len(executed)}/{EXPECTED_RULES} rules executed")
    if len(executed) != EXPECTED_RULES:
        print(f"⚠ {EXPECTED_RULES - len(executed)} rule(s) never executed: "
              "a mute audit is not a green audit.")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if violations or errs: raise SystemExit(1)
asyncio.run(main())
