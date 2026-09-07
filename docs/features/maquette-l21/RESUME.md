# L21 — where the wave stands, for whoever picks it up

Rewritten at the quota pause by the session that landed phase 7, the close, and the two repairs the
gate uncovered. Read `BRIEF.md`, `DESIGN.md` and `plan/INDEX.md` first — this file says only what is
TRUE NOW and what the plan does not.

**Branch** `feat/maquette-l21`, pull request **#572** (draft). **Version** 0.98.75 — re-read `main`
and bump again at the close if it has moved.

**HEAD is the sha the last commit of this file carries, and it IS pushed** — proven by
`git ls-remote --heads origin feat/maquette-l21` against the local sha, never by a push's own
output.

⚠ **`origin/main` at `163cbfcbb` IS MERGED, and the proof is a COMMAND, not a merge commit.**
`git merge-base --is-ancestor origin/main HEAD` succeeds; `git log --oneline HEAD..origin/main` is
empty. **There are TWO merge commits on this branch** — `27a2ef6a9` brought `ae1b8de48`, and
`e6fbdb7c4` brought `163cbfcbb` — so reading the first one's second parent says the branch is three
pull requests behind, which is false. That reading was made, an order to re-merge followed it, and
it was withdrawn on these four readings. **« Merged » is proven by `--is-ancestor` on the branch's
HEAD; never by one merge commit's parent, and never on a shared checkout another session has a
commit checked out in.**

---

## 1. Done, with the reading that proves it

| Phase                               | State          | Proof                                         |
| ----------------------------------- | -------------- | --------------------------------------------- |
| 1 — the contract                    | **DONE**       | 3 operations + types + register               |
| 2 — the season grab (B-301)         | **DONE**       | R125, 16 holds · `fixed #572`                 |
| 3 — the journey's two verbs (B-302) | **DONE**       | R126, 16 holds · `fixed #572`                 |
| 4 — the five acts                   | **DONE**       | the act grep reads 0                          |
| 4b — B-315 (a)                      | **DONE**       | R136 red-then-green                           |
| 5 — the release take                | **DONE**       | R137 + R123 + `exits.py`                      |
| 6 — the pastille                    | **DONE**       | R138 green + mutated; R124 15 holds           |
| **7 — B-313 + the close**           | **DONE, READ** | R139 red on `main`'s producer then green, § 2 |
| **the wave gate**                   | **NOT TAKEN**  | § 4 — it is the next unit                     |

**Register**: B-301, B-302, B-313, B-315, B-322, B-323 read `fixed #572`. **Filed by this lot**:
B-329, B-330, B-350, B-351, B-352, **B-363**, **B-364**, **B-365**, **B-366**. Free in this block:
**B-367…B-369**. Rules R136–R139 are spent; **R140+ are the desktop-frame wave's, not yours**.

**Readings on the current head**: `--contracts` 18 rules + 27 guards, no violation · R139 3 holds ·
`persistence.py` 57 holds · `drawer.py` **30** holds (was 28) · `tsc` 0 · unit suite 107/107 ·
`check-mock-seeds` clean · the cheap guards clean.

**The numbers that gate the wave**: `legacy.js` **31 467** non-blank against a record of 31 467 ·
the six-verb grep reads **0** · **107 rule files** (103 at the wave base).

---

## 2. Phase 7 — what landed

**B-313.** The secondary journey action carries the guard « Voir la fiche » already had beside it.
**R139** (`harness/panel_label_once.py`) raises EVERY panel a finger can reach on two surfaces —
eighteen — and refuses a repeated label in any, which is the FAMILY the register asked for.
**RED on `main`'s producer with no mutation** (`git diff origin/main HEAD` over
`follow-actions.ts` was empty at the reading), naming « Stuart Fails to Save the Universe (2026) »
— the operator's own subject. Green after, panel count unchanged at 18. It counts LABELS and not
destinations because both of his buttons carried the same destination; its subject hold reads
`data-journey`, never the French word; the panels are raised by a real finger.

