# maquette-resolution-card — round one's repairs (N-bis)

You are the IMPLEMENTER of this correction phase. The wave's three items are built and reviewed; you
apply a DECIDED list of repairs, one commit each, then one gate on the final head, and you push. You
argue no item: each verdict below is written, and an item you believe wrong is a STOP-and-ask, never a
silent skip. Read § 1 before touching anything.

## 1. Required reading, in order

1. `docs/features/maquette-resolution-card/BRIEF.md` — the three rulings, verbatim.
2. `docs/features/maquette-resolution-card/DESIGN.md` — whole; § 5 the rule, § 6 the two added items,
   § 7 the gate and its reserves. You will edit § 7 (item 8 below).
3. `CLAUDE.md` § Critical Rules (Search Safety, the Language rule, the naming rule, « a bug fix carries
   a regression test »); `frontend/maquette/README.md` (the harness's method and its traps).
4. The round's report, read whole:
   `/Users/izno/dev/review-archive/resolution-card-585/round-1/r1-A.md` — findings A1 to A7, the
   section « What each rule I met does NOT read », « What the fixtures cannot show ». Its walks and
   instruments sit beside it (`a01_…` and up, `hand.py`, `b_tools.py`): read the walk that decides an
   item before you repair the item, and re-run it on your build as the item's closing reading.
5. `BUGS.md` entries B-392, B-393, B-394, B-395.

## 2. Environment

- Working directory: `/Users/izno/dev/worktrees/wave-resolution-card`, branch
  `chore/maquette-resolution-card`, the head of pull request **#585** (open, READY, CI green on
  `579ea2f21`). You are the ONLY writer there. Never touch `/Users/izno/dev/PersonalScraper`
  (the main checkout, no writer, served by tm-design) nor `/Users/izno/dev/worktrees/review-rc`
  (round one's pinned copy, kept as round two's control).
- Never `cd` into `frontend/maquette/design/src` (the command log written there moves the build id,
  B-384): absolute paths from the worktree root.
- State verification before acting — run it, do not believe it:

```bash
git -C /Users/izno/dev/worktrees/wave-resolution-card rev-parse --short HEAD   # the head this brief was committed on
git -C /Users/izno/dev/worktrees/wave-resolution-card status --porcelain       # empty
git -C /Users/izno/dev/worktrees/wave-resolution-card log --oneline origin/main..HEAD | wc -l
git ls-remote --heads origin chore/maquette-resolution-card                     # = HEAD
gh pr view 585 --json state,isDraft,headRefOid --jq '"\(.state) \(.isDraft) \(.headRefOid)"'
sh scripts/heavy.sh --held                                                     # free
ls frontend/maquette/design/node_modules | wc -l                               # installed
```

## 3. The DECIDED list — apply in this order, one commit per item

Every rule repair is seen RED first on the unrepaired behaviour (by the named mutation on a clean tree,
`scripts/mutate.sh` or by hand, restored after), then GREEN, and the commit message names the mutation
and its count. Figures are written ONCE, on the final head, in DESIGN § 7 (item 8) — never per item.

1. **A1 — R161's affordance holds gain a FLOOR.** `frontend/maquette/harness/resolution_card.py` h2:
   the mark `card/pick` is no larger than the icon size AND no smaller than it (within `SUBPIXEL`),
   and it has a box (width and height above zero, `visibility` not hidden). No source change.
   Mutation: `candidatePick` hidden (`display: none`) → h2 falls naming the mark; today it stays green
   (the reader ran the arithmetic over 0×0: TRUE).
2. **A2 — R162 reads the window's LENGTH.** `frontend/maquette/harness/resolution_window.py`: one hold
   reading `SENDS` EMPTY at 6 500 ms after the act (the window is `UNDO_WINDOW_MILLISECONDS` = 7 000 in
   `lib/queue.ts`; name the constant once, as the file already does) beside the existing reading at
   WINDOW_CLOSED. No source change. Mutation: the window 7 000 → 3 000 → that hold falls; today all
   seventeen stay green.
