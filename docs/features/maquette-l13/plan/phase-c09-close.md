# Phase c·9 — The close

**Opening measure (2026-09-15, on `6839dd913`):**

- **Commands.** DESIGN § 2.1's own counting command
  (`python3 -c "import re;print(len(re.findall(r'^\s*\[\s*\n?\s*[\"\x27]([a-zA-Z0-9_-]+)[\"\x27]\s*,',
  open(FILE).read(), re.M)))"`) run per file over `design/src/harness/states/*.ts`: account 1,
  acquisition 26, arrivals 8, entry 5, frame 2, library 11, maintenance 4, media 6, relay 3,
  settings 17, system 30 — **total 113**. `python3 scripts/check-no-french.py`'s own "Named-state ids"
  arm independently reports "113 state identifiers / engine" (the bucket's label is itself residue —
  it still says `/ engine` though the source is `harness/states/`, since L13r). `grep -n
  "Every state has a name" frontend/maquette/README.md` → still says « 54 ». `grep -c
  "| B-" BUGS.md` scoped to the c·9 row list (B-232, B-352, B-465, B-290, B-397, B-275, B-312, B-340,
  B-339, B-336, B-331, B-327, B-366, B-345, B-337, B-071, B-220, B-236) confirms all eighteen rows
  exist in BUGS.md today. `grep -n "In flight" IMPLEMENTATION.md` and `frame-model.md`/
  `frame-survey.md`'s cited line numbers are unread by this commit (c·9's own job, at its own
  opening, on its own head — this measure does not pre-empt it beyond the count above).
- **Points ≈ 5.** No code sites; the register re-read (18 rows), the `README.md` count correction, and
  `REPORT.md`'s authorship are documentation effort comparable to a small phase, not a "new rule"
  phase — no rule/mutation/named-state buckets apply here.
- **Found (2026-09-15).** The true count on THIS head, by the design's own command, is **113**, not
  the "87 unless a later phase added one" the phase file assumes as its unless-clause, and obviously
  not the README's stale "54". Both an independent regex count and `check-no-french.py`'s own
  instrumentation agree at 113, so the figure c·9 writes into `README.md` should read 113 unless a
  phase between c·1 and c·9 adds or removes a named state.

A documentation phase: the register rows, the stale reference sentences and the plan's debts are re-read
against what L13 left, and the wave writes its report. This is the LAST phase of L13c (DESIGN § 9, § 10).

## The proof FIRST

Every claim below is a command re-run on the branch head, with its output pasted in the report. A sentence
that cannot be re-run is removed, not softened.

- **The register, row by row** (DESIGN § 10). For each row, the report records the reading that closes it,
  or the reason it is re-owned:
  - B-232, B-352, B-465, B-290, B-397, B-275, B-312, B-340, B-339, B-336, B-331, B-327, B-366, and B-345's
    library half;
  - B-337 stays open: its device reading is the operator's (b·8);
  - B-071, B-220 and B-236 are stale (DESIGN § 9.10) and the steward closes them.
- **`frontend/maquette/README.md`, section « Every state has a name »**, still says « 54 ». Re-count the
  named states (DESIGN § 2.1's command, pointed at `design/src/harness/states/`); the figure there reads 87
  unless a later phase added one. Its « 54 routes » sentence about the mock layer is a DIFFERENT figure, and
  is re-counted separately.
- **`docs/reference/frame-model.md`'s « Today → target » lines that now read false**:
  - Part 1 (`#screen` removed with its readers);
  - Part 2 (`#shell` re-parented relative to `#screen`);
  - Part 4 (the handler out of the engine, and the three homes of DESIGN § 9.2);
  - Part 11 (the seams that « die with the engine » are the shell's, DESIGN § 9.7);
  - any line citing `legacy.js` by line number.
- **`docs/reference/frame-survey.md`** describes what the dying engine still draws, and after L13 it draws
  nothing. The report says which of its sections are void.
- **The plan's § 5 debts** that name L13 in `docs/reference/frontend-architecture.md` (the instruments'
  debts block). Each is read as discharged or not, with its command.
- **« Guards green », re-counted.** `run.sh --contracts` prints the cheap-guard count, and the report
  records it next to the figure written in the reference documents.

## The move

- **`docs/features/maquette-l13/REPORT.md` (new file)**, added BY FILE (never a folder add). It
  carries the readings above, one per line, with their commands.
- **This wave does not edit the reference documents.** The steward amends `frame-model.md`,
  `frame-survey.md`, the plan's L07, L13 and D3/D10 entries, `CLAUDE.md` and `IMPLEMENTATION.md` from the
  report, in the steward's docs pull request (the operator's fourth measure: one docs PR per lot).
  `frontend/maquette/README.md` is the maquette's own, and its « 54 » is corrected in this commit.

## Gate

Per INDEX « Gates ». In addition, `python3 scripts/check-docs-cited-paths.py` exits 0.

**Before L13c's pull request, which is STOP C:**

- the full suite (`run.sh` with no flag), with no failure;
- the `--a11y` tier at 0;
- `harness-hold-counts.py --compare`, with `failed` read first and every movement of L13c written;
- `make check` at zero failures and zero errors;
- `python3 scripts/check-bug-register.py` and `python3 scripts/check-intent-map.py`, read by OUTPUT.

The steward is told before the full-suite run. **STOP C: the pull request.**

## Commit

`docs(maquette-l13): the close — register rows re-read, the named-state count corrected and the report written`
