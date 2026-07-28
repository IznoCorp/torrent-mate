# Phase 02 — m15 : taxons d'erreur SearchOutcome (D4)

**Goal**: une clé tracker cassée devient un verdict `tracker_auth` terminal au lieu d'un
`trackers_unavailable` perpétuel ; le label search-stage `circuit_open` redevient exact.

## Surface

| Fichier                                                     | Action                                                                                                                                                                                                                                                               |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `personalscraper/acquire/_dedup.py` (SearchOutcome)         | + `errors: dict[str, str]` (nom → `auth`\|`circuit`\|`api`) ; `errored_names` conservé (dérivable, ne pas casser les consommateurs)                                                                                                                                  |
| `personalscraper/api/tracker/_registry.py`                  | `search_candidates` remplit le taxon par tracker (TrackerAuthError→auth, CircuitOpenError→circuit, reste→api) — les deux boucles except de #322 restent fail-soft                                                                                                    |
| `personalscraper/acquire/orchestrator.py` (`_search_chain`) | tous `auth` ⇒ (`terminal`,`tracker_auth`,None) ; tous `circuit` ⇒ (`retryable`,`circuit_open`,None) ; mélange/`api` ⇒ `trackers_unavailable` (inchangé). Les docstrings « defense-in-depth only » + la note de #322 tombent.                                         |
| tests                                                       | rouge-avant : registry avec les deux trackers en TrackerAuthError ⇒ verdict tracker_auth terminal (abandon guardé + WantedAbandoned) ; tous circuit ⇒ circuit_open ; mélange ⇒ trackers_unavailable ; grab() : dispositions byte-identiques (tests pinnés existants) |

## Règles

- `SEARCH_OUTCOMES`/`INCONCLUSIVE_OUTCOMES` inchangés (les 9 outcomes existent déjà — on rend
  atteignable ce qui était mort, on ne crée rien).
- États UI intacts : `tracker_auth` → abandon (terminal), `circuit_open` ∈ INCONCLUSIVE → non_verifie.
- Le set-equality test du mapping service doit passer inchangé.

## Gate

pytest tests/acquire/ tests/unit -k "tracker or torznab or search" -q vert ; mypy 0 ; rouge-avant vérifié ;
`rg -n "m15|defense-in-depth" -t py personalscraper/` ⇒ 0 marqueur restant.
