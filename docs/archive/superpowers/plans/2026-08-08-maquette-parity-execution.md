# Maquette Parity Execution Plan (L0–L5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the Acquisition UI to measured pixel-parity with the operator maquette (390 px and ≥ md) plus four backend additions, with every claim backed by a measurement on the deployed staging build.

**Architecture:** Hybrid comparison (scripted DOM probe = hard gate, PIL overlay diff on maquette-mirroring synthetic data, GIF flow pass) driving fix→deploy→measure loops over six lots. CSS is transplanted verbatim from the maquette source under the existing `.mq` scope; the DOM adapts to the maquette, never the reverse. Spec: `docs/archive/superpowers/specs/2026-08-08-maquette-parity-method-design.md`. Contract: `docs/archive/superpowers/handoffs/2026-08-08-maquette-parity-handoff.md`.

**Tech Stack:** React + TS (frontend/), maquette CSS in `frontend/src/styles/ps/maquette-acquisition.css`, FastAPI + Pydantic + sqlite migrations (personalscraper/), chrome-devtools MCP, Python PIL, staging at `tm-staging.iznogoudatall.xyz`.

## Global Constraints

- Worktree `/Users/izno/dev/PersonalScraper/.claude/worktrees/acq-mobile`, branch `feat/acq-mobile`. Frontend commands from `frontend/`.
- `MAQ` = `/private/tmp/claude-501/-Users-izno-dev-PersonalScraper--claude-worktrees-acq-escalade/d8548240-3ead-448a-96f1-c31ea219ab69/scratchpad` (prior session: maquette + reference + serve.py + mint_session.py). `acquisition-prototype.html` and the operator's tabs are UNTOUCHABLE; render only `acquisition-prototype-debug.html` in MY OWN tab.
- `SCRATCH` = `/private/tmp/claude-501/-Users-izno-dev-PersonalScraper/ac74863d-444b-49bc-8923-a2a88beb4456/scratchpad` (this session: parity tools under `SCRATCH/parity/`, screenshots, token).
- Every `rg` MUST carry a type filter (`-t py`, `-g '*.tsx'`, `-g '*.css'`…). Every `curl` MUST carry `--connect-timeout 10 --max-time 30`. Never any server on 8710/8711 (the maquette server is 127.0.0.1:8801, localhost static only).
- Conventional Commits, French bodies, no AI attribution, no dev-phase references in code; in `frontend/` write « ticket 411 », never « #411 ».
- Operator arbitrations (handoff §3) are pinned by tests and NEVER regressed: « ··· » on every card at every pointer; grid badges carry numbers (`max(1, aired-owned)`), « ? » only for `non_verifie`/`verification_en_cours`, films « acquis / non acquis »; grouped mode = 4 urgency groups, chips stay on cards; nav pills primary.
- CSS values come verbatim from `MAQ/maquette-reference.md` — never re-improvised. Line references below are into that file.
- **GATES block** (run before every push): `cd frontend && npx tsc -b --noEmit && npx eslint src && npx vitest run` — expect 0 errors, all tests green (baseline 1274, count grows). Any Python change ⇒ also `make check` from the worktree root.
- **DEPLOY block**:
  ```bash
  cd /Users/izno/dev/PersonalScraper/.claude/worktrees/acq-mobile
  git push --no-verify origin feat/acq-mobile
  git fetch origin staging
  TREE=$(git rev-parse 'HEAD^{tree}')
  MERGE=$(git commit-tree "$TREE" -p HEAD -p origin/staging -m "staging: <msg>")
  git push --no-verify origin "${MERGE}:refs/heads/staging"
  # poll (~60 s autodeploy) until it serves MY sha:
  curl -s --connect-timeout 10 --max-time 30 \
    -H "Cookie: tm_session=$(cat "$SCRATCH/tm_session.txt")" \
    https://tm-staging.iznogoudatall.xyz/api/version
  ```
  `--no-verify` only when the diff is frontend-only AND GATES ran; run the pre-push suite for Python changes.
- **MEASURE block**: in MY app tab (emulated `390x844x2,mobile,touch`), first `/api/version` must equal the deployed sha (PWA trap); probe both tabs with the task's region map; run `probe_diff.py`; overlay when the task says so; append the ledger entry (`docs/archive/analysis/2026-08-08-maquette-parity-ledger.md`): loop id, sha, probe table (or « 0 divergences on N selectors »), overlay % + heatmap path, flows (GIF paths), gate outputs. No « conforme » without its measure.
- Synthetic states ONLY via `window.fetch` patch in `evaluate_script` (never `initScript`) + PointerEvents pull-to-refresh on `#acq-tabpanel` (down y=200 → move y=320 → up). Shared `library.db`/`.data/` — never test rows.
- One region per fix loop; a lot ends deployed + measured + logged before the next lot starts.

---

## L0 — Tooling (no app code)

### Task 1: Session prerequisites — token, maquette server, tabs

**Files:** none (environment only).

**Interfaces:** Produces: `SCRATCH/tm_session.txt` (24 h JWT), maquette served at `http://127.0.0.1:8801/acquisition-prototype-debug.html`, two emulated tabs (maquette, app).

- [ ] **Step 1: Re-mint the staging token into MY scratchpad** (the prior token expires 2026-08-08 ~19:49). `mint_session.py` writes next to itself, so copy it into `SCRATCH` first:
  ```bash
  mkdir -p "$SCRATCH/parity" && cp "$MAQ/mint_session.py" "$SCRATCH/mint_session.py"
  cd "$SCRATCH" && ~/staging/torrentmate-venv/bin/python mint_session.py
  # verify:
  curl -s --connect-timeout 10 --max-time 30 -H "Cookie: tm_session=$(cat "$SCRATCH/tm_session.txt")" https://tm-staging.iznogoudatall.xyz/api/version
  ```
  Expected: JSON with the current staging sha. If `mint_session.py` hardcodes its output path, edit the COPY in `SCRATCH` only.
