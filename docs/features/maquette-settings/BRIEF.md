# maquette-settings — the settings the operator could not use by hand, repaired off the engine

## Launch addenda — 2026-09-12, written by the steward at launch; they override the text below where the two differ

1. **Where you write.** In the worktree `/Users/izno/dev/worktrees/wave-settings`, branch
   `fix/maquette-settings` cut from `origin/main` at `468162dc6` (version 0.98.83) — NOT the main
   checkout. You are the only writer there. The « L21 still there → STOP » clause is void: L21 merged
   on 2026-09-11 (#572, squash `2ffdc4ba3`) and its folder is gone.
2. **Register and rules.** Your block is **B-397 to B-419** and **R165+** — B-393..B-396 and R161..R164
   are the resolution-card micro-wave's (#585, in flight, not yet on main); the tooling wave holds
   B-420+, the L20 design wave B-440+. Gaps are accepted; renumbering happens at the merge only on a
   collision. Verify with `python3 scripts/check-bug-register.py --next` on YOUR branch and say the
   reserved block in the pull request.
3. **The « on the operator's phone » sentences are void** (operator, 2026-09-06: device readings are
   over — a defect must be visible on the Mac; B-333's probe is cited as history, not re-run). Your
   rules drive the real path with a real touch in the harness's browser; the operator walks the
   build on his Mac when the steward serves it.
4. **The pull request is opened READY, not draft** (a draft runs no CI; a PR opened draft and made
   ready in the same breath dispatches a skipped run — trap of 2026-09-12). Title in English,
   conventional; the version bump reads `main`'s at that moment (0.98.83 now; #585 will bump to
   0.98.84 — re-read before you write). Label nothing.
5. **Figures once**, on the final head, in a DESIGN.md § of your folder (`docs/features/maquette-settings/DESIGN.md`,
   yours to create: the state measured, the rules and their holds, the mutations, what the fixtures
   cannot show). Every figure carries its command.
6. **Gate on the final head, in this order, each exit code read**: contracts tier (shared lock) →
   the full suite once (shared lock, expected no violation) → `--a11y` → the oracle (divergences
   accepted ONLY on the states § 6 names, zero elsewhere or STOP B) → hold-counts compare with
   `failed` read FIRST → `make check` (own lock, 3 workers) → wrapped push. `docs/` is no longer
   ignored anywhere (`git check-ignore` is clean): add documents by file, `git add <path>`.
7. **Every heavy run follows the envelope at the end of this file**, which the operator loosened
   today; the settings text below that names `heavy.sh settings <command>` without the floor is read
   with it.
8. **Communication**: your orchestrator's exact name and reference are in your launch prompt, never
   discovered; handshake first (one message: the state-verification readings, your gauge, and
   nothing edited before the answer); reports on start, each push, any STOP, and at the end with
   named sections; silence rule 15 min. **Do not stop between steps to report one done.**


You open a **micro-wave of BEHAVIOUR**, decided by the operator on 2026-09-06 (his second decision
round, questions 1, 3, 4, 5 and 8). His test session on the design host that morning found
« Réglages » unusable by hand: an edit that only commits when the field loses focus, a save that says
« Enregistré » and shows the old value, a restart banner that never follows a save, two secret-panel
acts that do nothing, and rubrics — on « Réglages » and on « Maintenance » alike — that cannot be
left. Every one of them is React's, the mock layer's, or a verb the dying engine still answers; none
needs the engine EDITED, and the operator refused to leave them to L13, the last lot, because they are
what keeps two repairs of L19 (B-299, B-300) unconfirmable by hand. No lot. It runs AFTER L21 merges
(it rests on L21's verb registry, `lib/verbs.ts`, and on ARM 7 of `check-markup-contracts`, which
refuses a `data-*` verb that markup emits and no feature registers) and BEFORE L20. Branch
`fix/maquette-settings`, one pull request, squash merge, the version bumps. It writes in the main
checkout `~/dev/PersonalScraper` once L21 is merged and its folder gone; if L21 is still there when you
are launched, STOP and tell the steward — two writers in one checkout is the failure this repository
paid for.

