# Maquette parity method — Acquisition UI (design)

Date: 2026-08-08. Operator-approved via brainstorm (three decisions recorded in §2).
Companion to `docs/superpowers/handoffs/2026-08-08-maquette-parity-handoff.md`, which
remains the contract (Definition of Done §1, source-of-truth hierarchy §2, operator
arbitrations §3, runbook §4). This document specifies the METHOD used to reach the
Definition of Done, plus the design of the remaining functional work.

## 1. Mission restated

Make the Acquisition UI a perfect reflection of the operator-approved maquette —
visually, dimensionally and behaviorally — at 390 px and ≥ md, plus four backend
additions, with every claim backed by a measurement on the DEPLOYED staging build.
Worktree `.claude/worktrees/acq-mobile`, branch `feat/acq-mobile`.

## 2. Operator decisions of 2026-08-08 (binding)

1. **Method**: hybrid comparison approved — scripted DOM probe as the hard gate,
   pixel-overlay diff on synthetic data mirroring the maquette fixtures, behavioral
   flow pass recorded as GIFs. Sweep in 6 lots (L0–L5, §4), deploy + measure on
   staging at every lot.
2. **`.sugg` suggestion chips** (add screen idle): fed by this device's recent
   search queries (localStorage), deduplicated against existing follows; chips
   absent until history exists. No hardcoded titles, no backend.
3. **Desktop ≥ md**: mobile maquette grammar in a centered reading column
   (~672 px / `max-w-2xl`, replacing the current `max-w-5xl`), tile grid switches
   to auto-fill, sheets and dialogs capped in width. No invented desktop layout.

## 3. Comparison architecture (three layers)

### 3.1 Scripted DOM probe — the hard gate

> **Driver addendum (2026-08-08, operator-approved):** the browser MCP
> extension is not connected in this session, so the measurement driver is a
> **headless Playwright harness** (Python Playwright already installed,
> Chromium already cached — no downloads). Everything below reading « tab »
> means an isolated headless browser context; probe semantics, emulation
> (390×844, DPR 2, mobile, touch), synthetic-injection recipe, staging URL
> and evidence formats are unchanged. Headless contexts have zero contact
> with the operator's Chrome, which strengthens arbitration §3.5.

A versioned probe script (scratchpad + referenced in the ledger) executed in
TWO browser contexts I own:

- **Maquette tab**: `acquisition-prototype-debug.html` served by the prior
  session's `serve.py` (127.0.0.1:8801, no-store). The original maquette file and
  the operator's tabs are NEVER touched.
- **App tab**: `https://tm-staging.iznogoudatall.xyz` — after verifying
  `/api/version` serves the sha under test.
- Both tabs emulated `390x844x2,mobile,touch`; the probe asserts
  `document.documentElement.clientWidth === 390` before measuring (per-tab
  emulation stickiness trap).

The probe walks a per-region selector map and emits normalized JSON per node:
`getBoundingClientRect` (w/h, x/y within region), and a fixed `getComputedStyle`
subset (font-size, font-weight, line-height, padding, margin, border, radius,
gap, color, background-color — colors resolved to rgb). A Python differ compares
maquette vs app JSON. **Pass = zero divergence** on box metrics and typography;
colors must resolve equal after the documented token mapping
(`maquette-acquisition.css` header). Divergences are reported as a table
(selector, property, maquette value, app value) — that table is the evidence.

Selector maps are per-region and grow with the sweep; the union at L5 covers
every region of §4. The probe file is append-only across lots so L5 re-runs
everything measured before (regression guard).

### 3.2 Pixel-overlay diff — the net

For each region, screenshot both tabs and compare with PIL:
`ImageChops.difference`, per-channel tolerance ≤ 10 (font antialiasing), report
% differing pixels + a heatmap PNG. Advisory evidence (the probe is the gate);
target < 2 % per region with zero structural hotspots.

Key upgrade over the prior session's sketch: the app is fed **synthetic API
payloads mirroring the maquette's own fixtures** (same titles, states, counts —
extracted from the maquette JS `CATALOG`/fixtures), via the proven recipe:
patch `window.fetch` through `evaluate_script` (never `initScript` — isolated
world) for `/api/acquisition/{followed,wanted,journeys,downloads,to-handle}`,
then trigger the app's own pull-to-refresh by dispatching PointerEvents on
`#acq-tabpanel` (down y=200 → move y=320 → up). Payload shapes: fixture
builders in `MaintenantPanel.test.tsx` (lines 56–254). With identical content,
whole-card overlays become meaningful, not just stable chrome.

