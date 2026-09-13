# maquette-scroll-jump — the in-flight list throws the reader back to the top

A repair micro-wave of the maquette (the NEXT version of the web UI, `frontend/maquette/design`). Its subject is ONE
defect the operator met on his Mac on 2026-09-12, reported in his words:

> Bug majeur : double scroll systématique sur Acquisition › En cours ; dès que le scroll arrive au niveau de Lucky on
> remonte automatiquement en haut de la page.

Two facts in that sentence, and they are measured separately: a DOUBLE scroll (two scroll containers moving under one
gesture), and a JUMP to the top when the scroll offset reaches the card of « Lucky » — the one in-flight card whose scrape
stop is red and which carries « Résoudre → » (seed `mocks/seeds/blocked.json`, `pending-decisions.json`). Whether the two
facts are one mechanism or two is the first thing this wave establishes; a repair that guesses the mechanism is refused.

Tier: deep (the map binds every tier to opus). No MCP server: the harness drives its own Playwright.

## Required reading, in order

1. `docs/reference/product-intent.md` § 12 (mobile) and the DOIT / NE-DOIT-PAS list — a reader who loses their place is
   the defect the constitution names first.
2. `docs/reference/frontend-architecture.md` § 1 (the semantic scroll index and « programmatic scrolling must have one
   path »), § 3 invariants, § 5 instruments' debts.
