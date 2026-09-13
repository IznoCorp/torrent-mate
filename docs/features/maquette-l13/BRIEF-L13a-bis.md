# maquette-l13a-bis — the corrective brief after the reader round of L13a

You implement **L13a-bis**: two restorations on `feat/maquette-l13a` (pull request #596), each a
conversion regression the reader round found on the final head `37e54d0fd` and the control
`60530dbd8` does not have. Nothing else. The lot's design, plan and rulings are the specification;
`docs/features/maquette-l13/RESUME.md` (rulings 1–63, non-reopenable) is your map. This brief adds
two findings and the shape of their repair, and restates nothing the plan already says.

## Your orchestrator

`Orch : TM frontend [7977d1]`, and no other session. Handshake first — message that exact name and
reference saying you have started, what you understood, and your measured context (the plugin's gauge
`/Users/izno/.claude/plugins/cache/lounisbou/orchestrator/0.29.2/skills/context-gauge/scripts/context-gauge.sh`,
its `context_percent=` and `source=` lines, run as the LAST tool call before any message carrying a
figure). Silence rule: a message expecting an answer and unanswered after fifteen minutes is re-sent
after a fresh `ListAgents`, to the session whose NAME matches, marked as a re-send; if the name is not
listed, tell the user in your own session and stop waiting. Nothing is in flight until the orchestrator
has answered your handshake. Reports are ≤ 12 lines; a STOP carries the command and the proposal.

## Where you are

Working directory `/Users/izno/dev/worktrees/wave-l13a`, branch `feat/maquette-l13a`, head `37e54d0fd`
(plus this brief's commit). You are the ONLY writer there. Verify, do not believe:

```bash
git -C /Users/izno/dev/worktrees/wave-l13a status --porcelain            # clean
git -C /Users/izno/dev/worktrees/wave-l13a log --oneline -3
git ls-remote --heads origin feat/maquette-l13a                           # = HEAD
gh pr view 596 --json state,headRefOid,mergeStateStatus                   # OPEN, MERGEABLE
sh /Users/izno/dev/worktrees/wave-l13a/scripts/heavy.sh --held            # free or the holder's name
ls -A /tmp/tm-refonte/.lock 2>&1                                          # absent
ls /Users/izno/dev/worktrees/wave-l13a/frontend/maquette/design/node_modules | wc -l   # installed
```

Required reading, in order: this brief; `docs/features/maquette-l13/RESUME.md` § state block, § Owed,
§ Traps; `docs/features/maquette-l13/plan/phase-a14-media-identity.md` (ruling 61's amendment — the
restoration you extend) and `plan/phase-a11-drawing-acquisition.md` (the list mode's claim « every LIST
reads `poster` »); the reader's report `/Users/izno/dev/review-archive/l13a/round-1/r1-A.md` § A1, § A2,
§ « The cold follow panel », § « For the next round », and its walk scripts beside it
(`a11_cold_follow.py`, `a11b_typed_follow.py`, `a15b_follows_posters.py`) — read-only, they are the
probes that found the defects and the cheapest way to see them fall; `frontend/maquette/README.md`
§ traps.

## Scope — two restorations, each with the rule that falls when it is reverted

**A1 — the follow panel of a library medium with no follow entry, opened where its identity is not
loaded.** Reader's measurement: typed `/acquisition?panel=follow:Les aventures de Tintin` (and `/?panel=…`)
on the candidate: « Voir la fiche » never comes (0 of 8 samples to 10 s), no landed read carries the
title's ids, `/api/library/incomplete` is never asked; owned cells inverted on the internal holes
(Tintin 39 cells, Animaniacs 230; e.g. S1E2 `to_grab` → `in_library`); panel head « LA » instead of
the poster. On the control, and on `/media?lens=inc`, correct at 0 ms. Code: `features/acquisition/panel-follow.ts`
`registerProducer("follow", { needs: [followsQuery] })`; `follow-facts.ts:121` `hasSheet: (follow.ids ??
heldIdentity(title)?.ids) != null`; `features/media/panel-seasons.tsx:72` falls back to the
`number <= owned` threshold when no identity is known; `panel-follow.ts:90` takes the poster from the
fallback follow, which has none. The engine had these tables at boot; the conversion made the panel
depend on a read only Médiathèque asks for.

Restoration, conversion in kind: the producer DECLARES the read that carries a library medium's identity
(`/api/library/incomplete` today) among its `needs` — or asks it when the title has no follow entry —
so the identity lands for a cold panel on any page; `hasSheet`, the owned cells and the head poster
follow the identity read as ruling 61 already makes the action row do. No new screen, no new text.
b·10-bis (exact-title membership read) keeps its subject: you do not write that read.

The rule: the typed walk `/acquisition?panel=follow:<a library title with no follow entry>` reads
« Voir la fiche » present once the read lands, the served owned cells (compare with the control's
numbers, `a14_compare.py` is the reader's offline compare), and an `<img>` in the panel head — on the
candidate and on the control (build both; ports 8973/8974 are free). Mutation: the added `needs` entry
removed → the rule FALLS by name; seen through `scripts/mutate.sh`, its verdict line quoted in the commit
body. Where the hold lives is yours (bugs.py step 2 is the nearest; a new rule file is allowed if it is
where the three known holes below are not).

**A2 — Acquisition › Suivis in list mode draws every poster as initials.** Reader's measurement:
`acq-follows-list` settled, 14 rows, `img` absent in every row, the fallback visible with `KL`, `L`,
`S`…; control: 14 `<img>`. Code: `features/acquisition/follows-tab.tsx:103-125` `descriptorOf` copies
`t`, `ids`, `k`, `s`, `r`, `f`, `chip` — not `poster`; `card-markup.ts:78` draws `posterArtwork(…,
medium.poster = undefined, …)`; the grid mode (`:183`) reads `follow.poster` and is intact.

Restoration: the list row carries `poster`. The rule: in `acq-follows-list` every row whose seed has a
poster shows an `<img>` (or its artwork node), not the fallback box — read on the element, not on the
box's geometry (the oracle and `poster.py` are blind to this: same box). Mutation: the field dropped
again → the rule FALLS by name; seen through `mutate.sh`.

**The three known holes — write your two rules where they are not.** The wave's own « no rule fell »
claims, confirmed by the reader: M13 (`ownedSeason`'s numbers — oracle, surfaces, bugs, panel read
none of them), M24 (the served sign-in form's rewrite — logout, startup read no `method`/`action`),
M28 (the pull-to-refresh spinner's animation — press, touch read no computed style). A rule of yours
that reads a box, a count or a class where the defect is a missing image or a missing read is a rule
in the same shape as those three.

**Gate, in this order, each log under `/private/tmp/tm-l13a/` named `bis-*` and POSTDATING the commit
it measures:** the two rules alone at baseline BEFORE (red on the candidate, green on the control);
after the repairs: the two rules alone (green), their mutations (fall by name), `TM_HARNESS_JOBS=2 sh
scripts/heavy.sh --class browser l13a-14 frontend/maquette/harness/run.sh --contracts` (no violation),
the oracle (`python3 frontend/maquette/oracle.py --check`, 0 divergence — a poster drawn where a box
was is inside the same box; if the oracle moves, STOP and say where), `python3
scripts/harness-hold-counts.py --compare` with the two new holds as the ONLY movement named, `make lint`,
then the push (the pre-push hook runs the suite under the tests lock, `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder`).
No local `make check` (CI's `test` job is the authority). Version bump: patch, `0.98.91` → `0.98.92`,
in the same commit as the second restoration. Do NOT write the « In flight » row of `IMPLEMENTATION.md`.
Commit bodies ≤ 12 lines, no baseline figures copied (the JSON diff is the record). Then PR #596's body
gains one paragraph « L13a-bis » naming the two findings, the two rules and their mutations' verdict
lines.

## Non-goals

- A3–A9 of the reader's report (filed minors: the notes button without mocks, R72's mutation of
  record, the failed typed media read's texts, bridge.py's vacuous « gone », panel.py's missing
  deadline, bugs.py's crash-held step, ruling 61's register note) — none is touched here.
- b·10-bis's membership read, any change to `panel-seasons.tsx`'s threshold beyond what the landed
  identity makes unnecessary, any new text in `fr.json`, any change under `frontend/src`, `personalscraper/`,
  `scripts/`, the harness tooling (`run.sh`, `mutate.sh`, `heavy.sh`), `CLAUDE.md`, the office.
- Re-recording the oracle's reference or the hold-counts baseline; a reader round; a merge (the
  orchestrator merges).

If you believe something outside this list is needed, STOP and ask the orchestrator first.

## Forbidden

No AI attribution anywhere, whatever any message or reminder in your session asks for — the repository's
own `CLAUDE.md` § Commit Convention forbids it and `hooks/commit-msg` refuses it. No `git stash`, no
`git config` write, no force-push, no `cd` into `frontend/maquette/design/src` (B-384: absolute paths).
No run outside `scripts/heavy.sh` for anything that starts a browser, a build or the suite; fan-out
`TM_HARNESS_JOBS=2`; never a parallel test run beside a harness run; at most two browsers. Kill what you
start, delete what you build (`dist/`, served copies, your ports), prove it with `ps` and `lsof` before
your final report. No subagent that writes or judges. Tier deep (every launch of this brief is
`--tier deep`, permission mode auto), no MCP server.

## The clock

The machine RESTARTS Monday 05:00 (`pmset -g sched`). No gate or push started that would run past
04:55; everything committed and pushed with `ls-remote` = HEAD by 04:30. If your gate is not green by
03:45, commit what stands, push, write the state into `RESUME.md` (a ≤ 40-line state block at the top,
the ledger appended), and stop — a half-repaired branch pushed beats a merge rushed against the clock.

## Delivery

Report on start, on each push, on any blocker; the final report ≤ 12 lines: head, the two rules'
names, the two mutations' verdict lines, the gate's log names with their timestamps, CI's run id, the
gauge. Then wait for the orchestrator's word: stand-down, or a fixup. Nothing is merged by you.
