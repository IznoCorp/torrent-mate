# maquette-mock-layer — the mock answers what the contract declares, one season family, and two verbs that send

You open a **micro-wave of BEHAVIOUR on the mock layer and its seeds**, ordered by the operator on
2026-09-12 (« dès la fusion de #585 tu lanceras tout ce qui est parallélisable »). Four register
entries, each read WHOLE in `BUGS.md` before anything is touched, each repaired with a rule seen RED
first and mutated. Worktree `/Users/izno/dev/worktrees/wave-mock-layer`, branch
`fix/maquette-mock-layer` (cut from `origin/main` at `561ac7a39`, version 0.98.84); you are its only
writer. One pull request opened READY, patch bump, squash merge. Register block **B-470 to B-489**,
rules **R170+** (settings holds B-397+/R165–R169, the gesture B-460+, tooling B-420/421, L20 B-440+;
gaps accepted; `--next` on your branch cannot see the others).

**The seeds are B-369's cost, and the operator accepted paying it for this wave**: a seed edit moves
the named states drawn from that seed, their rules and the oracle's reference. So every seed change
lists, in DESIGN.md, the named states it moves (`grep -rn "<title>" frontend/maquette/regions.json
frontend/maquette/design/src/mocks/seeds/`), the rules that read them, and the oracle divergences it
accepts on exactly those states (D8) — zero elsewhere, or STOP B.

## The entries

1. **B-379 — the mock answers 200 whatever the contract declares** (`mocks/scenario.ts:145`,
   `armed ? (asked.status ?? 200) : 200`): `grabSeasonForFollow` declares 201, `requeueJourney` and
   `rescrapeJourney` 202. **Closes when** an unarmed answer carries the operation's declared success
   code, read from the maquette's contract (`frontend/maquette/contract/openapi.json` — the
   generated types or a small reader of the contract, never a hand-written table), and a rule holds
   one declared code per family (201 for a creation, 202 for an accepted ask, 200 otherwise) by
   reading `window.__mocks.answered()`; mutation = the code forced to 200.
2. **B-380 — two season families at one title**: `absorbedCount` derives from `seeds/seasons.json`
   while the media sheet draws its rows from `media-sheets.json`; the two disagree on 13 of 49
   seasons (the table is in the entry). **The operator ruled on 2026-09-11: « manquant » = AIRED and
   not owned; an unaired episode is not missing, it is drawn to INFORM of an upcoming release.**
   **Closes when** (a) the seeds agree: `seasons.json` is the one family for aired counts and the
   sheet's catalogue says, per season, how many episodes are AIRED at the referential's TODAY
   (2026-08-10) and how many are announced — reconcile the 13 disagreements TOWARDS the aired counts
   and write the reconciliation table in DESIGN.md; (b) the sheet's row denominator is the aired
   count and its « N manquants » counts aired-not-owned only; (c) an upcoming season or episode is
   drawn as information (« à venir », the date if known) and offers NO act — L21's `seasonUpcoming`
   gate already refuses the act; you draw the information beside it, minimal, the copy extracted
   into `i18n/fr.json` never retyped; (d) a rule reads both surfaces (the sheet's row and the follow
   panel's) on three titles and holds they agree with the seed, plus one upcoming season drawn as
   information with no act; mutation = the denominator back to the catalogue's total.
   The Animaniacs sheet's season 5 (aired 1997) keeps the act.
3. **B-396 — one folder with candidate cards**: the resolution window's riskiest path (a second pick
   inside the first's 7 s window; the put-back into a list that moved) has no finger proof.
   **Closes when** the seed offers a SECOND queued folder with candidate cards (a real title, two or
   three candidates with distinct providers/years), and a rule walks by a REAL touch: pick A, then
   pick B inside A's window, « Annuler » on the latest message puts back ONE card at its index, the
   POST for A still leaves at 7 s (network), only the latest message carries an undo; then the
   put-back with the list moved (a third folder arriving through the mock's own path between the
   pick and the undo). The `arr-*` named states this moves are listed and their divergences
   accepted (D8). Mutation = the second folder's cards removed → the walk cannot start (the rule
   says so rather than passing).
