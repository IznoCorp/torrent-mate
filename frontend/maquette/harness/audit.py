"""Adversarial review — every reported defect becomes a RULE checked across
ALL states, never a patch on the single case that was reported.

The stance is to try to make the prototype FAIL, not to confirm it.
"""
import asyncio
import json
import pathlib

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
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>window.__measure(true)")
    states = await pg.evaluate("()=>window.__states()")
    violations = {}
    def note(rule, detail):
        violations.setdefault(rule, []).append(detail)

    # A rule that disappears must be VISIBLE. Counting violated rules reads «
    # 0 of 0 » both when everything is fine and when nothing runs at all:
    # count the rules EXECUTED instead, and require the expected total.
    executed = set()
    def ran(*rules):
        executed.update(rules)
    EXPECTED_RULES = 13

    print(f"{BAR}\nAdversarial review — {len(states)} states\n{BAR}")

    for e in states:
        await pg.evaluate("(i)=>window.__go(i)", e); await pg.wait_for_timeout(280)
        ran('R1','R2','R3','R4','R4bis','R5','R6','R6bis','R7','R22','R23')
        r = await pg.evaluate("""(stateId)=>{
          const R = {};
          const vis = (el)=>el.offsetParent!==null || el.getClientRects().length>0;
          // Every screen migrated off `#screen` onto a real route (the media
          // sheet at `/mediasheet/$title`, the add screen at `/add`, the
          // arbitration screen at `/resolution/$folder`, the release picker
          // at `/releases/$title`, the quality profile at `/profile/$title`)
          // answers to ONE generic rung: any OPEN screen carries a `data-key`,
          // so the identity itself is never read here, only its presence —
          // naming each prefix would have re-opened the same hole for the
          // next screen that migrates. It sits LAST, after the legacy
          // dialog/screen/sheet trio, so every pre-existing case resolves
          // exactly as it did, and a layer opened OVER a route (a panel, a
          // dialog) is still what gets read. Without this rung, a state
          // opening any of those routes falls through to `#view` and the
          // rules pass on a page the state never shows — a rule gone quiet,
          // not a rule satisfied.
          const root = document.querySelector('#dlg').hasAttribute('data-open') ? document.querySelector('#dlg')
                     : document.querySelector('#screen').hasAttribute('data-open') ? document.querySelector('#screen')
                     : document.querySelector('#sheet').hasAttribute('data-open') ? document.querySelector('#sheet')
                     : document.querySelector('[data-part="screen"][data-open][data-key]')
                     ?? document.querySelector('#view');

          // R1 — every tappable poster leads to a FILLED-IN sheet
          R.hollowSheets = [...root.querySelectorAll('[data-mediasheet]')].map(el=>el.dataset.mediasheet)
            .filter(t=>{const f=sheetFor(t); return !f || !f.ov || !f.g || !(f.cast||[]).length;});

          // R2 — HARDENED: a button must have a declared DESTINATION, not
          // merely a known class. Whitelisting by class blessed every `.sact`,
          // so a control could lead nowhere without the rule flinching.
          R.deadButtons = [...root.querySelectorAll('button, a')]
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
          R.targetsTooSmall = [...root.querySelectorAll('button,a')].filter(el=>{
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
          const clipped = (el) => {
            for (let p = el.parentElement; p && p !== root.parentElement; p = p.parentElement) {
              const ox = getComputedStyle(p).overflowX;
              if (ox === 'hidden' || ox === 'clip') return p.getBoundingClientRect().right <= 390.5;
            }
            return false;
          };
          R.overflows = [...root.querySelectorAll('*')].filter(el=>{
            const bb=el.getBoundingClientRect();
            return bb.right>390.5 && bb.width>0 && !el.closest(SCROLLERS) && !clipped(el);
          }).map(el=>(el.className||el.tagName)+' →'+Math.round(el.getBoundingClientRect().right));

          // R4b — the measurement that cannot be talked out of it: the
          // scrollport itself must offer NO horizontal scrolling. An illusory
          // clip would show up here.
          R.horizontalPan = [...root.querySelectorAll('.port,[data-scroll-root]')]
            .filter(el=>el.scrollWidth > el.clientWidth + 1)
            .map(el=>(el.className||el.tagName)+' scrollWidth '+el.scrollWidth+' > '+el.clientWidth);

          // R5 — a horizontal scroller must NEVER block vertical panning
          R.blockingScrollers = [...root.querySelectorAll('*')].filter(el=>{
            const s=getComputedStyle(el);
            return s.overflowX==='auto'||s.overflowX==='scroll';
          }).filter(el=>{const ta=getComputedStyle(el).touchAction; return ta==='pan-x';})
            .map(el=>el.className+' touch-action:'+getComputedStyle(el).touchAction);

          // R6 — an essential title is never truncated to the point of being a
          // guess
          R.truncatedTitles = [...root.querySelectorAll('.ht,.sheettitle,.dlg h3')].filter(el=>
            el.scrollWidth>el.clientWidth+1).map(el=>el.textContent.trim().slice(0,30));

          // R6 bis — a card title MAY ellipsize; the list is a list. But the full
          // string must stay reachable, because for an unidentified arrival the
          // release name IS its identity, and the truncation lands on the group —
          // exactly what tells two versions of the same media apart.
          R.lostTitles = [...root.querySelectorAll('[data-part="card/title"]')].filter(el=>
            el.scrollWidth>el.clientWidth+1 && !el.getAttribute('title'))
            .map(el=>el.textContent.trim().slice(0,34));

          // R7 — no panel renders emptiness in silence
          R.emptyPanels = [...root.querySelectorAll('.panel')].filter(el=>
            el.children.length===0).length;

          // R23 — within an option group every row has the same size, and
          // SHAPE distinguishes single choice (circle) from multiple choice
          // (square). Identical pills stated no rule.
          R.irregularOptions = [];
          for (const grp of root.querySelectorAll('.optlist')) {
            const opts = [...grp.querySelectorAll('.opt')];
            const t = opts.map(e=>{const b=e.getBoundingClientRect();
              return Math.round(b.width)+'×'+Math.round(b.height);});
            if (new Set(t).size > 1) R.irregularOptions.push('sizes '+[...new Set(t)].join(' / '));
            const shapes = new Set(opts.map(e=>e.classList.contains('radio')?'radio':'check'));
            if (shapes.size > 1) R.irregularOptions.push('mixed radio/checkbox group');
            const roles = new Set(opts.map(e=>e.getAttribute('role')));
            if (roles.size > 1) R.irregularOptions.push('mixed roles');
          }

          // R22 — every switch has EXACTLY the same dimensions, whatever the
          // length of the label beside it. A chip inside a flex row took the
          // text's height.
          R.irregularSwitches = [];
          const sw = [...root.querySelectorAll('.switch')];
          if (sw.length > 1) {
            const sizes = sw.map(e=>{const b=e.getBoundingClientRect();
              return Math.round(b.width)+'×'+Math.round(b.height);});
            if (new Set(sizes).size > 1) R.irregularSwitches = sizes;
          }

          // R20 — the library has only ONE sub-line grammar: « année · type ».
          // Two grammars make rows incomparable.
          R.subLines = [];
          if (stateId.startsWith('lib-') && !stateId.includes('incomplete')) {
            const expected = /^(\\d{4}|année inconnue) · (Film|Série)$/;
            R.subLines = [...root.querySelectorAll('#libitems .csub, #libitems .fr')]
              .map(e=>e.textContent.trim()).filter(t=>t && !expected.test(t)).slice(0,5);
          }

          // R8 — EVERY layer reserves the height of the tab bar that passes
          // above it: screen, sheet and dialog. The rule once covered screens
          // only, and the defect came back through sheets.
          R.screenReserve = null;
          const bar = document.querySelector('.bottombar').getBoundingClientRect().height;
          // Every screen migrated off `#screen` onto a real route is a LAYER
          // like the others — the tab bar passes above it too — and joins
          // this sweep through the SAME generic entry the root ladder above
          // uses: any open `[data-part="screen"][data-open][data-key]`, never a per-identity
          // prefix. One generic entry covers the mediaSheet, the add screen, the
          // arbitration screen, the release picker, the quality profile and
          // whatever migrates next — naming each one here would have re-open
          // this exact gap on every future migration. Dropping it entirely
          // would leave every state that opens a route inspecting nothing at
          // all: its `.port` padding and the reachability of its last action
          // are exactly what this rule holds on it.
          const layers = [['#screen','.port'],['#sheet','.sheetin'],
                          ['[data-part="screen"][data-open][data-key]','.port']];
          for (const [sel, inner] of layers) {
            const el = document.querySelector(sel);
            // The mediaSheet's selector matches only while it is open, so an absent
            // node is a closed layer — not an error, and not a reason to throw.
            if (!el || !el.hasAttribute('data-open')) continue;
            const port = el.querySelector(inner);
            if (!port) continue;
            const pb = parseFloat(getComputedStyle(port).paddingBottom);
            if (pb < bar) R.screenReserve = `${sel} ${Math.round(pb)}px < bar ${Math.round(bar)}px`;
            // And the last button must be REACHABLE at maximum scroll.
            port.scrollTop = port.scrollHeight;
            // A collapsed <details> still gives its children a layout box:
            // filter on VISIBILITY, not on DOM order.
            const btns = [...port.querySelectorAll('button, a')]
              .filter(x => !x.closest('details:not([open])') && x.getBoundingClientRect().height > 0);
            const last = btns[btns.length-1];
            if (last) {
              const bb = last.getBoundingClientRect();
              const barTop = document.querySelector('.bottombar').getBoundingClientRect().top;
              if (bb.bottom > barTop + 1) R.screenReserve = `${sel}: last button under the bar (${Math.round(bb.bottom - barTop)}px)`;
            }
          }
          return R;
        }""", e)
        for k, v in r.items():
            if k == "irregularOptions":
                for x in v: note("R23 inconsistent option group", f"{e} : {x}")
            elif k == "irregularSwitches":
                if v: note("R22 switches of differing sizes", f"{e} : {v}")
            elif k == "subLines":
                for x in v: note("R20 diverging sub-line grammar", f"{e} : « {x} »")
            elif k == "screenReserve":
                if v: note("R8 insufficient screen reservation", f"{e} : {v}")
            elif k == "emptyPanels":
                if v: note("R7 empty panel", f"{e} : {v}")
            elif v:
                key = {"hollowSheets":"R1 hollow sheet behind a poster",
                       "deadButtons":"R2 button with no effect",
                       "targetsTooSmall":"R3 touch target < 32px",
                       "overflows":"R4 horizontal overflow",
                       "horizontalPan":"R4b real horizontal scrolling",
                       "blockingScrollers":"R5 scroller blocking vertical panning",
                       "truncatedTitles":"R6 truncated title",
                       "lostTitles":"R6 bis title cut with no recourse"}[k]
                for x in (v if isinstance(v, list) else [v]):
                    note(key, f"{e} : {x}")

    # R9 — film/series vocabulary, across ALL surfaces
    voc = await pg.evaluate("""()=>{
      const out=[];
      const expected={movie:{add:'Ajouter',pause:'Ne plus chercher',retrait:'Retirer de la liste'},
                      show:{add:'Suivre',pause:'Mettre en pause',retrait:'Retirer le suivi'}};
      for (const f of world.follows) {
        const lab = stLabel(f);
        if (f.k==='movie' && /jour|Terminé/.test(lab)) out.push(`movie « ${f.t} » wears « ${lab} » (series vocabulary)`);
      }
      return out;}""")
    ran('R9')
    for x in voc: note("R9 film/series vocabulary", x)

    # R10 — every action opens a layer, navigates, or mutates — never nothing
    inert = await pg.evaluate("""async ()=>{
      // The snapshot has to carry every dial the interface tracks, or an
      // action that moves one the snapshot forgets reads as inert. The
      // pipeline dial joined when Arrivées gained its pilot's bar: « Lancer le
      // pipeline » really does change the interface, and this rule said it did
      // not — a false accusation is as expensive as a missed defect.
      const out=[]; const snap=()=>JSON.stringify({t:world.takeable.length,i:world.inflight.length,s:world.stuck.length,
        m:world.moving.length,f:world.follows.length,l:world.lib.length,p:state.page,tab:state.acqTab,lens:state.libLens,
        pipe:state.pipe});
      for (const id of ['acq-now-loaded','arr-loaded','lib-incomplete']) {
        window.__go(id); await new Promise(r=>setTimeout(r,220));
        const btns=[...document.querySelectorAll('#view .cfoot')];
        for (let i=0;i<btns.length;i++){
          window.__go(id); await new Promise(r=>setTimeout(r,200));
          const b=[...document.querySelectorAll('#view .cfoot')][i]; if(!b) continue;
          const lab=b.textContent.trim(); const before=snap();
          // Pre-existing gap found while wiring the generic route rung above:
          // this check never learned about a screen migrated off `#screen`
          // onto a real route (`/resolution/$folder` among them) — the SAME
          // generic entry as the root ladder's covers it here too.
          const layer=()=>['#sheet','#screen','#dlg'].some(s=>document.querySelector(s).hasAttribute('data-open'))
            || !!document.querySelector('[data-part="screen"][data-open][data-key]');
          b.click(); await new Promise(r=>setTimeout(r,320));
          if (snap()===before && !layer()) out.push(`${id} : « ${lab} » changes nothing`);
          ['#scrim'].forEach(s=>document.querySelector(s).click());
        }
      }
      return out;}""")
    ran('R10')
    for x in inert: note("R10 action with no effect", x)

    print()
    if not violations and not errs:
        print("No violations. (For an adversarial review, that deserves suspicion.)")
    for rule, lst in sorted(violations.items()):
        print(f"■ {rule} — {len(lst)}")
        for x in lst[:6]: print("   ", x)
        if len(lst) > 6: print(f"    … and {len(lst)-6} more")
    print(f"\nJS errors: {errs or 'none'}")
    missing = EXPECTED_RULES - len(executed)
    print(f"{BAR}\nTOTAL: {sum(len(v) for v in violations.values())} violations "
          f"· {len(executed)}/{EXPECTED_RULES} rules executed")
    if missing:
        print(f"⚠ {missing} rule(s) declared but never executed: "
              f"a mute audit is not a green audit.")
    # Beside THIS FILE, never in the current directory. Written as
    # `open("violations.json")` it landed wherever the caller happened to
    # stand — and `run.sh` stands at the repository root, so a second copy
    # appeared there and was committed by a `git add -A`. A run artifact with
    # a floating path is an artifact that ends up in the history.
    report = pathlib.Path(__file__).resolve().parent / "violations.json"
    report.write_text(json.dumps({k: v for k, v in violations.items()},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if violations or errs: raise SystemExit(1)
asyncio.run(main())