- [ ] **Step 2: Start the maquette server** (background): `cd "$MAQ" && python3 serve.py` → verify `curl -s --connect-timeout 10 --max-time 30 http://127.0.0.1:8801/acquisition-prototype-debug.html | head -c 100` returns HTML.
- [ ] **Step 3: Open MY two tabs** via chrome-devtools MCP (`tabs_create_mcp`): tab M = the debug maquette URL, tab A = `https://tm-staging.iznogoudatall.xyz/acquisition` (inject the cookie if the login page shows). Emulate `390x844x2,mobile,touch` on BOTH; assert `document.documentElement.clientWidth === 390` in each before anything else.

### Task 2: DOM probe + differ, calibrated on known-zero regions

**Files:**
- Create: `SCRATCH/parity/probe.js` (source also lives in this plan)
- Create: `SCRATCH/parity/probe_diff.py`
- Create: `docs/archive/analysis/2026-08-08-maquette-parity-ledger.md`

**Interfaces:** Produces: `runProbe(REGIONS)` page function returning JSON; `python3 probe_diff.py maq.json app.json` printing a markdown divergence table (empty = pass) and exiting 0/1. Every later task's MEASURE step uses these unchanged.

- [ ] **Step 1: Write `probe.js`** — a function evaluated in each tab with a region map `{region: [selector, …]}`:
  ```js
  // probe.js — evaluate in-page: JSON.stringify(runProbe(REGIONS))
  const PROPS = ["fontSize","fontWeight","lineHeight","paddingTop","paddingRight","paddingBottom","paddingLeft",
    "marginTop","marginBottom","borderTopWidth","borderTopStyle","borderTopLeftRadius","borderBottomLeftRadius",
    "rowGap","columnGap","color","backgroundColor","borderTopColor","opacity","display","alignItems","justifyContent"];
  function runProbe(REGIONS) {
    if (document.documentElement.clientWidth !== 390) return { error: "clientWidth != 390" };
    const out = {};
    for (const [region, sels] of Object.entries(REGIONS)) {
      out[region] = [];
      for (const sel of sels) {
        document.querySelectorAll(sel).forEach((el, i) => {
          const r = el.getBoundingClientRect(), cs = getComputedStyle(el), styles = {};
          for (const p of PROPS) styles[p] = cs[p];
          out[region].push({ sel, i, w: +r.width.toFixed(1), h: +r.height.toFixed(1), styles });
        });
      }
    }
    return out;
  }
  ```
- [ ] **Step 2: Write `probe_diff.py`** — align by `(region, sel, i)`, compare `w`/`h` exactly (0.5 px float guard) and every style string exactly; print a markdown table `| region | sel[i] | prop | maquette | app |` of divergences; print `0 divergences on N selectors` when clean; exit 1 on divergence, 2 on selectors present in one file only (missing DOM = divergence too):
  ```python
  import json, sys
  maq, app = (json.load(open(p)) for p in sys.argv[1:3])
  rows, missing, n = [], [], 0
  for region in sorted(set(maq) | set(app)):
      am = {(e["sel"], e["i"]): e for e in maq.get(region, [])}
      aa = {(e["sel"], e["i"]): e for e in app.get(region, [])}
      for k in sorted(set(am) | set(aa), key=str):
          n += 1
          if k not in am or k not in aa:
              missing.append((region, k, "maquette" if k not in aa else "app-only" and "app" if k not in am else "maquette-only")); continue
          m, a = am[k], aa[k]
          for prop in ("w", "h"):
              if abs(m[prop] - a[prop]) > 0.5: rows.append((region, k, prop, m[prop], a[prop]))
          for prop, mv in m["styles"].items():
              av = a["styles"].get(prop)
              if mv != av: rows.append((region, k, prop, mv, av))
  for r in rows: print("| %s | %s[%s] | %s | %s | %s |" % (r[0], r[1][0], r[1][1], r[2], r[3], r[4]))
  for r in missing: print("| %s | %s[%s] | MISSING on one side | | |" % (r[0], r[1][0], r[1][1]))
  if not rows and not missing: print(f"0 divergences on {n} selectors"); sys.exit(0)
  sys.exit(2 if missing else 1)
  ```
  (Colors compare as computed strings; the token mapping in `maquette-acquisition.css` must make them resolve identically — a mismatch is a finding, not noise.)
- [ ] **Step 3: Calibrate on regions measured at zero by the prior session** — region map `{"tabs": [".mq .viewtabs", ".mq .seg > button", ".mq .seg .n", ".mq .more"], "chips": [".mq .sact"]}` on the app side and the equivalent (`.viewtabs`, `.seg > button`, `.seg .n`, `.more`, `.sact` — open the « ⋮ » sheet first in both tabs for `.sact`) on the maquette side. Expected: **0 divergences** (tabs 36 px, `.more` 40×40, `.sact` 42 px). If not zero, the TOOL is wrong — fix the tool, do not touch the app.
- [ ] **Step 4: Create the ledger** with a header (mission, method pointer, entry format) and entry #1: L0 calibration evidence.
- [ ] **Step 5: Commit** (ledger only): `git add -f docs/archive/analysis/2026-08-08-maquette-parity-ledger.md && git commit -m "docs(acq-mobile): registre de parité — calibration L0 à zéro divergence"`.

### Task 3: Overlay tool + synthetic fixture payloads mirroring the maquette

**Files:**
- Create: `SCRATCH/parity/overlay_diff.py`
- Create: `SCRATCH/parity/fixtures.js`

