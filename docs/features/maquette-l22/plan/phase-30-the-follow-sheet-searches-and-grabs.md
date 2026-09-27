# Phase 30 — The follow sheet searches live, and grabs through the per-follow operation

**Born 2026-09-27 from the coherence triage's F6 + F42**, one phase, **cut at its opening if above 15**.

**Opening measure (estimate — RE-MEASURED at the opening):**

- **F6**: the follow sheet's « Chercher maintenant » sends `searchForFollow`, reads `found`, and says « aucun torrent
  trouvé » when it is 0, the count otherwise (round 7: what was not found reads on the follow, and a live search confirms
  it). The `searchStarted` toast retires (it pointed at the removed « Cherché, rien trouvé » card). `harness/panel.py`
  (it requires « Recherche lancée ») is RE-AIMED OUT LOUD.
- **F42**: « Récupérer maintenant » sends the per-follow grab with the backend's meaning — `POST /followed/{id}/grab`, no
  body, 202 with `run_uid` (`personalscraper/web/routes/acquisition_triggers.py`); `grabForFollow` re-declared to match.
  The release picker gets an operation carrying the chosen release, **filed as a demand**. `takeQueued` retires from the
  contract, the mocks and R225; the register is regenerated. L18's row L is re-aimed by L18.
- **Points ≈ 16** (F6 ≈ 8, F42 ≈ 8) → **likely cut at the opening** into the search and the grab.

## Red today

A rule holds the network call and the zero sentence; R225 re-aimed onto the per-follow grab.

## Mutation

Toast without sending → falls; drop the zero sentence → falls; send `takeQueued` again → the grab hold falls.

## Commit

`feat(maquette-l22): the follow sheet searches live and grabs through its own operation`
