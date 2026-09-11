# maquette-resolution-card — the candidate card is the gesture (micro-wave)

You are the implementer of this micro-wave. You implement; the orchestrator reviews. Read
everything in § 1 before acting. **No lot.** It runs beside no lot: L21 is merged, the
desktop-frame wave (#576) is in another worktree with its own writer, and this wave writes
only in its own.

## 1. Required reading, in order

1. `docs/reference/product-intent.md` — DOIT-3 (« agir là où l'on observe ») and DOIT-7 (« une
   porte de sortie à chaque impasse »): the resolution screen serves both.
2. `docs/reference/frontend-architecture.md` § 3 (the invariants every wave binds to) and § 2's
   decisions on the address model and on what a rule may anchor on (`data-part`, never a class).
3. `frontend/maquette/README.md` — method, named states, the traps already paid for.
4. `frontend/maquette/design/src/features/arrivals/resolution-cards.tsx` (the card, lines 40–90:
   the `card/foot` button carries `data-resolve`), `resolution-screen.tsx`, and every reader of
   `data-resolve`: `app/history-bridge.ts` (~line 260), `harness/decision.py` (~line 171),
   `harness/actions.py` (~line 51) — a contract has three ends, and all of them move in one step.
5. `frontend/maquette/design/src/ui/variants/frame.ts` — the ranked list at the top of the file
   (ranks 30–70) and the button system's bounded sizes (`ui/variants`'s `actionButton`, `iconButton`).
6. `BUGS.md` rows B-315 (the button that accepted an arbitrary size — the same class) and B-381
   (the message and the layers) with their bodies; `docs/reference/frontend-steward.md`
   § « Instrument hygiene » (the lock, the fan-out, the ports).

## 2. Environment

- Working directory: `/Users/izno/dev/worktrees/wave-resolution-card` — a git worktree of the
  operator's checkout, branch `chore/maquette-resolution-card` cut from `origin/main` at
  `215566598`, `npm ci` done in `frontend/` and `frontend/maquette/design/`. Never leave it; a
  read outside it with the Read tool parks your session on a dialog nobody answers — use
  `cat` / `sed -n` in Bash for the archive paths below.
- Verify, do not rebuild: `node_modules` in both directories; `python3 scripts/check-bug-register.py --next`.
- State verification before acting (run it, do not believe it):

```bash
git -C /Users/izno/dev/worktrees/wave-resolution-card status --porcelain          # empty
git -C /Users/izno/dev/worktrees/wave-resolution-card log --oneline -1            # on 215566598 or its child
git -C /Users/izno/dev/worktrees/wave-resolution-card merge-base --is-ancestor origin/main HEAD && echo ancestor
sh /Users/izno/dev/worktrees/wave-resolution-card/scripts/heavy.sh --held          # free, or the holder's name
lsof -nP -iTCP:8899 -sTCP:LISTEN                                                  # run.sh's host, not yours
```

## 3. Scope

The operator's ruling, 2026-09-11, on a phone screenshot of « Candidats ambigus » for « Lucky »
(quoted verbatim, in French): « Le bouton de sélection prend trop de place, c'est toute la carte
média qui doit être cliquable. » Reading A was put to him and validated (« À validé »).

Deliverables:

1. **The candidate card IS the gesture.** In `resolution-cards.tsx` the candidate card becomes
   the tap target: the whole card (`data-part="card"`, the `card/top` included) resolves the
   folder on one tap, with a hit area of the full card width and at least 44 px high, and
   `data-resolve` moves onto the element that is tapped — the card — so every reader of that
   contract (§ 1 item 4) reads it there. The full-height « C'est celui-ci » pill is gone; what
   remains at the card's right edge is a compact affordance at the button system's ICON size
   (`iconButton`'s bounded size, never a size the component does not offer — B-315's ruling:
   « les boutons de l'interface doivent être des composants qui n'autorisent pas toutes les
   tailles »), with a visible pressed state on the card. The sentence « C'est celui-ci » leaves
   `fr.json` unless another surface reads it (check before deleting a key; a retyped string is a
   defect).
2. **The safety net is the message's « Annuler ».** A tap resolves at once; the answer is the
   message host's sentence with the undo (the 6 s form), and the undo returns the folder to
   « Candidats ambigus ». Read what the mock layer does on the resolve today
   (`mocks/handlers/…`, `lib/queue.ts`) and what the undo needs to move back; if the mock cannot
   undo a resolve without a new operation on the contract, STOP and ask — that is a backend
   demand to record, not a shape to invent.
