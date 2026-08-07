# Handoff — Acquisition UI: perfect parity with the maquette

> **You are the next agent.** Your mission: make the Acquisition UI a PERFECT
> reflection of the operator-approved maquette — visually, dimensionally and
> behaviorally — on mobile (390 px) AND desktop, plus the finishing work and
> the four backend additions listed below. The operator's bar is literal:
> « pixel perfect ». The previous session got structurally close and left you
> working tooling, but also burned days on method errors documented here so
> you do not repeat them.
>
> **Before writing any code, you MUST brainstorm your own method** (invoke
> `superpowers:brainstorming`): read this document, inspect the maquette
> source and the current app, then propose to the operator the approach you
> believe reaches the highest exactness. The proven building blocks from the
> previous session (§ What worked) are candidates, not orders — keep them,
> improve them, or replace them with something better. What is NOT negotiable
> is the Definition of Done and the operator arbitrations.

---

## 1. Mission & Definition of Done

Scope — the operator chose **everything, no exceptions**:

1. **UI exactness** — every screen and state of the Acquisition page matches
   the maquette: Maintenant (5 sections, all card states), Suivis (liste /
   groupé / grille), detail sheet, journey sheet, add screen (idle / results
   / added), « ⋮ » sheet, dialogs, toasts, swipe layers, gestures.
2. **Finishing work** — desktop pass (the layout must be correct and pleasant
   ≥ md, not just not-broken), automated image-overlay diff on stable chrome
   regions, verification that the T15 cleanup left no orphan (superseded
   panels deleted, ranking editor lives in /config), and the T16 gate:
   operator validation on a real phone, then the PR flow.
3. **Backend additions (4)** — the maquette shows data the API does not serve
   yet. Add them end-to-end (Pydantic model → route → `make openapi` →
   regenerated `schema.d.ts` committed → UI → tests → version bump):
   - **Candidate info** on « À récupérer » cards: best candidate quality +
     source count from the last search (maquette: « S02E05 · 1080p WEB-DL ·
     42 sources »).
   - **ETA** on downloads: qBittorrent serves an `eta` per torrent → expose it
     on `AcquisitionDownload` (maquette: « 12 min restantes »).
   - **`last_search_at`** per followed item (maquette resting card: « rien de
     conforme au profil · il y a 3 h » — the current UI substitutes the next
     check because only `next_search_at` exists).
   - **Episode label** on `ToHandleItem` (maquette blocked card subtitle:
     « S16E12 · titre ambigu — 3 candidats proposés »).
   - Frontend-only sibling: « En vol » stage elapsed time (« depuis 4 min »)
     is derivable from journey timestamps — no backend needed.

**Done means, in order:**

1. A measured comparison (your method) reports **zero structural divergence**
   per screen/state at 390 px, and the desktop pass is clean.
2. Every interaction flow of the maquette brief is exercised on the DEPLOYED
   staging build: horizontal view swipe, pull-to-refresh, card swipe with its
   actions, card tap → sheet, sheet actions, add flow round-trip (search →
   fiche → back restores the search), back gesture everywhere.
3. All gates green: frontend `npx tsc -b`, `npx eslint src`, `npx vitest run`
   (baseline 1274 tests — they now pin the operator arbitrations, see §3);
   `make check` for any backend change.
4. Deployed to staging and `/api/version` serves your sha (see §4 runbook).
5. The operator validates on their phone. Only they close the mission.

Report progress with evidence (measures, DOM probes, screenshots of the
deployed build) — never with impressions. The operator has zero tolerance
left for « conforme » claims that turn out to be eyeballed; every such claim
this session cost trust.

## 2. Sources of truth, in precedence order

1. **Operator messages** — always win, including over the maquette.
2. **Operator arbitrations already made** (§3) — treat as standing orders;
   do not re-litigate, do not "fix back" to the maquette.