**Interfaces:** Produces: `python3 overlay_diff.py maq.png app.png out_heatmap.png` printing `diff_pct=X.XX`; `fixtures.js` defining `patchFetch()` (in-page) that intercepts `/api/acquisition/{followed,wanted,journeys,downloads,to-handle}` and returns the mirror payloads. Later tasks call `patchFetch()` then trigger pull-to-refresh to render maquette-identical content.

- [ ] **Step 1: Write `overlay_diff.py`** (PIL): open both PNGs, resize-assert equal dims, `ImageChops.difference`, count pixels where any channel > 10, print `diff_pct`, write a red-on-gray heatmap (`Image.point` mask composited on a desaturated base). ~30 lines, no options beyond the three paths.
- [ ] **Step 2: Write `fixtures.js`** — payload shapes copied from `frontend/src/components/acquisition/MaintenantPanel.test.tsx` fixture builders (lines 56–254: `takeableShow`, `blockedItem`, `inflightWanted`, `inflightDownload` info_hash-correlated, `inflightJourney`, `waitingShow`, `shogunDispatchedToday`, `upToDateShow`), retitled to the maquette's own fixture set (its JS `CATALOG`/demo data, `MAQ/maquette-reference.md` from line 1202) so both tabs render the SAME titles, states and counts. Cover: a_recuperer, blocked (« titre ambigu — 3 candidats proposés », stage scrape), en vol ×3 stages + download 42 %/78 %, en_attente, dispatched-today, a_jour, en pause, non_verifie.
- [ ] **Step 3: Calibration overlay** on the filter zone (`.filters` cropped): patch fetch in tab A, PointerEvents refresh, screenshot the same crop box in both tabs, run the tool. Expected `diff_pct < 2` with no structural hotspot; archive heatmap; ledger entry #2.

---

## L1 — §7 missing CSS transplants (one loop each: fix → GATES → commit → DEPLOY → MEASURE)

### Task 4: `.act` swipe panes — icons and tones

**Files:**
- Modify: `frontend/src/styles/ps/maquette-acquisition.css` (append `.actions`/`.act` block)
- Modify: `frontend/src/components/acquisition/followActions.tsx:106,120,136`
- Modify: `frontend/src/components/acquisition/SwipeActions.tsx:52-56,126-153`
- Test: `frontend/src/components/acquisition/SwipeActions.test.tsx`

**Interfaces:** Produces: action descriptors carry `icon: JSX.Element` (17 px SVG) and `actClass: "grab" | "pause" | "remove"`; SwipeActions renders maquette classes `.actions > .side > button.act.<actClass>`.

- [ ] **Step 1: Append the verbatim maquette CSS** (reference lines 139–149) to `maquette-acquisition.css`:
  ```css
  .mq .actions { position: absolute; inset: 0; display: flex; align-items: stretch; }
  .mq .actions .side { display: flex; }
  .mq .actions .side.left { margin-right: auto; }
  .mq .actions .side.right { margin-left: auto; }
  .mq .act { border: 0; font: inherit; font-size: 11px; font-weight: 700; line-height: 1.2; color: #fff; flex: 0 0 84px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; padding: 0 5px; text-align: center; cursor: pointer; }
  .mq .act svg { width: 17px; height: 17px; }
  .mq .act.grab { background: var(--primary); color: var(--primary-foreground); }
  .mq .act.pause { background: var(--muted); color: var(--foreground); }
  .mq .act.remove { background: var(--danger); color: #fff; }
  ```
- [ ] **Step 2: Transplant the three icons** — copy the exact `<svg>` markup for `down`, `pause`, `trash` from the maquette icon set `I` (`MAQ/maquette-reference.md` lines 687–699) into `followActions.tsx` as JSX constants; set `icon` (replacing the three `icon: null`) and add `actClass: "grab" | "pause" | "remove"` per action (suspend/resume → `"pause"`).
- [ ] **Step 3: Rewrite the SwipeActions button** to maquette grammar: container `<div className="actions">`, sides `<div className="side left|right">`, button `className={"act " + action.actClass}` (drop `TONE_CLASS` and the Tailwind sizing — `.act` carries it). Keep `ACTION_WIDTH_PX = 84`, `inert` hidden-side logic and handlers unchanged.
- [ ] **Step 4: Update tests** — assert each rendered action button has classes `act` + its `actClass` and contains an `svg` (`container.querySelector("button.act.grab svg")` non-null); update any pin that asserted `TONE_CLASS` strings. Run `npx vitest run src/components/acquisition/SwipeActions.test.tsx` → green.
- [ ] **Step 5: GATES → commit** `fix(web-ui): panneaux swipe au contrat maquette — icônes 17px et tons .act` **→ DEPLOY → MEASURE**: probe region `{"swipe": [".mq .act", ".mq .act svg"]}` with a card swiped open in both tabs (maquette: swipe a « À récupérer » card left; app: same on synthetic data) + overlay of the opened card. Ledger.

### Task 5: `.ptr` pull-to-refresh spinner

**Files:**
- Modify: `frontend/src/styles/ps/maquette-acquisition.css` (append `.ptr` block)
- Modify: `frontend/src/pages/AcquisitionPage.tsx:164-223,386-400`
- Test: `frontend/src/pages/AcquisitionPage.test.tsx`

**Interfaces:** Consumes `gestures.ts` `PULL_THRESHOLD_PX = 64` (unchanged). Produces: `.ptr` element with `armed`/`loading` classes, height = `min(pull*0.55, 80)`, loading height 44 px.