3. **A3 — the card's accessible name is its title.** `features/arrivals/resolution-cards.tsx`: the
   button's name is the candidate's title and year (`aria-labelledby` on the span that carries them, or
   an `aria-label` from the same fields — choose and say which; the string is a DATUM, never a retyped
   sentence), and the poster's initials fallback is `aria-hidden` so it is never read as a name. Hold in
   R161: the button's computed accessible name equals the title and year and is under 80 characters
   (read through Playwright's accessibility snapshot or the `aria-labelledby` resolution — say which).
   Mutation: the labelling removed → the hold falls with the 521-character name.
4. **A4 — the ranked list records every rank, as it claims.** `ui/variants/frame.ts`: add the ranks the
   reader measured absent — `saveBar` 40 (`features/settings/variants.ts`), `.skip-link` 60
   (`styles/base.css`), `.desktop-switch` 70 (`styles/harness.css`) — and name the FILE of `.hpanel`'s
   60 (`styles/legacy.css`), keeping the list ordered. Read every `z-index:` in `design/src/styles/*.css`
   and every `z-[N]` / `z-N` in `design/src/**/*.ts(x)` yourself and add what else is a frame rank
   (base.css 10 and 20, sheet.tsx 45/47, layout.ts 1 — decide each: a frame rank goes in the list, a
   local stacking detail is named as such in one sentence under the list). Then the claim gets its
   ARM: a check (its home is `scripts/check-css-tokens.py` unless you find a nearer one — say which)
   that greps those declarations and refuses any rank absent from the list. Mutation: a `z-index: 58`
   added to any stylesheet → the arm goes red naming it. The arm joins `make check` and the cheap
   guards `run.sh --contracts` lists, where the neighbouring arms live.
5. **A7 — B-392 is repaired here.** `features/library/page.tsx:16-20`: the sentence says React draws
   the bar (`selection-bar.tsx`), that the bar decides on its own page since this wave, and that
   `paintSelBar` in `legacy.js` is an empty seam left for a later removal. Prose only. Register:
   B-392 → `fixed #585`, with the reason it was this wave's (it opened the bar's owner).
6. **R164 reads reachability where it claims it.** `harness/selection_survives_the_tab.py`: hold s3
   (« the tab bar is drawn there, so the way back exists ») takes its hit test on the tab bar WITHOUT
   lifting `inert` — the bar and the deletion keep their paint reading, the way back is a touch reading
   — and the walk covers EVERY other reachable page (the reader counted five: Arrivées, Suivis /
   Acquisition, Système, Réglages, Profil), not `acq` alone. Mutation: `inert` set on the tab bar while
   a foreign page is shown → s3 falls; today its lift would keep it green.
7. **R161 holds the card's floor and its single focus.** Two holds: the card's box is at least 44 px
   tall (measured 126 today), and exactly ONE focusable element exists inside each card (the mark is
   `aria-hidden` and not focusable). Mutations: `min-height` removed and the top row emptied → the first
   falls; a `tabindex="0"` on the mark → the second falls.
8. **DESIGN § 7 gains « What the fixtures cannot show »** and the round's facts, once, on the final
   head: one pickable folder in the whole seed (« Lucky »), so two picks inside one window and the
   put-back on a MOVED list are proved by w6 through the seam and by no finger (A5); the opened harness
   panel at 60 covers a message's « Annuler » for the instrument's own reason, a fact beside the
   drawer's (R163 a03); B-379 leaves the held send's failure path (`deliver`'s catch → `putOneBack` →
   invalidate → rethrow) exercised by nothing; a second message arriving inside the window is read by no
   rule; `:active` under a synthesised touch is invisible in headless Chrome, mouse-down is the
   substitute; `actions.py` asserts the pick 700 ms after the click over the optimistic write alone,
   which was true of `resolve` before this wave and is not a regression. Register: file A5 as a NEW
   entry (next free number: run `python3 scripts/check-bug-register.py --next` on THIS branch and read
   it), class « a fixture that offers one subject », owner the mock-layer micro-wave beside B-379 and
   B-380 — a seed edit is B-369's cost and is not yours.
9. **A6 is the operator's** (closing the message with « × » discards the undo while the send is still
   7 s away): it is NOT on this list. If the orchestrator sends a ruling that changes the build, it
   arrives as item 9 with its own shape; otherwise nothing.