**The entries, and what each one is — read them whole in `BUGS.md` before touching anything.**

- **B-334** « Remplacer la valeur » and **B-335** « Retirer la clé » on a secret do nothing:
  `features/settings/panel-secret.ts:81` and `:88` give the actions `target: { toast: … }`, a
  `data-toast` the engine's delegation reads (`legacy.js`, `if (closest.dataset.toast) toast(…)`) into
  `#toast` — the dying engine's message element, EMPTY while a React message is on screen (L21's
  measurement). No layer is written. B-335 is DESTRUCTIVE (a provider cut for every account of the
  household) and confirms first, in B-300's form; **the sentence is dictated** (question 5): title
  « Retirer la clé <fournisseur> ? », body « La clé sera retirée pour tous les comptes du foyer. Ce
  fournisseur ne répondra plus tant qu'une nouvelle clé n'est pas saisie. », buttons « Annuler » /
  « Retirer la clé » (danger, right), message after confirming « Clé retirée. ». The walk goes through
  the cancel before the confirm.
- **B-341** the field commits on blur and the two labels read backwards: `panel-field.tsx:159-185`
  binds the native `change` event (three measured reasons in its comment — keep them) and offers no
  control; the panel prints the pending value under « Valeur actuelle » and the stored one under
  « Valeur écrite » (`fr.json` `panels.setting.currentValue` / `writtenValue`). **Dictated**
  (question 4): a **« Valider »** button in the field's panel — the edit is filed on the tap; and the
  labels become **« Nouvelle valeur »** (pending) and **« Valeur enregistrée »** (stored). The
  two-step writing (edit, then the bottom bar writes the files) is DOIT-8's and stays.
- **B-342** the save says « Enregistré » and the row shows the old value:
  `mocks/handlers/configuration.ts`, `updateConfigurationFile`, records the file's NAME in
  `changedFiles` and never reads the request's body into `held.settings`, so the next read answers
  the seed (D7: a mock that answers without moving certifies nothing).
- **B-343** the restart banner does not follow a real save: `panel-setting.ts:195` raises
  `reference.SETTINGS_STATE.redemarrage` on an ENGINE object, `page.tsx:149` reads it, nothing
  re-renders between. The layer already answers `restartRequired` on the write — the banner becomes a
  reader of the LAYER (a query), and the flag leaves the engine object. This is what makes B-300's
  confirmation reachable by hand, and B-299's conflict banner with it.
- **B-332** and **B-361** a rubric of « Réglages » / of « Maintenance » cannot be left — measured on
  the operator's phone by the real path (B-333's inventory): entering pushes NO history entry
  (`legacy.js` `if (closest.dataset.topic)` writes `SETTINGS_STATE.topic` and `replacePath()`;
  `if (closest.dataset.maintopic !== undefined)` writes `maintTopic` and `replacePath()`), no back is
  drawn (`page.tsx` `TopicView`, `features/maintenance/page.tsx:66-75`), and the system Back leaves the
  PAGE for `/acquisition`. D1b rule 1: a topic is a deliberate ARRIVAL — it pushes, and it draws its
  back like a screen does (`data-part="screen/back"`, `backAction()`, `window.__bridge.back()` —
  `media-screen.tsx:233` is the pattern). The two verbs move onto the registry; the two engine
  branches are DELETED and the ledger re-recorded downward in the same commit.
- **B-345, the settings half** (question 3): the data the design host serves at rest offers to a
  hand what these surfaces can draw — a file whose write answers `conflict: true` so B-299's banner
  can be reached by saving it, and the restart banner reachable THROUGH a save (B-343) — with a rule
  that counts them and never calls `window.__go`.

## What you read before acting