- [ ] **Step 1: Append verbatim CSS** (reference lines 102–107): the `.ptr` block, `.ptr.armed`, `.ptr .spin`, `.ptr.loading .spin`, `@keyframes spin`, and the reduced-motion variant — copy the exact block quoted in the spec exploration (§2b), scoped `.mq`.
- [ ] **Step 2: Replace the text indicator** (`data-testid="pull-indicator"`, lines 386–400) with the maquette markup — copy the exact `.ptr` inner HTML from `MAQ/acquisition-prototype-debug.html` (grep `class="ptr"`). Drive `style={{height}}` from pull distance ×0.55 capped 80; `armed` class at ≥ 39.7 px; on release ≥ threshold: `loading` class, height 44, `invalidateQueries` (existing line 219), then collapse to 0. Keep `data-testid="pull-indicator"` on the `.ptr` element.
- [ ] **Step 3: Update tests** — armed class appears past the arm point, `loading` + 44 px during refresh, collapsed after; run the page test file → green.
- [ ] **Step 4: GATES → commit** `fix(web-ui): pull-to-refresh maquette — spinner, hauteurs 44/80, armed` **→ DEPLOY → MEASURE**: probe `{"ptr": [".mq .ptr", ".mq .ptr .spin"]}` mid-pull is impractical — measure the `loading` state (dispatch the PointerEvents refresh, screenshot during the 1 s refetch window) + a flow GIF of the full gesture. Ledger.

### Task 6: `.skel` shimmer + `.empty` states in panels

**Files:**
- Modify: `frontend/src/styles/ps/maquette-acquisition.css` (append `.skel`; `.empty` already present at lines 331–342)
- Modify: `frontend/src/components/acquisition/MaintenantPanel.tsx:731-751`, `frontend/src/components/acquisition/SuivisPanel.tsx:556-579`, `frontend/src/components/acquisition/AddMediaScreen.tsx:450-455,573-578`
- Test: the three co-named `.test.tsx` files

**Interfaces:** Produces: loading = `<div className="skel" />` ×3; empty = `<div className="empty"><b>…</b>…</div>`.

- [ ] **Step 1: Append verbatim `.skel`** (reference lines 434–436, scoped `.mq`): height 101 px, `--r-lg`, shimmer gradient `var(--card) 25% / var(--muted) 50% / var(--card) 75%`, `background-size: 400% 100%`, `animation: sh 1.3s linear infinite`, `@keyframes sh { to { background-position: -400% 0 } }`, reduced-motion off.
- [ ] **Step 2: Replace the loading branches**: MaintenantPanel 731–735 and SuivisPanel 556–560 « Chargement… » paragraphs → three `.skel` divs (keep an `aria-busy="true"` wrapper and a `sr-only` « Chargement »); AddMediaScreen shadcn `Skeleton`s → three `.skel` divs inside the existing `aria-busy` reslist (maquette add-loading shape).
- [ ] **Step 3: Replace panel empties with `.empty`**: SuivisPanel filter-no-match takes the maquette copy verbatim (reference line 923): `<b>Aucun suivi ne correspond</b>Change de filtre, ou ajoute un média avec le bouton +.`; the no-follows-at-all and MaintenantPanel « Rien à signaler — tout est en ordre. » branches keep their app copy but move into `.empty` markup.
- [ ] **Step 4: Update the three test files** (assert `.skel` count and `.empty` structure/copy), run them → green.
- [ ] **Step 5: GATES → commit** `fix(web-ui): squelettes et états vides à la grammaire maquette` **→ DEPLOY → MEASURE**: probe `{"empty": [".mq .empty", ".mq .empty b"]}` (filter to nonsense text in both tabs); `.skel` measured by forcing the loading state (patch fetch to a never-resolving promise) + overlay. Ledger.

### Task 7: `.crossref` row + `.tile.off` dimming

**Files:**
- Modify: `frontend/src/styles/ps/maquette-acquisition.css` (append `.crossref`, `.tile.off` opacity pair)
- Modify: `frontend/src/components/acquisition/MaintenantPanel.tsx:677-686`, `frontend/src/components/acquisition/SuivisPanel.tsx:402-454`
- Test: co-named test files

- [ ] **Step 1: Append verbatim CSS** — `.crossref` (reference 186–187: 1 px DASHED border, 12 px mutedfg, padding 10/11, `--r-lg`; `span` pinned right `margin-left:auto`, primary 600 nowrap) and the `.tile.off` opacities (reference 232–239: `.off .p { opacity:.42 }`, `.off .nm { opacity:.55 }`), scoped `.mq`.
- [ ] **Step 2: Rewrite the crossref Link** to maquette DOM: `<Link className="crossref">N autres médias à traiter ne viennent pas d'une acquisition <span>Contrôle →</span></Link>` (singular/plural preserved; drop the Tailwind classes).
- [ ] **Step 3: Switch tile dimming** from `opacity-50`/`opacity-60` Tailwind to the maquette values: poster wrapper `.42`, name `.55` (add `off` class on the tile and let CSS drive it, matching maquette structure `.tile.off`), and the paused tile's fraction line reads « en pause » (verify it already does — SuivisPanel:404-454).
- [ ] **Step 4: Update tests** (crossref DOM shape + tile.off class), run → green.
- [ ] **Step 5: GATES → commit** `fix(web-ui): crossref pointillé et extinction .tile.off aux opacités maquette` **→ DEPLOY → MEASURE**: probe `{"crossref": [".mq .crossref", ".mq .crossref span"], "tiles": [".mq .tile.off .p", ".mq .tile.off .nm"]}` (synthetic paused follow + orphan count ≥ 1) + overlay of the grid. Ledger.

### Task 8: `.dlg` confirmation dialog

**Files:**
- Modify: `frontend/src/styles/ps/maquette-acquisition.css` (append `.dlg` family)
- Create: `frontend/src/components/acquisition/MqDialog.tsx`
- Modify: `frontend/src/components/acquisition/AddMediaScreen.tsx:605-640`, `frontend/src/components/acquisition/followActions.tsx:197-238`
- Test: `frontend/src/components/acquisition/MqDialog.test.tsx`

