# Phase 9 — The close

Nothing new is drawn. This phase re-reads what the phases CLAIMED, seeds the instruments, records
the references, and writes the report.

## 1. The states, seeded into the rule that walks them all

`harness/states.py` takes the **26** new ids (DESIGN § 5) and asserts each renders content, has no
horizontal overflow at 390 px and raises no JS error. **That is DOIT-9's half of this lot's « Done
when »**, and it is a seed into an existing rule rather than a rule of its own — inventing a
numbered rule for what `states.py` already reads would be a second instrument for one question.

Then the accessibility tier over the 26: `run.sh --a11y` at **0**.

## 2. The register

`BUGS.md`: **B-296** and **B-297** read `fixed`; **B-371** reads `fixed` with the path a hand takes
written out; **B-383's veille half** reads `fixed` **and the entry says WHICH half** — its three
other verbs stay the mock-layer wave's, and closing the whole entry would silently claim three
repairs nobody made.

    python3 scripts/check-bug-register.py

⚠ **Read its OUTPUT, not its exit code.** B-346 is live: the closure arm reads an entry's body up to
the first paragraph OPENING with another identifier, so a `**B-NNN's …` paragraph ends the entry it
lives in and claims the body of the one it names — it refused an honest closure once and would have
accepted a silent one. Re-take the 25 affected heads with the command in that entry if any of this
lot's four is among them.

## 3. The clause map

`docs/reference/product-intent-map.md` — DESIGN § 10 carries the intended rows. **This phase
PROPOSES; the operator amends the map**, which that file says in its own header. What is written
here is the proposal and the proof each row names:

- **DOIT-3** — the levers' half `served`, R-L20-a and R-L20-b.
- **DOIT-4** — `partly` → `served`, R-L20-h, R138 unchanged.
- **DOIT-6** — `served`, naming **two** operations (DESIGN § 8.2), R-L20-c, R-L20-e, R-L20-f.
- **NE-DOIT-PAS-2** — the locks called; who holds the lock behind « En file » stays L19's line.
- **DOIT-5 is NOT touched.** Its « progress to the library » is per media, in the tunnel, and L19
  owns it. L20's share is a passage reaching its end — a different sentence, and the map must not be
  made to read as if the per-media half had landed.

    python3 scripts/check-intent-map.py

## 4. The references, and the order matters

`python3 scripts/harness-hold-counts.py --compare`, with **`failed` READ FIRST**. If it is not zero,
the failing rule is repaired before anything is recorded, or the reason is written into the
baseline's record AND into the register entry that owns it — and the report says which of the two
was done. **A baseline written over a failing suite is indistinguishable from a good one**, and
every later comparison rests on it (B-291).

The oracle's own record is the **post-merge gesture's**, not this branch's: `--record` reads `HEAD`,
and `HEAD` must BE the squash. This phase therefore writes the two commands into the report and does
not run `--record` here.

## 5. The gate, in full

`make lint` at zero · `make test` with **no failure and no error** (an ERROR means collection
crashed and everything after it was skipped) · `make check` · the **full** `run.sh` · `--a11y` at 0 ·
the oracle green or its divergences accepted with the reasons DESIGN § 7 names.

Each under the wave's own lock, output to a file, exit code read in the same call, never piped
through `tail`. Then `ps -eo pid,etime,command | grep -E "chrom|playwright|vite|node|pytest" | grep
-v grep` — **kill what was started, and prove it**; a sentence saying « stopped » is not a reading.

## 6. `IMPLEMENTATION.md`

The « In flight » row, written when the pull request opens — the pull request number FIRST, then the
version. `scripts/check-implementation-state.py` holds the row by both.

## 7. The report

`docs/features/maquette-l20/REPORT.md`, and five things it must carry because nothing else will:

1. **The rule-label → number mapping** phase 1 bound, and the red reading of every rule.
2. **Every mutation run**, with the hold that fell and the words it printed. A rule that never bit
   proves nothing.
3. **The stale figures this wave re-measured**: `frontend/maquette/README.md` says the named states
   number 54 (twice) and `product-intent.md` says 82; the count is **87 before this lot** and 113
   after (`python3 -c "import re;print(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"', open('frontend/maquette/design/src/engine/states.js').read(), re.M)))"`).
   **The README's own line is corrected on this branch; the constitution's is the operator's and is
   reported, never edited.**
4. **« Guards green over what they do not read » — the recount**, added to `BUGS.md` § of that name
   with this wave's figure and what establishes it. **Zero is a real answer and is written down with
   the same authority as six.**
5. **The debts this lot names and does not pay**: the three raw `<details>` sites, and the
   `RunSummary` counts the composite line needs from the backend (DESIGN § 9). If no lot claims the
   first, it is B-253's species and needs an entry.

## Commit

`docs(maquette-l20): the close — the map, the register, the counts re-measured and the report`
