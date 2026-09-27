# L22b — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l22/BRIEF-L22b.md` (governs) and `RULINGS.md` (the lot's own; L22a wrote 1–12,
L22b appends from 13).

## STATE

- Branch `feat/maquette-l22b`, worktree `/Users/izno/dev/worktrees/wave-l22b`, cut from L22a's pull-request head
  `6f0c987a3` (#619, READY, under its reader round). L22a's squash onto `main` is the steward's, named when it lands;
  then you merge `origin/main` in at your next unit boundary. Steward: `Orch : TM frontend`.
- Head: see `git log -1`; pushed state: `git ls-remote origin refs/heads/feat/maquette-l22b`.
- ORDER (steward, 2026-09-27): phase 15 CUT at its opening into 15a / 15b. 15a DONE. **15b WAITS** for the operator's
  word on Q1 (« supprimer » = a real disk delete, new operation — recommended — or `discardStagedMedia`) and on the
  « suivis stoppés » question; Q2 is ruled (both: the act removes the card; a folder deleted outside the app is absent
  after the re-read, an assertion in R227). Keep for 15b: ingest COPIES a seeding/seed-obligated torrent and MOVES any
  other (`ingest.py:549-561`, tracker `action: copied|moved`) — deleting a moved arrival deletes the only copy.
- DONE: 15a, 16, 17. NEXT: 18 → 19 → 20 → [MIDPOINT full suite] → 21 … 27; 15b slots back in when
  ruled (at the next unit boundary after the word).
- Rule numbers: L22's a..u = R202–R222; R223 #616's; R224 (v), R225 (w) L22a's. L22b: i = **R226**
  (`set_aside_is_later.py`); 15b's rule = R227 (reserved); j = **R228** (`not_a_media.py`); l = **R229** (`follow_offered.py`); next free R230.
- LOGS: `~/Library/Logs/tm-l22b/`. Mutex `sh scripts/heavy.sh --held`; own npm lock `/private/tmp/tm-heavy-l22b/holder`.
- GATE FORM: `TM_HARNESS_JOBS=3 sh scripts/heavy.sh --class browser l22b frontend/maquette/harness/run.sh
  --contracts --oracle <full rule paths>`; `--a11y` on every gate that draws (the light ledger may only fall, 98 now).
- ORACLE ACCEPT: the 8899 host does not outlive an invocation — accept INSIDE one:
  `heavy.sh … bash -c 'run.sh --oracle; python3 frontend/maquette/oracle.py --accept'`, then prove by script that
  only the named states moved, and bump `tests/scripts/test_oracle.py`'s state-count pin in the same commit.
- MUTATIONS: `sh scripts/mutate.sh <full path> "<expr>" frontend/maquette/harness/<rule>.py`; commit before; keep the
  EXPRESSION; « RULE CRASHED » proves something only when its message names the subject (RULINGS 1's reading).
- PUSH: `sh scripts/heavy.sh --class test l22b git push -u origin feat/maquette-l22b`, its own command from the
  worktree root; a refusal = STOP with its exact text.
- Traps inherited from L22a: `--accept` rewrites the WHOLE reference (name every changed state); a closed `#dlg`
  keeps the last dialog's box (B-554); a rule green on the wrong subject (B-555); a gate's named rules include every
  reader of a surface the phase moves; `outbox.py` falls under a full suite's load and passes alone (B-546's mode).
- New trap (17): `go()` commits through a view transition, and its commit closes any panel opened before it
  (`leavePanel`) — a named state that opens a screen AND a panel races; `acq-resolution-not-media` opens its choice
  alone over « À traiter » (its BACKDROP differs from the product's, said in its comment; R228 walks the product's
  path by finger).
- New trap (15a): the staging list is not read on the « À traiter » tab — a rule counting `__queue().stuck` there
  reads an empty list until a screen asks for it.

## LEDGER (append-only)

- 2026-09-27 phase 15 opened: re-measured ≈ 29 (ruling 16's four acts) → CUT 15a / 15b (steward accepted; 15b waits
  for Q1). 15a: R226 red (`15a-red.log`, 5 holds + markup guard), move, readers re-aimed out loud (R57 leave half,
  actions.py, two_picks.py t6 — the latter now moves the list by the queue's `resolve`: no finger act takes a dense
  staging folder out today); 15a ≈ 16 by its end (two readers found beyond the opening's re-runs, and the candidates
  screen's guidance sentence) — said here. Commits c19ed60d3 (feat), 2918d4d19 (oracle accepts acq-card-set-aside
  by name, pin 122 → 123). Gate `15a-gate.log` 32 rules + 26 guards 0 failed, oracle 0; `15a-a11y.log` 0 + light
  98/98; mutation `15a-mutation.log`: EXPRESSION removes staging.ts's `if (… === LEFT_AS_IT_IS) return { ok:
  setAside(asked) };` → R226 FAIL « and it is still set aside after both reads are asked again » (and four more).
  Vocabulary gained « aside » (the contract's own token).
- 2026-09-27 phase 16: re-measured ≈ 14; the « Annuler » calls the declared inverse (DESIGN § 3.4), dated line in
  the phase file. R228 red (`16-red.log`), move, STOP A → RULINGS 13 (42 states on shell/sheet-content only, the
  closed #sheet — B-554 extended), audit2's CancelledError repaired (a cancelled read opens nothing), producers.py
  grown by `not-media` out loud. Commits e14a2f15c (feat), 61b09ac99 (oracle, script proof in the body, pin 124).
  Gate `16-gate.log` 31 rules + 26 guards 0 failed, oracle 0; `16-a11y.log` 0 + light 98/98; mutation
  `16-mutation.log`: EXPRESSION replaces the verb's `await send("POST", path, { destination })` by `undefined` → R228
  FAIL « the reclassification is answered, and the message says the destination » (and « the card is in neither »).
  Vocabulary gained « reclassify ».
- 2026-09-27 phase 17: re-measured ≈ 10; the one real subject is « Les Zinzins de l'Espace » (dense « En vol »,
  TVDB-identified, no follow); states declared at the opening: acq-now-loaded, acq-card-rungs, acq-card-waiting.
  R229 red (`17-red.log`; its first draft read `[data-follow]` by presence, which made the markup guard treat
  `data-follow` as a boolean — re-read by VALUE). Commits c67a904e9 (feat), d612e9323 (oracle, 3 states, script
  proof). Mutations (`17-mutation-{1,2,3}.log`): arrivals create follows (staging.ts arrivalsOf pushes a follow) →
  FAIL « a tap changes the follows list by exactly one » (14 → 26: the follows cache re-reads only at the tap);
  `|| ids[SERIES_PROVIDER] == null` removed → FAIL « no film and no followed series carries it »; follows-tab rows
  given a requester → FAIL « « Suivis » draws no card born of an arrival ». The gate then caught phase 16's state
  measured mid-fade: fix 9f61747fd (the choice opened alone over « À traiter », BACKDROP ≠ product, steward
  accepted) + 658c9b96b (oracle accepts its screen-resolution/body by name; a second pass read no divergence).
  Final gate on 658c9b96b (`17-final.log`): 32 rules + 26 guards 0 failed, oracle 0; `17-final-a11y.log` 0 + light 98/98.