3. **The maquette** — an interactive HTML prototype, data and CSS included:
   - Original (FORMALLY UNTOUCHABLE, read-only — file AND the browser tab the
     operator keeps open on it):
     `/private/tmp/claude-501/-Users-izno-dev-PersonalScraper--claude-worktrees-acq-escalade/d8548240-3ead-448a-96f1-c31ea219ab69/scratchpad/acquisition-prototype.html`
   - Your renderable copy (identical + a viewport meta so mobile emulation
     shows it full-screen at 390 px):
     `.../scratchpad/acquisition-prototype-debug.html`
   - Verbatim extraction of its full CSS + JS builders (grep-friendly):
     `.../scratchpad/maquette-reference.md`
   The maquette's **source** is the ground truth — its builders encode rules
   its screenshots do not show (e.g. `followRow(f, g.of.length > 1)` is why
   grouped cards keep chips). Read the source before trusting a pixel.
4. `docs/reference/product-intent.md` — the product constitution stays
   binding for anything the maquette does not specify (§8 nothing-in-silence,
   §11 no dead controls, §13 single derivation, §14 honesty rules).

## 3. Operator arbitrations — OVERRIDE the maquette and are pinned by tests

The operator issued these during the session, some against the maquette's own
rules or against the app's earlier "honesty" arbitrations. The test suite was
rewritten to pin them — if a test in this list's area fails on your change,
you probably regressed an arbitration:

1. **« ··· » on every card, at every pointer.** No chevron anywhere. (The
   maquette showed a chevron on touch; the operator overruled it three times
   before it was applied — do not bring it back.)
2. **Grid tiles: the badge carries a NUMBER** for every actionable status
   (`a_recuperer`, `en_acquisition`, `en_attente`): `max(1, aired - owned)`
   — a film counts as its one unit (1), unknown catalogue floors at 1. « ? »
   only for `non_verifie` / `verification_en_cours`. Nothing-to-do = no
   badge. Films' tile fraction line reads « acquis » / « non acquis ».
3. **Grouped mode: the maquette's four URGENCY groups**, not raw statuses —
   « Demandent quelque chose » (warning; a_recuperer + en_attente +
   non_verifie), « En cours » (info; en_acquisition + verification_en_cours),
   « À jour » (success), « En pause » (muted). Status chips STAY on cards
   inside heterogeneous groups.
4. **Nav count pills are PRIMARY (amber)** everywhere; the danger tone is
   reserved for the « ? » unknown-count state.
5. **Never touch the maquette** — not the file, not the operator's tab, not
   its emulation. Work in your own tabs only.
6. Repo-wide standing rules: code comments in English only, no dev-phase
   references in code; conventional commits, French bodies, no AI
   attribution; version bump on every PR; in `frontend/` write « ticket 411 »
   never « #411 » (eslint reads it as a hex color); `rg` ALWAYS with type
   filters (`-t py`, `-g '*.tsx'` — unfiltered rg scans 14 GB of fixtures and
   crashes the machine); `curl` ALWAYS with `--connect-timeout 10
   --max-time 30`; never start a server on ports 8710/8711.

## 4. Environment & runbook (all verified working this session)

- **Worktree**: `/Users/izno/dev/PersonalScraper/.claude/worktrees/acq-mobile`,
  branch `feat/acq-mobile`. Frontend commands run from `frontend/`
  (`npx tsc -b --noEmit`, `npx eslint src`, `npx vitest run`).
- **Staging**: `https://tm-staging.iznogoudatall.xyz` — tracks the `staging`
  branch, autodeploy poller ~60 s. Writes are role-blocked EXCEPT acquisition
  + decisions endpoints (opened deliberately). `library.db` and `.data/` are
  **shared with prod** — never create test rows in shared databases; use
  synthetic API interception instead (below).