1. `CLAUDE.md`; `docs/reference/documentation-model.md`; `docs/reference/frontend-architecture.md`
   § 0 (yours is BEHAVIOUR — every repair lands with its rule seen red first), D1b (Back pops a stack
   of deliberate arrivals; a topic is one), D5 (the engine only shrinks — you delete two branches and
   add none), D7 (the contract is the maquette's; the mock MOVES state), D8 (the oracle measures at
   rest — a « Valider » button and a back affordance are surface changes: their divergences are
   ACCEPTED with their entry as the reason, on the states they touch and on no other), § 3 invariants
   7 and 10, § 4's L13 entry (what stays there: B-312, B-331, B-336, B-340 — engine-drawn, not yours),
   § 5, § 7.1.
2. `docs/reference/product-intent.md` — DOIT-8 (two-step writing), §17 (a restart and a removed
   key reach every account of the household), NE-DOIT-PAS-1 (an interface that says a thing was done
   when it was not), NE-DOIT-PAS-6.
3. `frontend/maquette/design/src/lib/verbs.ts` — the registry (`registerVerb(name, act)`, one
   delegated listener in capture, `stopPropagation` on a match); `features/acquisition/journey-verbs.ts`
   — L21's two verbs, the pattern you copy; `scripts/markup_verbs.py` and ARM 7 of
   `scripts/check-markup-contracts.py` — the guard that refuses a verb nobody registers, and that
   will refuse yours until you register them.
4. `BUGS.md`: the seven entries above, whole; **B-299** and **B-300** (the two L19 repairs your
   wave makes confirmable — read their « CONFIRMATION ATTEMPTED » paragraphs); **B-309** and
   **B-345** (the seeds); **B-337** (a first tap lost after a swipe — not yours, but the shape of a
   rule that taps ONCE with a real touch); **B-273** and **B-330** (`mutate.sh` judges a RULE by its
   FAIL lines, takes a rule PATH, and is silent on a broken build); **B-307** (a fall under load
   prints its reading).
5. `frontend/maquette/design/src/features/settings/` whole (`page.tsx`, `panel-setting.ts`,
   `panel-field.tsx`, `panel-secret.ts`, `queries.ts`, `reference.ts`), `features/maintenance/page.tsx`,
   `mocks/handlers/configuration.ts` (the settings and the secrets routes — `updateSecrets` already
   moves `held.secrets`; `updateConfigurationFile` does not move `held.settings`), `app/history-bridge.ts`
   (`record`, `replace`, `pushLayer`, `back` — the bridge's verbs, on the router's own history),
   `frontend/maquette/harness/settings.py` (65 holds: B-299's three and B-300's seven, driven from
   NAMED STATES — your holds reach the same banners THROUGH a save), `harness/page_host.py`.
6. `docs/reference/frontend-steward.md` § « What a review costs, and the five rules » and
   § « Instrument hygiene »; `frontend/maquette/README.md`.

## Verify the state; do not believe it

    git remote update origin >/dev/null && git log --oneline origin/main -3
    pwd && git branch --show-current
    ls docs/features/            # maquette-l21 must be GONE (its post-merge gesture done), or STOP
    grep -o "| \*\*In flight\*\*[^|]*| [^.]\{0,60\}" IMPLEMENTATION.md
    python3 scripts/check-bug-register.py --next
    grep -n "registerVerb(" -r frontend/maquette/design/src/features | wc -l
    grep -nE "dataset\.(topic|maintopic|toast|restart)\b" frontend/maquette/design/src/engine/legacy.js
    grep -n "toast:" frontend/maquette/design/src/features/settings/panel-secret.ts
    grep -n "redemarrage" frontend/maquette/design/src/features/settings/panel-setting.ts frontend/maquette/design/src/features/settings/page.tsx
    grep -nE '"(currentValue|writtenValue)"' frontend/maquette/design/src/i18n/fr.json
    python3 scripts/check-frontend-boundaries.py --arm size | grep legacy.js
    grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1
    python3 -c "import json;d=json.load(open('frontend/maquette/hold-counts-baseline.json'));print(d['taken_at_commit'][:9], d['totals'])"

