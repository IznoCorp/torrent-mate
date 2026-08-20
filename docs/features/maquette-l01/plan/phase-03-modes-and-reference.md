# Phase 3 — The three modes and the reference

## Goal

The oracle gains a memory: `--record` writes the reference, `--check` compares and fails,
`--accept` entérines a reviewed change.

## Why the reference's FORMAT is the deliverable, not a detail

A committed, stably sorted JSON means a visual change is read **in the pull request's diff**,
region by region, instead of arriving as an opaque verdict. A reviewer sees
`font-size: 12px → 13px` on `library/card`. That is what makes the oracle reviewable rather than
merely obeyed.

## Work

1. **`--record`** — measure every *(state × region)*, write
   `frontend/maquette/oracle-reference.json`: sorted by state then region then property,
   fixed indentation, one value per line. Header carries `baseCommit` (the full SHA measured) and
   the region/state counts.

2. **`--check`** — compare; exit non-zero on any divergence. The report is **grouped by state**,
   and each line names the region, the property, and its before → after. An absent region that
   was present is a divergence, and so is the reverse.

3. **`--accept`** — re-record and overwrite the reference, so the change lands in the diff for
   review. It never runs implicitly: nothing invokes it from a gate.

4. **`--stdout`** on `--record`, so ACC-04 can prove stability by `diff`ing a fresh recording
   against the committed file without touching it.

## Done when

- ACC-01: `--check` exits 0 against its own reference and reports the counts measured.
- ACC-04: re-recording an unchanged tree reproduces the committed file **byte for byte**.
- ACC-05: `baseCommit` is a full SHA present in the repository's history.
- ACC-13: `--accept` after a one-pixel mutation touches only the entries that mutation moved.

## Traps

- **Floating-point rectangles.** `getBoundingClientRect()` returns fractional values that differ
  in the last bits between runs. Round to a declared precision and write the precision down; do
  not compare raw floats, and do not hide the rounding inside a helper nobody reads.
- **Key order.** Python dicts preserve insertion order, so an unsorted write is stable within one
  machine and unstable across a refactor. Sort explicitly (ACC-12 exercises this).
- `--accept` must not be reachable from `make check` or `run.sh`. An oracle that can silently
  accept its own divergence is not an oracle.
