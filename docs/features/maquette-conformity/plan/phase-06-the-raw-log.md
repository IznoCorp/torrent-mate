# Phase 6 — The run's raw log wraps: no sideways scroll (a responsive defect, the operator's OPEN 10 = A)

**Ruled 2026-09-29** (`/Users/izno/dev/review-archive/conformity-80/rulings-2026-09-29.md` § Q10, « A »): the run
screen's raw log goes `whitespace-pre-wrap`, breaking anywhere — no horizontal scroll, no exception to § 12 nor to
the responsive rule. Report B.5 R13. **Kind: defect.**

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `grep -n "runLog" -A2 frontend/maquette/design/src/features/system/variants.ts` → **:57**
  (`whitespace-pre overflow-x-auto`), drawn at `features/system/run-screen.tsx:253` (`run/log`, `tabIndex={0}` — a
  focusable scroller, whose reason goes with the scroll); R-conformity-a's `overflow` arm reads preformatted text in
  a horizontal scroll port (added for this ruling) — its red on `run-detail` read at the second full pass.
- **Points ≈ 7.** The class edit (1); `tabIndex` reconsidered with the scroll it existed for (1); `raw_log.py`'s hold
  « the log block is the one allowed to scroll sideways » (**:195**) RE-AIMED to « the log wraps, nothing scrolls
  sideways », said out loud (1); `BUGS.md` per order 57 (2); the owed entry removed (1); the RESUME (1).
- **Readers.** `raw_log.py` (a contract rule), `back.py`.

## Red today

R-conformity-a: `overflow · run/log` on `run-detail` (owed to this phase until it lands).

## Mutation

Restore `whitespace-pre` → R-conformity-a and the re-aimed `raw_log.py` hold fall by name.

## Oracle: states that diverge, declared by name

`run-detail` and every run screen state with a log (built by script) — accepted by name.

## Commit

`fix(maquette-conformity): the raw log wraps — nothing on the run screen scrolls sideways`
