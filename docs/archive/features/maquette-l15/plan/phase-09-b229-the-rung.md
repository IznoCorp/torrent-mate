# Phase 9 — B-229: the dialog's rung on the ladder

**Kind BEHAVIOUR.** It lands alone, in its own commit, with its own rule. The oracle may diverge
and every divergence is named before it is accepted.

## What is wrong

D1's third tier reads « Transient: no URL, but Back still closes it », and names a confirmation as
its example. `openDlg` pushes no history entry and `onEngineBack` has no `#dlg` branch — so a
hardware Back with a dialog open pops the entry UNDER it, a page or the exit guard, with the dialog
still up. It is not closerless: Escape reaches it (`app/focus.ts:213`) and so does a scrim tap.
Only Back does not.

Q5 records that this is an **unimplemented decision, not an open question**, and that the
finger-visible change is announced rather than discovered.

## What changes

`app/dialog-host.ts`'s open pushes a layer entry through `window.__bridge.pushLayer("dialog")`;
its close unwinds it unless the close IS the pop. The registration phase 7 added is what the
engine's handler walks, and the dialog takes the rung **above** the drawer and the sheet: it is
what sits on top.

## The rule

A hold that opens a confirmation, presses Back, and asserts three things together — the dialog is
closed, the page underneath is the same page, and `history.length` is back where it started.
Asserting the address alone is not enough: that is R69's own lesson, and a hold that reads only the
address passes over an entry spent twice.

**Its mutation**: remove the `pushLayer` and confirm the hold falls naming the page that changed —
not « the dialog is still open », which the missing branch alone would also say.

## What the oracle may show

Nothing. A history entry is not a rectangle. A divergence here would mean something else moved and
is a defect, not an acceptance.