**Interfaces:** Produces: `<MqDialog open title text okLabel danger onOk onCancel />` rendering maquette `.dlgscrim`/`.dlg`/`.dlgacts`/`.dlgbtn(.danger)`; both existing dialogs consume it.

- [ ] **Step 1: Append verbatim CSS** (reference 439–448): `.dlgscrim`, `.dlg`, `.dlg.open`, `.dlg h3` 15.5 px, `.dlg p` 13 px/1.5 mutedfg, `.dlgacts`, `.dlgbtn`, `.dlgbtn.danger`, scoped `.mq`.
- [ ] **Step 2: Write `MqDialog.tsx`** — controlled component, focus-trapped (`role="alertdialog"`, `aria-modal`, Escape = cancel, initial focus on cancel), two `.dlgbtn` (« Annuler », ok label; `danger` default true).
- [ ] **Step 3: Swap both call sites** — AddMediaScreen replace dialog gets the maquette §5 copy verbatim (reference 1505–1509): title « Ce film est déjà en médiathèque », text « “{title}” est déjà rangé. Le suivre relancera une acquisition dont le résultat REMPLACERA la version en place. », ok « Remplacer »; followActions removal dialog keeps its per-kind `removeAsk` copy and `data-testid="confirmer-le-retrait"`, ok « Retirer ».
- [ ] **Step 4: Tests** — MqDialog renders/fires/traps; update the two call-site tests (shadcn Dialog assertions → `.dlg` DOM). Run → green.
- [ ] **Step 5: GATES → commit** `fix(web-ui): dialog .dlg maquette pour remplacement et retrait` **→ DEPLOY → MEASURE**: probe `{"dlg": [".mq .dlg", ".mq .dlg h3", ".mq .dlg p", ".mq .dlgbtn"]}` with the remove dialog opened in both tabs + overlay. Ledger.

### Task 9: Toast unification + FAB size on the Acquisition surface

**Files:**
- Create: `frontend/src/components/acquisition/MqToast.tsx` (provider + hook + view)
- Modify: `frontend/src/pages/AcquisitionPage.tsx:269,422-432`, `frontend/src/components/acquisition/followActions.tsx:296` (and any other sonner call in `src/components/acquisition/` — enumerate with `rg "from \"sonner\"" -g '*.tsx' src/components/acquisition src/pages/AcquisitionPage.tsx`)
- Test: `frontend/src/components/acquisition/MqToast.test.tsx`

**Interfaces:** Produces: `useMqToast().show(msg)` context hook; `.mqtoast` view at page level (CSS already present, bottom 82 px); FAB 54×54.

- [ ] **Step 1: Write `MqToast.tsx`** — context provider, single message state, 5000 ms auto-hide, close button (`.mqtoastclose`) is the real control, `role="status"`. View markup identical to AddMediaScreen's existing local mqtoast (lines 641–660).
- [ ] **Step 2: Wrap the page** and replace the enumerated sonner calls in Acquisition components with `show(...)` (sonner remains everywhere outside Acquisition). AddMediaScreen keeps its local in-screen toast (maquette has an in-add toast).
- [ ] **Step 3: FAB to maquette metrics** (reference 250–253): 54×54 (`size-12` → exact 54 px), right/bottom 16 px, icon 24 px, shadow `0 6px 20px rgba(0,0,0,.55)` — so the toast's bottom 82 px (16+54+12) is truthful.
- [ ] **Step 4: Tests** — toast shows/auto-hides/closes; a followActions action surfaces the message; FAB box pinned. Run → green.
- [ ] **Step 5: GATES → commit** `fix(web-ui): toast maquette au niveau page et FAB 54px` **→ DEPLOY → MEASURE**: probe `{"toast": [".mq .mqtoast"], "fab": ["[data-testid=acq-fab]", ".fab"]}` with a toast visible in both tabs (maquette: trigger a refresh; app: trigger an action) + overlay. Ledger. **This closes L1: append an L1 summary ledger entry.**

---

## L2 — Never-measured regions

### Task 10: `.sugg` recent-searches chips (operator decision §2.2)

**Files:**
- Modify: `frontend/src/styles/ps/maquette-acquisition.css` (append `.sugg`, reference 416–418)
- Modify: `frontend/src/components/acquisition/AddMediaScreen.tsx` (idle state + submit path)
- Test: `frontend/src/components/acquisition/AddMediaScreen.test.tsx`

**Interfaces:** Produces: localStorage key `tm.add.recentSearches` (JSON array of strings, max 5, most-recent first).