### 3.3 Behavioral flow pass

Every interaction of the maquette brief exercised in MY tab on the DEPLOYED
build, recorded as GIFs: horizontal view swipe (30 px edge dead zone, 28 %
threshold), pull-to-refresh (armed ≥ ~40 px, loading 44 px), card swipe with
action panes (84 px per action, snap 45 %), card tap → detail sheet, sheet
actions, add flow round-trip (search → fiche → back restores the search), back
gesture everywhere. A flow claim without its GIF (or DOM-probe of the
transient state) does not count.

## 4. Sweep plan — six lots

Each lot ends deployed, measured, and logged before the next starts. One
coherent region per fix loop inside a lot — never two regions mixed before
measurement (divergence attribution).

- **L0 — tooling, no app code**: re-mint staging token (`mint_session.py` via
  `~/staging/torrentmate-venv/bin/python`; current token expires 2026-08-08
  ~19:49), start `serve.py`, write probe + differ + overlay tools, validate
  them on an already-measured-at-zero region (tabs 36 px / gutters 14 px must
  reproduce zero).
- **L1 — §7 missing CSS transplants** (all confirmed absent from
  `maquette-acquisition.css` and `src/`): `.act` panes with 17 px icons and
  tones grab=primary / pause=muted+`--fg` / remove=danger (replaces
  `icon: null` in `followActions.tsx:106/120/136` and Tailwind tones in
  `SwipeActions.tsx`); `.ptr` spinner with height animation (replaces
  text-only indicator in `AcquisitionPage.tsx:164–223`); `.skel` shimmer in
  panels (replaces « Chargement… » paragraphs); `.empty` in panels; `.crossref`
  dashed border + right-pinned primary « Contrôle → » (`MaintenantPanel.tsx:677–686`);
  `.tile.off` opacities .42/.55 (currently .50/.60, `SuivisPanel.tsx:402–454`);
  `.dlg` replace/remove dialog (replaces shadcn `Dialog`); maquette toast
  unified on the Acquisition surface (bottom 82 px above FAB; sonner stays
  outside Acquisition). CSS values transplanted verbatim from
  `maquette-reference.md` — never re-improvised.
- **L2 — never-measured regions**: full add screen metrics (`.fichebar`,
  `.addform`, `.res` 54×81 poster, `.resbtn` verbs, `.byid`, `.addfoot`,
  `.sugg` per §2.2), PlusSheet (40×40 `.more`, `.sact` rows, `.kv` rows,
  footnote), JourneyDetailSheet chrome (sheet shell 16 px radius, `sheetgrab`
  36×4), dialogs, toast metrics.
- **L3 — backend additions + honest data** (order D → C → B → A, each
  end-to-end: model → route → `make openapi` → committed `openapi.json` +
  `schema.d.ts` → UI → tests):
  - **D** episode label on to-handle: `ProvenanceRow.season/episode` already
    hydrated (`_provenance_store.py:194–195`) → add to `ToHandleItem`
    dataclass (`to_handle.py:38–52`) + `ToHandleItemModel`
    (`models/acquisition.py:856–882`); `**vars(item)` wires the route. UI
    formats « S16E12 ».
  - **C** `last_search_at` per follow: already stamped per wanted row
    (`_wanted_store.py:176–196`); add one batched
    `MAX(last_search_at) GROUP BY followed_id` query (all statuses) in
    `get_followed`, field on `FollowedSeriesItem`. Resting card shows the
    last search, not the next check.
  - **B** ETA: add `eta_seconds: int | None = None` to `TorrentItem`
    (`api/torrent/_base.py`); map in qBittorrent (`getattr(t, "eta", None)`,
    normalize ≥ 8640000 → None) and Transmission (add `"eta"` to the
    explicit arguments list, −1/−2 → None); expose on `AcquisitionDownload`,
    set in `_to_download`. UI « 12 min restantes ».
  - **A** best-candidate summary on « À récupérer »: source count already
    persisted (`wanted.last_search_found`); persist the chosen candidate too —
    migration `019_*` adds `wanted.last_search_best_json`; extend
    `record_search_outcome` (impl `_wanted_store.py:793`, protocol
    `_ports.py:121`) to accept a summary of `SearchVerdict.chosen`
    (resolution, source, codec, language, seeders, title) passed at
    `_search_pass.py:336`; expose on `WantedItemResponse`; UI
    « S02E05 · 1080p WEB-DL · 42 sources ».
  - **Frontend-only sibling**: « En vol » elapsed (« depuis 4 min ») from
    `JourneyItem.grabbed_at`/max non-null stage timestamp; stages named by
    `estimated_stages` are presented as approximate (§13 honesty).
  - All four are plain GET surfaces — no staging guard involved; version bump
    in `personalscraper/__init__.py` once for the PR.
