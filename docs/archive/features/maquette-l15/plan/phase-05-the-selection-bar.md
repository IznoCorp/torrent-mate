# Phase 5 — The selection bar becomes the library's

**Kind** conversion. **Part** 6, « frame slot, feature content ».

## What lands

`features/library/selection-bar.tsx` — the caption, « Annuler » and « Supprimer », at the same
class (`.selbar`), the same `data-part` values and the same `role="region"` with its accessible
name. It registers into phase 4's slot and reads the library's own selection state.

**It is a new file.** `features/library/page.tsx` is 613 non-blank lines and one of L14's four: it
is not extended, not by one line. The registration is a side-effect import named by `app/frame.tsx`
— the same posture `app/shell.tsx` already takes for `features/media/panel-seasons`.

## What the engine loses

`paintSelBar`, its two `innerHTML`/`appendChild` sites (`8236`, `8239`), its call at `10716`, and
the `selecting` class toggle on the document element — which moves with it, because the class is
what the poster grid reads to draw its checkboxes.

## The rule

`harness/selection.py` holds the bar today by PRINTING the dialog's title and asserting the sheet
opens. It gains a hold that READS: entering selection mode raises a bar whose caption states the
count, « Supprimer » is disabled at zero and enabled at one, and leaving selection mode removes the
bar. **Its mutation**: leave the bar mounted after `selMode` clears and confirm the hold falls
naming the residual bar.

## Trap

`.selbar` is created per open today, so its node identity is new every time by construction. As a
registered component it persists — which is right, and it means the « removes the bar » half of the
hold must read the SLOT being empty, not the node being gone.
