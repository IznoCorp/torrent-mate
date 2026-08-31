# Phase 1 — B-256: the lock and the stamp

**Why first.** Every other phase of this wave is proved by the harness, and B-256 is the finding
that the harness can measure the wrong prototype without saying so. Repairing the instrument at the
end would mean every earlier reading was taken before the thing that makes readings trustworthy
existed.

## What lands

- `frontend/maquette/harness/served_copy.py` — the lock and the stamp, one subject, one file.
- `frontend/maquette/harness/run.sh` — takes the lock before building, writes the stamp after the
  copy, and reads the stamp around **every** rule it launches.
- `frontend/maquette/harness/common.py` — reads the token at import, asserts it in `open_page`
  (the start) and in `Journal.summary` (the end).
- `tests/scripts/test_served_copy.py` — the logic, without a suite running.
- `Makefile` — the contract tier stops announcing a figure it cannot keep current.

## The coverage, stated rather than implied

| Reader | Rules it covers | What only it covers |
| --- | --- | --- |
| `run.sh`'s per-rule wrapper | **75 of 75** | `audit2.py` — the rule that started the incident, and one of the twelve importing nothing from `common.py` |
| `common.open_page` | 45 | a rule run **by hand** from an editor, which `run.sh` never sees |
| `common.Journal.summary` | 53 | the same, at the other end |

`grep -l "open_page" frontend/maquette/harness/*.py | wc -l` · `grep -l "Journal(" frontend/maquette/harness/*.py | wc -l` · `ls frontend/maquette/harness/*.py | grep -v common.py | wc -l`

## Two defects found while writing it, both silent by nature

- **The trap would have given away another session's lock.** `run.sh` releases from a trap that
  fires however the script ended — the refused-acquisition path included. Armed before the
  acquisition, a refusal would have released the lock of the session legitimately holding the copy,
  and the victim would have been the session that did everything right. Fixed twice over: the trap
  is armed *after* a successful acquisition, and `release()` refuses to give back a lock recording
  another pid.
- **The recorded pid was the helper's, not the suite's.** `run.sh` acquires through a `python3`
  that exits a millisecond later. Recording *its* pid made every lock look abandoned to the
  staleness check. The shell passes `$$`.

## Done when

- ACC-01 the copy carries a stamp · ACC-02 the tests pass and the live mutation is seen to bite ·
  ACC-03 two suites cannot interleave · ACC-04 the announced figure matches what runs.
- `run.sh --contracts` green with the wiring in place.