- [ ] **Step 1: Failing tests first**: (a) idle renders no `.sugg` when storage empty; (b) after a submitted search « silo », storage holds `["silo"]` and a fresh idle renders one chip; (c) chip tap fills the input AND runs the search (results state, not just prefill — maquette rule); (d) queries matching a followed title case-insensitively are not shown; (e) capped at 5, dedup, most-recent first. Run → FAIL.
- [ ] **Step 2: Implement** — on successful search submit, push the query; idle state renders `.sugg` buttons filtered against `useFollowed` titles; tap dispatches the real submit handler. Append the verbatim `.sugg` CSS.
- [ ] **Step 3: Run tests → green. GATES → commit** `feat(web-ui): chips de recherches récentes honnêtes sur l'écran d'ajout` **→ DEPLOY → MEASURE**: probe `{"sugg": [".mq .sugg", ".mq .sugg button"]}` (seed localStorage in tab A to mirror the maquette's 5 chips for geometry) + overlay of the idle screen. Ledger.

### Task 11: Add-screen full metric sweep

**Files:** measurement first; fixes wherever the probe diverges (expected: `frontend/src/components/acquisition/AddMediaScreen.tsx` + `maquette-acquisition.css` touch-ups).

- [ ] **Step 1: Probe the full add region** in both tabs, all four states (idle / loading / results / no-results — drive the maquette by typing+submitting, the app by synthetic search interception): map `{"add": [".mq .fichebar", ".mq .fback", ".mq .addform", ".mq .addrow", ".mq .btnprimary", ".mq .rescount", ".mq .res", ".mq .res .rp", ".mq .res .rt", ".mq .res .rm", ".mq .res .ro", ".mq .resbtn", ".mq .restag", ".mq .byid", ".mq .segmini", ".mq .field input", ".mq .addfoot"]}`.
- [ ] **Step 2: Fix every divergence** (verbatim values from reference 322–414), re-probe to zero. Also verify behaviors already pinned: resbtn verb flip (Suivre/Ajouter → ✓ Suivi/✓ Ajouté), `.restag` only for owned-not-followed, rescount « N affichés sur M trouvés », by-ID validation hints/regexes (reference 1517–1525), search only on submit.
- [ ] **Step 3: GATES → commit** `fix(web-ui): écran d'ajout mesuré à zéro divergence` **→ DEPLOY → MEASURE** (re-probe deployed + overlay idle/results + flow GIF: search → fiche → back restores the search). Ledger.

### Task 12: PlusSheet, JourneyDetailSheet, sheet chrome sweep

**Files:** measurement first; fixes expected in `frontend/src/components/acquisition/PlusSheet.tsx`, `WatcherPanel.tsx`, `ObligationsPanel.tsx`, `JourneyDetailSheet.tsx`, `FollowDetailSheet.tsx`, `maquette-acquisition.css`.

- [ ] **Step 1: Probe** `{"sheet": [".mq .sheetgrab", ".mq .sheettitle", ".mq .sheetmeta", ".mq .sheetacts", ".mq .sact", ".mq .sact svg", ".mq .kv"], "sheetshell": ["[role=dialog].mq, .mq [data-sheet]"]}` across the three sheets (detail, journey, ⋮) opened in both tabs. Maquette shell targets: radius 16 px top, border-top 1 px, max-height 86 %, shadow `0 -12px 44px rgba(0,0,0,.6)`, grab 36×4, h2 16 px, `.kv` rows 13 px with 9 px vertical padding (reference 263–274 and §2g).
- [ ] **Step 2: Fix divergences** — the ⋮ sheet must show the maquette's structure: 2 `.sact` info rows with 16 px icons + 4 `.kv` rows + the « Réglages → Config » footnote (WatcherPanel/ObligationsPanel content mapped into that grammar, real data only — no fake « Ratio global » if the API doesn't serve it; anything unavailable renders as an honest absence per §8/§14, never an invented value). Re-probe to zero.
- [ ] **Step 3: GATES → commit** `fix(web-ui): feuilles ⋮ et parcours au chrome maquette mesuré` **→ DEPLOY → MEASURE** + overlay of each sheet + flow GIF (card tap → sheet → action). Ledger. **L2 summary entry.**

---

## L3 — Backend additions (order D → C → B → A; each end-to-end; `make check` + `make openapi` every time)

### Task 13: (D) Episode label on to-handle items

**Files:**
- Modify: `personalscraper/web/acquisition/to_handle.py:38-52,148-161`
- Modify: `personalscraper/web/models/acquisition.py:856-882` (`ToHandleItemModel`)
- Modify: `frontend/src/components/acquisition/MaintenantPanel.tsx` (blocked card subtitle)
- Test: backend to-handle tests (same dir as existing, find with `rg "to_handle" -t py tests/ personalscraper/ -l`), `MaintenantPanel.test.tsx`

**Interfaces:** Produces: `ToHandleItem.season: int | None`, `.episode: int | None`; API `ToHandleItemModel.season/episode`; UI subtitle « S16E12 · {reason} ».

- [ ] **Step 1: Failing backend test** — build a to-handle item whose correlated `ProvenanceRow` has `season=16, episode=12`; assert the dataclass and the route payload carry them (and `None` when provenance lacks them):
  ```python
  def test_to_handle_carries_episode_identity(store_with_provenance):
      items = build_to_handle(store_with_provenance, ...)
      assert (items[0].season, items[0].episode) == (16, 12)
  ```
- [ ] **Step 2: Implement** — add the two fields to the dataclass (`to_handle.py:38-52`), populate at build (`148-161`) via `getattr(prov, "season", None)`/`getattr(prov, "episode", None)`; add `season: int | None = None` / `episode: int | None = None` to `ToHandleItemModel` (`**vars(item)` at `acquisition_overview.py:236` wires it). Run tests → green.
- [ ] **Step 3: `make openapi`** — commit regenerated `frontend/openapi.json` + `frontend/src/api/schema.d.ts`.
- [ ] **Step 4: Failing frontend test** — blocked card with season/episode shows « S16E12 · titre ambigu — 3 candidats proposés »; without them, reason only. Implement (zero-padded `S${String(s).padStart(2,"0")}E${…}`), run → green.
- [ ] **Step 5: GATES + `make check` → commit** `feat(web-ui): libellé épisode sur les éléments à traiter` **→ DEPLOY → MEASURE** (probe blocked card sub + synthetic payload now carrying season/episode). Ledger.

### Task 14: (C) `last_search_at` per followed item

**Files:**
- Modify: `personalscraper/web/routes/acquisition.py:189-389` (`get_followed`)
- Modify: `personalscraper/web/models/acquisition.py:62-178` (`FollowedSeriesItem`)
- Modify: the resting-card renderer (find with `rg "prochain passage|next_search" -g '*.tsx' frontend/src/components/acquisition/`)
- Test: backend followed-route tests; the resting card's component test