3. `frontend/maquette/README.md` — how the prototype runs, the named states, the harness, the traps already paid.
4. `frontend/maquette/design/src/app/scroll-restoration.ts` (the one path for history-driven scrolling; its header says the
   « one path » clause is NOT paid: `app/focus.ts` writes `#port.scrollTop = 0` from the skip link, `ui/sheet.tsx` resets a
   panel's offset), `app/focus.ts` (:250-259 the skip-link handler), `ui/virtual-rows.tsx` (:305 focus with preventScroll),
   `ui/variants/layout.ts` (:61 the `port` scroll container), `ui/variants/frame.ts` (:282 a second `overflow-y-auto`
   container — read which surface it draws), `features/acquisition/now-tab.tsx`, `features/acquisition/live.ts` (the TICK:
   what a server event refreshes on acquisition — a list re-mounted on a tick collapses its height for a frame and the
   port clamps to 0), `index.html` (:116-130 the desktop switch of B-344, `:root:has(#desktop-switch:checked)`: on a Mac
   the operator may read the maquette in the DESKTOP frame, where the document and the port can both scroll).
5. `BUGS.md` entries B-140 (the three clauses of the scroll index), B-307 (`virtual.py`, the scroll-restoration hold that
   falls under load — five instances), B-344 (the desktop frame), and the memory of the project on virtual windows:
   « estimateSize outside the memo key → blank list; restore an INDEX, not a pixel; focus() scrolls — preventScroll ».

## Environment

- Working directory: `/Users/izno/dev/worktrees/wave-scroll-jump`, branch `fix/maquette-scroll-jump` cut from
  `origin/main` at `a2721935f` (version 0.98.86). You are the ONLY writer there. Never `cd` into `design/src` (B-384's
  cause; absolute paths from the repository root).
- Verify the state before acting: `git status`, `git log --oneline -3`, `git ls-remote origin fix/maquette-scroll-jump`,
  `python3 scripts/check-bug-register.py --next`, `sh scripts/heavy.sh --held`.
- Install what the gates need, under the TESTS lock: `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder sh scripts/heavy.sh
  --class test scroll-jump npm ci` in `frontend/` and in `frontend/maquette/design/`.
- The design host `tm-design` (pm2 `torrentmate-design`, serve.py on 8712) serves the MAIN checkout's `design/dist` — it
  is where the operator read the defect. You do not point it at your worktree without the steward's word.

## Scope — deliverables, in order

1. **Reproduce and NAME the mechanism, before any edit.** A Playwright probe on a PRIVATE bench (build into your worktree's
   `design/dist`, publish to a directory under your scratchpad, serve it on a port of yours — 8902 — exactly as the
   mock-layer wave's bench does; never `/tmp/tm-refonte`, never 8899, never 8712), at TWO widths: the phone frame (390 px,
   the harness's) and a desktop viewport (1440 × 900 with the desktop switch checked, B-344's frame). Open Acquisition ›
   En cours (the named state the README lists for that tab), scroll the port in steps of 40 px with a settle after each,
   and record per step: `#port.scrollTop`, `document.scrollingElement.scrollTop`, the scrollTop of every other element
   whose `scrollHeight > clientHeight`, the element at the viewport's centre, `document.activeElement`, and any change of
   `#port.scrollHeight`. Also subscribe to `scroll` events on `#port`, `document` and `window` and log their targets with
   a timestamp. The probe's output names: WHICH containers scroll under one wheel/touch gesture (the double scroll), and
   at WHICH step and by WHAT the offset returns to 0 (a `scrollTop = 0` write — break on it with a setter trap on the
   element; a height collapse — `scrollHeight` dropping under the offset; a focus move — `activeElement` changing; a
   history-driven restore — `scroll-restoration.ts`'s path). Write the mechanism in DESIGN.md § 1 with the probe's lines.
   If Lucky is NOT special (the jump happens at an offset, whatever card sits there), say so: the operator's sentence is
   a reading, not a diagnosis.
2. **File the entry**: `B-490` in BUGS.md, body = the operator's sentence, the two widths' readings, the mechanism. Your
   register block is **B-490..B-494**; nothing else uses it tonight.
   (The block moved from B-478..B-482 on the orchestrator's correction: the mock-layer wave reserves B-470..B-489.)
3. **Repair at the mechanism**, on the surface that owns it, honouring D5 (the engine only shrinks) and the « one path »
   clause of § 1: if the cause is a programmatic scroll outside `scroll-restoration.ts`, the repair routes it through
   that one path or removes it; if it is a height collapse on the live tick, the list keeps its height across the
   refresh (a keyed list that does not re-mount, or a min-height held while the data is in flight); if it is the desktop
   frame letting the document scroll, the frame's own stylesheet (`styles/harness.css`, B-344's) confines the scroll to
   the port. Any repair that moves a frame rank, the engine's `legacy.js`, or a validated drawing is a STOP-and-ask.
4. **The rule**: a new harness rule `harness/scroll_keeps_place.py` (R174 or the next free — read `hold-counts-baseline.json`
   and `harness/` for the highest) whose holds scroll the in-flight list by finger and by wheel at both widths, past
   Lucky's card and to the end, and read that `#port.scrollTop` never decreases without a gesture and that exactly ONE
   container moves per gesture. Seen RED on the unrepaired tree first (write its count), GREEN after, and ONE mutation
   that reverts the repair and makes it fall on the right hold (write the count). Add it to the full suite like every
   rule; the contracts tier only if it reads a NAME.
5. **The gate**, on the final head: `run.sh --contracts`; the full suite once; `--a11y`; the oracle (zero divergence —
   this wave draws nothing new; a divergence is a STOP); `harness-hold-counts.py --compare --jobs 2` (`failed` read FIRST;
   « new since baseline » for your rule is expected and re-recorded by the post-merge gesture); `make check` under the
   tests lock at 2 workers. Figures written ONCE in DESIGN.md § 6 on the final head.
6. **Delivery**: merge `origin/main` (re-read the version — main is 0.98.86; settings and mock-layer land 0.98.87/88 tonight;
   bump above what you find), push under the tests lock, PR opened READY (never draft-then-ready in one breath), register
   row `fixed #<PR>`, report.

## Non-goals

- No redraw of Acquisition › En cours, of Lucky's card, of the pipeline stages or of « Résoudre → » (B-474 is filed on the
  panel's resolve and is not yours).
- No change to the desktop switch's shape (B-344, the operator's preference) beyond confining the scroll if that is the cause.
- No re-recording of the oracle reference or the hold-counts baseline (the post-merge gesture's).
- No edit under `docs/production/`, `personalscraper/`, or `frontend/src` (the archived app).
- No second defect: if the probe meets another one, FILE it (B-479+) and go on.
- If you believe something outside this list is needed, STOP and ask the orchestrator first.

## Method

TDD: the probe and the rule before the repair; the rule red first; incremental conventional commits (`fix(maquette-scroll-jump): …`,
`test(maquette-scroll-jump): …`, `docs(maquette-scroll-jump): …`); Google-style docstrings; English only in code and
docs, UI strings only in `i18n/fr.json`; names written out in full; exit codes read, never a guard's last line — a wave
lost a red guard tonight by reading prose. `frontend/maquette/README.md` and `docs/reference/testing.md` say where a rule
lives and how the harness runs it.

## Forbidden

No `--no-verify` on a code push; no `git stash`; no edit of another worktree; no process left running (kill what you
start, delete what you build — `design/dist`, your bench's copy — and prove it with `ps` and `ls` before reporting); no
AI attribution or workflow vocabulary in commits or PR text (`hooks/commit-msg` refuses it; CLAUDE.md § Commit Convention);
no reviewer or implementer subagent — read-only search subagents only; no `cd` into `design/src`.

## Resource envelope — the machine is shared tonight

Host 8 cores / 16 GB, two other waves gating, the kernel killed three runs at ~1.3 GB free this evening. SHARED mutex
`sh scripts/heavy.sh --class browser scroll-jump <cmd>` for anything that reads `/tmp/tm-refonte` or 8899 (`run.sh` any
tier, the oracle, hold-counts) — announce each run to the orchestrator one line before and one after; the mutex serialises
you behind the mock-layer and settings waves. TESTS lock `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder sh scripts/heavy.sh
--class test scroll-jump <cmd>` for `npm ci`, builds, `make check`, `pytest`, `git push` (the pre-push hook runs the suite).
`TM_HARNESS_JOBS=2`, `PYTEST_XDIST_AUTO_NUM_WORKERS=2`. Your private bench (one browser) runs outside the mutex but never
beside a run of yours under it; at most ONE browser of yours at a time outside the mutex. Under a named class the
environment may only raise the floor and lower the load ceiling; say which class you used.

## Communication protocol

Your orchestrator is **`Orch : TM frontend [8e18d6]`** — that exact name and reference, read from `ListAgents`, in every
`SendMessage`. First act after reading: the handshake (your name and reference, the head you read, your plan in five
lines, your measured gauge). Nothing is in flight until the orchestrator answers. Silence rule: a message expecting an
answer with none after fifteen minutes is re-sent once after a fresh `ListAgents`, marked as a re-send; if the name is not
listed, tell your user in your own session and stop waiting. Report at: the reproduction (the mechanism, the probe's
lines), the red rule, the repair commit, each shared-lock run start and end, the push (PR number, CI run id). Every report
carries `context_percent` measured by
`~/.claude/plugins/cache/lounisbou/orchestrator/0.28.3/skills/context-gauge/scripts/context-gauge.sh` — never estimated.
At 60 % you push what is committed, write `docs/features/maquette-scroll-jump/RESUME.md` (the head, what is done with the
rule that reads it, what is left in order, the envelope, the traps) and stand down. Do not stop between steps to report one
done; stop only at a STOP-and-ask or at a gate you cannot repair inside your scope.

## Delivery

PR title: `fix(maquette-scroll-jump): the in-flight list keeps the reader's place`. Body: what it does (the mechanism
named, the repair, the rule and its red/green/mutation counts, the two widths' readings, the gate's figures once), a
`Related PR:` section only if a dependent PR exists. The wave's folder is deleted and cited by commit at the post-merge
gesture, not by you.
