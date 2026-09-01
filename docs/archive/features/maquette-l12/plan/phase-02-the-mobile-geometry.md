# Phase 2 — The mobile geometry

**Kind: BEHAVIOUR.**

**Owns P11** (`100dvh`, no `100vh`), **contained overscroll**, and **P17 = B-234**
(`interactive-widget=resizes-content`).

## What it does

- `styles/base.css:54` is `height: 100%` on `html, body`. The frame becomes `100dvh`. **Measured:
  no `dvh` exists anywhere in the tree** — the only `100svh` is in `harness.css`, which is the
  measuring apparatus and ships nowhere.
- `overscroll-behavior-y: none` is already on `html, body` (`base.css:55`) and P12 reads true on
  `#port`. This phase **verifies and does not re-do it** — churn with no defect is churn — and
  extends containment only where a scrollable layer is measured to lack it.
- **B-234**: `design/index.html:18` reads `width=device-width,initial-scale=1`. It gains
  `interactive-widget=resizes-content`, so the virtual keyboard resizes the *content* rather than
  the viewport.

## The two directives that must NOT come back

`maximum-scale=1` and `user-scalable=no` **masked** the focus-zoom defect rather than fixing it; L03
removed them and `scripts/check-viewport-directives.py` keeps both out of markup, script **and**
stylesheet. This phase edits the same attribute they lived in. **The guard must be run and seen
green after the edit**, not assumed: P14 depends on their absence and axe can only see a directive
present on the document it audits.

## The 16 px half is PAID — it is not redone

L07 (#494) put every field on `text-6` = 16 px and **R83** refuses a focused field under it. P13
reads true. This phase touches none of it.

## The rules

Two static reads: one for `100dvh` present and `100vh` absent from `design/src` (the harness's own
`harness.css` excluded, and the exclusion written down with its reason); one for the viewport meta
carrying `interactive-widget=resizes-content` **and neither forbidden directive**.

## Mutation

Revert the meta to its current value → the B-234 rule falls naming the missing token. Write
`maximum-scale=1` into it → `check-viewport-directives.py` falls. Put a `100vh` back → the P11 rule
falls. Three mutations, three restores.

## Done when

P11 and P17 read true; B-234 closes in `BUGS.md`; `check-viewport-directives.py` is green **after**
the edit; P13 and P14 are unchanged.