4. **B-383 — « said, not done », two of its four verbs**: « Re-scraper les métadonnées » on the
   follow panel and « Lancer à blanc » on a maintenance action each answer a canned sentence and
   send nothing. **The other two are NOT yours**: « Remplacer la valeur » on a secret is repaired by
   the settings wave (B-334, PR #588), and « Lancer la veille maintenant » is L20's by the
   operator's ruling of 2026-09-12 (it is DOIT-6's operation, `POST /api/acquisition/detect`) — write
   that split into B-383's body and close only your half (`fixed #<PR>` when both of yours are done,
   the entry's body naming the two owners of the rest). **Closes when** each verb calls its
   operation through the layer (the follow's re-scrape: the existing `rescrapeJourney` or the
   operation the contract has for a follow — read the contract; if none exists it is a D7 demand and
   you STOP to say so with the reading), the mock MOVES the state it answers about, the message
   says what happened; a rule reads the network and the moved state, never the toast; mutation =
   the call removed.

## What you read before acting

1. `CLAUDE.md` whole; `docs/reference/frontend-architecture.md` § 0, D5 (the engine only shrinks —
   if a verb still lives in `legacy.js`, it moves onto `lib/verbs.ts` and the branch is deleted), D7,
   D8, § 3 invariants 7 and 10, § 5; `docs/reference/product-intent.md` NE-DOIT-PAS-1, NE-DOIT-PAS-5,
   §13, §5 (season by season).
2. `BUGS.md`: B-379, B-380 (with its table), B-396, B-383, B-369, B-378, B-309, B-088 (the class of
   two data families), B-273/B-330 (`mutate.sh`), B-307; § Status vocabulary.
3. `frontend/maquette/README.md` § « The mock layer » and § « Every state has a name »;
   `frontend/maquette/contract/README.md`; `mocks/scenario.ts`, `mocks/handlers/*.ts`,
   `mocks/seeds/seasons.json`, `mocks/seeds/media-sheets.json` (or where the sheet's catalogue lives —
   `grep -rn "MEDIA_SHEETS" frontend/maquette/design/src/mocks/`), `features/media/season-list.tsx`,
   `features/media/panel-seasons.tsx`, `features/acquisition/season-grab.ts`, `lib/queue.ts`,
   `lib/held-actions.ts`, `features/arrivals/resolution-cards.tsx`; the rules R125 `season_grab.py`,
   R138, R158, R160, R161, R162 (what each reads — you add legs or new rules, never weaken one).
4. `docs/reference/frontend-steward.md` § « What a review costs » and § « Instrument hygiene ».
5. The operator's rulings on B-380 are quoted in its body; DESIGN.md quotes them verbatim.

