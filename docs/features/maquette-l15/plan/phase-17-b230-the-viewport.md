# Phase 17 — B-230: the viewport fallback is removed

**Kind BEHAVIOUR.** Alone, with its own rule.

## What is wrong

`legacy.js:41–50` adds a viewport meta with `maximum-scale=1,user-scalable=no` to any host that has
none. **Dead on this host, which has one; live on any host that does not** — and it is the exact
directive L03 removed for WCAG 1.4.4, restored by a branch nobody reads. P14 is « true on this
host, a landmine on any other ».

The document's own comment records why the directives went: iOS Safari has ignored
`user-scalable=no` since version 10, so what they bought was the violation and nothing else.

## What changes

The branch is **deleted**, not corrected. A page that does not own its `<head>` is not a case this
prototype has: `index.html` is the document, and `serve.py` serves it. A fallback for a host nobody
serves is machinery nobody can justify — D5's own shape.

This removes the nineteenth of `SURVEY.md`'s sites, the one that « draws nothing at all ».

## The rule

A guard — file-reading, cheap, in the contracts tier — refuses `user-scalable` and `maximum-scale`
anywhere under `frontend/maquette/design/`. The axe tier already reports the violation when the
directive is PRESENT on the served document; it cannot see a branch that only fires elsewhere,
which is the whole reason this landmine survived. **Mutation**: restore the branch and confirm the
guard falls naming the file and the directive.

## What the oracle will show

Nothing on this host, by construction — the branch never fires here. The inventory command is what
records the change: nineteen sites become eighteen.