**Interfaces:** Produces: `FollowedSeriesItem.last_search_at: float | None` (Unix epoch); UI « rien de conforme au profil · il y a 3 h ».

- [ ] **Step 1: Failing backend test** — two wanted rows for one follow (one `done` old, one `pending` recent): `/api/acquisition/followed` item carries the MAX `last_search_at` across ALL statuses; a never-searched follow carries `None`.
- [ ] **Step 2: Implement** — one batched query in `get_followed`: `SELECT followed_id, MAX(last_search_at) AS last_search_at FROM wanted WHERE followed_id IS NOT NULL GROUP BY followed_id`; add the model field (default `None` keeps `_item_from_followed` in `service.py` source-compatible); populate at item build (`acquisition.py:355-382`). Tests → green. `make openapi`, commit regen.
- [ ] **Step 3: Frontend** — failing test: resting card shows « il y a 3 h » derived from `last_search_at` (reuse the existing relative-time formatter — locate with `rg "il y a" -g '*.ts' -g '*.tsx' frontend/src/`), honest absence when `null` (« jamais cherché »), NOT the next-check substitute. Implement, green.
- [ ] **Step 4: GATES + `make check` → commit** `feat(web-ui): dernière recherche réelle sur les cartes au repos` **→ DEPLOY → MEASURE**. Ledger.

### Task 15: (B) ETA on downloads

**Files:**
- Modify: `personalscraper/api/torrent/_base.py:25-77` (`TorrentItem`), `personalscraper/api/torrent/qbittorrent.py:783-829`, `personalscraper/api/torrent/transmission.py:147-161,525-581`
- Modify: `personalscraper/web/acquisition/downloads.py:75-116`, `personalscraper/web/models/acquisition.py:536-568`
- Modify: `frontend/src/components/acquisition/DownloadRow.tsx`
- Test: torrent-client mapper tests (find via `rg "_torrent_item" -t py tests/`), downloads route test, `DownloadRow` test

**Interfaces:** Produces: `TorrentItem.eta_seconds: int | None = None`; `AcquisitionDownload.eta_seconds: int | None`; UI « 12 min restantes ».

- [ ] **Step 1: Failing mapper tests** — qBittorrent: payload `eta=720` → `eta_seconds=720`; `eta=8640000` (qBit infinity sentinel) → `None`; missing → `None`. Transmission: the `arguments` list sent to `torrent_get` includes `"eta"`; `eta=-1`/`-2` → `None`; `eta=300` → `300`.
- [ ] **Step 2: Implement** — defaulted field on `TorrentItem` (same pattern as `swarm_seeds`); qbit mapper `eta = getattr(t, "eta", None)` normalized (`None` when `eta is None or eta < 0 or eta >= 8640000`); transmission adds `"eta"` to the explicit arguments list + maps negatives to `None`. Tests → green.
- [ ] **Step 3: Expose** — `AcquisitionDownload.eta_seconds: int | None = None`, set in `_to_download` (`None` when the live item is `None` — fail-soft path untouched). Route test asserts serialization. `make openapi`, commit regen.
- [ ] **Step 4: Frontend** — failing test: downloading row with `eta_seconds=720` shows « 12 min restantes »; `< 60` → « moins d'une minute »; `≥ 3600` → « 1 h 05 restantes »; `null` → no mention (honest absence). Implement in `DownloadRow.tsx`, green.
- [ ] **Step 5: GATES + `make check` → commit** `feat(web-ui): ETA véridique sur les téléchargements` **→ DEPLOY → MEASURE** (synthetic download with eta + probe of the row). Ledger.

### Task 16: (A) Best-candidate summary on « À récupérer »

**Files:**
- Create: `personalscraper/acquire/migrations/019_wanted_last_search_best.sql`
- Modify: `personalscraper/acquire/_ports.py:121` (protocol), `personalscraper/acquire/_wanted_store.py:793-819`, `personalscraper/acquire/_search_pass.py:336` (and the other `record_search_outcome` call sites: `_search_pass.py:208,248`, `_grab_pass.py:154,163,281` — pass `None`)
- Modify: `personalscraper/web/models/acquisition.py:187-198` (`WantedItemResponse` + new `WantedSearchBest`), `personalscraper/web/routes/acquisition.py:508-596`
- Modify: the « À récupérer » card renderer in `frontend/src/components/acquisition/MaintenantPanel.tsx`
- Test: wanted-store tests, search-pass test, route test, `MaintenantPanel.test.tsx`

**Interfaces:** Produces: `wanted.last_search_best_json` column; `record_search_outcome(wanted_id, outcome, found, best: Mapping[str, object] | None = None)`; API `WantedItemResponse.last_search_found: int | None` + `.last_search_best: WantedSearchBest | None` (`resolution/source/codec/language/seeders/title`, all optional); UI « S02E05 · 1080p WEB-DL · 42 sources ».

- [ ] **Step 1: Migration** `019_wanted_last_search_best.sql`: `ALTER TABLE wanted ADD COLUMN last_search_best_json TEXT;` (auto-applied by `apply_migrations`, `store.py:92`).
- [ ] **Step 2: Failing store test** — `record_search_outcome(id, "available", 42, best={"resolution": "1080p", "source": "WEB-DL", "seeders": 42, "title": "…"})` persists JSON; `best=None` leaves the column `NULL`; a later outcome without `best` clears it (the summary must always describe the LAST search — no stale carry-over).
- [ ] **Step 3: Implement** — extend the protocol (`_ports.py:121`) and impl with `best: Mapping[str, object] | None = None` (serialize inside, `UPDATE … last_search_best_json = ?` always setting the column); at `_search_pass.py:336` build the summary from `verdict.chosen` (`TrackerResult.resolution/source/codec/language/seeders/title` — `_base.py:66-91`) when outcome is `available`, else `None`; all other call sites pass `None` explicitly. Tests → green.
- [ ] **Step 4: API** — `WantedSearchBest` Pydantic model; `last_search_found` + parsed `last_search_best` on `WantedItemResponse`, populated in `get_wanted` (column already in `SELECT w.*`); route test. `make openapi`, commit regen.
- [ ] **Step 5: Frontend** — failing test: wanted card sub shows « S02E05 · 1080p WEB-DL · 42 sources » (compose season/episode + best.resolution + best.source + `last_search_found`, omitting missing parts honestly — e.g. no best ⇒ no quality segment, `found` alone ⇒ « 42 sources »). Implement, green.
- [ ] **Step 6: GATES + `make check` → commit** `feat(web-ui): le meilleur candidat de la dernière recherche sur les cartes à récupérer` **→ DEPLOY → MEASURE**. Ledger.

