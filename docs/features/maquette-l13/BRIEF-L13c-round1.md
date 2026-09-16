# maquette-l13c — round-one repairs (the reader's findings, DECIDED; a fresh session, the same branch, pull request #607)

You repair pull request #607 (`feat/maquette-l13c`, head `92288cbaf` = the sub-lot's c·9 close with `origin/main`
`e57ac110f` merged in) on the reader's round-one findings. The findings are DECIDED: you apply them, you do not
re-assess them; what you find beyond them is a STOP, never a widening. Read `docs/features/maquette-l13/BRIEF-L13c.md`
(governs: environment, locks, gate form, communication, envelope — all of it still binds), `RESUME-L13c.md`'s state
block, `RULINGS.md` 115–119 and its context block, and the reader's report
`/Users/izno/dev/review-archive/l13c/round-1/r1-C13.md` § FINDINGS (C1, C2, C3, C5, C7) and § « For the next round » —
its instruments (`c07e_refusal.py`, `c07d_refusal.py`, `build_both.sh`, the `.out` readings) are in that same
directory. Tier deep; no MCP server; the orchestrator's exact address is in your launch prompt; handshake first;
every long run waited for INSIDE the call (bounded polling, never `timeout N` around `run.sh`).

## Environment, unchanged

Worktree `/Users/izno/dev/worktrees/wave-l13c`, branch `feat/maquette-l13c`, you are the only writer. Logs
`~/Library/Logs/tm-l13c/`. The mutex (`sh scripts/heavy.sh --held`), the gate form `TM_HARNESS_JOBS=3 sh scripts/heavy.sh
--class browser l13c frontend/maquette/harness/run.sh --contracts --oracle <full rule paths>`, mutations through
`scripts/mutate.sh` (commit before), one line to the orchestrator before and after every mutex run. **Every push runs
under the HARNESS mutex** — `sh scripts/heavy.sh --class test l13c git push origin feat/maquette-l13c`, NO
`HEAVY_LOCK=` override; if the classifier refuses your push, STOP and say so — the orchestrator pushes. No force-push
ever (main is merged IN, never rebased). Verify: `git status --porcelain` empty, `git log --oneline -1` = the head this
brief was pushed on = `git ls-remote --heads origin feat/maquette-l13c`.

## The decided list — one commit per item, every hold RED first on the tree as it stands, then green, its mutation SEEN to fall

1. **C1 + C7 (MAJOR, c·7's adjacent case) — a refused follow is said refused, never « ajouté », and the sheet's act
   carries the medium's identity.** Two halves, one commit each, one hold set.
   (i) *The identity.* `features/acquisition/follow-verbs.ts`'s `registerVerb("follow", …)` passes `suggestion?.ids`
   only when `data-sugidx` names a suggestion; the media sheet's own « Suivre » (the `follow` producer of
   `panel-follow.ts`, `data-fkind` on the element) sends `{title, kind}` and NO identity — the create lands today
   only because the layer joins by title. Repair: the sheet's follow act carries the medium's `ids` to `follow()`
   (the producer's subject or a data attribute the verb reads — choose what the file already does for `fkind`, say
   which). The three sources — search result, suggestion, sheet — then all carry an identity; the layer's title-join
   stays as the fallback it is.
   (ii) *The answer.* `follow()` shows its toast BEFORE the request leaves, `add-verbs.ts` calls `markAdded(result)`
   before the act, and `queries.ts`'s `add` rejection path restores the local list and says nothing. Repair: the
   message follows the layer's answer — on a 200 the message as today; on a refusal (the layer's 400, B-366) a
   refusal is DRAWN where the act was taken: a toast naming it (a new key under `verbs.follows` in
   `design/src/i18n/fr.json`, the French there and nowhere else), the row loses « ✓ Suivi » (`markAdded` undone, or
   marked only on the answer), the local list equals the layer's. The HELD outcome (offline, the outbox, R107) is
   NOT a refusal: a held act keeps today's message and R107 must stay green — read `lib/query-client.ts`'s `HELD`
   before you touch the chain. Where the answer is awaited, the panel still leaves in the tap's own commit (B-249,
   the comment in the verb): only the message and the mark wait.
   *Holds*, in `frontend/maquette/harness/follow_needs_an_identity.py` (R200) or a sibling rule beside it, reading
   the INTERFACE after a create the layer refuses, the refusal armed AFTER the driven state
   (`window.__mocks.setOperationOutcome("createFollow", {status: 400})` — the reader's `c07e_refusal.py` shows the
   arming and the finger): the toast's text is the refusal's and never « ajouté »; no row wears « Suivi »; the local
   follow count equals the layer's after the answer; and, for (i), the sheet's act sends an identity (the layer's
   register records `ids` from a sheet-born create with the title-join disabled — read how `c07d_refusal.py` reads
   the register). RED on the head before the repair (log `r1-C1-red.log`), green after; TWO mutations through
   mutate.sh, each SEEN to fall by name (log `r1-C1-mut.log`): the toast fired before the answer again; the sheet's
   identity dropped again. **Write the mutation's EXPRESSION in the log**, not only the file and the FAIL (the reader
   had to reconstruct all thirteen of the wave's).