**B-247's producer half.** `persistence.py` reads `followsheet-complete`, `followsheet-gaps`,
`sheet-journey` and `screen-releases`. Every floor READ by raising it to 999 and taking the
capture — 423, 63, 14, and 158 on the release screen of which only **7** are the screen's own,
which is what set that floor rather than the union.

**The close.** The register rows, DOIT-4 → `served` (DOIT-3 stays `partly`: L20 and L16 still owe
halves), `REPORT.md`, the guards recount. The « Next » row still names L21 and says why.

---

## 3. THE TWO REPAIRS THE GATE UNCOVERED, and both are the same shape

**A repair that stops at the edge of the file it was written in.** Both of these are a fix this
codebase had already made once, in another file, that never travelled.

**B-366 / the hollow sheets — CLOSED BY A RENAME, and the defect is NOT repaired.** `audit.py` R1
read two hollow sheets: a grid tile emits `data-mediasheet` for a follow with no sheet, a poster
that leads nowhere. **Two roads were ruled and both were blocked by the same wall**: `SHEETS_RAW`
is a **20 538-line object literal inside `legacy.js`** (`:9897`–`:30434`) and
`mocks/seeds/media-sheets.json` is a DERIVED copy that `check-mock-seeds` re-derives and refuses
drift on, so giving a title a sheet grows the engine exactly as changing the tile would. The two
paused follows were renamed to titles that already have sheets. **Nothing sheetless is left, so R1
stops reading the case entirely** — the instrument goes quiet and the defect does not. Owner L13.

**The scroll loss — REPAIRED.** Closing a layer restored focus to its trigger without
`preventScroll`, so the browser scrolled that element into view and a list opened near its top went
back to its top. Measured across the close: scrollHeight 1495 both sides, 8 cards both sides, **no
mutation at all**, ONE scroll event 300 → 0 at 35 ms. `ui/virtual-rows.tsx:305` already carried
`focus({ preventScroll: true })` — the only occurrence in the tree — and it had never travelled.
Both branches of `focus.ts` take it now. **The mutation removing it again fells the panel's hold and
NOT the drawer's**, which is correct and worth knowing: the drawer's trigger lives in the chrome and
is always in view, so its close never scrolled.

⚠ **AND THE HOLD THAT CAUGHT IT WAS ITSELF GREEN OVER NOTHING.** On the parent commit the walk asks
for `scrollTop = 300` and the port takes **18** — the boot page was shorter than its viewport — so
`after == before` compared 18 with itself. `drawer.py` now holds that the offset it set actually
TOOK, on both layers, and the rule goes 28 → 30.

---

## 4. What is OWED, in order

### 4.1 HOW TO PUSH, because it is not what it looks like

A push runs the parallel suite through its pre-push hook, so **it IS a heavy run and is wrapped like
one, every time**:

    PYTEST_XDIST_AUTO_NUM_WORKERS=3 HEAVY_FREE_FLOOR_MB=3072 sh scripts/heavy.sh l21 \
      git push origin feat/maquette-l21 > <a file> 2>&1

then prove it with `git ls-remote --heads origin feat/maquette-l21` against the local sha (B-360).

### 4.2 Then, in this order

1. **B-365's repair** — ruled, not yet done. `busy.py`'s « no mutation was answered 409 » hold reads
   Playwright response events and the mock layer answers IN THE PAGE, so it can never see one. Read
   the refusal from `window.__mocks.answered()` across ALL operations, keep the network read beside
   it, keep it guarded so an empty `answered()` is a failure. **The mutation is the 409 forced in
   `mocks/scenario.ts`** — `t.replace("status: armed ? (asked.status ?? 200) : 200,",
"status: operationId === \"grabSeasonForFollow\" ? 409 : (armed ? (asked.status ?? 200) : 200),")`
   — and it must now fell **BOTH** refusal holds, each naming `409 POST grabSeasonForFollow`.
   ⚠ A THIRD hold on that clause will NOT fall and must not be made to: « nothing anywhere said the
   machine was busy » reads whether the INTERFACE says « occupé », which a caught 409 need not.
   While in the file: its `SAID` reads `'#toast, #view'`, and `#toast` is the dying engine's element
   that the React message layer never fills — the `#view` half is all that measures.