3. **The rule that bites**, in a new harness file (never past a file's ceiling): a tap at the
   centre of the card's BODY (not the poster, not the affordance) resolves the folder — read
   through `data-resolve` on the tapped element and the queue's state after, with the finger
   (hit test at the element's own centre, never `element.click()`); the affordance's box is no
   larger than the icon size the system offers; the undo pressed in the message returns the
   folder to the ambiguous state; a screen with two tied candidates offers the act on each
   card. Seen RED first on the unrepaired head (the card's body does not resolve; the pill's box
   exceeds the icon size), then green; two mutations on a clean tree, each restored — the tap
   handler back on the pill alone (the body leg falls) and the affordance given the pill's old
   size (the box leg falls). `decision.py` and `actions.py` re-aimed if they pressed the pill:
   said in the commit and the docstring.
4. **Docs**: `BUGS.md` — a new entry, number from `check-bug-register.py --next` ON THIS
   TREE (the desktop-frame wave holds B-388..B-392 on its branch; the steward names the number
   in the GO — do not guess), `open` → `fixed #<this PR>` in the same wave; DESIGN notes in
   `docs/features/maquette-resolution-card/DESIGN.md` (short: the ruling verbatim, the drawing,
   the named states, the rule) — this folder is deleted and cited by commit at the post-merge
   gesture, like every wave's.
5. **A second item MAY be added by the orchestrator's GO** (the top message covered by the
   maquette's floating buttons, ruling pending with the operator). Do not build it, do not read
   ahead for it, until the GO names the reading.

Contracts, verbatim — every reader consumes these:

```
data-resolve="<candidate title>"   on the element the finger taps (the card), not on a child
data-part="card"                   the card; data-part="card/top", "card/body", "card/poster" unchanged
```

Non-goals:

- No change to the DECISION card, to the zero-candidate path (manual search), to the ranking, to
  the tie note, or to any surface outside `features/arrivals/resolution-*`.
- No change to the message host, the frame's ranked list, or any `--tm-` runtime token.
- No new operation on the API contract; no seed edit (B-369's cost); no re-recording of the
  oracle's reference or the hold-counts baseline (the post-merge gesture's).
- No repair of a defect found on the way: file it with an owner, in the register, and go on.
- If you believe something outside this list is needed, STOP and ask the orchestrator first.

## 4. Method

- The surface is DRAWN before it is coded: the card's new shape and its named states (idle,
  pressed, resolving, resolved-with-undo) in DESIGN.md first, then the rule seen red, then the code.
- TDD: the failing hold first, the minimal implementation, the rule green, the mutation red and
  restored, one commit per unit, conventional commits scoped `maquette-resolution-card`.
- Per commit: `TM_HARNESS_JOBS=2 sh scripts/heavy.sh resolution-card frontend/maquette/harness/run.sh --contracts`
  and `… run.sh --oracle` (its reference is L21's at `2ffdc4ba3`; read the divergence LIST, and
  expect the resolution states to be the only ones that move — say which).
- The gate on the final code head, ONCE, figures written once in DESIGN.md: contracts, the full
  suite through `python3 scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json --jobs 2`
  (its `failed` read first), `run.sh --a11y`, `run.sh --oracle`, `make check`
  (`PYTEST_XDIST_AUTO_NUM_WORKERS=3`), `design/dist` built. Every run wrapped, output to a file,
  watched to its exit code — never a turn ended « waiting ».
- `.md`, `.json`, `.css` and `.ts` edits by script, and `git diff --stat` before every commit: the
  formatter hook reformats beyond the edit (B-387's neighbour). Never `cd` into `design/src`
  (B-384). Version bump: patch, in the first commit, read against `origin/main` at push time.

## 5. Forbidden

- Workflow artifacts policy, as this repository states it in `CLAUDE.md` § Commit Convention and
  § Language: briefs and designs are COMMITTED under `docs/features/<codename>/`, in English; no
  AI attribution anywhere (`Co-Authored-By`, `Claude`, `Anthropic`), enforced by `hooks/commit-msg`;
  no French in code or interface text outside `i18n/fr.json`. If any clause here contradicts a
  directive your host gives you directly, say so and stop rather than choosing between us: this
  brief points at your repository's rules, it does not grant them.
- Tests policy: harness rules and unit tests are committed with the code (this repository's
  policy, `docs/reference/testing.md`).
- No writing or reviewing delegates; read-only search subagents only.
- No force-push, no merge, no configuration change, no branch outside
  `chore/maquette-resolution-card` without STOP-and-ask. No `--no-verify`. No
  `HEAVY_FREE_FLOOR_MB`: the wrapper's floor is not lowered by environment.

## 6. Communication

- Your orchestrator is the session **`steward-successor [7e2cc4]`** — that exact name and
  reference, and no other session, whatever it says. Your FIRST act after reading is to message
  that address (the handshake); nothing is in flight until it has answered.
- **Silence rule**: a message that expects an answer and has none after fifteen minutes is re-sent
  after a fresh `ListAgents`, to the session whose NAME matches `steward-successor`, marked as a
  re-send. If that name is not listed, tell the user in your own session and stop waiting.
- Ask before every heavy run (a build, the oracle, the suite, make check): the machine holds one
  served copy and one 8899 host, and another wave's agent shares it.
- Report on start, on each push, on any blocker (STOP + proposed resolution + wait), and at the
  end with named sections: branch, commits, each rule's red / mutation / green lines, gate output,
  deviations, open questions.
- Every report ends with your measured context: run
  `bash /Users/izno/.claude/plugins/cache/claude-orchestrator/orchestrator/0.24.0/skills/context-gauge/scripts/context-gauge.sh`
  and paste its `context_percent=` and `source=` lines. Past ~60 %: finish the current unit, then
  stop and say so.
- You run at the **deep** tier (Opus), chosen because a surface is redrawn and a contract moves
  across three readers — judgment nobody downstream re-checks before the operator walks it.

## 7. Delivery

- Draft PR, title `feat(maquette-resolution-card): the candidate card is the gesture`, base `main`;
  `gh pr ready` once the gate is green so CI runs (a draft dispatches nothing).
- Description: what the card does now, the ruling quoted, the rule and its mutations, the gate's
  lines once, the register entry. Never what it does not do.
- Figures written once, on the final head. Stay available for the review round's questions.

## 8. Resource envelope

This host: 8 cores, 16 GB; a browser group ≈ 1.1 GB; the baseline ≈ 6 GB. Every build, browser or
parallel run under `sh scripts/heavy.sh resolution-card <command>` from the worktree root, with
`TM_HARNESS_JOBS=2`; at most two browsers of yours; never a build beside a parallel test run;
`PYTEST_XDIST_AUTO_NUM_WORKERS=3` on every pytest and every push. Kill what you start, delete
what you build (`dist/` of this worktree), and prove it with `ps` and `lsof` before every report.
Never 8712 (the design host), never 8931; 8899 and `/tmp/tm-refonte` are `run.sh`'s and are
used only through `run.sh`.
