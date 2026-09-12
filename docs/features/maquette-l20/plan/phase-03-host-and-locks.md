# Phase 3 — The host, and the locks (B-297)

The phase the operator's ruling touched, and the only one (DESIGN § 1, « Q1: B »). It creates the
« Pipeline » section of Système and fills it with the one part that WRITES NOTHING: the locks.

## The rule FIRST, and it is red against `main` with no mutation

`frontend/maquette/harness/locks.py` — new, label **R-L20-g** (bound to its number in phase 1). Four
holds, each failing differently:

1. **The four facts are DRAWN**, each with what makes it decidable: the pipeline lock with its
   AGE (« Libre » · « Pris — <age> » · « Verrou obsolète »), the `pause` sentinel with its age, the
   automatic trigger's sentinel with its age, and the sweep. Read on the DOM, by `data-part`.
2. **The sweep's `pending` skeleton covers the SWEEP BLOCK ONLY.** Driven through
   `window.__mocks.scenario()` with the sweep pending: the other three rows still carry their
   values. *A skeleton over the whole section would hide three facts that have already answered* —
   which is the defect this hold exists for, not thoroughness.
3. **Zero orphans is SAID** — « Aucune. » — never an empty block. §8: a « rien » with no visible
   reason is a lie by omission.
4. **The repair is a PATH, not a button.** The stale lock and the orphan list offer a
   cross-reference to Maintenance and no act of their own (B-297: « its repair stays a Maintenance
   command »). The hold refuses a mutating control inside this block.

**The agreement half of R-L20-g is phase 4's** — it needs a lever to disagree with — and this file
says so in its own docstring rather than leaving the next reader to wonder why a rule named for an
agreement reads none.

**Seen red how**: against `main` the section does not exist and `readLocks` is called nowhere
(`grep -rn "maintenance/locks" frontend/maquette/design/src` → nothing). All four fail there.

## The move

- **New file** `features/system/pipeline-panel.tsx` — the HOST: the section heading « Le pipeline »
  (`screens.system.pipeline`), its guidance line, and the slots its later blocks render into. It is
  the file the ruling decided, and nothing later decides anything about it.
- **New file** `features/system/locks.tsx` — the four fact rows, through `factRowsHTML`, the emitter
  Système already reuses verbatim (its markup carries `data-*` the delegation reads and re-deriving
  it would drift the seam).
- **New file** `features/system/locks-queries.ts` — `useLocks()` over `readLocks`, one read, in the
  query cache (invariant 4).
- `features/system/page.tsx` gains ONE element and its header's « it is a pure renderer — it writes
  nothing, ever » sentence is rewritten in this commit, naming what is coming. **A header that
  outlives its subject is read as current by the next session.**
- `features/system/live.ts` gains the locks key on the run-lifecycle rule, with its `because` — a
  lock is taken and freed by exactly those events.
- Copy in `i18n/fr.json` under `screens.system.*`, EXTRACTED and never retyped.
- **No PID is printed** (DESIGN § 4.3): NE-DOIT-PAS-4, and §12's width. The field stays in the
  answer and is drawn nowhere.
- `regions.json` gains `system/locks`, anchored on `data-region` — never on a class, the floor is a
  hard zero.

Named states added to `engine/states.js`: `locks-free`, `locks-held`, `locks-stale`,
`locks-sweep-pending`, `locks-orphans` (DESIGN § 5), each reachable by `window.__go`.

## Gate

`run.sh --contracts` under the shared lock, announced; R-L20-g green with its holds counted. The
oracle: `system`, `system-outage`, `system-loading` and `system-error` diverge on `system/body` and
`shell/page` because the page grew — accepted with « L20 § 4.3: the locks land on Système ». **Every
other state at zero, or STOP A.**

## Commit

`feat(maquette-l20): what holds the pipeline, and what a crash left behind, on Système`