2. **The wave gate**, on the final head: full `run.sh`, `--a11y`, `harness-hold-counts.py --compare`
   with **`failed` read FIRST** against the baseline already on disk
   (`taken_at_commit f70ca0295`, **93 rules**), the oracle, `make check`, the ledger, the six-verb
   grep. Expected movement: FOUR new rule rows (R136–R139) plus `drawer.py` 28 → 30 and
   `persistence.py` +10; the oracle's divergences on the four `acq-follows-*` states carry
   « fixture: two paused follows renamed to titles that have sheets », and the discover states carry
   the operator's 30-at-rest ruling (D8). **The reference is NOT re-recorded by this wave.**
3. **The pull request out of draft**, and only on the orchestrator's word.

---

## 5. The machine, and the traps that live in it

**One served copy machine-wide**, on 8899 from `/tmp/tm-refonte`. Announce every harness run to the
orchestrator (`personalscraper-bf`) and to whoever else holds it. The host is a **nohup process
started OUTSIDE the wrapper** — it was pid 5479 at this pause; read `lsof -nP -iTCP:8899 -sTCP:LISTEN`
rather than trusting a number written here.

⚠ **B-371 is settled by measurement, both halves true**: a host forked INSIDE a wrapped run dies
with it, because `heavy.sh` signals its own process group; one started outside that group survives.
`mutate.sh` starts neither, which is how it runs a rule against a refused port and prints
« NO RULE FELL » about it.

⚠ **READ THE `EXECUTED` LINE BEFORE THE `FAIL` LINES.** `mutate.sh` greps only `^  FAIL` and
`violation(s)`, so a crashed rule and an unmoved rule print identically in its summary. `N rules
EXECUTED` is what says the rule reached the page. It also **cannot read `audit.py`'s verdict at
all** — that rule prints `TOTAL: n violations`, plural and unparenthesised — and it **hides the
build's stderr**, so a mutation that breaks the build prints the mutation line, NO rule banner, and
« restored », exiting 1 in silence. **A mutation that produces no verdict line is not a mutation
that found nothing.** All of this is B-273.

⚠ **A `str.replace` mutation matches EVERY occurrence.** One written here matched a neighbouring
ternary that ended in the same three tokens and produced invalid TypeScript. Print the mutated
region before running the mutation, not after reading its result.

⚠ **`mutate.sh` REFUSES a dirty tree**, which is its whole correctness: fix → gates → commit →
mutate → restore.

⚠ **Before any bisect, check that the RULE is unchanged across the range** —
`git log --oneline <base>..HEAD -- <the rule> <common.py>` must read 0. If the rule moved too, every
step measures two changes at once. And **do not narrow a bisect by directory**: this one was nearly
narrowed to the five commits touching `design/src/app` and `design/src/lib`, and the answer was a
SEEDS commit. Narrowing assumes the mechanism, which is the thing the bisect is for.

⚠ **`drawer.py` is named in B-307/B-277** as a rule that has fallen under parallel load and passed
alone. In a bisect one flake sends every later step into the wrong half, so the step where the
verdict FLIPS is re-run once before the flip is accepted. It was, and it held.

---

## 6. The one thing not to repeat

**A repair that stops at the edge of its file, and a document that says it will travel.**
`focus({ preventScroll: true })` existed in `virtual-rows.tsx` and never reached `focus.ts`.
`answered()` replaced a response-event read in one hold of `busy.py` and not in its neighbour.
And `DESIGN.md` § 3.1c named that neighbour vacuous and wrote « Phase 6 owns `busy.py` and repairs
it there » — phase 6 repaired the sibling, left it, and the document went on saying it would be
met. **A wave that records an instrument defect, assigns it, and then reads its own document as
though the assignment were the repair has invented a new way to be green over what it does not
read — one level up, in the prose.**