Read on 2026-09-06 at `d9659a64e` (before L21 merged — re-read every figure on the day): the four
engine branches at `legacy.js:8914`, `:8991`, `:9120`, `:9325`; the two `toast:` targets at
`panel-secret.ts:81`, `:88`; the flag set at `panel-setting.ts:195` and read at `page.tsx:149`; the
labels at `fr.json:875-876`. **Your block is B-380+ and R150+** — L21's, the departure wave's, the
desktop-frame wave's and the steward's blocks are all below it; say so in the pull request rather
than renumber.

## The six things the plan does not tell you

### 1. A verb moves the way L21 moved one: rule first, red against the engine, then the move

For `data-topic` and `data-maintopic` the engine's branch still exists, so the rule is RED with no
mutation needed — the strongest form of « seen red first »: load `/settings` by its address, tap a
rubric row by a real click, hold that `history.length` grew by one, that `[data-part="screen/back"]`
is drawn inside the topic view, that `history.back()` lands on the page's LIST with the topic closed
(the heading gone) and the page still `/settings` — and the same on `/maintenance`. That walk is
exactly the one the steward took on the operator's phone (B-333's `cdp-back-real.py`), and it read
false on both pages. Then the move: `registerVerb("topic", …)` in `features/settings/`,
`registerVerb("maintopic", …)` in `features/maintenance/`, each pushing through the bridge's
`record` (or `pushLayer`, whichever the ladder's rules R59, R65, R69, R82, R94 accept — read them, do
not guess) and writing the address the same way the maintenance branch already does (`?topic=…`);
the two engine branches deleted in the same commit; the rule green with its count unchanged.
**Ask what the rule reads**: a hold on `history.length` alone is green over a topic that pushes and
draws no back; a hold on the back button alone is green over a button that pops the wrong entry.
Both, and the landing.

### 2. « Valider » is a panel ACTION, and its verb is registered like any other