- **Deploy loop** (the classifier blocks force-push; this ff ours-merge is
  the approved route):
  ```bash
  git push --no-verify origin feat/acq-mobile
  git fetch origin staging
  TREE=$(git rev-parse 'HEAD^{tree}')
  MERGE=$(git commit-tree "$TREE" -p HEAD -p origin/staging -m "staging: <msg>")
  git push --no-verify origin "${MERGE}:refs/heads/staging"
  # then poll until the build serves your sha:
  TOKEN_FILE="/private/tmp/claude-501/-Users-izno-dev-PersonalScraper--claude-worktrees-acq-escalade/d8548240-3ead-448a-96f1-c31ea219ab69/scratchpad/tm_session.txt"
  curl -s --connect-timeout 10 --max-time 30 \
    -H "Cookie: tm_session=$(cat "$TOKEN_FILE")" \
    https://tm-staging.iznogoudatall.xyz/api/version
  ```
  `--no-verify` is acceptable when only `frontend/` changed AND the frontend
  gates ran; run the pre-push suite for Python changes.
- **Auth token**: `.../scratchpad/tm_session.txt` (24 h JWT). Re-mint with
  `.../scratchpad/mint_session.py` executed by
  `~/staging/torrentmate-venv/bin/python` (server-side secret signs a session;
  no password involved).
- **Browser**: chrome-devtools MCP. Emulate `390x844x2,mobile,touch` in YOUR
  tab. Emulation and zoom stick per-tab — if `innerWidth` looks insane,
  measure it before concluding anything (`document.documentElement.clientWidth`).
- **Synthetic states** (to render card states absent from live data): patch
  `window.fetch` via `evaluate_script` (NOT `navigate_page`'s `initScript` —
  it runs in an isolated world and never intercepts the app), returning
  synthetic JSON for `/api/acquisition/{followed,wanted,journeys,downloads,to-handle}`.
  Then trigger the app's own pull-to-refresh by dispatching PointerEvents on
  `#acq-tabpanel` (down y=200 → move y=320 → up) — a `focus` event does NOT
  refetch because the window never lost focus. Payload shapes: copy the test
  fixtures in `MaintenantPanel.test.tsx`.
- **PWA trap**: after EVERY deploy, verify `/api/version` in the tab you are
  judging. The service worker happily serves the previous bundle; half of one
  session's "still broken" reports were a stale bundle on the operator's
  device. When the operator reports something you believe is fixed, the FIRST
  check is which build their device serves.

## 5. What exists and is verified (do not redo — build on it)

- **`frontend/src/styles/ps/maquette-acquisition.css`** — the maquette's CSS
  transplanted VERBATIM under a `.mq` scope (tabs `.seg`/`.more`, filter zone
  `.filters`/`.search`/`.pill`/`.vsw`, add screen `.fichebar`/`.addform`/
  `.res`/`.resbtn`/`.byid`/`.addfoot`/`.mqtoast`, sheet `.sheetgrab`/
  `.sheettitle`/`.sact`…). Token mapping documented in its header. Extend it
  from `maquette-reference.md`; never re-improvise values.