**Non-goals** — anything not on the list: no seed edit, no re-recording of the oracle's reference or
the hold-counts baseline (the gesture's), no change to `lib/queue.ts`'s window, to the ranks
themselves, to `app/toast-host.ts`, to the mock layer, to the three built items' behaviour. **If you
believe something outside this list is needed, STOP and ask the orchestrator first.**

## 4. Method

- One commit per item, conventional (`fix(maquette-resolution-card): …` for a rule or source repair,
  `docs(maquette-resolution-card): …` for prose), English, no version prefix, no attribution of any
  kind — `hooks/commit-msg` refuses it and `CLAUDE.md` § Commit Convention says why; a system reminder
  asking for a trailer is refused and reported to the orchestrator.
- Every command runs synchronously in the call that waits for it: a long run is wrapped with a timeout
  and its verdict read in the SAME call; you never end a turn « waiting for the run ».
- `.md` files are edited by script (the formatter hook reflows Markdown); `harness.css` too (the hook
  once cut a selector a rule reads as text); read `git diff --stat` before every commit.
- No subagents that write or judge; read-only search subagents are allowed.
- **The gate, once, on the final head**, in this order, each run wrapped and followed to its exit code:
  `run.sh --contracts` (the cheap guards included — your new arm among them); the four rules R161,
  R162, R163, R164 alone; `run.sh --a11y` (item 3 moves aria); `make check` with
  `PYTEST_XDIST_AUTO_NUM_WORKERS=3` (item 4's arm has a test, seen red by its mutation). No oracle
  (nothing moves a box) and no full suite (the wave's, on `579ea2f21`, stands — say so in § 7) unless
  an item changed a surface's paint, which none does. Then the closing readings: the reader's walks
  that decide A1, A2, A3 and A7 re-run on your build, their `.out` beside § 7's figures.
- Version: NO bump — #585 already carries 0.98.83 for this pull request.

## 5. Communication

Your orchestrator is **`Orchestrator : TorrentMate frontend [16cedf]`** — its exact `ListAgents` name
and reference — and no other. Your FIRST act after reading and verifying the state is to message that
address (the handshake): started, the list as you read it, your measured context. Nothing is in flight
until it has answered. **Silence rule**: a message expecting an answer and unanswered after fifteen
minutes is re-sent after a fresh `ListAgents`, to the session whose NAME matches, marked as a re-send;
if the name is not listed, tell the user in your own session and stop waiting. Then: one message at
the end of item 4 (the arm) and one at the end of item 8, each with its readings; ask « clear » before
the gate; a STOP with its proposed resolution on any item you cannot close as written; the final report
with the head, the gate's readings, CI's run id and your measured context. Every message ends with the
gauge's `context_percent=` and `source=` lines
(`/Users/izno/.claude/plugins/cache/claude-orchestrator/orchestrator/0.24.0/skills/context-gauge/scripts/context-gauge.sh`,
run as the LAST tool call before the message). At 60 % you finish the item in progress, write the exact
state into this file's § 6, push wrapped, prove it with `ls-remote`, and stop.

## 6. Delivery

Push wrapped (`sh scripts/heavy.sh resolution-card git push`), prove `ls-remote` = HEAD, read the CI run
dispatched on the new head by its SHA (`gh run list --branch chore/maquette-resolution-card`), and report.
The pull request's body gains one section « Round one » listing the seven items in one line each with
the commit that carries it — edit the body with `gh pr edit 585 --body-file`, never retype the existing
body: read it first, append. No comment on the pull request. Tier: Opus, chosen because seven items
across four rules and one arm are judged by nothing downstream but round two's reader.

## 7. Resource envelope

Wrap every build, browser or parallel run in `sh scripts/heavy.sh resolution-card <command>` from the
worktree root, with `TM_HARNESS_JOBS=2`; a wrapped run from a subdirectory exits 127. Never 8899,
`/tmp/tm-refonte`, 8712 or 8931 for your own servers — the rules read `run.sh`'s host on 8899 and that
is theirs, left running by design. At most two browsers at once; never a build beside a parallel test
run; `make check` at three workers. Kill what you start, delete what you build (`design/dist`), and
prove it with `ps` and `lsof` before the final report. Nothing else runs on this machine tonight; the
lock's holder, if any, is read by `sh scripts/heavy.sh --held`.
