# Phase 01 — Client + subscriber + câblage + tests

**Goal**: DESIGN D1+D2+D3 — l'événement porte le dossier, le client rafraîchit la bonne
section, le subscriber est câblé fail-soft.

## Surface

| Fichier                                  | Action                                                                                                                                                                                                                                                   |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `personalscraper/dispatch/events.py`     | `ItemDispatched.target_path: Path \| None = None` (additif)                                                                                                                                                                                              |
| `personalscraper/dispatch/dispatcher.py` | remplir `target_path` aux 3 émissions (moved/merged/replaced)                                                                                                                                                                                            |
| `personalscraper/api/plex.py`            | **NEW** — PlexClient (sections lazy-cachées, refresh par plus long préfixe, token jamais loggé, timeouts courts, 1 tentative)                                                                                                                            |
| `personalscraper/subscribers/plex.py`    | **NEW** — PlexSubscriber (modèle TelegramSubscriber : fail-soft absolu)                                                                                                                                                                                  |
| `personalscraper/config.py`              | `PLEX_URL` (défaut localhost:32400) + `PLEX_TOKEN` (None ⇒ non câblé)                                                                                                                                                                                    |
| câblage                                  | mêmes frontières que TelegramSubscriber (retrouver ses sites : rg -n "TelegramSubscriber" -t py)                                                                                                                                                         |
| tests                                    | subscriber (bon dossier/bonne section, multi-sections par préfixe), fail-soft (down/401/section introuvable ⇒ dispatch OK + warning), token-jamais-loggé (scan des records), pas-de-câblage sans token, target_path rempli par le dispatcher (3 actions) |

## Gate

pytest tests/ ciblés + make test FULL vert ; mypy 0 ; ruff clean ; rouge-avant sur le
subscriber (avant câblage, l'événement ne déclenche rien).
