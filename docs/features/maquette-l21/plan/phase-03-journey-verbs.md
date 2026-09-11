# Phase 3 — « Remettre en file » and « Re-scraper » (B-302)

§20: a blocked tunnel « reprend là où il s'est arrêté, par l'opérateur ». The journey sheet IS the
tunnel as the operator sees it, and it offers one action today — « Voir la fiche ».

## The rule FIRST

`frontend/maquette/harness/journey_verbs.py` — new. What it reads:

1. **The journey panel offers both verbs**, raised by a finger, hit-tested.
2. **The OPERATION IS CALLED** — on the NETWORK, one per verb, `requeueJourney` and
   `rescrapeJourney`, told apart.
3. **The journey's STAGES MOVE** — a `now` pip where a `todo` was — **read on the LAYER's answer,
   never on a literal.** `panel-journey.ts` reads its stages from the query cache
   (`["/api/acquisition/journeys", subject]`) since L19, so the MOCK has to move them. A rule
   asserting a hard-coded stage list is green over a build that called nothing.
4. **Under the busy scenario**: queued and said. **Never a 409** — the backend answers one, the
   interface must not show it (demand 2), and the mock answers the queued state instead.

**Seen red how**: the verbs do not exist on `main`; holds 1–4 fail with no mutation needed.

## The move

- **New file** `features/acquisition/journey-verbs.ts`.
- `features/acquisition/panel-journey.ts` (88 non-blank) gains the two actions in its `actions`
  block, and its header sentence — « the verbs … belong to the lot that wires the tunnel's verbs »
  — is corrected in the same commit, because it has just stopped being true.
- Copy under `panels.journey.*` in `i18n/fr.json`, beside `metaBefore`, `provenanceNote`,
  `seeSheet`.

⚠ **« Re-scraper » here is NOT the media sheet's metadata re-scrape.** `fr.json` already holds
« Re-scraper les métadonnées » twice, and that is another subject (B-302 says so). Two keys, two
sentences; the rule reads the journey's own and would pass over the wrong one if it grepped the
tree instead of the panel.

## Gate

`run.sh --contracts`; the rule green; the oracle diverging ONLY on the journey panel's states,
accepted with « B-302 / §20 / DOIT-3 » (D8).

## Commit

`feat(maquette-l21): a tunnel is resumed from where the operator looks at it`