## Verify the state; do not believe it

    git remote update origin >/dev/null && git log --oneline origin/main -3
    pwd && git branch --show-current && git status --short
    python3 scripts/check-bug-register.py --next
    grep -n "asked.status ?? 200" frontend/maquette/design/src/mocks/scenario.ts
    grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1
    grep -c "" frontend/maquette/design/src/mocks/seeds/seasons.json
    grep -rn "seasonUpcoming" frontend/maquette/design/src/features/media/*.tsx | head -3
    grep -rn "Re-scraper les métadonnées\|Lancer à blanc" frontend/maquette/design/src/i18n/fr.json | head
    python3 -c "import json;d=json.load(open('frontend/maquette/hold-counts-baseline.json'));print(d['taken_at_commit'][:9], d['totals'])"
    ls frontend/maquette/design/node_modules | wc -l; ls frontend/node_modules | wc -l   # 0 → npm ci (own lock)

## Order

B-379 first (every later rule reads answered codes), then B-383's two verbs, then B-396 (a seed
edit), then B-380 (the largest seed edit) — the seed edits LAST so the rules written before them are
green on the old seed and re-run on the new one. DESIGN.md (`docs/features/maquette-mock-layer/DESIGN.md`)
carries, per entry: the state measured, the rule and its holds, the mutation, the named states moved
and the divergences accepted, figures once on the final head.

## Non-goals

- No surface redrawn beyond the minimal « à venir » information of B-380 (c) and the sheet's
  denominator; no change to the card, the frame, the harness chrome, `harness.css`.
- No line added to `legacy.js`; the ledger re-recorded downward if a branch is deleted.
- No edit to the two B-383 verbs that are not yours; no edit to `features/settings/`.
- No re-recording of the oracle's reference or the hold-counts baseline (the gesture's).
- No edit to `IMPLEMENTATION.md` beyond nothing — a micro-wave is traced by the gesture.
- If you believe something outside this list is needed, STOP and ask the orchestrator first.

## Gates and delivery

Per commit: `run.sh --contracts` (shared lock). Before the pull request, on the final head: the
FULL suite once (shared lock), `--a11y` 0, the oracle with divergences accepted ONLY on the named
states DESIGN lists (zero elsewhere or STOP B), hold-counts compare with `failed` read FIRST,
`make check` (own lock, 3 workers). Merge `origin/main` before the push (two waves may land first:
settings #588, tooling #589 — the register's rows/bodies conflict has a SHAPE: rows with rows in
ascending order, bodies after, then the guard clean). Wrapped push, `ls-remote` read, PR READY,
title `fix(maquette-mock-layer): the mock answers the declared code, one season family, two verbs that send`,
register rows `fixed #<PR>` by rule 3, report to the orchestrator (head, PR, run id, gauge). Then
STOP as the sole writer.

## Communication

Your orchestrator's exact name and reference are in your launch prompt. Handshake first (readings,
gauge); report on each entry's commit, on the push, on any STOP; silence rule 15 min; do not stop
between entries to report one done.

## Resource envelope — the machine is shared with three other agents (2026-09-12)

Four agents and the steward run on this 8-core, 16 GB host at once, by the operator's order of
2026-09-12 (« tout ce qui peut être parallélisé doit l'être ; les agents lancés ne doivent pas être
bloqués »). The same word loosened the wrapper for this day: the readiness floor of
`scripts/heavy.sh` is 2 560 MB for every run of this wave (its hard floor stays 2 048 MB — it
kills its own child under it, never anything else), and B-386 is what turns this into a rule
by class instead of a number set by hand. Nothing below is optional.

- **Two locks, by what the run reads.** Anything that touches the ONE served copy
  (`/tmp/tm-refonte`) or the 8899 host — `run.sh` in any tier, the oracle, `harness-hold-counts.py`,
  `mutate.sh`, a single rule replay — runs under the SHARED lock:
  `HEAVY_FREE_FLOOR_MB=2560 TM_HARNESS_JOBS=2 sh scripts/heavy.sh <wave> <command>`. Everything
  else that is heavy — `npm ci`, `npm run build`, `make check`, `pytest`, a `git push` (the pre-push
  hook runs the test suite) — runs under the wave's OWN lock, so it can proceed beside another
  wave's harness run:
  `HEAVY_LOCK=/private/tmp/tm-heavy-<wave>/holder HEAVY_FREE_FLOOR_MB=2560 PYTEST_XDIST_AUTO_NUM_WORKERS=3 sh scripts/heavy.sh <wave> <command>`.
  `<wave>` is your wave's codename. A run that holds the shared lock is announced to the steward
  in one line before it starts (« harness run starting ») and one after (« done, exit N »).
- **Fan-out has a name and a value, every time**: `TM_HARNESS_JOBS=2`,
  `PYTEST_XDIST_AUTO_NUM_WORKERS=3`. Never a build beside a parallel test run of your own.
- **Every command runs synchronously in the tool call that waits for it**, output to a FILE
  (`> /tmp/<wave>-<step>.log 2>&1`), the exit code read in the same call; never `| tail -N` on a
  long gate, never a turn ended « waiting for » a run. A push landed only when
  `git ls-remote --heads origin <branch>` prints the ref.
- **Kill what you start, delete what you build, prove it with `ps`** (`ps -eo pid,etime,command |
  grep -E "chrom|playwright|vite|node|pytest" | grep -v grep`) before every report. The 8899 host
  (`server.py --serve 8899`, pid at parent 1) is `run.sh`'s and is left alone.
- **Never `cd` into `frontend/maquette/design/src`** (B-384): absolute paths from your worktree root.
- **Read the lock, never the directory**: `sh scripts/heavy.sh --held` (or with `HEAVY_LOCK` set).
- Context: run `/Users/izno/.claude/plugins/cache/lounisbou/orchestrator/0.26.1/skills/context-gauge/scripts/context-gauge.sh`
  as the LAST call before every report and paste its `context_percent=` and `source=` lines; past
  60 %, finish the unit in progress, push a resume note in your folder, and stop.
- Tier **deep** (the map binds every tier to opus; no tier of this project is ever Sonnet), chosen
  because every deliverable here is judged by nothing downstream but the steward's reading. Your
  session was spawned with NO MCP server; the harness needs none.