The field's panel is a producer (`panel-field.tsx`, re-opened by `window.__panel.produce("setting", id)`).
Its « Valider » is an action whose `target` names a verb you register — the edit filed from the
input's current value on the tap, then the panel re-produced so the pending count moves. The native
`change` listener may stay as a second path (a keyboard's « ✓ » that does blur still commits); what
must be true is that a tap on « Valider » commits WITHOUT a blur. The rule types into the field with
a real keyboard, taps « Valider » once, reads the bottom bar's pending count (`1 modification en
attente`) and the panel's « Nouvelle valeur »; its mutation is the button doing nothing. The two
labels are i18n keys renamed for what they say (`pendingValue`, `storedValue` or the like — English
keys, French values, extracted never retyped).

### 3. The mock MOVES, or the interface lies twice

`updateConfigurationFile` reads the request's body and writes each changed setting into
`held.settings`, so the next `readSettings` answers the new value; `restartRequired` stays as it is.
The rule saves and READS BACK through the layer (`window.__mocks.answered()` for the call, the
panel's « Valeur enregistrée » for the value) — never the toast. For the secrets, `updateSecrets`
already moves `held.secrets`: B-334 writes the new value through it (held when offline, put back on
refusal — the outbox's own discipline, `app/outbox.ts`), B-335 clears it after the confirm; the rules
count the layer's write and, for B-335, walk the cancel first (the key still there, nothing said)
then the confirm (the key gone, and said).

### 4. The restart flag becomes the layer's, and the banner a reader of it

`held.restartRequired` is the fact; the banner reads it through a query and re-renders when it
flips, as every other banner does. `panel-setting.ts:195` stops writing an engine object. The rule
reaches the banner THROUGH a real save — edit, « Valider », « Enregistrer », the banner up — and then
walks B-300's confirmation from there (`harness/settings.py`'s seven holds drive it from a named state;
yours reach it by the path the operator walks, which is rule 4 of the register). When that hold is
green, B-300 and B-299 can be confirmed by the operator by hand; say so in their entries rather than
closing them yourself — the confirmation is his.

### 5. The seeds' settings half

At rest, one file answers `conflict: true` on its write (the mock's `conflict` is a dial today —
`setConfigurationConflict(true)` — and stays one; what the seeds add is a FILE marked as moved under
the editor, so a hand reaches the banner by saving that file), and the restart banner is reachable by
saving any setting (4). R-seeds counts both, on the default scenario, and NEVER calls `window.__go`
(R128's own design: a hold that drives a named state first measures what the harness reaches and
reports it as what a hand reaches).

### 6. The oracle will move, and the entries say where

A « Valider » button in the field's panel, a back affordance in two topic views, a heading that was
not there: each is a surface change at rest, and D8 accepts its divergence with the entry as the
reason — ONLY on the states those surfaces draw (`settings-one`, `settings-field-*`, `settings-topic`,
`maintenance-topic`), every other state at zero. A divergence on a state this wave did not touch is
STOP B. The reference is re-recorded at the post-merge gesture by the steward, not by you.

## What you do not do

- **You do not enter a checkout another writer holds.** L21 is merged and gone before you start,
  or you STOP.
- **You do not add a line to `legacy.js`** — you delete four branches (`topic`, `maintopic`, `toast`
  where it is the only reader left, `restart` only if B-300's move needs it) and re-record the ledger
  downward; a branch that still has a reader elsewhere stays.
- **You do not touch B-312, B-331, B-336, B-340** (L13's, engine-drawn), nor the library, nor the
  frame's transitions, nor `harness.css`.
- **You do not change DOIT-8's two-step writing**, the field's native `change` path, nor the
  dialog primitive (`ui/dialog`) — you use it.
- **You do not close B-299 or B-300** — you make them confirmable and say so; the operator confirms.
- **You do not stop between steps**; the only stops are STOP B (a divergence on a state you did
  not touch) and the pull request.

## The gates, and the machine

Per commit: the contracts tier and the cheap guards (`run.sh --contracts` — ARM 7 among them, and it
must be clean over your registrations). Before the pull request: the full suite (`run.sh`, expected
**no failure**), `--a11y` 0, the oracle with its divergences ACCEPTED on the named states and zero
elsewhere, `make check` at 0 failed / 0 errors, the hold-count compare with `failed` read FIRST.
Every heavy run wrapped: `TM_HARNESS_JOBS=2 sh scripts/heavy.sh settings <command>`,
`PYTEST_XDIST_AUTO_NUM_WORKERS=3` for the test suite and the pre-push hook — **a `git push` IS a
heavy run** whose output goes to a FILE, landed only when `git ls-remote --heads origin <branch>`
shows the ref (B-360). One harness per machine: announce every run that touches the served copy to
the steward and to any other agent named in your invocation, and wait for the steward's word. Kill
what you start, delete what you build, prove with `ps`.

## How you deliver

Branch `fix/maquette-settings`, one pull request opened as a DRAFT at your first push (a draft
runs NO CI since the operator's decision of 2026-09-08 — read it after `ready_for_review`, or on
the draft itself by adding the `run-ci-on-draft` label), English title and body, the version
bumped after reading `main`'s at that moment. Write the « In flight » row when the pull request opens (number first, then version).
B-334, B-335, B-341, B-342, B-343, B-332, B-361 read `fixed #<n>` by rule 3; B-345's settings half
is written into B-345's entry with the rule that counts it; B-299 and B-300 gain the sentence that
makes them confirmable by hand. Recount « guards green over what they do not read » for your wave,
zero included. Then message the steward — its exact address is in your invocation — and the steward
launches independent readers on a worktree pinned at your head against a control of `main`, and reads
the topics' Back on the operator's phone by the same probe that found them. You alone write. The
operator gives the merge word. Your folder leaves the tree at the post-merge gesture, cited by the
squash.

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
