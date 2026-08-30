# Phase 6 — The toast

**Kind** conversion. **Part** 7. **Serves** §8 — « rien en silence ».

## What lands

`ui/toast.tsx` at `#toast` / `#toastmsg`, keeping `role="status"` and `aria-live="polite"` and — the
mechanism that makes them work — **the region present in the document before any text reaches it**.
A live region inserted together with its content announces nothing, so the component renders
always: shown is a class, not an absence, exactly as `ui/sheet.tsx` renders its layer.

`app/toast-host.ts` publishes `window.__toast` with the descriptor `{ message, undo? }`.
`toastUndo`'s « Annuler » becomes the descriptor's second field, not a string of markup.

## What the engine loses

`toast`, `toastUndo`, `setMessageShown`, the `#toastx` binding and the two timers. Its **34
callers** keep calling one-line forwarders (`toast(m)` → `window.__toast.show({ message: m })`),
because they are producers and L19 owns them; the forwarders die with the producers.

`select("#toastmsg").innerHTML =` at `8943` is the write `SURVEY.md` § 1.1 exists to have caught —
it is gone with this phase.

## The rules

- `harness/chrome.py` gains: the message region exists at first paint with no text in it, a
  message appears in it without the region being replaced (`isSameNode`), and the undo variant
  offers a control that is a real `<button>`. **Mutation**: render the region only while a message
  is up, and confirm the hold falls naming the replaced region.
- The action-button interlock of phase 3 now reads the store rather than a seam flag; its rule is
  re-run and must still bite.

## The oracle reads this one

`shell/toast` is one of the 35 regions. A conversion here is measured, and zero divergence is the
gate.

## Trap

Two timers, 5 s and 6 s, and they are not interchangeable: the undo variant is longer on purpose.
A single constant would be a behaviour change smuggled into a conversion.
