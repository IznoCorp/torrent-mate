# Phase 8 — The dialog

**Kind** conversion. **Part** 7.

## What lands

`ui/dialog.tsx` at `#dlg`, keeping `role="dialog"` and `aria-modal="true"`, and taking its
accessible NAME from the descriptor's heading rather than by reading back markup it has just
written.

`app/dialog-host.ts` publishes `window.__dialog` with the descriptor
`{ heading, body, actions: [{ text, tone, target }] }` — `app/panel-host.ts`'s sibling, and its
posture: **facts cross the seam, markup stays the component's.**

`body` is a list of BLOCKS, the way `ui/panel/contract` already declares its own: a paragraph, a
dry-run notice, a manifest, a warning box. A block type nobody declared must RAISE, and the refusal
is provable from outside — `window.__unknownPanel` is the precedent and the dialog gets its
sibling.

The **two producers** (`legacy.js:10788`, `10915`) hand descriptors instead of HTML strings.
DOIT-8's confirmation — « Ce film est déjà en médiathèque … remplacera … » — is one of them, and
its copy moves to `fr.json` in the same move.

`index.html`'s empty `<div id="dlg">` is removed in this commit.

## What the engine loses

`openDlg`, `closeDlg`, the `#dlgcancel` binding, and the two template strings.

## The rules

- A hold that opens each of the two dialogs, reads the heading as the accessible name, counts the
  actions and asserts the danger tone is on the destructive one. **Mutation**: drop the tone from
  the descriptor and confirm the hold falls naming the action.
- The unknown-block refusal, called as a plain function.
- `harness/audit2.py:239` (« deleting a medium: no confirmation ») reads `#dlg[data-open]` and is
  the ONE hold that does. It is re-run; the attribute is preserved.

## Trap

`openDlg` is called on the line after `panel.close()` in one producer, and the dialog raises the
**shared** `#scrim`. `app/panel-host.ts` flushes synchronously for exactly that reason. The dialog
host does the same, or a commit landing a frame later clears the scrim out from under it. Phase 12
gives the scrim one owner and removes the hazard; until then the flush is what holds it.
