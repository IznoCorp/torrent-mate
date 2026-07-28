# Phase 03 — M6 + m23 : I/O borné + registry fermé (D1 + D5-m23)

**Goal**: le POST /followed ne peut plus bloquer ~2 min sur une panne provider ; le registry
par requête est fermé proprement. Les TODO « M6 » et « m23 » tombent.

## Surface

| Fichier                                                                                                                                                                                 | Action                                                                                                                                                                                                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| le seam de construction (retrouver : `rg -n "M6\|m23" -t py personalscraper/web/`) — `web/acquisition/service.py::_build_provider_clients` + `cli_helpers`/factory selon le vrai chemin | paramètre d'override de `TransportPolicy` (attempts=1, timeouts existants) appliqué aux DEUX clients métadonnées construits pour l'enrichissement — PAS de mutation d'attributs privés ; si le constructeur ne l'expose pas, l'exposer proprement (petit changement de factory, mypy strict) |
| même seam                                                                                                                                                                               | context-manager / try-finally : `registry.close()` en fin d'enrichissement et de search web (m23)                                                                                                                                                                                            |
| tests                                                                                                                                                                                   | rouge-avant chronométré : providers fakes qui dorment ⇒ POST borné ≤ 30 s (hooks de sleep injectés, pas de vrai sleep long en CI — cap simulé) ; close() appelé (spy) sur tous les chemins incl. exception                                                                                   |

## Gate

pytest tests/unit/web/ -q vert ; mypy 0 ; rouge-avant vérifié ; `rg -n "M6 — OPEN|m23" -t py personalscraper/` ⇒ 0.