- **Components in maquette grammar**: `AcquisitionPage` (equal-width `.seg`
  tabs + `.n` badge + detached `.more`; sticky under the topbar via measured
  `--tm-topbar-h`/`--tm-viewtabs-h`), `SuivisPanel` (fixed `.filters` zone,
  urgency `GROUPS`, number `gridBadge`, tiles with name + mono fraction),
  `MaintenantPanel` (5 sections, download↔journey correlation by
  `info_hash`, compact « Rangé aujourd'hui » rows with episode),
  `AcquisitionCard` (kebab always), `Chip` (dotted, 19 px),
  `JourneyStrip` (5 stations, franchie/en cours/bloquée/à venir),
  `FollowDetailSheet` (poster 84×126, square episode cells 31×27 zero-padded,
  seasons newest-first / complete-collapsed / « N manquants », legend in
  squares, 6 iconed `.sact` actions, `sheetgrab`, no close cross,
  `EpisodeDatePopover` on tap), `AddMediaScreen` (full-screen from the right,
  `?add=1&q=` in history so back works and a fiche round-trip restores the
  search, « ← Retour », resbtn verb flip Suivre/Ajouter → ✓ Suivi/✓ Ajouté,
  in-screen maquette toast, `.addfoot` banner).
- **Geometry parity measured at zero** on: gutters 14, card 9/8, tabs 36,
  section heads 11/700 + 8 px pips + fg counts, chips 19, sheet title 16/700,
  `.sact` 42. Method: same `getBoundingClientRect`/`getComputedStyle` probe
  run in the maquette tab and the app tab, numbers compared.
- **All card states rendered and checked once** via synthetic injection
  (blocked strip in red, three in-flight stages, folded download 78 %,
  admitted-absent release name, resting verdicts, dispatched rows).
- **1274 frontend tests green**, pinning the operator arbitrations.

## 6. Post-mortem — the errors, in the order they were made

1. **Translating instead of transplanting.** Maquette fragments were grafted
   onto existing component skeletons; every detail "resembled", the whole
   diverged (« j'ai demandé un chat, j'ai eu un chien »). The fix that worked:
   port the maquette's DOM + CSS verbatim and adapt the app to it, never the
   reverse.
2. **Eyeball validation.** "Present-in-DOM" was treated as "conform".
   Multiple « c'est prêt » claims collapsed on contact with the operator.
   The fix: objective measurement — the geometry comparator caught a 16 px
   gutter error, 2 px tab error, 2 px sact error the eye had approved.
3. **Re-litigating operator orders.** Three reported defects (« ··· »,
   number badges, grouped chips) were answered with the app's own earlier
   arbitrations instead of being applied; the operator had to repeat them
   across three messages. An operator instruction is a standing order —
   apply it, update the tests that pinned the old rule, note it in §3.
4. **Touching the operator's belongings.** One meta-viewport line added to
   the maquette file broke its pager; emulation applied to the operator's own
   tabs alarmed them twice. Hence the formal ban in §3.5.
5. **Claiming completion without exercising flows.** Gestures, navigation
   round-trips and absent-data states went untested until the operator did it
   by hand. Every flow must run in YOUR browser tab before any claim.
6. **Not checking which bundle the device served** (PWA cache) before
   debating whether a fix landed.

## 7. What remains (backlog — verify, don't trust)

UI / parity:
- Comparator sweep not yet run on: add screen metrics, swipe action layers
  (maquette `.act` panes carry 17 px ICONS + tones grab=primary, pause=muted,
  remove=danger — the app's swipe actions currently render `icon: null`),
  pull-to-refresh spinner (`.ptr`), skeleton shimmer (`.skel`), empty states
  (`.empty`) inside panels, crossref row style (dashed border, « Contrôle → »
  in primary), grid `.tile.off` dimming for paused follows, PlusSheet,
  JourneyDetailSheet chrome, replace-confirmation dialog (`.dlg`), toast
  metrics.
- The maquette's add-screen suggestion chips (`.sugg`) show hardcoded titles;
  decide with the operator what honest data feeds them (or drop them with
  sign-off).
- Automated overlay diff (e.g. PIL) on stable chrome regions — designed, not
  built.
- Desktop pass (≥ md): the shell renders but has had zero parity attention.
- Full gesture pass on the deployed build.
Finishing:
- T16 gate: operator phone validation → PR (`/implement:feature-pr` flow),
  version bump, review cycles.
- Confirm T15 leftovers are really gone (superseded panels deleted, ranking
  editor reachable at /config?tab=classement — verify, the tracker entry was
  never closed).
Backend (see §1.3 for the four items): each needs staging-guard review,
`make openapi` + committed regenerated files (CI fails on drift), tests, and
a version bump.

## 8. Your first deliverable

Run `superpowers:brainstorming` with the operator: present the method you
propose (comparison technique, sweep order, batch size, deploy cadence,
evidence format), get their approval, then execute in small
fix→deploy→measure loops. Never present anything as done without its
measurement, and never stop between loops while divergences remain — the
operator has ordered continuous execution until perfect.
