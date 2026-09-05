# L19 — The producers · the plan

## THE PHASES CHAIN WITHOUT PAUSE

**The operator arbitrates the SCOPE, never the cadence.** No phase stops to report that it is
done; the next one begins in the same breath. The only stops are the four this file names in
§ « Where this plan stops », and they are stops because something outside this session has to
answer, not because a phase ended.

**The self-check that proves it was obeyed**, run before the pull request opens and pasted into
`REPORT.md`:

```bash
# One commit per phase at least, and no gap in the sequence.
git log --oneline main..HEAD | grep -c "maquette-l19"
# Every phase file records a verdict, and none is left blank.
grep -L "^## Verdict" docs/features/maquette-l19/plan/phase-*.md   # expect: no output
# And the honest half: every stop actually taken is named in REPORT.md § Stops.
grep -c "^### Stop" docs/features/maquette-l19/REPORT.md
```

A phase file with no `## Verdict` section is a phase that was not finished, whatever the commit
log says. The middle command is the one that bites, because it reads the FILES rather than the
narrative.

---

## The order, and why it is this order

**B-306 first** (phase 01), because every later phase's subtraction is read through it: an arm
that cannot count would let this wave repeat exactly what it was built to catch.

**The seam second** (phase 02), proved end to end by the smallest producer, so nine later moves
are a repetition of something already measured rather than nine first attempts.

**The producers in ascending risk**, each at zero divergence over the oracle.

**Each verb as two phases** — the rule on the engine's side seen red, then the move read green by
the same rule, its assertion count unchanged. A rule written after the move proves only that it
agrees with the move.

**The two behaviour phases LAST** (17, 18), each alone in its commit with its rule seen red
first. The first review rule: a conversion wave does not carry a behaviour repair, and keeping
them at the end is how this one honours it while still owing them.

| # | Phase | Kind | Commit(s) |
| --- | --- | --- | --- |
| 01 | The size arm learns to count (B-306) | instrument | 1 |
| 02 | The producer seam, proved on the account menu | seam + conversion | 1 |
| 03 | Maintenance — the action panel | conversion | 1 |
| 04 | Settings — a secret and a setting | conversion | 1 |
| 05 | `data-cancelsetting` — the rule, on the engine | instrument | 1 |
| 06 | `data-cancelsetting` — the move | behaviour move | 1 |
| 07 | Library — the sort sheet | conversion | 1 |
| 08 | Acquisition — « Veille et obligations » and the journey | conversion | 1 |
| 09 | Acquisition — a suggestion | conversion | 1 |
| 10 | Acquisition — a search result to add, and DOIT-8's rule | conversion + instrument | 1 |
| 11 | Acquisition — the follow sheet, and NE-DOIT-PAS-9's rule | conversion + instrument | 1 |
| 12 | `data-take` — the rule, on the engine | instrument | 1 |
| 13 | `data-take` — the move, and R103's floor | behaviour move | 1 |
| 14 | The Découvrir feed | conversion | 1 |
| 15 | The episode popover's sentence | conversion | 1 |
| 16 | DOIT-4 and NE-DOIT-PAS-3 — one instrument | instrument | 1 |
| 17 | B-299 — the version conflict draws | **behaviour** | 1 |
| 18 | B-300 — the restart is confirmed | **behaviour** | 1 |
| 19 | The gates, the figures, the register, the report | closing | 1+ |

---

## What every conversion phase does, so no phase file repeats it

1. The producer moves to `features/<domain>/panel-<subject>.ts`, registered through
   `registerProducer` at module evaluation.
2. Its French is **extracted** into `i18n/fr.json` under `panels.<kind>.*` — never retyped.
3. Its delegation branch in `legacy.js` becomes `panel.produce("<kind>", subject)`; the verb
   stays the engine's.
4. Its entry in `engine/states.js` calls the same seam, so the scenario table stops importing
   the producer by name.
5. Its family leaves `app/engine-data.ts`'s `NEEDED` if it was there, and its member leaves the
   feature's reference slice if the engine stops publishing it (`--arm reference-slice`).
6. **The oracle is green at zero divergence.** This is a conversion lot.
7. **R100's hold (f) gains the panel's own nodes** on the state that opens it, with a floor, and
   the addition is mutation-tested through `scripts/mutate.sh`.
8. The size arm's record for `engine/legacy.js` and `engine/states.js` is **re-recorded
   downward, in the same commit**.
9. The shell's line count is written into the phase file — it may only fall.
10. `--contracts` and the repository's cheap guards are green.

**Committed before every mutation** (B-303). **`git add -f` by FILE, never by directory**
(B-304).

---

## Where this plan stops

**Four stops, and each is a question this session cannot answer for itself.**

### Stop A — before the first harness run

The harness is one per machine. Before `run.sh`, the oracle, `mutate.sh` or
`harness-hold-counts.py`, the steward is messaged and its answer awaited.

### Stop B — DOIT-4's pastille, if it does not exist

Phase 16 measures whether the resolve queue's « En file » pastille is DRAWN today. If it is, the
rule reads it and the row turns `served`. **If it is not, drawing it is a behaviour change and
it is not this lot's** — the row is filed `partly` with L21 as owner and the phase says so. That
is not a stop for an answer; it is a stop for a RULING to be recorded, and the phase carries on.

### Stop C — a divergence the oracle refuses to call noise

A conversion lot's oracle is green at zero divergence or the divergence is a defect. A
divergence that survives investigation stops the phase and is reported before anything is
accepted.

### Stop D — the pull request is opened, and the review is the steward's

The readers are independent of this session. No head is reviewed until every item of the
previous round arrives with the probe reading that closes it, taken on a build of the candidate
against a control of the previous head — or with a sentence saying what the fixtures cannot
show. Every repair lands with the rule that falls when it is reverted.

---

## The instrument, and the machine

Every run that starts browsers, builds or a parallel test run is wrapped:

```bash
TM_HARNESS_JOBS=2 sh scripts/heavy.sh l19 <command>
PYTEST_XDIST_AUTO_NUM_WORKERS=3 …            # a parallel test run, three workers
```

Two browser groups machine-wide. Never a build beside a run. **Kill what is started, delete what
is built, and verify with `ps`** — a sentence saying « stopped » is not a reading. The host on
8899 is `run.sh`'s and is left alone.

A rule that falls while another session held the harness is re-run alone before it is read, and
a re-run that removes the load the failure needed is said in the same breath (B-277, B-307).
