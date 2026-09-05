# Phase 01 — The size arm learns to count (B-306)

## Objective

`scripts/check-frontend-boundaries.py`'s `GRANDFATHERED` dict maps a file to a LABEL and nothing
else: the arm checks the label exists and never that the file shrank. L14 added 77 non-blank
lines to the engine under a decision titled « dies by subtraction » and the arm printed clean.

**This wave is the next one that subtracts from the engine, so it takes the debt** (the plan's
§ 5 debts block). It is phase 01 because every later phase's subtraction is read through it.

## What changes

- `GRANDFATHERED` becomes `{path: (label, recorded_non_blank_lines)}`.
- **Above the record → violation**, naming the file, the record, and the reading.
- **Below the record → printed**, with « re-record it in the phase that subtracts ». It is
  re-recorded in the same commit that subtracts; a count re-recorded later is a count nobody
  compared.
- The record is measured exactly as the arm measures a file — non-blank lines — so the two
  readings cannot drift apart by definition.
- The label's grammar (`OWED_LOT`) is unchanged: it is the first element of the pair now, and
  every existing check on it keeps its subject.
- The summary line names the recorded counts, so a reader sees them without opening the file.

Starting records, measured on this branch at `446b0e921`:

```bash
grep -cve '^[[:space:]]*$' frontend/maquette/design/src/engine/legacy.js   # 32461
grep -cve '^[[:space:]]*$' frontend/maquette/design/src/engine/states.js   # 791
```

## The rule that bites

`tests/scripts/test_check_frontend_boundaries.py` (or the file that already holds this guard's
arms) gains three cases on a scratch tree pointed at with `--root`:

1. a grandfathered file AT its record → clean;
2. a grandfathered file ONE LINE ABOVE its record → exit 1, the message naming file, record and
   reading;
3. a grandfathered file BELOW its record → exit 0 and the « re-record » note printed.

Case 2 is the one B-306 is about; case 3 is what makes the ratchet fall rather than freeze.

## The mutation, and why it is read by hand

**`scripts/mutate.sh` cannot judge a guard** (B-273): it decides by reading journal `FAIL` lines,
which a guard in `scripts/` never prints, so it answers « no hold fell » whatever the arm says
and whatever its exit code. So:

```bash
# BEFORE — the arm on the tree as committed
python3 scripts/check-frontend-boundaries.py --arm size ; echo "exit=$?"
# THE MUTATION — one line added to the engine, by hand
printf '\n// mutation: one line, to be removed\n' >> frontend/maquette/design/src/engine/legacy.js
python3 scripts/check-frontend-boundaries.py --arm size ; echo "exit=$?"
# RESTORE, and verify
git checkout -- frontend/maquette/design/src/engine/legacy.js && git status --short
```

**Both exit codes are written into this file**, and `git status` is verified empty after the
restore. The tree is committed before the mutation.

## Gates

`make lint` · the guard's own tests · `--contracts` tier · `check-module-size` on `scripts/`
(the guard is near no ceiling but the arm is read).

## Verdict

**Landed.** `0e2a855e5`.

### The mutation, read by hand

`scripts/mutate.sh` cannot judge a guard (B-273), so the arm's EXIT CODE is the reading and both
readings are written here:

```
BEFORE    python3 scripts/check-frontend-boundaries.py --arm size   → exit 0
MUTATED   printf '\n// mutation: one line, to be removed\n' >> …/engine/legacy.js
          python3 scripts/check-frontend-boundaries.py --arm size   → exit 1

  engine/legacy.js — recorded at 32461 non-blank lines and reads 32462, 1 more.
  A grandfathered file is one that may not be EXTENDED; subtract the addition,
  or record the growth here with the decision that allows it

RESTORED  git checkout -- …/engine/legacy.js && git status --short   → empty
          python3 scripts/check-frontend-boundaries.py --arm size   → exit 0
```

The arm fell on **one** added line, which is the smallest form of the defect B-306 records, and
it named the file, the record and the reading.

### Deviation — the guard was split

**Not in the design, and taken here.** The change took `check-frontend-boundaries.py` to 1 026
non-blank lines against `check-module-size.py`'s **hard** ceiling of 1 000 (exit 1). The subject
split out is the ceiling's LEDGER — `scripts/frontend_size_ledger.py`, 177 lines: the forgiven
files, the lot that owes each reduction, the recorded sizes, and the reader of the plan and the
advancement. They travel together because every one of them answers « does this entry still
promise something », and splitting them would have left the reader of `IMPLEMENTATION.md` in one
file and the labels it judges in another — the arrangement that let `L09` sit at `NOT STARTED`
for a whole wave.

The guard keeps `arm_size` itself, which measures the tree: `arms()`'s census still finds it,
`ARMS["size"]` still points at it, and the arms test reads 11 arms as before.

**Split on a SUBJECT, not on a line count** — L07-bis's answer, taken twice again in L14. 948 →
885 (soft warning, as before) plus a 177-line ledger.

### Readings

| Reading | Value |
| --- | --- |
| `check-frontend-boundaries.py` | 948 → 885 non-blank |
| `scripts/frontend_size_ledger.py` | 177 non-blank |
| `check-module-size.py --root scripts` | exit 0 |
| guard tests | 56 passed |
| `make lint` | clean (ruff, ruff format, mypy 488 files, logging) |
| `check-no-french.py` · `check-code-abbreviations.py` | clean |
| `tests/scripts/test_ci_filter_covers_the_guards.py` | 69 passed |

**The ledger is read on every pull request**: `check-frontend-boundaries.py` is a step of the
`no-french` job, which carries **no path filter at all** — so the « a guard that runs in no CI
job » trap does not apply, and it was checked rather than assumed.