### Task 17: « En vol » stage elapsed (frontend-only)

**Files:**
- Modify: `frontend/src/components/acquisition/MaintenantPanel.tsx` (En vol rows) or `journey.ts` helper
- Test: `MaintenantPanel.test.tsx` (fake timers)

- [ ] **Step 1: Failing test** — journey with `grabbed_at = now-240` and no later stage shows « depuis 4 min »; a journey whose current stage comes from `estimated_stages` shows « ~ depuis 4 min » (approximate marker, §13); no timestamps ⇒ no mention.
- [ ] **Step 2: Implement** — elapsed = `now − max(non-null of grabbed_at/ingested_at/scraped_at/dispatched_at)`; helper in `journey.ts`. Green.
- [ ] **Step 3: GATES → commit** `feat(web-ui): temps écoulé dans l'étape sur les cartes en vol` **→ DEPLOY → MEASURE**. Ledger. **L3 summary entry.**

---

## L4 — Desktop ≥ md (operator decision §2.3)

### Task 18: Centered reading column

**Files:**
- Modify: `frontend/src/pages/AcquisitionPage.tsx:294`, `frontend/src/styles/ps/maquette-acquisition.css` (md overrides), sheet/dialog components for width caps
- Test: `AcquisitionPage.test.tsx`

- [ ] **Step 1: Implement** — `md:max-w-5xl` → `md:max-w-2xl` (672 px) on the page section; `@media (min-width: 768px)` block in `maquette-acquisition.css`: `.mq .grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }`; sheets (`FollowDetailSheet`, `JourneyDetailSheet`, `PlusSheet`) and `.dlg` capped 672 px / 420 px centered at md+. Element-level metrics (cards, chips, tabs) unchanged — the 390 px probe values remain the truth.
- [ ] **Step 2: Tests** (class pins) → green. **GATES → commit** `feat(web-ui): colonne de lecture centrée au-delà de md` **→ DEPLOY → MEASURE**: probe at 1280×900 and 1440×900 (element-level metrics must equal the 390 px values; column ≤ 672 px), full-page screenshots at both widths sent to the operator. Ledger.

---

## L5 — Global re-sweep and gate

### Task 19: Full-union probe, all card states, gesture pass, gates, version bump

**Files:**
- Modify: `personalscraper/__init__.py:17` (version bump `0.87.0` → `0.88.0` — new API fields = minor)
- Modify: `docs/archive/analysis/2026-08-08-maquette-parity-ledger.md` (final entries)

- [ ] **Step 1: Full probe union** — every region map from Tasks 2–18 re-run on the deployed build, maquette vs app, expecting `0 divergences` on the whole union. Any divergence ⇒ fix loop (smallest change, re-deploy, re-measure) before proceeding.
- [ ] **Step 2: All card states** rendered via `fixtures.js` and probed/overlaid: blocked strip, three in-flight stages, folded download, resting verdicts, dispatched rows, fresh glow, paused tiles, « ? » badges — each screenshot archived.
- [ ] **Step 3: Full gesture pass on the deployed build**, GIF-recorded: pager swipe (edge dead zone honored), pull-to-refresh, card swipe open + each action, card tap → sheet → actions, add round-trip (search → fiche → back restores results), back gesture everywhere.
- [ ] **Step 4: Gates** — GATES block + `make check` from the worktree root (zero failures; watch for ERROR = collection crash). Version bump commit: `chore(acq-mobile): version 0.88.0`.
- [ ] **Step 5: Final ledger entry** (L5 summary: every region « 0 divergences », overlay archive index, GIF index) **→ DEPLOY** the final sha **→ hand the T16 gate to the operator**: phone validation against the 11-point checklist (`docs/archive/superpowers/plans/2026-08-06-acquisition-mobile-refonte.md` lines 2433–2456). **STOP — only the operator closes the mission.** PR flow (`/implement:feature-pr`) starts only after their validation.

---

## Self-review notes

- Spec coverage: §3 layers → Tasks 2–3 + every MEASURE step; §4 L0–L5 → Tasks 1–19; §2.2 → Task 10; §2.3 → Task 18; four backend additions → Tasks 13–16; elapsed sibling → Task 17; ledger → Task 2 step 4 + every task; T16 → Task 19.
- The maquette-side probe selectors drop the `.mq` prefix (maquette has no scope class) — `probe.js` takes the region map as input, so each MEASURE step passes the app map and its unprefixed twin.
- Icon SVGs and `.ptr` inner markup are transplanted from `MAQ/maquette-reference.md` lines 687–699 / `MAQ/acquisition-prototype-debug.html` — verbatim sources, referenced not duplicated here.
- Type consistency: `actClass` (Task 4) consumed only by SwipeActions; `eta_seconds` name identical across TorrentItem/AcquisitionDownload/UI; `last_search_best`/`WantedSearchBest` names identical across store/API/UI; `tm.add.recentSearches` key used only in Task 10.
