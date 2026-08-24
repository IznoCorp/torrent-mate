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

## Gates

ACC-01, ACC-02 (zero divergence: no utility is used yet, so the generated sheet is empty of
anything the document references), ACC-03, ACC-08, ACC-17.