- **L4 — desktop ≥ md** per §2.3, then probe/overlay at 1280 and 1440 wide
  (app-only judgment: column width, grid density, sheet caps; the maquette
  stays the 390 px source for element-level metrics).
- **L5 — global re-sweep and gate**: full probe union (every region, every
  card state via synthetic injection: blocked strip, three in-flight stages,
  folded download, resting verdicts, dispatched rows, fresh glow), full
  gesture pass on the deployed build, overlay archive, frontend gates + `make
  check`, ledger complete. Then T16: operator phone validation (11-point
  checklist, plan lines 2433–2456) → PR flow.

## 5. Loop protocol (every fix loop, no exceptions)

1. Fix one region (CSS transplant verbatim; DOM adapted to the maquette,
   never the reverse).
2. Frontend gates: `npx tsc -b --noEmit`, `npx eslint src`, `npx vitest run`
   (baseline 1274 green — arbitration pins must stay green; a pinned-area
   failure means I regressed an arbitration, not that the test is wrong).
   `make check` when any Python file changed.
3. Commit (Conventional Commits, `(web-ui)` or `(acq-mobile)` scope, French
   body, no AI attribution; « ticket 411 » wording in frontend files).
4. Deploy: push branch, ff ours-merge to `staging`
   (`git commit-tree 'HEAD^{tree}' -p HEAD -p origin/staging`), poll
   `/api/version` until it serves MY sha. `--no-verify` only when the change
   is frontend-only AND the gates ran.
5. Measure on the deployed build (probe; overlay and/or flow GIF as the region
   requires). PWA trap: the version check happens in the measuring tab itself.
6. Ledger entry (§6). If divergence remains → loop again immediately. Never
   stop between loops while divergences remain; never report « conforme »
   without the measure.

## 6. Evidence ledger

`docs/analysis/2026-08-08-maquette-parity-ledger.md` (English), append-only,
one entry per loop: lot / loop id, deployed sha + `/api/version` proof, probe
result (divergence table or « 0 divergences on N selectors »), overlay %
+ heatmap path, flows exercised (GIF paths), gate outputs (test counts).
Screenshots and heatmaps live in the session scratchpad; key evidence is also
sent in chat. The ledger is the single place the operator can audit any
« conforme » claim.

## 7. Testing strategy

- Every visual fix that has a DOM-representable invariant gets or updates a
  component test (pinned heights/classes/labels pattern already in place —
  1274 baseline).
- Backend: per-addition unit tests (store, mapper sentinel normalization,
  route serialization) + regression test per bug found, written before/with
  the fix. `make openapi` drift gate stays green (CI fails on drift).
- Arbitration pins are never weakened; new arbitrations get pinned the same
  way and recorded in the handoff §3 list.

## 8. Risks and mitigations

- **PWA stale bundle**: every measurement preceded by `/api/version` in the
  measuring tab; any operator report first checked against the build their
  device serves.
- **Token expiry**: re-mint at L0; re-mint again if 401s appear.
- **Overlay AA noise**: tolerance ≤ 10/channel, hotspot clustering; probe
  remains the gate — overlay disagreements are investigated, not hand-waved.
- **Shared `library.db`/`.data/`**: synthetic states ONLY via fetch
  interception; never test rows in shared databases.
- **Emulation stickiness**: probe asserts clientWidth before any number is
  trusted.
- **rg over 14 GB fixtures**: type filters always (`-t py`, `-g '*.tsx'`…);
  `curl` always with `--connect-timeout 10 --max-time 30`; never a local
  server on 8710/8711 (the 8801 maquette server is localhost-only static).

## 9. Out of scope

- Any change to the maquette files or the operator's browser tabs/emulation.
- Re-litigating handoff §3 arbitrations (« ··· » everywhere, number grid
  badges, urgency groups with chips, primary nav pills).
- The stale repo-root `IMPLEMENTATION.md` (describes the previous
  `file-absorbee` feature): left untouched; this mission tracks via the
  handoff, this spec, and the plan. Flagged to the operator.
