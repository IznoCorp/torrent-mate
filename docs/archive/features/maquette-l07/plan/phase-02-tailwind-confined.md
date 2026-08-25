# Phase 2 — Tailwind arrives, confined

**Converts nothing.** The build learns Tailwind, the scale lifts into `@theme`, and the scan is
proved not to leave the maquette.

## What lands

1. **`design/src/styles/theme.css`** — `@import "tailwindcss"`, the `@theme` block, and the
   `@source` confinement. Imported from `index.html`, which is what puts a real stylesheet in
   `dist/vite/` for the first time. `serve.py` already serves `/vite/*.css` as `text/css` and
   `run.sh` already copies `dist/vite` to the served root, so neither needs a change — verified
   before relying on it.
2. **`@tailwindcss/vite`** in `design/package.json`, and the plugin in `vite.config.mjs`. The
   prototype fragment is still injected verbatim, `order: "post"`, untouched.
3. **L06's four families lift unchanged** — `--spacing-*`, `--text-*`, `--radius-*`, `--ease-*` —
   because P-2 of L06 named them for this. Re-verified by compilation before use, not assumed.
4. **The five `@keyframes` become `--animate-*` theme entries**, carrying the whole shorthand, so
   the computed `animation` the oracle measures is unchanged.

## The confinement, held from both ends

Production already carries `@source not "../../maquette"` in `frontend/src/styles/globals.css` —
the fix for the 936 bytes that leaked when the scan ran from the project root. The maquette
declares the mirror: it scans `design/src` and `design/index.html`, and nothing above them.

**A rule holds both directions**, because a confinement written in one file and read by nobody is
the shape of every guard this repository has found green over its own subject.

## Mutation tests

- Remove `@source not "../../maquette"` from production's entry → the rule exits 1 and names the
  file. Restore, green.
- Point the maquette's `@source` at the repository root → the rule exits 1. Restore, green.

## What this phase found that the plan did not forecast

Three things, each measured, and two of them invisible to every instrument that existed:

1. **Preflight cannot be imported here.** `@import "tailwindcss"` pulls an opinionated reset that
   would change the rendering on the first commit of a wave whose whole claim is that it does not.
   The two halves that carry no opinion are imported instead; `base.css` stays the one reset.
2. **`@source` confines nothing.** Tailwind v4 scans the project root automatically and `@source`
   ADDS to that scan. Measured: narrowing the list to five directories changed the output by
   nothing, down to the file hash. `source(none)` took it from 32 utilities to 20.
3. **A plain `@theme` is tree-shaken**, so the scale left the served document entirely — 2 236 of
   2 739 measurements collapsed. And the run before it was GREEN, because the leak of trap 2 was
   dragging the tokens into the output as a side effect. `@theme static` is the fix, held by a
   fifth hold of the new guard.

**The collision nobody would have looked for**: Tailwind generates a utility for any candidate
word it finds, and this prototype's vocabulary overlaps it — `grid`, `block`, `table`, `hidden`,
`fixed` are all names somebody might choose. One real collision today (`grid`), declared with its
reason. The prototype wins it only because its rules are unlayered while Tailwind's sit in a
layer, which is a property of the cascade rather than a decision anyone took.

## Gates

ACC-01, ACC-02 (zero divergence: no utility is used yet, so the generated sheet is empty of
anything the document references), ACC-03, ACC-08, ACC-17.
