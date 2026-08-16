# SP4 kickoff — ask first, then run all of SP4 autonomously

Paste-ready brief for a fresh session. Everything below is measured state, not memory.

## Resuming

You are resuming the TorrentMate maquette conversion. `main` = `d4d7e6bd`, v0.97.9 —
SP4a (the machinery, PR #437), the buttons/appearance work (PR #438) and the register
closure (#439) are merged. Spec: `docs/superpowers/specs/2026-08-15-maquette-sp4-vider-attrape-tout-design.md`
(the waves are defined there; the spike verdicts are engraved there). The executed SP4a plan:
`docs/superpowers/plans/2026-08-15-maquette-sp4a-machinerie.md` — the pattern to reproduce.

## The session's order (operator instruction — 2026-08-16)

**Ask the operator ONCE, at the start, for all of SP4 — then be as autonomous as
possible until the end of SP4** (SP4b → SP4c → SP4d… → SP4-end), interrupting only
for the four stop cases (irreversible/destructive, security-sensitive, effect outside
the perimeter, plan broken to the point where any path would be a guess). Concretely:

1. **First, ALL the briefs/arbitrations in one volley** (grouped AskUserQuestion): the
   SP4b plan's questions (§ below), the SP4d page-wave split (one per page or in pairs?
   proposed order: sys/maint/config → arr → lib with E-001 → acq), the fate of
   B-024/025/026 (handle in SP4b or rule on them), the CI scope (lever 2 TIA on PRs:
   now or after local confidence? coverage outside PRs: yes/no), and every arbitration
   that reading the spec surfaces. Nothing may remain that would force a mid-course
   re-ask.
2. **Then, the CI-optimization PR** (before SP4b, so every wave benefits): path filter
   AT THE JOB LEVEL (`dorny/paths-filter` — a `changes` job computes
   python/frontend/maquette/docs booleans; every heavy job always starts and reports
   green but exits in seconds outside its perimeter — the naive trigger-level
   `paths-ignore` was ALREADY rejected here: required checks stuck in "expected", the
   comment at the top of ci.yml says so) + local target `make test-impacte`
   (pytest-testmon). The full suite REMAINS the gate (main + phase gates). Patch bump,
   PR, merge.
3. **Then SP4b** (plan → execution), and chain the following waves without pause:
   each wave = branch, plan, subagents, reviews, final adversarial review, PR, CI,
   squash-merge (standing instruction), post-merge live check — then the next one.

## The first wave's mission

SP4b: **the sheet + the panel**. The most connected screen (artwork, seasons, cast,
trailers, actions) becomes the `/fiche/$titre` route as a final component; the **bottom
panel** (`openSheet` + `panneauHTML`, THE single derived constructor — R56) migrates with
it, and the legacy sites open it through the shell. Then SP4c (resolution + releases,
where M11 gets fixed), SP4d… (the pages, E-001 in the Médiathèque wave), SP4-end (the
engine's death: empty fragment, refonte.html removed as a source, bridge/aliases removed,
__go/__states reimplemented shell-side, R72/R74 renegotiated — recorded).

## What is true today (measured, not assumed)

- **The SP4a machinery**: TanStack store (`design/src/magasin.ts`, synchronous
  notification); hooks (`design/src/donnees.ts`: useEtat/useMonde/useContenu/useReferentiel
  - `ecrireEtat` — THE components' gate); boot inversion
    (`window.__demarrerMoteur({magasin, base})`, pre-bridge dead, broken module = visible
    splash); `aller()` sole navigator; `window.__ecrans.{profil,ajout}`.
- **The ownership law**: the dispatcher forwards EVERY pop; ownership lives in the
  SHAPE of the entries (`layer` / `tm:"nav"` / `tm:"garde"` / nothing = router); legacy
  writes its addresses on the `adresseBase` provided by the handshake (matchRoute at
  boot: screen route → "/", otherwise the pathname — the router is the ONLY list).
- **`#coquille` is rehomed INSIDE `.device`** (insertBefore ahead of `#screen`) — React
  screens are contained by the frame at every width, and the paint order keeps the
  legacy `#screen` on top.
- **48 rule scripts**, all green on `main`. R75 (`adresses_ecrans.py`, 8 held) and
  R76 (`navigation.py`) guard addresses and navigation. `commun.py` pins
  `color_scheme: "dark"`. CI carries the maquette typecheck.
- **`resynchro.py`** resynchronizes the search counters AND the drawer footer
  (version/sha read from the prod checkout `~/deploy/torrentmate`) — run it when
  `contenu.py` or the footer drift, commit as data.
- The measurement ritual (unchanged):
  `cd frontend/maquette/design && npm run build && cp dist/index.html /tmp/tm-refonte/wrapped.html && rm -rf /tmp/tm-refonte/vite && cp -R dist/vite /tmp/tm-refonte/vite`
  Static server 127.0.0.1:8899; drafts 8913/8917/8918; NEVER 8710/8711/8712.
  Python: `command python3` (3.12.4, chromium `channel="chrome"`). Node:
  `/Users/izno/.nvm/versions/node/v22.13.1/bin`.

## The traps this track has paid for (do not pay them again)

1. **A pathname-based filter/refusal is ALWAYS one step too short** — paid twice
   (R-5 then R-10). Ownership is read from the shape of the entries and from
   `adresseBase`, never from a copied list.
2. **A subagent that launches the suite in the background and ends its turn NEVER wakes
   up** — set a clock guard (25-30 min background sleep) on EVERY long dispatch; on
   waking, measure (processes + logs + git) and re-engage the sleeping agent via
   SendMessage with the measured state.
3. **Gesture listeners anchored on `#device` are a latent trap** for every migrated
   screen: long-press was rewired onto `document` in SP4a, but pull-to-refresh, the
   swipe between views and the sheet drag remain anchored — THE SHEET WILL MEET THEM
   (cast carousel, sheet). Mandatory audit in the SP4b plan.
4. **`.screen.open` is ambiguous** as soon as two stackable layers carry it — the rules
   read `#screen` explicitly next to it (ecrans.py/pont.py, held rules reinforced).
5. **The orchestrator's arbitrations are findings like any other**: submit them
   explicitly for contestation at the next review. The final adversarial review over
   the WHOLE diff is mandatory before the PR — it is what caught SP4a's Critical.
6. Source/harness comments in English, timeless (no phase tags). Commits in French,
   scope `(shell-mobile)`, patch bump on every PR, `git add -f` for docs/ only.
   Verify the remote SHA after every push. R59/R69/R71 at unchanged code = each
   wave's gate; any exception = an amendment RECORDED in regions.json.

## The questions the SP4b plan must settle

- **Route-on-route stacking**: the sheet opens from EVERYWHERE (`data-fiche`
  delegation), including from `/ajout` (results → sheet = a screen ON a screen, R71).
  In legacy it was `pileEcrans` inside `#screen`; in routes it is `/fiche/X` pushed
  onto `/ajout?q=…` — going back must rediscover the covered screen (query and scroll
  included). This is THE delicate piece of the wave, the SP3 bridge's equivalent.
- **The panel**: `openSheet`/`panneauHTML` becomes React (a single constructor,
  declared blocks, R56) — or stays legacy one more notch? The spec says: it migrates
  with the sheet, its biggest producer. The remaining legacy producers go through the
  seam.
- **The sheet's data**: `sheetFor`, `saisonsDe`, HEROS/POSTERS/ACTEURS, trailerIds —
  what the handshake exposes (referential) vs the world (mutable). Identity stays the
  title (NFC) until the binding mission.
- **The sheet's gestures** (cast carousel pan-x, draggable sheet) under a React
  screen — doigt.py/souris.py must pass through unchanged.

## Open in the register and deferred (do not lose)

**B-024 → B-029** (in the register, arrived from an adversarial review of fix #434 by
ANOTHER session — read their entries in `BUGS.md` before planning): B-024 `data-go` only
settles ONE history entry when several layers are buried (latent; check what SP4a's
dispatcher/base overhaul changed about it before handling); B-025 `bugs.py` check 10b
never presses Back (the screen half of the fix has no guard); B-026 the handler's
`catch {}` can leave URL and interface silently disagreeing; B-027/B-028 `resynchro.py`
(naive `t:` extraction; unknown titles read as up to date); B-029 `contenu.py`'s counter
rule misses suffix drift ("1" inside "11"). B-024/025/026 touch code SP4b will
re-traverse — handle them or rule on them in the wave plan, not in silence.

- B-021/B-022 `to confirm` (operator, on device). B-019/020/023: CLOSED (#439).
- M11: the Associer flow does two `history.back()` in the same task — deferred, FIXES
  ITSELF in SP4c when the resolution screen migrates (its code is rewritten).
- Dedicated rule for the visible error component (`EcranEnErreur`, wired) — to write
  when a screen error path becomes exercisable.
- `audit2.py` R11: the element-selection fallback ignores `.screen.open` (coverage
  silently narrowed). npm CI cache without design/'s lockfile (slow, never wrong).

## Expected starting state

`main` = `d4d7e6bd`, v0.97.9, suite 48/48 green, `make check` green, design host (pm2
`torrentmate-design`, 8712) serves this checkout. Squash-merge allowed once CI is green +
final review clean (standing operator instruction, verbatim: « on enchaîne », « le
travail doit être bien fait », « tu es le garant — jamais te cacher derrière les
sous-agents »).