2. **C3 (minor, c·7's regression) — a follow created from a result records every identifier the source carries.**
   `mocks/handlers/acquisition.ts`'s create PREFERS the request's single `{provider: providerId}` pair over the
   joined entry's three; the interface's local copy holds three, the layer one. Repair: the handler MERGES —
   `{...source?.ids, ...requested}` (the request's value wins on a shared key) — and refuses only when both are
   empty. `queries.ts` stays as it is (the contract carries one provider pair; a line in the demands block of
   `RESUME-L13c.md` if the register lacks « the create carries the whole identity »). Hold: a create from a result
   carrying three identifiers is recorded with all three (the recorded `ids` is a superset of the source's), read on
   the layer's register; red first; mutation: replace instead of merge → falls by name (log `r1-C3-mut.log`).
3. **C2 (minor, R200's own vacuity) — f4 reads a subject of its own.** f4 (`recorded["ids"] is not None`) is implied
   by f3 (`recorded["ids"]` truthy) on the same `named` follow. Repair: f4 chooses a subject with an identity and NO
   episode data — a FILM the seeds hold (`mocks/seeds/follows.json`: six movie follows carry `ids`; a create of a
   film from a search result carries an identity and no seasons) — and asserts that its create lands 200 with `ids`;
   a mutation that fells f4 while f3 stays green (the handler refusing a create whose kind is a film, or the
   subject's identity dropped for films alone) SEEN to fall (log `r1-C2-mut.log`).
4. **C5 (minor, the wave's own re-aim) — `virtual.py`'s second half can fail.** The hold types `zzz`, which lists
   nothing, so `all(title in alone["pressed"] for title in after_search["pressed"])` is true over an empty list.
   Repair: a query that NARROWS without emptying (a prefix the selected titles share, or one that keeps at least
   one selected row listed), the log printing `after_search["pressed"]` non-empty; mutation: the listing drawing
   pressed a row that is not selected → falls by name (log `r1-C5-mut.log`).
5. **README trap (docs commit).** `frontend/maquette/README.md`'s traps section gains one paragraph, in English:
   the mock layer intercepts `fetch` IN the page, so a Playwright response listener sees nothing on the API routes; a
   claim about « the request that leaves » is read in the layer's register, never in a network trace. And the
   mutation log keeps the mutation's EXPRESSION beside the file and the FAIL. `RESUME-L13c.md`'s ledger gains the
   round's line (head, the five items, the logs).

C4, C6, C8 and C9 are the steward's (the docs register); not yours.

Then the gate on the final head — ONE invocation, the contracts tier + oracle, with every rule that reads the
follow path NAMED (the order-42 amendment: the READERS of the behaviour, not only the writers):
`follow_needs_an_identity.py`, `outbox.py` (R107), `add_footer.py`, `add_screen_opens_fresh.py`, `follow_verb.py`,
`followed_sheet_act.py`, `follow_has_sheet.py`, `cold_follow_panel.py`, `follows.py`, `panel_label_once.py` (R139),
`said_and_done.py`, `virtual.py`, plus every file
`grep -l -E "ajouté à vos suivis|ajouté à votre liste|Suivi\b|createFollow|/api/acquisition/followed" frontend/maquette/harness/*.py`
names — the list in the body; the four mutations SEEN to fall on the final head; `make lint`;
`python3 scripts/check-no-french.py` (the new i18n key); `python3 scripts/check-docs-cited-paths.py`;
`tests/scripts/test_check_maquette_comments.py` alone (the comment baseline moves if a comment is added — re-record it
in the same commit, diff read as counts only); push (harness mutex); PR body amended with a « Round one » section:
per finding, the commit, the hold, the red, the mutation's FAIL line with its expression, the reading. No full suite:
the reader ran it on this head (147/26, a11y 0/147, oracle 0) and the orchestrator runs the contracts tier at the
gesture. Report the head; the orchestrator verifies on the files and merges — there is no second reader round
(measure 2).

## Non-goals

- Any file outside `frontend/maquette/design/src`, `frontend/maquette/harness`, `frontend/maquette/README.md`, the
  comment baseline, `RESUME-L13c.md` and the phase files' dated lines; no `scripts/`, no `docs/reference/`, no
  `IMPLEMENTATION.md`, no `BUGS.md`, no version bump (0.98.98 is done), no rebase, no reference re-record (the oracle
  reads 0 today and must still; a named state whose paint moves is a STOP), no seed change (the Clone Wars identity
  is filed).
- Widening a repair beyond its finding: the selection bar's touch floor (C8), the order-dependent states (C9), the
  centring hold (C6), the contract's single provider pair — none of them.

If you believe something outside this list is needed, STOP and ask the orchestrator first.
