# Phase 24 — The candidate's poster opens its sheet; only « Choisir » picks (a defect, the operator's)

**Reported 2026-09-29, 22:2x** (`/Users/izno/dev/review-archive/conformity-80/rulings-2026-09-29.md` § « DEFECT +
PRINCIPLE »): touching a candidate's poster on the resolution screen PICKS it; expected, as everywhere else in the app,
its media sheet. The operator's principle: « Il faut uniformiser les comportements. Sauf exception volontaire de ma
part. » **Kind: defect.** Same card as phase 23, so right after it.

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `sed -n 70,92p frontend/maquette/design/src/features/acquisition/resolution-cards.tsx` → the WHOLE
  candidate card is one `<button data-resolve>` (**:84**); « Choisir » (`card/pick`, **:118**) is `aria-hidden` inside
  it; the comment at **:71–78** justified not leaving the screen (« loses the queue »).
- **The Retour check FIRST, by finger** (class rule): resolution screen → a candidate's sheet (`/media/<provider>/<id>`)
  → Retour lands on the resolution screen with its queue intact. A screen over a screen is pushed and popped today
  (R71 `screens.py`), so it should hold; **if it does not without the navigation lot's stacking: STOP, told, nothing
  built around it.**
- **Points ≈ 13.** The card's body opens the sheet, « Choisir » alone carries `data-resolve` (≈ 12 lines, 3); the stale
  comment rewritten (1); `BUGS.md` per order 57 — escaped from « la carte-geste », family « one element, different
  behaviours », repaired by the rule (2); R-conformity-q, the poster touched on EVERY surface drawing one, expecting
  the sheet, the operator's declared exceptions listed — none today (4); the finger walk of Retour (2); the RESUME (1).
- **Readers.** `decision.py` (R57, « three ways out »), `resolution_card.py`, `resolution_window.py`, `two_picks.py`
  — every hold that taps the card to pick is re-aimed at « Choisir », said out loud.

## Red today

R-conformity-q: on `acq-resolution-tie`, the poster picks instead of opening the sheet — falls; every other surface's
poster read green (the rule's own proof that it reads).

## Mutation

Put `data-resolve` back on the card → falls by name.

## Oracle: states that diverge, declared by name

The resolution states (built by script), if the markup's change moves geometry — accepted by name.

## Commit

`fix(maquette-conformity): a candidate's poster opens its sheet — only « Choisir » picks`
